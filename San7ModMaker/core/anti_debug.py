"""
反调试与反反调试引擎 (Anti-Debug & Anti-Anti-Debug Engine)
提供全面的反调试技术检测、绕过策略生成、完整性校验识别与对抗能力。

引擎突破 16: 支持 20+ 反调试技术检测、自动绕过生成、ScyllaHide 风格隐藏、完整性校验对抗
"""

import os
import re
import struct
import zlib
import hashlib
import time
import json
from typing import Dict, List, Optional, Tuple, Set, Any, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict


# ============================================================
# 枚举与数据类
# ============================================================

class AntiDebugCategory(Enum):
    """反调试分类"""
    PROCESS_INFO = "process_info"           # 进程信息检测
    DEBUG_OBJECT = "debug_object"           # 调试对象检测
    HARDWARE_BP = "hardware_breakpoint"     # 硬件断点检测
    SOFTWARE_BP = "software_breakpoint"      # 软件断点检测
    TIMING = "timing"                        # 时间检测
    EXCEPTION = "exception"                  # 异常处理
    MEMORY = "memory"                        # 内存检测
    PARENT_PROCESS = "parent_process"        # 父进程检测
    CODE_INTEGRITY = "code_integrity"        # 代码完整性
    TLS_CALLBACK = "tls_callback"           # TLS 回调
    REGISTRY = "registry"                    # 注册表检测
    WINDOW = "window"                        # 窗口检测


class BypassStrategy(Enum):
    """绕过策略"""
    PATCH_CODE = "patch_code"               # 代码补丁
    HOOK_API = "hook_api"                   # API Hook
    MEMORY_PATCH = "memory_patch"           # 内存补丁
    RETURN_VALUE = "return_value"           # 修改返回值
    NOP_OUT = "nop_out"                     # NOP 填充
    JMP_OVER = "jmp_over"                   # 跳转绕过
    REGISTER_MODIFY = "register_modify"     # 寄存器修改
    TIMING_SPOOF = "timing_spoof"           # 时间欺骗
    TITAN_HIDE = "titan_hide"              # TitanHide 风格
    SCYLLA_HIDE = "scylla_hide"            # ScyllaHide 风格


class SeverityLevel(Enum):
    """严重程度"""
    CRITICAL = "critical"   # 致命 - 检测到直接退出
    HIGH = "high"           # 高危 - 影响核心功能
    MEDIUM = "medium"       # 中危 - 部分功能受限
    LOW = "low"             # 低危 - 仅记录日志
    INFO = "info"           # 信息 - 仅提示


@dataclass
class AntiDebugSignature:
    """反调试签名"""
    name: str
    category: AntiDebugCategory
    description: str
    severity: SeverityLevel
    # 检测模式
    api_calls: List[str] = field(default_factory=list)
    byte_patterns: List[bytes] = field(default_factory=list)
    code_patterns: List[str] = field(default_factory=list)
    # 绕过
    bypass_strategies: List[BypassStrategy] = field(default_factory=list)
    bypass_code: str = ""
    # 参考
    references: List[str] = field(default_factory=list)


@dataclass
class DetectionResult:
    """检测结果"""
    signature: AntiDebugSignature
    detected: bool
    confidence: float                    # 0.0 - 1.0
    locations: List[int] = field(default_factory=list)  # 检测到的偏移位置
    evidence: str = ""                   # 检测证据
    bypass_suggestion: str = ""          # 绕过建议


@dataclass
class IntegrityCheck:
    """完整性校验项"""
    name: str
    check_type: str                      # crc32, md5, sha256, custom
    target_range: Tuple[int, int]        # 校验范围 (start, end)
    expected_value: str = ""
    actual_value: str = ""
    algorithm: str = ""
    code_location: int = 0
    is_patched: bool = False


@dataclass
class AntiDebugReport:
    """反调试分析报告"""
    target_file: str = ""
    total_checks: int = 0
    detected_count: int = 0
    results: List[DetectionResult] = field(default_factory=list)
    integrity_checks: List[IntegrityCheck] = field(default_factory=list)
    bypass_plan: Dict[str, Any] = field(default_factory=dict)
    risk_score: float = 0.0              # 0-100 风险评分
    summary: str = ""


# ============================================================
# 反调试签名数据库
# ============================================================

ANTI_DEBUG_SIGNATURES: List[AntiDebugSignature] = [
    # ---- 进程信息检测 ----
    AntiDebugSignature(
        name="PEB.BeingDebugged",
        category=AntiDebugCategory.PROCESS_INFO,
        description="检测 PEB 结构中的 BeingDebugged 标志位",
        severity=SeverityLevel.HIGH,
        api_calls=["NtQueryInformationProcess", "ZwQueryInformationProcess"],
        byte_patterns=[
            bytes([0x64, 0xA1, 0x30, 0x00, 0x00, 0x00]),  # mov eax, fs:[0x30]
            bytes([0x65, 0x48, 0x8B, 0x04, 0x25, 0x60, 0x00, 0x00, 0x00]),  # x64: mov rax, gs:[0x60]
        ],
        code_patterns=[
            r"fs:\[0x30\]", r"gs:\[0x60\]",
            r"IsDebuggerPresent",
            r"PEB.*BeingDebugged",
        ],
        bypass_strategies=[BypassStrategy.MEMORY_PATCH, BypassStrategy.SCYLLA_HIDE],
        bypass_code="// 将 PEB.BeingDebugged 设为 0\nBYTE* peb = (BYTE*)__readfsdword(0x30);\npeb[2] = 0;",
        references=["https://anti-debug.checkpoint.com/techniques/process-memory.html#peb"]
    ),
    AntiDebugSignature(
        name="PEB.NtGlobalFlag",
        category=AntiDebugCategory.PROCESS_INFO,
        description="检测 PEB 中的 NtGlobalFlag 标志（调试时设为 0x70）",
        severity=SeverityLevel.MEDIUM,
        api_calls=[],
        byte_patterns=[
            bytes([0x64, 0xA1, 0x30, 0x00, 0x00, 0x00]),  # mov eax, fs:[0x30] + offset 0x68
        ],
        code_patterns=[
            r"NtGlobalFlag", r"0x68.*PEB", r"0x70.*flag",
        ],
        bypass_strategies=[BypassStrategy.MEMORY_PATCH, BypassStrategy.HOOK_API],
        bypass_code="// 将 NtGlobalFlag 设为 0\nDWORD* flag = (DWORD*)((BYTE*)__readfsdword(0x30) + 0x68);\n*flag = 0;",
    ),
    AntiDebugSignature(
        name="ProcessDebugPort",
        category=AntiDebugCategory.DEBUG_OBJECT,
        description="通过 NtQueryInformationProcess 检查 DebugPort",
        severity=SeverityLevel.HIGH,
        api_calls=["NtQueryInformationProcess", "ZwQueryInformationProcess"],
        byte_patterns=[
            bytes([0x07, 0x00, 0x00, 0x00]),  # ProcessDebugPort = 7
        ],
        code_patterns=[
            r"ProcessDebugPort", r"DebugPort.*!=.*0",
            r"ProcessInformationClass.*0x7",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.RETURN_VALUE],
        bypass_code="// Hook NtQueryInformationProcess, DebugPort 返回 0\nif (ProcessInformationClass == 7) {\n  *(DWORD*)ProcessInformation = 0;\n  return 0;\n}",
    ),
    AntiDebugSignature(
        name="ProcessDebugObjectHandle",
        category=AntiDebugCategory.DEBUG_OBJECT,
        description="检查进程调试对象句柄",
        severity=SeverityLevel.HIGH,
        api_calls=["NtQueryInformationProcess", "ZwQueryInformationProcess"],
        byte_patterns=[
            bytes([0x1E, 0x00, 0x00, 0x00]),  # ProcessDebugObjectHandle = 30
        ],
        code_patterns=[
            r"ProcessDebugObjectHandle", r"DebugObject",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.SCYLLA_HIDE],
        bypass_code="// Hook NtQueryInformationProcess, DebugObjectHandle 返回 STATUS_PORT_NOT_SET",
    ),
    AntiDebugSignature(
        name="NtQuerySystemInformation",
        category=AntiDebugCategory.PROCESS_INFO,
        description="通过 SystemKernelDebuggerInformation 检测内核调试器",
        severity=SeverityLevel.CRITICAL,
        api_calls=["NtQuerySystemInformation", "ZwQuerySystemInformation"],
        byte_patterns=[
            bytes([0x23, 0x00, 0x00, 0x00]),  # SystemKernelDebuggerInformation = 0x23
        ],
        code_patterns=[
            r"SystemKernelDebuggerInformation",
            r"KdDebuggerEnabled",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.TITAN_HIDE],
        bypass_code="// Hook 并返回 KdDebuggerEnabled = FALSE",
    ),

    # ---- 硬件断点检测 ----
    AntiDebugSignature(
        name="HardwareBreakpointDetection",
        category=AntiDebugCategory.HARDWARE_BP,
        description="检测 DR0-DR7 调试寄存器是否被设置",
        severity=SeverityLevel.HIGH,
        api_calls=["GetThreadContext", "NtGetContextThread"],
        byte_patterns=[
            bytes([0x0F, 0x31]),  # rdtsc (常与异常处理配合)
        ],
        code_patterns=[
            r"GetThreadContext", r"CONTEXT", r"DR[0-7]",
            r"CONTEXT_DEBUG_REGISTERS", r"0x10000",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.REGISTER_MODIFY],
        bypass_code="// Hook GetThreadContext, 清除 DR0-DR7\nctx->Dr0 = ctx->Dr1 = ctx->Dr2 = ctx->Dr3 = 0;\nctx->Dr6 = 0;\nctx->Dr7 = 0;",
    ),
    AntiDebugSignature(
        name="SEHHardwareBreakpoint",
        category=AntiDebugCategory.HARDWARE_BP,
        description="通过 SEH 异常处理检测硬件断点",
        severity=SeverityLevel.HIGH,
        api_calls=["SetUnhandledExceptionFilter", "AddVectoredExceptionHandler"],
        byte_patterns=[
            bytes([0xCD, 0x01]),  # INT 1 (单步异常触发）
        ],
        code_patterns=[
            r"EXCEPTION_SINGLE_STEP", r"0x80000004",
            r"UnhandledExceptionFilter",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.PATCH_CODE],
        bypass_code="// Hook 异常处理器，过滤单步异常",
    ),

    # ---- 软件断点检测 ----
    AntiDebugSignature(
        name="SoftwareBreakpointDetection",
        category=AntiDebugCategory.SOFTWARE_BP,
        description="扫描代码段中的 0xCC (INT 3) 字节",
        severity=SeverityLevel.HIGH,
        api_calls=[],
        byte_patterns=[
            bytes([0xCC]),  # INT 3
        ],
        code_patterns=[
            r"0xCC", r"INT.*3", r"breakpoint.*scan",
            r"memcmp.*0xCC", r"hash.*code.*section",
        ],
        bypass_strategies=[BypassStrategy.MEMORY_PATCH, BypassStrategy.HOOK_API],
        bypass_code="// 使用硬件断点替代软件断点，或 Hook 检测函数",
    ),
    AntiDebugSignature(
        name="INT2DDetection",
        category=AntiDebugCategory.EXCEPTION,
        description="使用 INT 0x2D 指令检测内核调试器",
        severity=SeverityLevel.CRITICAL,
        api_calls=[],
        byte_patterns=[
            bytes([0xCD, 0x2D]),  # INT 2D
        ],
        code_patterns=[
            r"INT.*0x2D", r"0xCD.*0x2D",
        ],
        bypass_strategies=[BypassStrategy.PATCH_CODE, BypassStrategy.TITAN_HIDE],
        bypass_code="// 将 INT 0x2D 替换为 NOP; NOP",
    ),
    AntiDebugSignature(
        name="INT3AntiDebug",
        category=AntiDebugCategory.EXCEPTION,
        description="使用 INT 3 + 异常处理进行反调试",
        severity=SeverityLevel.MEDIUM,
        api_calls=["SetUnhandledExceptionFilter"],
        byte_patterns=[
            bytes([0xCD, 0x03]),  # INT 3
        ],
        code_patterns=[
            r"__try.*__except", r"INT.*3.*exception",
        ],
        bypass_strategies=[BypassStrategy.PATCH_CODE, BypassStrategy.HOOK_API],
        bypass_code="// Hook 异常处理器，静默处理 INT 3 异常",
    ),

    # ---- 时间检测 ----
    AntiDebugSignature(
        name="RDTSCDetection",
        category=AntiDebugCategory.TIMING,
        description="通过 RDTSC 指令检测执行时间异常",
        severity=SeverityLevel.MEDIUM,
        api_calls=[],
        byte_patterns=[
            bytes([0x0F, 0x31]),  # rdtsc
        ],
        code_patterns=[
            r"rdtsc", r"RDTSC", r"__rdtsc",
        ],
        bypass_strategies=[BypassStrategy.TIMING_SPOOF, BypassStrategy.PATCH_CODE],
        bypass_code="// 将 RDTSC 结果缓慢递增，或 NOP 掉时间比较",
    ),
    AntiDebugSignature(
        name="GetTickCountDetection",
        category=AntiDebugCategory.TIMING,
        description="通过 GetTickCount/QueryPerformanceCounter 检测时间差",
        severity=SeverityLevel.MEDIUM,
        api_calls=["GetTickCount", "GetTickCount64", "QueryPerformanceCounter", "timeGetTime"],
        byte_patterns=[],
        code_patterns=[
            r"GetTickCount", r"QueryPerformanceCounter",
            r"timeGetTime", r"timing.*check",
        ],
        bypass_strategies=[BypassStrategy.TIMING_SPOOF, BypassStrategy.HOOK_API],
        bypass_code="// Hook 时间函数，返回预计算或缓慢递增的值",
    ),

    # ---- 异常处理 ----
    AntiDebugSignature(
        name="CloseHandleException",
        category=AntiDebugCategory.EXCEPTION,
        description="使用 CloseHandle(INVALID_HANDLE) 触发异常检测调试器",
        severity=SeverityLevel.MEDIUM,
        api_calls=["CloseHandle"],
        byte_patterns=[],
        code_patterns=[
            r"CloseHandle.*INVALID_HANDLE",
            r"CloseHandle.*0xFFFFFFFF",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.PATCH_CODE],
        bypass_code="// Hook CloseHandle, 检测无效句柄时返回 TRUE",
    ),
    AntiDebugSignature(
        name="OutputDebugStringExploit",
        category=AntiDebugCategory.EXCEPTION,
        description="使用 OutputDebugString 检测调试器存在",
        severity=SeverityLevel.LOW,
        api_calls=["OutputDebugString", "OutputDebugStringA", "OutputDebugStringW"],
        byte_patterns=[],
        code_patterns=[
            r"OutputDebugString.*GetLastError",
            r"SetLastError.*OutputDebugString",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.RETURN_VALUE],
        bypass_code="// Hook OutputDebugString, 始终返回成功",
    ),
    AntiDebugSignature(
        name="RaiseExceptionDetection",
        category=AntiDebugCategory.EXCEPTION,
        description="通过 RaiseException + 异常处理区分调试/非调试状态",
        severity=SeverityLevel.MEDIUM,
        api_calls=["RaiseException", "RtlRaiseException"],
        byte_patterns=[
            bytes([0x6A, 0x00]),  # push 0 (常用于异常参数)
        ],
        code_patterns=[
            r"RaiseException.*0x406D1388",  # MS_VC_EXCEPTION
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.PATCH_CODE],
        bypass_code="// Hook RaiseException, 根据异常代码选择性处理",
    ),

    # ---- 父进程检测 ----
    AntiDebugSignature(
        name="ParentProcessCheck",
        category=AntiDebugCategory.PARENT_PROCESS,
        description="检测父进程是否为 explorer.exe（非调试器启动）",
        severity=SeverityLevel.MEDIUM,
        api_calls=["CreateToolhelp32Snapshot", "Process32First", "Process32Next",
                    "NtQueryInformationProcess"],
        byte_patterns=[],
        code_patterns=[
            r"ParentProcess", r"explorer\.exe",
            r"Process32First", r"Process32Next",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.MEMORY_PATCH],
        bypass_code="// Hook Process32First/Next, 将父进程名改为 explorer.exe",
    ),

    # ---- 内存检测 ----
    AntiDebugSignature(
        name="MemoryBreakpointDetection",
        category=AntiDebugCategory.MEMORY,
        description="检测内存页面保护属性（PAGE_GUARD, PAGE_NOACCESS）",
        severity=SeverityLevel.MEDIUM,
        api_calls=["VirtualQuery", "NtQueryVirtualMemory"],
        byte_patterns=[],
        code_patterns=[
            r"VirtualQuery", r"PAGE_GUARD", r"PAGE_NOACCESS",
            r"PAGE_NOCACHE",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.MEMORY_PATCH],
        bypass_code="// Hook VirtualQuery, 过滤 PAGE_GUARD 和 PAGE_NOACCESS",
    ),
    AntiDebugSignature(
        name="ImageBaseValidation",
        category=AntiDebugCategory.MEMORY,
        description="检测 ImageBase 是否被篡改（重定位/注入）",
        severity=SeverityLevel.MEDIUM,
        api_calls=["GetModuleHandle", "GetModuleHandleA", "GetModuleHandleW"],
        code_patterns=[
            r"ImageBase.*compare", r"base.*address.*check",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.MEMORY_PATCH],
        bypass_code="// Hook GetModuleHandle, 返回原始 ImageBase",
    ),

    # ---- 代码完整性 ----
    AntiDebugSignature(
        name="CodeSectionCRC",
        category=AntiDebugCategory.CODE_INTEGRITY,
        description="对 .text 段进行 CRC32/MD5 校验",
        severity=SeverityLevel.CRITICAL,
        api_calls=[],
        byte_patterns=[
            bytes([0x8D, 0x04]),  # 接近 CRC 表查找模式
        ],
        code_patterns=[
            r"crc32", r"CRC32", r"checksum.*code",
            r"hash.*\.text", r"integrity.*check",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.PATCH_CODE],
        bypass_code="// Hook 校验函数，返回预期的正确值",
    ),
    AntiDebugSignature(
        name="AntiTamperCheck",
        category=AntiDebugCategory.CODE_INTEGRITY,
        description="代码段自修改检测（SMC）",
        severity=SeverityLevel.CRITICAL,
        api_calls=["VirtualProtect", "NtProtectVirtualMemory"],
        code_patterns=[
            r"VirtualProtect.*PAGE_EXECUTE_READWRITE",
            r"self.*modifying", r"smc",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.PATCH_CODE],
        bypass_code="// 在 SMC 完成后重新 Hook，或使用内存断点捕获修改",
    ),

    # ---- 注册表检测 ----
    AntiDebugSignature(
        name="RegistryDebuggerCheck",
        category=AntiDebugCategory.REGISTRY,
        description="检测注册表中的调试器路径",
        severity=SeverityLevel.MEDIUM,
        api_calls=["RegOpenKeyEx", "RegQueryValueEx"],
        byte_patterns=[],
        code_patterns=[
            r"AeDebug", r"Debugger.*path",
            r"Image File Execution Options",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.RETURN_VALUE],
        bypass_code="// Hook RegQueryValueEx, 返回空值或默认值",
    ),

    # ---- 窗口检测 ----
    AntiDebugSignature(
        name="FindWindowDebugger",
        category=AntiDebugCategory.WINDOW,
        description="通过窗口名检测调试器（WinDbg, OllyDbg, x64dbg）",
        severity=SeverityLevel.LOW,
        api_calls=["FindWindow", "FindWindowA", "FindWindowW", "EnumWindows"],
        byte_patterns=[],
        code_patterns=[
            r"FindWindow.*WinDbg", r"FindWindow.*OllyDbg",
            r"FindWindow.*x64dbg", r"FindWindow.*IDA",
            r"EnumWindows",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.RETURN_VALUE],
        bypass_code="// Hook FindWindow, 返回 NULL（窗口未找到）",
    ),

    # ---- 自调试 ----
    AntiDebugSignature(
        name="SelfDebugging",
        category=AntiDebugCategory.DEBUG_OBJECT,
        description="进程尝试自我调试，防止被外部调试器附加",
        severity=SeverityLevel.HIGH,
        api_calls=["DebugActiveProcess", "NtDebugActiveProcess"],
        code_patterns=[
            r"DebugActiveProcess", r"self.*debug",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.PATCH_CODE],
        bypass_code="// Hook DebugActiveProcess, 返回失败",
    ),
    AntiDebugSignature(
        name="BlockInputDetection",
        category=AntiDebugCategory.DEBUG_OBJECT,
        description="检测 BlockInput 防止自动化分析",
        severity=SeverityLevel.LOW,
        api_calls=["BlockInput"],
        code_patterns=[
            r"BlockInput",
        ],
        bypass_strategies=[BypassStrategy.HOOK_API, BypassStrategy.RETURN_VALUE],
        bypass_code="// Hook BlockInput, 返回 TRUE（假装成功）",
    ),
]


# ============================================================
# 反调试检测器
# ============================================================

class AntiDebugDetector:
    """
    反调试技术检测器
    
    扫描二进制代码，识别各类反调试技术：
    - 进程信息检测 (PEB, DebugPort, etc.)
    - 断点检测 (硬件/软件)
    - 时间检测 (RDTSC, GetTickCount)
    - 异常处理 (INT 3, INT 2D, SEH)
    - 内存检测 (Guard Page, ImageBase)
    - 代码完整性 (CRC, SMC)
    - 窗口/注册表检测
    """

    def __init__(self):
        self._data: bytes = b""
        self._signatures = ANTI_DEBUG_SIGNATURES
        self._results: List[DetectionResult] = []

    def load_data(self, data: bytes):
        """加载二进制数据"""
        self._data = data
        self._results.clear()

    def load_file(self, file_path: str) -> Dict[str, Any]:
        """从文件加载"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}
        try:
            with open(file_path, "rb") as f:
                self._data = f.read()
            return {"success": True, "file": file_path, "size": len(self._data)}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def scan_all(self) -> List[DetectionResult]:
        """执行全面扫描"""
        self._results = []
        if not self._data:
            return self._results

        for sig in self._signatures:
            result = self._scan_signature(sig)
            self._results.append(result)

        return self._results

    def scan_category(self, category: AntiDebugCategory) -> List[DetectionResult]:
        """按分类扫描"""
        results = []
        for sig in self._signatures:
            if sig.category == category:
                results.append(self._scan_signature(sig))
        return results

    def scan_by_name(self, name: str) -> Optional[DetectionResult]:
        """按名称扫描特定技术"""
        for sig in self._signatures:
            if sig.name.lower() == name.lower():
                return self._scan_signature(sig)
        return None

    def _scan_signature(self, sig: AntiDebugSignature) -> DetectionResult:
        """扫描单个签名"""
        locations = []
        confidence = 0.0
        evidence_parts = []

        # 1. 字节模式匹配
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
                evidence_parts.append(f"字节模式匹配: {pattern.hex()}")

        # 2. 代码模式匹配（正则表达式）
        try:
            text = self._data.decode("ascii", errors="ignore")
        except:
            text = ""

        for pattern in sig.code_patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    confidence += 0.2
                    evidence_parts.append(f"代码模式匹配: {pattern}")
            except re.error:
                pass

        # 3. API 调用匹配
        for api in sig.api_calls:
            try:
                api_bytes = api.encode("ascii")
                if api_bytes in self._data:
                    confidence += 0.25
                    evidence_parts.append(f"API 引用: {api}")
            except:
                pass

        # 4. 组合模式加权
        if confidence > 0:
            # 额外加权：多种证据同时出现
            if len(evidence_parts) >= 2:
                confidence += 0.1
            if len(evidence_parts) >= 3:
                confidence += 0.1

        confidence = min(confidence, 1.0)
        detected = confidence >= 0.3

        # 生成绕过建议
        bypass_suggestion = self._generate_bypass_suggestion(sig, detected)

        return DetectionResult(
            signature=sig,
            detected=detected,
            confidence=round(confidence, 2),
            locations=sorted(locations),
            evidence="; ".join(evidence_parts) if evidence_parts else "无",
            bypass_suggestion=bypass_suggestion,
        )

    def _generate_bypass_suggestion(self, sig: AntiDebugSignature, detected: bool) -> str:
        """生成绕过建议"""
        if not detected:
            return "无需绕过"

        strategies = {
            BypassStrategy.PATCH_CODE: "将检测代码替换为 NOP 指令",
            BypassStrategy.HOOK_API: "Hook 相关 API 函数，返回假值",
            BypassStrategy.MEMORY_PATCH: "直接修改内存中的检测标志",
            BypassStrategy.RETURN_VALUE: "修改 API 返回值",
            BypassStrategy.NOP_OUT: "用 NOP 填充检测代码区域",
            BypassStrategy.JMP_OVER: "使用 JMP 跳过检测逻辑",
            BypassStrategy.REGISTER_MODIFY: "在调用返回后修改寄存器值",
            BypassStrategy.TIMING_SPOOF: "欺骗时间检测，返回相近值",
            BypassStrategy.TITAN_HIDE: "使用内核级 TitanHide 驱动隐藏",
            BypassStrategy.SCYLLA_HIDE: "使用 ScyllaHide 插件隐藏调试器",
        }

        parts = []
        for strategy in sig.bypass_strategies:
            desc = strategies.get(strategy, strategy.value)
            parts.append(f"[{strategy.value}] {desc}")

        if sig.bypass_code:
            parts.append(f"\n// 示例代码:\n{sig.bypass_code}")

        return "\n".join(parts)

    def get_summary(self) -> Dict[str, Any]:
        """获取扫描摘要"""
        if not self._results:
            return {"total": 0, "detected": 0, "by_category": {}, "risk_score": 0}

        by_category = defaultdict(lambda: {"total": 0, "detected": 0})
        for r in self._results:
            cat = r.signature.category.value
            by_category[cat]["total"] += 1
            if r.detected:
                by_category[cat]["detected"] += 1

        # 风险评分
        severity_weights = {
            SeverityLevel.CRITICAL: 25,
            SeverityLevel.HIGH: 15,
            SeverityLevel.MEDIUM: 8,
            SeverityLevel.LOW: 3,
            SeverityLevel.INFO: 1,
        }
        risk_score = sum(
            severity_weights.get(r.signature.severity, 5) * r.confidence
            for r in self._results if r.detected
        )
        risk_score = min(risk_score, 100)

        return {
            "total": len(self._results),
            "detected": sum(1 for r in self._results if r.detected),
            "by_category": dict(by_category),
            "risk_score": round(risk_score, 1),
        }


# ============================================================
# 绕过策略生成器
# ============================================================

class BypassGenerator:
    """
    绕过策略生成器
    
    为检测到的反调试技术生成具体的绕过方案：
    - 代码补丁生成
    - API Hook 代码生成
    - 内存补丁方案
    - 综合绕过计划
    """

    def __init__(self):
        self._detector = AntiDebugDetector()

    def generate_bypass_plan(self, data: bytes) -> Dict[str, Any]:
        """生成完整的绕过方案"""
        self._detector.load_data(data)
        results = self._detector.scan_all()
        summary = self._detector.get_summary()

        if not results or summary["detected"] == 0:
            return {
                "success": True,
                "message": "未检测到反调试技术",
                "risk_score": 0,
                "steps": [],
            }

        steps = []
        # 按严重程度排序
        severity_order = {SeverityLevel.CRITICAL: 0, SeverityLevel.HIGH: 1,
                          SeverityLevel.MEDIUM: 2, SeverityLevel.LOW: 3, SeverityLevel.INFO: 4}

        sorted_results = sorted(
            [r for r in results if r.detected],
            key=lambda r: (severity_order.get(r.signature.severity, 99), -r.confidence)
        )

        for r in sorted_results:
            step = {
                "name": r.signature.name,
                "category": r.signature.category.value,
                "severity": r.signature.severity.value,
                "confidence": r.confidence,
                "strategies": [s.value for s in r.signature.bypass_strategies],
                "bypass_code": r.signature.bypass_code,
                "description": r.signature.description,
            }
            steps.append(step)

        return {
            "success": True,
            "message": f"检测到 {summary['detected']} 项反调试技术",
            "risk_score": summary["risk_score"],
            "total_detected": summary["detected"],
            "steps": steps,
            "recommended_order": ["ScyllaHide/TitanHide 驱动隐藏"] +
                                 [s["name"] for s in steps if s["severity"] in ("critical", "high")] +
                                 [s["name"] for s in steps if s["severity"] in ("medium", "low")],
        }

    def generate_patch_code(self, detection_name: str) -> Dict[str, Any]:
        """为特定检测生成补丁代码"""
        for sig in ANTI_DEBUG_SIGNATURES:
            if sig.name.lower() == detection_name.lower():
                return {
                    "success": True,
                    "name": sig.name,
                    "description": sig.description,
                    "bypass_strategies": [s.value for s in sig.bypass_strategies],
                    "bypass_code": sig.bypass_code,
                    "references": sig.references,
                }
        return {"success": False, "message": f"未找到检测技术: {detection_name}"}

    def generate_hook_script(self, results: List[DetectionResult]) -> str:
        """生成综合 Hook 脚本"""
        lines = ["// 自动生成的反反调试 Hook 脚本", "// 使用 MinHook 或 Detours 库", ""]
        lines.append("#include <Windows.h>")
        lines.append("#include <MinHook.h>")
        lines.append("")

        api_hooks = set()
        for r in results:
            if r.detected:
                for api in r.signature.api_calls:
                    api_hooks.add(api)

        for api in sorted(api_hooks):
            lines.append(f"// Hook {api}")

        lines.append("")
        lines.append("BOOL InstallAntiAntiDebug() {")
        lines.append("    MH_Initialize();")
        for api in sorted(api_hooks):
            lines.append(f"    // MH_CreateHook(&{api}, &Hook_{api}, (LPVOID*)&Original_{api});")
            lines.append(f"    // MH_EnableHook(&{api});")
        lines.append("    return TRUE;")
        lines.append("}")

        return "\n".join(lines)


# ============================================================
# 完整性校验分析器
# ============================================================

class IntegrityChecker:
    """
    完整性校验分析器
    
    检测代码中的完整性校验机制：
    - CRC32/MD5/SHA 代码校验
    - 段哈希比对
    - 反篡改检测
    - SMC (Self-Modifying Code) 检测
    """

    # CRC32 查找表特征
    CRC32_TABLE_PATTERN = bytes([0x00, 0x00, 0x00, 0x00,
                                  0x77, 0x07, 0x30, 0x96])  # CRC32 表前 8 字节

    def __init__(self):
        self._data: bytes = b""

    def load_data(self, data: bytes):
        self._data = data

    def scan_integrity_checks(self) -> List[IntegrityCheck]:
        """扫描完整性校验"""
        checks = []

        # 1. 检测 CRC32
        crc_checks = self._detect_crc32()
        checks.extend(crc_checks)

        # 2. 检测 MD5
        md5_checks = self._detect_md5()
        checks.extend(md5_checks)

        # 3. 检测 SHA
        sha_checks = self._detect_sha()
        checks.extend(sha_checks)

        # 4. 检测 SMC
        smc_checks = self._detect_smc()
        checks.extend(smc_checks)

        # 5. 检测通用校验模式
        generic_checks = self._detect_generic_checksum()
        checks.extend(generic_checks)

        return checks

    def _detect_crc32(self) -> List[IntegrityCheck]:
        """检测 CRC32 校验"""
        checks = []
        if not self._data:
            return checks

        # 查找 CRC32 查找表
        pos = 0
        while True:
            idx = self._data.find(self.CRC32_TABLE_PATTERN, pos)
            if idx == -1:
                break

            checks.append(IntegrityCheck(
                name=f"CRC32_Check_{len(checks)}",
                check_type="crc32",
                target_range=(idx, idx + 1024),
                algorithm="CRC32",
                code_location=idx,
            ))
            pos = idx + 1

        return checks

    def _detect_md5(self) -> List[IntegrityCheck]:
        """检测 MD5 校验"""
        checks = []
        if not self._data:
            return checks

        # MD5 初始化常量
        md5_init = [
            bytes([0x01, 0x23, 0x45, 0x67]),  # A
            bytes([0x89, 0xAB, 0xCD, 0xEF]),  # B
            bytes([0xFE, 0xDC, 0xBA, 0x98]),  # C
            bytes([0x76, 0x54, 0x32, 0x10]),  # D
        ]

        for init_val in md5_init:
            pos = 0
            while True:
                idx = self._data.find(init_val, pos)
                if idx == -1:
                    break
                checks.append(IntegrityCheck(
                    name=f"MD5_Check_{len(checks)}",
                    check_type="md5",
                    target_range=(max(0, idx - 256), idx + 512),
                    algorithm="MD5",
                    code_location=idx,
                ))
                pos = idx + 1

        return checks

    def _detect_sha(self) -> List[IntegrityCheck]:
        """检测 SHA 校验"""
        checks = []
        if not self._data:
            return checks

        # SHA256 初始化常量 (前 8 字节)
        sha256_init = bytes([
            0x6A, 0x09, 0xE6, 0x67,  # H0
            0xBB, 0x67, 0xAE, 0x85,  # H1
        ])

        pos = 0
        while True:
            idx = self._data.find(sha256_init, pos)
            if idx == -1:
                break
            checks.append(IntegrityCheck(
                name=f"SHA256_Check_{len(checks)}",
                check_type="sha256",
                target_range=(max(0, idx - 256), idx + 512),
                algorithm="SHA256",
                code_location=idx,
            ))
            pos = idx + 1

        return checks

    def _detect_smc(self) -> List[IntegrityCheck]:
        """检测 SMC (Self-Modifying Code)"""
        checks = []
        if not self._data:
            return checks

        # VirtualProtect 调用 + PAGE_EXECUTE_READWRITE
        vp_pattern = bytes([0x40, 0x00, 0x00, 0x00])  # PAGE_EXECUTE_READWRITE = 0x40

        pos = 0
        while True:
            idx = self._data.find(vp_pattern, pos)
            if idx == -1:
                break

            # 检查附近是否有 VirtualProtect 调用
            area = self._data[max(0, idx - 50):idx + 50]
            if b"VirtualProtect" in area or b"VirtualProtect" in area:
                checks.append(IntegrityCheck(
                    name=f"SMC_Check_{len(checks)}",
                    check_type="smc",
                    target_range=(max(0, idx - 100), idx + 100),
                    algorithm="SMC",
                    code_location=idx,
                ))
            pos = idx + 1

        return checks

    def _detect_generic_checksum(self) -> List[IntegrityCheck]:
        """检测通用校验模式"""
        checks = []
        if not self._data:
            return checks

        try:
            text = self._data.decode("ascii", errors="ignore")
        except:
            return checks

        patterns = [
            (r"checksum", "checksum"),
            (r"integrity", "integrity"),
            (r"hash.*check", "hash_check"),
            (r"verify.*code", "code_verify"),
            (r"anti.*tamper", "anti_tamper"),
        ]

        for pattern, ctype in patterns:
            try:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    start = max(0, match.start() - 200)
                    end = min(len(self._data), match.end() + 200)
                    checks.append(IntegrityCheck(
                        name=f"Generic_{ctype}_{len(checks)}",
                        check_type=ctype,
                        target_range=(start, end),
                        algorithm="generic",
                        code_location=match.start(),
                    ))
            except re.error:
                pass

        return checks

    def verify_integrity(self, expected_checks: List[IntegrityCheck]) -> List[IntegrityCheck]:
        """验证指定区域的完整性"""
        results = []
        for check in expected_checks:
            start, end = check.target_range
            actual_data = self._data[start:end]

            if check.check_type == "crc32":
                actual = format(zlib.crc32(actual_data) & 0xFFFFFFFF, "08x")
            elif check.check_type == "md5":
                actual = hashlib.md5(actual_data).hexdigest()
            elif check.check_type == "sha256":
                actual = hashlib.sha256(actual_data).hexdigest()
            else:
                actual = hashlib.md5(actual_data).hexdigest()[:8]

            check.actual_value = actual
            check.is_patched = (check.expected_value != "" and check.expected_value != actual)
            results.append(check)

        return results


# ============================================================
# 反反调试引擎主入口
# ============================================================

class AntiDebugEngine:
    """
    反调试与反反调试引擎（主入口）
    
    整合检测、绕过、完整性校验三大子系统：
    - 20+ 反调试技术识别
    - 自动绕过策略生成
    - 完整性校验检测与对抗
    """

    def __init__(self):
        self.detector = AntiDebugDetector()
        self.bypass = BypassGenerator()
        self.integrity = IntegrityChecker()

    def analyze(self, file_path: str) -> Dict[str, Any]:
        """综合分析二进制文件的反调试机制"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            return {"success": False, "message": str(e)}

        # 1. 反调试检测
        self.detector.load_data(data)
        results = self.detector.scan_all()
        summary = self.detector.get_summary()

        # 2. 完整性校验分析
        self.integrity.load_data(data)
        integrity_checks = self.integrity.scan_integrity_checks()

        # 3. 绕过方案
        bypass_plan = self.bypass.generate_bypass_plan(data)

        # 按严重程度分类
        detected_critical = [r for r in results if r.detected and r.signature.severity == SeverityLevel.CRITICAL]
        detected_high = [r for r in results if r.detected and r.signature.severity == SeverityLevel.HIGH]
        detected_medium = [r for r in results if r.detected and r.signature.severity == SeverityLevel.MEDIUM]
        detected_low = [r for r in results if r.detected and r.signature.severity == SeverityLevel.LOW]

        return {
            "success": True,
            "file": os.path.basename(file_path),
            "file_size": len(data),
            "risk_score": summary["risk_score"],
            "summary": {
                "total_signatures": summary["total"],
                "detected_count": summary["detected"],
                "by_category": summary["by_category"],
                "critical": len(detected_critical),
                "high": len(detected_high),
                "medium": len(detected_medium),
                "low": len(detected_low),
            },
            "detected": [
                {
                    "name": r.signature.name,
                    "category": r.signature.category.value,
                    "severity": r.signature.severity.value,
                    "confidence": r.confidence,
                    "locations": r.locations[:5],
                    "evidence": r.evidence,
                    "bypass": r.bypass_suggestion,
                }
                for r in results if r.detected
            ],
            "integrity_checks": [
                {
                    "name": c.name,
                    "type": c.check_type,
                    "algorithm": c.algorithm,
                    "target_range": list(c.target_range),
                    "code_location": c.code_location,
                }
                for c in integrity_checks
            ],
            "bypass_plan": bypass_plan.get("steps", []),
            "recommended_order": bypass_plan.get("recommended_order", []),
        }

    def scan_anti_debug(self, file_path: str, category: str = "") -> Dict[str, Any]:
        """扫描反调试技术"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            return {"success": False, "message": str(e)}

        self.detector.load_data(data)

        if category:
            try:
                cat = AntiDebugCategory(category)
                results = self.detector.scan_category(cat)
            except ValueError:
                valid = [c.value for c in AntiDebugCategory]
                return {"success": False, "message": f"无效分类，有效值: {valid}"}
        else:
            results = self.detector.scan_all()

        return {
            "success": True,
            "file": os.path.basename(file_path),
            "results": [
                {
                    "name": r.signature.name,
                    "category": r.signature.category.value,
                    "detected": r.detected,
                    "confidence": r.confidence,
                    "severity": r.signature.severity.value,
                    "description": r.signature.description,
                    "evidence": r.evidence,
                    "locations": r.locations[:5],
                }
                for r in results
            ],
            "summary": self.detector.get_summary(),
        }

    def scan_integrity(self, file_path: str) -> Dict[str, Any]:
        """扫描完整性校验"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            return {"success": False, "message": str(e)}

        self.integrity.load_data(data)
        checks = self.integrity.scan_integrity_checks()

        return {
            "success": True,
            "file": os.path.basename(file_path),
            "total_checks": len(checks),
            "checks": [
                {
                    "name": c.name,
                    "type": c.check_type,
                    "algorithm": c.algorithm,
                    "target_range": list(c.target_range),
                    "code_location": c.code_location,
                }
                for c in checks
            ],
        }

    def generate_bypass(self, file_path: str) -> Dict[str, Any]:
        """生成绕过方案"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            return {"success": False, "message": str(e)}

        return self.bypass.generate_bypass_plan(data)

    def get_bypass_code(self, detection_name: str) -> Dict[str, Any]:
        """获取特定检测的绕过代码"""
        return self.bypass.generate_patch_code(detection_name)

    def list_signatures(self, category: str = "") -> Dict[str, Any]:
        """列出所有已知反调试签名"""
        sigs = []
        for sig in ANTI_DEBUG_SIGNATURES:
            if category and sig.category.value != category:
                continue
            sigs.append({
                "name": sig.name,
                "category": sig.category.value,
                "severity": sig.severity.value,
                "description": sig.description,
                "bypass_strategies": [s.value for s in sig.bypass_strategies],
            })

        return {
            "success": True,
            "total": len(sigs),
            "signatures": sigs,
            "categories": [c.value for c in AntiDebugCategory],
        }

    def get_statistics(self) -> Dict[str, Any]:
        """获取签名统计"""
        by_category = defaultdict(int)
        by_severity = defaultdict(int)

        for sig in ANTI_DEBUG_SIGNATURES:
            by_category[sig.category.value] += 1
            by_severity[sig.severity.value] += 1

        strategies = defaultdict(int)
        for sig in ANTI_DEBUG_SIGNATURES:
            for s in sig.bypass_strategies:
                strategies[s.value] += 1

        return {
            "total_signatures": len(ANTI_DEBUG_SIGNATURES),
            "by_category": dict(by_category),
            "by_severity": dict(by_severity),
            "bypass_strategies": dict(strategies),
        }


# ============================================================
# 便捷函数
# ============================================================

def quick_scan(file_path: str) -> Dict[str, Any]:
    """快速扫描文件的反调试机制"""
    engine = AntiDebugEngine()
    return engine.analyze(file_path)


def quick_bypass(file_path: str) -> Dict[str, Any]:
    """快速生成绕过方案"""
    engine = AntiDebugEngine()
    return engine.generate_bypass(file_path)


def detect_single(file_path: str, technique_name: str) -> Dict[str, Any]:
    """检测单个反调试技术"""
    engine = AntiDebugEngine()
    if not os.path.exists(file_path):
        return {"success": False, "message": f"文件不存在: {file_path}"}
    with open(file_path, "rb") as f:
        data = f.read()
    engine.detector.load_data(data)
    result = engine.detector.scan_by_name(technique_name)
    if result is None:
        return {"success": False, "message": f"未找到技术: {technique_name}"}
    return {
        "success": True,
        "name": result.signature.name,
        "detected": result.detected,
        "confidence": result.confidence,
        "evidence": result.evidence,
        "bypass": result.bypass_suggestion,
    }