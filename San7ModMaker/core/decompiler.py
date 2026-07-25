"""
反编译与符号执行引擎 (Decompiler & Symbolic Execution Engine)
提供汇编到伪C代码的反编译、SSA形式构建、符号执行、约束求解与控制流结构恢复。

引擎突破 18: 支持 x86/x64 反编译、SSA 中间表示、符号执行路径探索、约束求解、结构恢复
"""

import os
import re
import struct
import copy
import json
from typing import Dict, List, Optional, Tuple, Set, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict, deque


# ============================================================
# 枚举与数据类
# ============================================================

class InstructionType(Enum):
    """指令类型"""
    # 数据移动
    MOV = "mov"
    PUSH = "push"
    POP = "pop"
    LEA = "lea"
    XCHG = "xchg"
    # 算术
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    IMUL = "imul"
    DIV = "div"
    IDIV = "idiv"
    INC = "inc"
    DEC = "dec"
    NEG = "neg"
    # 逻辑
    AND = "and"
    OR = "or"
    XOR = "xor"
    NOT = "not"
    SHL = "shl"
    SHR = "shr"
    SAR = "sar"
    # 比较
    CMP = "cmp"
    TEST = "test"
    # 跳转
    JMP = "jmp"
    JE = "je"
    JNE = "jne"
    JZ = "jz"
    JNZ = "jnz"
    JG = "jg"
    JGE = "jge"
    JL = "jl"
    JLE = "jle"
    JA = "ja"
    JAE = "jae"
    JB = "jb"
    JBE = "jbe"
    JO = "jo"
    JNO = "jno"
    JS = "js"
    JNS = "jns"
    # 调用
    CALL = "call"
    RET = "ret"
    # 字符串
    MOVS = "movs"
    STOS = "stos"
    LODS = "lods"
    SCAS = "scas"
    CMPS = "cmps"
    REP = "rep"
    # 其他
    NOP = "nop"
    LEAVE = "leave"
    INT = "int"
    SYSCALL = "syscall"
    UNKNOWN = "unknown"


class OperandType(Enum):
    """操作数类型"""
    REGISTER = "register"
    IMMEDIATE = "immediate"
    MEMORY = "memory"
    LABEL = "label"


class SymbolicOp(Enum):
    """符号操作类型"""
    CONST = "const"
    VAR = "var"
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    MOD = "%"
    AND = "&"
    OR = "|"
    XOR = "^"
    SHL = "<<"
    SHR = ">>"
    NEG = "neg"
    NOT = "~"
    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    LOAD = "load"
    STORE = "store"
    ITE = "ite"  # if-then-else
    CONCAT = "concat"
    EXTRACT = "extract"
    ZEXT = "zext"
    SEXT = "sext"


class BranchType(Enum):
    """分支类型"""
    UNCONDITIONAL = "unconditional"
    TRUE_BRANCH = "true_branch"
    FALSE_BRANCH = "false_branch"
    CALL = "call"
    RETURN = "return"
    SWITCH = "switch"


class StructureType(Enum):
    """控制流结构类型"""
    SEQUENCE = "sequence"
    IF_THEN = "if_then"
    IF_THEN_ELSE = "if_then_else"
    WHILE_LOOP = "while_loop"
    DO_WHILE = "do_while"
    FOR_LOOP = "for_loop"
    SWITCH = "switch"
    BREAK = "break"
    CONTINUE = "continue"


@dataclass
class Operand:
    """操作数"""
    type: OperandType
    value: Any = None
    size: int = 4

    def __str__(self):
        if self.type == OperandType.REGISTER:
            return str(self.value)
        elif self.type == OperandType.IMMEDIATE:
            return f"0x{self.value:X}" if isinstance(self.value, int) else str(self.value)
        elif self.type == OperandType.MEMORY:
            return f"[{self.value}]"
        elif self.type == OperandType.LABEL:
            return f"loc_{self.value:X}"
        return str(self.value)


@dataclass
class Instruction:
    """指令"""
    address: int
    mnemonic: str
    op_type: InstructionType = InstructionType.UNKNOWN
    operands: List[Operand] = field(default_factory=list)
    bytes_data: bytes = b""
    size: int = 0
    comment: str = ""
    # 控制流
    is_jump: bool = False
    is_conditional: bool = False
    is_call: bool = False
    is_return: bool = False
    jump_target: Optional[int] = None
    fallthrough_target: Optional[int] = None

    def __str__(self):
        ops = ", ".join(str(o) for o in self.operands)
        return f"{self.mnemonic} {ops}"


@dataclass
class BasicBlock:
    """基本块"""
    id: int
    start_address: int
    end_address: int
    instructions: List[Instruction] = field(default_factory=list)
    # 后继
    successors: List[int] = field(default_factory=list)  # block IDs
    # 前驱
    predecessors: List[int] = field(default_factory=list)
    # 结构信息
    is_loop_header: bool = False
    is_loop_exit: bool = False
    loop_depth: int = 0

    @property
    def size(self) -> int:
        return self.end_address - self.start_address


@dataclass
class SSAVariable:
    """SSA 变量"""
    name: str
    version: int = 0
    original_reg: str = ""
    defined_at: Optional[int] = None  # instruction address

    def __str__(self):
        return f"{self.name}_{self.version}"


@dataclass
class SymbolicExpr:
    """符号表达式"""
    op: SymbolicOp
    args: List[Any] = field(default_factory=list)  # SymbolicExpr, int, or SSAVariable
    size: int = 4

    def __str__(self):
        if self.op == SymbolicOp.CONST:
            return f"0x{self.args[0]:X}" if isinstance(self.args[0], int) else str(self.args[0])
        elif self.op == SymbolicOp.VAR:
            return str(self.args[0])
        elif len(self.args) == 0:
            return str(self.op.value)
        elif len(self.args) == 1:
            return f"{self.op.value}({self.args[0]})"
        elif len(self.args) == 2:
            return f"({self.args[0]} {self.op.value} {self.args[1]})"
        elif self.op == SymbolicOp.ITE:
            return f"({self.args[0]} ? {self.args[1]} : {self.args[2]})"
        return f"{self.op.value}({', '.join(str(a) for a in self.args)})"

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if not isinstance(other, SymbolicExpr):
            return False
        return self.op == other.op and self.args == other.args

    def __hash__(self):
        return hash((self.op, tuple(self.args)))


@dataclass
class Constraint:
    """约束"""
    expr: SymbolicExpr
    is_true: bool = True  # True: expr must be true, False: expr must be false

    def __str__(self):
        prefix = "" if self.is_true else "!"
        return f"{prefix}({self.expr})"


@dataclass
class PathState:
    """符号执行路径状态"""
    path_id: int
    address: int
    registers: Dict[str, SymbolicExpr] = field(default_factory=dict)
    memory: Dict[int, SymbolicExpr] = field(default_factory=dict)
    constraints: List[Constraint] = field(default_factory=list)
    depth: int = 0
    parent_id: Optional[int] = None

    def clone(self) -> "PathState":
        return PathState(
            path_id=self.path_id,
            address=self.address,
            registers=dict(self.registers),
            memory=dict(self.memory),
            constraints=list(self.constraints),
            depth=self.depth,
            parent_id=self.parent_id,
        )


@dataclass
class ControlStructure:
    """控制流结构"""
    type: StructureType
    header_address: int
    body: List[Any] = field(default_factory=list)  # nested structures or instructions
    else_body: List[Any] = field(default_factory=list)
    condition: str = ""
    exit_address: int = 0
    follow_address: int = 0


@dataclass
class FunctionInfo:
    """函数信息"""
    name: str
    start_address: int
    end_address: int
    basic_blocks: List[BasicBlock] = field(default_factory=list)
    arguments: List[str] = field(default_factory=list)
    local_vars: List[str] = field(default_factory=list)
    return_type: str = "void"
    calling_convention: str = "cdecl"


# ============================================================
# 指令解码器
# ============================================================

# x86 寄存器
REGISTERS_32 = ["eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi"]
REGISTERS_16 = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"]
REGISTERS_8 = ["al", "cl", "dl", "bl", "ah", "ch", "dh", "bh"]
REGISTERS_64 = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
                "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"]

ALL_REGISTERS = set(REGISTERS_32 + REGISTERS_16 + REGISTERS_8 + REGISTERS_64)

# 条件跳转映射
CONDITIONAL_JUMPS = {
    "je": "==", "jz": "==",
    "jne": "!=", "jnz": "!=",
    "jg": ">", "jge": ">=",
    "jl": "<", "jle": "<=",
    "ja": ">", "jae": ">=",
    "jb": "<", "jbe": "<=",
    "jo": "overflow", "jno": "!overflow",
    "js": "negative", "jns": "!negative",
    "jp": "parity", "jnp": "!parity",
}

# 指令类型映射
MNEMONIC_TO_TYPE = {
    "mov": InstructionType.MOV, "push": InstructionType.PUSH, "pop": InstructionType.POP,
    "lea": InstructionType.LEA, "xchg": InstructionType.XCHG,
    "add": InstructionType.ADD, "sub": InstructionType.SUB,
    "mul": InstructionType.MUL, "imul": InstructionType.IMUL,
    "div": InstructionType.DIV, "idiv": InstructionType.IDIV,
    "inc": InstructionType.INC, "dec": InstructionType.DEC, "neg": InstructionType.NEG,
    "and": InstructionType.AND, "or": InstructionType.OR, "xor": InstructionType.XOR,
    "not": InstructionType.NOT, "shl": InstructionType.SHL, "shr": InstructionType.SHR,
    "sar": InstructionType.SAR, "cmp": InstructionType.CMP, "test": InstructionType.TEST,
    "jmp": InstructionType.JMP, "je": InstructionType.JE, "jne": InstructionType.JNE,
    "jz": InstructionType.JZ, "jnz": InstructionType.JNZ,
    "jg": InstructionType.JG, "jge": InstructionType.JGE,
    "jl": InstructionType.JL, "jle": InstructionType.JLE,
    "ja": InstructionType.JA, "jae": InstructionType.JAE,
    "jb": InstructionType.JB, "jbe": InstructionType.JBE,
    "jo": InstructionType.JO, "jno": InstructionType.JNO,
    "js": InstructionType.JS, "jns": InstructionType.JNS,
    "call": InstructionType.CALL, "ret": InstructionType.RET,
    "nop": InstructionType.NOP, "leave": InstructionType.LEAVE,
    "int": InstructionType.INT, "syscall": InstructionType.SYSCALL,
}


class InstructionDecoder:
    """指令解码器 — 将汇编文本或原始字节解析为指令对象"""

    @staticmethod
    def parse_asm_line(line: str) -> Optional[Instruction]:
        """解析单行汇编文本"""
        line = line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            return None

        # 解析地址
        parts = line.split(None, 1)
        if not parts:
            return None

        address = 0
        rest = parts[0]
        try:
            address = int(parts[0], 16)
            rest = parts[1] if len(parts) > 1 else ""
        except ValueError:
            rest = line

        # 解析助记符
        rest = rest.strip()
        mnemonic_parts = rest.split(None, 1)
        mnemonic = mnemonic_parts[0].lower().strip()
        operands_str = mnemonic_parts[1] if len(mnemonic_parts) > 1 else ""

        # 解析操作数
        operands = []
        if operands_str:
            for op_str in operands_str.split(","):
                op = InstructionDecoder._parse_operand(op_str.strip())
                if op:
                    operands.append(op)

        # 确定指令类型
        op_type = MNEMONIC_TO_TYPE.get(mnemonic, InstructionType.UNKNOWN)

        inst = Instruction(
            address=address,
            mnemonic=mnemonic,
            op_type=op_type,
            operands=operands,
        )

        # 控制流属性
        inst.is_jump = mnemonic in ("jmp", "call", "ret") or mnemonic in CONDITIONAL_JUMPS
        inst.is_conditional = mnemonic in CONDITIONAL_JUMPS
        inst.is_call = mnemonic == "call"
        inst.is_return = mnemonic == "ret"

        # 跳转目标
        if operands and operands[0].type == OperandType.IMMEDIATE:
            if inst.is_jump:
                inst.jump_target = operands[0].value

        return inst

    @staticmethod
    def _parse_operand(op_str: str) -> Optional[Operand]:
        """解析操作数字符串"""
        op_str = op_str.strip()

        # 内存引用
        if op_str.startswith("[") and op_str.endswith("]"):
            inner = op_str[1:-1]
            return Operand(type=OperandType.MEMORY, value=inner)

        # 立即数
        if op_str.startswith("0x") or op_str.startswith("0X"):
            try:
                val = int(op_str, 16)
                return Operand(type=OperandType.IMMEDIATE, value=val)
            except ValueError:
                pass

        try:
            val = int(op_str)
            return Operand(type=OperandType.IMMEDIATE, value=val)
        except ValueError:
            pass

        # 寄存器
        if op_str.lower() in ALL_REGISTERS:
            return Operand(type=OperandType.REGISTER, value=op_str.lower())

        # 标签
        if op_str.startswith("loc_") or op_str.startswith("sub_"):
            try:
                val = int(op_str.split("_")[1], 16)
                return Operand(type=OperandType.LABEL, value=val)
            except (ValueError, IndexError):
                pass

        # 其他
        return Operand(type=OperandType.IMMEDIATE, value=op_str)

    @staticmethod
    def parse_asm_text(text: str) -> List[Instruction]:
        """解析多行汇编文本"""
        instructions = []
        for line in text.split("\n"):
            inst = InstructionDecoder.parse_asm_line(line)
            if inst:
                instructions.append(inst)
        return instructions


# ============================================================
# 控制流图构建器
# ============================================================

class CFGBuilder:
    """控制流图构建器"""

    def __init__(self):
        self.blocks: List[BasicBlock] = []
        self.block_map: Dict[int, int] = {}  # address -> block_id
        self._next_id = 0

    def build(self, instructions: List[Instruction]) -> List[BasicBlock]:
        """从指令列表构建 CFG"""
        if not instructions:
            return []

        self.blocks = []
        self.block_map = {}
        self._next_id = 0

        # 1. 识别基本块边界（leader 指令）
        leaders = self._find_leaders(instructions)

        # 2. 构建基本块
        for i, leader_idx in enumerate(sorted(leaders)):
            start = leader_idx
            end = len(instructions)
            for j in range(i + 1, len(sorted(leaders))):
                if sorted(leaders)[j] > start:
                    end = sorted(leaders)[j]
                    break

            block_instructions = instructions[start:end]
            if block_instructions:
                block = self._create_block(block_instructions)
                self.blocks.append(block)

        # 3. 建立边
        self._build_edges(instructions)

        return self.blocks

    def _find_leaders(self, instructions: List[Instruction]) -> Set[int]:
        """识别基本块 leader"""
        leaders = {0}  # 第一条指令是 leader

        for i, inst in enumerate(instructions):
            # 跳转目标
            if inst.jump_target is not None:
                for j, target_inst in enumerate(instructions):
                    if target_inst.address == inst.jump_target:
                        leaders.add(j)
                        break

            # 条件跳转的下一条指令
            if inst.is_conditional:
                if i + 1 < len(instructions):
                    leaders.add(i + 1)

            # 无条件跳转/call/ret 的下一条
            if inst.is_jump and not inst.is_conditional:
                if i + 1 < len(instructions):
                    leaders.add(i + 1)

        return leaders

    def _create_block(self, instructions: List[Instruction]) -> BasicBlock:
        """创建基本块"""
        block = BasicBlock(
            id=self._next_id,
            start_address=instructions[0].address,
            end_address=instructions[-1].address + instructions[-1].size,
            instructions=instructions,
        )
        self._next_id += 1
        self.block_map[block.start_address] = block.id
        return block

    def _build_edges(self, instructions: List[Instruction]):
        """构建 CFG 边"""
        for i, block in enumerate(self.blocks):
            last_inst = block.instructions[-1]

            if last_inst.is_return:
                continue

            if last_inst.is_conditional:
                # 真实分支
                if last_inst.jump_target is not None:
                    target_id = self.block_map.get(last_inst.jump_target)
                    if target_id is not None:
                        block.successors.append(target_id)

                # 假分支（fallthrough）
                if i + 1 < len(self.blocks):
                    block.successors.append(self.blocks[i + 1].id)

            elif last_inst.is_jump and not last_inst.is_call:
                # 无条件跳转
                if last_inst.jump_target is not None:
                    target_id = self.block_map.get(last_inst.jump_target)
                    if target_id is not None:
                        block.successors.append(target_id)

            elif last_inst.is_call:
                # call 指令：后继是下一条指令
                if i + 1 < len(self.blocks):
                    block.successors.append(self.blocks[i + 1].id)

            else:
                # 普通指令，后继是下一个块
                if i + 1 < len(self.blocks):
                    block.successors.append(self.blocks[i + 1].id)

        # 建立前驱关系
        for block in self.blocks:
            for succ_id in block.successors:
                if succ_id < len(self.blocks):
                    self.blocks[succ_id].predecessors.append(block.id)

    def compute_dominators(self) -> Dict[int, Set[int]]:
        """计算支配者关系"""
        if not self.blocks:
            return {}

        n = len(self.blocks)
        all_nodes = set(range(n))

        # 初始化：入口块支配自身，其他块被所有块支配
        dom = {i: all_nodes.copy() for i in range(n)}
        dom[0] = {0}

        changed = True
        while changed:
            changed = False
            for i in range(1, n):
                preds = self.blocks[i].predecessors
                if not preds:
                    continue

                new_dom = all_nodes.copy()
                for pred in preds:
                    new_dom &= dom[pred]
                new_dom.add(i)

                if new_dom != dom[i]:
                    dom[i] = new_dom
                    changed = True

        return dom

    def compute_dominance_frontiers(self) -> Dict[int, Set[int]]:
        """计算支配边界"""
        dom = self.compute_dominators()
        df = {i: set() for i in range(len(self.blocks))}

        for b in range(len(self.blocks)):
            preds = self.blocks[b].predecessors
            if len(preds) >= 2:  # 汇合点
                for pred in preds:
                    runner = pred
                    while runner not in dom[b]:
                        df[runner].add(b)
                        # 找到 runner 的直接支配者
                        for d, dom_set in dom.items():
                            if runner in dom_set and d != runner:
                                strict_dom = dom_set - {d}
                                # 简化：找到支配 runner 的节点
                                break
                        break

        return df

    def detect_loops(self) -> List[Tuple[int, int]]:
        """检测循环（返回 (header_id, latch_id) 列表）"""
        loops = []
        for block in self.blocks:
            for succ_id in block.successors:
                # 如果后继支配当前块，则存在循环
                dom = self.compute_dominators()
                if succ_id in dom.get(block.id, set()):
                    loops.append((succ_id, block.id))
                    self.blocks[succ_id].is_loop_header = True
        return loops


# ============================================================
# SSA 构造器
# ============================================================

class SSABuilder:
    """SSA (Static Single Assignment) 形式构造器"""

    def __init__(self):
        self.variables: Dict[str, List[SSAVariable]] = defaultdict(list)
        self.var_versions: Dict[str, int] = defaultdict(int)
        self.phi_nodes: Dict[int, Dict[str, List[Tuple[int, int]]]] = defaultdict(
            lambda: defaultdict(list))  # block_id -> {var: [(src_block, version)]}

    def build(self, blocks: List[BasicBlock], dom: Dict[int, Set[int]],
              df: Dict[int, Set[int]]) -> Dict[int, Dict[str, SSAVariable]]:
        """
        构建 SSA 形式
        
        返回: {block_id: {original_reg: SSAVariable}}
        """
        self.variables.clear()
        self.var_versions.clear()
        self.phi_nodes.clear()

        # 收集所有被赋值的变量
        all_defs = defaultdict(list)  # var -> [block_ids]
        for block in blocks:
            for inst in block.instructions:
                defs = self._get_defined_vars(inst)
                for var in defs:
                    all_defs[var].append(block.id)

        # 插入 phi 节点
        for var, def_blocks in all_defs.items():
            # 使用迭代支配边界
            worklist = list(def_blocks)
            processed = set(def_blocks)
            while worklist:
                b = worklist.pop(0)
                for df_block in df.get(b, set()):
                    if df_block not in processed:
                        # 在 df_block 中插入 phi 节点
                        self.phi_nodes[df_block][var] = []
                        processed.add(df_block)
                        worklist.append(df_block)

        # 重命名变量
        block_var_map = {}  # {block_id: {original_var: SSAVariable}}
        var_stack = defaultdict(list)  # var -> stack of versions
        var_counters = defaultdict(int)  # var -> current version

        def rename_block(block_id: int):
            current_defs = {}  # 当前块中定义的变量

            # 处理 phi 节点
            if block_id in self.phi_nodes:
                for var in self.phi_nodes[block_id]:
                    version = var_counters[var]
                    var_counters[var] += 1
                    ssa_var = SSAVariable(
                        name=var,
                        version=version,
                        original_reg=var,
                    )
                    current_defs[var] = ssa_var
                    var_stack[var].append(ssa_var)

            # 记录当前块映射
            block_var_map[block_id] = {}

            # 处理指令
            for inst in blocks[block_id].instructions:
                defs = self._get_defined_vars(inst)
                for var in defs:
                    version = var_counters[var]
                    var_counters[var] += 1
                    ssa_var = SSAVariable(
                        name=var,
                        version=version,
                        original_reg=var,
                        defined_at=inst.address,
                    )
                    current_defs[var] = ssa_var
                    var_stack[var].append(ssa_var)

            # 更新块映射
            for var, ssa_var in current_defs.items():
                block_var_map[block_id][var] = ssa_var

            # 重命名后继中的 phi 使用
            for succ_id in blocks[block_id].successors:
                if succ_id in self.phi_nodes:
                    for var in self.phi_nodes[succ_id]:
                        if var_stack[var]:
                            self.phi_nodes[succ_id][var].append(
                                (block_id, var_stack[var][-1].version)
                            )

            # 递归处理支配树子节点
            for child_id in range(len(blocks)):
                if child_id != block_id and block_id in dom.get(child_id, set()):
                    # 简单判断：child_id 的直接支配者是否是 block_id
                    is_direct_child = True
                    for intermediate in range(len(blocks)):
                        if (intermediate != block_id and intermediate != child_id and
                                block_id in dom.get(intermediate, set()) and
                                intermediate in dom.get(child_id, set())):
                            is_direct_child = False
                            break
                    if is_direct_child:
                        rename_block(child_id)

            # 弹出变量栈
            for var in current_defs:
                if var_stack[var]:
                    var_stack[var].pop()

        # 从入口块开始
        rename_block(0)

        return block_var_map

    def _get_defined_vars(self, inst: Instruction) -> List[str]:
        """获取指令定义的变量"""
        defs = []
        if inst.op_type in (InstructionType.MOV, InstructionType.LEA, InstructionType.XCHG):
            if inst.operands and inst.operands[0].type == OperandType.REGISTER:
                defs.append(inst.operands[0].value)
        elif inst.op_type in (InstructionType.ADD, InstructionType.SUB, InstructionType.IMUL,
                               InstructionType.AND, InstructionType.OR, InstructionType.XOR,
                               InstructionType.SHL, InstructionType.SHR, InstructionType.SAR,
                               InstructionType.INC, InstructionType.DEC, InstructionType.NEG,
                               InstructionType.NOT):
            if inst.operands and inst.operands[0].type == OperandType.REGISTER:
                defs.append(inst.operands[0].value)
        elif inst.op_type == InstructionType.POP:
            if inst.operands and inst.operands[0].type == OperandType.REGISTER:
                defs.append(inst.operands[0].value)
        return defs


# ============================================================
# 符号执行引擎
# ============================================================

class SymbolicExecutor:
    """
    符号执行引擎
    
    沿路径执行符号表达式，收集约束条件，探索可达路径。
    """

    def __init__(self, max_depth: int = 100, max_paths: int = 50):
        self.max_depth = max_depth
        self.max_paths = max_paths
        self.paths: List[PathState] = []
        self._next_path_id = 0

    def execute(self, blocks: List[BasicBlock], start_block: int = 0) -> List[PathState]:
        """从入口块开始符号执行"""
        self.paths = []
        self._next_path_id = 0

        if not blocks:
            return self.paths

        # 初始状态
        initial_state = PathState(
            path_id=self._next_path_id,
            address=blocks[start_block].start_address,
        )
        self._next_path_id += 1

        worklist = [(initial_state, start_block)]
        visited = set()

        while worklist and len(self.paths) < self.max_paths:
            state, block_id = worklist.pop(0)

            if state.depth > self.max_depth:
                self.paths.append(state)
                continue

            state_key = (block_id, self._hash_state(state))
            if state_key in visited:
                continue
            visited.add(state_key)

            block = blocks[block_id]

            # 符号执行块内指令
            new_state = self._execute_block(state, block)

            # 处理后继
            if not block.successors:
                self.paths.append(new_state)
            elif len(block.successors) == 1:
                worklist.append((new_state, block.successors[0]))
            else:
                # 分支：创建两个状态
                last_inst = block.instructions[-1]
                condition = self._get_condition(last_inst)

                # True 分支
                true_state = new_state.clone()
                true_state.path_id = self._next_path_id
                self._next_path_id += 1
                true_state.constraints.append(Constraint(condition, is_true=True))
                true_state.parent_id = state.path_id
                if last_inst.jump_target is not None:
                    target_id = self._find_block_by_address(blocks, last_inst.jump_target)
                    if target_id is not None:
                        worklist.append((true_state, target_id))

                # False 分支
                false_state = new_state.clone()
                false_state.path_id = self._next_path_id
                self._next_path_id += 1
                false_state.constraints.append(Constraint(condition, is_true=False))
                false_state.parent_id = state.path_id
                fallthrough = block.successors[1] if len(block.successors) > 1 else None
                if fallthrough is not None:
                    worklist.append((false_state, fallthrough))

        return self.paths

    def _execute_block(self, state: PathState, block: BasicBlock) -> PathState:
        """符号执行一个基本块"""
        new_state = state.clone()
        new_state.depth += 1

        for inst in block.instructions:
            new_state = self._execute_instruction(new_state, inst)

        return new_state

    def _execute_instruction(self, state: PathState, inst: Instruction) -> PathState:
        """符号执行单条指令"""
        new_state = state.clone()

        if inst.op_type == InstructionType.MOV:
            if len(inst.operands) >= 2:
                dst = inst.operands[0]
                src = inst.operands[1]
                if dst.type == OperandType.REGISTER:
                    new_state.registers[dst.value] = self._eval_operand(state, src)

        elif inst.op_type == InstructionType.ADD:
            if len(inst.operands) >= 2 and inst.operands[0].type == OperandType.REGISTER:
                dst = inst.operands[0].value
                a = self._eval_operand(state, inst.operands[0])
                b = self._eval_operand(state, inst.operands[1])
                new_state.registers[dst] = SymbolicExpr(SymbolicOp.ADD, [a, b])

        elif inst.op_type == InstructionType.SUB:
            if len(inst.operands) >= 2 and inst.operands[0].type == OperandType.REGISTER:
                dst = inst.operands[0].value
                a = self._eval_operand(state, inst.operands[0])
                b = self._eval_operand(state, inst.operands[1])
                new_state.registers[dst] = SymbolicExpr(SymbolicOp.SUB, [a, b])

        elif inst.op_type == InstructionType.IMUL:
            if len(inst.operands) >= 2 and inst.operands[0].type == OperandType.REGISTER:
                dst = inst.operands[0].value
                a = self._eval_operand(state, inst.operands[0])
                b = self._eval_operand(state, inst.operands[1])
                new_state.registers[dst] = SymbolicExpr(SymbolicOp.MUL, [a, b])

        elif inst.op_type == InstructionType.AND:
            if len(inst.operands) >= 2 and inst.operands[0].type == OperandType.REGISTER:
                dst = inst.operands[0].value
                a = self._eval_operand(state, inst.operands[0])
                b = self._eval_operand(state, inst.operands[1])
                new_state.registers[dst] = SymbolicExpr(SymbolicOp.AND, [a, b])

        elif inst.op_type == InstructionType.OR:
            if len(inst.operands) >= 2 and inst.operands[0].type == OperandType.REGISTER:
                dst = inst.operands[0].value
                a = self._eval_operand(state, inst.operands[0])
                b = self._eval_operand(state, inst.operands[1])
                new_state.registers[dst] = SymbolicExpr(SymbolicOp.OR, [a, b])

        elif inst.op_type == InstructionType.XOR:
            if len(inst.operands) >= 2 and inst.operands[0].type == OperandType.REGISTER:
                dst = inst.operands[0].value
                a = self._eval_operand(state, inst.operands[0])
                b = self._eval_operand(state, inst.operands[1])
                new_state.registers[dst] = SymbolicExpr(SymbolicOp.XOR, [a, b])

        elif inst.op_type == InstructionType.SHL:
            if len(inst.operands) >= 2 and inst.operands[0].type == OperandType.REGISTER:
                dst = inst.operands[0].value
                a = self._eval_operand(state, inst.operands[0])
                b = self._eval_operand(state, inst.operands[1])
                new_state.registers[dst] = SymbolicExpr(SymbolicOp.SHL, [a, b])

        elif inst.op_type == InstructionType.SHR:
            if len(inst.operands) >= 2 and inst.operands[0].type == OperandType.REGISTER:
                dst = inst.operands[0].value
                a = self._eval_operand(state, inst.operands[0])
                b = self._eval_operand(state, inst.operands[1])
                new_state.registers[dst] = SymbolicExpr(SymbolicOp.SHR, [a, b])

        elif inst.op_type == InstructionType.INC:
            if inst.operands and inst.operands[0].type == OperandType.REGISTER:
                reg = inst.operands[0].value
                val = self._eval_operand(state, inst.operands[0])
                new_state.registers[reg] = SymbolicExpr(
                    SymbolicOp.ADD, [val, SymbolicExpr(SymbolicOp.CONST, [1])]
                )

        elif inst.op_type == InstructionType.DEC:
            if inst.operands and inst.operands[0].type == OperandType.REGISTER:
                reg = inst.operands[0].value
                val = self._eval_operand(state, inst.operands[0])
                new_state.registers[reg] = SymbolicExpr(
                    SymbolicOp.SUB, [val, SymbolicExpr(SymbolicOp.CONST, [1])]
                )

        elif inst.op_type == InstructionType.LEA:
            if len(inst.operands) >= 2 and inst.operands[0].type == OperandType.REGISTER:
                new_state.registers[inst.operands[0].value] = self._eval_operand(
                    state, inst.operands[1])

        elif inst.op_type == InstructionType.PUSH:
            if inst.operands:
                val = self._eval_operand(state, inst.operands[0])
                # 简化：将 push 视为对 esp 的 sub 操作
                esp_val = new_state.registers.get("esp", SymbolicExpr(SymbolicOp.CONST, [0]))
                new_state.registers["esp"] = SymbolicExpr(
                    SymbolicOp.SUB, [esp_val, SymbolicExpr(SymbolicOp.CONST, [4])]
                )

        elif inst.op_type == InstructionType.POP:
            if inst.operands and inst.operands[0].type == OperandType.REGISTER:
                new_state.registers[inst.operands[0].value] = SymbolicExpr(
                    SymbolicOp.VAR, [f"mem_{state.address}"]
                )

        elif inst.op_type == InstructionType.CMP:
            # CMP 不修改寄存器，只设置标志位
            pass

        elif inst.op_type == InstructionType.XOR:
            # 特殊处理：xor eax, eax -> eax = 0
            if (len(inst.operands) >= 2 and
                    inst.operands[0].type == OperandType.REGISTER and
                    inst.operands[1].type == OperandType.REGISTER and
                    inst.operands[0].value == inst.operands[1].value):
                new_state.registers[inst.operands[0].value] = SymbolicExpr(
                    SymbolicOp.CONST, [0])

        new_state.address = inst.address
        return new_state

    def _eval_operand(self, state: PathState, op: Operand) -> SymbolicExpr:
        """求值操作数为符号表达式"""
        if op.type == OperandType.REGISTER:
            return state.registers.get(op.value, SymbolicExpr(
                SymbolicOp.VAR, [op.value]))
        elif op.type == OperandType.IMMEDIATE:
            return SymbolicExpr(SymbolicOp.CONST, [op.value])
        elif op.type == OperandType.MEMORY:
            return SymbolicExpr(SymbolicOp.VAR, [f"mem_{op.value}"])
        return SymbolicExpr(SymbolicOp.CONST, [0])

    def _get_condition(self, inst: Instruction) -> SymbolicExpr:
        """从条件跳转指令获取条件表达式"""
        if inst.mnemonic in CONDITIONAL_JUMPS:
            op = CONDITIONAL_JUMPS[inst.mnemonic]
            return SymbolicExpr(SymbolicOp.VAR, [f"flag_{inst.mnemonic}"])
        return SymbolicExpr(SymbolicOp.CONST, [1])

    def _find_block_by_address(self, blocks: List[BasicBlock], address: int) -> Optional[int]:
        for block in blocks:
            if block.start_address <= address < block.end_address:
                return block.id
        # 精确匹配
        for block in blocks:
            if block.start_address == address:
                return block.id
        return None

    def _hash_state(self, state: PathState) -> int:
        """状态哈希"""
        return hash((state.address, tuple(sorted(state.registers.keys()))))


# ============================================================
# 约束求解器
# ============================================================

class ConstraintSolver:
    """
    轻量级约束求解器
    
    支持基本表达式的化简与求解：
    - 常量折叠
    - 代数恒等式
    - 简单等式求解
    """

    @staticmethod
    def simplify(expr: SymbolicExpr) -> SymbolicExpr:
        """化简符号表达式"""
        if expr is None:
            return SymbolicExpr(SymbolicOp.CONST, [0])

        # 递归化简参数
        args = [ConstraintSolver.simplify(a) if isinstance(a, SymbolicExpr) else a
                for a in expr.args]

        op = expr.op

        # 常量折叠
        if all(isinstance(a, SymbolicExpr) and a.op == SymbolicOp.CONST for a in args):
            consts = [a.args[0] for a in args]
            result = ConstraintSolver._evaluate_const(op, consts)
            if result is not None:
                return SymbolicExpr(SymbolicOp.CONST, [result])

        # 代数化简
        if op == SymbolicOp.ADD:
            # x + 0 = x
            if len(args) == 2:
                if args[0].op == SymbolicOp.CONST and args[0].args[0] == 0:
                    return args[1]
                if args[1].op == SymbolicOp.CONST and args[1].args[0] == 0:
                    return args[0]

        elif op == SymbolicOp.SUB:
            # x - 0 = x
            if len(args) == 2:
                if args[1].op == SymbolicOp.CONST and args[1].args[0] == 0:
                    return args[0]
                # x - x = 0
                if args[0] == args[1]:
                    return SymbolicExpr(SymbolicOp.CONST, [0])

        elif op == SymbolicOp.MUL:
            # x * 0 = 0
            if len(args) == 2:
                if (args[0].op == SymbolicOp.CONST and args[0].args[0] == 0) or \
                        (args[1].op == SymbolicOp.CONST and args[1].args[0] == 0):
                    return SymbolicExpr(SymbolicOp.CONST, [0])
                # x * 1 = x
                if args[0].op == SymbolicOp.CONST and args[0].args[0] == 1:
                    return args[1]
                if args[1].op == SymbolicOp.CONST and args[1].args[0] == 1:
                    return args[0]

        elif op == SymbolicOp.AND:
            if len(args) == 2:
                # x & 0 = 0
                if (args[0].op == SymbolicOp.CONST and args[0].args[0] == 0) or \
                        (args[1].op == SymbolicOp.CONST and args[1].args[0] == 0):
                    return SymbolicExpr(SymbolicOp.CONST, [0])
                # x & x = x
                if args[0] == args[1]:
                    return args[0]

        elif op == SymbolicOp.OR:
            if len(args) == 2:
                # x | 0 = x
                if args[0].op == SymbolicOp.CONST and args[0].args[0] == 0:
                    return args[1]
                if args[1].op == SymbolicOp.CONST and args[1].args[0] == 0:
                    return args[0]

        elif op == SymbolicOp.XOR:
            if len(args) == 2:
                # x ^ 0 = x
                if args[0].op == SymbolicOp.CONST and args[0].args[0] == 0:
                    return args[1]
                if args[1].op == SymbolicOp.CONST and args[1].args[0] == 0:
                    return args[0]
                # x ^ x = 0
                if args[0] == args[1]:
                    return SymbolicExpr(SymbolicOp.CONST, [0])

        return SymbolicExpr(op=op, args=args, size=expr.size)

    @staticmethod
    def _evaluate_const(op: SymbolicOp, args: List[int]) -> Optional[int]:
        """计算常量表达式"""
        try:
            if op == SymbolicOp.ADD:
                return sum(args[:2])
            elif op == SymbolicOp.SUB:
                return args[0] - args[1]
            elif op == SymbolicOp.MUL:
                return args[0] * args[1]
            elif op == SymbolicOp.DIV:
                return args[0] // args[1] if args[1] != 0 else None
            elif op == SymbolicOp.MOD:
                return args[0] % args[1] if args[1] != 0 else None
            elif op == SymbolicOp.AND:
                return args[0] & args[1]
            elif op == SymbolicOp.OR:
                return args[0] | args[1]
            elif op == SymbolicOp.XOR:
                return args[0] ^ args[1]
            elif op == SymbolicOp.SHL:
                return (args[0] << args[1]) & 0xFFFFFFFF
            elif op == SymbolicOp.SHR:
                return args[0] >> args[1]
            elif op == SymbolicOp.NEG:
                return -args[0]
            elif op == SymbolicOp.NOT:
                return ~args[0] & 0xFFFFFFFF
            elif op == SymbolicOp.EQ:
                return 1 if args[0] == args[1] else 0
            elif op == SymbolicOp.NE:
                return 1 if args[0] != args[1] else 0
            elif op == SymbolicOp.LT:
                return 1 if args[0] < args[1] else 0
            elif op == SymbolicOp.LE:
                return 1 if args[0] <= args[1] else 0
            elif op == SymbolicOp.GT:
                return 1 if args[0] > args[1] else 0
            elif op == SymbolicOp.GE:
                return 1 if args[0] >= args[1] else 0
            elif op == SymbolicOp.CONST:
                return args[0]
        except (IndexError, ZeroDivisionError, TypeError):
            return None
        return None

    @staticmethod
    def check_sat(constraints: List[Constraint]) -> Tuple[bool, Dict[str, int]]:
        """检查约束可满足性（简化版）"""
        # 对于简单约束，尝试整数求解
        model = {}
        for constraint in constraints:
            expr = ConstraintSolver.simplify(constraint.expr)
            if expr.op == SymbolicOp.CONST:
                val = expr.args[0]
                if constraint.is_true and val == 0:
                    return False, {}
                if not constraint.is_true and val != 0:
                    return False, {}
        return True, model

    @staticmethod
    def solve_equal(expr: SymbolicExpr, target: int) -> Optional[Dict[str, int]]:
        """求解 expr == target（简单情况）"""
        simplified = ConstraintSolver.simplify(expr)

        if simplified.op == SymbolicOp.CONST:
            if simplified.args[0] == target:
                return {}
            return None

        if simplified.op == SymbolicOp.VAR:
            return {str(simplified.args[0]): target}

        if simplified.op == SymbolicOp.ADD:
            if len(simplified.args) == 2:
                left = simplified.args[0]
                right = simplified.args[1]
                # x + const = target => x = target - const
                if right.op == SymbolicOp.CONST:
                    return ConstraintSolver.solve_equal(
                        left, target - right.args[0])
                if left.op == SymbolicOp.CONST:
                    return ConstraintSolver.solve_equal(
                        right, target - left.args[0])

        if simplified.op == SymbolicOp.SUB:
            if len(simplified.args) == 2:
                # x - const = target => x = target + const
                if simplified.args[1].op == SymbolicOp.CONST:
                    return ConstraintSolver.solve_equal(
                        simplified.args[0], target + simplified.args[1].args[0])

        if simplified.op == SymbolicOp.XOR:
            if len(simplified.args) == 2:
                # x ^ const = target => x = target ^ const
                if simplified.args[1].op == SymbolicOp.CONST:
                    return ConstraintSolver.solve_equal(
                        simplified.args[0], target ^ simplified.args[1].args[0])

        return None


# ============================================================
# 控制流结构恢复器
# ============================================================

class StructureRecovery:
    """控制流结构恢复器 — 将 CFG 转换为高级控制结构"""

    @staticmethod
    def recover(blocks: List[BasicBlock]) -> List[ControlStructure]:
        """从 CFG 恢复结构化控制流"""
        if not blocks:
            return []

        structures = []
        # 使用结构分析算法
        # 简化实现：识别 if-else, while, do-while 模式

        processed = set()
        for block in blocks:
            if block.id in processed:
                continue

            if len(block.successors) == 2:
                # 可能是 if-else 或 while 循环
                structure = StructureRecovery._analyze_branch(blocks, block)
                if structure:
                    structures.append(structure)
                    processed.add(block.id)
                    # 标记处理过的块
                    for b in blocks:
                        if b.start_address >= block.start_address and \
                                b.start_address < structure.follow_address:
                            processed.add(b.id)
            elif len(block.successors) == 1:
                processed.add(block.id)
            else:
                processed.add(block.id)

        return structures

    @staticmethod
    def _analyze_branch(blocks: List[BasicBlock], block: BasicBlock) -> Optional[ControlStructure]:
        """分析分支结构"""
        if len(block.successors) != 2:
            return None

        succ_a = block.successors[0]
        succ_b = block.successors[1]

        # 检查是否是循环（后向边）
        if succ_a == block.id or succ_b == block.id:
            # while 循环
            return ControlStructure(
                type=StructureType.WHILE_LOOP,
                header_address=block.start_address,
                body=[],
                condition="condition",
                follow_address=block.end_address,
            )

        # 检查 if-else 模式
        # 两个分支都汇合到同一个点
        merge_block = StructureRecovery._find_merge(blocks, succ_a, succ_b)
        if merge_block is not None:
            return ControlStructure(
                type=StructureType.IF_THEN_ELSE,
                header_address=block.start_address,
                body=[],
                else_body=[],
                condition="condition",
                follow_address=blocks[merge_block].start_address if merge_block < len(blocks) else 0,
            )

        return ControlStructure(
            type=StructureType.IF_THEN,
            header_address=block.start_address,
            body=[],
            condition="condition",
            follow_address=block.end_address,
        )

    @staticmethod
    def _find_merge(blocks: List[BasicBlock], a: int, b: int) -> Optional[int]:
        """查找两个分支的汇合点"""
        visited_a = set()
        queue = deque([a])
        while queue:
            node = queue.popleft()
            if node in visited_a:
                continue
            visited_a.add(node)
            if node < len(blocks):
                for succ in blocks[node].successors:
                    queue.append(succ)

        queue = deque([b])
        visited_b = set()
        while queue:
            node = queue.popleft()
            if node in visited_b:
                continue
            visited_b.add(node)
            if node in visited_a:
                return node
            if node < len(blocks):
                for succ in blocks[node].successors:
                    queue.append(succ)

        return None


# ============================================================
# 伪代码生成器
# ============================================================

class PseudoCodeGenerator:
    """伪代码生成器 — 将指令序列转换为类 C 伪代码"""

    def __init__(self):
        self._indent = 0
        self._var_map: Dict[str, str] = {}
        self._var_counter = 0

    def generate(self, instructions: List[Instruction],
                 structures: List[ControlStructure] = None) -> str:
        """生成伪代码"""
        lines = []
        self._indent = 0
        self._var_map = {}
        self._var_counter = 0

        for inst in instructions:
            code = self._translate_instruction(inst)
            if code:
                lines.append("    " * self._indent + code)

        return "\n".join(lines)

    def _translate_instruction(self, inst: Instruction) -> str:
        """翻译单条指令为伪代码"""
        if inst.op_type == InstructionType.MOV:
            return self._translate_mov(inst)
        elif inst.op_type == InstructionType.ADD:
            return self._translate_arith(inst, "+")
        elif inst.op_type == InstructionType.SUB:
            return self._translate_arith(inst, "-")
        elif inst.op_type == InstructionType.IMUL:
            return self._translate_arith(inst, "*")
        elif inst.op_type == InstructionType.AND:
            return self._translate_arith(inst, "&")
        elif inst.op_type == InstructionType.OR:
            return self._translate_arith(inst, "|")
        elif inst.op_type == InstructionType.XOR:
            if (len(inst.operands) >= 2 and
                    inst.operands[0].type == OperandType.REGISTER and
                    inst.operands[1].type == OperandType.REGISTER and
                    inst.operands[0].value == inst.operands[1].value):
                dst = self._operand_str(inst.operands[0])
                return f"{dst} = 0;"
            return self._translate_arith(inst, "^")
        elif inst.op_type == InstructionType.SHL:
            return self._translate_arith(inst, "<<")
        elif inst.op_type == InstructionType.SHR:
            return self._translate_arith(inst, ">>")
        elif inst.op_type == InstructionType.INC:
            return self._translate_unary(inst, "++")
        elif inst.op_type == InstructionType.DEC:
            return self._translate_unary(inst, "--")
        elif inst.op_type == InstructionType.CMP:
            return self._translate_cmp(inst)
        elif inst.op_type == InstructionType.LEA:
            return self._translate_lea(inst)
        elif inst.op_type == InstructionType.PUSH:
            return f"push({self._operand_str(inst.operands[0])})" if inst.operands else "push"
        elif inst.op_type == InstructionType.POP:
            return f"pop({self._operand_str(inst.operands[0])})" if inst.operands else "pop"
        elif inst.op_type == InstructionType.CALL:
            return self._translate_call(inst)
        elif inst.op_type == InstructionType.RET:
            return "return;"
        elif inst.op_type == InstructionType.NOP:
            return "// nop"
        elif inst.op_type == InstructionType.LEAVE:
            return "// leave"
        elif inst.op_type == InstructionType.XCHG:
            return self._translate_xchg(inst)
        # 跳转
        elif inst.op_type in (InstructionType.JMP, InstructionType.JE, InstructionType.JNE,
                               InstructionType.JZ, InstructionType.JNZ, InstructionType.JG,
                               InstructionType.JGE, InstructionType.JL, InstructionType.JLE,
                               InstructionType.JA, InstructionType.JAE, InstructionType.JB,
                               InstructionType.JBE):
            return self._translate_jump(inst)

        return f"// {inst.mnemonic} " + ", ".join(str(o) for o in inst.operands)

    def _translate_mov(self, inst: Instruction) -> str:
        if len(inst.operands) < 2:
            return str(inst)
        dst = self._operand_str(inst.operands[0])
        src = self._operand_str(inst.operands[1])
        # 特殊：xor reg, reg -> reg = 0
        if inst.mnemonic == "xor" and dst == src:
            return f"{dst} = 0;"
        return f"{dst} = {src};"

    def _translate_arith(self, inst: Instruction, op: str) -> str:
        if len(inst.operands) < 2:
            return str(inst)
        dst = self._operand_str(inst.operands[0])
        src = self._operand_str(inst.operands[1])
        return f"{dst} = {dst} {op} {src};"

    def _translate_unary(self, inst: Instruction, op: str) -> str:
        if not inst.operands:
            return str(inst)
        dst = self._operand_str(inst.operands[0])
        if op == "++":
            return f"{dst} = {dst} + 1;"
        elif op == "--":
            return f"{dst} = {dst} - 1;"
        return f"{dst}{op};"

    def _translate_cmp(self, inst: Instruction) -> str:
        if len(inst.operands) < 2:
            return str(inst)
        a = self._operand_str(inst.operands[0])
        b = self._operand_str(inst.operands[1])
        return f"// cmp {a}, {b}"

    def _translate_lea(self, inst: Instruction) -> str:
        if len(inst.operands) < 2:
            return str(inst)
        dst = self._operand_str(inst.operands[0])
        src = self._operand_str(inst.operands[1])
        return f"{dst} = &{src};"

    def _translate_call(self, inst: Instruction) -> str:
        if inst.operands:
            target = self._operand_str(inst.operands[0])
            return f"call {target}();"
        return "call ???();"

    def _translate_jump(self, inst: Instruction) -> str:
        if inst.mnemonic == "jmp":
            if inst.jump_target:
                return f"goto loc_{inst.jump_target:X};"
            return "goto ???;"
        elif inst.mnemonic in CONDITIONAL_JUMPS:
            op = CONDITIONAL_JUMPS[inst.mnemonic]
            if inst.jump_target:
                return f"if (flag {op} 0) goto loc_{inst.jump_target:X};"
            return f"if (flag {op} 0) goto ???;"
        return f"// {inst.mnemonic}"

    def _translate_xchg(self, inst: Instruction) -> str:
        if len(inst.operands) < 2:
            return str(inst)
        a = self._operand_str(inst.operands[0])
        b = self._operand_str(inst.operands[1])
        return f"swap({a}, {b});"

    def _operand_str(self, op: Operand) -> str:
        """将操作数转换为伪代码字符串"""
        if op.type == OperandType.REGISTER:
            return self._map_register(op.value)
        elif op.type == OperandType.IMMEDIATE:
            if isinstance(op.value, int):
                if op.value < 0:
                    return f"-0x{-op.value:X}"
                return f"0x{op.value:X}"
            return str(op.value)
        elif op.type == OperandType.MEMORY:
            return f"*({str(op.value)})"
        elif op.type == OperandType.LABEL:
            return str(op.value)
        return str(op.value)

    def _map_register(self, reg: str) -> str:
        """将寄存器名映射为伪代码变量名"""
        # 特殊寄存器映射
        special = {
            "eax": "eax", "ebx": "ebx", "ecx": "ecx", "edx": "edx",
            "esi": "esi", "edi": "edi", "ebp": "ebp", "esp": "esp",
            "rax": "rax", "rbx": "rbx", "rcx": "rcx", "rdx": "rdx",
            "rsi": "rsi", "rdi": "rdi", "rbp": "rbp", "rsp": "rsp",
        }
        return special.get(reg, reg)


# ============================================================
# 反编译引擎主入口
# ============================================================

class DecompilerEngine:
    """
    反编译与符号执行引擎（主入口）
    
    整合反编译、SSA、符号执行、约束求解、结构恢复五大子系统。
    """

    def __init__(self):
        self.decoder = InstructionDecoder()
        self.cfg_builder = CFGBuilder()
        self.ssa_builder = SSABuilder()
        self.executor = SymbolicExecutor()
        self.solver = ConstraintSolver()
        self.codegen = PseudoCodeGenerator()
        self.structure_recovery = StructureRecovery()

    def decompile(self, asm_text: str, function_name: str = "sub_0") -> Dict[str, Any]:
        """反编译汇编文本为伪代码"""
        instructions = self.decoder.parse_asm_text(asm_text)
        if not instructions:
            return {"success": False, "message": "无法解析汇编文本"}

        # 1. 构建 CFG
        blocks = self.cfg_builder.build(instructions)

        # 2. 计算支配关系
        dom = self.cfg_builder.compute_dominators()
        df = self.cfg_builder.compute_dominance_frontiers()

        # 3. 检测循环
        loops = self.cfg_builder.detect_loops()

        # 4. 构建 SSA
        ssa_map = self.ssa_builder.build(blocks, dom, df)

        # 5. 符号执行
        paths = self.executor.execute(blocks)

        # 6. 结构恢复
        structures = self.structure_recovery.recover(blocks)

        # 7. 生成伪代码
        pseudo_code = self.codegen.generate(instructions, structures)

        return {
            "success": True,
            "function": function_name,
            "instruction_count": len(instructions),
            "block_count": len(blocks),
            "loop_count": len(loops),
            "path_count": len(paths),
            "structure_count": len(structures),
            "pseudo_code": pseudo_code,
            "blocks": [
                {
                    "id": b.id,
                    "start_address": f"0x{b.start_address:X}",
                    "end_address": f"0x{b.end_address:X}",
                    "instruction_count": len(b.instructions),
                    "successors": b.successors,
                    "predecessors": b.predecessors,
                    "is_loop_header": b.is_loop_header,
                }
                for b in blocks
            ],
            "loops": [
                {"header": h, "latch": l} for h, l in loops
            ],
            "structures": [
                {
                    "type": s.type.value,
                    "header": f"0x{s.header_address:X}",
                    "follow": f"0x{s.follow_address:X}" if s.follow_address else "",
                    "condition": s.condition,
                }
                for s in structures
            ],
            "paths": [
                {
                    "id": p.path_id,
                    "depth": p.depth,
                    "constraint_count": len(p.constraints),
                }
                for p in paths[:10]
            ],
        }

    def decompile_file(self, asm_file_path: str, function_name: str = "") -> Dict[str, Any]:
        """从文件反编译"""
        if not os.path.exists(asm_file_path):
            return {"success": False, "message": f"文件不存在: {asm_file_path}"}

        try:
            with open(asm_file_path, "r", encoding="utf-8", errors="ignore") as f:
                asm_text = f.read()
        except Exception as e:
            return {"success": False, "message": str(e)}

        name = function_name or os.path.splitext(os.path.basename(asm_file_path))[0]
        return self.decompile(asm_text, name)

    def build_cfg(self, asm_text: str) -> Dict[str, Any]:
        """构建控制流图"""
        instructions = self.decoder.parse_asm_text(asm_text)
        if not instructions:
            return {"success": False, "message": "无法解析汇编文本"}

        blocks = self.cfg_builder.build(instructions)
        dom = self.cfg_builder.compute_dominators()
        loops = self.cfg_builder.detect_loops()

        return {
            "success": True,
            "instruction_count": len(instructions),
            "block_count": len(blocks),
            "blocks": [
                {
                    "id": b.id,
                    "start_address": f"0x{b.start_address:X}",
                    "end_address": f"0x{b.end_address:X}",
                    "instruction_count": len(b.instructions),
                    "successors": b.successors,
                    "predecessors": b.predecessors,
                    "is_loop_header": b.is_loop_header,
                    "instructions": [str(i) for i in b.instructions[:5]],
                }
                for b in blocks
            ],
            "dominance": {str(k): list(v) for k, v in dom.items()},
            "loops": [{"header": h, "latch": l} for h, l in loops],
        }

    def symbolic_execute(self, asm_text: str, max_depth: int = 50) -> Dict[str, Any]:
        """符号执行"""
        instructions = self.decoder.parse_asm_text(asm_text)
        if not instructions:
            return {"success": False, "message": "无法解析汇编文本"}

        blocks = self.cfg_builder.build(instructions)
        self.executor.max_depth = max_depth
        paths = self.executor.execute(blocks)

        return {
            "success": True,
            "path_count": len(paths),
            "max_depth": max_depth,
            "paths": [
                {
                    "id": p.path_id,
                    "depth": p.depth,
                    "constraint_count": len(p.constraints),
                    "constraints": [str(c) for c in p.constraints[:5]],
                    "registers": {k: str(v) for k, v in list(p.registers.items())[:5]},
                }
                for p in paths[:15]
            ],
        }

    def solve_constraints(self, constraints_data: List[Dict]) -> Dict[str, Any]:
        """求解约束"""
        constraints = []
        for c in constraints_data:
            expr = self._parse_expr_from_dict(c.get("expr", {}))
            if expr:
                constraints.append(Constraint(expr, c.get("is_true", True)))

        sat, model = self.solver.check_sat(constraints)
        return {
            "success": True,
            "satisfiable": sat,
            "model": model,
            "constraint_count": len(constraints),
        }

    def simplify_expression(self, expr_data: Dict) -> Dict[str, Any]:
        """化简表达式"""
        expr = self._parse_expr_from_dict(expr_data)
        if expr is None:
            return {"success": False, "message": "无效表达式"}

        simplified = self.solver.simplify(expr)
        return {
            "success": True,
            "original": str(expr),
            "simplified": str(simplified),
        }

    def _parse_expr_from_dict(self, data: Dict) -> Optional[SymbolicExpr]:
        """从字典解析符号表达式"""
        if not data:
            return None
        op = SymbolicOp(data.get("op", "const"))
        args = []
        for a in data.get("args", []):
            if isinstance(a, dict):
                parsed = self._parse_expr_from_dict(a)
                if parsed:
                    args.append(parsed)
            else:
                args.append(a)
        return SymbolicExpr(op=op, args=args)

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "supported_instructions": len(MNEMONIC_TO_TYPE),
            "conditional_jumps": len(CONDITIONAL_JUMPS),
            "registers": len(ALL_REGISTERS),
            "symbolic_ops": len(SymbolicOp),
            "structure_types": len(StructureType),
        }


# ============================================================
# 便捷函数
# ============================================================

def quick_decompile(asm_text: str) -> Dict[str, Any]:
    """快速反编译"""
    engine = DecompilerEngine()
    return engine.decompile(asm_text)


def quick_build_cfg(asm_text: str) -> Dict[str, Any]:
    """快速构建 CFG"""
    engine = DecompilerEngine()
    return engine.build_cfg(asm_text)


def quick_symbolic_execute(asm_text: str) -> Dict[str, Any]:
    """快速符号执行"""
    engine = DecompilerEngine()
    return engine.symbolic_execute(asm_text)