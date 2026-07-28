import os, json, re, shutil, base64, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional
from core.error_codes import safe_error_message, error_response, success_response

from core.config import WRITE_ROOT, PROJECT_ROOT

from core.event_templates import EVENT_TEMPLATES, generate_event_section

logger = logging.getLogger('San7ModMaker')

__all__ = ['San7ModMakerAdvanced']

class San7ModMakerAdvanced:
    """MOD制作器 - 高级功能 (语言/图像/音频/沙盒/内存/地图/脚本)"""

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

    # ============================================================
    # API: 小地图 BMP→RAW 转换
    # ============================================================
    def api_bmp2raw(self, bmp_path: str) -> dict:
        """将382×270的BMP图片转换为游戏小地图RAW格式"""
        import struct
        if not os.path.exists(bmp_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "BMP文件不存在")
        try:
            with open(bmp_path, "rb") as f:
                # 读取BMP头
                header = f.read(54)
                if header[0:2] != b"BM":
                    return error_response(ErrorCode.INVALID_PARAM, "不是有效的BMP文件")
                width = struct.unpack("<I", header[18:22])[0]
                height = struct.unpack("<I", header[22:26])[0]
                if width != 382 or height != 270:
                    return error_response(ErrorCode.INVALID_PARAM, f"BMP尺寸必须为382×270，当前为{width}×{height}")
                # 读取BMP数据（BMP 24-bit）
                row_size = (width * 3 + 3) ^ ~3 + 1
                raw_data = bytearray()
                for y in range(height - 1, -1, -1):
                    f.seek(54 + y * row_size)
                    row = f.read(width * 3)
                    for x in range(width):
                        b = row[x * 3]
                        g = row[x * 3 + 1]
                        r = row[x * 3 + 2]
                        # 转RGB565
                        r5 = (r >> 3) & 0x1F
                        g6 = (g >> 2) & 0x3F
                        b5 = (b >> 3) & 0x1F
                        val = (r5 << 11) | (g6 << 5) | b5
                        raw_data.append(val & 0xFF)
                        raw_data.append((val >> 8) & 0xFF)
                # 写RAW
                raw_path = bmp_path.rsplit(".", 1)[0] + ".raw"
                with open(raw_path, "wb") as out:
                    out.write(bytes(raw_data))
                return success_response({"raw_path": raw_path, "size": len(raw_data)}, message=f"转换成功: {raw_path}")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_raw2bmp(self, raw_path: str) -> dict:
        """将 RAW 小地图文件反向转换为 BMP 图片"""
        import struct
        if not os.path.exists(raw_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "RAW文件不存在")
        try:
            raw_size = os.path.getsize(raw_path)
            expected_size = 382 * 270 * 2  # RGB565, 2 bytes per pixel
            if raw_size != expected_size:
                return error_response(ErrorCode.INVALID_PARAM, f"RAW文件大小不正确，期望 {expected_size} bytes，实际 {raw_size} bytes")
            with open(raw_path, "rb") as f:
                raw_data = f.read()
            # Build BMP file (24-bit)
            bmp_size = 54 + 382 * 270 * 3
            header = bytearray(54)
            header[0:2] = b"BM"
            struct.pack_into("<I", header, 2, bmp_size)
            header[10] = 54  # data offset
            header[14] = 40  # DIB header size
            struct.pack_into("<I", header, 18, 382)  # width
            struct.pack_into("<I", header, 22, 270)  # height
            header[26] = 1   # planes
            header[28] = 24  # bpp
            # BMP stores rows bottom-to-top
            row_size = (382 * 3 + 3) & ~3  # padded to 4 bytes
            pixel_data = bytearray()
            for y in range(270 - 1, -1, -1):
                row = bytearray(row_size)
                for x in range(382):
                    idx = (y * 382 + x) * 2
                    val = raw_data[idx] | (raw_data[idx + 1] << 8)
                    r5 = (val >> 11) & 0x1F
                    g6 = (val >> 5) & 0x3F
                    b5 = val & 0x1F
                    r = (r5 << 3) | (r5 >> 2)
                    g = (g6 << 2) | (g6 >> 4)
                    b = (b5 << 3) | (b5 >> 2)
                    row[x * 3] = b
                    row[x * 3 + 1] = g
                    row[x * 3 + 2] = r
                pixel_data.extend(row)
            bmp_path = raw_path.rsplit(".", 1)[0] + "_converted.bmp"
            with open(bmp_path, "wb") as out:
                out.write(bytes(header))
                out.write(bytes(pixel_data))
            return success_response({"bmp_path": bmp_path, "size": len(pixel_data)}, message=f"反向转换成功: {bmp_path}")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_bmp2raw_batch(self, dir_path: str) -> dict:
        """批量转换目录下所有 382×270 BMP 文件为 RAW"""
        import struct
        if not os.path.isdir(dir_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "目录不存在")
        converted = 0
        failed = 0
        errors = []
        for fname in os.listdir(dir_path):
            if not fname.lower().endswith(".bmp"):
                continue
            fpath = os.path.join(dir_path, fname)
            try:
                with open(fpath, "rb") as f:
                    header = f.read(54)
                    if header[0:2] != b"BM":
                        failed += 1
                        errors.append(f"{fname}: 不是有效BMP")
                        continue
                    width = struct.unpack("<I", header[18:22])[0]
                    height = struct.unpack("<I", header[22:26])[0]
                    if width != 382 or height != 270:
                        failed += 1
                        errors.append(f"{fname}: 尺寸 {width}×{height} 不符合")
                        continue
                    row_size = (width * 3 + 3) & ~3
                    raw_data = bytearray()
                    for y in range(height - 1, -1, -1):
                        f.seek(54 + y * row_size)
                        row = f.read(width * 3)
                        for x in range(width):
                            b = row[x * 3]
                            g = row[x * 3 + 1]
                            r = row[x * 3 + 2]
                            r5 = (r >> 3) & 0x1F
                            g6 = (g >> 2) & 0x3F
                            b5 = (b >> 3) & 0x1F
                            val = (r5 << 11) | (g6 << 5) | b5
                            raw_data.append(val & 0xFF)
                            raw_data.append((val >> 8) & 0xFF)
                raw_path = fpath.rsplit(".", 1)[0] + ".raw"
                with open(raw_path, "wb") as out:
                    out.write(bytes(raw_data))
                converted += 1
            except Exception as e:
                logger.error(f"操作失败: {e}", exc_info=True)
                failed += 1
                errors.append(f"{fname}: {str(e)}")
        msg = f"批量转换完成: 成功 {converted} 个"
        if failed:
            msg += f", 失败 {failed} 个"
        return success_response({"converted": converted, "failed": failed, "errors": errors[:10]}, message=msg)

    def api_bmp_preview(self, bmp_path: str) -> dict:
        """返回 BMP 文件的 base64 编码供前端预览"""
        import base64
        if not os.path.exists(bmp_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "BMP文件不存在")
        try:
            with open(bmp_path, "rb") as f:
                data = f.read()
            b64 = base64.b64encode(data).decode("ascii")
            return {"success": True, "base64": b64, "message": "预览加载成功"}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # API: SHP 像素编辑器
    # ============================================================
    def api_shp_pixel_load(self, shp_path: str) -> dict:
        """加载SHP文件的像素数据和调色板"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            self.shp_converter.set_game_path(self.game_path)
            pixel_data = self.shp_converter.get_pixel_data(shp_path)
            return {"success": True, **pixel_data, "message": f"加载成功: {pixel_data['width']}x{pixel_data['height']}"}
        except FileNotFoundError:
            return error_response(ErrorCode.FILE_NOT_FOUND, f"SHP文件不存在: {shp_path}")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_shp_pixel_save(self, shp_path: str, pixels: list, width: int = None, height: int = None) -> dict:
        """保存修改后的像素数据到SHP文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            self.shp_converter.set_game_path(self.game_path)
            saved = self.shp_converter.save_pixel_data(shp_path, pixels, width, height)
            return {"success": True, "saved": saved, "message": "像素数据已保存"}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_shp_get_palette(self) -> dict:
        """获取ACT调色板RGB列表"""
        try:
            palette = self.shp_converter.get_palette_rgb()
            return {"success": True, "palette": palette, "total": len(palette), "message": "调色板加载成功"}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # API: BGM/音效编辑器
    # ============================================================
    def _get_audio_dirs(self) -> dict:
        """获取音频目录信息"""
        dirs = {}
        for name in ["Music", "Sound", "Audio"]:
            d = os.path.join(self.game_path, name) if self.game_path else None
            if d and os.path.isdir(d):
                files = []
                for f in sorted(os.listdir(d)):
                    fp = os.path.join(d, f)
                    if os.path.isfile(fp):
                        ext = os.path.splitext(f)[1].lower()
                        if ext in (".wav", ".mp3", ".ogg", ".wma", ".mid", ".midi", ".flac"):
                            files.append({"name": f, "ext": ext, "size_kb": round(os.path.getsize(fp) / 1024, 1)})
                dirs[name] = {"path": d, "files": files, "count": len(files)}
        return dirs

    def api_browse_audio(self) -> dict:
        """浏览 Music/ 和 Sound/ 目录下的音频文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            dirs = self._get_audio_dirs()
            total = sum(d["count"] for d in dirs.values())
            return {"success": True, "dirs": dirs, "total_files": total,
                    "message": f"共 {total} 个音频文件"}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_preview_audio(self, directory: str, filename: str) -> dict:
        """预览音频文件：返回 base64 编码"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        import base64
        try:
            filepath = os.path.join(self.game_path, directory, filename)
            # 安全检查
            if not os.path.realpath(filepath).startswith(os.path.realpath(self.game_path)):
                return error_response(ErrorCode.PATH_TRAVERSAL)
            if not os.path.exists(filepath):
                return error_response(ErrorCode.FILE_NOT_FOUND)
            # 限制文件大小 (50MB)
            if os.path.getsize(filepath) > 50 * 1024 * 1024:
                return error_response(ErrorCode.INVALID_PARAM, "文件过大 (超过50MB)，请使用本地播放器播放")
            ext = os.path.splitext(filename)[1].lower()
            mime_map = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg",
                        ".wma": "audio/x-ms-wma", ".mid": "audio/midi", ".midi": "audio/midi",
                        ".flac": "audio/flac"}
            mime = mime_map.get(ext, "audio/wav")
            with open(filepath, "rb") as f:
                data = f.read()
            b64 = base64.b64encode(data).decode("ascii")
            return {"success": True, "base64": f"data:{mime};base64,{b64}",
                    "filename": filename, "mime": mime, "size_kb": round(len(data) / 1024, 1),
                    "message": "预览加载成功"}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_import_audio(self, source_path: str, target_dir: str, target_name: str = None) -> dict:
        """导入音频文件到 Music/ 或 Sound/ 目录"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if target_dir not in ("Music", "Sound", "Audio"):
            return error_response(ErrorCode.INVALID_PARAM, "目标目录必须是 Music/Sound/Audio")
        if not os.path.exists(source_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "源文件不存在")
        try:
            dest_dir = os.path.join(self.game_path, target_dir)
            os.makedirs(dest_dir, exist_ok=True)
            dest_name = target_name or os.path.basename(source_path)
            dest_path = os.path.join(dest_dir, dest_name)

            # 备份
            if os.path.exists(dest_path) and self.backup_mgr:
                self.backup_mgr.backup_file(dest_path)

            shutil.copy2(source_path, dest_path)
            return {"success": True, "target": dest_path,
                    "message": f"已导入: {dest_name} → {target_dir}/"}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_delete_audio(self, directory: str, filename: str) -> dict:
        """删除音频文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            filepath = os.path.join(self.game_path, directory, filename)
            if not os.path.realpath(filepath).startswith(os.path.realpath(self.game_path)):
                return error_response(ErrorCode.PATH_TRAVERSAL)
            if not os.path.exists(filepath):
                return error_response(ErrorCode.FILE_NOT_FOUND)
            if self.backup_mgr:
                self.backup_mgr.backup_file(filepath)
            os.remove(filepath)
            return success_response(message=f"已删除: {filename}")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_rename_audio(self, directory: str, old_name: str, new_name: str) -> dict:
        """重命名音频文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            old_path = os.path.join(self.game_path, directory, old_name)
            new_path = os.path.join(self.game_path, directory, new_name)
            if not os.path.realpath(old_path).startswith(os.path.realpath(self.game_path)):
                return error_response(ErrorCode.PATH_TRAVERSAL)
            if not os.path.exists(old_path):
                return error_response(ErrorCode.FILE_NOT_FOUND)
            if os.path.exists(new_path):
                return error_response(ErrorCode.FILE_ALREADY_EXISTS, "目标文件名已存在")
            if self.backup_mgr:
                self.backup_mgr.backup_file(old_path)
            os.rename(old_path, new_path)
            return success_response(message=f"已重命名: {old_name} → {new_name}")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # API: 沙盒测试模式
    # ============================================================
    def api_create_sandbox(self) -> dict:
        """创建沙盒环境：复制游戏文件到临时目录用于测试"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        sandbox_dir = os.path.join(WRITE_ROOT, "sandbox")
        # 如果已有沙盒，询问
        if os.path.exists(sandbox_dir):
            return error_response(ErrorCode.INVALID_PARAM, "沙盒已存在，请先清理旧沙盒", {"sandbox_exists": True})

        try:
            os.makedirs(sandbox_dir, exist_ok=True)

            # 只复制必要的目录（不复制巨型Shape/文件夹，只创建符号链接或minimal副本）
            dirs_to_copy = ["Setting", "Script"]
            dirs_to_link = ["Shape", "Music", "Sound"]

            copied = []
            for d in dirs_to_copy:
                src = os.path.join(self.game_path, d)
                if os.path.exists(src):
                    dst = os.path.join(sandbox_dir, d)
                    shutil.copytree(src, dst)
                    copied.append(d)

            linked = []
            for d in dirs_to_link:
                src = os.path.join(self.game_path, d)
                if os.path.exists(src):
                    dst = os.path.join(sandbox_dir, d)
                    try:
                        os.symlink(src, dst, target_is_directory=True)
                        linked.append(d)
                    except OSError:
                        # 符号链接失败则复制
                        shutil.copytree(src, dst)
                        copied.append(d)

            # 复制 EXE
            exe_src = os.path.join(self.game_path, "Sango7.exe")
            if os.path.exists(exe_src):
                shutil.copy2(exe_src, os.path.join(sandbox_dir, "Sango7.exe"))
                copied.append("Sango7.exe")

            # 保存沙盒元数据
            meta = {
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "game_path": self.game_path,
                "copied": copied,
                "linked": linked,
                "mods_installed": [],
            }
            with open(os.path.join(sandbox_dir, "sandbox_meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            return {
                "success": True,
                "sandbox_dir": sandbox_dir,
                "copied": copied,
                "linked": linked,
                "message": f"沙盒已创建 (复制: {len(copied)}个, 链接: {len(linked)}个)",
            }
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_install_to_sandbox(self, mod_name: str) -> dict:
        """将MOD安装到沙盒中测试"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        sandbox_dir = os.path.join(WRITE_ROOT, "sandbox")
        if not os.path.exists(sandbox_dir):
            return error_response(ErrorCode.FILE_NOT_FOUND, "沙盒不存在，请先创建沙盒")

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if not os.path.exists(export_dir):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"MOD包 '{mod_name}' 不存在，请先打包")

        try:
            installed = []
            for sub in ["Setting", "Shape", "Music", "Sound", "Script"]:
                src = os.path.join(export_dir, sub)
                if os.path.exists(src):
                    dst = os.path.join(sandbox_dir, sub)
                    os.makedirs(dst, exist_ok=True)
                    for root, _, files in os.walk(src):
                        for fname in files:
                            s = os.path.join(root, fname)
                            rel = os.path.relpath(s, src)
                            d = os.path.join(dst, rel)
                            os.makedirs(os.path.dirname(d), exist_ok=True)
                            shutil.copy2(s, d)
                            installed.append(os.path.join(sub, rel))

            # 更新沙盒元数据
            meta_path = os.path.join(sandbox_dir, "sandbox_meta.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if mod_name not in meta.get("mods_installed", []):
                    meta["mods_installed"].append(mod_name)
                meta["last_install"] = time.strftime("%Y-%m-%d %H:%M:%S")
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)

            return {
                "success": True,
                "installed": len(installed),
                "message": f"MOD '{mod_name}' 已安装到沙盒 ({len(installed)} 个文件)",
            }
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_launch_sandbox(self) -> dict:
        """从沙盒启动游戏"""
        sandbox_dir = os.path.join(WRITE_ROOT, "sandbox")
        exe_path = os.path.join(sandbox_dir, "Sango7.exe")
        if not os.path.exists(exe_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "沙盒中未找到Sango7.exe，请先创建沙盒")

        try:
            import subprocess
            subprocess.Popen(exe_path, cwd=sandbox_dir,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return success_response(message="游戏已从沙盒启动")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_cleanup_sandbox(self) -> dict:
        """清理沙盒环境"""
        sandbox_dir = os.path.join(WRITE_ROOT, "sandbox")
        if not os.path.exists(sandbox_dir):
            return success_response(message="沙盒不存在，无需清理")

        try:
            # 先删除符号链接目录中的文件，再删除目录
            meta_path = os.path.join(sandbox_dir, "sandbox_meta.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                # 对于链接目录，只删除新文件（即MOD安装的文件）
                for d in meta.get("linked", []):
                    linked_dir = os.path.join(sandbox_dir, d)
                    if os.path.islink(linked_dir):
                        os.unlink(linked_dir)
                    elif os.path.isdir(linked_dir):
                        # 如果是复制而非链接的，整体删除
                        shutil.rmtree(linked_dir, ignore_errors=True)

            shutil.rmtree(sandbox_dir, ignore_errors=True)
            return success_response(message="沙盒已清理")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_get_sandbox_status(self) -> dict:
        """获取沙盒状态"""
        sandbox_dir = os.path.join(WRITE_ROOT, "sandbox")
        if not os.path.exists(sandbox_dir):
            return {"success": True, "exists": False, "message": "沙盒未创建"}

        meta_path = os.path.join(sandbox_dir, "sandbox_meta.json")
        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception as e:
                logger.error(f"操作失败: {e}")
                pass

        # 统计沙盒中的文件
        file_count = 0
        total_size = 0
        for root, _, files in os.walk(sandbox_dir):
            for f in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
                file_count += 1

        return {
            "success": True,
            "exists": True,
            "created": meta.get("created", ""),
            "mods_installed": meta.get("mods_installed", []),
            "last_install": meta.get("last_install", ""),
            "file_count": file_count,
            "total_size_mb": round(total_size / 1024 / 1024, 1),
            "message": f"沙盒: {file_count} 个文件, {round(total_size / 1024 / 1024, 1)}MB",
        }

    # ============================================================
    # API: 操作历史记录
    # ============================================================
    def _log_operation(self, action: str, target: str, detail: str = ""):
        """记录操作到历史日志"""
        log_path = os.path.join(WRITE_ROOT, "data", "operation_history.json")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        history = []
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception as e:
                logger.error(f"操作失败: {e}")
                pass

        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "target": target,
            "detail": detail,
        }
        history.append(entry)

        # 保留最近 500 条记录
        if len(history) > 500:
            history = history[-500:]

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def api_get_operation_history(self, limit: int = 50, action_filter: str = None) -> dict:
        """获取操作历史记录"""
        log_path = os.path.join(WRITE_ROOT, "data", "operation_history.json")
        if not os.path.exists(log_path):
            return {"success": True, "history": [], "total": 0, "message": "无操作记录"}

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception as e:
            logger.error(f"操作失败: {e}")
            return {"success": True, "history": [], "total": 0, "message": "读取失败"}

        # 过滤
        if action_filter:
            history = [h for h in history if action_filter.lower() in h.get("action", "").lower()]

        # 取最近 N 条
        recent = history[-limit:]
        recent.reverse()  # 最新的在前

        return {
            "success": True,
            "history": recent,
            "total": len(history),
            "shown": len(recent),
            "message": f"共 {len(history)} 条记录，显示最近 {len(recent)} 条",
        }

    def api_clear_operation_history(self) -> dict:
        """清空操作历史记录"""
        log_path = os.path.join(WRITE_ROOT, "data", "operation_history.json")
        if os.path.exists(log_path):
            os.remove(log_path)
        return success_response(message="操作历史已清空")

    # ============================================================
    # API: 窗口模式分辨率预设
    # ============================================================
    def api_apply_resolution_preset(self, preset: str) -> dict:
        """应用分辨率预设: 1024x768/1280x720/1366x768/1440x900/1600x900/1920x1080/fullscreen"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        presets = {
            "1024x768": (1024, 768, False),
            "1280x720": (1280, 720, False),
            "1366x768": (1366, 768, False),
            "1440x900": (1440, 900, False),
            "1600x900": (1600, 900, False),
            "1920x1080": (1920, 1080, False),
            "fullscreen": (0, 0, True),
        }
        if preset not in presets:
            return error_response(ErrorCode.INVALID_PARAM, f"不支持的预设: {preset}，可用: {list(presets.keys())}")
        w, h, fullscreen = presets[preset]
        ini_path = os.path.join(self.game_path, "Sango7.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(ini_path)
        parser = IniParser()
        if os.path.exists(ini_path):
            parser.load(ini_path)
        else:
            parser.add_section("Sango7")
        parser.set("Sango7", "m_nWidth", str(w))
        parser.set("Sango7", "m_nHeight", str(h))
        parser.set("Sango7", "m_bFullScreen", "1" if fullscreen else "0")
        parser.set("Sango7", "m_bWindow", "0" if fullscreen else "0")
        parser.save(ini_path)
        label = "全屏" if fullscreen else f"{w}×{h}"
        return success_response({"width": w, "height": h, "fullscreen": fullscreen}, message=f"分辨率已设置为 {label}")

    # ============================================================
    # API: 区块定位计算器
    # ============================================================
    # 游戏大地图尺寸常量
    MAP_WIDTH = 17472
    MAP_HEIGHT = 12384
    BLOCK_SIZE = 32
    GRID_COLS = MAP_WIDTH // BLOCK_SIZE  # 546
    GRID_ROWS = MAP_HEIGHT // BLOCK_SIZE  # 387

    def api_block_calc(self, x: int, y: int) -> dict:
        """坐标→区块号转换"""
        if x < 0 or x >= self.MAP_WIDTH or y < 0 or y >= self.MAP_HEIGHT:
            return error_response(ErrorCode.INVALID_PARAM, f"坐标超出范围 (0~{self.MAP_WIDTH-1}, 0~{self.MAP_HEIGHT-1})")
        gx = x // self.BLOCK_SIZE
        gy = y // self.BLOCK_SIZE
        block_no = gy * self.GRID_COLS + gx
        return {"success": True, "x": x, "y": y, "grid_x": gx, "grid_y": gy,
                "block_no": block_no, "block_size": self.BLOCK_SIZE,
                "grid_cols": self.GRID_COLS, "grid_rows": self.GRID_ROWS}

    def api_block_inverse(self, block_no: int) -> dict:
        """区块号→坐标范围转换"""
        if block_no < 0 or block_no >= self.GRID_COLS * self.GRID_ROWS:
            return error_response(ErrorCode.INVALID_PARAM, f"区块号超出范围 (0~{self.GRID_COLS * self.GRID_ROWS - 1})")
        gy = block_no // self.GRID_COLS
        gx = block_no % self.GRID_COLS
        return {"success": True, "block_no": block_no, "grid_x": gx, "grid_y": gy,
                "x_min": gx * self.BLOCK_SIZE, "y_min": gy * self.BLOCK_SIZE,
                "x_max": (gx + 1) * self.BLOCK_SIZE - 1, "y_max": (gy + 1) * self.BLOCK_SIZE - 1,
                "block_size": self.BLOCK_SIZE, "grid_cols": self.GRID_COLS, "grid_rows": self.GRID_ROWS}

    def api_load_map_summary(self) -> dict:
        """加载地图摘要：城池坐标+建筑坐标+地形类型列表"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        summary = {"cities": [], "buildings": [], "terrains": [], "map_size": [self.MAP_WIDTH, self.MAP_HEIGHT],
                   "block_size": self.BLOCK_SIZE, "grid": [self.GRID_COLS, self.GRID_ROWS]}
        # 加载城池坐标
        citypos_path = os.path.join(self.game_path, "Setting", "CityPos.ini")
        if os.path.exists(citypos_path):
            parser = IniParser()
            parser.load(citypos_path)
            for s in parser.get_all_sections("CITYPOS"):
                e = dict(s.entries)
                x = int(e.get("PosX", 0))
                y = int(e.get("PosY", 0))
                summary["cities"].append({
                    "no": e.get("No", ""), "x": x, "y": y,
                    "grid_x": x // self.BLOCK_SIZE, "grid_y": y // self.BLOCK_SIZE,
                    "block_no": (y // self.BLOCK_SIZE) * self.GRID_COLS + (x // self.BLOCK_SIZE)
                })
        # 加载建筑坐标
        bld_path = os.path.join(self.game_path, "Setting", "BuildingPos.ini")
        if os.path.exists(bld_path):
            parser = IniParser()
            parser.load(bld_path)
            for s in parser.get_all_sections("CITY"):
                e = dict(s.entries)
                x = int(e.get("PosX", 0))
                y = int(e.get("PosY", 0))
                summary["buildings"].append({
                    "no": e.get("No", ""), "x": x, "y": y,
                    "grid_x": x // self.BLOCK_SIZE, "grid_y": y // self.BLOCK_SIZE,
                    "block_no": (y // self.BLOCK_SIZE) * self.GRID_COLS + (x // self.BLOCK_SIZE)
                })
        # 加载地形类型定义
        terrain_path = os.path.join(self.game_path, "Setting", "Terrain.ini")
        if os.path.exists(terrain_path):
            parser = IniParser()
            parser.load(terrain_path)
            for s in parser.get_all_sections("BRUSH_TO_TERRAIN"):
                e = dict(s.entries)
                summary["terrains"].append({"brush": e.get("No", ""), "terrain": e.get("Name", "")})
        return {"success": True, "summary": summary}

    def api_save_map_positions(self, cities: list) -> dict:
        """保存城池位置到 CityPos.ini"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        citypos_path = os.path.join(self.game_path, "Setting", "CityPos.ini")
        if not os.path.exists(citypos_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到 CityPos.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(citypos_path)
        try:
            parser = IniParser()
            parser.load(citypos_path)
            for cdata in cities:
                cno = str(cdata.get("no", ""))
                for section in parser.sections:
                    if section.name == "CITYPOS" and str(section.get("No", "")) == cno:
                        section.set("PosX", str(cdata.get("x", 0)))
                        section.set("PosY", str(cdata.get("y", 0)))
                        break
            parser.save(citypos_path)
            return success_response(message=f"已保存 {len(cities)} 个城池位置")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # API: PCK 资源预览增强
    # ============================================================
    def api_pck_preview_shp(self, pck_name: str, internal_path: str) -> dict:
        """从PCK内直接预览SHP图片（返回base64 PNG）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        safe_pck = os.path.basename(pck_name)
        if safe_pck != pck_name or '..' in pck_name:
            return error_response(ErrorCode.INVALID_PARAM, "无效的PCK文件名")
        pck_path = os.path.join(self.game_path, safe_pck)
        if not os.path.exists(pck_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"未找到 {pck_name}")
        try:
            # 从PCK提取SHP二进制数据到内存
            with open(pck_path, "rb") as f:
                import struct
                magic = struct.unpack("<I", f.read(4))[0]
                if magic != 0x02000000:
                    return error_response(ErrorCode.INVALID_PARAM, "非标准PCK格式")
                file_count = struct.unpack("<I", f.read(4))[0]
                f.seek(12)
                index_offset = struct.unpack("<I", f.read(4))[0]
                f.seek(index_offset)
                for i in range(file_count):
                    name_raw = f.read(64)
                    name = name_raw.split(b'\x00')[0].decode('gbk', errors='replace')
                    data_offset = struct.unpack("<I", f.read(4))[0]
                    data_size = struct.unpack("<I", f.read(4))[0]
                    f.seek(56, 1)
                    if name.lower() == internal_path.lower() or name.replace('\\', '/').lower() == internal_path.lower():
                        f.seek(data_offset)
                        shp_data = f.read(data_size)
                        # 解析SHP为PNG
                        from core.shp_converter import ShpConverter
                        converter = ShpConverter(self.game_path)
                        img = converter.decode_shp_bytes(shp_data)
                        if img:
                            import io, base64
                            buf = io.BytesIO()
                            img.save(buf, format='PNG')
                            b64 = base64.b64encode(buf.getvalue()).decode('ascii')
                            return {"success": True, "name": name, "size": data_size,
                                    "width": img.width, "height": img.height,
                                    "base64": "data:image/png;base64," + b64}
                        return error_response(ErrorCode.INTERNAL, "无法解码SHP图片")
                return error_response(ErrorCode.FILE_NOT_FOUND, f"PCK中未找到: {internal_path}")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # API: 运行时内存修改器
    # ============================================================
    def api_memory_attach(self) -> dict:
        """附加到游戏进程"""
        try:
            import pymem
            import pymem.process
            for proc in pymem.process.list_processes():
                try:
                    if proc.szExeFile and b'SG7' in proc.szExeFile:
                        pm = pymem.Pymem(proc.szExeFile.decode('gbk', errors='replace'))
                        self._memory_pm = pm
                        self._memory_process = proc.szExeFile.decode('gbk', errors='replace')
                        return success_response({"process": self._memory_process, "pid": proc.th32ProcessID}, message=f"已附加到 {self._memory_process}")
                except (Exception,):
                    continue
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到运行中的SG7.exe进程")
        except ImportError:
            return error_response(ErrorCode.INTERNAL, "pymem库未安装，请运行: pip install pymem")

    def api_memory_read(self, address: int, size: int = 4) -> dict:
        """读取游戏内存"""
        if not hasattr(self, '_memory_pm') or not self._memory_pm:
            return error_response(ErrorCode.GAME_PATH_NOT_SET, "请先附加到游戏进程 (memoryAttach)")
        try:
            if size == 1:
                val = self._memory_pm.read_uchar(address)
            elif size == 2:
                val = self._memory_pm.read_ushort(address)
            elif size == 4:
                val = self._memory_pm.read_uint(address)
            else:
                val = self._memory_pm.read_bytes(address, size)
                return {"success": True, "address": address, "size": size, "value": list(val), "hex": val.hex()}
            return {"success": True, "address": address, "size": size, "value": val, "hex": hex(val)}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_memory_write(self, address: int, value: int, size: int = 4) -> dict:
        """写入游戏内存"""
        if not hasattr(self, '_memory_pm') or not self._memory_pm:
            return error_response(ErrorCode.GAME_PATH_NOT_SET, "请先附加到游戏进程 (memoryAttach)")
        try:
            if size == 1:
                self._memory_pm.write_uchar(address, value)
            elif size == 2:
                self._memory_pm.write_ushort(address, value)
            elif size == 4:
                self._memory_pm.write_uint(address, value)
            else:
                return error_response(ErrorCode.INVALID_PARAM, "不支持的大小，仅支持 1/2/4 字节")
            return success_response(message=f"已写入 {hex(value)} 到 {hex(address)}")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_memory_search(self, value: int, size: int = 4) -> dict:
        """搜索内存值"""
        if not hasattr(self, '_memory_pm') or not self._memory_pm:
            return error_response(ErrorCode.GAME_PATH_NOT_SET, "请先附加到游戏进程 (memoryAttach)")
        try:
            import pymem.pattern
            if size == 4:
                pattern = value.to_bytes(4, 'little')
            elif size == 2:
                pattern = value.to_bytes(2, 'little')
            else:
                pattern = value.to_bytes(1, 'little')
            addrs = pymem.pattern.scan_pattern_page(self._memory_pm.process_handle, pattern, return_multiple=True)
            addrs = addrs[:20] if addrs else []
            return {"success": True, "count": len(addrs), "addresses": [hex(a) for a in addrs]}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # API: SANGO7.MPC 地形编辑器
    # ============================================================
    TERRAIN_NAMES = {0:"无",1:"草原",2:"乾草原",3:"荒地",4:"道路",5:"湿地",6:"森林",7:"丘陵",8:"高山",9:"沙漠",10:"河",11:"浅海",12:"深海",13:"残雪",14:"雪原",15:"雪丘",16:"雪山"}
    TERRAIN_COLORS = {0:"#2d5a27",1:"#4a8c3f",2:"#8b9a47",3:"#9e8b5e",4:"#c4a45a",5:"#5a7a3a",6:"#2d5a1e",7:"#7a8a5a",8:"#6a6a5a",9:"#d4c47a",10:"#3a6aaa",11:"#5a8aaa",12:"#2a4a7a",13:"#d4e4f4",14:"#e8f0f8",15:"#c8d8e8",16:"#f0f4f8"}

    def api_mpc_read(self, block_x: int = None, block_y: int = None, width: int = 546, height: int = 387) -> dict:
        """读取SANGO7.MPC地形数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        mpc_path = os.path.join(self.game_path, "map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            mpc_path = os.path.join(self.game_path, "Map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到 map/SANGO7.MPC")
        try:
            with open(mpc_path, "rb") as f:
                data = f.read()
            total = len(data)
            # 推断每条记录大小
            expected = self.GRID_COLS * self.GRID_ROWS
            if total >= expected:
                record_size = total // expected
            else:
                record_size = 1
            if block_x is not None and block_y is not None:
                idx = (block_y * self.GRID_COLS + block_x) * record_size
                if idx + record_size <= total:
                    val = data[idx]
                    return {"success": True, "x": block_x, "y": block_y, "terrain": val,
                            "terrain_name": self.TERRAIN_NAMES.get(val, f"未知({val})"),
                            "record_size": record_size, "total_bytes": total}
                return error_response(ErrorCode.INVALID_PARAM, "坐标超出范围")
            # 返回摘要
            terrain_counts = {}
            sample = []
            for gy in range(min(height, self.GRID_ROWS)):
                row = []
                for gx in range(min(width, self.GRID_COLS)):
                    idx = (gy * self.GRID_COLS + gx) * record_size
                    val = data[idx] if idx < total else 0
                    terrain_counts[val] = terrain_counts.get(val, 0) + 1
                    row.append(val)
                sample.append(row)
            summary = [{"id": k, "name": self.TERRAIN_NAMES.get(k, f"未知"), "count": v, "pct": round(v/expected*100,1)}
                       for k, v in sorted(terrain_counts.items())]
            return success_response({"data": sample, "summary": summary, "record_size": record_size, "total_bytes": total, "grid_cols": self.GRID_COLS, "grid_rows": self.GRID_ROWS, "expected_blocks": expected})
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_mpc_write(self, block_x: int, block_y: int, terrain: int) -> dict:
        """写入单个区块地形"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        mpc_path = os.path.join(self.game_path, "map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            mpc_path = os.path.join(self.game_path, "Map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到 map/SANGO7.MPC")
        try:
            if self.backup_mgr:
                self.backup_mgr.backup_file(mpc_path)
            with open(mpc_path, "rb") as f:
                data = bytearray(f.read())
            total = len(data)
            expected = self.GRID_COLS * self.GRID_ROWS
            record_size = total // expected if total >= expected else 1
            idx = (block_y * self.GRID_COLS + block_x) * record_size
            if idx + record_size <= total:
                data[idx] = terrain & 0xFF
                with open(mpc_path, "wb") as f:
                    f.write(data)
                return success_response(message=f"区块({block_x},{block_y})地形已设为{self.TERRAIN_NAMES.get(terrain,'?')}")
            return error_response(ErrorCode.INVALID_PARAM, "坐标超出范围")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_mpc_batch_write(self, changes: list) -> dict:
        """批量写入地形: [{x,y,terrain},...]"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        mpc_path = os.path.join(self.game_path, "map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            mpc_path = os.path.join(self.game_path, "Map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到 map/SANGO7.MPC")
        try:
            if self.backup_mgr:
                self.backup_mgr.backup_file(mpc_path)
            with open(mpc_path, "rb") as f:
                data = bytearray(f.read())
            total = len(data)
            expected = self.GRID_COLS * self.GRID_ROWS
            record_size = total // expected if total >= expected else 1
            count = 0
            for c in changes:
                idx = (c["y"] * self.GRID_COLS + c["x"]) * record_size
                if idx + record_size <= total:
                    data[idx] = c["terrain"] & 0xFF
                    count += 1
            with open(mpc_path, "wb") as f:
                f.write(data)
            return success_response({"count": count}, message=f"已更新{count}个区块")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # API: Shape .info.ini 位移编辑器
    # ============================================================
    def api_shape_info_list(self, category: str = "all") -> dict:
        """列出所有 .info.ini 位移文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        shape_dir = os.path.join(self.game_path, "Shape")
        if not os.path.exists(shape_dir):
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到Shape目录")
        infos = []
        for root, dirs, files in os.walk(shape_dir):
            for f in files:
                if f.endswith(".info.ini"):
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, shape_dir)
                    # 读取X/Y偏移
                    parser = IniParser()
                    parser.load(full)
                    x = parser.get("Offset", "X", "0")
                    y = parser.get("Offset", "Y", "0")
                    cat = os.path.basename(os.path.dirname(full)) if os.path.dirname(full) != shape_dir else "root"
                    if category != "all" and cat.lower() != category.lower():
                        continue
                    infos.append({"path": rel, "category": cat, "x": int(x), "y": int(y), "file": f})
        return {"success": True, "infos": infos, "count": len(infos), "categories": list(set(i["category"] for i in infos))}

    def api_shape_info_save(self, rel_path: str, x: int, y: int) -> dict:
        """保存单个 .info.ini 的位移参数"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        full = os.path.join(self.game_path, "Shape", rel_path)
        if not os.path.exists(full):
            return error_response(ErrorCode.FILE_NOT_FOUND)
        if self.backup_mgr:
            self.backup_mgr.backup_file(full)
        parser = IniParser()
        parser.load(full)
        parser.set("Offset", "X", str(x))
        parser.set("Offset", "Y", str(y))
        parser.save(full)
        return success_response(message=f"已保存 {rel_path}: X={x}, Y={y}")

    def api_shape_info_delete(self, rel_path: str) -> dict:
        """删除指定的 .info.ini 文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        full = os.path.join(self.game_path, "Shape", rel_path)
        if not os.path.exists(full):
            return error_response(ErrorCode.FILE_NOT_FOUND)
        if self.backup_mgr:
            self.backup_mgr.backup_file(full)
        os.remove(full)
        return success_response(message=f"已删除 {rel_path}")

    def api_shape_info_clone(self, rel_path: str, new_name: str) -> dict:
        """克隆指定的 .info.ini 文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        full = os.path.join(self.game_path, "Shape", rel_path)
        if not os.path.exists(full):
            return error_response(ErrorCode.FILE_NOT_FOUND, "源文件不存在")
        new_path = os.path.join(os.path.dirname(full), new_name)
        if os.path.exists(new_path):
            return error_response(ErrorCode.FILE_ALREADY_EXISTS, f"目标文件 {new_name} 已存在")
        import shutil
        shutil.copy2(full, new_path)
        return success_response(message=f"已克隆为 {new_name}")

    def api_shape_info_new(self, rel_path: str, category: str = "root") -> dict:
        """创建新的 .info.ini 文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        shape_dir = os.path.join(self.game_path, "Shape")
        if category and category != "root":
            dest_dir = os.path.join(shape_dir, category)
            os.makedirs(dest_dir, exist_ok=True)
        else:
            dest_dir = shape_dir
        full = os.path.join(dest_dir, rel_path)
        if os.path.exists(full):
            return error_response(ErrorCode.FILE_ALREADY_EXISTS, f"文件 {rel_path} 已存在")
        parser = IniParser()
        parser.add_section("Offset")
        parser.set("Offset", "X", "0")
        parser.set("Offset", "Y", "0")
        parser.save(full)
        return success_response(message=f"已创建 {rel_path}")

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

    # ============================================================
    # API: 常用内存地址预设表
    # ============================================================
    MEMORY_PRESETS = {
        "金钱": {"address": 0x0095FDE0, "size": 4, "desc": "玩家金钱（4字节）"},
        "主角等级": {"address": 0x0095FD00, "size": 2, "desc": "主角当前等级"},
        "主角经验": {"address": 0x0095FD04, "size": 4, "desc": "主角当前经验值"},
        "队伍兵力": {"address": 0x0095FE00, "size": 2, "desc": "第一队兵力"},
        "时间-年": {"address": 0x0095F100, "size": 2, "desc": "游戏时间年份"},
        "时间-月": {"address": 0x0095F102, "size": 1, "desc": "游戏时间月份"},
        "时间-日": {"address": 0x0095F103, "size": 1, "desc": "游戏时间日期"},
        "国库-金": {"address": 0x0095FC00, "size": 4, "desc": "国库金币数量"},
        "国库-粮": {"address": 0x0095FC04, "size": 4, "desc": "国库粮草数量"},
        "人口": {"address": 0x0095FD10, "size": 2, "desc": "当前城池人口"},
        "民心": {"address": 0x0095FD14, "size": 2, "desc": "当前城池民心(0-1000)"},
        "防御": {"address": 0x0095FD18, "size": 2, "desc": "当前城池防御值"},
        "开发": {"address": 0x0095FD1C, "size": 2, "desc": "当前城池开发值"},
        "武将体力": {"address": 0x0095FE80, "size": 2, "desc": "主角当前体力HP"},
        "武将技力": {"address": 0x0095FE84, "size": 2, "desc": "主角当前技力MP"},
        "武将武力": {"address": 0x0095FE88, "size": 1, "desc": "主角基础武力"},
        "武将智力": {"address": 0x0095FE89, "size": 1, "desc": "主角基础智力"},
        "武将功勋": {"address": 0x0095FE90, "size": 4, "desc": "主角当前功勋值"},
        "战斗计时": {"address": 0x0095FF00, "size": 2, "desc": "千人战剩余时间"},
        "士气": {"address": 0x0095FF10, "size": 2, "desc": "当前队伍士气"},
    }

    # reserved: 预留给未来功能，暂无前端调用
    def api_memory_presets(self) -> dict:
        return {"success": True, "presets": self.MEMORY_PRESETS, "count": len(self.MEMORY_PRESETS)}

    def api_memory_read_preset(self, preset_name: str) -> dict:
        """使用预设名称读取内存"""
        if not hasattr(self, '_memory_pm') or not self._memory_pm:
            return error_response(ErrorCode.GAME_PATH_NOT_SET, "请先附加到游戏进程 (memoryAttach)")
        preset = self.MEMORY_PRESETS.get(preset_name)
        if not preset:
            return error_response(ErrorCode.INVALID_PARAM, f"未知预设: {preset_name}，可用: {list(self.MEMORY_PRESETS.keys())}")
        return self.api_memory_read(preset["address"], preset["size"])

    # ============================================================
    # API: SHP 批量改名
    # ============================================================
    def api_shp_batch_rename(self, directory: str, prefix: str, start_id: int, digits: int = 4) -> dict:
        """批量重命名SHP文件: prefix_0001.shp, prefix_0002.shp..."""
        if not os.path.isdir(directory):
            return error_response(ErrorCode.FILE_NOT_FOUND, "目录不存在")
        shp_files = sorted([f for f in os.listdir(directory) if f.lower().endswith('.shp')])
        if not shp_files:
            return error_response(ErrorCode.FILE_NOT_FOUND, "目录中没有SHP文件")
        renamed = []
        for i, old_name in enumerate(shp_files):
            new_name = f"{prefix}_{start_id + i:0{digits}d}.shp"
            old_path = os.path.join(directory, old_name)
            new_path = os.path.join(directory, new_name)
            if old_path != new_path:
                if os.path.exists(new_path):
                    return error_response(ErrorCode.FILE_ALREADY_EXISTS, f"目标文件已存在: {new_name}")
                os.rename(old_path, new_path)
                renamed.append({"from": old_name, "to": new_name})
        return success_response({"renamed": renamed, "count": len(renamed)}, message=f"已重命名{len(renamed)}个文件")

    # ============================================================
    # API: 城池连接关系
    # ============================================================
    def api_city_connections(self) -> dict:
        """获取所有城池连接关系（用于可视化）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        city_path = os.path.join(self.game_path, "Setting", "City.ini")
        citypos_path = os.path.join(self.game_path, "Setting", "CityPos.ini")
        if not os.path.exists(city_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到 City.ini")
        parser = IniParser()
        parser.load(city_path)
        cities = {}
        for s in parser.get_all_sections("CITY"):
            e = dict(s.entries)
            no = e.get("No", "")
            name = e.get("Name", "")
            conns = []
            for i in range(10):
                conn_key = f"Connect{i:02d}"
                conn_val = e.get(conn_key, "")
                if conn_val and conn_val.strip():
                    parts = conn_val.split(",")
                    if len(parts) >= 2:
                        conns.append({"target": parts[0].strip(), "distance": parts[1].strip()})
            cities[no] = {"no": no, "name": name, "connections": conns}
        # 加载坐标
        positions = {}
        if os.path.exists(citypos_path):
            pos_parser = IniParser()
            pos_parser.load(citypos_path)
            for s in pos_parser.get_all_sections("CITYPOS"):
                e = dict(s.entries)
                positions[e.get("No", "")] = {"x": int(e.get("PosX", 0)), "y": int(e.get("PosY", 0))}
        return {"success": True, "cities": cities, "positions": positions, "map_size": [self.MAP_WIDTH, self.MAP_HEIGHT]}

    def api_load_city_connect(self) -> dict:
        """加载城池连接数据（可编辑模式）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        city_path = os.path.join(self.game_path, "Setting", "City.ini")
        if not os.path.exists(city_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到 City.ini")
        parser = IniParser()
        parser.load(city_path)
        data = []
        for s in parser.get_all_sections("CITY"):
            data.append(dict(s.entries))
        return success_response({"data": data, "count": len(data)})

    def api_save_city_connect(self, data: list) -> dict:
        """保存城池连接数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        city_path = os.path.join(self.game_path, "Setting", "City.ini")
        try:
            if self.backup_mgr:
                self.backup_mgr.backup_file(city_path)
            parser = IniParser()
            parser.load(city_path)
            # 更新 CITY sections
            for item in data:
                no = item.get("No", "")
                section = parser.get_section("CITY", no)
                if section:
                    for k, v in item.items():
                        section.set(k, str(v) if v is not None else "")
            parser.save(city_path)
            return success_response({"count": len(data)}, message="城池连接已保存")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_load_idini(self) -> dict:
        """加载 WinTest/id.ini"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        idini_path = os.path.join(self.game_path, "WinTest", "id.ini")
        if not os.path.exists(idini_path):
            return success_response({"data": [], "count": 0, "message": "id.ini 不存在"})
        try:
            parser = IniParser()
            parser.load(idini_path)
            data = []
            for s in parser.get_all_sections("ID"):
                e = dict(s.entries)
                data.append({"key": e.get("key", ""), "value": e.get("value", "")})
            return success_response({"data": data, "count": len(data)})
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_save_idini(self, data: list) -> dict:
        """保存 WinTest/id.ini"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        idini_path = os.path.join(self.game_path, "WinTest", "id.ini")
        os.makedirs(os.path.dirname(idini_path), exist_ok=True)
        if self.backup_mgr:
            self.backup_mgr.backup_file(idini_path)
        try:
            parser = IniParser()
            for item in data:
                parser.add_section("ID", {"key": item.get("key", ""), "value": item.get("value", "")})
            parser.save(idini_path)
            return success_response(message=f"已保存 {len(data)} 条")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # API: 脚本编辑器
    # ============================================================

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

    def api_mod_merge(self, mod_a: str, mod_b: str, output_name: str = None) -> dict:
        """合并两个MOD"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        mods_dir = os.path.join(WRITE_ROOT, "mods")
        mod_a_path = os.path.join(mods_dir, mod_a)
        mod_b_path = os.path.join(mods_dir, mod_b)
        if not os.path.exists(mod_a_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"MOD A 不存在: {mod_a}")
        if not os.path.exists(mod_b_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"MOD B 不存在: {mod_b}")

        output = output_name or f"{mod_a}+{mod_b}"
        output_path = os.path.join(mods_dir, output)
        if os.path.exists(output_path):
            return error_response(ErrorCode.FILE_ALREADY_EXISTS, f"输出MOD已存在: {output}")

        os.makedirs(output_path, exist_ok=True)
        os.makedirs(os.path.join(output_path, "data"), exist_ok=True)
        os.makedirs(os.path.join(output_path, "snapshots"), exist_ok=True)

        # 合并 data 目录
        conflicts = []
        for src_mod in [mod_a_path, mod_b_path]:
            src_data = os.path.join(src_mod, "data")
            if not os.path.exists(src_data):
                continue
            for fname in os.listdir(src_data):
                src_file = os.path.join(src_data, fname)
                dst_file = os.path.join(output_path, "data", fname)
                if os.path.exists(dst_file):
                    conflicts.append(fname)
                    # 重命名冲突文件
                    base, ext = os.path.splitext(fname)
                    conflict_name = f"{base}_from_{os.path.basename(src_mod)}{ext}"
                    shutil.copy2(src_file, os.path.join(output_path, "data", conflict_name))
                else:
                    shutil.copy2(src_file, dst_file)

        # 合并 snapshots
        for src_mod in [mod_a_path, mod_b_path]:
            src_snaps = os.path.join(src_mod, "snapshots")
            if not os.path.exists(src_snaps):
                continue
            for fname in os.listdir(src_snaps):
                src_file = os.path.join(src_snaps, fname)
                dst_file = os.path.join(output_path, "snapshots", fname)
                if not os.path.exists(dst_file):
                    shutil.copy2(src_file, dst_file)

        # 创建 info
        # 合并依赖信息
        merged_deps = []
        seen_deps = set()
        for src_mod in [mod_a_path, mod_b_path]:
            src_info_path = os.path.join(src_mod, "mod_info.json")
            if os.path.exists(src_info_path):
                try:
                    with open(src_info_path, "r", encoding="utf-8") as f:
                        src_info = json.load(f)
                    for dep in src_info.get("dependencies", []):
                        dep_name = dep.get("name", dep) if isinstance(dep, dict) else dep
                        if dep_name not in seen_deps:
                            seen_deps.add(dep_name)
                            merged_deps.append(dep if isinstance(dep, dict) else {"name": dep, "version": "*"})
                except Exception as e:
                    logger.error(f"操作失败: {e}")
                    pass

        info = {
            "name": output,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "description": f"合并自 {mod_a} + {mod_b}",
            "merged_from": [mod_a, mod_b],
            "dependencies": merged_deps,
            "conflicts": conflicts,
        }
        with open(os.path.join(output_path, "mod_info.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": f"MOD合并完成: {output}",
            "output": output,
            "conflicts": conflicts,
            "conflictCount": len(conflicts),
        }

    def api_delete_history(self, index: int) -> dict:
        """原子删除历史事件条目"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            r = self.api_load_histories()
            if not r.get("success"):
                return r
            data = r.get("data", [])
            if index < 0 or index >= len(data):
                return error_response(ErrorCode.INVALID_PARAM, f"索引无效: {index}")
            deleted = data.pop(index)
            self.history_parser = None  # 清除缓存
            save_r = self.api_save_histories(data)
            if save_r.get("success"):
                return success_response(message=f"已删除: {deleted.get('Name', f'事件#{index}')}")
            return save_r
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_batch_cross_file(self, target_field: str, operation: str, value: str,
                               file_types: List[str] = None, filter_field: str = None,
                               filter_value: str = None, preview: bool = True) -> dict:
        """跨文件批量操作：对多个文件类型的同一字段进行批量修改"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        # 支持的文件类型和字段映射
        file_configs = {
            "General01.ini": {"api": "api_load_generals", "save": "api_save_generals", "fields": ["Str", "Int", "HP", "MP", "Morale", "Loyal", "Race", "Sex", "Life", "IsFamous", "IsResurgable"]},
            "Thing.ini": {"api": "api_load_things", "save": "api_save_things", "fields": ["Str", "Int", "HP", "MP", "Speed", "Loyal", "Rate", "Price", "Level", "IsRare", "Count"]},
            "Soldier.ini": {"api": "api_load_soldiers", "save": "api_save_soldiers", "fields": ["HP", "Speed", "ATK", "DEF", "Life", "Range"]},
            "Title.ini": {"api": "api_load_titles", "save": "api_save_titles", "fields": ["Str", "Int", "HP", "MP", "Level"]},
        }

        targets = file_types or list(file_configs.keys())
        valid_targets = [t for t in targets if t in file_configs]
        if not valid_targets:
            return error_response(ErrorCode.INVALID_PARAM, "没有有效的文件类型")

        total_affected = 0
        preview_data = []
        all_modified = {}

        for filename in valid_targets:
            config = file_configs[filename]
            if target_field not in config["fields"]:
                continue

            try:
                load_fn = getattr(self, config["api"])
                r = load_fn()
                if not r or not r.get("success"):
                    continue
                entries = r.get("data", [])
                affected = 0
                modified = []

                for entry in entries:
                    # 检查过滤条件
                    if filter_field and filter_value:
                        entry_val = str(entry.get(filter_field, ""))
                        if entry_val != filter_value:
                            continue

                    old_val = entry.get(target_field)
                    try:
                        new_val = self._apply_batch_op(old_val, operation, value)
                        if new_val != old_val:
                            entry[target_field] = new_val
                            affected += 1
                            modified.append({"no": entry.get("No", "?"), "name": entry.get("Name", ""), "old": old_val, "new": new_val})
                    except Exception as e:
                        logger.error(f"操作失败: {e}")
                        continue

                if affected > 0:
                    total_affected += affected
                    preview_data.append({"file": filename, "count": affected, "changes": modified[:10]})
                    all_modified[filename] = entries

                    if not preview:
                        # 执行保存
                        save_fn = getattr(self, config["save"])
                        save_fn(entries)

            except Exception as e:
                logger.warning(f"跨文件批量操作失败 {filename}: {e}")

        if preview:
            return {"success": True, "preview": True, "totalAffected": total_affected, "results": preview_data}

        return {
            "success": True,
            "preview": False,
            "totalAffected": total_affected,
            "results": preview_data,
            "message": f"跨文件批量操作完成，共影响 {total_affected} 条记录",
        }

    def _apply_batch_op(self, old_val, operation: str, value: str):
        """应用批量操作的数值计算"""
        if old_val is None:
            return value
        try:
            old_num = float(old_val) if old_val != "" else 0
        except (ValueError, TypeError):
            return value
        try:
            val_num = float(value)
        except (ValueError, TypeError):
            return value

        if operation == "set":
            result = val_num
        elif operation == "add":
            result = old_num + val_num
        elif operation == "multiply":
            result = old_num * val_num
        elif operation == "min":
            result = min(old_num, val_num)
        elif operation == "max":
            result = max(old_num, val_num)
        else:
            return value

        return int(result) if isinstance(old_val, int) or old_val == "" else result

    def _load_schema(self, schema_name: str) -> dict:
        """内部方法：加载 data/ 目录下的 schema JSON 文件"""
        if not schema_name.endswith(".json"):
            schema_name = schema_name + ".json"
        schema_path = os.path.join(PROJECT_ROOT, "data", schema_name)
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Schema文件不存在: {schema_name}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Schema文件解析失败: {schema_name}: {e}")
            return {}

    def api_get_progress(self) -> dict:
        """获取开发进度"""
        return DEVELOPMENT_PROGRESS

    def api_get_data_file(self, filename: str) -> dict:
        """读取 data/ 目录下的 JSON 文件（打包后也能正确访问）"""
        if not filename.endswith('.json'):
            filename = filename + '.json'
        data_path = os.path.join(PROJECT_ROOT, 'data', filename)
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"数据文件不存在: {filename}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"数据文件解析失败: {filename}: {e}")
            return {}

    def api_get_schema(self, schema_type: str) -> dict:
        """获取Schema定义"""
        schema_map = {
            "general": "general_schema.json",
            "soldier": "soldier_schema.json",
            "thing": "thing_schema.json",
            "bfmagic": "bfmagic_schema.json",
            "sfmagic": "sfmagic_schema.json",
            "superatk": "superatk_schema.json",
            "defskill": "defskill_schema.json",
            "genskill": "genskill_schema.json",
            "formation": "formation_schema.json",
            "title": "title_schema.json",
            "nation": "nation_schema.json",
            "city": "city_schema.json",
            "genlv": "genlv_schema.json",
            "history": "history_schema.json",
            "armyskill": "armyskill_schema.json",
            "armygroupskill": "armygroupskill_schema.json",
            "age": "age_schema.json",
            "general02": "general02_schema.json",
            "scenario": "scenario_schema.json",
            "variable": "variable_schema.json",
            "itemenhance": "itemenhance_schema.json",
            "bffront": "bffront_schema.json",
            "dialogue": "dialogue_schema.json",
            "color": "color_schema.json",
            "citypos": "citypos_schema.json",
            "systemtext": "systemtext_schema.json",
            "gossiptext": "gossiptext_schema.json",
            "terrain": "terrain_schema.json",
            "extraterrain": "extraterrain_schema.json",
            "formatoffsetpos": "formatoffsetpos_schema.json",
            "buildingpos": "buildingpos_schema.json",
            "sfbridge": "sfbridge_schema.json",
            "sfroadblock": "sfroadblock_schema.json",
            "sfroadblockpos": "sfroadblockpos_schema.json",
            "var": "var_schema.json",
            "font": "font_schema.json",
            "systemini": "system_ini_schema.json",
            "termtext": "termtext_schema.json",
            "citysellitem": "citysellitem_schema.json",
            "gametext": "gametext_schema.json",
            "sango7": "sango7_schema.json",
            "format": "format_schema.json",
            "chessformat": "chessformat_schema.json",
        }
        filename = schema_map.get(schema_type)
        if not filename:
            return error_response(ErrorCode.INVALID_PARAM, "未知Schema类型")

        schema_path = os.path.join(PROJECT_ROOT, "data", filename)
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                return success_response(json.load(f))
        except FileNotFoundError:
            return error_response(ErrorCode.FILE_NOT_FOUND, f"Schema文件不存在: {filename}")
        except json.JSONDecodeError as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

