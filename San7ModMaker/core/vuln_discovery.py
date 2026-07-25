#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
引擎突破21: 漏洞挖掘引擎 (Vulnerability Discovery Engine)

本模块实现针对游戏可执行文件及动态链接库的静态漏洞挖掘分析。
通过对二进制文件、汇编代码、PE/ELF 结构进行深度扫描，自动检测常见
二进制漏洞并提供详细的风险评估报告。

核心能力:
    - 不安全函数调用检测 (strcpy/gets/printf/system 等)
    - 缓冲区溢出分析 (栈溢出/堆溢出/off-by-one)
    - 整数溢出与符号混淆检测
    - 内存安全分析 (UAF/双重释放/空指针解引用/类型混淆)
    - 二进制保护机制检查 (GS/DEP/ASLR/CFG/SafeSEH)
    - SEH 异常处理器安全分析
    - 综合风险评估与修复建议

支持的漏洞类型覆盖 18 种常见 CWE 漏洞分类，每种漏洞均提供
CWE 编号、严重等级、利用难度和修复建议。

作者: San7ModMaker Team
版本: 1.0.0
"""

import os
import re
import struct
import hashlib
import json
import math
from typing import Dict, List, Optional, Tuple, Set, Union, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from collections import defaultdict, Counter, OrderedDict


# ============================================================================
# 枚举定义 (Enums)
# ============================================================================

class VulnerabilityType(Enum):
    """漏洞类型枚举，每种类型对应一个 CWE 编号"""
    BUFFER_OVERFLOW = auto()
    FORMAT_STRING = auto()
    INTEGER_OVERFLOW = auto()
    USE_AFTER_FREE = auto()
    DOUBLE_FREE = auto()
    NULL_POINTER_DEREF = auto()
    RACE_CONDITION = auto()
    STACK_OVERFLOW = auto()
    HEAP_OVERFLOW = auto()
    COMMAND_INJECTION = auto()
    PATH_TRAVERSAL = auto()
    INSECURE_API = auto()
    MISSING_STACK_COOKIE = auto()
    DEP_DISABLED = auto()
    ASLR_DISABLED = auto()
    SEH_OVERWRITE = auto()
    UNINITIALIZED_MEMORY = auto()
    TYPE_CONFUSION = auto()


class SeverityLevel(Enum):
    """漏洞严重等级"""
    CRITICAL = (10.0, "严重")
    HIGH = (8.0, "高危")
    MEDIUM = (5.5, "中危")
    LOW = (3.0, "低危")
    INFO = (1.0, "信息")

    def __init__(self, score: float, label_cn: str):
        self.score = score
        self.label_cn = label_cn

    @property
    def numeric_score(self) -> float:
        return self.score

    @property
    def chinese_label(self) -> str:
        return self.label_cn


class ExploitDifficulty(Enum):
    """漏洞利用难度"""
    TRIVIAL = (1.0, "极为简单", "无需特殊技能，可自动化利用")
    EASY = (2.0, "容易", "需要基础技能，公开 Exp 可用")
    MODERATE = (3.0, "中等", "需要一定逆向经验，需绕过部分保护")
    HARD = (4.0, "困难", "需要高级技术，需绕过多种保护")
    EXTREME = (5.0, "极其困难", "需要零日级别技术，多阶段组合利用")

    def __init__(self, rating: float, label_cn: str, description: str):
        self.rating = rating
        self.label_cn = label_cn
        self.description = description

    @property
    def numeric_rating(self) -> float:
        return self.rating


# ============================================================================
# 数据类定义 (Dataclasses)
# ============================================================================

@dataclass
class Vulnerability:
    """单个漏洞的详细信息"""
    vuln_type: VulnerabilityType
    severity: SeverityLevel
    description: str
    location: str                        # 漏洞位置 (地址/函数名/RVA)
    confidence: float                    # 置信度 0.0 - 1.0
    exploit_difficulty: ExploitDifficulty
    cwe_id: str                          # CWE 编号，如 "CWE-120"
    fix_suggestion: str                  # 修复建议

    # 可选附加信息
    affected_code: Optional[str] = None  # 受影响代码片段
    line_number: Optional[int] = None
    extra_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，便于 JSON 序列化"""
        result = {
            "vuln_type": self.vuln_type.name,
            "severity": self.severity.name,
            "severity_score": self.severity.numeric_score,
            "description": self.description,
            "location": self.location,
            "confidence": self.confidence,
            "exploit_difficulty": self.exploit_difficulty.name,
            "exploit_difficulty_rating": self.exploit_difficulty.numeric_rating,
            "cwe_id": self.cwe_id,
            "fix_suggestion": self.fix_suggestion,
        }
        if self.affected_code:
            result["affected_code"] = self.affected_code
        if self.line_number is not None:
            result["line_number"] = self.line_number
        if self.extra_info:
            result["extra_info"] = self.extra_info
        return result

    def __str__(self) -> str:
        return (
            f"[{self.severity.name}] {self.vuln_type.name} "
            f"@ {self.location} (置信度: {self.confidence:.0%}, "
            f"CWE: {self.cwe_id})"
        )


@dataclass
class VulnerabilityReport:
    """漏洞扫描综合报告"""
    target_file: str
    vulns: List[Vulnerability] = field(default_factory=list)
    risk_score: float = 0.0
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)

    # 统计信息
    total_vulns: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0

    # 扫描元数据
    scan_timestamp: str = ""
    scan_duration_ms: float = 0.0
    file_hash: str = ""
    file_size: int = 0

    def update_statistics(self) -> None:
        """更新统计信息"""
        self.total_vulns = len(self.vulns)
        counter = Counter(v.severity for v in self.vulns)
        self.critical_count = counter.get(SeverityLevel.CRITICAL, 0)
        self.high_count = counter.get(SeverityLevel.HIGH, 0)
        self.medium_count = counter.get(SeverityLevel.MEDIUM, 0)
        self.low_count = counter.get(SeverityLevel.LOW, 0)
        self.info_count = counter.get(SeverityLevel.INFO, 0)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        self.update_statistics()
        return {
            "target_file": self.target_file,
            "risk_score": round(self.risk_score, 2),
            "summary": self.summary,
            "total_vulns": self.total_vulns,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "info_count": self.info_count,
            "recommendations": self.recommendations,
            "vulns": [v.to_dict() for v in self.vulns],
            "scan_timestamp": self.scan_timestamp,
            "scan_duration_ms": self.scan_duration_ms,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
        }

    def to_json(self, indent: int = 2) -> str:
        """导出为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ============================================================================
# CWE 映射表 (CWE Mapping)
# ============================================================================

_CWE_MAP: Dict[VulnerabilityType, str] = {
    VulnerabilityType.BUFFER_OVERFLOW: "CWE-120",
    VulnerabilityType.FORMAT_STRING: "CWE-134",
    VulnerabilityType.INTEGER_OVERFLOW: "CWE-190",
    VulnerabilityType.USE_AFTER_FREE: "CWE-416",
    VulnerabilityType.DOUBLE_FREE: "CWE-415",
    VulnerabilityType.NULL_POINTER_DEREF: "CWE-476",
    VulnerabilityType.RACE_CONDITION: "CWE-362",
    VulnerabilityType.STACK_OVERFLOW: "CWE-121",
    VulnerabilityType.HEAP_OVERFLOW: "CWE-122",
    VulnerabilityType.COMMAND_INJECTION: "CWE-77",
    VulnerabilityType.PATH_TRAVERSAL: "CWE-22",
    VulnerabilityType.INSECURE_API: "CWE-676",
    VulnerabilityType.MISSING_STACK_COOKIE: "CWE-693",
    VulnerabilityType.DEP_DISABLED: "CWE-693",
    VulnerabilityType.ASLR_DISABLED: "CWE-693",
    VulnerabilityType.SEH_OVERWRITE: "CWE-122",
    VulnerabilityType.UNINITIALIZED_MEMORY: "CWE-457",
    VulnerabilityType.TYPE_CONFUSION: "CWE-843",
}


def get_cwe_id(vuln_type: VulnerabilityType) -> str:
    """获取漏洞类型对应的 CWE 编号"""
    return _CWE_MAP.get(vuln_type, "CWE-UNKNOWN")


# ============================================================================
# 辅助工具函数 (Utility Functions)
# ============================================================================

def _compute_file_hash(file_path: str) -> str:
    """计算文件 SHA256 哈希"""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()
    except (IOError, OSError):
        return ""


def _read_file_bytes(file_path: str) -> Optional[bytes]:
    """安全读取文件字节"""
    try:
        with open(file_path, "rb") as f:
            return f.read()
    except (IOError, OSError):
        return None


def _read_file_text(file_path: str, encoding: str = "utf-8") -> Optional[str]:
    """安全读取文件文本"""
    try:
        with open(file_path, "r", encoding=encoding, errors="replace") as f:
            return f.read()
    except (IOError, OSError):
        return None


def _is_pe_file(data: bytes) -> bool:
    """检查是否为 PE 文件"""
    if len(data) < 2:
        return False
    return data[:2] == b"MZ"


def _is_elf_file(data: bytes) -> bool:
    """检查是否为 ELF 文件"""
    if len(data) < 4:
        return False
    return data[:4] == b"\x7fELF"


def _safe_search(pattern: Union[str, bytes], content: Union[str, bytes]) -> List[re.Match]:
    """安全正则搜索，返回所有匹配"""
    try:
        if isinstance(pattern, str) and isinstance(content, str):
            return list(re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE))
        elif isinstance(pattern, bytes) and isinstance(content, bytes):
            return list(re.finditer(pattern, content, re.IGNORECASE))
        return []
    except re.error:
        return []


# ============================================================================
# 不安全函数检测器 (UnsafeFunctionDetector)
# ============================================================================

class UnsafeFunctionDetector:
    """不安全函数调用检测器

    检测二进制文件中对危险 C 库函数和系统 API 的调用，
    这些函数在缺乏适当边界检查时可能导致缓冲区溢出、命令注入等漏洞。
    """

    # 不安全函数及其风险描述
    _UNSAFE_FUNCTIONS: Dict[str, Dict[str, Any]] = {
        # ---- 字符串操作类 ----
        "strcpy": {
            "category": "字符串复制",
            "risk": SeverityLevel.HIGH,
            "cwe": "CWE-120",
            "replacement": "strncpy / strcpy_s",
            "description": "无长度限制的字符串复制，易导致栈缓冲区溢出",
            "signature": rb"strcpy",
        },
        "strcat": {
            "category": "字符串拼接",
            "risk": SeverityLevel.HIGH,
            "cwe": "CWE-120",
            "replacement": "strncat / strcat_s",
            "description": "无长度限制的字符串拼接，易导致缓冲区溢出",
            "signature": rb"strcat",
        },
        "sprintf": {
            "category": "格式化输出",
            "risk": SeverityLevel.HIGH,
            "cwe": "CWE-120",
            "replacement": "snprintf / sprintf_s",
            "description": "无长度限制的格式化输出，易导致缓冲区溢出和格式字符串漏洞",
            "signature": rb"sprintf",
        },
        "vsprintf": {
            "category": "格式化输出",
            "risk": SeverityLevel.HIGH,
            "cwe": "CWE-120",
            "replacement": "vsnprintf / vsprintf_s",
            "description": "无长度限制的可变参数格式化输出",
            "signature": rb"vsprintf",
        },
        "gets": {
            "category": "标准输入",
            "risk": SeverityLevel.CRITICAL,
            "cwe": "CWE-120",
            "replacement": "fgets",
            "description": "极度危险，无法限制输入长度，无任何保护机制",
            "signature": rb"gets",
        },
        "scanf": {
            "category": "格式化输入",
            "risk": SeverityLevel.HIGH,
            "cwe": "CWE-120",
            "replacement": "带宽度限制的 scanf / fgets+sscanf",
            "description": "未指定字段宽度的 scanf 可能造成缓冲区溢出",
            "signature": rb"scanf",
        },
        "sscanf": {
            "category": "格式化输入",
            "risk": SeverityLevel.MEDIUM,
            "cwe": "CWE-120",
            "replacement": "带宽度限制的 sscanf",
            "description": "未指定字段宽度时可能造成缓冲区溢出",
            "signature": rb"sscanf",
        },
        # ---- 内存操作类 ----
        "strncpy": {
            "category": "字符串复制",
            "risk": SeverityLevel.MEDIUM,
            "cwe": "CWE-120",
            "replacement": "strcpy_s / strlcpy",
            "description": "可能不会自动添加 null 终止符，导致后续读取越界",
            "signature": rb"strncpy",
        },
        "memcpy": {
            "category": "内存复制",
            "risk": SeverityLevel.MEDIUM,
            "cwe": "CWE-120",
            "replacement": "memcpy_s",
            "description": "未验证目标缓冲区大小即进行复制，风险较高",
            "signature": rb"memcpy",
        },
        "memmove": {
            "category": "内存移动",
            "risk": SeverityLevel.LOW,
            "cwe": "CWE-120",
            "replacement": "memmove_s",
            "description": "未验证目标缓冲区大小，存在溢出风险",
            "signature": rb"memmove",
        },
        "memset": {
            "category": "内存初始化",
            "risk": SeverityLevel.LOW,
            "cwe": "CWE-120",
            "replacement": "memset_s",
            "description": "未验证目标缓冲区大小，可能造成越界写入",
            "signature": rb"memset",
        },
        "memcmp": {
            "category": "内存比较",
            "risk": SeverityLevel.LOW,
            "cwe": "CWE-125",
            "replacement": "memcmp_s",
            "description": "未验证比较长度，可能造成越界读取",
            "signature": rb"memcmp",
        },
        # ---- 命令执行类 ----
        "system": {
            "category": "命令执行",
            "risk": SeverityLevel.CRITICAL,
            "cwe": "CWE-78",
            "replacement": "CreateProcess / execve (参数化)",
            "description": "执行外部命令，若参数源自用户输入则存在命令注入风险",
            "signature": rb"system",
        },
        "popen": {
            "category": "命令执行",
            "risk": SeverityLevel.CRITICAL,
            "cwe": "CWE-78",
            "replacement": "CreateProcess / execve (参数化)",
            "description": "通过 shell 执行命令，存在命令注入风险",
            "signature": rb"popen",
        },
        "exec": {
            "category": "进程替换",
            "risk": SeverityLevel.CRITICAL,
            "cwe": "CWE-78",
            "replacement": "参数化进程创建",
            "description": "进程替换函数族，若参数可控则存在代码执行风险",
            "signature": rb"\bexec[vlp]{0,2}e?\b",
        },
        "WinExec": {
            "category": "命令执行",
            "risk": SeverityLevel.HIGH,
            "cwe": "CWE-78",
            "replacement": "CreateProcess",
            "description": "已废弃的 Win32 API，易被利用执行恶意命令",
            "signature": rb"WinExec",
        },
        "ShellExecute": {
            "category": "命令执行",
            "risk": SeverityLevel.MEDIUM,
            "cwe": "CWE-78",
            "replacement": "CreateProcess (参数化)",
            "description": "Shell 执行 API，若参数源于用户输入则有安全风险",
            "signature": rb"ShellExecute[AW]?\b",
        },
        # ---- 路径操作类 ----
        "sprintfW": {
            "category": "格式化输出 (宽字符)",
            "risk": SeverityLevel.HIGH,
            "cwe": "CWE-120",
            "replacement": "swprintf_s",
            "description": "宽字符版本 sprintf，无长度限制",
            "signature": rb"swprintf",
        },
        "RealPath": {
            "category": "路径解析",
            "risk": SeverityLevel.MEDIUM,
            "cwe": "CWE-22",
            "replacement": "realpath (带长度限制)",
            "description": "路径规范化函数，若缓冲区不足则可能溢出",
            "signature": rb"realpath",
        },
        "getwd": {
            "category": "路径获取",
            "risk": SeverityLevel.MEDIUM,
            "cwe": "CWE-120",
            "replacement": "getcwd (带长度限制)",
            "description": "获取当前工作目录，无缓冲区大小限制",
            "signature": rb"getwd",
        },
    }

    # 已废弃的 Win32 API 列表
    _DEPRECATED_WIN32_APIS: Dict[str, Dict[str, Any]] = {
        "lstrcpy": {
            "replacement": "StringCchCopy",
            "description": "已废弃的字符串复制 API",
        },
        "lstrcat": {
            "replacement": "StringCchCat",
            "description": "已废弃的字符串拼接 API",
        },
        "lstrcpyn": {
            "replacement": "StringCchCopyN",
            "description": "已废弃的定长字符串复制 API",
        },
        "lstrlen": {
            "replacement": "StringCchLength",
            "description": "已废弃的字符串长度 API",
        },
        "wsprintf": {
            "replacement": "StringCchPrintf",
            "description": "已废弃的格式化输出 API",
        },
        "wvsprintf": {
            "replacement": "StringCchVPrintf",
            "description": "已废弃的可变参数格式化输出 API",
        },
        "wnsprintf": {
            "replacement": "StringCchPrintf",
            "description": "已废弃的定长格式化输出 API",
        },
    }

    def __init__(self):
        """初始化不安全函数检测器"""
        self._function_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._compiled_patterns: Dict[str, re.Pattern] = {}

    def _compile_patterns(self) -> None:
        """预编译所有正则模式"""
        if self._compiled_patterns:
            return
        for func_name, info in self._UNSAFE_FUNCTIONS.items():
            try:
                self._compiled_patterns[func_name] = re.compile(
                    info["signature"], re.IGNORECASE
                )
            except re.error:
                pass

    def get_unsafe_function_list(self) -> Dict[str, Dict[str, Any]]:
        """获取完整的不安全函数列表及其详细信息

        Returns:
            Dict: 不安全函数名称到详细信息的映射
        """
        return dict(self._UNSAFE_FUNCTIONS)

    def detect_deprecated_apis(self) -> Dict[str, Dict[str, Any]]:
        """获取已废弃 Win32 API 列表

        Returns:
            Dict: 废弃 API 名称到详细信息的映射
        """
        return dict(self._DEPRECATED_WIN32_APIS)

    def scan_unsafe_functions(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """扫描二进制数据中的不安全函数调用

        对二进制文件进行扫描，检测 IAT（导入地址表）中的不安全函数引用，
        以及代码段中可能存在的直接调用。

        Args:
            data: 文件二进制数据
            text: 可选的文本内容（如汇编代码）

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        self._compile_patterns()
        vulns: List[Vulnerability] = []

        if data is None:
            return vulns

        # 在二进制数据中搜索不安全函数签名
        for func_name, pattern in self._compiled_patterns.items():
            matches = list(pattern.finditer(data))
            if matches:
                func_info = self._UNSAFE_FUNCTIONS[func_name]
                for match in matches:
                    offset = match.start()
                    vulns.append(Vulnerability(
                        vuln_type=VulnerabilityType.INSECURE_API
                        if func_info["risk"] != SeverityLevel.CRITICAL
                        else VulnerabilityType.BUFFER_OVERFLOW,
                        severity=func_info["risk"],
                        description=(
                            f"检测到不安全函数调用: {func_name} - "
                            f"{func_info['description']}"
                        ),
                        location=f"偏移 0x{offset:X}",
                        confidence=0.85,
                        exploit_difficulty=ExploitDifficulty.EASY,
                        cwe_id=func_info["cwe"],
                        fix_suggestion=(
                            f"将 {func_name} 替换为 {func_info['replacement']}，"
                            f"并确保进行适当的边界检查"
                        ),
                        affected_code=func_name,
                        extra_info={
                            "function_name": func_name,
                            "category": func_info["category"],
                            "offset": offset,
                        },
                    ))

        # 在汇编文本中搜索（如果提供）
        if text:
            for func_name, func_info in self._UNSAFE_FUNCTIONS.items():
                # 搜索 call 指令后的函数名
                call_pattern = re.compile(
                    rf"\bcall\s+.*{re.escape(func_name)}\b",
                    re.IGNORECASE,
                )
                matches = call_pattern.findall(text)
                if matches:
                    for _ in matches:
                        vulns.append(Vulnerability(
                            vuln_type=VulnerabilityType.INSECURE_API,
                            severity=func_info["risk"],
                            description=(
                                f"汇编代码中检测到不安全函数调用: {func_name}"
                            ),
                            location=f"汇编代码 - call {func_name}",
                            confidence=0.75,
                            exploit_difficulty=ExploitDifficulty.EASY,
                            cwe_id=func_info["cwe"],
                            fix_suggestion=(
                                f"将 {func_name} 替换为 {func_info['replacement']}"
                            ),
                            affected_code=f"call {func_name}",
                        ))

        # 检测已废弃的 Win32 API
        for api_name, api_info in self._DEPRECATED_WIN32_APIS.items():
            api_pattern = re.compile(rf"\b{api_name}\b".encode(), re.IGNORECASE)
            if api_pattern.search(data):
                vulns.append(Vulnerability(
                    vuln_type=VulnerabilityType.INSECURE_API,
                    severity=SeverityLevel.MEDIUM,
                    description=(
                        f"检测到已废弃的 Win32 API: {api_name} - "
                        f"{api_info['description']}"
                    ),
                    location=f"导入表 - {api_name}",
                    confidence=0.90,
                    exploit_difficulty=ExploitDifficulty.EASY,
                    cwe_id="CWE-676",
                    fix_suggestion=(
                        f"将 {api_name} 替换为 {api_info['replacement']}"
                    ),
                    affected_code=api_name,
                ))

        return vulns

    def detect_missing_size_check(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测缺失边界检查的模式

        分析函数调用前后是否缺少必要的边界验证（如 cmp/test 指令），
        判断是否存在未经验证的长度参数直接传递给内存操作函数。

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        # 在二进制码中搜索直接传递大小参数的模式
        # 常见模式: push large_value; call memcpy/strcpy (前面无 cmp 检查)
        memory_funcs = [b"memcpy", b"memmove", b"strcpy", b"strncpy", b"memset"]

        for func in memory_funcs:
            # 查找函数调用附近的模式
            func_matches = list(re.finditer(re.escape(func), data, re.IGNORECASE))
            for fm in func_matches:
                offset = fm.start()
                # 检查前 64 字节内是否有 cmp/test 指令
                preceding = data[max(0, offset - 64):offset]
                if re.search(rb"\x3b|\x39|\x85|\xf6|\xf7", preceding):
                    continue  # 存在比较指令，可能做了边界检查

                vulns.append(Vulnerability(
                    vuln_type=VulnerabilityType.BUFFER_OVERFLOW,
                    severity=SeverityLevel.HIGH,
                    description=(
                        f"调用 {func.decode('ascii', errors='replace')} 前 "
                        f"可能缺少边界检查"
                    ),
                    location=f"偏移 0x{offset:X}",
                    confidence=0.45,
                    exploit_difficulty=ExploitDifficulty.MODERATE,
                    cwe_id="CWE-120",
                    fix_suggestion="在调用内存操作函数前添加目标缓冲区大小验证",
                    extra_info={
                        "function": func.decode("ascii", errors="replace"),
                        "nearby_offset": offset,
                    },
                ))

        return vulns

    def analyze_function_usage(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """综合分析不安全函数的使用情况

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            Dict[str, Any]: 分析结果，包含各类统计信息
        """
        self._compile_patterns()

        result: Dict[str, Any] = {
            "total_unsafe_calls": 0,
            "by_category": defaultdict(int),
            "by_severity": defaultdict(int),
            "critical_functions": [],
            "high_risk_functions": [],
            "functions_found": {},
            "deprecated_api_count": 0,
        }

        if data is None:
            return result

        for func_name, pattern in self._compiled_patterns.items():
            matches = list(pattern.finditer(data))
            if matches:
                func_info = self._UNSAFE_FUNCTIONS[func_name]
                count = len(matches)
                result["total_unsafe_calls"] += count
                result["functions_found"][func_name] = {
                    "count": count,
                    "category": func_info["category"],
                    "severity": func_info["risk"].name,
                    "cwe": func_info["cwe"],
                    "offsets": [m.start() for m in matches[:10]],  # 最多记录10个偏移
                }
                result["by_category"][func_info["category"]] += count
                result["by_severity"][func_info["risk"].name] += count

                if func_info["risk"] == SeverityLevel.CRITICAL:
                    result["critical_functions"].append(func_name)
                elif func_info["risk"] == SeverityLevel.HIGH:
                    result["high_risk_functions"].append(func_name)

        # 检测废弃 API
        for api_name in self._DEPRECATED_WIN32_APIS:
            api_pattern = re.compile(rf"\b{api_name}\b".encode(), re.IGNORECASE)
            if api_pattern.search(data):
                result["deprecated_api_count"] += 1

        # 转换 defaultdict 为普通 dict 以便序列化
        result["by_category"] = dict(result["by_category"])
        result["by_severity"] = dict(result["by_severity"])

        return result


# ============================================================================
# 缓冲区溢出分析器 (BufferOverflowAnalyzer)
# ============================================================================

class BufferOverflowAnalyzer:
    """缓冲区溢出漏洞分析器

    检测栈缓冲区溢出、堆缓冲区溢出、off-by-one 错误、
    格式字符串漏洞和 sprintf 溢出等常见内存破坏漏洞。
    """

    # 栈缓冲区溢出模式
    _STACK_BUFFER_PATTERNS = [
        # 固定大小局部数组 + 变量长度复制
        re.compile(
            rb"sub\s+esp,\s*(0x[\da-fA-F]+)", re.IGNORECASE
        ),
        # 栈帧分配模式
        re.compile(
            rb"push\s+ebp.*mov\s+ebp,\s*esp.*sub\s+esp,\s*(0x[\da-fA-F]+)",
            re.IGNORECASE | re.DOTALL,
        ),
    ]

    # 格式字符串漏洞模式
    _FORMAT_STRING_PATTERNS = [
        # printf(user_input) 无格式字符串
        re.compile(
            rb"push\s+(?:eax|ebx|ecx|edx|esi|edi|\[.*\])\s*\n?\s*call\s+.*printf",
            re.IGNORECASE,
        ),
        # fprintf(stderr, user_input) 等
        re.compile(
            rb"push\s+(?:eax|ebx|ecx|edx|esi|edi)\s*\n?\s*push\s+\w+\s*\n?\s*call\s+.*fprintf",
            re.IGNORECASE,
        ),
    ]

    # 堆溢出模式
    _HEAP_OVERFLOW_PATTERNS = [
        # malloc(small) + memcpy(large)
        re.compile(
            rb"call\s+.*malloc.*\n.*call\s+.*memcpy",
            re.IGNORECASE | re.DOTALL,
        ),
        # HeapAlloc + memcpy
        re.compile(
            rb"call\s+.*HeapAlloc.*\n.*call\s+.*memcpy",
            re.IGNORECASE | re.DOTALL,
        ),
    ]

    def __init__(self):
        """初始化缓冲区溢出分析器"""
        self._stack_size_limit = 256  # 栈帧大小阈值
        self._buffer_size_threshold = 512  # 缓冲区大小阈值

    def detect_stack_buffer_overflow(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测栈缓冲区溢出

        分析栈帧分配大小与后续复制操作之间的不匹配，
        识别固定大小缓冲区与变量长度拷贝的组合。

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if data is None:
            return vulns

        # 检测固定大小栈缓冲区 + 变量长度复制
        # 特征: sub esp, 0x40 (64字节缓冲区) 后跟 memcpy(dest, src, 0x100)
        stack_alloc = re.compile(
            rb"sub\s+esp,\s*(0x[\da-fA-F]+)",
            re.IGNORECASE,
        )
        stack_allocs = list(stack_alloc.finditer(data))

        copy_funcs = re.compile(
            rb"call\s+.*(?:memcpy|strcpy|strcat|strncpy|memmove|memcpy_s)",
            re.IGNORECASE,
        )
        copy_calls = list(copy_funcs.finditer(data))

        for alloc_match in stack_allocs:
            if alloc_match.group(1):
                stack_size = int(alloc_match.group(1), 16)
                alloc_offset = alloc_match.start()

                # 查找同一函数内的 copy 调用
                for copy_match in copy_calls:
                    copy_offset = copy_match.start()
                    if copy_offset > alloc_offset and copy_offset - alloc_offset < 512:
                        # 检查栈大小是否足够小（可能被溢出）
                        if stack_size < self._stack_size_limit:
                            vulns.append(Vulnerability(
                                vuln_type=VulnerabilityType.STACK_OVERFLOW,
                                severity=SeverityLevel.HIGH,
                                description=(
                                    f"栈缓冲区仅分配 {stack_size} 字节，"
                                    f"后续内存复制操作可能溢出"
                                ),
                                location=f"偏移 0x{alloc_offset:X}",
                                confidence=0.50,
                                exploit_difficulty=ExploitDifficulty.MODERATE,
                                cwe_id="CWE-121",
                                fix_suggestion=(
                                    "增加栈缓冲区大小至合理范围，"
                                    "或使用带长度限制的安全函数"
                                ),
                                extra_info={
                                    "stack_size": stack_size,
                                    "alloc_offset": alloc_offset,
                                    "copy_offset": copy_offset,
                                },
                            ))

        # 在汇编文本中检测
        if text:
            # 检测 sub esp, small_value 后跟 memcpy/strcpy
            asm_stack_pattern = re.compile(
                r"sub\s+esp,\s*(0x[0-9a-fA-F]+).*?(?:call.*?(?:memcpy|strcpy|strcat))",
                re.IGNORECASE | re.DOTALL,
            )
            for match in asm_stack_pattern.finditer(text):
                try:
                    stack_size = int(match.group(1), 16)
                    if stack_size < self._stack_size_limit:
                        vulns.append(Vulnerability(
                            vuln_type=VulnerabilityType.STACK_OVERFLOW,
                            severity=SeverityLevel.HIGH,
                            description=(
                                f"栈帧分配 {stack_size} 字节后存在内存复制操作"
                            ),
                            location=f"汇编代码 - sub esp, 0x{stack_size:X}",
                            confidence=0.55,
                            exploit_difficulty=ExploitDifficulty.MODERATE,
                            cwe_id="CWE-121",
                            fix_suggestion=(
                                "增加栈缓冲区大小或使用安全的复制函数"
                            ),
                            affected_code=match.group(0)[:120],
                        ))
                except (ValueError, IndexError):
                    continue

        return vulns

    def detect_heap_buffer_overflow(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测堆缓冲区溢出

        分析堆分配大小与后续操作之间的不匹配，
        识别 malloc(size) 后 memcpy 超过 size 字节的模式。

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if data is None:
            return vulns

        # 搜索 malloc/HeapAlloc 调用及其大小参数
        alloc_patterns = [
            re.compile(rb"push\s+(0x[\da-fA-F]+)\s*\n?\s*call\s+.*malloc", re.IGNORECASE),
            re.compile(rb"push\s+(0x[\da-fA-F]+)\s*\n?\s*call\s+.*HeapAlloc", re.IGNORECASE),
            re.compile(rb"push\s+(0x[\da-fA-F]+)\s*\n?\s*call\s+.*operator new", re.IGNORECASE),
        ]

        for alloc_pattern in alloc_patterns:
            for match in alloc_pattern.finditer(data):
                if match.group(1):
                    alloc_size = int(match.group(1), 16)
                    alloc_offset = match.start()

                    # 查找附近的 memcpy 调用
                    nearby = data[alloc_offset:alloc_offset + 512]
                    copy_pattern = re.compile(
                        rb"push\s+(0x[\da-fA-F]+)\s*\n?\s*call\s+.*memcpy",
                        re.IGNORECASE,
                    )
                    copy_matches = list(copy_pattern.finditer(nearby))

                    for cm in copy_matches:
                        if cm.group(1):
                            copy_size = int(cm.group(1), 16)
                            if copy_size > alloc_size:
                                vulns.append(Vulnerability(
                                    vuln_type=VulnerabilityType.HEAP_OVERFLOW,
                                    severity=SeverityLevel.HIGH,
                                    description=(
                                        f"堆分配 {alloc_size} 字节，"
                                        f"但复制操作大小为 {copy_size} 字节"
                                    ),
                                    location=f"偏移 0x{alloc_offset:X}",
                                    confidence=0.60,
                                    exploit_difficulty=ExploitDifficulty.MODERATE,
                                    cwe_id="CWE-122",
                                    fix_suggestion=(
                                        "确保复制大小不超过分配的缓冲区大小"
                                    ),
                                    extra_info={
                                        "alloc_size": alloc_size,
                                        "copy_size": copy_size,
                                    },
                                ))

        return vulns

    def detect_off_by_one(self, data: bytes, text: Optional[str] = None) -> List[Vulnerability]:
        """检测 off-by-one 错误

        检测以下几种常见 off-by-one 模式:
        - 循环条件使用 <= 而非 <
        - 数组索引超出范围 1
        - strlen 返回值直接用作 memcpy 大小（未 +1 计入 null 终止符）

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if text is None:
            return vulns

        # 检测 strlen 后直接用于 memcpy（未 +1 处理 null 终止符）
        strlen_memcpy = re.compile(
            r"call.*strlen.*\n.*push\s+eax.*\n.*call.*memcpy",
            re.IGNORECASE | re.DOTALL,
        )
        for match in strlen_memcpy.finditer(text):
            vulns.append(Vulnerability(
                vuln_type=VulnerabilityType.BUFFER_OVERFLOW,
                severity=SeverityLevel.MEDIUM,
                description=(
                    "strlen 返回值直接用作 memcpy 大小，"
                    "未计入 null 终止符 (off-by-one)"
                ),
                location=f"汇编代码 - strlen/memcpy 序列",
                confidence=0.55,
                exploit_difficulty=ExploitDifficulty.MODERATE,
                cwe_id="CWE-193",
                fix_suggestion=(
                    "memcpy 大小应为 strlen(src) + 1 以包含 null 终止符"
                ),
                affected_code=match.group(0)[:120],
            ))

        # 检测循环中 <= 比较（可能的 off-by-one）
        # 在汇编中: jle (jump if less or equal) 而非 jl (jump if less)
        le_loop_pattern = re.compile(
            r"\bjle\b\s+0x[\da-fA-F]+\s*\n.*\binc\b",
            re.IGNORECASE | re.DOTALL,
        )
        for match in le_loop_pattern.finditer(text):
            vulns.append(Vulnerability(
                vuln_type=VulnerabilityType.BUFFER_OVERFLOW,
                severity=SeverityLevel.LOW,
                description="循环条件使用 <= 可能导致 off-by-one 错误",
                location=f"汇编代码 - jle 指令",
                confidence=0.30,
                exploit_difficulty=ExploitDifficulty.HARD,
                cwe_id="CWE-193",
                fix_suggestion="检查循环边界条件，确保索引不超出数组范围",
                affected_code=match.group(0)[:80],
            ))

        return vulns

    def analyze_copy_size(self, data: bytes, text: Optional[str] = None) -> Dict[str, Any]:
        """分析复制操作与缓冲区大小之间的关系

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            Dict[str, Any]: 分析结果
        """
        result: Dict[str, Any] = {
            "total_copy_operations": 0,
            "potentially_unsafe": 0,
            "copy_details": [],
        }

        if data is None:
            return result

        # 统计所有复制操作
        copy_funcs = [
            b"memcpy", b"memmove", b"strcpy", b"strncpy",
            b"strcat", b"strncat", b"CopyMemory", b"MoveMemory",
        ]
        for func in copy_funcs:
            pattern = re.compile(re.escape(func), re.IGNORECASE)
            matches = list(pattern.finditer(data))
            for m in matches:
                result["total_copy_operations"] += 1
                result["copy_details"].append({
                    "function": func.decode("ascii", errors="replace"),
                    "offset": m.start(),
                })

        return result

    def detect_format_string_vuln(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测格式字符串漏洞

        检测 printf/fprintf/sprintf 等函数是否将用户可控的输入
        直接作为格式字符串参数传递。

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if data is None:
            return vulns

        # 在二进制中检测: 直接 push 寄存器/变量 到 printf，无格式字符串
        fmt_funcs = [b"printf", b"fprintf", b"sprintf", b"snprintf",
                     b"wprintf", b"fwprintf", b"swprintf", b"vprintf"]

        for func in fmt_funcs:
            # 查找函数调用
            func_matches = list(re.finditer(re.escape(func), data, re.IGNORECASE))
            for fm in func_matches:
                offset = fm.start()
                # 检查调用前 32 字节，看 push 的是否是格式字符串
                preceding = data[max(0, offset - 32):offset]
                # 如果没有 push 立即数/字符串引用（可能是变量），则为格式字符串漏洞
                if not re.search(rb"push\s+(?:0x[\da-fA-F]+|offset\s)", preceding):
                    vulns.append(Vulnerability(
                        vuln_type=VulnerabilityType.FORMAT_STRING,
                        severity=SeverityLevel.HIGH,
                        description=(
                            f"调用 {func.decode('ascii', errors='replace')} 时 "
                            f"格式字符串参数可能来自用户输入"
                        ),
                        location=f"偏移 0x{offset:X}",
                        confidence=0.50,
                        exploit_difficulty=ExploitDifficulty.EASY,
                        cwe_id="CWE-134",
                        fix_suggestion=(
                            f"始终使用固定格式字符串，如 {func.decode('ascii', errors='replace')}"
                            f"(\"%s\", user_input)"
                        ),
                        extra_info={
                            "function": func.decode("ascii", errors="replace"),
                        },
                    ))

        # 在汇编文本中检测
        if text:
            # 模式: push eax/ebx/ecx/edx; call printf  (无格式字符串)
            asm_fmt_pattern = re.compile(
                r"push\s+(?:eax|ebx|ecx|edx|esi|edi|\[ebp[^\]]*\])"
                r"\s*\n?\s*call\s+.*printf",
                re.IGNORECASE,
            )
            for match in asm_fmt_pattern.finditer(text):
                vulns.append(Vulnerability(
                    vuln_type=VulnerabilityType.FORMAT_STRING,
                    severity=SeverityLevel.HIGH,
                    description="格式字符串参数可能来自用户可控输入",
                    location=f"汇编代码 - printf 调用",
                    confidence=0.55,
                    exploit_difficulty=ExploitDifficulty.EASY,
                    cwe_id="CWE-134",
                    fix_suggestion="使用 printf(\"%s\", user_input) 替代 printf(user_input)",
                    affected_code=match.group(0)[:100],
                ))

        return vulns

    def detect_sprintf_overflow(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测 sprintf 溢出

        检测 sprintf 调用中目标缓冲区大小是否足够容纳格式化输出。

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if data is None:
            return vulns

        # 搜索 sprintf 调用
        sprintf_pattern = re.compile(rb"sprintf", re.IGNORECASE)
        matches = list(sprintf_pattern.finditer(data))

        for match in matches:
            offset = match.start()
            vulns.append(Vulnerability(
                vuln_type=VulnerabilityType.BUFFER_OVERFLOW,
                severity=SeverityLevel.HIGH,
                description=(
                    "sprintf 无输出长度限制，可能造成缓冲区溢出"
                ),
                location=f"偏移 0x{offset:X}",
                confidence=0.70,
                exploit_difficulty=ExploitDifficulty.EASY,
                cwe_id="CWE-120",
                fix_suggestion=(
                    "使用 snprintf 或 sprintf_s 替代 sprintf，"
                    "并指定最大输出长度"
                ),
                extra_info={"function": "sprintf"},
            ))

        return vulns


# ============================================================================
# 整数溢出分析器 (IntegerOverflowAnalyzer)
# ============================================================================

class IntegerOverflowAnalyzer:
    """整数溢出漏洞分析器

    检测整数运算中的溢出、符号混淆、截断和负值分配等模式。
    这些漏洞可能导致缓冲区分配不足，进而引发内存破坏。
    """

    def __init__(self):
        """初始化整数溢出分析器"""
        self._max_int32 = 0x7FFFFFFF
        self._max_uint32 = 0xFFFFFFFF

    def detect_integer_overflow(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测整数溢出

        检测加法、乘法操作后缺少溢出检查的模式。

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if text is None:
            return vulns

        # 检测 add 后未检查进位的模式
        add_no_check = re.compile(
            r"\badd\s+\w+,\s*\w+\s*\n(?!\s*\bj[oc]\b)",
            re.IGNORECASE | re.DOTALL,
        )
        for match in add_no_check.finditer(text):
            vulns.append(Vulnerability(
                vuln_type=VulnerabilityType.INTEGER_OVERFLOW,
                severity=SeverityLevel.MEDIUM,
                description="加法操作后未检查溢出标志",
                location=f"汇编代码 - add 指令",
                confidence=0.25,
                exploit_difficulty=ExploitDifficulty.HARD,
                cwe_id="CWE-190",
                fix_suggestion="在加法操作后检查进位标志 (CF) 或使用安全整数运算库",
                affected_code=match.group(0)[:60],
            ))

        # 检测 mul/imul 后未检查溢出
        mul_no_check = re.compile(
            r"\b(?:mul|imul)\s+\w+\s*\n(?!\s*\bj[oc]\b)",
            re.IGNORECASE | re.DOTALL,
        )
        for match in mul_no_check.finditer(text):
            vulns.append(Vulnerability(
                vuln_type=VulnerabilityType.INTEGER_OVERFLOW,
                severity=SeverityLevel.MEDIUM,
                description="乘法操作后未检查溢出标志",
                location=f"汇编代码 - mul/imul 指令",
                confidence=0.30,
                exploit_difficulty=ExploitDifficulty.HARD,
                cwe_id="CWE-190",
                fix_suggestion="在乘法操作后检查溢出标志 (OF) 或使用安全整数运算库",
                affected_code=match.group(0)[:60],
            ))

        return vulns

    def detect_signed_unsigned_mismatch(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测有符号/无符号整数混淆

        检测比较操作中符号处理不一致的模式，如:
        - 有符号值与无符号值比较
        - 负数传递给期望无符号参数的函数

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if text is None:
            return vulns

        # 检测 jg/jl（有符号比较）与 ja/jb（无符号比较）混用
        signed_unsigned_mix = re.compile(
            r"\bj(?:g|l|ge|le)\b.*\n.*\bj(?:a|b|ae|be)\b",
            re.IGNORECASE | re.DOTALL,
        )
        for match in signed_unsigned_mix.finditer(text):
            vulns.append(Vulnerability(
                vuln_type=VulnerabilityType.INTEGER_OVERFLOW,
                severity=SeverityLevel.LOW,
                description="有符号和无符号比较指令混用，可能导致符号混淆",
                location=f"汇编代码 - 混合比较跳转",
                confidence=0.25,
                exploit_difficulty=ExploitDifficulty.HARD,
                cwe_id="CWE-195",
                fix_suggestion="统一使用有符号或无符号比较，确保语义一致",
                affected_code=match.group(0)[:80],
            ))

        return vulns

    def detect_size_multiplication_overflow(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测乘法溢出导致缓冲区分配不足

        检测模式: malloc(width * height * sizeof(element))
        如果 width * height 溢出，将分配过小的缓冲区。

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if text is None:
            return vulns

        # 检测 mul/imul 后跟 malloc/calloc/HeapAlloc
        mul_alloc_pattern = re.compile(
            r"\b(?:mul|imul)\s+\w+\s*\n.*\b(?:call.*(?:malloc|calloc|HeapAlloc|new))\b",
            re.IGNORECASE | re.DOTALL,
        )
        for match in mul_alloc_pattern.finditer(text):
            vulns.append(Vulnerability(
                vuln_type=VulnerabilityType.INTEGER_OVERFLOW,
                severity=SeverityLevel.HIGH,
                description=(
                    "乘法结果直接用作内存分配大小，"
                    "若乘法溢出将导致缓冲区分配不足"
                ),
                location=f"汇编代码 - mul + malloc 序列",
                confidence=0.40,
                exploit_difficulty=ExploitDifficulty.MODERATE,
                cwe_id="CWE-190",
                fix_suggestion=(
                    "在乘法前检查操作数是否会导致溢出，"
                    "例如: if (width > SIZE_MAX / height) return error;"
                ),
                affected_code=match.group(0)[:120],
            ))

        return vulns

    def detect_truncation(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测数值截断

        检测将较大类型转换为较小类型时的截断，如:
        - int64 -> int32
        - int -> short
        - size_t -> int

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if text is None:
            return vulns

        # 检测 32位寄存器 -> 16位寄存器（截断）
        trunc_pattern = re.compile(
            r"\bmov(?:sx|zx)?\s+(?:ax|bx|cx|dx|si|di),\s*(?:eax|ebx|ecx|edx|esi|edi)",
            re.IGNORECASE,
        )
        for match in trunc_pattern.finditer(text):
            vulns.append(Vulnerability(
                vuln_type=VulnerabilityType.INTEGER_OVERFLOW,
                severity=SeverityLevel.LOW,
                description="检测到 32位到16位 的数值截断",
                location=f"汇编代码 - mov 截断",
                confidence=0.20,
                exploit_difficulty=ExploitDifficulty.HARD,
                cwe_id="CWE-197",
                fix_suggestion="检查源值是否在目标类型的表示范围内",
                affected_code=match.group(0)[:60],
            ))

        return vulns

    def detect_negative_allocation(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测负值分配的可能

        检测当有符号整数为负数时传递给 malloc 等分配函数的情况。
        负值被解释为无符号大整数时，malloc 可能返回 NULL 或分配异常。

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if text is None:
            return vulns

        # 检测 jl/jle（检查负数）后跟 malloc 的缺失
        # 即: 有符号值直接传给 malloc，未检查是否为负数
        neg_alloc_pattern = re.compile(
            r"\b(?:mov|push)\s+(?:eax|ebx|ecx|edx|esi|edi)\s*\n.*"
            r"\bcall\s+.*(?:malloc|calloc|HeapAlloc|new)\b",
            re.IGNORECASE | re.DOTALL,
        )
        for match in neg_alloc_pattern.finditer(text):
            # 检查前面是否有 jl/jle 检查负数
            chunk = match.group(0)
            if not re.search(r"\bj(?:l|le)\b", chunk[:200]):
                vulns.append(Vulnerability(
                    vuln_type=VulnerabilityType.INTEGER_OVERFLOW,
                    severity=SeverityLevel.MEDIUM,
                    description="可能将负值传递给内存分配函数，未检查符号",
                    location=f"汇编代码 - malloc 调用",
                    confidence=0.25,
                    exploit_difficulty=ExploitDifficulty.HARD,
                    cwe_id="CWE-190",
                    fix_suggestion="在分配前检查大小是否为正数",
                    affected_code=match.group(0)[:80],
                ))

        return vulns


# ============================================================================
# 内存安全分析器 (MemorySafetyAnalyzer)
# ============================================================================

class MemorySafetyAnalyzer:
    """内存安全分析器

    检测使用已释放内存 (UAF)、双重释放、空指针解引用、
    未初始化内存使用和类型混淆等内存安全问题。
    """

    def __init__(self):
        """初始化内存安全分析器"""
        self._free_funcs = [b"free", b"delete", b"HeapFree", b"VirtualFree"]
        self._alloc_funcs = [b"malloc", b"calloc", b"realloc", b"new",
                            b"HeapAlloc", b"VirtualAlloc"]

    def detect_use_after_free(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测释放后使用 (Use-After-Free)

        检测以下模式:
        - free 后对同一指针的访问
        - 释放后传递给其他函数使用

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if text is None:
            return vulns

        # 检测 free(ptr) 后 ptr 仍被使用
        free_pattern = re.compile(
            r"call\s+.*(?:free|delete|HeapFree).*\n"
            r"(?:.*\n){0,5}"
            r".*\[(?:eax|ebx|ecx|edx|esi|edi|ebp)\]",
            re.IGNORECASE | re.DOTALL,
        )
        for match in free_pattern.finditer(text):
            vulns.append(Vulnerability(
                vuln_type=VulnerabilityType.USE_AFTER_FREE,
                severity=SeverityLevel.CRITICAL,
                description="释放内存后同一指针可能被再次使用 (UAF)",
                location=f"汇编代码 - free 后访问",
                confidence=0.45,
                exploit_difficulty=ExploitDifficulty.MODERATE,
                cwe_id="CWE-416",
                fix_suggestion=(
                    "释放后将指针置为 NULL，"
                    "并在使用前检查指针有效性"
                ),
                affected_code=match.group(0)[:120],
            ))

        return vulns

    def detect_double_free(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测双重释放 (Double-Free)

        检测同一指针被多次释放的模式。

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if text is None:
            return vulns

        # 检测两个连续的 free 调用，传入了相同的指针
        double_free_pattern = re.compile(
            r"push\s+(eax|ebx|ecx|edx|esi|edi)\s*\n"
            r"\s*call\s+.*(?:free|delete|HeapFree)\s*\n"
            r"(?:.*\n){0,3}"
            r"\s*push\s+\1\s*\n"
            r"\s*call\s+.*(?:free|delete|HeapFree)",
            re.IGNORECASE | re.DOTALL,
        )
        for match in double_free_pattern.finditer(text):
            vulns.append(Vulnerability(
                vuln_type=VulnerabilityType.DOUBLE_FREE,
                severity=SeverityLevel.CRITICAL,
                description="同一指针可能被多次释放 (Double-Free)",
                location=f"汇编代码 - 双重释放",
                confidence=0.50,
                exploit_difficulty=ExploitDifficulty.MODERATE,
                cwe_id="CWE-415",
                fix_suggestion=(
                    "释放后将指针置为 NULL，"
                    "或使用引用计数/智能指针管理生命周期"
                ),
                affected_code=match.group(0)[:120],
            ))

        return vulns

    def detect_null_pointer_deref(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测空指针解引用

        检测以下模式:
        - 函数返回指针后未检查 NULL 即使用
        - malloc 返回 NULL 后未检查即使用

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if text is None:
            return vulns

        # 检测 malloc 后未检查 eax 是否为 0 即使用
        null_deref_pattern = re.compile(
            r"call\s+.*(?:malloc|calloc|realloc|HeapAlloc|new)\s*\n"
            r"(?!.*\btest\s+eax,\s*eax\b)"
            r"(?:.*\n){0,3}"
            r".*\[eax\]",
            re.IGNORECASE | re.DOTALL,
        )
        for match in null_deref_pattern.finditer(text):
            vulns.append(Vulnerability(
                vuln_type=VulnerabilityType.NULL_POINTER_DEREF,
                severity=SeverityLevel.HIGH,
                description="malloc 返回后未检查 NULL 即进行解引用",
                location=f"汇编代码 - malloc 后解引用",
                confidence=0.55,
                exploit_difficulty=ExploitDifficulty.EASY,
                cwe_id="CWE-476",
                fix_suggestion="在解引用前检查指针是否为 NULL",
                affected_code=match.group(0)[:120],
            ))

        return vulns

    def detect_uninitialized_memory(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测未初始化内存使用

        检测以下模式:
        - 栈变量未初始化即使用
        - malloc (非 calloc) 分配的内存未初始化即读取

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if text is None:
            return vulns

        # 检测 malloc 后直接读取（未初始化）
        malloc_read_pattern = re.compile(
            r"call\s+.*malloc\s*\n"
            r"(?:.*\n){0,3}"
            r".*\bmov\s+\w+,\s*\[eax\]",
            re.IGNORECASE | re.DOTALL,
        )
        for match in malloc_read_pattern.finditer(text):
            vulns.append(Vulnerability(
                vuln_type=VulnerabilityType.UNINITIALIZED_MEMORY,
                severity=SeverityLevel.MEDIUM,
                description="malloc 分配的内存未初始化即被读取",
                location=f"汇编代码 - malloc 后读取",
                confidence=0.40,
                exploit_difficulty=ExploitDifficulty.MODERATE,
                cwe_id="CWE-457",
                fix_suggestion=(
                    "使用 calloc 替代 malloc 进行零初始化，"
                    "或在分配后立即使用 memset 初始化"
                ),
                affected_code=match.group(0)[:100],
            ))

        return vulns

    def detect_type_confusion(
        self,
        data: bytes,
        text: Optional[str] = None,
    ) -> List[Vulnerability]:
        """检测类型混淆

        检测以下模式:
        - C 风格强制转换可能导致类型混淆
        - reinterpret_cast 的使用
        - 不安全的 union 使用

        Args:
            data: 文件二进制数据
            text: 可选的汇编文本

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if text is None:
            return vulns

        # 检测 C++ 的 reinterpret_cast 模式
        type_confuse_pattern = re.compile(
            r"\breinterpret_cast\b",
            re.IGNORECASE,
        )
        for match in type_confuse_pattern.finditer(text):
            vulns.append(Vulnerability(
                vuln_type=VulnerabilityType.TYPE_CONFUSION,
                severity=SeverityLevel.MEDIUM,
                description="使用 reinterpret_cast 可能导致类型混淆",
                location=f"代码 - reinterpret_cast",
                confidence=0.35,
                exploit_difficulty=ExploitDifficulty.HARD,
                cwe_id="CWE-843",
                fix_suggestion=(
                    "避免使用 reinterpret_cast，"
                    "使用 static_cast 或 dynamic_cast 进行类型安全的转换"
                ),
                affected_code=match.group(0)[:80],
            ))

        return vulns


# ============================================================================
# 二进制保护分析器 (BinaryProtectionAnalyzer)
# ============================================================================

class BinaryProtectionAnalyzer:
    """二进制保护机制分析器

    检查 PE/ELF 文件中的安全保护机制:
    - GS (/GS stack cookie) - 栈金丝雀
    - DEP (NX) - 数据执行保护
    - ASLR - 地址空间布局随机化
    - SafeSEH - 安全异常处理
    - CFG - 控制流保护
    - 高熵 ASLR (64位)
    """

    # PE 文件 DLL 特征表
    _PE_DLL_CHARACTERISTICS = {
        "DYNAMIC_BASE": 0x0040,      # ASLR 启用
        "NX_COMPAT": 0x0100,          # DEP 兼容
        "NO_SEH": 0x0400,             # 无 SEH
        "GUARD_CF": 0x4000,           # CFG 启用
        "HIGH_ENTROPY_VA": 0x0020,    # 高熵 ASLR (64位)
    }

    def __init__(self):
        """初始化二进制保护分析器"""
        self._section_header_size = 40  # PE 节表头大小

    def _parse_pe_header(self, data: bytes) -> Optional[Dict[str, Any]]:
        """解析 PE 头部信息

        Args:
            data: 文件二进制数据

        Returns:
            Optional[Dict]: PE 头部信息，或 None（非 PE 文件）
        """
        if len(data) < 64 or data[:2] != b"MZ":
            return None

        try:
            # 获取 PE 签名偏移
            pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
            if pe_offset + 4 > len(data):
                return None
            if data[pe_offset:pe_offset + 4] != b"PE\0\0":
                return None

            # COFF 头部
            coff_offset = pe_offset + 4
            machine = struct.unpack_from("<H", data, coff_offset)[0]
            num_sections = struct.unpack_from("<H", data, coff_offset + 2)[0]
            size_of_optional_header = struct.unpack_from("<H", data, coff_offset + 16)[0]

            # Optional Header
            opt_offset = coff_offset + 20
            if opt_offset + 68 > len(data):
                return None

            magic = struct.unpack_from("<H", data, opt_offset)[0]
            is_64bit = (magic == 0x20B)

            # DLL Characteristics
            if is_64bit:
                dll_char_offset = opt_offset + 70
            else:
                dll_char_offset = opt_offset + 70

            dll_characteristics = struct.unpack_from("<H", data, dll_char_offset)[0]

            # ImageBase
            if is_64bit:
                image_base = struct.unpack_from("<Q", data, opt_offset + 24)[0]
            else:
                image_base = struct.unpack_from("<I", data, opt_offset + 28)[0]

            return {
                "is_pe": True,
                "is_64bit": is_64bit,
                "machine": machine,
                "num_sections": num_sections,
                "dll_characteristics": dll_characteristics,
                "image_base": image_base,
                "pe_offset": pe_offset,
            }
        except (struct.error, IndexError):
            return None

    def _parse_elf_header(self, data: bytes) -> Optional[Dict[str, Any]]:
        """解析 ELF 头部信息

        Args:
            data: 文件二进制数据

        Returns:
            Optional[Dict]: ELF 头部信息，或 None（非 ELF 文件）
        """
        if len(data) < 64 or data[:4] != b"\x7fELF":
            return None

        try:
            is_64bit = data[4] == 2  # ELFCLASS64
            is_big_endian = data[5] == 2

            if is_64bit:
                if is_big_endian:
                    fmt = ">HHIQQQIHHHHHH"
                else:
                    fmt = "<HHIQQQIHHHHHH"
                header_size = 64
            else:
                if is_big_endian:
                    fmt = ">HHIIIIIHHHHHH"
                else:
                    fmt = "<HHIIIIIHHHHHH"
                header_size = 52

            if len(data) < header_size:
                return None

            fields = struct.unpack_from(fmt, data, 16)
            e_type = fields[0] if is_64bit else fields[0]
            e_machine = fields[1] if is_64bit else fields[1]
            e_entry = fields[3] if is_64bit else fields[3]
            e_phoff = fields[4] if is_64bit else fields[4]
            e_shoff = fields[5] if is_64bit else fields[5]
            e_phentsize = fields[8] if is_64bit else fields[8]
            e_phnum = fields[9] if is_64bit else fields[9]

            # 检查 GNU_STACK 段 (标志 RW 而非 RWE，即 NX 启用)
            has_nx = True   # 默认启用
            has_pie = False  # 默认未启用

            # 解析程序头表
            for i in range(e_phnum):
                ph_offset = e_phoff + i * e_phentsize
                if ph_offset + e_phentsize > len(data):
                    break
                if is_64bit:
                    p_type = struct.unpack_from("<I", data, ph_offset)[0]
                    p_flags = struct.unpack_from("<I", data, ph_offset + 4)[0]
                else:
                    p_type = struct.unpack_from("<I", data, ph_offset)[0]
                    p_flags = struct.unpack_from("<I", data, ph_offset + 24)[0]

                if p_type == 0x6474E551:  # PT_GNU_STACK
                    has_nx = not (p_flags & 0x1)  # 无可执行权限

                if p_type == 3:  # PT_INTERP (动态链接器存在，PIE 可能)
                    has_pie = True

            return {
                "is_elf": True,
                "is_64bit": is_64bit,
                "machine": e_machine,
                "entry_point": e_entry,
                "has_nx": has_nx,
                "has_pie": has_pie,
            }
        except (struct.error, IndexError):
            return None

    def check_stack_cookie(self, data: bytes) -> Dict[str, Any]:
        """检查栈金丝雀 (/GS) 保护

        PE: 检查是否导入 __security_cookie / __security_check_cookie
        ELF: 检查是否有 __stack_chk_fail 引用

        Args:
            data: 文件二进制数据

        Returns:
            Dict[str, Any]: 检查结果
        """
        result = {
            "enabled": False,
            "details": "未检测到栈金丝雀保护",
            "risk": SeverityLevel.MEDIUM,
        }

        if data is None:
            return result

        # PE 文件: 检查 __security_cookie 符号
        security_cookie = re.search(
            rb"__security_cookie|__security_check_cookie|__GSHandlerCheck",
            data,
            re.IGNORECASE,
        )
        # ELF 文件: 检查 __stack_chk_fail
        stack_chk = re.search(rb"__stack_chk_fail", data, re.IGNORECASE)

        if security_cookie or stack_chk:
            result["enabled"] = True
            result["details"] = "检测到栈金丝雀保护"
            result["risk"] = SeverityLevel.INFO
        else:
            result["details"] = "未检测到栈金丝雀保护 (/GS / -fstack-protector)"

        return result

    def check_dep(self, data: bytes) -> Dict[str, Any]:
        """检查数据执行保护 (DEP/NX)

        PE: 检查 DLL Characteristics 中的 NX_COMPAT 标志
        ELF: 检查 GNU_STACK 段是否无可执行权限

        Args:
            data: 文件二进制数据

        Returns:
            Dict[str, Any]: 检查结果
        """
        result = {
            "enabled": False,
            "details": "未检测到 DEP/NX 保护",
            "risk": SeverityLevel.HIGH,
        }

        if data is None:
            return result

        pe_info = self._parse_pe_header(data)
        if pe_info:
            if pe_info["dll_characteristics"] & self._PE_DLL_CHARACTERISTICS["NX_COMPAT"]:
                result["enabled"] = True
                result["details"] = "DEP (NX_COMPAT) 已启用"
                result["risk"] = SeverityLevel.INFO
            return result

        elf_info = self._parse_elf_header(data)
        if elf_info:
            if elf_info.get("has_nx", False):
                result["enabled"] = True
                result["details"] = "NX (栈不可执行) 已启用"
                result["risk"] = SeverityLevel.INFO
            return result

        return result

    def check_aslr(self, data: bytes) -> Dict[str, Any]:
        """检查地址空间布局随机化 (ASLR)

        PE: 检查 DLL Characteristics 中的 DYNAMIC_BASE 标志
        ELF: 检查是否为 PIE (Position Independent Executable)

        Args:
            data: 文件二进制数据

        Returns:
            Dict[str, Any]: 检查结果
        """
        result = {
            "enabled": False,
            "details": "未检测到 ASLR 保护",
            "risk": SeverityLevel.HIGH,
        }

        if data is None:
            return result

        pe_info = self._parse_pe_header(data)
        if pe_info:
            if pe_info["dll_characteristics"] & self._PE_DLL_CHARACTERISTICS["DYNAMIC_BASE"]:
                result["enabled"] = True
                result["details"] = "ASLR (DYNAMIC_BASE) 已启用"
                result["risk"] = SeverityLevel.INFO
            return result

        elf_info = self._parse_elf_header(data)
        if elf_info:
            if elf_info.get("has_pie", False):
                result["enabled"] = True
                result["details"] = "PIE (位置无关可执行文件) 已启用"
                result["risk"] = SeverityLevel.INFO
            return result

        return result

    def check_safe_seh(self, data: bytes) -> Dict[str, Any]:
        """检查 SafeSEH 保护

        仅适用于 PE 文件。检查是否包含 SafeSEH 异常处理表。

        Args:
            data: 文件二进制数据

        Returns:
            Dict[str, Any]: 检查结果
        """
        result = {
            "enabled": False,
            "details": "未检测到 SafeSEH 保护",
            "risk": SeverityLevel.MEDIUM,
        }

        if data is None:
            return result

        pe_info = self._parse_pe_header(data)
        if not pe_info:
            return result

        # SafeSEH 通过检查 NO_SEH 标志和异常表来判断
        if pe_info["dll_characteristics"] & self._PE_DLL_CHARACTERISTICS["NO_SEH"]:
            result["details"] = "NO_SEH 标志已设置（无 SEH 支持）"
            result["risk"] = SeverityLevel.INFO
            result["enabled"] = True
            return result

        # 搜索异常处理表
        safe_seh = re.search(
            rb"__safe_se_handler_table|_safe_se_handler_table",
            data,
            re.IGNORECASE,
        )
        if safe_seh:
            result["enabled"] = True
            result["details"] = "SafeSEH 异常处理表已注册"
            result["risk"] = SeverityLevel.INFO

        return result

    def check_control_flow_guard(self, data: bytes) -> Dict[str, Any]:
        """检查控制流保护 (CFG)

        检查 PE 文件中的 GUARD_CF 标志和 CFG 相关函数。

        Args:
            data: 文件二进制数据

        Returns:
            Dict[str, Any]: 检查结果
        """
        result = {
            "enabled": False,
            "details": "未检测到 CFG 保护",
            "risk": SeverityLevel.MEDIUM,
        }

        if data is None:
            return result

        pe_info = self._parse_pe_header(data)
        if not pe_info:
            return result

        if pe_info["dll_characteristics"] & self._PE_DLL_CHARACTERISTICS["GUARD_CF"]:
            result["enabled"] = True
            result["details"] = "Control Flow Guard (CFG) 已启用"
            result["risk"] = SeverityLevel.INFO
            return result

        # 检查 CFG 相关函数
        cfg_funcs = re.search(
            rb"__guard_check_icall|__guard_dispatch_icall|_guard_check_icall",
            data,
            re.IGNORECASE,
        )
        if cfg_funcs:
            result["enabled"] = True
            result["details"] = "检测到 CFG 检查函数"
            result["risk"] = SeverityLevel.INFO

        return result

    def check_high_entropy_aslr(self, data: bytes) -> Dict[str, Any]:
        """检查高熵 ASLR (64位)

        仅适用于 64位 PE 文件。检查 HIGH_ENTROPY_VA 标志。

        Args:
            data: 文件二进制数据

        Returns:
            Dict[str, Any]: 检查结果
        """
        result = {
            "enabled": False,
            "details": "未检测到高熵 ASLR",
            "risk": SeverityLevel.LOW,
        }

        if data is None:
            return result

        pe_info = self._parse_pe_header(data)
        if not pe_info or not pe_info["is_64bit"]:
            result["details"] = "非 64位程序，不适用高熵 ASLR"
            result["risk"] = SeverityLevel.INFO
            return result

        if pe_info["dll_characteristics"] & self._PE_DLL_CHARACTERISTICS["HIGH_ENTROPY_VA"]:
            result["enabled"] = True
            result["details"] = "高熵 ASLR (HIGH_ENTROPY_VA) 已启用"
            result["risk"] = SeverityLevel.INFO

        return result

    def analyze_all_protections(self, data: bytes) -> Dict[str, Any]:
        """综合分析所有二进制保护机制

        Args:
            data: 文件二进制数据

        Returns:
            Dict[str, Any]: 所有保护机制的检查结果
        """
        protections = {
            "stack_cookie": self.check_stack_cookie(data),
            "dep": self.check_dep(data),
            "aslr": self.check_aslr(data),
            "safe_seh": self.check_safe_seh(data),
            "control_flow_guard": self.check_control_flow_guard(data),
            "high_entropy_aslr": self.check_high_entropy_aslr(data),
        }

        # 统计启用的保护数量
        enabled_count = sum(
            1 for p in protections.values() if p.get("enabled", False)
        )
        total = len(protections)

        protections["summary"] = {
            "enabled_count": enabled_count,
            "total_count": total,
            "coverage_percent": round((enabled_count / total) * 100, 1),
            "status": (
                "保护充分" if enabled_count >= 5
                else "保护一般" if enabled_count >= 3
                else "保护不足"
            ),
        }

        return protections


# ============================================================================
# SEH 分析器 (SEHAnalyzer)
# ============================================================================

class SEHAnalyzer:
    """SEH (结构化异常处理) 分析器

    分析 PE 文件中的异常处理机制，检测 SEH 覆写漏洞、
    异常处理流程安全性以及 catch(...) 模式。
    """

    def __init__(self):
        """初始化 SEH 分析器"""
        self._seh_handler_pattern = re.compile(
            rb"__except_handler|_except_handler|__C_specific_handler",
            re.IGNORECASE,
        )

    def find_seh_handlers(self, data: bytes) -> List[Dict[str, Any]]:
        """定位 SEH/VEH 异常处理器

        在 PE 文件中搜索异常处理器的注册位置。

        Args:
            data: 文件二进制数据

        Returns:
            List[Dict]: 找到的异常处理器信息列表
        """
        handlers: List[Dict[str, Any]] = []

        if data is None:
            return handlers

        # 搜索 SEH 处理器注册
        for match in self._seh_handler_pattern.finditer(data):
            handlers.append({
                "handler_name": match.group(0).decode("ascii", errors="replace"),
                "offset": match.start(),
                "type": "SEH",
            })

        # 搜索 VEH 处理器 (AddVectoredExceptionHandler)
        veh_pattern = re.compile(
            rb"AddVectoredExceptionHandler|RtlAddVectoredExceptionHandler",
            re.IGNORECASE,
        )
        for match in veh_pattern.finditer(data):
            handlers.append({
                "handler_name": match.group(0).decode("ascii", errors="replace"),
                "offset": match.start(),
                "type": "VEH",
            })

        return handlers

    def detect_seh_overwrite(self, data: bytes) -> List[Vulnerability]:
        """检测 SEH 覆写漏洞

        检测以下模式:
        - SEH 处理器注册在栈上，且存在栈缓冲区溢出风险
        - 异常处理链中的节点可能被覆盖

        Args:
            data: 文件二进制数据

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if data is None:
            return vulns

        # 查找 SEH 处理器
        handlers = self.find_seh_handlers(data)

        if not handlers:
            return vulns

        # 检查每个处理器是否存在覆写风险
        for handler in handlers:
            # 检查文件是否启用 SafeSEH
            safe_seh_check = re.search(
                rb"__safe_se_handler_table|_safe_se_handler_table",
                data,
                re.IGNORECASE,
            )

            if not safe_seh_check:
                vulns.append(Vulnerability(
                    vuln_type=VulnerabilityType.SEH_OVERWRITE,
                    severity=SeverityLevel.HIGH,
                    description=(
                        f"检测到 SEH 处理器 {handler['handler_name']}，"
                        f"但未启用 SafeSEH 保护"
                    ),
                    location=f"偏移 0x{handler['offset']:X}",
                    confidence=0.60,
                    exploit_difficulty=ExploitDifficulty.MODERATE,
                    cwe_id="CWE-122",
                    fix_suggestion="启用 SafeSEH 保护，确保异常处理器经过验证",
                    extra_info=handler,
                ))

        return vulns

    def analyze_exception_flow(self, data: bytes) -> Dict[str, Any]:
        """分析异常处理流程安全性

        Args:
            data: 文件二进制数据

        Returns:
            Dict[str, Any]: 分析结果
        """
        result: Dict[str, Any] = {
            "handler_count": 0,
            "safe_seh_enabled": False,
            "veh_handler_count": 0,
            "risk_assessment": SeverityLevel.INFO.name,
        }

        if data is None:
            return result

        handlers = self.find_seh_handlers(data)
        result["handler_count"] = len(handlers)
        result["veh_handler_count"] = sum(
            1 for h in handlers if h["type"] == "VEH"
        )

        safe_seh = re.search(
            rb"__safe_se_handler_table|_safe_se_handler_table",
            data,
            re.IGNORECASE,
        )
        if safe_seh:
            result["safe_seh_enabled"] = True

        # 风险评估
        if result["handler_count"] > 0 and not result["safe_seh_enabled"]:
            result["risk_assessment"] = SeverityLevel.HIGH.name
        elif result["handler_count"] > 5:
            result["risk_assessment"] = SeverityLevel.MEDIUM.name
        else:
            result["risk_assessment"] = SeverityLevel.LOW.name

        return result

    def detect_catch_all(self, data: bytes) -> List[Vulnerability]:
        """检测 catch(...) 模式

        捕获所有异常的 catch(...) 可能隐藏真正的错误，
        导致程序在异常状态下继续运行，产生安全问题。

        Args:
            data: 文件二进制数据

        Returns:
            List[Vulnerability]: 检测到的漏洞列表
        """
        vulns: List[Vulnerability] = []

        if data is None:
            return vulns

        # catch(...) 在汇编中通常表现为无条件跳转到异常处理代码
        catch_all_pattern = re.compile(
            rb"__catch\b.*\b__except\b",
            re.IGNORECASE | re.DOTALL,
        )
        for match in catch_all_pattern.finditer(data):
            vulns.append(Vulnerability(
                vuln_type=VulnerabilityType.INSECURE_API,
                severity=SeverityLevel.LOW,
                description="检测到 catch-all 异常处理模式，可能隐藏错误",
                location=f"偏移 0x{match.start():X}",
                confidence=0.35,
                exploit_difficulty=ExploitDifficulty.HARD,
                cwe_id="CWE-396",
                fix_suggestion=(
                    "避免使用 catch(...)，仅捕获已知的异常类型，"
                    "让未预期的异常传播至顶层处理"
                ),
            ))

        return vulns


# ============================================================================
# 漏洞挖掘引擎主入口 (VulnerabilityDiscoveryEngine)
# ============================================================================

class VulnerabilityDiscoveryEngine:
    """漏洞挖掘引擎主入口

    整合所有子分析器，提供统一的漏洞扫描接口。
    支持对 PE/ELF 文件、汇编代码进行全面扫描，
    生成结构化的漏洞报告。

    使用示例:
        >>> engine = VulnerabilityDiscoveryEngine()
        >>> report = engine.scan_file("game.exe")
        >>> print(report.summary)
        >>> json_report = report.to_json()
    """

    def __init__(self):
        """初始化漏洞挖掘引擎及所有子组件"""
        # 初始化各个子分析器
        self._unsafe_func_detector = UnsafeFunctionDetector()
        self._buffer_overflow_analyzer = BufferOverflowAnalyzer()
        self._integer_overflow_analyzer = IntegerOverflowAnalyzer()
        self._memory_safety_analyzer = MemorySafetyAnalyzer()
        self._binary_protection_analyzer = BinaryProtectionAnalyzer()
        self._seh_analyzer = SEHAnalyzer()

        # 扫描统计
        self._total_scans: int = 0
        self._total_vulns_found: int = 0
        self._scan_history: List[Dict[str, Any]] = []

    def _read_file_data(self, file_path: str) -> Tuple[Optional[bytes], Optional[str]]:
        """读取文件，返回二进制数据和文本内容

        Args:
            file_path: 文件路径

        Returns:
            Tuple[Optional[bytes], Optional[str]]: (二进制数据, 文本内容)
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        data = _read_file_bytes(file_path)
        text = _read_file_text(file_path) if data else None

        # 如果文本读取失败，尝试将二进制解码为文本（用于汇编分析）
        if text is None and data:
            try:
                text = data.decode("ascii", errors="replace")
            except (UnicodeDecodeError, ValueError):
                text = None

        return data, text

    def scan_file(self, file_path: str) -> VulnerabilityReport:
        """对文件执行全面漏洞扫描

        扫描包括:
        - 不安全函数调用检测
        - 缓冲区溢出分析
        - 整数溢出分析
        - 内存安全分析
        - 二进制保护机制检查
        - SEH 异常处理分析

        Args:
            file_path: 目标文件路径

        Returns:
            VulnerabilityReport: 综合漏洞报告
        """
        import time
        start_time = time.time()

        # 读取文件数据
        data, text = self._read_file_data(file_path)

        # 初始化报告
        report = VulnerabilityReport(
            target_file=file_path,
            file_hash=_compute_file_hash(file_path) if data else "",
            file_size=os.path.getsize(file_path) if os.path.isfile(file_path) else 0,
        )

        all_vulns: List[Vulnerability] = []

        # ---- 1. 不安全函数扫描 ----
        if data:
            unsafe_vulns = self._unsafe_func_detector.scan_unsafe_functions(
                data, text
            )
            all_vulns.extend(unsafe_vulns)

            # 缺失边界检查
            missing_check_vulns = self._unsafe_func_detector.detect_missing_size_check(
                data, text
            )
            all_vulns.extend(missing_check_vulns)

        # ---- 2. 缓冲区溢出分析 ----
        if data:
            buf_vulns = self._buffer_overflow_analyzer.detect_stack_buffer_overflow(
                data, text
            )
            all_vulns.extend(buf_vulns)

            heap_vulns = self._buffer_overflow_analyzer.detect_heap_buffer_overflow(
                data, text
            )
            all_vulns.extend(heap_vulns)

            off_by_one_vulns = self._buffer_overflow_analyzer.detect_off_by_one(
                data, text
            )
            all_vulns.extend(off_by_one_vulns)

            fmt_vulns = self._buffer_overflow_analyzer.detect_format_string_vuln(
                data, text
            )
            all_vulns.extend(fmt_vulns)

            sprintf_vulns = self._buffer_overflow_analyzer.detect_sprintf_overflow(
                data, text
            )
            all_vulns.extend(sprintf_vulns)

        # ---- 3. 整数溢出分析 ----
        if text:
            int_vulns = self._integer_overflow_analyzer.detect_integer_overflow(
                data, text
            )
            all_vulns.extend(int_vulns)

            sign_vulns = self._integer_overflow_analyzer.detect_signed_unsigned_mismatch(
                data, text
            )
            all_vulns.extend(sign_vulns)

            mul_vulns = self._integer_overflow_analyzer.detect_size_multiplication_overflow(
                data, text
            )
            all_vulns.extend(mul_vulns)

            trunc_vulns = self._integer_overflow_analyzer.detect_truncation(
                data, text
            )
            all_vulns.extend(trunc_vulns)

            neg_vulns = self._integer_overflow_analyzer.detect_negative_allocation(
                data, text
            )
            all_vulns.extend(neg_vulns)

        # ---- 4. 内存安全分析 ----
        if text:
            uaf_vulns = self._memory_safety_analyzer.detect_use_after_free(
                data, text
            )
            all_vulns.extend(uaf_vulns)

            df_vulns = self._memory_safety_analyzer.detect_double_free(
                data, text
            )
            all_vulns.extend(df_vulns)

            null_vulns = self._memory_safety_analyzer.detect_null_pointer_deref(
                data, text
            )
            all_vulns.extend(null_vulns)

            uninit_vulns = self._memory_safety_analyzer.detect_uninitialized_memory(
                data, text
            )
            all_vulns.extend(uninit_vulns)

            type_vulns = self._memory_safety_analyzer.detect_type_confusion(
                data, text
            )
            all_vulns.extend(type_vulns)

        # ---- 5. 二进制保护机制检查 ----
        if data:
            protections = self._binary_protection_analyzer.analyze_all_protections(data)

            # 将缺失的保护机制作为漏洞报告
            if not protections["stack_cookie"]["enabled"]:
                all_vulns.append(Vulnerability(
                    vuln_type=VulnerabilityType.MISSING_STACK_COOKIE,
                    severity=SeverityLevel.MEDIUM,
                    description="未启用栈金丝雀保护 (/GS / -fstack-protector)",
                    location="二进制保护配置",
                    confidence=0.95,
                    exploit_difficulty=ExploitDifficulty.EASY,
                    cwe_id="CWE-693",
                    fix_suggestion="启用 /GS (MSVC) 或 -fstack-protector-strong (GCC)",
                ))

            if not protections["dep"]["enabled"]:
                all_vulns.append(Vulnerability(
                    vuln_type=VulnerabilityType.DEP_DISABLED,
                    severity=SeverityLevel.HIGH,
                    description="数据执行保护 (DEP/NX) 未启用",
                    location="二进制保护配置",
                    confidence=0.95,
                    exploit_difficulty=ExploitDifficulty.EASY,
                    cwe_id="CWE-693",
                    fix_suggestion="启用 DEP (/NXCOMPAT) 或 NX 位保护",
                ))

            if not protections["aslr"]["enabled"]:
                all_vulns.append(Vulnerability(
                    vuln_type=VulnerabilityType.ASLR_DISABLED,
                    severity=SeverityLevel.HIGH,
                    description="地址空间布局随机化 (ASLR) 未启用",
                    location="二进制保护配置",
                    confidence=0.95,
                    exploit_difficulty=ExploitDifficulty.EASY,
                    cwe_id="CWE-693",
                    fix_suggestion="启用 ASLR (/DYNAMICBASE) 或编译为 PIE",
                ))

            # 将保护分析结果存入 extra_info
            report.extra_info = protections

        # ---- 6. SEH 分析 ----
        if data:
            seh_vulns = self._seh_analyzer.detect_seh_overwrite(data)
            all_vulns.extend(seh_vulns)

            catch_vulns = self._seh_analyzer.detect_catch_all(data)
            all_vulns.extend(catch_vulns)

        # ---- 汇总报告 ----
        report.vulns = all_vulns
        report.update_statistics()

        # 计算风险评分
        report.risk_score = self._calculate_risk_score(all_vulns)

        # 生成摘要
        report.summary = self._generate_summary(report)

        # 生成建议
        report.recommendations = self._generate_recommendations(all_vulns)

        # 记录扫描时间
        elapsed = (time.time() - start_time) * 1000
        report.scan_duration_ms = round(elapsed, 2)

        # 更新统计
        self._total_scans += 1
        self._total_vulns_found += report.total_vulns
        self._scan_history.append({
            "file": file_path,
            "vulns_found": report.total_vulns,
            "risk_score": report.risk_score,
            "duration_ms": elapsed,
        })

        return report

    def scan_asm(self, asm_text: str) -> VulnerabilityReport:
        """从汇编文本进行扫描

        Args:
            asm_text: 汇编代码文本

        Returns:
            VulnerabilityReport: 漏洞报告
        """
        import time
        start_time = time.time()

        report = VulnerabilityReport(
            target_file="<assembly_text>",
            file_hash=hashlib.md5(asm_text.encode()).hexdigest(),
            file_size=len(asm_text),
        )

        all_vulns: List[Vulnerability] = []

        # 模拟二进制数据（基于汇编文本）
        fake_data = asm_text.encode("ascii", errors="replace")

        # 不安全函数扫描
        unsafe_vulns = self._unsafe_func_detector.scan_unsafe_functions(
            fake_data, asm_text
        )
        all_vulns.extend(unsafe_vulns)

        # 缓冲区溢出分析
        buf_vulns = self._buffer_overflow_analyzer.detect_stack_buffer_overflow(
            fake_data, asm_text
        )
        all_vulns.extend(buf_vulns)

        fmt_vulns = self._buffer_overflow_analyzer.detect_format_string_vuln(
            fake_data, asm_text
        )
        all_vulns.extend(fmt_vulns)

        off_vulns = self._buffer_overflow_analyzer.detect_off_by_one(
            fake_data, asm_text
        )
        all_vulns.extend(off_vulns)

        # 整数溢出分析
        int_vulns = self._integer_overflow_analyzer.detect_integer_overflow(
            fake_data, asm_text
        )
        all_vulns.extend(int_vulns)

        sign_vulns = self._integer_overflow_analyzer.detect_signed_unsigned_mismatch(
            fake_data, asm_text
        )
        all_vulns.extend(sign_vulns)

        mul_vulns = self._integer_overflow_analyzer.detect_size_multiplication_overflow(
            fake_data, asm_text
        )
        all_vulns.extend(mul_vulns)

        # 内存安全分析
        uaf_vulns = self._memory_safety_analyzer.detect_use_after_free(
            fake_data, asm_text
        )
        all_vulns.extend(uaf_vulns)

        df_vulns = self._memory_safety_analyzer.detect_double_free(
            fake_data, asm_text
        )
        all_vulns.extend(df_vulns)

        null_vulns = self._memory_safety_analyzer.detect_null_pointer_deref(
            fake_data, asm_text
        )
        all_vulns.extend(null_vulns)

        report.vulns = all_vulns
        report.update_statistics()
        report.risk_score = self._calculate_risk_score(all_vulns)
        report.summary = self._generate_summary(report)
        report.recommendations = self._generate_recommendations(all_vulns)

        elapsed = (time.time() - start_time) * 1000
        report.scan_duration_ms = round(elapsed, 2)

        return report

    def scan_unsafe_functions(self, file_path: str) -> VulnerabilityReport:
        """仅扫描不安全函数调用

        Args:
            file_path: 目标文件路径

        Returns:
            VulnerabilityReport: 漏洞报告
        """
        import time
        start_time = time.time()

        data, text = self._read_file_data(file_path)

        report = VulnerabilityReport(
            target_file=file_path,
            file_hash=_compute_file_hash(file_path) if data else "",
            file_size=os.path.getsize(file_path) if os.path.isfile(file_path) else 0,
        )

        if data:
            vulns = self._unsafe_func_detector.scan_unsafe_functions(data, text)
            missing_vulns = self._unsafe_func_detector.detect_missing_size_check(
                data, text
            )
            report.vulns = vulns + missing_vulns

        report.update_statistics()
        report.risk_score = self._calculate_risk_score(report.vulns)
        report.summary = self._generate_summary(report)
        report.recommendations = self._generate_recommendations(report.vulns)

        elapsed = (time.time() - start_time) * 1000
        report.scan_duration_ms = round(elapsed, 2)

        return report

    def scan_buffer_overflow(self, file_path: str) -> VulnerabilityReport:
        """仅扫描缓冲区溢出

        Args:
            file_path: 目标文件路径

        Returns:
            VulnerabilityReport: 漏洞报告
        """
        import time
        start_time = time.time()

        data, text = self._read_file_data(file_path)

        report = VulnerabilityReport(
            target_file=file_path,
            file_hash=_compute_file_hash(file_path) if data else "",
            file_size=os.path.getsize(file_path) if os.path.isfile(file_path) else 0,
        )

        if data:
            vulns: List[Vulnerability] = []
            vulns.extend(self._buffer_overflow_analyzer.detect_stack_buffer_overflow(data, text))
            vulns.extend(self._buffer_overflow_analyzer.detect_heap_buffer_overflow(data, text))
            vulns.extend(self._buffer_overflow_analyzer.detect_off_by_one(data, text))
            vulns.extend(self._buffer_overflow_analyzer.detect_format_string_vuln(data, text))
            vulns.extend(self._buffer_overflow_analyzer.detect_sprintf_overflow(data, text))
            report.vulns = vulns

        report.update_statistics()
        report.risk_score = self._calculate_risk_score(report.vulns)
        report.summary = self._generate_summary(report)
        report.recommendations = self._generate_recommendations(report.vulns)

        elapsed = (time.time() - start_time) * 1000
        report.scan_duration_ms = round(elapsed, 2)

        return report

    def scan_integer_overflow(self, file_path: str) -> VulnerabilityReport:
        """仅扫描整数溢出

        Args:
            file_path: 目标文件路径

        Returns:
            VulnerabilityReport: 漏洞报告
        """
        import time
        start_time = time.time()

        data, text = self._read_file_data(file_path)

        report = VulnerabilityReport(
            target_file=file_path,
            file_hash=_compute_file_hash(file_path) if data else "",
            file_size=os.path.getsize(file_path) if os.path.isfile(file_path) else 0,
        )

        if text:
            vulns: List[Vulnerability] = []
            vulns.extend(self._integer_overflow_analyzer.detect_integer_overflow(data, text))
            vulns.extend(self._integer_overflow_analyzer.detect_signed_unsigned_mismatch(data, text))
            vulns.extend(self._integer_overflow_analyzer.detect_size_multiplication_overflow(data, text))
            vulns.extend(self._integer_overflow_analyzer.detect_truncation(data, text))
            vulns.extend(self._integer_overflow_analyzer.detect_negative_allocation(data, text))
            report.vulns = vulns

        report.update_statistics()
        report.risk_score = self._calculate_risk_score(report.vulns)
        report.summary = self._generate_summary(report)
        report.recommendations = self._generate_recommendations(report.vulns)

        elapsed = (time.time() - start_time) * 1000
        report.scan_duration_ms = round(elapsed, 2)

        return report

    def scan_memory_safety(self, file_path: str) -> VulnerabilityReport:
        """仅扫描内存安全问题

        Args:
            file_path: 目标文件路径

        Returns:
            VulnerabilityReport: 漏洞报告
        """
        import time
        start_time = time.time()

        data, text = self._read_file_data(file_path)

        report = VulnerabilityReport(
            target_file=file_path,
            file_hash=_compute_file_hash(file_path) if data else "",
            file_size=os.path.getsize(file_path) if os.path.isfile(file_path) else 0,
        )

        if text:
            vulns: List[Vulnerability] = []
            vulns.extend(self._memory_safety_analyzer.detect_use_after_free(data, text))
            vulns.extend(self._memory_safety_analyzer.detect_double_free(data, text))
            vulns.extend(self._memory_safety_analyzer.detect_null_pointer_deref(data, text))
            vulns.extend(self._memory_safety_analyzer.detect_uninitialized_memory(data, text))
            vulns.extend(self._memory_safety_analyzer.detect_type_confusion(data, text))
            report.vulns = vulns

        report.update_statistics()
        report.risk_score = self._calculate_risk_score(report.vulns)
        report.summary = self._generate_summary(report)
        report.recommendations = self._generate_recommendations(report.vulns)

        elapsed = (time.time() - start_time) * 1000
        report.scan_duration_ms = round(elapsed, 2)

        return report

    def scan_binary_protections(self, file_path: str) -> Dict[str, Any]:
        """检查二进制保护机制

        Args:
            file_path: 目标文件路径

        Returns:
            Dict[str, Any]: 保护机制检查结果
        """
        data = _read_file_bytes(file_path)
        if data is None:
            return {"error": f"无法读取文件: {file_path}"}

        return self._binary_protection_analyzer.analyze_all_protections(data)

    def scan_seh(self, file_path: str) -> VulnerabilityReport:
        """分析 SEH 异常处理器

        Args:
            file_path: 目标文件路径

        Returns:
            VulnerabilityReport: 漏洞报告
        """
        import time
        start_time = time.time()

        data = _read_file_bytes(file_path)

        report = VulnerabilityReport(
            target_file=file_path,
            file_hash=_compute_file_hash(file_path) if data else "",
            file_size=os.path.getsize(file_path) if os.path.isfile(file_path) else 0,
        )

        if data:
            vulns: List[Vulnerability] = []
            vulns.extend(self._seh_analyzer.detect_seh_overwrite(data))
            vulns.extend(self._seh_analyzer.detect_catch_all(data))
            report.vulns = vulns

        report.update_statistics()
        report.risk_score = self._calculate_risk_score(report.vulns)
        report.summary = self._generate_summary(report)
        report.recommendations = self._generate_recommendations(report.vulns)

        elapsed = (time.time() - start_time) * 1000
        report.scan_duration_ms = round(elapsed, 2)

        return report

    def generate_report(self, file_path: str) -> VulnerabilityReport:
        """生成漏洞报告（等同于 scan_file）

        Args:
            file_path: 目标文件路径

        Returns:
            VulnerabilityReport: 综合漏洞报告
        """
        return self.scan_file(file_path)

    def get_risk_score(self, file_path: str) -> float:
        """计算并返回文件的整体风险评分

        Args:
            file_path: 目标文件路径

        Returns:
            float: 风险评分 (0.0 - 100.0)
        """
        report = self.scan_file(file_path)
        return report.risk_score

    def get_statistics(self) -> Dict[str, Any]:
        """获取引擎统计信息

        Returns:
            Dict[str, Any]: 引擎运行统计
        """
        return {
            "total_scans": self._total_scans,
            "total_vulns_found": self._total_vulns_found,
            "average_vulns_per_scan": (
                round(self._total_vulns_found / self._total_scans, 2)
                if self._total_scans > 0
                else 0.0
            ),
            "components": {
                "unsafe_function_detector": "ready",
                "buffer_overflow_analyzer": "ready",
                "integer_overflow_analyzer": "ready",
                "memory_safety_analyzer": "ready",
                "binary_protection_analyzer": "ready",
                "seh_analyzer": "ready",
            },
            "supported_vuln_types": len(VulnerabilityType),
            "cwe_coverage": len(set(_CWE_MAP.values())),
            "scan_history": self._scan_history[-10:],  # 最近10次扫描
        }

    def _calculate_risk_score(self, vulns: List[Vulnerability]) -> float:
        """计算综合风险评分

        评分公式:
            risk_score = sum(severity_score * confidence * exploit_factor) / normalization
            映射到 0-100 范围

        Args:
            vulns: 漏洞列表

        Returns:
            float: 风险评分 (0.0 - 100.0)
        """
        if not vulns:
            return 0.0

        total_score = 0.0
        for v in vulns:
            severity_score = v.severity.numeric_score
            exploit_factor = 1.0 / v.exploit_difficulty.numeric_rating
            total_score += severity_score * v.confidence * exploit_factor

        # 归一化到 0-100
        risk_score = min(100.0, total_score * 10.0)
        return round(risk_score, 2)

    def _generate_summary(self, report: VulnerabilityReport) -> str:
        """生成报告摘要

        Args:
            report: 漏洞报告

        Returns:
            str: 摘要文本
        """
        report.update_statistics()

        if report.total_vulns == 0:
            return f"对 {os.path.basename(report.target_file)} 的扫描未发现已知漏洞模式。"

        severity_desc = []
        if report.critical_count > 0:
            severity_desc.append(f"{report.critical_count} 个严重")
        if report.high_count > 0:
            severity_desc.append(f"{report.high_count} 个高危")
        if report.medium_count > 0:
            severity_desc.append(f"{report.medium_count} 个中危")
        if report.low_count > 0:
            severity_desc.append(f"{report.low_count} 个低危")

        severity_str = "、".join(severity_desc) if severity_desc else "若干"

        risk_level = (
            "严重风险" if report.risk_score >= 80
            else "高风险" if report.risk_score >= 60
            else "中风险" if report.risk_score >= 40
            else "低风险" if report.risk_score >= 20
            else "极低风险"
        )

        return (
            f"对 {os.path.basename(report.target_file)} 的漏洞扫描发现 "
            f"共 {report.total_vulns} 个潜在漏洞（{severity_str}），"
            f"综合风险评分: {report.risk_score}/100 ({risk_level})。"
        )

    def _generate_recommendations(self, vulns: List[Vulnerability]) -> List[str]:
        """生成修复建议列表

        Args:
            vulns: 漏洞列表

        Returns:
            List[str]: 建议列表
        """
        recommendations: List[str] = []
        seen = set()

        # 收集所有 CWE 类别
        cwe_categories: Dict[str, List[Vulnerability]] = defaultdict(list)
        for v in vulns:
            cwe_categories[v.cwe_id].append(v)

        # 对每个 CWE 类别生成建议
        for cwe_id, cwe_vulns in cwe_categories.items():
            if cwe_id in seen:
                continue
            seen.add(cwe_id)

            if cwe_id == "CWE-120":
                recommendations.append(
                    "【缓冲区溢出】使用安全函数 (strcpy_s, strncpy, snprintf) "
                    "替代不安全函数，并确保所有复制操作前进行边界检查。"
                )
            elif cwe_id == "CWE-134":
                recommendations.append(
                    "【格式字符串】始终使用固定格式字符串，如 printf(\"%s\", user_input)，"
                    "避免将用户输入直接作为格式字符串参数。"
                )
            elif cwe_id == "CWE-190":
                recommendations.append(
                    "【整数溢出】在算术运算前检查操作数是否会导致溢出，"
                    "使用安全整数运算库 (SafeInt) 或编译器内置检查。"
                )
            elif cwe_id == "CWE-416":
                recommendations.append(
                    "【释放后使用】释放内存后将指针置为 NULL，"
                    "使用智能指针 (std::unique_ptr, std::shared_ptr) 管理生命周期。"
                )
            elif cwe_id == "CWE-415":
                recommendations.append(
                    "【双重释放】确保每个分配只释放一次，"
                    "释放后立即置空指针，使用 RAII 模式管理资源。"
                )
            elif cwe_id == "CWE-476":
                recommendations.append(
                    "【空指针解引用】在解引用前检查指针是否为 NULL，"
                    "使用引用而非指针，或使用 optional 类型。"
                )
            elif cwe_id == "CWE-693":
                recommendations.append(
                    "【保护机制缺失】启用所有可用的二进制保护机制: "
                    "DEP、ASLR、SafeSEH、CFG、栈金丝雀。"
                )
            elif cwe_id == "CWE-676":
                recommendations.append(
                    "【不安全 API】将废弃 API 替换为现代安全替代方案，"
                    "如 lstrcpy -> StringCchCopy。"
                )
            elif cwe_id == "CWE-457":
                recommendations.append(
                    "【未初始化内存】使用 calloc 替代 malloc，"
                    "或在声明时初始化所有变量。"
                )
            elif cwe_id == "CWE-843":
                recommendations.append(
                    "【类型混淆】避免使用 reinterpret_cast，"
                    "使用 static_cast 或 dynamic_cast 进行类型安全的转换。"
                )
            elif cwe_id == "CWE-78":
                recommendations.append(
                    "【命令注入】避免使用 system/popen 处理用户输入，"
                    "使用参数化的进程创建 API (CreateProcess, execve)。"
                )
            elif cwe_id == "CWE-22":
                recommendations.append(
                    "【路径遍历】验证和规范化所有文件路径，"
                    "拒绝包含 \"..\" 的路径，限制文件访问范围。"
                )

        # 添加通用建议
        if not recommendations:
            recommendations.append("未发现明显的漏洞模式，建议保持代码审查和测试。")
        else:
            recommendations.append(
                "【通用建议】定期进行代码审计，使用静态分析工具 (Coverity, PVS-Studio) "
                "辅助发现潜在漏洞，保持编译器和依赖库更新。"
            )

        return recommendations


# ============================================================================
# 模块级便捷函数
# ============================================================================

# 全局引擎实例（惰性初始化）
_engine_instance: Optional[VulnerabilityDiscoveryEngine] = None


def _get_engine() -> VulnerabilityDiscoveryEngine:
    """获取全局引擎实例，惰性初始化"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = VulnerabilityDiscoveryEngine()
    return _engine_instance


def quick_scan(file_path: str) -> Dict[str, Any]:
    """快速全面扫描文件

    便捷函数，快速执行完整漏洞扫描并返回字典格式结果。

    Args:
        file_path: 目标文件路径

    Returns:
        Dict[str, Any]: 扫描结果字典
    """
    engine = _get_engine()
    report = engine.scan_file(file_path)
    return report.to_dict()


def quick_scan_unsafe(file_path: str) -> Dict[str, Any]:
    """快速扫描不安全函数

    便捷函数，仅扫描不安全函数调用。

    Args:
        file_path: 目标文件路径

    Returns:
        Dict[str, Any]: 扫描结果字典
    """
    engine = _get_engine()
    report = engine.scan_unsafe_functions(file_path)
    return report.to_dict()


def quick_check_protections(file_path: str) -> Dict[str, Any]:
    """快速检查二进制保护机制

    便捷函数，检查目标文件的保护机制状态。

    Args:
        file_path: 目标文件路径

    Returns:
        Dict[str, Any]: 保护机制检查结果
    """
    engine = _get_engine()
    return engine.scan_binary_protections(file_path)


# ============================================================================
# 模块自检 (Module Self-Check)
# ============================================================================

def _self_test() -> Dict[str, Any]:
    """模块自检功能

    验证所有组件是否正常工作。

    Returns:
        Dict[str, Any]: 自检结果
    """
    results: Dict[str, Any] = {
        "status": "ok",
        "components": {},
        "vulnerability_types": len(VulnerabilityType),
        "cwe_mappings": len(_CWE_MAP),
    }

    try:
        # 测试 UnsafeFunctionDetector
        detector = UnsafeFunctionDetector()
        func_list = detector.get_unsafe_function_list()
        results["components"]["unsafe_function_detector"] = {
            "status": "ok",
            "functions_defined": len(func_list),
        }
    except Exception as e:
        results["components"]["unsafe_function_detector"] = {
            "status": "error",
            "error": str(e),
        }
        results["status"] = "partial_failure"

    try:
        # 测试 BufferOverflowAnalyzer
        buf_analyzer = BufferOverflowAnalyzer()
        test_data = b"call malloc\ncall memcpy\ncall strcpy\nsprintf"
        test_asm = "push eax\ncall printf\nsub esp, 0x40\ncall memcpy"
        vulns = buf_analyzer.detect_stack_buffer_overflow(test_data, test_asm)
        results["components"]["buffer_overflow_analyzer"] = {
            "status": "ok",
            "test_detections": len(vulns),
        }
    except Exception as e:
        results["components"]["buffer_overflow_analyzer"] = {
            "status": "error",
            "error": str(e),
        }
        results["status"] = "partial_failure"

    try:
        # 测试 IntegerOverflowAnalyzer
        int_analyzer = IntegerOverflowAnalyzer()
        test_asm = "add eax, ebx\nmul ecx\ncall malloc"
        vulns = int_analyzer.detect_integer_overflow(None, test_asm)
        results["components"]["integer_overflow_analyzer"] = {
            "status": "ok",
            "test_detections": len(vulns),
        }
    except Exception as e:
        results["components"]["integer_overflow_analyzer"] = {
            "status": "error",
            "error": str(e),
        }
        results["status"] = "partial_failure"

    try:
        # 测试 MemorySafetyAnalyzer
        mem_analyzer = MemorySafetyAnalyzer()
        test_asm = "call malloc\nmov eax, [eax]\ncall free\npush eax\ncall free"
        vulns = mem_analyzer.detect_null_pointer_deref(None, test_asm)
        results["components"]["memory_safety_analyzer"] = {
            "status": "ok",
            "test_detections": len(vulns),
        }
    except Exception as e:
        results["components"]["memory_safety_analyzer"] = {
            "status": "error",
            "error": str(e),
        }
        results["status"] = "partial_failure"

    try:
        # 测试 BinaryProtectionAnalyzer
        prot_analyzer = BinaryProtectionAnalyzer()
        results["components"]["binary_protection_analyzer"] = {
            "status": "ok",
        }
    except Exception as e:
        results["components"]["binary_protection_analyzer"] = {
            "status": "error",
            "error": str(e),
        }
        results["status"] = "partial_failure"

    try:
        # 测试 SEHAnalyzer
        seh_analyzer = SEHAnalyzer()
        test_data = b"__except_handler4\x00\x20\x40\x00"
        handlers = seh_analyzer.find_seh_handlers(test_data)
        results["components"]["seh_analyzer"] = {
            "status": "ok",
            "handlers_found": len(handlers),
        }
    except Exception as e:
        results["components"]["seh_analyzer"] = {
            "status": "error",
            "error": str(e),
        }
        results["status"] = "partial_failure"

    try:
        # 测试 VulnerabilityDiscoveryEngine
        engine = VulnerabilityDiscoveryEngine()
        stats = engine.get_statistics()
        results["components"]["vulnerability_discovery_engine"] = {
            "status": "ok",
            "supported_vuln_types": stats["supported_vuln_types"],
        }
    except Exception as e:
        results["components"]["vulnerability_discovery_engine"] = {
            "status": "error",
            "error": str(e),
        }
        results["status"] = "partial_failure"

    try:
        # 测试 VulnerabilityReport 序列化
        report = VulnerabilityReport(target_file="test.exe")
        report.update_statistics()
        json_str = report.to_json()
        results["components"]["vulnerability_report"] = {
            "status": "ok",
            "json_serializable": isinstance(json.loads(json_str), dict),
        }
    except Exception as e:
        results["components"]["vulnerability_report"] = {
            "status": "error",
            "error": str(e),
        }
        results["status"] = "partial_failure"

    return results


# ============================================================================
# 模块入口
# ============================================================================

if __name__ == "__main__":
    """直接运行模块时执行自检"""
    import sys

    print("=" * 60)
    print("  漏洞挖掘引擎 (Vulnerability Discovery Engine) 自检")
    print("=" * 60)

    test_results = _self_test()

    print(f"\n模块状态: {test_results['status']}")
    print(f"漏洞类型覆盖: {test_results['vulnerability_types']} 种")
    print(f"CWE 映射: {test_results['cwe_mappings']} 个")
    print(f"\n组件检查:")

    for comp_name, comp_result in test_results["components"].items():
        status_icon = "OK" if comp_result["status"] == "ok" else "FAIL"
        print(f"  [{status_icon}] {comp_name}")
        if comp_result["status"] != "ok":
            print(f"         错误: {comp_result.get('error', '未知错误')}")

    print("\n" + "=" * 60)

    sys.exit(0 if test_results["status"] == "ok" else 1)