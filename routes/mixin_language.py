import os, json, re, shutil, base64, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional
from core.error_codes import ErrorCode, safe_error_message, error_response, success_response

from core.config import WRITE_ROOT, PROJECT_ROOT

from core.event_templates import EVENT_TEMPLATES, generate_event_section

logger = logging.getLogger('San7ModMaker')

__all__ = ['San7ModMakerAdvanced']

__all__ = ['San7ModMakerLanguage']

class San7ModMakerLanguage:
    """MOD制作器 - 语言管理 (language.DAT/语言包/文本对比)"""

    # API: language.DAT 语言标识编辑
    # ============================================================
    def api_read_language_dat(self) -> dict:
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "language.DAT")
        if not os.path.exists(path):
            return {"success": True, "current": "BIG5", "message": "language.DAT 不存在，默认为BIG5"}
        with open(path, "rb") as f:
            raw = f.read()
        val = raw.decode("ascii", errors="replace").strip()
        if val.startswith("LANG_"):
            val = val[5:]
        return {"success": True, "current": val, "raw": list(raw)}
    def api_write_language_dat(self, lang: str) -> dict:
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if lang not in ("BIG5", "GB", "SJIS", "KOR"):
            return error_response(ErrorCode.INVALID_PARAM, f"不支持的语言: {lang}，支持: BIG5/GB/SJIS/KOR")
        path = os.path.join(self.game_path, "language.DAT")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        with open(path, "wb") as f:
            f.write(f"LANG_{lang}".encode("ascii"))
        return success_response({"current": lang}, message=f"language.DAT 已切换为: LANG_{lang}")
    def api_switch_language_preset(self, lang: str) -> dict:
        """一键切换语言：同步 language.DAT + font.ini + 三个文本INI"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if lang not in ("BIG5", "GB", "SJIS", "KOR"):
            return error_response(ErrorCode.INVALID_PARAM, f"不支持的语言: {lang}")
        lang_map = {"BIG5": "", "GB": "gb", "SJIS": "jp", "KOR": "ko"}
        suffix = lang_map.get(lang, "")
        switched = []
        try:
            # 1. language.DAT
            dat_path = os.path.join(self.game_path, "language.DAT")
            if self.backup_mgr:
                self.backup_mgr.backup_file(dat_path)
            with open(dat_path, "wb") as f:
                f.write(f"LANG_{lang}".encode("ascii"))
            switched.append("language.DAT")
            # 2. font.ini (从备份文件复制)
            font_src = os.path.join(self.game_path, "Setting", f"font.ini_{suffix}" if suffix else "font.ini")
            font_dst = os.path.join(self.game_path, "Setting", "font.ini")
            if os.path.exists(font_src):
                if self.backup_mgr:
                    self.backup_mgr.backup_file(font_dst)
                import shutil
                shutil.copy2(font_src, font_dst)
                switched.append("font.ini")
            # 3. TermText.ini
            for ini_name in ("TermText", "SystemText", "GossipText"):
                src = os.path.join(self.game_path, "Setting", f"{ini_name}.ini_{suffix}.txt" if suffix else f"{ini_name}.ini")
                dst = os.path.join(self.game_path, "Setting", f"{ini_name}.ini")
                if os.path.exists(src):
                    if self.backup_mgr:
                        self.backup_mgr.backup_file(dst)
                    import shutil
                    shutil.copy2(src, dst)
                    switched.append(f"{ini_name}.ini")
            # 刷新 TermText 缓存
            try:
                self.term_text = TermTextManager(self.game_path)
                self.term_text.load()
            except Exception as e:
                logger.warning(f"TermText刷新失败: {e}")
            return success_response({"switched": switched}, message=f"语言已切换为 {lang}")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e), {"switched": switched})

    def api_export_language_pack(self, target_path: str = None) -> dict:
        """导出当前语言包为ZIP文件（含 language.DAT + font.ini + 三个文本INI）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        import zipfile, io
        # 读取当前语言
        lang = "BIG5"
        dat_path = os.path.join(self.game_path, "language.DAT")
        if os.path.exists(dat_path):
            try:
                with open(dat_path, "rb") as f:
                    raw = f.read()
                val = raw.decode("ascii", errors="replace").strip()
                if val.startswith("LANG_"):
                    lang = val[5:]
            except (IOError, OSError, UnicodeDecodeError) as e:
                logger.warning(f"读取语言包标识失败: {e}")

        if not target_path:
            target_path = os.path.join(self.game_path, f"lang_pack_{lang}.zip")

        files_to_pack = [
            ("language.DAT", dat_path),
            ("Setting/font.ini", os.path.join(self.game_path, "Setting", "font.ini")),
            ("Setting/TermText.ini", os.path.join(self.game_path, "Setting", "TermText.ini")),
            ("Setting/SystemText.ini", os.path.join(self.game_path, "Setting", "SystemText.ini")),
            ("Setting/GossipText.ini", os.path.join(self.game_path, "Setting", "GossipText.ini")),
        ]

        packed = []
        try:
            with zipfile.ZipFile(target_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # 添加元数据
                meta = {"language": lang, "exported_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"), "tool": "San7ModMaker V3.11.0"}
                zf.writestr("pack_meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
                for arcname, fpath in files_to_pack:
                    if os.path.exists(fpath):
                        zf.write(fpath, arcname)
                        packed.append(arcname)
            size_kb = round(os.path.getsize(target_path) / 1024, 1)
            return success_response({"path": target_path, "files": packed, "language": lang, "size_kb": size_kb}, message=f"语言包已导出: {os.path.basename(target_path)} ({size_kb} KB)")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_import_language_pack(self, file_path: str) -> dict:
        """导入语言包ZIP文件"""
        import zipfile
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if not os.path.exists(file_path):
            return error_response(ErrorCode.FILE_NOT_FOUND)
        if not file_path.lower().endswith(".zip"):
            return error_response(ErrorCode.INVALID_PARAM, "仅支持 .zip 格式的语言包")

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()
                # 验证包结构
                if "language.DAT" not in names:
                    return error_response(ErrorCode.INVALID_PARAM, "无效的语言包: 缺少 language.DAT")
                if "pack_meta.json" in names:
                    meta = json.loads(zf.read("pack_meta.json"))
                    lang = meta.get("language", "?")
                else:
                    lang = "?"

                imported = []
                for name in names:
                    if name == "pack_meta.json":
                        continue
                    # 路径遍历防护：拒绝包含 .. 或绝对路径的条目
                    if ".." in name or name.startswith("/") or name.startswith("\\"):
                        logger.warning(f"语言包导入拒绝可疑路径: {name}")
                        continue
                    target = os.path.join(self.game_path, name)
                    # 确保目标路径在 game_path 内
                    target_real = os.path.realpath(target)
                    game_real = os.path.realpath(self.game_path)
                    if not target_real.startswith(game_real + os.sep) and target_real != game_real:
                        logger.warning(f"语言包导入拒绝路径遍历: {name}")
                        continue
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    if self.backup_mgr and os.path.exists(target):
                        self.backup_mgr.backup_file(target)
                    with open(target, "wb") as f:
                        f.write(zf.read(name))
                    imported.append(name)

            return success_response({"files": imported, "language": lang}, message=f"语言包已导入 ({lang}): {len(imported)} 个文件")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_diff_language_texts(self, source_lang: str = "BIG5") -> dict:
        """对比当前语言与源语言的文本差异"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        # 获取当前语言
        current_lang = "BIG5"
        dat_path = os.path.join(self.game_path, "language.DAT")
        if os.path.exists(dat_path):
            with open(dat_path, "rb") as f:
                raw = f.read()
            val = raw.decode("ascii", errors="replace").strip()
            if val.startswith("LANG_"):
                current_lang = val[5:]

        if current_lang == source_lang:
            return {"success": True, "diff": {}, "message": "当前语言与源语言相同，无差异", "current": current_lang, "source": source_lang}

        # 尝试加载源语言文件
        suffix_map = {"BIG5": "", "GB": "gb", "SJIS": "jp", "KOR": "ko"}
        src_suffix = suffix_map.get(source_lang, "")
        cur_suffix = suffix_map.get(current_lang, "")

        results = {}
        for ini_name in ("TermText", "SystemText", "GossipText"):
            src_path = os.path.join(self.game_path, "Setting", f"{ini_name}.ini_{src_suffix}.txt" if src_suffix else f"{ini_name}.ini")
            cur_path = os.path.join(self.game_path, "Setting", f"{ini_name}.ini")

            if not os.path.exists(src_path):
                results[ini_name] = {"status": "source_missing", "message": f"源语言文件不存在: {src_path}"}
                continue

            parser = IniParser()
            parser.load(cur_path)
            cur_data = {}
            for s in parser.get_all_sections():
                e = dict(s.entries)
                no = e.get("No", "")
                if no:
                    cur_data[no] = e.get("Text", e.get("Name", ""))

            parser2 = IniParser()
            parser2.load(src_path)
            src_data = {}
            for s in parser2.get_all_sections():
                e = dict(s.entries)
                no = e.get("No", "")
                if no:
                    src_data[no] = e.get("Text", e.get("Name", ""))

            added = [k for k in cur_data if k not in src_data]
            removed = [k for k in src_data if k not in cur_data]
            changed = [(k, src_data[k], cur_data[k]) for k in cur_data if k in src_data and cur_data[k] != src_data[k]]

            results[ini_name] = {
                "total_current": len(cur_data),
                "total_source": len(src_data),
                "added": len(added),
                "removed": len(removed),
                "changed": len(changed),
                "changed_samples": [{"No": k, "source": s, "current": c} for k, s, c in changed[:20]],
                "added_samples": added[:10],
                "removed_samples": removed[:10],
            }

        return {
            "success": True,
            "diff": results,
            "current": current_lang,
            "source": source_lang,
            "total_changes": sum(r.get("changed", 0) + r.get("added", 0) + r.get("removed", 0) for r in results.values()),
        }

    def api_reload_termtext(self) -> dict:
        """语言切换后重新加载 TermTextManager 缓存"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            self.term_text = TermTextManager(self.game_path)
            self.term_text.load()
            return success_response({"count": len(self.term_text._data) if hasattr(self.term_text, '_data') else 0}, message="TermText 缓存已刷新")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_language_status(self) -> dict:
        """获取语言系统完整状态（检测所有可用语言文件）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        # 当前语言
        current_lang = "BIG5"
        dat_path = os.path.join(self.game_path, "language.DAT")
        if os.path.exists(dat_path):
            with open(dat_path, "rb") as f:
                raw = f.read()
            val = raw.decode("ascii", errors="replace").strip()
            if val.startswith("LANG_"):
                current_lang = val[5:]

        # 检测可用语言
        available = []
        for lang, suffix in [("BIG5", ""), ("GB", "gb"), ("SJIS", "jp"), ("KOR", "ko")]:
            lang_files = {}
            for ini_name in ("TermText", "SystemText", "GossipText"):
                fpath = os.path.join(self.game_path, "Setting", f"{ini_name}.ini_{suffix}.txt" if suffix else f"{ini_name}.ini")
                lang_files[ini_name] = os.path.exists(fpath)
            font_path = os.path.join(self.game_path, "Setting", f"font.ini_{suffix}" if suffix else "font.ini")
            lang_files["font"] = os.path.exists(font_path)
            all_ok = all(lang_files.values())
            available.append({
                "lang": lang,
                "label": {"BIG5": "繁体中文", "GB": "简体中文", "SJIS": "日文", "KOR": "韩文"}.get(lang, lang),
                "is_current": lang == current_lang,
                "files": lang_files,
                "complete": all_ok,
                "missing": [k for k, v in lang_files.items() if not v],
            })

        return {
            "success": True,
            "current": current_lang,
            "available": available,
            "has_language_dat": os.path.exists(dat_path),
        }

