import os, json, re, shutil, base64, tempfile, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional
from core.error_codes import safe_error_message, error_response, success_response

from core.config import WRITE_ROOT

logger = logging.getLogger('San7ModMaker')

__all__ = ['San7ModMakerTools']

class San7ModMakerTools:
    """MOD制作器 - 工具集 (备份/校验/EXE/批量/差异)"""

    # API: 备份还原
    # ============================================================

    def api_backup_all(self) -> dict:
        """全量备份"""
        if not self.backup_mgr:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        backed = self.backup_mgr.backup_all_settings()
        return {"success": True, "message": f"备份完成，共{len(backed)}个文件", "count": len(backed)}

    def api_restore_all(self) -> dict:
        """一键还原"""
        if not self.backup_mgr:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        results = self.backup_mgr.restore_all()
        success_count = sum(1 for v in results.values() if v)
        return {"success": True, "message": f"还原完成，成功{success_count}个", "details": results}

    def api_cleanup_backups(self, keep_count: int = 10) -> dict:
        """清理旧备份，每个文件只保留最近N个"""
        if not self.backup_mgr:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
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
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
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
                results.append({"file": fname, "success": False, "message": safe_error_message(e)})
        success_count = sum(1 for r in results if r["success"])
        return {"success": True, "message": f"批量转换完成: {success_count}/{len(results)} 成功", "results": results, "total": len(results), "successCount": success_count}

    def api_batch_rename(self, file_type: str, name_prefix: str, start_no: int = 1) -> dict:
        """批量重命名武将/物品/兵种的 Name 字段"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
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
        return success_response({"data": texts, "count": len(texts)})

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
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

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
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
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
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
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
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if self.backup_mgr:
            self.backup_mgr.backup_exe()
        return self.exe_patcher.apply_patch_auto(patch_name, new_value)

    def api_disassemble_exe(self, offset: int, count: int = 8) -> dict:
        """反汇编 EXE 指定偏移处的指令"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
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
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.exe_patcher.disassemble_scan_results(scan_name, top_n)

    def api_apply_nop_patch(self, offset: int, size: int) -> dict:
        """应用 NOP 补丁"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if self.backup_mgr:
            self.backup_mgr.backup_exe()
        ok = self.exe_patcher.apply_nop_patch(offset, size)
        return {"success": ok, "message": f"NOP {size}字节 @ {hex(offset)}" if ok else "写入失败"}

    def api_apply_jmp_patch(self, offset: int, target_offset: int, is_short: bool = True) -> dict:
        """应用 JMP 补丁"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if self.backup_mgr:
            self.backup_mgr.backup_exe()
        ok = self.exe_patcher.apply_jmp_patch(offset, target_offset, is_short)
        return {"success": ok, "message": f"JMP {hex(offset)} → {hex(target_offset)}" if ok else "JMP失败"}

    def api_apply_template_patch(self, template_name: str, offset: int, *args) -> dict:
        """应用预设补丁模板"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
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
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if self.backup_mgr:
            self.backup_mgr.backup_exe()
        return self.exe_patcher.apply_patch_auto(patch_id, value)

    # ============================================================
    # API: Sango7.ini 分辨率设置
    # ============================================================

    def api_get_sango7_config(self) -> dict:
        """读取 Sango7.ini 配置（分辨率、窗口模式等）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
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
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
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
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

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
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

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
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

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
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

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
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
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

