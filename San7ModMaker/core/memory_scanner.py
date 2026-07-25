"""
游戏进程内存扫描与代码注入引擎
===================================

专为三国群英传7设计的内存扫描器，支持：
- 跨平台进程附加（Windows / Wine/Linux）
- 精确值与模糊搜索（增/减/不变/变化/范围）
- AOB (Array of Bytes) 模式扫描
- 多级指针链解析
- Code Cave 搜索与代码注入
- 内存 Hook（Detour/IAT）
- 内存快照对比
- 内置游戏数值扫描预设

实现方式：
- Windows: ctypes + kernel32.dll (ReadProcessMemory/WriteProcessMemory/OpenProcess/...)
- Linux/Wine: /proc/pid/mem 直接读写
- 不依赖 pymem，纯 ctypes 实现
"""

import os
import re
import sys
import time
import struct
import ctypes
import logging
import platform
import threading
from ctypes import wintypes
from typing import Dict, List, Optional, Tuple, Any, Callable

# ============================================================
# 日志
# ============================================================
logger = logging.getLogger('San7ModMaker.MemoryScanner')

# ============================================================
# 平台检测
# ============================================================
IS_WINDOWS = platform.system() == 'Windows'
IS_WINE = False
if not IS_WINDOWS and sys.platform.startswith('linux'):
    try:
        # 检测是否在 Wine 下运行 Python
        import subprocess
        result = subprocess.run(['wine', '--version'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            IS_WINE = True
            logger.info("检测到 Wine 环境")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

# ============================================================
# Windows API 常量与 ctypes 声明
# ============================================================

# --- 进程权限常量 ---
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_CREATE_THREAD = 0x0002
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_ALL_ACCESS = 0x1F0FFF
PROCESS_SUSPEND_RESUME = 0x0800

# --- 内存保护常量 ---
PAGE_NOACCESS = 0x01
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE = 0x10
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
PAGE_GUARD = 0x100
PAGE_NOCACHE = 0x200
PAGE_WRITECOMBINE = 0x400

# --- 内存分配常量 ---
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
MEM_DECOMMIT = 0x4000
MEM_FREE = 0x10000

# --- 内存状态常量 ---
MEM_PRIVATE = 0x20000
MEM_MAPPED = 0x40000
MEM_IMAGE = 0x1000000

# --- 线程创建标志 ---
THREAD_CREATE_RUN_IMMEDIATE = 0x00000000
CREATE_SUSPENDED = 0x00000004
STACK_SIZE_PARAM_IS_A_RESERVATION = 0x00010000

# --- 工具常量 ---
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
NULL = 0

# 内存保护属性名称映射
PROTECTION_NAMES = {
    PAGE_NOACCESS: "NOACCESS",
    PAGE_READONLY: "READONLY",
    PAGE_READWRITE: "READWRITE",
    PAGE_WRITECOPY: "WRITECOPY",
    PAGE_EXECUTE: "EXECUTE",
    PAGE_EXECUTE_READ: "EXECUTE_READ",
    PAGE_EXECUTE_READWRITE: "EXECUTE_READWRITE",
    PAGE_EXECUTE_WRITECOPY: "EXECUTE_WRITECOPY",
    PAGE_GUARD: "GUARD",
    PAGE_NOCACHE: "NOCACHE",
    PAGE_WRITECOMBINE: "WRITECOMBINE",
}

# 内存状态名称映射
STATE_NAMES = {
    MEM_COMMIT: "COMMIT",
    MEM_RESERVE: "RESERVE",
    MEM_FREE: "FREE",
}

# 内存类型名称映射
TYPE_NAMES = {
    MEM_PRIVATE: "PRIVATE",
    MEM_MAPPED: "MAPPED",
    MEM_IMAGE: "IMAGE",
}


# --- Windows 结构体定义 ---
class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


class SYSTEM_INFO(ctypes.Structure):
    _fields_ = [
        ("wProcessorArchitecture", wintypes.WORD),
        ("wReserved", wintypes.WORD),
        ("dwPageSize", wintypes.DWORD),
        ("lpMinimumApplicationAddress", ctypes.c_void_p),
        ("lpMaximumApplicationAddress", ctypes.c_void_p),
        ("dwActiveProcessorMask", ctypes.c_void_p),
        ("dwNumberOfProcessors", wintypes.DWORD),
        ("dwProcessorType", wintypes.DWORD),
        ("dwAllocationGranularity", wintypes.DWORD),
        ("wProcessorLevel", wintypes.WORD),
        ("wProcessorRevision", wintypes.WORD),
    ]


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", ctypes.c_void_p),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260),
    ]


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ThreadID", wintypes.DWORD),
        ("th32OwnerProcessID", wintypes.DWORD),
        ("tpBasePri", wintypes.LONG),
        ("tpDeltaPri", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
    ]


# --- Windows API 函数声明 ---
_KERNEL32 = None
_PSAPI = None
_KERNEL32_HANDLE = None

if IS_WINDOWS or IS_WINE:
    try:
        _KERNEL32 = ctypes.windll.kernel32
        _PSAPI = ctypes.windll.psapi
    except (AttributeError, OSError) as e:
        logger.warning(f"无法加载 Windows API DLL: {e}")
        _KERNEL32 = None
        _PSAPI = None


def _setup_kernel32_functions():
    """设置 kernel32 函数签名"""
    if _KERNEL32 is None:
        return

    # OpenProcess
    _KERNEL32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _KERNEL32.OpenProcess.restype = wintypes.HANDLE

    # CloseHandle
    _KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
    _KERNEL32.CloseHandle.restype = wintypes.BOOL

    # ReadProcessMemory
    _KERNEL32.ReadProcessMemory.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)
    ]
    _KERNEL32.ReadProcessMemory.restype = wintypes.BOOL

    # WriteProcessMemory
    _KERNEL32.WriteProcessMemory.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)
    ]
    _KERNEL32.WriteProcessMemory.restype = wintypes.BOOL

    # VirtualAllocEx
    _KERNEL32.VirtualAllocEx.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD
    ]
    _KERNEL32.VirtualAllocEx.restype = ctypes.c_void_p

    # VirtualFreeEx
    _KERNEL32.VirtualFreeEx.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD
    ]
    _KERNEL32.VirtualFreeEx.restype = wintypes.BOOL

    # VirtualProtectEx
    _KERNEL32.VirtualProtectEx.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
    ]
    _KERNEL32.VirtualProtectEx.restype = wintypes.BOOL

    # VirtualQueryEx
    _KERNEL32.VirtualQueryEx.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t
    ]
    _KERNEL32.VirtualQueryEx.restype = ctypes.c_size_t

    # CreateRemoteThread
    _KERNEL32.CreateRemoteThread.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
    ]
    _KERNEL32.CreateRemoteThread.restype = wintypes.HANDLE

    # WaitForSingleObject
    _KERNEL32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _KERNEL32.WaitForSingleObject.restype = wintypes.DWORD

    # GetExitCodeThread
    _KERNEL32.GetExitCodeThread.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _KERNEL32.GetExitCodeThread.restype = wintypes.BOOL

    # GetModuleHandle
    _KERNEL32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    _KERNEL32.GetModuleHandleW.restype = wintypes.HANDLE

    # GetProcAddress
    _KERNEL32.GetProcAddress.argtypes = [wintypes.HANDLE, ctypes.c_char_p]
    _KERNEL32.GetProcAddress.restype = ctypes.c_void_p

    # CreateToolhelp32Snapshot
    _KERNEL32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _KERNEL32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

    # Process32First / Process32Next
    _KERNEL32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
    _KERNEL32.Process32FirstW.restype = wintypes.BOOL
    _KERNEL32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
    _KERNEL32.Process32NextW.restype = wintypes.BOOL

    # Module32First / Module32Next
    _KERNEL32.Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32)]
    _KERNEL32.Module32FirstW.restype = wintypes.BOOL
    _KERNEL32.Module32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32)]
    _KERNEL32.Module32NextW.restype = wintypes.BOOL

    # Thread32First / Thread32Next
    _KERNEL32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
    _KERNEL32.Thread32First.restype = wintypes.BOOL
    _KERNEL32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
    _KERNEL32.Thread32Next.restype = wintypes.BOOL

    # GetSystemInfo
    _KERNEL32.GetSystemInfo.argtypes = [ctypes.POINTER(SYSTEM_INFO)]
    _KERNEL32.GetSystemInfo.restype = None

    # GetCurrentProcess
    _KERNEL32.GetCurrentProcess.restype = wintypes.HANDLE

    # SuspendThread / ResumeThread
    _KERNEL32.SuspendThread.argtypes = [wintypes.HANDLE]
    _KERNEL32.SuspendThread.restype = wintypes.DWORD
    _KERNEL32.ResumeThread.argtypes = [wintypes.HANDLE]
    _KERNEL32.ResumeThread.restype = wintypes.DWORD

    # GetLastError
    _KERNEL32.GetLastError.restype = wintypes.DWORD


if _KERNEL32 is not None:
    _setup_kernel32_functions()


def _get_last_error() -> int:
    """获取最后一次 Windows API 错误码"""
    if _KERNEL32 is not None:
        return _KERNEL32.GetLastError()
    return 0


# ============================================================
# MemoryScanner 类
# ============================================================

class MemoryScanner:
    """
    游戏进程内存扫描与代码注入引擎

    独立于 pymem，使用纯 ctypes 实现跨平台内存操作。
    支持 Windows (kernel32.dll) 和 Linux/Wine (/proc/pid/mem) 两种后端。

    使用示例:
        scanner = MemoryScanner()
        scanner.attach("Sango7.exe")
        result = scanner.scan_exact_value(999, "int16")
        addresses = scanner.next_scan("increased")
        scanner.write_memory(0x123456, struct.pack("<i", 9999))
        scanner.detach()
    """

    # 内置扫描预设（游戏数值搜索模板）
    BUILTIN_PRESETS = {
        "money": {
            "label": "金钱",
            "value_type": "int32",
            "default_value": 1000,
            "description": "玩家金钱（4字节有符号整数）",
            "hint": "在游戏中消费或获得金钱后使用 next_scan 过滤",
        },
        "hp": {
            "label": "体力",
            "value_type": "int16",
            "default_value": 100,
            "description": "武将体力 HP（2字节）",
            "hint": "战斗或恢复后使用 increased/decreased 过滤",
        },
        "mp": {
            "label": "技力",
            "value_type": "int16",
            "default_value": 100,
            "description": "武将技力 MP（2字节）",
            "hint": "释放技能或恢复后使用 increased/decreased 过滤",
        },
        "level": {
            "label": "等级",
            "value_type": "int16",
            "default_value": 1,
            "description": "武将等级（2字节）",
            "hint": "升级后使用 increased 过滤",
        },
        "exp": {
            "label": "经验",
            "value_type": "int32",
            "default_value": 0,
            "description": "武将经验值（4字节）",
            "hint": "获得经验后使用 increased 过滤",
        },
        "troops": {
            "label": "兵力",
            "value_type": "int16",
            "default_value": 100,
            "description": "队伍兵力数量（2字节）",
            "hint": "战斗减员后使用 decreased 过滤，征兵后使用 increased 过滤",
        },
        "morale": {
            "label": "士气",
            "value_type": "int16",
            "default_value": 100,
            "description": "队伍士气（2字节）",
            "hint": "战斗后士气变化，使用 changed 过滤",
        },
        "strength": {
            "label": "武力",
            "value_type": "int8",
            "default_value": 80,
            "description": "武将武力值（1字节）",
            "hint": "装备道具后使用 increased 过滤",
        },
        "intelligence": {
            "label": "智力",
            "value_type": "int8",
            "default_value": 80,
            "description": "武将智力值（1字节）",
            "hint": "装备道具后使用 increased 过滤",
        },
        "population": {
            "label": "人口",
            "value_type": "int16",
            "default_value": 50000,
            "description": "城池人口（2字节）",
            "hint": "内政开发后使用 increased 过滤",
        },
        "gold_treasury": {
            "label": "国库金币",
            "value_type": "int32",
            "default_value": 10000,
            "description": "国库金币数量（4字节）",
            "hint": "消费/收入后使用 increased/decreased 过滤",
        },
        "food_treasury": {
            "label": "国库粮草",
            "value_type": "int32",
            "default_value": 10000,
            "description": "国库粮草数量（4字节）",
            "hint": "消耗/收入后使用 increased/decreased 过滤",
        },
        "defense": {
            "label": "城防",
            "value_type": "int16",
            "default_value": 100,
            "description": "城池防御值（2字节）",
            "hint": "修筑后使用 increased 过滤",
        },
        "development": {
            "label": "开发",
            "value_type": "int16",
            "default_value": 100,
            "description": "城池开发值（2字节）",
            "hint": "开发后使用 increased 过滤",
        },
        "support": {
            "label": "民心",
            "value_type": "int16",
            "default_value": 500,
            "description": "城池民心（2字节，0-1000）",
            "hint": "事件后使用 changed 过滤",
        },
        "year": {
            "label": "年份",
            "value_type": "int16",
            "default_value": 200,
            "description": "游戏时间年份（2字节）",
            "hint": "过年后使用 increased 过滤",
        },
        "month": {
            "label": "月份",
            "value_type": "int8",
            "default_value": 1,
            "description": "游戏时间月份（1字节）",
            "hint": "过月后使用 changed 过滤",
        },
        "day": {
            "label": "日期",
            "value_type": "int8",
            "default_value": 1,
            "description": "游戏时间日期（1字节）",
            "hint": "过天后使用 changed 过滤",
        },
        "merit": {
            "label": "功勋",
            "value_type": "int32",
            "default_value": 0,
            "description": "武将功勋值（4字节）",
            "hint": "战斗后使用 increased 过滤",
        },
        "battle_timer": {
            "label": "战斗计时",
            "value_type": "int16",
            "default_value": 99,
            "description": "千人战剩余时间（2字节）",
            "hint": "战斗中时间流逝，使用 decreased 过滤",
        },
    }

    # 值类型对应的 struct 格式和大小
    VALUE_TYPE_FORMATS = {
        "int8": ("b", 1),
        "uint8": ("B", 1),
        "int16": ("<h", 2),
        "uint16": ("<H", 2),
        "int32": ("<i", 4),
        "uint32": ("<I", 4),
        "int64": ("<q", 8),
        "uint64": ("<Q", 8),
        "float32": ("<f", 4),
        "float64": ("<d", 8),
    }

    def __init__(self):
        # --- 进程状态 ---
        self._process_handle = None
        self._process_id = None
        self._process_name = ""
        self._platform = "windows" if IS_WINDOWS else ("wine" if IS_WINE else "linux")
        self._base_address = 0
        self._module_list: List[dict] = []

        # --- 扫描状态 ---
        self._scan_results: Dict[int, bytes] = {}  # address -> raw bytes (上次扫描的快照)
        self._scan_previous: Dict[int, bytes] = {}  # 上上次扫描结果
        self._scan_initial: Dict[int, bytes] = {}   # 初始扫描结果
        self._scan_round = 0

        # --- 内存缓存 ---
        self._memory_cache: Dict[int, bytes] = {}  # 按页缓存已读取内存
        self._cache_page_size = 4096

        # --- Hook 管理 ---
        self._hooks: Dict[int, dict] = {}  # address -> {original_bytes, hook_code, hook_type}

        # --- 快照管理 ---
        self._snapshots: Dict[str, dict] = {}

        # --- 线程安全 ---
        self._lock = threading.Lock()

        # --- 内存备份（用于 write_memory 回滚） ---
        self._write_backups: List[dict] = []

        # --- 系统信息 ---
        self._system_info = self._get_native_system_info()

        logger.info(f"MemoryScanner 初始化，平台: {self._platform}")

    # ============================================================
    # 内部辅助方法
    # ============================================================

    def _get_native_system_info(self) -> dict:
        """获取系统信息"""
        info = {
            "platform": self._platform,
            "page_size": 4096,
            "allocation_granularity": 65536,
            "min_address": 0x10000,
            "max_address": 0x7FFFFFFF if not IS_WINDOWS else 0x7FFEFFFF,
        }
        if _KERNEL32 is not None:
            try:
                si = SYSTEM_INFO()
                _KERNEL32.GetSystemInfo(ctypes.byref(si))
                info["page_size"] = si.dwPageSize
                info["allocation_granularity"] = si.dwAllocationGranularity
                info["min_address"] = ctypes.cast(si.lpMinimumApplicationAddress, ctypes.c_void_p).value or 0x10000
                info["max_address"] = ctypes.cast(si.lpMaximumApplicationAddress, ctypes.c_void_p).value or 0x7FFFFFFF
            except Exception:
                pass
        return info

    def _get_page_base(self, address: int) -> int:
        """获取地址所在页基址"""
        page_size = self._system_info.get("page_size", 4096)
        return address - (address % page_size)

    def _invalidate_cache(self, address: int = None, size: int = None):
        """使内存缓存失效"""
        if address is None:
            self._memory_cache.clear()
        elif size is not None:
            page_start = self._get_page_base(address)
            page_end = self._get_page_base(address + size - 1) + self._system_info.get("page_size", 4096)
            keys_to_remove = [k for k in self._memory_cache if page_start <= k < page_end]
            for k in keys_to_remove:
                del self._memory_cache[k]

    def _is_address_valid(self, address: int) -> bool:
        """检查地址是否在有效范围内"""
        min_addr = self._system_info.get("min_address", 0x10000)
        max_addr = self._system_info.get("max_address", 0x7FFFFFFF)
        return min_addr <= address <= max_addr

    # ============================================================
    # 平台抽象层：内存读写
    # ============================================================

    def _native_read_memory(self, address: int, size: int) -> Optional[bytes]:
        """平台原生内存读取"""
        if self._process_handle is None:
            return None

        if IS_WINDOWS and _KERNEL32 is not None:
            # Windows API 读取
            buffer = ctypes.create_string_buffer(size)
            bytes_read = ctypes.c_size_t(0)
            success = _KERNEL32.ReadProcessMemory(
                self._process_handle,
                ctypes.c_void_p(address),
                buffer,
                size,
                ctypes.byref(bytes_read)
            )
            if success and bytes_read.value > 0:
                return buffer.raw[:bytes_read.value]
            elif not success:
                err = _get_last_error()
                if err != 0 and err != 299:  # 299 = 部分读取也是常见情况
                    logger.debug(f"ReadProcessMemory 失败 @ 0x{address:X}: 错误码 {err}")
            return None
        else:
            # Linux/Wine /proc/pid/mem 读取
            try:
                mem_path = f"/proc/{self._process_id}/mem"
                with open(mem_path, "rb") as f:
                    f.seek(address)
                    return f.read(size)
            except (IOError, OSError) as e:
                logger.debug(f"/proc/pid/mem 读取失败 @ 0x{address:X}: {e}")
                return None

    def _native_write_memory(self, address: int, data: bytes) -> bool:
        """平台原生内存写入"""
        if self._process_handle is None:
            return False

        if IS_WINDOWS and _KERNEL32 is not None:
            # Windows API 写入
            buffer = ctypes.create_string_buffer(data, len(data))
            bytes_written = ctypes.c_size_t(0)
            success = _KERNEL32.WriteProcessMemory(
                self._process_handle,
                ctypes.c_void_p(address),
                buffer,
                len(data),
                ctypes.byref(bytes_written)
            )
            if not success:
                logger.debug(f"WriteProcessMemory 失败 @ 0x{address:X}: 错误码 {_get_last_error()}")
            return success and bytes_written.value == len(data)
        else:
            # Linux/Wine /proc/pid/mem 写入
            try:
                mem_path = f"/proc/{self._process_id}/mem"
                with open(mem_path, "r+b") as f:
                    f.seek(address)
                    f.write(data)
                return True
            except (IOError, OSError) as e:
                logger.debug(f"/proc/pid/mem 写入失败 @ 0x{address:X}: {e}")
                return False

    def _native_virtual_protect(self, address: int, size: int, new_protect: int) -> Optional[int]:
        """修改内存页保护属性，返回旧保护"""
        if _KERNEL32 is not None and self._process_handle is not None:
            old_protect = wintypes.DWORD(0)
            success = _KERNEL32.VirtualProtectEx(
                self._process_handle,
                ctypes.c_void_p(address),
                size,
                new_protect,
                ctypes.byref(old_protect)
            )
            if success:
                return old_protect.value
        return None

    def _native_virtual_alloc(self, size: int, protect: int = PAGE_EXECUTE_READWRITE) -> Optional[int]:
        """在目标进程中分配内存"""
        if _KERNEL32 is not None and self._process_handle is not None:
            addr = _KERNEL32.VirtualAllocEx(
                self._process_handle,
                None,
                size,
                MEM_COMMIT | MEM_RESERVE,
                protect
            )
            if addr and addr != 0:
                return ctypes.cast(addr, ctypes.c_void_p).value or addr
        return None

    def _native_virtual_free(self, address: int, size: int = 0) -> bool:
        """释放目标进程中的内存"""
        if _KERNEL32 is not None and self._process_handle is not None:
            return _KERNEL32.VirtualFreeEx(
                self._process_handle,
                ctypes.c_void_p(address),
                size,
                MEM_RELEASE
            )
        return False

    def _native_create_remote_thread(self, address: int, arg: int = 0) -> Optional[int]:
        """在目标进程中创建远程线程"""
        if _KERNEL32 is not None and self._process_handle is not None:
            thread_id = wintypes.DWORD(0)
            h_thread = _KERNEL32.CreateRemoteThread(
                self._process_handle,
                None,
                0,
                ctypes.c_void_p(address),
                ctypes.c_void_p(arg),
                0,
                ctypes.byref(thread_id)
            )
            if h_thread and h_thread != INVALID_HANDLE_VALUE:
                return thread_id.value
        return None

    # ============================================================
    # 进程管理
    # ============================================================

    def attach(self, process_name: str = "Sango7.exe") -> dict:
        """
        附加到游戏进程

        自动检测进程 PID、获取进程句柄、读取进程基本信息（基址、模块列表、内存区域）。

        参数:
            process_name: 进程名称，默认为 "Sango7.exe"

        返回:
            {success, pid, process_name, base_address, module_count, platform, message}
        """
        with self._lock:
            # 先断开已有连接
            if self._process_handle is not None:
                self.detach()

            pid = None
            process_found = ""

            if IS_WINDOWS and _KERNEL32 is not None:
                # Windows: 使用 CreateToolhelp32Snapshot 枚举进程
                snapshot = _KERNEL32.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
                if snapshot and snapshot != INVALID_HANDLE_VALUE:
                    pe = PROCESSENTRY32()
                    pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
                    if _KERNEL32.Process32FirstW(snapshot, ctypes.byref(pe)):
                        while True:
                            try:
                                exe_name = pe.szExeFile.decode('utf-8', errors='replace')
                            except (UnicodeDecodeError, AttributeError):
                                try:
                                    exe_name = pe.szExeFile.decode('gbk', errors='replace')
                                except (UnicodeDecodeError, AttributeError):
                                    exe_name = str(pe.szExeFile)

                            # 匹配进程名（支持大小写不敏感）
                            if process_name.lower() in exe_name.lower():
                                pid = pe.th32ProcessID
                                process_found = exe_name
                                break
                            if not _KERNEL32.Process32NextW(snapshot, ctypes.byref(pe)):
                                break
                    _KERNEL32.CloseHandle(snapshot)
            else:
                # Linux: 遍历 /proc
                try:
                    for entry in os.listdir("/proc"):
                        if not entry.isdigit():
                            continue
                        try:
                            cmdline_path = f"/proc/{entry}/cmdline"
                            with open(cmdline_path, "rb") as f:
                                cmdline = f.read().replace(b'\x00', b' ').decode('utf-8', errors='replace')
                            # 检查是否包含进程名 (Wine 进程可能包含 .exe 路径)
                            if process_name.lower() in cmdline.lower() or (
                                IS_WINE and ".exe" in cmdline.lower() and
                                any(term in cmdline.lower() for term in process_name.lower().replace('.exe', '').split())
                            ):
                                pid = int(entry)
                                process_found = cmdline.strip()
                                break
                        except (IOError, OSError, ValueError):
                            continue
                except (IOError, OSError):
                    pass

            if pid is None:
                return {
                    "success": False,
                    "message": f"未找到运行中的 {process_name} 进程",
                    "platform": self._platform,
                }

            # 打开进程
            if IS_WINDOWS and _KERNEL32 is not None:
                desired_access = (
                    PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION |
                    PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION | PROCESS_SUSPEND_RESUME
                )
                handle = _KERNEL32.OpenProcess(desired_access, False, pid)
                if not handle or handle == INVALID_HANDLE_VALUE:
                    # 尝试降级权限
                    handle = _KERNEL32.OpenProcess(
                        PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION, False, pid
                    )
                if not handle or handle == INVALID_HANDLE_VALUE:
                    return {
                        "success": False,
                        "message": f"无法打开进程 PID={pid}，错误码: {_get_last_error()}",
                        "pid": pid,
                    }
                self._process_handle = handle
            else:
                # Linux/Wine: 只需要 PID
                self._process_handle = pid  # 存储 PID 作为句柄引用

            self._process_id = pid
            self._process_name = process_found

            # 获取模块列表和基址
            modules = self._enumerate_modules()
            base_address = 0
            if modules:
                # 找到主模块 (.exe) 的基址
                for mod in modules:
                    if mod.get("name", "").lower() in process_found.lower() or (
                        mod.get("name", "").lower().endswith(".exe")
                    ):
                        base_address = mod.get("base_address", 0)
                        break
                if base_address == 0 and modules:
                    base_address = modules[0].get("base_address", 0)

            self._base_address = base_address
            self._module_list = modules

            # 重置扫描状态
            self._scan_results.clear()
            self._scan_previous.clear()
            self._scan_initial.clear()
            self._scan_round = 0
            self._memory_cache.clear()

            logger.info(f"已附加到进程 {process_found} (PID={pid}), 基址=0x{base_address:X}")

            return {
                "success": True,
                "pid": pid,
                "process_name": process_found,
                "base_address": base_address,
                "base_address_hex": hex(base_address) if base_address else "0x0",
                "module_count": len(modules),
                "platform": self._platform,
                "message": f"已附加到 {process_found} (PID={pid})",
            }

    def detach(self) -> dict:
        """
        断开进程连接

        返回:
            {success, message}
        """
        with self._lock:
            if self._process_handle is None:
                return {"success": False, "message": "未附加到任何进程"}

            pid = self._process_id
            name = self._process_name

            if IS_WINDOWS and _KERNEL32 is not None:
                try:
                    _KERNEL32.CloseHandle(self._process_handle)
                except Exception:
                    pass

            self._process_handle = None
            self._process_id = None
            self._process_name = ""
            self._base_address = 0
            self._module_list.clear()
            self._scan_results.clear()
            self._scan_previous.clear()
            self._scan_initial.clear()
            self._scan_round = 0
            self._memory_cache.clear()

            logger.info(f"已断开进程 {name} (PID={pid})")
            return {"success": True, "message": f"已断开 {name} (PID={pid})"}

    def is_attached(self) -> bool:
        """
        检查是否已附加到进程

        返回:
            True 如果已附加
        """
        if self._process_handle is None:
            return False
        if IS_WINDOWS and _KERNEL32 is not None:
            # 检查进程是否仍然存在
            try:
                code = wintypes.DWORD(0)
                if _KERNEL32.GetExitCodeProcess(self._process_handle, ctypes.byref(code)):
                    return code.value == 259  # STILL_ACTIVE
            except Exception:
                pass
            return True
        else:
            # Linux: 检查 /proc/pid 是否存在
            if self._process_id:
                return os.path.exists(f"/proc/{self._process_id}")
            return False

    def get_process_info(self) -> dict:
        """
        获取进程详细信息

        返回:
            {success, pid, process_name, base_address, modules, thread_count,
             memory_usage, is_wow64, platform, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        info = {
            "success": True,
            "pid": self._process_id,
            "process_name": self._process_name,
            "base_address": self._base_address,
            "base_address_hex": hex(self._base_address) if self._base_address else "0x0",
            "platform": self._platform,
            "modules": self._module_list[:50],  # 限制返回数量
            "module_count": len(self._module_list),
            "thread_count": 0,
            "memory_usage_mb": 0,
            "is_wow64": False,
        }

        # 获取线程数
        if IS_WINDOWS and _KERNEL32 is not None:
            snapshot = _KERNEL32.CreateToolhelp32Snapshot(0x00000004, 0)  # TH32CS_SNAPTHREAD
            if snapshot and snapshot != INVALID_HANDLE_VALUE:
                te = THREADENTRY32()
                te.dwSize = ctypes.sizeof(THREADENTRY32)
                thread_count = 0
                if _KERNEL32.Thread32First(snapshot, ctypes.byref(te)):
                    while True:
                        if te.th32OwnerProcessID == self._process_id:
                            thread_count += 1
                        if not _KERNEL32.Thread32Next(snapshot, ctypes.byref(te)):
                            break
                _KERNEL32.CloseHandle(snapshot)
                info["thread_count"] = thread_count
        else:
            try:
                task_path = f"/proc/{self._process_id}/status"
                with open(task_path, "r") as f:
                    for line in f:
                        if line.startswith("Threads:"):
                            info["thread_count"] = int(line.split(":")[1].strip())
                            break
            except (IOError, OSError, ValueError):
                pass

        # 获取内存使用
        if IS_WINDOWS and _PSAPI is not None:
            try:
                class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                    _fields_ = [
                        ("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t),
                    ]
                pmc = PROCESS_MEMORY_COUNTERS()
                pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                _PSAPI.GetProcessMemoryInfo(
                    self._process_handle,
                    ctypes.byref(pmc),
                    pmc.cb
                )
                info["memory_usage_mb"] = round(pmc.WorkingSetSize / (1024 * 1024), 2)
            except Exception:
                pass
        else:
            try:
                statm_path = f"/proc/{self._process_id}/statm"
                with open(statm_path, "r") as f:
                    parts = f.read().split()
                    if parts:
                        # 第一个字段是总虚拟内存（页），乘以页大小
                        info["memory_usage_mb"] = round(int(parts[0]) * 4 / 1024, 2)
            except (IOError, OSError, ValueError):
                pass

        return info

    def _enumerate_modules(self) -> List[dict]:
        """枚举进程已加载模块"""
        modules = []
        if IS_WINDOWS and _KERNEL32 is not None and self._process_id:
            snapshot = _KERNEL32.CreateToolhelp32Snapshot(0x00000008, self._process_id)  # TH32CS_SNAPMODULE
            if snapshot and snapshot != INVALID_HANDLE_VALUE:
                me = MODULEENTRY32()
                me.dwSize = ctypes.sizeof(MODULEENTRY32)
                if _KERNEL32.Module32FirstW(snapshot, ctypes.byref(me)):
                    while True:
                        try:
                            name = me.szModule.decode('utf-8', errors='replace')
                        except (UnicodeDecodeError, AttributeError):
                            try:
                                name = me.szModule.decode('gbk', errors='replace')
                            except (UnicodeDecodeError, AttributeError):
                                name = str(me.szModule)
                        try:
                            path = me.szExePath.decode('utf-8', errors='replace')
                        except (UnicodeDecodeError, AttributeError):
                            try:
                                path = me.szExePath.decode('gbk', errors='replace')
                            except (UnicodeDecodeError, AttributeError):
                                path = str(me.szExePath)
                        base = ctypes.cast(me.modBaseAddr, ctypes.c_void_p).value or me.modBaseAddr
                        modules.append({
                            "name": name,
                            "path": path,
                            "base_address": base,
                            "base_address_hex": hex(base) if base else "0x0",
                            "size": me.modBaseSize,
                            "size_hex": hex(me.modBaseSize),
                        })
                        if not _KERNEL32.Module32NextW(snapshot, ctypes.byref(me)):
                            break
                _KERNEL32.CloseHandle(snapshot)
        elif self._process_id:
            # Linux: 读取 /proc/pid/maps 获取模块
            try:
                maps_path = f"/proc/{self._process_id}/maps"
                with open(maps_path, "r") as f:
                    seen_base = set()
                    for line in f:
                        # 格式: address perms offset dev inode pathname
                        parts = line.strip().split(None, 5)
                        if len(parts) >= 6:
                            addr_range = parts[0].split('-')
                            start = int(addr_range[0], 16)
                            path = parts[5]
                            name = os.path.basename(path)
                            if name and start not in seen_base:
                                seen_base.add(start)
                                if '.exe' in name.lower() or '.dll' in name.lower() or '.so' in name.lower():
                                    modules.append({
                                        "name": name,
                                        "path": path,
                                        "base_address": start,
                                        "base_address_hex": hex(start),
                                        "size": 0,
                                        "size_hex": "0x0",
                                    })
            except (IOError, OSError):
                pass
        return modules

    # ============================================================
    # 内存读写
    # ============================================================

    def read_memory(self, address: int, size: int) -> dict:
        """
        读取指定地址的内存

        参数:
            address: 内存地址
            size: 读取字节数

        返回:
            {success, address, size, raw_bytes, hex_preview, printable}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        if not self._is_address_valid(address):
            return {"success": False, "message": f"地址无效: 0x{address:X}"}

        if size <= 0:
            return {"success": False, "message": "size 必须大于 0"}

        if size > 1024 * 1024:  # 限制 1MB
            return {"success": False, "message": "单次读取不能超过 1MB"}

        try:
            data = self._native_read_memory(address, size)
            if data is None:
                return {"success": False, "message": f"读取失败 @ 0x{address:X}"}

            # 生成十六进制预览
            hex_str = data.hex()
            if len(hex_str) > 128:
                hex_preview = ' '.join(hex_str[i:i+2] for i in range(0, 64, 2)) + " ..."
            else:
                hex_preview = ' '.join(hex_str[i:i+2] for i in range(0, len(hex_str), 2))

            # 生成可打印字符预览
            printable = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[:64])

            return {
                "success": True,
                "address": address,
                "address_hex": hex(address),
                "size": len(data),
                "raw_bytes": list(data),
                "hex_preview": hex_preview,
                "full_hex": hex_str,
                "printable": printable,
            }
        except Exception as e:
            logger.error(f"read_memory 异常 @ 0x{address:X}: {e}")
            return {"success": False, "message": f"读取异常: {str(e)}"}

    def write_memory(self, address: int, data: bytes) -> dict:
        """
        写入内存，自动备份原始数据用于回滚

        参数:
            address: 目标地址
            data: 要写入的字节数据

        返回:
            {success, address, size, backup_index, message}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        if not self._is_address_valid(address):
            return {"success": False, "message": f"地址无效: 0x{address:X}"}

        if not data:
            return {"success": False, "message": "数据不能为空"}

        try:
            # 备份原始数据
            original = self._native_read_memory(address, len(data))
            backup_index = len(self._write_backups)
            self._write_backups.append({
                "index": backup_index,
                "address": address,
                "size": len(data),
                "original": original,
                "timestamp": time.time(),
            })

            # 写入新数据
            success = self._native_write_memory(address, data)
            if not success:
                return {"success": False, "message": f"写入失败 @ 0x{address:X}"}

            # 使缓存失效
            self._invalidate_cache(address, len(data))

            return {
                "success": True,
                "address": address,
                "address_hex": hex(address),
                "size": len(data),
                "backup_index": backup_index,
                "hex_data": data.hex(),
                "message": f"已写入 {len(data)} 字节到 0x{address:X}",
            }
        except Exception as e:
            logger.error(f"write_memory 异常 @ 0x{address:X}: {e}")
            return {"success": False, "message": f"写入异常: {str(e)}"}

    def read_pointer(self, address: int, offsets: List[int]) -> dict:
        """
        解析多级指针链

        从基址开始，依次解引用每个偏移量。
        例如: read_pointer(0x123456, [0x10, 0x4, 0x8]) 会读取:
            [0x123456] + 0x10 -> [result] + 0x4 -> [result] + 0x8 -> final

        参数:
            address: 指针链基址
            offsets: 偏移量列表

        返回:
            {success, final_address, pointer_chain, value, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        chain = []
        current = address

        for i, offset in enumerate(offsets):
            # 读取当前地址的指针值（4字节）
            ptr_data = self._native_read_memory(current, 4)
            if ptr_data is None or len(ptr_data) < 4:
                return {
                    "success": False,
                    "message": f"指针链在第 {i} 级断开 @ 0x{current:X}",
                    "pointer_chain": chain,
                    "failed_at": i,
                    "failed_address": current,
                }

            ptr_value = struct.unpack("<I", ptr_data[:4])[0]
            chain.append({
                "level": i,
                "address": current,
                "address_hex": hex(current),
                "offset": offset,
                "pointer_value": ptr_value,
                "pointer_value_hex": hex(ptr_value),
            })

            if i < len(offsets) - 1:
                current = ptr_value + offset
            else:
                current = ptr_value + offset  # 最终地址

        # 读取最终值（4字节）
        final_data = self._native_read_memory(current, 4)
        final_value = None
        if final_data and len(final_data) >= 4:
            final_value = struct.unpack("<I", final_data[:4])[0]

        return {
            "success": True,
            "base_address": address,
            "base_address_hex": hex(address),
            "final_address": current,
            "final_address_hex": hex(current),
            "value": final_value,
            "value_hex": hex(final_value) if final_value is not None else None,
            "pointer_chain": chain,
            "depth": len(offsets),
        }

    def write_pointer(self, address: int, offsets: List[int], value: bytes) -> dict:
        """
        通过指针链写入值

        参数:
            address: 指针链基址
            offsets: 偏移量列表
            value: 要写入的字节数据

        返回:
            {success, final_address, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        # 先解析指针链找到最终地址
        chain = []
        current = address

        for i, offset in enumerate(offsets):
            ptr_data = self._native_read_memory(current, 4)
            if ptr_data is None or len(ptr_data) < 4:
                return {
                    "success": False,
                    "message": f"指针链在第 {i} 级断开",
                    "pointer_chain": chain,
                }

            ptr_value = struct.unpack("<I", ptr_data[:4])[0]
            chain.append({
                "level": i,
                "address": current,
                "offset": offset,
                "pointer_value": ptr_value,
            })
            current = ptr_value + offset

        # 写入最终地址
        result = self.write_memory(current, value)
        if result["success"]:
            result["pointer_chain"] = chain
            result["final_address"] = current
            result["final_address_hex"] = hex(current)
        return result

    # ============================================================
    # 精确值扫描
    # ============================================================

    def scan_exact_value(self, value: int, value_type: str = "int32") -> dict:
        """
        扫描精确值

        参数:
            value: 要搜索的值
            value_type: 值类型 (int8/int16/int32/int64/float32/float64/bytes)

        返回:
            {success, count, matches, scan_time, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        if value_type not in self.VALUE_TYPE_FORMATS:
            return {"success": False, "message": f"不支持的值类型: {value_type}，支持: {list(self.VALUE_TYPE_FORMATS.keys())}"}

        fmt, size = self.VALUE_TYPE_FORMATS[value_type]
        try:
            pattern = struct.pack(fmt, value)
        except struct.error as e:
            return {"success": False, "message": f"值打包失败: {e}"}

        return self._scan_memory_for_pattern(pattern, value_type)

    def scan_exact_text(self, text: str, encoding: str = "gbk") -> dict:
        """
        扫描精确文本

        参数:
            text: 要搜索的文本
            encoding: 编码方式，默认 gbk（三国群英传7使用 GBK 编码）

        返回:
            {success, count, matches, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        try:
            pattern = text.encode(encoding)
        except (UnicodeEncodeError, LookupError) as e:
            return {"success": False, "message": f"编码失败: {e}"}

        # 同时搜索带 null 终止符和不带的版本
        pattern_null = pattern + b'\x00'
        return self._scan_memory_for_pattern(pattern, "text", alt_pattern=pattern_null)

    def scan_pattern(self, pattern: bytes, mask: str = None) -> dict:
        """
        AOB (Array of Bytes) 模式扫描

        mask 中 'x' 表示必须匹配，'?' 表示忽略该字节。
        如果不提供 mask，则进行精确匹配。

        参数:
            pattern: 字节模式
            mask: 匹配掩码，'x'=必须匹配，'?'=忽略

        返回:
            {success, count, matches, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        if not pattern:
            return {"success": False, "message": "模式不能为空"}

        if mask is None:
            return self._scan_memory_for_pattern(pattern, "aob")

        if len(mask) != len(pattern):
            return {"success": False, "message": f"mask 长度 ({len(mask)}) 与 pattern 长度 ({len(pattern)}) 不匹配"}

        return self._scan_memory_for_pattern(pattern, "aob", mask=mask)

    def _scan_memory_for_pattern(self, pattern: bytes, value_type: str = "",
                                  alt_pattern: bytes = None, mask: str = None) -> dict:
        """内部扫描实现：遍历所有可读内存区域搜索模式"""
        regions = self._get_readable_regions()
        if not regions:
            return {"success": False, "message": "无法枚举内存区域"}

        matches = []
        start_time = time.time()
        total_scanned = 0
        chunk_size = 64 * 1024  # 64KB 块

        for region in regions:
            base = region["base"]
            size = region["size"]
            if size <= 0 or size > 512 * 1024 * 1024:  # 跳过无效和超大区域
                continue

            offset = 0
            while offset < size:
                read_size = min(chunk_size, size - offset)
                data = self._native_read_memory(base + offset, read_size)
                if data is None:
                    offset += self._system_info.get("page_size", 4096)
                    continue

                total_scanned += len(data)
                self._search_in_buffer(data, pattern, base + offset, matches,
                                       alt_pattern, mask, value_type)
                offset += read_size - len(pattern) + 1  # 重叠以确保不遗漏跨块匹配

        scan_time = round(time.time() - start_time, 3)

        # 限制返回数量
        max_matches = 5000
        truncated = len(matches) > max_matches
        if truncated:
            matches = matches[:max_matches]

        result = {
            "success": True,
            "count": len(matches),
            "matches": matches,
            "scan_time": scan_time,
            "total_scanned_mb": round(total_scanned / (1024 * 1024), 2),
            "truncated": truncated,
            "value_type": value_type,
            "pattern_hex": pattern.hex() if len(pattern) <= 32 else pattern[:32].hex() + "...",
        }

        if mask:
            result["mask"] = mask

        return result

    def _search_in_buffer(self, data: bytes, pattern: bytes, base_addr: int,
                          results: list, alt_pattern: bytes = None,
                          mask: str = None, value_type: str = ""):
        """在缓冲区中搜索模式"""
        if mask:
            # 带掩码的模式匹配
            pat_len = len(pattern)
            for i in range(len(data) - pat_len + 1):
                match = True
                for j in range(pat_len):
                    if mask[j] == 'x' and data[i + j] != pattern[j]:
                        match = False
                        break
                if match:
                    addr = base_addr + i
                    results.append({
                        "address": addr,
                        "address_hex": hex(addr),
                        "value_type": value_type,
                    })
        else:
            # 精确匹配
            pos = 0
            while True:
                pos = data.find(pattern, pos)
                if pos == -1:
                    break
                addr = base_addr + pos
                results.append({
                    "address": addr,
                    "address_hex": hex(addr),
                    "value_type": value_type,
                })
                pos += 1

            # 搜索替代模式
            if alt_pattern:
                pos = 0
                while True:
                    pos = data.find(alt_pattern, pos)
                    if pos == -1:
                        break
                    addr = base_addr + pos
                    results.append({
                        "address": addr,
                        "address_hex": hex(addr),
                        "value_type": value_type,
                    })
                    pos += 1

    def _get_readable_regions(self) -> List[dict]:
        """获取所有可读内存区域"""
        regions = self.enumerate_regions()
        if not regions.get("success"):
            return []

        readable = []
        for r in regions.get("regions", []):
            protect = r.get("protect", 0)
            state = r.get("state", 0)
            # 跳过未提交和无效保护的内存
            if state == MEM_FREE:
                continue
            if protect == PAGE_NOACCESS:
                continue
            readable.append(r)
        return readable

    # ============================================================
    # 模糊搜索
    # ============================================================

    def new_scan(self) -> dict:
        """
        开始新一轮扫描

        重置扫描状态，读取所有可读内存区域作为初始结果集。
        之后使用 next_scan() 进行多轮过滤。

        返回:
            {success, count, regions_scanned, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        with self._lock:
            self._scan_previous = dict(self._scan_results)
            self._scan_results.clear()
            self._scan_initial.clear()
            self._scan_round = 0

            regions = self._get_readable_regions()
            if not regions:
                return {"success": False, "message": "无法枚举可读内存区域"}

            start_time = time.time()
            total_scanned = 0
            chunk_size = 64 * 1024

            for region in regions:
                base = region["base"]
                size = region["size"]
                if size <= 0 or size > 512 * 1024 * 1024:
                    continue

                offset = 0
                while offset < size:
                    read_size = min(chunk_size, size - offset)
                    data = self._native_read_memory(base + offset, read_size)
                    if data is None:
                        offset += self._system_info.get("page_size", 4096)
                        continue

                    total_scanned += len(data)
                    # 将每个地址的字节值存储到扫描结果中
                    for i in range(len(data)):
                        addr = base + offset + i
                        self._scan_results[addr] = bytes([data[i]])

                    offset += read_size

            self._scan_initial = dict(self._scan_results)
            self._scan_round = 1

            scan_time = round(time.time() - start_time, 3)

            logger.info(f"new_scan: 扫描了 {total_scanned / (1024*1024):.1f} MB, "
                        f"找到 {len(self._scan_results)} 个地址")

            return {
                "success": True,
                "count": len(self._scan_results),
                "total_scanned_mb": round(total_scanned / (1024 * 1024), 2),
                "scan_time": scan_time,
                "round": self._scan_round,
                "message": f"初始扫描完成，共 {len(self._scan_results)} 个地址，可进行 next_scan 过滤",
            }

    def next_scan(self, filter_type: str, **kwargs) -> dict:
        """
        对当前结果集进行过滤扫描

        参数:
            filter_type: 过滤类型
                - "exact": 精确值匹配，需要 value 和 value_type
                - "increased": 值增大
                - "decreased": 值减小
                - "unchanged": 值未变化
                - "changed": 值变化（任意变化）
                - "range": 值在范围内，需要 min_val 和 max_val
                - "pattern": 模式匹配，需要 pattern 和可选的 mask

        关键字参数:
            value: 精确值（用于 exact）
            value_type: 值类型（用于 exact/range），默认 "int32"
            min_val: 最小值（用于 range）
            max_val: 最大值（用于 range）
            pattern: 字节模式（用于 pattern）
            mask: 掩码（用于 pattern）

        返回:
            {success, count, eliminated, round, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        if not self._scan_results:
            return {"success": False, "message": "请先调用 new_scan() 开始扫描"}

        with self._lock:
            self._scan_previous = dict(self._scan_results)
            old_count = len(self._scan_results)
            new_results = {}
            start_time = time.time()

            value_type = kwargs.get("value_type", "int32")
            fmt, val_size = self.VALUE_TYPE_FORMATS.get(value_type, ("<i", 4))

            # 批量读取当前内存值
            # 先按地址范围分组，减少读取次数
            addresses = sorted(self._scan_results.keys())
            addr_groups = self._group_addresses_by_region(addresses)

            for base_addr, addrs in addr_groups.items():
                if not addrs:
                    continue
                min_addr = min(addrs)
                max_addr = max(addrs) + val_size
                read_size = max_addr - min_addr
                if read_size > 1024 * 1024:
                    continue

                data = self._native_read_memory(min_addr, read_size)
                if data is None:
                    continue

                for addr in addrs:
                    offset = addr - min_addr
                    if offset + val_size > len(data):
                        continue

                    prev_bytes = self._scan_results.get(addr)
                    cur_bytes = data[offset:offset + val_size]

                    if filter_type == "exact":
                        try:
                            target = struct.pack(fmt, kwargs.get("value", 0))
                        except struct.error:
                            continue
                        if cur_bytes == target:
                            new_results[addr] = cur_bytes

                    elif filter_type == "increased":
                        if prev_bytes is not None and cur_bytes > prev_bytes:
                            new_results[addr] = cur_bytes

                    elif filter_type == "decreased":
                        if prev_bytes is not None and cur_bytes < prev_bytes:
                            new_results[addr] = cur_bytes

                    elif filter_type == "unchanged":
                        if prev_bytes is not None and cur_bytes == prev_bytes:
                            new_results[addr] = cur_bytes

                    elif filter_type == "changed":
                        if prev_bytes is not None and cur_bytes != prev_bytes:
                            new_results[addr] = cur_bytes

                    elif filter_type == "range":
                        try:
                            cur_val = struct.unpack(fmt, cur_bytes)[0]
                            min_val = kwargs.get("min_val", 0)
                            max_val = kwargs.get("max_val", 0)
                            if min_val <= cur_val <= max_val:
                                new_results[addr] = cur_bytes
                        except (struct.error, ValueError):
                            continue

                    elif filter_type == "pattern":
                        pattern = kwargs.get("pattern")
                        mask = kwargs.get("mask")
                        if pattern is None:
                            continue
                        if self._match_pattern(cur_bytes, pattern, mask):
                            new_results[addr] = cur_bytes

                    else:
                        return {"success": False, "message": f"不支持的过滤类型: {filter_type}"}

            self._scan_results = new_results
            self._scan_round += 1
            eliminated = old_count - len(new_results)
            scan_time = round(time.time() - start_time, 3)

            logger.info(f"next_scan({filter_type}): {old_count} -> {len(new_results)} "
                        f"(-{eliminated}), 轮次 {self._scan_round}")

            return {
                "success": True,
                "count": len(new_results),
                "previous_count": old_count,
                "eliminated": eliminated,
                "round": self._scan_round,
                "scan_time": scan_time,
                "filter_type": filter_type,
                "message": f"过滤后剩余 {len(new_results)} 个地址（淘汰 {eliminated} 个）",
            }

    def _group_addresses_by_region(self, addresses: List[int]) -> Dict[int, List[int]]:
        """将地址按内存区域分组"""
        groups = {}
        for addr in addresses:
            page = self._get_page_base(addr)
            if page not in groups:
                groups[page] = []
            groups[page].append(addr)
        return groups

    def _match_pattern(self, data: bytes, pattern: bytes, mask: str = None) -> bool:
        """检查数据是否匹配模式"""
        if mask is None:
            return data == pattern
        if len(data) < len(pattern):
            return False
        for i in range(len(pattern)):
            if i >= len(data):
                return False
            if mask[i] == 'x' and data[i] != pattern[i]:
                return False
        return True

    def scan_increased(self) -> dict:
        """扫描所有增大的值（相对于上次扫描）"""
        return self.next_scan("increased")

    def scan_decreased(self) -> dict:
        """扫描所有减小的值"""
        return self.next_scan("decreased")

    def scan_unchanged(self) -> dict:
        """扫描所有未变化的值"""
        return self.next_scan("unchanged")

    def scan_changed(self) -> dict:
        """扫描所有变化的值"""
        return self.next_scan("changed")

    def scan_range(self, min_val: int, max_val: int, value_type: str = "int32") -> dict:
        """扫描值在指定范围内的地址"""
        return self.next_scan("range", min_val=min_val, max_val=max_val, value_type=value_type)

    # ============================================================
    # 内存区域分析
    # ============================================================

    def enumerate_regions(self) -> dict:
        """
        枚举进程的所有内存区域

        返回每个区域的基址、大小、保护属性、状态、类型。

        返回:
            {success, region_count, regions, total_size_mb, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        regions = []
        total_size = 0

        if IS_WINDOWS and _KERNEL32 is not None:
            # Windows: 使用 VirtualQueryEx
            min_addr = self._system_info.get("min_address", 0x10000)
            max_addr = self._system_info.get("max_address", 0x7FFFFFFF)
            address = min_addr

            while address < max_addr:
                mbi = MEMORY_BASIC_INFORMATION()
                result = _KERNEL32.VirtualQueryEx(
                    self._process_handle,
                    ctypes.c_void_p(address),
                    ctypes.byref(mbi),
                    ctypes.sizeof(MEMORY_BASIC_INFORMATION)
                )
                if result == 0:
                    break

                base = ctypes.cast(mbi.BaseAddress, ctypes.c_void_p).value or mbi.BaseAddress
                region_size = mbi.RegionSize

                if mbi.State != MEM_FREE:
                    regions.append({
                        "base": base,
                        "base_hex": hex(base) if base else "0x0",
                        "size": region_size,
                        "size_hex": hex(region_size),
                        "protect": mbi.Protect,
                        "protect_name": self._get_protection_name(mbi.Protect),
                        "allocation_protect": mbi.AllocationProtect,
                        "allocation_protect_name": self._get_protection_name(mbi.AllocationProtect),
                        "state": mbi.State,
                        "state_name": STATE_NAMES.get(mbi.State, f"UNKNOWN({mbi.State})"),
                        "type": mbi.Type,
                        "type_name": TYPE_NAMES.get(mbi.Type, f"UNKNOWN({mbi.Type})"),
                    })
                    total_size += region_size

                address = base + region_size
        else:
            # Linux: 读取 /proc/pid/maps
            try:
                maps_path = f"/proc/{self._process_id}/maps"
                with open(maps_path, "r") as f:
                    for line in f:
                        parts = line.strip().split(None, 5)
                        if len(parts) < 5:
                            continue
                        addr_range = parts[0].split('-')
                        start = int(addr_range[0], 16)
                        end = int(addr_range[1], 16)
                        perms = parts[1]
                        size = end - start
                        path = parts[5] if len(parts) > 5 else ""

                        protect = 0
                        if 'r' in perms:
                            protect |= PAGE_READONLY
                        if 'w' in perms:
                            protect |= PAGE_READWRITE
                        if 'x' in perms:
                            protect |= PAGE_EXECUTE_READ

                        region_type = MEM_PRIVATE
                        if path and ('.so' in path or '.exe' in path or '.dll' in path):
                            region_type = MEM_IMAGE
                        elif '[stack' in path or '[heap' in path:
                            region_type = MEM_PRIVATE
                        elif path:
                            region_type = MEM_MAPPED

                        regions.append({
                            "base": start,
                            "base_hex": hex(start),
                            "size": size,
                            "size_hex": hex(size),
                            "protect": protect,
                            "protect_name": self._get_protection_name(protect),
                            "permissions": perms,
                            "path": path,
                            "state": MEM_COMMIT,
                            "state_name": "COMMIT",
                            "type": region_type,
                            "type_name": TYPE_NAMES.get(region_type, f"UNKNOWN({region_type})"),
                        })
                        total_size += size
            except (IOError, OSError) as e:
                return {"success": False, "message": f"读取 /proc/pid/maps 失败: {e}"}

        return {
            "success": True,
            "region_count": len(regions),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "regions": regions[:200],  # 限制返回数量
            "truncated": len(regions) > 200,
        }

    def _get_protection_name(self, protect: int) -> str:
        """获取保护属性名称"""
        names = []
        for flag, name in PROTECTION_NAMES.items():
            if protect & flag:
                names.append(name)
        if not names:
            # 尝试组合值精确匹配
            base = protect & 0xFF
            extra = protect & ~0xFF
            result = PROTECTION_NAMES.get(base, f"UNKNOWN(0x{protect:X})")
            if extra & PAGE_GUARD:
                result += "+GUARD"
            if extra & PAGE_NOCACHE:
                result += "+NOCACHE"
            if extra & PAGE_WRITECOMBINE:
                result += "+WRITECOMBINE"
            return result
        return "+".join(names)

    def find_writable_regions(self) -> dict:
        """
        找到所有可写内存区域

        返回:
            {success, count, regions, total_size_mb, ...}
        """
        result = self.enumerate_regions()
        if not result.get("success"):
            return result

        writable = []
        total_size = 0
        for r in result.get("regions", []):
            protect = r.get("protect", 0)
            if protect & PAGE_READWRITE:
                writable.append(r)
                total_size += r["size"]

        return {
            "success": True,
            "count": len(writable),
            "regions": writable[:100],
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "truncated": len(writable) > 100,
        }

    def find_executable_regions(self) -> dict:
        """
        找到所有可执行内存区域

        返回:
            {success, count, regions, total_size_mb, ...}
        """
        result = self.enumerate_regions()
        if not result.get("success"):
            return result

        executable = []
        total_size = 0
        for r in result.get("regions", []):
            protect = r.get("protect", 0)
            if protect & (PAGE_EXECUTE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY):
                executable.append(r)
                total_size += r["size"]

        return {
            "success": True,
            "count": len(executable),
            "regions": executable[:100],
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "truncated": len(executable) > 100,
        }

    def find_code_cave(self, min_size: int = 256) -> dict:
        """
        在进程内存中搜索 Code Cave

        搜索连续 0x00 或 0xCC 区域，适用于注入自定义代码。

        参数:
            min_size: 最小需要的空间（字节）

        返回:
            {success, cave_count, caves, total_available, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        # 在可执行区域中搜索
        exec_result = self.find_executable_regions()
        if not exec_result.get("success"):
            return exec_result

        caves = []
        chunk_size = 64 * 1024

        for region in exec_result.get("regions", []):
            base = region["base"]
            size = region["size"]
            if size <= 0 or size > 200 * 1024 * 1024:
                continue

            offset = 0
            while offset < size:
                read_size = min(chunk_size, size - offset)
                data = self._native_read_memory(base + offset, read_size)
                if data is None:
                    offset += self._system_info.get("page_size", 4096)
                    continue

                # 搜索连续零字节 (0x00)
                i = 0
                while i < len(data):
                    if data[i] == 0x00:
                        cave_start = i
                        while i < len(data) and data[i] == 0x00:
                            i += 1
                        cave_size = i - cave_start
                        if cave_size >= min_size:
                            addr = base + offset + cave_start
                            caves.append({
                                "address": addr,
                                "address_hex": hex(addr),
                                "size": cave_size,
                                "fill_byte": "0x00",
                                "fill_type": "ZERO",
                                "region_base": base,
                            })
                    elif data[i] == 0xCC:
                        cave_start = i
                        while i < len(data) and data[i] == 0xCC:
                            i += 1
                        cave_size = i - cave_start
                        if cave_size >= min_size:
                            addr = base + offset + cave_start
                            caves.append({
                                "address": addr,
                                "address_hex": hex(addr),
                                "size": cave_size,
                                "fill_byte": "0xCC",
                                "fill_type": "INT3",
                                "region_base": base,
                            })
                    else:
                        i += 1

                offset += read_size

        # 排序：大的优先
        caves.sort(key=lambda c: -c["size"])
        total = sum(c["size"] for c in caves)

        return {
            "success": True,
            "cave_count": len(caves),
            "total_available": total,
            "total_available_kb": round(total / 1024, 1),
            "caves": caves[:30],
            "truncated": len(caves) > 30,
            "largest": caves[0] if caves else None,
            "message": f"找到 {len(caves)} 个 Code Cave，总可用 {total / 1024:.1f} KB",
        }

    # ============================================================
    # 代码注入
    # ============================================================

    def inject_code(self, address: int, machine_code: bytes) -> dict:
        """
        向目标进程注入机器码

        使用 VirtualAllocEx 分配内存 -> 写入代码 -> 修改页保护为可执行

        参数:
            address: 注入目标地址（0 表示自动分配）
            machine_code: 机器码字节

        返回:
            {success, allocated_address, code_size, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        if not machine_code:
            return {"success": False, "message": "机器码不能为空"}

        code_size = len(machine_code)

        if IS_WINDOWS and _KERNEL32 is not None:
            # Windows: 使用 VirtualAllocEx
            if address == 0:
                allocated = self._native_virtual_alloc(code_size + 16, PAGE_EXECUTE_READWRITE)
                if allocated is None:
                    return {"success": False, "message": "VirtualAllocEx 失败"}
                address = allocated
            else:
                # 确保目标地址可写可执行
                old_protect = self._native_virtual_protect(address, code_size, PAGE_EXECUTE_READWRITE)
                if old_protect is None:
                    return {"success": False, "message": f"无法修改内存保护 @ 0x{address:X}"}

            # 写入代码
            written = self._native_write_memory(address, machine_code)
            if not written:
                return {"success": False, "message": f"写入机器码失败 @ 0x{address:X}"}

            return {
                "success": True,
                "allocated_address": address,
                "allocated_address_hex": hex(address),
                "code_size": code_size,
                "code_hex": machine_code.hex()[:64] + ("..." if len(machine_code) > 32 else ""),
                "allocation_method": "VirtualAllocEx" if address == 0 else "in-place",
                "message": f"已注入 {code_size} 字节机器码到 0x{address:X}",
            }
        else:
            # Linux/Wine: 不支持代码注入
            return {
                "success": False,
                "message": "代码注入仅在 Windows 下支持",
            }

    def inject_dll(self, dll_path: str) -> dict:
        """
        注入 DLL 到目标进程

        使用 LoadLibrary 远程线程注入技术。

        参数:
            dll_path: DLL 文件的完整路径

        返回:
            {success, dll_path, thread_id, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        if not IS_WINDOWS or _KERNEL32 is None:
            return {"success": False, "message": "DLL 注入仅在 Windows 下支持"}

        if not os.path.exists(dll_path):
            return {"success": False, "message": f"DLL 文件不存在: {dll_path}"}

        try:
            # 编码 DLL 路径
            dll_path_bytes = dll_path.encode('utf-8') + b'\x00'

            # 在目标进程中分配内存存放 DLL 路径
            path_addr = self._native_virtual_alloc(len(dll_path_bytes), PAGE_READWRITE)
            if path_addr is None:
                return {"success": False, "message": "VirtualAllocEx 失败"}

            # 写入 DLL 路径
            written = self._native_write_memory(path_addr, dll_path_bytes)
            if not written:
                self._native_virtual_free(path_addr)
                return {"success": False, "message": "写入 DLL 路径失败"}

            # 获取 kernel32.dll 中 LoadLibraryA 的地址
            kernel32 = _KERNEL32.GetModuleHandleW("kernel32.dll")
            if not kernel32:
                self._native_virtual_free(path_addr)
                return {"success": False, "message": "无法获取 kernel32.dll 句柄"}

            load_library_addr = _KERNEL32.GetProcAddress(kernel32, b"LoadLibraryA")
            if not load_library_addr:
                self._native_virtual_free(path_addr)
                return {"success": False, "message": "无法获取 LoadLibraryA 地址"}

            load_library_addr_val = ctypes.cast(load_library_addr, ctypes.c_void_p).value or load_library_addr

            # 创建远程线程执行 LoadLibraryA
            thread_id = self._native_create_remote_thread(load_library_addr_val, path_addr)
            if thread_id is None:
                self._native_virtual_free(path_addr)
                return {"success": False, "message": "CreateRemoteThread 失败"}

            return {
                "success": True,
                "dll_path": dll_path,
                "path_address": path_addr,
                "path_address_hex": hex(path_addr),
                "load_library_address": load_library_addr_val,
                "load_library_address_hex": hex(load_library_addr_val),
                "thread_id": thread_id,
                "message": f"DLL 注入成功，线程 ID={thread_id}",
            }
        except Exception as e:
            logger.error(f"inject_dll 异常: {e}")
            return {"success": False, "message": f"注入异常: {str(e)}"}

    def create_remote_thread(self, address: int, arg: int = 0) -> dict:
        """
        在目标进程中创建远程线程

        参数:
            address: 线程入口地址
            arg: 传递给线程的参数

        返回:
            {success, thread_id, entry_address, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        if not IS_WINDOWS or _KERNEL32 is None:
            return {"success": False, "message": "远程线程创建仅在 Windows 下支持"}

        thread_id = self._native_create_remote_thread(address, arg)
        if thread_id is None:
            return {"success": False, "message": f"CreateRemoteThread 失败，错误码: {_get_last_error()}"}

        return {
            "success": True,
            "thread_id": thread_id,
            "entry_address": address,
            "entry_address_hex": hex(address),
            "argument": arg,
            "message": f"远程线程已创建，ID={thread_id}",
        }

    # ============================================================
    # 内存 Hook
    # ============================================================

    def install_hook(self, address: int, hook_code: bytes, hook_type: str = "detour") -> dict:
        """
        安装内存 Hook

        detour: 修改函数开头跳转到 hook_code（5字节 JMP）
        iat: 修改 IAT 条目

        参数:
            address: Hook 目标地址
            hook_code: Hook 代码（detour 中是跳转目标地址，iat 中是新的函数指针）
            hook_type: "detour" 或 "iat"

        返回:
            {success, address, hook_type, original_bytes, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        if address in self._hooks:
            return {"success": False, "message": f"该地址已安装 Hook @ 0x{address:X}"}

        if hook_type == "detour":
            # Detour Hook: 在目标地址写入 JMP 到 hook_code
            if len(hook_code) < 5:
                return {"success": False, "message": "Detour hook 需要至少 5 字节的 JMP 代码"}

            # 备份原始 5 字节
            original = self._native_read_memory(address, 5)
            if original is None or len(original) < 5:
                return {"success": False, "message": f"无法读取原始字节 @ 0x{address:X}"}

            # 修改内存保护为可写可执行
            old_protect = self._native_virtual_protect(address, 5, PAGE_EXECUTE_READWRITE)

            # 写入 JMP 跳转
            written = self._native_write_memory(address, hook_code[:5])
            if not written:
                return {"success": False, "message": f"写入 Hook 失败 @ 0x{address:X}"}

            # 恢复原始保护
            if old_protect is not None:
                self._native_virtual_protect(address, 5, old_protect)

            self._hooks[address] = {
                "address": address,
                "original_bytes": original,
                "hook_code": hook_code,
                "hook_type": hook_type,
                "old_protect": old_protect,
                "installed_at": time.time(),
            }

            return {
                "success": True,
                "address": address,
                "address_hex": hex(address),
                "hook_type": hook_type,
                "original_bytes_hex": original.hex(),
                "hook_code_hex": hook_code[:5].hex(),
                "message": f"Detour Hook 已安装 @ 0x{address:X}",
            }

        elif hook_type == "iat":
            # IAT Hook: 修改导入地址表中的函数指针
            # 读取原始指针值
            original = self._native_read_memory(address, 4)
            if original is None or len(original) < 4:
                return {"success": False, "message": f"无法读取 IAT 条目 @ 0x{address:X}"}

            original_ptr = struct.unpack("<I", original[:4])[0]

            old_protect = self._native_virtual_protect(address, 4, PAGE_READWRITE)

            # 写入新的函数指针
            new_ptr_bytes = struct.pack("<I", hook_code if isinstance(hook_code, int) else
                                        struct.unpack("<I", hook_code[:4])[0])
            written = self._native_write_memory(address, new_ptr_bytes)
            if not written:
                return {"success": False, "message": f"写入 IAT Hook 失败 @ 0x{address:X}"}

            if old_protect is not None:
                self._native_virtual_protect(address, 4, old_protect)

            self._hooks[address] = {
                "address": address,
                "original_bytes": original,
                "original_pointer": original_ptr,
                "hook_code": hook_code,
                "hook_type": hook_type,
                "old_protect": old_protect,
                "installed_at": time.time(),
            }

            return {
                "success": True,
                "address": address,
                "address_hex": hex(address),
                "hook_type": hook_type,
                "original_pointer": original_ptr,
                "original_pointer_hex": hex(original_ptr),
                "message": f"IAT Hook 已安装 @ 0x{address:X}",
            }

        else:
            return {"success": False, "message": f"不支持的 Hook 类型: {hook_type}，支持: detour, iat"}

    def remove_hook(self, address: int) -> dict:
        """
        移除 Hook，恢复原始字节

        参数:
            address: Hook 地址

        返回:
            {success, address, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        if address not in self._hooks:
            return {"success": False, "message": f"该地址未安装 Hook @ 0x{address:X}"}

        hook_info = self._hooks[address]
        original = hook_info["original_bytes"]
        hook_type = hook_info["hook_type"]

        # 修改内存保护
        size = len(original)
        old_protect = self._native_virtual_protect(address, size, PAGE_EXECUTE_READWRITE)

        # 恢复原始字节
        written = self._native_write_memory(address, original)
        if not written:
            return {"success": False, "message": f"恢复原始字节失败 @ 0x{address:X}"}

        # 恢复原始保护
        if old_protect is not None:
            self._native_virtual_protect(address, size, old_protect)

        del self._hooks[address]

        return {
            "success": True,
            "address": address,
            "address_hex": hex(address),
            "hook_type": hook_type,
            "restored_bytes_hex": original.hex(),
            "message": f"Hook 已移除 @ 0x{address:X}",
        }

    def list_hooks(self) -> dict:
        """
        列出所有已安装的 Hook

        返回:
            {success, count, hooks, ...}
        """
        hooks = []
        for addr, info in self._hooks.items():
            hooks.append({
                "address": addr,
                "address_hex": hex(addr),
                "hook_type": info["hook_type"],
                "original_bytes_hex": info["original_bytes"].hex() if info["original_bytes"] else "",
                "hook_code_hex": info["hook_code"].hex()[:32] if isinstance(info["hook_code"], bytes) else str(info["hook_code"]),
                "installed_at": info["installed_at"],
            })

        return {
            "success": True,
            "count": len(hooks),
            "hooks": hooks,
        }

    # ============================================================
    # 内存快照与对比
    # ============================================================

    def take_snapshot(self, name: str = None) -> dict:
        """
        创建进程内存快照

        保存当前所有可读内存区域的状态。

        参数:
            name: 快照名称，默认自动生成时间戳名称

        返回:
            {success, name, address_count, snapshot_size_mb, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        if name is None:
            name = f"snapshot_{int(time.time())}"

        regions = self._get_readable_regions()
        if not regions:
            return {"success": False, "message": "无法枚举内存区域"}

        snapshot_data = {}
        total_bytes = 0
        chunk_size = 64 * 1024

        for region in regions:
            base = region["base"]
            size = region["size"]
            if size <= 0 or size > 100 * 1024 * 1024:  # 限制单区域最大 100MB
                continue

            region_data = {}
            offset = 0
            while offset < size:
                read_size = min(chunk_size, size - offset)
                addr = base + offset
                data = self._native_read_memory(addr, read_size)
                if data is not None:
                    region_data[addr] = data
                    total_bytes += len(data)
                offset += read_size

            if region_data:
                snapshot_data[base] = {
                    "base": base,
                    "size": size,
                    "data": region_data,
                }

        self._snapshots[name] = {
            "name": name,
            "data": snapshot_data,
            "timestamp": time.time(),
            "region_count": len(snapshot_data),
            "total_bytes": total_bytes,
        }

        return {
            "success": True,
            "name": name,
            "address_count": sum(len(r["data"]) for r in snapshot_data.values()),
            "region_count": len(snapshot_data),
            "snapshot_size_mb": round(total_bytes / (1024 * 1024), 2),
            "message": f"快照 '{name}' 已创建，{total_bytes / (1024*1024):.1f} MB",
        }

    def compare_snapshots(self, snapshot1: str, snapshot2: str) -> dict:
        """
        对比两个快照，找出所有变化的内存区域和具体变化

        参数:
            snapshot1: 第一个快照名称
            snapshot2: 第二个快照名称

        返回:
            {success, changed_regions, total_changes, ...}
        """
        if snapshot1 not in self._snapshots:
            return {"success": False, "message": f"快照不存在: {snapshot1}"}
        if snapshot2 not in self._snapshots:
            return {"success": False, "message": f"快照不存在: {snapshot2}"}

        snap1 = self._snapshots[snapshot1]
        snap2 = self._snapshots[snapshot2]

        changed_regions = []
        total_changes = 0

        # 获取两个快照共有的区域
        all_bases = set(snap1["data"].keys()) | set(snap2["data"].keys())

        for base in all_bases:
            r1 = snap1["data"].get(base)
            r2 = snap2["data"].get(base)

            if r1 is None or r2 is None:
                # 区域仅存在于一个快照中
                changed_regions.append({
                    "base": base,
                    "base_hex": hex(base),
                    "change_type": "added" if r2 else "removed",
                    "changes": [],
                })
                continue

            changes = []
            # 比较两个区域中的数据
            all_addrs = set(r1["data"].keys()) | set(r2["data"].keys())
            for addr in all_addrs:
                d1 = r1["data"].get(addr)
                d2 = r2["data"].get(addr)

                if d1 is None or d2 is None:
                    changes.append({
                        "address": addr,
                        "address_hex": hex(addr),
                        "change_type": "new" if d2 else "removed",
                    })
                    total_changes += 1
                elif d1 != d2:
                    # 找出具体变化的字节
                    diff_bytes = []
                    min_len = min(len(d1), len(d2))
                    for i in range(min_len):
                        if d1[i] != d2[i]:
                            diff_bytes.append({
                                "offset": i,
                                "old": d1[i],
                                "new": d2[i],
                                "old_hex": hex(d1[i]),
                                "new_hex": hex(d2[i]),
                            })
                    changes.append({
                        "address": addr,
                        "address_hex": hex(addr),
                        "change_type": "modified",
                        "diff_count": len(diff_bytes),
                        "diff_bytes": diff_bytes[:20],  # 限制数量
                    })
                    total_changes += len(diff_bytes)

            if changes:
                changed_regions.append({
                    "base": base,
                    "base_hex": hex(base),
                    "change_type": "modified",
                    "changes": changes[:50],  # 限制每区域变化数
                    "total_region_changes": len(changes),
                })

        return {
            "success": True,
            "snapshot1": snapshot1,
            "snapshot2": snapshot2,
            "snapshot1_time": snap1["timestamp"],
            "snapshot2_time": snap2["timestamp"],
            "changed_regions_count": len(changed_regions),
            "total_changes": total_changes,
            "changed_regions": changed_regions[:30],
            "truncated": len(changed_regions) > 30,
            "message": f"对比 '{snapshot1}' vs '{snapshot2}': {total_changes} 处变化",
        }

    def list_snapshots(self) -> dict:
        """
        列出所有快照

        返回:
            {success, count, snapshots, ...}
        """
        snapshots = []
        for name, snap in self._snapshots.items():
            snapshots.append({
                "name": name,
                "timestamp": snap["timestamp"],
                "region_count": snap["region_count"],
                "total_bytes": snap["total_bytes"],
                "total_mb": round(snap["total_bytes"] / (1024 * 1024), 2),
            })

        snapshots.sort(key=lambda s: s["timestamp"], reverse=True)

        return {
            "success": True,
            "count": len(snapshots),
            "snapshots": snapshots,
        }

    # ============================================================
    # 扫描预设
    # ============================================================

    @staticmethod
    def get_presets() -> dict:
        """
        获取内置扫描预设

        包括常见的游戏数值搜索模板（体力、技力、金钱、兵力等）。

        返回:
            {success, count, presets, ...}
        """
        presets = {}
        for key, preset in MemoryScanner.BUILTIN_PRESETS.items():
            presets[key] = dict(preset)

        return {
            "success": True,
            "count": len(presets),
            "presets": presets,
            "message": f"共 {len(presets)} 个扫描预设",
        }

    def run_preset(self, preset_name: str) -> dict:
        """
        执行预设扫描

        参数:
            preset_name: 预设名称（如 "money", "hp", "mp", "level" 等）

        返回:
            {success, preset, scan_result, ...}
        """
        if not self.is_attached():
            return {"success": False, "message": "未附加到进程"}

        if preset_name not in self.BUILTIN_PRESETS:
            return {
                "success": False,
                "message": f"未知预设: {preset_name}",
                "available_presets": list(self.BUILTIN_PRESETS.keys()),
            }

        preset = self.BUILTIN_PRESETS[preset_name]
        value_type = preset["value_type"]
        default_value = preset["default_value"]

        # 开始新一轮扫描
        self.new_scan()

        # 使用默认值进行精确搜索
        scan_result = self.scan_exact_value(default_value, value_type)

        return {
            "success": scan_result.get("success", False),
            "preset_name": preset_name,
            "preset": dict(preset),
            "scan_result": scan_result,
            "message": f"预设 '{preset['label']}' 扫描完成，找到 {scan_result.get('count', 0)} 个匹配",
        }

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def get_info() -> dict:
        """
        静态方法，返回模块信息

        返回:
            {name, version, description, platform, capabilities, ...}
        """
        return {
            "success": True,
            "name": "MemoryScanner",
            "version": "1.0.0",
            "description": "游戏进程内存扫描与代码注入引擎",
            "platform": platform.system(),
            "is_wine": IS_WINE,
            "capabilities": {
                "process_management": ["attach", "detach", "is_attached", "get_process_info"],
                "memory_rw": ["read_memory", "write_memory", "read_pointer", "write_pointer"],
                "exact_scan": ["scan_exact_value", "scan_exact_text", "scan_pattern"],
                "fuzzy_scan": ["new_scan", "next_scan", "scan_increased", "scan_decreased",
                              "scan_unchanged", "scan_changed", "scan_range"],
                "region_analysis": ["enumerate_regions", "find_writable_regions",
                                   "find_executable_regions", "find_code_cave"],
                "code_injection": ["inject_code", "inject_dll", "create_remote_thread"],
                "hooks": ["install_hook", "remove_hook", "list_hooks"],
                "snapshots": ["take_snapshot", "compare_snapshots", "list_snapshots"],
                "presets": ["get_presets", "run_preset"],
                "utility": ["get_info"],
            },
            "value_types": list(MemoryScanner.VALUE_TYPE_FORMATS.keys()),
            "preset_count": len(MemoryScanner.BUILTIN_PRESETS),
            "preset_names": list(MemoryScanner.BUILTIN_PRESETS.keys()),
            "usage_tip": (
                "基本使用流程: attach() -> new_scan() -> scan_exact_value(value, type) "
                "-> 在游戏中改变数值 -> next_scan('increased') -> 重复直到找到目标地址 "
                "-> write_memory(address, bytes)"
            ),
        }