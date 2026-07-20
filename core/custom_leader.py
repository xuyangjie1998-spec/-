"""
CustomLeaders.bytes 解析器
- 读取/写入自建武将数据
- 格式: 每个武将固定长度记录，包含属性、名字等
"""

import os
import struct
from typing import Dict, List, Optional


class CustomLeader:
    """自建武将数据对象"""
    def __init__(self):
        self.index = 0
        self.name = ""
        self.str_val = 0
        self.int_val = 0
        self.hp = 0
        self.mp = 0
        self.sex = 0
        self.face_id = 0
        self.raw_data = b""


class CustomLeaderParser:
    """CustomLeaders.bytes 解析器"""

    # 每条记录大小（估算，实际可能因版本而异）
    RECORD_SIZE = 256

    def __init__(self, game_path: str = None):
        self.game_path = game_path
        self._file_path = None
        if game_path:
            self._file_path = os.path.join(game_path, "Save", "CoustomLeaders.bytes")

    def set_game_path(self, game_path: str):
        self.game_path = game_path
        self._file_path = os.path.join(game_path, "Save", "CoustomLeaders.bytes")

    def exists(self) -> bool:
        return self._file_path and os.path.exists(self._file_path)

    def load(self) -> dict:
        """加载自建武将列表"""
        if not self.exists():
            return {"success": False, "message": "CustomLeaders.bytes 不存在", "leaders": []}

        try:
            with open(self._file_path, "rb") as f:
                data = f.read()

            leaders = []
            # 尝试解析：每条记录以 name 开头，后面跟数值
            pos = 0
            idx = 0
            while pos + 4 < len(data):
                # 尝试读取名字（以 null 结尾的 ASCII/GBK 字符串）
                name_end = data.find(b'\x00', pos)
                if name_end < 0 or name_end - pos > 32:
                    # 可能是纯二进制数据，用固定偏移
                    break

                name = ""
                try:
                    name = data[pos:name_end].decode("gbk", errors="replace")
                except (UnicodeDecodeError, LookupError):
                    name = data[pos:name_end].decode("ascii", errors="replace")

                if not name or len(name) < 1:
                    pos += 1
                    continue

                # 跳过名字区域，读取后面的数值
                value_start = (name_end + 4) & ~3  # 对齐到4字节
                if value_start + 16 > len(data):
                    break

                leader = CustomLeader()
                leader.index = idx
                leader.name = name
                try:
                    leader.str_val = struct.unpack_from("<i", data, value_start)[0]
                    leader.int_val = struct.unpack_from("<i", data, value_start + 4)[0]
                    leader.hp = struct.unpack_from("<i", data, value_start + 8)[0]
                    leader.mp = struct.unpack_from("<i", data, value_start + 12)[0]
                except (struct.error, ValueError, IndexError):
                    pass

                leaders.append({
                    "index": leader.index,
                    "name": leader.name,
                    "str_val": leader.str_val,
                    "int_val": leader.int_val,
                    "hp": leader.hp,
                    "mp": leader.mp,
                    "offset": pos,
                })

                # 移动到下一条记录
                idx += 1
                pos = value_start + 64  # 跳过固定长度

            return {"success": True, "leaders": leaders, "count": len(leaders), "total_size": len(data)}

        except Exception as e:
            return {"success": False, "message": str(e), "leaders": []}

    def save(self, leaders: List[dict]) -> dict:
        """保存自建武将列表"""
        if not self._file_path:
            return {"success": False, "message": "未设置游戏目录"}

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self._file_path), exist_ok=True)

            # 读取原始数据
            original = b""
            if os.path.exists(self._file_path):
                with open(self._file_path, "rb") as f:
                    original = f.read()

            # 重建数据
            result = bytearray()
            for idx, leader in enumerate(leaders):
                name_bytes = leader.get("name", "").encode("gbk", errors="replace")
                name_bytes = name_bytes[:31] + b'\x00'  # 最多31字符+null

                # 对齐到4字节
                while len(name_bytes) % 4 != 0:
                    name_bytes += b'\x00'

                result.extend(name_bytes)
                result.extend(struct.pack("<i", leader.get("str_val", 0)))
                result.extend(struct.pack("<i", leader.get("int_val", 0)))
                result.extend(struct.pack("<i", leader.get("hp", 0)))
                result.extend(struct.pack("<i", leader.get("mp", 0)))

                # 补齐到固定长度
                while len(result) % 64 != 0:
                    result.append(0)

            with open(self._file_path, "wb") as f:
                f.write(bytes(result))

            return {"success": True, "message": f"保存成功，共{len(leaders)}个自建武将", "size": len(result)}

        except Exception as e:
            return {"success": False, "message": str(e)}