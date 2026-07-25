"""
汇编级代码分析器 (Assembly Code Analyzer)
提供完整的指令级分析、函数边界检测、内联Hook生成、栈帧分析、调用约定检测等功能。

引擎突破 7: 支持 x86/x64/ARM 三架构的深度汇编分析
"""

import os
import struct
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum, auto


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class Instruction:
    """反汇编指令"""
    address: int
    mnemonic: str
    op_str: str
    size: int
    bytes: bytes
    group: str = ""
    is_jump: bool = False
    is_call: bool = False
    is_ret: bool = False
    is_conditional: bool = False
    target: Optional[int] = None
    registers_read: List[str] = field(default_factory=list)
    registers_write: List[str] = field(default_factory=list)


@dataclass
class BasicBlock:
    """基本块（单入口、单出口的指令序列）"""
    start_address: int
    end_address: int
    instructions: List[Instruction] = field(default_factory=list)
    successors: List[int] = field(default_factory=list)
    predecessors: List[int] = field(default_factory=list)
    is_entry: bool = False
    is_exit: bool = False


@dataclass
class Function:
    """函数信息"""
    address: int
    end_address: int = 0
    name: str = ""
    size: int = 0
    basic_blocks: List[BasicBlock] = field(default_factory=list)
    calling_convention: str = "unknown"
    stack_frame_size: int = 0
    has_seh: bool = False
    prologue_size: int = 0
    epilogue_addresses: List[int] = field(default_factory=list)
    xrefs_from: List[int] = field(default_factory=list)
    xrefs_to: List[int] = field(default_factory=list)
    estimated_args_count: int = 0
    is_exported: bool = False
    is_imported: bool = False


@dataclass
class HookTemplate:
    """Hook 模板"""
    name: str
    hook_type: str  # detour, trampoline, inline, vtable
    original_address: int
    hook_address: int
    machine_code: bytes
    overwritten_bytes: bytes
    trampoline_code: bytes = b""
    size: int = 0
    description: str = ""


class Arch(Enum):
    """目标架构"""
    X86 = auto()
    X64 = auto()
    ARM = auto()
    ARM64 = auto()
    UNKNOWN = auto()


class CallingConvention(Enum):
    """调用约定"""
    CDECL = "cdecl"
    STDCALL = "stdcall"
    FASTCALL = "fastcall"
    THISCALL = "thiscall"
    X64_MS = "x64_ms"
    X64_SYSV = "x64_sysv"
    UNKNOWN = "unknown"


# ============================================================
# 指令模式定义
# ============================================================

# x86 函数序言模式
X86_PROLOGUE_PATTERNS = [
    b'\x55\x89\xe5',           # push ebp; mov ebp, esp
    b'\x55\x8b\xec',           # push ebp; mov ebp, esp (alt)
    b'\x83\xec',               # sub esp, imm8
    b'\x81\xec',               # sub esp, imm32
    b'\x6a\xff',               # push -1 (SEH)
    b'\x64\xa1\x00\x00\x00\x00', # mov eax, fs:[0] (SEH)
]

# x64 函数序言模式
X64_PROLOGUE_PATTERNS = [
    b'\x40\x53',               # push rbx
    b'\x48\x83\xec',           # sub rsp, imm8
    b'\x48\x81\xec',           # sub rsp, imm32
    b'\x48\x89\x5c\x24',       # mov [rsp+imm8], rbx
    b'\x48\x89\x6c\x24',       # mov [rsp+imm8], rbp
    b'\x48\x89\x74\x24',       # mov [rsp+imm8], rsi
    b'\x48\x89\x7c\x24',       # mov [rsp+imm8], rdi
]

# 函数尾声模式
X86_EPILOGUE_PATTERNS = [
    b'\xc9',                   # leave
    b'\xc3',                   # ret
    b'\xc2',                   # ret imm16
    b'\x5d\xc3',               # pop ebp; ret
    b'\x8b\xe5\x5d\xc3',       # mov esp, ebp; pop ebp; ret
]

X64_EPILOGUE_PATTERNS = [
    b'\x48\x83\xc4',           # add rsp, imm8
    b'\x48\x81\xc4',           # add rsp, imm32
    b'\xc3',                   # ret
    b'\x5b\xc3',               # pop rbx; ret
    b'\x41\x5c',               # pop r12
    b'\x41\x5d',               # pop r13
]

# 常见库函数特征模式
KNOWN_PATTERNS = {
    # 数学函数
    "sinf": (b'\xf3\x0f\x11\x44\x24', "float sin(float)"),
    "cosf": (b'\xf3\x0f\x11\x4c\x24', "float cos(float)"),
    "sqrtf": (b'\xf3\x0f\x51', "float sqrt(float)"),
    # 字符串函数
    "strlen": (b'\x8b\x4c\x24\x04\x31\xc0', "size_t strlen(const char*)"),
    "strcmp": (b'\x8b\x4c\x24\x04\x8b\x54\x24\x08', "int strcmp(const char*, const char*)"),
    "memcpy": (b'\x8b\x4c\x24\x04\x8b\x54\x24\x08', "void* memcpy(void*, const void*, size_t)"),
    "memset": (b'\x8b\x4c\x24\x04\x8b\x54\x24\x08', "void* memset(void*, int, size_t)"),
    # 内存分配
    "malloc": (b'\x8b\x4c\x24\x04\x85\xc9', "void* malloc(size_t)"),
    "free": (b'\x8b\x4c\x24\x04\x85\xc9', "void free(void*)"),
    # 安全检查
    "stack_chk_fail": (b'\xe8', "__stack_chk_fail()"),
    "security_check_cookie": (b'\x48\x8b\x0d', "__security_check_cookie()"),
}

# 寄存器名称（x86）
X86_REGS = {
    "eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp",
    "ax", "bx", "cx", "dx", "si", "di", "bp", "sp",
    "al", "ah", "bl", "bh", "cl", "ch", "dl", "dh",
    "xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7",
    "st0", "st1", "st2", "st3", "st4", "st5", "st6", "st7",
}

# 跳转指令助记符
JUMP_MNEMONICS = {
    "jmp", "jmp", "call", "ret", "retn", "retf",
    "je", "jz", "jne", "jnz", "jg", "jnle", "jge", "jnl",
    "jl", "jnge", "jle", "jng", "ja", "jnbe", "jae", "jnb",
    "jb", "jnae", "jbe", "jna", "jo", "jno", "js", "jns",
    "jp", "jpe", "jnp", "jpo", "jcxz", "jecxz", "jrcxz",
    "loop", "loope", "loopz", "loopne", "loopnz",
}

CALL_MNEMONICS = {"call"}
RET_MNEMONICS = {"ret", "retn", "retf", "iret", "iretd", "iretq"}
CONDITIONAL_JUMP_MNEMONICS = JUMP_MNEMONICS - {"jmp", "call", "ret", "retn", "retf", "iret", "iretd", "iretq"}


# ============================================================
# 汇编分析器
# ============================================================

class AsmAnalyzer:
    """
    汇编级代码分析器
    
    支持功能:
    - 反汇编 (x86/x64/ARM)
    - 指令模式匹配
    - 函数边界检测
    - 控制流图构建
    - 内联Hook生成
    - 栈帧分析
    - 调用约定检测
    """

    def __init__(self):
        self._data = b""
        self._base_address = 0
        self._arch = Arch.UNKNOWN
        self._instructions: Dict[int, Instruction] = {}
        self._functions: Dict[int, Function] = {}
        self._basic_blocks: Dict[int, BasicBlock] = {}
        self._disassembled = False
        self._capstone_available = False
        self._md = None

        # 尝试加载 Capstone
        try:
            import capstone
            self._capstone = capstone
            self._capstone_available = True
        except ImportError:
            self._capstone = None
            self._capstone_available = False

    # ============================================================
    # 初始化与数据加载
    # ============================================================

    def load_bytes(self, data: bytes, base_address: int = 0, arch: str = "x86") -> "AsmAnalyzer":
        """加载二进制数据"""
        self._data = data
        self._base_address = base_address
        self._arch = self._parse_arch(arch)
        self._instructions.clear()
        self._functions.clear()
        self._basic_blocks.clear()
        self._disassembled = False
        return self

    def load_file(self, file_path: str, base_address: int = 0, arch: str = "x86") -> dict:
        """从文件加载二进制数据"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()
            self.load_bytes(data, base_address, arch)
            return {
                "success": True,
                "message": f"加载成功: {len(data)} 字节",
                "size": len(data),
                "base_address": hex(base_address),
                "arch": self._arch.name
            }
        except Exception as e:
            return {"success": False, "message": f"加载失败: {str(e)}"}

    def _parse_arch(self, arch: str) -> Arch:
        """解析架构字符串"""
        arch_map = {
            "x86": Arch.X86, "x32": Arch.X86, "i386": Arch.X86, "i686": Arch.X86,
            "x64": Arch.X64, "x86-64": Arch.X64, "amd64": Arch.X64, "x86_64": Arch.X64,
            "arm": Arch.ARM, "arm32": Arch.ARM,
            "arm64": Arch.ARM64, "aarch64": Arch.ARM64,
        }
        return arch_map.get(arch.lower(), Arch.UNKNOWN)

    # ============================================================
    # 反汇编
    # ============================================================

    def disassemble(self, start: int = 0, end: int = None, count: int = None) -> dict:
        """反汇编指定范围"""
        if not self._data:
            return {"success": False, "message": "未加载数据"}

        if end is None:
            end = len(self._data)

        if not self._capstone_available:
            return self._disassemble_fallback(start, min(end, len(self._data)), count)

        try:
            cs_arch = self._get_capstone_arch()
            cs_mode = self._get_capstone_mode()
            self._md = self._capstone.Cs(cs_arch, cs_mode)
            self._md.detail = True

            instructions = []
            actual_count = 0
            data_view = self._data[start:end]

            for insn in self._md.disasm(data_view, self._base_address + start):
                if count and actual_count >= count:
                    break

                inst = self._parse_capstone_instruction(insn)
                instructions.append(inst)
                self._instructions[inst.address] = inst
                actual_count += 1

            self._disassembled = True
            return {
                "success": True,
                "count": len(instructions),
                "instructions": instructions,
                "range": f"{hex(self._base_address + start)} - {hex(self._base_address + end)}"
            }

        except Exception as e:
            return {"success": False, "message": f"反汇编失败: {str(e)}"}

    def _get_capstone_arch(self):
        """获取 Capstone 架构常量"""
        if self._arch in (Arch.X86, Arch.X64):
            return self._capstone.CS_ARCH_X86
        elif self._arch == Arch.ARM:
            return self._capstone.CS_ARCH_ARM
        elif self._arch == Arch.ARM64:
            return self._capstone.CS_ARCH_ARM64
        return self._capstone.CS_ARCH_X86

    def _get_capstone_mode(self):
        """获取 Capstone 模式常量"""
        if self._arch == Arch.X64:
            return self._capstone.CS_MODE_64
        elif self._arch == Arch.X86:
            return self._capstone.CS_MODE_32
        elif self._arch == Arch.ARM:
            return self._capstone.CS_MODE_ARM
        elif self._arch == Arch.ARM64:
            return self._capstone.CS_MODE_ARM
        return self._capstone.CS_MODE_32

    def _parse_capstone_instruction(self, insn) -> Instruction:
        """解析 Capstone 指令"""
        inst = Instruction(
            address=insn.address,
            mnemonic=insn.mnemonic,
            op_str=insn.op_str,
            size=insn.size,
            bytes=insn.bytes,
            is_jump=insn.mnemonic in JUMP_MNEMONICS,
            is_call=insn.mnemonic in CALL_MNEMONICS,
            is_ret=insn.mnemonic in RET_MNEMONICS,
            is_conditional=insn.mnemonic in CONDITIONAL_JUMP_MNEMONICS,
        )

        # 提取目标地址
        if insn.mnemonic in JUMP_MNEMONICS or insn.mnemonic in CALL_MNEMONICS:
            # 尝试从操作数提取地址
            op_str = insn.op_str
            if op_str.startswith("0x"):
                try:
                    inst.target = int(op_str, 16)
                except ValueError:
                    pass
            elif " " in op_str:
                # 间接跳转如 "jmp dword ptr [eax]"
                pass

        # 提取寄存器读写
        if hasattr(insn, 'regs_read'):
            inst.registers_read = [insn.reg_name(r) for r in insn.regs_read]
        if hasattr(insn, 'regs_write'):
            inst.registers_write = [insn.reg_name(r) for r in insn.regs_write]

        # 确定指令组
        inst.group = self._classify_instruction_group(inst)

        return inst

    def _classify_instruction_group(self, inst: Instruction) -> str:
        """分类指令到功能组"""
        m = inst.mnemonic.lower()

        if m in ("mov", "lea", "push", "pop", "xchg", "movsx", "movzx", "cmov"):
            return "data_transfer"
        elif m in ("add", "sub", "mul", "imul", "div", "idiv", "inc", "dec", "neg", "adc", "sbb"):
            return "arithmetic"
        elif m in ("and", "or", "xor", "not", "shl", "shr", "sal", "sar", "rol", "ror", "rcl", "rcr"):
            return "logic"
        elif m in ("cmp", "test", "bt", "bts", "btr", "btc"):
            return "compare"
        elif m in JUMP_MNEMONICS:
            return "control_flow"
        elif m in CALL_MNEMONICS:
            return "call"
        elif m in RET_MNEMONICS:
            return "return"
        elif m in ("nop", "int", "int3", "syscall", "sysenter", "sysexit", "hlt", "ud2"):
            return "system"
        elif m in ("fld", "fst", "fadd", "fsub", "fmul", "fdiv", "fcom", "fstp", "fldz", "fld1"):
            return "float"
        elif m.startswith("cmov"):
            return "conditional_move"
        elif m.startswith("set"):
            return "setcc"
        elif m.startswith("rep"):
            return "string"
        elif m in ("movs", "stos", "lods", "scas", "cmps"):
            return "string"
        elif m.startswith("pxor") or m.startswith("movd") or m.startswith("movq") or m.startswith("padd") or m.startswith("psub"):
            return "simd"
        else:
            return "other"

    def _disassemble_fallback(self, start: int, end: int, count: int = None) -> dict:
        """无 Capstone 时的回退反汇编（仅做基本字节扫描）"""
        instructions = []
        actual_count = 0
        offset = start

        while offset < end:
            if count and actual_count >= count:
                break

            # 基本指令识别（仅处理常见模式）
            byte = self._data[offset]
            addr = self._base_address + offset
            size = 1

            if byte == 0x90:  # NOP
                inst = Instruction(address=addr, mnemonic="nop", op_str="", size=1,
                                   bytes=self._data[offset:offset+1], group="system")
            elif byte == 0xC3:  # RET
                inst = Instruction(address=addr, mnemonic="ret", op_str="", size=1,
                                   bytes=self._data[offset:offset+1], group="return", is_ret=True)
            elif byte == 0xCC:  # INT3
                inst = Instruction(address=addr, mnemonic="int3", op_str="", size=1,
                                   bytes=self._data[offset:offset+1], group="system")
            elif byte == 0xE8:  # CALL rel32
                if offset + 5 <= end:
                    rel = struct.unpack("<i", self._data[offset+1:offset+5])[0]
                    target = addr + 5 + rel
                    inst = Instruction(address=addr, mnemonic="call", op_str=f"0x{target:x}", size=5,
                                       bytes=self._data[offset:offset+5], group="call", is_call=True, target=target)
                    size = 5
                else:
                    inst = Instruction(address=addr, mnemonic="db", op_str=f"0x{byte:02x}", size=1,
                                       bytes=self._data[offset:offset+1], group="other")
            elif byte == 0xE9:  # JMP rel32
                if offset + 5 <= end:
                    rel = struct.unpack("<i", self._data[offset+1:offset+5])[0]
                    target = addr + 5 + rel
                    inst = Instruction(address=addr, mnemonic="jmp", op_str=f"0x{target:x}", size=5,
                                       bytes=self._data[offset:offset+5], group="control_flow", is_jump=True, target=target)
                    size = 5
                else:
                    inst = Instruction(address=addr, mnemonic="db", op_str=f"0x{byte:02x}", size=1,
                                       bytes=self._data[offset:offset+1], group="other")
            elif byte == 0xEB:  # JMP SHORT
                if offset + 2 <= end:
                    rel = struct.unpack("<b", self._data[offset+1:offset+2])[0]
                    target = addr + 2 + rel
                    inst = Instruction(address=addr, mnemonic="jmp", op_str=f"0x{target:x}", size=2,
                                       bytes=self._data[offset:offset+2], group="control_flow", is_jump=True, target=target)
                    size = 2
                else:
                    inst = Instruction(address=addr, mnemonic="db", op_str=f"0x{byte:02x}", size=1,
                                       bytes=self._data[offset:offset+1], group="other")
            elif byte == 0x55:  # PUSH EBP
                inst = Instruction(address=addr, mnemonic="push", op_str="ebp", size=1,
                                   bytes=self._data[offset:offset+1], group="data_transfer")
            elif byte == 0x5D:  # POP EBP
                inst = Instruction(address=addr, mnemonic="pop", op_str="ebp", size=1,
                                   bytes=self._data[offset:offset+1], group="data_transfer")
            elif byte == 0xC9:  # LEAVE
                inst = Instruction(address=addr, mnemonic="leave", op_str="", size=1,
                                   bytes=self._data[offset:offset+1], group="data_transfer")
            elif byte == 0x0F:  # 两字节操作码前缀
                if offset + 2 <= end:
                    inst = Instruction(address=addr, mnemonic="db", op_str=f"0x{byte:02x} 0x{self._data[offset+1]:02x}",
                                       size=2, bytes=self._data[offset:offset+2], group="other")
                    size = 2
                else:
                    inst = Instruction(address=addr, mnemonic="db", op_str=f"0x{byte:02x}", size=1,
                                       bytes=self._data[offset:offset+1], group="other")
            else:
                inst = Instruction(address=addr, mnemonic="db", op_str=f"0x{byte:02x}", size=1,
                                   bytes=self._data[offset:offset+1], group="other")

            instructions.append(inst)
            self._instructions[addr] = inst
            offset += size
            actual_count += 1

        self._disassembled = True
        return {
            "success": True,
            "count": len(instructions),
            "instructions": instructions,
            "range": f"{hex(self._base_address + start)} - {hex(self._base_address + end)}",
            "note": "使用了回退反汇编（无Capstone），仅基础指令识别"
        }

    # ============================================================
    # 指令模式匹配
    # ============================================================

    def find_pattern(self, pattern: bytes, mask: bytes = None, start: int = 0, end: int = None) -> dict:
        """在二进制数据中搜索字节模式"""
        if not self._data:
            return {"success": False, "message": "未加载数据"}

        if end is None:
            end = len(self._data)

        results = []
        data = self._data[start:end]

        if mask:
            if len(mask) != len(pattern):
                return {"success": False, "message": "掩码长度必须与模式长度相同"}
            # 掩码模式搜索
            for i in range(len(data) - len(pattern) + 1):
                match = True
                for j in range(len(pattern)):
                    if mask[j] == ord('x') and data[i+j] != pattern[j]:
                        match = False
                        break
                if match:
                    results.append({
                        "offset": start + i,
                        "address": self._base_address + start + i,
                        "bytes": data[i:i+len(pattern)].hex()
                    })
        else:
            # 精确模式搜索
            pos = 0
            while True:
                pos = data.find(pattern, pos)
                if pos == -1:
                    break
                results.append({
                    "offset": start + pos,
                    "address": self._base_address + start + pos,
                    "bytes": data[pos:pos+len(pattern)].hex()
                })
                pos += 1

        return {
            "success": True,
            "count": len(results),
            "results": results,
            "pattern": pattern.hex(),
            "mask": mask.decode() if mask else None
        }

    def match_known_patterns(self) -> dict:
        """匹配已知库函数特征模式"""
        if not self._data:
            return {"success": False, "message": "未加载数据"}

        matches = {}
        for func_name, (pattern, signature) in KNOWN_PATTERNS.items():
            result = self.find_pattern(pattern)
            if result["success"] and result["count"] > 0:
                matches[func_name] = {
                    "signature": signature,
                    "occurrences": result["results"],
                    "count": result["count"]
                }

        return {
            "success": True,
            "matches": matches,
            "total_matched": len(matches),
            "total_occurrences": sum(m["count"] for m in matches.values())
        }

    def scan_for_patterns(self, patterns: Dict[str, bytes]) -> dict:
        """扫描自定义模式集合"""
        results = {}
        for name, pattern in patterns.items():
            result = self.find_pattern(pattern)
            if result["success"]:
                results[name] = {
                    "count": result["count"],
                    "results": result["results"]
                }
        return {"success": True, "patterns": results}

    # ============================================================
    # 函数边界检测
    # ============================================================

    def detect_functions(self) -> dict:
        """检测函数边界"""
        if not self._disassembled:
            disasm_result = self.disassemble()
            if not disasm_result["success"]:
                return disasm_result

        functions = []
        current_func = None
        sorted_addrs = sorted(self._instructions.keys())

        for addr in sorted_addrs:
            inst = self._instructions[addr]

            # 检测函数序言
            if self._is_prologue(inst):
                if current_func:
                    # 结束前一个函数
                    current_func.end_address = addr
                    current_func.size = current_func.end_address - current_func.address
                    functions.append(current_func)
                current_func = Function(address=addr)
                current_func.prologue_size = inst.size

            if current_func:
                current_func.basic_blocks.append(
                    BasicBlock(start_address=addr, end_address=addr + inst.size,
                               instructions=[inst])
                )

                # 检测调用约定
                if current_func.calling_convention == "unknown":
                    current_func.calling_convention = self._detect_calling_convention(inst)

                # 检测函数尾声
                if self._is_epilogue(inst):
                    current_func.epilogue_addresses.append(addr)

                # RET 结束函数
                if inst.is_ret and current_func:
                    current_func.end_address = addr + inst.size
                    current_func.size = current_func.end_address - current_func.address
                    functions.append(current_func)
                    current_func = None

        # 处理最后一个未结束的函数
        if current_func and current_func.address > 0:
            current_func.end_address = sorted_addrs[-1] + self._instructions[sorted_addrs[-1]].size if sorted_addrs else 0
            current_func.size = current_func.end_address - current_func.address
            functions.append(current_func)

        self._functions = {f.address: f for f in functions}

        return {
            "success": True,
            "count": len(functions),
            "functions": functions,
            "total_size": sum(f.size for f in functions)
        }

    def _is_prologue(self, inst: Instruction) -> bool:
        """检测是否为函数序言"""
        b = inst.bytes

        # x86: push ebp; mov ebp, esp
        if b == b'\x55' or b[:2] == b'\x55\x89' or b[:2] == b'\x55\x8b':
            return True

        # x64: push rbx; sub rsp, ...
        if b == b'\x40\x53' or b[:3] == b'\x48\x83\xec' or b[:3] == b'\x48\x81\xec':
            return True

        # sub esp, imm (分配栈空间)
        if b[:3] == b'\x83\xec' or b[:3] == b'\x81\xec':
            return True

        return False

    def _is_epilogue(self, inst: Instruction) -> bool:
        """检测是否为函数尾声"""
        if inst.is_ret:
            return True

        b = inst.bytes

        # leave
        if b == b'\xc9':
            return True

        # add rsp, imm
        if b[:3] == b'\x48\x83\xc4' or b[:3] == b'\x48\x81\xc4':
            return True

        # pop ebp; ret
        if b == b'\x5d' or b[:2] == b'\x5d\xc3':
            return True

        return False

    def _detect_calling_convention(self, inst: Instruction) -> str:
        """检测调用约定"""
        m = inst.mnemonic.lower()
        op = inst.op_str.lower()

        # 检测 fastcall/thiscall (ecx 作为第一个参数)
        if "ecx" in op or "rcx" in op:
            if "edx" in op or "rdx" in op:
                return "fastcall"

        # 检测 thiscall (ecx 中的 this 指针)
        if m == "mov" and ("[ecx]" in op or "[rcx]" in op):
            return "thiscall"

        return "cdecl"

    # ============================================================
    # 控制流图构建
    # ============================================================

    def build_cfg(self, function_address: int = None) -> dict:
        """构建控制流图"""
        if not self._disassembled:
            self.disassemble()

        if function_address:
            func = self._functions.get(function_address)
            if not func:
                return {"success": False, "message": f"未找到函数: {hex(function_address)}"}
            return self._build_function_cfg(func)

        # 构建所有函数的 CFG
        all_cfgs = {}
        for addr, func in self._functions.items():
            cfg = self._build_function_cfg(func)
            if cfg["success"]:
                all_cfgs[hex(addr)] = cfg

        return {
            "success": True,
            "function_count": len(all_cfgs),
            "cfgs": all_cfgs
        }

    def _build_function_cfg(self, func: Function) -> dict:
        """构建单个函数的 CFG"""
        if not func.basic_blocks:
            return {"success": False, "message": "函数无基本块"}

        nodes = []
        edges = []
        blocks = {}

        # 创建基本块
        current_block = []
        current_start = func.address

        for bb in func.basic_blocks:
            for inst in bb.instructions:
                current_block.append(inst)

                # 跳转/调用/返回结束当前基本块
                if inst.is_jump or inst.is_call or inst.is_ret:
                    block = BasicBlock(
                        start_address=current_start,
                        end_address=inst.address + inst.size,
                        instructions=current_block.copy()
                    )
                    nodes.append(block)
                    blocks[current_start] = block

                    # 添加边
                    if inst.target:
                        edges.append({
                            "from": current_start,
                            "to": inst.target,
                            "type": "call" if inst.is_call else "jump"
                        })
                        if inst.is_conditional:
                            # 条件跳转：添加 fall-through 边
                            fall_through = inst.address + inst.size
                            edges.append({
                                "from": current_start,
                                "to": fall_through,
                                "type": "fall_through"
                            })

                    current_block = []
                    current_start = inst.address + inst.size
                    break

            # 如果当前块没有以跳转结束，继续
            if current_block and current_block[-1].is_ret:
                block = BasicBlock(
                    start_address=current_start,
                    end_address=current_block[-1].address + current_block[-1].size,
                    instructions=current_block.copy(),
                    is_exit=True
                )
                nodes.append(block)
                blocks[current_start] = block
                current_block = []
                current_start = current_block[-1].address + current_block[-1].size if current_block else func.end_address

        # 处理剩余指令
        if current_block:
            block = BasicBlock(
                start_address=current_start,
                end_address=current_block[-1].address + current_block[-1].size,
                instructions=current_block.copy()
            )
            nodes.append(block)
            blocks[current_start] = block

        return {
            "success": True,
            "function": hex(func.address),
            "size": func.size,
            "nodes": len(nodes),
            "edges": len(edges),
            "blocks": blocks,
            "edge_list": edges
        }

    # ============================================================
    # 栈帧分析
    # ============================================================

    def analyze_stack_frame(self, function_address: int) -> dict:
        """分析函数栈帧"""
        if not self._disassembled:
            self.disassemble()

        func = self._functions.get(function_address)
        if not func:
            # 尝试从指令中动态分析
            if function_address in self._instructions:
                return self._analyze_stack_dynamic(function_address)
            return {"success": False, "message": f"未找到函数: {hex(function_address)}"}

        # 分析栈帧大小
        stack_size = 0
        local_vars = []
        saved_regs = []

        for bb in func.basic_blocks:
            for inst in bb.instructions:
                m = inst.mnemonic.lower()
                op = inst.op_str.lower()

                # sub esp, imm — 分配栈空间
                if m == "sub" and ("esp" in op or "rsp" in op):
                    try:
                        parts = op.replace(",", " ").split()
                        val_str = parts[-1]
                        if val_str.startswith("0x"):
                            val = int(val_str, 16)
                        else:
                            val = int(val_str)
                        if val > stack_size:
                            stack_size = val
                    except (ValueError, IndexError):
                        pass

                # push reg — 保存寄存器
                if m == "push" and op in X86_REGS:
                    saved_regs.append(op)

                # mov [ebp-xx], ... — 局部变量
                if m == "mov" and ("ebp" in op or "rbp" in op):
                    if "-" in op:
                        try:
                            offset_str = op.split("-")[1].split("]")[0].strip()
                            if offset_str.startswith("0x"):
                                offset = int(offset_str, 16)
                            else:
                                offset = int(offset_str)
                            local_vars.append({
                                "offset": f"ebp-0x{offset:x}",
                                "size": inst.size,
                                "type": "unknown"
                            })
                        except (ValueError, IndexError):
                            pass

        func.stack_frame_size = stack_size

        return {
            "success": True,
            "function": hex(function_address),
            "stack_frame_size": stack_size,
            "saved_registers": saved_regs,
            "local_variables": local_vars,
            "local_count": len(local_vars)
        }

    def _analyze_stack_dynamic(self, address: int) -> dict:
        """动态分析栈帧（无预检测函数时）"""
        if address not in self._instructions:
            return {"success": False, "message": f"地址无指令: {hex(address)}"}

        stack_size = 0
        local_vars = []
        saved_regs = []

        # 扫描后续指令
        current = address
        max_scan = 100
        scanned = 0

        while current in self._instructions and scanned < max_scan:
            inst = self._instructions[current]
            m = inst.mnemonic.lower()
            op = inst.op_str.lower()

            if m == "sub" and ("esp" in op or "rsp" in op):
                try:
                    parts = op.replace(",", " ").split()
                    val_str = parts[-1]
                    if val_str.startswith("0x"):
                        val = int(val_str, 16)
                    else:
                        val = int(val_str)
                    if val > stack_size:
                        stack_size = val
                except (ValueError, IndexError):
                    pass

            if m == "push" and op in X86_REGS:
                saved_regs.append(op)

            if inst.is_ret:
                break

            current += inst.size
            scanned += 1

        return {
            "success": True,
            "function": hex(address),
            "stack_frame_size": stack_size,
            "saved_registers": saved_regs,
            "local_variables": local_vars,
            "note": "动态分析（无预检测函数）"
        }

    # ============================================================
    # 内联 Hook 生成
    # ============================================================

    def generate_detour_hook(self, target_address: int, hook_address: int, arch: str = "x86") -> dict:
        """生成 Detour Hook（5字节 JMP）"""
        if arch == "x64":
            # x64: 使用 push + ret 或 mov rax + jmp rax
            # push low32; mov [rsp+4], high32; ret
            low = hook_address & 0xFFFFFFFF
            high = (hook_address >> 32) & 0xFFFFFFFF
            machine_code = struct.pack("<BIBBBBI",
                0x68, low,           # push low32
                0xC7, 0x44, 0x24, 0x04, high,  # mov [rsp+4], high32
            ) + b'\xC3'  # ret
            size = 14
        else:
            # x86: JMP rel32 (5字节)
            rel = hook_address - (target_address + 5)
            machine_code = b'\xE9' + struct.pack("<i", rel)
            size = 5

        return {
            "success": True,
            "hook_type": "detour",
            "target_address": hex(target_address),
            "hook_address": hex(hook_address),
            "machine_code": machine_code.hex(),
            "size": size,
            "bytes": machine_code,
            "arch": arch
        }

    def generate_trampoline(self, original_address: int, hook_address: int,
                            overwritten_size: int, arch: str = "x86") -> dict:
        """生成跳板代码（保存原始指令 + 跳回原函数）"""
        if not self._data:
            return {"success": False, "message": "未加载数据"}

        offset = original_address - self._base_address
        if offset < 0 or offset + overwritten_size > len(self._data):
            return {"success": False, "message": "地址超出范围"}

        # 复制被覆盖的原始指令
        original_bytes = self._data[offset:offset + overwritten_size]

        # 跳回原函数
        return_addr = original_address + overwritten_size
        if arch == "x64":
            low = return_addr & 0xFFFFFFFF
            high = (return_addr >> 32) & 0xFFFFFFFF
            jump_back = struct.pack("<BIBBBBI", 0x68, low, 0xC7, 0x44, 0x24, 0x04, high) + b'\xC3'
        else:
            rel = return_addr - (original_address + overwritten_size + 5)
            jump_back = b'\xE9' + struct.pack("<i", rel)

        trampoline = original_bytes + jump_back

        return {
            "success": True,
            "hook_type": "trampoline",
            "original_address": hex(original_address),
            "hook_address": hex(hook_address),
            "trampoline_code": trampoline.hex(),
            "trampoline_size": len(trampoline),
            "original_bytes": original_bytes.hex(),
            "overwritten_size": overwritten_size
        }

    def generate_inline_hook(self, target_address: int, hook_address: int,
                             trampoline_address: int, overwritten_size: int = 5,
                             arch: str = "x86") -> dict:
        """生成完整的内联 Hook（Detour + Trampoline）"""
        detour = self.generate_detour_hook(target_address, hook_address, arch)
        trampoline = self.generate_trampoline(target_address, hook_address, overwritten_size, arch)

        if not detour["success"] or not trampoline["success"]:
            return {"success": False, "message": "Hook 生成失败"}

        return {
            "success": True,
            "hook_type": "inline",
            "target_address": hex(target_address),
            "hook_address": hex(hook_address),
            "trampoline_address": hex(trampoline_address),
            "detour": detour,
            "trampoline": trampoline,
            "total_size": detour["size"] + trampoline["trampoline_size"]
        }

    def generate_vtable_hook(self, vtable_address: int, method_index: int,
                             hook_address: int, arch: str = "x86") -> dict:
        """生成虚函数表 Hook"""
        pointer_size = 8 if arch == "x64" else 4
        method_ptr_addr = vtable_address + method_index * pointer_size

        return {
            "success": True,
            "hook_type": "vtable",
            "vtable_address": hex(vtable_address),
            "method_index": method_index,
            "method_ptr_address": hex(method_ptr_addr),
            "hook_address": hex(hook_address),
            "pointer_size": pointer_size
        }

    def generate_code_cave_jump(self, cave_address: int, target_address: int,
                                arch: str = "x86") -> dict:
        """生成 Code Cave 跳转"""
        if arch == "x64":
            low = target_address & 0xFFFFFFFF
            high = (target_address >> 32) & 0xFFFFFFFF
            machine_code = struct.pack("<BIBBBBI", 0x68, low, 0xC7, 0x44, 0x24, 0x04, high) + b'\xC3'
        else:
            rel = target_address - (cave_address + 5)
            machine_code = b'\xE9' + struct.pack("<i", rel & 0xFFFFFFFF)

        return {
            "success": True,
            "cave_address": hex(cave_address),
            "target_address": hex(target_address),
            "machine_code": machine_code.hex(),
            "size": len(machine_code),
            "arch": arch
        }

    # ============================================================
    # 综合分析与统计
    # ============================================================

    def get_instruction_statistics(self) -> dict:
        """获取指令统计信息"""
        if not self._disassembled:
            self.disassemble()

        if not self._instructions:
            return {"success": False, "message": "无指令数据"}

        group_counts = {}
        mnemonic_counts = {}
        total_size = 0
        call_count = 0
        jump_count = 0
        ret_count = 0
        cond_jump_count = 0

        for inst in self._instructions.values():
            group_counts[inst.group] = group_counts.get(inst.group, 0) + 1
            mnemonic_counts[inst.mnemonic] = mnemonic_counts.get(inst.mnemonic, 0) + 1
            total_size += inst.size

            if inst.is_call:
                call_count += 1
            if inst.is_jump:
                jump_count += 1
            if inst.is_ret:
                ret_count += 1
            if inst.is_conditional:
                cond_jump_count += 1

        # 排序
        sorted_groups = sorted(group_counts.items(), key=lambda x: x[1], reverse=True)
        sorted_mnemonics = sorted(mnemonic_counts.items(), key=lambda x: x[1], reverse=True)[:30]

        return {
            "success": True,
            "total_instructions": len(self._instructions),
            "total_size": total_size,
            "group_distribution": dict(sorted_groups),
            "top_mnemonics": dict(sorted_mnemonics),
            "call_count": call_count,
            "jump_count": jump_count,
            "ret_count": ret_count,
            "conditional_jump_count": cond_jump_count,
            "arch": self._arch.name
        }

    def get_cross_references(self) -> dict:
        """获取交叉引用"""
        xrefs = {
            "calls": {},     # 谁调用了谁
            "jumps": {},     # 跳转目标
            "data_refs": {}, # 数据引用
        }

        if not self._disassembled:
            self.disassemble()

        for addr, inst in self._instructions.items():
            if inst.is_call and inst.target:
                if inst.target not in xrefs["calls"]:
                    xrefs["calls"][inst.target] = []
                xrefs["calls"][inst.target].append(addr)

            if inst.is_jump and inst.target:
                if inst.target not in xrefs["jumps"]:
                    xrefs["jumps"][inst.target] = []
                xrefs["jumps"][inst.target].append(addr)

        return {
            "success": True,
            "xrefs": xrefs,
            "call_targets": len(xrefs["calls"]),
            "jump_targets": len(xrefs["jumps"])
        }

    def find_string_references(self, strings: List[str] = None) -> dict:
        """查找字符串引用"""
        if not self._data:
            return {"success": False, "message": "未加载数据"}

        refs = {}
        search_strings = strings or []

        # 如果没有指定字符串，搜索所有可打印字符串
        if not search_strings:
            search_strings = self._extract_strings()

        # 在反汇编中查找引用
        if self._disassembled:
            for addr, inst in self._instructions.items():
                if inst.target:
                    # 检查目标地址是否指向字符串
                    offset = inst.target - self._base_address
                    if 0 <= offset < len(self._data):
                        for s in search_strings:
                            s_bytes = s.encode('utf-8', errors='ignore')
                            if self._data[offset:offset+len(s_bytes)] == s_bytes:
                                if s not in refs:
                                    refs[s] = []
                                refs[s].append({
                                    "address": hex(addr),
                                    "instruction": f"{inst.mnemonic} {inst.op_str}",
                                    "type": "instruction"
                                })

        return {
            "success": True,
            "references": refs,
            "total_unique_strings": len(refs)
        }

    def _extract_strings(self, min_length: int = 4) -> List[str]:
        """提取二进制中的可打印字符串"""
        strings = []
        current = b""
        for byte in self._data:
            if 0x20 <= byte <= 0x7E:
                current += bytes([byte])
            else:
                if len(current) >= min_length:
                    try:
                        strings.append(current.decode('ascii'))
                    except UnicodeDecodeError:
                        pass
                current = b""
        if len(current) >= min_length:
            try:
                strings.append(current.decode('ascii'))
            except UnicodeDecodeError:
                pass
        return strings

    def get_full_analysis(self) -> dict:
        """获取完整分析报告"""
        if not self._data:
            return {"success": False, "message": "未加载数据"}

        # 反汇编
        if not self._disassembled:
            self.disassemble()

        # 函数检测
        functions = self.detect_functions()

        # 指令统计
        stats = self.get_instruction_statistics()

        # 交叉引用
        xrefs = self.get_cross_references()

        # 已知模式匹配
        patterns = self.match_known_patterns()

        return {
            "success": True,
            "arch": self._arch.name,
            "data_size": len(self._data),
            "base_address": hex(self._base_address),
            "capstone_available": self._capstone_available,
            "instruction_count": len(self._instructions),
            "function_count": functions.get("count", 0),
            "statistics": stats,
            "cross_references": xrefs,
            "known_patterns": patterns,
            "functions": functions.get("functions", [])
        }

    # ============================================================
    # 辅助方法
    # ============================================================

    def get_instruction_at(self, address: int) -> Optional[Instruction]:
        """获取指定地址的指令"""
        if not self._disassembled:
            self.disassemble()
        return self._instructions.get(address)

    def get_instructions_in_range(self, start: int, end: int) -> List[Instruction]:
        """获取指定范围的指令"""
        if not self._disassembled:
            self.disassemble()
        return [i for addr, i in sorted(self._instructions.items()) if start <= addr < end]

    def get_function_at(self, address: int) -> Optional[Function]:
        """获取指定地址的函数"""
        if not self._functions:
            self.detect_functions()

        # 精确匹配
        if address in self._functions:
            return self._functions[address]

        # 范围匹配
        for func in self._functions.values():
            if func.address <= address < func.end_address:
                return func

        return None

    def get_all_functions(self) -> List[Function]:
        """获取所有函数"""
        if not self._functions:
            self.detect_functions()
        return list(self._functions.values())

    def get_arch(self) -> str:
        """获取当前架构"""
        return self._arch.name

    def is_capstone_available(self) -> bool:
        """检查 Capstone 是否可用"""
        return self._capstone_available

    def get_data_info(self) -> dict:
        """获取数据信息"""
        return {
            "size": len(self._data),
            "base_address": hex(self._base_address),
            "arch": self._arch.name,
            "disassembled": self._disassembled,
            "functions_detected": len(self._functions),
            "capstone_available": self._capstone_available
        }