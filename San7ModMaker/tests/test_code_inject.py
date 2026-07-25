"""
代码注入与DLL劫持引擎测试套件
测试 code_inject.py 的所有核心功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import tempfile
from core.code_inject import (
    CodeInjectEngine, ProcessAnalyzer, InjectionPlanner,
    CodeCaveFinder, HookGenerator, DLLAnalyzer,
    ProxyDLLGenerator, SecurityAnalyzer,
    ProcessInfo, ModuleInfo, ExportInfo, ImportInfo,
    SectionInfo, CodeCave, HookTemplate, InjectionPlan,
    DllHijackOpportunity, SecurityReport,
    InjectionMethod, HookType, MemoryProtection,
    DllHijackMethod, SecurityMeasure,
    quick_analyze, quick_inject_plan, quick_find_caves, quick_hook_plan,
)


# ============================================================
# 测试数据
# ============================================================

def _make_test_exe_data(size: int = 0x2000) -> bytes:
    """生成模拟 EXE 数据"""
    data = bytearray(size)
    # DOS header
    data[0:2] = b"MZ"
    # PE signature at offset 0x80
    data[0x80:0x84] = b"PE\x00\x00"
    # 一些零填充 (代码洞穴)
    for i in range(0x200, 0x300):
        data[i] = 0
    # INT3 填充区域
    for i in range(0x400, 0x480):
        data[i] = 0xCC
    # NOP 填充区域
    for i in range(0x500, 0x540):
        data[i] = 0x90
    # 模拟代码段
    for i in range(0x1000, 0x1100):
        data[i] = (i * 7 + 13) & 0xFF
    return bytes(data)


# ============================================================
# ProcessAnalyzer 测试
# ============================================================

class TestProcessAnalyzer(unittest.TestCase):
    """进程分析器测试"""

    def setUp(self):
        self.analyzer = ProcessAnalyzer()

    def test_analyze_process(self):
        info = self.analyzer.analyze_process("test_game.exe")
        self.assertIsInstance(info, ProcessInfo)
        self.assertEqual(info.name, "test_game.exe")
        self.assertGreater(len(info.modules), 0)

    def test_analyze_process_with_security(self):
        info = self.analyzer.analyze_process("game_with_easyanticheat.exe")
        self.assertIn(SecurityMeasure.ANTI_DEBUG, info.security_measures)

    def test_analyze_process_with_battleye(self):
        info = self.analyzer.analyze_process("game_with_battleye.exe")
        self.assertIn(SecurityMeasure.ANTI_DEBUG, info.security_measures)

    def test_enumerate_modules(self):
        modules = self.analyzer.enumerate_modules("test_game.exe")
        self.assertGreater(len(modules), 0)
        names = [m.name for m in modules]
        self.assertIn("kernel32.dll", names)

    def test_find_module_found(self):
        mod = self.analyzer.find_module("test_game.exe", "kernel32.dll")
        self.assertIsNotNone(mod)
        self.assertEqual(mod.name, "kernel32.dll")

    def test_find_module_not_found(self):
        mod = self.analyzer.find_module("test_game.exe", "nonexistent.dll")
        self.assertIsNone(mod)

    def test_get_imports(self):
        imports = self.analyzer.get_imports("kernel32.dll")
        self.assertGreater(len(imports), 0)
        names = [i.name for i in imports]
        self.assertIn("LoadLibraryA", names)

    def test_get_imports_empty(self):
        imports = self.analyzer.get_imports("unknown.dll")
        self.assertEqual(len(imports), 0)

    def test_detect_security_eac(self):
        mod = ModuleInfo(name="easyanticheat_x64.dll")
        measures = self.analyzer._detect_security_measures([mod])
        self.assertIn(SecurityMeasure.ANTI_DEBUG, measures)

    def test_detect_security_denuvo(self):
        mod = ModuleInfo(name="denuvo64.dll")
        measures = self.analyzer._detect_security_measures([mod])
        self.assertIn(SecurityMeasure.OBFUSCATION, measures)

    def test_detect_security_multiple(self):
        modules = [
            ModuleInfo(name="easyanticheat.dll"),
            ModuleInfo(name="vmprotect.dll"),
        ]
        measures = self.analyzer._detect_security_measures(modules)
        self.assertIn(SecurityMeasure.ANTI_DEBUG, measures)
        self.assertIn(SecurityMeasure.OBFUSCATION, measures)

    def test_get_known_exports_kernel32(self):
        exports = self.analyzer._get_known_exports("kernel32.dll")
        self.assertGreater(len(exports), 0)
        names = [e.name for e in exports]
        self.assertIn("LoadLibraryA", names)
        self.assertIn("VirtualAlloc", names)

    def test_get_known_exports_cached(self):
        # 第一次调用
        exports1 = self.analyzer._get_known_exports("kernel32.dll")
        # 第二次调用（应从缓存获取）
        exports2 = self.analyzer._get_known_exports("kernel32.dll")
        self.assertEqual(len(exports1), len(exports2))

    def test_get_known_exports_unknown_dll(self):
        exports = self.analyzer._get_known_exports("unknown.dll")
        self.assertEqual(len(exports), 0)


# ============================================================
# InjectionPlanner 测试
# ============================================================

class TestInjectionPlanner(unittest.TestCase):
    """注入策略规划器测试"""

    def setUp(self):
        self.planner = InjectionPlanner()

    def test_plan_injection(self):
        plans = self.planner.plan_injection("test_game.exe", "test.dll")
        self.assertGreater(len(plans), 0)
        self.assertIsInstance(plans[0], InjectionPlan)

    def test_plan_injection_stealth(self):
        plans = self.planner.plan_injection("test_game.exe", prefer_stealth=True)
        self.assertGreaterEqual(plans[0].stealth_level, plans[-1].stealth_level)

    def test_plan_injection_risk(self):
        plans = self.planner.plan_injection("test_game.exe", prefer_stealth=False)
        self.assertLessEqual(plans[0].risk_level, plans[-1].risk_level)

    def test_plan_steps_not_empty(self):
        plans = self.planner.plan_injection("test_game.exe")
        for plan in plans:
            self.assertGreater(len(plan.steps), 0)

    def test_plan_permissions(self):
        plans = self.planner.plan_injection("test_game.exe")
        for plan in plans:
            self.assertGreater(len(plan.required_permissions), 0)

    def test_create_remote_thread_plan(self):
        plan = self.planner._create_plan(
            InjectionMethod.CREATE_REMOTE_THREAD, "test.exe", "test.dll",
            ProcessInfo(pid=0, name="test.exe")
        )
        self.assertEqual(plan.method, InjectionMethod.CREATE_REMOTE_THREAD)
        self.assertGreater(len(plan.steps), 0)
        self.assertIn("CreateRemoteThread", plan.steps[4])

    def test_reflective_dll_plan(self):
        plan = self.planner._create_plan(
            InjectionMethod.REFLECTIVE_DLL, "test.exe", "test.dll",
            ProcessInfo(pid=0, name="test.exe")
        )
        self.assertEqual(plan.method, InjectionMethod.REFLECTIVE_DLL)
        self.assertIn("ReflectiveLoader", plan.steps[0])

    def test_process_hollowing_plan(self):
        plan = self.planner._create_plan(
            InjectionMethod.PROCESS_HOLLOWING, "test.exe", "test.dll",
            ProcessInfo(pid=0, name="test.exe")
        )
        self.assertIn("CREATE_SUSPENDED", plan.steps[0])

    def test_get_best_method_no_security(self):
        plan = self.planner.get_best_method("test.exe", [])
        self.assertIsNotNone(plan)
        self.assertIsInstance(plan, InjectionPlan)

    def test_get_best_method_with_anti_cheat(self):
        plan = self.planner.get_best_method("test.exe", [SecurityMeasure.ANTI_DEBUG])
        self.assertIsNotNone(plan)
        self.assertGreaterEqual(plan.stealth_level, 50)

    def test_all_methods_have_plans(self):
        for method in InjectionMethod:
            plan = self.planner._create_plan(
                method, "test.exe", "test.dll",
                ProcessInfo(pid=0, name="test.exe")
            )
            self.assertIsNotNone(plan)
            self.assertGreater(len(plan.steps), 0, f"No steps for {method}")

    def test_alternatives_not_empty(self):
        plans = self.planner.plan_injection("test.exe")
        for plan in plans:
            self.assertIsInstance(plan.alternatives, list)


# ============================================================
# CodeCaveFinder 测试
# ============================================================

class TestCodeCaveFinder(unittest.TestCase):
    """代码洞穴扫描器测试"""

    def setUp(self):
        self.finder = CodeCaveFinder()
        self.test_data = _make_test_exe_data()

    def test_find_caves(self):
        caves = self.finder.find_caves(self.test_data)
        self.assertGreater(len(caves), 0)

    def test_find_zero_caves(self):
        # 零填充区域: 0x200-0x300 = 256 bytes
        caves = self.finder.find_caves(self.test_data)
        zero_caves = [c for c in caves if c.address <= 0x200 and c.address + c.size >= 0x300]
        self.assertGreater(len(zero_caves), 0, f"No zero cave covering 0x200-0x300; caves found at: {[(hex(c.address), c.size) for c in caves[:5]]}")

    def test_find_int3_caves(self):
        # INT3 填充区域: 0x400-0x480 = 128 bytes
        caves = self.finder.find_caves(self.test_data)
        int3_caves = [c for c in caves if c.address <= 0x400 and c.address + c.size >= 0x480]
        self.assertGreater(len(int3_caves), 0)

    def test_find_nop_caves(self):
        # NOP 填充区域: 0x500-0x540 = 64 bytes
        caves = self.finder.find_caves(self.test_data)
        nop_caves = [c for c in caves if c.address <= 0x500 and c.address + c.size >= 0x540]
        self.assertGreater(len(nop_caves), 0)

    def test_find_best_cave(self):
        cave = self.finder.find_best_cave(self.test_data, 64)
        self.assertIsNotNone(cave)
        self.assertGreaterEqual(cave.size, 64)

    def test_find_best_cave_too_large(self):
        cave = self.finder.find_best_cave(self.test_data, 10000)
        self.assertIsNone(cave)

    def test_find_caves_near_rva(self):
        caves = self.finder.find_caves_near_rva(self.test_data, 0x200, 0x1000)
        self.assertGreater(len(caves), 0)
        # 检查是否有洞穴覆盖或接近 0x200
        found = any(
            abs(c.address - 0x200) <= 0x1000 or
            (c.address <= 0x200 and c.address + c.size >= 0x200)
            for c in caves
        )
        self.assertTrue(found, f"No cave near 0x200; caves: {[(hex(c.address), c.size) for c in caves[:5]]}")

    def test_analyze_cave_quality(self):
        cave = CodeCave(address=0x200, size=512, alignment=4, near_function="test_func")
        quality = self.finder.analyze_cave_quality(cave, self.test_data)
        self.assertIn("quality", quality)
        self.assertGreater(quality["score"], 0)

    def test_analyze_cave_quality_small(self):
        cave = CodeCave(address=0x200, size=16, alignment=1)
        quality = self.finder.analyze_cave_quality(cave, self.test_data)
        self.assertLess(quality["score"], 80)

    def test_caves_sorted_by_size(self):
        caves = self.finder.find_caves(self.test_data)
        for i in range(len(caves) - 1):
            self.assertGreaterEqual(caves[i].size, caves[i + 1].size)

    def test_empty_data(self):
        caves = self.finder.find_caves(b"")
        self.assertEqual(len(caves), 0)

    def test_no_caves_small_data(self):
        # 数据太小，没有洞穴
        small_data = b"\x01\x02\x03\x04\x05"
        caves = self.finder.find_caves(small_data)
        self.assertEqual(len(caves), 0)


# ============================================================
# HookGenerator 测试
# ============================================================

class TestHookGenerator(unittest.TestCase):
    """Hook 生成器测试"""

    def setUp(self):
        self.generator = HookGenerator()

    def test_generate_inline_hook_x64(self):
        hook = self.generator.generate_inline_hook(0x1000, 0x2000, b"\x48\x89\x5C\x24\x08", True)
        self.assertEqual(hook.hook_type, HookType.INLINE)
        self.assertGreater(len(hook.hook_code), 0)
        self.assertGreater(len(hook.trampoline), 0)
        self.assertGreater(len(hook.patches), 0)

    def test_generate_inline_hook_x86(self):
        hook = self.generator.generate_inline_hook(0x1000, 0x2000, b"\x55\x8B\xEC", False)
        self.assertEqual(hook.hook_type, HookType.INLINE)
        self.assertGreater(len(hook.hook_code), 0)

    def test_generate_iat_hook(self):
        hook = self.generator.generate_iat_hook("kernel32.dll", "CreateFileA", 0x3000)
        self.assertEqual(hook.hook_type, HookType.IAT)
        self.assertEqual(hook.target_module, "kernel32.dll")
        self.assertEqual(hook.target_function, "CreateFileA")

    def test_generate_detour(self):
        hook = self.generator.generate_detour(0x1000, 0x2000, b"\x48\x89\x5C\x24\x08")
        self.assertEqual(hook.hook_type, HookType.INLINE)
        self.assertGreater(len(hook.hook_code), 0)

    def test_generate_hot_patch(self):
        hook = self.generator.generate_hot_patch(0x1000, 0x2000, True)
        self.assertEqual(hook.hook_type, HookType.HOT_PATCH)
        self.assertGreater(len(hook.hook_code), 0)
        self.assertEqual(len(hook.patches), 2)

    def test_generate_nop_patch(self):
        hook = self.generator.generate_nop_patch(0x1000, 5)
        self.assertEqual(hook.hook_type, HookType.INLINE)
        self.assertEqual(hook.hook_size, 5)
        self.assertEqual(hook.hook_code, b"\x90" * 5)

    def test_generate_hook_chain(self):
        hooks = [
            {"type": "nop", "target": 0x1000, "size": 5},
            {"type": "iat", "module": "kernel32.dll", "function": "Sleep", "hook": 0x2000},
        ]
        results = self.generator.generate_hook_chain(hooks)
        self.assertEqual(len(results), 2)

    def test_get_hook_code_asm_inline(self):
        hook = self.generator.generate_inline_hook(0x1000, 0x2000, b"\x48\x89\x5C\x24\x08")
        asm = self.generator.get_hook_code_asm(hook)
        self.assertIn("Inline Hook", asm)
        self.assertIn("Trampoline", asm)

    def test_get_hook_code_asm_iat(self):
        hook = self.generator.generate_iat_hook("kernel32.dll", "Sleep", 0x2000)
        asm = self.generator.get_hook_code_asm(hook)
        self.assertIn("IAT Hook", asm)
        self.assertIn("kernel32.dll", asm)

    def test_get_hook_code_asm_hot_patch(self):
        hook = self.generator.generate_hot_patch(0x1000, 0x2000)
        asm = self.generator.get_hook_code_asm(hook)
        self.assertIn("Hot Patch", asm)

    def test_nop_patch_various_sizes(self):
        for size in [1, 2, 3, 5, 10, 20]:
            hook = self.generator.generate_nop_patch(0x1000, size)
            self.assertEqual(hook.hook_size, size)
            self.assertEqual(len(hook.hook_code), size)


# ============================================================
# DLLAnalyzer 测试
# ============================================================

class TestDLLAnalyzer(unittest.TestCase):
    """DLL 分析器测试"""

    def setUp(self):
        self.analyzer = DLLAnalyzer()

    def test_analyze_dll_known(self):
        result = self.analyzer.analyze_dll("kernel32.dll")
        self.assertTrue(result["is_known_dll"])
        self.assertGreater(len(result["hijack_methods"]), 0)

    def test_analyze_dll_unknown(self):
        result = self.analyzer.analyze_dll("custom_game.dll")
        self.assertFalse(result["is_known_dll"])
        self.assertIn(DllHijackMethod.SEARCH_ORDER, result["hijack_methods"])

    def test_analyze_dll_critical(self):
        result = self.analyzer.analyze_dll("ntdll.dll")
        self.assertTrue(result["is_system_critical"])

    def test_analyze_dll_not_critical(self):
        result = self.analyzer.analyze_dll("version.dll")
        self.assertFalse(result["is_system_critical"])

    def test_analyze_dll_cached(self):
        result1 = self.analyzer.analyze_dll("version.dll")
        result2 = self.analyzer.analyze_dll("version.dll")
        self.assertEqual(result1["risk_assessment"], result2["risk_assessment"])

    def test_find_hijack_opportunities(self):
        opportunities = self.analyzer.find_hijack_opportunities("san7.exe")
        self.assertGreater(len(opportunities), 0)
        self.assertIsInstance(opportunities[0], DllHijackOpportunity)

    def test_find_hijack_opportunities_game(self):
        opportunities = self.analyzer.find_hijack_opportunities("unity_game.exe")
        self.assertGreater(len(opportunities), 0)

    def test_hijack_opportunity_has_guide(self):
        opportunities = self.analyzer.find_hijack_opportunities("test.exe")
        for opp in opportunities:
            self.assertIsNotNone(opp.exploit_guide)
            self.assertGreater(len(opp.exploit_guide), 0)

    def test_assess_risk_low(self):
        analysis = {"is_system_critical": False, "is_known_dll": False}
        risk = self.analyzer._assess_risk(analysis)
        self.assertIn("LOW", risk)

    def test_assess_risk_high(self):
        analysis = {"is_system_critical": True, "is_known_dll": True}
        risk = self.analyzer._assess_risk(analysis)
        self.assertIn("HIGH", risk)

    def test_common_hijack_targets(self):
        targets = [t["name"] for t in self.analyzer.COMMON_HIJACK_TARGETS]
        self.assertIn("version.dll", targets)
        self.assertIn("dwmapi.dll", targets)

    def test_known_dlls_list(self):
        self.assertIn("kernel32.dll", self.analyzer.KNOWN_DLLS)
        self.assertIn("ntdll.dll", self.analyzer.KNOWN_DLLS)


# ============================================================
# ProxyDLLGenerator 测试
# ============================================================

class TestProxyDLLGenerator(unittest.TestCase):
    """代理 DLL 生成器测试"""

    def setUp(self):
        self.generator = ProxyDLLGenerator()

    def test_generate_proxy_dll(self):
        files = self.generator.generate_proxy_dll("version.dll")
        self.assertIn("proxy_dll.c", files)
        self.assertIn("proxy_dll.h", files)
        self.assertIn("exports.def", files)
        self.assertIn("build.bat", files)
        self.assertIn("README.txt", files)

    def test_generate_proxy_dll_with_payload(self):
        payload = "MessageBoxA(NULL, \"Injected!\", \"Proxy\", MB_OK);"
        files = self.generator.generate_proxy_dll("version.dll", payload)
        self.assertIn(payload.strip(), files["proxy_dll.c"])

    def test_dll_main_contains_dllmain(self):
        files = self.generator.generate_proxy_dll("version.dll")
        self.assertIn("DllMain", files["proxy_dll.c"])
        self.assertIn("DLL_PROCESS_ATTACH", files["proxy_dll.c"])

    def test_def_file_format(self):
        files = self.generator.generate_proxy_dll("version.dll")
        self.assertIn("LIBRARY", files["exports.def"])
        self.assertIn("EXPORTS", files["exports.def"])

    def test_build_script_architecture(self):
        files_x64 = self.generator.generate_proxy_dll("test.dll", architecture="x64")
        self.assertIn("MACHINE:X64", files_x64["build.bat"])

        files_x86 = self.generator.generate_proxy_dll("test.dll", architecture="x86")
        self.assertIn("MACHINE:X86", files_x86["build.bat"])

    def test_generate_forward_chain(self):
        chain = self.generator.generate_forward_chain(["dll1.dll", "dll2.dll"])
        self.assertIn("chain_info", chain)
        self.assertIn("instructions", chain)
        self.assertEqual(chain["chain_info"]["dlls"], ["dll1.dll", "dll2.dll"])

    def test_readme_content(self):
        files = self.generator.generate_proxy_dll("test.dll")
        self.assertIn("test.dll", files["README.txt"])
        self.assertIn("代理 DLL", files["README.txt"])

    def test_indent_empty(self):
        result = self.generator._indent("", "    ")
        self.assertIn("默认", result)

    def test_indent_with_text(self):
        result = self.generator._indent("line1\nline2", ">> ")
        self.assertIn(">> line1", result)
        self.assertIn(">> line2", result)


# ============================================================
# SecurityAnalyzer 测试
# ============================================================

class TestSecurityAnalyzer(unittest.TestCase):
    """安全分析器测试"""

    def setUp(self):
        self.analyzer = SecurityAnalyzer()

    def test_analyze_security(self):
        report = self.analyzer.analyze_security("test_game.exe")
        self.assertIsInstance(report, SecurityReport)
        self.assertGreaterEqual(report.risk_score, 0)
        self.assertLessEqual(report.risk_score, 100)

    def test_analyze_security_with_anti_cheat(self):
        report = self.analyzer.analyze_security("game_with_easyanticheat.exe")
        self.assertGreater(report.risk_score, 0)

    def test_analyze_security_cached(self):
        report1 = self.analyzer.analyze_security("test_game.exe")
        report2 = self.analyzer.analyze_security("test_game.exe")
        self.assertEqual(report1.risk_score, report2.risk_score)

    def test_bypass_suggestions(self):
        report = self.analyzer.analyze_security("game_with_easyanticheat.exe")
        self.assertGreater(len(report.bypass_suggestions), 0)
        for suggestion in report.bypass_suggestions:
            self.assertIn("target", suggestion)
            self.assertIn("methods", suggestion)

    def test_scan_anti_tamper_vmprotect(self):
        data = b"\x00" * 100 + b"VMProtect" + b"\x00" * 100
        findings = self.analyzer.scan_for_anti_tamper(data)
        self.assertGreater(len(findings), 0)
        self.assertTrue(any("VMProtect" in f["name"] for f in findings))

    def test_scan_anti_tamper_themida(self):
        data = b"\x00" * 100 + b"Themida" + b"\x00" * 100
        findings = self.analyzer.scan_for_anti_tamper(data)
        self.assertGreater(len(findings), 0)

    def test_scan_anti_tamper_clean(self):
        data = b"\x00" * 1000
        findings = self.analyzer.scan_for_anti_tamper(data)
        self.assertEqual(len(findings), 0)

    def test_scan_anti_tamper_denuvo(self):
        data = b"\x00" * 100 + b"Denuvo" + b"\x00" * 100
        findings = self.analyzer.scan_for_anti_tamper(data)
        self.assertGreater(len(findings), 0)

    def test_calculate_risk_score(self):
        measures = [
            {"type": "anti_debug", "severity": "high"},
            {"type": "integrity_check", "severity": "high"},
        ]
        score = self.analyzer._calculate_risk_score(measures)
        self.assertEqual(score, 80)

    def test_calculate_risk_score_empty(self):
        score = self.analyzer._calculate_risk_score([])
        self.assertEqual(score, 0)

    def test_overall_assessment(self):
        report = self.analyzer.analyze_security("game_with_vanguard.exe")
        self.assertIsNotNone(report.overall_assessment)
        self.assertGreater(len(report.overall_assessment), 0)


# ============================================================
# CodeInjectEngine 测试
# ============================================================

class TestCodeInjectEngine(unittest.TestCase):
    """代码注入引擎测试"""

    def setUp(self):
        self.engine = CodeInjectEngine()
        self.test_data = _make_test_exe_data()

    def test_analyze_process(self):
        result = self.engine.analyze_process("test_game.exe")
        self.assertTrue(result["success"])
        self.assertIn("modules", result)
        self.assertIn("security_measures", result)

    def test_enumerate_modules(self):
        result = self.engine.enumerate_modules("test_game.exe")
        self.assertTrue(result["success"])
        self.assertGreater(len(result["modules"]), 0)

    def test_plan_injection(self):
        result = self.engine.plan_injection("test_game.exe", "test.dll")
        self.assertTrue(result["success"])
        self.assertIn("recommended", result)
        self.assertIn("method", result["recommended"])

    def test_plan_injection_stealth(self):
        result = self.engine.plan_injection("test_game.exe", prefer_stealth=True)
        self.assertTrue(result["success"])

    def test_find_code_caves(self):
        result = self.engine.find_code_caves(self.test_data)
        self.assertTrue(result["success"])
        self.assertGreater(result["total_caves"], 0)

    def test_find_code_caves_with_min_size(self):
        result = self.engine.find_code_caves(self.test_data, required_size=64)
        self.assertTrue(result["success"])
        for cave in result["caves"]:
            self.assertGreaterEqual(cave["size"], 64)

    def test_find_best_cave(self):
        result = self.engine.find_best_cave(self.test_data, 64)
        self.assertTrue(result["success"])
        self.assertTrue(result["found"])

    def test_find_best_cave_not_found(self):
        result = self.engine.find_best_cave(self.test_data, 10000)
        self.assertTrue(result["success"])
        self.assertFalse(result["found"])

    def test_generate_inline_hook(self):
        result = self.engine.generate_inline_hook(0x1000, 0x2000, b"\x48\x89\x5C\x24\x08")
        self.assertTrue(result["success"])
        self.assertEqual(result["hook_type"], "inline")
        self.assertIn("hook_code", result)

    def test_generate_iat_hook(self):
        result = self.engine.generate_iat_hook("kernel32.dll", "Sleep", 0x2000)
        self.assertTrue(result["success"])
        self.assertEqual(result["hook_type"], "iat")
        self.assertEqual(result["target_module"], "kernel32.dll")

    def test_generate_nop_patch(self):
        result = self.engine.generate_nop_patch(0x1000, 5)
        self.assertTrue(result["success"])
        self.assertEqual(result["size"], 5)

    def test_analyze_dll(self):
        result = self.engine.analyze_dll("version.dll")
        self.assertTrue(result["success"])
        self.assertIn("hijack_methods", result)

    def test_find_hijack_opportunities(self):
        result = self.engine.find_hijack_opportunities("san7.exe")
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["opportunity_count"], 0)

    def test_generate_proxy_dll(self):
        result = self.engine.generate_proxy_dll("version.dll")
        self.assertTrue(result["success"])
        self.assertIn("files", result)
        self.assertGreater(len(result["files"]), 0)

    def test_analyze_security(self):
        result = self.engine.analyze_security("test_game.exe")
        self.assertTrue(result["success"])
        self.assertIn("risk_score", result)
        self.assertIn("bypass_suggestions", result)

    def test_scan_anti_tamper(self):
        data = b"\x00" * 100 + b"VMProtect" + b"\x00" * 100
        result = self.engine.scan_anti_tamper(data)
        self.assertTrue(result["success"])
        self.assertTrue(result["has_packer"])

    def test_comprehensive_analysis(self):
        result = self.engine.comprehensive_analysis("test_game.exe", self.test_data)
        self.assertTrue(result["success"])
        self.assertIn("security", result)
        self.assertIn("injection", result)
        self.assertIn("dll_hijack", result)
        self.assertIn("code_caves", result)

    def test_comprehensive_analysis_bypass(self):
        result = self.engine.comprehensive_analysis("game_with_easyanticheat.exe", self.test_data)
        self.assertTrue(result["success"])
        self.assertIn("bypass_suggestions", result)


# ============================================================
# 快捷函数测试
# ============================================================

class TestQuickFunctions(unittest.TestCase):
    """快捷函数测试"""

    def test_quick_analyze(self):
        result = quick_analyze("test_game.exe")
        self.assertTrue(result["success"])
        self.assertIn("security", result)

    def test_quick_inject_plan(self):
        result = quick_inject_plan("test_game.exe", "test.dll")
        self.assertTrue(result["success"])
        self.assertIn("recommended", result)

    def test_quick_find_caves(self):
        data = _make_test_exe_data()
        result = quick_find_caves(data, min_size=32)
        self.assertTrue(result["success"])
        self.assertGreater(result["total_caves"], 0)

    def test_quick_hook_plan(self):
        result = quick_hook_plan("Sleep", "kernel32.dll")
        self.assertTrue(result["success"])


# ============================================================
# 数据类测试
# ============================================================

class TestDataClasses(unittest.TestCase):
    """数据类测试"""

    def test_process_info(self):
        info = ProcessInfo(pid=1234, name="test.exe", path="C:\\test.exe")
        self.assertEqual(info.pid, 1234)
        self.assertEqual(info.name, "test.exe")
        self.assertTrue(info.is_64bit)

    def test_module_info(self):
        mod = ModuleInfo(name="kernel32.dll", base_address=0x7FFE0000, size=0x100000)
        self.assertEqual(mod.name, "kernel32.dll")
        self.assertEqual(mod.base_address, 0x7FFE0000)

    def test_export_info(self):
        exp = ExportInfo(name="LoadLibraryA", ordinal=1, rva=0x1000)
        self.assertEqual(exp.name, "LoadLibraryA")
        self.assertFalse(exp.forwarded)

    def test_import_info(self):
        imp = ImportInfo(name="CreateFileA", module_name="kernel32.dll", iat_rva=0x2000)
        self.assertEqual(imp.name, "CreateFileA")
        self.assertEqual(imp.module_name, "kernel32.dll")

    def test_section_info(self):
        sec = SectionInfo(name=".text", virtual_address=0x1000, is_executable=True)
        self.assertEqual(sec.name, ".text")
        self.assertTrue(sec.is_executable)

    def test_code_cave(self):
        cave = CodeCave(address=0x200, size=256, section=".text", near_function="main")
        self.assertEqual(cave.address, 0x200)
        self.assertEqual(cave.size, 256)

    def test_hook_template(self):
        hook = HookTemplate(
            hook_type=HookType.INLINE,
            target_function="Sleep",
            target_module="kernel32.dll",
            hook_code=b"\xE9\x00\x00\x00\x00",
            hook_size=5,
        )
        self.assertEqual(hook.hook_type, HookType.INLINE)
        self.assertEqual(hook.hook_size, 5)

    def test_injection_plan(self):
        plan = InjectionPlan(
            method=InjectionMethod.CREATE_REMOTE_THREAD,
            target_process="test.exe",
            dll_path="test.dll",
            risk_level=30,
            stealth_level=20,
        )
        self.assertEqual(plan.method, InjectionMethod.CREATE_REMOTE_THREAD)
        self.assertEqual(plan.risk_level, 30)

    def test_dll_hijack_opportunity(self):
        opp = DllHijackOpportunity(
            dll_name="version.dll",
            method=DllHijackMethod.SEARCH_ORDER,
            priority=80,
        )
        self.assertEqual(opp.dll_name, "version.dll")
        self.assertEqual(opp.priority, 80)

    def test_security_report(self):
        report = SecurityReport(risk_score=75, overall_assessment="Medium risk")
        self.assertEqual(report.risk_score, 75)
        self.assertEqual(report.overall_assessment, "Medium risk")


# ============================================================
# 边界条件测试
# ============================================================

class TestEdgeCases(unittest.TestCase):
    """边界条件测试"""

    def test_empty_data_code_caves(self):
        engine = CodeInjectEngine()
        result = engine.find_code_caves(b"")
        self.assertTrue(result["success"])
        self.assertEqual(result["total_caves"], 0)

    def test_small_data_best_cave(self):
        engine = CodeInjectEngine()
        result = engine.find_best_cave(b"\x01\x02\x03", 16)
        self.assertTrue(result["success"])
        self.assertFalse(result["found"])

    def test_empty_payload_proxy_dll(self):
        engine = CodeInjectEngine()
        result = engine.generate_proxy_dll("version.dll", "")
        self.assertTrue(result["success"])

    def test_unknown_dll_analysis(self):
        engine = CodeInjectEngine()
        result = engine.analyze_dll("completely_unknown.dll")
        self.assertTrue(result["success"])

    def test_zero_size_nop(self):
        engine = CodeInjectEngine()
        result = engine.generate_nop_patch(0x1000, 0)
        self.assertTrue(result["success"])
        self.assertEqual(result["size"], 0)

    def test_large_data_caves(self):
        data = b"\x00" * 0x10000
        engine = CodeInjectEngine()
        result = engine.find_code_caves(data)
        self.assertTrue(result["success"])
        self.assertGreater(result["total_caves"], 0)


if __name__ == "__main__":
    unittest.main()