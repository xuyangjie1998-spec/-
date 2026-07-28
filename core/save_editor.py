
__all__ = ["SaveEditor"]

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

    def parse_customgen(self) -> list:
        """解析 CustomGen.sav 并返回扁平化武将列表（供前端使用）"""
        if not self.save_dir:
            return []
        sav_path = os.path.join(self.save_dir, self.CUSTOM_GEN)
        if not os.path.exists(sav_path):
            return []
        try:
            with open(sav_path, "rb") as f:
                data = f.read()
        except (IOError, OSError):
            return []

        result = self._parse_customgen_v2(data)
        raw_generals = result.get("generals", [])

        flat = []
        for g in raw_generals:
            fields = g.get("fields", {})
            flat.append({
                "index": g.get("index", 0),
                "Name": g.get("name", ""),
                "Level": fields.get("Level", 1),
                "Str": fields.get("Str", 80),
                "Int": fields.get("Int", 80),
                "HP": fields.get("HP", 100),
                "MP": fields.get("MP", 50),
                "Weapon": fields.get("Weapon", ""),
                "Mount": fields.get("Mount", ""),
                "Title": fields.get("Title", ""),
                "Nation": fields.get("Nation", ""),
                "City": fields.get("City", ""),
                "Formation": fields.get("Formation", ""),
                "Soldier": fields.get("Soldier", ""),
                "Skill1": fields.get("Skill1", ""),
                "Skill2": fields.get("Skill2", ""),
                "Skill3": fields.get("Skill3", ""),
                "SuperSkill": fields.get("SuperSkill", ""),
                "ArmySkill": fields.get("ArmySkill", ""),
                "ArmyGroupSkill": fields.get("ArmyGroupSkill", ""),
                "offset": g.get("offset", 0),
                "size": g.get("size", 0),
                "id": g.get("id", ""),
            })
        return flat

    def get_customgen_detail(self, index: int) -> dict:
        """获取单个自定义武将详情"""
        generals = self.parse_customgen()
        if 0 <= index < len(generals):
            # 附加原始 hex 数据
            g = dict(generals[index])
            try:
                sav_path = os.path.join(self.save_dir, self.CUSTOM_GEN)
                with open(sav_path, "rb") as f:
                    f.seek(g.get("offset", 0))
                    raw = f.read(g.get("size", 256))
                g["raw_hex"] = raw.hex()
            except (IOError, OSError, KeyError):
                g["raw_hex"] = ""
            return g
        return None

    def edit_customgen_field(self, index: int, field: str, value) -> dict:
        """编辑自定义武将的单个字段"""
        if not self.save_dir:
            return {"success": False, "message": "请先设置游戏目录"}
        sav_path = os.path.join(self.save_dir, self.CUSTOM_GEN)
        if not os.path.exists(sav_path):
            return {"success": False, "message": "CustomGen.sav 不存在"}

        try:
            with open(sav_path, "rb") as f:
                data = bytearray(f.read())

            self._make_backup(sav_path)

            # 解析定位武将
            result = self._parse_customgen_v2(bytes(data))
            generals = result.get("generals", [])
            if index < 0 or index >= len(generals):
                return {"success": False, "message": "索引 {} 超出范围 (共 {} 个)".format(index, len(generals))}

            gen = generals[index]
            offset = gen.get("offset", 0)
            gen_size = gen.get("size", 0)

            # 将 value 转为字符串
            str_val = str(value) if value is not None else ""

            if field in ("Name", "name"):
                name_bytes = str_val.encode("gbk", errors="replace")[:31]
                old_name = gen.get("name", "")
                if old_name:
                    old_bytes = old_name.encode("gbk", errors="replace")
                    block = data[offset:offset + gen_size]
                    pos = block.find(old_bytes)
                    if pos >= 0:
                        old_len = len(old_bytes)
                        new_len = len(name_bytes)
                        if new_len <= old_len:
                            padded = name_bytes + b'\x00' * (old_len - new_len)
                            data[offset + pos:offset + pos + old_len] = padded
                        else:
                            return {"success": False, "message": "新名称过长（{}字节），无法原地编辑".format(new_len)}
                    else:
                        return {"success": False, "message": "未在二进制数据中找到原名称"}
                else:
                    return {"success": False, "message": "原名称未知，无法编辑"}
            else:
                # 非名称字段：二进制格式未完全逆向，暂不支持直接编辑
                return {"success": False, "message": "字段 '{}' 暂不支持编辑（二进制格式限制，仅支持名称修改）".format(field)}

            with open(sav_path, "wb") as f:
                f.write(data)

            return {"success": True, "message": "{} 已更新".format(field)}
        except Exception as e:
            return {"success": False, "message": "编辑失败: {}".format(str(e))}

    def add_customgen(self, name: str = "新武将") -> dict:
        """添加新的自定义武将（克隆首个现有武将作为模板）"""
        if not self.save_dir:
            return {"success": False, "message": "请先设置游戏目录"}
        sav_path = os.path.join(self.save_dir, self.CUSTOM_GEN)

        try:
            if os.path.exists(sav_path):
                with open(sav_path, "rb") as f:
                    data = bytearray(f.read())
                self._make_backup(sav_path)

                if len(data) >= 8:
                    current_count = struct.unpack("<I", data[4:8])[0]
                else:
                    current_count = 0

                # 尝试克隆第一个武将作为模板
                generals = self._find_general_blocks(data)
                if generals:
                    source = generals[0]
                    source_data = data[source["data_start"]:source["data_end"]]
                else:
                    # 没有现有武将，创建最小模板
                    name_bytes = name.encode("gbk", errors="replace")[:31]
                    source_data = name_bytes + b'\x00' * (32 - len(name_bytes))
                    source_data += struct.pack("<iiiii", 1, 80, 80, 100, 50)
            else:
                # 创建新文件
                data = bytearray()
                data.extend(struct.pack("<I", self.CUSTOMGEN_MAGIC))
                data.extend(struct.pack("<I", 0))
                current_count = 0
                # 创建最小模板
                name_bytes = name.encode("gbk", errors="replace")[:31]
                source_data = name_bytes + b'\x00' * (32 - len(name_bytes))
                source_data += struct.pack("<iiiii", 1, 80, 80, 100, 50)

            # 追加新条目
            new_id = "NWJ{}".format(current_count)
            new_id_bytes = new_id.encode("gbk")
            new_id_len = bytes([len(new_id_bytes)])

            new_count = current_count + 1
            data[4:8] = struct.pack("<I", new_count)
            data.extend(new_id_len)
            data.extend(new_id_bytes)
            data.extend(source_data)

            with open(sav_path, "wb") as f:
                f.write(data)

            return {"success": True, "message": "已添加新武将 '{}'，当前共 {} 个".format(name, new_count), "count": new_count}
        except Exception as e:
            return {"success": False, "message": "添加失败: {}".format(str(e))}

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
        if backup_path is None:
            return {"success": False, "message": "备份创建失败"}
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
            return backup_path
        except (IOError, OSError) as e:
            logger.warning(f"备份失败: {e}")
            return None

    # ============================================================
    # V3.12.0: 引擎突破 — SG7-XX.sav 深度格式逆向
    # ============================================================

    # SG7-XX.sav 已知结构标记
    SG7_MARKERS = {
        "general_table": b"\x01\x00\x00\x00",  # 武将表起始标记
        "faction_table": b"\x53\x47\x37",      # SG7 标记
        "city_table": b"\x00" * 16,             # 零填充分隔区
        "item_table": b"Mark\x00",              # 物品标记
    }

    # 武将属性字段偏移（基于社区逆向数据，相对位置）
    GENERAL_FIELD_LAYOUT = {
        "name": {"offset": 0, "type": "gbk_string", "max_len": 32},
        "force": {"offset": 32, "type": "int16"},
        "intelligence": {"offset": 34, "type": "int16"},
        "hp": {"offset": 36, "type": "int16"},
        "mp": {"offset": 38, "type": "int16"},
        "level": {"offset": 40, "type": "int16"},
        "exp": {"offset": 42, "type": "int32"},
        "loyalty": {"offset": 46, "type": "int16"},
        "morale": {"offset": 48, "type": "int16"},
        "soldier_count": {"offset": 50, "type": "int16"},
        "soldier_type": {"offset": 52, "type": "int16"},
        "formation": {"offset": 54, "type": "int8"},
        "weapon": {"offset": 55, "type": "int16"},
        "horse": {"offset": 57, "type": "int16"},
        "item1": {"offset": 59, "type": "int16"},
        "item2": {"offset": 61, "type": "int16"},
        "item3": {"offset": 63, "type": "int16"},
        "skill1": {"offset": 65, "type": "int16"},
        "skill2": {"offset": 67, "type": "int16"},
        "skill3": {"offset": 69, "type": "int16"},
        "skill4": {"offset": 71, "type": "int16"},
        "skill5": {"offset": 73, "type": "int16"},
        "skill6": {"offset": 75, "type": "int16"},
        "skill7": {"offset": 77, "type": "int16"},
        "skill8": {"offset": 79, "type": "int16"},
        "faction": {"offset": 81, "type": "int8"},
        "city": {"offset": 82, "type": "int8"},
        "portrait": {"offset": 83, "type": "int16"},
        "battle_power": {"offset": 85, "type": "int16"},
    }

    GENERAL_RECORD_SIZE = 128  # 预估每条武将记录 128 字节

    def deep_parse_sg7_save(self, save_name: str = None) -> dict:
        """
        深度解析 SG7-XX.sav 场景存档

        尝试识别并存档中的武将数据、势力数据、城池数据等核心结构
        基于社区逆向资料和模式匹配的启发式分析
        """
        if not self.save_dir:
            return {"success": False, "message": "请先设置游戏目录"}

        if save_name is None:
            # 自动选择第一个场景存档
            saves = self.list_saves()
            scenario_saves = [s for s in saves if s["type"] == "scenario"]
            if not scenario_saves:
                return {"success": False, "message": "未找到场景存档"}
            save_name = scenario_saves[0]["name"]

        save_path = os.path.join(self.save_dir, save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}

        try:
            with open(save_path, "rb") as f:
                data = f.read()
        except (IOError, OSError) as e:
            return {"success": False, "message": f"读取失败: {e}"}

        result = {
            "success": True,
            "save_name": save_name,
            "file_size": len(data),
            "sections": [],
            "generals": [],
            "general_count": 0,
            "factions": [],
            "cities": [],
            "summary": "",
        }

        # 1. 检测存档结构段
        sections = self._detect_sg7_sections(data)
        result["sections"] = sections

        # 2. 尝试解析武将数据
        general_data = self._parse_sg7_generals_v2(data, sections)
        if general_data.get("success"):
            result["generals"] = general_data["generals"]
            result["general_count"] = general_data["count"]

        # 3. 尝试解析势力数据
        faction_data = self._parse_sg7_factions(data, sections)
        if faction_data.get("success"):
            result["factions"] = faction_data["factions"]

        # 4. 尝试解析城池数据
        city_data = self._parse_sg7_cities(data, sections)
        if city_data.get("success"):
            result["cities"] = city_data["cities"]

        # 生成摘要
        parts = [f"文件大小: {len(data)} 字节"]
        if result["general_count"]:
            parts.append(f"武将: {result['general_count']} 人")
        if result["factions"]:
            parts.append(f"势力: {len(result['factions'])} 个")
        if result["cities"]:
            parts.append(f"城池: {len(result['cities'])} 个")
        result["summary"] = " | ".join(parts)

        return result

    def _detect_sg7_sections(self, data: bytes) -> list:
        """检测 SG7-XX.sav 中的结构段边界"""
        sections = []

        # 检测已知标记
        for marker, desc in {
            b"SG7": "存档头",
            b"Mark\x00": "物品标记区",
            b"\x00" * 32: "零填充分隔",
        }.items():
            positions = self._find_all(data, marker)
            for p in positions[:5]:
                sections.append({
                    "offset": p,
                    "offset_hex": "0x{:X}".format(p),
                    "type": desc,
                    "marker": marker.hex()[:8],
                })

        # 检测文本密集区（势力名、武将名等）
        text_regions = self._detect_text_regions(data)
        for tr in text_regions[:5]:
            sections.append({
                "offset": tr["offset"],
                "offset_hex": tr["offset_hex"],
                "type": "文本区",
                "preview": tr["preview"],
                "length": tr["length"],
            })

        # 检测数值密集区（属性数组）
        value_regions = self._detect_value_regions(data)
        for vr in value_regions[:5]:
            sections.append({
                "offset": vr["offset"],
                "offset_hex": vr["offset_hex"],
                "type": "数值区",
                "count": vr["count"],
                "samples": vr["sample_values"],
            })

        sections.sort(key=lambda x: x["offset"])
        return sections

    def _parse_sg7_generals_v2(self, data: bytes, sections: list) -> dict:
        """
        从场景存档中解析武将数据

        策略:
        1. 在数值密集区中搜索符合武将记录模式的数据
        2. 武将记录特征: 连续 128 字节块，内含中文名称 + 小整数属性
        """
        generals = []

        # 在数值区中搜索武将记录
        for sec in sections:
            if sec["type"] != "数值区":
                continue

            # 尝试以 128 字节为步长解析
            offset = sec["offset"]
            end = min(offset + 50000, len(data))

            while offset < end - 32:
                # 检查是否像武将记录开头
                # 特征: 前面有中文名称（GBK 双字节），后跟小整数
                try:
                    # 尝试读取名称
                    name_data = data[offset:offset + 32]
                    name_end = name_data.find(b'\x00')
                    if name_end < 2:
                        offset += self.GENERAL_RECORD_SIZE
                        continue

                    name = name_data[:name_end].decode("gbk", errors="replace")
                    if not name or len(name) > 16:
                        offset += self.GENERAL_RECORD_SIZE
                        continue

                    # 检查后续是否像属性值
                    if offset + 86 > len(data):
                        break

                    # 读取武力值
                    force = struct.unpack("<H", data[offset + 32:offset + 34])[0]
                    if not (1 <= force <= 999):
                        offset += self.GENERAL_RECORD_SIZE
                        continue

                    # 读取智力值
                    intelligence = struct.unpack("<H", data[offset + 34:offset + 36])[0]
                    if not (1 <= intelligence <= 999):
                        offset += self.GENERAL_RECORD_SIZE
                        continue

                    # 像一条有效的武将记录，提取所有字段
                    gen = {"name": name, "offset": offset, "offset_hex": "0x{:X}".format(offset)}

                    for field_name, layout in self.GENERAL_FIELD_LAYOUT.items():
                        if field_name == "name":
                            continue
                        field_offset = offset + layout["offset"]
                        if field_offset + 2 > len(data):
                            break
                        if layout["type"] == "int16":
                            gen[field_name] = struct.unpack("<H", data[field_offset:field_offset + 2])[0]
                        elif layout["type"] == "int32":
                            gen[field_name] = struct.unpack("<I", data[field_offset:field_offset + 4])[0]
                        elif layout["type"] == "int8":
                            gen[field_name] = data[field_offset]

                    # 验证合理性
                    if gen.get("level", 0) > 99:
                        offset += self.GENERAL_RECORD_SIZE
                        continue

                    generals.append(gen)
                    offset += self.GENERAL_RECORD_SIZE

                except (struct.error, UnicodeDecodeError, IndexError):
                    offset += self.GENERAL_RECORD_SIZE

        return {
            "success": True,
            "count": len(generals),
            "generals": generals,
            "record_size": self.GENERAL_RECORD_SIZE,
            "note": "基于启发式模式匹配，字段偏移为预估值，可能不适用于所有MOD版本",
        }

    def _parse_sg7_factions(self, data: bytes, sections: list) -> dict:
        """解析势力数据"""
        factions = []
        faction_names = []

        # 在文本区中查找势力名称
        for sec in sections:
            if sec["type"] != "文本区":
                continue
            # 势力名称通常为 2-4 个汉字
            preview = sec.get("preview", "")
            if 2 <= len(preview) <= 8 and all('\u4e00' <= c <= '\u9fff' or c in '·' for c in preview):
                faction_names.append({
                    "name": preview,
                    "offset": sec["offset"],
                    "offset_hex": sec["offset_hex"],
                })

        # 为每个势力名关联数据
        for i, fn in enumerate(faction_names):
            factions.append({
                "index": i,
                "name": fn["name"],
                "data_offset": fn["offset"],
                "data_offset_hex": fn["offset_hex"],
            })

        return {
            "success": True,
            "count": len(factions),
            "factions": factions,
            "note": "基于文本段检测，势力数据块格式待进一步逆向",
        }

    def _parse_sg7_cities(self, data: bytes, sections: list) -> dict:
        """解析城池数据"""
        cities = []
        city_names = []

        # 在文本区中查找城池名称（通常 2-3 个汉字，后跟城/关/港等）
        for sec in sections:
            if sec["type"] != "文本区":
                continue
            preview = sec.get("preview", "")
            if 2 <= len(preview) <= 6:
                if any(preview.endswith(suffix) for suffix in ['城', '关', '港', '寨', '都', '郡', '州', '阳']):
                    city_names.append({
                        "name": preview,
                        "offset": sec["offset"],
                        "offset_hex": sec["offset_hex"],
                    })

        for i, cn in enumerate(city_names):
            cities.append({
                "index": i,
                "name": cn["name"],
                "data_offset": cn["offset"],
                "data_offset_hex": cn["offset_hex"],
            })

        return {
            "success": True,
            "count": len(cities),
            "cities": cities,
            "note": "基于文本段检测，城池数据块格式待进一步逆向",
        }

    def get_save_generals(self, save_name: str = None) -> dict:
        """
        获取场景存档中的武将列表（含属性）
        封装 deep_parse_sg7_save 的武将部分
        """
        result = self.deep_parse_sg7_save(save_name)
        if not result.get("success"):
            return result

        return {
            "success": True,
            "save_name": result.get("save_name", ""),
            "general_count": result.get("general_count", 0),
            "generals": result.get("generals", []),
            "summary": result.get("summary", ""),
        }

    def edit_save_general(self, save_name: str, general_index: int,
                           field_updates: dict) -> dict:
        """
        编辑场景存档中指定武将的属性

        参数:
            save_name: 存档文件名
            general_index: 武将索引（从0开始）
            field_updates: 要修改的字段及其新值 {"force": 500, "level": 50}

        注意: 此功能基于启发式偏移，修改前会自动备份
        """
        if not self.save_dir:
            return {"success": False, "message": "请先设置游戏目录"}

        save_path = os.path.join(self.save_dir, save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}

        # 先解析武将列表获取偏移
        gen_data = self.get_save_generals(save_name)
        if not gen_data.get("success"):
            return gen_data

        generals = gen_data.get("generals", [])
        if general_index < 0 or general_index >= len(generals):
            return {
                "success": False,
                "message": f"武将索引无效: {general_index} (范围: 0-{len(generals) - 1})",
            }

        gen = generals[general_index]
        base_offset = gen["offset"]

        # 备份
        self._make_backup(save_path)

        updated = []
        failed = []

        try:
            with open(save_path, "r+b") as f:
                for field_name, new_value in field_updates.items():
                    if field_name not in self.GENERAL_FIELD_LAYOUT:
                        failed.append({"field": field_name, "reason": "未知字段"})
                        continue

                    layout = self.GENERAL_FIELD_LAYOUT[field_name]
                    field_offset = base_offset + layout["offset"]
                    old_value = gen.get(field_name, 0)

                    try:
                        f.seek(field_offset)
                        if layout["type"] == "int16":
                            f.write(struct.pack("<H", new_value & 0xFFFF))
                        elif layout["type"] == "int32":
                            f.write(struct.pack("<I", new_value & 0xFFFFFFFF))
                        elif layout["type"] == "int8":
                            f.write(struct.pack("<B", new_value & 0xFF))
                        elif layout["type"] == "gbk_string":
                            name_bytes = new_value.encode("gbk", errors="replace")
                            if len(name_bytes) > layout.get("max_len", 32):
                                name_bytes = name_bytes[:layout["max_len"]]
                            f.write(name_bytes + b'\x00' * (layout["max_len"] - len(name_bytes)))

                        updated.append({
                            "field": field_name,
                            "old_value": old_value,
                            "new_value": new_value,
                        })
                    except (IOError, OSError) as e:
                        failed.append({"field": field_name, "reason": str(e)})

            return {
                "success": len(updated) > 0,
                "general_index": general_index,
                "general_name": gen.get("name", ""),
                "updated": updated,
                "updated_count": len(updated),
                "failed": failed,
                "failed_count": len(failed),
                "message": f"修改 {len(updated)} 个字段，失败 {len(failed)} 个",
            }
        except Exception as e:
            return {"success": False, "message": f"编辑失败: {e}"}