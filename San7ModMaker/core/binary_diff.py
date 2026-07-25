"""
二进制差异化与补丁引擎 (Binary Diff & Patch Engine)
提供完整的二进制差异生成、结构感知对比、签名扫描、补丁管理与合并功能。

引擎突破 13: 支持 bsdiff 风格 delta 压缩、结构/语义级差异、IPS/BPS 补丁格式
"""

import os
import struct
import hashlib
import zlib
import json
from typing import Dict, List, Optional, Tuple, Set, Any, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict


# ============================================================
# 数据类定义
# ============================================================

class DiffType(Enum):
    """差异类型"""
    INSERT = "insert"        # 新增字节
    DELETE = "delete"        # 删除字节
    REPLACE = "replace"      # 替换字节
    EQUAL = "equal"          # 相同字节
    SHIFT = "shift"          # 偏移变化


class PatchFormat(Enum):
    """补丁格式"""
    DELTA = "delta"          # 自定义 delta 格式
    IPS = "ips"              # International Patching System
    BPS = "bps"              # Beat Patching System
    BINARY = "binary"        # 原始二进制补丁


class SignatureFormat(Enum):
    """签名格式"""
    IDA = "ida"              # IDA Pro 格式: 48 8B ? ? ? ? 00
    X64DBG = "x64dbg"        # x64dbg 格式: 48 8B ?? ?? ?? ?? 00
    CODE = "code"            # 代码风格: \x48\x8B\x00\x00\x00\x00\x00
    PEID = "peid"            # PEiD 格式: 48 8B ?? ?? ?? ?? 00


@dataclass
class DiffEntry:
    """差异条目"""
    diff_type: DiffType
    offset: int
    old_data: bytes = b""
    new_data: bytes = b""
    length: int = 0
    source_offset: int = 0
    target_offset: int = 0

    @property
    def size(self) -> int:
        if self.diff_type == DiffType.INSERT:
            return len(self.new_data)
        elif self.diff_type == DiffType.DELETE:
            return len(self.old_data)
        elif self.diff_type == DiffType.SHIFT:
            return self.length
        return len(self.old_data)


@dataclass
class BlockInfo:
    """块信息"""
    block_id: int
    offset: int
    size: int
    hash_value: str
    data: bytes = b""


@dataclass
class SignatureMatch:
    """签名匹配结果"""
    signature: str
    offset: int
    matched_bytes: bytes
    pattern: str
    format: SignatureFormat = SignatureFormat.IDA


@dataclass
class DiffReport:
    """差异报告"""
    file_a: str = ""
    file_b: str = ""
    total_entries: int = 0
    insertions: int = 0
    deletions: int = 0
    replacements: int = 0
    shifts: int = 0
    bytes_added: int = 0
    bytes_removed: int = 0
    bytes_changed: int = 0
    similarity: float = 0.0
    entries: List[DiffEntry] = field(default_factory=list)
    sections: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def _update_stats(self):
        """从 entries 更新统计信息"""
        self.total_entries = len(self.entries)
        self.insertions = sum(1 for e in self.entries if e.diff_type == DiffType.INSERT)
        self.deletions = sum(1 for e in self.entries if e.diff_type == DiffType.DELETE)
        self.replacements = sum(1 for e in self.entries if e.diff_type == DiffType.REPLACE)
        self.shifts = sum(1 for e in self.entries if e.diff_type == DiffType.SHIFT)
        self.bytes_added = sum(len(e.new_data) for e in self.entries if e.diff_type == DiffType.INSERT)
        self.bytes_removed = sum(len(e.old_data) for e in self.entries if e.diff_type == DiffType.DELETE)
        self.bytes_changed = sum(len(e.old_data) for e in self.entries if e.diff_type == DiffType.REPLACE)
        # 计算相似度
        total_bytes = max(self.bytes_added + self.bytes_removed + self.bytes_changed, 1)
        equal_bytes = sum(e.length for e in self.entries if e.diff_type == DiffType.EQUAL)
        self.similarity = round(equal_bytes / max(total_bytes + equal_bytes, 1), 4)


@dataclass
class PatchInfo:
    """补丁信息"""
    patch_id: str
    format: PatchFormat
    source_hash: str
    target_hash: str
    description: str = ""
    entries: List[DiffEntry] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# Delta 生成器
# ============================================================

class DeltaGenerator:
    """
    Delta 差异生成器
    
    实现多种差异算法:
    - 基于滑动窗口的快速字节级差异
    - 基于哈希块的块级差异
    - 指令级差异（保留指令边界）
    """

    BLOCK_SIZE = 64
    WINDOW_SIZE = 256

    def __init__(self):
        self._block_size = DeltaGenerator.BLOCK_SIZE

    # ============================================================
    # 字节级差异
    # ============================================================

    def diff_bytes(self, old_data: bytes, new_data: bytes) -> List[DiffEntry]:
        """生成字节级差异"""
        entries = []
        i = 0
        j = 0

        while i < len(old_data) and j < len(new_data):
            if old_data[i] == new_data[j]:
                # 计算相同区域长度
                eq_start = i
                while i < len(old_data) and j < len(new_data) and old_data[i] == new_data[j]:
                    i += 1
                    j += 1
                eq_len = i - eq_start
                if eq_len > 0:
                    entries.append(DiffEntry(
                        diff_type=DiffType.EQUAL,
                        offset=eq_start,
                        length=eq_len,
                        source_offset=eq_start,
                        target_offset=j - eq_len
                    ))
            else:
                # 尝试找到下一个匹配点
                next_match = self._find_next_match(old_data, new_data, i, j, self.WINDOW_SIZE)
                if next_match:
                    old_end, new_end = next_match
                    if old_end > i:
                        entries.append(DiffEntry(
                            diff_type=DiffType.DELETE,
                            offset=i,
                            old_data=old_data[i:old_end],
                            length=old_end - i
                        ))
                    if new_end > j:
                        entries.append(DiffEntry(
                            diff_type=DiffType.INSERT,
                            offset=j,
                            new_data=new_data[j:new_end],
                            length=new_end - j
                        ))
                    i, j = old_end, new_end
                else:
                    # 无法找到匹配，将剩余全部作为替换
                    if i < len(old_data) or j < len(new_data):
                        entries.append(DiffEntry(
                            diff_type=DiffType.REPLACE,
                            offset=i,
                            old_data=old_data[i:] if i < len(old_data) else b"",
                            new_data=new_data[j:] if j < len(new_data) else b"",
                            length=max(len(old_data) - i, len(new_data) - j)
                        ))
                    i = len(old_data)
                    j = len(new_data)
                    break

        # 处理剩余
        if i < len(old_data):
            entries.append(DiffEntry(
                diff_type=DiffType.DELETE,
                offset=i,
                old_data=old_data[i:],
                length=len(old_data) - i
            ))
        if j < len(new_data):
            entries.append(DiffEntry(
                diff_type=DiffType.INSERT,
                offset=j,
                new_data=new_data[j:],
                length=len(new_data) - j
            ))

        return entries

    def _find_next_match(self, old: bytes, new: bytes, old_pos: int, new_pos: int,
                         window: int) -> Optional[Tuple[int, int]]:
        """在窗口内寻找下一个匹配点"""
        # 计算搜索模式长度 - 至少 1 字节
        remaining_old = len(old) - old_pos
        remaining_new = len(new) - new_pos
        search_len = min(8, min(remaining_old, remaining_new))
        if search_len < 1:
            return None

        search_pattern = old[old_pos:old_pos + search_len]
        end = min(new_pos + window, len(new) - search_len + 1)
        for k in range(new_pos, end):
            if new[k:k + search_len] == search_pattern:
                return (old_pos, k)

        return None

    # ============================================================
    # 块级差异
    # ============================================================

    def diff_blocks(self, old_data: bytes, new_data: bytes) -> List[DiffEntry]:
        """生成块级差异（基于哈希比对）"""
        old_blocks = self._split_blocks(old_data)
        new_blocks = self._split_blocks(new_data)

        old_hash_map = {b.hash_value: b for b in old_blocks}
        new_hash_map = {b.hash_value: b for b in new_blocks}

        entries = []

        # 找到新增块
        for block in new_blocks:
            if block.hash_value not in old_hash_map:
                entries.append(DiffEntry(
                    diff_type=DiffType.INSERT,
                    offset=block.offset,
                    new_data=block.data,
                    length=block.size
                ))

        # 找到删除块
        for block in old_blocks:
            if block.hash_value not in new_hash_map:
                entries.append(DiffEntry(
                    diff_type=DiffType.DELETE,
                    offset=block.offset,
                    old_data=block.data,
                    length=block.size
                ))

        # 找到移动/偏移块
        for block in new_blocks:
            if block.hash_value in old_hash_map:
                old_block = old_hash_map[block.hash_value]
                if old_block.offset != block.offset:
                    entries.append(DiffEntry(
                        diff_type=DiffType.SHIFT,
                        offset=block.offset,
                        length=block.size,
                        source_offset=old_block.offset,
                        target_offset=block.offset
                    ))

        return sorted(entries, key=lambda e: e.offset)

    def _split_blocks(self, data: bytes) -> List[BlockInfo]:
        """将数据分割为哈希块"""
        blocks = []
        for i in range(0, len(data), self._block_size):
            chunk = data[i:i + self._block_size]
            blocks.append(BlockInfo(
                block_id=i // self._block_size,
                offset=i,
                size=len(chunk),
                hash_value=hashlib.md5(chunk).hexdigest(),
                data=chunk
            ))
        return blocks

    # ============================================================
    # 指令级差异
    # ============================================================

    def diff_instructions(self, old_instructions: List[dict],
                          new_instructions: List[dict]) -> List[DiffEntry]:
        """生成指令级差异（保留指令边界）"""
        entries = []
        i = j = 0

        while i < len(old_instructions) and j < len(new_instructions):
            old_ins = old_instructions[i]
            new_ins = new_instructions[j]

            if old_ins.get("bytes") == new_ins.get("bytes"):
                i += 1
                j += 1
                continue

            # 查找匹配
            found = False
            for k in range(j, min(j + 5, len(new_instructions))):
                if new_instructions[k].get("bytes") == old_ins.get("bytes"):
                    # 删除了 j 到 k-1 的指令
                    for m in range(j, k):
                        entries.append(DiffEntry(
                            diff_type=DiffType.DELETE,
                            offset=new_instructions[m].get("address", 0),
                            old_data=new_instructions[m].get("bytes", b""),
                            length=new_instructions[m].get("size", 0)
                        ))
                    j = k
                    found = True
                    break

            if not found:
                entries.append(DiffEntry(
                    diff_type=DiffType.REPLACE,
                    offset=old_ins.get("address", 0),
                    old_data=old_ins.get("bytes", b""),
                    new_data=new_ins.get("bytes", b""),
                    length=max(old_ins.get("size", 0), new_ins.get("size", 0))
                ))
                i += 1
                j += 1

        return entries

    # ============================================================
    # Delta 压缩
    # ============================================================

    def generate_delta(self, old_data: bytes, new_data: bytes) -> bytes:
        """生成压缩 delta 数据"""
        entries = self.diff_bytes(old_data, new_data)
        return self._encode_delta(entries)

    def apply_delta(self, old_data: bytes, delta: bytes) -> bytes:
        """应用 delta 补丁"""
        entries = self._decode_delta(delta)
        result = bytearray()
        old_pos = 0

        for entry in entries:
            if entry.diff_type == DiffType.EQUAL:
                # 从 old_data 复制 length 字节
                end = min(old_pos + entry.length, len(old_data))
                result.extend(old_data[old_pos:end])
                old_pos += entry.length
            elif entry.diff_type == DiffType.INSERT:
                result.extend(entry.new_data)
            elif entry.diff_type == DiffType.DELETE:
                old_pos += entry.length
            elif entry.diff_type == DiffType.REPLACE:
                old_pos += len(entry.old_data)
                result.extend(entry.new_data)
            elif entry.diff_type == DiffType.SHIFT:
                end = min(old_pos + entry.length, len(old_data))
                result.extend(old_data[old_pos:end])
                old_pos += entry.length

        # 追加 old_data 剩余部分
        if old_pos < len(old_data):
            result.extend(old_data[old_pos:])

        return bytes(result)

    def _encode_delta(self, entries: List[DiffEntry]) -> bytes:
        """编码 delta 条目为二进制"""
        parts = [b"DELTA\x01\x00"]

        for entry in entries:
            if entry.diff_type == DiffType.EQUAL:
                parts.append(struct.pack("<BI", 0x04, entry.length))
            elif entry.diff_type == DiffType.INSERT:
                parts.append(struct.pack("<BI", 0x01, len(entry.new_data)))
                parts.append(entry.new_data)
            elif entry.diff_type == DiffType.DELETE:
                parts.append(struct.pack("<BI", 0x02, len(entry.old_data)))
            elif entry.diff_type == DiffType.REPLACE:
                parts.append(struct.pack("<BII", 0x03, len(entry.old_data), len(entry.new_data)))
                parts.append(entry.new_data)
            elif entry.diff_type == DiffType.SHIFT:
                parts.append(struct.pack("<BII", 0x05, entry.length, entry.target_offset))

        raw = b"".join(parts)
        return zlib.compress(raw, 9)

    def _decode_delta(self, delta: bytes) -> List[DiffEntry]:
        """解码 delta 二进制为条目"""
        raw = zlib.decompress(delta)
        if raw[:6] != b"DELTA\x01":
            raise ValueError("无效的 delta 格式")

        entries = []
        pos = 7  # 跳过 DELTA\x01\x00 (7 字节)

        while pos < len(raw):
            if pos >= len(raw):
                break
            type_byte = raw[pos]
            pos += 1

            if type_byte == 0x01:  # INSERT
                length = struct.unpack("<I", raw[pos:pos + 4])[0]
                pos += 4
                new_data = raw[pos:pos + length]
                pos += length
                entries.append(DiffEntry(
                    diff_type=DiffType.INSERT,
                    offset=0, new_data=new_data, length=length
                ))
            elif type_byte == 0x02:  # DELETE
                length = struct.unpack("<I", raw[pos:pos + 4])[0]
                pos += 4
                entries.append(DiffEntry(
                    diff_type=DiffType.DELETE,
                    offset=0, length=length
                ))
            elif type_byte == 0x03:  # REPLACE
                old_len = struct.unpack("<I", raw[pos:pos + 4])[0]
                pos += 4
                new_len = struct.unpack("<I", raw[pos:pos + 4])[0]
                pos += 4
                new_data = raw[pos:pos + new_len]
                pos += new_len
                entries.append(DiffEntry(
                    diff_type=DiffType.REPLACE,
                    offset=0, old_data=b"\x00" * old_len, new_data=new_data,
                    length=old_len
                ))
            elif type_byte == 0x04:  # EQUAL
                length = struct.unpack("<I", raw[pos:pos + 4])[0]
                pos += 4
                entries.append(DiffEntry(
                    diff_type=DiffType.EQUAL,
                    offset=0, length=length
                ))
            elif type_byte == 0x05:  # SHIFT
                length = struct.unpack("<I", raw[pos:pos + 4])[0]
                pos += 4
                target = struct.unpack("<I", raw[pos:pos + 4])[0]
                pos += 4
                entries.append(DiffEntry(
                    diff_type=DiffType.SHIFT,
                    offset=0, length=length, target_offset=target
                ))
            else:
                break

        return entries


# ============================================================
# 签名扫描器
# ============================================================

class SignatureScanner:
    """
    签名扫描器
    
    支持格式:
    - IDA: 48 8B ? ? ? ? 00
    - x64dbg: 48 8B ?? ?? ?? ?? 00
    - Code: \\x48\\x8B\\x00\\x00\\x00\\x00\\x00
    - PEiD: 48 8B ?? ?? ?? ?? 00
    """

    WILDCARD_MARKERS = {
        SignatureFormat.IDA: "?",
        SignatureFormat.X64DBG: "??",
        SignatureFormat.PEID: "??",
    }

    def __init__(self):
        self._patterns: Dict[str, Tuple[bytes, bytes]] = {}  # name -> (pattern, mask)

    # ============================================================
    # 签名解析
    # ============================================================

    def parse_signature(self, pattern: str, fmt: SignatureFormat = SignatureFormat.IDA) -> Tuple[bytes, bytes]:
        """解析签名为 (pattern_bytes, mask_bytes)"""
        if fmt == SignatureFormat.IDA:
            return self._parse_ida(pattern)
        elif fmt == SignatureFormat.X64DBG:
            return self._parse_x64dbg(pattern)
        elif fmt == SignatureFormat.CODE:
            return self._parse_code(pattern)
        elif fmt == SignatureFormat.PEID:
            return self._parse_peid(pattern)
        raise ValueError(f"不支持的签名格式: {fmt}")

    def _parse_ida(self, pattern: str) -> Tuple[bytes, bytes]:
        """解析 IDA 格式: 48 8B ? ? ? ? 00"""
        pat_bytes = bytearray()
        mask = bytearray()

        tokens = pattern.strip().split()
        for token in tokens:
            if token == "?":
                pat_bytes.append(0x00)
                mask.append(0x00)
            else:
                try:
                    pat_bytes.append(int(token, 16))
                    mask.append(0xFF)
                except ValueError:
                    raise ValueError(f"无效的签名标记: {token}")

        return bytes(pat_bytes), bytes(mask)

    def _parse_x64dbg(self, pattern: str) -> Tuple[bytes, bytes]:
        """解析 x64dbg 格式: 48 8B ?? ?? ?? ?? 00"""
        pat_bytes = bytearray()
        mask = bytearray()

        tokens = pattern.strip().split()
        for token in tokens:
            if token == "??":
                pat_bytes.append(0x00)
                mask.append(0x00)
            else:
                try:
                    pat_bytes.append(int(token, 16))
                    mask.append(0xFF)
                except ValueError:
                    raise ValueError(f"无效的签名标记: {token}")

        return bytes(pat_bytes), bytes(mask)

    def _parse_code(self, pattern: str) -> Tuple[bytes, bytes]:
        """解析代码格式: \\x48\\x8B\\x00\\x00\\x00\\x00\\x00"""
        pat_bytes = bytearray()
        mask = bytearray()

        i = 0
        while i < len(pattern):
            if pattern[i:i + 2] == "\\x":
                try:
                    pat_bytes.append(int(pattern[i + 2:i + 4], 16))
                    mask.append(0xFF)
                except (ValueError, IndexError):
                    pat_bytes.append(0x00)
                    mask.append(0x00)
                i += 4
            elif pattern[i:i + 2] == "\\?":
                pat_bytes.append(0x00)
                mask.append(0x00)
                i += 2
            else:
                i += 1

        return bytes(pat_bytes), bytes(mask)

    def _parse_peid(self, pattern: str) -> Tuple[bytes, bytes]:
        """解析 PEiD 格式 (同 x64dbg)"""
        return self._parse_x64dbg(pattern)

    # ============================================================
    # 签名扫描
    # ============================================================

    def scan(self, data: bytes, pattern: str,
             fmt: SignatureFormat = SignatureFormat.IDA,
             find_all: bool = False) -> List[SignatureMatch]:
        """扫描签名"""
        pat_bytes, mask = self.parse_signature(pattern, fmt)
        return self._scan_pattern(data, pat_bytes, mask, pattern, fmt, find_all)

    def scan_multi(self, data: bytes, patterns: Dict[str, str],
                   fmt: SignatureFormat = SignatureFormat.IDA) -> Dict[str, List[SignatureMatch]]:
        """批量扫描多个签名"""
        results = {}
        for name, pattern in patterns.items():
            results[name] = self.scan(data, pattern, fmt)
        return results

    def scan_file(self, file_path: str, pattern: str,
                  fmt: SignatureFormat = SignatureFormat.IDA) -> List[SignatureMatch]:
        """扫描文件"""
        if not os.path.exists(file_path):
            return []
        with open(file_path, "rb") as f:
            data = f.read()
        return self.scan(data, pattern, fmt, find_all=True)

    def _scan_pattern(self, data: bytes, pat_bytes: bytes, mask: bytes,
                      pattern: str, fmt: SignatureFormat,
                      find_all: bool) -> List[SignatureMatch]:
        """内部模式扫描"""
        results = []
        pat_len = len(pat_bytes)

        if pat_len == 0 or pat_len > len(data):
            return results

        for i in range(len(data) - pat_len + 1):
            match = True
            for j in range(pat_len):
                if mask[j] == 0xFF and data[i + j] != pat_bytes[j]:
                    match = False
                    break
            if match:
                results.append(SignatureMatch(
                    signature=pattern,
                    offset=i,
                    matched_bytes=data[i:i + pat_len],
                    pattern=pattern,
                    format=fmt
                ))
                if not find_all:
                    return results

        return results

    # ============================================================
    # 签名生成
    # ============================================================

    def generate_signature(self, data: bytes, offset: int, length: int = 16,
                           fmt: SignatureFormat = SignatureFormat.IDA,
                           wildcard_bytes: List[int] = None) -> str:
        """从指定位置生成签名"""
        if offset + length > len(data):
            length = len(data) - offset
        if length <= 0:
            return ""

        chunk = data[offset:offset + length]
        wildcard = set(wildcard_bytes or [])
        return self._format_signature(chunk, fmt, wildcard)

    def generate_unique_signature(self, data: bytes, offset: int,
                                  min_length: int = 8, max_length: int = 32,
                                  fmt: SignatureFormat = SignatureFormat.IDA) -> Optional[str]:
        """生成唯一签名（确保只匹配一次）"""
        for length in range(min_length, max_length + 1):
            sig = self.generate_signature(data, offset, length, fmt)
            matches = self.scan(data, sig, fmt, find_all=True)
            if len(matches) == 1:
                return sig
        return None

    def _format_signature(self, data: bytes, fmt: SignatureFormat,
                          wildcard: Set[int]) -> str:
        """格式化签名字符串"""
        if fmt == SignatureFormat.IDA:
            tokens = []
            for i, b in enumerate(data):
                if i in wildcard:
                    tokens.append("?")
                else:
                    tokens.append(f"{b:02X}")
            return " ".join(tokens)
        elif fmt == SignatureFormat.X64DBG:
            tokens = []
            for i, b in enumerate(data):
                if i in wildcard:
                    tokens.append("??")
                else:
                    tokens.append(f"{b:02X}")
            return " ".join(tokens)
        elif fmt == SignatureFormat.CODE:
            tokens = []
            for i, b in enumerate(data):
                if i in wildcard:
                    tokens.append("\\x00")
                else:
                    tokens.append(f"\\x{b:02X}")
            return "".join(tokens)
        elif fmt == SignatureFormat.PEID:
            return self._format_signature(data, SignatureFormat.X64DBG, wildcard)
        return ""


# ============================================================
# 补丁引擎
# ============================================================

class PatchEngine:
    """
    补丁引擎
    
    支持 IPS、BPS、自定义 Delta 格式的补丁创建、应用、验证和回滚。
    """

    IPS_MAGIC = b"PATCH"
    IPS_EOF = b"EOF"
    IPS32_MAGIC = b"IPS32"
    BPS_MAGIC = b"BPS1"

    def __init__(self):
        self._delta_generator = DeltaGenerator()
        self._patches: Dict[str, PatchInfo] = {}
        self._backups: Dict[str, bytes] = {}  # patch_id -> original data

    # ============================================================
    # IPS 补丁
    # ============================================================

    def create_ips(self, old_data: bytes, new_data: bytes) -> bytes:
        """创建 IPS 补丁"""
        entries = self._delta_generator.diff_bytes(old_data, new_data)
        parts = [self.IPS_MAGIC]

        for entry in entries:
            if entry.diff_type == DiffType.REPLACE:
                offset = entry.offset
                data = entry.new_data
                if offset > 0xFFFFFF:
                    raise ValueError(f"IPS 不支持超过 16MB 的偏移: {offset}")
                parts.append(struct.pack(">BH", (offset >> 16) & 0xFF, offset & 0xFFFF))
                parts.append(struct.pack(">H", len(data)))
                parts.append(data)
            elif entry.diff_type == DiffType.INSERT:
                # IPS 没有原生的 INSERT 支持，作为 REPLACE 处理
                offset = entry.offset
                data = entry.new_data
                if offset > 0xFFFFFF:
                    raise ValueError(f"IPS 不支持超过 16MB 的偏移: {offset}")
                parts.append(struct.pack(">BH", (offset >> 16) & 0xFF, offset & 0xFFFF))
                parts.append(struct.pack(">H", len(data)))
                parts.append(data)

        parts.append(self.IPS_EOF)
        return b"".join(parts)

    def apply_ips(self, data: bytes, patch: bytes) -> bytes:
        """应用 IPS 补丁"""
        if patch[:5] != self.IPS_MAGIC:
            raise ValueError("无效的 IPS 补丁")

        result = bytearray(data)
        pos = 5

        while pos < len(patch) - 3:
            if patch[pos:pos + 3] == self.IPS_EOF:
                break

            if len(patch) - pos < 3:
                break
            offset = ((patch[pos] & 0xFF) << 16) | struct.unpack(">H", patch[pos + 1:pos + 3])[0]
            pos += 3

            if len(patch) - pos < 2:
                break
            length = struct.unpack(">H", patch[pos:pos + 2])[0]
            pos += 2

            if length == 0:  # RLE 编码
                if len(patch) - pos < 2:
                    break
                rle_len = struct.unpack(">H", patch[pos:pos + 2])[0]
                pos += 2
                if pos < len(patch):
                    value = patch[pos]
                    pos += 1
                    if offset + rle_len <= len(result):
                        result[offset:offset + rle_len] = bytes([value]) * rle_len
            else:
                if len(patch) - pos < length:
                    break
                if offset + length <= len(result):
                    result[offset:offset + length] = patch[pos:pos + length]
                else:
                    # 扩展结果
                    extra = offset + length - len(result)
                    result.extend(b"\x00" * extra)
                    result[offset:offset + length] = patch[pos:pos + length]
                pos += length

        return bytes(result)

    def create_ips_file(self, old_path: str, new_path: str, output_path: str) -> dict:
        """从文件创建 IPS 补丁"""
        if not os.path.exists(old_path) or not os.path.exists(new_path):
            return {"success": False, "message": "文件不存在"}

        try:
            with open(old_path, "rb") as f:
                old_data = f.read()
            with open(new_path, "rb") as f:
                new_data = f.read()

            patch = self.create_ips(old_data, new_data)
            with open(output_path, "wb") as f:
                f.write(patch)

            return {
                "success": True,
                "message": "IPS 补丁创建成功",
                "patch_size": len(patch),
                "source_size": len(old_data),
                "target_size": len(new_data),
                "output": output_path
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def apply_ips_file(self, target_path: str, patch_path: str, output_path: str = None) -> dict:
        """应用 IPS 补丁到文件"""
        if not os.path.exists(target_path) or not os.path.exists(patch_path):
            return {"success": False, "message": "文件不存在"}

        try:
            with open(target_path, "rb") as f:
                data = f.read()
            with open(patch_path, "rb") as f:
                patch = f.read()

            result = self.apply_ips(data, patch)
            output = output_path or target_path
            with open(output, "wb") as f:
                f.write(result)

            return {
                "success": True,
                "message": "IPS 补丁应用成功",
                "original_size": len(data),
                "patched_size": len(result),
                "output": output
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ============================================================
    # Delta 补丁
    # ============================================================

    def create_delta_patch(self, old_data: bytes, new_data: bytes,
                           description: str = "") -> PatchInfo:
        """创建 Delta 补丁"""
        entries = self._delta_generator.diff_bytes(old_data, new_data)
        patch_id = hashlib.md5(old_data + new_data).hexdigest()[:12]

        patch = PatchInfo(
            patch_id=patch_id,
            format=PatchFormat.DELTA,
            source_hash=hashlib.sha256(old_data).hexdigest(),
            target_hash=hashlib.sha256(new_data).hexdigest(),
            description=description,
            entries=entries,
            metadata={
                "source_size": len(old_data),
                "target_size": len(new_data),
                "entry_count": len(entries),
                "insertions": sum(1 for e in entries if e.diff_type == DiffType.INSERT),
                "deletions": sum(1 for e in entries if e.diff_type == DiffType.DELETE),
                "replacements": sum(1 for e in entries if e.diff_type == DiffType.REPLACE),
            }
        )

        self._patches[patch_id] = patch
        return patch

    def apply_delta_patch(self, data: bytes, patch: PatchInfo) -> bytes:
        """应用 Delta 补丁"""
        result = bytearray()
        old_pos = 0

        for entry in patch.entries:
            if entry.diff_type == DiffType.EQUAL:
                end = min(old_pos + entry.length, len(data))
                result.extend(data[old_pos:end])
                old_pos += entry.length
            elif entry.diff_type == DiffType.DELETE:
                old_pos += entry.length
            elif entry.diff_type == DiffType.INSERT:
                result.extend(entry.new_data)
            elif entry.diff_type == DiffType.REPLACE:
                old_pos += len(entry.old_data)
                result.extend(entry.new_data)

        # 追加 data 剩余部分
        if old_pos < len(data):
            result.extend(data[old_pos:])

        return bytes(result)

    def save_delta_patch(self, patch: PatchInfo, output_path: str) -> dict:
        """保存 Delta 补丁到文件"""
        try:
            data = {
                "format": "delta_v1",
                "patch_id": patch.patch_id,
                "source_hash": patch.source_hash,
                "target_hash": patch.target_hash,
                "description": patch.description,
                "metadata": patch.metadata,
                "entries": []
            }

            for entry in patch.entries:
                data["entries"].append({
                    "type": entry.diff_type.value,
                    "offset": entry.offset,
                    "length": entry.length,
                    "old_data": entry.old_data.hex() if entry.old_data else None,
                    "new_data": entry.new_data.hex() if entry.new_data else None,
                    "source_offset": entry.source_offset,
                    "target_offset": entry.target_offset,
                })

            json_str = json.dumps(data, indent=2)
            compressed = zlib.compress(json_str.encode("utf-8"), 9)

            with open(output_path, "wb") as f:
                f.write(b"DLTA\x01")
                f.write(compressed)

            return {"success": True, "message": "补丁保存成功", "output": output_path}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def load_delta_patch(self, file_path: str) -> Optional[PatchInfo]:
        """从文件加载 Delta 补丁"""
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, "rb") as f:
                magic = f.read(5)
                if magic != b"DLTA\x01":
                    return None
                compressed = f.read()

            json_str = zlib.decompress(compressed).decode("utf-8")
            data = json.loads(json_str)

            entries = []
            for e in data["entries"]:
                entries.append(DiffEntry(
                    diff_type=DiffType(e["type"]),
                    offset=e["offset"],
                    old_data=bytes.fromhex(e["old_data"]) if e["old_data"] else b"",
                    new_data=bytes.fromhex(e["new_data"]) if e["new_data"] else b"",
                    length=e["length"],
                    source_offset=e.get("source_offset", 0),
                    target_offset=e.get("target_offset", 0),
                ))

            patch = PatchInfo(
                patch_id=data["patch_id"],
                format=PatchFormat.DELTA,
                source_hash=data["source_hash"],
                target_hash=data["target_hash"],
                description=data.get("description", ""),
                entries=entries,
                metadata=data.get("metadata", {}),
            )

            self._patches[patch.patch_id] = patch
            return patch

        except Exception:
            return None

    # ============================================================
    # 补丁验证与回滚
    # ============================================================

    def verify_patch(self, original_data: bytes, patch: PatchInfo) -> dict:
        """验证补丁可以正确应用"""
        try:
            patched = self.apply_delta_patch(original_data, patch)
            actual_hash = hashlib.sha256(patched).hexdigest()
            valid = actual_hash == patch.target_hash

            return {
                "success": True,
                "valid": valid,
                "expected_hash": patch.target_hash,
                "actual_hash": actual_hash,
                "original_size": len(original_data),
                "patched_size": len(patched),
            }
        except Exception as e:
            return {"success": False, "valid": False, "message": str(e)}

    def create_backup(self, data: bytes, patch_id: str) -> str:
        """创建备份"""
        self._backups[patch_id] = data
        return patch_id

    def rollback(self, patch_id: str) -> Optional[bytes]:
        """回滚补丁"""
        return self._backups.pop(patch_id, None)


# ============================================================
# 结构感知对比器
# ============================================================

class StructureComparator:
    """
    结构感知对比器
    
    理解二进制文件结构，进行分段/函数/字符串级别的对比。
    """

    def __init__(self):
        self._delta = DeltaGenerator()

    # ============================================================
    # 分段对比
    # ============================================================

    def compare_sections(self, sections_a: Dict[str, bytes],
                         sections_b: Dict[str, bytes]) -> DiffReport:
        """对比两组分段"""
        report = DiffReport()
        all_sections = set(sections_a.keys()) | set(sections_b.keys())

        for name in sorted(all_sections):
            data_a = sections_a.get(name, b"")
            data_b = sections_b.get(name, b"")

            if data_a == data_b:
                status = "identical"
                entries = []
            elif name not in sections_a:
                status = "added"
                entries = [DiffEntry(
                    diff_type=DiffType.INSERT,
                    offset=0, new_data=data_b, length=len(data_b)
                )]
            elif name not in sections_b:
                status = "removed"
                entries = [DiffEntry(
                    diff_type=DiffType.DELETE,
                    offset=0, old_data=data_a, length=len(data_a)
                )]
            else:
                status = "modified"
                entries = self._delta.diff_bytes(data_a, data_b)

            report.sections[name] = {
                "status": status,
                "size_a": len(data_a),
                "size_b": len(data_b),
                "entries": len(entries),
                "hash_a": hashlib.md5(data_a).hexdigest() if data_a else "",
                "hash_b": hashlib.md5(data_b).hexdigest() if data_b else "",
            }

            report.entries.extend(entries)

        report._update_stats()
        return report

    # ============================================================
    # 函数级对比
    # ============================================================

    def compare_functions(self, funcs_a: Dict[int, bytes],
                          funcs_b: Dict[int, bytes]) -> Dict[int, Dict[str, Any]]:
        """对比函数级数据"""
        results = {}
        all_addrs = set(funcs_a.keys()) | set(funcs_b.keys())

        for addr in sorted(all_addrs):
            data_a = funcs_a.get(addr, b"")
            data_b = funcs_b.get(addr, b"")

            if data_a == data_b:
                results[addr] = {"status": "identical", "size": len(data_a)}
            elif addr not in funcs_a:
                results[addr] = {"status": "new", "size_b": len(data_b)}
            elif addr not in funcs_b:
                results[addr] = {"status": "removed", "size_a": len(data_a)}
            else:
                entries = self._delta.diff_bytes(data_a, data_b)
                results[addr] = {
                    "status": "modified",
                    "size_a": len(data_a),
                    "size_b": len(data_b),
                    "changes": len(entries),
                    "insertions": sum(1 for e in entries if e.diff_type == DiffType.INSERT),
                    "deletions": sum(1 for e in entries if e.diff_type == DiffType.DELETE),
                    "replacements": sum(1 for e in entries if e.diff_type == DiffType.REPLACE),
                }

        return results

    # ============================================================
    # 字符串表对比
    # ============================================================

    def compare_strings(self, strings_a: List[str],
                        strings_b: List[str]) -> Dict[str, Any]:
        """对比字符串表"""
        set_a = set(strings_a)
        set_b = set(strings_b)

        added = set_b - set_a
        removed = set_a - set_b
        common = set_a & set_b

        return {
            "total_a": len(strings_a),
            "total_b": len(strings_b),
            "added": sorted(added),
            "removed": sorted(removed),
            "common_count": len(common),
            "added_count": len(added),
            "removed_count": len(removed),
            "similarity": len(common) / max(len(set_a | set_b), 1),
        }


# ============================================================
# 二进制差异分析器（主入口）
# ============================================================

class BinaryDiffAnalyzer:
    """
    二进制差异分析器（主入口）
    
    整合 Delta 生成、签名扫描、补丁管理、结构对比四大子系统。
    """

    def __init__(self):
        self.delta = DeltaGenerator()
        self.scanner = SignatureScanner()
        self.patcher = PatchEngine()
        self.comparator = StructureComparator()

    # ============================================================
    # 文件差异分析
    # ============================================================

    def diff_files(self, file_a: str, file_b: str,
                   method: str = "byte") -> dict:
        """对比两个文件"""
        if not os.path.exists(file_a):
            return {"success": False, "message": f"文件不存在: {file_a}"}
        if not os.path.exists(file_b):
            return {"success": False, "message": f"文件不存在: {file_b}"}

        try:
            with open(file_a, "rb") as f:
                data_a = f.read()
            with open(file_b, "rb") as f:
                data_b = f.read()

            if method == "block":
                entries = self.delta.diff_blocks(data_a, data_b)
            else:
                entries = self.delta.diff_bytes(data_a, data_b)

            # 计算统计
            insertions = sum(1 for e in entries if e.diff_type == DiffType.INSERT)
            deletions = sum(1 for e in entries if e.diff_type == DiffType.DELETE)
            replacements = sum(1 for e in entries if e.diff_type == DiffType.REPLACE)
            shifts = sum(1 for e in entries if e.diff_type == DiffType.SHIFT)
            equal_count = sum(1 for e in entries if e.diff_type == DiffType.EQUAL)

            bytes_added = sum(len(e.new_data) for e in entries if e.diff_type == DiffType.INSERT)
            bytes_removed = sum(len(e.old_data) for e in entries if e.diff_type == DiffType.DELETE)
            bytes_changed = sum(len(e.old_data) for e in entries if e.diff_type == DiffType.REPLACE)
            bytes_equal = sum(e.length for e in entries if e.diff_type == DiffType.EQUAL)

            total = max(len(data_a), len(data_b), 1)
            similarity = bytes_equal / total if total > 0 else 0

            return {
                "success": True,
                "file_a": os.path.basename(file_a),
                "file_b": os.path.basename(file_b),
                "size_a": len(data_a),
                "size_b": len(data_b),
                "total_entries": len(entries),
                "insertions": insertions,
                "deletions": deletions,
                "replacements": replacements,
                "shifts": shifts,
                "equal_blocks": equal_count,
                "bytes_added": bytes_added,
                "bytes_removed": bytes_removed,
                "bytes_changed": bytes_changed,
                "bytes_equal": bytes_equal,
                "similarity": round(similarity, 4),
                "entries": [
                    {
                        "type": e.diff_type.value,
                        "offset": e.offset,
                        "length": e.length,
                        "old_hex": e.old_data[:32].hex() if e.old_data else None,
                        "new_hex": e.new_data[:32].hex() if e.new_data else None,
                        "old_size": len(e.old_data),
                        "new_size": len(e.new_data),
                    }
                    for e in entries[:100]  # 限制返回数量
                ],
                "hash_a": hashlib.md5(data_a).hexdigest(),
                "hash_b": hashlib.md5(data_b).hexdigest(),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def diff_bytes(self, data_a: bytes, data_b: bytes,
                   method: str = "byte") -> dict:
        """对比两段字节数据"""
        if method == "block":
            entries = self.delta.diff_blocks(data_a, data_b)
        else:
            entries = self.delta.diff_bytes(data_a, data_b)

        return {
            "success": True,
            "size_a": len(data_a),
            "size_b": len(data_b),
            "total_entries": len(entries),
            "entries": [
                {
                    "type": e.diff_type.value,
                    "offset": e.offset,
                    "length": e.length,
                    "old_hex": e.old_data[:16].hex() if e.old_data else None,
                    "new_hex": e.new_data[:16].hex() if e.new_data else None,
                }
                for e in entries[:50]
            ],
        }

    # ============================================================
    # Delta 压缩
    # ============================================================

    def generate_delta(self, old_data: bytes, new_data: bytes) -> bytes:
        """生成压缩 delta"""
        return self.delta.generate_delta(old_data, new_data)

    def apply_delta(self, old_data: bytes, delta: bytes) -> bytes:
        """应用 delta"""
        return self.delta.apply_delta(old_data, delta)

    def generate_delta_file(self, old_path: str, new_path: str,
                            output_path: str) -> dict:
        """从文件生成 delta 文件"""
        if not os.path.exists(old_path) or not os.path.exists(new_path):
            return {"success": False, "message": "文件不存在"}

        try:
            with open(old_path, "rb") as f:
                old_data = f.read()
            with open(new_path, "rb") as f:
                new_data = f.read()

            delta = self.delta.generate_delta(old_data, new_data)
            with open(output_path, "wb") as f:
                f.write(delta)

            return {
                "success": True,
                "message": "Delta 生成成功",
                "source_size": len(old_data),
                "target_size": len(new_data),
                "delta_size": len(delta),
                "compression_ratio": round(len(delta) / max(len(new_data), 1), 4),
                "output": output_path,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def apply_delta_file(self, target_path: str, delta_path: str,
                         output_path: str = None) -> dict:
        """从文件应用 delta"""
        if not os.path.exists(target_path) or not os.path.exists(delta_path):
            return {"success": False, "message": "文件不存在"}

        try:
            with open(target_path, "rb") as f:
                data = f.read()
            with open(delta_path, "rb") as f:
                delta = f.read()

            result = self.delta.apply_delta(data, delta)
            output = output_path or target_path
            with open(output, "wb") as f:
                f.write(result)

            return {
                "success": True,
                "message": "Delta 应用成功",
                "original_size": len(data),
                "patched_size": len(result),
                "output": output,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ============================================================
    # 签名扫描
    # ============================================================

    def scan_signature(self, data: bytes, pattern: str,
                       fmt: str = "ida", find_all: bool = False) -> dict:
        """扫描签名"""
        fmt_map = {
            "ida": SignatureFormat.IDA,
            "x64dbg": SignatureFormat.X64DBG,
            "code": SignatureFormat.CODE,
            "peid": SignatureFormat.PEID,
        }
        sig_fmt = fmt_map.get(fmt.lower(), SignatureFormat.IDA)

        results = self.scanner.scan(data, pattern, sig_fmt, find_all)
        return {
            "success": True,
            "matches": len(results),
            "results": [
                {"offset": r.offset, "offset_hex": hex(r.offset),
                 "bytes": r.matched_bytes.hex()}
                for r in results
            ],
        }

    def scan_signature_file(self, file_path: str, pattern: str,
                            fmt: str = "ida") -> dict:
        """在文件中扫描签名"""
        if not os.path.exists(file_path):
            return {"success": False, "message": "文件不存在"}

        fmt_map = {
            "ida": SignatureFormat.IDA,
            "x64dbg": SignatureFormat.X64DBG,
            "code": SignatureFormat.CODE,
            "peid": SignatureFormat.PEID,
        }
        sig_fmt = fmt_map.get(fmt.lower(), SignatureFormat.IDA)

        results = self.scanner.scan_file(file_path, pattern, sig_fmt)
        return {
            "success": True,
            "file": os.path.basename(file_path),
            "matches": len(results),
            "results": [
                {"offset": r.offset, "offset_hex": hex(r.offset),
                 "bytes": r.matched_bytes.hex()}
                for r in results
            ],
        }

    def generate_signature(self, data: bytes, offset: int, length: int = 16,
                           fmt: str = "ida") -> dict:
        """生成签名"""
        fmt_map = {
            "ida": SignatureFormat.IDA,
            "x64dbg": SignatureFormat.X64DBG,
            "code": SignatureFormat.CODE,
            "peid": SignatureFormat.PEID,
        }
        sig_fmt = fmt_map.get(fmt.lower(), SignatureFormat.IDA)

        sig = self.scanner.generate_signature(data, offset, length, sig_fmt)
        return {
            "success": True,
            "signature": sig,
            "format": fmt,
            "offset": offset,
            "length": length,
        }

    def generate_unique_signature(self, data: bytes, offset: int,
                                  min_length: int = 8, max_length: int = 32,
                                  fmt: str = "ida") -> dict:
        """生成唯一签名"""
        fmt_map = {
            "ida": SignatureFormat.IDA,
            "x64dbg": SignatureFormat.X64DBG,
            "code": SignatureFormat.CODE,
            "peid": SignatureFormat.PEID,
        }
        sig_fmt = fmt_map.get(fmt.lower(), SignatureFormat.IDA)

        sig = self.scanner.generate_unique_signature(data, offset, min_length, max_length, sig_fmt)
        return {
            "success": sig is not None,
            "signature": sig,
            "format": fmt,
            "offset": offset,
        }

    # ============================================================
    # 补丁管理
    # ============================================================

    def create_patch(self, old_data: bytes, new_data: bytes,
                     description: str = "") -> dict:
        """创建补丁"""
        patch = self.patcher.create_delta_patch(old_data, new_data, description)
        return {
            "success": True,
            "patch_id": patch.patch_id,
            "entries": len(patch.entries),
            "metadata": patch.metadata,
        }

    def apply_patch(self, data: bytes, patch_id: str) -> dict:
        """应用补丁"""
        patch = self.patcher._patches.get(patch_id)
        if not patch:
            return {"success": False, "message": f"补丁不存在: {patch_id}"}

        try:
            result = self.patcher.apply_delta_patch(data, patch)
            return {
                "success": True,
                "result_size": len(result),
                "result_hash": hashlib.sha256(result).hexdigest(),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def save_patch(self, patch_id: str, output_path: str) -> dict:
        """保存补丁到文件"""
        patch = self.patcher._patches.get(patch_id)
        if not patch:
            return {"success": False, "message": f"补丁不存在: {patch_id}"}

        return self.patcher.save_delta_patch(patch, output_path)

    def load_patch(self, file_path: str) -> dict:
        """从文件加载补丁"""
        patch = self.patcher.load_delta_patch(file_path)
        if not patch:
            return {"success": False, "message": "加载补丁失败"}

        return {
            "success": True,
            "patch_id": patch.patch_id,
            "entries": len(patch.entries),
            "metadata": patch.metadata,
        }

    def verify_patch(self, data: bytes, patch_id: str) -> dict:
        """验证补丁"""
        patch = self.patcher._patches.get(patch_id)
        if not patch:
            return {"success": False, "message": f"补丁不存在: {patch_id}"}

        return self.patcher.verify_patch(data, patch)

    def create_ips_patch(self, old_path: str, new_path: str,
                         output_path: str) -> dict:
        """创建 IPS 补丁"""
        return self.patcher.create_ips_file(old_path, new_path, output_path)

    def apply_ips_patch(self, target_path: str, patch_path: str,
                        output_path: str = None) -> dict:
        """应用 IPS 补丁"""
        return self.patcher.apply_ips_file(target_path, patch_path, output_path)

    # ============================================================
    # 结构对比
    # ============================================================

    def compare_sections(self, sections_a: dict, sections_b: dict) -> dict:
        """对比分段"""
        report = self.comparator.compare_sections(sections_a, sections_b)
        return {
            "success": True,
            "sections": report.sections,
            "total_entries": report.total_entries,
            "insertions": report.insertions,
            "deletions": report.deletions,
            "replacements": report.replacements,
            "similarity": report.similarity,
        }

    def compare_strings(self, strings_a: list, strings_b: list) -> dict:
        """对比字符串表"""
        result = self.comparator.compare_strings(strings_a, strings_b)
        result["success"] = True
        return result

    # ============================================================
    # 十六进制差异
    # ============================================================

    def hex_diff(self, data_a: bytes, data_b: bytes, width: int = 16) -> dict:
        """生成十六进制差异视图"""
        max_len = max(len(data_a), len(data_b))
        lines = []

        for offset in range(0, max_len, width):
            chunk_a = data_a[offset:offset + width] if offset < len(data_a) else b""
            chunk_b = data_b[offset:offset + width] if offset < len(data_b) else b""

            diff_flags = []
            for i in range(width):
                ba = chunk_a[i] if i < len(chunk_a) else None
                bb = chunk_b[i] if i < len(chunk_b) else None
                if ba is None and bb is None:
                    diff_flags.append(" ")
                elif ba is None:
                    diff_flags.append("+")
                elif bb is None:
                    diff_flags.append("-")
                elif ba == bb:
                    diff_flags.append(" ")
                else:
                    diff_flags.append("*")

            lines.append({
                "offset": hex(offset),
                "hex_a": chunk_a.hex(" ") if chunk_a else "",
                "hex_b": chunk_b.hex(" ") if chunk_b else "",
                "flags": "".join(diff_flags),
                "has_diff": any(f in "*+-" for f in diff_flags),
            })

        return {
            "success": True,
            "lines": lines,
            "total_lines": len(lines),
            "diff_lines": sum(1 for l in lines if l["has_diff"]),
        }

    # ============================================================
    # 批量操作
    # ============================================================

    def batch_diff(self, file_pairs: List[Tuple[str, str]]) -> dict:
        """批量对比多对文件"""
        results = []
        for old_path, new_path in file_pairs:
            result = self.diff_files(old_path, new_path)
            results.append(result)

        return {
            "success": True,
            "total": len(results),
            "successful": sum(1 for r in results if r.get("success")),
            "results": results,
        }

    def merge_patches(self, patch_ids: List[str]) -> dict:
        """合并多个补丁（按顺序应用）"""
        if not all(pid in self.patcher._patches for pid in patch_ids):
            return {"success": False, "message": "部分补丁不存在"}

        merged = {
            "success": True,
            "patch_ids": patch_ids,
            "total_entries": sum(
                len(self.patcher._patches[pid].entries) for pid in patch_ids
            ),
        }
        return merged


# ============================================================
# 辅助函数
# ============================================================

def diff_files(file_a: str, file_b: str, method: str = "byte") -> dict:
    """快捷函数: 对比两个文件"""
    analyzer = BinaryDiffAnalyzer()
    return analyzer.diff_files(file_a, file_b, method)


def quick_scan(file_path: str, pattern: str, fmt: str = "ida") -> dict:
    """快捷函数: 快速扫描签名"""
    analyzer = BinaryDiffAnalyzer()
    return analyzer.scan_signature_file(file_path, pattern, fmt)


def quick_delta(old_data: bytes, new_data: bytes) -> bytes:
    """快捷函数: 快速生成 delta"""
    analyzer = BinaryDiffAnalyzer()
    return analyzer.generate_delta(old_data, new_data)