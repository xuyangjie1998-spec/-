import os, json, re, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional
from core.error_codes import ErrorCode, safe_error_message, error_response, success_response

from core.ini_parser import IniParser

from core.config import PROJECT_ROOT

logger = logging.getLogger('San7ModMaker')

__all__ = ['San7ModMakerCore']

class San7ModMakerCore:
    """MOD制作器 - 核心数据 (武将/兵种/物品/技能/特性)"""

    # ============================================================
    # API: 武将编辑
    # ============================================================

    def api_load_generals(self) -> dict:
        """加载所有武将数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        general_path = os.path.join(self.game_path, "Setting", "General01.ini")
        if not os.path.exists(general_path):
            return {"success": False, "message": "未找到General01.ini，请先解包Setting资源"}

        parser = IniParser()
        parser.load(general_path)
        sections = parser.get_all_sections("GENERAL")
        # 反向映射：游戏INI字段名 → Schema内部名
        entries = [self.field_mapper.entry_to_schema("general", dict(s.entries)) for s in sections]

        self._general_cache = entries
        return {
            "success": True,
            "count": len(entries),
            "data": entries,
        }

    def api_save_generals(self, data: list) -> dict:
        """保存武将数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        general_path = os.path.join(self.game_path, "Setting", "General01.ini")

        # 校验
        self.validator.clear()
        self.validator.check_duplicate_ids(data, "general", "General01.ini")
        self.validator.check_missing_ids(data, "general", "General01.ini")
        self.validator.check_value_ranges(data, "general", "General01.ini")

        if self.validator.has_errors():
            return {
                "success": False,
                "message": "数据校验未通过",
                "errors": self.validator.to_dict_list(),
            }

        # 校验通过后自动备份
        if self.backup_mgr:
            self.backup_mgr.backup_file(general_path)
        else:
            logger.warning("备份管理器未初始化，跳过备份")

        # 检测编号变更，同步关联文件
        old_cache = {int(g.get("No", 0)): g for g in self._general_cache}
        num_changes = []  # [(old_no, new_no), ...]
        for entry in data:
            new_no = int(entry.get("No", 0))
            # 在旧缓存中查找同名武将（通过原始No匹配）
            # 由于顺序可能改变，我们用Name匹配
            for old_g in self._general_cache:
                old_no = int(old_g.get("No", 0))
                if old_no == new_no:
                    continue
                # 找到同名但编号不同的情况
                if old_g.get("Name") == entry.get("Name") and old_no != new_no and old_no in old_cache:
                    num_changes.append((old_no, new_no))
                    break

        # 编号变更同步
        sync_results = []
        for old_no, new_no in num_changes:
            sync_results.append(self._sync_general_no_in_related(old_no, new_no))

        # 正向映射：Schema内部名 → 游戏INI字段名
        mapped_data = self.field_mapper.entries_to_game("general", data)

        # 写入（带缓存回滚保护）
        old_cache = self._general_cache.copy() if self._general_cache else []
        try:
            parser = IniParser()
            parser.load(general_path)
            # 清空现有GENERAL section
            # 写入新数据
            parser.replace_sections("GENERAL", mapped_data, "No")

            parser.save(general_path)
            self._general_cache = data
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            self._general_cache = old_cache
            return {"success": False, "message": f"保存失败: {str(e)}"}

        # 同步TermText
        for entry in data:
            name = entry.get("Name", "")
            if name and self.term_text.is_loaded():
                self.term_text.allocate_new_id(name)
        self.term_text.save()

        result = {"success": True, "message": f"保存成功，共{len(data)}条武将数据"}
        if sync_results:
            result["num_sync"] = sync_results
        return result

    def api_new_general(self) -> dict:
        """新增武将 - 联动创建 DefSkill / General02 / TermText 条目"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "general_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        template = dict(schema["new_entry_template"])

        # 自动分配空编号
        used_ids = {int(g.get("No", 0)) for g in self._general_cache}
        new_id = 0
        for i in range(1, 10000):
            if i not in used_ids:
                new_id = i
                break

        template["No"] = new_id
        template["Name"] = f"新武将_{new_id:04d}"

        # 联动: TermText
        if self.term_text.is_loaded():
            self.term_text.allocate_new_id(template["Name"])

        # 联动: DefSkill.ini - 在第一个 GenSkill 组中创建空条目
        linkage_info = self._create_defskill_entry(new_id)
        # 联动: General02.ini - 创建默认出生地
        g2_info = self._create_general02_entry(new_id)

        return {
            "success": True,
            "data": template,
            "new_id": new_id,
            "linkage": {
                "term_text": template["Name"],
                "defskill": linkage_info,
                "general02": g2_info,
            }
        }

    def _create_defskill_entry(self, general_no: int) -> dict:
        """为新增武将创建 DefSkill.ini 空条目"""
        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if not os.path.exists(defskill_path):
            return {"created": False, "reason": "DefSkill.ini 不存在"}
        try:
            from core.ini_parser import IniParser
            if self.backup_mgr:
                self.backup_mgr.backup_file(defskill_path)
            parser = IniParser()
            parser.load(defskill_path)
            # 找到第一个 GenSkill 组
            gen_skill_sections = [s for s in parser.sections if s.name.startswith("GenSkill")]
            target = gen_skill_sections[0] if gen_skill_sections else parser.add_section("GenSkill01")
            # 添加空技能条目
            target.set(str(general_no), "")
            parser.save(defskill_path)
            return {"created": True, "section": target.name, "general_no": general_no}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return {"created": False, "reason": str(e)}

    def _create_general02_entry(self, general_no: int) -> dict:
        """为新增武将创建 General02.ini 默认出生地"""
        g2_path = os.path.join(self.game_path, "Setting", "General02.ini")
        if not os.path.exists(g2_path):
            return {"created": False, "reason": "General02.ini 不存在"}
        try:
            from core.ini_parser import IniParser
            if self.backup_mgr:
                self.backup_mgr.backup_file(g2_path)
            parser = IniParser()
            parser.load(g2_path)
            section = parser.add_section("GENERAL")
            section.set("No", str(general_no))
            for i in range(1, 11):
                section.set(f"City{i}", "0, 0")
            parser.save(g2_path)
            return {"created": True, "general_no": general_no}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return {"created": False, "reason": str(e)}

    def api_clone_general(self, source_no: int) -> dict:
        """克隆武将 - 联动创建 DefSkill / General02 / TermText 条目"""
        source = None
        for g in self._general_cache:
            if int(g.get("No", 0)) == source_no:
                source = dict(g)
                break

        if not source:
            return {"success": False, "message": f"未找到编号 {source_no} 的武将"}

        # 分配新编号
        used_ids = {int(g.get("No", 0)) for g in self._general_cache}
        new_id = 0
        for i in range(1, 10000):
            if i not in used_ids:
                new_id = i
                break

        source["No"] = new_id
        source["Name"] = f"{source.get('Name', '克隆')}_副本"

        # 联动: TermText
        if self.term_text.is_loaded():
            self.term_text.allocate_new_id(source["Name"])

        # 联动: DefSkill.ini - 复制源武将的技能
        linkage_info = self._clone_defskill_entry(source_no, new_id)
        # 联动: General02.ini
        g2_info = self._clone_general02_entry(source_no, new_id)

        return {
            "success": True,
            "data": source,
            "new_id": new_id,
            "linkage": {
                "term_text": source["Name"],
                "defskill": linkage_info,
                "general02": g2_info,
            }
        }

    def _clone_defskill_entry(self, source_no: int, new_no: int) -> dict:
        """克隆武将的 DefSkill.ini 条目"""
        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if not os.path.exists(defskill_path):
            return {"created": False, "reason": "DefSkill.ini 不存在"}
        try:
            from core.ini_parser import IniParser
            if self.backup_mgr:
                self.backup_mgr.backup_file(defskill_path)
            parser = IniParser()
            parser.load(defskill_path)
            cloned = False
            for section in parser.sections:
                if str(source_no) in section.entries:
                    section.set(str(new_no), section.entries[str(source_no)])
                    cloned = True
            if cloned:
                parser.save(defskill_path)
            return {"created": cloned, "general_no": new_no}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return {"created": False, "reason": str(e)}

    def _clone_general02_entry(self, source_no: int, new_no: int) -> dict:
        """克隆武将的 General02.ini 条目"""
        g2_path = os.path.join(self.game_path, "Setting", "General02.ini")
        if not os.path.exists(g2_path):
            return {"created": False, "reason": "General02.ini 不存在"}
        try:
            from core.ini_parser import IniParser
            if self.backup_mgr:
                self.backup_mgr.backup_file(g2_path)
            parser = IniParser()
            parser.load(g2_path)
            source_section = None
            for s in parser.get_all_sections("GENERAL"):
                if s.get("No") == str(source_no):
                    source_section = s
                    break
            if source_section:
                new_section = parser.add_section("GENERAL")
                new_section.set("No", str(new_no))
                for key in ["City1", "City2", "City3", "City4", "City5",
                            "City6", "City7", "City8", "City9", "City10"]:
                    new_section.set(key, source_section.get(key, "0, 0"))
                parser.save(g2_path)
                return {"created": True, "general_no": new_no}
            return {"created": False, "reason": f"未找到源武将 {source_no} 的出生地数据"}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return {"created": False, "reason": str(e)}

    def _sync_general_no_in_related(self, old_no: int, new_no: int) -> dict:
        """武将编号变更后，同步更新所有关联文件中的编号引用"""
        if not self.game_path:
            return {"synced": False, "reason": "未设置游戏目录"}

        results = {"old_no": old_no, "new_no": new_no, "files": {}}

        # 1. DefSkill.ini - 更新 GenSkill 组中的编号
        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if os.path.exists(defskill_path):
            if self.backup_mgr:
                self.backup_mgr.backup_file(defskill_path)
            try:
                parser = IniParser()
                parser.load(defskill_path)
                for section in parser.sections:
                    if section.name.startswith("GenSkill"):
                        if str(old_no) in section.entries:
                            section.set(str(new_no), section.entries[str(old_no)])
                            del section.entries[str(old_no)]
                            results["files"]["DefSkill.ini"] = "updated"
                parser.save(defskill_path)
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                results["files"]["DefSkill.ini"] = f"error: {e}"

        # 2. General02.ini - 更新出生地
        g2_path = os.path.join(self.game_path, "Setting", "General02.ini")
        if os.path.exists(g2_path):
            if self.backup_mgr:
                self.backup_mgr.backup_file(g2_path)
            try:
                parser = IniParser()
                parser.load(g2_path)
                for section in parser.get_all_sections("GENERAL"):
                    if section.get("No") == str(old_no):
                        section.set("No", str(new_no))
                        results["files"]["General02.ini"] = "updated"
                parser.save(g2_path)
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                results["files"]["General02.ini"] = f"error: {e}"

        # 3. Nation.ini - 更新势力武将引用
        nation_path = os.path.join(self.game_path, "Setting", "Nation.ini")
        if os.path.exists(nation_path):
            if self.backup_mgr:
                self.backup_mgr.backup_file(nation_path)
            try:
                parser = IniParser()
                parser.load(nation_path)
                for section in parser.sections:
                    if section.name == "GENERAL" or section.name == "NATION":
                        for key, value in list(section.entries.items()):
                            if str(old_no) in value:
                                section.set(key, value.replace(str(old_no), str(new_no)))
                                results["files"]["Nation.ini"] = "updated"
                parser.save(nation_path)
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                results["files"]["Nation.ini"] = f"error: {e}"

        # 4. Thing.ini - 更新物品关联（专属武器等）
        thing_path = os.path.join(self.game_path, "Setting", "Thing.ini")
        if os.path.exists(thing_path):
            if self.backup_mgr:
                self.backup_mgr.backup_file(thing_path)
            try:
                parser = IniParser()
                parser.load(thing_path)
                for section in parser.get_all_sections("THING"):
                    if section.get("General") == str(old_no):
                        section.set("General", str(new_no))
                        results["files"]["Thing.ini"] = "updated"
                parser.save(thing_path)
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                results["files"]["Thing.ini"] = f"error: {e}"

        # 5. City01~City10.ini - 更新城池占领/太守/军师引用
        for period in range(1, 11):
            period_str = f"{period:02d}"
            city_path = os.path.join(self.game_path, "Setting", f"City{period_str}.ini")
            if not os.path.exists(city_path):
                continue
            if self.backup_mgr:
                self.backup_mgr.backup_file(city_path)
            try:
                parser = IniParser()
                parser.load(city_path)
                updated = False
                for section in parser.get_all_sections("CITY"):
                    for field in ["Lord", "Chief", "Adviser"]:
                        val = str(section.get(field, "")).strip()
                        if val == str(old_no):
                            section.set(field, str(new_no))
                            updated = True
                if updated:
                    parser.save(city_path)
                    results["files"][f"City{period_str}.ini"] = "updated"
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                results["files"][f"City{period_str}.ini"] = f"error: {e}"

        results["synced"] = True
        return results

    def api_delete_general(self, general_no: int) -> dict:
        """删除武将 - 联动清理 DefSkill / General02 / TermText / Nation"""
        cascaded = {}

        # 1. 清理 DefSkill.ini
        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if os.path.exists(defskill_path):
            if self.backup_mgr:
                self.backup_mgr.backup_file(defskill_path)
            try:
                parser = IniParser()
                parser.load(defskill_path)
                for section in parser.sections:
                    if section.name.startswith("GenSkill"):
                        if str(general_no) in section.entries:
                            del section.entries[str(general_no)]
                            cascaded["DefSkill.ini"] = "removed"
                parser.save(defskill_path)
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                cascaded["DefSkill.ini"] = f"error: {e}"

        # 2. 清理 General02.ini
        g2_path = os.path.join(self.game_path, "Setting", "General02.ini")
        if os.path.exists(g2_path):
            if self.backup_mgr:
                self.backup_mgr.backup_file(g2_path)
            try:
                parser = IniParser()
                parser.load(g2_path)
                for section in list(parser.get_all_sections("GENERAL")):
                    if section.get("No") == str(general_no):
                        parser.sections.remove(section)
                        cascaded["General02.ini"] = "removed"
                parser.save(g2_path)
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                cascaded["General02.ini"] = f"error: {e}"

        # 3. 清理 TermText.ini
        if self.term_text.is_loaded():
            general_name = ""
            for g in self._general_cache:
                if int(g.get("No", 0)) == general_no:
                    general_name = g.get("Name", "")
                    break
            if general_name:
                self.term_text.release_by_name(general_name)
                cascaded["TermText.ini"] = "removed"

        # 4. 清理 Nation.ini 中的武将引用
        nation_path = os.path.join(self.game_path, "Setting", "Nation.ini")
        if os.path.exists(nation_path):
            if self.backup_mgr:
                self.backup_mgr.backup_file(nation_path)
            try:
                parser = IniParser()
                parser.load(nation_path)
                for section in parser.sections:
                    if section.name == "GENERAL" or section.name == "NATION":
                        for key, value in list(section.entries.items()):
                            if str(general_no) in value.split(","):
                                # 移除该编号，保留其他编号
                                vals = [v.strip() for v in value.split(",") if v.strip() != str(general_no)]
                                section.set(key, ",".join(vals) if vals else "")
                                cascaded["Nation.ini"] = "updated"
                parser.save(nation_path)
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                cascaded["Nation.ini"] = f"error: {e}"

        # 5. 清理 City01~City10.ini 中的城池引用
        for period in range(1, 11):
            period_str = f"{period:02d}"
            city_path = os.path.join(self.game_path, "Setting", f"City{period_str}.ini")
            if not os.path.exists(city_path):
                continue
            if self.backup_mgr:
                self.backup_mgr.backup_file(city_path)
            try:
                parser = IniParser()
                parser.load(city_path)
                updated = False
                for section in parser.get_all_sections("CITY"):
                    for field in ["Lord", "Chief", "Adviser"]:
                        val = str(section.get(field, "")).strip()
                        if val == str(general_no):
                            section.set(field, "0")
                            updated = True
                if updated:
                    parser.save(city_path)
                    cascaded[f"City{period_str}.ini"] = "cleared"
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                cascaded[f"City{period_str}.ini"] = f"error: {e}"

        # 6. 清除内存缓存
        self._general_cache = [g for g in self._general_cache if int(g.get("No", 0)) != general_no]

        return {
            "success": True, 
            "message": f"武将 {general_no} 已删除",
            "count": len(self._general_cache),
            "cascaded": cascaded
        }

    def api_check_references(self) -> dict:
        """跨文件引用完整性检查"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        issues = []
        refs = {}  # 收集所有引用关系

        # 1. 加载武将列表
        general_ids = set()
        general_names = {}
        for g in self._general_cache:
            no = int(g.get("No", 0))
            general_ids.add(no)
            general_names[no] = g.get("Name", "")

        # 2. 检查 Nation.ini 引用
        nation_path = os.path.join(self.game_path, "Setting", "Nation.ini")
        if os.path.exists(nation_path):
            try:
                parser = IniParser()
                parser.load(nation_path)
                for s in parser.get_all_sections("NATION"):
                    lord = s.get("Lord", "")
                    if lord and lord != "0":
                        lord_no = int(lord)
                        refs.setdefault(f"general_{lord_no}", []).append(f"Nation.ini [NATION] Lord={lord}")
                        if lord_no not in general_ids:
                            issues.append({"type": "broken_ref", "file": "Nation.ini", "section": s.name,
                                           "field": "Lord", "value": lord, "detail": f"君主 #{lord} 不存在于 General01.ini"})
                    advisor = s.get("Advisor", "")
                    if advisor and advisor != "0":
                        adv_no = int(advisor)
                        refs.setdefault(f"general_{adv_no}", []).append(f"Nation.ini [NATION] Advisor={advisor}")
                        if adv_no not in general_ids:
                            issues.append({"type": "broken_ref", "file": "Nation.ini", "section": s.name,
                                           "field": "Advisor", "value": advisor, "detail": f"军师 #{advisor} 不存在于 General01.ini"})
                    # 检查 Cities 列表中的武将
                    cities = s.get("Cities", "")
                    for cid in cities.split(","):
                        cid = cid.strip()
                        if cid.isdigit() and int(cid) > 0:
                            cno = int(cid)
                            refs.setdefault(f"city_{cno}", []).append(f"Nation.ini [NATION] {s.get('Name','')}")
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                issues.append({"type": "error", "file": "Nation.ini", "detail": str(e)})

        # 3. 检查 Thing.ini 的武将引用
        thing_path = os.path.join(self.game_path, "Setting", "Thing.ini")
        if os.path.exists(thing_path):
            try:
                parser = IniParser()
                parser.load(thing_path)
                for s in parser.get_all_sections("THING"):
                    gen_no = s.get("General", "")
                    if gen_no and gen_no != "0" and gen_no != "-1":
                        try:
                            gn = int(gen_no)
                            refs.setdefault(f"general_{gn}", []).append(f"Thing.ini [THING] {s.get('Name','')}")
                            if gn not in general_ids:
                                issues.append({"type": "broken_ref", "file": "Thing.ini", "section": s.get("Name", ""),
                                               "field": "General", "value": gen_no, "detail": f"专属武将 #{gen_no} 不存在"})
                        except ValueError:
                            pass
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                issues.append({"type": "error", "file": "Thing.ini", "detail": str(e)})

        # 4. 检查 DefSkill.ini 引用
        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if os.path.exists(defskill_path):
            try:
                parser = IniParser()
                parser.load(defskill_path)
                for s in parser.sections:
                    for key in s.entries:
                        if key.isdigit():
                            kn = int(key)
                            refs.setdefault(f"general_{kn}", []).append(f"DefSkill.ini [{s.name}]")
                            if kn not in general_ids:
                                issues.append({"type": "broken_ref", "file": "DefSkill.ini", "section": s.name,
                                               "field": key, "value": key, "detail": f"武将 #{key} 不存在于 General01.ini"})
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                issues.append({"type": "error", "file": "DefSkill.ini", "detail": str(e)})

        # 5. 检查 General02.ini 引用
        g2_path = os.path.join(self.game_path, "Setting", "General02.ini")
        if os.path.exists(g2_path):
            try:
                parser = IniParser()
                parser.load(g2_path)
                g2_ids = set()
                for s in parser.get_all_sections("GENERAL"):
                    no = s.get("No", "")
                    if no:
                        g2_ids.add(int(no))
                        refs.setdefault(f"general_{int(no)}", []).append("General02.ini [GENERAL]")
                # 检查哪些武将没有 General02 条目
                for gid in general_ids:
                    if gid not in g2_ids:
                        issues.append({"type": "missing_entry", "file": "General02.ini",
                                       "detail": f"武将 #{gid} ({general_names.get(gid, '')}) 缺少出生地数据"})
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                issues.append({"type": "error", "file": "General02.ini", "detail": str(e)})

        # 6. 检查 DefSkill 缺失
        if os.path.exists(defskill_path):
            try:
                parser = IniParser()
                parser.load(defskill_path)
                all_ds_keys = set()
                for s in parser.sections:
                    for key in s.entries:
                        if key.isdigit():
                            all_ds_keys.add(int(key))
                for gid in general_ids:
                    if gid not in all_ds_keys:
                        issues.append({"type": "missing_entry", "file": "DefSkill.ini",
                                       "detail": f"武将 #{gid} ({general_names.get(gid, '')}) 缺少技能/特性数据"})
            except Exception as e:
                logger.warning(f"DefSkill引号校验失败: {e}")

        # 7. 统计引用关系
        ref_summary = {}
        for key, sources in refs.items():
            ref_summary[key] = {"count": len(sources), "sources": sources[:5]}  # 最多5个来源

        return {
            "success": True,
            "total_issues": len(issues),
            "issues": issues,
            "broken_refs": [i for i in issues if i["type"] == "broken_ref"],
            "missing_entries": [i for i in issues if i["type"] == "missing_entry"],
            "reference_summary": ref_summary,
            "general_count": len(general_ids),
        }

    # ============================================================
    # API: 技能/特性 (DefSkill.ini)
    # ============================================================
    def api_load_defskill(self) -> dict:
        """加载DefSkill.ini"""
        entries, err = self._load_ini_sections("DefSkill.ini", "DefSkill")
        if err is not None:
            return err
        return success_response({"data": entries, "count": len(entries)})

    def api_save_defskill(self, data: dict) -> dict:
        """保存DefSkill.ini"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if not os.path.exists(defskill_path):
            return {"success": False, "message": "未找到DefSkill.ini"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(defskill_path)

        try:
            parser = IniParser()
            parser.load(defskill_path)

            for section_name, entries_list in data.items():
                parser.replace_sections(section_name, entries_list, "No")

            parser.save(defskill_path)
            self._defskill_cache = data
            return success_response(message="DefSkill.ini 保存成功")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return {"success": False, "message": f"保存失败: {str(e)}"}

    def api_new_defskill_entry(self, general_no: str) -> dict:
        """在 DefSkill.ini 中为指定武将添加空条目"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if not os.path.exists(defskill_path):
            return {"success": False, "message": "未找到DefSkill.ini"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(defskill_path)
        parser = IniParser()
        parser.load(defskill_path)
        # 为所有 GenSkill/GenFeature section 添加此武将的空条目
        for section in parser.sections:
            section.set(str(general_no), "0")
        parser.save(defskill_path)
        self._defskill_cache = parser.get_all_entries()
        return {"success": True, "message": f"已为武将 {general_no} 添加 DefSkill 条目", "data": self._defskill_cache}

    def api_delete_defskill_entry(self, general_no: str) -> dict:
        """从 DefSkill.ini 中删除指定武将的条目"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if not os.path.exists(defskill_path):
            return {"success": False, "message": "未找到DefSkill.ini"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(defskill_path)
        parser = IniParser()
        parser.load(defskill_path)
        # 删除所有 section 中此武将的 key
        for section in parser.sections:
            if section.get(str(general_no)) is not None:
                section.entries.pop(str(general_no), None)
                section._modified_keys.add(str(general_no))
        parser.save(defskill_path)
        self._defskill_cache = parser.get_all_entries()
        return {"success": True, "message": f"已删除武将 {general_no} 的 DefSkill 条目", "data": self._defskill_cache}

    def api_delete_ini_item(self, file_path: str, section_name: str, id_field: str, item_id: str) -> dict:
        """通用INI条目删除 - 删除指定section中id_field=item_id的条目"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        # 路径安全校验：禁止路径遍历
        if '..' in file_path or os.path.isabs(file_path):
            return {"success": False, "message": "非法的文件路径"}
        full_path = os.path.join(self.game_path, file_path)
        # 二次确认：确保最终路径在 game_path 内
        if not os.path.realpath(full_path).startswith(os.path.realpath(self.game_path)):
            return {"success": False, "message": "非法的文件路径"}
        if not os.path.exists(full_path):
            return {"success": False, "message": f"未找到文件: {file_path}"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(full_path)
        parser = IniParser()
        parser.load(full_path)
        removed = False
        item_str = str(item_id)
        for section in list(parser.sections):
            if section.name == section_name:
                if str(section.get(id_field, "")) == item_str:
                    parser.sections.remove(section)
                    removed = True
                    break
        if not removed:
            return {"success": False, "message": f"未找到 {section_name} 中 {id_field}={item_id} 的条目"}
        parser.save(full_path)
        return {"success": True, "message": f"已删除 {section_name} #{item_id}"}

    # ============================================================
    # API: 兵种编辑
    # ============================================================
    def api_load_soldiers(self) -> dict:
        """加载所有兵种数据"""
        entries, err = self._load_ini_sections("Soldier.ini", "SOLDIER")
        if err is not None:
            return err
        self._soldier_cache = entries
        return success_response({"data": entries, "count": len(entries), "limit": 67, "over_limit": len(entries) > 67})

    def api_save_soldiers(self, data: list) -> dict:
        """保存兵种数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        soldier_path = os.path.join(self.game_path, "Setting", "Soldier.ini")

        self.validator.clear()
        self.validator.check_duplicate_ids(data, "soldier", "Soldier.ini")
        self.validator.check_value_ranges(data, "soldier", "Soldier.ini")
        self.validator.check_soldier_limit(len(data), "Soldier.ini")

        if self.validator.has_errors():
            return {
                "success": False,
                "message": "数据校验未通过",
                "errors": self.validator.to_dict_list(),
            }

        # 校验通过后自动备份
        if self.backup_mgr:
            self.backup_mgr.backup_file(soldier_path)
        else:
            logger.warning("备份管理器未初始化，跳过备份")

        # 缓存回滚保护：先保存旧缓存，写入失败时恢复
        old_cache = self._soldier_cache.copy() if self._soldier_cache else []
        try:
            parser = IniParser()
            parser.load(soldier_path)
            parser.replace_sections("SOLDIER", data, "No")
            parser.save(soldier_path)

            # 自动联动：检测新增兵种，自动创建兵符物品
            # 注意：必须在覆盖缓存之前计算 old_ids，否则永远检测不到新兵种
            old_ids = {int(s.get("No", 0)) for s in self._soldier_cache if s.get("No")}
            self._soldier_cache = data
            new_entries = [s for s in data if int(s.get("No", 0)) not in old_ids]
            linkages = []
            for entry in new_entries[:5]:
                sid = entry.get("No")
                sname = entry.get("Name", f"兵种{sid}")
                try:
                    thing_path = os.path.join(self.game_path, "Setting", "Thing.ini")
                    if os.path.exists(thing_path):
                        tp = IniParser()
                        tp.load(thing_path)
                        used = {int(t.get("No", 0)) for t in tp.sections if t.get("No")}
                        tid = 0
                        for i in range(900, 10000):
                            if i not in used:
                                tid = i
                                break
                        if tid:
                            sec = tp.add_section("THING")
                            sec["No"] = str(tid)
                            sec["Name"] = sname + "兵符"
                            sec["Type"] = "2"
                            sec["IsUsed"] = "1"
                            sec["Price"] = "100"
                            tp.save(thing_path)
                            if self.term_text.is_loaded():
                                self.term_text.allocate_new_id(sname + "兵符")
                            linkages.append(f"兵符已创建(No={tid})")
                except Exception as e:
                    logger.error(f"操作失败: {e}", exc_info=True)
                    linkages.append(f"兵符创建失败: {e}")

            result = {"success": True, "message": f"保存成功，共{len(data)}条兵种数据", "count": len(data)}
            if linkages:
                result["linkages"] = linkages
                result["message"] += " | " + "; ".join(linkages)
            return result
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            self._soldier_cache = old_cache
            return {"success": False, "message": f"保存失败: {str(e)}"}

    def api_new_soldier(self) -> dict:
        """新增兵种（含ObjID自动分配 + OBD模型联动）"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "soldier_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        template = dict(schema["new_entry_template"])
        used_ids = {int(s.get("No", 0)) for s in self._soldier_cache}
        new_id = 0
        for i in range(1, 10000):
            if i not in used_ids:
                new_id = i
                break

        # 自动分配 ObjID：查找 OBD 中空闲的 Sequence
        obj_id = 0
        try:
            self.obd_parser.load("bfsoldier")
            existing_objs = self.obd_parser.get_all_sequences()
            # ObjID = Sequence % 100, 从 1 开始查找
            used_obj_ids = {s % 100 for s in existing_objs}
            for oid in range(1, 100):
                if oid not in used_obj_ids:
                    obj_id = oid
                    break
        except Exception as e:
            logger.warning(f"读取OBJ ID失败: {e}")
            obj_id = new_id % 100  # 回退方案

        template["No"] = new_id
        template["Name"] = f"新兵种_{new_id:04d}"
        template["ObjID"] = obj_id

        if self.term_text.is_loaded():
            self.term_text.allocate_new_id(template["Name"])

        # 自动在 OBD 中创建模型条目
        linkage = None
        try:
            self.obd_parser.load("bfsoldier")
            seq = self.obd_parser.find_free_sequence()
            obj = OBDObject()
            obj.sequence = seq
            obj.name = template["Name"]
            obj.space = (0, 0, 0)
            self.obd_parser.objects.append(obj)
            self.obd_parser.save("bfsoldier", self.obd_parser.objects)
            template["ObjID"] = seq % 100
            linkage = f"OBD模型已创建(Sequence={seq}, ObjID={seq % 100})"
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            linkage = f"OBD模型创建失败: {e}"

        result = {"success": True, "data": template, "new_id": new_id}
        if linkage:
            result["linkage"] = linkage
        return result

    def api_delete_soldier(self, soldier_no: int) -> dict:
        """删除兵种 — 联动清理 Soldier.ini + OBD模型 + TermText + 兵符物品"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        soldier_no = int(soldier_no)

        # 1. 查找要删除的兵种
        target = None
        for s in self._soldier_cache:
            if int(s.get("No", 0)) == soldier_no:
                target = s
                break
        if not target:
            return {"success": False, "message": f"未找到兵种 No={soldier_no}"}

        soldier_name = target.get("Name", f"兵种#{soldier_no}")
        obj_id = int(target.get("ObjID", 0))
        linkage_results = []

        # 2. 备份 + 删除 Soldier.ini 条目
        soldier_path = os.path.join(self.game_path, "Setting", "Soldier.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(soldier_path)
        parser = IniParser()
        parser.load(soldier_path)
        removed = False
        for section in list(parser.sections):
            if section.name == "SOLDIER":
                if str(section.get("No", "")) == str(soldier_no):
                    parser.sections.remove(section)
                    removed = True
                    break
        if not removed:
            return {"success": False, "message": f"Soldier.ini 中未找到 No={soldier_no}"}
        parser.save(soldier_path)
        linkage_results.append("Soldier.ini 条目已删除")

        # 3. 清理 OBD 模型 (bfsoldier)
        if obj_id > 0:
            try:
                self.obd_parser.load("bfsoldier")
                # ObjID = Sequence % 100，需要找到对应的 Sequence
                for obj in list(self.obd_parser.objects):
                    if obj.sequence % 100 == obj_id:
                        self.obd_parser.objects.remove(obj)
                        self.obd_parser.save("bfsoldier")
                        linkage_results.append(f"OBD模型已删除(ObjID={obj_id}, Sequence={obj.sequence})")
                        break
                else:
                    linkage_results.append(f"OBD模型未找到(ObjID={obj_id})")
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                linkage_results.append(f"OBD清理失败: {e}")

        # 4. 清理 TermText (13000+No = 名称)
        if self.term_text.is_loaded():
            try:
                name_key = 13000 + soldier_no
                self.term_text.delete(name_key)
                linkage_results.append(f"TermText名称已删除(key={name_key})")
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                linkage_results.append(f"TermText清理失败: {e}")

        # 5. 清理关联的兵符物品 (Thing.ini 中 No=900+soldierNo 的兵符)
        try:
            thing_path = os.path.join(self.game_path, "Setting", "Thing.ini")
            if os.path.exists(thing_path):
                if self.backup_mgr:
                    self.backup_mgr.backup_file(thing_path)
                tp = IniParser()
                tp.load(thing_path)
                thing_removed = False
                for section in list(tp.sections):
                    if section.name == "THING":
                        if str(section.get("No", "")) == str(soldier_no):
                            tp.sections.remove(section)
                            thing_removed = True
                            break
                if thing_removed:
                    tp.save(thing_path)
                    linkage_results.append("兵符物品已删除(Thing.ini)")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            linkage_results.append(f"兵符清理失败: {e}")

        # 6. 更新缓存
        self._soldier_cache = [s for s in self._soldier_cache if int(s.get("No", 0)) != soldier_no]

        return {
            "success": True,
            "message": f"已删除兵种「{soldier_name}」#{soldier_no}",
            "linkage": linkage_results,
        }

    def api_get_soldier_obd_info(self, soldier_no: int) -> dict:
        """查询兵种的 OBD 模型绑定状态"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            # 读取 Soldier.ini 获取 ObjID
            path = os.path.join(self.game_path, "Setting", "Soldier.ini")
            if not os.path.exists(path):
                return {"success": False, "message": "未找到Soldier.ini"}
            parser = IniParser()
            parser.load(path)
            obj_id = None
            soldier_name = ""
            for s in parser.get_all_sections("SOLDIER"):
                if str(s.entries.get("No", "")) == str(soldier_no):
                    soldier_name = s.entries.get("Name", "")
                    obj_id_str = s.entries.get("ObjID", "0")
                    obj_id = int(obj_id_str) if obj_id_str else None
                    break
            if obj_id is None:
                return {"success": True, "soldier_no": soldier_no, "soldier_name": soldier_name,
                        "obj_id": None, "obd_linked": False, "message": "该兵种未设置ObjID"}

            # 检查 OBD 中是否存在对应模型
            self.obd_parser.load("bfsoldier")
            for obj in self.obd_parser.objects:
                if obj.sequence % 100 == obj_id:
                    return {"success": True, "soldier_no": soldier_no,
                            "soldier_name": soldier_name, "obj_id": obj_id,
                            "obd_linked": True, "obd_sequence": obj.sequence,
                            "obd_name": obj.name,
                            "message": f"OBD已绑定: Sequence={obj.sequence}, Name={obj.name}"}
            return {"success": True, "soldier_no": soldier_no, "soldier_name": soldier_name,
                    "obj_id": obj_id, "obd_linked": False,
                    "message": f"ObjID={obj_id} 但 OBD 中未找到对应模型"}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # API: 物品编辑
    # ============================================================
    def api_load_things(self) -> dict:
        """加载所有物品数据"""
        entries, err = self._load_ini_sections("Thing.ini", "THING")
        if err is not None:
            return err
        self._thing_cache = entries
        return success_response({"data": entries, "count": len(entries)})

    def api_save_things(self, data: list) -> dict:
        """保存物品数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        thing_path = os.path.join(self.game_path, "Setting", "Thing.ini")

        self.validator.clear()
        self.validator.check_duplicate_ids(data, "thing", "Thing.ini")
        self.validator.check_value_ranges(data, "thing", "Thing.ini")

        if self.validator.has_errors():
            return {
                "success": False,
                "message": "数据校验未通过",
                "errors": self.validator.to_dict_list(),
            }

        # 校验通过后自动备份
        if self.backup_mgr:
            self.backup_mgr.backup_file(thing_path)
        else:
            logger.warning("备份管理器未初始化，跳过备份")

        # 缓存回滚保护：先保存旧缓存，写入失败时恢复
        old_cache = self._thing_cache.copy() if self._thing_cache else []
        try:
            parser = IniParser()
            parser.load(thing_path)
            parser.replace_sections("THING", data, "No")
            parser.save(thing_path)

            # 自动联动：同步物品名称到 TermText (14000+No)
            if self.term_text.is_loaded():
                for entry in data:
                    tname = entry.get("Name", "")
                    tno = int(entry.get("No", 0))
                    if tname and tno > 0:
                        self.term_text.set_item_name(tno, tname)
                self.term_text.save()

            # 自动联动：检测新增物品，选择性添加到商店
            # 注意：必须在覆盖缓存之前计算 old_thing_ids，否则永远检测不到新物品
            old_thing_ids = {int(t.get("No", 0)) for t in self._thing_cache if t.get("No")}
            self._thing_cache = data
            new_things = [t for t in data if int(t.get("No", 0)) not in old_thing_ids]
            linkages = []
            for entry in new_things[:5]:
                tname = entry.get("Name", "")
                ttype = entry.get("Type", "0")
                if ttype in ("1", "2"):  # 消耗品(兵符)或武器，添加到商店
                    try:
                        city_path = os.path.join(self.game_path, "Setting", "CitySellItem.ini")
                        if os.path.exists(city_path):
                            cp = IniParser()
                            cp.load(city_path)
                            tid = entry.get("No")
                            # 添加到最后一项后面
                            last_section = cp.sections[-1] if cp.sections else None
                            if last_section:
                                new_sec = cp.add_section("CITY_SELL_ITEM")
                                new_sec["No"] = str(int(last_section.get("No", "0")) + 1)
                                new_sec["ItemID"] = str(tid)
                                new_sec["CityID"] = "1"
                                new_sec["IsUsed"] = "1"
                                cp.save(city_path)
                                linkages.append(f"{tname}已上架商店")
                    except Exception as e:
                        logger.error(f"操作失败: {e}", exc_info=True)
                        linkages.append(f"商店上架失败: {e}")

            result = {"success": True, "message": f"保存成功，共{len(data)}条物品数据", "count": len(data)}
            if linkages:
                result["linkages"] = linkages
                result["message"] += " | " + "; ".join(linkages)
            return result
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            self._thing_cache = old_cache
            return {"success": False, "message": f"保存失败: {str(e)}"}

    def api_new_thing(self) -> dict:
        """新增物品"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "thing_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        template = dict(schema["new_entry_template"])
        used_ids = {int(t.get("No", 0)) for t in self._thing_cache}
        new_id = 0
        for i in range(1, 10000):
            if i not in used_ids:
                new_id = i
                break

        template["No"] = new_id
        template["Name"] = f"新物品_{new_id:04d}"

        if self.term_text.is_loaded():
            self.term_text.set_item_name(new_id, template["Name"])
            self.term_text.set_item_desc(new_id, f"{template['Name']}的描述")

        return {"success": True, "data": template, "new_id": new_id}

    # ============================================================
    # API: ItemEnhance 合成配方
    # ============================================================
    def api_load_item_enhance(self) -> dict:
        """加载 ItemEnhance.ini 合成配方"""
        entries, err = self._load_ini_sections("ItemEnhance.ini", "ItemEnhance")
        if err is not None:
            return err
        return success_response({"data": entries, "count": len(entries)})

    def api_save_item_enhance(self, data: list) -> dict:
        """保存 ItemEnhance.ini"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", "ItemEnhance.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        try:
            parser = IniParser()
            parser.load(path)
            parser.replace_sections("ITEMENHANCE", data, "No")
            parser.save(path)
            return {"success": True, "message": f"保存成功，共{len(data)}个配方"}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return {"success": False, "message": f"保存失败: {str(e)}"}

    # ============================================================
    # API: 商店配置 (CitySellItem.ini / Thing.ini 中Sell字段)
    # ============================================================
    def api_load_store_config(self) -> dict:
        """加载商店售卖配置"""
        entries, err = self._load_ini_sections("StoreConfig.ini", "StoreConfig")
        if err is not None:
            return err
        return success_response({"data": entries, "count": len(entries)})

    def api_save_store_config(self, data) -> dict:
        """保存商店售卖配置 - 接受 list 或 dict 格式"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", "CitySellItem.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        try:
            parser = IniParser()
            if os.path.exists(path):
                parser.load(path)
            section = parser.get_section("CITYSELLITEM")
            if section:
                section.entries.clear()
                section._modified_keys = set()
            else:
                section = parser.add_section("CITYSELLITEM")
            if isinstance(data, list):
                for entry in data:
                    city_name = entry.get("name", entry.get("city", ""))
                    items = entry.get("items", "")
                    section.set(str(city_name), str(items))
            else:
                for key, value in data.items():
                    section.set(str(key), str(value))
            parser.save(path)
            return success_response(message="商店配置保存成功")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return {"success": False, "message": f"保存失败: {str(e)}"}

    # ============================================================
    # API: 武将技/军师技 (BFMagic.ini / SFMagic.ini)
    # ============================================================
    def api_load_skills(self) -> dict:
        """加载技能数据（BFMagic.ini=武将技, SFMagic.ini=军师技）"""
        entries, err = self._load_ini_sections("Skill.ini", "Skill")
        if err is not None:
            return err
        return success_response({"data": entries, "count": len(entries)})

    def api_save_skills(self, data: list) -> dict:
        """保存技能数据（BFMagic.ini=武将技, SFMagic.ini=军师技）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        skill_entries = [d for d in data if d.get("_source") == "BFMagic.ini"]
        magic_entries = [d for d in data if d.get("_source") == "SFMagic.ini"]
        saved = 0
        for fname, entries in [("BFMagic.ini", skill_entries), ("SFMagic.ini", magic_entries)]:
            path = os.path.join(self.game_path, "Setting", fname)
            if entries:
                if self.backup_mgr:
                    self.backup_mgr.backup_file(path)
                parser = IniParser()
                parser.load(path)
                section_name = parser.sections[0].name if parser.sections else "BFMAGIC"
                clean_entries = []
                for entry in entries:
                    clean = {k: v for k, v in entry.items() if k not in ("SkillType", "_source")}
                    clean_entries.append(clean)
                parser.replace_sections(section_name, clean_entries, "No")
                parser.save(path)
                saved += len(entries)
        self._sync_term_text_names(data)
        return {"success": True, "message": f"保存成功，共{saved}个技能"}

    def api_new_skill(self) -> dict:
        """新增技能（默认武将技）"""
        return {
            "success": True,
            "data": {
                "No": 0, "Name": "新技能", "SkillType": "magic",
                "MP": 50, "ATK": 100, "Level": 1, "Range": 1,
                "Target": 0, "Damage": 1.0, "Effect": 0, "Element": 0,
                "IsUsed": 1, "Desc": "", "_source": "BFMagic.ini"
            }
        }

    # ============================================================
    # API: 必杀技 (SuperAtk.ini)
    # ============================================================
    def api_load_super_atk(self) -> dict:
        """加载必杀技数据"""
        entries, err = self._load_ini_sections("SuperAtk.ini", "SuperAtk")
        if err is not None:
            return err
        return success_response({"data": entries, "count": len(entries)})

    def api_save_super_atk(self, data: list) -> dict:
        """保存必杀技数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", "SuperAtk.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        try:
            parser = IniParser()
            parser.load(path)
            parser.replace_sections("SuperAtk", data, "No")
            parser.save(path)
            # 同步必杀技名称到 TermText
            if self.term_text.is_loaded():
                for entry in data:
                    name = entry.get("Name", "")
                    if name:
                        self.term_text.allocate_new_id(name)
                self.term_text.save()
            return {"success": True, "message": f"保存成功，共{len(data)}个必杀技"}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return {"success": False, "message": f"保存失败: {str(e)}"}

    def api_new_super_atk(self) -> dict:
        """新增必杀技"""
        return {"success": True, "data": {"NO": 0, "Name": "新必杀技", "HitRatio": 25, "General01": 1, "General02": 1, "IsUsed": 1}}

    # ============================================================
    # API: 特性定义 (GenSkill.ini / ArmySkill.ini / ArmyGroupSkill.ini)
    # ============================================================
    def api_load_gen_skills(self) -> dict:
        """加载所有特性定义"""
        entries, err = self._load_ini_sections("GenSkill.ini", "GenSkill")
        if err is not None:
            return err
        return success_response({"data": entries, "count": len(entries)})

    def api_save_gen_skills(self, data: dict) -> dict:
        """保存特性定义"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if not isinstance(data, dict):
            return {"success": False, "message": "数据格式错误，应为字典"}
        try:
            for fname, key in [("GenSkill.ini", "gen"), ("ArmySkill.ini", "army"), ("ArmyGroupSkill.ini", "group")]:
                if key not in data:
                    continue
                sections_data = data[key]
                if isinstance(sections_data, dict):
                    sections_data = sections_data.get("sections", [])
                if not isinstance(sections_data, list):
                    return {"success": False, "message": f"{key} 数据格式错误"}
                path = os.path.join(self.game_path, "Setting", fname)
                if not os.path.exists(path):
                    continue
                if self.backup_mgr:
                    self.backup_mgr.backup_file(path)
                parser = IniParser()
                parser.load(path)
                section_name = parser.sections[0].name if parser.sections else key.upper()
                clean_entries = []
                for entry in sections_data:
                    clean = {k: v for k, v in entry.items() if k != "_id"}
                    clean_entries.append(clean)
                parser.replace_sections(section_name, clean_entries, "No")
                parser.save(path)
            return success_response(message="特性定义保存成功")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return {"success": False, "message": f"保存失败: {str(e)}"}

    # ============================================================
    # API: TermText 文本管理
    # ============================================================

    def api_load_term_text_full(self) -> dict:
        """加载 TermText.ini 全部数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", "TermText.ini")
        if not os.path.exists(path):
            return success_response({"data": [], "count": 0})
        parser = IniParser()
        parser.load(path)
        entries = []
        for section in parser.sections:
            for key, value in section.entries.items():
                if re.match(r'^String\d+$', key):
                    no = key.replace("String", "").strip()
                    entries.append({"id": no, "key": key, "value": value})
        return success_response({"data": entries, "count": len(entries)})

    def api_save_term_text(self, data: list) -> dict:
        """保存 TermText.ini"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", "TermText.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        # 删除所有已有的 String 键（保留 StringCount 等非数字后缀键）
        for section in parser.sections:
            string_keys = [k for k in section.entries if re.match(r'^String\d+$', k)]
            for k in string_keys:
                del section.entries[k]
        # 定位 TermText section（优先按名称匹配，否则用第一个 section）
        target_section = None
        for s in parser.sections:
            if s.name.lower() == "termtext":
                target_section = s
                break
        if not target_section:
            target_section = parser.sections[0] if parser.sections else parser.add_section("TermText")
        # 写入所有条目
        for entry in data:
            string_id = entry.get("id", "")
            value = entry.get("value", "")
            if string_id and value:
                target_section.set(f"String{string_id}", value)
        parser.save(path)
        return {"success": True, "message": f"TermText保存成功，共{len(data)}条"}

    def api_get_thing_termtext(self, item_no: int) -> dict:
        """获取物品的 TermText 名称和描述"""
        if not self.term_text.is_loaded():
            return {"success": True, "name": "", "desc": ""}
        name = self.term_text.get_item_name(item_no)
        desc = self.term_text.get_item_desc(item_no)
        return {"success": True, "name": name, "desc": desc}

    def api_set_thing_termtext(self, item_no: int, name: str = "", desc: str = "") -> dict:
        """设置物品的 TermText 名称和描述，并保存"""
        if not self.term_text.is_loaded():
            return {"success": False, "message": "TermText 未加载"}
        if name:
            self.term_text.set_item_name(item_no, name)
        if desc:
            self.term_text.set_item_desc(item_no, desc)
        self.term_text.save()
        return success_response(message="物品文本已保存")

    # ============================================================
    # API: 等级经验/带兵数 (GenLV.ini)
    # ============================================================
    def api_load_gen_lv(self) -> dict:
        """加载 GenLV.ini"""
        entries, err = self._load_ini_sections("GenLV.ini", "GenLV")
        if err is not None:
            return err
        return success_response({"data": entries, "count": len(entries)})

    def api_save_gen_lv(self, data: list) -> dict:
        """保存 GenLV.ini"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", "GenLV.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("GenLV", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}级"}

    # ============================================================
    # API: 剧本年代 (Age.ini)
    # ============================================================
    def api_load_age(self) -> dict:
        """加载 Age.ini"""
        entries, err = self._load_ini_sections("Age.ini", "Age")
        if err is not None:
            return err
        return success_response({"data": entries, "count": len(entries)})

    def api_save_age(self, data: list) -> dict:
        """保存 Age.ini"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", "Age.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("AGE", data, "No")
        parser.save(path)
        return success_response(message="剧本年代保存成功")

    # ============================================================
    # API: 城池商店 (CitySellItem.ini)
    # ============================================================
    def api_load_city_sell_items(self) -> dict:
        """加载城池商店数据"""
        entries, err = self._load_ini_sections("CitySellItem.ini", "CitySellItem")
        if err is not None:
            return err
        return success_response({"data": entries, "count": len(entries)})

    def api_save_city_sell_items(self, data: list) -> dict:
        """保存城池商店数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", "CitySellItem.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        clean_entries = []
        for entry in data:
            clean = {"City": entry.get("City", "")}
            items = entry.get("items", [])
            for item in items:
                clean[f"item[{item['index']}]"] = item.get("item_id", "")
            for k, v in entry.items():
                if k not in ("City", "items"):
                    clean[k] = str(v)
            clean_entries.append(clean)
        parser.replace_sections("CITY_ITEM", clean_entries, "City")
        parser.save(path)
        # 同步到 storeConfig
        self._store_config_cache = data
        return {"success": True, "message": f"城池商店保存成功，{len(data)}个城池"}

    # ============================================================
    # API: 游戏文本 (GameText.ini)
    # ============================================================

    def api_load_game_text(self) -> dict:
        """加载游戏文本"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", "GameText.ini")
        if not os.path.exists(path):
            return {"success": True, "data": {}, "sections": []}
        parser = IniParser()
        parser.load(path)
        sections = []
        for s in parser.sections:
            sections.append({
                "name": s.name,
                "entries": dict(s.entries),
                "count": len(s.entries),
            })
        return {"success": True, "sections": sections, "count": len(sections)}

    def api_save_game_text(self, data: list) -> dict:
        """保存游戏文本"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", "GameText.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        # 保留原始section，更新entries
        for section_data in data:
            section = parser.get_section(section_data["name"])
            if not section:
                section = parser.add_section(section_data["name"])
            for k, v in section_data.get("entries", {}).items():
                section.set(k, str(v))
        parser.save(path)
        return success_response(message="游戏文本保存成功")

    # ============================================================
    # API: 武将出生地 (General02.ini)
    # ============================================================

    def api_load_general02(self) -> dict:
        """加载 General02.ini"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", "General02.ini")
        if not os.path.exists(path):
            return success_response({"data": [], "count": 0})
        parser = IniParser()
        parser.load(path)
        data = [dict(s.entries) for s in parser.get_all_sections("GENERAL")]
        return success_response({"data": data, "count": len(data)})

    def api_save_general02(self, data: list) -> dict:
        """保存 General02.ini"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", "General02.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("GENERAL", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}个武将出生地"}

    # ============================================================
    # API: 阵型 (Formation.ini)
    # ============================================================
    def api_load_formations(self) -> dict:
        """加载阵型数据"""
        entries, err = self._load_ini_sections("Formation.ini", "Formation")
        if err is not None:
            return err
        return success_response({"data": entries, "count": len(entries)})

    def api_save_formations(self, data: list) -> dict:
        """保存阵型数据"""
        err = self._save_ini_sections("Formation.ini", data, "FORMATION")
        if err is not None:
            return err
        self._sync_term_text_names(data)
        return {"success": True, "message": f"保存成功，共{len(data)}个阵型"}

    def api_new_formation(self) -> dict:
        """创建新阵型模板"""
        data = self._load_schema("formation_schema")
        template = data["new_entry_template"] if data and "new_entry_template" in data else {}
        if not template:
            template = {"No": 0, "Name": "新阵型", "SoldierCount": 5, "GenSkill1": 0, "GenSkill2": 0}
        return {"success": True, "data": template}

    # ============================================================
    # API: 官职 (Title.ini)
    # ============================================================
    def api_load_titles(self) -> dict:
        """加载官职数据"""
        entries, err = self._load_ini_sections("Title.ini", "Title")
        if err is not None:
            return err
        return success_response({"data": entries, "count": len(entries)})

    def api_save_titles(self, data: list) -> dict:
        """保存官职数据"""
        err = self._save_ini_sections("Title.ini", data, "TITLE")
        if err is not None:
            return err
        self._sync_term_text_names(data)
        return {"success": True, "message": f"保存成功，共{len(data)}个官职"}

    def api_new_title(self) -> dict:
        """新增官职"""
        return {
            "success": True,
            "data": {
                "No": 0, "Name": "新官职", "Rank": 9,
                "WStr": 0, "Int": 0, "HP": 0, "MP": 0,
                "GeneralCount": 1, "Exp": 100, "ATK": 0, "DEF": 0,
                "Speed": 0, "Skill": 0, "Upgrade": 0, "IsUsed": 1
            }
        }

    # ============================================================
    # API: 剧本 (Scenario.ini)
    # ============================================================
    def api_load_scenarios(self) -> dict:
        """加载剧本数据"""
        entries, err = self._load_ini_sections("Scenario.ini", "Scenario")
        if err is not None:
            return err
        return success_response({"data": entries, "count": len(entries)})

    def api_save_scenarios(self, data: list) -> dict:
        """保存剧本数据"""
        err = self._save_ini_sections("Scenario.ini", data, "SCENARIO")
        if err is not None:
            return err
        self._sync_term_text_names(data)
        return {"success": True, "message": f"保存成功，共{len(data)}个剧本"}

