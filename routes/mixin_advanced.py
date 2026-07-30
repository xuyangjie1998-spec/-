import os, json, re, shutil, base64, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional
from core.error_codes import ErrorCode, safe_error_message, error_response, success_response

from core.config import WRITE_ROOT, PROJECT_ROOT

from core.event_templates import EVENT_TEMPLATES, generate_event_section

logger = logging.getLogger('San7ModMaker')

__all__ = ['San7ModMakerAdvanced']

class San7ModMakerAdvanced:
    """MOD制作器 - 高级功能 (语言/图像/音频/沙盒/内存/地图/脚本)"""

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

