"""
代码注入与DLL劫持引擎 (Code Injection & DLL Hijacking Engine)
提供全面的进程注入、代码Hook、DLL劫持分析与代码洞穴扫描功能。

引擎突破 15: 支持多种注入策略、Hook生成、代理DLL创建、安全分析
"""

import os
import re
import struct
import hashlib
import json
from typing import Dict, List, Optional, Tuple, Set, Any, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict


# ============================================================
# 枚举定义
# ============================================================

class InjectionMethod(Enum):
    """注入方法"""
    CREATE_REMOTE_THREAD = "create_remote_thread"
    SET_WINDOWS_HOOK = "set_windows_hook"
    QUEUE_USER_APC = "queue_user_apc"
    THREAD_HIJACKING = "thread_hijacking"
    REFLECTIVE_DLL = "reflective_dll"
    PROCESS_HOLLOWING = "process_hollowing"
    ATOM_BOMBING = "atom_bombing"
    MANUAL_MAP = "manual_map"


class HookType(Enum):
    """Hook 类型"""
    INLINE = "inline"           # 内联 Hook (修改函数开头)
    IAT = "iat"                 # IAT Hook
    EAT = "eat"                 # EAT Hook
    VTABLE = "vtable"           # 虚表 Hook
    DETOUR = "detour"           # Detour (跳转)
    HOT_PATCH = "hot_patch"     # 热补丁
    VEH = "veh"                 # 向量化异常处理 Hook
    HARDWARE_BP = "hw_bp"       # 硬件断点 Hook


class MemoryProtection(Enum):
    """内存保护"""
    READ = "PAGE_READONLY"
    READ_WRITE = "PAGE_READWRITE"
    EXECUTE = "PAGE_EXECUTE"
    EXECUTE_READ = "PAGE_EXECUTE_READ"
    EXECUTE_READ_WRITE = "PAGE_EXECUTE_READWRITE"
    NO_ACCESS = "PAGE_NOACCESS"
    GUARD = "PAGE_GUARD"


class DllHijackMethod(Enum):
    """DLL 劫持方法"""
    SEARCH_ORDER = "search_order"       # 搜索顺序劫持
    PROXY_DLL = "proxy_dll"             # 代理 DLL
    PHANTOM_DLL = "phantom_dll"         # 幻影 DLL
    COM_HIJACK = "com_hijack"           # COM 劫持
    SIDEBY_SIDE = "side_by_side"        # 并行配置劫持
    PATH_REDIRECTION = "path_redirection"  # 路径重定向


class SecurityMeasure(Enum):
    """安全措施"""
    ANTI_DEBUG = "anti_debug"
    INTEGRITY_CHECK = "integrity_check"
    MODULE_CHECK = "module_check"
    MEMORY_SCAN = "memory_scan"
    TIMING_CHECK = "timing_check"
    CODE_SIGNING = "code_signing"
    OBFUSCATION = "obfuscation"
    PACKER = "packer"


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class ProcessInfo:
    """进程信息"""
    pid: int
    name: str
    path: str = ""
    is_64bit: bool = True
    modules: List["ModuleInfo"] = field(default_factory=list)
    security_measures: List[SecurityMeasure] = field(default_factory=list)


@dataclass
class ModuleInfo:
    """模块信息"""
    name: str
    base_address: int = 0
    size: int = 0
    path: str = ""
    exports: List["ExportInfo"] = field(default_factory=list)
    imports: List["ImportInfo"] = field(default_factory=list)
    sections: List["SectionInfo"] = field(default_factory=list)


@dataclass
class ExportInfo:
    """导出函数信息"""
    name: str
    ordinal: int = 0
    rva: int = 0
    forwarded: bool = False
    forward_target: str = ""


@dataclass
class ImportInfo:
    """导入函数信息"""
    name: str
    module_name: str
    ordinal: int = 0
    hint: int = 0
    iat_rva: int = 0


@dataclass
class SectionInfo:
    """节区信息"""
    name: str
    virtual_address: int = 0
    virtual_size: int = 0
    raw_size: int = 0
    characteristics: int = 0
    is_executable: bool = False
    is_writable: bool = False
    is_readable: bool = False


@dataclass
class CodeCave:
    """代码洞穴"""
    address: int
    size: int
    section: str = ""
    alignment: int = 1
    near_function: str = ""
    near_function_rva: int = 0


@dataclass
class HookTemplate:
    """Hook 模板"""
    hook_type: HookType
    target_function: str
    target_module: str = ""
    target_rva: int = 0
    detour_function: str = ""
    trampoline: bytes = b""
    hook_code: bytes = b""
    hook_size: int = 0
    original_bytes: bytes = b""
    patches: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class InjectionPlan:
    """注入计划"""
    method: InjectionMethod
    target_process: str = ""
    dll_path: str = ""
    entry_point: str = ""
    priority: int = 50
    stealth_level: int = 50
    risk_level: int = 50
    steps: List[str] = field(default_factory=list)
    required_permissions: List[str] = field(default_factory=list)
    alternatives: List[InjectionMethod] = field(default_factory=list)
    notes: str = ""


@dataclass
class DllHijackOpportunity:
    """DLL 劫持机会"""
    dll_name: str
    method: DllHijackMethod
    load_path: str = ""
    priority: int = 50
    is_signed: bool = False
    is_known_dll: bool = False
    dependencies: List[str] = field(default_factory=list)
    risk_assessment: str = ""
    exploit_guide: str = ""


@dataclass
class SecurityReport:
    """安全分析报告"""
    measures_detected: List[Dict[str, Any]] = field(default_factory=list)
    bypass_suggestions: List[Dict[str, Any]] = field(default_factory=list)
    risk_score: int = 0
    overall_assessment: str = ""


# ============================================================
# 进程分析器
# ============================================================

class ProcessAnalyzer:
    """
    进程分析器
    分析目标进程的模块、导出/导入、安全措施
    """

    KNOWN_SECURITY_MODULES = {
        "easyanticheat": SecurityMeasure.ANTI_DEBUG,
        "eac": SecurityMeasure.ANTI_DEBUG,
        "battleye": SecurityMeasure.ANTI_DEBUG,
        "be": SecurityMeasure.ANTI_DEBUG,
        "xigncode": SecurityMeasure.ANTI_DEBUG,
        "xigncode3": SecurityMeasure.ANTI_DEBUG,
        "nprotect": SecurityMeasure.ANTI_DEBUG,
        "gameguard": SecurityMeasure.ANTI_DEBUG,
        "hackshield": SecurityMeasure.ANTI_DEBUG,
        "punkbuster": SecurityMeasure.ANTI_DEBUG,
        "warden": SecurityMeasure.MEMORY_SCAN,
        "vanguard": SecurityMeasure.ANTI_DEBUG,
        "faceit": SecurityMeasure.ANTI_DEBUG,
        "esl": SecurityMeasure.ANTI_DEBUG,
        "denuvo": SecurityMeasure.OBFUSCATION,
        "vmprotect": SecurityMeasure.OBFUSCATION,
        "themida": SecurityMeasure.OBFUSCATION,
        "obsidium": SecurityMeasure.OBFUSCATION,
    }

    def __init__(self):
        self._processes: Dict[int, ProcessInfo] = {}
        self._known_exports: Dict[str, List[ExportInfo]] = defaultdict(list)

    def analyze_process(self, process_name: str, pid: int = 0) -> ProcessInfo:
        """分析进程"""
        info = ProcessInfo(pid=pid, name=process_name)
        info.modules = self._enumerate_expected_modules(process_name)
        info.security_measures = self._detect_security_measures(info.modules, process_name)
        return info

    def _enumerate_expected_modules(self, process_name: str) -> List[ModuleInfo]:
        """枚举预期模块"""
        modules = []

        # 系统模块
        system_dlls = [
            "ntdll.dll", "kernel32.dll", "kernelbase.dll",
            "user32.dll", "gdi32.dll", "advapi32.dll",
            "shell32.dll", "ole32.dll", "comctl32.dll",
            "ws2_32.dll", "winmm.dll", "d3d9.dll",
            "d3d11.dll", "d3d12.dll", "dxgi.dll",
            "msvcrt.dll", "vcruntime140.dll", "msvcp140.dll",
        ]

        for dll in system_dlls:
            mod = ModuleInfo(name=dll, path=f"C:\\Windows\\System32\\{dll}")
            mod.exports = self._get_known_exports(dll)
            modules.append(mod)

        return modules

    def _get_known_exports(self, dll_name: str) -> List[ExportInfo]:
        """获取已知导出函数"""
        if dll_name in self._known_exports:
            return self._known_exports[dll_name]

        exports = []
        known = {
            "kernel32.dll": [
                "LoadLibraryA", "LoadLibraryW", "GetProcAddress",
                "VirtualAlloc", "VirtualFree", "VirtualProtect",
                "CreateRemoteThread", "WriteProcessMemory", "ReadProcessMemory",
                "OpenProcess", "CloseHandle", "CreateThread",
                "GetModuleHandleA", "GetModuleHandleW", "GetCurrentProcess",
                "WaitForSingleObject", "CreateFileA", "CreateFileW",
                "Sleep", "ExitProcess", "TerminateProcess",
            ],
            "ntdll.dll": [
                "NtCreateThreadEx", "NtWriteVirtualMemory", "NtReadVirtualMemory",
                "NtProtectVirtualMemory", "NtAllocateVirtualMemory",
                "NtQueryInformationProcess", "NtSetInformationThread",
                "LdrLoadDll", "RtlCreateUserThread", "NtUnmapViewOfSection",
                "NtMapViewOfSection", "NtCreateSection",
            ],
            "user32.dll": [
                "MessageBoxA", "MessageBoxW", "SetWindowsHookExA",
                "SetWindowsHookExW", "UnhookWindowsHookEx",
                "GetMessageA", "GetMessageW", "PeekMessageA",
                "CallNextHookEx", "FindWindowA", "FindWindowW",
                "GetWindowThreadProcessId", "SetWindowLongA",
            ],
            "ws2_32.dll": [
                "send", "recv", "connect", "bind", "listen",
                "accept", "WSAStartup", "WSACleanup", "socket",
                "select", "closesocket", "WSASend", "WSARecv",
            ],
        }

        for name in known.get(dll_name, []):
            exports.append(ExportInfo(name=name))

        self._known_exports[dll_name] = exports
        return exports

    def _detect_security_measures(self, modules: List[ModuleInfo],
                                 process_name: str = "") -> List[SecurityMeasure]:
        """检测安全措施"""
        measures = set()
        for mod in modules:
            name_lower = mod.name.lower().replace(".dll", "").replace(".sys", "").replace(".exe", "")
            for keyword, measure in self.KNOWN_SECURITY_MODULES.items():
                if keyword in name_lower:
                    measures.add(measure)

        # 也检查进程名
        if process_name:
            proc_lower = process_name.lower().replace(".exe", "")
            for keyword, measure in self.KNOWN_SECURITY_MODULES.items():
                if keyword in proc_lower:
                    measures.add(measure)

        return list(measures)

    def enumerate_modules(self, process_name: str) -> List[ModuleInfo]:
        """枚举模块（模拟）"""
        return self._enumerate_expected_modules(process_name)

    def find_module(self, process_name: str, module_name: str) -> Optional[ModuleInfo]:
        """查找模块"""
        modules = self.enumerate_modules(process_name)
        for mod in modules:
            if mod.name.lower() == module_name.lower():
                return mod
        return None

    def get_imports(self, module_name: str) -> List[ImportInfo]:
        """获取导入函数"""
        known_imports = {
            "kernel32.dll": [
                ImportInfo("LoadLibraryA", "kernel32.dll"),
                ImportInfo("GetProcAddress", "kernel32.dll"),
                ImportInfo("VirtualAlloc", "kernel32.dll"),
                ImportInfo("VirtualProtect", "kernel32.dll"),
                ImportInfo("CreateThread", "kernel32.dll"),
                ImportInfo("WriteProcessMemory", "kernel32.dll"),
            ],
            "ntdll.dll": [
                ImportInfo("NtCreateThreadEx", "ntdll.dll"),
                ImportInfo("NtWriteVirtualMemory", "ntdll.dll"),
                ImportInfo("NtProtectVirtualMemory", "ntdll.dll"),
            ],
        }
        return known_imports.get(module_name, [])


# ============================================================
# 注入策略规划器
# ============================================================

class InjectionPlanner:
    """
    注入策略规划器
    根据目标进程特征规划最佳注入方案
    """

    METHOD_RISK = {
        InjectionMethod.CREATE_REMOTE_THREAD: 30,
        InjectionMethod.SET_WINDOWS_HOOK: 40,
        InjectionMethod.QUEUE_USER_APC: 50,
        InjectionMethod.THREAD_HIJACKING: 60,
        InjectionMethod.REFLECTIVE_DLL: 70,
        InjectionMethod.PROCESS_HOLLOWING: 80,
        InjectionMethod.ATOM_BOMBING: 85,
        InjectionMethod.MANUAL_MAP: 75,
    }

    METHOD_STEALTH = {
        InjectionMethod.CREATE_REMOTE_THREAD: 20,
        InjectionMethod.SET_WINDOWS_HOOK: 30,
        InjectionMethod.QUEUE_USER_APC: 50,
        InjectionMethod.THREAD_HIJACKING: 70,
        InjectionMethod.REFLECTIVE_DLL: 80,
        InjectionMethod.PROCESS_HOLLOWING: 85,
        InjectionMethod.ATOM_BOMBING: 90,
        InjectionMethod.MANUAL_MAP: 95,
    }

    def __init__(self):
        self._analyzer = ProcessAnalyzer()

    def plan_injection(self, target_process: str, dll_path: str = "",
                       prefer_stealth: bool = True) -> List[InjectionPlan]:
        """规划注入策略"""
        process_info = self._analyzer.analyze_process(target_process)
        plans = []

        for method in InjectionMethod:
            plan = self._create_plan(method, target_process, dll_path, process_info)
            plans.append(plan)

        # 排序: 隐形优先或低风险优先
        if prefer_stealth:
            plans.sort(key=lambda p: p.stealth_level, reverse=True)
        else:
            plans.sort(key=lambda p: p.risk_level)

        return plans

    def _create_plan(self, method: InjectionMethod, target: str,
                     dll_path: str, process_info: ProcessInfo) -> InjectionPlan:
        """创建注入计划"""
        plan = InjectionPlan(
            method=method,
            target_process=target,
            dll_path=dll_path,
            risk_level=self.METHOD_RISK.get(method, 50),
            stealth_level=self.METHOD_STEALTH.get(method, 50),
        )

        steps = {
            InjectionMethod.CREATE_REMOTE_THREAD: [
                "1. OpenProcess(PROCESS_ALL_ACCESS) 获取进程句柄",
                "2. VirtualAllocEx() 在目标进程中分配内存",
                "3. WriteProcessMemory() 写入 DLL 路径",
                "4. GetProcAddress() 获取 LoadLibraryA 地址",
                "5. CreateRemoteThread() 创建远程线程执行 LoadLibrary",
                "6. WaitForSingleObject() 等待线程完成",
                "7. VirtualFreeEx() 清理分配的内存",
                "8. CloseHandle() 关闭句柄",
            ],
            InjectionMethod.SET_WINDOWS_HOOK: [
                "1. LoadLibrary() 加载包含 Hook 过程的 DLL",
                "2. GetProcAddress() 获取 Hook 过程地址",
                "3. GetWindowThreadProcessId() 获取目标线程 ID",
                "4. SetWindowsHookEx() 设置全局消息钩子",
                "5. 目标进程处理消息时自动加载 DLL",
                "6. UnhookWindowsHookEx() 清理钩子",
            ],
            InjectionMethod.QUEUE_USER_APC: [
                "1. OpenProcess() 获取进程句柄",
                "2. VirtualAllocEx() 分配内存",
                "3. WriteProcessMemory() 写入 Shellcode 和 DLL 路径",
                "4. 枚举目标进程所有线程",
                "5. OpenThread() 获取每个线程句柄",
                "6. QueueUserAPC() 为每个线程排队 APC",
                "7. 线程进入 alertable 状态时执行 Shellcode",
            ],
            InjectionMethod.THREAD_HIJACKING: [
                "1. OpenProcess() 获取进程句柄",
                "2. VirtualAllocEx() 分配内存",
                "3. WriteProcessMemory() 写入 Shellcode",
                "4. 枚举目标进程线程",
                "5. SuspendThread() 挂起目标线程",
                "6. GetThreadContext() 保存线程上下文",
                "7. SetThreadContext() 修改 RIP 指向 Shellcode",
                "8. ResumeThread() 恢复线程执行",
                "9. Shellcode 执行后恢复原始上下文",
            ],
            InjectionMethod.REFLECTIVE_DLL: [
                "1. 编写自反射加载器 (ReflectiveLoader)",
                "2. 将 DLL 和加载器打包为 Shellcode",
                "3. 使用任意注入方法写入 Shellcode",
                "4. 加载器解析自身 PE 头",
                "5. 加载器映射节区到内存",
                "6. 加载器处理重定位和导入表",
                "7. 加载器调用 DllMain()",
                "8. 无需 LoadLibrary 注册, 更隐蔽",
            ],
            InjectionMethod.PROCESS_HOLLOWING: [
                "1. CREATE_SUSPENDED 创建目标进程",
                "2. NtUnmapViewOfSection() 卸载原始镜像",
                "3. VirtualAllocEx() 分配新内存",
                "4. WriteProcessMemory() 写入 PE 头和节区",
                "5. 处理重定位",
                "6. SetThreadContext() 修改入口点",
                "7. ResumeThread() 恢复进程",
            ],
            InjectionMethod.ATOM_BOMBING: [
                "1. GlobalAddAtom() 将 Shellcode 写入原子表",
                "2. NtQueueApcThread() 为线程排队 APC",
                "3. APC 中 GlobalGetAtomName() 读取 Shellcode",
                "4. 执行 Shellcode 加载 DLL",
                "5. GlobalDeleteAtom() 清理原子表",
            ],
            InjectionMethod.MANUAL_MAP: [
                "1. 手动解析 DLL 的 PE 结构",
                "2. 在目标进程中分配内存",
                "3. 手动映射所有节区",
                "4. 手动处理导入表",
                "5. 手动处理重定位",
                "6. 调用 TLS 回调和 DllMain",
                "7. 完全绕过 LoadLibrary 检测",
            ],
        }

        plan.steps = steps.get(method, [])
        plan.required_permissions = self._get_required_permissions(method)
        plan.alternatives = self._get_alternatives(method)

        return plan

    def _get_required_permissions(self, method: InjectionMethod) -> List[str]:
        """获取所需权限"""
        base = ["PROCESS_VM_OPERATION", "PROCESS_VM_WRITE"]
        extras = {
            InjectionMethod.CREATE_REMOTE_THREAD: ["PROCESS_CREATE_THREAD", "PROCESS_VM_READ"],
            InjectionMethod.THREAD_HIJACKING: ["PROCESS_SUSPEND_RESUME", "PROCESS_GET_CONTEXT", "PROCESS_SET_CONTEXT"],
            InjectionMethod.PROCESS_HOLLOWING: ["PROCESS_CREATE_PROCESS", "PROCESS_DUP_HANDLE"],
            InjectionMethod.QUEUE_USER_APC: ["PROCESS_SET_CONTEXT", "THREAD_SET_CONTEXT"],
        }
        return base + extras.get(method, [])

    def _get_alternatives(self, method: InjectionMethod) -> List[InjectionMethod]:
        """获取替代方案"""
        alternatives = {
            InjectionMethod.CREATE_REMOTE_THREAD: [
                InjectionMethod.QUEUE_USER_APC,
                InjectionMethod.SET_WINDOWS_HOOK,
            ],
            InjectionMethod.SET_WINDOWS_HOOK: [
                InjectionMethod.CREATE_REMOTE_THREAD,
                InjectionMethod.QUEUE_USER_APC,
            ],
            InjectionMethod.QUEUE_USER_APC: [
                InjectionMethod.THREAD_HIJACKING,
                InjectionMethod.CREATE_REMOTE_THREAD,
            ],
            InjectionMethod.THREAD_HIJACKING: [
                InjectionMethod.REFLECTIVE_DLL,
                InjectionMethod.MANUAL_MAP,
            ],
            InjectionMethod.REFLECTIVE_DLL: [
                InjectionMethod.MANUAL_MAP,
                InjectionMethod.THREAD_HIJACKING,
            ],
        }
        return alternatives.get(method, [])

    def get_best_method(self, target_process: str,
                        security_measures: List[SecurityMeasure]) -> InjectionPlan:
        """获取最佳注入方法"""
        plans = self.plan_injection(target_process, prefer_stealth=True)

        # 如果有反作弊，优先选择隐蔽性最高的
        has_anti_cheat = SecurityMeasure.ANTI_DEBUG in security_measures
        if has_anti_cheat:
            plans.sort(key=lambda p: p.stealth_level, reverse=True)

        return plans[0] if plans else None


# ============================================================
# 代码洞穴扫描器
# ============================================================

class CodeCaveFinder:
    """
    代码洞穴扫描器
    在二进制文件中寻找可用于注入代码的空隙
    """

    MIN_CAVE_SIZE = 16
    CAVE_PATTERNS = [
        b"\x00",           # 零填充
        b"\xCC",           # INT3 填充
        b"\x90",           # NOP 填充
        b"\x00\x00",       # 零填充 (2字节对齐)
        b"\xCC\xCC",       # INT3 填充 (2字节对齐)
        b"\x90\x90",       # NOP 填充 (2字节对齐)
    ]

    def __init__(self):
        self._caves: List[CodeCave] = []

    def find_caves(self, data: bytes, base_address: int = 0) -> List[CodeCave]:
        """在数据中寻找代码洞穴"""
        self._caves = []
        self._find_zero_caves(data, base_address)
        self._find_pattern_caves(data, base_address, b"\xCC", "INT3 padding")
        self._find_pattern_caves(data, base_address, b"\x90", "NOP padding")
        self._find_section_gaps(data, base_address)
        return sorted(self._caves, key=lambda c: c.size, reverse=True)

    def _find_zero_caves(self, data: bytes, base: int):
        """寻找零填充洞穴"""
        i = 0
        while i < len(data):
            if data[i] == 0:
                start = i
                while i < len(data) and data[i] == 0:
                    i += 1
                size = i - start
                if size >= self.MIN_CAVE_SIZE:
                    self._caves.append(CodeCave(
                        address=base + start,
                        size=size,
                        section="",
                        alignment=1,
                    ))
            else:
                i += 1

    def _find_pattern_caves(self, data: bytes, base: int, pattern: bytes, label: str):
        """寻找模式填充洞穴"""
        p_len = len(pattern)
        i = 0
        while i < len(data) - p_len + 1:
            if data[i:i + p_len] == pattern:
                start = i
                while i < len(data) - p_len + 1 and data[i:i + p_len] == pattern:
                    i += p_len
                size = i - start
                if size >= self.MIN_CAVE_SIZE:
                    self._caves.append(CodeCave(
                        address=base + start,
                        size=size,
                        section="",
                        alignment=p_len,
                    ))
            else:
                i += 1

    def _find_section_gaps(self, data: bytes, base: int):
        """寻找节区间隙"""
        # 检查 PE 头后的间隙
        if len(data) > 0x1000:
            # DOS 头到 PE 头之间的间隙
            for i in range(0x40, 0x100, 4):
                if i + 4 <= len(data) and data[i:i + 4] == b"\x00\x00\x00\x00":
                    start = i
                    while i < 0x100 and i + 4 <= len(data) and data[i:i + 4] == b"\x00\x00\x00\x00":
                        i += 4
                    size = i - start
                    if size >= self.MIN_CAVE_SIZE:
                        self._caves.append(CodeCave(
                            address=base + start,
                            size=size,
                            section="PE header gap",
                            alignment=4,
                        ))

    def find_best_cave(self, data: bytes, required_size: int,
                       base_address: int = 0) -> Optional[CodeCave]:
        """寻找最佳洞穴"""
        caves = self.find_caves(data, base_address)
        for cave in caves:
            if cave.size >= required_size:
                return cave
        return None

    def find_caves_near_rva(self, data: bytes, target_rva: int,
                            search_range: int = 0x1000,
                            base_address: int = 0) -> List[CodeCave]:
        """在目标地址附近寻找洞穴"""
        caves = self.find_caves(data, base_address)
        return [
            c for c in caves
            if abs(int(c.address - base_address) - target_rva) <= search_range
        ]

    def analyze_cave_quality(self, cave: CodeCave, data: bytes,
                             base_address: int = 0) -> Dict[str, Any]:
        """分析洞穴质量"""
        offset = cave.address - base_address
        if offset < 0 or offset + cave.size > len(data):
            return {"quality": "invalid", "score": 0}

        cave_data = data[offset:offset + cave.size]

        # 检查是否可执行
        score = 50
        notes = []

        if cave.size >= 256:
            score += 20
            notes.append("Large enough for complex code")
        elif cave.size >= 64:
            score += 10
            notes.append("Adequate for simple hooks")

        # 检查对齐
        if cave.alignment >= 4:
            score += 10
            notes.append("Good alignment")

        # 检查是否在代码段附近
        if cave.near_function:
            score += 10
            notes.append(f"Near function: {cave.near_function}")

        return {
            "quality": "excellent" if score >= 80 else "good" if score >= 60 else "adequate",
            "score": min(score, 100),
            "notes": notes,
            "usable_bytes": cave.size,
        }


# ============================================================
# Hook 生成器
# ============================================================

class HookGenerator:
    """
    Hook 生成器
    生成各种 Hook 的代码模板和跳板
    """

    # x86 跳转指令模板
    JMP_NEAR32 = bytes([0xE9])  # JMP rel32 (5 bytes)
    JMP_ABS64 = bytes([0xFF, 0x25, 0x00, 0x00, 0x00, 0x00])  # JMP [rip+0] (14 bytes total)
    CALL_NEAR32 = bytes([0xE8])  # CALL rel32
    NOP = bytes([0x90])
    INT3 = bytes([0xCC])
    RET = bytes([0xC3])

    def __init__(self):
        self._hooks: List[HookTemplate] = []

    def generate_inline_hook(self, target_addr: int, hook_addr: int,
                             original_bytes: bytes = b"",
                             is_64bit: bool = True) -> HookTemplate:
        """生成内联 Hook"""
        if is_64bit:
            # x64: JMP [rip+0] + 8-byte absolute address
            hook_code = self.JMP_ABS64 + struct.pack("<Q", hook_addr)
        else:
            # x86: JMP rel32
            rel = hook_addr - (target_addr + 5)
            hook_code = self.JMP_NEAR32 + struct.pack("<i", rel & 0xFFFFFFFF)

        # 生成跳板 (执行原始指令 + 跳回)
        trampoline = self._generate_trampoline(target_addr, hook_addr,
                                                original_bytes, is_64bit)

        hook = HookTemplate(
            hook_type=HookType.INLINE,
            target_function="",
            target_rva=target_addr,
            hook_code=hook_code,
            hook_size=len(hook_code),
            original_bytes=original_bytes,
            trampoline=trampoline,
            patches=[
                {"address": target_addr, "bytes": hook_code, "description": "Inline hook jump"},
            ],
        )

        self._hooks.append(hook)
        return hook

    def _generate_trampoline(self, target_addr: int, hook_addr: int,
                             original_bytes: bytes, is_64bit: bool) -> bytes:
        """生成跳板代码"""
        trampoline = bytearray()

        # 复制原始指令
        trampoline.extend(original_bytes)

        # 跳回原始代码 (使用绝对地址确保安全)
        return_addr = target_addr + len(original_bytes)
        if is_64bit:
            trampoline.extend(self.JMP_ABS64)
            trampoline.extend(struct.pack("<Q", return_addr))
        else:
            # x86: 使用 push/ret 组合实现绝对跳转
            trampoline.extend(bytes([0x68]))  # PUSH imm32
            trampoline.extend(struct.pack("<I", return_addr & 0xFFFFFFFF))
            trampoline.extend(bytes([0xC3]))  # RET

        return bytes(trampoline)

    def generate_iat_hook(self, module_name: str, function_name: str,
                          hook_addr: int) -> HookTemplate:
        """生成 IAT Hook"""
        return HookTemplate(
            hook_type=HookType.IAT,
            target_function=function_name,
            target_module=module_name,
            detour_function=f"hook_{function_name}",
            patches=[
                {
                    "module": module_name,
                    "function": function_name,
                    "new_address": hook_addr,
                    "description": f"IAT hook: {module_name}!{function_name}",
                }
            ],
        )

    def generate_detour(self, target_addr: int, hook_addr: int,
                        original_bytes: bytes = b"",
                        is_64bit: bool = True) -> HookTemplate:
        """生成 Detour Hook"""
        return self.generate_inline_hook(target_addr, hook_addr,
                                         original_bytes, is_64bit)

    def generate_hot_patch(self, target_addr: int, hook_addr: int,
                           is_64bit: bool = True) -> HookTemplate:
        """生成热补丁 Hook"""
        # 热补丁: 修改函数开头的 2 字节为短跳转
        # 然后在函数前 5 字节处放置长跳转

        # 短跳转: JMP $-5 (EB F9)
        short_jmp = bytes([0xEB, 0xF9])

        if is_64bit:
            long_jmp = self.JMP_ABS64 + struct.pack("<Q", hook_addr)
        else:
            rel = hook_addr - (target_addr - 5)
            long_jmp = self.JMP_NEAR32 + struct.pack("<i", rel & 0xFFFFFFFF)

        return HookTemplate(
            hook_type=HookType.HOT_PATCH,
            target_function="",
            target_rva=target_addr,
            hook_code=short_jmp + long_jmp,
            hook_size=len(short_jmp) + len(long_jmp),
            patches=[
                {"address": target_addr - 5, "bytes": long_jmp, "description": "Hot patch long jump"},
                {"address": target_addr, "bytes": short_jmp, "description": "Hot patch short jump"},
            ],
        )

    def generate_nop_patch(self, address: int, size: int) -> HookTemplate:
        """生成 NOP 补丁"""
        return HookTemplate(
            hook_type=HookType.INLINE,
            target_function="",
            target_rva=address,
            hook_code=self.NOP * size,
            hook_size=size,
            patches=[
                {"address": address, "bytes": self.NOP * size, "description": f"NOP patch ({size} bytes)"},
            ],
        )

    def generate_hook_chain(self, hooks: List[Dict[str, Any]],
                            is_64bit: bool = True) -> List[HookTemplate]:
        """生成 Hook 链"""
        results = []
        for h in hooks:
            hook_type = h.get("type", "inline")
            if hook_type == "inline":
                results.append(self.generate_inline_hook(
                    h["target"], h["hook"], h.get("original", b""), is_64bit
                ))
            elif hook_type == "iat":
                results.append(self.generate_iat_hook(
                    h.get("module", ""), h["function"], h["hook"]
                ))
            elif hook_type == "nop":
                results.append(self.generate_nop_patch(h["target"], h["size"]))
        return results

    def get_hook_code_asm(self, hook: HookTemplate, is_64bit: bool = True) -> str:
        """生成 Hook 汇编代码"""
        lines = []
        lines.append(f"; Hook: {hook.target_function} ({hook.hook_type.value})")
        lines.append(f"; Target: 0x{hook.target_rva:X}")
        lines.append("")

        if hook.hook_type == HookType.INLINE:
            lines.append("; Inline Hook")
            if is_64bit:
                lines.append("jmp [rip]")
                lines.append(f".dq 0x{hook.hook_code[6:].hex()}")
            else:
                lines.append(f"jmp 0x{hook.hook_code[1:].hex()}")
            lines.append("")
            lines.append("; Trampoline:")
            lines.append(f".db {hook.trampoline.hex()}")

        elif hook.hook_type == HookType.IAT:
            lines.append("; IAT Hook")
            lines.append(f"; Replace {hook.target_module}!{hook.target_function}")
            lines.append(f"; With: {hook.detour_function}")

        elif hook.hook_type == HookType.HOT_PATCH:
            lines.append("; Hot Patch")
            lines.append("jmp $-5  ; Short jump to long jump")
            lines.append(f"jmp 0x{hook.hook_code[2:].hex()}  ; Long jump to hook")

        return "\n".join(lines)


# ============================================================
# DLL 分析器
# ============================================================

class DLLAnalyzer:
    """
    DLL 分析器
    分析 DLL 依赖、导出函数、劫持机会
    """

    KNOWN_DLL_SEARCH_PATHS = [
        # 标准搜索顺序 (SafeDllSearchMode)
        "%SYSTEM32%",
        "%SYSTEM%",
        "%WINDOWS%",
        ".",
        "%PATH%",
    ]

    KNOWN_DLLS = {
        # HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Session Manager\KnownDLLs
        "kernel32.dll", "kernelbase.dll", "ntdll.dll",
        "user32.dll", "gdi32.dll", "gdi32full.dll",
        "advapi32.dll", "shell32.dll", "ole32.dll",
        "oleaut32.dll", "comctl32.dll", "comdlg32.dll",
        "ws2_32.dll", "winmm.dll", "wininet.dll",
        "msvcrt.dll", "msvcp140.dll", "vcruntime140.dll",
        "bcrypt.dll", "crypt32.dll", "secur32.dll",
        "d3d9.dll", "d3d11.dll", "dxgi.dll",
    }

    COMMON_HIJACK_TARGETS = [
        # 常用 DLL 劫持目标
        {"name": "version.dll", "exports": ["GetFileVersionInfoA", "GetFileVersionInfoW",
                                              "GetFileVersionInfoSizeA", "GetFileVersionInfoSizeW",
                                              "VerQueryValueA", "VerQueryValueW"]},
        {"name": "userenv.dll", "exports": ["CreateEnvironmentBlock", "DestroyEnvironmentBlock"]},
        {"name": "propsys.dll", "exports": ["PSGetPropertyKeyFromName", "PSGetNameFromPropertyKey"]},
        {"name": "dwmapi.dll", "exports": ["DwmIsCompositionEnabled", "DwmGetWindowAttribute"]},
        {"name": "uxtheme.dll", "exports": ["BeginBufferedPaint", "EndBufferedPaint"]},
        {"name": "cryptbase.dll", "exports": ["SystemFunction036", "SystemFunction041"]},
        {"name": "ntmarta.dll", "exports": ["GetMartaExtensionInterface"]},
        {"name": "profapi.dll", "exports": ["CreateWellKnownSid", "GetWellKnownSid"]},
        {"name": "wtsapi32.dll", "exports": ["WTSRegisterSessionNotification", "WTSUnRegisterSessionNotification"]},
        {"name": "bcryptprimitives.dll", "exports": ["ProcessPrng", "GetRandomBytes"]},
    ]

    def __init__(self):
        self._analyzed_dlls: Dict[str, Dict[str, Any]] = {}

    def analyze_dll(self, dll_name: str) -> Dict[str, Any]:
        """分析 DLL 的劫持可能性"""
        if dll_name in self._analyzed_dlls:
            return self._analyzed_dlls[dll_name]

        name_lower = dll_name.lower()

        result = {
            "name": dll_name,
            "is_known_dll": name_lower in self.KNOWN_DLLS,
            "is_system_critical": self._is_system_critical(name_lower),
            "hijack_methods": [],
            "exports": [],
            "dependencies": [],
            "risk_assessment": "",
        }

        # 检查已知劫持目标
        for target in self.COMMON_HIJACK_TARGETS:
            if target["name"] == name_lower:
                result["exports"] = target["exports"]
                result["hijack_methods"].append(DllHijackMethod.PROXY_DLL)
                break

        # 分析劫持方法
        if not result["is_known_dll"]:
            result["hijack_methods"].append(DllHijackMethod.SEARCH_ORDER)
        result["hijack_methods"].append(DllHijackMethod.PROXY_DLL)

        if name_lower in ["version.dll", "userenv.dll", "propsys.dll"]:
            result["hijack_methods"].append(DllHijackMethod.COM_HIJACK)

        result["risk_assessment"] = self._assess_risk(result)
        self._analyzed_dlls[dll_name] = result
        return result

    def _is_system_critical(self, name: str) -> bool:
        """检查是否是系统关键 DLL"""
        critical = {"ntdll.dll", "kernel32.dll", "kernelbase.dll"}
        return name in critical

    def _assess_risk(self, analysis: Dict[str, Any]) -> str:
        """评估风险"""
        if analysis["is_system_critical"]:
            return "HIGH - 系统关键 DLL, 劫持可能导致系统不稳定"
        if analysis["is_known_dll"]:
            return "MEDIUM - KnownDLL, 需要注册表操作或代理 DLL"
        return "LOW - 可安全劫持, 注意保持导出函数兼容"

    def find_hijack_opportunities(self, target_exe: str) -> List[DllHijackOpportunity]:
        """寻找劫持机会"""
        opportunities = []

        # 模拟搜索 DLL 依赖
        dependencies = self._get_expected_dependencies(target_exe)

        for dep in dependencies:
            analysis = self.analyze_dll(dep)
            if not analysis["is_system_critical"]:
                for method in analysis["hijack_methods"]:
                    opportunities.append(DllHijackOpportunity(
                        dll_name=dep,
                        method=method,
                        load_path=f".\\{dep}",
                        priority=80 if method == DllHijackMethod.SEARCH_ORDER else 60,
                        is_signed=False,
                        is_known_dll=analysis["is_known_dll"],
                        dependencies=analysis.get("dependencies", []),
                        risk_assessment=analysis["risk_assessment"],
                        exploit_guide=self._generate_exploit_guide(dep, method),
                    ))

        return sorted(opportunities, key=lambda o: o.priority, reverse=True)

    def _get_expected_dependencies(self, exe_name: str) -> List[str]:
        """获取预期依赖"""
        common_deps = [
            "kernel32.dll", "user32.dll", "gdi32.dll",
            "advapi32.dll", "shell32.dll", "ole32.dll",
            "comctl32.dll", "ws2_32.dll", "winmm.dll",
            "version.dll", "d3d9.dll", "dxgi.dll",
        ]

        game_specific = {
            "san7": ["obdb.dll", "mss32.dll", "binkw32.dll"],
            "unity": ["UnityPlayer.dll", "mono.dll"],
            "unreal": ["UE4Game.dll", "OpenAL32.dll"],
        }

        for key, deps in game_specific.items():
            if key in exe_name.lower():
                return common_deps + deps

        return common_deps + ["version.dll", "winmm.dll", "d3d9.dll"]

    def _generate_exploit_guide(self, dll_name: str, method: DllHijackMethod) -> str:
        """生成利用指南"""
        guides = {
            DllHijackMethod.SEARCH_ORDER: (
                f"1. 将代理 DLL 命名为 {dll_name}\n"
                f"2. 放置在目标 EXE 同目录\n"
                f"3. 代理 DLL 转发所有导出到原始 DLL\n"
                f"4. 在 DllMain 中执行自定义代码"
            ),
            DllHijackMethod.PROXY_DLL: (
                f"1. 创建代理 DLL (命名为 {dll_name})\n"
                f"2. 实现所有原始导出函数\n"
                f"3. 每个导出函数转发到原始 DLL\n"
                f"4. 在 DllMain 的 DLL_PROCESS_ATTACH 中执行 payload"
            ),
            DllHijackMethod.COM_HIJACK: (
                f"1. 找到使用 {dll_name} 的 COM 对象\n"
                f"2. 修改注册表中的 COM 注册\n"
                f"3. 指向自定义 DLL\n"
                f"4. 自定义 DLL 实现 COM 接口"
            ),
            DllHijackMethod.PHANTOM_DLL: (
                f"1. 分析目标加载 {dll_name} 的时机\n"
                f"2. 在目标尝试加载前创建 {dll_name}\n"
                f"3. DLL 加载后立即转发到原始 DLL"
            ),
        }
        return guides.get(method, "标准 DLL 劫持流程")


# ============================================================
# 代理 DLL 生成器
# ============================================================

class ProxyDLLGenerator:
    """
    代理 DLL 生成器
    生成代理 DLL 的 C/C++ 源代码
    """

    def __init__(self):
        self._analyzer = DLLAnalyzer()

    def generate_proxy_dll(self, target_dll: str, payload_code: str = "",
                           architecture: str = "x64") -> Dict[str, str]:
        """生成代理 DLL 源代码"""
        analysis = self._analyzer.analyze_dll(target_dll)
        exports = analysis.get("exports", [])

        files = {}

        # 生成 DLL 主源文件
        files["proxy_dll.c"] = self._generate_dll_main(target_dll, exports, payload_code)
        files["proxy_dll.h"] = self._generate_dll_header(target_dll)
        files["exports.def"] = self._generate_def_file(target_dll, exports)
        files["build.bat"] = self._generate_build_script(target_dll, architecture)
        files["README.txt"] = self._generate_readme(target_dll, analysis)

        return files

    def _generate_dll_main(self, target_dll: str, exports: List[str],
                           payload_code: str) -> str:
        """生成 DLL 主文件"""
        orig_name = target_dll.replace(".dll", "_orig.dll")

        source = f'''/**
 * 代理 DLL for {target_dll}
 * 自动生成的代理 DLL 源代码
 */

#include <windows.h>
#include <stdio.h>

// 原始 DLL 路径
#define ORIGINAL_DLL "{orig_name}"

// ============================================================
// 全局变量
// ============================================================

static HMODULE g_hOriginal = NULL;

// ============================================================
// 辅助函数
// ============================================================

static BOOL LoadOriginalDLL() {{
    if (g_hOriginal) return TRUE;

    // 尝试从系统目录加载原始 DLL
    CHAR szSystemPath[MAX_PATH];
    GetSystemDirectoryA(szSystemPath, MAX_PATH);
    strcat_s(szSystemPath, MAX_PATH, "\\\\{target_dll}");

    g_hOriginal = LoadLibraryA(szSystemPath);
    if (!g_hOriginal) {{
        // 回退到当前目录
        g_hOriginal = LoadLibraryA(ORIGINAL_DLL);
    }}

    return g_hOriginal != NULL;
}}

static FARPROC GetOriginalExport(LPCSTR lpProcName) {{
    if (!LoadOriginalDLL()) return NULL;
    return GetProcAddress(g_hOriginal, lpProcName);
}}

// ============================================================
// DllMain
// ============================================================

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {{
    switch (ul_reason_for_call) {{
    case DLL_PROCESS_ATTACH:
        DisableThreadLibraryCalls(hModule);

        // --- 自定义 Payload 开始 ---
{self._indent(payload_code, "        ")}
        // --- 自定义 Payload 结束 ---

        break;
    case DLL_PROCESS_DETACH:
        if (g_hOriginal) {{
            FreeLibrary(g_hOriginal);
            g_hOriginal = NULL;
        }}
        break;
    }}
    return TRUE;
}}

// ============================================================
// 导出函数转发
// ============================================================
'''

        for exp in exports:
            source += f'''
// 转发: {exp}
__declspec(naked) void proxy_{exp}() {{
    __asm {{
        jmp [{exp}]
    }}
}}
'''

        source += '''
// ============================================================
// 导出转发表
// ============================================================
'''

        for exp in exports:
            source += f'#pragma comment(linker, "/EXPORT:{exp}=proxy_{exp}")\n'

        source += f'''
// ============================================================
// 延迟加载原始导出
// 如果需要更复杂的转发逻辑:
// ============================================================

typedef FARPROC (*PFN_{target_dll.replace(".", "_")}_GETEXPORT)(LPCSTR);

PFN_{target_dll.replace(".", "_")}_GETEXPORT Get{target_dll.replace(".", "_")}Export = GetOriginalExport;
'''

        return source

    def _generate_dll_header(self, target_dll: str) -> str:
        """生成头文件"""
        return f'''/**
 * 代理 DLL 头文件 for {target_dll}
 */

#pragma once

#include <windows.h>

// 原始 DLL 句柄
extern HMODULE g_hOriginal;

// 初始化代理 DLL
BOOL InitializeProxy();

// 获取原始导出
FARPROC GetOriginalExport(LPCSTR lpProcName);

// 清理
void CleanupProxy();
'''

    def _generate_def_file(self, target_dll: str, exports: List[str]) -> str:
        """生成 .def 文件"""
        def_content = f"; 代理 DLL 导出定义 for {target_dll}\n"
        def_content += "LIBRARY " + target_dll.replace(".dll", "") + "\n"
        def_content += "EXPORTS\n"
        for exp in exports:
            def_content += f"    {exp}=proxy_{exp}\n"
        return def_content

    def _generate_build_script(self, target_dll: str, arch: str) -> str:
        """生成构建脚本"""
        machine = "/MACHINE:X64" if arch == "x64" else "/MACHINE:X86"
        return f'''@echo off
REM 构建代理 DLL: {target_dll}
REM 使用 Visual Studio 开发者命令提示符运行

cl.exe /nologo /O2 /MT /LD /D_USRDLL /D_WINDLL ^
    proxy_dll.c ^
    /link /NODEFAULTLIB /ENTRY:DllMain ^
    /DEF:exports.def ^
    {machine} ^
    /OUT:{target_dll}

echo.
echo 构建完成: {target_dll}
echo 请将原始 DLL 重命名为 {target_dll.replace(".dll", "_orig.dll")}
echo 并将 {target_dll} 放在目标 EXE 同目录
'''

    def _generate_readme(self, target_dll: str, analysis: Dict[str, Any]) -> str:
        """生成说明文件"""
        return f'''代理 DLL 使用说明
===============

目标 DLL: {target_dll}
风险等级: {analysis.get("risk_assessment", "Unknown")}

使用步骤:
1. 将原始 {target_dll} 重命名为 {target_dll.replace(".dll", "_orig.dll")}
2. 编译代理 DLL: 运行 build.bat
3. 将生成的 {target_dll} 放在目标 EXE 同目录
4. 启动目标程序，代理 DLL 将自动加载

自定义 Payload:
- 编辑 proxy_dll.c 中的 DllMain 函数
- 在 "自定义 Payload" 区域添加代码
- 重新编译

注意事项:
- 确保所有原始导出函数都有转发
- 不要在 DllMain 中调用 LoadLibrary (可能导致死锁)
- 测试前备份原始 DLL
'''

    def _indent(self, text: str, indent: str) -> str:
        """缩进文本"""
        if not text:
            return indent + "// 默认: 无额外 Payload"
        return "\n".join(indent + line for line in text.split("\n"))

    def generate_forward_chain(self, dlls: List[str]) -> Dict[str, str]:
        """生成转发链"""
        chain = {
            "chain_info": {
                "dlls": dlls,
                "entry_point": dlls[0] if dlls else "",
                "description": "DLL 转发链",
            },
            "instructions": [],
        }

        for i, dll in enumerate(dlls):
            orig = dll.replace(".dll", "_orig.dll")
            if i == 0:
                chain["instructions"].append(f"1. 目标加载 {dll}")
            chain["instructions"].append(f"{i+2}. {dll} 转发到 {orig}")

        return chain


# ============================================================
# 安全分析器
# ============================================================

class SecurityAnalyzer:
    """
    安全分析器
    分析目标的安全措施并提供绕过建议
    """

    ANTI_DEBUG_PATTERNS = [
        (rb"IsDebuggerPresent", "IsDebuggerPresent 检测"),
        (rb"CheckRemoteDebuggerPresent", "CheckRemoteDebuggerPresent 检测"),
        (rb"NtQueryInformationProcess.*ProcessDebugPort", "DebugPort 检测"),
        (rb"NtQueryInformationProcess.*ProcessDebugObjectHandle", "DebugObject 检测"),
        (rb"NtQueryInformationProcess.*ProcessDebugFlags", "DebugFlags 检测"),
        (rb"NtSetInformationThread.*ThreadHideFromDebugger", "HideFromDebugger"),
        (rb"OutputDebugString", "OutputDebugString 反调试"),
        (rb"GetTickCount", "时序检测"),
        (rb"QueryPerformanceCounter", "高精度时序检测"),
        (rb"rdtsc", "RDTSC 时序检测"),
        (rb"int\s*3", "INT3 断点检测"),
        (rb"int\s*1", "INT1 检测"),
        (rb"icebp", "ICEBP 检测"),
    ]

    INTEGRITY_PATTERNS = [
        (rb"CreateFile.*\.exe", "EXE 完整性检查"),
        (rb"CreateFile.*\.dll", "DLL 完整性检查"),
        (rb"MapViewOfFile", "内存映射文件检查"),
        (rb"GetFileSize", "文件大小检查"),
        (rb"VirtualProtect.*\.text", "代码段保护检查"),
        (rb"CRC32", "CRC32 校验"),
        (rb"MD5", "MD5 校验"),
        (rb"SHA", "SHA 校验"),
        (rb"memcmp", "内存比较"),
    ]

    def __init__(self):
        self._reports: Dict[str, SecurityReport] = {}

    def analyze_security(self, process_name: str,
                         code_sections: bytes = b"") -> SecurityReport:
        """分析安全措施"""
        if process_name in self._reports:
            return self._reports[process_name]

        report = SecurityReport()
        measures = []

        # 检测反调试
        for pattern, desc in self.ANTI_DEBUG_PATTERNS:
            if re.search(pattern, code_sections, re.IGNORECASE) if code_sections else False:
                measures.append({
                    "type": SecurityMeasure.ANTI_DEBUG.value,
                    "pattern": desc,
                    "severity": "medium",
                })

        # 检测完整性检查
        for pattern, desc in self.INTEGRITY_PATTERNS:
            if re.search(pattern, code_sections, re.IGNORECASE) if code_sections else False:
                measures.append({
                    "type": SecurityMeasure.INTEGRITY_CHECK.value,
                    "pattern": desc,
                    "severity": "high",
                })

        # 模拟检测
        simulated = self._simulate_detection(process_name)
        measures.extend(simulated)

        report.measures_detected = measures
        report.risk_score = self._calculate_risk_score(measures)
        report.bypass_suggestions = self._generate_bypass_suggestions(measures)
        report.overall_assessment = self._generate_assessment(report)

        self._reports[process_name] = report
        return report

    def _simulate_detection(self, process_name: str) -> List[Dict[str, Any]]:
        """模拟检测"""
        measures = []
        name_lower = process_name.lower()

        anti_cheat_indicators = {
            "easyanticheat": ["EAC 内核驱动", "EAC 用户态模块", "EAC 完整性检查"],
            "battleye": ["BEDaisy 驱动", "BattlEye 用户态 Hook", "BE 内存扫描"],
            "xigncode": ["xigncode 驱动", "xigncode 用户态 Hook"],
            "vanguard": ["vgk.sys 内核驱动", "Vanguard 用户态监控"],
            "faceit": ["FACEIT AC 驱动", "FACEIT 服务"],
            "esl": ["ESL Wire AC", "ESL 反作弊服务"],
        }

        for keyword, indicators in anti_cheat_indicators.items():
            if keyword in name_lower:
                for ind in indicators:
                    measures.append({
                        "type": SecurityMeasure.ANTI_DEBUG.value,
                        "pattern": ind,
                        "severity": "high",
                    })

        return measures

    def _calculate_risk_score(self, measures: List[Dict[str, Any]]) -> int:
        """计算风险分数"""
        score = 0
        severity_map = {"low": 10, "medium": 25, "high": 40, "critical": 60}
        for m in measures:
            score += severity_map.get(m.get("severity", "medium"), 25)
        return min(score, 100)

    def _generate_bypass_suggestions(self, measures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成绕过建议"""
        suggestions = []
        seen_types = set()

        for m in measures:
            mtype = m.get("type", "")
            if mtype in seen_types:
                continue
            seen_types.add(mtype)

            if mtype == SecurityMeasure.ANTI_DEBUG.value:
                suggestions.append({
                    "target": "反调试",
                    "methods": [
                        "Hook IsDebuggerPresent 返回 FALSE",
                        "Hook NtQueryInformationProcess 返回成功",
                        "Patch PEB.BeingDebugged 标志",
                        "Hook NtSetInformationThread 拦截 ThreadHideFromDebugger",
                        "使用 ScyllaHide 等反反调试工具",
                        "内核级 Hook (需驱动)",
                    ],
                    "difficulty": "medium",
                })
            elif mtype == SecurityMeasure.INTEGRITY_CHECK.value:
                suggestions.append({
                    "target": "完整性检查",
                    "methods": [
                        "Hook CreateFile/ReadFile 返回原始文件内容",
                        "使用内存补丁而非文件补丁",
                        "Hook 校验函数返回预期值",
                        "在检查前恢复原始字节, 检查后重新补丁",
                        "使用硬件断点拦截校验调用",
                    ],
                    "difficulty": "high",
                })
            elif mtype == SecurityMeasure.MEMORY_SCAN.value:
                suggestions.append({
                    "target": "内存扫描",
                    "methods": [
                        "使用硬件断点 (DR0-DR3) 而非 INT3",
                        "VEH Hook 而非内联 Hook",
                        "手动映射绕过 VAD 扫描",
                        "使用页面保护技巧",
                        "Hypervisor 级隐藏 (需虚拟化)",
                    ],
                    "difficulty": "high",
                })
            elif mtype == SecurityMeasure.MODULE_CHECK.value:
                suggestions.append({
                    "target": "模块检查",
                    "methods": [
                        "Hook LdrLoadDll 隐藏 DLL",
                        "从 PEB 中移除模块条目",
                        "手动映射 (不注册到 Loader)",
                        "使用反射式 DLL 注入",
                        "抹除 PE 头和导入表",
                    ],
                    "difficulty": "medium",
                })

        return suggestions

    def _generate_assessment(self, report: SecurityReport) -> str:
        """生成总体评估"""
        if report.risk_score >= 80:
            return "高安全等级 - 建议使用内核级方案或手动映射 + VEH Hook"
        elif report.risk_score >= 50:
            return "中等安全等级 - 内联 Hook + 反射式 DLL 注入可行"
        elif report.risk_score >= 20:
            return "低安全等级 - 标准注入方法可行"
        else:
            return "基本无安全措施 - 任意注入方法可用"

    def scan_for_anti_tamper(self, data: bytes) -> List[Dict[str, Any]]:
        """扫描反篡改措施"""
        findings = []

        # 检查常见的反篡改模式
        patterns = [
            (b"VMProtect", "VMProtect 加壳"),
            (b"Themida", "Themida 加壳"),
            (b"ASPack", "ASPack 加壳"),
            (b"UPX", "UPX 加壳"),
            (b"Enigma", "Enigma Protector"),
            (b"Obsidium", "Obsidium 加壳"),
            (b"Safengine", "Safengine 加壳"),
            (b"WinLicense", "WinLicense 保护"),
            (b"SecuROM", "SecuROM DRM"),
            (b"Denuvo", "Denuvo 反篡改"),
        ]

        for pattern, desc in patterns:
            if pattern in data:
                findings.append({"type": "packer", "name": desc, "severity": "high"})

        return findings


# ============================================================
# 代码注入引擎 (主入口)
# ============================================================

class CodeInjectEngine:
    """
    代码注入与 DLL 劫持引擎
    提供统一的代码注入、Hook 和 DLL 劫持接口
    """

    def __init__(self):
        self.process_analyzer = ProcessAnalyzer()
        self.injection_planner = InjectionPlanner()
        self.code_cave_finder = CodeCaveFinder()
        self.hook_generator = HookGenerator()
        self.dll_analyzer = DLLAnalyzer()
        self.proxy_dll_generator = ProxyDLLGenerator()
        self.security_analyzer = SecurityAnalyzer()

    # ============================================================
    # 进程分析
    # ============================================================

    def analyze_process(self, process_name: str) -> dict:
        """分析进程"""
        info = self.process_analyzer.analyze_process(process_name)
        return {
            "success": True,
            "process": info.name,
            "pid": info.pid,
            "is_64bit": info.is_64bit,
            "modules": [
                {
                    "name": m.name,
                    "path": m.path,
                    "export_count": len(m.exports),
                }
                for m in info.modules
            ],
            "security_measures": [s.value for s in info.security_measures],
        }

    def enumerate_modules(self, process_name: str) -> dict:
        """枚举模块"""
        modules = self.process_analyzer.enumerate_modules(process_name)
        return {
            "success": True,
            "process": process_name,
            "modules": [
                {
                    "name": m.name,
                    "path": m.path,
                    "exports": [e.name for e in m.exports],
                }
                for m in modules
            ],
        }

    # ============================================================
    # 注入计划
    # ============================================================

    def plan_injection(self, target_process: str, dll_path: str = "",
                       prefer_stealth: bool = True) -> dict:
        """规划注入策略"""
        plans = self.injection_planner.plan_injection(target_process, dll_path, prefer_stealth)

        return {
            "success": True,
            "target": target_process,
            "method_count": len(plans),
            "recommended": {
                "method": plans[0].method.value,
                "risk_level": plans[0].risk_level,
                "stealth_level": plans[0].stealth_level,
                "steps": plans[0].steps,
                "permissions": plans[0].required_permissions,
            },
            "alternatives": [
                {
                    "method": p.method.value,
                    "risk_level": p.risk_level,
                    "stealth_level": p.stealth_level,
                    "steps": p.steps,
                }
                for p in plans[1:4]
            ],
        }

    # ============================================================
    # 代码洞穴
    # ============================================================

    def find_code_caves(self, data: bytes, base_address: int = 0,
                        required_size: int = 0) -> dict:
        """寻找代码洞穴"""
        caves = self.code_cave_finder.find_caves(data, base_address)

        if required_size > 0:
            caves = [c for c in caves if c.size >= required_size]

        return {
            "success": True,
            "total_caves": len(caves),
            "total_usable_bytes": sum(c.size for c in caves),
            "largest_cave": max(c.size for c in caves) if caves else 0,
            "caves": [
                {
                    "address": hex(c.address),
                    "size": c.size,
                    "section": c.section or "unknown",
                    "alignment": c.alignment,
                }
                for c in caves[:20]
            ],
        }

    def find_best_cave(self, data: bytes, required_size: int,
                       base_address: int = 0) -> dict:
        """寻找最佳洞穴"""
        cave = self.code_cave_finder.find_best_cave(data, required_size, base_address)
        if cave:
            quality = self.code_cave_finder.analyze_cave_quality(cave, data, base_address)
            return {
                "success": True,
                "found": True,
                "address": hex(cave.address),
                "size": cave.size,
                "quality": quality,
            }
        return {"success": True, "found": False, "message": "No suitable cave found"}

    # ============================================================
    # Hook 生成
    # ============================================================

    def generate_inline_hook(self, target_addr: int, hook_addr: int,
                             original_bytes: bytes = b"",
                             is_64bit: bool = True) -> dict:
        """生成内联 Hook"""
        hook = self.hook_generator.generate_inline_hook(
            target_addr, hook_addr, original_bytes, is_64bit
        )
        return {
            "success": True,
            "hook_type": hook.hook_type.value,
            "target_addr": hex(hook.target_rva),
            "hook_code": hook.hook_code.hex(),
            "hook_size": hook.hook_size,
            "trampoline": hook.trampoline.hex() if hook.trampoline else "",
            "patches": hook.patches,
        }

    def generate_iat_hook(self, module_name: str, function_name: str,
                          hook_addr: int) -> dict:
        """生成 IAT Hook"""
        hook = self.hook_generator.generate_iat_hook(module_name, function_name, hook_addr)
        return {
            "success": True,
            "hook_type": hook.hook_type.value,
            "target_module": hook.target_module,
            "target_function": hook.target_function,
            "detour_function": hook.detour_function,
            "patches": hook.patches,
        }

    def generate_nop_patch(self, address: int, size: int) -> dict:
        """生成 NOP 补丁"""
        hook = self.hook_generator.generate_nop_patch(address, size)
        return {
            "success": True,
            "address": hex(address),
            "size": size,
            "hook_code": hook.hook_code.hex(),
            "patches": hook.patches,
        }

    # ============================================================
    # DLL 分析
    # ============================================================

    def analyze_dll(self, dll_name: str) -> dict:
        """分析 DLL"""
        result = self.dll_analyzer.analyze_dll(dll_name)
        return {
            "success": True,
            "dll": dll_name,
            "is_known_dll": result["is_known_dll"],
            "is_system_critical": result["is_system_critical"],
            "hijack_methods": [m.value for m in result["hijack_methods"]],
            "exports": result["exports"],
            "risk_assessment": result["risk_assessment"],
        }

    def find_hijack_opportunities(self, target_exe: str) -> dict:
        """寻找劫持机会"""
        opportunities = self.dll_analyzer.find_hijack_opportunities(target_exe)

        return {
            "success": True,
            "target": target_exe,
            "opportunity_count": len(opportunities),
            "top_opportunities": [
                {
                    "dll": o.dll_name,
                    "method": o.method.value,
                    "load_path": o.load_path,
                    "priority": o.priority,
                    "risk": o.risk_assessment,
                    "guide": o.exploit_guide,
                }
                for o in opportunities[:10]
            ],
        }

    # ============================================================
    # 代理 DLL 生成
    # ============================================================

    def generate_proxy_dll(self, target_dll: str, payload_code: str = "",
                           architecture: str = "x64") -> dict:
        """生成代理 DLL"""
        files = self.proxy_dll_generator.generate_proxy_dll(
            target_dll, payload_code, architecture
        )
        return {
            "success": True,
            "target_dll": target_dll,
            "generated_files": list(files.keys()),
            "files": files,
            "build_instructions": (
                "1. 使用 Visual Studio 开发者命令提示符\n"
                "2. 运行 build.bat\n"
                f"3. 将原始 {target_dll} 重命名为 {target_dll.replace('.dll', '_orig.dll')}\n"
                f"4. 将生成的 {target_dll} 放在目标程序目录"
            ),
        }

    # ============================================================
    # 安全分析
    # ============================================================

    def analyze_security(self, process_name: str,
                         code_data: bytes = b"") -> dict:
        """分析安全措施"""
        report = self.security_analyzer.analyze_security(process_name, code_data)

        return {
            "success": True,
            "process": process_name,
            "risk_score": report.risk_score,
            "overall_assessment": report.overall_assessment,
            "measures_detected": report.measures_detected,
            "bypass_suggestions": report.bypass_suggestions,
        }

    def scan_anti_tamper(self, data: bytes) -> dict:
        """扫描反篡改措施"""
        findings = self.security_analyzer.scan_for_anti_tamper(data)
        return {
            "success": True,
            "findings": findings,
            "has_packer": any(f["type"] == "packer" for f in findings),
            "has_drm": any("DRM" in f.get("name", "") for f in findings),
        }

    # ============================================================
    # 综合分析
    # ============================================================

    def comprehensive_analysis(self, process_name: str, exe_data: bytes = b"",
                               is_64bit: bool = True) -> dict:
        """综合分析"""
        # 进程分析
        process_info = self.process_analyzer.analyze_process(process_name)

        # 安全分析
        security = self.security_analyzer.analyze_security(process_name, exe_data)

        # 注入计划
        inject_plan = self.injection_planner.plan_injection(process_name, prefer_stealth=True)

        # DLL 劫持机会
        hijack = self.dll_analyzer.find_hijack_opportunities(process_name)

        # 代码洞穴
        caves = self.code_cave_finder.find_caves(exe_data) if exe_data else []

        return {
            "success": True,
            "target": process_name,
            "architecture": "x64" if is_64bit else "x86",
            "security": {
                "risk_score": security.risk_score,
                "assessment": security.overall_assessment,
                "measures": [m["pattern"] for m in security.measures_detected],
            },
            "injection": {
                "recommended_method": inject_plan[0].method.value if inject_plan else "unknown",
                "stealth_level": inject_plan[0].stealth_level if inject_plan else 0,
                "risk_level": inject_plan[0].risk_level if inject_plan else 0,
            },
            "dll_hijack": {
                "opportunities": len(hijack),
                "best_target": hijack[0].dll_name if hijack else "",
            },
            "code_caves": {
                "total_caves": len(caves),
                "total_usable": sum(c.size for c in caves),
            },
            "bypass_suggestions": security.bypass_suggestions,
        }


# ============================================================
# 快捷函数
# ============================================================

def quick_analyze(process_name: str) -> dict:
    """快速分析进程"""
    engine = CodeInjectEngine()
    return engine.comprehensive_analysis(process_name)


def quick_inject_plan(target: str, dll: str = "") -> dict:
    """快速获取注入计划"""
    engine = CodeInjectEngine()
    return engine.plan_injection(target, dll)


def quick_find_caves(data: bytes, min_size: int = 16) -> dict:
    """快速寻找代码洞穴"""
    engine = CodeInjectEngine()
    return engine.find_code_caves(data, required_size=min_size)


def quick_hook_plan(target_func: str, module: str = "") -> dict:
    """快速 Hook 计划"""
    engine = CodeInjectEngine()
    if module:
        return engine.generate_iat_hook(module, target_func, 0x1000)
    hook = engine.hook_generator.generate_inline_hook(0x1000, 0x2000, b"\x48\x89\x5C\x24\x08")
    return {
        "success": True,
        "hook_type": hook.hook_type.value,
        "hook_code": hook.hook_code.hex(),
        "hook_size": hook.hook_size,
    }