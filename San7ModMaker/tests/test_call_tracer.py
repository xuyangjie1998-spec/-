"""
调用追踪与API拦截器测试套件
测试 call_tracer.py 的所有核心功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import time
import tempfile
import json
from core.call_tracer import (
    CallTracerEngine, CallTracer, APIInterceptor,
    PerformanceProfiler, CallGraphGenerator,
    FunctionRegistry, FunctionSignature,
    TraceEventType, HookType, ParamType, CallConvention,
    TraceEvent, Hook, CallNode, PerformanceProfile
)


class TestFunctionRegistry(unittest.TestCase):
    """函数签名注册表测试"""

    def setUp(self):
        self.registry = FunctionRegistry()

    def test_default_signatures(self):
        sigs = self.registry.list_all()
        self.assertGreater(len(sigs), 10)

    def test_get_signature(self):
        sig = self.registry.get("malloc", "libc")
        self.assertIsNotNone(sig)
        self.assertEqual(sig.name, "malloc")
        self.assertEqual(sig.module, "libc")

    def test_get_nonexistent(self):
        sig = self.registry.get("nonexistent", "nonexistent")
        self.assertIsNone(sig)

    def test_get_by_name(self):
        results = self.registry.get_by_name("malloc")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].name, "malloc")

    def test_list_by_module(self):
        results = self.registry.list_by_module("libc")
        self.assertGreater(len(results), 3)
        self.assertTrue(all(s.module == "libc" for s in results))

    def test_register_signature(self):
        result = self.registry.register(
            "test_func", "test_module",
            [("arg1", ParamType.INT), ("arg2", ParamType.STRING)],
            ParamType.BOOL, CallConvention.CDECL,
            description="测试函数"
        )
        self.assertTrue(result["success"])
        sig = self.registry.get("test_func", "test_module")
        self.assertIsNotNone(sig)
        self.assertEqual(sig.description, "测试函数")

    def test_search(self):
        results = self.registry.search("malloc")
        self.assertGreater(len(results), 0)

    def test_search_no_match(self):
        results = self.registry.search("zzzzzz_not_found")
        self.assertEqual(len(results), 0)


class TestCallTracer(unittest.TestCase):
    """调用追踪器测试"""

    def setUp(self):
        self.tracer = CallTracer()

    def test_enable_disable(self):
        self.assertFalse(self.tracer.is_enabled())
        result = self.tracer.enable()
        self.assertTrue(result["success"])
        self.assertTrue(self.tracer.is_enabled())
        result = self.tracer.disable()
        self.assertTrue(result["success"])
        self.assertFalse(self.tracer.is_enabled())

    def test_trace_call_disabled(self):
        """追踪未启用时不应记录"""
        call_id = self.tracer.trace_function_call("test_func")
        self.assertEqual(call_id, -1)

    def test_trace_call(self):
        self.tracer.enable()
        call_id = self.tracer.trace_function_call(
            "test_func", "test_module",
            params=[1, "hello", 3.14]
        )
        self.assertGreater(call_id, 0)
        self.assertEqual(self.tracer.get_event_count(), 1)

    def test_trace_call_and_return(self):
        self.tracer.enable()
        call_id = self.tracer.trace_function_call("test_func", params=[42])
        result = self.tracer.trace_function_return(call_id, "result_value")
        self.assertTrue(result["success"])
        self.assertGreater(result["duration"], 0)
        self.assertEqual(self.tracer.get_event_count(), 2)

    def test_trace_return_disabled(self):
        result = self.tracer.trace_function_return(1, "value")
        self.assertFalse(result["success"])

    def test_get_events(self):
        self.tracer.enable()
        self.tracer.trace_function_call("func_a")
        self.tracer.trace_function_call("func_b")
        events = self.tracer.get_events(limit=10)
        self.assertEqual(len(events), 2)

    def test_get_events_by_type(self):
        self.tracer.enable()
        call_id = self.tracer.trace_function_call("func_a")
        self.tracer.trace_function_return(call_id, "val")
        events = self.tracer.get_events(event_type="function_call")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "function_call")

    def test_get_statistics(self):
        self.tracer.enable()
        call_id = self.tracer.trace_function_call("func_a")
        self.tracer.trace_function_return(call_id, "val")
        self.tracer.trace_function_call("func_a")
        call_id2 = self.tracer.trace_function_call("func_b")
        self.tracer.trace_function_return(call_id2, "val2")
        stats = self.tracer.get_statistics()
        self.assertTrue(stats["success"])
        self.assertGreater(stats["total_events"], 0)
        self.assertIn("top_functions", stats)

    def test_clear_events(self):
        self.tracer.enable()
        self.tracer.trace_function_call("func_a")
        self.tracer.clear_events()
        self.assertEqual(self.tracer.get_event_count(), 0)

    def test_add_filter_include(self):
        result = self.tracer.add_filter("malloc", "libc", "include")
        self.assertTrue(result["success"])
        self.assertEqual(len(self.tracer.list_filters()), 1)

    def test_add_filter_invalid_type(self):
        result = self.tracer.add_filter("test", filter_type="invalid")
        self.assertFalse(result["success"])

    def test_clear_filters(self):
        self.tracer.add_filter("test", filter_type="include")
        self.tracer.clear_filters()
        self.assertEqual(len(self.tracer.list_filters()), 0)

    def test_call_tree(self):
        self.tracer.enable()
        call_id1 = self.tracer.trace_function_call("main")
        call_id2 = self.tracer.trace_function_call("sub_func")
        time.sleep(0.001)
        self.tracer.trace_function_return(call_id2, "ok")
        self.tracer.trace_function_return(call_id1, "done")
        tree = self.tracer.get_call_tree()
        self.assertTrue(tree["success"])

    def test_call_tree_empty(self):
        tree = self.tracer.get_call_tree()
        self.assertTrue(tree["success"])


class TestAPIInterceptor(unittest.TestCase):
    """API拦截器测试"""

    def setUp(self):
        self.interceptor = APIInterceptor()

    def test_add_hook(self):
        def callback(func_name, args, kwargs):
            return "intercepted"

        result = self.interceptor.add_hook(
            "test_func", "replace", callback
        )
        self.assertTrue(result["success"])
        self.assertIn("hook_id", result)

    def test_add_hook_invalid_type(self):
        result = self.interceptor.add_hook("test", "invalid", lambda: None)
        self.assertFalse(result["success"])

    def test_remove_hook(self):
        self.interceptor.add_hook("test", "replace", lambda *a: None)
        hooks = self.interceptor.list_hooks()
        self.assertEqual(len(hooks), 1)
        result = self.interceptor.remove_hook(hooks[0]["hook_id"])
        self.assertTrue(result["success"])
        self.assertEqual(len(self.interceptor.list_hooks()), 0)

    def test_remove_nonexistent_hook(self):
        result = self.interceptor.remove_hook("nonexistent")
        self.assertFalse(result["success"])

    def test_enable_disable_hook(self):
        self.interceptor.add_hook("test", "replace", lambda *a: "intercepted")
        hooks = self.interceptor.list_hooks()
        hook_id = hooks[0]["hook_id"]

        result = self.interceptor.disable_hook(hook_id)
        self.assertTrue(result["success"])
        hook = self.interceptor.get_hook(hook_id)
        self.assertFalse(hook["enabled"])

        result = self.interceptor.enable_hook(hook_id)
        self.assertTrue(result["success"])
        hook = self.interceptor.get_hook(hook_id)
        self.assertTrue(hook["enabled"])

    def test_get_hook(self):
        self.interceptor.add_hook("test", "replace", lambda *a: None)
        hooks = self.interceptor.list_hooks()
        hook = self.interceptor.get_hook(hooks[0]["hook_id"])
        self.assertIsNotNone(hook)
        self.assertEqual(hook["function_name"], "test")

    def test_get_nonexistent_hook(self):
        hook = self.interceptor.get_hook("nonexistent")
        self.assertIsNone(hook)

    def test_intercept(self):
        def callback(func_name, args, kwargs):
            return f"intercepted_{func_name}"

        self.interceptor.add_hook("test_func", "replace", callback)
        result = self.interceptor.intercept("test_func", (1, 2, 3), {"key": "val"})
        self.assertTrue(result["intercepted"])
        self.assertEqual(result["result"], "intercepted_test_func")

    def test_intercept_no_hooks(self):
        result = self.interceptor.intercept("nonexistent_func")
        self.assertFalse(result["intercepted"])

    def test_wrap_function(self):
        def original_func(x, y):
            return x + y

        wrapped = self.interceptor.wrap_function(original_func, "add")
        result = wrapped(3, 4)
        self.assertEqual(result, 7)

    def test_wrap_function_with_intercept(self):
        def original_func(x, y):
            return x + y

        def callback(func_name, args, kwargs):
            return args[0] * args[1]

        self.interceptor.add_hook("add", "replace", callback)
        wrapped = self.interceptor.wrap_function(original_func, "add")
        result = wrapped(3, 4)
        self.assertEqual(result, 12)

    def test_clear_hooks(self):
        self.interceptor.add_hook("test1", "replace", lambda *a: None)
        self.interceptor.add_hook("test2", "replace", lambda *a: None)
        result = self.interceptor.clear_hooks()
        self.assertTrue(result["success"])
        self.assertEqual(len(self.interceptor.list_hooks()), 0)


class TestPerformanceProfiler(unittest.TestCase):
    """性能分析器测试"""

    def setUp(self):
        self.profiler = PerformanceProfiler()

    def test_record_call(self):
        self.profiler.record_call("test_func", "test_module", 0.001)
        self.profiler.record_call("test_func", "test_module", 0.002)
        self.profiler.record_call("test_func", "test_module", 0.003)

        profile = self.profiler.get_profile("test_func", "test_module")
        self.assertIsNotNone(profile)
        self.assertEqual(profile["call_count"], 3)
        self.assertAlmostEqual(profile["avg_time"], 0.002, places=4)

    def test_get_nonexistent_profile(self):
        profile = self.profiler.get_profile("nonexistent")
        self.assertIsNone(profile)

    def test_get_all_profiles(self):
        self.profiler.record_call("func_a", duration=0.01)
        self.profiler.record_call("func_b", duration=0.02)
        profiles = self.profiler.get_all_profiles(sort_by="total_time")
        self.assertEqual(len(profiles), 2)
        self.assertEqual(profiles[0]["function"], "func_b")

    def test_get_summary(self):
        self.profiler.record_call("func_a", duration=0.01)
        self.profiler.record_call("func_b", duration=0.02)
        summary = self.profiler.get_summary()
        self.assertTrue(summary["success"])
        self.assertEqual(summary["total_functions"], 2)
        self.assertEqual(summary["total_calls"], 2)

    def test_get_summary_empty(self):
        summary = self.profiler.get_summary()
        self.assertTrue(summary["success"])
        self.assertEqual(summary["total_functions"], 0)

    def test_clear(self):
        self.profiler.record_call("func_a", duration=0.01)
        result = self.profiler.clear()
        self.assertTrue(result["success"])
        self.assertEqual(len(self.profiler.get_all_profiles()), 0)

    def test_compare(self):
        self.profiler.record_call("func_a", duration=0.01)
        self.profiler.record_call("func_b", duration=0.05)
        result = self.profiler.compare("func_a", "func_b")
        self.assertTrue(result["success"])
        self.assertEqual(result["time_ratio"], 0.2)

    def test_compare_nonexistent(self):
        result = self.profiler.compare("nonexistent", "func_b")
        self.assertFalse(result["success"])


class TestCallGraphGenerator(unittest.TestCase):
    """调用图生成器测试"""

    def setUp(self):
        self.tracer = CallTracer()
        self.tracer.enable()
        call_id1 = self.tracer.trace_function_call("main")
        call_id2 = self.tracer.trace_function_call("init", params=[1])
        self.tracer.trace_function_return(call_id2, "ok")
        call_id3 = self.tracer.trace_function_call("process", params=["data"])
        call_id4 = self.tracer.trace_function_call("sub_process", params=[42])
        self.tracer.trace_function_return(call_id4, True)
        self.tracer.trace_function_return(call_id3, "done")
        self.tracer.trace_function_return(call_id1, 0)

    def test_generate_dot(self):
        dot = CallGraphGenerator.generate_dot(self.tracer)
        self.assertIn("digraph CallGraph", dot)
        self.assertIn("main", dot)
        self.assertIn("init", dot)

    def test_generate_json(self):
        result = CallGraphGenerator.generate_json(self.tracer)
        self.assertEqual(result["format"], "call_graph")
        self.assertIn("tree", result)

    def test_generate_mermaid(self):
        mmd = CallGraphGenerator.generate_mermaid(self.tracer)
        self.assertIn("graph TD", mmd)

    def test_generate_sequence(self):
        seq = CallGraphGenerator.generate_sequence(self.tracer)
        self.assertIn("调用序列", seq)
        self.assertIn("main", seq)


class TestCallTracerEngine(unittest.TestCase):
    """主引擎测试"""

    def setUp(self):
        self.engine = CallTracerEngine()

    def test_enable_tracing(self):
        result = self.engine.enable_tracing()
        self.assertTrue(result["success"])

    def test_trace_call_and_return(self):
        self.engine.enable_tracing()
        result = self.engine.trace_call("test_func", "test_module", [1, "hello"])
        self.assertTrue(result["success"])
        self.assertIn("call_id", result)

        ret = self.engine.trace_return(result["call_id"], "result")
        self.assertTrue(ret["success"])

    def test_trace_disabled(self):
        result = self.engine.trace_call("test_func")
        self.assertFalse(result["success"])

    def test_add_filter(self):
        result = self.engine.add_filter("test", "module", "include")
        self.assertTrue(result["success"])

    def test_get_trace_events(self):
        self.engine.enable_tracing()
        call_id = self.engine.trace_call("func_a")["call_id"]
        self.engine.trace_return(call_id, "val")
        events = self.engine.get_trace_events(limit=10)
        self.assertEqual(len(events), 2)

    def test_get_trace_statistics(self):
        self.engine.enable_tracing()
        call_id = self.engine.trace_call("func_a")["call_id"]
        self.engine.trace_return(call_id, "val")
        stats = self.engine.get_trace_statistics()
        self.assertTrue(stats["success"])

    def test_get_call_tree(self):
        self.engine.enable_tracing()
        call_id = self.engine.trace_call("func_a")["call_id"]
        self.engine.trace_return(call_id, "val")
        tree = self.engine.get_call_tree()
        self.assertTrue(tree["success"])

    def test_clear_trace(self):
        self.engine.enable_tracing()
        self.engine.trace_call("func_a")
        result = self.engine.clear_trace()
        self.assertTrue(result["success"])

    def test_add_hook(self):
        result = self.engine.add_hook("test_func", "replace")
        self.assertTrue(result["success"])

    def test_remove_hook(self):
        result = self.engine.add_hook("test_func", "replace")
        result = self.engine.remove_hook(result["hook_id"])
        self.assertTrue(result["success"])

    def test_enable_disable_hook(self):
        result = self.engine.add_hook("test_func", "replace")
        hook_id = result["hook_id"]
        self.engine.disable_hook(hook_id)
        hook = self.engine.get_hook(hook_id)
        self.assertFalse(hook["enabled"])
        self.engine.enable_hook(hook_id)
        hook = self.engine.get_hook(hook_id)
        self.assertTrue(hook["enabled"])

    def test_list_hooks(self):
        self.engine.add_hook("test1", "replace")
        self.engine.add_hook("test2", "pre_call")
        hooks = self.engine.list_hooks()
        self.assertEqual(len(hooks), 2)

    def test_intercept_call(self):
        def callback(func_name, args, kwargs):
            return "intercepted"

        self.engine.add_hook("test_func", "replace", callback)
        result = self.engine.intercept_call("test_func", [1, 2, 3])
        self.assertTrue(result["intercepted"])
        self.assertEqual(result["result"], "intercepted")

    def test_wrap_function(self):
        def add(x, y):
            return x + y

        wrapped = self.engine.wrap_function(add, "add")
        result = wrapped(3, 4)
        self.assertEqual(result, 7)

    def test_register_signature(self):
        result = self.engine.register_signature(
            "test_func", "test_module",
            [("arg1", "int"), ("arg2", "string")],
            "bool", "cdecl"
        )
        self.assertTrue(result["success"])

    def test_register_signature_invalid_type(self):
        result = self.engine.register_signature(
            "test", params=[("arg1", "invalid_type")]
        )
        self.assertTrue(result["success"])  # 使用 UNKNOWN 作为回退

    def test_get_signature(self):
        sig = self.engine.get_signature("malloc", "libc")
        self.assertIsNotNone(sig)
        self.assertEqual(sig["name"], "malloc")

    def test_search_signatures(self):
        results = self.engine.search_signatures("malloc")
        self.assertGreater(len(results), 0)

    def test_list_signatures(self):
        sigs = self.engine.list_signatures()
        self.assertGreater(len(sigs), 10)

    def test_list_signatures_by_module(self):
        sigs = self.engine.list_signatures_by_module("libc")
        self.assertGreater(len(sigs), 3)

    def test_get_performance_profile(self):
        self.engine.profiler.record_call("test_func", duration=0.01)
        profile = self.engine.get_performance_profile("test_func")
        self.assertIsNotNone(profile)

    def test_get_all_performance_profiles(self):
        self.engine.profiler.record_call("func_a", duration=0.01)
        self.engine.profiler.record_call("func_b", duration=0.02)
        profiles = self.engine.get_all_performance_profiles()
        self.assertEqual(len(profiles), 2)

    def test_get_performance_summary(self):
        self.engine.profiler.record_call("func_a", duration=0.01)
        summary = self.engine.get_performance_summary()
        self.assertTrue(summary["success"])

    def test_clear_performance_data(self):
        self.engine.profiler.record_call("func_a", duration=0.01)
        result = self.engine.clear_performance_data()
        self.assertTrue(result["success"])

    def test_compare_performance(self):
        self.engine.profiler.record_call("func_a", duration=0.01)
        self.engine.profiler.record_call("func_b", duration=0.05)
        result = self.engine.compare_performance("func_a", "func_b")
        self.assertTrue(result["success"])

    def test_generate_call_graph_dot(self):
        self.engine.enable_tracing()
        call_id = self.engine.trace_call("main")["call_id"]
        self.engine.trace_return(call_id, "done")
        dot = self.engine.generate_call_graph_dot()
        self.assertIn("digraph", dot)

    def test_generate_call_graph_json(self):
        self.engine.enable_tracing()
        call_id = self.engine.trace_call("main")["call_id"]
        self.engine.trace_return(call_id, "done")
        result = self.engine.generate_call_graph_json()
        self.assertIn("tree", result)

    def test_generate_call_graph_mermaid(self):
        self.engine.enable_tracing()
        call_id = self.engine.trace_call("main")["call_id"]
        self.engine.trace_return(call_id, "done")
        mmd = self.engine.generate_call_graph_mermaid()
        self.assertIn("graph", mmd)

    def test_generate_call_sequence(self):
        self.engine.enable_tracing()
        call_id = self.engine.trace_call("main")["call_id"]
        self.engine.trace_return(call_id, "done")
        seq = self.engine.generate_call_sequence()
        self.assertIn("main", seq)

    def test_export_trace_json(self):
        self.engine.enable_tracing()
        call_id = self.engine.trace_call("test_func")["call_id"]
        self.engine.trace_return(call_id, "val")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            result = self.engine.export_trace(path, "json")
            self.assertTrue(result["success"])
            with open(path, "r") as f:
                data = json.load(f)
            self.assertIn("events", data)
        finally:
            os.unlink(path)

    def test_export_trace_dot(self):
        self.engine.enable_tracing()
        call_id = self.engine.trace_call("main")["call_id"]
        self.engine.trace_return(call_id, "done")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".dot", delete=False) as f:
            path = f.name
        try:
            result = self.engine.export_trace(path, "dot")
            self.assertTrue(result["success"])
        finally:
            os.unlink(path)

    def test_export_trace_mermaid(self):
        self.engine.enable_tracing()
        call_id = self.engine.trace_call("main")["call_id"]
        self.engine.trace_return(call_id, "done")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False) as f:
            path = f.name
        try:
            result = self.engine.export_trace(path, "mermaid")
            self.assertTrue(result["success"])
        finally:
            os.unlink(path)

    def test_export_trace_sequence(self):
        self.engine.enable_tracing()
        call_id = self.engine.trace_call("main")["call_id"]
        self.engine.trace_return(call_id, "done")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            path = f.name
        try:
            result = self.engine.export_trace(path, "sequence")
            self.assertTrue(result["success"])
        finally:
            os.unlink(path)

    def test_export_trace_invalid_format(self):
        result = self.engine.export_trace("/tmp/test.xxx", "invalid")
        self.assertFalse(result["success"])

    def test_parse_params(self):
        params = [42, "hello", 3.14, None, b"\x01\x02"]
        sig = self.engine.registry.get("malloc", "libc")
        parsed = self.engine.parse_params(params, sig)
        self.assertEqual(len(parsed), 5)

    def test_get_info(self):
        info = self.engine.get_info()
        self.assertEqual(info["name"], "调用追踪与API拦截器")
        self.assertIn("capabilities", info)

    def test_clear_hooks(self):
        self.engine.add_hook("test1", "replace")
        self.engine.add_hook("test2", "replace")
        result = self.engine.clear_hooks()
        self.assertTrue(result["success"])

    def test_clear_filters(self):
        self.engine.add_filter("test", filter_type="include")
        result = self.engine.clear_filters()
        self.assertTrue(result["success"])

    def test_is_tracing(self):
        self.assertFalse(self.engine.is_tracing())
        self.engine.enable_tracing()
        self.assertTrue(self.engine.is_tracing())


if __name__ == "__main__":
    unittest.main()