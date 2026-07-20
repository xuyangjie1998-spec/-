"""
存档修改器 (v2.0)
- 读取群7存档文件(.sav)格式
- 支持CustomGen.sav自定义武将文件（完整解析）
- 支持SG7-00.sav ~ SG7-09.sav 剧本存档（结构分析）
- 十六进制查看器
- 武将克隆/复制

群7存档格式说明:
- 存档文件是原始二进制格式，无压缩无加密
- CustomGen.sav: 自定义武将数据
  Magic: 4E F8 11 0C (4 bytes, LE)
  Count: 武将数量 (4 bytes, LE)
  Data: 武将列表（每个武将以 NWJ+编号 开头）
- SG7-XX.sav: 场景存档（格式未完整逆向）

参考:
- 3DM论坛 qweytr_1 (2025) CustomGen.sav逆向分析
- 游侠论坛 sdlt (2006) SG6存档格式
- S7Edit by cly1982 (2008) 功能反推
"""

import os
import struct
import time as _time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class SaveEditor:
    """
    群7存档编辑器 v2.0

    支持的存档文件:
    - CustomGen.sav: 自定义武将（最多512个）
    - SG7-XX.sav: 剧本存档
    """

    SAVE_EXT = ".sav"
    CUSTOM_GEN = "CustomGen.sav"
    SCENARIO_SAVE = "SG7-{:02d}.sav"

    # CustomGen.sav 已知魔数
    CUSTOMGEN_MAGIC = 0x0C11F84E  # 4E F8 11 0C in little-endian

    def __init__(self, game_path: str = None):
        self.game_path = game_path
        self.save_dir = os.path.join(game_path, "Save") if game_path else ""
        self._last_save_data: bytes = b""
        self._last_save_name: str = ""

    def set_game_path(self, game_path: str):
        self.game_path = game_path
        self.save_dir = os.path.join(game_path, "Save")

    def list_saves(self) -> List[dict]:
        """列出所有存档文件"""
        saves = []
        if not self.save_dir or not os.path.exists(self.save_dir):
            return saves

        for fname in sorted(os.listdir(self.save_dir)):
            if fname.lower().endswith(self.SAVE_EXT):
                fpath = os.path.join(self.save_dir, fname)
                size_kb = os.path.getsize(fpath) / 1024
                mtime = os.path.getmtime(fpath)
                dt = datetime.fromtimestamp(mtime)

                save_type = "unknown"
                if fname == self.CUSTOM_GEN:
                    save_type = "custom_general"
                elif fname.startswith("SG7-"):
                    save_type = "scenario"

                saves.append({
                    "name": fname,
                    "path": fpath,
                    "size_kb": round(size_kb, 1),
                    "size_bytes": os.path.getsize(fpath),
                    "modified": dt.strftime("%Y-%m-%d %H:%M"),
                    "type": save_type,
                })

        return saves

    def load_save(self, save_name: str) -> dict:
        """加载存档文件"""
        if not self.save_dir:
            return {"success": False, "message": "请先设置游戏目录"}

        save_path = os.path.join(self.save_dir, save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}

        try:
            with open(save_path, "rb") as f:
                data = f.read()

            self._last_save_data = data
            self._last_save_name = save_name

            info = self._analyze_save(data, save_name)

            return {
                "success": True,
                "name": save_name,
                "size": len(data),
                "info": info,
            }
        except Exception as e:
            return {"success": False, "message": f"读取失败: {e}"}

    def _analyze_save(self, data: bytes, save_name: str) -> dict:
        """分析存档结构"""
        info = {
            "magic": None,
            "magic_ascii": "",
            "version": None,
            "compressed": False,
            "decompressed_size": 0,
            "sections": [],
            "type": "unknown",
            "description": "",
        }

        if len(data) < 4:
            return info

        # 检测文件头
        magic = struct.unpack("<I", data[:4])[0]
        info["magic"] = "0x{:08X}".format(magic)
        try:
            magic_ascii = data[:4].decode("ascii", errors="replace")
            if all(32 <= b < 127 for b in data[:4]):
                info["magic_ascii"] = magic_ascii
        except (UnicodeDecodeError, IndexError):
            pass

        # 检测CustomGen.sav魔数
        if magic == self.CUSTOMGEN_MAGIC:
            info["is_customgen"] = True
        else:
            info["is_customgen"] = False

        # 特殊处理CustomGen.sav
        if save_name == self.CUSTOM_GEN:
            info["type"] = "custom_general"
            info["description"] = "自定义武将存档"
            result = self._parse_customgen_v2(data)
            info.update(result)
        elif save_name.startswith("SG7-"):
            info["type"] = "scenario"
            info["description"] = f"剧本存档 ({save_name})"
            scenario_info = self._analyze_scenario_save(data)
            info.update(scenario_info)

        return info

    # ============================================================
    # CustomGen.sav v2 解析 (基于社区逆向资料)
    # ============================================================

    def _parse_customgen_v2(self, data: bytes) -> dict:
        """解析CustomGen.sav v2 — 完整格式"""
        result = {
            "format_version": "v2",
            "max_generals": 20,
            "generals": [],
            "general_count": 0,
            "raw_structure": {},
        }

        if len(data) < 8:
            return result

        magic = struct.unpack("<I", data[:4])[0]
        result["raw_structure"]["magic"] = "0x{:08X}".format(magic)
        result["raw_structure"]["is_known_magic"] = (magic == self.CUSTOMGEN_MAGIC)

        count = struct.unpack("<I", data[4:8])[0]
        result["raw_structure"]["declared_count"] = count

        # 解析每个武将数据块
        generals = []
        pos = 8
        index = 0

        while pos < len(data) and index < 512:
            if pos + 1 > len(data):
                break
            id_len = data[pos]
            if id_len == 0 or id_len > 64:
                # 可能到达数据末尾
                break
            if pos + 1 + id_len > len(data):
                break

            general_id = data[pos + 1:pos + 1 + id_len]
            try:
                gid_str = general_id.decode("gbk", errors="replace")
            except (UnicodeDecodeError, AttributeError):
                gid_str = str(general_id)

            pos += 1 + id_len

            # 武将数据块（直到下一个 NWJ 标记或文件末尾）
            data_start = pos
            next_nwj = self._find_next_nwj(data, pos)
            if next_nwj >= 0:
                data_end = next_nwj
            else:
                data_end = len(data)

            raw_block = data[data_start:data_end]
            gen_info = self._parse_general_block(raw_block, gid_str, index)

            generals.append({
                "index": index,
                "id": gid_str,
                "offset": data_start,
                "size": len(raw_block),
                "used": True,
                **gen_info,
            })

            pos = data_end
            index += 1

        result["generals"] = generals
        result["general_count"] = len(generals)
        result["max_generals"] = max(20, len(generals))
        return result

    def _find_next_nwj(self, data: bytes, start: int) -> int:
        """查找下一个 NWJ 标记位置"""
        if start >= len(data):
            return -1
        for i in range(start, len(data) - 3):
            if data[i] == 0x03 and data[i + 1:i + 4] == b"NWJ":
                return i
            if data[i] == 0x04 and data[i + 1:i + 4] == b"NWJ":
                return i
        return -1

    def _parse_general_block(self, data: bytes, gid: str, index: int) -> dict:
        """解析武将数据块 — 提取可识别的字段"""
        info = {
            "name": "",
            "name_raw": "",
            "has_stats": False,
            "fields": {},
        }

        if len(data) < 4:
            return info

        # 尝试提取名称（通常在数据块开头附近，GBK编码）
        try:
            # 搜索可打印的GBK中文字符序列
            name_start = -1
            name_end = -1
            in_name = False
            for i in range(min(128, len(data))):
                b = data[i]
                if not in_name:
                    if b > 0x7F or (0x30 <= b <= 0x7A):
                        name_start = i
                        in_name = True
                else:
                    if b == 0x00 or (b < 0x20 and b != 0x00):
                        name_end = i
                        break
            if name_start >= 0:
                if name_end < 0:
                    name_end = min(name_start + 32, len(data))
                try:
                    name = data[name_start:name_end].replace(b"\x00", b"").decode("gbk", errors="replace")
                    if name and len(name) <= 16 and not name.startswith("NWJ"):
                        info["name"] = name
                        info["name_raw"] = data[name_start:name_end].hex()
                except (UnicodeDecodeError, AttributeError):
                    pass
        except (IndexError, UnicodeDecodeError):
            pass

        # 提取统计信息
        info["fields"]["block_size"] = len(data)
        info["fields"]["hex_preview"] = data[:64].hex()

        return info

    # ============================================================
    # SG7-XX.sav 场景存档分析
    # ============================================================

    def _analyze_scenario_save(self, data: bytes) -> dict:
        """分析场景存档结构"""
        info = {
            "sections": [],
            "detected_structures": [],
        }

        if len(data) < 16:
            return info

        # 检测已知的标记码
        markers = [
            (b"Mark\x00", "物品标记"),
            (b"SG7", "存档标记"),
            (b"\x00" * 16, "零填充区"),
        ]

        for marker, desc in markers:
            positions = self._find_all(data, marker)
            if positions:
                for p in positions[:5]:
                    info["detected_structures"].append({
                        "type": desc,
                        "offset": p,
                        "offset_hex": "0x{:X}".format(p),
                        "marker": marker.hex(),
                    })

        # 尝试检测文本段
        text_regions = self._detect_text_regions(data)
        if text_regions:
            info["text_regions"] = text_regions[:10]

        # 检测可能的整数数组
        value_regions = self._detect_value_regions(data)
        if value_regions:
            info["value_regions"] = value_regions[:10]

        return info

    def _find_all(self, data: bytes, pattern: bytes) -> List[int]:
        """查找所有匹配位置"""
        positions = []
        start = 0
        while True:
            pos = data.find(pattern, start)
            if pos < 0:
                break
            positions.append(pos)
            start = pos + 1
        return positions

    def _detect_text_regions(self, data: bytes) -> List[dict]:
        """检测文本区域"""
        regions = []
        min_run = 4
        i = 0
        while i < len(data):
            if data[i] > 0x7F:
                run_start = i
                while i < len(data) and data[i] > 0x7F:
                    i += 1
                run_len = i - run_start
                if run_len >= min_run:
                    try:
                        text = data[run_start:i].decode("gbk", errors="replace")
                        if any('\u4e00' <= c <= '\u9fff' for c in text):
                            regions.append({
                                "offset": run_start,
                                "offset_hex": "0x{:X}".format(run_start),
                                "length": run_len,
                                "preview": text[:30],
                            })
                    except (UnicodeDecodeError, IndexError):
                        pass
            else:
                i += 1
        return regions

    def _detect_value_regions(self, data: bytes) -> List[dict]:
        """检测连续的小整数区域"""
        regions = []
        i = 0
        min_run = 10
        while i < len(data) - 3:
            val = struct.unpack("<I", data[i:i + 4])[0]
            if 0 < val < 10000:
                run_start = i
                count = 0
                while i < len(data) - 3 and count < 50:
                    v = struct.unpack("<I", data[i:i + 4])[0]
                    if 0 < v < 10000:
                        count += 1
                        i += 4
                    else:
                        break
                if count >= min_run:
                    samples = [struct.unpack("<I", data[run_start + j * 4:run_start + j * 4 + 4])[0]
                               for j in range(min(5, count))]
                    regions.append({
                        "offset": run_start,
                        "offset_hex": "0x{:X}".format(run_start),
                        "count": count,
                        "sample_values": samples,
                    })
            else:
                i += 1
        return regions

    # ============================================================
    # 十六进制查看器
    # ============================================================

    def hex_view(self, save_name: str, offset: int = 0, length: int = 512) -> dict:
        """返回指定范围的十六进制数据"""
        if not self.save_dir:
            return {"success": False, "message": "请先设置游戏目录"}

        save_path = os.path.join(self.save_dir, save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}

        try:
            with open(save_path, "rb") as f:
                f.seek(offset)
                chunk = f.read(length)
        except (IOError, OSError) as e:
            return {"success": False, "message": f"读取失败: {e}"}

        if not chunk:
            return {"success": False, "message": "偏移超出文件范围"}

        # 生成十六进制行
        lines = []
        ascii_lines = []
        for i in range(0, len(chunk), 16):
            row = chunk[i:i + 16]
            hex_part = " ".join("{:02X}".format(b) for b in row)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
            lines.append("{:08X}  {:48}  |{}|".format(offset + i, hex_part, ascii_part))
            ascii_lines.append(ascii_part)

        return {
            "success": True,
            "offset": offset,
            "length": len(chunk),
            "total_size": os.path.getsize(save_path),
            "hex_lines": lines,
            "raw_hex": chunk.hex(),
        }

    def hex_search(self, save_name: str, pattern_hex: str, start_offset: int = 0) -> dict:
        """在存档中搜索十六进制模式"""
        if not self.save_dir:
            return {"success": False, "message": "请先设置游戏目录"}

        save_path = os.path.join(self.save_dir, save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}

        try:
            pattern = bytes.fromhex(pattern_hex.replace(" ", ""))
        except ValueError:
            return {"success": False, "message": "无效的十六进制模式"}

        try:
            with open(save_path, "rb") as f:
                f.seek(start_offset)
                data = f.read()
        except (IOError, OSError) as e:
            return {"success": False, "message": f"读取失败: {e}"}

        positions = self._find_all(data, pattern)
        return {
            "success": True,
            "pattern": pattern_hex,
            "match_count": len(positions),
            "positions": ["0x{:X}".format(start_offset + p) for p in positions[:50]],
        }

    # ============================================================
    # CustomGen.sav 编辑
    # ============================================================

    def edit_customgen(self, save_name: str, generals: list) -> dict:
        """编辑CustomGen.sav中的自定义武将"""
        if not self.save_dir:
            return {"success": False, "message": "请先设置游戏目录"}

        save_path = os.path.join(self.save_dir, save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}

        try:
            with open(save_path, "rb") as f:
                data = bytearray(f.read())

            # 备份
            self._make_backup(save_path)

            # 修改武将数据
            for gen in generals:
                idx = gen.get("index", 0)
                offset = gen.get("offset", 8)
                if "name" in gen and gen["name"]:
                    # 尝试在数据块中写入名称
                    name_bytes = gen["name"].encode("gbk", errors="replace")[:31]
                    name_bytes += b'\x00' * (32 - len(name_bytes))
                    if offset + 36 <= len(data):
                        # 尝试在数据块中查找并替换名称
                        for search_off in range(offset, min(offset + 128, len(data))):
                            if data[search_off:search_off + 2] == name_bytes[:2]:
                                data[search_off:search_off + len(name_bytes)] = name_bytes
                                break

            with open(save_path, "wb") as f:
                f.write(data)

            return {"success": True, "message": f"已更新 {len(generals)} 个武将"}
        except Exception as e:
            return {"success": False, "message": f"编辑失败: {str(e)}"}

    def clone_custom_general(self, save_name: str, source_index: int, clone_count: int = 1) -> dict:
        """克隆自定义武将"""
        if not self.save_dir:
            return {"success": False, "message": "请先设置游戏目录"}

        save_path = os.path.join(self.save_dir, save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}

        try:
            with open(save_path, "rb") as f:
                data = bytearray(f.read())

            # 解析现有武将
            if len(data) < 8:
                return {"success": False, "message": "存档格式无效"}

            magic = data[:4]
            count_bytes = data[4:8]
            current_count = struct.unpack("<I", count_bytes)[0]

            # 找到源武将数据
            generals = self._find_general_blocks(data)
            if source_index >= len(generals):
                return {"success": False, "message": f"武将索引 {source_index} 超出范围 (共 {len(generals)} 个)"}

            source_block = generals[source_index]
            source_data = data[source_block["data_start"]:source_block["data_end"]]

            # 克隆
            self._make_backup(save_path)
            new_count = current_count + clone_count
            data[4:8] = struct.pack("<I", new_count)

            for c in range(clone_count):
                new_id = "NWJ{}".format(current_count + c)
                new_id_bytes = new_id.encode("gbk")
                new_id_len = bytes([len(new_id_bytes)])
                clone_entry = new_id_len + new_id_bytes + source_data
                data.extend(clone_entry)

            with open(save_path, "wb") as f:
                f.write(data)

            return {
                "success": True,
                "message": f"成功克隆 {clone_count} 个武将，当前共 {new_count} 个",
                "new_count": new_count,
            }
        except Exception as e:
            return {"success": False, "message": f"克隆失败: {str(e)}"}

    def _find_general_blocks(self, data: bytes) -> List[dict]:
        """查找所有武将数据块"""
        blocks = []
        pos = 8
        while pos < len(data):
            if pos + 1 > len(data):
                break
            id_len = data[pos]
            if id_len == 0 or id_len > 64:
                break
            if pos + 1 + id_len > len(data):
                break
            general_id = data[pos + 1:pos + 1 + id_len]
            pos += 1 + id_len
            data_start = pos
            next_nwj = self._find_next_nwj(data, pos)
            data_end = next_nwj if next_nwj >= 0 else len(data)

            blocks.append({
                "id": general_id,
                "data_start": data_start,
                "data_end": data_end,
                "size": data_end - data_start,
            })
            pos = data_end

        return blocks

    # ============================================================
    # 存档操作
    # ============================================================

    def save_save(self, save_name: str, data: bytes) -> dict:
        """保存存档文件（带备份）"""
        if not self.save_dir:
            return {"success": False, "message": "请先设置游戏目录"}

        save_path = os.path.join(self.save_dir, save_name)

        if os.path.exists(save_path):
            self._make_backup(save_path)

        try:
            os.makedirs(self.save_dir, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(data)
            return {"success": True, "message": f"存档 {save_name} 已保存"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def backup_save(self, save_name: str) -> dict:
        """创建存档备份"""
        if not self.save_dir:
            return {"success": False, "message": "请先设置游戏目录"}

        save_path = os.path.join(self.save_dir, save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}

        backup_path = self._make_backup(save_path)
        return {"success": True, "message": f"备份已创建: {os.path.basename(backup_path)}"}

    def restore_backup(self, save_name: str, backup_name: str) -> dict:
        """从备份恢复存档"""
        backup_path = os.path.join(self.save_dir, backup_name)
        save_path = os.path.join(self.save_dir, save_name)

        if not os.path.exists(backup_path):
            return {"success": False, "message": "备份文件不存在"}

        try:
            with open(backup_path, "rb") as src:
                with open(save_path, "wb") as dst:
                    dst.write(src.read())
            return {"success": True, "message": f"已从 {backup_name} 恢复"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_save_info(self) -> dict:
        """获取存档系统信息"""
        saves = self.list_saves()
        return {
            "save_dir": self.save_dir,
            "exists": os.path.exists(self.save_dir) if self.save_dir else False,
            "count": len(saves),
            "saves": saves,
            "custom_gen_exists": os.path.exists(
                os.path.join(self.save_dir, self.CUSTOM_GEN)
            ) if self.save_dir else False,
        }

    def _make_backup(self, save_path: str) -> str:
        """创建备份文件，返回备份路径"""
        ts = int(_time.time())
        backup_path = save_path + ".{}.bak".format(ts)
        try:
            with open(save_path, "rb") as src:
                with open(backup_path, "wb") as dst:
                    dst.write(src.read())
        except (IOError, OSError) as e:
            logger.warning(f"备份失败: {e}")
        return backup_path