import os, json, re, shutil, base64, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional
from core.error_codes import ErrorCode, safe_error_message, error_response, success_response

from core.config import WRITE_ROOT, PROJECT_ROOT

from core.event_templates import EVENT_TEMPLATES, generate_event_section

logger = logging.getLogger('San7ModMaker')

__all__ = ['San7ModMakerAdvanced']

__all__ = ['San7ModMakerScripts']

class San7ModMakerScripts:
    """MOD制作器 - 脚本/自定义武将/全局搜索"""

    # ============================================================
    # API: CustomGen 自定义武将编辑
    # ============================================================
    def api_customgen_list(self) -> dict:
        """列出所有自定义武将"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        sav_path = os.path.join(self.game_path, "Save", "CustomGen.sav")
        if not os.path.exists(sav_path):
            return {"success": True, "generals": [], "count": 0, "message": "CustomGen.sav 不存在"}
        try:
            from core.save_editor import SaveEditor
            editor = SaveEditor(self.game_path)
            generals = editor.parse_customgen()
            return {"success": True, "generals": generals, "count": len(generals)}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_customgen_get(self, index: int) -> dict:
        """获取单个自定义武将详情"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        sav_path = os.path.join(self.game_path, "Save", "CustomGen.sav")
        if not os.path.exists(sav_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "CustomGen.sav 不存在")
        try:
            from core.save_editor import SaveEditor
            editor = SaveEditor(self.game_path)
            general = editor.get_customgen_detail(index)
            if general:
                return {"success": True, "general": general}
            return error_response(ErrorCode.INVALID_PARAM, "索引超出范围")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_customgen_edit(self, index: int, field: str, value) -> dict:
        """编辑自定义武将字段"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        sav_path = os.path.join(self.game_path, "Save", "CustomGen.sav")
        if not os.path.exists(sav_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "CustomGen.sav 不存在")
        try:
            from core.save_editor import SaveEditor
            if self.backup_mgr:
                self.backup_mgr.backup_file(sav_path)
            editor = SaveEditor(self.game_path)
            result = editor.edit_customgen_field(index, field, value)
            return result
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_customgen_add(self, name: str = "新武将") -> dict:
        """添加新的自定义武将"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            from core.save_editor import SaveEditor
            editor = SaveEditor(self.game_path)
            return editor.add_customgen(name)
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))



    def api_list_scripts(self) -> dict:
        """列出 Script/ 目录下的剧本脚本文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        script_dir = os.path.join(self.game_path, "Script")
        if not os.path.exists(script_dir):
            return {"success": True, "files": [], "message": "Script 目录不存在"}
        files = []
        for f in sorted(os.listdir(script_dir)):
            fpath = os.path.join(script_dir, f)
            if os.path.isfile(fpath):
                files.append({
                    "name": f,
                    "size": os.path.getsize(fpath),
                    "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                })
        return {"success": True, "files": files, "count": len(files)}

    def api_read_script(self, filename: str) -> dict:
        """读取脚本文件内容"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        safe_name = os.path.basename(filename)
        if safe_name != filename or '..' in filename:
            return error_response(ErrorCode.INVALID_PARAM, "无效的文件名")
        script_path = os.path.join(self.game_path, "Script", safe_name)
        if not os.path.exists(script_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"脚本文件不存在: {safe_name}")
        try:
            # 尝试多种编码
            content = ""
            for enc in ["gbk", "utf-8", "latin-1"]:
                try:
                    with open(script_path, "r", encoding=enc) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            return {
                "success": True,
                "filename": safe_name,
                "content": content,
                "lines": content.count('\n') + 1,
                "size_kb": round(os.path.getsize(script_path) / 1024, 1),
            }
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_save_script(self, filename: str, content: str) -> dict:
        """保存脚本文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        safe_name = os.path.basename(filename)
        if safe_name != filename or '..' in filename:
            return error_response(ErrorCode.INVALID_PARAM, "无效的文件名")
        script_path = os.path.join(self.game_path, "Script", safe_name)
        if not os.path.exists(script_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"脚本文件不存在: {safe_name}")
        if self.backup_mgr:
            self.backup_mgr.backup_file(script_path)
        try:
            with open(script_path, "w", encoding="big5", errors="replace") as f:
                f.write(content)
            return success_response(message=f"已保存: {safe_name}")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_new_script(self, filename: str) -> dict:
        """新建脚本文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        safe_name = os.path.basename(filename)
        if safe_name != filename or '..' in filename:
            return error_response(ErrorCode.INVALID_PARAM, "无效的文件名")
        script_dir = os.path.join(self.game_path, "Script")
        os.makedirs(script_dir, exist_ok=True)
        script_path = os.path.join(script_dir, safe_name)
        if os.path.exists(script_path):
            return error_response(ErrorCode.FILE_ALREADY_EXISTS, f"文件已存在: {safe_name}")
        try:
            with open(script_path, "w", encoding="big5", errors="replace") as f:
                f.write(f"; {safe_name}\n; 新建脚本\n")
            return success_response({"filename": safe_name}, message=f"已创建: {safe_name}")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_delete_script(self, filename: str) -> dict:
        """删除脚本文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        safe_name = os.path.basename(filename)
        if safe_name != filename or '..' in filename:
            return error_response(ErrorCode.INVALID_PARAM, "无效的文件名")
        script_path = os.path.join(self.game_path, "Script", safe_name)
        if not os.path.exists(script_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"文件不存在: {safe_name}")
        if self.backup_mgr:
            self.backup_mgr.backup_file(script_path)
        try:
            os.remove(script_path)
            return success_response(message=f"已删除: {safe_name}")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_rename_script(self, old_name: str, new_name: str) -> dict:
        """重命名脚本文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        safe_old = os.path.basename(old_name)
        safe_new = os.path.basename(new_name)
        if safe_old != old_name or '..' in old_name or safe_new != new_name or '..' in new_name:
            return error_response(ErrorCode.INVALID_PARAM, "无效的文件名")
        old_path = os.path.join(self.game_path, "Script", safe_old)
        new_path = os.path.join(self.game_path, "Script", safe_new)
        if not os.path.exists(old_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"文件不存在: {safe_old}")
        if os.path.exists(new_path):
            return error_response(ErrorCode.FILE_ALREADY_EXISTS, f"目标文件已存在: {safe_new}")
        if self.backup_mgr:
            self.backup_mgr.backup_file(old_path)
        try:
            os.rename(old_path, new_path)
            return success_response({"old_name": safe_old, "new_name": safe_new}, message=f"已重命名: {safe_old} → {safe_new}")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_global_search(self, query: str, search_type: str = "id", tables: List[str] = None) -> dict:
        """全局数据搜索：跨所有表按ID或值搜索"""
        if not self.game_path:

            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if not query or not query.strip():
            return error_response(ErrorCode.MISSING_PARAM, "请输入搜索内容")
        query = query.strip()
        results = []

        # 默认搜索范围
        all_tables = tables or [
            "General01.ini", "Soldier.ini", "Thing.ini", "DefSkill.ini",
            "BFMagic.ini", "SFMagic.ini", "Title.ini", "Nation.ini",
            "City.ini", "GenSkill.ini", "ArmySkill.ini", "ArmyGroupSkill.ini",
            "SuperAtk.ini", "Formation.ini", "Format.ini", "City01.ini",
            "City02.ini", "City03.ini", "City04.ini", "City05.ini",
            "City06.ini", "City07.ini", "City08.ini", "City09.ini", "City10.ini",
            "GenLV.ini", "ItemEnhance.ini", "Age.ini", "Color.ini",
        ]

        for filename in all_tables:
            path = os.path.join(self.game_path, "Setting", filename)
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="big5", errors="replace") as f:
                    content = f.read()
                # 解析 INI 条目
                entries = re.split(r'\n\s*\n', content)
                file_matches = []
                for entry in entries:
                    lines = entry.strip().split('\n')
                    if not lines:
                        continue
                    # 提取 No 和 Name
                    no_val = ""
                    name_val = ""
                    for line in lines:
                        m = re.match(r'No\s*=\s*(.+)', line)
                        if m:
                            no_val = m.group(1).strip()
                        m = re.match(r'Name\s*=\s*(.+)', line)
                        if m:
                            name_val = m.group(1).strip()
                    # 按 ID 搜索
                    if search_type == "id" and no_val == query:
                        file_matches.append({"no": no_val, "name": name_val, "entry": entry.strip()[:500]})
                    elif search_type == "name" and query.lower() in name_val.lower():
                        file_matches.append({"no": no_val, "name": name_val, "entry": entry.strip()[:500]})
                    elif search_type == "value" and query.lower() in entry.lower():
                        file_matches.append({"no": no_val, "name": name_val, "entry": entry.strip()[:500]})
                if file_matches:
                    results.append({"file": filename, "matches": file_matches, "count": len(file_matches)})
            except Exception as e:
                logger.warning(f"全局搜索文件失败 {filename}: {e}")
                continue

        total = sum(r["count"] for r in results)
        return {"success": True, "query": query, "type": search_type, "results": results, "totalMatches": total}

    def api_balance_analysis(self, scope: str = "all") -> dict:
        """游戏平衡分析：统计武将/兵种/物品属性分布"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        setting_dir = os.path.join(self.game_path, "Setting")
        analysis = {}

        # 武将分析
        if scope in ("all", "generals"):
            gen_path = os.path.join(setting_dir, "General01.ini")
            if os.path.exists(gen_path):
                stats = {"count": 0, "wstr": [], "intelligence": [], "hp": [], "mp": [], "morale": []}
                try:
                    entries = self.api_load_generals().get("data", [])
                    for g in entries:
                        stats["count"] += 1
                        for k in ["wstr", "intelligence", "hp", "mp", "morale"]:
                            v = int(g.get(k, 0))
                            stats[k].append(v)
                    analysis["generals"] = {
                        "count": stats["count"],
                        "wstr": {"min": min(stats["wstr"]) if stats["wstr"] else 0, "max": max(stats["wstr"]) if stats["wstr"] else 0, "avg": round(sum(stats["wstr"])/len(stats["wstr"]), 1) if stats["wstr"] else 0},
                        "intelligence": {"min": min(stats["intelligence"]) if stats["intelligence"] else 0, "max": max(stats["intelligence"]) if stats["intelligence"] else 0, "avg": round(sum(stats["intelligence"])/len(stats["intelligence"]), 1) if stats["intelligence"] else 0},
                        "hp": {"min": min(stats["hp"]) if stats["hp"] else 0, "max": max(stats["hp"]) if stats["hp"] else 0, "avg": round(sum(stats["hp"])/len(stats["hp"]), 1) if stats["hp"] else 0},
                        "mp": {"min": min(stats["mp"]) if stats["mp"] else 0, "max": max(stats["mp"]) if stats["mp"] else 0, "avg": round(sum(stats["mp"])/len(stats["mp"]), 1) if stats["mp"] else 0},
                    }
                except Exception as e:
                    logger.error(f"操作失败: {e}", exc_info=True)
                    analysis["generals"] = {"error": str(e)}

        # 兵种分析
        if scope in ("all", "soldiers"):
            sol_path = os.path.join(setting_dir, "Soldier.ini")
            if os.path.exists(sol_path):
                stats = {"count": 0, "hp": [], "atk": [], "def": [], "speed": []}
                try:
                    entries = self.api_load_soldiers().get("data", [])
                    for s in entries:
                        stats["count"] += 1
                        for k in ["hp", "atk", "def", "speed"]:
                            v = int(s.get(k, 0))
                            stats[k].append(v)
                    analysis["soldiers"] = {
                        "count": stats["count"],
                        "hp": {"min": min(stats["hp"]) if stats["hp"] else 0, "max": max(stats["hp"]) if stats["hp"] else 0, "avg": round(sum(stats["hp"])/len(stats["hp"]), 1) if stats["hp"] else 0},
                        "atk": {"min": min(stats["atk"]) if stats["atk"] else 0, "max": max(stats["atk"]) if stats["atk"] else 0, "avg": round(sum(stats["atk"])/len(stats["atk"]), 1) if stats["atk"] else 0},
                        "def": {"min": min(stats["def"]) if stats["def"] else 0, "max": max(stats["def"]) if stats["def"] else 0, "avg": round(sum(stats["def"])/len(stats["def"]), 1) if stats["def"] else 0},
                    }
                except Exception as e:
                    logger.error(f"操作失败: {e}", exc_info=True)
                    analysis["soldiers"] = {"error": str(e)}

        # 物品分析
        if scope in ("all", "things"):
            thing_path = os.path.join(setting_dir, "Thing.ini")
            if os.path.exists(thing_path):
                stats = {"count": 0, "str": [], "int": [], "hp": [], "mp": [], "price": [], "type_dist": {}}
                try:
                    entries = self.api_load_things().get("data", [])
                    for t in entries:
                        stats["count"] += 1
                        ttype = str(t.get("Type", "?"))
                        stats["type_dist"][ttype] = stats["type_dist"].get(ttype, 0) + 1
                        for k in ["str", "int", "hp", "mp", "price"]:
                            v = int(t.get(k, 0))
                            if v > 0:
                                stats[k].append(v)
                    analysis["things"] = {
                        "count": stats["count"],
                        "type_distribution": stats["type_dist"],
                        "str": {"min": min(stats["str"]) if stats["str"] else 0, "max": max(stats["str"]) if stats["str"] else 0, "avg": round(sum(stats["str"])/len(stats["str"]), 1) if stats["str"] else 0},
                        "int": {"min": min(stats["int"]) if stats["int"] else 0, "max": max(stats["int"]) if stats["int"] else 0, "avg": round(sum(stats["int"])/len(stats["int"]), 1) if stats["int"] else 0},
                        "hp": {"min": min(stats["hp"]) if stats["hp"] else 0, "max": max(stats["hp"]) if stats["hp"] else 0, "avg": round(sum(stats["hp"])/len(stats["hp"]), 1) if stats["hp"] else 0},
                        "price": {"min": min(stats["price"]) if stats["price"] else 0, "max": max(stats["price"]) if stats["price"] else 0, "avg": round(sum(stats["price"])/len(stats["price"]), 1) if stats["price"] else 0},
                    }
                except Exception as e:
                    logger.error(f"操作失败: {e}", exc_info=True)
                    analysis["things"] = {"error": str(e)}

        return {"success": True, "analysis": analysis}

