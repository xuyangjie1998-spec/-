"""
反调试与反反调试引擎测试套件
测试 anti_debug.py 的所有核心功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import tempfile
from core.anti_debug import (
    AntiDebugEngine, AntiDebugDetector, BypassGenerator, IntegrityChecker,
    AntiDebugCategory, SeverityLevel, BypassStrategy,
    AntiDebugSignature, DetectionResult, IntegrityCheck,
    ANTI_DEBUG_SIGNATURES, quick_scan, quick_bypass, detect_single
)


class TestAntiDebugDetector(unittest.TestCase):
    """反调试检测器测试"""

    def setUp(self):
        self.detector = AntiDebugDetector()

    def test_load_data(self):
        self.detector.load_data(b"\x64\xA1\x30\x00\x00\x00")
        self.assertEqual(len(self.detector._data), 6)

    def test_load_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(b"\x64\xA1\x30\x00\x00\x00")
            tmp = f.name
        try:
            result = self.detector.load_file(tmp)
            self.assertTrue(result["success"])
        finally:
            os.unlink(tmp)

    def test_load_nonexistent(self):
        result = self.detector.load_file("/nonexistent/file.bin")
        self.assertFalse(result["success"])

    def test_scan_peb_being_debugged(self):
        data = b"\x64\xA1\x30\x00\x00\x00"  # mov eax, fs:[0x30]
        data += b"IsDebuggerPresent\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("PEB.BeingDebugged")
        self.assertIsNotNone(result)
        self.assertTrue(result.detected)
        self.assertGreater(result.confidence, 0)

    def test_scan_peb_nt_global_flag(self):
        data = b"\x64\xA1\x30\x00\x00\x00"  # mov eax, fs:[0x30]
        data += b"NtGlobalFlag\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("PEB.NtGlobalFlag")
        self.assertIsNotNone(result)

    def test_scan_process_debug_port(self):
        data = b"\x07\x00\x00\x00"  # ProcessDebugPort = 7
        data += b"NtQueryInformationProcess\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("ProcessDebugPort")
        self.assertIsNotNone(result)
        self.assertTrue(result.detected)

    def test_scan_debug_object_handle(self):
        data = b"\x1E\x00\x00\x00"  # ProcessDebugObjectHandle = 30
        data += b"NtQueryInformationProcess\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("ProcessDebugObjectHandle")
        self.assertIsNotNone(result)

    def test_scan_hardware_breakpoint(self):
        data = b"GetThreadContext\x00"
        data += b"DR0\x00DR7\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("HardwareBreakpointDetection")
        self.assertIsNotNone(result)
        self.assertTrue(result.detected)

    def test_scan_software_breakpoint(self):
        data = b"\xCC" * 10  # INT 3
        data += b"breakpoint\x00scan\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("SoftwareBreakpointDetection")
        self.assertIsNotNone(result)

    def test_scan_int2d(self):
        data = b"\xCD\x2D"  # INT 2D
        self.detector.load_data(data)
        result = self.detector.scan_by_name("INT2DDetection")
        self.assertIsNotNone(result)
        self.assertTrue(result.detected)

    def test_scan_int3_anti_debug(self):
        data = b"\xCD\x03"  # INT 3
        data += b"SetUnhandledExceptionFilter\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("INT3AntiDebug")
        self.assertIsNotNone(result)

    def test_scan_rdtsc(self):
        data = b"\x0F\x31"  # rdtsc
        data += b"rdtsc\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("RDTSCDetection")
        self.assertIsNotNone(result)
        self.assertTrue(result.detected)

    def test_scan_get_tick_count(self):
        data = b"GetTickCount\x00QueryPerformanceCounter\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("GetTickCountDetection")
        self.assertIsNotNone(result)
        self.assertTrue(result.detected)

    def test_scan_close_handle(self):
        data = b"CloseHandle\x00INVALID_HANDLE\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("CloseHandleException")
        self.assertIsNotNone(result)

    def test_scan_parent_process(self):
        data = b"CreateToolhelp32Snapshot\x00"
        data += b"Process32First\x00explorer.exe\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("ParentProcessCheck")
        self.assertIsNotNone(result)
        self.assertTrue(result.detected)

    def test_scan_memory_breakpoint(self):
        data = b"VirtualQuery\x00PAGE_GUARD\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("MemoryBreakpointDetection")
        self.assertIsNotNone(result)

    def test_scan_code_section_crc(self):
        data = b"crc32\x00checksum\x00code\x00integrity\x00check\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("CodeSectionCRC")
        self.assertIsNotNone(result)
        self.assertTrue(result.detected)

    def test_scan_find_window(self):
        data = b"FindWindow\x00WinDbg\x00OllyDbg\x00x64dbg\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("FindWindowDebugger")
        self.assertIsNotNone(result)
        self.assertTrue(result.detected)

    def test_scan_registry(self):
        data = b"AeDebug\x00Debugger\x00path\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("RegistryDebuggerCheck")
        self.assertIsNotNone(result)

    def test_scan_self_debugging(self):
        data = b"DebugActiveProcess\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("SelfDebugging")
        self.assertIsNotNone(result)

    def test_scan_output_debug_string(self):
        data = b"OutputDebugString\x00GetLastError\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("OutputDebugStringExploit")
        self.assertIsNotNone(result)

    def test_scan_all_empty(self):
        self.detector.load_data(b"")
        results = self.detector.scan_all()
        self.assertEqual(len(results), 0)

    def test_scan_all_comprehensive(self):
        data = (
            b"\x64\xA1\x30\x00\x00\x00"  # PEB
            b"\x0F\x31"  # rdtsc
            b"\xCD\x2D"  # INT 2D
            b"\xCC\xCC\xCC"  # INT 3
            b"IsDebuggerPresent\x00"
            b"NtQueryInformationProcess\x00"
            b"GetThreadContext\x00"
            b"VirtualQuery\x00"
            b"FindWindow\x00"
            b"crc32\x00checksum\x00"
        )
        self.detector.load_data(data)
        results = self.detector.scan_all()
        self.assertGreater(len(results), 0)

    def test_scan_category_process_info(self):
        data = b"\x64\xA1\x30\x00\x00\x00" + b"IsDebuggerPresent\x00"
        self.detector.load_data(data)
        results = self.detector.scan_category(AntiDebugCategory.PROCESS_INFO)
        self.assertGreater(len(results), 0)

    def test_get_summary(self):
        data = b"\x64\xA1\x30\x00\x00\x00" + b"IsDebuggerPresent\x00"
        self.detector.load_data(data)
        self.detector.scan_all()
        summary = self.detector.get_summary()
        self.assertIn("total", summary)
        self.assertIn("detected", summary)
        self.assertIn("risk_score", summary)

    def test_summary_empty(self):
        self.detector.load_data(b"")
        summary = self.detector.get_summary()
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["risk_score"], 0)

    def test_scan_unknown_technique(self):
        self.detector.load_data(b"abc")
        result = self.detector.scan_by_name("NonExistent")
        self.assertIsNone(result)

    def test_scan_block_input(self):
        data = b"BlockInput\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("BlockInputDetection")
        self.assertIsNotNone(result)

    def test_scan_anti_tamper(self):
        data = b"VirtualProtect\x00PAGE_EXECUTE_READWRITE\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("AntiTamperCheck")
        self.assertIsNotNone(result)

    def test_scan_raise_exception(self):
        data = b"RaiseException\x00\x6A\x00"
        self.detector.load_data(data)
        result = self.detector.scan_by_name("RaiseExceptionDetection")
        self.assertIsNotNone(result)


class TestBypassGenerator(unittest.TestCase):
    """绕过策略生成器测试"""

    def setUp(self):
        self.generator = BypassGenerator()

    def test_generate_bypass_plan_empty(self):
        data = b"\x00" * 100
        plan = self.generator.generate_bypass_plan(data)
        self.assertTrue(plan["success"])
        self.assertEqual(plan["risk_score"], 0)

    def test_generate_bypass_plan(self):
        data = b"\x64\xA1\x30\x00\x00\x00" + b"IsDebuggerPresent\x00"
        plan = self.generator.generate_bypass_plan(data)
        self.assertTrue(plan["success"])
        self.assertGreater(plan["total_detected"], 0)

    def test_generate_patch_code(self):
        result = self.generator.generate_patch_code("PEB.BeingDebugged")
        self.assertTrue(result["success"])
        self.assertIn("bypass_code", result)
        self.assertIn("bypass_strategies", result)

    def test_generate_patch_code_unknown(self):
        result = self.generator.generate_patch_code("NonExistent")
        self.assertFalse(result["success"])

    def test_generate_hook_script(self):
        from core.anti_debug import DetectionResult
        sig = ANTI_DEBUG_SIGNATURES[0]
        result = DetectionResult(
            signature=sig, detected=True, confidence=0.8,
            evidence="test", bypass_suggestion="test"
        )
        script = self.generator.generate_hook_script([result])
        self.assertIn("MinHook", script)
        self.assertIn("InstallAntiAntiDebug", script)


class TestIntegrityChecker(unittest.TestCase):
    """完整性校验分析器测试"""

    def setUp(self):
        self.checker = IntegrityChecker()

    def test_scan_empty(self):
        self.checker.load_data(b"")
        checks = self.checker.scan_integrity_checks()
        self.assertEqual(len(checks), 0)

    def test_detect_crc32(self):
        data = b"\x00" * 100
        data += self.checker.CRC32_TABLE_PATTERN
        data += b"\x00" * 100
        self.checker.load_data(data)
        checks = self.checker.scan_integrity_checks()
        # Should find CRC32 table
        crc_checks = [c for c in checks if c.check_type == "crc32"]
        self.assertGreater(len(crc_checks), 0)

    def test_detect_md5(self):
        data = b"\x00" * 100
        data += bytes([0x01, 0x23, 0x45, 0x67])  # MD5 A init
        data += b"\x00" * 100
        self.checker.load_data(data)
        checks = self.checker.scan_integrity_checks()
        md5_checks = [c for c in checks if c.check_type == "md5"]
        self.assertGreater(len(md5_checks), 0)

    def test_detect_sha256(self):
        data = b"\x00" * 100
        data += bytes([0x6A, 0x09, 0xE6, 0x67, 0xBB, 0x67, 0xAE, 0x85])
        data += b"\x00" * 100
        self.checker.load_data(data)
        checks = self.checker.scan_integrity_checks()
        sha_checks = [c for c in checks if c.check_type == "sha256"]
        self.assertGreater(len(sha_checks), 0)

    def test_detect_smc(self):
        data = b"VirtualProtect\x00"
        data += bytes([0x40, 0x00, 0x00, 0x00])  # PAGE_EXECUTE_READWRITE
        self.checker.load_data(data)
        checks = self.checker.scan_integrity_checks()
        smc_checks = [c for c in checks if c.check_type == "smc"]
        self.assertGreater(len(smc_checks), 0)

    def test_verify_integrity(self):
        import zlib
        data = b"test data for integrity check"
        crc = format(zlib.crc32(data) & 0xFFFFFFFF, "08x")
        self.checker.load_data(data)
        check = IntegrityCheck(
            name="test", check_type="crc32",
            target_range=(0, len(data)),
            expected_value=crc,
        )
        results = self.checker.verify_integrity([check])
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].is_patched)
        self.assertEqual(results[0].expected_value, results[0].actual_value)


class TestAntiDebugEngine(unittest.TestCase):
    """反调试引擎主入口测试"""

    def setUp(self):
        self.engine = AntiDebugEngine()

    def _create_test_file(self, data: bytes) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(data)
            return f.name

    def test_analyze(self):
        data = (
            b"\x64\xA1\x30\x00\x00\x00"  # PEB
            b"\x0F\x31"  # rdtsc
            b"\xCD\x2D"  # INT 2D
            b"IsDebuggerPresent\x00"
            b"NtQueryInformationProcess\x00"
        )
        path = self._create_test_file(data)
        try:
            result = self.engine.analyze(path)
            self.assertTrue(result["success"])
            self.assertIn("risk_score", result)
            self.assertIn("detected", result)
            self.assertIn("integrity_checks", result)
            self.assertIn("bypass_plan", result)
        finally:
            os.unlink(path)

    def test_analyze_nonexistent(self):
        result = self.engine.analyze("/nonexistent/file.bin")
        self.assertFalse(result["success"])

    def test_scan_anti_debug(self):
        data = b"\x64\xA1\x30\x00\x00\x00" + b"IsDebuggerPresent\x00"
        path = self._create_test_file(data)
        try:
            result = self.engine.scan_anti_debug(path)
            self.assertTrue(result["success"])
            self.assertIn("results", result)
            self.assertIn("summary", result)
        finally:
            os.unlink(path)

    def test_scan_anti_debug_by_category(self):
        data = b"\x64\xA1\x30\x00\x00\x00" + b"IsDebuggerPresent\x00"
        path = self._create_test_file(data)
        try:
            result = self.engine.scan_anti_debug(path, "process_info")
            self.assertTrue(result["success"])
        finally:
            os.unlink(path)

    def test_scan_anti_debug_invalid_category(self):
        data = b"\x00"
        path = self._create_test_file(data)
        try:
            result = self.engine.scan_anti_debug(path, "invalid_category")
            self.assertFalse(result["success"])
        finally:
            os.unlink(path)

    def test_scan_integrity(self):
        data = b"\x00" * 100 + b"checksum\x00" + b"\x00" * 100
        path = self._create_test_file(data)
        try:
            result = self.engine.scan_integrity(path)
            self.assertTrue(result["success"])
            self.assertIn("total_checks", result)
        finally:
            os.unlink(path)

    def test_generate_bypass(self):
        data = b"\x64\xA1\x30\x00\x00\x00" + b"IsDebuggerPresent\x00"
        path = self._create_test_file(data)
        try:
            result = self.engine.generate_bypass(path)
            self.assertTrue(result["success"])
        finally:
            os.unlink(path)

    def test_get_bypass_code(self):
        result = self.engine.get_bypass_code("PEB.BeingDebugged")
        self.assertTrue(result["success"])
        self.assertIn("bypass_code", result)

    def test_list_signatures(self):
        result = self.engine.list_signatures()
        self.assertTrue(result["success"])
        self.assertGreater(result["total"], 0)
        self.assertIn("signatures", result)
        self.assertIn("categories", result)

    def test_list_signatures_by_category(self):
        result = self.engine.list_signatures("process_info")
        self.assertTrue(result["success"])
        for sig in result["signatures"]:
            self.assertEqual(sig["category"], "process_info")

    def test_get_statistics(self):
        result = self.engine.get_statistics()
        self.assertTrue(result["total_signatures"] > 0)
        self.assertIn("by_category", result)
        self.assertIn("by_severity", result)
        self.assertIn("bypass_strategies", result)

    def test_quick_scan(self):
        data = b"\x64\xA1\x30\x00\x00\x00" + b"IsDebuggerPresent\x00"
        path = self._create_test_file(data)
        try:
            result = quick_scan(path)
            self.assertTrue(result["success"])
        finally:
            os.unlink(path)

    def test_quick_bypass(self):
        data = b"\x64\xA1\x30\x00\x00\x00" + b"IsDebuggerPresent\x00"
        path = self._create_test_file(data)
        try:
            result = quick_bypass(path)
            self.assertTrue(result["success"])
        finally:
            os.unlink(path)

    def test_detect_single(self):
        data = b"\x64\xA1\x30\x00\x00\x00" + b"IsDebuggerPresent\x00"
        path = self._create_test_file(data)
        try:
            result = detect_single(path, "PEB.BeingDebugged")
            self.assertTrue(result["success"])
            self.assertTrue(result["detected"])
        finally:
            os.unlink(path)

    def test_detect_single_not_found(self):
        data = b"\x00"
        path = self._create_test_file(data)
        try:
            result = detect_single(path, "NonExistent")
            self.assertFalse(result["success"])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)