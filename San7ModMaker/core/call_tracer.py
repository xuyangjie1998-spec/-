"""
调用追踪与API拦截器 (Call Tracer & API Interceptor)
提供函数调用追踪、API拦截、参数日志、返回值捕获、调用图生成、性能分析等功能。

引擎突破 12: 深度追踪游戏运行时函数调用链，支持 Hook 管理、调用统计、导出分析、
性能剖析、参数序列化、调用图可视化
"""

import json
import os
import time
import threading
from typing import Dict, List, Optional, Tuple, Set, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict, Counter
from functools import wraps
import struct


# ============================================================
# 枚举定义
# ============================================================

class TraceEventType(Enum):
    """追踪事件类型"""
    FUNCTION_CALL = "function_call"       # 函数调用
    FUNCTION_RETURN = "function_return"   # 函数返回
    API_CALL = "api_call"                 # API调用
    API_RETURN = "api_return"             # API返回
    EXCEPTION = "exception"               # 异常
    MEMORY_READ = "memory_read"           # 内存读取
    MEMORY_WRITE = "memory_write"         # 内存写入
    HOOK_TRIGGER = "hook_trigger"         # Hook触发
    CUSTOM = "custom"                     # 自定义事件


class HookType(Enum):
    """Hook类型"""
    PRE_CALL = "pre_call"          # 调用前Hook
    POST_CALL = "post_call"        # 调用后Hook
    REPLACE = "replace"            # 替换Hook
    PRE_POST = "pre_post"          # 前后Hook
    CONDITIONAL = "conditional"    # 条件Hook


class CallConvention(Enum):
    """调用约定"""
    CDECL = "cdecl"
    STDCALL = "stdcall"
    FASTCALL = "fastcall"
    THISCALL = "thiscall"
    X64_MS = "x64_ms"


class ParamType(Enum):
    """参数类型"""
    INT = "int"
    UINT = "uint"
    FLOAT = "float"
    DOUBLE = "double"
    STRING = "string"
    POINTER = "pointer"
    STRUCT = "struct"
    BOOL = "bool"
    BYTES = "bytes"
    HANDLE = "handle"
    UNKNOWN = "unknown"


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class FunctionSignature:
    """函数签名"""
    name: str
    module: str = ""
    address: int = 0
    calling_convention: CallConvention = CallConvention.CDECL
    params: List[Tuple[str, ParamType]] = field(default_factory=list)
    return_type: ParamType = ParamType.UNKNOWN
    description: str = ""
    is_variadic: bool = False


@dataclass
class TraceEvent:
    """追踪事件"""
    event_id: int
    event_type: TraceEventType
    timestamp: float
    function_name: str = ""
    module: str = ""
    address: int = 0
    thread_id: int = 0
    params: List[Any] = field(default_factory=list)
    param_types: List[ParamType] = field(default_factory=list)
    return_value: Any = None
    duration: float = 0.0
    depth: int = 0
    caller: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Hook:
    """Hook定义"""
    hook_id: str
    function_name: str
    hook_type: HookType
    callback: Callable = None
    module: str = ""
    condition: str = ""
    enabled: bool = True
    hit_count: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class CallNode:
    """调用图节点"""
    function_name: str
    module: str = ""
    call_count: int = 0
    total_duration: float = 0.0
    avg_duration: float = 0.0
    min_duration: float = float("inf")
    max_duration: float = 0.0
    children: Dict[str, "CallNode"] = field(default_factory=dict)
    parent: Optional["CallNode"] = None
    params_summary: List[dict] = field(default_factory=list)
    errors: int = 0


@dataclass
class PerformanceProfile:
    """性能分析"""
    function_name: str
    module: str = ""
    call_count: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    p50_time: float = 0.0
    p95_time: float = 0.0
    p99_time: float = 0.0
    times: List[float] = field(default_factory=list)


# ============================================================
# 函数签名注册表
# ============================================================

class FunctionRegistry:
    """函数签名注册表"""

    def __init__(self):
        self._signatures: Dict[str, FunctionSignature] = {}
        self._register_default_signatures()

    def _register_default_signatures(self):
        """注册默认函数签名"""
        defaults = [
            # C标准库
            ("malloc", "libc", [
                ("size", ParamType.UINT)
            ], ParamType.POINTER, CallConvention.CDECL),
            ("free", "libc", [
                ("ptr", ParamType.POINTER)
            ], ParamType.UNKNOWN, CallConvention.CDECL),
            ("memcpy", "libc", [
                ("dest", ParamType.POINTER), ("src", ParamType.POINTER), ("n", ParamType.UINT)
            ], ParamType.POINTER, CallConvention.CDECL),
            ("memset", "libc", [
                ("ptr", ParamType.POINTER), ("value", ParamType.INT), ("n", ParamType.UINT)
            ], ParamType.POINTER, CallConvention.CDECL),
            ("strlen", "libc", [
                ("str", ParamType.STRING)
            ], ParamType.UINT, CallConvention.CDECL),
            ("strcmp", "libc", [
                ("s1", ParamType.STRING), ("s2", ParamType.STRING)
            ], ParamType.INT, CallConvention.CDECL),
            ("printf", "libc", [
                ("format", ParamType.STRING)
            ], ParamType.INT, CallConvention.CDECL, True),
            ("fopen", "libc", [
                ("filename", ParamType.STRING), ("mode", ParamType.STRING)
            ], ParamType.POINTER, CallConvention.CDECL),
            ("fread", "libc", [
                ("ptr", ParamType.POINTER), ("size", ParamType.UINT),
                ("count", ParamType.UINT), ("stream", ParamType.POINTER)
            ], ParamType.UINT, CallConvention.CDECL),
            ("fwrite", "libc", [
                ("ptr", ParamType.POINTER), ("size", ParamType.UINT),
                ("count", ParamType.UINT), ("stream", ParamType.POINTER)
            ], ParamType.UINT, CallConvention.CDECL),
            ("fclose", "libc", [
                ("stream", ParamType.POINTER)
            ], ParamType.INT, CallConvention.CDECL),
            # Windows API
            ("CreateFileW", "kernel32", [
                ("filename", ParamType.STRING), ("access", ParamType.UINT),
                ("share", ParamType.UINT), ("security", ParamType.POINTER),
                ("creation", ParamType.UINT), ("flags", ParamType.UINT),
                ("template", ParamType.HANDLE)
            ], ParamType.HANDLE, CallConvention.STDCALL),
            ("ReadFile", "kernel32", [
                ("file", ParamType.HANDLE), ("buffer", ParamType.POINTER),
                ("bytes", ParamType.UINT), ("read", ParamType.POINTER),
                ("overlapped", ParamType.POINTER)
            ], ParamType.BOOL, CallConvention.STDCALL),
            ("WriteFile", "kernel32", [
                ("file", ParamType.HANDLE), ("buffer", ParamType.POINTER),
                ("bytes", ParamType.UINT), ("written", ParamType.POINTER),
                ("overlapped", ParamType.POINTER)
            ], ParamType.BOOL, CallConvention.STDCALL),
            ("CloseHandle", "kernel32", [
                ("handle", ParamType.HANDLE)
            ], ParamType.BOOL, CallConvention.STDCALL),
            ("VirtualAlloc", "kernel32", [
                ("address", ParamType.POINTER), ("size", ParamType.UINT),
                ("alloc_type", ParamType.UINT), ("protect", ParamType.UINT)
            ], ParamType.POINTER, CallConvention.STDCALL),
            ("VirtualFree", "kernel32", [
                ("address", ParamType.POINTER), ("size", ParamType.UINT),
                ("free_type", ParamType.UINT)
            ], ParamType.BOOL, CallConvention.STDCALL),
            ("MessageBoxA", "user32", [
                ("hwnd", ParamType.HANDLE), ("text", ParamType.STRING),
                ("caption", ParamType.STRING), ("type", ParamType.UINT)
            ], ParamType.INT, CallConvention.STDCALL),
            # 游戏 API
            ("LoadScript", "game", [
                ("path", ParamType.STRING)
            ], ParamType.POINTER, CallConvention.CDECL),
            ("ExecuteScript", "game", [
                ("script", ParamType.POINTER), ("args", ParamType.POINTER)
            ], ParamType.INT, CallConvention.CDECL),
            ("GetGameState", "game", [], ParamType.INT, CallConvention.CDECL),
            ("SetGameState", "game", [
                ("state", ParamType.INT)
            ], ParamType.UNKNOWN, CallConvention.CDECL),
            ("LoadSaveFile", "game", [
                ("slot", ParamType.INT)
            ], ParamType.BOOL, CallConvention.CDECL),
            ("SaveSaveFile", "game", [
                ("slot", ParamType.INT)
            ], ParamType.BOOL, CallConvention.CDECL),
            ("GetGeneralData", "game", [
                ("id", ParamType.INT)
            ], ParamType.POINTER, CallConvention.CDECL),
            ("SetGeneralData", "game", [
                ("id", ParamType.INT), ("data", ParamType.POINTER)
            ], ParamType.BOOL, CallConvention.CDECL),
            ("BattleUpdate", "game", [
                ("delta", ParamType.FLOAT)
            ], ParamType.UNKNOWN, CallConvention.THISCALL),
            ("AIDecision", "game", [
                ("strategy", ParamType.INT), ("context", ParamType.POINTER)
            ], ParamType.INT, CallConvention.CDECL),
        ]

        for name, module, params, ret_type, cc, *extra in defaults:
            is_variadic = extra[0] if extra else False
            sig = FunctionSignature(
                name=name,
                module=module,
                calling_convention=cc,
                params=params,
                return_type=ret_type,
                is_variadic=is_variadic
            )
            self._signatures[f"{module}:{name}"] = sig

    def register(self, name: str, module: str = "", params: List[Tuple[str, ParamType]] = None,
                 return_type: ParamType = ParamType.UNKNOWN,
                 calling_convention: CallConvention = CallConvention.CDECL,
                 address: int = 0, description: str = "",
                 is_variadic: bool = False) -> dict:
        """注册函数签名"""
        key = f"{module}:{name}" if module else name
        sig = FunctionSignature(
            name=name, module=module, address=address,
            calling_convention=calling_convention,
            params=params or [],
            return_type=return_type,
            description=description,
            is_variadic=is_variadic
        )
        self._signatures[key] = sig
        return {"success": True, "message": f"签名注册成功: {key}"}

    def get(self, name: str, module: str = "") -> Optional[FunctionSignature]:
        """获取函数签名"""
        key = f"{module}:{name}" if module else name
        return self._signatures.get(key)

    def get_by_name(self, name: str) -> List[FunctionSignature]:
        """按名称搜索签名"""
        results = []
        for key, sig in self._signatures.items():
            if sig.name == name:
                results.append(sig)
        return results

    def list_by_module(self, module: str) -> List[FunctionSignature]:
        """按模块列出签名"""
        return [sig for key, sig in self._signatures.items() if sig.module == module]

    def list_all(self) -> List[dict]:
        """列出所有签名"""
        return [
            {
                "name": sig.name,
                "module": sig.module,
                "param_count": len(sig.params),
                "return_type": sig.return_type.value,
                "calling_convention": sig.calling_convention.value,
                "address": hex(sig.address) if sig.address else ""
            }
            for sig in self._signatures.values()
        ]

    def search(self, query: str) -> List[dict]:
        """搜索函数签名"""
        query_lower = query.lower()
        results = []
        for key, sig in self._signatures.items():
            if query_lower in sig.name.lower() or query_lower in sig.module.lower():
                results.append({
                    "name": sig.name,
                    "module": sig.module,
                    "params": [(p[0], p[1].value) for p in sig.params],
                    "return_type": sig.return_type.value,
                    "description": sig.description
                })
        return results


# ============================================================
# 调用追踪器
# ============================================================

class CallTracer:
    """调用追踪器 — 核心追踪引擎"""

    def __init__(self):
        self._events: List[TraceEvent] = []
        self._event_counter = 0
        self._enabled = False
        self._depth = 0
        self._thread_id = 0
        self._lock = threading.Lock()
        self._filters: List[dict] = []
        self._signature_registry = FunctionRegistry()
        self._call_stack: List[TraceEvent] = []

    def enable(self) -> dict:
        """启用追踪"""
        self._enabled = True
        return {"success": True, "message": "追踪已启用"}

    def disable(self) -> dict:
        """禁用追踪"""
        self._enabled = False
        return {"success": True, "message": "追踪已禁用"}

    def is_enabled(self) -> bool:
        """检查追踪状态"""
        return self._enabled

    def trace_function_call(self, function_name: str, module: str = "",
                            params: List[Any] = None,
                            address: int = 0, metadata: dict = None) -> int:
        """记录函数调用"""
        if not self._enabled:
            return -1

        if not self._apply_filters(function_name, module):
            return -1

        with self._lock:
            self._event_counter += 1
            event_id = self._event_counter
            self._depth += 1

            event = TraceEvent(
                event_id=event_id,
                event_type=TraceEventType.FUNCTION_CALL,
                timestamp=time.time(),
                function_name=function_name,
                module=module,
                address=address,
                thread_id=self._thread_id,
                params=params or [],
                depth=self._depth,
                caller=self._call_stack[-1].function_name if self._call_stack else None,
                metadata=metadata or {}
            )

            self._events.append(event)
            self._call_stack.append(event)

            return event_id

    def trace_function_return(self, call_event_id: int, return_value: Any = None,
                              metadata: dict = None) -> dict:
        """记录函数返回"""
        if not self._enabled:
            return {"success": False, "message": "追踪未启用"}

        with self._lock:
            self._event_counter += 1
            event_id = self._event_counter

            # 查找对应的调用事件
            call_event = None
            for ev in reversed(self._events):
                if ev.event_id == call_event_id:
                    call_event = ev
                    break

            if call_event:
                duration = time.time() - call_event.timestamp
            else:
                duration = 0.0

            event = TraceEvent(
                event_id=event_id,
                event_type=TraceEventType.FUNCTION_RETURN,
                timestamp=time.time(),
                function_name=call_event.function_name if call_event else "",
                module=call_event.module if call_event else "",
                return_value=return_value,
                duration=duration,
                depth=self._depth,
                metadata=metadata or {}
            )

            self._events.append(event)

            # 弹出调用栈
            if self._call_stack:
                popped = self._call_stack.pop()
                if popped.event_id == call_event_id:
                    self._depth -= 1

            return {
                "success": True,
                "event_id": event_id,
                "call_event_id": call_event_id,
                "duration": round(duration, 6),
                "return_value": str(return_value)[:100] if return_value is not None else None
            }

    def _apply_filters(self, function_name: str, module: str) -> bool:
        """应用过滤器"""
        if not self._filters:
            return True

        for filt in self._filters:
            filter_type = filt.get("type", "include")
            name_pattern = filt.get("name", "")
            module_pattern = filt.get("module", "")

            # 检查是否匹配
            name_match = name_pattern in function_name if name_pattern else True
            module_match = module_pattern in module if module_pattern else True

            if filter_type == "include":
                if name_match and module_match:
                    return True
            elif filter_type == "exclude":
                if name_match and module_match:
                    return False

        # 默认过滤掉
        return any(f.get("type") == "include" for f in self._filters) is False

    def add_filter(self, name: str = "", module: str = "",
                   filter_type: str = "include") -> dict:
        """添加过滤器"""
        if filter_type not in ("include", "exclude"):
            return {"success": False, "message": "过滤类型必须是 include 或 exclude"}
        self._filters.append({
            "type": filter_type,
            "name": name,
            "module": module
        })
        return {"success": True, "message": "过滤器已添加"}

    def clear_filters(self) -> dict:
        """清除所有过滤器"""
        self._filters.clear()
        return {"success": True, "message": "过滤器已清除"}

    def list_filters(self) -> List[dict]:
        """列出所有过滤器"""
        return self._filters

    def get_events(self, limit: int = 100, event_type: str = None) -> List[dict]:
        """获取追踪事件"""
        events = self._events
        if event_type:
            try:
                et = TraceEventType(event_type)
                events = [e for e in events if e.event_type == et]
            except ValueError:
                pass

        return [
            {
                "event_id": e.event_id,
                "type": e.event_type.value,
                "timestamp": round(e.timestamp, 6),
                "function": e.function_name,
                "module": e.module,
                "params": [str(p)[:50] for p in e.params],
                "return_value": str(e.return_value)[:50] if e.return_value is not None else None,
                "duration": round(e.duration, 6),
                "depth": e.depth,
                "caller": e.caller
            }
            for e in events[-limit:]
        ]

    def get_event_count(self) -> int:
        """获取事件数量"""
        return len(self._events)

    def clear_events(self) -> dict:
        """清除所有事件"""
        with self._lock:
            self._events.clear()
            self._event_counter = 0
            self._depth = 0
            self._call_stack.clear()
        return {"success": True, "message": "事件已清除"}

    def get_statistics(self) -> dict:
        """获取追踪统计"""
        function_counts = Counter()
        module_counts = Counter()
        total_duration = 0.0
        errors = 0

        call_events = {}
        for event in self._events:
            if event.event_type == TraceEventType.FUNCTION_CALL:
                function_counts[event.function_name] += 1
                module_counts[event.module] += 1
                call_events[event.event_id] = event

            elif event.event_type == TraceEventType.FUNCTION_RETURN:
                if event.duration > 0:
                    total_duration += event.duration

        return {
            "success": True,
            "total_events": len(self._events),
            "unique_functions": len(function_counts),
            "unique_modules": len(module_counts),
            "top_functions": function_counts.most_common(20),
            "top_modules": module_counts.most_common(10),
            "total_duration": round(total_duration, 6),
            "max_depth": self._depth,
            "active_filters": len(self._filters)
        }

    def get_call_tree(self) -> dict:
        """获取调用树"""
        root = CallNode(function_name="__root__")
        node_map: Dict[str, CallNode] = {"__root__": root}
        call_pairs = []

        # 匹配调用和返回
        call_events = {}
        for event in self._events:
            if event.event_type == TraceEventType.FUNCTION_CALL:
                call_events[event.event_id] = event

        return_events = {}
        for event in self._events:
            if event.event_type == TraceEventType.FUNCTION_RETURN:
                # 找到最近的匹配调用
                for call_id, call_ev in reversed(list(call_events.items())):
                    if call_ev.function_name == event.function_name and call_id not in return_events:
                        return_events[call_id] = event
                        call_pairs.append((call_ev, event))
                        break

        # 构建调用树
        for call_event, return_event in call_pairs:
            key = call_event.function_name
            if key not in node_map:
                node_map[key] = CallNode(function_name=key, module=call_event.module)

            node = node_map[key]
            node.call_count += 1
            node.total_duration += return_event.duration
            node.avg_duration = node.total_duration / node.call_count
            node.min_duration = min(node.min_duration, return_event.duration)
            node.max_duration = max(node.max_duration, return_event.duration)

            # 添加调用者关系
            caller_name = call_event.caller or "__root__"
            if caller_name not in node_map:
                node_map[caller_name] = CallNode(function_name=caller_name)

            parent = node_map[caller_name]
            if key not in parent.children:
                parent.children[key] = node
                node.parent = parent

        return {
            "success": True,
            "total_functions": len(node_map) - 1,  # 减去 root
            "call_pairs": len(call_pairs),
            "tree": _serialize_call_node(root)
        }


def _serialize_call_node(node: CallNode, max_depth: int = 5) -> dict:
    """序列化调用树节点"""
    result = {
        "function": node.function_name,
        "module": node.module,
        "call_count": node.call_count,
        "total_duration": round(node.total_duration, 6),
        "avg_duration": round(node.avg_duration, 6),
        "min_duration": round(node.min_duration, 6) if node.min_duration != float("inf") else 0,
        "max_duration": round(node.max_duration, 6),
        "errors": node.errors
    }

    if max_depth > 0 and node.children:
        result["children"] = [
            _serialize_call_node(child, max_depth - 1)
            for child in node.children.values()
        ]

    return result


# ============================================================
# API拦截器
# ============================================================

class APIInterceptor:
    """API拦截器 — 拦截和修改API调用"""

    def __init__(self, tracer: CallTracer = None):
        self._hooks: Dict[str, Hook] = {}
        self._hook_counter = 0
        self._tracer = tracer
        self._intercepted_calls: Dict[str, Any] = {}
        self._original_functions: Dict[str, Callable] = {}

    def add_hook(self, function_name: str, hook_type: str, callback: Callable,
                 module: str = "", condition: str = "",
                 metadata: dict = None) -> dict:
        """添加Hook"""
        try:
            ht = HookType(hook_type)
        except ValueError:
            return {"success": False, "message": f"无效的Hook类型: {hook_type}"}

        self._hook_counter += 1
        hook_id = f"hook_{self._hook_counter}"

        hook = Hook(
            hook_id=hook_id,
            function_name=function_name,
            hook_type=ht,
            callback=callback,
            module=module,
            condition=condition,
            metadata=metadata or {}
        )
        self._hooks[hook_id] = hook
        return {"success": True, "hook_id": hook_id, "message": f"Hook添加成功: {function_name}"}

    def remove_hook(self, hook_id: str) -> dict:
        """移除Hook"""
        if hook_id in self._hooks:
            hook = self._hooks[hook_id]
            del self._hooks[hook_id]
            return {"success": True, "message": f"Hook已移除: {hook.function_name}"}
        return {"success": False, "message": f"Hook不存在: {hook_id}"}

    def enable_hook(self, hook_id: str) -> dict:
        """启用Hook"""
        hook = self._hooks.get(hook_id)
        if not hook:
            return {"success": False, "message": f"Hook不存在: {hook_id}"}
        hook.enabled = True
        return {"success": True, "message": f"Hook已启用: {hook.function_name}"}

    def disable_hook(self, hook_id: str) -> dict:
        """禁用Hook"""
        hook = self._hooks.get(hook_id)
        if not hook:
            return {"success": False, "message": f"Hook不存在: {hook_id}"}
        hook.enabled = False
        return {"success": True, "message": f"Hook已禁用: {hook.function_name}"}

    def get_hook(self, hook_id: str) -> Optional[dict]:
        """获取Hook详情"""
        hook = self._hooks.get(hook_id)
        if not hook:
            return None
        return {
            "hook_id": hook.hook_id,
            "function_name": hook.function_name,
            "hook_type": hook.hook_type.value,
            "module": hook.module,
            "condition": hook.condition,
            "enabled": hook.enabled,
            "hit_count": hook.hit_count,
            "metadata": hook.metadata
        }

    def list_hooks(self) -> List[dict]:
        """列出所有Hook"""
        return [
            {
                "hook_id": h.hook_id,
                "function_name": h.function_name,
                "hook_type": h.hook_type.value,
                "module": h.module,
                "enabled": h.enabled,
                "hit_count": h.hit_count
            }
            for h in self._hooks.values()
        ]

    def intercept(self, function_name: str, args: tuple = None,
                  kwargs: dict = None, module: str = "") -> dict:
        """模拟拦截API调用"""
        args = args or ()
        kwargs = kwargs or {}

        # 检查条件
        hooks = [
            h for h in self._hooks.values()
            if h.function_name == function_name and h.enabled
            and (not h.module or h.module == module)
        ]

        if not hooks:
            return {"intercepted": False, "result": None, "hooks": 0}

        result = None
        modified_args = list(args)
        modified_kwargs = dict(kwargs)
        hooks_triggered = 0

        for hook in hooks:
            if not hook.enabled:
                continue

            try:
                if hook.hook_type == HookType.PRE_CALL:
                    result = hook.callback(function_name, modified_args, modified_kwargs)
                elif hook.hook_type == HookType.POST_CALL:
                    result = hook.callback(function_name, result, modified_args, modified_kwargs)
                elif hook.hook_type == HookType.REPLACE:
                    result = hook.callback(function_name, modified_args, modified_kwargs)
                elif hook.hook_type == HookType.PRE_POST:
                    pre_result = hook.callback("pre", function_name, modified_args, modified_kwargs)
                    if pre_result is not None:
                        modified_args = list(pre_result.get("args", modified_args))
                        modified_kwargs = pre_result.get("kwargs", modified_kwargs)

                hook.hit_count += 1
                hooks_triggered += 1
            except Exception as e:
                if self._tracer:
                    self._tracer.trace_function_call(
                        f"hook_error_{hook.hook_id}", "interceptor",
                        params=[str(e)]
                    )

        return {
            "intercepted": True,
            "result": result,
            "hooks": hooks_triggered,
            "modified_args": modified_args,
            "modified_kwargs": modified_kwargs
        }

    def wrap_function(self, func: Callable, function_name: str,
                      module: str = "") -> Callable:
        """包装函数以进行拦截"""
        tracer = self._tracer

        @wraps(func)
        def wrapper(*args, **kwargs):
            # 追踪调用
            call_id = None
            if tracer and tracer.is_enabled():
                call_id = tracer.trace_function_call(
                    function_name, module,
                    params=list(args)
                )

            # 拦截
            intercept_result = self.intercept(
                function_name, args, kwargs, module
            )

            if intercept_result["intercepted"] and intercept_result["result"] is not None:
                result = intercept_result["result"]
            else:
                result = func(*args, **kwargs)

            # 追踪返回
            if call_id and call_id > 0 and tracer:
                tracer.trace_function_return(call_id, result)

            return result

        self._original_functions[function_name] = func
        return wrapper

    def get_wrapped_function(self, function_name: str) -> Optional[Callable]:
        """获取原始函数"""
        return self._original_functions.get(function_name)

    def clear_hooks(self) -> dict:
        """清除所有Hook"""
        count = len(self._hooks)
        self._hooks.clear()
        return {"success": True, "message": f"已清除 {count} 个Hook"}


# ============================================================
# 性能分析器
# ============================================================

class PerformanceProfiler:
    """性能分析器 — 函数性能统计"""

    def __init__(self):
        self._profiles: Dict[str, PerformanceProfile] = {}
        self._lock = threading.Lock()

    def record_call(self, function_name: str, module: str = "",
                    duration: float = 0.0) -> None:
        """记录函数调用"""
        with self._lock:
            key = f"{module}:{function_name}" if module else function_name
            if key not in self._profiles:
                self._profiles[key] = PerformanceProfile(
                    function_name=function_name, module=module
                )

            profile = self._profiles[key]
            profile.call_count += 1
            profile.total_time += duration
            profile.avg_time = profile.total_time / profile.call_count
            profile.min_time = min(profile.min_time, duration)
            profile.max_time = max(profile.max_time, duration)
            profile.times.append(duration)

    def get_profile(self, function_name: str, module: str = "") -> Optional[dict]:
        """获取性能分析"""
        key = f"{module}:{function_name}" if module else function_name
        profile = self._profiles.get(key)
        if not profile:
            return None

        return self._serialize_profile(profile)

    def get_all_profiles(self, sort_by: str = "total_time") -> List[dict]:
        """获取所有性能分析"""
        profiles = list(self._profiles.values())

        if sort_by == "total_time":
            profiles.sort(key=lambda p: p.total_time, reverse=True)
        elif sort_by == "avg_time":
            profiles.sort(key=lambda p: p.avg_time, reverse=True)
        elif sort_by == "call_count":
            profiles.sort(key=lambda p: p.call_count, reverse=True)

        return [self._serialize_profile(p) for p in profiles]

    def _serialize_profile(self, profile: PerformanceProfile) -> dict:
        """序列化性能分析"""
        if profile.times:
            times_sorted = sorted(profile.times)
            p50 = times_sorted[len(times_sorted) // 2]
            p95 = times_sorted[int(len(times_sorted) * 0.95)]
            p99 = times_sorted[int(len(times_sorted) * 0.99)]
        else:
            p50 = p95 = p99 = 0.0

        return {
            "function": profile.function_name,
            "module": profile.module,
            "call_count": profile.call_count,
            "total_time": round(profile.total_time, 6),
            "avg_time": round(profile.avg_time, 6),
            "min_time": round(profile.min_time, 6) if profile.min_time != float("inf") else 0,
            "max_time": round(profile.max_time, 6),
            "p50_time": round(p50, 6),
            "p95_time": round(p95, 6),
            "p99_time": round(p99, 6)
        }

    def get_summary(self) -> dict:
        """获取性能摘要"""
        if not self._profiles:
            return {"success": True, "total_functions": 0, "total_calls": 0}

        total_calls = sum(p.call_count for p in self._profiles.values())
        total_time = sum(p.total_time for p in self._profiles.values())

        # 热点函数
        hotspots = sorted(
            self._profiles.values(),
            key=lambda p: p.total_time, reverse=True
        )[:10]

        return {
            "success": True,
            "total_functions": len(self._profiles),
            "total_calls": total_calls,
            "total_time": round(total_time, 6),
            "hotspots": [
                {
                    "function": p.function_name,
                    "module": p.module,
                    "total_time": round(p.total_time, 6),
                    "percentage": round(p.total_time / total_time * 100, 2) if total_time > 0 else 0
                }
                for p in hotspots
            ]
        }

    def clear(self) -> dict:
        """清除所有性能数据"""
        count = len(self._profiles)
        self._profiles.clear()
        return {"success": True, "message": f"已清除 {count} 个性能分析"}

    def compare(self, function_name1: str, function_name2: str) -> dict:
        """比较两个函数的性能"""
        p1 = self._profiles.get(function_name1)
        p2 = self._profiles.get(function_name2)

        if not p1 or not p2:
            return {"success": False, "message": "一个或多个函数不存在"}

        return {
            "success": True,
            "function1": {
                "name": function_name1,
                "calls": p1.call_count,
                "total_time": round(p1.total_time, 6),
                "avg_time": round(p1.avg_time, 6)
            },
            "function2": {
                "name": function_name2,
                "calls": p2.call_count,
                "total_time": round(p2.total_time, 6),
                "avg_time": round(p2.avg_time, 6)
            },
            "time_ratio": round(p1.total_time / p2.total_time, 3) if p2.total_time > 0 else float("inf")
        }


# ============================================================
# 调用图生成器
# ============================================================

class CallGraphGenerator:
    """调用图生成器 — 生成各种格式的调用图"""

    @staticmethod
    def generate_dot(tracer: CallTracer) -> str:
        """生成 Graphviz DOT 格式"""
        lines = ["digraph CallGraph {"]
        lines.append('  rankdir=TB;')
        lines.append('  node [shape=box, style=filled, fillcolor=lightblue];')

        # 匹配调用和返回
        call_events = {}
        for event in tracer._events:
            if event.event_type == TraceEventType.FUNCTION_CALL:
                call_events[event.event_id] = event

        pairs = []
        return_events = {}
        for event in tracer._events:
            if event.event_type == TraceEventType.FUNCTION_RETURN:
                for call_id, call_ev in reversed(list(call_events.items())):
                    if call_ev.function_name == event.function_name and call_id not in return_events:
                        return_events[call_id] = event
                        pairs.append((call_ev, event))
                        break

        edges = Counter()
        for call_ev, ret_ev in pairs:
            caller = call_ev.caller or "__main__"
            callee = call_ev.function_name
            edges[(caller, callee)] += 1

        # 添加节点
        all_nodes = set()
        for (caller, callee) in edges:
            all_nodes.add(caller)
            all_nodes.add(callee)

        for node in sorted(all_nodes):
            if node == "__main__":
                lines.append(f'  "{node}" [shape=box, style=filled, fillcolor=lightgreen];')
            else:
                lines.append(f'  "{node}" [shape=box, style=filled, fillcolor=lightblue];')

        # 添加边
        for (caller, callee), count in edges.items():
            lines.append(f'  "{caller}" -> "{callee}" [label="{count}"];')

        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def generate_json(tracer: CallTracer) -> dict:
        """生成 JSON 格式调用图"""
        call_tree = tracer.get_call_tree()
        return {
            "format": "call_graph",
            "version": "1.0",
            "tree": call_tree.get("tree", {}),
            "total_functions": call_tree.get("total_functions", 0),
            "total_calls": call_tree.get("call_pairs", 0)
        }

    @staticmethod
    def generate_mermaid(tracer: CallTracer) -> str:
        """生成 Mermaid 格式调用图"""
        lines = ["graph TD"]

        call_events = {}
        for event in tracer._events:
            if event.event_type == TraceEventType.FUNCTION_CALL:
                call_events[event.event_id] = event

        pairs = []
        return_events = {}
        for event in tracer._events:
            if event.event_type == TraceEventType.FUNCTION_RETURN:
                for call_id, call_ev in reversed(list(call_events.items())):
                    if call_ev.function_name == event.function_name and call_id not in return_events:
                        return_events[call_id] = event
                        pairs.append((call_ev, event))
                        break

        edges = Counter()
        for call_ev, ret_ev in pairs:
            caller = call_ev.caller or "MAIN"
            callee = call_ev.function_name
            edges[(caller.replace(":", "_"), callee.replace(":", "_"))] += 1

        for (caller, callee), count in edges.items():
            lines.append(f"    {caller} -->|{count}x| {callee}")

        return "\n".join(lines)

    @staticmethod
    def generate_sequence(tracer: CallTracer) -> str:
        """生成序列图文本"""
        lines = ["# 调用序列"]
        lines.append("")

        for event in tracer._events:
            if event.event_type == TraceEventType.FUNCTION_CALL:
                indent = "  " * event.depth
                params_str = ", ".join(str(p)[:30] for p in event.params)
                lines.append(f"{indent}→ {event.function_name}({params_str})")
                lines.append(f"{indent}  [{event.module}]")

            elif event.event_type == TraceEventType.FUNCTION_RETURN:
                indent = "  " * event.depth
                ret_str = str(event.return_value)[:30] if event.return_value is not None else "void"
                lines.append(f"{indent}← return {ret_str} ({event.duration:.6f}s)")

        return "\n".join(lines)


# ============================================================
# 主分析器
# ============================================================

class CallTracerEngine:
    """
    调用追踪与API拦截器主类
    
    整合所有子模块:
    - 函数签名注册表
    - 调用追踪器
    - API拦截器
    - 性能分析器
    - 调用图生成器
    - 数据导出
    """

    def __init__(self):
        self.registry = FunctionRegistry()
        self.tracer = CallTracer()
        self.interceptor = APIInterceptor(self.tracer)
        self.profiler = PerformanceProfiler()
        self.graph_generator = CallGraphGenerator()

    # ============================================================
    # 参数解析
    # ============================================================

    @staticmethod
    def parse_params(raw_params: List[Any], signature: FunctionSignature = None) -> List[dict]:
        """解析参数列表"""
        parsed = []
        for i, param in enumerate(raw_params):
            param_info = {
                "index": i,
                "raw_value": str(param)[:100],
                "type": "unknown",
                "interpreted": None
            }

            # 从签名获取类型
            if signature and i < len(signature.params):
                param_info["name"] = signature.params[i][0]
                param_info["type"] = signature.params[i][1].value

            # 尝试解释值
            if isinstance(param, int):
                param_info["interpreted"] = {
                    "int": param,
                    "hex": hex(param),
                    "is_pointer": 0x100000 <= param <= 0x7FFFFFFFFFFF
                }
            elif isinstance(param, str):
                param_info["type"] = "string"
                param_info["interpreted"] = {"string": param}
            elif isinstance(param, float):
                param_info["type"] = "float"
                param_info["interpreted"] = {"float": param}
            elif isinstance(param, bytes):
                param_info["type"] = "bytes"
                param_info["interpreted"] = {"hex": param.hex(), "size": len(param)}
            elif param is None:
                param_info["type"] = "null"

            parsed.append(param_info)

        return parsed

    # ============================================================
    # 追踪操作
    # ============================================================

    def enable_tracing(self) -> dict:
        """启用追踪"""
        return self.tracer.enable()

    def disable_tracing(self) -> dict:
        """禁用追踪"""
        return self.tracer.disable()

    def is_tracing(self) -> bool:
        """检查追踪状态"""
        return self.tracer.is_enabled()

    def trace_call(self, function_name: str, module: str = "",
                   params: List[Any] = None, address: int = 0) -> dict:
        """追踪一次函数调用"""
        call_id = self.tracer.trace_function_call(
            function_name, module, params, address
        )
        if call_id < 0:
            return {"success": False, "message": "追踪未启用或被过滤"}

        return {
            "success": True,
            "call_id": call_id,
            "function": function_name,
            "module": module,
            "depth": self.tracer._depth
        }

    def trace_return(self, call_id: int, return_value: Any = None) -> dict:
        """追踪一次函数返回"""
        result = self.tracer.trace_function_return(call_id, return_value)

        if result["success"]:
            # 记录性能
            func_name = ""
            for ev in reversed(self.tracer._events):
                if ev.event_id == call_id:
                    func_name = ev.function_name
                    break
            self.profiler.record_call(func_name, "", result["duration"])

        return result

    def add_filter(self, name: str = "", module: str = "",
                   filter_type: str = "include") -> dict:
        """添加追踪过滤器"""
        return self.tracer.add_filter(name, module, filter_type)

    def clear_filters(self) -> dict:
        """清除追踪过滤器"""
        return self.tracer.clear_filters()

    def list_filters(self) -> List[dict]:
        """列出追踪过滤器"""
        return self.tracer.list_filters()

    def get_trace_events(self, limit: int = 100, event_type: str = None) -> List[dict]:
        """获取追踪事件"""
        return self.tracer.get_events(limit, event_type)

    def get_trace_statistics(self) -> dict:
        """获取追踪统计"""
        return self.tracer.get_statistics()

    def get_call_tree(self) -> dict:
        """获取调用树"""
        return self.tracer.get_call_tree()

    def clear_trace(self) -> dict:
        """清除追踪数据"""
        return self.tracer.clear_events()

    # ============================================================
    # Hook操作
    # ============================================================

    def add_hook(self, function_name: str, hook_type: str, callback: Callable = None,
                 module: str = "", condition: str = "") -> dict:
        """添加Hook"""
        if callback is None:
            callback = lambda *args: None
        return self.interceptor.add_hook(
            function_name, hook_type, callback, module, condition
        )

    def remove_hook(self, hook_id: str) -> dict:
        """移除Hook"""
        return self.interceptor.remove_hook(hook_id)

    def enable_hook(self, hook_id: str) -> dict:
        """启用Hook"""
        return self.interceptor.enable_hook(hook_id)

    def disable_hook(self, hook_id: str) -> dict:
        """禁用Hook"""
        return self.interceptor.disable_hook(hook_id)

    def get_hook(self, hook_id: str) -> Optional[dict]:
        """获取Hook"""
        return self.interceptor.get_hook(hook_id)

    def list_hooks(self) -> List[dict]:
        """列出所有Hook"""
        return self.interceptor.list_hooks()

    def intercept_call(self, function_name: str, args: List[Any] = None,
                       kwargs: dict = None, module: str = "") -> dict:
        """拦截一次调用"""
        return self.interceptor.intercept(
            function_name, tuple(args or []), kwargs or {}, module
        )

    def wrap_function(self, func: Callable, function_name: str,
                      module: str = "") -> Callable:
        """包装函数"""
        return self.interceptor.wrap_function(func, function_name, module)

    def clear_hooks(self) -> dict:
        """清除所有Hook"""
        return self.interceptor.clear_hooks()

    # ============================================================
    # 签名操作
    # ============================================================

    def register_signature(self, name: str, module: str = "",
                           params: List[tuple] = None,
                           return_type: str = "unknown",
                           calling_convention: str = "cdecl") -> dict:
        """注册函数签名"""
        try:
            rt = ParamType(return_type)
            cc = CallConvention(calling_convention)
        except ValueError:
            return {"success": False, "message": "无效的类型"}

        parsed_params = []
        if params:
            for p in params:
                if len(p) >= 2:
                    try:
                        pt = ParamType(p[1])
                        parsed_params.append((p[0], pt))
                    except ValueError:
                        parsed_params.append((p[0], ParamType.UNKNOWN))
                elif len(p) == 1:
                    parsed_params.append((p[0], ParamType.UNKNOWN))

        return self.registry.register(
            name, module, parsed_params, rt, cc
        )

    def get_signature(self, name: str, module: str = "") -> Optional[dict]:
        """获取函数签名"""
        sig = self.registry.get(name, module)
        if not sig:
            return None
        return {
            "name": sig.name,
            "module": sig.module,
            "params": [(p[0], p[1].value) for p in sig.params],
            "return_type": sig.return_type.value,
            "calling_convention": sig.calling_convention.value,
            "description": sig.description
        }

    def search_signatures(self, query: str) -> List[dict]:
        """搜索函数签名"""
        return self.registry.search(query)

    def list_signatures(self) -> List[dict]:
        """列出所有签名"""
        return self.registry.list_all()

    def list_signatures_by_module(self, module: str) -> List[dict]:
        """按模块列出签名"""
        sigs = self.registry.list_by_module(module)
        return [
            {
                "name": s.name,
                "params": [(p[0], p[1].value) for p in s.params],
                "return_type": s.return_type.value
            }
            for s in sigs
        ]

    # ============================================================
    # 性能分析操作
    # ============================================================

    def get_performance_profile(self, function_name: str) -> Optional[dict]:
        """获取性能分析"""
        return self.profiler.get_profile(function_name)

    def get_all_performance_profiles(self, sort_by: str = "total_time") -> List[dict]:
        """获取所有性能分析"""
        return self.profiler.get_all_profiles(sort_by)

    def get_performance_summary(self) -> dict:
        """获取性能摘要"""
        return self.profiler.get_summary()

    def clear_performance_data(self) -> dict:
        """清除性能数据"""
        return self.profiler.clear()

    def compare_performance(self, func1: str, func2: str) -> dict:
        """比较性能"""
        return self.profiler.compare(func1, func2)

    # ============================================================
    # 调用图操作
    # ============================================================

    def generate_call_graph_dot(self) -> str:
        """生成 DOT 格式调用图"""
        return self.graph_generator.generate_dot(self.tracer)

    def generate_call_graph_json(self) -> dict:
        """生成 JSON 格式调用图"""
        return self.graph_generator.generate_json(self.tracer)

    def generate_call_graph_mermaid(self) -> str:
        """生成 Mermaid 格式调用图"""
        return self.graph_generator.generate_mermaid(self.tracer)

    def generate_call_sequence(self) -> str:
        """生成调用序列"""
        return self.graph_generator.generate_sequence(self.tracer)

    # ============================================================
    # 导出操作
    # ============================================================

    def export_trace(self, file_path: str, format: str = "json") -> dict:
        """导出追踪数据"""
        try:
            data = {
                "version": "1.0",
                "timestamp": time.time(),
                "events": [
                    {
                        "event_id": e.event_id,
                        "type": e.event_type.value,
                        "timestamp": e.timestamp,
                        "function": e.function_name,
                        "module": e.module,
                        "address": hex(e.address) if e.address else "",
                        "params": [str(p) for p in e.params],
                        "return_value": str(e.return_value) if e.return_value is not None else None,
                        "duration": e.duration,
                        "depth": e.depth,
                        "caller": e.caller
                    }
                    for e in self.tracer._events
                ],
                "statistics": self.tracer.get_statistics()
            }

            if format == "json":
                os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

            elif format == "dot":
                dot_graph = self.graph_generator.generate_dot(self.tracer)
                os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(dot_graph)

            elif format == "mermaid":
                mmd = self.graph_generator.generate_mermaid(self.tracer)
                os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(mmd)

            elif format == "sequence":
                seq = self.graph_generator.generate_sequence(self.tracer)
                os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(seq)

            else:
                return {"success": False, "message": f"不支持的格式: {format}"}

            return {
                "success": True,
                "message": f"导出成功: {file_path}",
                "format": format,
                "event_count": len(self.tracer._events)
            }
        except Exception as e:
            return {"success": False, "message": f"导出失败: {str(e)}"}

    def get_info(self) -> dict:
        """获取引擎信息"""
        return {
            "name": "调用追踪与API拦截器",
            "version": "1.0.0",
            "capabilities": [
                "函数调用追踪", "API拦截", "参数日志", "返回值捕获",
                "调用图生成 (DOT/Mermaid/JSON)", "性能分析 (P50/P95/P99)",
                "Hook管理", "调用统计", "过滤器", "数据导出",
                "函数签名注册", "调用序列生成"
            ],
            "trace_enabled": self.tracer.is_enabled(),
            "event_count": self.tracer.get_event_count(),
            "hook_count": len(self.interceptor._hooks),
            "signature_count": len(self.registry._signatures),
            "profiled_functions": len(self.profiler._profiles)
        }