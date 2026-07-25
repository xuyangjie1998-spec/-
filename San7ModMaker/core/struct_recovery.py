#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
结构体恢复引擎 (Structure Recovery Engine)
===========================================

引擎突破20: 结构体恢复引擎

从二进制代码中恢复 C/C++ 的 struct/class 定义。
通过分析内存访问模式和虚函数表，重建结构体布局、推断字段类型、
解析虚函数、分析类继承关系，并生成可编译的 C/C++ 头文件。

核心能力:
  - 从汇编指令中提取结构体字段访问模式
  - 推断字段类型（整数、浮点、指针、字符串等）
  - 解析虚函数表 (vtable) 并恢复虚函数信息
  - 分析类继承关系和类层次结构
  - 生成 C/C++ 结构体/类定义和 IDA Pro 导入脚本

使用示例:
    >>> from struct_recovery import StructRecoveryEngine
    >>> engine = StructRecoveryEngine()
    >>> structs = engine.recover_from_asm(asm_text, base_address=0x400000)
    >>> header = engine.generate_header(structs, vtables)

作者: San7ModMaker Team
版本: 1.0.0
"""

from __future__ import annotations

import re
import json
import struct as py_struct
import math
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any, Dict, FrozenSet, List, Optional, Set, Tuple, Union,
)

# ============================================================================
# 枚举定义
# ============================================================================

class MemberType(Enum):
    """结构体成员类型枚举。覆盖 C/C++ 中常见的字段类型。"""
    INT8 = auto()          # int8_t / char (signed)
    INT16 = auto()         # int16_t / short
    INT32 = auto()         # int32_t / int
    INT64 = auto()         # int64_t / long long
    UINT8 = auto()         # uint8_t / unsigned char
    UINT16 = auto()        # uint16_t / unsigned short
    UINT32 = auto()        # uint32_t / unsigned int
    UINT64 = auto()        # uint64_t / unsigned long long
    FLOAT = auto()         # float (32-bit IEEE 754)
    DOUBLE = auto()        # double (64-bit IEEE 754)
    POINTER = auto()       # void* / typed pointer
    CHAR_ARRAY = auto()    # char[] / ASCII string buffer
    WCHAR_ARRAY = auto()   # wchar_t[] / wide string buffer
    VTABLE_PTR = auto()    # 虚函数表指针 (vfptr)
    FUNCTION_PTR = auto()  # 函数指针
    BITFIELD = auto()      # 位域
    PADDING = auto()       # 对齐填充字节
    UNKNOWN = auto()       # 未知类型

    @property
    def c_type_name(self) -> str:
        _map: Dict[MemberType, str] = {
            MemberType.INT8: "int8_t", MemberType.INT16: "int16_t",
            MemberType.INT32: "int32_t", MemberType.INT64: "int64_t",
            MemberType.UINT8: "uint8_t", MemberType.UINT16: "uint16_t",
            MemberType.UINT32: "uint32_t", MemberType.UINT64: "uint64_t",
            MemberType.FLOAT: "float", MemberType.DOUBLE: "double",
            MemberType.POINTER: "void*", MemberType.CHAR_ARRAY: "char",
            MemberType.WCHAR_ARRAY: "wchar_t", MemberType.VTABLE_PTR: "void**",
            MemberType.FUNCTION_PTR: "void*", MemberType.BITFIELD: "uint32_t",
            MemberType.PADDING: "uint8_t", MemberType.UNKNOWN: "uint8_t",
        }
        return _map.get(self, "uint8_t")

    @property
    def size(self) -> int:
        _map: Dict[MemberType, int] = {
            MemberType.INT8: 1, MemberType.INT16: 2, MemberType.INT32: 4,
            MemberType.INT64: 8, MemberType.UINT8: 1, MemberType.UINT16: 2,
            MemberType.UINT32: 4, MemberType.UINT64: 8, MemberType.FLOAT: 4,
            MemberType.DOUBLE: 8, MemberType.POINTER: 4, MemberType.CHAR_ARRAY: 1,
            MemberType.WCHAR_ARRAY: 2, MemberType.VTABLE_PTR: 4,
            MemberType.FUNCTION_PTR: 4, MemberType.BITFIELD: 4,
            MemberType.PADDING: 1, MemberType.UNKNOWN: 1,
        }
        return _map.get(self, 1)


class AccessType(Enum):
    """内存访问类型枚举。"""
    READ = auto()
    WRITE = auto()
    READ_WRITE = auto()


# ============================================================================
# 数据类定义
# ============================================================================

@dataclass
class StructMember:
    """结构体成员描述。"""
    name: str
    offset: int
    size: int
    member_type: MemberType = MemberType.UNKNOWN
    array_size: int = 0
    access_type: AccessType = AccessType.READ_WRITE
    access_count: int = 0
    confidence: float = 0.0

    def __repr__(self) -> str:
        arr = f"[{self.array_size}]" if self.array_size > 0 else ""
        return (f"StructMember({self.name}: {self.member_type.name}{arr} "
                f"@ +0x{self.offset:X}, size={self.size}, conf={self.confidence:.2f})")


@dataclass
class RecoveredStruct:
    """恢复出的结构体/类定义。"""
    name: str
    total_size: int
    members: List[StructMember] = field(default_factory=list)
    alignment: int = 4
    inheritance: List[str] = field(default_factory=list)
    vtable_address: Optional[int] = None
    constructor_address: Optional[int] = None
    destructor_address: Optional[int] = None

    @property
    def has_vtable(self) -> bool:
        return self.vtable_address is not None

    @property
    def member_count(self) -> int:
        return sum(1 for m in self.members if m.member_type != MemberType.PADDING)

    def get_member_by_offset(self, offset: int) -> Optional[StructMember]:
        for m in self.members:
            if m.offset == offset:
                return m
        return None

    def get_member_by_name(self, name: str) -> Optional[StructMember]:
        for m in self.members:
            if m.name == name:
                return m
        return None

    def __repr__(self) -> str:
        return (f"RecoveredStruct({self.name}, size=0x{self.total_size:X}, "
                f"members={self.member_count}, vtable={self.has_vtable})")


@dataclass
class VTableEntry:
    """虚函数表条目。"""
    index: int
    address: int
    demangled_name: str = ""
    is_virtual: bool = True
    is_pure_virtual: bool = False

    def __repr__(self) -> str:
        tag = " [pure]" if self.is_pure_virtual else (" [virtual]" if self.is_virtual else "")
        return f"VTableEntry[{self.index}]: 0x{self.address:08X} {self.demangled_name}{tag}"


@dataclass
class RecoveredVTable:
    """恢复出的虚函数表。"""
    class_name: str
    address: int
    entries: List[VTableEntry] = field(default_factory=list)
    size: int = 0

    @property
    def virtual_count(self) -> int:
        return sum(1 for e in self.entries if e.is_virtual and not e.is_pure_virtual)

    @property
    def pure_virtual_count(self) -> int:
        return sum(1 for e in self.entries if e.is_pure_virtual)

    def get_entry_by_index(self, index: int) -> Optional[VTableEntry]:
        for e in self.entries:
            if e.index == index:
                return e
        return None

    def __repr__(self) -> str:
        return (f"RecoveredVTable({self.class_name}, addr=0x{self.address:08X}, "
                f"entries={self.size}, virtual={self.virtual_count}, "
                f"pure={self.pure_virtual_count})")


@dataclass
class ClassHierarchy:
    """类层次结构描述。"""
    root_class: str
    sub_classes: List[str] = field(default_factory=list)
    depth: int = 0
    is_virtual_base: bool = False
    has_multiple_inheritance: bool = False

    def __repr__(self) -> str:
        return (f"ClassHierarchy(root={self.root_class}, depth={self.depth}, "
                f"subs={len(self.sub_classes)}, virtual_base={self.is_virtual_base})")


# ============================================================================
# 内部辅助数据结构
# ============================================================================

@dataclass
class _MemoryAccess:
    """内存访问模式内部表示。"""
    base_register: str
    offset: int
    size: int
    access_type: AccessType
    instruction: str
    index_register: Optional[str] = None
    scale: int = 1
    is_bitfield: bool = False


@dataclass
class _VTableCandidate:
    """虚表候选信息。"""
    address: int
    entries: List[int] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class EngineStatistics:
    """引擎运行统计信息。"""
    total_functions_analyzed: int = 0
    total_instructions_analyzed: int = 0
    total_structs_recovered: int = 0
    total_members_recovered: int = 0
    total_vtables_found: int = 0
    total_virtual_functions: int = 0
    total_hierarchies_built: int = 0
    average_confidence: float = 0.0
    elapsed_time_ms: float = 0.0

    def __repr__(self) -> str:
        return "\n".join([
            "=== 结构体恢复引擎统计 ===",
            f"  分析函数数:    {self.total_functions_analyzed}",
            f"  分析指令数:    {self.total_instructions_analyzed}",
            f"  恢复结构体数:  {self.total_structs_recovered}",
            f"  恢复成员数:    {self.total_members_recovered}",
            f"  发现虚表数:    {self.total_vtables_found}",
            f"  虚函数数:      {self.total_virtual_functions}",
            f"  层次结构数:    {self.total_hierarchies_built}",
            f"  平均置信度:    {self.average_confidence:.2%}",
            f"  耗时:          {self.elapsed_time_ms:.1f} ms",
        ])


# ============================================================================
# 1. MemoryAccessAnalyzer — 内存访问模式分析器
# ============================================================================

class MemoryAccessAnalyzer:
    """内存访问模式分析器。

    从汇编指令序列中提取结构体字段的内存访问模式。
    支持 x86/x86_64 汇编格式。
    """

    _BASE_REGISTERS: FrozenSet[str] = frozenset({
        "eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp",
        "rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
        "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15",
    })

    _READ_PREFIXES: FrozenSet[str] = frozenset({
        "mov", "movzx", "movsx", "movsxd", "lea", "fld", "fild",
        "movss", "movsd", "movaps", "movups", "movdqa", "movdqu",
        "cmp", "test", "add", "sub", "and", "or", "xor", "shl",
        "shr", "sar", "rol", "ror", "imul", "mul", "div", "idiv",
        "push", "call", "jmp",
    })

    _WRITE_PREFIXES: FrozenSet[str] = frozenset({
        "mov", "fst", "fstp", "fist", "fistp",
        "movss", "movsd", "movaps", "movups", "movdqa", "movdqu",
        "lea", "add", "sub", "and", "or", "xor", "shl", "shr",
        "sar", "rol", "ror", "inc", "dec", "neg", "not",
        "push", "pop", "xchg",
    })

    _INSTRUCTION_SIZE_MAP: Dict[str, int] = {
        "movzx": 1, "movsx": 1, "movsxd": 4,
        "movsb": 1, "movsw": 2, "movsd": 4, "movsq": 8,
        "stosb": 1, "stosw": 2, "stosd": 4, "stosq": 8,
        "lodsb": 1, "lodsw": 2, "lodsd": 4, "lodsq": 8,
        "fld": 4, "fldl": 8, "fstp": 4, "fstpl": 8,
        "movss": 4, "movsd": 8, "movaps": 16, "movups": 16,
        "movdqa": 16, "movdqu": 16,
    }

    def __init__(self) -> None:
        self._accesses: List[_MemoryAccess] = []
        self._base_registers_found: Set[str] = set()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def analyze_access_patterns(self, instructions: List[str]) -> List[_MemoryAccess]:
        """分析指令序列，提取所有结构体字段访问模式。"""
        self._accesses = []
        self._base_registers_found.clear()
        for i, instr in enumerate(instructions):
            instr = instr.strip()
            if not instr or instr.startswith((";", "#", "//")):
                continue
            access = self._parse_single_instruction(instr)
            if access is not None:
                self._accesses.append(access)
                self._base_registers_found.add(access.base_register)
        return self._accesses

    def detect_base_pointer(
        self, accesses: Optional[List[_MemoryAccess]] = None
    ) -> Optional[str]:
        """检测结构体基址指针（排除 esp/rsp）。"""
        data = accesses if accesses is not None else self._accesses
        if not data:
            return None
        counter: Dict[str, int] = defaultdict(int)
        for acc in data:
            counter[acc.base_register] += 1
        if not counter:
            return None
        candidates = {r: c for r, c in counter.items() if r.lower() not in ("esp", "rsp")}
        return max(candidates, key=lambda k: candidates[k]) if candidates else max(counter, key=lambda k: counter[k])

    def group_by_base_register(
        self, accesses: Optional[List[_MemoryAccess]] = None
    ) -> Dict[str, List[_MemoryAccess]]:
        """按基址寄存器分组内存访问。"""
        data = accesses if accesses is not None else self._accesses
        groups: Dict[str, List[_MemoryAccess]] = defaultdict(list)
        for acc in data:
            groups[acc.base_register].append(acc)
        return dict(groups)

    def infer_member_size(self, access: _MemoryAccess) -> int:
        """从指令推断字段访问大小（字节）。"""
        instr_lower = access.instruction.lower()
        tokens = instr_lower.split()
        if not tokens:
            return 4
        mnemonic = tokens[0]
        if mnemonic in self._INSTRUCTION_SIZE_MAP:
            return self._INSTRUCTION_SIZE_MAP[mnemonic]
        # 从操作数大小前缀推断
        for token in tokens:
            if token in ("byte", "byte ptr"):
                return 1
            if token in ("word", "word ptr"):
                return 2
            if token in ("dword", "dword ptr"):
                return 4
            if token in ("qword", "qword ptr"):
                return 8
            if token in ("xmmword", "xmmword ptr", "oword", "oword ptr"):
                return 16
        # 从寄存器大小推断
        for token in tokens[1:]:
            clean = token.strip("[],")
            if clean in ("al", "ah", "bl", "bh", "cl", "ch", "dl", "dh"):
                return 1
            if clean in ("ax", "bx", "cx", "dx", "si", "di", "bp", "sp"):
                return 2
            if clean in ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"):
                return 4
            if clean in ("rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
                         "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"):
                return 8
            if clean.startswith("xmm"):
                return 16
        return access.size if access.size > 0 else 4

    def detect_array_access(
        self, accesses: Optional[List[_MemoryAccess]] = None
    ) -> List[Tuple[int, int, int]]:
        """识别数组元素访问模式。返回 (起始偏移, 元素大小, 元素个数) 列表。"""
        data = accesses if accesses is not None else self._accesses
        arrays: List[Tuple[int, int, int]] = []
        indexed: Dict[Tuple[str, str, int], List[_MemoryAccess]] = defaultdict(list)
        for acc in data:
            if acc.index_register and acc.scale > 1:
                indexed[(acc.base_register, acc.index_register, acc.scale)].append(acc)
        for key, group in indexed.items():
            if len(group) < 2:
                continue
            offsets = sorted(set(a.offset for a in group))
            element_size = key[2]
            count = max(1, (offsets[0] + element_size * 10) // element_size)
            arrays.append((offsets[0], element_size, count))
        return arrays

    def detect_bitfield_access(
        self, accesses: Optional[List[_MemoryAccess]] = None
    ) -> List[Tuple[int, int, int]]:
        """识别位域操作模式。返回 (偏移, 位宽, 位偏移) 列表。"""
        data = accesses if accesses is not None else self._accesses
        bitfields: List[Tuple[int, int, int]] = []
        for acc in data:
            if not acc.is_bitfield:
                continue
            instr = acc.instruction.lower()
            mask_match = re.search(r'(?:and|or|xor)\s+.*?,\s*(0x[0-9a-fA-F]+|\d+)', instr)
            if mask_match:
                mask_val = int(mask_match.group(1), 0)
                bit_width = mask_val.bit_length()
                bit_offset = (mask_val & -mask_val).bit_length() - 1
                bitfields.append((acc.offset, bit_width, bit_offset))
        return bitfields

    # ------------------------------------------------------------------
    # 内部解析方法
    # ------------------------------------------------------------------

    def _parse_single_instruction(self, instr: str) -> Optional[_MemoryAccess]:
        """解析单条汇编指令，提取内存访问信息。"""
        instr_lower = instr.lower().strip()
        tokens = instr_lower.split()
        if not tokens:
            return None
        mnemonic = tokens[0]
        access_type = self._determine_access_type(mnemonic)
        mem_patterns = re.findall(r'\[([^\]]+)\]', instr_lower)
        if not mem_patterns:
            return None
        for mem_expr in mem_patterns:
            parsed = self._parse_memory_operand(mem_expr)
            if parsed is None:
                continue
            base_reg, offset, index_reg, scale = parsed
            size = self._infer_size_from_instruction(instr, mnemonic)
            is_bitfield = self._is_bitfield_operation(mnemonic, instr)
            return _MemoryAccess(
                base_register=base_reg, offset=offset, size=size,
                access_type=access_type, instruction=instr,
                index_register=index_reg, scale=scale, is_bitfield=is_bitfield,
            )
        return None

    def _parse_memory_operand(
        self, mem_expr: str
    ) -> Optional[Tuple[str, int, Optional[str], int]]:
        """解析内存操作数表达式。支持 reg+offset, reg+reg*scale+offset 等格式。"""
        expr = mem_expr.strip().replace("ptr", "").strip()
        # 模式: reg+reg*scale+offset
        scaled_match = re.match(
            r'(\w+)\s*\+\s*(\w+)\s*\*\s*(\d+)\s*([+-]\s*0x[0-9a-fA-F]+|[+-]\s*\d+)?',
            expr)
        if scaled_match:
            base = scaled_match.group(1)
            offset = self._parse_offset(scaled_match.group(4)) if scaled_match.group(4) else 0
            if base in self._BASE_REGISTERS:
                return (base, offset, scaled_match.group(2), int(scaled_match.group(3)))
        # 模式: reg+offset 或 reg-offset
        offset_match = re.match(r'(\w+)\s*([+-]\s*(?:0x[0-9a-fA-F]+|\d+))', expr)
        if offset_match:
            base = offset_match.group(1)
            if base in self._BASE_REGISTERS:
                return (base, self._parse_offset(offset_match.group(2)), None, 1)
        # 模式: offset+reg
        offset_match2 = re.match(r'(0x[0-9a-fA-F]+|\d+)\s*\+\s*(\w+)', expr)
        if offset_match2:
            base = offset_match2.group(2)
            if base in self._BASE_REGISTERS:
                return (base, self._parse_offset(offset_match2.group(1)), None, 1)
        # 模式: 纯寄存器
        if expr.strip() in self._BASE_REGISTERS:
            return (expr.strip(), 0, None, 1)
        return None

    def _parse_offset(self, offset_str: str) -> int:
        """解析偏移字符串为整数。"""
        s = offset_str.strip().replace(" ", "")
        negative = False
        if s.startswith("+"):
            s = s[1:]
        elif s.startswith("-"):
            negative = True
            s = s[1:]
        value = int(s, 16) if s.lower().startswith("0x") else int(s)
        return -value if negative else value

    def _determine_access_type(self, mnemonic: str) -> AccessType:
        """根据指令助记符确定访问类型。"""
        mnemonic = mnemonic.lower()
        can_read = mnemonic in self._READ_PREFIXES or any(
            mnemonic.startswith(p) for p in ["mov", "cmp", "test", "push", "fld"])
        can_write = mnemonic in self._WRITE_PREFIXES or any(
            mnemonic.startswith(p) for p in ["mov", "pop", "fst", "fstp"])
        if can_read and can_write:
            return AccessType.READ_WRITE
        return AccessType.WRITE if can_write else AccessType.READ

    def _infer_size_from_instruction(self, instr: str, mnemonic: str) -> int:
        """从指令文本推断操作数大小。"""
        if mnemonic.lower() in self._INSTRUCTION_SIZE_MAP:
            return self._INSTRUCTION_SIZE_MAP[mnemonic.lower()]
        il = instr.lower()
        if "byte ptr" in il or "byte " in il.split():
            return 1
        if "word ptr" in il or "word " in il.split():
            return 2
        if "dword ptr" in il or "dword " in il.split():
            return 4
        if "qword ptr" in il or "qword " in il.split():
            return 8
        if "xmmword" in il or "oword" in il:
            return 16
        return 4

    def _is_bitfield_operation(self, mnemonic: str, instr: str) -> bool:
        """检测是否为位域操作指令。"""
        bit_ops = {"and", "or", "xor", "shl", "shr", "sar", "rol", "ror",
                    "bt", "bts", "btr", "btc", "bsf", "bsr"}
        if mnemonic.lower() not in bit_ops:
            return False
        return bool(re.search(r',\s*(0x[0-9a-fA-F]+|\d+)', instr.lower()))


# ============================================================================
# 2. TypeInferenceEngine — 类型推断引擎
# ============================================================================

class TypeInferenceEngine:
    """类型推断引擎。

    根据内存访问的上下文（指令类型、操作数特征、使用模式），
    推断每个结构体字段的 C/C++ 类型。
    """

    _FPU_INSTRUCTIONS: FrozenSet[str] = frozenset({
        "fld", "fst", "fstp", "fadd", "fsub", "fmul", "fdiv",
        "fild", "fist", "fistp", "fcom", "fcomp", "fucom",
        "fldz", "fld1", "fldpi", "fsin", "fcos", "fsqrt",
        "fabs", "fchs", "fptan", "fpatan", "fprem", "fyl2x",
    })

    _SSE_FLOAT_INSTRUCTIONS: FrozenSet[str] = frozenset({
        "movss", "movsd", "addss", "addsd", "subss", "subsd",
        "mulss", "mulsd", "divss", "divsd", "sqrtss", "sqrtsd",
        "cvtsi2ss", "cvtsi2sd", "cvtss2si", "cvtsd2si",
        "ucomiss", "ucomisd", "comiss", "comisd",
        "minss", "minsd", "maxss", "maxsd",
        "movaps", "movups", "movapd", "movupd",
    })

    _ARITHMETIC_INSTRUCTIONS: FrozenSet[str] = frozenset({
        "add", "sub", "imul", "mul", "idiv", "div", "inc", "dec",
        "neg", "adc", "sbb", "cmp", "test",
    })

    _SIGNED_EXTEND: FrozenSet[str] = frozenset({
        "movsx", "movsxd", "cbw", "cwd", "cwde", "cdq", "cdqe", "cqo",
    })

    _ZERO_EXTEND: FrozenSet[str] = frozenset({"movzx"})

    def __init__(self) -> None:
        self._pointer_size: int = 4

    def set_pointer_size(self, size: int) -> None:
        """设置指针大小（32 位: 4, 64 位: 8）。"""
        if size in (4, 8):
            self._pointer_size = size

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def infer_type_from_usage(
        self, instructions: List[str], offset: int
    ) -> Tuple[MemberType, float]:
        """综合推断字段类型。返回 (类型, 置信度)。"""
        if not instructions:
            return (MemberType.UNKNOWN, 0.0)
        scores: Dict[MemberType, float] = defaultdict(float)
        for instr in instructions:
            mnemonic = instr.strip().lower().split()[0] if instr.strip() else ""
            if self._is_float_instruction(mnemonic):
                scores[MemberType.DOUBLE if "sd" in mnemonic or "l" in mnemonic[-2:]
                       else MemberType.FLOAT] += 1.0
            elif self._is_pointer_instruction(instr):
                scores[MemberType.POINTER] += 0.8
            elif self._is_string_reference(instr):
                scores[MemberType.CHAR_ARRAY] += 0.9
            elif self._is_vtable_access(instr):
                scores[MemberType.VTABLE_PTR] += 0.95
            elif self._is_function_pointer_usage(instr):
                scores[MemberType.FUNCTION_PTR] += 0.85
            elif mnemonic in self._ARITHMETIC_INSTRUCTIONS:
                scores[MemberType.INT32] += 0.5
                if mnemonic in self._SIGNED_EXTEND:
                    scores[MemberType.INT32] += 0.3
                elif mnemonic in self._ZERO_EXTEND:
                    scores[MemberType.UINT32] += 0.3
        if not scores:
            return (MemberType.UNKNOWN, 0.0)
        best_type = max(scores, key=lambda k: scores[k])
        confidence = min(scores[best_type] / max(3.0, len(instructions)), 1.0)
        return (best_type, confidence)

    def detect_string_pointer(self, instructions: List[str]) -> Optional[Tuple[int, int]]:
        """检测字符串指针（char*）字段。"""
        for instr in instructions:
            il = instr.lower()
            if re.search(r'push\s+(?:offset\s+)?(a[A-Z]\w+)', il):
                return (0, 0)
            match = re.search(r'lea\s+\w+,\s*\[?([a-zA-Z_]\w*)\]?', il)
            if match and match.group(1).startswith(("a", "str", "sz", "s_")):
                return (0, 0)
        return None

    def detect_function_pointer(self, instructions: List[str]) -> bool:
        """检测函数指针。通过 call [reg+offset] 等间接调用模式。"""
        for instr in instructions:
            il = instr.lower().strip()
            if re.search(r'call\s+\w+\s+ptr\s*\[', il) or re.search(r'call\s+\[', il):
                return True
            if re.match(r'call\s+\w+$', il):
                return True
        return False

    def detect_vtable_pointer(self, instructions: List[str]) -> bool:
        """检测虚表指针。通过 call [reg+0] 等虚函数调用模式。"""
        for instr in instructions:
            il = instr.lower().strip()
            if re.search(r'call\s+\w+\s+ptr\s*\[.*\]', il):
                mem = re.search(r'\[([^\]]+)\]', il)
                if mem and re.search(r'[+\-]\s*(0|4|8|12|16|20|24|28|32|36|40)', mem.group(1)):
                    return True
        return False

    def detect_integer_field(self, instructions: List[str]) -> Tuple[bool, bool, int]:
        """检测整数字段。返回 (是否整数, 是否有符号, 位宽)。"""
        is_int, is_signed, bit_width = False, False, 32
        for instr in instructions:
            il = instr.lower().strip()
            tokens = il.split()
            if not tokens:
                continue
            m = tokens[0]
            if m in self._ARITHMETIC_INSTRUCTIONS:
                is_int = True
            if m in self._SIGNED_EXTEND:
                is_int = is_signed = True
                bit_width = 8 if m == "movsx" else 32
            if m in self._ZERO_EXTEND:
                is_int = True
                bit_width = 8
            for token in tokens[1:]:
                clean = token.strip("[],")
                if clean in ("al", "bl", "cl", "dl"):
                    bit_width = 8
                elif clean in ("ax", "bx", "cx", "dx"):
                    bit_width = 16
                elif clean in ("eax", "ebx", "ecx", "edx"):
                    bit_width = 32
                elif clean in ("rax", "rbx", "rcx", "rdx"):
                    bit_width = 64
            if m == "cmp" and any(t in il for t in ("ja", "jb", "jae", "jbe")):
                is_signed = False
            elif m == "cmp" and any(t in il for t in ("jg", "jl", "jge", "jle")):
                is_signed = True
        return (is_int, is_signed, bit_width)

    def detect_float_field(self, instructions: List[str]) -> Tuple[bool, int]:
        """检测浮点字段。返回 (是否浮点, 位宽: 32=float, 64=double)。"""
        for instr in instructions:
            tokens = instr.lower().strip().split()
            if not tokens:
                continue
            m = tokens[0]
            if m in self._SSE_FLOAT_INSTRUCTIONS:
                if "sd" in m:
                    return (True, 64)
                if "ss" in m:
                    return (True, 32)
                return (True, 64 if "pd" in m else 32)
            if m in self._FPU_INSTRUCTIONS:
                return (True, 32)
        return (False, 0)

    def detect_pointer_field(self, instructions: List[str]) -> bool:
        """检测指针字段。通过 lea 指令和间接寻址模式。"""
        for instr in instructions:
            il = instr.lower().strip()
            if il.startswith("lea"):
                return True
            if re.search(r'mov\s+\w+,\s*\[', il):
                match = re.search(r'mov\s+(\w+),\s*\[', il)
                if match:
                    reg = match.group(1)
                    for other in instructions:
                        if f"[{reg}" in other.lower():
                            return True
        return False

    def infer_struct_alignment(self, accesses: List[_MemoryAccess]) -> int:
        """推断结构体对齐要求。"""
        if not accesses:
            return 4
        max_size = max((a.size for a in accesses), default=4)
        offsets = [a.offset for a in accesses]
        if offsets:
            gcd_val = offsets[0]
            for o in offsets[1:]:
                gcd_val = math.gcd(gcd_val, o)
            alignment = 1
            while alignment < max_size and alignment <= gcd_val:
                alignment *= 2
            if gcd_val % alignment != 0:
                alignment = max_size
        alignment = max(1, min(16, alignment or max_size))
        return 1 << (alignment.bit_length() - 1)

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _is_float_instruction(self, mnemonic: str) -> bool:
        return mnemonic.lower() in self._FPU_INSTRUCTIONS or mnemonic.lower() in self._SSE_FLOAT_INSTRUCTIONS

    def _is_pointer_instruction(self, instr: str) -> bool:
        return instr.lower().strip().startswith("lea")

    def _is_string_reference(self, instr: str) -> bool:
        return bool(re.search(r'(?:push|lea|mov)\s+.*?(?:offset\s+)?a[A-Z]\w*', instr.lower()))

    def _is_vtable_access(self, instr: str) -> bool:
        return bool(re.search(r'call\s+\w+\s+ptr\s*\[\w+\s*\]', instr.lower()))

    def _is_function_pointer_usage(self, instr: str) -> bool:
        return bool(re.search(r'call\s+\[', instr.lower()))


# ============================================================================
# 3. VTableAnalyzer — 虚函数表分析器
# ============================================================================

class VTableAnalyzer:
    """虚函数表分析器。

    从二进制数据或控制流图信息中定位和解析虚函数表。
    支持识别虚函数、纯虚函数、构造函数和析构函数。
    """

    _PURE_VIRTUAL_MARKERS: FrozenSet[str] = frozenset({
        "__cxa_pure_virtual", "__purecall", "__pure_virtual",
        "_purecall", "pure_virtual_called",
    })

    _CONSTRUCTOR_PATTERNS: List[bytes] = [
        b'\xc7\x00', b'\xc7\x03', b'\xc7\x01',
        b'\x48\xc7\x07', b'\x48\xc7\x03',
    ]

    def __init__(self) -> None:
        self._vtables: List[RecoveredVTable] = []
        self._rtti_map: Dict[int, str] = {}

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def find_vtable(self, cfg_data: Dict[str, Any]) -> List[RecoveredVTable]:
        """从控制流图数据中定位虚函数表。"""
        self._vtables = []
        data_sections = cfg_data.get("data_sections", [])
        functions = cfg_data.get("functions", [])
        candidates = self._scan_for_vtable_candidates(functions, data_sections)
        for candidate in candidates:
            vtable = self._build_vtable_from_candidate(candidate)
            if vtable and vtable.size > 0:
                self._vtables.append(vtable)
        return self._vtables

    def parse_vtable_entries(
        self, vtable_address: int, raw_data: Optional[bytes] = None,
        symbol_names: Optional[Dict[int, str]] = None
    ) -> List[VTableEntry]:
        """解析虚函数表中的单个条目。"""
        entries: List[VTableEntry] = []
        symbol_names = symbol_names or {}
        if raw_data is None:
            return entries
        ptr_size = 4
        index = 0
        while index * ptr_size < len(raw_data):
            if index * ptr_size + ptr_size > len(raw_data):
                break
            func_addr_bytes = raw_data[index * ptr_size: index * ptr_size + ptr_size]
            func_addr = py_struct.unpack("<I", func_addr_bytes)[0] if ptr_size == 4 else py_struct.unpack("<Q", func_addr_bytes)[0]
            if func_addr == 0:
                break
            name = symbol_names.get(func_addr, "")
            entries.append(VTableEntry(
                index=index, address=func_addr, demangled_name=name,
                is_virtual=True, is_pure_virtual=self._is_pure_virtual(func_addr, name),
            ))
            index += 1
        return entries

    def recover_virtual_functions(
        self, vtable: RecoveredVTable, raw_data: Optional[bytes] = None
    ) -> List[VTableEntry]:
        """识别虚函数边界，恢复完整虚函数信息。"""
        if raw_data is not None:
            vtable.entries = self.parse_vtable_entries(vtable.address, raw_data)
            vtable.size = len(vtable.entries)
        return vtable.entries

    def detect_pure_virtual(self, entries: List[VTableEntry]) -> List[int]:
        """检测纯虚函数。返回纯虚函数索引列表。"""
        pure_indices: List[int] = []
        for entry in entries:
            if self._is_pure_virtual(entry.address, entry.demangled_name):
                entry.is_pure_virtual = True
                entry.is_virtual = False
                pure_indices.append(entry.index)
        return pure_indices

    def find_constructor(
        self, vtable: RecoveredVTable,
        functions: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[int]:
        """通过虚表初始化模式定位构造函数。"""
        if functions is None:
            return None
        for func in functions:
            instrs = func.get("instructions", [])
            for instr in instrs:
                if isinstance(instr, bytes):
                    for pattern in self._CONSTRUCTOR_PATTERNS:
                        if pattern in instr:
                            if py_struct.pack("<I", vtable.address) in instr:
                                return func.get("address")
                elif isinstance(instr, str):
                    if (f"0x{vtable.address:X}" in instr or f"0x{vtable.address:x}" in instr):
                        if "mov" in instr.lower() and "[" in instr:
                            return func.get("address")
        return None

    def find_destructor(
        self, vtable: RecoveredVTable,
        functions: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[int]:
        """定位析构函数。"""
        if functions is None:
            return None
        for func in functions:
            func_name = func.get("name", "")
            if not any(kw in func_name.lower() for kw in ("destructor", "~", "destroy", "dtor")):
                continue
            instrs = func.get("instructions", [])
            for instr in instrs:
                if isinstance(instr, str):
                    if (f"0x{vtable.address:X}" in instr or f"0x{vtable.address:x}" in instr):
                        return func.get("address")
                elif isinstance(instr, bytes):
                    for pattern in self._CONSTRUCTOR_PATTERNS:
                        if pattern in instr and py_struct.pack("<I", vtable.address) in instr:
                            return func.get("address")
        return None

    def build_vtable_layout(self, vtable: RecoveredVTable) -> str:
        """生成虚表布局描述文本。"""
        lines = [
            f"// VTable for class '{vtable.class_name}'",
            f"// Address: 0x{vtable.address:08X}, Entries: {vtable.size}",
            f"// Virtual: {vtable.virtual_count}, Pure: {vtable.pure_virtual_count}",
            "// +--------+---------------------------+",
        ]
        for entry in vtable.entries:
            if entry.is_pure_virtual:
                desc = "[PURE VIRTUAL]"
            elif entry.demangled_name:
                desc = entry.demangled_name
            else:
                desc = f"sub_0x{entry.address:08X}"
            lines.append(f"// | {entry.index:6d} | {desc:<25s} |")
        lines.append("// +--------+---------------------------+")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _scan_for_vtable_candidates(
        self, functions: List[Dict[str, Any]],
        data_sections: List[Dict[str, Any]],
    ) -> List[_VTableCandidate]:
        """扫描潜在的虚表位置。"""
        candidates: List[_VTableCandidate] = []
        for section in data_sections:
            raw = section.get("raw_data", b"")
            base = section.get("address", 0)
            if not isinstance(raw, bytes):
                continue
            candidates.extend(self._scan_data_for_vtables(raw, base))
        for func in functions:
            rtti_refs = self._extract_rtti_refs(func)
            for addr, name in rtti_refs.items():
                self._rtti_map[addr] = name
        return candidates

    def _scan_data_for_vtables(self, raw: bytes, base: int) -> List[_VTableCandidate]:
        """在数据段中扫描虚表。"""
        candidates: List[_VTableCandidate] = []
        ptr_size, min_entries = 4, 2
        i = 0
        while i + ptr_size <= len(raw):
            entries: List[int] = []
            j = i
            while j + ptr_size <= len(raw):
                addr = py_struct.unpack("<I", raw[j:j + ptr_size])[0] if ptr_size == 4 else py_struct.unpack("<Q", raw[j:j + ptr_size])[0]
                if addr == 0:
                    break
                if addr < 0x1000 or addr > 0xFFFFFFFF:
                    break
                entries.append(addr)
                j += ptr_size
            if len(entries) >= min_entries:
                candidates.append(_VTableCandidate(
                    address=base + i, entries=entries,
                    confidence=min(0.5 + len(entries) * 0.1, 1.0),
                ))
                i = j
            else:
                i += ptr_size
        return candidates

    def _extract_rtti_refs(self, func: Dict[str, Any]) -> Dict[int, str]:
        return {}

    def _build_vtable_from_candidate(self, candidate: _VTableCandidate) -> Optional[RecoveredVTable]:
        class_name = f"Class_0x{candidate.address:08X}"
        entries = [
            VTableEntry(index=idx, address=addr, demangled_name="",
                        is_virtual=True, is_pure_virtual=False)
            for idx, addr in enumerate(candidate.entries)
        ]
        return RecoveredVTable(class_name=class_name, address=candidate.address,
                               entries=entries, size=len(entries))

    def _is_pure_virtual(self, address: int, name: str) -> bool:
        if name:
            for marker in self._PURE_VIRTUAL_MARKERS:
                if marker in name.lower():
                    return True
        return False


# ============================================================================
# 4. ClassHierarchyAnalyzer — 类层次结构分析器
# ============================================================================

class ClassHierarchyAnalyzer:
    """类层次结构分析器。

    通过分析结构体成员布局和虚表关系，推断 C++ 类之间的继承关系。
    """

    def __init__(self) -> None:
        self._hierarchies: List[ClassHierarchy] = []
        self._struct_map: Dict[str, RecoveredStruct] = {}

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def analyze_inheritance(self, structs: List[RecoveredStruct]) -> List[ClassHierarchy]:
        """推断继承关系。"""
        self._hierarchies = []
        self._struct_map = {s.name: s for s in structs}
        base_relations = self.detect_base_class_embedding(structs)
        multi_inheritance = self.detect_multiple_inheritance(structs)
        virtual_inheritance = self.detect_virtual_inheritance(structs)
        self._hierarchies = self._build_hierarchy_tree(
            base_relations, multi_inheritance, virtual_inheritance)
        return self._hierarchies

    def detect_base_class_embedding(
        self, structs: List[RecoveredStruct]
    ) -> Dict[str, List[str]]:
        """检测基类嵌入模式。比较结构体前 N 个成员是否匹配。"""
        relations: Dict[str, List[str]] = defaultdict(list)
        for i, derived in enumerate(structs):
            for j, base in enumerate(structs):
                if i != j and self._is_base_embedded_in(base, derived):
                    relations[derived.name].append(base.name)
        return dict(relations)

    def detect_multiple_inheritance(self, structs: List[RecoveredStruct]) -> Set[str]:
        """检测多重继承：结构体中有多个虚表指针。"""
        multi: Set[str] = set()
        for struct in structs:
            if sum(1 for m in struct.members if m.member_type == MemberType.VTABLE_PTR) >= 2:
                multi.add(struct.name)
        return multi

    def detect_virtual_inheritance(self, structs: List[RecoveredStruct]) -> Set[str]:
        """检测虚继承：有 vbptr 或偏移表指针。"""
        virtual: Set[str] = set()
        for struct in structs:
            for member in struct.members:
                if member.name.lower().startswith("vbptr"):
                    virtual.add(struct.name)
                    break
                if (member.member_type == MemberType.POINTER and
                    member.offset == 0 and not struct.has_vtable):
                    virtual.add(struct.name)
        return virtual

    def analyze_rtti(self, rtti_data: Optional[Dict[str, Any]] = None) -> Dict[str, List[str]]:
        """分析 RTTI 数据提取类层次结构。"""
        if rtti_data is None:
            return {}
        hierarchy: Dict[str, List[str]] = {}
        class_hierarchy = rtti_data.get("class_hierarchy", {})
        if isinstance(class_hierarchy, dict):
            for class_name, info in class_hierarchy.items():
                bases = info.get("base_classes", [])
                hierarchy[class_name] = list(bases) if isinstance(bases, list) else list(bases.keys()) if isinstance(bases, dict) else []
        return hierarchy

    def build_hierarchy_tree(
        self, structs: Optional[List[RecoveredStruct]] = None
    ) -> List[ClassHierarchy]:
        """构建类层次结构树（公共接口）。"""
        if structs is not None:
            return self.analyze_inheritance(structs)
        return self._hierarchies

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _is_base_embedded_in(self, base: RecoveredStruct, derived: RecoveredStruct) -> bool:
        """检查 base 是否被嵌入在 derived 的开头。"""
        if len(base.members) == 0 or len(base.members) > len(derived.members):
            return False
        base_m = [m for m in base.members if m.member_type != MemberType.PADDING]
        derived_m = [m for m in derived.members if m.member_type != MemberType.PADDING]
        if len(base_m) > len(derived_m):
            return False
        matches = 0
        for bm in base_m:
            dm = derived.get_member_by_offset(bm.offset)
            if dm is None:
                for d in derived_m:
                    if d.offset == bm.offset and d.size == bm.size:
                        matches += 1
                        break
            elif dm.size == bm.size:
                matches += 1
        return len(base_m) > 0 and matches / len(base_m) >= 0.6

    def _build_hierarchy_tree(
        self, base_relations: Dict[str, List[str]],
        multi_inheritance: Set[str], virtual_inheritance: Set[str],
    ) -> List[ClassHierarchy]:
        """构建类层次结构树。"""
        all_classes = set(base_relations.keys()) | {
            b for bases in base_relations.values() for b in bases
        }
        depths: Dict[str, int] = {}

        def _calc_depth(cls: str, visited: Optional[Set[str]] = None) -> int:
            if visited is None:
                visited = set()
            if cls in visited:
                return 0
            visited.add(cls)
            if cls not in base_relations or not base_relations[cls]:
                return 0
            return 1 + max((_calc_depth(b, visited.copy()) for b in base_relations[cls]), default=0)

        for cls in all_classes:
            depths[cls] = _calc_depth(cls)

        children: Dict[str, List[str]] = defaultdict(list)
        for derived, bases in base_relations.items():
            for base in bases:
                children[base].append(derived)

        return [
            ClassHierarchy(
                root_class=cls,
                sub_classes=children.get(cls, []),
                depth=depths.get(cls, 0),
                is_virtual_base=cls in virtual_inheritance,
                has_multiple_inheritance=cls in multi_inheritance,
            )
            for cls in all_classes
        ]


# ============================================================================
# 5. StructLayoutGenerator — 结构体布局生成器
# ============================================================================

class StructLayoutGenerator:
    """结构体布局生成器。

    负责根据恢复出的结构体信息生成 C/C++ 定义代码、
    计算填充字节、优化布局，以及生成 IDA Pro 导入脚本。
    """

    def __init__(self) -> None:
        self._indent_size = 4

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def generate_struct_padding(
        self, members: List[StructMember], alignment: int = 4
    ) -> List[StructMember]:
        """计算并插入结构体成员之间的填充字节。"""
        if not members:
            return []
        sorted_members = sorted(members, key=lambda m: m.offset)
        result: List[StructMember] = []
        current_offset = sorted_members[0].offset
        for member in sorted_members:
            if member.offset > current_offset:
                padding_size = member.offset - current_offset
                result.append(StructMember(
                    name=f"pad_{current_offset:04X}", offset=current_offset,
                    size=padding_size, member_type=MemberType.PADDING, confidence=1.0))
            result.append(member)
            current_offset = member.offset + member.size
        return result

    def optimize_layout(
        self, members: List[StructMember], alignment: int = 4
    ) -> List[StructMember]:
        """建议最优成员排序（按大小降序减少填充）。"""
        real_members = [m for m in members
                        if m.member_type not in (MemberType.PADDING, MemberType.VTABLE_PTR)]
        real_members.sort(key=lambda m: m.size, reverse=True)
        offset = 0
        vt_ptr = next((m for m in members if m.member_type == MemberType.VTABLE_PTR), None)
        optimized: List[StructMember] = []
        if vt_ptr:
            optimized.append(StructMember(
                name=vt_ptr.name, offset=0, size=vt_ptr.size,
                member_type=vt_ptr.member_type, confidence=vt_ptr.confidence))
            offset = vt_ptr.size
        for member in real_members:
            align = min(member.size, alignment)
            if offset % align != 0:
                offset += align - (offset % align)
            optimized.append(StructMember(
                name=member.name, offset=offset, size=member.size,
                member_type=member.member_type, array_size=member.array_size,
                access_type=member.access_type, access_count=member.access_count,
                confidence=member.confidence))
            offset += member.size
        return optimized

    def generate_c_definition(self, struct: RecoveredStruct) -> str:
        """生成 C 结构体定义。"""
        lines = [
            f"/* Recovered struct: {struct.name} */",
            f"/* Total size: 0x{struct.total_size:X}, Alignment: {struct.alignment} */",
            f"typedef struct {struct.name} {{",
        ]
        for member in sorted(struct.members, key=lambda m: m.offset):
            if member.member_type == MemberType.PADDING:
                lines.append(f"    uint8_t pad_{member.offset:04X}[{member.size}];")
                continue
            c_type = self._member_to_c_type(member)
            arr = f"[{member.array_size}]" if member.array_size > 0 else ""
            lines.append(
                f"    {c_type} {member.name}{arr};  "
                f"// offset: 0x{member.offset:04X}, conf: {member.confidence:.0%}")
        lines.append(f"}} {struct.name};")
        lines.append(
            f"/* static_assert(sizeof({struct.name}) == 0x{struct.total_size:X}, "
            f"\"Size mismatch for {struct.name}\"); */")
        return "\n".join(lines)

    def generate_cpp_class(
        self, struct: RecoveredStruct,
        vtable: Optional[RecoveredVTable] = None
    ) -> str:
        """生成 C++ 类定义（含虚函数）。"""
        lines = [
            f"/* Recovered class: {struct.name} */",
            f"/* Total size: 0x{struct.total_size:X} */",
        ]
        if struct.inheritance:
            bases = ", ".join(f"public {b}" for b in struct.inheritance)
            lines.append(f"class {struct.name} : {bases} {{")
        else:
            lines.append(f"class {struct.name} {{")
        lines.append("public:")
        if struct.constructor_address:
            lines.append(f"    {struct.name}();  // 0x{struct.constructor_address:08X}")
        if struct.destructor_address:
            lines.append(f"    virtual ~{struct.name}();  // 0x{struct.destructor_address:08X}")
        if vtable and vtable.entries:
            lines.append("")
            lines.append("    // Virtual functions:")
            for entry in vtable.entries:
                if entry.is_pure_virtual:
                    lines.append(f"    virtual void func_{entry.index:02d}() = 0;  // 0x{entry.address:08X}")
                elif entry.demangled_name:
                    lines.append(f"    virtual void {entry.demangled_name}();  // 0x{entry.address:08X}")
                else:
                    lines.append(f"    virtual void func_{entry.index:02d}();  // 0x{entry.address:08X}")
        lines.append("")
        lines.append("    // Member variables:")
        for member in sorted(struct.members, key=lambda m: m.offset):
            if member.member_type == MemberType.PADDING:
                lines.append(f"    uint8_t pad_{member.offset:04X}[{member.size}];  // 0x{member.offset:04X}")
                continue
            if member.member_type == MemberType.VTABLE_PTR:
                continue
            c_type = self._member_to_c_type(member)
            arr = f"[{member.array_size}]" if member.array_size > 0 else ""
            lines.append(f"    {c_type} {member.name}{arr};  // offset: 0x{member.offset:04X}")
        lines.append("};")
        return "\n".join(lines)

    def generate_header_file(
        self, structs: List[RecoveredStruct],
        vtables: Optional[List[RecoveredVTable]] = None
    ) -> str:
        """生成完整的头文件。"""
        vtables = vtables or []
        vtable_map: Dict[str, RecoveredVTable] = {
            f"Class_0x{v.address:08X}": v for v in vtables
        }
        for struct in structs:
            for vtable in vtables:
                if struct.vtable_address == vtable.address:
                    vtable_map[struct.name] = vtable
        lines = [
            "/*",
            " * Auto-generated by Structure Recovery Engine (San7ModMaker)",
            f" * Structures: {len(structs)}, Virtual tables: {len(vtables)}",
            " * WARNING: Best-effort recovery. Manual verification recommended.",
            " */",
            "",
            "#ifndef RECOVERED_STRUCTS_H",
            "#define RECOVERED_STRUCTS_H",
            "",
            "#include <stdint.h>",
            "",
            "#ifdef __cplusplus",
            'extern "C" {',
            "#endif",
            "",
        ]
        for struct in structs:
            vtable = vtable_map.get(struct.name)
            if vtable or struct.has_vtable:
                lines.append(self.generate_cpp_class(struct, vtable))
            else:
                lines.append(self.generate_c_definition(struct))
            lines.append("")
        lines.extend([
            "#ifdef __cplusplus",
            "}",
            "#endif",
            "",
            "#endif /* RECOVERED_STRUCTS_H */",
        ])
        return "\n".join(lines)

    def generate_ida_script(self, structs: List[RecoveredStruct]) -> str:
        """生成 IDA Pro 结构体定义脚本。"""
        lines = [
            "// IDA Pro Structure Definition Script",
            "// Generated by Structure Recovery Engine",
            "// Run: File -> Script File... in IDA Pro",
            "",
            "#include <idc.idc>",
            "",
            "static main(void)",
            "{",
            "    auto sid, mid;",
            "",
        ]
        for struct in structs:
            struct_name = struct.name.replace(" ", "_")
            lines.append(f'    // --- {struct.name} (size: 0x{struct.total_size:X}) ---')
            lines.append(f'    sid = AddStrucEx(-1, "{struct_name}", 0);')
            lines.append(f'    if (sid == -1)')
            lines.append(f'        sid = GetStrucIdByName("{struct_name}");')
            lines.append("")
            for member in sorted(struct.members, key=lambda m: m.offset):
                if member.member_type == MemberType.PADDING:
                    continue
                ida_type = self._member_to_ida_type(member)
                lines.append(
                    f'    AddStrucMember(sid, "{member.name}", '
                    f'0x{member.offset:X}, {ida_type}, -1, {member.size});')
            lines.append("")
        lines.append('    Message("Struct definitions imported successfully.\\n");')
        lines.append("}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _member_to_c_type(self, member: StructMember) -> str:
        if member.member_type == MemberType.BITFIELD:
            return f"uint32_t {member.name} : {member.size * 8}"
        return member.member_type.c_type_name

    def _member_to_ida_type(self, member: StructMember) -> str:
        _ida_map: Dict[MemberType, str] = {
            MemberType.INT8: "FF_BYTE | FF_SIGN", MemberType.INT16: "FF_WORD | FF_SIGN",
            MemberType.INT32: "FF_DWORD | FF_SIGN", MemberType.INT64: "FF_QWORD | FF_SIGN",
            MemberType.UINT8: "FF_BYTE", MemberType.UINT16: "FF_WORD",
            MemberType.UINT32: "FF_DWORD", MemberType.UINT64: "FF_QWORD",
            MemberType.FLOAT: "FF_FLOAT", MemberType.DOUBLE: "FF_DOUBLE",
            MemberType.POINTER: "FF_DWORD | FF_DATA", MemberType.VTABLE_PTR: "FF_DWORD | FF_DATA",
            MemberType.FUNCTION_PTR: "FF_DWORD | FF_DATA",
            MemberType.CHAR_ARRAY: "FF_BYTE", MemberType.WCHAR_ARRAY: "FF_WORD",
            MemberType.BITFIELD: "FF_DWORD", MemberType.PADDING: "FF_BYTE",
            MemberType.UNKNOWN: "FF_BYTE",
        }
        return _ida_map.get(member.member_type, "FF_BYTE")


# ============================================================================
# 6. StructRecoveryEngine — 主入口引擎
# ============================================================================

class StructRecoveryEngine:
    """结构体恢复引擎（主入口）。

    整合所有子组件，提供统一的恢复接口。

    使用示例:
        >>> engine = StructRecoveryEngine()
        >>> structs = engine.recover_from_asm(asm_lines, 0x400000)
        >>> header = engine.generate_header(structs, vtables)
        >>> print(engine.get_statistics())
    """

    def __init__(self) -> None:
        """初始化引擎及所有子组件。"""
        self._memory_analyzer = MemoryAccessAnalyzer()
        self._type_inference = TypeInferenceEngine()
        self._vtable_analyzer = VTableAnalyzer()
        self._hierarchy_analyzer = ClassHierarchyAnalyzer()
        self._layout_generator = StructLayoutGenerator()
        self._stats = EngineStatistics()
        self._recovered_structs: List[RecoveredStruct] = []
        self._recovered_vtables: List[RecoveredVTable] = []
        self._recovered_hierarchies: List[ClassHierarchy] = []
        self._pointer_size: int = 4
        self._default_alignment: int = 4
        self._struct_name_prefix: str = "Struct"

    # ------------------------------------------------------------------
    # 配置方法
    # ------------------------------------------------------------------

    def set_pointer_size(self, size: int) -> None:
        """设置指针大小（4 = 32位, 8 = 64位）。"""
        if size in (4, 8):
            self._pointer_size = size
            self._type_inference.set_pointer_size(size)

    def set_default_alignment(self, alignment: int) -> None:
        """设置默认对齐字节数。"""
        if alignment > 0 and (alignment & (alignment - 1)) == 0:
            self._default_alignment = alignment

    def set_struct_name_prefix(self, prefix: str) -> None:
        """设置结构体名称前缀。"""
        self._struct_name_prefix = prefix

    # ------------------------------------------------------------------
    # 核心恢复方法
    # ------------------------------------------------------------------

    def recover_from_asm(
        self, asm_text: Union[str, List[str]], base_address: int = 0
    ) -> List[RecoveredStruct]:
        """从汇编代码恢复结构体定义。

        分析汇编代码，提取字段访问模式并推断类型，生成结构体定义。

        Args:
            asm_text: 汇编代码文本（字符串或行列表）。
            base_address: 代码基址。

        Returns:
            恢复出的结构体列表。
        """
        if isinstance(asm_text, str):
            instructions = asm_text.strip().split("\n")
        else:
            instructions = list(asm_text)
        instructions = [i.strip() for i in instructions if i.strip()]
        self._stats.total_instructions_analyzed += len(instructions)

        # 步骤 1: 分析内存访问模式
        accesses = self._memory_analyzer.analyze_access_patterns(instructions)

        # 步骤 2: 按基址寄存器分组
        grouped = self._memory_analyzer.group_by_base_register(accesses)

        # 步骤 3: 对每个分组恢复结构体
        structs: List[RecoveredStruct] = []
        struct_index = 0

        for base_reg, group_accesses in grouped.items():
            if len(group_accesses) < 2:
                continue
            # 收集每个偏移相关的指令
            offset_instructions: Dict[int, List[str]] = defaultdict(list)
            for acc in group_accesses:
                offset_instructions[acc.offset].append(acc.instruction)
            # 构建成员列表
            members: List[StructMember] = []
            for offset, instrs in sorted(offset_instructions.items()):
                member_type, confidence = self._type_inference.infer_type_from_usage(instrs, offset)
                size = 0
                for acc in group_accesses:
                    if acc.offset == offset:
                        s = self._memory_analyzer.infer_member_size(acc)
                        size = s if size == 0 else max(size, s)
                if size == 0:
                    size = member_type.size
                array_size = max(size, 16) if member_type in (MemberType.CHAR_ARRAY, MemberType.WCHAR_ARRAY) else 0
                first_mnemonic = instrs[0].strip().lower().split()[0] if instrs and instrs[0].strip() else ""
                access_type = self._memory_analyzer._determine_access_type(first_mnemonic)
                member_name = self._generate_member_name(member_type, offset)
                members.append(StructMember(
                    name=member_name, offset=offset, size=size,
                    member_type=member_type, array_size=array_size,
                    access_type=access_type, access_count=len(instrs),
                    confidence=confidence))
            if not members:
                continue
            alignment = self._type_inference.infer_struct_alignment(group_accesses)
            max_offset = max(m.offset + m.size for m in members)
            if max_offset % alignment != 0:
                max_offset += alignment - (max_offset % alignment)
            struct_name = f"{self._struct_name_prefix}_{struct_index:04d}"
            struct_index += 1
            structs.append(RecoveredStruct(
                name=struct_name, total_size=max_offset, members=members,
                alignment=alignment))

        self._recovered_structs = structs
        self._stats.total_structs_recovered = len(structs)
        self._stats.total_members_recovered = sum(s.member_count for s in structs)
        if structs:
            confs = [m.confidence for s in structs for m in s.members]
            if confs:
                self._stats.average_confidence = sum(confs) / len(confs)
        self._stats.total_functions_analyzed = len(grouped)
        return structs

    def recover_from_binary(self, file_path: str) -> List[RecoveredStruct]:
        """从二进制文件恢复结构体。"""
        try:
            with open(file_path, "rb") as f:
                raw_data = f.read()
        except (IOError, OSError) as e:
            raise ValueError(f"无法读取二进制文件: {file_path}") from e
        return self._scan_binary_for_structs(raw_data)

    def analyze_vtable(self, file_path: str) -> List[RecoveredVTable]:
        """分析二进制文件中的虚函数表。"""
        try:
            with open(file_path, "rb") as f:
                raw_data = f.read()
        except (IOError, OSError) as e:
            raise ValueError(f"无法读取二进制文件: {file_path}") from e
        cfg_data: Dict[str, Any] = {
            "data_sections": [{"raw_data": raw_data, "address": 0}],
            "text_sections": [], "functions": [],
        }
        vtables = self._vtable_analyzer.find_vtable(cfg_data)
        self._recovered_vtables = vtables
        self._stats.total_vtables_found = len(vtables)
        self._stats.total_virtual_functions = sum(v.size for v in vtables)
        return vtables

    def analyze_class_hierarchy(
        self, structs: Optional[List[RecoveredStruct]] = None
    ) -> List[ClassHierarchy]:
        """推断类层次结构。"""
        data = structs if structs is not None else self._recovered_structs
        hierarchies = self._hierarchy_analyzer.analyze_inheritance(data)
        self._recovered_hierarchies = hierarchies
        self._stats.total_hierarchies_built = len(hierarchies)
        return hierarchies

    def generate_c_code(
        self, struct: RecoveredStruct, vtable: Optional[RecoveredVTable] = None
    ) -> str:
        """为单个结构体/类生成 C/C++ 定义。"""
        if vtable is not None or struct.has_vtable:
            return self._layout_generator.generate_cpp_class(struct, vtable)
        return self._layout_generator.generate_c_definition(struct)

    def generate_header(
        self, structs: Optional[List[RecoveredStruct]] = None,
        vtables: Optional[List[RecoveredVTable]] = None
    ) -> str:
        """生成完整的头文件。"""
        data_structs = structs if structs is not None else self._recovered_structs
        data_vtables = vtables if vtables is not None else self._recovered_vtables
        return self._layout_generator.generate_header_file(data_structs, data_vtables)

    def generate_ida_script(
        self, structs: Optional[List[RecoveredStruct]] = None
    ) -> str:
        """生成 IDA Pro 导入脚本。"""
        data = structs if structs is not None else self._recovered_structs
        return self._layout_generator.generate_ida_script(data)

    def get_statistics(self) -> EngineStatistics:
        """获取引擎运行统计信息。"""
        return self._stats

    def get_recovered_structs(self) -> List[RecoveredStruct]:
        """获取最近恢复的结构体列表。"""
        return self._recovered_structs

    def get_recovered_vtables(self) -> List[RecoveredVTable]:
        """获取最近恢复的虚表列表。"""
        return self._recovered_vtables

    def get_recovered_hierarchies(self) -> List[ClassHierarchy]:
        """获取最近恢复的类层次结构列表。"""
        return self._recovered_hierarchies

    def reset(self) -> None:
        """重置引擎状态。"""
        self._recovered_structs = []
        self._recovered_vtables = []
        self._recovered_hierarchies = []
        self._stats = EngineStatistics()

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _generate_member_name(self, member_type: MemberType, offset: int) -> str:
        prefix_map: Dict[MemberType, str] = {
            MemberType.FLOAT: "f", MemberType.DOUBLE: "dbl",
            MemberType.POINTER: "ptr", MemberType.CHAR_ARRAY: "str",
            MemberType.WCHAR_ARRAY: "wstr", MemberType.VTABLE_PTR: "vftable",
            MemberType.FUNCTION_PTR: "fn", MemberType.BITFIELD: "bits",
            MemberType.PADDING: "pad", MemberType.UNKNOWN: "unk",
        }
        prefix = prefix_map.get(member_type, "field")
        return f"{prefix}_{offset:04X}"

    def _scan_binary_for_structs(self, raw_data: bytes) -> List[RecoveredStruct]:
        """从原始二进制数据中扫描结构体模式（基本实现）。"""
        return []


# ============================================================================
# 7. 模块级便捷函数
# ============================================================================

_global_engine: Optional[StructRecoveryEngine] = None


def _get_engine() -> StructRecoveryEngine:
    """获取或创建全局引擎实例（懒加载）。"""
    global _global_engine
    if _global_engine is None:
        _global_engine = StructRecoveryEngine()
    return _global_engine


def quick_recover(
    asm_text: Union[str, List[str]], base_address: int = 0, pointer_size: int = 4,
) -> List[RecoveredStruct]:
    """快速恢复结构体（便捷函数）。

    一步完成从汇编代码到结构体定义的恢复过程。

    Example:
        >>> asm = ['mov eax, [ebp+8]', 'mov ecx, [ebp+0x0C]']
        >>> structs = quick_recover(asm)
        >>> for s in structs:
        ...     print(s.name, hex(s.total_size))
    """
    engine = _get_engine()
    engine.set_pointer_size(pointer_size)
    engine.reset()
    return engine.recover_from_asm(asm_text, base_address)


def quick_analyze_vtable(file_path: str) -> List[RecoveredVTable]:
    """快速分析虚函数表（便捷函数）。

    Example:
        >>> vtables = quick_analyze_vtable("target.dll")
        >>> for v in vtables:
        ...     print(v.class_name, v.size)
    """
    engine = _get_engine()
    engine.reset()
    return engine.analyze_vtable(file_path)


def quick_generate_header(
    structs: List[RecoveredStruct],
    vtables: Optional[List[RecoveredVTable]] = None,
) -> str:
    """快速生成头文件（便捷函数）。

    Example:
        >>> structs = quick_recover(asm_code)
        >>> header = quick_generate_header(structs)
        >>> with open("recovered.h", "w") as f:
        ...     f.write(header)
    """
    engine = _get_engine()
    return engine.generate_header(structs, vtables)


# ============================================================================
# 模块导出 & 版本
# ============================================================================

__all__ = [
    "MemberType", "AccessType",
    "StructMember", "RecoveredStruct", "VTableEntry", "RecoveredVTable", "ClassHierarchy",
    "MemoryAccessAnalyzer", "TypeInferenceEngine", "VTableAnalyzer",
    "ClassHierarchyAnalyzer", "StructLayoutGenerator",
    "StructRecoveryEngine", "EngineStatistics",
    "quick_recover", "quick_analyze_vtable", "quick_generate_header",
]

__version__ = "1.0.0"
__author__ = "San7ModMaker Team"