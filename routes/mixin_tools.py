import os, json, re, shutil, base64, tempfile, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional

# 从 main.py 导入模块级常量
try:
    from main import WRITE_ROOT
except ImportError:
    import sys
    WRITE_ROOT = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger('San7ModMaker')

class San7ModMakerTools:
    """MOD制作器 - 工具集 (备份/校验/EXE/批量/差异/MOD)"""

    # API: 备份还原
    # ============================================================

    def api_backup_all(self) -> dict:
        """全量备份"""
        if not self.backup_mgr:
            return {"success": False, "message": "请先设置游戏目录"}
        backed = self.backup_mgr.backup_all_settings()
        return {"success": True, "message": f"备份完成，共{len(backed)}个文件", "count": len(backed)}

    def api_restore_all(self) -> dict:
        """一键还原"""
        if not self.backup_mgr:
            return {"success": False, "message": "请先设置游戏目录"}
        results = self.backup_mgr.restore_all()
        success_count = sum(1 for v in results.values() if v)
        return {"success": True, "message": f"还原完成，成功{success_count}个", "details": results}

    def api_cleanup_backups(self, keep_count: int = 10) -> dict:
        """清理旧备份，每个文件只保留最近N个"""
        if not self.backup_mgr:
            return {"success": False, "message": "请先设置游戏目录"}
        old_count = sum(len(v) for v in self.backup_mgr.index.values())
        self.backup_mgr.cleanup_old_backups(keep_count)
        new_count = sum(len(v) for v in self.backup_mgr.index.values())
        removed = old_count - new_count
        return {"success": True, "message": f"清理完成：移除 {removed} 个旧备份，保留 {new_count} 个", "removed": removed, "kept": new_count}

    def api_auto_backup_config(self, enabled: bool = None, interval_minutes: int = None) -> dict:
        """配置自动备份：设置是否启用和间隔时间"""
        config_path = os.path.join(WRITE_ROOT, "data", "auto_backup.json")
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception:
                pass
        if enabled is not None:
            config["enabled"] = bool(enabled)
        if interval_minutes is not None:
            config["interval_minutes"] = max(5, min(1440, int(interval_minutes)))
        config.setdefault("enabled", False)
        config.setdefault("interval_minutes", 30)
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return {"success": True, "config": config,
                "message": "自动备份已" + ("启用" if config["enabled"] else "禁用") +
                (f"，间隔{config['interval_minutes']}分钟" if config["enabled"] else "")}

    def api_auto_backup_status(self) -> dict:
        """获取自动备份状态"""
        config_path = os.path.join(WRITE_ROOT, "data", "auto_backup.json")
        config = {"enabled": False, "interval_minutes": 30}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config.update(json.load(f))
            except Exception:
                pass
        backup_count = self.backup_mgr.get_backup_count() if self.backup_mgr else 0
        last_backup = None
        if self.backup_mgr and self.backup_mgr.index:
            all_records = []
            for records in self.backup_mgr.index.values():
                all_records.extend(records)
            if all_records:
                last_backup = max(r["timestamp"] for r in all_records)
        return {"success": True, "config": config, "backup_count": backup_count,
                "last_backup": last_backup}

    def api_shp_batch_convert(self, source_dir: str, category: str = "Face") -> dict:
        """批量将PNG目录转换为SHP文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if not os.path.isdir(source_dir):
            return {"success": False, "message": f"源目录不存在: {source_dir}"}
        # 确定目标目录
        if category == "Face":
            target_dir = os.path.join(self.game_path, "Shape", "GenFace")
        elif category == "ThingIcon":
            target_dir = os.path.join(self.game_path, "Shape", "ThingIcon")
        elif category == "genhalf":
            target_dir = os.path.join(self.game_path, "Shape", "genhalf")
        else:
            target_dir = os.path.join(self.game_path, "Shape", category)
        os.makedirs(target_dir, exist_ok=True)
        # 扫描PNG文件
        results = []
        png_files = [f for f in os.listdir(source_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]
        for fname in sorted(png_files):
            src = os.path.join(source_dir, fname)
            try:
                # 从文件名提取编号
                num = ''.join(c for c in os.path.splitext(fname)[0] if c.isdigit())
                if not num:
                    results.append({"file": fname, "success": False, "message": "无法从文件名提取编号"})
                    continue
                out_path = self.shp_converter.image_to_shp(src, int(num), target_dir)
                results.append({"file": fname, "success": True, "output": out_path})
            except Exception as e:
                results.append({"file": fname, "success": False, "message": str(e)})
        success_count = sum(1 for r in results if r["success"])
        return {"success": True, "message": f"批量转换完成: {success_count}/{len(results)} 成功", "results": results, "total": len(results), "successCount": success_count}

    def api_batch_rename(self, file_type: str, name_prefix: str, start_no: int = 1) -> dict:
        """批量重命名武将/物品/兵种的 Name 字段"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        api_map = {
            "generals": ("api_load_generals", "api_save_generals"),
            "things": ("api_load_things", "api_save_things"),
            "soldiers": ("api_load_soldiers", "api_save_soldiers"),
            "skills": ("api_load_skills", "api_save_skills"),
            "formations": ("api_load_formations", "api_save_formations"),
            "titles": ("api_load_titles", "api_save_titles"),
        }
        if file_type not in api_map:
            return {"success": False, "message": f"不支持的文件类型: {file_type}，支持: {list(api_map.keys())}"}
        load_fn_name, save_fn_name = api_map[file_type]
        load_fn = getattr(self, load_fn_name)
        save_fn = getattr(self, save_fn_name)
        r = load_fn()
        if not r or not r.get("success"):
            return {"success": False, "message": "加载数据失败"}
        data = r.get("data", [])
        renamed = 0
        for i, entry in enumerate(data):
            new_name = f"{name_prefix}{start_no + i:04d}"
            old_name = entry.get("Name", "")
            entry["Name"] = new_name
            renamed += 1
        save_fn(data)
        return {"success": True, "message": f"批量重命名完成: {renamed} 条记录", "count": renamed, "prefix": name_prefix, "start": start_no}

    def api_dashboard_stats(self) -> dict:
        """获取首页仪表盘统计数据"""
        stats = {"game_path": self.game_path or ""}
        if not self.game_path:
            return {"success": True, "stats": stats}
        setting_dir = os.path.join(self.game_path, "Setting")
        counts = {}
        # 尝试加载各数据表
        for key, api_name in [
            ("generals", "api_load_generals"), ("soldiers", "api_load_soldiers"),
            ("things", "api_load_things"), ("skills", "api_load_skills"),
            ("superatk", "api_load_superatk"), ("formations", "api_load_formations"),
            ("titles", "api_load_titles"), ("nations", "api_load_nations"),
            ("cities", "api_load_cities"), ("histories", "api_load_histories"),
            ("scenarios", "api_load_scenarios"), ("ages", "api_load_ages"),
        ]:
            try:
                fn = getattr(self, api_name)
                r = fn()
                counts[key] = len(r.get("data", [])) if r and r.get("success") else 0
            except (AttributeError, TypeError, KeyError, ValueError) as e:
                logger.warning(f"统计 {key} 失败: {e}")
                counts[key] = 0
        # Setting 目录文件统计
        if os.path.exists(setting_dir):
            ini_files = [f for f in os.listdir(setting_dir) if f.endswith('.ini')]
            counts["setting_files"] = len(ini_files)
        else:
            counts["setting_files"] = 0
        # Shape 目录统计
        shape_dir = os.path.join(self.game_path, "Shape")
        if os.path.exists(shape_dir):
            counts["shape_dirs"] = len([d for d in os.listdir(shape_dir) if os.path.isdir(os.path.join(shape_dir, d))])
            genface_dir = os.path.join(shape_dir, "GenFace")
            counts["genface_files"] = len([f for f in os.listdir(genface_dir) if f.endswith('.shp')]) if os.path.exists(genface_dir) else 0
        else:
            counts["shape_dirs"] = counts["genface_files"] = 0
        # 备份统计
        if self.backup_mgr:
            counts["backup_files"] = sum(len(v) for v in self.backup_mgr.index.values())
        else:
            counts["backup_files"] = 0
        stats["counts"] = counts
        return {"success": True, "stats": stats}

    def api_get_backup_history(self) -> dict:
        """获取备份历史"""
        if not self.backup_mgr:
            return {"success": True, "history": [], "count": 0}
        history = self.backup_mgr.get_backup_history()
        return {"success": True, "history": history, "count": len(history)}

    # ============================================================
    # API: 数据校验
    # ============================================================

    def api_validate_all(self) -> dict:
        """全量数据校验（含技能引用校验）"""
        self.validator.clear()
        if self.game_path:
            self.validator.set_game_path(self.game_path)

        # 校验武将
        if self._general_cache:
            self.validator.check_duplicate_ids(self._general_cache, "general", "General01.ini")
            self.validator.check_value_ranges(self._general_cache, "general", "General01.ini")

        # 校验兵种
        if self._soldier_cache:
            self.validator.check_duplicate_ids(self._soldier_cache, "soldier", "Soldier.ini")
            self.validator.check_value_ranges(self._soldier_cache, "soldier", "Soldier.ini")
            self.validator.check_soldier_limit(len(self._soldier_cache), "Soldier.ini")

        # 校验物品
        if self._thing_cache:
            self.validator.check_duplicate_ids(self._thing_cache, "thing", "Thing.ini")
            self.validator.check_value_ranges(self._thing_cache, "thing", "Thing.ini")

        # 跨文件引用校验
        if self._general_cache and self._soldier_cache and self._thing_cache:
            self.validator.check_cross_references(
                self._general_cache, self._soldier_cache, self._thing_cache
            )

        # 6类技能引用校验
        if self.game_path:
            bfmagic_ids = self._load_skill_ids("BFMagic.ini")
            sfmagic_ids = self._load_skill_ids("SFMagic.ini")
            genskill_ids = self._load_skill_ids("GenSkill.ini")
            armyskill_ids = self._load_skill_ids("ArmySkill.ini")
            armygroupskill_ids = self._load_skill_ids("ArmyGroupSkill.ini")
            superatk_ids = self._load_skill_ids("SuperAtk.ini")

            generals = self._general_cache if self._general_cache else []
            defskill = self._defskill_cache if self._defskill_cache else []
            things = self._thing_cache if self._thing_cache else []
            titles = self._title_cache if self._title_cache else []

            # 如果defskill是dict格式，提取sections
            if isinstance(defskill, dict):
                defskill_entries = []
                for sections in defskill.values():
                    if isinstance(sections, list):
                        defskill_entries.extend(sections)
                defskill = defskill_entries

            self.validator.check_skill_id_references(
                generals, defskill, things, titles,
                bfmagic_ids, sfmagic_ids, genskill_ids,
                armyskill_ids, armygroupskill_ids, superatk_ids
            )

        return {
            "success": True,
            "summary": self.validator.summary(),
            "results": self.validator.to_dict_list(),
        }

    def _load_skill_ids(self, filename: str) -> set:
        """从技能INI文件中加载所有技能ID集合"""
        path = os.path.join(self.game_path, "Setting", filename)
        if not os.path.exists(path):
            return set()
        parser = IniParser()
        parser.load(path)
        ids = set()
        for section in parser.sections:
            sid = str(section.get("No", section.get("NO", ""))).strip()
            if sid:
                ids.add(sid)
        return ids

    # ============================================================
    # API: TermText
    # ============================================================

    def api_search_termtext(self, keyword: str) -> dict:
        """搜索TermText"""
        if not self.term_text.is_loaded():
            return {"success": False, "message": "请先加载游戏数据"}
        results = self.term_text.search_text(keyword)
        return {"success": True, "results": results, "count": len(results)}

    def api_get_all_termtext(self) -> dict:
        """获取所有TermText"""
        if not self.term_text.is_loaded():
            return {"success": False, "message": "请先加载游戏数据"}
        texts = self.term_text.get_all_texts()
        return {"success": True, "data": texts, "count": len(texts)}

    # ============================================================
    # API: EXE修改
    # ============================================================

    def api_get_exe_info(self) -> dict:
        """获取EXE信息"""
        return {
            "exists": self.exe_patcher.exe_exists(),
            "size": self.exe_patcher.get_exe_size(),
            "patches": self.exe_patcher.get_patch_info(),
            "applied": self.exe_patcher.get_applied_patches(),
        }

    def api_apply_exe_patch(self, patch_name: str, offset: int, value: int) -> dict:
        """应用EXE补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        # 先备份EXE
        if self.backup_mgr:
            self.backup_mgr.backup_exe()

        success = self.exe_patcher.apply_patch(patch_name, offset, value)
        if success:
            return {"success": True, "message": f"补丁 {patch_name} 应用成功"}
        return {"success": False, "message": f"补丁 {patch_name} 应用失败"}

    def api_revert_exe_patches(self) -> dict:
        """撤销所有EXE补丁"""
        count = self.exe_patcher.revert_all()
        return {"success": True, "message": f"已撤销{count}个补丁", "count": count}

    def api_scan_exe_signatures(self) -> dict:
        """扫描EXE中所有已知特征码"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        results = self.exe_patcher.scan_all_signatures()
        return {
            "success": len(results) > 0,
            "message": f"扫描完成，发现 {len(results)} 组特征码",
            "signatures": {k: len(v) for k, v in results.items()},
            "candidates": {k: v[:10] for k, v in results.items()},
        }

    def api_scan_exe_value(self, value: int, value_type: str = "int32") -> dict:
        """扫描EXE中特定数值的出现位置"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        results = self.exe_patcher.scan_exe_for_value_range(value, value_type)
        return {
            "success": True,
            "message": f"找到 {len(results)} 处匹配",
            "value": value,
            "value_type": value_type,
            "count": len(results),
            "offsets": results[:50],  # 最多返回50个
        }

    def api_apply_exe_patch_auto(self, patch_name: str, new_value: int) -> dict:
        """自动检测偏移量并应用EXE补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if self.backup_mgr:
            self.backup_mgr.backup_exe()
        return self.exe_patcher.apply_patch_auto(patch_name, new_value)

    def api_disassemble_exe(self, offset: int, count: int = 8) -> dict:
        """反汇编 EXE 指定偏移处的指令"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        instructions = self.exe_patcher.disassemble_at(offset, count)
        has_capstone = getattr(self.exe_patcher, 'HAS_CAPSTONE', False) or (
            hasattr(self.exe_patcher.__class__, 'HAS_CAPSTONE') or True
        )
        try:
            from capstone import Cs
            has_capstone = True
        except ImportError:
            has_capstone = False
        return {
            "success": len(instructions) > 0 and "error" not in instructions[0],
            "offset": offset,
            "count": count,
            "instructions": instructions,
            "has_capstone": has_capstone,
        }

    def api_disassemble_scan(self, scan_name: str, top_n: int = 5) -> dict:
        """对特征码扫描结果进行反汇编"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.exe_patcher.disassemble_scan_results(scan_name, top_n)

    def api_apply_nop_patch(self, offset: int, size: int) -> dict:
        """应用 NOP 补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if self.backup_mgr:
            self.backup_mgr.backup_exe()
        ok = self.exe_patcher.apply_nop_patch(offset, size)
        return {"success": ok, "message": f"NOP {size}字节 @ {hex(offset)}" if ok else "写入失败"}

    def api_apply_jmp_patch(self, offset: int, target_offset: int, is_short: bool = True) -> dict:
        """应用 JMP 补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if self.backup_mgr:
            self.backup_mgr.backup_exe()
        ok = self.exe_patcher.apply_jmp_patch(offset, target_offset, is_short)
        return {"success": ok, "message": f"JMP {hex(offset)} → {hex(target_offset)}" if ok else "JMP失败"}

    def api_apply_template_patch(self, template_name: str, offset: int, *args) -> dict:
        """应用预设补丁模板"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if self.backup_mgr:
            self.backup_mgr.backup_exe()
        return self.exe_patcher.apply_template_patch(template_name, offset, *args)

    def api_get_jmp_templates(self) -> dict:
        """获取 JMP 补丁模板列表"""
        return {"success": True, "templates": self.exe_patcher.get_jmp_templates()}

    def api_exe_community_patches(self) -> dict:
        """获取社区教程补丁列表"""
        patches = self.exe_patcher.get_community_patches()
        return {"success": True, "patches": patches, "count": len(patches),
                "message": f"共 {len(patches)} 个社区补丁"}

    def api_exe_apply_community_patch(self, patch_id: str, value: int) -> dict:
        """应用社区教程补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if self.backup_mgr:
            self.backup_mgr.backup_exe()
        return self.exe_patcher.apply_patch_auto(patch_id, value)

    # ============================================================
    # API: Sango7.ini 分辨率设置
    # ============================================================

    def api_get_sango7_config(self) -> dict:
        """读取 Sango7.ini 配置（分辨率、窗口模式等）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Sango7.ini")
        if not os.path.exists(path):
            return {"success": True, "config": {"width": 1024, "height": 768, "fullscreen": 1}}
        config = {"width": 1024, "height": 768, "fullscreen": 1}
        try:
            with open(path, "r", encoding="big5", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("m_lScreenWidth"):
                        config["width"] = int(line.split("=")[1].strip())
                    elif line.startswith("m_lScreenHeight"):
                        config["height"] = int(line.split("=")[1].strip())
                    elif line.startswith("m_bFullScreen"):
                        config["fullscreen"] = int(line.split("=")[1].strip())
        except Exception:
            logger.warning("读取Sango7.ini配置失败，使用默认值")
        return {"success": True, "config": config}

    def api_set_sango7_config(self, width: int = 0, height: int = 0, fullscreen: int = -1) -> dict:
        """修改 Sango7.ini 分辨率/窗口配置"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Sango7.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        # 读取现有内容
        lines = []
        if os.path.exists(path):
            with open(path, "r", encoding="big5", errors="replace") as f:
                lines = f.readlines()
        # 更新设置
        updated = {"width": False, "height": False, "fullscreen": False}
        new_lines = []
        for line in lines:
            s = line.strip()
            if width > 0 and s.startswith("m_lScreenWidth"):
                new_lines.append(f"m_lScreenWidth = {width}\n")
                updated["width"] = True
            elif height > 0 and s.startswith("m_lScreenHeight"):
                new_lines.append(f"m_lScreenHeight = {height}\n")
                updated["height"] = True
            elif fullscreen >= 0 and s.startswith("m_bFullScreen"):
                new_lines.append(f"m_bFullScreen = {fullscreen}\n")
                updated["fullscreen"] = True
            else:
                new_lines.append(line)
        # 追加缺失的配置项
        for key, val, flag in [("m_lScreenWidth", width, "width"),
                                ("m_lScreenHeight", height, "height"),
                                ("m_bFullScreen", fullscreen, "fullscreen")]:
            if not updated[flag]:
                if key == "m_bFullScreen" and fullscreen >= 0:
                    new_lines.append(f"{key} = {fullscreen}\n")
                elif key != "m_bFullScreen" and val > 0:
                    new_lines.append(f"{key} = {val}\n")
        with open(path, "w", encoding="big5", errors="replace") as f:
            f.writelines(new_lines)
        return {"success": True, "message": f"分辨率设置为 {width}x{height}" if width > 0 else "配置已保存"}

    # ============================================================
    # API: 批量修改工具
    # ============================================================

    # 文件字段映射（依据群7游戏实际INI字段）
    _BATCH_LABELS = {
        "General01.ini": "武将 (General01.ini)",
        "Soldier.ini": "兵种 (Soldier.ini)",
        "Thing.ini": "物品 (Thing.ini)",
        "Title.ini": "官职 (Title.ini)",
        "Nation.ini": "势力 (Nation.ini)",
        "City.ini": "城池连接 (City.ini)",
        "BFFront.ini": "冲阵兵器 (BFFront.ini)",
        "BFMagic.ini": "武将技 (BFMagic.ini)",
        "SFMagic.ini": "军师技 (SFMagic.ini)",
        "SuperAtk.ini": "必杀技 (SuperAtk.ini)",
        "GenSkill.ini": "个人特性 (GenSkill.ini)",
        "ArmySkill.ini": "主将特性 (ArmySkill.ini)",
        "ArmyGroupSkill.ini": "元帅特性 (ArmyGroupSkill.ini)",
        "DefSkill.ini": "初始特性 (DefSkill.ini)",
        "Variable.ini": "游戏变量 (Variable.ini)",
        "GenLV.ini": "等级经验 (GenLV.ini)",
        "ItemEnhance.ini": "物品合成 (ItemEnhance.ini)",
        "Format.ini": "阵型属性 (Format.ini)",
        "ChessFormat.ini": "自设阵法 (ChessFormat.ini)",
    }

    def api_get_batch_files(self) -> dict:
        """获取批量修改可用文件列表"""
        return {"success": True, "files": self._get_batch_schemas()}

    def _get_batch_schemas(self) -> dict:
        """从 Schema JSON 动态加载批量配置"""
        schema_dir = os.path.join(os.path.dirname(__file__), "data")
        dynamic = {}
        file_to_schema = {
            "General01.ini": "general_schema.json",
            "Soldier.ini": "soldier_schema.json",
            "Thing.ini": "thing_schema.json",
            "Title.ini": "title_schema.json",
            "Nation.ini": "nation_schema.json",
            "City.ini": "city_schema.json",
            "BFFront.ini": "bffront_schema.json",
            "BFMagic.ini": "bfmagic_schema.json",
            "SFMagic.ini": "sfmagic_schema.json",
            "SuperAtk.ini": "superatk_schema.json",
            "GenSkill.ini": "genskill_schema.json",
            "ArmySkill.ini": "armyskill_schema.json",
            "ArmyGroupSkill.ini": "armygroupskill_schema.json",
            "DefSkill.ini": "defskill_schema.json",
            "GenLV.ini": "genlv_schema.json",
            "Variable.ini": "variable_schema.json",
            "ItemEnhance.ini": "itemenhance_schema.json",
            "Format.ini": "format_schema.json",
            "ChessFormat.ini": "chessformat_schema.json",
        }
        for ini_file, schema_file in file_to_schema.items():
            schema_path = os.path.join(schema_dir, schema_file)
            if os.path.exists(schema_path):
                with open(schema_path, "r", encoding="utf-8") as f:
                    s = json.load(f)
                sections = s.get("sections", {})
                if sections:
                    first_section = list(sections.values())[0]
                    fields = list(first_section.get("fields", {}).keys())
                    section_name = list(sections.keys())[0]
                    label = self._BATCH_LABELS.get(ini_file, ini_file)
                    dynamic[ini_file] = {
                        "label": label,
                        "section": section_name,
                        "fields": fields,
                    }
        return dynamic

    def _load_ini_data(self, filename: str) -> List[Dict]:
        """加载指定INI文件的数据"""
        if not self.game_path:
            return []
        path = os.path.join(self.game_path, "Setting", filename)
        if not os.path.exists(path):
            return []
        parser = IniParser()
        parser.load(path)
        schemas = self._get_batch_schemas()
        schema = schemas.get(filename, {})
        section_name = schema.get("section", "")
        sections = parser.get_all_sections(section_name) if section_name else parser.sections
        return [dict(s.entries) for s in sections]

    def _save_ini_data(self, filename: str, data: List[Dict]) -> bool:
        """保存INI文件数据"""
        if not self.game_path:
            return False
        path = os.path.join(self.game_path, "Setting", filename)
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        schemas = self._get_batch_schemas()
        schema = schemas.get(filename, {})
        section_name = schema.get("section", "")
        parser = IniParser()
        parser.load(path)
        parser.replace_sections(section_name, data, "No")
        parser.save(path)
        return True

    def _apply_numeric_op(self, old_val: int, op: str, value: int) -> int:
        """应用数值操作"""
        if op == "add":
            return old_val + value
        elif op == "sub":
            return max(0, old_val - value)
        elif op == "mul":
            return int(old_val * value)
        elif op == "set":
            return value
        elif op == "cap":
            return min(old_val, value)
        return old_val

    def api_batch_preview(self, file: str, field: str, op: str, value: int,
                          filterField: str = None, filterValue: str = None) -> dict:
        """预览批量数值修改"""
        data = self._load_ini_data(file)
        if not data:
            return {"success": False, "message": f"无法加载 {file}"}

        preview = []
        for entry in data:
            if filterField and filterValue:
                if str(entry.get(filterField, "")) != str(filterValue):
                    continue
            old_val = int(entry.get(field, 0))
            new_val = self._apply_numeric_op(old_val, op, value)
            preview.append({
                "id": entry.get("No", ""),
                "name": entry.get("Name", ""),
                "oldVal": old_val,
                "newVal": new_val,
            })

        return {"success": True, "preview": preview, "count": len(preview)}

    def api_batch_execute(self, file: str, field: str, op: str, value: int,
                          filterField: str = None, filterValue: str = None) -> dict:
        """执行批量数值修改"""
        data = self._load_ini_data(file)
        if not data:
            return {"success": False, "message": f"无法加载 {file}"}

        modified = 0
        preview = []
        for entry in data:
            if filterField and filterValue:
                if str(entry.get(filterField, "")) != str(filterValue):
                    continue
            old_val = int(entry.get(field, 0))
            new_val = self._apply_numeric_op(old_val, op, value)
            if old_val != new_val:
                entry[field] = str(new_val)
                modified += 1
            preview.append({
                "id": entry.get("No", ""),
                "name": entry.get("Name", ""),
                "oldVal": old_val,
                "newVal": new_val,
            })

        if modified > 0:
            self._save_ini_data(file, data)

        # 刷新缓存
        if file == "General01.ini":
            self._general_cache = data

        return {"success": True, "message": f"修改了 {modified} 条记录", "preview": preview, "modified": modified}

    # ============================================================
    # V3.6.0: 复合筛选条件
    # ============================================================
    def _match_filters(self, entry: dict, filters: list, filter_mode: str = "AND") -> bool:
        """检查条目是否匹配复合筛选条件
        filters: [{"field": str, "op": str, "value": any}, ...]
        op: eq/ne/gt/lt/gte/lte/contains/in
        filter_mode: AND/OR
        """
        if not filters:
            return True

        results = []
        for f in filters:
            field = f.get("field", "")
            op = f.get("op", "eq")
            filter_val = f.get("value")
            entry_val = entry.get(field)

            matched = False
            try:
                if op == "eq":
                    matched = str(entry_val) == str(filter_val)
                elif op == "ne":
                    matched = str(entry_val) != str(filter_val)
                elif op in ("gt", "lt", "gte", "lte"):
                    ev = float(entry_val) if entry_val is not None else 0
                    fv = float(filter_val) if filter_val is not None else 0
                    if op == "gt":
                        matched = ev > fv
                    elif op == "lt":
                        matched = ev < fv
                    elif op == "gte":
                        matched = ev >= fv
                    elif op == "lte":
                        matched = ev <= fv
                elif op == "contains":
                    matched = str(filter_val).lower() in str(entry_val).lower()
                elif op == "in":
                    # filter_val should be comma-separated list
                    vals = [v.strip() for v in str(filter_val).split(",")]
                    matched = str(entry_val) in vals
            except (ValueError, TypeError):
                matched = False

            results.append(matched)

        if filter_mode == "OR":
            return any(results)
        return all(results)  # AND

    def api_batch_preview_adv(self, file: str, field: str, op: str, value: int,
                              filters: list = None, filter_mode: str = "AND") -> dict:
        """增强版批量数值修改预览 — 支持复合筛选"""
        data = self._load_ini_data(file)
        if not data:
            return {"success": False, "message": f"无法加载 {file}"}

        preview = []
        for entry in data:
            if not self._match_filters(entry, filters, filter_mode):
                continue
            old_val = int(entry.get(field, 0))
            new_val = self._apply_numeric_op(old_val, op, value)
            preview.append({
                "id": entry.get("No", ""),
                "name": entry.get("Name", ""),
                "oldVal": old_val,
                "newVal": new_val,
            })

        return {"success": True, "preview": preview, "count": len(preview)}

    def api_batch_execute_adv(self, file: str, field: str, op: str, value: int,
                              filters: list = None, filter_mode: str = "AND") -> dict:
        """增强版批量数值修改执行 — 支持复合筛选"""
        data = self._load_ini_data(file)
        if not data:
            return {"success": False, "message": f"无法加载 {file}"}

        # 自动备份
        if self.backup_mgr:
            path = os.path.join(self.game_path, "Setting", file)
            if os.path.exists(path):
                self.backup_mgr.backup_file(path)

        modified = 0
        preview = []
        for entry in data:
            if not self._match_filters(entry, filters, filter_mode):
                continue
            old_val = int(entry.get(field, 0))
            new_val = self._apply_numeric_op(old_val, op, value)
            if old_val != new_val:
                entry[field] = str(new_val)
                modified += 1
            preview.append({
                "id": entry.get("No", ""),
                "name": entry.get("Name", ""),
                "oldVal": old_val,
                "newVal": new_val,
            })

        if modified > 0:
            self._save_ini_data(file, data)

        if file == "General01.ini":
            self._general_cache = data

        return {"success": True, "message": f"修改了 {modified} 条记录", "preview": preview, "modified": modified}

    # ============================================================
    # V3.6.0: 批量操作预设/模板
    # ============================================================
    def _get_preset_dir(self) -> str:
        d = os.path.join(WRITE_ROOT, "data", "batch_presets")
        os.makedirs(d, exist_ok=True)
        return d

    def api_batch_preset_list(self) -> dict:
        """列出所有批量操作预设"""
        preset_dir = self._get_preset_dir()
        presets = []
        for fname in sorted(os.listdir(preset_dir)):
            if fname.endswith(".json"):
                fpath = os.path.join(preset_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        p = json.load(f)
                    presets.append({
                        "id": fname.replace(".json", ""),
                        "name": p.get("name", fname),
                        "mode": p.get("mode", "numeric"),
                        "description": p.get("description", ""),
                        "created": p.get("created", ""),
                        "step_count": len(p.get("steps", [p.get("params", {})])),
                    })
                except Exception:
                    pass
        return {"success": True, "presets": presets, "count": len(presets)}

    def api_batch_preset_save(self, name: str, mode: str, params: dict,
                              description: str = "") -> dict:
        """保存批量操作预设"""
        if not name or not name.strip():
            return {"success": False, "message": "预设名称不能为空"}
        preset_dir = self._get_preset_dir()
        safe_name = "".join(c for c in name if c.isalnum() or c in "._- ")
        preset = {
            "name": name.strip(),
            "mode": mode,
            "description": description,
            "params": params,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        fpath = os.path.join(preset_dir, f"{safe_name}.json")
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(preset, f, ensure_ascii=False, indent=2)
        return {"success": True, "message": f"预设已保存: {name}", "id": safe_name}

    def api_batch_preset_load(self, preset_id: str) -> dict:
        """加载批量操作预设"""
        fpath = os.path.join(self._get_preset_dir(), f"{preset_id}.json")
        if not os.path.exists(fpath):
            return {"success": False, "message": "预设不存在"}
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                preset = json.load(f)
            return {"success": True, "preset": preset}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_batch_preset_delete(self, preset_id: str) -> dict:
        """删除批量操作预设"""
        fpath = os.path.join(self._get_preset_dir(), f"{preset_id}.json")
        if not os.path.exists(fpath):
            return {"success": False, "message": "预设不存在"}
        os.remove(fpath)
        return {"success": True, "message": f"预设已删除: {preset_id}"}

    # ============================================================
    # V3.6.0: 批量修改撤销/回滚
    # ============================================================
    def api_batch_undo(self) -> dict:
        """撤销最近一次批量修改（恢复备份）"""
        if not self.backup_mgr:
            return {"success": False, "message": "备份系统未启用"}
        results = self.backup_mgr.restore_all()
        restored = sum(1 for v in results.values() if v)
        if restored > 0:
            # 清除缓存
            self._general_cache = None
            return {"success": True, "message": f"已还原 {restored} 个文件", "restored": restored,
                    "details": {k: v for k, v in results.items() if v}}
        return {"success": False, "message": "没有可还原的备份"}

    # ============================================================
    # V3.6.0: 操作链/流水线
    # ============================================================
    def api_batch_pipeline_execute(self, steps: list) -> dict:
        """顺序执行多个批量操作步骤
        steps: [{"file": str, "field": str, "op": str, "value": int, "filters": list, "filterMode": str}, ...]
        """
        if not steps:
            return {"success": False, "message": "操作步骤不能为空"}

        results = []
        total_modified = 0
        for i, step in enumerate(steps):
            file = step.get("file", "")
            field = step.get("field", "")
            op = step.get("op", "set")
            value = step.get("value", 0)
            filters = step.get("filters", None)
            filter_mode = step.get("filterMode", "AND")

            r = self.api_batch_execute_adv(
                file=file, field=field, op=op, value=value,
                filters=filters, filter_mode=filter_mode
            )
            results.append({
                "step": i + 1,
                "file": file,
                "field": field,
                "op": op,
                "success": r.get("success", False),
                "modified": r.get("modified", 0),
                "message": r.get("message", ""),
            })
            if r.get("success"):
                total_modified += r.get("modified", 0)

        return {
            "success": True,
            "message": f"流水线执行完成: {len(steps)} 步, 共修改 {total_modified} 条记录",
            "steps": results,
            "totalModified": total_modified,
        }

    def api_batch_clone_preview(self, source: int, from_: int, to: int, type: str) -> dict:
        """预览批量复制技能"""
        if not self._general_cache:
            self._general_cache = self._load_ini_data("General01.ini")

        # 查找源武将
        source_general = None
        for g in self._general_cache:
            if int(g.get("No", 0)) == source:
                source_general = g
                break

        if not source_general:
            return {"success": False, "message": f"未找到武将 #{source}"}

        targets = []
        for g in self._general_cache:
            no = int(g.get("No", 0))
            if from_ <= no <= to and no != source:
                skill_count = 0
                for i in range(1, 9):
                    if g.get(f"Skill{i}"):
                        skill_count += 1
                targets.append({"id": no, "name": g.get("Name", ""), "skillCount": skill_count})

        return {"success": True, "targets": targets, "sourceName": source_general.get("Name", "")}

    def api_batch_clone_execute(self, source: int, from_: int, to: int, type: str) -> dict:
        """执行批量复制技能"""
        if not self._general_cache:
            self._general_cache = self._load_ini_data("General01.ini")

        source_general = None
        for g in self._general_cache:
            if int(g.get("No", 0)) == source:
                source_general = g
                break

        if not source_general:
            return {"success": False, "message": f"未找到武将 #{source}"}

        modified = 0
        for g in self._general_cache:
            no = int(g.get("No", 0))
            if from_ <= no <= to and no != source:
                if type in ("skills", "all"):
                    for i in range(1, 9):
                        g[f"Skill{i}"] = source_general.get(f"Skill{i}", "")
                if type in ("strategies", "all"):
                    for i in range(1, 5):
                        g[f"Strategy{i}"] = source_general.get(f"Strategy{i}", "")
                if type in ("traits", "all"):
                    for i in range(1, 4):
                        g[f"Feature{i}"] = source_general.get(f"Feature{i}", "")
                if type in ("soldiers", "all"):
                    for i in range(1, 4):
                        g[f"Soldier{i}"] = source_general.get(f"Soldier{i}", "")
                modified += 1

        if modified > 0:
            self._save_ini_data("General01.ini", self._general_cache)

        return {"success": True, "message": f"已复制到 {modified} 个武将", "modified": modified}

    def api_batch_search(self, find: str, replace: str = None, isRegex: bool = False,
                         caseSensitive: bool = False, scope: List[str] = None) -> dict:
        """全局查找"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        import re
        results = []
        total_matches = 0

        for filename in (scope or []):
            path = os.path.join(self.game_path, "Setting", filename)
            if not os.path.exists(path):
                continue

            matches = []
            try:
                with open(path, "r", encoding="big5", errors="replace") as f:
                    lines = f.readlines()

                for line_num, line in enumerate(lines, 1):
                    if isRegex:
                        flags = 0 if caseSensitive else re.IGNORECASE
                        try:
                            if re.search(find, line, flags):
                                matches.append(f"[行{line_num}] {line.strip()}")
                                total_matches += 1
                        except re.error:
                            return {"success": False, "message": f"正则表达式错误: {find}"}
                    else:
                        if caseSensitive:
                            if find in line:
                                matches.append(f"[行{line_num}] {line.strip()}")
                                total_matches += 1
                        else:
                            if find.lower() in line.lower():
                                matches.append(f"[行{line_num}] {line.strip()}")
                                total_matches += 1
            except Exception as e:
                logger.warning(f"批量搜索文件失败 {path}: {e}")
                continue

            if matches:
                results.append({"file": filename, "matches": matches})

        return {"success": True, "results": results, "totalMatches": total_matches}

    def api_batch_search_replace(self, find: str, replace: str, isRegex: bool = False,
                                  caseSensitive: bool = False, scope: List[str] = None) -> dict:
        """全局查找替换"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        import re
        results = []
        total_matches = 0
        total_replaced = 0

        for filename in (scope or []):
            path = os.path.join(self.game_path, "Setting", filename)
            if not os.path.exists(path):
                continue

            if self.backup_mgr:
                self.backup_mgr.backup_file(path)

            try:
                with open(path, "r", encoding="big5", errors="replace") as f:
                    content = f.read()

                if isRegex:
                    flags = 0 if caseSensitive else re.IGNORECASE
                    try:
                        new_content, count = re.subn(find, replace, content, flags=flags)
                        total_replaced += count
                    except re.error:
                        return {"success": False, "message": f"正则表达式错误: {find}"}
                else:
                    if caseSensitive:
                        count = content.count(find)
                        new_content = content.replace(find, replace)
                    else:
                        pattern = re.compile(re.escape(find), re.IGNORECASE)
                        new_content, count = pattern.subn(replace, content)
                    total_replaced += count

                if count > 0:
                    total_matches += count
                    with open(path, "w", encoding="big5", errors="replace") as f:
                        f.write(new_content)
                    results.append({"file": filename, "matches": [f"替换了 {count} 处"], "count": count})

            except Exception as e:
                results.append({"file": filename, "matches": [f"错误: {str(e)}"]})

        return {
            "success": True,
            "message": f"在 {len(results)} 个文件中替换了 {total_replaced} 处",
            "results": results,
            "totalMatches": total_matches,
            "totalReplaced": total_replaced,
        }

    # ============================================================
    # API: 差异对比
    # ============================================================

    def api_get_diff_backups(self, file: str) -> dict:
        """获取指定文件的备份列表"""
        if not self.backup_mgr:
            return {"success": True, "backups": []}

        backups = self.backup_mgr.get_backup_list(file)
        return {"success": True, "backups": backups}

    def api_diff_compare(self, file: str, backup_id: str) -> dict:
        """对比当前文件与备份"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        current_path = os.path.join(self.game_path, "Setting", file)
        if not os.path.exists(current_path):
            return {"success": False, "message": f"当前文件不存在: {file}"}

        if not self.backup_mgr:
            return {"success": False, "message": "备份管理器未初始化"}

        backup_path = self.backup_mgr.get_backup_path(file, backup_id)
        if not backup_path or not os.path.exists(backup_path):
            return {"success": False, "message": "备份文件不存在"}

        # 解析当前文件和备份文件
        parser_cur = IniParser()
        parser_cur.load(current_path)

        parser_old = IniParser()
        parser_old.load(backup_path)

        schema = self._get_batch_schemas().get(file, {})
        section_name = schema.get("section", "")

        cur_data = {}
        for s in parser_cur.get_all_sections(section_name):
            entries = dict(s.entries)
            no = entries.get("No", "")
            cur_data[no] = entries

        old_data = {}
        for s in parser_old.get_all_sections(section_name):
            entries = dict(s.entries)
            no = entries.get("No", "")
            old_data[no] = entries

        entries = []
        counts = {"added": 0, "modified": 0, "deleted": 0, "unchanged": 0}

        # 检查新增和修改
        for no, cur in cur_data.items():
            if no not in old_data:
                counts["added"] += 1
                entries.append({
                    "id": no,
                    "name": cur.get("Name", ""),
                    "type": "added",
                    "changes": [{"field": k, "oldVal": "(无)", "newVal": str(v)} for k, v in cur.items() if k != "No"],
                })
            else:
                old = old_data[no]
                changes = []
                for k, v in cur.items():
                    if k == "No":
                        continue
                    old_v = old.get(k, "")
                    if str(v) != str(old_v):
                        changes.append({"field": k, "oldVal": str(old_v), "newVal": str(v)})
                if changes:
                    counts["modified"] += 1
                    entries.append({
                        "id": no,
                        "name": cur.get("Name", ""),
                        "type": "modified",
                        "changes": changes,
                    })
                else:
                    counts["unchanged"] += 1

        # 检查删除
        for no, old in old_data.items():
            if no not in cur_data:
                counts["deleted"] += 1
                entries.append({
                    "id": no,
                    "name": old.get("Name", ""),
                    "type": "deleted",
                    "changes": [{"field": k, "oldVal": str(v), "newVal": "(已删除)"} for k, v in old.items() if k != "No"],
                })

        return {
            "success": True,
            "counts": counts,
            "entries": entries,
            "file": file,
            "backupId": backup_id,
        }

    def api_diff_export(self, diff_data: dict = None) -> dict:
        """导出差异报告"""
        if not diff_data:
            return {"success": False, "message": "无差异数据"}

        export_dir = os.path.join(WRITE_ROOT, "exports", "diff_reports")
        os.makedirs(export_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"diff_{diff_data.get('file', 'unknown')}_{timestamp}.txt"
        path = os.path.join(export_dir, filename)

        with open(path, "w", encoding="utf-8") as f:
            f.write(f"差异报告: {diff_data.get('file', '')}\n")
            f.write(f"生成时间: {timestamp}\n")
            f.write("=" * 60 + "\n\n")
            counts = diff_data.get("counts", {})
            f.write(f"新增: {counts.get('added', 0)}  修改: {counts.get('modified', 0)}  删除: {counts.get('deleted', 0)}  未变更: {counts.get('unchanged', 0)}\n\n")
            for entry in diff_data.get("entries", []):
                type_label = {"added": "新增", "modified": "修改", "deleted": "删除", "unchanged": "未变更"}.get(entry.get("type", ""), "")
                f.write(f"[{type_label}] #{entry.get('id', '')} {entry.get('name', '')}\n")
                for change in entry.get("changes", []):
                    f.write(f"  {change['field']}: {change['oldVal']} → {change['newVal']}\n")
                f.write("\n")

        return {"success": True, "message": f"差异报告已导出到 {path}", "path": path}

    # V3.8.0: 差异对比增强
    def api_diff_cross_mod(self, mod_a: str, mod_b: str) -> dict:
        """跨MOD对比：对比两个MOD包的差异"""
        export_a = os.path.join(WRITE_ROOT, "exports", mod_a)
        export_b = os.path.join(WRITE_ROOT, "exports", mod_b)

        if not os.path.exists(export_a):
            return {"success": False, "message": f"MOD '{mod_a}' 不存在，请先打包"}
        if not os.path.exists(export_b):
            return {"success": False, "message": f"MOD '{mod_b}' 不存在，请先打包"}

        # 获取两个MOD的文件列表
        def get_file_map(export_dir):
            file_map = {}
            for root, _, files in os.walk(export_dir):
                for fname in files:
                    if fname in ("mod_info.json", "pack_meta.json", "README.md"):
                        continue
                    rel = os.path.relpath(os.path.join(root, fname), export_dir)
                    fp = os.path.join(root, fname)
                    file_map[rel] = {
                        "size": os.path.getsize(fp),
                        "mtime": os.path.getmtime(fp),
                    }
            return file_map

        files_a = get_file_map(export_a)
        files_b = get_file_map(export_b)

        only_a = [f for f in files_a if f not in files_b]
        only_b = [f for f in files_b if f not in files_a]
        common = [f for f in files_a if f in files_b]

        # 比较共同文件
        different = []
        same = []
        for f in common:
            if files_a[f]["size"] != files_b[f]["size"]:
                different.append({
                    "file": f,
                    "size_a": files_a[f]["size"],
                    "size_b": files_b[f]["size"],
                    "diff_kb": round((files_b[f]["size"] - files_a[f]["size"]) / 1024, 1),
                })
            else:
                same.append(f)

        return {
            "success": True,
            "mod_a": mod_a,
            "mod_b": mod_b,
            "summary": {
                "only_in_a": len(only_a),
                "only_in_b": len(only_b),
                "same": len(same),
                "different": len(different),
                "total_a": len(files_a),
                "total_b": len(files_b),
            },
            "only_in_a": only_a[:100],
            "only_in_b": only_b[:100],
            "different": different[:100],
            "overlap_pct": round(len(common) / max(len(files_a), len(files_b)) * 100, 1) if files_a and files_b else 0,
        }

    def api_diff_summary(self, file: str = None) -> dict:
        """生成差异摘要：列出所有有变更的文件相比最新备份"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if not self.backup_mgr:
            return {"success": False, "message": "备份管理器未初始化"}

        setting_dir = os.path.join(self.game_path, "Setting")
        if not os.path.exists(setting_dir):
            return {"success": False, "message": "Setting目录不存在"}

        changed = []
        unchanged = []
        total_size_change = 0

        scan_files = [file] if file else sorted(os.listdir(setting_dir))
        for fname in scan_files:
            if not fname.endswith(".ini"):
                continue
            current_path = os.path.join(setting_dir, fname)
            if not os.path.isfile(current_path):
                continue

            backup_record = self.backup_mgr.get_latest_backup(current_path)
            if not backup_record:
                changed.append({
                    "file": fname,
                    "status": "new",
                    "size_kb": round(os.path.getsize(current_path) / 1024, 1),
                })
                continue

            backup_path = backup_record.get("backup_path", "")
            if not backup_path or not os.path.exists(backup_path):
                changed.append({
                    "file": fname,
                    "status": "no_backup",
                    "size_kb": round(os.path.getsize(current_path) / 1024, 1),
                })
                continue

            try:
                with open(current_path, "rb") as f:
                    cur_data = f.read()
                with open(backup_path, "rb") as f:
                    bak_data = f.read()
            except Exception:
                continue

            if cur_data != bak_data:
                diff_kb = round((len(cur_data) - len(bak_data)) / 1024, 1)
                total_size_change += diff_kb
                changed.append({
                    "file": fname,
                    "status": "modified",
                    "size_kb": round(len(cur_data) / 1024, 1),
                    "backup_size_kb": round(len(bak_data) / 1024, 1),
                    "diff_kb": diff_kb,
                })
            else:
                unchanged.append(fname)

        return {
            "success": True,
            "summary": {
                "changed": len(changed),
                "unchanged": len(unchanged),
                "total": len(changed) + len(unchanged),
                "total_size_change_kb": round(total_size_change, 1),
            },
            "changed_files": changed,
            "has_changes": len(changed) > 0,
        }

    # ============================================================
    # API: MOD管理（增强版）
    # ============================================================

    def api_get_mod_list(self) -> dict:
        """获取MOD列表（含文件统计）"""
        mod_dir = os.path.join(WRITE_ROOT, "mods")
        if not os.path.exists(mod_dir):
            return {"success": True, "mods": []}

        mods = []
        for name in os.listdir(mod_dir):
            mod_path = os.path.join(mod_dir, name)
            if os.path.isdir(mod_path):
                info_path = os.path.join(mod_path, "mod_info.json")
                info = {}
                if os.path.exists(info_path):
                    with open(info_path, "r", encoding="utf-8") as f:
                        info = json.load(f)
                # 统计文件数
                file_count = 0
                data_dir = os.path.join(mod_path, "data")
                if os.path.exists(data_dir):
                    file_count = len([f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))])
                mods.append({
                    "name": name,
                    "path": mod_path,
                    "info": info,
                    "files": file_count,
                })
        return {"success": True, "mods": mods}

    def api_get_active_mod(self) -> dict:
        """获取当前活跃MOD"""
        active_path = os.path.join(WRITE_ROOT, "active_mod.txt")
        active = None
        if os.path.exists(active_path):
            with open(active_path, "r", encoding="utf-8") as f:
                active = f.read().strip()
        return {"success": True, "active": active}

    def api_set_active_mod(self, name: str) -> dict:
        """设置当前活跃MOD"""
        mod_dir = os.path.join(WRITE_ROOT, "mods", name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{name}' 不存在"}

        active_path = os.path.join(WRITE_ROOT, "active_mod.txt")
        with open(active_path, "w", encoding="utf-8") as f:
            f.write(name)

        # 更新MOD信息中的最后活跃时间
        info_path = os.path.join(mod_dir, "mod_info.json")
        if os.path.exists(info_path):
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            info["last_active"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)

        return {"success": True, "message": f"已切换到 MOD '{name}'"}

    def api_create_mod(self, name: str, description: str = "") -> dict:
        """创建新MOD工程"""
        if not name or not name.strip():
            return {"success": False, "message": "MOD名称不能为空"}
        # 安全名称：只保留字母、数字、中文、下划线
        safe_name = "".join(c for c in name if c.isalnum() or c in "_\u4e00-\u9fff")
        if not safe_name:
            return {"success": False, "message": "MOD名称无效"}

        mod_dir = os.path.join(WRITE_ROOT, "mods", safe_name)
        if os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{safe_name}' 已存在"}

        os.makedirs(mod_dir, exist_ok=True)
        os.makedirs(os.path.join(mod_dir, "data"), exist_ok=True)
        os.makedirs(os.path.join(mod_dir, "snapshots"), exist_ok=True)

        info = {
            "name": safe_name,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "description": description or "",
            "last_active": time.strftime("%Y-%m-%d %H:%M:%S"),
            "snapshot_count": 0,
        }
        with open(os.path.join(mod_dir, "mod_info.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        # 设置为活跃MOD
        self.api_set_active_mod(safe_name)

        return {"success": True, "message": f"MOD工程 '{safe_name}' 创建成功", "path": mod_dir}

    def api_delete_mod(self, name: str) -> dict:
        """删除MOD工程"""
        mod_dir = os.path.join(WRITE_ROOT, "mods", name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{name}' 不存在"}

        shutil.rmtree(mod_dir)

        # 如果删除的是活跃MOD，清除活跃状态
        active_path = os.path.join(WRITE_ROOT, "active_mod.txt")
        if os.path.exists(active_path):
            with open(active_path, "r", encoding="utf-8") as f:
                active = f.read().strip()
            if active == name:
                os.remove(active_path)

        return {"success": True, "message": f"MOD工程 '{name}' 已删除"}

    def api_mod_snapshot(self, name: str) -> dict:
        """创建当前游戏数据快照（用于增量对比）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        mod_dir = os.path.join(WRITE_ROOT, "mods", name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{name}' 不存在"}

        snap_dir = os.path.join(mod_dir, "snapshots")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        snap_name = f"snapshot_{timestamp}"
        snap_path = os.path.join(snap_dir, snap_name)
        os.makedirs(snap_path, exist_ok=True)

        # 复制所有INI文件作为快照
        setting_dir = os.path.join(self.game_path, "Setting")
        count = 0
        if os.path.exists(setting_dir):
            for f in os.listdir(setting_dir):
                if f.endswith(".ini"):
                    src = os.path.join(setting_dir, f)
                    dst = os.path.join(snap_path, f)
                    shutil.copy2(src, dst)
                    count += 1

        # 更新快照计数
        info_path = os.path.join(mod_dir, "mod_info.json")
        if os.path.exists(info_path):
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            info["snapshot_count"] = info.get("snapshot_count", 0) + 1
            info["last_snapshot"] = timestamp
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)

        return {"success": True, "message": f"快照创建成功，共 {count} 个文件", "count": count, "snapshot": snap_name}

    def api_pack_mod_incremental(self, mod_name: str) -> dict:
        """增量打包：只打包变更文件 + Shape资源 + 生成ZIP可分发包"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        mod_dir = os.path.join(WRITE_ROOT, "mods", mod_name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{mod_name}' 不存在"}

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if os.path.exists(export_dir):
            shutil.rmtree(export_dir)
        os.makedirs(export_dir, exist_ok=True)

        # 找到最新快照
        snap_dir = os.path.join(mod_dir, "snapshots")
        latest_snap = None
        if os.path.exists(snap_dir):
            snaps = sorted(os.listdir(snap_dir), reverse=True)
            if snaps:
                latest_snap = os.path.join(snap_dir, snaps[0])

        # 读取MOD元数据，自动递增版本号
        mod_info = {
            "name": mod_name,
            "packed": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0.0",
            "author": "",
            "description": "",
            "game_version": "Sango7",
            "files": [],
            "changed_files": [],
            "shape_files": [],
            "total_files": 0,
            "changed_count": 0,
            "dependencies": [],
            "install_instructions": "将 Setting/ 复制到游戏目录，Shape/ 合并到游戏目录 Shape/，Script/ 复制到游戏目录，如有 EXE 替换原文件",
        }
        info_path = os.path.join(mod_dir, "mod_info.json")
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                mod_info.update({k: v for k, v in existing.items() if k in mod_info})
                # 保留依赖信息
                if "dependencies" in existing:
                    mod_info["dependencies"] = existing["dependencies"]
                # 自动递增补丁版本号
                old_ver = existing.get("version", "1.0.0")
                try:
                    parts = [int(x) for x in old_ver.replace("v", "").split(".")]
                    if len(parts) >= 3:
                        parts[2] += 1
                        mod_info["version"] = ".".join(str(x) for x in parts)
                    elif len(parts) == 2:
                        parts[1] += 1
                        mod_info["version"] = ".".join(str(x) for x in parts) + ".0"
                    else:
                        mod_info["version"] = old_ver + ".1"
                except (ValueError, IndexError):
                    mod_info["version"] = old_ver + ".1"
            except Exception:
                logger.warning("读取已有mod_info.json失败，将使用新配置")
        all_files = []
        changed_files = []

        # 1. 打包 Setting/ 目录变更文件
        setting_dir = os.path.join(self.game_path, "Setting")
        subdirs = ["", "bfdata", "HSData", "OBD", "var"]

        if os.path.exists(setting_dir):
            for subdir in subdirs:
                scan_dir = os.path.join(setting_dir, subdir) if subdir else setting_dir
                if not os.path.exists(scan_dir):
                    continue
                for f in sorted(os.listdir(scan_dir)):
                    src = os.path.join(scan_dir, f)
                    if not os.path.isfile(src):
                        continue
                    rel_path = os.path.join(subdir, f) if subdir else f
                    all_files.append(rel_path)
                    changed = True
                    if latest_snap:
                        snap_file = os.path.join(latest_snap, rel_path)
                        if os.path.exists(snap_file):
                            with open(src, "rb") as fs:
                                changed = fs.read() != open(snap_file, "rb").read()
                    if changed:
                        changed_count += 1
                        changed_files.append(rel_path)
                        dest_dir = os.path.join(export_dir, "Setting", subdir) if subdir else os.path.join(export_dir, "Setting")
                        os.makedirs(dest_dir, exist_ok=True)
                        shutil.copy2(src, os.path.join(dest_dir, f))

        # 2. 打包 Shape/ 目录变更资源（头像、模型、半身像等）
        shape_dir = os.path.join(self.game_path, "Shape")
        shape_files = []
        shape_always = ["Face", "BFObj", "genhalf"]  # 核心资源目录
        if os.path.exists(shape_dir):
            # 扫描所有 Shape 子目录
            try:
                all_shape_subdirs = [d for d in os.listdir(shape_dir)
                                     if os.path.isdir(os.path.join(shape_dir, d))]
            except Exception as e:
                logger.warning(f"列出Shape子目录失败: {e}")
                all_shape_subdirs = []
            for sdir in all_shape_subdirs:
                scan = os.path.join(shape_dir, sdir)
                if not os.path.exists(scan):
                    continue
                for root, _, files in os.walk(scan):
                    for f in sorted(files):
                        src = os.path.join(root, f)
                        if not os.path.isfile(src):
                            continue
                        rel = os.path.relpath(src, shape_dir)
                        # 核心资源目录始终打包，其他目录按7天新鲜度
                        is_core = any(sdir.startswith(core) for core in shape_always)
                        try:
                            mtime = os.path.getmtime(src)
                            fresh = time.time() - mtime < 7 * 86400
                            if is_core or fresh or not latest_snap:
                                shape_files.append(rel)
                                dest = os.path.join(export_dir, "Shape", os.path.dirname(rel))
                                os.makedirs(dest, exist_ok=True)
                                shutil.copy2(src, os.path.join(dest, f))
                        except Exception:
                            logger.warning(f"复制Shape文件失败: {src}")

        # 3. 打包 Script/ 目录
        script_dir = os.path.join(self.game_path, "Script")
        script_files = []
        if os.path.exists(script_dir):
            for root, _, files in os.walk(script_dir):
                for f in sorted(files):
                    src = os.path.join(root, f)
                    if not os.path.isfile(src):
                        continue
                    rel = os.path.relpath(src, script_dir)
                    changed = True
                    if latest_snap:
                        snap_file = os.path.join(latest_snap, "Script", rel)
                        if os.path.exists(snap_file):
                            with open(src, "rb") as fs:
                                changed = fs.read() != open(snap_file, "rb").read()
                    if changed:
                        script_files.append(rel)
                        dest = os.path.join(export_dir, "Script", os.path.dirname(rel))
                        os.makedirs(dest, exist_ok=True)
                        shutil.copy2(src, os.path.join(dest, f))

        # 4. 打包 EXE（如果已修改）
        exe_packed = False
        exe_name = "Sango7.exe"
        exe_src = os.path.join(self.game_path, exe_name)
        if os.path.exists(exe_src) and self.exe_patcher.exe_exists():
            changed = True
            if latest_snap:
                snap_exe = os.path.join(latest_snap, exe_name)
                if os.path.exists(snap_exe):
                    with open(exe_src, "rb") as fs:
                        changed = fs.read() != open(snap_exe, "rb").read()
            if changed:
                shutil.copy2(exe_src, os.path.join(export_dir, exe_name))
                exe_packed = True
        readme = f"""# {mod_name} v{mod_info['version']}

## 作者
{mod_info.get('author', '未知')}

## 描述
{mod_info.get('description', '无描述')}

## 安装方法
1. 将 Setting/ 文件夹复制到游戏目录
2. 将 Shape/ 文件夹（如有）合并到游戏目录的 Shape/ 文件夹
3. 将 Script/ 文件夹（如有）复制到游戏目录的 Script/ 文件夹
4. 如有 Sango7.exe，替换游戏目录中的原文件（已解除限制）
5. 启动游戏即可

## 卸载方法
使用 San7ModMaker 的"还原备份"功能，或手动替换回原始文件。

## 文件清单
### Setting 文件 ({len(changed_files)} 个变更)
{chr(10).join('- ' + f for f in changed_files[:50])}
{'' if len(changed_files) <= 50 else f'... 还有 {len(changed_files) - 50} 个文件'}

### Shape 资源 ({len(shape_files)} 个)
{chr(10).join('- ' + f for f in shape_files[:20])}
{'' if len(shape_files) <= 20 else f'... 还有 {len(shape_files) - 20} 个文件'}

### Script 脚本 ({len(script_files)} 个)
{chr(10).join('- ' + f for f in script_files[:20])}
{'' if len(script_files) <= 20 else f'... 还有 {len(script_files) - 20} 个文件'}

### EXE 补丁
{'已打包 Sango7.exe（含解除限制补丁）' if exe_packed else '未包含 EXE'}
"""
        with open(os.path.join(export_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme)

        # 4. 写入元数据
        mod_info["files"] = all_files
        mod_info["changed_files"] = changed_files
        mod_info["shape_files"] = shape_files
        mod_info["script_files"] = script_files
        mod_info["exe_packed"] = exe_packed
        mod_info["total_files"] = len(all_files) + len(shape_files) + len(script_files) + (1 if exe_packed else 0)
        mod_info["changed_count"] = changed_count

        with open(os.path.join(export_dir, "mod_info.json"), "w", encoding="utf-8") as f:
            json.dump(mod_info, f, ensure_ascii=False, indent=2)

        # 5. 生成 ZIP 可分发包
        zip_path = os.path.join(WRITE_ROOT, "exports", f"{mod_name}_v{mod_info['version']}.zip")
        try:
            import zipfile
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(export_dir):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        arcname = os.path.relpath(fpath, export_dir)
                        zf.write(fpath, arcname)
            zip_size = round(os.path.getsize(zip_path) / (1024 * 1024), 2)
        except Exception as e:
            zip_path = None
            zip_size = 0
            logger.error(f"ZIP打包失败: {e}")

        return {
            "success": True,
            "message": f"MOD发布完成：{changed_count}个文件变更 + {len(shape_files)}个资源 + {len(script_files)}个脚本{' + EXE' if exe_packed else ''}",
            "files": all_files,
            "changedFiles": changed_files,
            "shapeFiles": shape_files,
            "scriptFiles": script_files,
            "exePacked": exe_packed,
            "fileCount": len(all_files),
            "changedCount": changed_count,
            "exportPath": export_dir,
            "zipPath": zip_path,
            "zipSize": zip_size,
        }

    def api_pack_mod_one_click(self, mod_name: str) -> dict:
        """一键打包：自动创建快照 + 增量打包 + 生成ZIP"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        # 1. 先检查是否有活跃MOD
        if not mod_name:
            return {"success": False, "message": "请先创建或选择一个MOD工程"}
        # 2. 打包前校验
        validate_r = self.api_validate_all()
        if validate_r and validate_r.get("summary", {}).get("errors", 0) > 0:
            return {"success": False, "message": f"数据校验发现 {validate_r.get('summary', {}).get('errors', 0)} 个错误，请修复后再打包", "validation": validate_r}
        # 3. 自动创建快照
        snap_res = self.api_mod_snapshot(mod_name)
        if not snap_res.get("success"):
            return {"success": False, "message": f"快照创建失败: {snap_res.get('message', '')}"}
        # 3. 执行增量打包
        pack_res = self.api_pack_mod_incremental(mod_name)
        if pack_res.get("success"):
            pack_res["snapshot"] = snap_res.get("snapshot", "")
            pack_res["message"] = f"一键打包完成！共 {pack_res.get('changedCount', 0)} 个变更文件，{pack_res.get('zipSize', 0)}MB\nZIP: {pack_res.get('zipPath', '')}"
        return pack_res

    # V3.8.0: MOD打包增强
    def api_pack_mod_full(self, mod_name: str, include_shape: bool = True, include_script: bool = True, include_exe: bool = True, compress: bool = True) -> dict:
        """完整打包：全量打包MOD（非增量），包含所有指定资源"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        mod_dir = os.path.join(WRITE_ROOT, "mods", mod_name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{mod_name}' 不存在"}

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if os.path.exists(export_dir):
            shutil.rmtree(export_dir)
        os.makedirs(export_dir, exist_ok=True)

        stats = {"setting": 0, "shape": 0, "script": 0, "exe": 0}

        # 打包Setting
        setting_dir = os.path.join(self.game_path, "Setting")
        if os.path.exists(setting_dir):
            for root, _, files in os.walk(setting_dir):
                for fname in files:
                    src = os.path.join(root, fname)
                    rel = os.path.relpath(src, setting_dir)
                    dst = os.path.join(export_dir, "Setting", rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    stats["setting"] += 1

        # 打包Shape
        if include_shape:
            shape_dir = os.path.join(self.game_path, "Shape")
            if os.path.exists(shape_dir):
                for root, _, files in os.walk(shape_dir):
                    for fname in files:
                        src = os.path.join(root, fname)
                        rel = os.path.relpath(src, shape_dir)
                        dst = os.path.join(export_dir, "Shape", rel)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
                        stats["shape"] += 1

        # 打包Script
        if include_script:
            script_dir = os.path.join(self.game_path, "Script")
            if os.path.exists(script_dir):
                for root, _, files in os.walk(script_dir):
                    for fname in files:
                        src = os.path.join(root, fname)
                        rel = os.path.relpath(src, script_dir)
                        dst = os.path.join(export_dir, "Script", rel)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
                        stats["script"] += 1

        # 打包EXE
        if include_exe:
            exe_src = os.path.join(self.game_path, "Sango7.exe")
            if os.path.exists(exe_src):
                shutil.copy2(exe_src, os.path.join(export_dir, "Sango7.exe"))
                stats["exe"] = 1

        # 生成元数据
        mod_info = {
            "name": mod_name,
            "version": "1.0.0",
            "packed": time.strftime("%Y-%m-%d %H:%M:%S"),
            "type": "full",
            "stats": stats,
            "total_files": sum(stats.values()),
        }
        with open(os.path.join(export_dir, "mod_info.json"), "w", encoding="utf-8") as f:
            json.dump(mod_info, f, ensure_ascii=False, indent=2)

        with open(os.path.join(export_dir, "pack_meta.json"), "w", encoding="utf-8") as f:
            json.dump({"packed_at": time.strftime("%Y-%m-%d %H:%M:%S"), "type": "full", "source": "San7ModMaker V3.8.0"}, f, ensure_ascii=False, indent=2)

        # 压缩
        zip_path = ""
        zip_size = 0
        if compress:
            zip_path = os.path.join(WRITE_ROOT, "exports", f"{mod_name}_full.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(export_dir):
                    for fname in files:
                        if fname in ("mod_info.json", "pack_meta.json"):
                            continue
                        fp = os.path.join(root, fname)
                        zf.write(fp, os.path.relpath(fp, export_dir))
            zip_size = round(os.path.getsize(zip_path) / 1024 / 1024, 1)

        return {
            "success": True,
            "message": f"完整打包完成：{sum(stats.values())} 个文件",
            "stats": stats,
            "total_files": sum(stats.values()),
            "zip_path": zip_path,
            "zip_size_mb": zip_size,
            "export_dir": export_dir,
        }

    def api_pack_mod_distribution(self, mod_name: str, author: str = "", description: str = "", version: str = "1.0.0") -> dict:
        """生成MOD分发包：完整打包 + 安装说明 + 截图目录 + 版本信息"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        # 使用完整打包
        pack_result = self.api_pack_mod_full(mod_name, include_shape=True, include_script=True, include_exe=True, compress=True)
        if not pack_result.get("success"):
            return pack_result

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)

        # 更新元数据
        info_path = os.path.join(export_dir, "mod_info.json")
        if os.path.exists(info_path):
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            info["author"] = author
            info["description"] = description
            info["version"] = version
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)

        # 生成安装说明
        readme = f"""# {mod_name} v{version}
        
## 作者
{author or '未知'}

## 描述
{description or '无描述'}

## 安装方法
1. 将 Setting/ 文件夹复制到游戏目录
2. 将 Shape/ 文件夹（如有）合并到游戏目录的 Shape/ 文件夹
3. 将 Script/ 文件夹（如有）复制到游戏目录的 Script/ 文件夹
4. 如有 Sango7.exe，替换游戏目录中的原文件
5. 启动游戏即可

## 文件统计
- Setting: {pack_result['stats'].get('setting', 0)} 个文件
- Shape: {pack_result['stats'].get('shape', 0)} 个文件
- Script: {pack_result['stats'].get('script', 0)} 个文件
- EXE: {'是' if pack_result['stats'].get('exe', 0) > 0 else '否'}

## 打包信息
- 打包时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
- 工具: San7ModMaker V3.8.0
"""
        # 创建screenshots目录
        screenshots_dir = os.path.join(export_dir, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)

        with open(os.path.join(export_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme)

        return {
            "success": True,
            "message": f"MOD分发包生成完成: {mod_name} v{version}",
            "mod_name": mod_name,
            "version": version,
            "author": author,
            "export_dir": export_dir,
            "zip_path": pack_result.get("zip_path", ""),
            "zip_size_mb": pack_result.get("zip_size_mb", 0),
            "total_files": pack_result.get("total_files", 0),
            "screenshots_dir": screenshots_dir,
        }

    def api_pack_mod_preset(self, action: str = "list", name: str = "", config: dict = None) -> dict:
        """打包预设配置管理：save/load/list/delete预设"""
        preset_dir = os.path.join(WRITE_ROOT, "mods", ".pack_presets")
        os.makedirs(preset_dir, exist_ok=True)

        if action == "list":
            presets = []
            if os.path.exists(preset_dir):
                for fname in os.listdir(preset_dir):
                    if fname.endswith(".json"):
                        preset_path = os.path.join(preset_dir, fname)
                        try:
                            with open(preset_path, "r", encoding="utf-8") as f:
                                p = json.load(f)
                            presets.append({
                                "name": p.get("name", ""),
                                "include_shape": p.get("include_shape", True),
                                "include_script": p.get("include_script", True),
                                "include_exe": p.get("include_exe", True),
                                "compress": p.get("compress", True),
                                "created": p.get("created", ""),
                            })
                        except Exception:
                            continue
            return {"success": True, "presets": presets}

        elif action == "save" and name and config:
            preset_path = os.path.join(preset_dir, f"{name}.json")
            config["name"] = name
            config["created"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(preset_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return {"success": True, "message": f"预设 '{name}' 已保存"}

        elif action == "load" and name:
            preset_path = os.path.join(preset_dir, f"{name}.json")
            if not os.path.exists(preset_path):
                return {"success": False, "message": f"预设 '{name}' 不存在"}
            with open(preset_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return {"success": True, "config": config}

        elif action == "delete" and name:
            preset_path = os.path.join(preset_dir, f"{name}.json")
            if os.path.exists(preset_path):
                os.remove(preset_path)
            return {"success": True, "message": f"预设 '{name}' 已删除"}

        return {"success": False, "message": "无效操作"}

    def api_import_mod(self, import_name: str = None, auto_remap: bool = True, backup_first: bool = True) -> dict:
        """导入MOD（从导出的MOD包导入）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        if not HAS_TK:
            return {"success": False, "message": "当前环境不支持文件对话框"}

        # 选择导出目录
        root = tk.Tk()
        root.withdraw()
        source_dir = filedialog.askdirectory(title="选择MOD导出目录（包含mod_pack_info.json的文件夹）")
        root.destroy()

        if not source_dir:
            return {"success": False, "message": "未选择目录"}

        info_file = os.path.join(source_dir, "mod_pack_info.json")
        if not os.path.exists(info_file):
            return {"success": False, "message": "所选目录不是有效的MOD包（缺少mod_pack_info.json）"}

        with open(info_file, "r", encoding="utf-8") as f:
            pack_info = json.load(f)

        final_name = import_name or pack_info.get("name", "imported_mod")

        # 备份当前数据
        if backup_first and self.backup_mgr:
            self.backup_mgr.backup_all_settings()

        # 检测冲突
        conflicts = []
        if auto_remap:
            setting_dir = os.path.join(self.game_path, "Setting")
            for ini_file in pack_info.get("changed_files", []):
                src_file = os.path.join(source_dir, ini_file)
                dst_file = os.path.join(setting_dir, ini_file)
                if os.path.exists(src_file) and os.path.exists(dst_file):
                    conflicts.extend(self._detect_ini_conflicts(src_file, dst_file, ini_file))

        # 如果无冲突或有冲突但已展示，直接复制文件
        if not conflicts:
            setting_dir = os.path.join(self.game_path, "Setting")
            for ini_file in pack_info.get("changed_files", []):
                src_file = os.path.join(source_dir, ini_file)
                dst_file = os.path.join(setting_dir, ini_file)
                if os.path.exists(src_file):
                    shutil.copy2(src_file, dst_file)

        # 创建MOD工程记录
        mod_dir = os.path.join(WRITE_ROOT, "mods", final_name)
        if not os.path.exists(mod_dir):
            os.makedirs(mod_dir, exist_ok=True)
            os.makedirs(os.path.join(mod_dir, "data"), exist_ok=True)
            os.makedirs(os.path.join(mod_dir, "snapshots"), exist_ok=True)
            info = {
                "name": final_name,
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "version": pack_info.get("version", "1.0"),
                "description": pack_info.get("description", "导入的MOD"),
                "imported_from": source_dir,
                "snapshot_count": 0,
            }
            with open(os.path.join(mod_dir, "mod_info.json"), "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": f"MOD '{final_name}' 导入成功",
            "conflicts": conflicts,
            "conflictCount": len(conflicts),
            "importName": final_name,
        }

    def _detect_ini_conflicts(self, src_file: str, dst_file: str, filename: str) -> List[dict]:
        """检测两个INI文件之间的ID冲突"""
        conflicts = []
        try:
            parser_src = IniParser()
            parser_src.load(src_file)
            parser_dst = IniParser()
            parser_dst.load(dst_file)

            # 获取所有section名
            src_nos = {}
            dst_nos = {}
            for s in parser_src.sections:
                no = s.entries.get("No", "")
                if no:
                    src_nos[no] = s.entries.get("Name", "")
            for s in parser_dst.sections:
                no = s.entries.get("No", "")
                if no:
                    dst_nos[no] = s.entries.get("Name", "")

            # 找冲突的ID
            for no in src_nos:
                if no in dst_nos:
                    # 找到一个新的未使用ID
                    all_nos = set(int(n) for n in dst_nos.keys() if n.isdigit())
                    suggested = 10000
                    while suggested in all_nos:
                        suggested += 1
                    conflicts.append({
                        "file": filename,
                        "existingId": no,
                        "importId": no,
                        "existingName": dst_nos[no],
                        "importName": src_nos[no],
                        "suggestedId": suggested,
                    })
        except Exception as e:
            logger.warning(f"冲突重映射失败: {e}")
        return conflicts

    def api_remap_conflicts(self, conflict_data: dict) -> dict:
        """重映射冲突ID"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        setting_dir = os.path.join(self.game_path, "Setting")
        remapped = 0

        for conflict in conflict_data.get("conflicts", []):
            filename = conflict.get("file", "")
            old_id = str(conflict.get("importId", ""))
            new_id = str(conflict.get("suggestedId", ""))
            if not filename or not old_id or not new_id:
                continue

            file_path = os.path.join(setting_dir, filename)
            if not os.path.exists(file_path):
                continue

            # 备份
            if self.backup_mgr:
                self.backup_mgr.backup_file(file_path)

            # 读取并重映射
            try:
                with open(file_path, "r", encoding="big5", errors="replace") as f:
                    content = f.read()

                # 替换 No=old_id 为 No=new_id（对 old_id 做正则转义）
                import re
                escaped_id = re.escape(str(old_id))
                content = re.sub(rf'(\bNo\s*=\s*){escaped_id}\b', rf'\g<1>{new_id}', content)

                with open(file_path, "w", encoding="big5", errors="replace") as f:
                    f.write(content)
                remapped += 1
            except Exception as e:
                logger.warning(f"重映射写入失败 {file_path}: {e}")
                continue

        return {"success": True, "message": f"已重映射 {remapped} 个冲突", "remapped": remapped}

    # ============================================================
    # API: MOD 安装/卸载
    # ============================================================

    def api_preview_mod_install(self, mod_name: str) -> dict:
        """预览MOD安装：列出MOD将修改/新增的所有文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if not os.path.exists(export_dir):
            return {"success": False, "message": f"MOD包 '{mod_name}' 不存在，请先打包"}

        # 读取MOD元数据
        info_path = os.path.join(export_dir, "mod_info.json")
        mod_info = {}
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    mod_info = json.load(f)
            except Exception:
                pass

        will_overwrite = []
        will_create = []
        setting_src = os.path.join(export_dir, "Setting")
        setting_dst = os.path.join(self.game_path, "Setting")
        if os.path.exists(setting_src):
            for root, _, files in os.walk(setting_src):
                for fname in files:
                    rel = os.path.join("Setting", os.path.relpath(os.path.join(root, fname), setting_src))
                    dst = os.path.join(self.game_path, rel)
                    entry = {"file": rel, "size_kb": round(os.path.getsize(os.path.join(root, fname)) / 1024, 1)}
                    if os.path.exists(dst):
                        entry["action"] = "覆盖"
                        will_overwrite.append(entry)
                    else:
                        entry["action"] = "新增"
                        will_create.append(entry)

        shape_src = os.path.join(export_dir, "Shape")
        shape_dst = os.path.join(self.game_path, "Shape")
        if os.path.exists(shape_src):
            for root, _, files in os.walk(shape_src):
                for fname in files:
                    rel = os.path.join("Shape", os.path.relpath(os.path.join(root, fname), shape_src))
                    dst = os.path.join(self.game_path, rel)
                    entry = {"file": rel, "size_kb": round(os.path.getsize(os.path.join(root, fname)) / 1024, 1)}
                    if os.path.exists(dst):
                        entry["action"] = "覆盖"
                        will_overwrite.append(entry)
                    else:
                        entry["action"] = "新增"
                        will_create.append(entry)

        total = len(will_overwrite) + len(will_create)
        return {
            "success": True,
            "mod_name": mod_name,
            "mod_info": mod_info,
            "will_overwrite": will_overwrite,
            "will_create": will_create,
            "total_files": total,
            "overwrite_count": len(will_overwrite),
            "create_count": len(will_create),
            "message": f"将{('覆盖'+str(len(will_overwrite))+'个' if will_overwrite else '')} {'新增' if will_create else ''}{len(will_create)}个文件" if total > 0 else "该MOD不包含任何文件",
        }

    def api_check_mod_compatibility(self, mod_name: str) -> dict:
        """检查MOD与当前游戏版本的兼容性"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if not os.path.exists(export_dir):
            return {"success": False, "message": f"MOD包 '{mod_name}' 不存在，请先打包"}

        # 读取MOD元数据
        info_path = os.path.join(export_dir, "mod_info.json")
        mod_info = {}
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    mod_info = json.load(f)
            except Exception:
                pass

        # 检测游戏版本
        game_info = self.api_get_game_info()
        version_info = self.version_detector.detect() if self.version_detector else {}

        # 检查兼容性
        warnings = []
        issues = []

        # 1. 检查 EXE 是否存在
        if not game_info.get("has_exe"):
            issues.append("未检测到 Sango7.exe，游戏可能未正确安装")

        # 2. 检查 MOD 声明的最低版本要求
        required_version = mod_info.get("min_game_version", "")
        if required_version and version_info:
            game_version = version_info.get("version", "")
            if game_version and game_version < required_version:
                issues.append(f"MOD要求游戏版本 ≥ {required_version}，当前版本: {game_version}")

        # 3. 检查 MOD 打包时间 vs 游戏文件时间
        mod_pack_time = mod_info.get("packed_at", "")
        if mod_pack_time and version_info.get("file_timestamp"):
            if version_info["file_timestamp"] > mod_pack_time:
                warnings.append("游戏文件比MOD打包时间更新，安装后可能覆盖游戏更新")

        # 4. 检查 MOD 声明的依赖
        mod_dependencies = mod_info.get("dependencies", [])
        if mod_dependencies:
            installed_log = os.path.join(WRITE_ROOT, "mods", ".installed_mods.json")
            installed = {}
            if os.path.exists(installed_log):
                try:
                    with open(installed_log, "r", encoding="utf-8") as f:
                        installed = json.load(f)
                except Exception:
                    pass
            missing_deps = []
            for dep in mod_dependencies:
                dep_name = dep if isinstance(dep, str) else dep.get("name", "")
                if dep_name and dep_name not in installed:
                    missing_deps.append(dep_name)
            if missing_deps:
                issues.append(f"缺少依赖MOD: {', '.join(missing_deps)}")

        return {
            "success": True,
            "compatible": len(issues) == 0,
            "mod_name": mod_name,
            "mod_info": mod_info,
            "game_version": version_info.get("version", "unknown"),
            "game_version_name": version_info.get("version_name", "未知版本"),
            "warnings": warnings,
            "issues": issues,
            "message": "兼容性检查通过" if len(issues) == 0 else f"发现 {len(issues)} 个兼容性问题",
        }

    # ==================== MOD 依赖管理 ====================

    def api_set_mod_dependencies(self, mod_name: str, dependencies: List[dict] = None) -> dict:
        """设置MOD的依赖声明"""
        mod_dir = os.path.join(WRITE_ROOT, "mods", mod_name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{mod_name}' 不存在"}

        info_path = os.path.join(mod_dir, "mod_info.json")
        info = {}
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
            except Exception:
                pass

        # 规范化依赖格式
        normalized = []
        if dependencies:
            for dep in dependencies:
                if isinstance(dep, str):
                    normalized.append({"name": dep, "version": "*"})
                elif isinstance(dep, dict):
                    normalized.append({
                        "name": dep.get("name", ""),
                        "version": dep.get("version", "*"),
                        "required": dep.get("required", True),
                    })

        info["dependencies"] = normalized
        info["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(info_path), exist_ok=True)
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "dependencies": normalized,
            "message": f"已设置 {len(normalized)} 个依赖",
        }

    def api_get_mod_dependencies(self, mod_name: str) -> dict:
        """获取MOD的依赖列表及其满足状态"""
        mod_dir = os.path.join(WRITE_ROOT, "mods", mod_name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{mod_name}' 不存在"}

        info_path = os.path.join(mod_dir, "mod_info.json")
        info = {}
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
            except Exception:
                pass

        dependencies = info.get("dependencies", [])

        # 获取所有可用MOD列表
        mods_list = []
        mods_path = os.path.join(WRITE_ROOT, "mods")
        if os.path.exists(mods_path):
            for name in os.listdir(mods_path):
                mp = os.path.join(mods_path, name)
                if os.path.isdir(mp):
                    mi_path = os.path.join(mp, "mod_info.json")
                    mi = {}
                    if os.path.exists(mi_path):
                        try:
                            with open(mi_path, "r", encoding="utf-8") as f:
                                mi = json.load(f)
                        except Exception:
                            pass
                    mods_list.append({
                        "name": name,
                        "version": mi.get("version", "1.0"),
                        "description": mi.get("description", ""),
                    })

        # 检查每个依赖是否满足
        satisfied_count = 0
        for dep in dependencies:
            dep_name = dep.get("name", dep) if isinstance(dep, dict) else dep
            dep_version = dep.get("version", "*") if isinstance(dep, dict) else "*"
            dep["satisfied"] = False
            dep["available_version"] = None
            for m in mods_list:
                if m["name"] == dep_name:
                    dep["available_version"] = m["version"]
                    if dep_version == "*" or dep_version == m["version"]:
                        dep["satisfied"] = True
                        satisfied_count += 1
                    break

        return {
            "success": True,
            "mod_name": mod_name,
            "dependencies": dependencies,
            "total": len(dependencies),
            "satisfied": satisfied_count,
            "all_satisfied": satisfied_count == len(dependencies) if dependencies else True,
            "available_mods": [m["name"] for m in mods_list],
            "message": f"依赖满足: {satisfied_count}/{len(dependencies)}" if dependencies else "该MOD无依赖声明",
        }

    def api_check_mod_dependencies(self, mod_name: str) -> dict:
        """检查MOD的所有依赖是否满足，返回详细的依赖报告"""
        result = self.api_get_mod_dependencies(mod_name)
        if not result.get("success"):
            return result

        dependencies = result.get("dependencies", [])
        missing = []
        warnings = []
        for dep in dependencies:
            if not dep.get("satisfied"):
                dep_name = dep.get("name", "?")
                if dep.get("available_version"):
                    warnings.append(f"依赖 '{dep_name}' 版本不匹配: 需要 {dep.get('version', '*')}, 可用 {dep['available_version']}")
                else:
                    missing.append(f"依赖 '{dep_name}' 不可用")

        result["missing"] = missing
        result["warnings"] = warnings
        result["ok"] = len(missing) == 0 and len(warnings) == 0
        result["message"] = "所有依赖已满足" if result["ok"] else (
            f"缺 {len(missing)} 个依赖" + (f", {len(warnings)} 个版本不匹配" if warnings else "")
        )
        return result

    def api_mod_conflict_detect(self, mod_a: str, mod_b: str) -> dict:
        """检测两个MOD之间的文件冲突"""
        mods_dir = os.path.join(WRITE_ROOT, "mods")
        mod_a_path = os.path.join(mods_dir, mod_a)
        mod_b_path = os.path.join(mods_dir, mod_b)
        if not os.path.exists(mod_a_path):
            return {"success": False, "message": f"MOD A 不存在: {mod_a}"}
        if not os.path.exists(mod_b_path):
            return {"success": False, "message": f"MOD B 不存在: {mod_b}"}

        # 获取两个MOD的文件列表
        def _get_files(mod_path):
            files = set()
            for sub in ["data", "exports"]:
                sub_path = os.path.join(mod_path, sub)
                if os.path.exists(sub_path):
                    for root, _, fnames in os.walk(sub_path):
                        for fn in fnames:
                            files.add(os.path.relpath(os.path.join(root, fn), mod_path))
            return files

        files_a = _get_files(mod_a_path)
        files_b = _get_files(mod_b_path)

        conflicts = sorted(files_a & files_b)
        summary = {
            "mod_a": mod_a,
            "mod_b": mod_b,
            "files_a_count": len(files_a),
            "files_b_count": len(files_b),
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
            "has_conflicts": len(conflicts) > 0,
        }

        return {
            "success": True,
            **summary,
            "message": f"检测到 {len(conflicts)} 个文件冲突" if conflicts else "无冲突",
        }

    def api_install_mod(self, mod_name: str) -> dict:
        """安装MOD：将 exports/ 中的MOD文件复制到游戏目录，并记录安装状态"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if not os.path.exists(export_dir):
            return {"success": False, "message": f"MOD包 '{mod_name}' 不存在，请先打包"}

        # 读取MOD元数据
        info_path = os.path.join(export_dir, "mod_info.json")
        mod_info = {}
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    mod_info = json.load(f)
            except Exception:
                logger.warning("读取mod_info.json失败，将使用默认配置")

        # 依赖检查：安装前检查依赖是否满足
        dep_check = self.api_check_mod_dependencies(mod_name)
        if dep_check.get("success") and not dep_check.get("ok"):
            missing = dep_check.get("missing", [])
            warnings = dep_check.get("warnings", [])
            dep_issues = []
            if missing:
                dep_issues.extend(missing)
            if warnings:
                dep_issues.extend(warnings)
            # 不阻止安装，但返回警告
            logger.warning(f"MOD '{mod_name}' 依赖检查发现问题: {'; '.join(dep_issues)}")

        installed_files = []
        install_backups = {}  # 记录每个文件对应的备份路径，用于精确还原
        setting_src = os.path.join(export_dir, "Setting")
        if os.path.exists(setting_src):
            setting_dst = os.path.join(self.game_path, "Setting")
            for root, _, files in os.walk(setting_src):
                for fname in files:
                    src = os.path.join(root, fname)
                    rel = os.path.relpath(src, setting_src)
                    dst = os.path.join(setting_dst, rel)
                    # 备份原始文件并记录备份路径
                    if os.path.exists(dst) and self.backup_mgr:
                        backup_path = self.backup_mgr.backup_file(dst)
                        install_backups[os.path.join("Setting", rel)] = backup_path
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    installed_files.append(os.path.join("Setting", rel))

        shape_src = os.path.join(export_dir, "Shape")
        if os.path.exists(shape_src):
            shape_dst = os.path.join(self.game_path, "Shape")
            for root, _, files in os.walk(shape_src):
                for fname in files:
                    src = os.path.join(root, fname)
                    rel = os.path.relpath(src, shape_src)
                    dst = os.path.join(shape_dst, rel)
                    if os.path.exists(dst) and self.backup_mgr:
                        backup_path = self.backup_mgr.backup_file(dst)
                        install_backups[os.path.join("Shape", rel)] = backup_path
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    installed_files.append(os.path.join("Shape", rel))

        # 记录安装状态（含备份路径用于精确还原）
        install_log = os.path.join(WRITE_ROOT, "mods", ".installed_mods.json")
        installed_mods = {}
        if os.path.exists(install_log):
            try:
                with open(install_log, "r", encoding="utf-8") as f:
                    installed_mods = json.load(f)
            except Exception:
                logger.warning("读取install_log.json失败，将创建新记录")
        installed_mods[mod_name] = {
            "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": mod_info.get("version", "1.0"),
            "files": installed_files,
            "file_count": len(installed_files),
            "backups": install_backups,  # 精确备份路径，用于卸载时还原
        }
        with open(install_log, "w", encoding="utf-8") as f:
            json.dump(installed_mods, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": f"MOD '{mod_name}' 安装成功，{len(installed_files)} 个文件已部署",
            "installedFiles": len(installed_files),
        }

    def api_uninstall_mod(self, mod_name: str) -> dict:
        """卸载MOD：通过备份还原MOD安装时被替换的文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        install_log = os.path.join(WRITE_ROOT, "mods", ".installed_mods.json")
        if not os.path.exists(install_log):
            return {"success": False, "message": "没有已安装的MOD记录"}

        try:
            with open(install_log, "r", encoding="utf-8") as f:
                installed_mods = json.load(f)
        except Exception:
            return {"success": False, "message": "安装记录文件损坏"}

        if mod_name not in installed_mods:
            return {"success": False, "message": f"MOD '{mod_name}' 未安装"}

        mod_record = installed_mods[mod_name]
        restored = 0
        failed = 0
        install_backups = mod_record.get("backups", {})

        for f in mod_record.get("files", []):
            file_path = os.path.join(self.game_path, f)
            # 优先使用安装时记录的精确备份路径
            backup_path = install_backups.get(f, "")
            if backup_path and os.path.exists(backup_path):
                try:
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    shutil.copy2(backup_path, file_path)
                    restored += 1
                    continue
                except Exception as e:
                    logger.warning(f"MOD卸载恢复失败: {e}")
            # 回退：使用最新备份
            if self.backup_mgr:
                backup_record = self.backup_mgr.get_latest_backup(file_path)
                if backup_record:
                    backup_file = backup_record.get("backup_path", "")
                    if backup_file and os.path.exists(backup_file):
                        try:
                            os.makedirs(os.path.dirname(file_path), exist_ok=True)
                            shutil.copy2(backup_file, file_path)
                            restored += 1
                        except Exception as e:
                            logger.warning(f"还原文件失败: {file_path}: {e}")
                            failed += 1

        # 删除安装记录
        del installed_mods[mod_name]
        with open(install_log, "w", encoding="utf-8") as f:
            json.dump(installed_mods, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": f"MOD '{mod_name}' 已卸载，还原 {restored} 个文件" + (f"，{failed} 个失败" if failed else ""),
            "restored": restored,
            "failed": failed,
        }

    def api_list_installed_mods(self) -> dict:
        """列出已安装的MOD"""
        install_log = os.path.join(WRITE_ROOT, "mods", ".installed_mods.json")
        if not os.path.exists(install_log):
            return {"success": True, "mods": {}}
        try:
            with open(install_log, "r", encoding="utf-8") as f:
                mods = json.load(f)
            return {"success": True, "mods": mods}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ============================================================
    # V3.7.0: MOD 安装回滚 / 重新安装 / 打包校验
    # ============================================================

    def api_mod_rollback(self, mod_name: str) -> dict:
        """回滚MOD安装：使用安装记录中的备份精确还原文件，但保留安装记录"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        install_log = os.path.join(WRITE_ROOT, "mods", ".installed_mods.json")
        if not os.path.exists(install_log):
            return {"success": False, "message": "没有已安装的MOD记录"}

        try:
            with open(install_log, "r", encoding="utf-8") as f:
                installed_mods = json.load(f)
        except Exception:
            return {"success": False, "message": "安装记录文件损坏"}

        if mod_name not in installed_mods:
            return {"success": False, "message": f"MOD '{mod_name}' 未安装"}

        mod_record = installed_mods[mod_name]
        restored = 0
        failed = 0
        skipped = 0
        install_backups = mod_record.get("backups", {})

        for f in mod_record.get("files", []):
            file_path = os.path.join(self.game_path, f)
            backup_path = install_backups.get(f, "")
            if backup_path and os.path.exists(backup_path):
                try:
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    shutil.copy2(backup_path, file_path)
                    restored += 1
                except Exception as e:
                    logger.warning(f"回滚失败: {f}: {e}")
                    failed += 1
            elif self.backup_mgr:
                backup_record = self.backup_mgr.get_latest_backup(file_path)
                if backup_record:
                    backup_file = backup_record.get("backup_path", "")
                    if backup_file and os.path.exists(backup_file):
                        try:
                            os.makedirs(os.path.dirname(file_path), exist_ok=True)
                            shutil.copy2(backup_file, file_path)
                            restored += 1
                        except Exception as e:
                            logger.warning(f"回滚失败: {f}: {e}")
                            failed += 1
                    else:
                        skipped += 1
                else:
                    skipped += 1
            else:
                skipped += 1

        # 更新安装记录中的回滚计数
        installed_mods[mod_name]["rollback_count"] = installed_mods[mod_name].get("rollback_count", 0) + 1
        installed_mods[mod_name]["last_rollback"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(install_log, "w", encoding="utf-8") as f:
            json.dump(installed_mods, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": f"MOD '{mod_name}' 回滚完成，成功还原 {restored} 个文件" + (f"，{failed} 个失败" if failed else "") + (f"，{skipped} 个跳过" if skipped else ""),
            "restored": restored,
            "failed": failed,
            "skipped": skipped,
        }

    def api_mod_reinstall(self, mod_name: str) -> dict:
        """重新安装MOD：先回滚再重新安装，适用于MOD包更新后重装"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        # 先回滚
        rollback_result = self.api_mod_rollback(mod_name)
        if not rollback_result.get("success"):
            return {"success": False, "message": f"回滚失败，无法重新安装: {rollback_result.get('message')}"}

        # 重新安装
        install_result = self.api_install_mod(mod_name)
        if not install_result.get("success"):
            return {"success": False, "message": f"安装失败: {install_result.get('message')}"}

        return {
            "success": True,
            "message": f"MOD '{mod_name}' 重新安装完成，{install_result.get('installedFiles', 0)} 个文件已部署",
            "rollback": {"restored": rollback_result.get("restored", 0)},
            "install": {"installedFiles": install_result.get("installedFiles", 0)},
        }

    def api_mod_validate_pack(self, mod_name: str) -> dict:
        """验证MOD打包完整性：检查目录结构、必要文件、文件大小、引用完整性"""
        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if not os.path.exists(export_dir):
            return {"success": False, "message": f"MOD包 '{mod_name}' 不存在，请先打包"}

        issues = []
        warnings = []
        info = {}

        # 1. 检查必要文件
        required_files = ["mod_info.json", "pack_meta.json"]
        missing = []
        for f in required_files:
            if not os.path.exists(os.path.join(export_dir, f)):
                missing.append(f)
        if missing:
            issues.append(f"缺少必要文件: {', '.join(missing)}")

        # 2. 检查目录结构
        has_setting = os.path.exists(os.path.join(export_dir, "Setting"))
        has_shape = os.path.exists(os.path.join(export_dir, "Shape"))
        if not has_setting and not has_shape:
            issues.append("缺少Setting或Shape目录，MOD包为空")

        # 3. 统计文件
        file_count = 0
        total_size = 0
        large_files = []
        setting_count = 0
        shape_count = 0

        if has_setting:
            for root, _, files in os.walk(os.path.join(export_dir, "Setting")):
                for fname in files:
                    fp = os.path.join(root, fname)
                    sz = os.path.getsize(fp)
                    file_count += 1
                    total_size += sz
                    setting_count += 1
                    if sz > 50 * 1024 * 1024:  # 50MB
                        large_files.append({"file": os.path.relpath(fp, export_dir), "size_mb": round(sz / 1024 / 1024, 1)})

        if has_shape:
            for root, _, files in os.walk(os.path.join(export_dir, "Shape")):
                for fname in files:
                    fp = os.path.join(root, fname)
                    sz = os.path.getsize(fp)
                    file_count += 1
                    total_size += sz
                    shape_count += 1
                    if sz > 50 * 1024 * 1024:
                        large_files.append({"file": os.path.relpath(fp, export_dir), "size_mb": round(sz / 1024 / 1024, 1)})

        if large_files:
            warnings.append(f"{len(large_files)} 个大文件（>50MB），可能影响分发")

        info = {
            "file_count": file_count,
            "total_size_mb": round(total_size / 1024 / 1024, 1),
            "setting_files": setting_count,
            "shape_files": shape_count,
        }

        # 4. 检查mod_info.json内容
        info_path = os.path.join(export_dir, "mod_info.json")
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    mod_info = json.load(f)
                info["mod_name"] = mod_info.get("name", "")
                info["version"] = mod_info.get("version", "")
                info["author"] = mod_info.get("author", "")
                if not mod_info.get("name"):
                    warnings.append("mod_info.json中缺少name字段")
                if not mod_info.get("version"):
                    warnings.append("mod_info.json中缺少version字段")
            except Exception:
                issues.append("mod_info.json格式无效")

        # 5. 检查pack_meta.json内容
        meta_path = os.path.join(export_dir, "pack_meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                info["packed_at"] = meta.get("packed_at", "")
                info["source"] = meta.get("source", "")
            except Exception:
                warnings.append("pack_meta.json格式无效")

        valid = len(issues) == 0
        return {
            "success": True,
            "valid": valid,
            "message": "MOD包验证通过" if valid else f"发现 {len(issues)} 个问题，{len(warnings)} 个警告",
            "issues": issues,
            "warnings": warnings,
            "info": info,
            "large_files": large_files,
        }

    def api_launch_game(self, mod_name: str = None) -> dict:
        """启动游戏（可指定MOD名称）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        exe_path = os.path.join(self.game_path, "SG7.exe")
        if not os.path.exists(exe_path):
            # 尝试其他常见名称
            for alt in ["Sango7.exe", "Sango6.exe", "SG6.exe"]:
                alt_path = os.path.join(self.game_path, alt)
                if os.path.exists(alt_path):
                    exe_path = alt_path
                    break
            else:
                return {"success": False, "message": f"未找到游戏主程序，请确保游戏目录下有 SG7.exe"}
        try:
            cwd = self.game_path
            if mod_name:
                # 如果指定了MOD，先确保MOD已安装
                install_log = os.path.join(WRITE_ROOT, "mods", ".installed_mods.json")
                if os.path.exists(install_log):
                    with open(install_log, "r", encoding="utf-8") as f:
                        installed = json.load(f)
                    if mod_name not in installed:
                        return {"success": False, "message": f"MOD '{mod_name}' 未安装，请先安装"}
            # 使用 subprocess 启动游戏（非阻塞）
            import subprocess
            if os.name == 'nt':
                subprocess.Popen([exe_path], cwd=cwd, shell=True)
            else:
                subprocess.Popen([exe_path], cwd=cwd)
            return {"success": True, "message": "游戏已启动" + (f" (MOD: {mod_name})" if mod_name else "")}
        except Exception as e:
            return {"success": False, "message": f"启动失败: {str(e)}"}


    # ============================================================
