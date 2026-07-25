"""
游戏资源文件格式深度逆向 (Resource Format Reverse Engineering)
提供 SHP/PCK/OBD/MPC 等游戏资源格式的完整格式规范、二进制解析、完整性校验和跨格式映射。

引擎突破 8: 深度逆向工程游戏资源文件格式
"""

import os
import struct
import json
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from io import BytesIO
import hashlib


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class FileFormatSpec:
    """文件格式规范"""
    name: str
    extension: str
    magic: bytes
    magic_offset: int = 0
    description: str = ""
    header_size: int = 0
    header_fields: List[Dict] = field(default_factory=list)
    is_archive: bool = False
    contains_compressed: bool = False
    endian: str = "little"


@dataclass
class FormatField:
    """格式字段定义"""
    name: str
    offset: int
    size: int
    type: str  # uint8, uint16, uint32, int32, float32, bytes, string, struct
    description: str = ""
    endian: str = "little"
    enum_values: Dict[int, str] = field(default_factory=dict)


@dataclass
class BinaryStructure:
    """二进制结构解析结果"""
    name: str
    fields: Dict[str, Any] = field(default_factory=dict)
    raw_bytes: bytes = b""
    offset: int = 0
    size: int = 0


@dataclass
class FileValidationResult:
    """文件校验结果"""
    file_path: str
    is_valid: bool
    format_type: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# 格式规范定义
# ============================================================

# SHP 格式规范 (群7 SHP 图片格式)
SHP_FORMAT = FileFormatSpec(
    name="SHP Image",
    extension=".shp",
    magic=b"",
    description="群7 SHP 图片格式，支持多帧动画和调色板",
    header_size=8,
    header_fields=[
        {"name": "frame_count", "offset": 0, "size": 4, "type": "uint32", "description": "帧数"},
        {"name": "header_size", "offset": 4, "size": 4, "type": "uint32", "description": "头部大小"},
    ],
    endian="little"
)

# PCK 格式规范 (群7 资源包格式)
PCK_FORMAT = FileFormatSpec(
    name="PCK Archive",
    extension=".pck",
    magic=b"PCK\x00",
    magic_offset=0,
    description="群7 资源包格式，支持压缩存储",
    header_size=16,
    header_fields=[
        {"name": "magic", "offset": 0, "size": 4, "type": "bytes", "description": "魔数 PCK\\x00"},
        {"name": "file_count", "offset": 4, "size": 4, "type": "uint32", "description": "文件数量"},
        {"name": "header_size_field", "offset": 8, "size": 4, "type": "uint32", "description": "文件表大小"},
        {"name": "flags", "offset": 12, "size": 4, "type": "uint32", "description": "标志位"},
    ],
    is_archive=True,
    contains_compressed=True,
    endian="little"
)

# OBD 格式规范 (群7 模型定义格式)
OBD_FORMAT = FileFormatSpec(
    name="OBD Model Definition",
    extension=".obd",
    magic=b"",
    description="群7 模型定义格式，定义角色/兵种模型的Sprite序列和动画",
    header_size=0,
    endian="little"
)

# MPC 格式规范 (群7 地形/地图格式)
MPC_FORMAT = FileFormatSpec(
    name="MPC Terrain",
    extension=".mpc",
    magic=b"",
    description="群7 地形/地图格式，存储地图瓦片和地形数据",
    header_size=0,
    endian="little"
)

# INI 格式规范
INI_FORMAT = FileFormatSpec(
    name="INI Configuration",
    extension=".ini",
    magic=b"[",
    description="群7 配置文件格式，使用 INI 节/键/值结构",
    endian="little"
)

# Script.so 格式规范
SCRIPTSO_FORMAT = FileFormatSpec(
    name="Script.so (ELF Shared Object)",
    extension=".so",
    magic=b"\x7fELF",
    magic_offset=0,
    description="群7 游戏逻辑脚本库，ELF 格式的共享对象文件",
    header_size=52,
    header_fields=[
        {"name": "ei_magic", "offset": 0, "size": 4, "type": "bytes", "description": "ELF魔数 0x7F E L F"},
        {"name": "ei_class", "offset": 4, "size": 1, "type": "uint8", "description": "32/64位"},
        {"name": "ei_data", "offset": 5, "size": 1, "type": "uint8", "description": "字节序"},
        {"name": "ei_version", "offset": 6, "size": 1, "type": "uint8", "description": "ELF版本"},
        {"name": "e_type", "offset": 16, "size": 2, "type": "uint16", "description": "文件类型"},
        {"name": "e_machine", "offset": 18, "size": 2, "type": "uint16", "description": "目标架构"},
        {"name": "e_entry", "offset": 24, "size": 4, "type": "uint32", "description": "入口点"},
        {"name": "e_phoff", "offset": 28, "size": 4, "type": "uint32", "description": "程序头偏移"},
        {"name": "e_shoff", "offset": 32, "size": 4, "type": "uint32", "description": "节头偏移"},
    ],
    endian="little"
)

# 所有已知格式
KNOWN_FORMATS = {
    "shp": SHP_FORMAT,
    "pck": PCK_FORMAT,
    "obd": OBD_FORMAT,
    "mpc": MPC_FORMAT,
    "ini": INI_FORMAT,
    "scriptso": SCRIPTSO_FORMAT,
}

# 魔数到格式的映射
MAGIC_TO_FORMAT = {
    b"\x7fELF": "scriptso",
    b"PCK\x00": "pck",
    b"[": "ini",
}


# ============================================================
# 格式检测器
# ============================================================

class FormatDetector:
    """文件格式自动检测器"""

    @staticmethod
    def detect(file_path: str) -> Optional[str]:
        """检测文件格式"""
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
        except Exception:
            return None

        # 魔数检测
        for magic, fmt_name in MAGIC_TO_FORMAT.items():
            if header[:len(magic)] == magic:
                return fmt_name

        # 扩展名检测
        ext = os.path.splitext(file_path)[1].lower()
        ext_map = {
            ".shp": "shp",
            ".pck": "pck",
            ".obd": "obd",
            ".mpc": "mpc",
            ".ini": "ini",
            ".so": "scriptso",
            ".txt": "ini",
            ".csv": "csv",
            ".raw": "raw",
            ".bmp": "bmp",
        }
        if ext in ext_map:
            return ext_map[ext]

        # 启发式检测
        if header[:4] == b"RIFF":
            return "riff"
        if header[:2] == b"BM":
            return "bmp"
        if header[:2] == b"\xff\xd8":
            return "jpeg"
        if header[:4] == b"\x89PNG":
            return "png"
        if header[:2] == b"PK":
            return "zip"
        if header[:3] == b"GIF":
            return "gif"

        return "unknown"

    @staticmethod
    def detect_from_bytes(data: bytes) -> Optional[str]:
        """从字节数据检测格式"""
        if not data:
            return None

        for magic, fmt_name in MAGIC_TO_FORMAT.items():
            if data[:len(magic)] == magic:
                return fmt_name

        return "unknown"


# ============================================================
# SHP 格式深度解析
# ============================================================

class SHPReverser:
    """SHP 格式深度逆向"""

    def __init__(self):
        self._data = b""
        self._file_path = ""
        self._frame_count = 0
        self._header_size = 0
        self._frame_offsets: List[int] = []
        self._frame_sizes: List[int] = []
        self._palette: Optional[bytes] = None
        self._width = 0
        self._height = 0
        self._parsed = False

    def load(self, file_path: str) -> dict:
        """加载 SHP 文件"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        self._file_path = file_path
        try:
            with open(file_path, "rb") as f:
                self._data = f.read()
        except Exception as e:
            return {"success": False, "message": f"读取失败: {str(e)}"}

        self._parsed = False
        return {
            "success": True,
            "message": f"加载成功: {len(self._data)} 字节",
            "size": len(self._data)
        }

    def load_bytes(self, data: bytes) -> dict:
        """从字节数据加载"""
        self._data = data
        self._file_path = ""
        self._parsed = False
        return {
            "success": True,
            "message": f"加载成功: {len(data)} 字节",
            "size": len(data)
        }

    def parse_header(self) -> dict:
        """解析 SHP 头部"""
        if not self._data:
            return {"success": False, "message": "未加载数据"}

        if len(self._data) < 8:
            return {"success": False, "message": "数据不足: 需要至少8字节"}

        try:
            self._frame_count = struct.unpack("<I", self._data[0:4])[0]
            self._header_size = struct.unpack("<I", self._data[4:8])[0]

            # 解析帧偏移表
            self._frame_offsets = []
            self._frame_sizes = []
            offset_table_start = 8
            for i in range(self._frame_count):
                if offset_table_start + 8 > len(self._data):
                    break
                frame_offset = struct.unpack("<I", self._data[offset_table_start:offset_table_start+4])[0]
                frame_size = struct.unpack("<I", self._data[offset_table_start+4:offset_table_start+8])[0]
                self._frame_offsets.append(frame_offset)
                self._frame_sizes.append(frame_size)
                offset_table_start += 8

            self._parsed = True
            return {
                "success": True,
                "frame_count": self._frame_count,
                "header_size": self._header_size,
                "frame_offsets": self._frame_offsets,
                "frame_sizes": self._frame_sizes,
                "total_data_size": len(self._data)
            }
        except struct.error as e:
            return {"success": False, "message": f"解析失败: {str(e)}"}

    def extract_frame(self, frame_index: int) -> dict:
        """提取指定帧数据"""
        if not self._parsed:
            result = self.parse_header()
            if not result["success"]:
                return result

        if frame_index < 0 or frame_index >= len(self._frame_offsets):
            return {"success": False, "message": f"帧索引超出范围: {frame_index}"}

        offset = self._frame_offsets[frame_index]
        size = self._frame_sizes[frame_index]

        if offset + size > len(self._data):
            return {"success": False, "message": "帧数据超出文件范围"}

        frame_data = self._data[offset:offset + size]

        return {
            "success": True,
            "frame_index": frame_index,
            "offset": offset,
            "size": size,
            "data": frame_data,
            "data_hex": frame_data[:64].hex(),
            "md5": hashlib.md5(frame_data).hexdigest()
        }

    def extract_all_frames(self) -> dict:
        """提取所有帧"""
        if not self._parsed:
            result = self.parse_header()
            if not result["success"]:
                return result

        frames = []
        for i in range(self._frame_count):
            frame_result = self.extract_frame(i)
            if frame_result["success"]:
                frames.append(frame_result)

        return {
            "success": True,
            "count": len(frames),
            "frames": frames
        }

    def get_format_specification(self) -> dict:
        """获取 SHP 格式完整规范"""
        return {
            "format": "SHP",
            "extension": ".shp",
            "mime": "application/octet-stream",
            "sections": [
                {
                    "name": "Header",
                    "offset": 0,
                    "size": 8,
                    "fields": [
                        {"name": "frame_count", "offset": 0, "size": 4, "type": "uint32_le", "description": "总帧数"},
                        {"name": "header_size", "offset": 4, "size": 4, "type": "uint32_le", "description": "头部大小（含偏移表）"},
                    ]
                },
                {
                    "name": "Frame Offset Table",
                    "offset": 8,
                    "size": "frame_count * 8",
                    "fields": [
                        {"name": "frame_offset", "offset": "0 (per entry)", "size": 4, "type": "uint32_le", "description": "帧数据偏移"},
                        {"name": "frame_size", "offset": "4 (per entry)", "size": 4, "type": "uint32_le", "description": "帧数据大小"},
                    ]
                },
                {
                    "name": "Frame Data",
                    "offset": "header_size",
                    "size": "variable",
                    "fields": [
                        {"name": "width", "offset": "varies", "size": 2, "type": "uint16_le", "description": "帧宽度"},
                        {"name": "height", "offset": "varies", "size": 2, "type": "uint16_le", "description": "帧高度"},
                        {"name": "pixel_data", "offset": "varies", "size": "variable", "type": "bytes", "description": "像素数据（可能含调色板索引）"},
                    ]
                }
            ]
        }

    def get_info(self) -> dict:
        """获取 SHP 文件信息"""
        if not self._parsed:
            self.parse_header()

        return {
            "format": "SHP",
            "file_path": self._file_path,
            "file_size": len(self._data),
            "frame_count": self._frame_count,
            "header_size": self._header_size,
            "total_frame_data_size": sum(self._frame_sizes),
            "average_frame_size": sum(self._frame_sizes) / max(self._frame_count, 1)
        }


# ============================================================
# PCK 格式深度解析
# ============================================================

class PCKReverser:
    """PCK 格式深度逆向"""

    PCK_MAGIC = b"PCK\x00"

    def __init__(self):
        self._data = b""
        self._file_path = ""
        self._file_count = 0
        self._header_size = 0
        self._flags = 0
        self._entries: List[Dict] = []
        self._parsed = False

    def load(self, file_path: str) -> dict:
        """加载 PCK 文件"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        self._file_path = file_path
        try:
            with open(file_path, "rb") as f:
                self._data = f.read()
        except Exception as e:
            return {"success": False, "message": f"读取失败: {str(e)}"}

        self._parsed = False
        return {
            "success": True,
            "message": f"加载成功: {len(self._data)} 字节",
            "size": len(self._data)
        }

    def load_bytes(self, data: bytes) -> dict:
        """从字节数据加载"""
        self._data = data
        self._file_path = ""
        self._parsed = False
        return {
            "success": True,
            "message": f"加载成功: {len(data)} 字节",
            "size": len(data)
        }

    def parse_header(self) -> dict:
        """解析 PCK 头部"""
        if not self._data:
            return {"success": False, "message": "未加载数据"}

        if len(self._data) < 16:
            return {"success": False, "message": "数据不足: 需要至少16字节"}

        magic = self._data[0:4]
        if magic != self.PCK_MAGIC:
            return {"success": False, "message": f"无效的PCK魔数: {magic.hex()}"}

        try:
            self._file_count = struct.unpack("<I", self._data[4:8])[0]
            self._header_size = struct.unpack("<I", self._data[8:12])[0]
            self._flags = struct.unpack("<I", self._data[12:16])[0]

            self._parsed = True
            return {
                "success": True,
                "magic": magic.hex(),
                "file_count": self._file_count,
                "header_size": self._header_size,
                "flags": self._flags,
                "flags_hex": hex(self._flags),
                "is_compressed": bool(self._flags & 0x01),
                "is_encrypted": bool(self._flags & 0x02)
            }
        except struct.error as e:
            return {"success": False, "message": f"解析失败: {str(e)}"}

    def parse_entries(self) -> dict:
        """解析 PCK 文件条目"""
        if not self._parsed:
            result = self.parse_header()
            if not result["success"]:
                return result

        self._entries = []
        try:
            entry_offset = 16  # 文件表起始偏移
            for i in range(self._file_count):
                if entry_offset + 16 > len(self._data):
                    break

                name_len = struct.unpack("<I", self._data[entry_offset:entry_offset+4])[0]
                data_offset = struct.unpack("<I", self._data[entry_offset+4:entry_offset+8])[0]
                data_size = struct.unpack("<I", self._data[entry_offset+8:entry_offset+12])[0]
                data_size_compressed = struct.unpack("<I", self._data[entry_offset+12:entry_offset+16])[0]

                # 读取文件名
                name_start = entry_offset + 16
                name_end = name_start + name_len
                if name_end > len(self._data):
                    break
                file_name = self._data[name_start:name_end].decode("utf-8", errors="replace").rstrip("\x00")

                self._entries.append({
                    "index": i,
                    "name": file_name,
                    "name_length": name_len,
                    "data_offset": data_offset,
                    "data_size": data_size,
                    "data_size_compressed": data_size_compressed,
                    "is_compressed": data_size_compressed > 0 and data_size_compressed != data_size,
                    "compression_ratio": data_size_compressed / max(data_size, 1) if data_size_compressed > 0 else 1.0
                })

                entry_offset = name_end

            return {
                "success": True,
                "count": len(self._entries),
                "entries": self._entries
            }
        except Exception as e:
            return {"success": False, "message": f"解析条目失败: {str(e)}"}

    def extract_file(self, index: int) -> dict:
        """提取指定文件"""
        if not self._entries:
            result = self.parse_entries()
            if not result["success"]:
                return result

        if index < 0 or index >= len(self._entries):
            return {"success": False, "message": f"索引超出范围: {index}"}

        entry = self._entries[index]
        offset = entry["data_offset"]
        size = entry["data_size"]

        if offset + size > len(self._data):
            return {"success": False, "message": "文件数据超出范围"}

        file_data = self._data[offset:offset + size]

        return {
            "success": True,
            "entry": entry,
            "data": file_data,
            "size": len(file_data),
            "md5": hashlib.md5(file_data).hexdigest()
        }

    def validate(self) -> dict:
        """校验 PCK 文件完整性"""
        errors = []
        warnings = []

        if not self._data:
            return {"success": False, "message": "未加载数据", "errors": ["无数据"]}

        # 魔数校验
        if self._data[:4] != self.PCK_MAGIC:
            errors.append(f"无效魔数: {self._data[:4].hex()}")

        # 大小校验
        if len(self._data) < 16:
            errors.append(f"文件太小: {len(self._data)} 字节")

        if not self._parsed:
            self.parse_header()

        if self._file_count > 100000:
            warnings.append(f"文件数量异常大: {self._file_count}")

        if self._header_size > len(self._data):
            errors.append(f"头部大小超出文件大小: {self._header_size} > {len(self._data)}")

        # 校验条目
        if self._entries:
            for entry in self._entries:
                if entry["data_offset"] + entry["data_size"] > len(self._data):
                    errors.append(f"条目 {entry['name']} 数据超出范围")
                if entry["data_size"] == 0:
                    warnings.append(f"条目 {entry['name']} 大小为0")

        return {
            "success": len(errors) == 0,
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "file_size": len(self._data),
            "file_count": self._file_count
        }

    def get_format_specification(self) -> dict:
        """获取 PCK 格式完整规范"""
        return {
            "format": "PCK",
            "extension": ".pck",
            "magic": "50434B00 (PCK\\x00)",
            "sections": [
                {
                    "name": "PCK Header",
                    "offset": 0,
                    "size": 16,
                    "fields": [
                        {"name": "magic", "offset": 0, "size": 4, "type": "bytes", "description": "魔数 'PCK\\x00'"},
                        {"name": "file_count", "offset": 4, "size": 4, "type": "uint32_le", "description": "文件数量"},
                        {"name": "header_size", "offset": 8, "size": 4, "type": "uint32_le", "description": "文件表大小"},
                        {"name": "flags", "offset": 12, "size": 4, "type": "uint32_le", "description": "标志位 (bit0=压缩, bit1=加密)"},
                    ]
                },
                {
                    "name": "File Entry Table",
                    "offset": 16,
                    "size": "variable",
                    "fields": [
                        {"name": "name_length", "offset": "0 (per entry)", "size": 4, "type": "uint32_le", "description": "文件名长度"},
                        {"name": "data_offset", "offset": "4 (per entry)", "size": 4, "type": "uint32_le", "description": "文件数据偏移"},
                        {"name": "data_size", "offset": "8 (per entry)", "size": 4, "type": "uint32_le", "description": "原始数据大小"},
                        {"name": "compressed_size", "offset": "12 (per entry)", "size": 4, "type": "uint32_le", "description": "压缩后大小"},
                        {"name": "file_name", "offset": "16 (per entry)", "size": "name_length", "type": "string", "description": "文件名 (UTF-8)"},
                    ]
                },
                {
                    "name": "File Data",
                    "offset": "data_offset",
                    "size": "data_size",
                    "fields": [
                        {"name": "raw_data", "offset": 0, "size": "data_size", "type": "bytes", "description": "文件原始数据"},
                    ]
                }
            ],
            "flags": {
                "0x01": "压缩",
                "0x02": "加密",
                "0x04": "保留",
                "0x08": "保留",
            }
        }

    def get_info(self) -> dict:
        """获取 PCK 信息"""
        if not self._parsed:
            self.parse_header()

        total_raw = sum(e["data_size"] for e in self._entries)
        total_compressed = sum(e["data_size_compressed"] for e in self._entries) if self._entries else 0

        return {
            "format": "PCK",
            "file_path": self._file_path,
            "file_size": len(self._data),
            "file_count": self._file_count,
            "header_size": self._header_size,
            "flags": self._flags,
            "is_compressed": bool(self._flags & 0x01),
            "is_encrypted": bool(self._flags & 0x02),
            "total_raw_size": total_raw,
            "total_compressed_size": total_compressed,
            "compression_ratio": total_compressed / max(total_raw, 1) if total_compressed > 0 else 1.0
        }


# ============================================================
# OBD 格式深度解析
# ============================================================

class OBDReverser:
    """OBD 格式深度逆向"""

    def __init__(self):
        self._data = b""
        self._file_path = ""
        self._objects: List[Dict] = []
        self._parsed = False

    def load(self, file_path: str) -> dict:
        """加载 OBD 文件"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        self._file_path = file_path
        try:
            with open(file_path, "rb") as f:
                self._data = f.read()
        except Exception as e:
            return {"success": False, "message": f"读取失败: {str(e)}"}

        self._parsed = False
        return {"success": True, "message": f"加载成功: {len(self._data)} 字节", "size": len(self._data)}

    def load_bytes(self, data: bytes) -> dict:
        """从字节数据加载"""
        self._data = data
        self._file_path = ""
        self._parsed = False
        return {"success": True, "message": f"加载成功: {len(data)} 字节", "size": len(data)}

    def parse(self) -> dict:
        """解析 OBD 文件"""
        if not self._data:
            return {"success": False, "message": "未加载数据"}

        self._objects = []
        try:
            text = self._data.decode("utf-8", errors="replace")
            lines = text.split("\n")

            current_obj = None
            current_section = None

            for line_num, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith(";") or line.startswith("#"):
                    continue

                # 检测对象定义
                if line.startswith("[") and line.endswith("]"):
                    if current_obj:
                        self._objects.append(current_obj)
                    section_name = line[1:-1]
                    current_obj = {
                        "name": section_name,
                        "line": line_num + 1,
                        "sections": {},
                        "properties": {}
                    }
                    current_section = section_name
                    continue

                # 解析键值对
                if "=" in line and current_obj is not None:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()

                    # 分类字段
                    if key.lower() in ("objid", "sequence", "sprite", "interval", "loop", "direction"):
                        if key not in current_obj["properties"]:
                            current_obj["properties"][key] = []
                        current_obj["properties"][key].append(value)
                    else:
                        current_obj["properties"][key] = value

            if current_obj:
                self._objects.append(current_obj)

            self._parsed = True
            return {
                "success": True,
                "count": len(self._objects),
                "objects": self._objects
            }
        except Exception as e:
            return {"success": False, "message": f"解析失败: {str(e)}"}

    def get_object(self, name: str) -> Optional[Dict]:
        """获取指定对象"""
        if not self._parsed:
            self.parse()
        for obj in self._objects:
            if obj["name"].lower() == name.lower():
                return obj
        return None

    def get_all_sequences(self) -> List[str]:
        """获取所有 Sequence"""
        if not self._parsed:
            self.parse()
        sequences = set()
        for obj in self._objects:
            for seq in obj["properties"].get("Sequence", []):
                sequences.add(seq)
        return sorted(sequences)

    def get_all_sprites(self) -> List[str]:
        """获取所有 Sprite"""
        if not self._parsed:
            self.parse()
        sprites = set()
        for obj in self._objects:
            for sprite in obj["properties"].get("Sprite", []):
                sprites.add(sprite)
        return sorted(sprites)

    def get_format_specification(self) -> dict:
        """获取 OBD 格式完整规范"""
        return {
            "format": "OBD",
            "extension": ".obd",
            "type": "text",
            "encoding": "UTF-8",
            "sections": [
                {
                    "name": "Object Definition",
                    "syntax": "[ObjectName]",
                    "description": "对象定义节，每个对象代表一个模型或动画"
                },
                {
                    "name": "Properties",
                    "syntax": "Key = Value",
                    "description": "对象属性键值对",
                    "known_keys": {
                        "ObjID": "对象唯一标识符",
                        "Sequence": "动画序列名称",
                        "Sprite": "精灵帧引用",
                        "Interval": "帧间隔时间",
                        "Loop": "是否循环播放",
                        "Direction": "方向数量",
                        "Shadow": "阴影设置",
                        "Sound": "音效引用",
                    }
                }
            ]
        }

    def get_info(self) -> dict:
        """获取 OBD 信息"""
        if not self._parsed:
            self.parse()

        return {
            "format": "OBD",
            "file_path": self._file_path,
            "file_size": len(self._data),
            "object_count": len(self._objects),
            "sequence_count": len(self.get_all_sequences()),
            "sprite_count": len(self.get_all_sprites()),
            "objects": [obj["name"] for obj in self._objects]
        }


# ============================================================
# 跨格式映射分析
# ============================================================

class CrossFormatMapper:
    """跨格式资源映射分析器"""

    def __init__(self):
        self._file_registry: Dict[str, Dict] = {}
        self._cross_references: Dict[str, List[Dict]] = {}
        self._resolved_refs: Dict[str, List[str]] = {}
        self._unresolved_refs: Dict[str, List[str]] = {}

    def register_file(self, file_path: str, format_type: str, info: Dict) -> None:
        """注册文件"""
        self._file_registry[file_path] = {
            "format": format_type,
            "info": info,
            "registered_at": len(self._file_registry)
        }

    def map_references(self) -> dict:
        """映射跨文件引用关系"""
        self._cross_references.clear()
        self._resolved_refs.clear()
        self._unresolved_refs.clear()

        for path, meta in self._file_registry.items():
            refs = []
            resolved = []
            unresolved = []

            fmt = meta["format"]
            info = meta["info"]

            # OBD → SHP 引用
            if fmt == "obd" and "sprites" in info:
                for sprite in info.get("sprites", []):
                    refs.append({"type": "sprite", "target": sprite, "source": "obd"})
                    resolved.append(sprite)

            # INI → 其他 INI 引用
            if fmt == "ini" and "references" in info:
                for ref in info.get("references", []):
                    refs.append({"type": "ini_ref", "target": ref["file"], "source": "ini"})
                    if self._resolve_file(ref["file"]):
                        resolved.append(ref["file"])
                    else:
                        unresolved.append(ref["file"])

            # PCK → 内部文件引用
            if fmt == "pck" and "entries" in info:
                for entry in info.get("entries", []):
                    refs.append({"type": "internal", "target": entry["name"], "source": "pck"})
                    resolved.append(entry["name"])

            if refs:
                self._cross_references[path] = refs
            if resolved:
                self._resolved_refs[path] = resolved
            if unresolved:
                self._unresolved_refs[path] = unresolved

        return {
            "success": True,
            "cross_references": self._cross_references,
            "resolved": self._resolved_refs,
            "unresolved": self._unresolved_refs,
            "total_files": len(self._file_registry),
            "total_refs": sum(len(r) for r in self._cross_references.values()),
            "total_unresolved": sum(len(r) for r in self._unresolved_refs.values())
        }

    def _resolve_file(self, file_name: str) -> bool:
        """检查文件是否存在于注册表中"""
        for path in self._file_registry:
            if os.path.basename(path) == file_name:
                return True
        return False

    def get_registry(self) -> dict:
        """获取文件注册表"""
        return {
            "success": True,
            "count": len(self._file_registry),
            "files": self._file_registry
        }


# ============================================================
# 二进制格式模板生成器
# ============================================================

class BinaryTemplateGenerator:
    """二进制格式模板生成器 — 自动生成 010 Editor 二进制模板"""

    @staticmethod
    def generate_shp_template() -> str:
        """生成 SHP 格式的 010 Editor 模板"""
        return """// SHP Image Format Template for 010 Editor
// Generated by San7ModMaker Resource Reverse Engine

typedef struct {
    uint32 frame_count;
    uint32 header_size;
} SHP_HEADER;

typedef struct {
    uint32 offset;
    uint32 size;
} SHP_FRAME_ENTRY;

typedef struct {
    uint16 width;
    uint16 height;
    // pixel data follows
} SHP_FRAME_HEADER;

LittleEndian();
SHP_HEADER header;

local int i;
local uint64 frame_start;

SHP_FRAME_ENTRY frame_entries[header.frame_count] <optimize=false>;

for (i = 0; i < header.frame_count; i++) {
    FSeek(frame_entries[i].offset);
    SHP_FRAME_HEADER frame_header;
    // pixel data: frame_entries[i].size - 4 bytes
    uint8 pixel_data[frame_entries[i].size - sizeof(SHP_FRAME_HEADER)];
}
"""

    @staticmethod
    def generate_pck_template() -> str:
        """生成 PCK 格式的 010 Editor 模板"""
        return """// PCK Archive Format Template for 010 Editor
// Generated by San7ModMaker Resource Reverse Engine

typedef struct {
    char magic[4];
    uint32 file_count;
    uint32 header_size;
    uint32 flags; // bit0=compressed, bit1=encrypted
} PCK_HEADER;

typedef struct {
    uint32 name_length;
    uint32 data_offset;
    uint32 data_size;
    uint32 compressed_size;
} PCK_ENTRY;

LittleEndian();
PCK_HEADER header;

local int i;
local uint64 current_pos;

PCK_ENTRY entries[header.file_count] <optimize=false>;

for (i = 0; i < header.file_count; i++) {
    char file_name[entries[i].name_length];
    FSeek(entries[i].data_offset);
    uint8 file_data[entries[i].data_size];
}
"""

    @staticmethod
    def generate_elf_template() -> str:
        """生成 ELF 格式的 010 Editor 模板"""
        return """// ELF Format Template for 010 Editor
// Generated by San7ModMaker Resource Reverse Engine

typedef struct {
    uchar ei_magic[4]; // 0x7F 'E' 'L' 'F'
    uchar ei_class;    // 1=32bit, 2=64bit
    uchar ei_data;     // 1=LE, 2=BE
    uchar ei_version;
    uchar ei_osabi;
    uchar ei_abiversion;
    uchar ei_pad[7];
} ELF_IDENT;

typedef struct {
    ELF_IDENT ident;
    uint16 e_type;
    uint16 e_machine;
    uint32 e_version;
    uint32 e_entry;
    uint32 e_phoff;
    uint32 e_shoff;
    uint32 e_flags;
    uint16 e_ehsize;
    uint16 e_phentsize;
    uint16 e_phnum;
    uint16 e_shentsize;
    uint16 e_shnum;
    uint16 e_shstrndx;
} ELF32_HEADER;

LittleEndian();
ELF32_HEADER elf_header;

// Program Headers
if (elf_header.e_phoff) {
    FSeek(elf_header.e_phoff);
    local int i;
    for (i = 0; i < elf_header.e_phnum; i++) {
        struct {
            uint32 p_type;
            uint32 p_offset;
            uint32 p_vaddr;
            uint32 p_paddr;
            uint32 p_filesz;
            uint32 p_memsz;
            uint32 p_flags;
            uint32 p_align;
        } phdr;
    }
}

// Section Headers
if (elf_header.e_shoff) {
    FSeek(elf_header.e_shoff);
    local int j;
    for (j = 0; j < elf_header.e_shnum; j++) {
        struct {
            uint32 sh_name;
            uint32 sh_type;
            uint32 sh_flags;
            uint32 sh_addr;
            uint32 sh_offset;
            uint32 sh_size;
            uint32 sh_link;
            uint32 sh_info;
            uint32 sh_addralign;
            uint32 sh_entsize;
        } shdr;
    }
}
"""

    @classmethod
    def generate_template(cls, format_type: str) -> Optional[str]:
        """生成指定格式的模板"""
        generators = {
            "shp": cls.generate_shp_template,
            "pck": cls.generate_pck_template,
            "scriptso": cls.generate_elf_template,
            "elf": cls.generate_elf_template,
        }
        generator = generators.get(format_type)
        return generator() if generator else None

    @classmethod
    def list_templates(cls) -> List[str]:
        """列出所有可用模板"""
        return ["shp", "pck", "scriptso", "elf"]


# ============================================================
# 完整性校验引擎
# ============================================================

class IntegrityChecker:
    """文件完整性校验引擎"""

    @staticmethod
    def verify_shp(file_path: str) -> FileValidationResult:
        """校验 SHP 文件完整性"""
        result = FileValidationResult(file_path=file_path, is_valid=False, format_type="SHP")

        if not os.path.exists(file_path):
            result.errors.append("文件不存在")
            return result

        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            result.errors.append(f"读取失败: {str(e)}")
            return result

        if len(data) < 8:
            result.errors.append(f"文件太小 ({len(data)} 字节)，最少需要8字节")
            return result

        try:
            frame_count = struct.unpack("<I", data[0:4])[0]
            header_size = struct.unpack("<I", data[4:8])[0]

            result.info["frame_count"] = frame_count
            result.info["header_size"] = header_size
            result.info["file_size"] = len(data)

            if frame_count == 0:
                result.warnings.append("帧数为0")
            if frame_count > 10000:
                result.warnings.append(f"帧数异常大: {frame_count}")
            if header_size > len(data):
                result.errors.append(f"头部大小 ({header_size}) 超出文件大小 ({len(data)})")

            # 校验帧偏移表
            for i in range(frame_count):
                offset = 8 + i * 8
                if offset + 8 > len(data):
                    result.errors.append(f"帧偏移表超出范围 (帧 {i})")
                    break
                frame_offset = struct.unpack("<I", data[offset:offset+4])[0]
                frame_size = struct.unpack("<I", data[offset+4:offset+8])[0]
                if frame_offset + frame_size > len(data):
                    result.errors.append(f"帧 {i} 数据超出文件范围")

            result.is_valid = len(result.errors) == 0

        except struct.error as e:
            result.errors.append(f"结构解析失败: {str(e)}")

        return result

    @staticmethod
    def verify_pck(file_path: str) -> FileValidationResult:
        """校验 PCK 文件完整性"""
        result = FileValidationResult(file_path=file_path, is_valid=False, format_type="PCK")

        if not os.path.exists(file_path):
            result.errors.append("文件不存在")
            return result

        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            result.errors.append(f"读取失败: {str(e)}")
            return result

        if len(data) < 16:
            result.errors.append(f"文件太小 ({len(data)} 字节)，最少需要16字节")
            return result

        magic = data[0:4]
        if magic != b"PCK\x00":
            result.errors.append(f"无效魔数: {magic.hex()} (期望: 50434B00)")
            return result

        try:
            file_count = struct.unpack("<I", data[4:8])[0]
            header_size = struct.unpack("<I", data[8:12])[0]
            flags = struct.unpack("<I", data[12:16])[0]

            result.info["file_count"] = file_count
            result.info["header_size"] = header_size
            result.info["flags"] = flags
            result.info["file_size"] = len(data)
            result.info["is_compressed"] = bool(flags & 0x01)
            result.info["is_encrypted"] = bool(flags & 0x02)

            if file_count == 0:
                result.warnings.append("文件数为0")
            if file_count > 100000:
                result.warnings.append(f"文件数异常大: {file_count}")

            result.is_valid = len(result.errors) == 0

        except struct.error as e:
            result.errors.append(f"结构解析失败: {str(e)}")

        return result

    @staticmethod
    def verify_scriptso(file_path: str) -> FileValidationResult:
        """校验 Script.so 完整性"""
        result = FileValidationResult(file_path=file_path, is_valid=False, format_type="Script.so")

        if not os.path.exists(file_path):
            result.errors.append("文件不存在")
            return result

        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            result.errors.append(f"读取失败: {str(e)}")
            return result

        if len(data) < 52:
            result.errors.append(f"文件太小 ({len(data)} 字节)，最少需要52字节")
            return result

        magic = data[0:4]
        if magic != b"\x7fELF":
            result.errors.append(f"无效ELF魔数: {magic.hex()}")
            return result

        ei_class = data[4]
        ei_data = data[5]

        result.info["ei_class"] = "32-bit" if ei_class == 1 else "64-bit" if ei_class == 2 else f"未知({ei_class})"
        result.info["ei_data"] = "小端" if ei_data == 1 else "大端" if ei_data == 2 else f"未知({ei_data})"
        result.info["file_size"] = len(data)

        result.is_valid = True

        return result

    @classmethod
    def verify_file(cls, file_path: str) -> FileValidationResult:
        """自动检测并校验文件"""
        fmt = FormatDetector.detect(file_path)
        verifiers = {
            "shp": cls.verify_shp,
            "pck": cls.verify_pck,
            "scriptso": cls.verify_scriptso,
        }
        verifier = verifiers.get(fmt)
        if verifier:
            return verifier(file_path)

        return FileValidationResult(
            file_path=file_path,
            is_valid=False,
            format_type=fmt or "unknown",
            errors=[f"不支持的格式: {fmt}"]
        )


# ============================================================
# 资源格式综合引擎
# ============================================================

class ResourceReverseEngine:
    """
    资源文件格式深度逆向综合引擎
    
    整合格式检测、二进制解析、完整性校验、跨格式映射和模板生成。
    """

    def __init__(self):
        self.shp_reverser = SHPReverser()
        self.pck_reverser = PCKReverser()
        self.obd_reverser = OBDReverser()
        self.cross_mapper = CrossFormatMapper()
        self.format_detector = FormatDetector()
        self.integrity_checker = IntegrityChecker()

    def analyze_file(self, file_path: str) -> dict:
        """综合分析单个文件"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        fmt = self.format_detector.detect(file_path)
        if not fmt:
            return {"success": False, "message": "无法检测文件格式"}

        result = {
            "success": True,
            "file_path": file_path,
            "format": fmt,
            "file_size": os.path.getsize(file_path),
            "md5": hashlib.md5(open(file_path, "rb").read()).hexdigest()
        }

        # 格式特定分析
        if fmt == "shp":
            self.shp_reverser.load(file_path)
            result["header"] = self.shp_reverser.parse_header()
            result["info"] = self.shp_reverser.get_info()
            result["spec"] = self.shp_reverser.get_format_specification()
        elif fmt == "pck":
            self.pck_reverser.load(file_path)
            result["header"] = self.pck_reverser.parse_header()
            result["entries"] = self.pck_reverser.parse_entries()
            result["info"] = self.pck_reverser.get_info()
            result["spec"] = self.pck_reverser.get_format_specification()
        elif fmt == "obd":
            self.obd_reverser.load(file_path)
            result["parse"] = self.obd_reverser.parse()
            result["info"] = self.obd_reverser.get_info()
            result["spec"] = self.obd_reverser.get_format_specification()

        # 完整性校验
        result["integrity"] = self.integrity_checker.verify_file(file_path)

        return result

    def analyze_directory(self, directory: str) -> dict:
        """综合分析目录中的所有文件"""
        if not os.path.isdir(directory):
            return {"success": False, "message": f"目录不存在: {directory}"}

        results = []
        format_counts = {}
        errors = []
        total_size = 0

        for root, dirs, files in os.walk(directory):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                fmt = self.format_detector.detect(file_path)

                if fmt and fmt != "unknown":
                    format_counts[fmt] = format_counts.get(fmt, 0) + 1
                    total_size += os.path.getsize(file_path)

                    analysis = self.analyze_file(file_path)
                    results.append({
                        "file": file_path,
                        "format": fmt,
                        "valid": analysis.get("integrity", FileValidationResult(
                            file_path=file_path, is_valid=False, format_type=fmt
                        )).is_valid
                    })

        return {
            "success": True,
            "directory": directory,
            "total_files": len(results),
            "total_size": total_size,
            "format_distribution": format_counts,
            "results": results,
            "errors": errors
        }

    def get_format_specification(self, format_type: str) -> dict:
        """获取格式规范"""
        spec_map = {
            "shp": SHP_FORMAT,
            "pck": PCK_FORMAT,
            "obd": OBD_FORMAT,
            "mpc": MPC_FORMAT,
            "ini": INI_FORMAT,
            "scriptso": SCRIPTSO_FORMAT,
        }
        spec = spec_map.get(format_type)
        if not spec:
            return {"success": False, "message": f"未知格式: {format_type}"}

        return {
            "success": True,
            "format": spec.name,
            "extension": spec.extension,
            "magic": spec.magic.hex() if spec.magic else "无固定魔数",
            "description": spec.description,
            "header_size": spec.header_size,
            "header_fields": spec.header_fields,
            "is_archive": spec.is_archive,
            "contains_compressed": spec.contains_compressed,
            "endian": spec.endian
        }

    def generate_binary_template(self, format_type: str) -> dict:
        """生成二进制模板"""
        template = BinaryTemplateGenerator.generate_template(format_type)
        if not template:
            return {"success": False, "message": f"不支持的模板格式: {format_type}"}

        return {
            "success": True,
            "format": format_type,
            "template": template,
            "language": "010 Editor Binary Template"
        }

    def get_all_formats(self) -> dict:
        """获取所有已知格式"""
        formats = {}
        for name, spec in KNOWN_FORMATS.items():
            formats[name] = {
                "name": spec.name,
                "extension": spec.extension,
                "magic": spec.magic.hex() if spec.magic else "无",
                "description": spec.description,
                "is_archive": spec.is_archive,
                "contains_compressed": spec.contains_compressed
            }
        return {"success": True, "formats": formats, "count": len(formats)}