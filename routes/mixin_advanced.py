import os, json, re, shutil, base64, tempfile, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional

# 从 main.py 导入模块级常量
try:
    from main import WRITE_ROOT
except ImportError:
    import sys
    WRITE_ROOT = os.path.dirname(os.path.abspath(__file__))

from core.event_templates import EVENT_TEMPLATES, generate_event_section

logger = logging.getLogger('San7ModMaker')

__all__ = ['San7ModMakerAdvanced']

class San7ModMakerAdvanced:
    """MOD制作器 - 高级功能 (存档/脚本/PCK/模板/引擎)"""

    # API: language.DAT 语言标识编辑
    # ============================================================
    def api_read_language_dat(self) -> dict:
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": "请先设置游戏目录"}
        if lang not in ("BIG5", "GB", "SJIS", "KOR"):
            return {"success": False, "message": f"不支持的语言: {lang}，支持: BIG5/GB/SJIS/KOR"}
        path = os.path.join(self.game_path, "language.DAT")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        with open(path, "wb") as f:
            f.write(f"LANG_{lang}".encode("ascii"))
        return {"success": True, "message": f"language.DAT 已切换为: LANG_{lang}", "current": lang}
    def api_switch_language_preset(self, lang: str) -> dict:
        """一键切换语言：同步 language.DAT + font.ini + 三个文本INI"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if lang not in ("BIG5", "GB", "SJIS", "KOR"):
            return {"success": False, "message": f"不支持的语言: {lang}"}
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
            return {"success": True, "message": f"语言已切换为 {lang}", "switched": switched}
        except Exception as e:
            return {"success": False, "message": f"切换失败: {str(e)}", "switched": switched}

    def api_export_language_pack(self, target_path: str = None) -> dict:
        """导出当前语言包为ZIP文件（含 language.DAT + font.ini + 三个文本INI）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": True, "message": f"语言包已导出: {os.path.basename(target_path)} ({size_kb} KB)", "path": target_path, "files": packed, "language": lang, "size_kb": size_kb}
        except Exception as e:
            return {"success": False, "message": f"导出失败: {str(e)}"}

    def api_import_language_pack(self, file_path: str) -> dict:
        """导入语言包ZIP文件"""
        import zipfile
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if not os.path.exists(file_path):
            return {"success": False, "message": "文件不存在"}
        if not file_path.lower().endswith(".zip"):
            return {"success": False, "message": "仅支持 .zip 格式的语言包"}

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()
                # 验证包结构
                if "language.DAT" not in names:
                    return {"success": False, "message": "无效的语言包: 缺少 language.DAT"}
                if "pack_meta.json" in names:
                    meta = json.loads(zf.read("pack_meta.json"))
                    lang = meta.get("language", "?")
                else:
                    lang = "?"

                imported = []
                for name in names:
                    if name == "pack_meta.json":
                        continue
                    target = os.path.join(self.game_path, name)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    if self.backup_mgr and os.path.exists(target):
                        self.backup_mgr.backup_file(target)
                    with open(target, "wb") as f:
                        f.write(zf.read(name))
                    imported.append(name)

            return {"success": True, "message": f"语言包已导入 ({lang}): {len(imported)} 个文件", "files": imported, "language": lang}
        except Exception as e:
            return {"success": False, "message": f"导入失败: {str(e)}"}

    def api_diff_language_texts(self, source_lang: str = "BIG5") -> dict:
        """对比当前语言与源语言的文本差异"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

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
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            self.term_text = TermTextManager(self.game_path)
            self.term_text.load()
            return {"success": True, "message": "TermText 缓存已刷新", "count": len(self.term_text._data) if hasattr(self.term_text, '_data') else 0}
        except Exception as e:
            return {"success": False, "message": f"刷新失败: {str(e)}"}

    def api_language_status(self) -> dict:
        """获取语言系统完整状态（检测所有可用语言文件）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": "BMP文件不存在"}
        try:
            with open(bmp_path, "rb") as f:
                # 读取BMP头
                header = f.read(54)
                if header[0:2] != b"BM":
                    return {"success": False, "message": "不是有效的BMP文件"}
                width = struct.unpack("<I", header[18:22])[0]
                height = struct.unpack("<I", header[22:26])[0]
                if width != 382 or height != 270:
                    return {"success": False, "message": f"BMP尺寸必须为382×270，当前为{width}×{height}"}
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
                return {"success": True, "message": f"转换成功: {raw_path}", "raw_path": raw_path, "size": len(raw_data)}
        except Exception as e:
            return {"success": False, "message": f"转换失败: {str(e)}"}

    def api_raw2bmp(self, raw_path: str) -> dict:
        """将 RAW 小地图文件反向转换为 BMP 图片"""
        import struct
        if not os.path.exists(raw_path):
            return {"success": False, "message": "RAW文件不存在"}
        try:
            raw_size = os.path.getsize(raw_path)
            expected_size = 382 * 270 * 2  # RGB565, 2 bytes per pixel
            if raw_size != expected_size:
                return {"success": False, "message": f"RAW文件大小不正确，期望 {expected_size} bytes，实际 {raw_size} bytes"}
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
            return {"success": True, "message": f"反向转换成功: {bmp_path}", "bmp_path": bmp_path, "size": len(pixel_data)}
        except Exception as e:
            return {"success": False, "message": f"反向转换失败: {str(e)}"}

    def api_bmp2raw_batch(self, dir_path: str) -> dict:
        """批量转换目录下所有 382×270 BMP 文件为 RAW"""
        import struct
        if not os.path.isdir(dir_path):
            return {"success": False, "message": "目录不存在"}
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
                failed += 1
                errors.append(f"{fname}: {str(e)}")
        msg = f"批量转换完成: 成功 {converted} 个"
        if failed:
            msg += f", 失败 {failed} 个"
        return {"success": True, "message": msg, "converted": converted, "failed": failed, "errors": errors[:10]}

    def api_bmp_preview(self, bmp_path: str) -> dict:
        """返回 BMP 文件的 base64 编码供前端预览"""
        import base64
        if not os.path.exists(bmp_path):
            return {"success": False, "message": "BMP文件不存在"}
        try:
            with open(bmp_path, "rb") as f:
                data = f.read()
            b64 = base64.b64encode(data).decode("ascii")
            return {"success": True, "base64": b64, "message": "预览加载成功"}
        except Exception as e:
            return {"success": False, "message": f"预览失败: {str(e)}"}

    # ============================================================
    # API: SHP 像素编辑器
    # ============================================================
    def api_shp_pixel_load(self, shp_path: str) -> dict:
        """加载SHP文件的像素数据和调色板"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            self.shp_converter.set_game_path(self.game_path)
            pixel_data = self.shp_converter.get_pixel_data(shp_path)
            return {"success": True, **pixel_data, "message": f"加载成功: {pixel_data['width']}x{pixel_data['height']}"}
        except FileNotFoundError:
            return {"success": False, "message": f"SHP文件不存在: {shp_path}"}
        except Exception as e:
            return {"success": False, "message": f"加载失败: {str(e)}"}

    def api_shp_pixel_save(self, shp_path: str, pixels: list, width: int = None, height: int = None) -> dict:
        """保存修改后的像素数据到SHP文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            self.shp_converter.set_game_path(self.game_path)
            saved = self.shp_converter.save_pixel_data(shp_path, pixels, width, height)
            return {"success": True, "saved": saved, "message": "像素数据已保存"}
        except Exception as e:
            return {"success": False, "message": f"保存失败: {str(e)}"}

    def api_shp_get_palette(self) -> dict:
        """获取ACT调色板RGB列表"""
        try:
            palette = self.shp_converter.get_palette_rgb()
            return {"success": True, "palette": palette, "total": len(palette), "message": "调色板加载成功"}
        except Exception as e:
            return {"success": False, "message": f"加载失败: {str(e)}"}

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
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            dirs = self._get_audio_dirs()
            total = sum(d["count"] for d in dirs.values())
            return {"success": True, "dirs": dirs, "total_files": total,
                    "message": f"共 {total} 个音频文件"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_preview_audio(self, directory: str, filename: str) -> dict:
        """预览音频文件：返回 base64 编码"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        import base64
        try:
            filepath = os.path.join(self.game_path, directory, filename)
            # 安全检查
            if not os.path.realpath(filepath).startswith(os.path.realpath(self.game_path)):
                return {"success": False, "message": "路径越界"}
            if not os.path.exists(filepath):
                return {"success": False, "message": "文件不存在"}
            # 限制文件大小 (50MB)
            if os.path.getsize(filepath) > 50 * 1024 * 1024:
                return {"success": False, "message": "文件过大 (超过50MB)，请使用本地播放器播放"}
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
            return {"success": False, "message": f"预览失败: {str(e)}"}

    def api_import_audio(self, source_path: str, target_dir: str, target_name: str = None) -> dict:
        """导入音频文件到 Music/ 或 Sound/ 目录"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if target_dir not in ("Music", "Sound", "Audio"):
            return {"success": False, "message": "目标目录必须是 Music/Sound/Audio"}
        if not os.path.exists(source_path):
            return {"success": False, "message": "源文件不存在"}
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
            return {"success": False, "message": str(e)}

    def api_delete_audio(self, directory: str, filename: str) -> dict:
        """删除音频文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            filepath = os.path.join(self.game_path, directory, filename)
            if not os.path.realpath(filepath).startswith(os.path.realpath(self.game_path)):
                return {"success": False, "message": "路径越界"}
            if not os.path.exists(filepath):
                return {"success": False, "message": "文件不存在"}
            if self.backup_mgr:
                self.backup_mgr.backup_file(filepath)
            os.remove(filepath)
            return {"success": True, "message": f"已删除: {filename}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_rename_audio(self, directory: str, old_name: str, new_name: str) -> dict:
        """重命名音频文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            old_path = os.path.join(self.game_path, directory, old_name)
            new_path = os.path.join(self.game_path, directory, new_name)
            if not os.path.realpath(old_path).startswith(os.path.realpath(self.game_path)):
                return {"success": False, "message": "路径越界"}
            if not os.path.exists(old_path):
                return {"success": False, "message": "文件不存在"}
            if os.path.exists(new_path):
                return {"success": False, "message": "目标文件名已存在"}
            if self.backup_mgr:
                self.backup_mgr.backup_file(old_path)
            os.rename(old_path, new_path)
            return {"success": True, "message": f"已重命名: {old_name} → {new_name}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ============================================================
    # API: 沙盒测试模式
    # ============================================================
    def api_create_sandbox(self) -> dict:
        """创建沙盒环境：复制游戏文件到临时目录用于测试"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        sandbox_dir = os.path.join(WRITE_ROOT, "sandbox")
        # 如果已有沙盒，询问
        if os.path.exists(sandbox_dir):
            return {"success": False, "message": "沙盒已存在，请先清理旧沙盒", "sandbox_exists": True}

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
            return {"success": False, "message": f"创建沙盒失败: {str(e)}"}

    def api_install_to_sandbox(self, mod_name: str) -> dict:
        """将MOD安装到沙盒中测试"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        sandbox_dir = os.path.join(WRITE_ROOT, "sandbox")
        if not os.path.exists(sandbox_dir):
            return {"success": False, "message": "沙盒不存在，请先创建沙盒"}

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if not os.path.exists(export_dir):
            return {"success": False, "message": f"MOD包 '{mod_name}' 不存在，请先打包"}

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
            return {"success": False, "message": f"安装失败: {str(e)}"}

    def api_launch_sandbox(self) -> dict:
        """从沙盒启动游戏"""
        sandbox_dir = os.path.join(WRITE_ROOT, "sandbox")
        exe_path = os.path.join(sandbox_dir, "Sango7.exe")
        if not os.path.exists(exe_path):
            return {"success": False, "message": "沙盒中未找到Sango7.exe，请先创建沙盒"}

        try:
            import subprocess
            subprocess.Popen(exe_path, cwd=sandbox_dir,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"success": True, "message": "游戏已从沙盒启动"}
        except Exception as e:
            return {"success": False, "message": f"启动失败: {str(e)}"}

    def api_cleanup_sandbox(self) -> dict:
        """清理沙盒环境"""
        sandbox_dir = os.path.join(WRITE_ROOT, "sandbox")
        if not os.path.exists(sandbox_dir):
            return {"success": True, "message": "沙盒不存在，无需清理"}

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
            return {"success": True, "message": "沙盒已清理"}
        except Exception as e:
            return {"success": False, "message": f"清理失败: {str(e)}"}

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
            except Exception:
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
            except Exception:
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
        except Exception:
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
        return {"success": True, "message": "操作历史已清空"}

    # ============================================================
    # API: 窗口模式分辨率预设
    # ============================================================
    def api_apply_resolution_preset(self, preset: str) -> dict:
        """应用分辨率预设: 1024x768/1280x720/1366x768/1440x900/1600x900/1920x1080/fullscreen"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": f"不支持的预设: {preset}，可用: {list(presets.keys())}"}
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
        return {"success": True, "message": f"分辨率已设置为 {label}", "width": w, "height": h, "fullscreen": fullscreen}

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
            return {"success": False, "message": f"坐标超出范围 (0~{self.MAP_WIDTH-1}, 0~{self.MAP_HEIGHT-1})"}
        gx = x // self.BLOCK_SIZE
        gy = y // self.BLOCK_SIZE
        block_no = gy * self.GRID_COLS + gx
        return {"success": True, "x": x, "y": y, "grid_x": gx, "grid_y": gy,
                "block_no": block_no, "block_size": self.BLOCK_SIZE,
                "grid_cols": self.GRID_COLS, "grid_rows": self.GRID_ROWS}

    def api_block_inverse(self, block_no: int) -> dict:
        """区块号→坐标范围转换"""
        if block_no < 0 or block_no >= self.GRID_COLS * self.GRID_ROWS:
            return {"success": False, "message": f"区块号超出范围 (0~{self.GRID_COLS * self.GRID_ROWS - 1})"}
        gy = block_no // self.GRID_COLS
        gx = block_no % self.GRID_COLS
        return {"success": True, "block_no": block_no, "grid_x": gx, "grid_y": gy,
                "x_min": gx * self.BLOCK_SIZE, "y_min": gy * self.BLOCK_SIZE,
                "x_max": (gx + 1) * self.BLOCK_SIZE - 1, "y_max": (gy + 1) * self.BLOCK_SIZE - 1,
                "block_size": self.BLOCK_SIZE, "grid_cols": self.GRID_COLS, "grid_rows": self.GRID_ROWS}

    def api_load_map_summary(self) -> dict:
        """加载地图摘要：城池坐标+建筑坐标+地形类型列表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": "请先设置游戏目录"}
        citypos_path = os.path.join(self.game_path, "Setting", "CityPos.ini")
        if not os.path.exists(citypos_path):
            return {"success": False, "message": "未找到 CityPos.ini"}
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
            return {"success": True, "message": f"已保存 {len(cities)} 个城池位置"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ============================================================
    # API: PCK 资源预览增强
    # ============================================================
    def api_pck_preview_shp(self, pck_name: str, internal_path: str) -> dict:
        """从PCK内直接预览SHP图片（返回base64 PNG）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        safe_pck = os.path.basename(pck_name)
        if safe_pck != pck_name or '..' in pck_name:
            return {"success": False, "message": "无效的PCK文件名"}
        pck_path = os.path.join(self.game_path, safe_pck)
        if not os.path.exists(pck_path):
            return {"success": False, "message": f"未找到 {pck_name}"}
        try:
            # 从PCK提取SHP二进制数据到内存
            with open(pck_path, "rb") as f:
                import struct
                magic = struct.unpack("<I", f.read(4))[0]
                if magic != 0x02000000:
                    return {"success": False, "message": "非标准PCK格式"}
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
                        return {"success": False, "message": "无法解码SHP图片"}
                return {"success": False, "message": f"PCK中未找到: {internal_path}"}
        except Exception as e:
            return {"success": False, "message": f"预览失败: {str(e)}"}

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
                        return {"success": True, "message": f"已附加到 {self._memory_process}",
                                "process": self._memory_process, "pid": proc.th32ProcessID}
                except (Exception,):
                    continue
            return {"success": False, "message": "未找到运行中的SG7.exe进程"}
        except ImportError:
            return {"success": False, "message": "pymem库未安装，请运行: pip install pymem"}

    def api_memory_read(self, address: int, size: int = 4) -> dict:
        """读取游戏内存"""
        if not hasattr(self, '_memory_pm') or not self._memory_pm:
            return {"success": False, "message": "请先附加到游戏进程 (memoryAttach)"}
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
            return {"success": False, "message": f"读取失败: {str(e)}"}

    def api_memory_write(self, address: int, value: int, size: int = 4) -> dict:
        """写入游戏内存"""
        if not hasattr(self, '_memory_pm') or not self._memory_pm:
            return {"success": False, "message": "请先附加到游戏进程 (memoryAttach)"}
        try:
            if size == 1:
                self._memory_pm.write_uchar(address, value)
            elif size == 2:
                self._memory_pm.write_ushort(address, value)
            elif size == 4:
                self._memory_pm.write_uint(address, value)
            else:
                return {"success": False, "message": "不支持的大小，仅支持 1/2/4 字节"}
            return {"success": True, "message": f"已写入 {hex(value)} 到 {hex(address)}"}
        except Exception as e:
            return {"success": False, "message": f"写入失败: {str(e)}"}

    def api_memory_search(self, value: int, size: int = 4) -> dict:
        """搜索内存值"""
        if not hasattr(self, '_memory_pm') or not self._memory_pm:
            return {"success": False, "message": "请先附加到游戏进程 (memoryAttach)"}
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
            return {"success": False, "message": f"搜索失败: {str(e)}"}

    # ============================================================
    # API: SANGO7.MPC 地形编辑器
    # ============================================================
    TERRAIN_NAMES = {0:"无",1:"草原",2:"乾草原",3:"荒地",4:"道路",5:"湿地",6:"森林",7:"丘陵",8:"高山",9:"沙漠",10:"河",11:"浅海",12:"深海",13:"残雪",14:"雪原",15:"雪丘",16:"雪山"}
    TERRAIN_COLORS = {0:"#2d5a27",1:"#4a8c3f",2:"#8b9a47",3:"#9e8b5e",4:"#c4a45a",5:"#5a7a3a",6:"#2d5a1e",7:"#7a8a5a",8:"#6a6a5a",9:"#d4c47a",10:"#3a6aaa",11:"#5a8aaa",12:"#2a4a7a",13:"#d4e4f4",14:"#e8f0f8",15:"#c8d8e8",16:"#f0f4f8"}

    def api_mpc_read(self, block_x: int = None, block_y: int = None, width: int = 546, height: int = 387) -> dict:
        """读取SANGO7.MPC地形数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        mpc_path = os.path.join(self.game_path, "map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            mpc_path = os.path.join(self.game_path, "Map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            return {"success": False, "message": "未找到 map/SANGO7.MPC"}
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
                return {"success": False, "message": "坐标超出范围"}
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
            return {"success": True, "data": sample, "summary": summary, "record_size": record_size,
                    "total_bytes": total, "grid_cols": self.GRID_COLS, "grid_rows": self.GRID_ROWS,
                    "expected_blocks": expected}
        except Exception as e:
            return {"success": False, "message": f"读取失败: {str(e)}"}

    def api_mpc_write(self, block_x: int, block_y: int, terrain: int) -> dict:
        """写入单个区块地形"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        mpc_path = os.path.join(self.game_path, "map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            mpc_path = os.path.join(self.game_path, "Map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            return {"success": False, "message": "未找到 map/SANGO7.MPC"}
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
                return {"success": True, "message": f"区块({block_x},{block_y})地形已设为{self.TERRAIN_NAMES.get(terrain,'?')}"}
            return {"success": False, "message": "坐标超出范围"}
        except Exception as e:
            return {"success": False, "message": f"写入失败: {str(e)}"}

    def api_mpc_batch_write(self, changes: list) -> dict:
        """批量写入地形: [{x,y,terrain},...]"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        mpc_path = os.path.join(self.game_path, "map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            mpc_path = os.path.join(self.game_path, "Map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            return {"success": False, "message": "未找到 map/SANGO7.MPC"}
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
            return {"success": True, "message": f"已更新{count}个区块", "count": count}
        except Exception as e:
            return {"success": False, "message": f"批量写入失败: {str(e)}"}

    # ============================================================
    # API: Shape .info.ini 位移编辑器
    # ============================================================
    def api_shape_info_list(self, category: str = "all") -> dict:
        """列出所有 .info.ini 位移文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        shape_dir = os.path.join(self.game_path, "Shape")
        if not os.path.exists(shape_dir):
            return {"success": False, "message": "未找到Shape目录"}
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
            return {"success": False, "message": "请先设置游戏目录"}
        full = os.path.join(self.game_path, "Shape", rel_path)
        if not os.path.exists(full):
            return {"success": False, "message": "文件不存在"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(full)
        parser = IniParser()
        parser.load(full)
        parser.set("Offset", "X", str(x))
        parser.set("Offset", "Y", str(y))
        parser.save(full)
        return {"success": True, "message": f"已保存 {rel_path}: X={x}, Y={y}"}

    def api_shape_info_delete(self, rel_path: str) -> dict:
        """删除指定的 .info.ini 文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        full = os.path.join(self.game_path, "Shape", rel_path)
        if not os.path.exists(full):
            return {"success": False, "message": "文件不存在"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(full)
        os.remove(full)
        return {"success": True, "message": f"已删除 {rel_path}"}

    def api_shape_info_clone(self, rel_path: str, new_name: str) -> dict:
        """克隆指定的 .info.ini 文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        full = os.path.join(self.game_path, "Shape", rel_path)
        if not os.path.exists(full):
            return {"success": False, "message": "源文件不存在"}
        new_path = os.path.join(os.path.dirname(full), new_name)
        if os.path.exists(new_path):
            return {"success": False, "message": f"目标文件 {new_name} 已存在"}
        import shutil
        shutil.copy2(full, new_path)
        return {"success": True, "message": f"已克隆为 {new_name}"}

    def api_shape_info_new(self, rel_path: str, category: str = "root") -> dict:
        """创建新的 .info.ini 文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        shape_dir = os.path.join(self.game_path, "Shape")
        if category and category != "root":
            dest_dir = os.path.join(shape_dir, category)
            os.makedirs(dest_dir, exist_ok=True)
        else:
            dest_dir = shape_dir
        full = os.path.join(dest_dir, rel_path)
        if os.path.exists(full):
            return {"success": False, "message": f"文件 {rel_path} 已存在"}
        parser = IniParser()
        parser.add_section("Offset")
        parser.set("Offset", "X", "0")
        parser.set("Offset", "Y", "0")
        parser.save(full)
        return {"success": True, "message": f"已创建 {rel_path}"}

    # ============================================================
    # API: CustomGen 自定义武将编辑
    # ============================================================
    def api_customgen_list(self) -> dict:
        """列出所有自定义武将"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        sav_path = os.path.join(self.game_path, "Save", "CustomGen.sav")
        if not os.path.exists(sav_path):
            return {"success": True, "generals": [], "count": 0, "message": "CustomGen.sav 不存在"}
        try:
            from core.save_editor import SaveEditor
            editor = SaveEditor(self.game_path)
            generals = editor.parse_customgen()
            return {"success": True, "generals": generals, "count": len(generals)}
        except Exception as e:
            return {"success": False, "message": f"解析失败: {str(e)}"}

    def api_customgen_get(self, index: int) -> dict:
        """获取单个自定义武将详情"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        sav_path = os.path.join(self.game_path, "Save", "CustomGen.sav")
        if not os.path.exists(sav_path):
            return {"success": False, "message": "CustomGen.sav 不存在"}
        try:
            from core.save_editor import SaveEditor
            editor = SaveEditor(self.game_path)
            general = editor.get_customgen_detail(index)
            if general:
                return {"success": True, "general": general}
            return {"success": False, "message": "索引超出范围"}
        except Exception as e:
            return {"success": False, "message": f"读取失败: {str(e)}"}

    def api_customgen_edit(self, index: int, field: str, value) -> dict:
        """编辑自定义武将字段"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        sav_path = os.path.join(self.game_path, "Save", "CustomGen.sav")
        if not os.path.exists(sav_path):
            return {"success": False, "message": "CustomGen.sav 不存在"}
        try:
            from core.save_editor import SaveEditor
            if self.backup_mgr:
                self.backup_mgr.backup_file(sav_path)
            editor = SaveEditor(self.game_path)
            result = editor.edit_customgen_field(index, field, value)
            return result
        except Exception as e:
            return {"success": False, "message": f"编辑失败: {str(e)}"}

    def api_customgen_add(self, name: str = "新武将") -> dict:
        """添加新的自定义武将"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            from core.save_editor import SaveEditor
            editor = SaveEditor(self.game_path)
            return editor.add_customgen(name)
        except Exception as e:
            return {"success": False, "message": f"添加失败: {str(e)}"}

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
            return {"success": False, "message": "请先附加到游戏进程 (memoryAttach)"}
        preset = self.MEMORY_PRESETS.get(preset_name)
        if not preset:
            return {"success": False, "message": f"未知预设: {preset_name}，可用: {list(self.MEMORY_PRESETS.keys())}"}
        return self.api_memory_read(preset["address"], preset["size"])

    # ============================================================
    # API: SHP 批量改名
    # ============================================================
    def api_shp_batch_rename(self, directory: str, prefix: str, start_id: int, digits: int = 4) -> dict:
        """批量重命名SHP文件: prefix_0001.shp, prefix_0002.shp..."""
        if not os.path.isdir(directory):
            return {"success": False, "message": "目录不存在"}
        shp_files = sorted([f for f in os.listdir(directory) if f.lower().endswith('.shp')])
        if not shp_files:
            return {"success": False, "message": "目录中没有SHP文件"}
        renamed = []
        for i, old_name in enumerate(shp_files):
            new_name = f"{prefix}_{start_id + i:0{digits}d}.shp"
            old_path = os.path.join(directory, old_name)
            new_path = os.path.join(directory, new_name)
            if old_path != new_path:
                if os.path.exists(new_path):
                    return {"success": False, "message": f"目标文件已存在: {new_name}"}
                os.rename(old_path, new_path)
                renamed.append({"from": old_name, "to": new_name})
        return {"success": True, "message": f"已重命名{len(renamed)}个文件", "renamed": renamed, "count": len(renamed)}

    # ============================================================
    # API: 城池连接关系
    # ============================================================
    def api_city_connections(self) -> dict:
        """获取所有城池连接关系（用于可视化）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        city_path = os.path.join(self.game_path, "Setting", "City.ini")
        citypos_path = os.path.join(self.game_path, "Setting", "CityPos.ini")
        if not os.path.exists(city_path):
            return {"success": False, "message": "未找到 City.ini"}
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
            return {"success": False, "message": "请先设置游戏目录"}
        city_path = os.path.join(self.game_path, "Setting", "City.ini")
        if not os.path.exists(city_path):
            return {"success": False, "message": "未找到 City.ini"}
        parser = IniParser()
        parser.load(city_path)
        data = []
        for s in parser.get_all_sections("CITY"):
            data.append(dict(s.entries))
        return {"success": True, "data": data, "count": len(data)}

    def api_save_city_connect(self, data: list) -> dict:
        """保存城池连接数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": True, "message": "城池连接已保存", "count": len(data)}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_load_idini(self) -> dict:
        """加载 WinTest/id.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        idini_path = os.path.join(self.game_path, "WinTest", "id.ini")
        if not os.path.exists(idini_path):
            return {"success": True, "data": [], "count": 0, "message": "id.ini 不存在"}
        try:
            parser = IniParser()
            parser.load(idini_path)
            data = []
            for s in parser.get_all_sections("ID"):
                e = dict(s.entries)
                data.append({"key": e.get("key", ""), "value": e.get("value", "")})
            return {"success": True, "data": data, "count": len(data)}
        except Exception as e:
            return {"success": False, "message": f"加载失败: {str(e)}"}

    def api_save_idini(self, data: list) -> dict:
        """保存 WinTest/id.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        idini_path = os.path.join(self.game_path, "WinTest", "id.ini")
        os.makedirs(os.path.dirname(idini_path), exist_ok=True)
        if self.backup_mgr:
            self.backup_mgr.backup_file(idini_path)
        try:
            parser = IniParser()
            for item in data:
                parser.add_section("ID", {"key": item.get("key", ""), "value": item.get("value", "")})
            parser.save(idini_path)
            return {"success": True, "message": f"已保存 {len(data)} 条"}
        except Exception as e:
            return {"success": False, "message": f"保存失败: {str(e)}"}

    # ============================================================
    # API: 脚本编辑器
    # ============================================================

    def api_list_scripts(self) -> dict:
        """列出 Script/ 目录下的剧本脚本文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": "请先设置游戏目录"}
        safe_name = os.path.basename(filename)
        if safe_name != filename or '..' in filename:
            return {"success": False, "message": "无效的文件名"}
        script_path = os.path.join(self.game_path, "Script", safe_name)
        if not os.path.exists(script_path):
            return {"success": False, "message": f"脚本文件不存在: {safe_name}"}
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
            return {"success": False, "message": f"读取失败: {e}"}

    def api_save_script(self, filename: str, content: str) -> dict:
        """保存脚本文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        safe_name = os.path.basename(filename)
        if safe_name != filename or '..' in filename:
            return {"success": False, "message": "无效的文件名"}
        script_path = os.path.join(self.game_path, "Script", safe_name)
        if not os.path.exists(script_path):
            return {"success": False, "message": f"脚本文件不存在: {safe_name}"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(script_path)
        try:
            with open(script_path, "w", encoding="big5", errors="replace") as f:
                f.write(content)
            return {"success": True, "message": f"已保存: {safe_name}"}
        except Exception as e:
            return {"success": False, "message": f"保存失败: {e}"}

    def api_new_script(self, filename: str) -> dict:
        """新建脚本文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        safe_name = os.path.basename(filename)
        if safe_name != filename or '..' in filename:
            return {"success": False, "message": "无效的文件名"}
        script_dir = os.path.join(self.game_path, "Script")
        os.makedirs(script_dir, exist_ok=True)
        script_path = os.path.join(script_dir, safe_name)
        if os.path.exists(script_path):
            return {"success": False, "message": f"文件已存在: {safe_name}"}
        try:
            with open(script_path, "w", encoding="big5", errors="replace") as f:
                f.write(f"; {safe_name}\n; 新建脚本\n")
            return {"success": True, "message": f"已创建: {safe_name}", "filename": safe_name}
        except Exception as e:
            return {"success": False, "message": f"创建失败: {e}"}

    def api_delete_script(self, filename: str) -> dict:
        """删除脚本文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        safe_name = os.path.basename(filename)
        if safe_name != filename or '..' in filename:
            return {"success": False, "message": "无效的文件名"}
        script_path = os.path.join(self.game_path, "Script", safe_name)
        if not os.path.exists(script_path):
            return {"success": False, "message": f"文件不存在: {safe_name}"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(script_path)
        try:
            os.remove(script_path)
            return {"success": True, "message": f"已删除: {safe_name}"}
        except Exception as e:
            return {"success": False, "message": f"删除失败: {e}"}

    def api_rename_script(self, old_name: str, new_name: str) -> dict:
        """重命名脚本文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        safe_old = os.path.basename(old_name)
        safe_new = os.path.basename(new_name)
        if safe_old != old_name or '..' in old_name or safe_new != new_name or '..' in new_name:
            return {"success": False, "message": "无效的文件名"}
        old_path = os.path.join(self.game_path, "Script", safe_old)
        new_path = os.path.join(self.game_path, "Script", safe_new)
        if not os.path.exists(old_path):
            return {"success": False, "message": f"文件不存在: {safe_old}"}
        if os.path.exists(new_path):
            return {"success": False, "message": f"目标文件已存在: {safe_new}"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(old_path)
        try:
            os.rename(old_path, new_path)
            return {"success": True, "message": f"已重命名: {safe_old} → {safe_new}", "old_name": safe_old, "new_name": safe_new}
        except Exception as e:
            return {"success": False, "message": f"重命名失败: {e}"}

    def api_global_search(self, query: str, search_type: str = "id", tables: List[str] = None) -> dict:
        """全局数据搜索：跨所有表按ID或值搜索"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if not query or not query.strip():
            return {"success": False, "message": "请输入搜索内容"}
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
            return {"success": False, "message": "请先设置游戏目录"}
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
                    analysis["things"] = {"error": str(e)}

        return {"success": True, "analysis": analysis}

    def api_mod_merge(self, mod_a: str, mod_b: str, output_name: str = None) -> dict:
        """合并两个MOD"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        mods_dir = os.path.join(WRITE_ROOT, "mods")
        mod_a_path = os.path.join(mods_dir, mod_a)
        mod_b_path = os.path.join(mods_dir, mod_b)
        if not os.path.exists(mod_a_path):
            return {"success": False, "message": f"MOD A 不存在: {mod_a}"}
        if not os.path.exists(mod_b_path):
            return {"success": False, "message": f"MOD B 不存在: {mod_b}"}

        output = output_name or f"{mod_a}+{mod_b}"
        output_path = os.path.join(mods_dir, output)
        if os.path.exists(output_path):
            return {"success": False, "message": f"输出MOD已存在: {output}"}

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
                except Exception:
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
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            r = self.api_load_histories()
            if not r.get("success"):
                return r
            data = r.get("data", [])
            if index < 0 or index >= len(data):
                return {"success": False, "message": f"索引无效: {index}"}
            deleted = data.pop(index)
            self.history_parser = None  # 清除缓存
            save_r = self.api_save_histories(data)
            if save_r.get("success"):
                return {"success": True, "message": f"已删除: {deleted.get('Name', f'事件#{index}')}"}
            return save_r
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_batch_cross_file(self, target_field: str, operation: str, value: str,
                               file_types: List[str] = None, filter_field: str = None,
                               filter_value: str = None, preview: bool = True) -> dict:
        """跨文件批量操作：对多个文件类型的同一字段进行批量修改"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

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
            return {"success": False, "message": "没有有效的文件类型"}

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
                    except Exception:
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
            return {"success": False, "message": "未知Schema类型"}

        schema_path = os.path.join(PROJECT_ROOT, "data", filename)
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                return {"success": True, "data": json.load(f)}
        except FileNotFoundError:
            return {"success": False, "message": f"Schema文件不存在: {filename}"}
        except json.JSONDecodeError as e:
            return {"success": False, "message": f"Schema文件解析失败: {e}"}

    # ============================================================
    # API: 存档编辑器（旧版 saveEditor 专用方法）
    # 注意: saveList/saveBackup/saveHexView 已由下方 saveMgr 统一提供
    # ============================================================

    def api_save_load(self, save_name: str) -> dict:
        """加载存档"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.load_save(save_name)

    def api_save_get_info(self) -> dict:
        """获取存档系统信息"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.get_save_info()

    def api_save_edit_customgen(self, save_name: str, generals: list) -> dict:
        """编辑CustomGen.sav中的自定义武将"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.edit_customgen(save_name, generals)

    def api_save_hex_search(self, save_name: str, pattern_hex: str, start_offset: int = 0) -> dict:
        """在存档中搜索十六进制模式"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.hex_search(save_name, pattern_hex, start_offset)

    def api_save_clone_general(self, save_name: str, source_index: int, clone_count: int = 1) -> dict:
        """克隆自定义武将"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.clone_custom_general(save_name, source_index, clone_count)

    # ============================================================
    # API: CustomLeaders.bytes 自建武将
    # ============================================================

    # reserved: 预留给未来功能，暂无前端调用
    def api_custom_leader_load(self) -> dict:
        """加载自建武将列表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.custom_leader.set_game_path(self.game_path)
        return self.custom_leader.load()

    def api_custom_leader_save(self, leaders: list) -> dict:
        """保存自建武将列表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.custom_leader.set_game_path(self.game_path)
        return self.custom_leader.save(leaders)

    # ============================================================
    # API: 存档管理
    # ============================================================

    def api_save_list(self) -> dict:
        """列出存档文件"""
        return self.save_manager.list_saves()

    def api_save_backup(self, save_name: str) -> dict:
        """备份存档"""
        return self.save_manager.backup_save(save_name)

    def api_save_restore(self, backup_path: str, save_name: str) -> dict:
        """还原存档"""
        return self.save_manager.restore_save(backup_path, save_name)

    def api_save_list_backups(self) -> dict:
        """列出备份"""
        return self.save_manager.list_backups()

    def api_save_delete_backup(self, backup_path: str) -> dict:
        """删除备份"""
        return self.save_manager.delete_backup(backup_path)

    def api_save_hex_view(self, save_name: str, offset: int = 0, length: int = 1024) -> dict:
        """十六进制查看"""
        return self.save_manager.hex_view(save_name, offset, length)

    def api_save_analyze(self, save_name: str) -> dict:
        """分析存档文件头"""
        return self.save_manager.analyze_save_header(save_name)

    # ============================================================
    # API: 存档解析器 (SaveParser) — 结构化编辑
    # ============================================================

    def api_save_parse_generals(self, save_name: str) -> dict:
        """解析存档中的武将数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        load_result = self.save_parser.load(save_path)
        if not load_result["success"]:
            return load_result
        generals = self.save_parser.find_generals()
        return {"success": True, "save_name": save_name, "generals": generals, "count": len(generals)}

    def api_save_edit_stat(self, save_name: str, offset: int, field: str, value: int) -> dict:
        """修改武将属性"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_general_stats(offset, field, value)
        if result["success"]:
            # 自动备份
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_edit_merit(self, save_name: str, offset: int, value: int) -> dict:
        """修改功勋值"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_merit(offset, value)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_edit_exp(self, save_name: str, offset: int, value: int) -> dict:
        """修改经验值"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_experience(offset, value)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_edit_soldier(self, save_name: str, offset: int, soldier_type: int, soldier_count: int) -> dict:
        """修改兵种和带兵数"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_soldier(offset, soldier_type, soldier_count)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_edit_weapon_exp(self, save_name: str, offset: int, weapon: str, value: int) -> dict:
        """修改武器熟练度"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_weapon_exp(offset, weapon, value)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_get_soldier_types(self) -> dict:
        """获取兵种代码表"""
        return {"success": True, "soldiers": [{"id": k, "name": v} for k, v in SaveParser.SOLDIER_TYPES.items()]}

    def api_save_get_structured_general(self, save_name: str, general_index: int) -> dict:
        """获取武将结构化数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        return self.save_parser.get_structured_general(general_index)

    def api_save_write_equipment(self, save_name: str, general_index: int, slot: str, item_id: int) -> dict:
        """修改武将装备"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_equipment(general_index, slot, item_id)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_write_skills(self, save_name: str, general_index: int, skill_type: str, slot: int, skill_id: int) -> dict:
        """修改武将技能"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_skills(general_index, skill_type, slot, skill_id)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    # reserved: 预留给未来功能，暂无前端调用
    def api_save_write_soldier_count(self, save_name: str, general_index: int, count: int) -> dict:
        """修改武将带兵数"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_soldier_count(general_index, count)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_write_formation(self, save_name: str, general_index: int, formation_id: int) -> dict:
        """修改武将阵型"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_formation(general_index, formation_id)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_get_weapon_names(self) -> dict:
        """获取武器名称字典"""
        return {"success": True, "weapons": [{"id": k, "name": v} for k, v in SaveParser.WEAPON_TYPES.items()]}

    def api_save_get_horse_names(self) -> dict:
        """获取坐骑名称字典"""
        return {"success": True, "horses": [{"id": k, "name": v} for k, v in SaveParser.HORSE_TYPES.items()]}

    def api_save_get_item_names(self) -> dict:
        """获取道具名称字典"""
        return {"success": True, "items": [{"id": k, "name": v} for k, v in SaveParser.ITEM_TYPES.items()]}

    def api_save_get_formation_names(self) -> dict:
        """获取阵型名称字典"""
        return {"success": True, "formations": [{"id": k, "name": v} for k, v in SaveParser.FORMATION_TYPES.items()]}

    # ============================================================
    # API: Script.so 分析器
    # ============================================================

    def api_scriptso_info(self) -> dict:
        """获取 Script.so 基本信息"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.get_script_so_info()

    def api_scriptso_strings(self) -> dict:
        """分析 Script.so 字符串"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.analyze_strings()

    def api_scriptso_hex_view(self, offset: int = 0, length: int = 512) -> dict:
        """十六进制查看 Script.so"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.hex_view(offset, length)

    def api_scriptso_hex_search(self, pattern_hex: str) -> dict:
        """在 Script.so 中搜索十六进制模式"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.hex_search(pattern_hex)

    def api_scriptso_list_files(self) -> dict:
        """列出 Script/ 目录文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        files = self.scriptso_analyzer.list_script_files()
        return {"success": True, "files": files, "count": len(files)}

    def api_scriptso_backup(self) -> dict:
        """备份 Script.so"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.backup_script_so()

    def api_scriptso_hex_write(self, offset: int, data_hex: str) -> dict:
        """十六进制写入 Script.so"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.hex_write(offset, data_hex)

    def api_scriptso_hex_patch(self, patches: list) -> dict:
        """批量十六进制补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.hex_patch(patches)

    def api_scriptso_sections(self) -> dict:
        """解析 Script.so ELF 段表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.parse_sections()

    def api_scriptso_symbols(self) -> dict:
        """解析 Script.so 符号表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.parse_symbols()

    def api_scriptso_string_replace(self, old_text: str, new_text: str) -> dict:
        """替换 Script.so 中的字符串"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.string_replace(old_text, new_text)

    def api_scriptso_get_patches(self) -> dict:
        """获取已知 Script.so 补丁列表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.get_known_patches()

    def api_scriptso_search_patch(self, patch_id: str) -> dict:
        """搜索已知补丁偏移"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.search_patch_offset(patch_id)

    def api_scriptso_apply_patch(self, patch_id: str, offset: int, new_value, value_type: str = None) -> dict:
        """应用已知补丁到指定偏移"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.apply_known_patch(patch_id, offset, new_value, value_type)

    def api_scriptso_community_patches(self) -> dict:
        """获取社区教程补丁列表"""
        return self.scriptso_analyzer.get_community_patches()

    def api_scriptso_apply_community_patch(self, patch_id: str) -> dict:
        """应用社区教程补丁（字符串替换）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.apply_community_patch(patch_id)

    def api_scriptso_disassemble(self, offset: int = None, length: int = 512) -> dict:
        """反汇编 Script.so"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.disassemble(offset, length)

    def api_scriptso_find_functions(self) -> dict:
        """检测 Script.so 函数边界"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.find_functions()

    def api_scriptso_disasm_func(self, address: int) -> dict:
        """反汇编单个函数"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.disassemble_function(address)

    def api_scriptso_find_xrefs(self, address: int) -> dict:
        """查找交叉引用"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.find_xrefs_to(address)

    def api_scriptso_instruction_patch(self, address: int, mnemonic: str, operands: str = "") -> dict:
        """指令级补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.instruction_patch(address, mnemonic, operands)

    # ============================================================
    # API: 兵种相克矩阵
    # ============================================================

    def api_matrix_load(self, soldiers: list) -> dict:
        """加载兵种相克矩阵"""
        return self.soldier_matrix.load_from_soldiers(soldiers)

    def api_matrix_get(self) -> dict:
        """获取矩阵数据"""
        return {
            "success": True,
            "matrix": self.soldier_matrix.get_matrix(),
            "summary": self.soldier_matrix.get_summary(),
            "analysis": self.soldier_matrix.analyze(),
        }

    def api_matrix_update(self, attacker: int, defender: int, value: int) -> dict:
        """更新单个克制值"""
        return self.soldier_matrix.update_cell(attacker, defender, value)

    def api_matrix_get_soldiers(self) -> dict:
        """获取更新后的兵种数据"""
        return {"success": True, "data": self.soldier_matrix.get_soldiers_data()}

    # ============================================================
    # API: MOD制作向导
    # ============================================================

    def api_wizard_templates(self) -> dict:
        """获取所有制作模板"""
        return {"success": True, "templates": self.mod_wizard.get_templates()}

    def api_wizard_start(self, template_id: str) -> dict:
        """开始一个模板"""
        return self.mod_wizard.start_template(template_id)

    def api_wizard_step(self, template_id: str, step: int) -> dict:
        """标记步骤完成"""
        return self.mod_wizard.mark_step_complete(template_id, step)

    def api_wizard_progress(self, template_id: str = None) -> dict:
        """获取进度"""
        return self.mod_wizard.get_progress(template_id)

    # reserved: 预留给未来功能，暂无前端调用
    def api_wizard_dependencies(self, file: str) -> dict:
        """获取文件依赖"""
        return self.mod_wizard.get_file_dependencies(file)

    def api_wizard_get_sample(self, template_id: str) -> dict:
        """获取MOD模板的示例数据"""
        sample = self.mod_wizard.get_sample(template_id)
        return {"success": True, "data": sample}

    def api_wizard_create_general(self, no: int, name: str, str_val: int = 70,
                                   int_val: int = 50, hp: float = 100, mp: int = 30,
                                   justice: int = 80, personality: int = 50, morale: int = 70,
                                   weapon: int = 0, horse: int = 0, formation: int = 0,
                                   sol_type1: int = 1, sol_type2: int = 0,
                                   face_id: int = 0, sex: int = 1, default_title: int = 1,
                                   gen_skills: list = None, army_skills: list = None,
                                   ag_skills: list = None, bf_magic: list = None, sf_magic: list = None,
                                   city1: str = "", city2: str = "", city3: str = "",
                                   city4: str = "", city5: str = "", city6: str = "",
                                   city7: str = "", city8: str = "", city9: str = "", city10: str = "",
                                   lord: int = 0) -> dict:
        """
        一键创建武将：自动联动 General01 + DefSkill + General02 + TermText
        """
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        if no <= 0:
            return {"success": False, "message": "武将编号必须大于0"}

        results = {}
        no_str = str(no)

        # 1. General01.ini
        try:
            path = os.path.join(self.game_path, "Setting", "General01.ini")
            if self.backup_mgr:
                self.backup_mgr.backup_file(path)
            parser = IniParser()
            if os.path.exists(path):
                parser.load(path)
            # 检查是否已存在
            for s in parser.get_all_sections("GENERAL"):
                if str(s.entries.get("No", "")) == no_str:
                    return {"success": False, "message": f"武将编号 {no} 已存在于 General01.ini"}
            section = parser.add_section("GENERAL")
            section.set("No", no_str)
            section.set("Name", name)
            section.set("Str", str(str_val))
            section.set("Int", str(int_val))
            section.set("HP", str(hp))
            section.set("MP", str(mp))
            section.set("Justice", str(justice))
            section.set("Personality", str(personality))
            section.set("Morale", str(morale))
            if weapon: section.set("Weapon", str(weapon))
            if horse: section.set("Horse", str(horse))
            if formation: section.set("Formation", str(formation))
            section.set("SolType1", str(sol_type1))
            if sol_type2: section.set("SolType2", str(sol_type2))
            if face_id: section.set("FaceID", str(face_id))
            section.set("Sex", str(sex))
            if default_title: section.set("DefaultTitle", str(default_title))
            section.set("IsUsed", "1")
            parser.save(path)
            results["general01"] = "OK"
        except Exception as e:
            results["general01_error"] = str(e)

        # 2. DefSkill.ini
        try:
            path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
            if self.backup_mgr:
                self.backup_mgr.backup_file(path)
            parser = IniParser()
            if os.path.exists(path):
                parser.load(path)
            for s in parser.get_all_sections("GenSkill"):
                if str(s.entries.get("No", "")) == no_str:
                    return {"success": False, "message": f"武将编号 {no} 已存在于 DefSkill.ini"}
            section = parser.add_section("GenSkill")
            section.set("No", no_str)
            section.set("Name", name)
            gs = gen_skills or []
            section.set("GenSkill", ",".join(str(x) for x in gs))
            as_ = army_skills or []
            section.set("ArmySkill", ",".join(str(x) for x in as_))
            ags = ag_skills or []
            section.set("ArmyGroupSkill", ",".join(str(x) for x in ags))
            bm = bf_magic or []
            section.set("BFMagic", ",".join(str(x) for x in bm))
            sm = sf_magic or []
            section.set("SFMagic", ",".join(str(x) for x in sm))
            parser.save(path)
            results["defskill"] = "OK"
        except Exception as e:
            results["defskill_error"] = str(e)

        # 3. General02.ini
        try:
            path = os.path.join(self.game_path, "Setting", "General02.ini")
            if self.backup_mgr:
                self.backup_mgr.backup_file(path)
            parser = IniParser()
            if os.path.exists(path):
                parser.load(path)
            for s in parser.get_all_sections("GENERAL"):
                if str(s.entries.get("No", "")) == no_str:
                    return {"success": False, "message": f"武将编号 {no} 已存在于 General02.ini"}
            section = parser.add_section("GENERAL")
            section.set("No", no_str)
            section.set("Name", name)
            city_map = {1: city1, 2: city2, 3: city3, 4: city4, 5: city5,
                        6: city6, 7: city7, 8: city8, 9: city9, 10: city10}
            for i in range(1, 11):
                val = city_map.get(i, "")
                if val:
                    section.set(f"City{i}", val)
                else:
                    section.set(f"City{i}", "")
            section.set("IsUsed", "1")
            if lord:
                section.set("RLord", str(lord))
            parser.save(path)
            results["general02"] = "OK"
        except Exception as e:
            results["general02_error"] = str(e)

        # 4. TermText.ini
        try:
            if self.term_text.is_loaded():
                string_id = 25000 + no
                self.term_text.allocate_new_id(name)
                results["termtext"] = f"String={string_id}"
            else:
                results["termtext_skip"] = "TermText未加载"
        except Exception as e:
            results["termtext_error"] = str(e)

        results["success"] = (results.get("general01") == "OK" and
                              results.get("defskill") == "OK" and
                              results.get("general02") == "OK")
        results["message"] = f"已为武将 {name} (No.{no}) 创建 General01 + DefSkill + General02 + TermText"
        return results

    def api_wizard_create_soldier(self, no: int, name: str, level: int = 1,
                                   upgrade: int = 0, hp: int = 50, atk: int = 10,
                                   def_val: int = 5, speed: int = 6, range_val: int = 1,
                                   cost: int = 100, troop_count: int = 1,
                                   hit_sol1: int = 0, hit_sol2: int = 0,
                                   obj_id: int = 0, is_used: int = 1) -> dict:
        """
        一键创建兵种：自动联动 Soldier.ini + TermText.ini + OBD模型
        """
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        if no <= 0:
            return {"success": False, "message": "兵种编号必须大于0"}

        results = {}
        no_str = str(no)

        # 1. Soldier.ini（使用正确的字段名）
        try:
            path = os.path.join(self.game_path, "Setting", "Soldier.ini")
            if self.backup_mgr:
                self.backup_mgr.backup_file(path)
            parser = IniParser()
            if os.path.exists(path):
                parser.load(path)
            for s in parser.get_all_sections("SOLDIER"):
                if str(s.entries.get("No", "")) == no_str:
                    return {"success": False, "message": f"兵种编号 {no} 已存在于 Soldier.ini"}
            section = parser.add_section("SOLDIER")
            section.set("No", no_str)
            section.set("Name", name)
            section.set("Rank", str(level))
            section.set("Upgrade", str(upgrade))
            section.set("Life", str(hp))
            section.set("BasePower", str(atk))
            section.set("AddPower", str(def_val))
            section.set("Speed", str(speed))
            section.set("DetectRangeMax", str(range_val))
            section.set("IsUsed", str(is_used))
            # 默认值
            section.set("Str", "1.0")
            section.set("Int", "1.0")
            section.set("Interval", "65")
            section.set("DetectRangeMin", "1")
            section.set("Height", "150")
            section.set("Type", "1")
            section.set("Color", "10")
            section.set("SizeX", "1")
            section.set("Sex", "0")
            section.set("DieMode", "0")
            section.set("OffsetZ", "0")
            section.set("Horse", "0")
            section.set("Weapon", "0")
            section.set("WeaponSpeed", "0")
            section.set("SuperHit", "0")
            section.set("Feature", "0")
            section.set("Special", "0")
            section.set("OrderNo", "0")
            section.set("Data01", "0")
            section.set("Data02", "0")
            section.set("Data03", "0")
            if hit_sol1: section.set("HitSol1", str(hit_sol1))
            if hit_sol2: section.set("HitSol2", str(hit_sol2))
            parser.save(path)
            results["soldier"] = "OK"
        except Exception as e:
            results["soldier_error"] = str(e)

        # 2. TermText.ini (兵种名=13000+No, 说明=13500+No)
        try:
            if self.term_text.is_loaded():
                self.term_text.allocate_new_id(name)
                results["termtext"] = f"String={13000 + no}"
            else:
                results["termtext_skip"] = "TermText未加载"
        except Exception as e:
            results["termtext_error"] = str(e)

        # 3. OBD 模型联动创建
        actual_obj_id = obj_id
        try:
            self.obd_parser.load("bfsoldier")
            seq = self.obd_parser.find_free_sequence()
            obj = OBDObject()
            obj.sequence = seq
            obj.name = name
            obj.space = (0, 0, 0)
            self.obd_parser.objects.append(obj)
            self.obd_parser.save("bfsoldier", self.obd_parser.objects)
            actual_obj_id = seq % 100
            results["obd"] = f"Sequence={seq}, ObjID={actual_obj_id}"
            # 回写 ObjID 到 Soldier.ini
            if results.get("soldier") == "OK":
                try:
                    parser2 = IniParser()
                    parser2.load(path)
                    for s in parser2.get_all_sections("SOLDIER"):
                        if str(s.entries.get("No", "")) == no_str:
                            s.set("ObjID", str(actual_obj_id))
                            break
                    parser2.save(path)
                except Exception:
                    pass
        except Exception as e:
            results["obd_error"] = str(e)
            if not actual_obj_id:
                actual_obj_id = no % 100

        # 如果传入了 obj_id 但 OBD 创建失败，回退
        if obj_id and not results.get("obd"):
            try:
                parser3 = IniParser()
                parser3.load(path)
                for s in parser3.get_all_sections("SOLDIER"):
                    if str(s.entries.get("No", "")) == no_str:
                        s.set("ObjID", str(obj_id))
                        break
                parser3.save(path)
            except Exception:
                pass
        elif actual_obj_id:
            try:
                parser3 = IniParser()
                parser3.load(path)
                for s in parser3.get_all_sections("SOLDIER"):
                    if str(s.entries.get("No", "")) == no_str:
                        s.set("ObjID", str(actual_obj_id))
                        break
                parser3.save(path)
            except Exception:
                pass

        results["success"] = results.get("soldier") == "OK"
        results["message"] = f"已为兵种 {name} (No.{no}) 创建 Soldier + TermText + OBD模型"
        if actual_obj_id:
            results["obj_id"] = actual_obj_id
        return results

    # ============================================================
    # API: 一键创建势力向导
    # ============================================================

    def api_wizard_create_nation(self, no: int, name: str, color: int = 0,
                                  lord: int = 0, advisor: int = 0, capital: int = 0,
                                  cities: str = "", generals: str = "",
                                  money: int = 10000, food: int = 50000,
                                  soldier: int = 10000, bgm: int = 8) -> dict:
        """
        一键创建势力：自动联动 Nation.ini + Color.ini + City.ini + City01-10.ini + General01.ini + TermText
        """
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if no <= 0:
            return {"success": False, "message": "势力编号必须大于0"}
        results = {}
        no_str = str(no)

        # 1. Nation.ini
        try:
            path = os.path.join(self.game_path, "Setting", "Nation.ini")
            if self.backup_mgr:
                self.backup_mgr.backup_file(path)
            parser = IniParser()
            if os.path.exists(path):
                parser.load(path)
            for s in parser.get_all_sections("NATION"):
                if str(s.entries.get("No", "")) == no_str:
                    return {"success": False, "message": f"势力编号 {no} 已存在"}
            section = parser.add_section("NATION")
            section.set("No", no_str)
            section.set("Name", name)
            section.set("Color", str(color))
            section.set("Lord", str(lord))
            section.set("Advisor", str(advisor))
            section.set("Capital", str(capital))
            section.set("Cities", cities)
            section.set("Generals", generals)
            section.set("Money", str(money))
            section.set("Food", str(food))
            section.set("Soldier", str(soldier))
            section.set("BGM", str(bgm))
            section.set("IsUsed", "1")
            parser.save(path)
            results["nation"] = "OK"
        except Exception as e:
            results["nation_error"] = str(e)

        # 2. Color.ini
        try:
            cpath = os.path.join(self.game_path, "Setting", "Color.ini")
            parser = IniParser()
            if os.path.exists(cpath):
                parser.load(cpath)
            section = parser.add_section("COLOR")
            section.set("No", no_str)
            section.set("R", "255")
            section.set("G", "0")
            section.set("B", "0")
            parser.save(cpath)
            results["color"] = "OK"
        except Exception as e:
            results["color_error"] = str(e)

        # 3. City.ini
        try:
            city_path = os.path.join(self.game_path, "Setting", "City.ini")
            parser = IniParser()
            if os.path.exists(city_path):
                parser.load(city_path)
            section = parser.add_section("CITY")
            section.set("No", str(capital or no))
            section.set("Name", name + "城")
            section.set("Owner", no_str)
            parser.save(city_path)
            results["city"] = "OK"
        except Exception as e:
            results["city_error"] = str(e)

        # 4. City01-10.ini (10个剧本)
        for i in range(1, 11):
            try:
                cpath = os.path.join(self.game_path, "Setting", f"City{i:02d}.ini")
                if os.path.exists(cpath):
                    parser = IniParser()
                    parser.load(cpath)
                    section = parser.add_section("CITY")
                    section.set("No", str(capital))
                    section.set("Owner", no_str)
                    section.set("Soldier", "500")
                    section.set("HP", "500")
                    parser.save(cpath)
            except Exception:
                pass
        results["city_periods"] = "OK"

        # 5. TermText
        try:
            if self.term_text.is_loaded():
                self.term_text.allocate_new_id(name)
                results["termtext"] = "OK"
        except Exception:
            results["termtext_skip"] = "TermText未加载"

        results["success"] = results.get("nation") == "OK"
        results["message"] = f"已为势力 {name} (No.{no}) 创建 Nation + Color + City + City01-10 + TermText"
        return results

    # ============================================================
    # API: 一键创建物品向导
    # ============================================================

    def api_wizard_create_item(self, no: int, name: str, item_type: int = 2,
                                price: int = 100, is_rare: int = 0,
                                icon_id: int = 0, script_no: int = 0,
                                level: int = 1, str_val: int = 0,
                                int_val: int = 0, hp_val: int = 0,
                                mp_val: int = 0, desc: str = "") -> dict:
        """
        一键创建物品：自动联动 Thing.ini + TermText(名称+描述)
        """
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if no <= 0:
            return {"success": False, "message": "物品编号必须大于0"}
        results = {}
        no_str = str(no)

        # 1. Thing.ini
        try:
            path = os.path.join(self.game_path, "Setting", "Thing.ini")
            if self.backup_mgr:
                self.backup_mgr.backup_file(path)
            parser = IniParser()
            if os.path.exists(path):
                parser.load(path)
            for s in parser.get_all_sections("THING"):
                if str(s.entries.get("No", "")) == no_str:
                    return {"success": False, "message": f"物品编号 {no} 已存在"}
            section = parser.add_section("THING")
            section.set("No", no_str)
            section.set("Name", name)
            section.set("Type", str(item_type))
            section.set("IconID", str(icon_id))
            section.set("Price", str(price))
            section.set("Level", str(level))
            section.set("IsRare", str(is_rare))
            section.set("Count", "1")
            section.set("ScriptNo", str(script_no))
            section.set("Str", str(str_val))
            section.set("Int", str(int_val))
            section.set("HP", str(hp_val))
            section.set("MP", str(mp_val))
            section.set("IsUsed", "1")
            parser.save(path)
            results["thing"] = "OK"
        except Exception as e:
            results["thing_error"] = str(e)

        # 2. TermText
        try:
            if self.term_text.is_loaded():
                self.term_text.set_item_name(no, name)
                item_desc = desc if desc else f"{name}的描述"
                self.term_text.set_item_desc(no, item_desc)
                results["termtext"] = "OK"
        except Exception:
            results["termtext_skip"] = "TermText未加载"

        results["success"] = results.get("thing") == "OK"
        results["message"] = f"已为物品 {name} (No.{no}) 创建 Thing + TermText"
        return results

    # ============================================================
    # API: OBD模型编辑
    # ============================================================

    def api_obd_load(self, obd_type: str = "bfsoldier") -> dict:
        """加载OBD模型数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            objects = self.obd_parser.load(obd_type)
            return {
                "success": True,
                "data": self.obd_parser.to_dict_list(),
                "count": len(objects),
                "sprite_types": self.obd_parser.get_sprite_types(),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_obd_save(self, obd_type: str, data: list) -> dict:
        """保存OBD模型数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            objects = [OBDObject.from_dict(d) for d in data]
            path = self.obd_parser.save(obd_type, objects)
            return {"success": True, "message": f"保存成功，共{len(objects)}个模型", "path": path}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_obd_new_object(self, obd_type: str = "bfsoldier") -> dict:
        """创建新OBD对象"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            self.obd_parser.load(obd_type)
            seq = self.obd_parser.find_free_sequence()
            obj = OBDObject()
            obj.sequence = seq
            obj.name = f"新模型_{seq}"
            return {"success": True, "data": obj.to_dict(), "sequence": seq}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_obd_delete(self, obd_type: str, sequence: int) -> dict:
        """删除指定OBD模型对象"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            self.obd_parser.load(obd_type)
            obj = self.obd_parser.find_by_sequence(sequence)
            if not obj:
                return {"success": False, "message": f"未找到 Sequence={sequence} 的模型"}
            if self.backup_mgr:
                file_path = os.path.join(self.game_path, "Setting", "OBD", self.obd_parser.OBD_FILES[obd_type])
                self.backup_mgr.backup_file(file_path)
            self.obd_parser.objects.remove(obj)
            self.obd_parser.save(obd_type)
            return {"success": True, "message": f"已删除模型 Sequence={sequence}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_list_obd_models(self, obd_type: str = "bfsoldier") -> dict:
        """列出指定OBD类型的所有模型（仅返回关键信息，供兵种编辑器使用）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            self.obd_parser.load(obd_type)
            models = []
            for obj in self.obd_parser.objects:
                models.append({
                    "sequence": obj.sequence,
                    "name": obj.name or "",
                    "obj_id": obj.sequence % 100,
                    "action_count": len(getattr(obj, 'sprites', {})),
                })
            return {"success": True, "data": models, "count": len(models)}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_obd_get_info(self) -> dict:
        """获取OBD格式信息"""
        return OBDParser.get_info()

    def api_obd_get_sprites(self, obd_type: str, sequence: int) -> dict:
        """获取指定OBD对象的Sprite帧列表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            self.obd_parser.load(obd_type)
            obj = self.obd_parser.find_by_sequence(sequence)
            if not obj:
                return {"success": False, "message": f"未找到Sequence={sequence}的对象"}
            return {
                "success": True,
                "sequence": sequence,
                "name": obj.name,
                "sprites": {k: v for k, v in obj.sprites.items()},
                "sprite_types": OBDObject.SPRITE_TYPES,
                "sprite_count": len(obj.sprites),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    # reserved: 预留给未来功能，暂无前端调用
    def api_obd_update_sprites(self, obd_type: str, sequence: int, sprites: dict) -> dict:
        """更新OBD对象的Sprite帧"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            self.obd_parser.load(obd_type)
            obj = self.obd_parser.find_by_sequence(sequence)
            if not obj:
                return {"success": False, "message": f"未找到Sequence={sequence}的对象"}
            obj.sprites = OrderedDict(sprites)
            self.obd_parser.save(obd_type, self.obd_parser.objects)
            return {"success": True, "message": f"已更新 {len(sprites)} 个Sprite帧"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_obd_copy_to(self, source_type: str, target_type: str, sequence: int) -> dict:
        """跨文件复制OBD模型（如 NPC→武将）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            self.obd_parser.load(source_type)
            src_obj = self.obd_parser.find_by_sequence(sequence)
            if not src_obj:
                return {"success": False, "message": f"源文件 {source_type} 中未找到 Sequence={sequence}"}
            # 在目标文件中分配新Sequence
            self.obd_parser.load(target_type)
            new_seq = self.obd_parser.find_free_sequence()
            new_obj = OBDObject()
            new_obj.sequence = new_seq
            new_obj.name = src_obj.name + "_导入"
            new_obj.space = src_obj.space
            new_obj.sprites = src_obj.sprites
            new_obj.extra = dict(src_obj.extra)
            self.obd_parser.objects.append(new_obj)
            self.obd_parser.save(target_type, self.obd_parser.objects)
            return {
                "success": True,
                "message": f"已从 {source_type} 复制到 {target_type}，新Sequence={new_seq}",
                "new_sequence": new_seq,
                "new_obj_id": new_obj.get_obj_id(),
                "data": new_obj.to_dict(),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_obd_preview_sprite_frame(self, obd_type: str, sequence: int, sprite_type: str, frame_index: int = 0) -> dict:
        """预览OBD中指定动作的指定帧图像（返回base64 PNG）"""
        if not HAS_PIL:
            return {"success": False, "message": "PIL库不可用"}
        if not self.game_path:
            return {"success": False, "message": "未配置游戏目录"}
        try:
            objects = self.obd_parser.load(obd_type)
            obj = None
            for o in objects:
                if o.sequence == sequence:
                    obj = o
                    break
            if not obj:
                return {"success": False, "message": f"未找到Sequence={sequence}的对象"}
            sprite_params = obj.get_sprite(sprite_type)
            if not sprite_params or frame_index >= len(sprite_params):
                return {"success": False, "message": f"动作{sprite_type}的第{frame_index}帧不存在"}
            # 帧参数格式: 文件名, #帧数, 文件名, #帧数, ...
            # 实际SHP文件名就是参数中的非#开头的条目
            frame_name = None
            frame_count = 0
            for param in sprite_params:
                if param.startswith('#'):
                    continue
                if param.startswith('@'):
                    continue
                if frame_count == frame_index:
                    frame_name = param
                    break
                frame_count += 1
            if not frame_name:
                # 尝试直接用第一个非#参数
                for param in sprite_params:
                    if not param.startswith('#') and not param.startswith('@'):
                        frame_name = param
                        break
            if not frame_name:
                return {"success": False, "message": "无法解析帧文件名"}
            # 查找帧文件: Shape/BFObj/BFSoldier/{sequence后两位}/{frame_name}.shp
            import os as _os
            obj_id = sequence % 100
            bfobj_dir = _os.path.join(self.game_path, "Shape", "BFObj", "BFSoldier", f"{obj_id:03d}")
            shp_path = _os.path.join(bfobj_dir, f"{frame_name}.shp")
            if not _os.path.exists(shp_path):
                # 尝试其他子目录
                for subdir in ["BFGen", "BFHorse", "BFWeapon", "BFSpec"]:
                    alt_dir = _os.path.join(self.game_path, "Shape", "BFObj", subdir, f"{obj_id:03d}")
                    alt_path = _os.path.join(alt_dir, f"{frame_name}.shp")
                    if _os.path.exists(alt_path):
                        shp_path = alt_path
                        break
            if not _os.path.exists(shp_path):
                return {"success": False, "message": f"帧文件不存在: {frame_name}.shp"}
            img = self.shp_converter._load_shp_file(shp_path)
            if img:
                buf = BytesIO()
                img.save(buf, "PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                return {"success": True, "image_base64": b64, "size": f"{img.width}x{img.height}", "frame_name": frame_name}
            return {"success": False, "message": "SHP解析失败"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_obd_list_sprite_frames(self, obd_type: str, sequence: int) -> dict:
        """列出OBD对象所有动作的帧列表"""
        objects = self.obd_parser.load(obd_type)
        obj = None
        for o in objects:
            if o.sequence == sequence:
                obj = o
                break
        if not obj:
            return {"success": False, "message": f"未找到Sequence={sequence}的对象"}
        result = {"success": True, "sequence": sequence, "name": obj.name, "actions": {}}
        for sprite_type, params in obj.sprites.items():
            frames = [p for p in params if not p.startswith('#') and not p.startswith('@')]
            result["actions"][sprite_type] = {
                "frame_count": len(frames),
                "frames": frames,
                "all_params": params,
            }
        return result

    # ============================================================
    # API: PCK资源管理
    # ============================================================

    def api_pck_detect(self) -> dict:
        """检测游戏目录PCK状态"""
        return self.pck_mgr.detect_game_state()

    def api_pck_list_files(self, pck_name: str = "Patch.pck") -> dict:
        """列出PCK包内文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        # 路径遍历防护：只允许安全的PCK文件名
        safe_name = os.path.basename(pck_name)
        if safe_name != pck_name or '..' in pck_name:
            return {"success": False, "message": "无效的PCK文件名"}
        pck_path = os.path.join(self.game_path, safe_name)
        if not os.path.exists(pck_path):
            return {"success": False, "message": f"未找到 {pck_name}"}
        files = self.pck_mgr.get_pck_files_list(pck_path)
        return {"success": True, "files": files, "count": len(files)}

    def api_pck_extract_all(self, pck_name: str = "Patch.pck") -> dict:
        """从PCK提取所有文件到游戏目录"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        safe_name = os.path.basename(pck_name)
        if safe_name != pck_name or '..' in pck_name:
            return {"success": False, "message": "无效的PCK文件名"}
        pck_path = os.path.join(self.game_path, safe_name)
        if not os.path.exists(pck_path):
            return {"success": False, "message": f"未找到 {pck_name}"}
        result = self.pck_mgr.extract_all_from_pck(pck_path, self.game_path)
        return result

    # reserved: 预留给未来功能，暂无前端调用
    def api_pck_extract_file(self, pck_name: str, internal_path: str) -> dict:
        """从PCK提取单个文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        safe_name = os.path.basename(pck_name)
        safe_internal = os.path.basename(internal_path)
        if safe_name != pck_name or '..' in pck_name or '..' in internal_path:
            return {"success": False, "message": "无效的文件路径"}
        pck_path = os.path.join(self.game_path, safe_name)
        output_path = os.path.join(self.game_path, safe_internal)
        ok = self.pck_mgr.extract_pck_file(pck_path, internal_path, output_path)
        return {"success": ok, "extracted_path": output_path if ok else None}

    # reserved: 预留给未来功能，暂无前端调用
    def api_pck_prepare_setting(self) -> dict:
        """准备Setting文件夹（自动检测+提取）"""
        return self.pck_mgr.prepare_setting_folder()

    def api_pck_get_setting_status(self) -> dict:
        """获取Setting文件夹详细状态"""
        return self.pck_mgr.get_setting_status()

    def api_pck_get_info(self) -> dict:
        """获取PCK格式信息"""
        return PckManager.get_info()

    def api_pck_repack(self) -> dict:
        """重新打包 Setting/ 为 Patch.pck"""
        return self.pck_mgr.repack_patch()

    # reserved: 预留给未来功能，暂无前端调用
    def api_shape_pck_extract(self, pck_name: str) -> dict:
        """从 Shape*.pck 提取 SHP 资源"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.pck_mgr.extract_shape_pck(pck_name)

    def api_shape_pck_extract_all(self) -> dict:
        """批量提取所有 Shape*.pck"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.pck_mgr.extract_all_shape_pcks()

    def api_shape_pck_repack(self, pck_name: str = "Shape00.pck") -> dict:
        """将 Shape/ 目录重新打包为 Shape*.pck"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.pck_mgr.repack_shape_pck(pck_name)

    # ============================================================
    # CSV 导入导出
    # ============================================================

    def api_csv_export(self, setting_name: str, output_path: str = None) -> dict:
        """根据 setting_name 导出 INI 数据为 CSV 文件

        Args:
            setting_name: Schema 名称，对应 _get_batch_schemas() 的 key（如 "General01.ini"）
            output_path: 可选的输出路径，默认保存到 Setting 目录下同名 .csv
        """
        try:
            # 1. 查找 Schema
            schemas = self._get_batch_schemas()
            schema = schemas.get(setting_name)
            if not schema:
                # 尝试通过 label 前缀匹配
                for key, s in schemas.items():
                    if s.get("label", "").startswith(setting_name):
                        schema = s
                        setting_name = key
                        break
            if not schema:
                return {"success": False, "message": f"未找到对应的 Schema: {setting_name}"}

            section_name = schema.get("section", "")
            ini_path = os.path.join(self.game_path, "Setting", setting_name)
            if not os.path.exists(ini_path):
                return {"success": False, "message": f"INI 文件不存在: {ini_path}"}

            # 2. 加载 INI 数据
            parser = IniParser()
            parser.load(ini_path)
            sections = parser.get_all_sections(section_name)
            data = [dict(s.entries) for s in sections]

            if not data:
                return {"success": False, "message": "没有数据可导出"}

            # 3. 确定输出路径
            if output_path is None:
                output_path = os.path.join(
                    os.path.dirname(ini_path),
                    f"{setting_name.replace('.ini', '')}.csv"
                )

            # 4. 导出 CSV（utf-8-sig BOM）
            import csv
            fields = schema.get("fields", [])
            if not fields and data:
                fields = list(data[0].keys())

            with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(data)

            return {"success": True, "message": f"成功导出 {len(data)} 条记录", "path": output_path}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_csv_import(self, setting_name: str, csv_path: str) -> dict:
        """根据 setting_name 从 CSV 文件导入数据到对应 INI 文件

        Args:
            setting_name: Schema 名称，对应 _get_batch_schemas() 的 key（如 "General01.ini"）
            csv_path: CSV 文件路径，第一行为表头
        """
        try:
            # 1. 查找 Schema
            schemas = self._get_batch_schemas()
            schema = schemas.get(setting_name)
            if not schema:
                # 尝试通过 label 前缀匹配
                for key, s in schemas.items():
                    if s.get("label", "").startswith(setting_name):
                        schema = s
                        setting_name = key
                        break
            if not schema:
                return {"success": False, "message": f"未找到对应的 Schema: {setting_name}"}

            section_name = schema.get("section", "")
            ini_path = os.path.join(self.game_path, "Setting", setting_name)
            if not os.path.exists(ini_path):
                return {"success": False, "message": f"INI 文件不存在: {ini_path}"}
            if not os.path.exists(csv_path):
                return {"success": False, "message": f"CSV 文件不存在: {csv_path}"}

            # 2. 备份目标文件
            if self.backup_mgr:
                self.backup_mgr.backup_file(ini_path)

            # 3. 读取 CSV 文件（支持 utf-8 和 gbk 编码）
            import csv
            rows = None
            for encoding in ["utf-8", "gbk"]:
                try:
                    with open(csv_path, "r", encoding=encoding) as f:
                        reader = csv.DictReader(f)
                        rows = list(reader)
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            if rows is None:
                return {"success": False, "message": "无法读取 CSV 文件或文件编码不支持"}

            if not rows:
                return {"success": False, "message": "CSV 文件为空或无有效数据行"}

            # 4. 将 CSV 数据转换为 INI entries 列表
            entries = []
            for row in rows:
                entry = dict(row)
                entries.append(entry)

            # 5. 使用 IniParser 写入
            parser = IniParser()
            parser.load(ini_path)
            parser.replace_sections(section_name, entries, "No")
            parser.save(ini_path)

            return {"success": True, "message": f"成功导入 {len(entries)} 条记录", "count": len(entries)}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_csv_confirm_import(self, data_type: str, file_path: str) -> dict:
        """确认导入 CSV 数据"""
        try:
            return self.csv_manager.import_csv(data_type, file_path)
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_csv_get_fields(self, data_type: str) -> dict:
        """获取指定数据类型的标准字段列表"""
        fields = self.csv_manager.get_field_map(data_type)
        if fields:
            return {"success": True, "data": fields}
        return {"success": False, "message": f"不支持的数据类型: {data_type}"}

    def api_encoding_scan(self) -> dict:
        """扫描 Setting/ 目录下所有 INI 文件编码"""
        return self.encoding_converter.batch_scan()

    def api_encoding_preview(self, file_path: str, target_encoding: str = "gbk") -> dict:
        """预览文件编码转换"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if '..' in file_path or os.path.isabs(file_path):
            return {"success": False, "message": "非法的文件路径"}
        full_path = os.path.join(self.game_path, "Setting", file_path)
        if not os.path.realpath(full_path).startswith(os.path.realpath(self.game_path)):
            return {"success": False, "message": "非法的文件路径"}
        return self.encoding_converter.preview_conversion(full_path, target_encoding)

    def api_encoding_convert_file(self, file_path: str, target_encoding: str = "gbk") -> dict:
        """转换单个文件编码"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if '..' in file_path or os.path.isabs(file_path):
            return {"success": False, "message": "非法的文件路径"}
        full_path = os.path.join(self.game_path, "Setting", file_path)
        if not os.path.realpath(full_path).startswith(os.path.realpath(self.game_path)):
            return {"success": False, "message": "非法的文件路径"}
        return self.encoding_converter.convert_file(full_path, target_encoding)

    def api_encoding_batch_convert(self, target_encoding: str = "gbk") -> dict:
        """批量转换所有 INI 文件编码"""
        return self.encoding_converter.batch_convert(target_encoding=target_encoding)

    # ============================================================
    # API: 剧情事件模板
    # ============================================================

    def api_event_templates(self) -> dict:
        """返回所有剧情事件模板"""
        return {"success": True, "templates": EVENT_TEMPLATES}

    def api_event_generate(self, class_type: str, params: dict) -> dict:
        """根据模板和参数生成 History.ini 片段"""
        if not class_type or class_type not in EVENT_TEMPLATES:
            return {"success": False, "message": "未知的 ClassType: " + str(class_type)}
        section = generate_event_section(class_type, params)
        return {"success": True, "section": section}

    def _get_data_by_type(self, data_type: str) -> list:
        """根据数据类型获取当前编辑器数据"""
        data_map = {
            "general": self._general_cache,
            "soldier": self._soldier_cache,
            "thing": self._thing_cache,
            "skill": self._skill_cache,
            "formation": self._formation_cache,
            "title": self._title_cache,
            "scenario": self._scenario_cache,
            "nation": self._nation_cache,
            "city": self._city_cache,
        }
        return data_map.get(data_type, [])

    # ============================================================
    # V3.12.0: MOD 打包分发系统 (mod_packager)
    # ============================================================

    def api_analyze_mod_structure(self, mod_path: str) -> dict:
        """分析 MOD 目录结构"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.mod_packager.analyze_mod(mod_path)

    def api_resolve_mod_deps(self, mod_path: str) -> dict:
        """解析 MOD 依赖关系"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.mod_packager.resolve_dependencies(mod_path, self.game_path)

    def api_generate_mod_installer(self, package_path: str, output_path: str = None) -> dict:
        """生成自解压安装器"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.mod_packager.generate_installer(package_path, output_path)

    def api_detect_mod_conflicts_v2(self, mod1_path: str, mod2_path: str) -> dict:
        """检测两个 MOD 之间的冲突"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.mod_packager.detect_conflicts(mod1_path, mod2_path)

    def api_resolve_mod_conflicts_v2(self, mod1_path: str, mod2_path: str, strategy: str = "auto") -> dict:
        """解决两个 MOD 之间的冲突"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.mod_packager.resolve_conflicts(mod1_path, mod2_path, strategy)

    def api_generate_mod_readme(self, mod_path: str, output_path: str = None) -> dict:
        """生成 MOD README 文档"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.mod_packager.generate_readme(mod_path, output_path)

    def api_version_bump_mod(self, mod_path: str, level: str = "patch") -> dict:
        """MOD 版本号升级"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.mod_packager.version_bump(mod_path, level)

    def api_create_mod_snapshot_v2(self, mod_path: str) -> dict:
        """创建 MOD 快照"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.mod_packager.create_snapshot(mod_path)

    def api_compare_mod_snapshots(self, snapshot1: str, snapshot2: str) -> dict:
        """对比两个 MOD 快照"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.mod_packager.compare_snapshots(snapshot1, snapshot2)

    # ============================================================
    # V3.12.0: TermText 智能编号分配器 (termtext_allocator)
    # ============================================================

    def api_allocate_termtext_id(self, content_type: str, preferred_text: str = None) -> dict:
        """分配 TermText 编号"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.termtext_allocator.allocate_id(content_type, preferred_text)

    def api_allocate_termtext_batch(self, requests) -> dict:
        """批量分配 TermText 编号"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.termtext_allocator.allocate_batch(requests)

    def api_detect_termtext_conflicts(self, termtext_path: str = None) -> dict:
        """检测 TermText 编号冲突"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.termtext_allocator.detect_conflicts(termtext_path)

    def api_resolve_termtext_conflicts(self, strategy: str = "auto") -> dict:
        """解决 TermText 编号冲突"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.termtext_allocator.resolve_conflicts(strategy)

    def api_migrate_termtext_ids(self, mapping) -> dict:
        """迁移 TermText 编号"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.termtext_allocator.migrate_ids(mapping)

    def api_get_termtext_segment_info(self, content_type: str) -> dict:
        """获取 TermText 编号段信息"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.termtext_allocator.get_segment_info(content_type)

    def api_get_termtext_all_segments(self) -> dict:
        """获取所有 TermText 编号段"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.termtext_allocator.get_all_segments()

    def api_smart_allocate_termtext(self, content_type: str, count: int, contiguous: bool = False) -> dict:
        """智能分配 TermText 编号"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.termtext_allocator.smart_allocate(content_type, count, contiguous)

    def api_cross_file_termtext_detect(self, file_paths) -> dict:
        """跨文件 TermText 编号检测"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.termtext_allocator.cross_file_detect(file_paths)

    def api_generate_termtext_report(self) -> dict:
        """生成 TermText 分配报告"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.termtext_allocator.generate_allocation_report()

    def api_auto_remediate_termtext(self) -> dict:
        """自动修复 TermText 编号问题"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.termtext_allocator.auto_remediate()

    # ============================================================
    # 启动
    # ============================================================

    def run(self):
        """启动应用"""
        try:
            import webview
        except ImportError:
            logger.error("请先安装 pywebview: pip install pywebview")
            sys.exit(1)

        # 创建API暴露对象
        api = _JsApi(self)
        html_path = os.path.join(PROJECT_ROOT, "web", "index.html")

        if not os.path.exists(html_path):
            logger.error(f"前端文件不存在: {html_path}")
            sys.exit(1)

        try:
            window = webview.create_window(
                title="San7ModMaker - 三国群英传7 MOD制作器 V3.13.0",
                url=html_path,
                js_api=api,
                width=1280,
                height=860,
                min_size=(1024, 700),
                resizable=True,
            )

            webview.start(debug=False)
        except Exception as e:
            logger.error(f"窗口启动失败: {e}")
            # 尝试弹窗报错
            try:
                import tkinter.messagebox as mb
                mb.showerror("启动失败", f"San7ModMaker 无法启动窗口:\n\n{str(e)[:200]}\n\n"
                           "请确认:\n"
                           "  Windows: 已安装 pythonnet 和 WebView2 Runtime\n"
                           "  Linux: 已安装 GTK3 或 Qt5")
            except Exception:
                pass
            sys.exit(1)


    # ============================================================
    # V3.12.0: INI 模板化数据生成引擎 (ini_template)
    # ============================================================

    def api_create_data_template(self, template_name: str, data_type: str, fields: list, rules: dict = None) -> dict:
        """创建数据模板"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.ini_template.create_template(template_name, data_type, fields, rules)

    def api_save_template(self, template: dict, filepath: str = None) -> dict:
        """保存模板到文件"""
        return self.ini_template.save_template(template, filepath)

    def api_load_template(self, filepath: str) -> dict:
        """从文件加载模板"""
        return self.ini_template.load_template(filepath)

    def api_list_templates(self) -> dict:
        """列出所有可用模板"""
        return self.ini_template.list_templates()

    def api_delete_template(self, template_name: str) -> dict:
        """删除模板"""
        return self.ini_template.delete_template(template_name)

    def api_generate_from_template(self, template_name: str, count: int, overrides: dict = None) -> dict:
        """从模板批量生成数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.ini_template.generate_from_template(template_name, count, overrides)

    def api_generate_cross_file(self, templates: list, relationships: list) -> dict:
        """跨文件批量生成"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.ini_template.generate_cross_file(templates, relationships)

    def api_batch_generate_templates(self, requests: list) -> dict:
        """批量生成请求"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.ini_template.batch_generate(requests)

    def api_validate_cross_file_data(self, generated_data: dict) -> dict:
        """验证跨文件数据一致性"""
        return self.ini_template.validate_cross_file(generated_data)

    def api_get_preset_templates(self) -> dict:
        """获取内置预设模板"""
        return self.ini_template.get_preset_templates()

    def api_merge_templates(self, base_template: str, overlay_templates: list) -> dict:
        """合并多个模板"""
        return self.ini_template.merge_templates(base_template, overlay_templates)

    def api_apply_template_overrides(self, data: dict, overrides: dict) -> dict:
        """应用字段覆盖"""
        return self.ini_template.apply_overrides(data, overrides)

    def api_transform_template_data(self, data: dict, transformations: list) -> dict:
        """数据转换"""
        return self.ini_template.transform_data(data, transformations)

    # ============================================================
    # V3.12.0: 引擎突破 — Script.so 深层逆向
    # ============================================================

    def api_build_scriptso_cfg(self, start_address: int = None, max_blocks: int = 500) -> dict:
        """构建 Script.so 控制流图"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.scriptso_analyzer.build_cfg(start_address, max_blocks)

    def api_find_scriptso_vtables(self) -> dict:
        """识别 Script.so 虚函数表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.scriptso_analyzer.find_vtables()

    def api_inject_scriptso_code_cave(self, cave_address: int, machine_code_hex: str, hook_address: int = None) -> dict:
        """向 Script.so Code Cave 注入代码"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            machine_code = bytes.fromhex(machine_code_hex.replace(" ", ""))
        except ValueError:
            return {"success": False, "message": "无效的十六进制机器码"}
        return self.scriptso_analyzer.inject_code_cave(cave_address, machine_code, hook_address)

    # ============================================================
    # V3.12.0: 引擎突破 — SG7-XX.sav 深度格式逆向
    # ============================================================

    def api_deep_parse_sg7_save(self, save_name: str = None) -> dict:
        """深度解析 SG7-XX.sav 场景存档"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.deep_parse_sg7_save(save_name)

    def api_edit_save_general(self, save_name: str, general_index: int, field_updates: dict) -> dict:
        """编辑场景存档中指定武将的属性"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.edit_save_general(save_name, general_index, field_updates)

    # ============================================================
    # V3.12.0: 引擎突破 — EXE Code Cave 注入
    # ============================================================

    def api_find_exe_code_cave(self, min_size: int = 64, section_end: bool = True) -> dict:
        """搜索 EXE Code Cave"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.exe_patcher.set_game_path(self.game_path)
        return self.exe_patcher.find_code_cave(min_size, section_end)

    def api_inject_exe_code_cave(self, cave_offset: int, machine_code_hex: str, hook_offset: int = None, backup: bool = True) -> dict:
        """向 EXE Code Cave 注入代码"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            machine_code = bytes.fromhex(machine_code_hex.replace(" ", ""))
        except ValueError:
            return {"success": False, "message": "无效的十六进制机器码"}
        self.exe_patcher.set_game_path(self.game_path)
        return self.exe_patcher.inject_code_cave(cave_offset, machine_code, hook_offset, backup)

    def api_build_jump_stub(self, from_offset: int, to_offset: int, stub_type: str = "jmp") -> dict:
        """构建跳转桩代码"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.exe_patcher.set_game_path(self.game_path)
        return self.exe_patcher.build_jump_stub(from_offset, to_offset, stub_type)

