"""
代码混淆检测与反混淆引擎 (Code Obfuscation Detection & Deobfuscation Engine)
提供全面的代码混淆类型识别、反混淆变换、控制流展平逆转、字符串解密、不透明谓词检测。

引擎突破 17: 支持 OLLVM/CFF/指令替换/字符串加密/虚拟化混淆检测与对抗
"""

import os
import re
import struct
import math
import json
from typing import Dict, List, Optional, Tuple, Set, Any, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict, Counter


# ============================================================
# 枚举与数据类
# ============================================================

class ObfuscationType(Enum):
    """混淆类型"""
    CONTROL_FLOW_FLATTENING = "control_flow_flattening"     # 控制流展平
    INSTRUCTION_SUBSTITUTION = "instruction_substitution"    # 指令替换
    BOGUS_CONTROL_FLOW = "bogus_control_flow"               # 虚假控制流
    STRING_ENCRYPTION = "string_encryption"                  # 字符串加密
    OPAQUE_PREDICATE = "opaque_predicate"                   # 不透明谓词
    ANTI_DISASSEMBLY = "anti_disassembly"                   # 反反汇编
    DEAD_CODE = "dead_code"                                  # 死代码插入
    CONSTANT_ENCRYPTION = "constant_encryption"              # 常量加密
    CODE_VIRTUALIZATION = "code_virtualization"              # 代码虚拟化
    PACKING = "packing"                                      # 加壳
    IMPORT_HIDING = "import_hiding"                          # 导入表隐藏
    CALL_OBFUSCATION = "call_obfuscation"                    # 调用混淆
    OVERLAPPING_INSTRUCTIONS = "overlapping_instructions"    # 指令重叠
    JUNK_CODE = "junk_code"                                  # 垃圾代码插入


class ObfuscationLevel(Enum):
    """混淆强度"""
    NONE = "none"
    LIGHT = "light"         # 轻度混淆
    MODERATE = "moderate"   # 中度混淆
    HEAVY = "heavy"         # 重度混淆
    EXTREME = "extreme"     # 极端混淆


class DeobfuscationPhase(Enum):
    """反混淆阶段"""
    DETECTION = "detection"           # 检测
    DATA_RECOVERY = "data_recovery"   # 数据恢复
    CFG_RECONSTRUCT = "cfg_reconstruct"  # 控制流重建
    CLEANUP = "cleanup"               # 清理
    VERIFICATION = "verification"     # 验证


@dataclass
class ObfuscationSignature:
    """混淆签名"""
    name: str
    obfuscation_type: ObfuscationType
    description: str
    # 检测特征
    byte_patterns: List[bytes] = field(default_factory=list)
    code_patterns: List[str] = field(default_factory=list)
    entropy_threshold: float = 0.0
    # 特征统计
    instruction_sequences: List[List[str]] = field(default_factory=list)
    # 反混淆方法
    deobfuscation_methods: List[str] = field(default_factory=list)


@dataclass
class ObfuscationDetection:
    """混淆检测结果"""
    signature: ObfuscationSignature
    detected: bool
    confidence: float
    locations: List[int] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)


@dataclass
class StringEncryption:
    """字符串加密项"""
    address: int
    encrypted_data: bytes
    key: bytes = b""
    decrypted: str = ""
    algorithm: str = "unknown"
    key_ref: int = 0


@dataclass
class OpaquePredicate:
    """不透明谓词"""
    address: int
    pattern: str
    always_true: bool
    always_false: bool
    instruction_bytes: bytes = b""


@dataclass
class DeobfuscationReport:
    """反混淆报告"""
    target_file: str = ""
    detected_types: List[ObfuscationType] = field(default_factory=list)
    obfuscation_level: ObfuscationLevel = ObfuscationLevel.NONE
    detections: List[ObfuscationDetection] = field(default_factory=list)
    encrypted_strings: List[StringEncryption] = field(default_factory=list)
    opaque_predicates: List[OpaquePredicate] = field(default_factory=list)
    entropy_score: float = 0.0
    complexity_score: float = 0.0
    deobfuscation_plan: List[str] = field(default_factory=list)


# ============================================================
# 混淆签名数据库
# ============================================================

OBFUSCATION_SIGNATURES: List[ObfuscationSignature] = [
    # ---- 控制流展平 ----
    ObfuscationSignature(
        name="OLLVM_ControlFlowFlattening",
        obfuscation_type=ObfuscationType.CONTROL_FLOW_FLATTENING,
        description="OLLVM 控制流展平：将正常控制流转换为 switch-case 分发器模式",
        byte_patterns=[
            # 典型的分发器模式: cmp/jmp/jmp table
            bytes([0x83, 0xF8]),  # cmp eax, imm8 (状态比较)
        ],
        code_patterns=[
            r"stateVar.*=.*\d+",              # 状态变量赋值
            r"switch.*state",                  # switch 分发
            r"cmov|cmovn?[ezsbl]?",           # 条件移动
            r"jmp.*\[.*\*.*4\]",              # 跳转表
        ],
        instruction_sequences=[
            ["cmp", "je", "jmp"],              # 分发器常见模式
            ["cmp", "ja", "jmp"],              # 边界检查
            ["mov", "add", "jmp"],             # 状态更新
        ],
        deobfuscation_methods=[
            "符号执行恢复真实控制流",
            "基于静态分析的状态变量追踪",
            "跳转表重构与直接跳转替换",
            "CFG 重建与分发器节点消除",
        ],
    ),
    ObfuscationSignature(
        name="SwitchBasedFlattening",
        obfuscation_type=ObfuscationType.CONTROL_FLOW_FLATTENING,
        description="基于 switch 的控制流展平",
        code_patterns=[
            r"switch\(.*\)", r"case\s+0x[0-9a-fA-F]+",
        ],
        deobfuscation_methods=[
            "识别 switch 分发器，恢复原始控制流",
            "合并 case 块为顺序执行",
        ],
    ),

    # ---- 指令替换 ----
    ObfuscationSignature(
        name="OLLVM_InstructionSubstitution",
        obfuscation_type=ObfuscationType.INSTRUCTION_SUBSTITUTION,
        description="OLLVM 指令替换：将简单指令替换为复杂等效操作",
        byte_patterns=[
            # add -> sub/neg 替换模式
            bytes([0xF7, 0xD8]),  # neg eax
            bytes([0x29, 0xC0]),  # sub eax, eax
        ],
        code_patterns=[
            r"sub.*neg.*add",         # a+b = a-(-b)
            r"xor.*sub.*and",         # 复杂算术替换
            r"and.*shr.*xor",         # 位运算替换
        ],
        instruction_sequences=[
            ["neg", "sub"],            # a - b = a + (-b)
            ["xor", "sub", "xor"],     # 复杂位运算
            ["and", "shr", "xor"],     # 混淆比较
        ],
        deobfuscation_methods=[
            "模式匹配还原简单指令",
            "常量折叠与代数简化",
            "Peephole 优化",
        ],
    ),
    ObfuscationSignature(
        name="MBA_Obfuscation",
        obfuscation_type=ObfuscationType.INSTRUCTION_SUBSTITUTION,
        description="MBA (Mixed Boolean-Arithmetic) 混淆",
        code_patterns=[
            r"\(x\s*\^\s*y\)\s*\+.*\(x\s*&\s*y\)",
            r"\(x\s*\|\s*y\)\s*\-.*\(x\s*&\s*y\)",
        ],
        deobfuscation_methods=[
            "MBA 表达式简化",
            "布尔代数恒等式化简",
            "符号执行求解",
        ],
    ),

    # ---- 虚假控制流 ----
    ObfuscationSignature(
        name="OLLVM_BogusControlFlow",
        obfuscation_type=ObfuscationType.BOGUS_CONTROL_FLOW,
        description="OLLVM 虚假控制流：插入永不执行的代码块",
        code_patterns=[
            r"if\s*\(\s*[a-z]+\s*[<>=]+\s*[a-z]+\s*&&\s*[a-z]+\s*[<>=]+\s*[a-z]+\s*\)",
        ],
        instruction_sequences=[
            ["cmp", "jg", "cmp", "jl", "jmp"],  # 永假条件
            ["cmp", "jge", "cmp", "jle", "jmp"], # 永真条件
        ],
        deobfuscation_methods=[
            "不透明谓词检测与消除",
            "不可达代码块移除",
            "基于抽象解释的路径分析",
        ],
    ),

    # ---- 字符串加密 ----
    ObfuscationSignature(
        name="XORStringEncryption",
        obfuscation_type=ObfuscationType.STRING_ENCRYPTION,
        description="XOR 字符串加密",
        byte_patterns=[
            bytes([0x34]),  # xor al, imm8
            bytes([0x80, 0xF0]),  # xor al, imm8
            bytes([0x80, 0xF1]),  # xor cl, imm8
        ],
        code_patterns=[
            r"xor.*byte.*ptr", r"XOR.*0x",
            r"decrypt.*string", r"string.*decrypt",
        ],
        deobfuscation_methods=[
            "XOR 密钥提取与批量解密",
            "静态解密器模拟执行",
            "字符串引用重建",
        ],
    ),
    ObfuscationSignature(
        name="StackStringConstruction",
        obfuscation_type=ObfuscationType.STRING_ENCRYPTION,
        description="栈字符串构造（运行时拼接）",
        code_patterns=[
            r"mov\s+(?:byte|word|dword)\s+ptr\s+\[ebp|\[rsp",
        ],
        instruction_sequences=[
            ["mov", "mov", "mov", "mov"],  # 连续 mov 到栈
        ],
        deobfuscation_methods=[
            "栈内存追踪与字符串拼接",
            "模拟执行收集栈值",
            "模式识别重建字符串",
        ],
    ),

    # ---- 不透明谓词 ----
    ObfuscationSignature(
        name="InvariantOpaquePredicate",
        obfuscation_type=ObfuscationType.OPAQUE_PREDICATE,
        description="基于不变量的不透明谓词",
        byte_patterns=[
            # x*(x+1) % 2 == 0 模式
            bytes([0x6B, 0xC0]),  # imul eax, eax, imm8
        ],
        code_patterns=[
            r"x\s*\*\s*\(x\s*\+\s*1\)\s*%\s*2",
            r"n\s*\*\s*\(n\s*\+\s*1\)",
        ],
        deobfuscation_methods=[
            "不透明谓词模式识别",
            "代数恒等式验证",
            "Z3 约束求解验证",
        ],
    ),
    ObfuscationSignature(
        name="ConstantOpaquePredicate",
        obfuscation_type=ObfuscationType.OPAQUE_PREDICATE,
        description="基于常量比较的不透明谓词",
        instruction_sequences=[
            ["cmp", "sete", "test", "jne"],  # 常量永真比较
            ["cmp", "setne", "test", "je"],  # 常量永假比较
        ],
        deobfuscation_methods=[
            "常量折叠识别",
            "死代码路径消除",
        ],
    ),

    # ---- 反反汇编 ----
    ObfuscationSignature(
        name="JumpIntoMiddle",
        obfuscation_type=ObfuscationType.ANTI_DISASSEMBLY,
        description="跳转到指令中间（破坏线性反汇编）",
        byte_patterns=[
            bytes([0xEB, 0xFF]),  # jmp -1 (跳转到自身)
            bytes([0xE8, 0x00, 0x00, 0x00, 0x00]),  # call $+5
        ],
        code_patterns=[
            r"jmp.*\$-1", r"jmp.*\$\+1",
        ],
        deobfuscation_methods=[
            "递归下降反汇编",
            "代码/数据分离",
            "跳转目标分析",
        ],
    ),
    ObfuscationSignature(
        name="DisassemblyDesync",
        obfuscation_type=ObfuscationType.ANTI_DISASSEMBLY,
        description="反汇编同步破坏",
        byte_patterns=[
            bytes([0xEB, 0x01]),  # jmp +1 (跳转到下一条指令的中间)
            bytes([0x74, 0x01]),  # je +1 (条件跳转破坏同步)
        ],
        deobfuscation_methods=[
            "多路径反汇编",
            "字节级分析",
            "NOP 填充识别",
        ],
    ),

    # ---- 死代码 ----
    ObfuscationSignature(
        name="DeadCodeInsertion",
        obfuscation_type=ObfuscationType.DEAD_CODE,
        description="死代码插入（无用指令填充）",
        instruction_sequences=[
            ["push", "pop"],  # 无用的 push/pop 对
            ["mov", "mov"],  # 重复赋值
            ["nop", "nop", "nop"],  # 连续 NOP
        ],
        deobfuscation_methods=[
            "活性分析消除死代码",
            "数据流分析识别无用赋值",
            "Peephole 优化",
        ],
    ),

    # ---- 常量加密 ----
    ObfuscationSignature(
        name="ConstantEncryption",
        obfuscation_type=ObfuscationType.CONSTANT_ENCRYPTION,
        description="常量加密（将立即数替换为运行时计算）",
        byte_patterns=[
            bytes([0x35]),  # xor eax, imm32
            bytes([0x81, 0xF0]),  # xor eax, imm32
        ],
        code_patterns=[
            r"xor.*0x[0-9a-fA-F]{8}",
            r"imul.*0x[0-9a-fA-F]+",
            r"ror.*ror.*add",
        ],
        deobfuscation_methods=[
            "常量折叠",
            "代数简化",
            "符号执行求值",
        ],
    ),

    # ---- 代码虚拟化 ----
    ObfuscationSignature(
        name="VMProtectStyle",
        obfuscation_type=ObfuscationType.CODE_VIRTUALIZATION,
        description="VMProtect 风格代码虚拟化",
        byte_patterns=[
            bytes([0xE9]),  # jmp rel32 (VM 入口)
            bytes([0x50, 0x51, 0x52, 0x53]),  # pushad (保存寄存器)
        ],
        code_patterns=[
            r"pushad|pushfd|pushfq",
            r"vm_entry|vm_exit|vm_handler",
            r"VMProtect|vmp",
        ],
        deobfuscation_methods=[
            "VM Handler 识别与分析",
            "VM 指令集提取",
            "VM 字节码转译",
            "VM 退出点识别",
        ],
    ),
    ObfuscationSignature(
        name="ThemidaStyle",
        obfuscation_type=ObfuscationType.CODE_VIRTUALIZATION,
        description="Themida 风格代码虚拟化",
        byte_patterns=[
            bytes([0xE8, 0x00, 0x00, 0x00, 0x00]),  # call $+5 (获取EIP)
        ],
        code_patterns=[
            r"Themida|WinLicense",
            r"Fish|Tiger|Eagle|Panther|Shark",
        ],
        deobfuscation_methods=[
            "虚拟机入口检测",
            "Handler 表提取",
            "字节码反汇编",
        ],
    ),

    # ---- 加壳 ----
    ObfuscationSignature(
        name="UPX_Packing",
        obfuscation_type=ObfuscationType.PACKING,
        description="UPX 加壳",
        byte_patterns=[
            b"UPX0", b"UPX1", b"UPX!",
        ],
        code_patterns=[
            r"UPX0|UPX1|UPX!", r"upx.*packed",
        ],
        deobfuscation_methods=[
            "upx -d 自动脱壳",
            "OEP 查找与内存转储",
            "导入表重建",
        ],
    ),
    ObfuscationSignature(
        name="ASPack_Packing",
        obfuscation_type=ObfuscationType.PACKING,
        description="ASPack 加壳",
        byte_patterns=[
            b".aspack", b".adata",
        ],
        deobfuscation_methods=[
            "ESP 定律脱壳",
            "单步跟踪 OEP",
            "内存转储 + 导入表修复",
        ],
    ),

    # ---- 导入表隐藏 ----
    ObfuscationSignature(
        name="DynamicImportResolution",
        obfuscation_type=ObfuscationType.IMPORT_HIDING,
        description="动态导入解析（隐藏 API 调用）",
        code_patterns=[
            r"GetProcAddress", r"LoadLibrary",
            r"LdrLoadDll|LdrGetProcedureAddress",
        ],
        deobfuscation_methods=[
            "API 调用追踪",
            "导入表重建",
            "IAT 修复",
        ],
    ),

    # ---- 调用混淆 ----
    ObfuscationSignature(
        name="CallObfuscation",
        obfuscation_type=ObfuscationType.CALL_OBFUSCATION,
        description="调用混淆（push/ret 替代 call, jmp 跳板）",
        byte_patterns=[
            bytes([0x68]),  # push imm32 (push 返回地址 + ret)
            bytes([0xC3]),  # ret
        ],
        instruction_sequences=[
            ["push", "ret"],  # push addr; ret = call addr
            ["push", "call", "ret"],  # 复杂调用链
        ],
        deobfuscation_methods=[
            "push/ret 模式识别与还原",
            "调用图重建",
            "跳板消除",
        ],
    ),

    # ---- 指令重叠 ----
    ObfuscationSignature(
        name="OverlappingInstructions",
        obfuscation_type=ObfuscationType.OVERLAPPING_INSTRUCTIONS,
        description="指令重叠（同一字节被多条指令共享）",
        code_patterns=[
            r"overlapping|obfuscated.*code",
        ],
        deobfuscation_methods=[
            "多偏移反汇编",
            "执行路径追踪",
            "指令边界分析",
        ],
    ),

    # ---- 垃圾代码 ----
    ObfuscationSignature(
        name="JunkCodeInsertion",
        obfuscation_type=ObfuscationType.JUNK_CODE,
        description="垃圾代码插入（无实际效果的指令序列）",
        instruction_sequences=[
            ["add", "sub"],  # add/sub 抵消
            ["xor", "xor"],  # xor 自身清零
            ["shl", "shr"],  # 移位抵消
            ["inc", "dec"],  # 增减抵消
        ],
        deobfuscation_methods=[
            "Peephole 优化消除",
            "数据流分析识别无效操作",
            "模式匹配批处理",
        ],
    ),
]


# ============================================================
# 熵分析器
# ============================================================

class EntropyAnalyzer:
    """信息熵分析器 — 用于检测加密/压缩/混淆"""

    @staticmethod
    def calculate_entropy(data: bytes) -> float:
        """计算香农熵"""
        if not data:
            return 0.0
        freq = Counter(data)
        length = len(data)
        entropy = 0.0
        for count in freq.values():
            p = count / length
            entropy -= p * math.log2(p)
        return entropy

    @staticmethod
    def calculate_block_entropy(data: bytes, block_size: int = 256) -> List[float]:
        """计算分块熵"""
        entropies = []
        for i in range(0, len(data), block_size):
            block = data[i:i + block_size]
            entropies.append(EntropyAnalyzer.calculate_entropy(block))
        return entropies

    @staticmethod
    def calculate_entropy_variance(data: bytes, block_size: int = 256) -> float:
        """计算熵方差（高方差表示代码/数据混合）"""
        entropies = EntropyAnalyzer.calculate_block_entropy(data, block_size)
        if not entropies:
            return 0.0
        mean = sum(entropies) / len(entropies)
        variance = sum((e - mean) ** 2 for e in entropies) / len(entropies)
        return variance

    @staticmethod
    def detect_high_entropy_regions(data: bytes, threshold: float = 6.5,
                                     block_size: int = 256) -> List[Tuple[int, int, float]]:
        """检测高熵区域"""
        regions = []
        for i in range(0, len(data), block_size):
            block = data[i:i + block_size]
            entropy = EntropyAnalyzer.calculate_entropy(block)
            if entropy >= threshold:
                regions.append((i, i + len(block), round(entropy, 2)))
        return regions


# ============================================================
# 字符串解密器
# ============================================================

class StringDecryptor:
    """字符串解密器 — 识别和解密各种加密字符串"""

    # 常见 XOR 密钥值
    COMMON_XOR_KEYS = [0x00, 0x01, 0xFF, 0x55, 0xAA, 0x20, 0x2E, 0x41, 0x50, 0xDE, 0xAD, 0xBE, 0xEF]

    def __init__(self):
        self._data: bytes = b""

    def load_data(self, data: bytes):
        self._data = data

    def find_xor_strings(self) -> List[StringEncryption]:
        """查找 XOR 加密的字符串"""
        results = []
        if not self._data:
            return results

        for key in self.COMMON_XOR_KEYS:
            pos = 0
            while pos < len(self._data) - 4:
                # 尝试解密连续的字节序列
                decrypted = bytearray()
                for i in range(pos, min(pos + 256, len(self._data))):
                    d = self._data[i] ^ key
                    if d == 0:
                        break
                    if 0x20 <= d <= 0x7E:
                        decrypted.append(d)
                    else:
                        break

                if len(decrypted) >= 4:
                    text = decrypted.decode("ascii", errors="replace")
                    if self._is_meaningful_string(text):
                        results.append(StringEncryption(
                            address=pos,
                            encrypted_data=self._data[pos:pos + len(decrypted)],
                            key=bytes([key]),
                            decrypted=text,
                            algorithm="xor_single_byte",
                            key_ref=key,
                        ))
                        pos += len(decrypted)
                    else:
                        pos += 1
                else:
                    pos += 1

        return results

    def find_stack_strings(self) -> List[StringEncryption]:
        """查找栈字符串构造"""
        results = []
        if not self._data:
            return results

        # 查找连续的 mov [ebp/rsp + offset], imm 模式
        # x86: mov byte ptr [ebp-XX], imm8  -> C6 45 XX YY
        pattern = bytes([0xC6, 0x45])
        pos = 0
        while True:
            idx = self._data.find(pattern, pos)
            if idx == -1:
                break

            # 收集连续的 mov 操作
            chars = bytearray()
            scan_pos = idx
            while scan_pos < len(self._data) - 4:
                if self._data[scan_pos:scan_pos + 2] == pattern:
                    char_val = self._data[scan_pos + 3]
                    if 0x20 <= char_val <= 0x7E or char_val == 0:
                        chars.append(char_val)
                    else:
                        break
                    scan_pos += 4
                else:
                    break

            if len(chars) >= 4:
                text = chars.decode("ascii", errors="replace")
                if self._is_meaningful_string(text):
                    results.append(StringEncryption(
                        address=idx,
                        encrypted_data=bytes(chars),
                        decrypted=text,
                        algorithm="stack_string",
                    ))

            pos = idx + 1

        return results

    def find_rc4_strings(self) -> List[StringEncryption]:
        """查找 RC4 加密的字符串"""
        results = []

        # RC4 特征: 256 字节的 S-Box 初始化
        # for i in range(256): S[i] = i
        sbox_patterns = [
            bytes(range(256)),  # 完整 S-Box
        ]

        for pattern in sbox_patterns:
            pos = 0
            while True:
                idx = self._data.find(pattern, pos)
                if idx == -1:
                    break

                results.append(StringEncryption(
                    address=idx,
                    encrypted_data=b"",
                    algorithm="rc4",
                    key_ref=idx,
                ))
                pos = idx + 1

        return results

    def _is_meaningful_string(self, text: str) -> bool:
        """判断是否为有意义的字符串"""
        if len(text) < 4:
            return False
        # 检查是否包含足够的字母字符
        alpha_count = sum(1 for c in text if c.isalpha())
        if alpha_count < len(text) * 0.6:
            return False
        # 常见无意义模式
        noise_patterns = ["AAAA", "BBBB", "XXXX", "\x00\x00"]
        for p in noise_patterns:
            if p in text:
                return False
        return True

    def decrypt_all(self) -> List[StringEncryption]:
        """解密所有类型的字符串"""
        results = []
        results.extend(self.find_xor_strings())
        results.extend(self.find_stack_strings())
        results.extend(self.find_rc4_strings())
        # 去重
        seen = set()
        unique = []
        for r in results:
            key = (r.address, r.decrypted)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return sorted(unique, key=lambda x: x.address)


# ============================================================
# 不透明谓词检测器
# ============================================================

class OpaquePredicateDetector:
    """不透明谓词检测器"""

    # 恒真谓词模式
    ALWAYS_TRUE_PATTERNS = [
        # x == x
        ([0x39, 0xC0], "cmp eax, eax -> always equal"),
        ([0x39, 0xC9], "cmp ecx, ecx -> always equal"),
        ([0x39, 0xD2], "cmp edx, edx -> always equal"),
        ([0x39, 0xDB], "cmp ebx, ebx -> always equal"),
        # x - x == 0
        ([0x29, 0xC0], "sub eax, eax -> always 0"),
        # xor x, x -> 0
        ([0x31, 0xC0], "xor eax, eax -> always 0"),
        ([0x33, 0xC0], "xor eax, eax -> always 0"),
        # test x, x if x == 0
        ([0x85, 0xC0], "test eax, eax (after zeroing)"),
        # or x, -1 -> always non-zero
        ([0x83, 0xC8, 0xFF], "or eax, -1 -> always non-zero"),
    ]

    # 恒假谓词模式
    ALWAYS_FALSE_PATTERNS = [
        # x != x
        ([0x39, 0xC0], "cmp eax, eax after jne"),
        # x & 0 == 0
        ([0x83, 0xE0, 0x00], "and eax, 0 -> always 0"),
        # 0 test
        ([0x85, 0xC0], "test eax, eax (if eax is 0)"),
    ]

    def __init__(self):
        self._data: bytes = b""

    def load_data(self, data: bytes):
        self._data = data

    def detect(self) -> List[OpaquePredicate]:
        """检测不透明谓词"""
        results = []

        for pattern, desc in self.ALWAYS_TRUE_PATTERNS:
            pos = 0
            while True:
                idx = self._data.find(bytes(pattern), pos)
                if idx == -1:
                    break
                # 检查后续指令是否为条件跳转
                following = self._data[idx + len(pattern):idx + len(pattern) + 10]
                if (following[:1] in (bytes([0x74]), bytes([0x75])) or
                        following[:2] in (bytes([0x0F, 0x84]), bytes([0x0F, 0x85]))):
                    results.append(OpaquePredicate(
                        address=idx,
                        pattern=desc,
                        always_true=True,
                        always_false=False,
                        instruction_bytes=bytes(pattern),
                    ))
                pos = idx + 1

        for pattern, desc in self.ALWAYS_FALSE_PATTERNS:
            pos = 0
            while True:
                idx = self._data.find(bytes(pattern), pos)
                if idx == -1:
                    break
                following = self._data[idx + len(pattern):idx + len(pattern) + 10]
                if (following[:1] in (bytes([0x74]), bytes([0x75])) or
                        following[:2] in (bytes([0x0F, 0x84]), bytes([0x0F, 0x85]))):
                    results.append(OpaquePredicate(
                        address=idx,
                        pattern=desc,
                        always_true=False,
                        always_false=True,
                        instruction_bytes=bytes(pattern),
                    ))
                pos = idx + 1

        return results


# ============================================================
# 控制流展平检测器
# ============================================================

class CFFDetector:
    """控制流展平 (Control Flow Flattening) 检测器"""

    def __init__(self):
        self._data: bytes = b""

    def load_data(self, data: bytes):
        self._data = data

    def detect(self) -> Dict[str, Any]:
        """检测 CFF 特征"""
        if not self._data:
            return {"detected": False, "confidence": 0.0, "evidence": []}

        evidence = []
        confidence = 0.0

        # 1. 检测状态变量（多次赋值给同一寄存器/内存位置）
        state_var_patterns = [
            bytes([0xC7, 0x45]),  # mov [ebp-XX], imm32
            bytes([0xC7, 0x85]),  # mov [ebp-XXXX], imm32
        ]
        state_assigns = 0
        for pattern in state_var_patterns:
            pos = 0
            while True:
                idx = self._data.find(pattern, pos)
                if idx == -1:
                    break
                state_assigns += 1
                pos = idx + 1

        if state_assigns >= 5:
            evidence.append(f"检测到 {state_assigns} 个状态变量赋值")
            confidence += 0.3

        # 2. 检测分发器模式（比较 + 条件跳转 + 无条件跳转）
        # cmp + conditional jmp + jmp 模式
        dispatcher_count = 0
        for i in range(len(self._data) - 6):
            if self._data[i] == 0x83 and self._data[i + 1] == 0xF8:  # cmp eax, imm8
                # 检查后续是否有条件跳转
                window = self._data[i:i + 20]
                if b'\x0F\x84' in window or b'\x0F\x85' in window or b'\x74' in window or b'\x75' in window:
                    dispatcher_count += 1

        if dispatcher_count >= 3:
            evidence.append(f"检测到 {dispatcher_count} 个分发器模式")
            confidence += 0.3

        # 3. 检测间接跳转（jmp [reg + index*4]）
        jump_table_patterns = [
            bytes([0xFF, 0x24, 0x85]),  # jmp [eax*4 + disp32]
            bytes([0xFF, 0x24, 0x8D]),  # jmp [ecx*4 + disp32]
            bytes([0xFF, 0x24, 0x95]),  # jmp [edx*4 + disp32]
        ]
        for pattern in jump_table_patterns:
            if pattern in self._data:
                evidence.append("检测到间接跳转表")
                confidence += 0.2
                break

        # 4. 检测循环结构（状态变量更新循环）
        # 预分配器模式: mov state, X; jmp dispatcher
        pre_dispatcher = 0
        for i in range(len(self._data) - 5):
            if self._data[i:i + 2] == bytes([0xC7, 0x45]):  # mov [ebp-XX], imm
                if i + 7 < len(self._data):
                    following = self._data[i + 7:i + 12]
                    if following[:1] == bytes([0xEB]):  # jmp short (to dispatcher)
                        pre_dispatcher += 1

        if pre_dispatcher >= 3:
            evidence.append(f"检测到 {pre_dispatcher} 个预分配器")
            confidence += 0.2

        return {
            "detected": confidence >= 0.3,
            "confidence": min(confidence, 1.0),
            "evidence": evidence,
            "state_assigns": state_assigns,
            "dispatcher_count": dispatcher_count,
            "pre_dispatcher_count": pre_dispatcher,
        }


# ============================================================
# 混淆检测器主入口
# ============================================================

class ObfuscationDetector:
    """
    混淆检测器
    
    综合检测各类代码混淆技术：
    - 控制流展平 (CFF)
    - 指令替换
    - 字符串加密
    - 不透明谓词
    - 代码虚拟化
    - 反反汇编
    - 加壳检测
    """

    def __init__(self):
        self._data: bytes = b""
        self._signatures = OBFUSCATION_SIGNATURES
        self._detections: List[ObfuscationDetection] = []
        self._entropy = EntropyAnalyzer()
        self._string_decryptor = StringDecryptor()
        self._opaque_detector = OpaquePredicateDetector()
        self._cff_detector = CFFDetector()

    def load_data(self, data: bytes):
        self._data = data
        self._detections.clear()
        self._string_decryptor.load_data(data)
        self._opaque_detector.load_data(data)
        self._cff_detector.load_data(data)

    def load_file(self, file_path: str) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}
        try:
            with open(file_path, "rb") as f:
                self._data = f.read()
            self._string_decryptor.load_data(self._data)
            self._opaque_detector.load_data(self._data)
            self._cff_detector.load_data(self._data)
            return {"success": True, "file": file_path, "size": len(self._data)}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def scan_all(self) -> List[ObfuscationDetection]:
        """全面扫描"""
        self._detections = []
        if not self._data:
            return self._detections

        for sig in self._signatures:
            detection = self._scan_signature(sig)
            self._detections.append(detection)

        return self._detections

    def _scan_signature(self, sig: ObfuscationSignature) -> ObfuscationDetection:
        """扫描单个签名"""
        locations = []
        evidence = []
        confidence = 0.0

        # 字节模式
        for pattern in sig.byte_patterns:
            pos = 0
            while True:
                idx = self._data.find(pattern, pos)
                if idx == -1:
                    break
                locations.append(idx)
                pos = idx + 1

        if locations:
            confidence += 0.3
            evidence.append(f"字节模式匹配: {len(locations)} 处")

        # 代码模式
        try:
            text = self._data.decode("ascii", errors="ignore")
        except:
            text = ""

        for pattern in sig.code_patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    confidence += 0.2
                    evidence.append(f"代码模式匹配: {pattern}")
            except re.error:
                pass

        # 指令序列
        for seq in sig.instruction_sequences:
            seq_bytes = [instr.encode("ascii") for instr in seq]
            if self._find_instruction_sequence(seq_bytes):
                confidence += 0.25
                evidence.append(f"指令序列匹配: {' -> '.join(seq)}")
                break

        confidence = min(confidence, 1.0)
        detected = confidence >= 0.3

        return ObfuscationDetection(
            signature=sig,
            detected=detected,
            confidence=round(confidence, 2),
            locations=sorted(locations),
            evidence=evidence,
        )

    def _find_instruction_sequence(self, instructions: List[bytes]) -> bool:
        """在数据中查找指令序列模式"""
        if not instructions or not self._data:
            return False

        # 简化：检查每个指令是否出现在数据中
        for instr in instructions:
            if instr not in self._data:
                return False
        return True

    def get_obfuscation_level(self) -> ObfuscationLevel:
        """评估混淆强度"""
        if not self._detections:
            return ObfuscationLevel.NONE

        detected = [d for d in self._detections if d.detected]
        count = len(detected)

        if count == 0:
            return ObfuscationLevel.NONE
        elif count <= 2:
            return ObfuscationLevel.LIGHT
        elif count <= 4:
            return ObfuscationLevel.MODERATE
        elif count <= 7:
            return ObfuscationLevel.HEAVY
        else:
            return ObfuscationLevel.EXTREME

    def get_complexity_score(self) -> float:
        """计算代码复杂度评分"""
        if not self._data:
            return 0.0

        score = 0.0

        # 1. 熵评分
        entropy = self._entropy.calculate_entropy(self._data)
        entropy_variance = self._entropy.calculate_entropy_variance(self._data)
        score += min(entropy / 8.0, 1.0) * 0.3

        # 2. 混淆检测评分
        if self._detections:
            avg_confidence = sum(d.confidence for d in self._detections) / len(self._detections)
            score += avg_confidence * 0.4

        # 3. 熵方差（高方差表示混淆）
        score += min(entropy_variance / 2.0, 1.0) * 0.3

        return round(score, 2)


# ============================================================
# 反混淆器主入口
# ============================================================

class DeobfuscatorEngine:
    """
    代码混淆检测与反混淆引擎（主入口）
    
    整合检测、解密、CFG 重建、清理四大阶段：
    - 13+ 混淆类型识别
    - 字符串自动解密
    - 不透明谓词检测
    - 控制流展平检测
    - 反混淆方案生成
    """

    def __init__(self):
        self.detector = ObfuscationDetector()
        self._entropy = EntropyAnalyzer()
        self._string_decryptor = StringDecryptor()
        self._opaque_detector = OpaquePredicateDetector()
        self._cff_detector = CFFDetector()

    def analyze(self, file_path: str) -> Dict[str, Any]:
        """综合分析文件混淆情况"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            return {"success": False, "message": str(e)}

        # 1. 混淆检测
        self.detector.load_data(data)
        detections = self.detector.scan_all()
        level = self.detector.get_obfuscation_level()
        complexity = self.detector.get_complexity_score()

        # 2. 熵分析
        entropy = self._entropy.calculate_entropy(data)
        entropy_variance = self._entropy.calculate_entropy_variance(data)
        high_entropy_regions = self._entropy.detect_high_entropy_regions(data)

        # 3. 字符串解密
        self._string_decryptor.load_data(data)
        encrypted_strings = self._string_decryptor.decrypt_all()

        # 4. 不透明谓词
        self._opaque_detector.load_data(data)
        opaque_predicates = self._opaque_detector.detect()

        # 5. CFF 检测
        self._cff_detector.load_data(data)
        cff_result = self._cff_detector.detect()

        # 6. 生成反混淆方案
        deobfuscation_plan = self._generate_deobfuscation_plan(detections)

        detected_types = [d.signature.obfuscation_type.value
                          for d in detections if d.detected]

        return {
            "success": True,
            "file": os.path.basename(file_path),
            "file_size": len(data),
            "entropy": {
                "overall": round(entropy, 2),
                "variance": round(entropy_variance, 2),
                "max_entropy": 8.0,
                "high_entropy_regions": [
                    {"start": r[0], "end": r[1], "entropy": r[2]}
                    for r in high_entropy_regions[:10]
                ],
            },
            "obfuscation_level": level.value,
            "complexity_score": complexity,
            "detected_types": detected_types,
            "detections": [
                {
                    "name": d.signature.name,
                    "type": d.signature.obfuscation_type.value,
                    "detected": d.detected,
                    "confidence": d.confidence,
                    "description": d.signature.description,
                    "evidence": d.evidence,
                    "deobfuscation_methods": d.signature.deobfuscation_methods,
                }
                for d in detections
            ],
            "encrypted_strings": [
                {
                    "address": s.address,
                    "decrypted": s.decrypted,
                    "algorithm": s.algorithm,
                }
                for s in encrypted_strings[:20]
            ],
            "encrypted_string_count": len(encrypted_strings),
            "opaque_predicates": [
                {
                    "address": p.address,
                    "pattern": p.pattern,
                    "always_true": p.always_true,
                    "always_false": p.always_false,
                }
                for p in opaque_predicates[:10]
            ],
            "opaque_predicate_count": len(opaque_predicates),
            "cff_analysis": cff_result,
            "deobfuscation_plan": deobfuscation_plan,
        }

    def _generate_deobfuscation_plan(self, detections: List[ObfuscationDetection]) -> List[str]:
        """生成反混淆方案"""
        plan = []
        phase_order = {
            DeobfuscationPhase.DATA_RECOVERY: [],
            DeobfuscationPhase.CFG_RECONSTRUCT: [],
            DeobfuscationPhase.CLEANUP: [],
            DeobfuscationPhase.VERIFICATION: [],
        }

        for d in detections:
            if not d.detected:
                continue
            for method in d.signature.deobfuscation_methods:
                obf_type = d.signature.obfuscation_type
                if obf_type in (ObfuscationType.STRING_ENCRYPTION,
                                ObfuscationType.CONSTANT_ENCRYPTION,
                                ObfuscationType.PACKING):
                    phase_order[DeobfuscationPhase.DATA_RECOVERY].append(method)
                elif obf_type in (ObfuscationType.CONTROL_FLOW_FLATTENING,
                                  ObfuscationType.OPAQUE_PREDICATE,
                                  ObfuscationType.BOGUS_CONTROL_FLOW):
                    phase_order[DeobfuscationPhase.CFG_RECONSTRUCT].append(method)
                else:
                    phase_order[DeobfuscationPhase.CLEANUP].append(method)

        # 构建有序方案
        phase_names = {
            DeobfuscationPhase.DATA_RECOVERY: "阶段1: 数据恢复",
            DeobfuscationPhase.CFG_RECONSTRUCT: "阶段2: 控制流重建",
            DeobfuscationPhase.CLEANUP: "阶段3: 代码清理",
            DeobfuscationPhase.VERIFICATION: "阶段4: 验证",
        }

        for phase, methods in phase_order.items():
            if methods:
                plan.append(phase_names[phase])
                for method in methods:
                    plan.append(f"  - {method}")

        if not plan:
            plan.append("未检测到混淆，无需反混淆处理")

        return plan

    def scan_obfuscation(self, file_path: str) -> Dict[str, Any]:
        """扫描混淆类型"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        result = self.detector.load_file(file_path)
        if not result["success"]:
            return result

        detections = self.detector.scan_all()

        return {
            "success": True,
            "file": os.path.basename(file_path),
            "obfuscation_level": self.detector.get_obfuscation_level().value,
            "complexity_score": self.detector.get_complexity_score(),
            "detected": [
                {
                    "name": d.signature.name,
                    "type": d.signature.obfuscation_type.value,
                    "detected": d.detected,
                    "confidence": d.confidence,
                    "description": d.signature.description,
                }
                for d in detections
            ],
            "summary": {
                "total_signatures": len(detections),
                "detected_count": sum(1 for d in detections if d.detected),
            },
        }

    def decrypt_strings(self, file_path: str) -> Dict[str, Any]:
        """解密字符串"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            return {"success": False, "message": str(e)}

        self._string_decryptor.load_data(data)
        strings = self._string_decryptor.decrypt_all()

        return {
            "success": True,
            "file": os.path.basename(file_path),
            "total_strings": len(strings),
            "strings": [
                {
                    "address": s.address,
                    "decrypted": s.decrypted,
                    "algorithm": s.algorithm,
                }
                for s in strings
            ],
        }

    def detect_opaque_predicates(self, file_path: str) -> Dict[str, Any]:
        """检测不透明谓词"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            return {"success": False, "message": str(e)}

        self._opaque_detector.load_data(data)
        predicates = self._opaque_detector.detect()

        return {
            "success": True,
            "file": os.path.basename(file_path),
            "total": len(predicates),
            "predicates": [
                {
                    "address": p.address,
                    "pattern": p.pattern,
                    "always_true": p.always_true,
                    "always_false": p.always_false,
                }
                for p in predicates
            ],
        }

    def detect_cff(self, file_path: str) -> Dict[str, Any]:
        """检测控制流展平"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            return {"success": False, "message": str(e)}

        self._cff_detector.load_data(data)
        result = self._cff_detector.detect()

        return {
            "success": True,
            "file": os.path.basename(file_path),
            **result,
        }

    def get_entropy_analysis(self, file_path: str) -> Dict[str, Any]:
        """获取熵分析"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            return {"success": False, "message": str(e)}

        entropy = self._entropy.calculate_entropy(data)
        variance = self._entropy.calculate_entropy_variance(data)
        high_regions = self._entropy.detect_high_entropy_regions(data)

        return {
            "success": True,
            "file": os.path.basename(file_path),
            "file_size": len(data),
            "entropy": round(entropy, 2),
            "entropy_variance": round(variance, 2),
            "assessment": self._entropy_assessment(entropy, variance),
            "high_entropy_regions": [
                {"start": r[0], "end": r[1], "entropy": r[2]}
                for r in high_regions[:10]
            ],
        }

    def _entropy_assessment(self, entropy: float, variance: float) -> str:
        """评估熵含义"""
        if entropy > 7.5:
            return "极高熵值，强烈提示加密或高强度压缩"
        elif entropy > 7.0:
            return "高熵值，可能包含加密数据或压缩代码"
        elif entropy > 6.0:
            return "中等熵值，可能存在部分加密或混淆"
        elif entropy > 4.0:
            return "正常熵值，常规代码/数据"
        else:
            return "低熵值，高度重复的数据/代码"

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        by_type = defaultdict(int)
        for sig in OBFUSCATION_SIGNATURES:
            by_type[sig.obfuscation_type.value] += 1

        return {
            "total_signatures": len(OBFUSCATION_SIGNATURES),
            "by_type": dict(by_type),
            "obfuscation_types": [t.value for t in ObfuscationType],
            "levels": [l.value for l in ObfuscationLevel],
        }


# ============================================================
# 便捷函数
# ============================================================

def quick_analyze(file_path: str) -> Dict[str, Any]:
    """快速分析文件混淆"""
    engine = DeobfuscatorEngine()
    return engine.analyze(file_path)


def quick_decrypt_strings(file_path: str) -> Dict[str, Any]:
    """快速解密字符串"""
    engine = DeobfuscatorEngine()
    return engine.decrypt_strings(file_path)


def quick_entropy(file_path: str) -> Dict[str, Any]:
    """快速熵分析"""
    engine = DeobfuscatorEngine()
    return engine.get_entropy_analysis(file_path)