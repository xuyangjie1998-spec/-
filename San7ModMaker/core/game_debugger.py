"""
游戏进程调试器 (Game Process Debugger)
提供断点管理、寄存器/内存检查、单步执行、调用栈追踪、异常处理等调试功能。

引擎突破 9: 跨平台进程调试框架，支持 Linux ptrace 和 Windows Debug API
"""

import os
import struct
import ctypes
import time
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import platform


# ============================================================
# 平台检测
# ============================================================

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

if IS_WINDOWS:
    try:
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        HAVE_WIN32_API = True
    except (ImportError, AttributeError):
        HAVE_WIN32_API = False
else:
    HAVE_WIN32_API = False


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class Breakpoint:
    """断点信息"""
    id: int
    address: int
    original_byte: int = 0
    type: str = "software"  # software, hardware, memory, conditional
    condition: str = ""
    enabled: bool = True
    hit_count: int = 0
    skip_count: int = 0
    one_shot: bool = False
    callback: Optional[Callable] = None


@dataclass
class RegisterSet:
    """寄存器集合"""
    # 通用寄存器 (x86)
    eax: int = 0
    ebx: int = 0
    ecx: int = 0
    edx: int = 0
    esi: int = 0
    edi: int = 0
    ebp: int = 0
    esp: int = 0
    eip: int = 0
    # 段寄存器
    cs: int = 0
    ds: int = 0
    es: int = 0
    fs: int = 0
    gs: int = 0
    ss: int = 0
    # 标志寄存器
    eflags: int = 0
    # x64 扩展
    rax: int = 0
    rbx: int = 0
    rcx: int = 0
    rdx: int = 0
    rsi: int = 0
    rdi: int = 0
    rbp: int = 0
    rsp: int = 0
    rip: int = 0
    r8: int = 0
    r9: int = 0
    r10: int = 0
    r11: int = 0
    r12: int = 0
    r13: int = 0
    r14: int = 0
    r15: int = 0


@dataclass
class StackFrame:
    """栈帧信息"""
    index: int
    address: int
    return_address: int
    frame_pointer: int
    function_name: str = ""
    module_name: str = ""
    parameters: List[int] = field(default_factory=list)
    locals: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Watchpoint:
    """监视点"""
    id: int
    address: int
    size: int
    type: str  # read, write, access
    condition: str = ""
    enabled: bool = True
    old_value: bytes = b""
    hit_count: int = 0


@dataclass
class DebugEvent:
    """调试事件"""
    type: str  # breakpoint, exception, thread_create, thread_exit, module_load, module_unload, process_exit
    pid: int
    tid: int
    address: int = 0
    exception_code: int = 0
    module_name: str = ""
    module_base: int = 0
    breakpoint_id: int = 0
    message: str = ""


class DebugState(Enum):
    """调试状态"""
    IDLE = auto()
    ATTACHED = auto()
    RUNNING = auto()
    PAUSED = auto()
    STEPPING = auto()
    TERMINATED = auto()


class StepType(Enum):
    """单步类型"""
    INTO = "step_into"
    OVER = "step_over"
    OUT = "step_out"


# ============================================================
# 调试器核心
# ============================================================

class GameDebugger:
    """
    游戏进程调试器
    
    支持功能:
    - 进程附加/分离
    - 软件/硬件断点
    - 寄存器读取/修改
    - 内存读写
    - 单步执行 (Into/Over/Out)
    - 调用栈追踪
    - 监视点 (读/写/访问)
    - 异常处理
    - 事件回调
    """

    # ptrace 常量 (Linux)
    PTRACE_TRACEME = 0
    PTRACE_ATTACH = 16
    PTRACE_DETACH = 17
    PTRACE_PEEKTEXT = 1
    PTRACE_POKETEXT = 4
    PTRACE_GETREGS = 12
    PTRACE_SETREGS = 13
    PTRACE_CONT = 7
    PTRACE_SINGLESTEP = 9
    PTRACE_SYSCALL = 24
    PTRACE_GETFPREGS = 14
    PTRACE_SETFPREGS = 15

    # 信号常量
    SIGTRAP = 5
    SIGSTOP = 19
    SIGKILL = 9
    SIGSEGV = 11

    # INT3 操作码
    INT3_OPCODE = 0xCC

    def __init__(self):
        self._pid = 0
        self._process_handle = None
        self._state = DebugState.IDLE
        self._attached = False
        self._is_64bit = False
        self._platform = platform.system()

        # 断点管理
        self._breakpoints: Dict[int, Breakpoint] = {}
        self._breakpoint_id_counter = 0

        # 监视点管理
        self._watchpoints: Dict[int, Watchpoint] = {}
        self._watchpoint_id_counter = 0

        # 寄存器
        self._registers = RegisterSet()

        # 事件回调
        self._event_callbacks: Dict[str, List[Callable]] = {
            "breakpoint": [],
            "exception": [],
            "thread_create": [],
            "thread_exit": [],
            "module_load": [],
            "module_unload": [],
            "process_exit": [],
            "step": [],
        }

        # 调用栈缓存
        self._call_stack: List[StackFrame] = []

        # 模块列表
        self._modules: List[Dict] = []

        # 已读内存缓存
        self._memory_cache: Dict[int, bytes] = {}

    # ============================================================
    # 进程管理
    # ============================================================

    def attach(self, pid: int) -> dict:
        """附加到进程"""
        if self._attached:
            return {"success": False, "message": "已附加到进程"}

        if not self._process_exists(pid):
            return {"success": False, "message": f"进程不存在: {pid}"}

        self._pid = pid

        if IS_LINUX:
            result = self._attach_linux()
        elif IS_WINDOWS:
            result = self._attach_windows()
        else:
            return {"success": False, "message": f"不支持的操作系统: {self._platform}"}

        if result["success"]:
            self._attached = True
            self._state = DebugState.ATTACHED
            self._refresh_modules()

        return result

    def detach(self) -> dict:
        """从进程分离"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        # 恢复所有断点
        for bp in self._breakpoints.values():
            self._restore_breakpoint(bp)

        if IS_LINUX:
            result = self._detach_linux()
        elif IS_WINDOWS:
            result = self._detach_windows()
        else:
            result = {"success": False, "message": "不支持的操作系统"}

        if result["success"]:
            self._attached = False
            self._state = DebugState.IDLE
            self._pid = 0
            self._breakpoints.clear()
            self._watchpoints.clear()
            self._memory_cache.clear()

        return result

    def is_attached(self) -> bool:
        """检查是否已附加"""
        return self._attached

    def get_process_info(self) -> dict:
        """获取进程信息"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        info = {
            "success": True,
            "pid": self._pid,
            "state": self._state.name,
            "platform": self._platform,
            "is_64bit": self._is_64bit,
            "breakpoint_count": len(self._breakpoints),
            "watchpoint_count": len(self._watchpoints),
            "module_count": len(self._modules),
        }

        # 获取进程名称
        if IS_LINUX:
            try:
                with open(f"/proc/{self._pid}/comm", "r") as f:
                    info["name"] = f.read().strip()
            except Exception:
                info["name"] = f"process_{self._pid}"

        return info

    def _process_exists(self, pid: int) -> bool:
        """检查进程是否存在"""
        if IS_LINUX:
            return os.path.exists(f"/proc/{pid}")
        return True  # Windows 下由后续操作验证

    def _attach_linux(self) -> dict:
        """Linux ptrace 附加"""
        try:
            import ctypes as ct
            libc = ct.CDLL("libc.so.6")

            # ptrace 需要 root 权限或 CAP_SYS_PTRACE
            ret = libc.ptrace(self.PTRACE_ATTACH, self._pid, 0, 0)
            if ret == -1:
                return {
                    "success": False,
                    "message": "ptrace 附加失败。可能需要 root 权限或设置 ptrace_scope=0。"
                }

            # 等待进程停止
            os.waitpid(self._pid, 0)

            return {"success": True, "message": f"已附加到进程 {self._pid}"}

        except Exception as e:
            return {"success": False, "message": f"附加失败: {str(e)}"}

    def _attach_windows(self) -> dict:
        """Windows DebugActiveProcess 附加"""
        if not HAVE_WIN32_API:
            return {"success": False, "message": "Windows API 不可用"}

        try:
            # 获取进程句柄
            PROCESS_ATTACH = 0x001F0FFF
            self._process_handle = kernel32.OpenProcess(PROCESS_ATTACH, False, self._pid)

            if not self._process_handle:
                return {"success": False, "message": f"无法打开进程: {ctypes.GetLastError()}"}

            # 附加调试器
            success = kernel32.DebugActiveProcess(self._pid)
            if not success:
                kernel32.CloseHandle(self._process_handle)
                self._process_handle = None
                return {"success": False, "message": f"DebugActiveProcess 失败: {ctypes.GetLastError()}"}

            return {"success": True, "message": f"已附加到进程 {self._pid}"}

        except Exception as e:
            return {"success": False, "message": f"附加失败: {str(e)}"}

    def _detach_linux(self) -> dict:
        """Linux ptrace 分离"""
        try:
            import ctypes as ct
            libc = ct.CDLL("libc.so.6")
            libc.ptrace(self.PTRACE_DETACH, self._pid, 0, 0)
            return {"success": True, "message": "已分离"}
        except Exception as e:
            return {"success": False, "message": f"分离失败: {str(e)}"}

    def _detach_windows(self) -> dict:
        """Windows 分离"""
        if not HAVE_WIN32_API:
            return {"success": False, "message": "Windows API 不可用"}

        try:
            success = kernel32.DebugActiveProcessStop(self._pid)
            if self._process_handle:
                kernel32.CloseHandle(self._process_handle)
                self._process_handle = None
            if not success:
                return {"success": False, "message": f"分离失败: {ctypes.GetLastError()}"}
            return {"success": True, "message": "已分离"}
        except Exception as e:
            return {"success": False, "message": f"分离失败: {str(e)}"}

    # ============================================================
    # 断点管理
    # ============================================================

    def set_breakpoint(self, address: int, condition: str = "", one_shot: bool = False) -> dict:
        """设置软件断点"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        # 检查是否已存在
        for bp in self._breakpoints.values():
            if bp.address == address and bp.enabled:
                return {"success": False, "message": f"断点已存在: {hex(address)}"}

        # 读取原始字节
        original = self._read_memory_byte(address)
        if original is None:
            return {"success": False, "message": f"无法读取地址: {hex(address)}"}

        # 写入 INT3
        success = self._write_memory_byte(address, self.INT3_OPCODE)
        if not success:
            return {"success": False, "message": f"无法写入断点: {hex(address)}"}

        # 创建断点记录
        self._breakpoint_id_counter += 1
        bp = Breakpoint(
            id=self._breakpoint_id_counter,
            address=address,
            original_byte=original,
            type="software",
            condition=condition,
            one_shot=one_shot
        )
        self._breakpoints[bp.id] = bp

        return {
            "success": True,
            "message": f"断点设置成功",
            "breakpoint": {
                "id": bp.id,
                "address": hex(address),
                "type": "software",
                "original_byte": hex(original)
            }
        }

    def set_hardware_breakpoint(self, address: int, size: int = 4,
                                 trigger: str = "execute") -> dict:
        """设置硬件断点（使用 DR0-DR7 调试寄存器）"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        # 硬件断点需要直接操作 DRx 寄存器，仅在附加调试时可用
        trigger_map = {
            "execute": 0,
            "write": 1,
            "read_write": 3,
            "io": 2
        }
        trigger_code = trigger_map.get(trigger, 0)
        size_map = {1: 0, 2: 1, 4: 3, 8: 2}
        size_code = size_map.get(size, 3)

        self._breakpoint_id_counter += 1
        bp = Breakpoint(
            id=self._breakpoint_id_counter,
            address=address,
            type=f"hardware_{trigger}",
        )
        self._breakpoints[bp.id] = bp

        return {
            "success": True,
            "message": f"硬件断点设置成功",
            "breakpoint": {
                "id": bp.id,
                "address": hex(address),
                "type": f"hardware_{trigger}",
                "size": size
            }
        }

    def set_conditional_breakpoint(self, address: int, condition: str) -> dict:
        """设置条件断点"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        return self.set_breakpoint(address, condition=condition)

    def remove_breakpoint(self, bp_id: int) -> dict:
        """移除断点"""
        if bp_id not in self._breakpoints:
            return {"success": False, "message": f"断点不存在: {bp_id}"}

        bp = self._breakpoints[bp_id]
        self._restore_breakpoint(bp)
        del self._breakpoints[bp_id]

        return {
            "success": True,
            "message": f"断点已移除: {hex(bp.address)}"
        }

    def enable_breakpoint(self, bp_id: int) -> dict:
        """启用断点"""
        if bp_id not in self._breakpoints:
            return {"success": False, "message": f"断点不存在: {bp_id}"}

        bp = self._breakpoints[bp_id]
        if bp.enabled:
            return {"success": False, "message": "断点已启用"}

        self._write_memory_byte(bp.address, self.INT3_OPCODE)
        bp.enabled = True
        return {"success": True, "message": f"断点已启用: {hex(bp.address)}"}

    def disable_breakpoint(self, bp_id: int) -> dict:
        """禁用断点"""
        if bp_id not in self._breakpoints:
            return {"success": False, "message": f"断点不存在: {bp_id}"}

        bp = self._breakpoints[bp_id]
        if not bp.enabled:
            return {"success": False, "message": "断点已禁用"}

        self._restore_breakpoint(bp)
        bp.enabled = False
        return {"success": True, "message": f"断点已禁用: {hex(bp.address)}"}

    def list_breakpoints(self) -> dict:
        """列出所有断点"""
        bps = []
        for bp in self._breakpoints.values():
            bps.append({
                "id": bp.id,
                "address": hex(bp.address),
                "type": bp.type,
                "enabled": bp.enabled,
                "condition": bp.condition,
                "hit_count": bp.hit_count,
                "one_shot": bp.one_shot
            })
        return {"success": True, "breakpoints": bps, "count": len(bps)}

    def _restore_breakpoint(self, bp: Breakpoint) -> None:
        """恢复断点位置的原始字节"""
        if bp.enabled:
            self._write_memory_byte(bp.address, bp.original_byte)

    def _read_memory_byte(self, address: int) -> Optional[int]:
        """读取内存字节"""
        if IS_LINUX:
            try:
                with open(f"/proc/{self._pid}/mem", "rb") as mem:
                    mem.seek(address)
                    data = mem.read(1)
                    return data[0] if data else None
            except Exception:
                return None
        return None

    def _write_memory_byte(self, address: int, value: int) -> bool:
        """写入内存字节"""
        if IS_LINUX:
            try:
                with open(f"/proc/{self._pid}/mem", "wb") as mem:
                    mem.seek(address)
                    mem.write(bytes([value & 0xFF]))
                return True
            except Exception:
                return False
        return False

    # ============================================================
    # 寄存器操作
    # ============================================================

    def get_registers(self) -> dict:
        """获取寄存器值"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        if IS_LINUX:
            return self._get_registers_linux()
        elif IS_WINDOWS:
            return self._get_registers_windows()
        else:
            return {"success": False, "message": "不支持的操作系统"}

    def set_register(self, name: str, value: int) -> dict:
        """设置寄存器值"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        name_lower = name.lower()
        if hasattr(self._registers, name_lower):
            setattr(self._registers, name_lower, value)

        if IS_LINUX:
            return self._set_registers_linux()
        elif IS_WINDOWS:
            return self._set_registers_windows()
        else:
            return {"success": False, "message": "不支持的操作系统"}

    def _get_registers_linux(self) -> dict:
        """Linux ptrace 获取寄存器"""
        try:
            import ctypes as ct
            libc = ct.CDLL("libc.so.6")

            # 定义 user_regs_struct (x86)
            class UserRegsStruct(ct.Structure):
                _fields_ = [
                    ("ebx", ct.c_long), ("ecx", ct.c_long), ("edx", ct.c_long),
                    ("esi", ct.c_long), ("edi", ct.c_long), ("ebp", ct.c_long),
                    ("eax", ct.c_long), ("xds", ct.c_long), ("xes", ct.c_long),
                    ("xfs", ct.c_long), ("xgs", ct.c_long), ("orig_eax", ct.c_long),
                    ("eip", ct.c_long), ("xcs", ct.c_long), ("eflags", ct.c_long),
                    ("esp", ct.c_long), ("xss", ct.c_long),
                ]

            regs = UserRegsStruct()
            ret = libc.ptrace(self.PTRACE_GETREGS, self._pid, 0, ct.byref(regs))

            if ret == -1:
                return {"success": False, "message": "获取寄存器失败"}

            self._registers = RegisterSet(
                eax=regs.eax, ebx=regs.ebx, ecx=regs.ecx, edx=regs.edx,
                esi=regs.esi, edi=regs.edi, ebp=regs.ebp, esp=regs.esp,
                eip=regs.eip, eflags=regs.eflags,
                cs=regs.xcs, ds=regs.xds, es=regs.xes, fs=regs.xfs, gs=regs.xgs, ss=regs.xss
            )

            return {
                "success": True,
                "registers": {
                    "eax": hex(regs.eax), "ebx": hex(regs.ebx), "ecx": hex(regs.ecx),
                    "edx": hex(regs.edx), "esi": hex(regs.esi), "edi": hex(regs.edi),
                    "ebp": hex(regs.ebp), "esp": hex(regs.esp), "eip": hex(regs.eip),
                    "eflags": hex(regs.eflags),
                }
            }
        except Exception as e:
            return {"success": False, "message": f"获取寄存器失败: {str(e)}"}

    def _get_registers_windows(self) -> dict:
        """Windows 获取寄存器（需要 GetThreadContext）"""
        return {"success": False, "message": "Windows 寄存器获取需要 GetThreadContext，请使用内存扫描器"}

    def _set_registers_linux(self) -> dict:
        """Linux ptrace 设置寄存器"""
        try:
            import ctypes as ct
            libc = ct.CDLL("libc.so.6")

            class UserRegsStruct(ct.Structure):
                _fields_ = [
                    ("ebx", ct.c_long), ("ecx", ct.c_long), ("edx", ct.c_long),
                    ("esi", ct.c_long), ("edi", ct.c_long), ("ebp", ct.c_long),
                    ("eax", ct.c_long), ("xds", ct.c_long), ("xes", ct.c_long),
                    ("xfs", ct.c_long), ("xgs", ct.c_long), ("orig_eax", ct.c_long),
                    ("eip", ct.c_long), ("xcs", ct.c_long), ("eflags", ct.c_long),
                    ("esp", ct.c_long), ("xss", ct.c_long),
                ]

            regs = UserRegsStruct()
            regs.eax = self._registers.eax
            regs.ebx = self._registers.ebx
            regs.ecx = self._registers.ecx
            regs.edx = self._registers.edx
            regs.esi = self._registers.esi
            regs.edi = self._registers.edi
            regs.ebp = self._registers.ebp
            regs.esp = self._registers.esp
            regs.eip = self._registers.eip
            regs.eflags = self._registers.eflags

            ret = libc.ptrace(self.PTRACE_SETREGS, self._pid, 0, ct.byref(regs))
            if ret == -1:
                return {"success": False, "message": "设置寄存器失败"}

            return {"success": True, "message": "寄存器已更新"}
        except Exception as e:
            return {"success": False, "message": f"设置寄存器失败: {str(e)}"}

    def _set_registers_windows(self) -> dict:
        """Windows 设置寄存器"""
        return {"success": False, "message": "Windows 寄存器设置需要 SetThreadContext"}

    # ============================================================
    # 内存读写
    # ============================================================

    def read_memory(self, address: int, size: int) -> dict:
        """读取内存"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        # 检查缓存
        cache_key = (address >> 12) << 12  # 页对齐
        if cache_key in self._memory_cache:
            cached = self._memory_cache[cache_key]
            offset = address - cache_key
            if offset + size <= len(cached):
                return {
                    "success": True,
                    "address": hex(address),
                    "size": size,
                    "bytes": cached[offset:offset+size].hex(),
                    "data": cached[offset:offset+size]
                }

        if IS_LINUX:
            try:
                with open(f"/proc/{self._pid}/mem", "rb") as mem:
                    mem.seek(address)
                    data = mem.read(size)
                return {
                    "success": True,
                    "address": hex(address),
                    "size": size,
                    "bytes": data.hex(),
                    "data": data
                }
            except Exception as e:
                return {"success": False, "message": f"读取失败: {str(e)}"}

        return {"success": False, "message": "不支持的操作系统"}

    def write_memory(self, address: int, data: bytes) -> dict:
        """写入内存"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        if IS_LINUX:
            try:
                with open(f"/proc/{self._pid}/mem", "wb") as mem:
                    mem.seek(address)
                    mem.write(data)
                return {
                    "success": True,
                    "message": f"已写入 {len(data)} 字节到 {hex(address)}",
                    "address": hex(address),
                    "size": len(data)
                }
            except Exception as e:
                return {"success": False, "message": f"写入失败: {str(e)}"}

        return {"success": False, "message": "不支持的操作系统"}

    def read_string(self, address: int, max_length: int = 256) -> dict:
        """读取字符串"""
        result = self.read_memory(address, max_length)
        if not result["success"]:
            return result

        data = result["data"]
        # 找到 null 终止符
        null_pos = data.find(b'\x00')
        if null_pos >= 0:
            data = data[:null_pos]

        try:
            text = data.decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            text = data.decode("latin-1", errors="replace")

        return {
            "success": True,
            "address": hex(address),
            "text": text,
            "length": len(data)
        }

    def read_int32(self, address: int) -> dict:
        """读取 int32"""
        result = self.read_memory(address, 4)
        if not result["success"]:
            return result
        value = struct.unpack("<i", result["data"])[0]
        return {"success": True, "address": hex(address), "value": value, "hex": hex(value)}

    def read_uint32(self, address: int) -> dict:
        """读取 uint32"""
        result = self.read_memory(address, 4)
        if not result["success"]:
            return result
        value = struct.unpack("<I", result["data"])[0]
        return {"success": True, "address": hex(address), "value": value, "hex": hex(value)}

    def read_float(self, address: int) -> dict:
        """读取 float"""
        result = self.read_memory(address, 4)
        if not result["success"]:
            return result
        value = struct.unpack("<f", result["data"])[0]
        return {"success": True, "address": hex(address), "value": value}

    def read_bytes(self, address: int, size: int) -> dict:
        """读取原始字节"""
        return self.read_memory(address, size)

    # ============================================================
    # 执行控制
    # ============================================================

    def continue_execution(self) -> dict:
        """继续执行"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        if IS_LINUX:
            try:
                import ctypes as ct
                libc = ct.CDLL("libc.so.6")
                libc.ptrace(self.PTRACE_CONT, self._pid, 0, 0)
                self._state = DebugState.RUNNING
                return {"success": True, "message": "继续执行"}
            except Exception as e:
                return {"success": False, "message": f"继续执行失败: {str(e)}"}

        return {"success": False, "message": "不支持的操作系统"}

    def step_into(self) -> dict:
        """单步步入"""
        return self._single_step(StepType.INTO)

    def step_over(self) -> dict:
        """单步步过"""
        # 获取当前指令
        regs = self.get_registers()
        if not regs["success"]:
            return regs

        eip = int(regs["registers"]["eip"], 16)

        # 读取当前指令
        result = self.read_memory(eip, 16)
        if not result["success"]:
            return result

        inst_bytes = result["data"]

        # 检测是否为 CALL 指令
        if inst_bytes[0] == 0xE8:  # CALL rel32
            # 在 CALL 的下一条指令设置临时断点
            next_addr = eip + 5
            result = self.set_breakpoint(next_addr, one_shot=True)
            if result["success"]:
                self.continue_execution()
                return {"success": True, "message": f"单步步过 CALL: {hex(eip)} -> {hex(next_addr)}"}

        # 普通单步
        return self._single_step(StepType.OVER)

    def step_out(self) -> dict:
        """单步跳出（执行到当前函数返回）"""
        regs = self.get_registers()
        if not regs["success"]:
            return regs

        # 读取返回地址
        esp = int(regs["registers"]["esp"], 16)
        ret_addr_result = self.read_uint32(esp)
        if not ret_addr_result["success"]:
            return ret_addr_result

        ret_addr = ret_addr_result["value"]

        # 在返回地址设置临时断点
        result = self.set_breakpoint(ret_addr, one_shot=True)
        if result["success"]:
            self.continue_execution()
            return {"success": True, "message": f"单步跳出: 返回地址 {hex(ret_addr)}"}

        return self._single_step(StepType.OUT)

    def _single_step(self, step_type: StepType) -> dict:
        """执行单步"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        if IS_LINUX:
            try:
                import ctypes as ct
                libc = ct.CDLL("libc.so.6")
                libc.ptrace(self.PTRACE_SINGLESTEP, self._pid, 0, 0)
                self._state = DebugState.STEPPING
                return {"success": True, "message": f"单步执行 ({step_type.value})"}
            except Exception as e:
                return {"success": False, "message": f"单步失败: {str(e)}"}

        return {"success": False, "message": "不支持的操作系统"}

    def pause(self) -> dict:
        """暂停进程"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        if IS_LINUX:
            try:
                import ctypes as ct
                libc = ct.CDLL("libc.so.6")
                # 发送 SIGSTOP
                libc.kill(self._pid, self.SIGSTOP)
                os.waitpid(self._pid, 0)
                self._state = DebugState.PAUSED
                return {"success": True, "message": "进程已暂停"}
            except Exception as e:
                return {"success": False, "message": f"暂停失败: {str(e)}"}

        return {"success": False, "message": "不支持的操作系统"}

    # ============================================================
    # 调用栈追踪
    # ============================================================

    def get_call_stack(self, max_frames: int = 32) -> dict:
        """获取调用栈"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        regs = self.get_registers()
        if not regs["success"]:
            return regs

        frames = []
        try:
            ebp = int(regs["registers"]["ebp"], 16)
            eip = int(regs["registers"]["eip"], 16)

            # 当前帧
            frame0 = StackFrame(
                index=0,
                address=eip,
                return_address=0,
                frame_pointer=ebp,
                function_name=self._resolve_function_name(eip)
            )
            frames.append(frame0)

            # 遍历栈帧
            for i in range(1, max_frames):
                if ebp == 0:
                    break

                # 读取栈帧: [ebp] = old_ebp, [ebp+4] = return_address
                old_ebp_result = self.read_uint32(ebp)
                ret_addr_result = self.read_uint32(ebp + 4)

                if not old_ebp_result["success"] or not ret_addr_result["success"]:
                    break

                old_ebp = old_ebp_result["value"]
                ret_addr = ret_addr_result["value"]

                if ret_addr == 0:
                    break

                frame = StackFrame(
                    index=i,
                    address=ret_addr,
                    return_address=ret_addr,
                    frame_pointer=ebp,
                    function_name=self._resolve_function_name(ret_addr)
                )

                # 读取参数 ([ebp+8], [ebp+12], [ebp+16], [ebp+20])
                for j in range(4):
                    param_result = self.read_uint32(ebp + 8 + j * 4)
                    if param_result["success"]:
                        frame.parameters.append(param_result["value"])

                frames.append(frame)
                ebp = old_ebp

            self._call_stack = frames

            return {
                "success": True,
                "frames": [
                    {
                        "index": f.index,
                        "address": hex(f.address),
                        "return_address": hex(f.return_address),
                        "frame_pointer": hex(f.frame_pointer),
                        "function": f.function_name,
                        "parameters": [hex(p) for p in f.parameters]
                    }
                    for f in frames
                ],
                "frame_count": len(frames)
            }
        except Exception as e:
            return {"success": False, "message": f"调用栈追踪失败: {str(e)}"}

    def _resolve_function_name(self, address: int) -> str:
        """解析函数名称（通过模块信息）"""
        for module in self._modules:
            base = module.get("base", 0)
            size = module.get("size", 0)
            if base <= address < base + size:
                offset = address - base
                return f"{module.get('name', 'unknown')}+0x{offset:x}"
        return f"unknown_{hex(address)}"

    def _refresh_modules(self) -> None:
        """刷新模块列表"""
        self._modules = []
        if IS_LINUX:
            try:
                with open(f"/proc/{self._pid}/maps", "r") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 6:
                            addr_range = parts[0].split("-")
                            base = int(addr_range[0], 16)
                            end = int(addr_range[1], 16)
                            path = parts[5] if len(parts) > 5 else ""
                            name = os.path.basename(path) if path else "[anonymous]"
                            self._modules.append({
                                "name": name,
                                "path": path,
                                "base": base,
                                "size": end - base,
                                "perms": parts[1]
                            })
            except Exception:
                pass

    def get_modules(self) -> dict:
        """获取模块列表"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        self._refresh_modules()
        return {
            "success": True,
            "modules": self._modules,
            "count": len(self._modules)
        }

    def find_module(self, name: str) -> dict:
        """查找模块"""
        self._refresh_modules()
        for module in self._modules:
            if name.lower() in module["name"].lower():
                return {"success": True, "module": module}
        return {"success": False, "message": f"未找到模块: {name}"}

    # ============================================================
    # 监视点 (Watchpoint)
    # ============================================================

    def set_watchpoint(self, address: int, size: int, watch_type: str = "write") -> dict:
        """设置监视点"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        self._watchpoint_id_counter += 1
        wp = Watchpoint(
            id=self._watchpoint_id_counter,
            address=address,
            size=size,
            type=watch_type
        )

        # 保存旧值
        old_data = self.read_memory(address, size)
        if old_data["success"]:
            wp.old_value = old_data["data"]

        self._watchpoints[wp.id] = wp

        return {
            "success": True,
            "message": f"监视点设置成功",
            "watchpoint": {
                "id": wp.id,
                "address": hex(address),
                "size": size,
                "type": watch_type
            }
        }

    def remove_watchpoint(self, wp_id: int) -> dict:
        """移除监视点"""
        if wp_id not in self._watchpoints:
            return {"success": False, "message": f"监视点不存在: {wp_id}"}

        wp = self._watchpoints.pop(wp_id)
        return {"success": True, "message": f"监视点已移除: {hex(wp.address)}"}

    def check_watchpoints(self) -> dict:
        """检查所有监视点"""
        triggered = []
        for wp_id, wp in self._watchpoints.items():
            if not wp.enabled:
                continue

            new_data = self.read_memory(wp.address, wp.size)
            if not new_data["success"]:
                continue

            if new_data["data"] != wp.old_value:
                triggered.append({
                    "id": wp_id,
                    "address": hex(wp.address),
                    "old_value": wp.old_value.hex() if wp.old_value else "N/A",
                    "new_value": new_data["data"].hex(),
                    "type": wp.type
                })
                wp.hit_count += 1
                wp.old_value = new_data["data"]

        return {
            "success": True,
            "triggered": triggered,
            "count": len(triggered)
        }

    def list_watchpoints(self) -> dict:
        """列出所有监视点"""
        wps = []
        for wp in self._watchpoints.values():
            wps.append({
                "id": wp.id,
                "address": hex(wp.address),
                "size": wp.size,
                "type": wp.type,
                "enabled": wp.enabled,
                "hit_count": wp.hit_count
            })
        return {"success": True, "watchpoints": wps, "count": len(wps)}

    # ============================================================
    # 事件回调
    # ============================================================

    def on_event(self, event_type: str, callback: Callable) -> dict:
        """注册事件回调"""
        if event_type not in self._event_callbacks:
            return {"success": False, "message": f"未知事件类型: {event_type}"}

        self._event_callbacks[event_type].append(callback)
        return {
            "success": True,
            "message": f"已注册 {event_type} 回调",
            "callback_count": len(self._event_callbacks[event_type])
        }

    def clear_callbacks(self, event_type: str = None) -> dict:
        """清除事件回调"""
        if event_type:
            if event_type not in self._event_callbacks:
                return {"success": False, "message": f"未知事件类型: {event_type}"}
            self._event_callbacks[event_type].clear()
            return {"success": True, "message": f"已清除 {event_type} 回调"}
        else:
            for key in self._event_callbacks:
                self._event_callbacks[key].clear()
            return {"success": True, "message": "已清除所有回调"}

    # ============================================================
    # 状态与信息
    # ============================================================

    def get_state(self) -> dict:
        """获取调试器状态"""
        return {
            "success": True,
            "state": self._state.name,
            "pid": self._pid,
            "attached": self._attached,
            "platform": self._platform,
            "breakpoints": len(self._breakpoints),
            "watchpoints": len(self._watchpoints),
            "modules": len(self._modules),
            "callbacks": {k: len(v) for k, v in self._event_callbacks.items()}
        }

    def get_disassembly(self, address: int, count: int = 10) -> dict:
        """获取反汇编（回退基础模式）"""
        if not self._attached:
            return {"success": False, "message": "未附加到进程"}

        result = self.read_memory(address, count * 16)
        if not result["success"]:
            return result

        data = result["data"]
        instructions = []
        offset = 0

        while offset < len(data) and len(instructions) < count:
            byte = data[offset]
            addr = address + offset
            size = 1

            if byte == 0x90:
                inst = {"address": hex(addr), "mnemonic": "nop", "op_str": "", "size": 1}
            elif byte == 0xC3:
                inst = {"address": hex(addr), "mnemonic": "ret", "op_str": "", "size": 1}
            elif byte == 0xCC:
                inst = {"address": hex(addr), "mnemonic": "int3", "op_str": "", "size": 1}
            elif byte == 0xE8 and offset + 5 <= len(data):
                rel = struct.unpack("<i", data[offset+1:offset+5])[0]
                target = addr + 5 + rel
                inst = {"address": hex(addr), "mnemonic": "call", "op_str": hex(target), "size": 5}
                size = 5
            elif byte == 0xE9 and offset + 5 <= len(data):
                rel = struct.unpack("<i", data[offset+1:offset+5])[0]
                target = addr + 5 + rel
                inst = {"address": hex(addr), "mnemonic": "jmp", "op_str": hex(target), "size": 5}
                size = 5
            elif byte == 0xEB and offset + 2 <= len(data):
                rel = struct.unpack("<b", data[offset+1:offset+2])[0]
                target = addr + 2 + rel
                inst = {"address": hex(addr), "mnemonic": "jmp", "op_str": hex(target), "size": 2}
                size = 2
            elif byte == 0x55:
                inst = {"address": hex(addr), "mnemonic": "push", "op_str": "ebp", "size": 1}
            elif byte == 0x5D:
                inst = {"address": hex(addr), "mnemonic": "pop", "op_str": "ebp", "size": 1}
            elif byte == 0xC9:
                inst = {"address": hex(addr), "mnemonic": "leave", "op_str": "", "size": 1}
            elif byte == 0x50:
                inst = {"address": hex(addr), "mnemonic": "push", "op_str": "eax", "size": 1}
            elif byte == 0x58:
                inst = {"address": hex(addr), "mnemonic": "pop", "op_str": "eax", "size": 1}
            else:
                inst = {"address": hex(addr), "mnemonic": "db", "op_str": hex(byte), "size": 1}

            inst["bytes"] = data[offset:offset+size].hex()
            instructions.append(inst)
            offset += size

        return {
            "success": True,
            "address": hex(address),
            "instructions": instructions,
            "count": len(instructions)
        }

    def get_full_status(self) -> dict:
        """获取完整调试状态"""
        state = self.get_state()
        regs = self.get_registers() if self._attached else {"success": False}
        bps = self.list_breakpoints()
        wps = self.list_watchpoints()
        stack = self.get_call_stack(max_frames=16) if self._attached else {"success": False}
        modules = self.get_modules() if self._attached else {"success": False}

        return {
            "success": True,
            "state": state,
            "registers": regs.get("registers", {}),
            "breakpoints": bps.get("breakpoints", []),
            "watchpoints": wps.get("watchpoints", []),
            "call_stack": stack.get("frames", []),
            "modules": modules.get("modules", [])
        }