"""
脚本虚拟机逆向引擎 (Script VM Reverse Engineering Engine)
提供字节码解析、指令集推断、控制流分析、伪代码生成与虚拟机状态模拟功能。

引擎突破 14: 支持 Lua 5.1/5.2/5.3、Python 字节码、自定义 VM 的深度逆向分析
"""

import os
import struct
import json
from typing import Dict, List, Optional, Tuple, Set, Any, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict, deque


# ============================================================
# 数据类型定义
# ============================================================

class OpcodeType(Enum):
    """操作码类型"""
    ARITHMETIC = "arithmetic"       # 算术运算
    LOGIC = "logic"                 # 逻辑运算
    COMPARE = "compare"             # 比较运算
    BRANCH = "branch"               # 分支跳转
    CALL = "call"                   # 函数调用
    RETURN = "return"               # 返回
    LOAD = "load"                   # 加载
    STORE = "store"                 # 存储
    MOVE = "move"                   # 移动/复制
    STACK = "stack"                 # 栈操作
    MEMORY = "memory"               # 内存操作
    CONVERT = "convert"             # 类型转换
    SYSTEM = "system"               # 系统调用
    NOP = "nop"                     # 空操作
    UNKNOWN = "unknown"             # 未知


class VMType(Enum):
    """虚拟机类型"""
    LUA_51 = "lua_5.1"
    LUA_52 = "lua_5.2"
    LUA_53 = "lua_5.3"
    LUA_54 = "lua_5.4"
    PYTHON_3X = "python_3.x"
    PYTHON_2X = "python_2.x"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class OperandType(Enum):
    """操作数类型"""
    REGISTER = "register"          # 寄存器
    CONSTANT = "constant"          # 常量索引
    IMMEDIATE = "immediate"        # 立即数
    OFFSET = "offset"              # 偏移量
    ADDRESS = "address"            # 地址
    FLAG = "flag"                  # 标志位
    STRING = "string"              # 字符串
    NONE = "none"                  # 无操作数


@dataclass
class VMOpcode:
    """虚拟机操作码定义"""
    opcode: int
    name: str
    op_type: OpcodeType
    operands: List[OperandType] = field(default_factory=list)
    description: str = ""
    is_terminator: bool = False
    is_branch: bool = False
    is_conditional: bool = False
    stack_effect: int = 0  # 正数=push, 负数=pop
    format: str = ""  # 操作数格式描述


@dataclass
class VMInstruction:
    """虚拟机指令"""
    address: int
    opcode: int
    opcode_name: str = ""
    opcode_type: OpcodeType = OpcodeType.UNKNOWN
    operands: List[Any] = field(default_factory=list)
    size: int = 0
    raw_bytes: bytes = b""
    comment: str = ""
    is_branch_target: bool = False
    is_jump: bool = False
    is_conditional: bool = False
    jump_target: Optional[int] = None
    fallthrough_target: Optional[int] = None
    line_number: int = 0


@dataclass
class BasicBlock:
    """基本块"""
    block_id: int
    start_address: int
    end_address: int
    instructions: List[VMInstruction] = field(default_factory=list)
    successors: List[int] = field(default_factory=list)
    predecessors: List[int] = field(default_factory=list)
    is_entry: bool = False
    is_exit: bool = False


@dataclass
class VMConfig:
    """虚拟机配置"""
    vm_type: VMType = VMType.UNKNOWN
    opcode_size: int = 1
    operand_size: int = 4
    is_big_endian: bool = False
    register_count: int = 256
    stack_size: int = 1024
    constant_pool_offset: int = 0
    entry_point: int = 0
    header_size: int = 0


@dataclass
class VMState:
    """虚拟机状态"""
    pc: int = 0                     # 程序计数器
    registers: Dict[int, Any] = field(default_factory=dict)
    stack: List[Any] = field(default_factory=list)
    memory: bytearray = field(default_factory=bytearray)
    flags: Dict[str, Any] = field(default_factory=dict)
    call_stack: List[int] = field(default_factory=list)
    trace: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================
# 已知 VM 操作码表
# ============================================================

# Lua 5.1 操作码 (部分)
LUA51_OPCODES = {
    0: VMOpcode(0, "MOVE", OpcodeType.MOVE, [OperandType.REGISTER, OperandType.REGISTER], "R(A) := R(B)"),
    1: VMOpcode(1, "LOADK", OpcodeType.LOAD, [OperandType.REGISTER, OperandType.CONSTANT], "R(A) := K(Bx)"),
    2: VMOpcode(2, "LOADBOOL", OpcodeType.LOAD, [OperandType.REGISTER, OperandType.IMMEDIATE, OperandType.FLAG], "R(A) := (bool)B"),
    3: VMOpcode(3, "LOADNIL", OpcodeType.LOAD, [OperandType.REGISTER, OperandType.REGISTER], "R(A)..R(B) := nil"),
    4: VMOpcode(4, "GETUPVAL", OpcodeType.LOAD, [OperandType.REGISTER, OperandType.CONSTANT], "R(A) := UpValue[B]"),
    5: VMOpcode(5, "GETGLOBAL", OpcodeType.LOAD, [OperandType.REGISTER, OperandType.CONSTANT], "R(A) := GLOBAL[K(Bx)]"),
    6: VMOpcode(6, "GETTABLE", OpcodeType.LOAD, [OperandType.REGISTER, OperandType.REGISTER, OperandType.REGISTER], "R(A) := R(B)[RK(C)]"),
    7: VMOpcode(7, "SETGLOBAL", OpcodeType.STORE, [OperandType.REGISTER, OperandType.CONSTANT], "GLOBAL[K(Bx)] := R(A)"),
    8: VMOpcode(8, "SETUPVAL", OpcodeType.STORE, [OperandType.REGISTER, OperandType.CONSTANT], "UpValue[B] := R(A)"),
    9: VMOpcode(9, "SETTABLE", OpcodeType.STORE, [OperandType.REGISTER, OperandType.REGISTER, OperandType.REGISTER], "R(A)[RK(B)] := RK(C)"),
    10: VMOpcode(10, "NEWTABLE", OpcodeType.MEMORY, [OperandType.REGISTER, OperandType.IMMEDIATE, OperandType.IMMEDIATE], "R(A) := {}"),
    11: VMOpcode(11, "SELF", OpcodeType.LOAD, [OperandType.REGISTER, OperandType.REGISTER, OperandType.REGISTER], "R(A+1) := R(B); R(A) := R(B)[RK(C)]"),
    12: VMOpcode(12, "ADD", OpcodeType.ARITHMETIC, [OperandType.REGISTER, OperandType.REGISTER, OperandType.REGISTER], "R(A) := RK(B) + RK(C)"),
    13: VMOpcode(13, "SUB", OpcodeType.ARITHMETIC, [OperandType.REGISTER, OperandType.REGISTER, OperandType.REGISTER], "R(A) := RK(B) - RK(C)"),
    14: VMOpcode(14, "MUL", OpcodeType.ARITHMETIC, [OperandType.REGISTER, OperandType.REGISTER, OperandType.REGISTER], "R(A) := RK(B) * RK(C)"),
    15: VMOpcode(15, "DIV", OpcodeType.ARITHMETIC, [OperandType.REGISTER, OperandType.REGISTER, OperandType.REGISTER], "R(A) := RK(B) / RK(C)"),
    17: VMOpcode(17, "POW", OpcodeType.ARITHMETIC, [OperandType.REGISTER, OperandType.REGISTER, OperandType.REGISTER], "R(A) := RK(B) ^ RK(C)"),
    22: VMOpcode(22, "JMP", OpcodeType.BRANCH, [OperandType.OFFSET], "pc += sBx", is_branch=True, stack_effect=0),
    23: VMOpcode(23, "EQ", OpcodeType.COMPARE, [OperandType.REGISTER, OperandType.REGISTER, OperandType.FLAG], "if RK(B)==RK(C) ~= A then pc++"),
    24: VMOpcode(24, "LT", OpcodeType.COMPARE, [OperandType.REGISTER, OperandType.REGISTER, OperandType.FLAG], "if RK(B)<RK(C) ~= A then pc++"),
    25: VMOpcode(25, "LE", OpcodeType.COMPARE, [OperandType.REGISTER, OperandType.REGISTER, OperandType.FLAG], "if RK(B)<=RK(C) ~= A then pc++"),
    26: VMOpcode(26, "TEST", OpcodeType.LOGIC, [OperandType.REGISTER, OperandType.REGISTER, OperandType.FLAG], "if not R(A) <=> C then pc++"),
    27: VMOpcode(27, "TESTSET", OpcodeType.LOGIC, [OperandType.REGISTER, OperandType.REGISTER, OperandType.FLAG], "if R(B) <=> C then R(A) := R(B) else pc++"),
    28: VMOpcode(28, "CALL", OpcodeType.CALL, [OperandType.REGISTER, OperandType.IMMEDIATE, OperandType.IMMEDIATE], "R(A)..R(A+C-2) := R(A)(R(A+1)..R(A+B-1))"),
    29: VMOpcode(29, "TAILCALL", OpcodeType.CALL, [OperandType.REGISTER, OperandType.IMMEDIATE, OperandType.IMMEDIATE], "return R(A)(R(A+1)..R(A+B-1))"),
    30: VMOpcode(30, "RETURN", OpcodeType.RETURN, [OperandType.REGISTER, OperandType.IMMEDIATE], "return R(A)..R(A+B-2)", is_terminator=True),
    31: VMOpcode(31, "FORLOOP", OpcodeType.BRANCH, [OperandType.REGISTER, OperandType.OFFSET], "R(A)+=R(A+2); if R(A)<?=R(A+1) then pc+=sBx"),
    32: VMOpcode(32, "FORPREP", OpcodeType.BRANCH, [OperandType.REGISTER, OperandType.OFFSET], "R(A)-=R(A+2); pc+=sBx"),
    34: VMOpcode(34, "SETLIST", OpcodeType.MEMORY, [OperandType.REGISTER, OperandType.IMMEDIATE, OperandType.IMMEDIATE], "R(A)[(C-1)*FPF+i] := R(A+i)"),
    35: VMOpcode(35, "CLOSE", OpcodeType.STACK, [OperandType.REGISTER], "close upvalues of R(A)"),
    36: VMOpcode(36, "CLOSURE", OpcodeType.LOAD, [OperandType.REGISTER, OperandType.CONSTANT], "R(A) := closure(KPROTO[Bx])"),
    37: VMOpcode(37, "VARARG", OpcodeType.LOAD, [OperandType.REGISTER, OperandType.IMMEDIATE], "R(A)..R(A+B-1) = vararg"),
}

# Python 3.x 字节码操作码 (部分)
PYTHON3_OPCODES = {
    1: VMOpcode(1, "POP_TOP", OpcodeType.STACK, [], "TOS = stack.pop()", stack_effect=-1),
    2: VMOpcode(2, "ROT_TWO", OpcodeType.STACK, [], "TOS, TOS1 = TOS1, TOS"),
    3: VMOpcode(3, "ROT_THREE", OpcodeType.STACK, [], "TOS, TOS1, TOS2 = TOS1, TOS2, TOS"),
    9: VMOpcode(9, "NOP", OpcodeType.NOP, [], "do nothing"),
    20: VMOpcode(20, "BINARY_MULTIPLY", OpcodeType.ARITHMETIC, [], "TOS = TOS1 * TOS", stack_effect=-1),
    23: VMOpcode(23, "BINARY_ADD", OpcodeType.ARITHMETIC, [], "TOS = TOS1 + TOS", stack_effect=-1),
    24: VMOpcode(24, "BINARY_SUBTRACT", OpcodeType.ARITHMETIC, [], "TOS = TOS1 - TOS", stack_effect=-1),
    83: VMOpcode(83, "RETURN_VALUE", OpcodeType.RETURN, [], "return TOS", is_terminator=True, stack_effect=-1),
    90: VMOpcode(90, "STORE_NAME", OpcodeType.STORE, [OperandType.CONSTANT], "namei = TOS", stack_effect=-1),
    100: VMOpcode(100, "LOAD_CONST", OpcodeType.LOAD, [OperandType.CONSTANT], "PUSH const", stack_effect=1),
    101: VMOpcode(101, "LOAD_NAME", OpcodeType.LOAD, [OperandType.CONSTANT], "PUSH name", stack_effect=1),
    106: VMOpcode(106, "COMPARE_OP", OpcodeType.COMPARE, [OperandType.IMMEDIATE], "TOS = TOS1 <cmp> TOS", stack_effect=-1),
    110: VMOpcode(110, "JUMP_FORWARD", OpcodeType.BRANCH, [OperandType.OFFSET], "pc += delta", is_branch=True),
    111: VMOpcode(111, "JUMP_IF_FALSE_OR_POP", OpcodeType.BRANCH, [OperandType.OFFSET], "if not TOS: pc+=delta; else: POP", is_conditional=True),
    112: VMOpcode(112, "JUMP_IF_TRUE_OR_POP", OpcodeType.BRANCH, [OperandType.OFFSET], "if TOS: pc+=delta; else: POP", is_conditional=True),
    113: VMOpcode(113, "JUMP_ABSOLUTE", OpcodeType.BRANCH, [OperandType.OFFSET], "pc = target", is_branch=True),
    114: VMOpcode(114, "POP_JUMP_IF_FALSE", OpcodeType.BRANCH, [OperandType.OFFSET], "if not POP: pc+=delta", is_conditional=True, stack_effect=-1),
    115: VMOpcode(115, "POP_JUMP_IF_TRUE", OpcodeType.BRANCH, [OperandType.OFFSET], "if POP: pc+=delta", is_conditional=True, stack_effect=-1),
    116: VMOpcode(116, "LOAD_GLOBAL", OpcodeType.LOAD, [OperandType.CONSTANT], "PUSH global", stack_effect=1),
    122: VMOpcode(122, "CALL", OpcodeType.CALL, [OperandType.IMMEDIATE], "call function with argc", stack_effect=-1),
    124: VMOpcode(124, "LOAD_FAST", OpcodeType.LOAD, [OperandType.REGISTER], "PUSH local", stack_effect=1),
    125: VMOpcode(125, "STORE_FAST", OpcodeType.STORE, [OperandType.REGISTER], "local = TOS", stack_effect=-1),
}


# ============================================================
# 字节码解析器
# ============================================================

class BytecodeParser:
    """
    字节码解析器
    
    支持解析多种 VM 字节码格式:
    - Lua 5.1/5.2/5.3/5.4
    - Python 2.x/3.x
    - 自定义 VM 格式
    """

    def __init__(self):
        self._data = b""
        self._vm_config = VMConfig()
        self._opcode_table: Dict[int, VMOpcode] = {}
        self._instructions: List[VMInstruction] = []
        self._constants: List[Any] = []
        self._functions: List[Dict[str, Any]] = []
        self._strings: List[str] = []

    # ============================================================
    # 数据加载
    # ============================================================

    def load_bytes(self, data: bytes) -> "BytecodeParser":
        """加载字节码数据"""
        self._data = data
        self._instructions.clear()
        self._constants.clear()
        self._functions.clear()
        self._strings.clear()
        return self

    def load_file(self, file_path: str) -> dict:
        """从文件加载字节码"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()
            self.load_bytes(data)
            return {
                "success": True,
                "message": f"加载成功: {len(data)} 字节",
                "size": len(data)
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ============================================================
    # VM 类型检测
    # ============================================================

    def detect_vm_type(self) -> dict:
        """检测虚拟机类型"""
        if len(self._data) < 4:
            return {"success": False, "message": "数据太短"}

        results = []

        # 检测 Lua 字节码
        lua_result = self._detect_lua()
        if lua_result:
            results.append(lua_result)

        # 检测 Python 字节码
        py_result = self._detect_python()
        if py_result:
            results.append(py_result)

        # 检测通用模式
        if not results:
            results.append({
                "vm_type": "custom",
                "confidence": 0.0,
                "details": "未知 VM 格式"
            })

        best = max(results, key=lambda r: r.get("confidence", 0))
        return {
            "success": True,
            "vm_type": best["vm_type"],
            "confidence": best["confidence"],
            "details": best.get("details", ""),
            "candidates": results,
        }

    def _detect_lua(self) -> Optional[dict]:
        """检测 Lua 字节码"""
        if len(self._data) < 5:
            return None

        # Lua 签名: "\x1bLua" + version byte
        if self._data[:4] == b"\x1bLua":
            version = self._data[4]
            if version == 0x51:
                return {"vm_type": "lua_5.1", "confidence": 1.0, "details": "Lua 5.1 字节码"}
            elif version == 0x52:
                return {"vm_type": "lua_5.2", "confidence": 1.0, "details": "Lua 5.2 字节码"}
            elif version == 0x53:
                return {"vm_type": "lua_5.3", "confidence": 1.0, "details": "Lua 5.3 字节码"}
            elif version == 0x54:
                return {"vm_type": "lua_5.4", "confidence": 1.0, "details": "Lua 5.4 字节码"}

        # 检测 stripped Lua 字节码 (无签名)
        if self._detect_lua_stripped():
            return {"vm_type": "lua_5.1", "confidence": 0.7, "details": "疑似 Lua 5.1 stripped 字节码"}

        return None

    def _detect_lua_stripped(self) -> bool:
        """检测 stripped Lua 字节码"""
        if len(self._data) < 8:
            return False

        # 检查是否是有效的 Lua 函数头
        try:
            # Lua 函数头通常以 source name 开始，然后 line defined, last line defined
            # 然后是 num upvalues, num params, is_vararg, max stack size
            pos = 0
            # 尝试读取 source name (可能是空字符串或字符串长度)
            string_len = self._data[pos]
            if string_len == 0:
                pos += 1
            elif string_len < 255:
                string_len = struct.unpack("<I", self._data[pos:pos + 4])[0]
                if string_len > 1024 * 1024:  # 不合理的大小
                    return False
                pos += 4 + string_len
            else:
                return False

            # 检查后续字段是否合理
            if pos + 12 > len(self._data):
                return False

            # 检查 opcode 分布
            return self._check_opcode_distribution({0: 1.0, 1: 0.5, 12: 0.3, 28: 0.2, 30: 0.1})
        except Exception:
            return False

    def _detect_python(self) -> Optional[dict]:
        """检测 Python 字节码"""
        if len(self._data) < 4:
            return None

        # Python 3.x .pyc magic number
        magic = struct.unpack("<H", self._data[:2])[0]
        # Python 3.0-3.12 magic numbers range
        if 0x0A0D <= magic <= 0x0A0D + 0x1000 or 0x0D0A <= magic <= 0x0D0A + 0x1000:
            return {"vm_type": "python_3.x", "confidence": 0.9, "details": f"Python 3.x 字节码 (magic=0x{magic:04X})"}

        # Python 2.x .pyc magic
        if magic in (0x03F3, 0x6161, 0x6226, 0x632E, 0x642E, 0x652E, 0x662E, 0x033E):
            return {"vm_type": "python_2.x", "confidence": 0.9, "details": f"Python 2.x 字节码 (magic=0x{magic:04X})"}

        return None

    def _get_code_offset(self, vm_type: str) -> int:
        """计算代码起始偏移（跳过文件头和函数头）"""
        if vm_type.startswith("lua_"):
            if len(self._data) < 12:
                return 0
            # Lua 文件头: 12 字节
            offset = 12
            # Lua 函数头:
            #   1 byte: source name (0 = 空)
            #   4 bytes: line defined
            #   4 bytes: last line defined
            #   1 byte: num upvalues
            #   1 byte: num params
            #   1 byte: is_vararg
            #   1 byte: max stack size
            #   4 bytes: instruction count
            if offset + 1 > len(self._data):
                return 0
            source_len = self._data[offset]
            if source_len == 0:
                offset += 1
            else:
                offset += 1 + source_len  # size byte + string
            offset += 4 + 4 + 1 + 1 + 1 + 1 + 4  # 16 bytes
            return min(offset, len(self._data))
        return 0

    def _check_opcode_distribution(self, expected_freq: Dict[int, float]) -> bool:
        """检查操作码分布是否符合预期"""
        if len(self._data) < 100:
            return False

        # 简单检查: 统计每个字节的出现频率，看是否集中在少数值
        byte_counts = defaultdict(int)
        for b in self._data[:min(500, len(self._data))]:
            byte_counts[b] += 1

        # 常见 VM 操作码通常在 0-50 范围
        in_range = sum(1 for b in byte_counts if b <= 50)
        total = len(byte_counts)
        if total == 0:
            return False

        return in_range / total > 0.5

    # ============================================================
    # 操作码表加载
    # ============================================================

    def load_opcode_table(self, vm_type: str) -> dict:
        """加载已知操作码表"""
        if vm_type in ("lua_5.1", "lua_51"):
            self._opcode_table = LUA51_OPCODES.copy()
            self._vm_config.vm_type = VMType.LUA_51
            self._vm_config.opcode_size = 4
            self._vm_config.operand_size = 0
        elif vm_type in ("lua_5.2", "lua_52"):
            self._opcode_table = LUA51_OPCODES.copy()  # Lua 5.2 类似
            self._vm_config.vm_type = VMType.LUA_51
            self._vm_config.opcode_size = 4
            self._vm_config.operand_size = 0
        elif vm_type in ("lua_5.3", "lua_53"):
            self._opcode_table = LUA51_OPCODES.copy()
            self._vm_config.vm_type = VMType.LUA_51
            self._vm_config.opcode_size = 4
            self._vm_config.operand_size = 0
        elif vm_type in ("lua_5.4", "lua_54"):
            self._opcode_table = LUA51_OPCODES.copy()
            self._vm_config.vm_type = VMType.LUA_51
            self._vm_config.opcode_size = 4
            self._vm_config.operand_size = 0
        elif vm_type in ("python_3.x", "python_3", "python3"):
            self._opcode_table = PYTHON3_OPCODES.copy()
            self._vm_config.vm_type = VMType.PYTHON_3X
            self._vm_config.opcode_size = 1
            self._vm_config.operand_size = 2
        else:
            return {"success": False, "message": f"不支持的操作码表: {vm_type}"}

        return {
            "success": True,
            "vm_type": vm_type,
            "opcode_count": len(self._opcode_table),
        }

    def add_custom_opcode(self, opcode: int, name: str, op_type: str,
                          operands: List[str] = None,
                          description: str = "") -> dict:
        """添加自定义操作码"""
        try:
            op_type_enum = OpcodeType(op_type)
        except ValueError:
            return {"success": False, "message": f"无效的操作码类型: {op_type}"}

        operand_types = []
        for op in (operands or []):
            try:
                operand_types.append(OperandType(op))
            except ValueError:
                return {"success": False, "message": f"无效的操作数类型: {op}"}

        self._opcode_table[opcode] = VMOpcode(
            opcode=opcode,
            name=name,
            op_type=op_type_enum,
            operands=operand_types,
            description=description,
        )

        return {"success": True, "opcode": opcode, "name": name}

    def get_opcode_table(self) -> dict:
        """获取当前操作码表"""
        return {
            "success": True,
            "opcode_count": len(self._opcode_table),
            "opcodes": {
                str(k): {
                    "name": v.name,
                    "type": v.op_type.value,
                    "operands": [op.value for op in v.operands],
                    "description": v.description,
                }
                for k, v in sorted(self._opcode_table.items())
            },
        }

    # ============================================================
    # 指令反汇编
    # ============================================================

    def disassemble(self, start: int = 0, end: int = None,
                    count: int = None) -> dict:
        """反汇编字节码"""
        if not self._data:
            return {"success": False, "message": "未加载数据"}

        if not self._opcode_table:
            return {"success": False, "message": "未加载操作码表"}

        if end is None:
            end = len(self._data)

        self._instructions = []
        pos = start
        addresses = set()

        while pos < end:
            if count and len(self._instructions) >= count:
                break

            if pos + self._vm_config.opcode_size > end:
                break

            # 读取操作码
            if self._vm_config.opcode_size == 1:
                opcode = self._data[pos]
                pos += 1
            elif self._vm_config.opcode_size == 2:
                opcode = struct.unpack("<H" if not self._vm_config.is_big_endian else ">H",
                                       self._data[pos:pos + 2])[0]
                pos += 2
            else:
                opcode = struct.unpack("<I" if not self._vm_config.is_big_endian else ">I",
                                       self._data[pos:pos + 4])[0]
                pos += 4

            # 查找操作码定义
            opcode_def = self._opcode_table.get(opcode)
            if not opcode_def:
                opcode_def = VMOpcode(
                    opcode=opcode,
                    name=f"UNK_{opcode:02X}",
                    op_type=OpcodeType.UNKNOWN,
                    operands=[OperandType.IMMEDIATE],
                )

            # 读取操作数
            operands = []
            raw_size = self._vm_config.opcode_size
            if self._vm_config.operand_size > 0:
                for op_type in opcode_def.operands:
                    if pos + self._vm_config.operand_size > end:
                        break

                    if op_type == OperandType.REGISTER:
                        val = self._data[pos]
                        operands.append(val)
                        pos += 1
                        raw_size += 1
                    elif op_type in (OperandType.CONSTANT, OperandType.IMMEDIATE,
                                     OperandType.OFFSET, OperandType.ADDRESS):
                        if self._vm_config.operand_size == 2:
                            val = struct.unpack("<h" if not self._vm_config.is_big_endian else ">h",
                                                self._data[pos:pos + 2])[0]
                        else:
                            val = struct.unpack("<i" if not self._vm_config.is_big_endian else ">i",
                                                self._data[pos:pos + 4])[0]
                        operands.append(val)
                        pos += self._vm_config.operand_size
                        raw_size += self._vm_config.operand_size
                    elif op_type == OperandType.FLAG:
                        val = self._data[pos] & 0x01
                        operands.append(val)
                        pos += 1
                        raw_size += 1
            elif self._vm_config.opcode_size == 4:
                # 操作数嵌入在 32-bit 指令字中 (Lua 5.1 格式)
                # A = bits 6-13, B = bits 23-31, C = bits 14-22
                for i, op_type in enumerate(opcode_def.operands):
                    if i == 0:
                        val = (opcode >> 6) & 0xFF
                    elif i == 1:
                        # 对于 CONSTANT/ADDRESS 类型，使用 Bx (bits 14-31, 18 bits)
                        if op_type in (OperandType.CONSTANT, OperandType.ADDRESS):
                            val = (opcode >> 14) & 0x3FFFF
                        else:
                            val = (opcode >> 23) & 0x1FF
                    elif i == 2:
                        val = (opcode >> 14) & 0x1FF
                    else:
                        val = 0
                    operands.append(val)

            # 计算跳转目标
            jump_target = None
            fallthrough = None
            if opcode_def.is_branch and operands:
                if opcode_def.op_type == OpcodeType.BRANCH:
                    jump_target = pos + operands[-1] * self._vm_config.operand_size
                if opcode_def.is_conditional:
                    fallthrough = pos

            inst = VMInstruction(
                address=pos - raw_size,
                opcode=opcode,
                opcode_name=opcode_def.name,
                opcode_type=opcode_def.op_type,
                operands=operands,
                size=raw_size,
                raw_bytes=self._data[pos - raw_size:pos],
                is_jump=opcode_def.is_branch,
                is_conditional=opcode_def.is_conditional,
                jump_target=jump_target,
                fallthrough_target=fallthrough,
                comment=opcode_def.description,
            )

            self._instructions.append(inst)
            addresses.add(inst.address)

            if opcode_def.is_terminator:
                # 遇到终止符，可选继续
                pass

        return {
            "success": True,
            "instruction_count": len(self._instructions),
            "range": f"{hex(start)} - {hex(pos)}",
            "instructions": [
                {
                    "address": i.address,
                    "opcode": i.opcode,
                    "name": i.opcode_name,
                    "type": i.opcode_type.value,
                    "operands": i.operands,
                    "size": i.size,
                    "is_jump": i.is_jump,
                    "is_conditional": i.is_conditional,
                    "jump_target": i.jump_target,
                    "comment": i.comment,
                }
                for i in self._instructions[:100]
            ],
        }

    def disassemble_file(self, file_path: str, vm_type: str = "lua_5.1") -> dict:
        """从文件反汇编"""
        load_result = self.load_file(file_path)
        if not load_result["success"]:
            return load_result

        table_result = self.load_opcode_table(vm_type)
        if not table_result["success"]:
            return table_result

        return self.disassemble()

    # ============================================================
    # 操作码统计
    # ============================================================

    def get_opcode_statistics(self) -> dict:
        """获取操作码统计信息"""
        if not self._instructions:
            return {"success": False, "message": "未反汇编"}

        counts = defaultdict(int)
        type_counts = defaultdict(int)
        for inst in self._instructions:
            counts[inst.opcode_name] += 1
            type_counts[inst.opcode_type.value] += 1

        total = len(self._instructions)
        sorted_ops = sorted(counts.items(), key=lambda x: -x[1])

        return {
            "success": True,
            "total_instructions": total,
            "unique_opcodes": len(counts),
            "opcode_counts": {k: v for k, v in sorted_ops[:20]},
            "type_distribution": {
                k: round(v / max(total, 1), 4)
                for k, v in sorted(type_counts.items(), key=lambda x: -x[1])
            },
            "top_5": [{"name": k, "count": v, "percentage": round(v / max(total, 1) * 100, 1)}
                      for k, v in sorted_ops[:5]],
        }


# ============================================================
# 控制流分析器
# ============================================================

class ControlFlowAnalyzer:
    """
    控制流分析器
    
    构建控制流图 (CFG):
    - 基本块划分
    - 支配关系分析
    - 循环检测
    - 数据流分析
    """

    def __init__(self):
        self._instructions: List[VMInstruction] = []
        self._basic_blocks: Dict[int, BasicBlock] = {}
        self._entry_block_id: int = 0
        self._exit_block_id: int = -1

    def load_instructions(self, instructions: List[dict]) -> "ControlFlowAnalyzer":
        """加载指令列表"""
        self._instructions = []
        for inst_dict in instructions:
            inst = VMInstruction(
                address=inst_dict.get("address", 0),
                opcode=inst_dict.get("opcode", 0),
                opcode_name=inst_dict.get("name", ""),
                opcode_type=OpcodeType(inst_dict.get("type", "unknown")),
                operands=inst_dict.get("operands", []),
                size=inst_dict.get("size", 0),
                is_jump=inst_dict.get("is_jump", False),
                is_conditional=inst_dict.get("is_conditional", False),
                jump_target=inst_dict.get("jump_target"),
                fallthrough_target=inst_dict.get("fallthrough_target"),
            )
            self._instructions.append(inst)
        self._basic_blocks.clear()
        return self

    def build_cfg(self) -> dict:
        """构建控制流图"""
        if not self._instructions:
            return {"success": False, "message": "无指令"}

        self._basic_blocks.clear()

        # 步骤 1: 识别基本块入口点 (leaders)
        leaders = self._find_leaders()

        # 步骤 2: 划分基本块
        self._partition_blocks(leaders)

        # 步骤 3: 建立块间连接
        self._connect_blocks()

        # 步骤 4: 分析循环
        loops = self._detect_loops()

        return {
            "success": True,
            "block_count": len(self._basic_blocks),
            "entry_block": self._entry_block_id,
            "exit_block": self._exit_block_id,
            "blocks": {
                str(bid): {
                    "start_address": bb.start_address,
                    "end_address": bb.end_address,
                    "instruction_count": len(bb.instructions),
                    "successors": bb.successors,
                    "predecessors": bb.predecessors,
                    "is_entry": bb.is_entry,
                    "is_exit": bb.is_exit,
                    "instructions": [
                        {"address": i.address, "name": i.opcode_name}
                        for i in bb.instructions
                    ],
                }
                for bid, bb in self._basic_blocks.items()
            },
            "loops": loops,
        }

    def _find_leaders(self) -> Set[int]:
        """找到基本块入口点"""
        leaders = set()
        if self._instructions:
            leaders.add(self._instructions[0].address)

        for i, inst in enumerate(self._instructions):
            # 跳转目标
            if inst.jump_target is not None:
                leaders.add(inst.jump_target)
            # 条件跳转后的下一条指令
            if inst.fallthrough_target is not None:
                leaders.add(inst.fallthrough_target)
            # 跳转指令后的下一条指令
            if inst.is_jump and i + 1 < len(self._instructions):
                leaders.add(self._instructions[i + 1].address)
            # 调用指令后的下一条指令
            if inst.opcode_type == OpcodeType.CALL and i + 1 < len(self._instructions):
                leaders.add(self._instructions[i + 1].address)
            # 返回指令后的下一条指令 (可能被调用返回)
            if inst.opcode_type == OpcodeType.RETURN and i + 1 < len(self._instructions):
                leaders.add(self._instructions[i + 1].address)

        return leaders

    def _partition_blocks(self, leaders: Set[int]):
        """划分基本块"""
        block_id = 0
        current_block = None

        for inst in self._instructions:
            if inst.address in leaders:
                # 保存当前块
                if current_block and current_block.instructions:
                    current_block.end_address = current_block.instructions[-1].address
                    self._basic_blocks[block_id - 1] = current_block

                # 开始新块
                current_block = BasicBlock(
                    block_id=block_id,
                    start_address=inst.address,
                    end_address=inst.address,
                )
                block_id += 1

            if current_block:
                current_block.instructions.append(inst)

        # 保存最后一个块
        if current_block and current_block.instructions:
            current_block.end_address = current_block.instructions[-1].address
            self._basic_blocks[block_id - 1] = current_block

        # 标记入口和出口
        if self._basic_blocks:
            self._entry_block_id = 0
            # 出口块: 最后一条指令是返回的块
            for bid, bb in self._basic_blocks.items():
                if bb.instructions and bb.instructions[-1].opcode_type == OpcodeType.RETURN:
                    self._exit_block_id = bid
                    bb.is_exit = True
                    break
            # 如果没有返回指令，最后一个块是出口
            if self._exit_block_id == -1 and self._basic_blocks:
                last_bid = max(self._basic_blocks.keys())
                self._basic_blocks[last_bid].is_exit = True
                self._exit_block_id = last_bid

            # 入口块
            if 0 in self._basic_blocks:
                self._basic_blocks[0].is_entry = True

    def _connect_blocks(self):
        """建立块间连接"""
        # 构建地址到块ID的映射
        addr_to_block = {}
        for bid, bb in self._basic_blocks.items():
            addr_to_block[bb.start_address] = bid

        for bid, bb in self._basic_blocks.items():
            if not bb.instructions:
                continue

            last_inst = bb.instructions[-1]

            # 无条件跳转
            if last_inst.is_jump and not last_inst.is_conditional:
                if last_inst.jump_target is not None:
                    target_bid = addr_to_block.get(last_inst.jump_target)
                    if target_bid is not None:
                        bb.successors.append(target_bid)
                        self._basic_blocks[target_bid].predecessors.append(bid)

            # 条件跳转
            elif last_inst.is_conditional:
                if last_inst.jump_target is not None:
                    target_bid = addr_to_block.get(last_inst.jump_target)
                    if target_bid is not None:
                        bb.successors.append(target_bid)
                        self._basic_blocks[target_bid].predecessors.append(bid)

                # fallthrough
                if last_inst.fallthrough_target is not None:
                    fall_bid = addr_to_block.get(last_inst.fallthrough_target)
                    if fall_bid is not None:
                        bb.successors.append(fall_bid)
                        self._basic_blocks[fall_bid].predecessors.append(bid)

            # 返回指令 (无后继)
            elif last_inst.opcode_type == OpcodeType.RETURN:
                pass  # 无后继

            # 普通指令 (顺序执行)
            else:
                next_bid = bid + 1
                if next_bid in self._basic_blocks:
                    bb.successors.append(next_bid)
                    self._basic_blocks[next_bid].predecessors.append(bid)

    def _detect_loops(self) -> List[Dict[str, Any]]:
        """检测循环"""
        loops = []
        visited = set()
        in_stack = set()

        def dfs(block_id, path):
            if block_id in in_stack:
                # 找到循环
                loop_start = path.index(block_id)
                loop_blocks = path[loop_start:]
                loops.append({
                    "header": block_id,
                    "blocks": loop_blocks,
                    "size": len(loop_blocks),
                })
                return

            if block_id in visited:
                return

            visited.add(block_id)
            in_stack.add(block_id)

            bb = self._basic_blocks.get(block_id)
            if bb:
                for succ in bb.successors:
                    dfs(succ, path + [block_id])

            in_stack.discard(block_id)

        if self._entry_block_id in self._basic_blocks:
            dfs(self._entry_block_id, [])

        return loops

    # ============================================================
    # 数据流分析
    # ============================================================

    def analyze_registers(self) -> dict:
        """分析寄存器使用"""
        if not self._instructions:
            return {"success": False, "message": "无指令"}

        read_regs = defaultdict(int)
        write_regs = defaultdict(int)
        reg_last_write = {}
        reg_live_range = defaultdict(list)

        for i, inst in enumerate(self._instructions):
            operands = inst.operands
            if inst.opcode_name in ("MOVE", "LOADK", "GETGLOBAL", "GETTABLE", "LOADBOOL",
                                    "LOADNIL", "GETUPVAL", "NEWTABLE", "SELF", "CLOSURE"):
                if operands:
                    write_regs[operands[0]] += 1
                    reg_last_write[operands[0]] = i
                    reg_live_range[operands[0]].append(i)

            elif inst.opcode_name in ("SETGLOBAL", "SETTABLE", "SETUPVAL", "RETURN"):
                if operands:
                    read_regs[operands[0]] += 1
                    if operands[0] in reg_last_write:
                        reg_live_range[operands[0]].append(i)

            elif inst.opcode_name in ("ADD", "SUB", "MUL", "DIV", "POW",
                                      "EQ", "LT", "LE"):
                if len(operands) >= 3:
                    write_regs[operands[0]] += 1
                    read_regs[operands[1]] += 1
                    read_regs[operands[2]] += 1

            elif inst.opcode_name == "CALL":
                if operands:
                    read_regs[operands[0]] += 1

        return {
            "success": True,
            "read_registers": dict(read_regs),
            "write_registers": dict(write_regs),
            "most_read": sorted(read_regs.items(), key=lambda x: -x[1])[:10],
            "most_written": sorted(write_regs.items(), key=lambda x: -x[1])[:10],
            "total_registers_used": len(set(read_regs.keys()) | set(write_regs.keys())),
        }

    def analyze_stack(self) -> dict:
        """分析栈使用"""
        if not self._instructions:
            return {"success": False, "message": "无指令"}

        stack_depth = 0
        max_depth = 0
        min_depth = 0
        depth_history = []

        for inst in self._instructions:
            # 估算栈效果
            effect = 0
            name = inst.opcode_name

            if name in ("LOADK", "LOADBOOL", "GETGLOBAL", "GETTABLE", "GETUPVAL",
                        "NEWTABLE", "SELF", "CLOSURE", "VARARG", "LOAD_CONST",
                        "LOAD_NAME", "LOAD_FAST", "LOAD_GLOBAL"):
                effect = 1
            elif name in ("SETGLOBAL", "SETTABLE", "SETUPVAL", "STORE_NAME",
                          "STORE_FAST", "POP_TOP"):
                effect = -1
            elif name in ("CALL",):
                effect = -inst.operands[1] if len(inst.operands) > 1 else -1
            elif name == "RETURN":
                effect = -inst.operands[1] if len(inst.operands) > 1 else -1
            elif name in ("ADD", "SUB", "MUL", "DIV", "POW", "BINARY_ADD",
                          "BINARY_SUBTRACT", "BINARY_MULTIPLY"):
                effect = -1  # 2 pop, 1 push

            stack_depth += effect
            max_depth = max(max_depth, stack_depth)
            min_depth = min(min_depth, stack_depth)
            depth_history.append(stack_depth)

        return {
            "success": True,
            "max_depth": max_depth,
            "min_depth": min_depth,
            "final_depth": stack_depth,
            "depth_range": max_depth - min_depth,
            "depth_history": depth_history[:100],
        }


# ============================================================
# 伪代码生成器
# ============================================================

class PseudoCodeGenerator:
    """
    伪代码生成器
    
    将字节码翻译为可读的伪代码:
    - 控制流结构 (if/else/while/for)
    - 函数调用
    - 变量赋值
    """

    def __init__(self):
        self._instructions: List[VMInstruction] = []
        self._indent = 0
        self._output: List[str] = []
        self._label_map: Dict[int, str] = {}

    def load_instructions(self, instructions: List[dict]) -> "PseudoCodeGenerator":
        """加载指令"""
        self._instructions = []
        for inst_dict in instructions:
            inst = VMInstruction(
                address=inst_dict.get("address", 0),
                opcode=inst_dict.get("opcode", 0),
                opcode_name=inst_dict.get("name", ""),
                opcode_type=OpcodeType(inst_dict.get("type", "unknown")),
                operands=inst_dict.get("operands", []),
                size=inst_dict.get("size", 0),
                is_jump=inst_dict.get("is_jump", False),
                is_conditional=inst_dict.get("is_conditional", False),
                jump_target=inst_dict.get("jump_target"),
                comment=inst_dict.get("comment", ""),
            )
            self._instructions.append(inst)
        return self

    def generate(self) -> dict:
        """生成伪代码"""
        if not self._instructions:
            return {"success": False, "message": "无指令"}

        self._output = []
        self._indent = 0

        # 识别跳转目标标签
        self._build_labels()

        # 逐条翻译
        i = 0
        while i < len(self._instructions):
            inst = self._instructions[i]

            # 输出标签
            if inst.address in self._label_map:
                self._output.append(f"{self._label_map[inst.address]}:")

            # 翻译指令
            line = self._translate_instruction(inst)
            if line:
                self._output.append(f"{'  ' * self._indent}{line}")

            i += 1

        return {
            "success": True,
            "line_count": len(self._output),
            "code": "\n".join(self._output),
            "lines": self._output,
        }

    def _build_labels(self):
        """构建标签映射"""
        for inst in self._instructions:
            if inst.jump_target is not None:
                if inst.jump_target not in self._label_map:
                    self._label_map[inst.jump_target] = f"L_{len(self._label_map)}"

    def _translate_instruction(self, inst: VMInstruction) -> str:
        """翻译单条指令"""
        name = inst.opcode_name
        ops = inst.operands

        # Lua 操作码翻译
        translations = {
            "MOVE": lambda: f"R{ops[0]} = R{ops[1]}" if len(ops) >= 2 else f"R{ops[0]} = ?",
            "LOADK": lambda: f"R{ops[0]} = K[{ops[1]}]" if len(ops) >= 2 else f"R{ops[0]} = ?",
            "LOADBOOL": lambda: f"R{ops[0]} = {bool(ops[1]) if len(ops) > 1 else 'False'}",
            "LOADNIL": lambda: f"R{ops[0]}..R{ops[1]} = nil" if len(ops) >= 2 else f"R{ops[0]} = nil",
            "GETGLOBAL": lambda: f"R{ops[0]} = _G[K[{ops[1]}]]" if len(ops) >= 2 else f"R{ops[0]} = _G[?]",
            "SETGLOBAL": lambda: f"_G[K[{ops[1]}]] = R{ops[0]}" if len(ops) >= 2 else f"_G[?] = R{ops[0]}",
            "GETTABLE": lambda: f"R{ops[0]} = R{ops[1]}[R{ops[2]}]" if len(ops) >= 3 else f"R{ops[0]} = ?[?]",
            "SETTABLE": lambda: f"R{ops[0]}[R{ops[1]}] = R{ops[2]}" if len(ops) >= 3 else f"?[?] = ?",
            "ADD": lambda: f"R{ops[0]} = R{ops[1]} + R{ops[2]}" if len(ops) >= 3 else f"R{ops[0]} = ? + ?",
            "SUB": lambda: f"R{ops[0]} = R{ops[1]} - R{ops[2]}" if len(ops) >= 3 else f"R{ops[0]} = ? - ?",
            "MUL": lambda: f"R{ops[0]} = R{ops[1]} * R{ops[2]}" if len(ops) >= 3 else f"R{ops[0]} = ? * ?",
            "DIV": lambda: f"R{ops[0]} = R{ops[1]} / R{ops[2]}" if len(ops) >= 3 else f"R{ops[0]} = ? / ?",
            "POW": lambda: f"R{ops[0]} = R{ops[1]} ^ R{ops[2]}" if len(ops) >= 3 else f"R{ops[0]} = ? ^ ?",
            "EQ": lambda: f"if R{ops[1]} {'==' if ops[2] else '~='} R{ops[2]} then skip next" if len(ops) >= 3 else "compare",
            "LT": lambda: f"if R{ops[1]} {'<' if ops[2] else '>='} R{ops[2]} then skip next" if len(ops) >= 3 else "compare",
            "LE": lambda: f"if R{ops[1]} {'<=' if ops[2] else '>'} R{ops[2]} then skip next" if len(ops) >= 3 else "compare",
            "JMP": lambda: f"goto {self._label_map.get(inst.jump_target, '?')}" if inst.jump_target else "goto ?",
            "CALL": lambda: f"R{ops[0]}..R{ops[0]+ops[2]-2} = R{ops[0]}(...)" if len(ops) >= 3 else f"call R{ops[0]}",
            "TAILCALL": lambda: f"return R{ops[0]}(...)" if ops else "tail call",
            "RETURN": lambda: f"return R{ops[0]}..R{ops[0]+ops[1]-2}" if len(ops) >= 2 else "return",
            "CLOSURE": lambda: f"R{ops[0]} = function(...)" if ops else "closure",
            "NEWTABLE": lambda: f"R{ops[0]} = {{}}" if ops else "R{ops[0]} = {}",
            "FORLOOP": lambda: f"R{ops[0]} += R{ops[0]+2}; if R{ops[0]} <= R{ops[0]+1} then continue",
            "FORPREP": lambda: f"R{ops[0]} -= R{ops[0]+2}; goto loop",
            "SETLIST": lambda: f"R{ops[0]}[...] = R{ops[0]+1}..R{ops[0]+ops[2]}" if len(ops) >= 3 else "set list",
            "VARARG": lambda: f"R{ops[0]}..R{ops[0]+ops[1]-1} = ..." if len(ops) >= 2 else "vararg",
            "SELF": lambda: f"R{ops[0]+1} = R{ops[1]}; R{ops[0]} = R{ops[1]}[R{ops[2]}]" if len(ops) >= 3 else "self",
            "TESTSET": lambda: f"if R{ops[1]} then R{ops[0]} = R{ops[1]} else skip" if len(ops) >= 2 else "testset",
            "TEST": lambda: f"if not R{ops[0]} then skip" if ops else "test",
            # Python 操作码
            "LOAD_CONST": lambda: f"PUSH const[{ops[0]}]" if ops else "PUSH const",
            "LOAD_NAME": lambda: f"PUSH {ops[0]}" if ops else "PUSH name",
            "LOAD_FAST": lambda: f"PUSH local_{ops[0]}" if ops else "PUSH local",
            "LOAD_GLOBAL": lambda: f"PUSH global[{ops[0]}]" if ops else "PUSH global",
            "STORE_NAME": lambda: f"name[{ops[0]}] = POP" if ops else "name = POP",
            "STORE_FAST": lambda: f"local_{ops[0]} = POP" if ops else "local = POP",
            "BINARY_ADD": lambda: "POP; POP; PUSH(TOS1 + TOS)",
            "BINARY_SUBTRACT": lambda: "POP; POP; PUSH(TOS1 - TOS)",
            "BINARY_MULTIPLY": lambda: "POP; POP; PUSH(TOS1 * TOS)",
            "COMPARE_OP": lambda: f"POP; POP; PUSH(TOS1 <cmp_{ops[0]}> TOS)" if ops else "compare",
            "RETURN_VALUE": lambda: "return POP",
            "POP_TOP": lambda: "POP",
            "JUMP_FORWARD": lambda: f"goto {self._label_map.get(inst.jump_target, '?')}" if inst.jump_target else "goto ?",
            "JUMP_ABSOLUTE": lambda: f"goto {self._label_map.get(inst.jump_target, '?')}" if inst.jump_target else "goto ?",
            "POP_JUMP_IF_FALSE": lambda: f"if not POP: goto {self._label_map.get(inst.jump_target, '?')}" if inst.jump_target else "if not POP: goto ?",
            "POP_JUMP_IF_TRUE": lambda: f"if POP: goto {self._label_map.get(inst.jump_target, '?')}" if inst.jump_target else "if POP: goto ?",
            "CALL": lambda: f"call_function({ops[0] if ops else '?'})" if ops else "call",
            "NOP": lambda: "nop",
        }

        translator = translations.get(name)
        if translator:
            return translator()

        # 未知操作码
        comment = f"  # {inst.comment}" if inst.comment else ""
        return f"{name} {ops}{comment}"


# ============================================================
# VM 状态模拟器
# ============================================================

class VMStateSimulator:
    """
    VM 状态模拟器
    
    模拟虚拟机执行:
    - 寄存器/栈操作
    - 控制流
    - 执行追踪
    """

    def __init__(self):
        self._state = VMState()
        self._instructions: List[VMInstruction] = []
        self._addr_to_idx: Dict[int, int] = {}
        self._max_steps: int = 10000
        self._step_count: int = 0

    def load_instructions(self, instructions: List[dict]) -> "VMStateSimulator":
        """加载指令"""
        self._instructions = []
        self._addr_to_idx = {}
        for i, inst_dict in enumerate(instructions):
            inst = VMInstruction(
                address=inst_dict.get("address", 0),
                opcode=inst_dict.get("opcode", 0),
                opcode_name=inst_dict.get("name", ""),
                opcode_type=OpcodeType(inst_dict.get("type", "unknown")),
                operands=inst_dict.get("operands", []),
                size=inst_dict.get("size", 0),
                is_jump=inst_dict.get("is_jump", False),
                is_conditional=inst_dict.get("is_conditional", False),
                jump_target=inst_dict.get("jump_target"),
                fallthrough_target=inst_dict.get("fallthrough_target"),
            )
            self._instructions.append(inst)
            self._addr_to_idx[inst.address] = i
        return self

    def simulate(self, max_steps: int = 1000, initial_state: Dict[str, Any] = None) -> dict:
        """模拟执行"""
        self._max_steps = max_steps
        self._step_count = 0
        self._state = VMState()

        # 初始化状态
        if initial_state:
            for k, v in initial_state.get("registers", {}).items():
                self._state.registers[int(k)] = v
            self._state.pc = initial_state.get("pc", 0)

        trace = []

        try:
            while self._step_count < self._max_steps:
                if self._state.pc not in self._addr_to_idx:
                    break

                idx = self._addr_to_idx[self._state.pc]
                inst = self._instructions[idx]

                # 记录执行前状态
                trace_entry = {
                    "step": self._step_count,
                    "address": inst.address,
                    "opcode": inst.opcode_name,
                    "operands": inst.operands,
                    "pc_before": self._state.pc,
                }

                # 执行指令
                next_pc = self._execute_instruction(inst)

                trace_entry["pc_after"] = next_pc
                trace_entry["registers"] = dict(self._state.registers)
                trace_entry["stack"] = list(self._state.stack)
                trace.append(trace_entry)

                self._state.pc = next_pc
                self._step_count += 1

                if inst.opcode_type == OpcodeType.RETURN:
                    break

        except Exception as e:
            return {
                "success": False,
                "message": f"模拟执行失败: {str(e)}",
                "step": self._step_count,
                "trace": trace,
            }

        return {
            "success": True,
            "total_steps": self._step_count,
            "final_pc": self._state.pc,
            "final_registers": dict(self._state.registers),
            "final_stack": list(self._state.stack),
            "trace": trace,
        }

    def _execute_instruction(self, inst: VMInstruction) -> int:
        """执行单条指令，返回下一个 PC"""
        name = inst.opcode_name
        ops = inst.operands
        next_pc = inst.address + inst.size

        # Lua 风格指令
        if name == "MOVE" and len(ops) >= 2:
            self._state.registers[ops[0]] = self._state.registers.get(ops[1], 0)
        elif name == "LOADK" and len(ops) >= 2:
            self._state.registers[ops[0]] = ops[1]
        elif name == "LOADBOOL" and len(ops) >= 2:
            self._state.registers[ops[0]] = bool(ops[1])
        elif name == "LOADNIL" and len(ops) >= 2:
            for r in range(ops[0], ops[1] + 1):
                self._state.registers[r] = None
        elif name == "ADD" and len(ops) >= 3:
            self._state.registers[ops[0]] = (
                self._state.registers.get(ops[1], 0) +
                self._state.registers.get(ops[2], 0)
            )
        elif name == "SUB" and len(ops) >= 3:
            self._state.registers[ops[0]] = (
                self._state.registers.get(ops[1], 0) -
                self._state.registers.get(ops[2], 0)
            )
        elif name == "MUL" and len(ops) >= 3:
            self._state.registers[ops[0]] = (
                self._state.registers.get(ops[1], 0) *
                self._state.registers.get(ops[2], 0)
            )
        elif name == "DIV" and len(ops) >= 3:
            divisor = self._state.registers.get(ops[2], 1)
            self._state.registers[ops[0]] = (
                self._state.registers.get(ops[1], 0) / divisor if divisor != 0 else 0
            )
        elif name == "JMP" and ops:
            if inst.jump_target is not None:
                next_pc = inst.jump_target
        elif name == "EQ" and len(ops) >= 3:
            a = self._state.registers.get(ops[1], 0)
            b = self._state.registers.get(ops[2], 0)
            if (a == b) != bool(ops[0] if len(ops) > 2 else 0):
                next_pc += inst.size  # skip next
        elif name == "LT" and len(ops) >= 3:
            a = self._state.registers.get(ops[1], 0)
            b = self._state.registers.get(ops[2], 0)
            if (a < b) != bool(ops[0] if len(ops) > 2 else 0):
                next_pc += inst.size
        elif name == "CALL" and len(ops) >= 3:
            # 模拟: 设置返回值
            func = self._state.registers.get(ops[0])
            if func is not None:
                for r in range(ops[2]):
                    self._state.registers[ops[0] + r] = f"ret_{r}"
        elif name == "RETURN":
            pass  # 终止
        elif name == "FORLOOP" and len(ops) >= 2:
            self._state.registers[ops[0]] = self._state.registers.get(ops[0], 0) + 1
            limit = self._state.registers.get(ops[0] + 1, 0)
            if self._state.registers[ops[0]] <= limit:
                if inst.jump_target is not None:
                    next_pc = inst.jump_target
        elif name == "FORPREP" and len(ops) >= 2:
            self._state.registers[ops[0]] = self._state.registers.get(ops[0], 0) - 1
            if inst.jump_target is not None:
                next_pc = inst.jump_target
        elif name == "CLOSURE" and ops:
            self._state.registers[ops[0]] = f"<function_{ops[0]}>"
        elif name == "NEWTABLE" and ops:
            self._state.registers[ops[0]] = {}
        elif name == "SELF" and len(ops) >= 3:
            self._state.registers[ops[0] + 1] = self._state.registers.get(ops[1], 0)
            self._state.registers[ops[0]] = self._state.registers.get(ops[1], {})
        elif name == "GETGLOBAL" and len(ops) >= 2:
            self._state.registers[ops[0]] = f"<global_{ops[1]}>"
        elif name == "SETGLOBAL" and len(ops) >= 2:
            pass  # 模拟全局变量设置
        elif name == "LOAD_CONST" and ops:
            self._state.stack.append(ops[0])
        elif name == "LOAD_FAST" and ops:
            self._state.stack.append(self._state.registers.get(ops[0], 0))
        elif name == "STORE_FAST" and ops:
            if self._state.stack:
                self._state.registers[ops[0]] = self._state.stack.pop()
        elif name == "BINARY_ADD":
            if len(self._state.stack) >= 2:
                b = self._state.stack.pop()
                a = self._state.stack.pop()
                self._state.stack.append(a + b)
        elif name == "BINARY_SUBTRACT":
            if len(self._state.stack) >= 2:
                b = self._state.stack.pop()
                a = self._state.stack.pop()
                self._state.stack.append(a - b)
        elif name == "BINARY_MULTIPLY":
            if len(self._state.stack) >= 2:
                b = self._state.stack.pop()
                a = self._state.stack.pop()
                self._state.stack.append(a * b)
        elif name == "RETURN_VALUE":
            if self._state.stack:
                self._state.stack.pop()
        elif name == "POP_TOP":
            if self._state.stack:
                self._state.stack.pop()
        elif name == "JUMP_FORWARD" and ops:
            if inst.jump_target is not None:
                next_pc = inst.jump_target
        elif name == "POP_JUMP_IF_FALSE" and ops:
            if self._state.stack:
                val = self._state.stack.pop()
                if not val and inst.jump_target is not None:
                    next_pc = inst.jump_target
        elif name == "POP_JUMP_IF_TRUE" and ops:
            if self._state.stack:
                val = self._state.stack.pop()
                if val and inst.jump_target is not None:
                    next_pc = inst.jump_target

        return next_pc


# ============================================================
# 指令集推断器
# ============================================================

class InstructionSetInferrer:
    """
    指令集推断器
    
    从原始字节码推断操作码语义:
    - 操作码频率分析
    - 操作数模式识别
    - 控制流结构识别
    - 与已知 VM 比对
    """

    def __init__(self):
        self._data = b""
        self._inferred_opcodes: Dict[int, VMOpcode] = {}

    def load_bytes(self, data: bytes) -> "InstructionSetInferrer":
        """加载数据"""
        self._data = data
        self._inferred_opcodes.clear()
        return self

    def infer(self, opcode_size: int = 1, operand_size: int = 4) -> dict:
        """推断指令集"""
        if not self._data:
            return {"success": False, "message": "未加载数据"}

        # 步骤 1: 统计操作码频率
        opcode_freq = self._analyze_opcode_frequency(opcode_size)

        # 步骤 2: 分析操作数分布
        operand_patterns = self._analyze_operand_patterns(opcode_size, operand_size)

        # 步骤 3: 识别控制流指令
        control_flow = self._identify_control_flow(opcode_size, operand_size)

        # 步骤 4: 推断操作码类型
        inferred = self._classify_opcodes(opcode_freq, operand_patterns, control_flow)

        # 步骤 5: 与已知 VM 比对
        matches = self._match_known_vms(opcode_freq)

        return {
            "success": True,
            "inferred_opcodes": inferred,
            "opcode_frequency": opcode_freq,
            "operand_patterns": operand_patterns,
            "control_flow_ops": control_flow,
            "known_vm_matches": matches,
            "confidence": self._calculate_confidence(matches),
        }

    def _analyze_opcode_frequency(self, opcode_size: int) -> Dict[int, int]:
        """分析操作码频率"""
        freq = defaultdict(int)
        for i in range(0, len(self._data) - opcode_size + 1, opcode_size):
            if opcode_size == 1:
                opcode = self._data[i]
            elif opcode_size == 2:
                opcode = struct.unpack("<H", self._data[i:i + 2])[0]
            else:
                opcode = struct.unpack("<I", self._data[i:i + 4])[0]
            freq[opcode] += 1
        return dict(sorted(freq.items(), key=lambda x: -x[1]))

    def _analyze_operand_patterns(self, opcode_size: int, operand_size: int) -> Dict[int, List[int]]:
        """分析操作数分布模式"""
        patterns = defaultdict(list)
        step = opcode_size + operand_size

        for i in range(0, len(self._data) - step + 1, step):
            if opcode_size == 1:
                opcode = self._data[i]
            else:
                opcode = struct.unpack("<H", self._data[i:i + 2])[0]

            if operand_size == 2:
                operand = struct.unpack("<h", self._data[i + opcode_size:i + step])[0]
            else:
                operand = struct.unpack("<i", self._data[i + opcode_size:i + step])[0]

            patterns[opcode].append(operand)

        return {k: v[:20] for k, v in patterns.items()}

    def _identify_control_flow(self, opcode_size: int, operand_size: int) -> Dict[int, str]:
        """识别控制流指令"""
        control_flow = {}
        step = opcode_size + operand_size

        for i in range(0, len(self._data) - step + 1, step):
            if opcode_size == 1:
                opcode = self._data[i]
            else:
                opcode = struct.unpack("<H", self._data[i:i + 2])[0]

            if operand_size == 4:
                operand = struct.unpack("<i", self._data[i + opcode_size:i + step])[0]
            else:
                operand = struct.unpack("<h", self._data[i + opcode_size:i + step])[0]

            # 正向跳转 = 条件跳转候选
            if operand > 0 and operand < 1000:
                if opcode not in control_flow:
                    control_flow[opcode] = "conditional_jump"
            # 负向跳转 = 循环跳转候选
            elif operand < 0 and operand > -1000:
                if opcode not in control_flow or control_flow[opcode] != "conditional_jump":
                    control_flow[opcode] = "backward_jump"

        return control_flow

    def _classify_opcodes(self, freq: Dict[int, int], patterns: Dict[int, List[int]],
                          control_flow: Dict[int, str]) -> List[Dict[str, Any]]:
        """分类推断的操作码"""
        sorted_ops = sorted(freq.items(), key=lambda x: -x[1])
        inferred = []

        for opcode, count in sorted_ops[:20]:
            op_type = "unknown"
            description = ""

            if opcode in control_flow:
                cf = control_flow[opcode]
                if cf == "conditional_jump":
                    op_type = "branch"
                    description = "条件跳转"
                elif cf == "backward_jump":
                    op_type = "branch"
                    description = "循环跳转"

            if opcode == 0:
                op_type = "move"
                description = "可能的 MOVE 操作码"
            elif count > len(self._data) * 0.05:
                op_type = "load"
                description = "高频操作码，可能是 LOAD"

            pat = patterns.get(opcode, [])
            if pat:
                all_positive = all(p >= 0 for p in pat)
                all_small = all(0 <= p < 256 for p in pat)
                if all_small and all_positive:
                    description += " (操作数范围: 0-255，可能是寄存器)"

            inferred.append({
                "opcode": opcode,
                "frequency": count,
                "percentage": round(count / max(len(self._data) // (1 + 4), 1) * 100, 1),
                "inferred_type": op_type,
                "description": description,
                "sample_operands": pat[:5],
            })

        return inferred

    def _match_known_vms(self, freq: Dict[int, int]) -> List[Dict[str, Any]]:
        """与已知 VM 对比"""
        matches = []

        # 与 Lua 5.1 对比
        lua_match = self._compare_opcode_sets(freq, LUA51_OPCODES)
        if lua_match > 0.3:
            matches.append({"vm": "lua_5.1", "similarity": round(lua_match, 3)})

        # 与 Python 3.x 对比
        py_match = self._compare_opcode_sets(freq, PYTHON3_OPCODES)
        if py_match > 0.3:
            matches.append({"vm": "python_3.x", "similarity": round(py_match, 3)})

        matches.sort(key=lambda x: -x["similarity"])
        return matches

    def _compare_opcode_sets(self, freq: Dict[int, int],
                             known: Dict[int, VMOpcode]) -> float:
        """比较操作码集合相似度"""
        known_set = set(known.keys())
        observed_set = set(freq.keys())
        overlap = known_set & observed_set
        return len(overlap) / max(len(known_set), 1)

    def _calculate_confidence(self, matches: List[Dict[str, Any]]) -> float:
        """计算推断置信度"""
        if not matches:
            return 0.0
        return matches[0]["similarity"]


# ============================================================
# 脚本虚拟机逆向引擎（主入口）
# ============================================================

class ScriptVMEngine:
    """
    脚本虚拟机逆向引擎（主入口）
    
    整合字节码解析、控制流分析、伪代码生成、状态模拟、指令集推断五大子系统。
    """

    def __init__(self):
        self.parser = BytecodeParser()
        self.cfg_analyzer = ControlFlowAnalyzer()
        self.codegen = PseudoCodeGenerator()
        self.simulator = VMStateSimulator()
        self.inferrer = InstructionSetInferrer()

    # ============================================================
    # 综合分析
    # ============================================================

    def analyze(self, file_path: str, vm_type: str = None) -> dict:
        """综合分析脚本文件"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()

            # 检测 VM 类型
            self.parser.load_bytes(data)
            detection = self.parser.detect_vm_type()
            detected_type = detection.get("vm_type", "unknown")

            # 使用检测到的或指定的 VM 类型
            use_type = vm_type or detected_type
            if use_type not in ("lua_5.1", "lua_5.2", "lua_5.3", "lua_5.4",
                                "python_3.x", "python_2.x"):
                use_type = "lua_5.1"  # 默认

            # 加载操作码表
            table_result = self.parser.load_opcode_table(use_type)
            if not table_result["success"]:
                return table_result

            # 计算代码起始偏移（跳过 Lua 文件头）
            start_offset = self.parser._get_code_offset(use_type)

            # 反汇编
            disasm_result = self.parser.disassemble(start=start_offset)
            if not disasm_result["success"]:
                return disasm_result

            instructions = disasm_result["instructions"]

            # 控制流分析
            self.cfg_analyzer.load_instructions(instructions)
            cfg_result = self.cfg_analyzer.build_cfg()

            # 伪代码生成
            self.codegen.load_instructions(instructions)
            pseudo_result = self.codegen.generate()

            # 操作码统计
            stats_result = self.parser.get_opcode_statistics()

            # 栈分析
            stack_result = self.cfg_analyzer.analyze_stack()

            # 寄存器分析
            reg_result = self.cfg_analyzer.analyze_registers()

            return {
                "success": True,
                "file": os.path.basename(file_path),
                "vm_type": detected_type,
                "detection_confidence": detection.get("confidence", 0),
                "instruction_count": disasm_result["instruction_count"],
                "block_count": cfg_result.get("block_count", 0),
                "pseudo_code_lines": pseudo_result.get("line_count", 0),
                "opcode_stats": stats_result,
                "cfg": cfg_result,
                "pseudo_code": pseudo_result.get("code", ""),
                "stack_analysis": stack_result,
                "register_analysis": reg_result,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ============================================================
    # 反汇编
    # ============================================================

    def disassemble(self, data: bytes, vm_type: str = "lua_5.1") -> dict:
        """反汇编字节码"""
        self.parser.load_bytes(data)
        table_result = self.parser.load_opcode_table(vm_type)
        if not table_result["success"]:
            return table_result
        return self.parser.disassemble()

    def disassemble_file(self, file_path: str, vm_type: str = "lua_5.1") -> dict:
        """从文件反汇编"""
        return self.parser.disassemble_file(file_path, vm_type)

    # ============================================================
    # VM 类型检测
    # ============================================================

    def detect_vm_type(self, data: bytes) -> dict:
        """检测 VM 类型"""
        self.parser.load_bytes(data)
        return self.parser.detect_vm_type()

    def detect_vm_type_file(self, file_path: str) -> dict:
        """从文件检测 VM 类型"""
        if not os.path.exists(file_path):
            return {"success": False, "message": "文件不存在"}

        with open(file_path, "rb") as f:
            data = f.read()
        return self.detect_vm_type(data)

    # ============================================================
    # 操作码表管理
    # ============================================================

    def load_opcode_table(self, vm_type: str) -> dict:
        """加载操作码表"""
        return self.parser.load_opcode_table(vm_type)

    def add_custom_opcode(self, opcode: int, name: str, op_type: str,
                          operands: List[str] = None,
                          description: str = "") -> dict:
        """添加自定义操作码"""
        return self.parser.add_custom_opcode(opcode, name, op_type, operands, description)

    def get_opcode_table(self) -> dict:
        """获取操作码表"""
        return self.parser.get_opcode_table()

    # ============================================================
    # 控制流分析
    # ============================================================

    def build_cfg(self, instructions: List[dict]) -> dict:
        """构建控制流图"""
        self.cfg_analyzer.load_instructions(instructions)
        return self.cfg_analyzer.build_cfg()

    def analyze_registers(self, instructions: List[dict]) -> dict:
        """分析寄存器使用"""
        self.cfg_analyzer.load_instructions(instructions)
        return self.cfg_analyzer.analyze_registers()

    def analyze_stack(self, instructions: List[dict]) -> dict:
        """分析栈使用"""
        self.cfg_analyzer.load_instructions(instructions)
        return self.cfg_analyzer.analyze_stack()

    # ============================================================
    # 伪代码生成
    # ============================================================

    def generate_pseudo_code(self, instructions: List[dict]) -> dict:
        """生成伪代码"""
        self.codegen.load_instructions(instructions)
        return self.codegen.generate()

    # ============================================================
    # 状态模拟
    # ============================================================

    def simulate(self, instructions: List[dict], max_steps: int = 1000,
                 initial_state: dict = None) -> dict:
        """模拟执行"""
        self.simulator.load_instructions(instructions)
        return self.simulator.simulate(max_steps, initial_state)

    # ============================================================
    # 指令集推断
    # ============================================================

    def infer_instruction_set(self, data: bytes, opcode_size: int = 1,
                              operand_size: int = 4) -> dict:
        """推断指令集"""
        self.inferrer.load_bytes(data)
        return self.inferrer.infer(opcode_size, operand_size)


# ============================================================
# 辅助函数
# ============================================================

def quick_detect(file_path: str) -> dict:
    """快捷函数: 快速检测 VM 类型"""
    engine = ScriptVMEngine()
    return engine.detect_vm_type_file(file_path)


def quick_disassemble(data: bytes, vm_type: str = "lua_5.1") -> dict:
    """快捷函数: 快速反汇编"""
    engine = ScriptVMEngine()
    return engine.disassemble(data, vm_type)