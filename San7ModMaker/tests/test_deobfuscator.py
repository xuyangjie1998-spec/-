"""
代码混淆检测与反混淆引擎测试套件
测试 deobfuscator.py 的所有核心功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import struct
import tempfile
from core.deobfuscator import (
    DeobfuscatorEngine, ObfuscationDetector, EntropyAnalyzer,
    StringDecryptor, OpaquePredicateDetector, CFFDetector,
    ObfuscationType, ObfuscationLevel, DeobfuscationPhase,
    ObfuscationSignature, ObfuscationDetection, StringEncryption,
    OpaquePredicate, OBFUSCATION_SIGNATURES,
    quick_analyze, quick_decrypt_strings, quick_entropy
)


class TestEntropyAnalyzer(unittest.TestCase):
    """熵分析器测试"""

    def setUp(self):
        self.analyzer = EntropyAnalyzer()

    def test_calculate_entropy_empty(self):
        self.assertEqual(self.analyzer.calculate_entropy(b""), 0.0)

    def test_calculate_entropy_constant(self):
        # 所有字节相同，熵为 0
        self.assertEqual(self.analyzer.calculate_entropy(b"\x00" * 100), 0.0)

    def test_calculate_entropy_random(self):
        # 随机数据熵接近 8
        import random
        data = bytes(random.randint(0, 255) for _ in range(1000))
        entropy = self.analyzer.calculate_entropy(data)
        self.assertGreater(entropy, 5.0)

    def test_calculate_entropy_plain_text(self):
        data = b"Hello World! This is a test string with normal English text."
        entropy = self.analyzer.calculate_entropy(data)
        self.assertGreater(entropy, 3.0)
        self.assertLess(entropy, 6.0)

    def test_block_entropy(self):
        data = b"\x00" * 200 + b"\xFF" * 200
        entropies = self.analyzer.calculate_block_entropy(data, block_size=200)
        self.assertEqual(len(entropies), 2)
        self.assertAlmostEqual(entropies[0], 0.0, places=1)

    def test_entropy_variance(self):
        data = b"\x00" * 256 + bytes(range(256))
        variance = self.analyzer.calculate_entropy_variance(data, block_size=256)
        self.assertGreater(variance, 0)

    def test_high_entropy_regions(self):
        import random
        data = b"\x00" * 256 + bytes(random.randint(0, 255) for _ in range(300))
        regions = self.analyzer.detect_high_entropy_regions(data, threshold=6.0)
        self.assertGreater(len(regions), 0)


class TestStringDecryptor(unittest.TestCase):
    """字符串解密器测试"""

    def setUp(self):
        self.decryptor = StringDecryptor()

    def test_find_xor_strings_simple(self):
        # XOR key 0x00: "test" -> same bytes
        data = b"\x00" * 10 + b"test" + b"\x00"
        self.decryptor.load_data(data)
        strings = self.decryptor.find_xor_strings()
        self.assertGreater(len(strings), 0)

    def test_find_xor_strings_zero_key(self):
        # "hello" XOR 0x00 = "hello"
        data = b"hello world test"
        self.decryptor.load_data(data)
        strings = self.decryptor.find_xor_strings()
        self.assertGreater(len(strings), 0)

    def test_find_xor_strings_key_ff(self):
        # "AAAA" XOR 0xFF = b"\xBE\xBE\xBE\xBE"
        data = b"\x00\x00\x00" + bytes([0xBE, 0xBE, 0xBE, 0xBE]) + b"\x00\x00\x00"
        self.decryptor.load_data(data)
        strings = self.decryptor.find_xor_strings()
        self.assertGreater(len(strings), 0)

    def test_find_stack_strings(self):
        # C6 45 XX YY pattern: mov byte ptr [ebp-XX], YY
        # Need at least 4 chars for meaningful string detection
        data = bytes([0xC6, 0x45, 0xFC, ord("H")])
        data += bytes([0xC6, 0x45, 0xFD, ord("e")])
        data += bytes([0xC6, 0x45, 0xFE, ord("l")])
        data += bytes([0xC6, 0x45, 0xFF, ord("l")])
        data += bytes([0xC6, 0x45, 0x00, 0x00])
        self.decryptor.load_data(data)
        strings = self.decryptor.find_stack_strings()
        self.assertGreater(len(strings), 0)

    def test_find_rc4_strings(self):
        # S-Box
        data = bytes(range(256))
        self.decryptor.load_data(data)
        strings = self.decryptor.find_rc4_strings()
        self.assertGreater(len(strings), 0)

    def test_decrypt_all(self):
        data = b"test_string" + b"\x00" * 4
        data += bytes([0xC6, 0x45, 0xFC, ord("S")])
        data += bytes([0xC6, 0x45, 0xFD, ord("t")])
        data += bytes([0xC6, 0x45, 0xFE, 0x00])
        self.decryptor.load_data(data)
        strings = self.decryptor.decrypt_all()
        self.assertGreater(len(strings), 0)

    def test_is_meaningful_string_true(self):
        self.assertTrue(self.decryptor._is_meaningful_string("hello_world"))

    def test_is_meaningful_string_false(self):
        self.assertFalse(self.decryptor._is_meaningful_string("AAAA"))
        self.assertFalse(self.decryptor._is_meaningful_string("abc"))
        self.assertFalse(self.decryptor._is_meaningful_string("1234"))


class TestOpaquePredicateDetector(unittest.TestCase):
    """不透明谓词检测器测试"""

    def setUp(self):
        self.detector = OpaquePredicateDetector()

    def test_detect_cmp_eax_eax(self):
        # cmp eax, eax; jne ... (always false)
        data = bytes([0x39, 0xC0, 0x75, 0x10])  # cmp eax,eax; jne +0x10
        self.detector.load_data(data)
        predicates = self.detector.detect()
        self.assertGreater(len(predicates), 0)

    def test_detect_xor_eax_eax(self):
        # xor eax, eax; je ... (always true, since eax=0)
        data = bytes([0x31, 0xC0, 0x74, 0x10])  # xor eax,eax; je +0x10
        self.detector.load_data(data)
        predicates = self.detector.detect()
        self.assertGreater(len(predicates), 0)

    def test_detect_and_eax_0(self):
        # and eax, 0; jne ... (always false)
        data = bytes([0x83, 0xE0, 0x00, 0x75, 0x10])
        self.detector.load_data(data)
        predicates = self.detector.detect()
        self.assertGreater(len(predicates), 0)

    def test_detect_empty(self):
        self.detector.load_data(b"")
        predicates = self.detector.detect()
        self.assertEqual(len(predicates), 0)


class TestCFFDetector(unittest.TestCase):
    """控制流展平检测器测试"""

    def setUp(self):
        self.detector = CFFDetector()

    def test_detect_empty(self):
        self.detector.load_data(b"")
        result = self.detector.detect()
        self.assertFalse(result["detected"])

    def test_detect_state_variables(self):
        # 多个 mov [ebp-XX], imm32 指令
        data = b""
        for i in range(6):
            data += bytes([0xC7, 0x45, 0xF8]) + struct.pack("<I", i)
        self.detector.load_data(data)
        result = self.detector.detect()
        self.assertTrue(result["detected"])

    def test_detect_dispatcher(self):
        # cmp eax, imm8 + conditional jump patterns
        data = b""
        for i in range(5):
            data += bytes([0x83, 0xF8, i])  # cmp eax, i
            data += bytes([0x0F, 0x84, 0x00, 0x00, 0x00, 0x00])  # je
        self.detector.load_data(data)
        result = self.detector.detect()
        self.assertTrue(result["detected"])

    def test_detect_jump_table(self):
        data = bytes([0xFF, 0x24, 0x85, 0x00, 0x00, 0x00, 0x00])  # jmp [eax*4+disp]
        self.detector.load_data(data)
        result = self.detector.detect()
        # Should have some evidence at least
        self.assertIn("evidence", result)


class TestObfuscationDetector(unittest.TestCase):
    """混淆检测器测试"""

    def setUp(self):
        self.detector = ObfuscationDetector()

    def test_load_data(self):
        self.detector.load_data(b"\x00" * 100)
        self.assertEqual(len(self.detector._data), 100)

    def test_load_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(b"\x00" * 100)
            tmp = f.name
        try:
            result = self.detector.load_file(tmp)
            self.assertTrue(result["success"])
        finally:
            os.unlink(tmp)

    def test_scan_empty(self):
        self.detector.load_data(b"")
        results = self.detector.scan_all()
        self.assertEqual(len(results), 0)

    def test_scan_ollvm_cff(self):
        data = b"\x83\xF8" * 5  # cmp eax, imm8
        data += b"stateVar\x00switch\x00state\x00"
        self.detector.load_data(data)
        results = self.detector.scan_all()
        self.assertGreater(len(results), 0)

    def test_scan_upx_packing(self):
        data = b"UPX0\x00UPX1\x00UPX!\x00"
        self.detector.load_data(data)
        results = self.detector.scan_all()
        upx = [r for r in results if r.signature.name == "UPX_Packing"]
        self.assertGreater(len(upx), 0)
        self.assertTrue(upx[0].detected)

    def test_scan_aspack_packing(self):
        data = b".aspack\x00.adata\x00"
        self.detector.load_data(data)
        results = self.detector.scan_all()
        aspack = [r for r in results if r.signature.name == "ASPack_Packing"]
        self.assertGreater(len(aspack), 0)

    def test_scan_xor_string_encryption(self):
        data = b"\x34" * 10  # xor al, imm8
        data += b"decrypt\x00string\x00"
        self.detector.load_data(data)
        results = self.detector.scan_all()
        xor = [r for r in results if r.signature.name == "XORStringEncryption"]
        self.assertGreater(len(xor), 0)

    def test_scan_dynamic_import(self):
        data = b"GetProcAddress\x00LoadLibrary\x00"
        self.detector.load_data(data)
        results = self.detector.scan_all()
        dyn = [r for r in results if r.signature.name == "DynamicImportResolution"]
        self.assertGreater(len(dyn), 0)

    def test_scan_call_obfuscation(self):
        data = b"\x68" * 5 + b"\xC3" * 5  # push + ret
        self.detector.load_data(data)
        results = self.detector.scan_all()
        call = [r for r in results if r.signature.name == "CallObfuscation"]
        self.assertGreater(len(call), 0)

    def test_scan_jump_into_middle(self):
        data = bytes([0xEB, 0xFF, 0xE8, 0x00, 0x00, 0x00, 0x00])
        self.detector.load_data(data)
        results = self.detector.scan_all()
        jmp = [r for r in results if r.signature.name == "JumpIntoMiddle"]
        self.assertGreater(len(jmp), 0)

    def test_scan_disassembly_desync(self):
        data = bytes([0xEB, 0x01, 0x74, 0x01])
        self.detector.load_data(data)
        results = self.detector.scan_all()
        desync = [r for r in results if r.signature.name == "DisassemblyDesync"]
        self.assertGreater(len(desync), 0)

    def test_scan_junk_code(self):
        # add + sub pattern (cancels out)
        data = b"add\x00sub\x00"
        self.detector.load_data(data)
        results = self.detector.scan_all()
        junk = [r for r in results if r.signature.name == "JunkCodeInsertion"]
        self.assertGreater(len(junk), 0)

    def test_get_obfuscation_level_none(self):
        self.detector.load_data(b"\x00" * 100)
        self.detector.scan_all()
        self.assertEqual(self.detector.get_obfuscation_level(), ObfuscationLevel.NONE)

    def test_get_obfuscation_level_heavy(self):
        # Large amount of obfuscation features
        data = b"UPX0" + b"\x00" + b"UPX1" + b"\x00"
        data += b"GetProcAddress" + b"\x00" + b"LoadLibrary" + b"\x00"
        data += bytes([0x83, 0xF8]) * 5
        data += bytes([0x34]) * 10
        data += b"decrypt" + b"\x00" + b"string" + b"\x00"
        data += bytes([0x68]) * 5 + bytes([0xC3]) * 5
        data += bytes([0xEB, 0xFF]) * 3
        self.detector.load_data(data)
        self.detector.scan_all()
        level = self.detector.get_obfuscation_level()
        self.assertIn(level, [ObfuscationLevel.HEAVY, ObfuscationLevel.EXTREME])

    def test_get_complexity_score(self):
        self.detector.load_data(b"\x00" * 1000)
        self.detector.scan_all()
        score = self.detector.get_complexity_score()
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 1.0)


class TestDeobfuscatorEngine(unittest.TestCase):
    """反混淆引擎主入口测试"""

    def setUp(self):
        self.engine = DeobfuscatorEngine()

    def _create_file(self, data: bytes) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(data)
            return f.name

    def test_analyze(self):
        data = b"UPX0\x00" + b"\x00" * 100 + b"checksum\x00"
        path = self._create_file(data)
        try:
            result = self.engine.analyze(path)
            self.assertTrue(result["success"])
            self.assertIn("entropy", result)
            self.assertIn("obfuscation_level", result)
            self.assertIn("detected_types", result)
            self.assertIn("encrypted_strings", result)
            self.assertIn("opaque_predicates", result)
            self.assertIn("cff_analysis", result)
            self.assertIn("deobfuscation_plan", result)
        finally:
            os.unlink(path)

    def test_analyze_nonexistent(self):
        result = self.engine.analyze("/nonexistent/file.bin")
        self.assertFalse(result["success"])

    def test_scan_obfuscation(self):
        data = b"UPX0\x00UPX1\x00" + b"\x00" * 100
        path = self._create_file(data)
        try:
            result = self.engine.scan_obfuscation(path)
            self.assertTrue(result["success"])
            self.assertIn("obfuscation_level", result)
            self.assertIn("detected", result)
        finally:
            os.unlink(path)

    def test_decrypt_strings(self):
        data = b"hello_world_test" + b"\x00" * 10
        path = self._create_file(data)
        try:
            result = self.engine.decrypt_strings(path)
            self.assertTrue(result["success"])
            self.assertIn("total_strings", result)
        finally:
            os.unlink(path)

    def test_detect_opaque_predicates(self):
        data = bytes([0x39, 0xC0, 0x75, 0x10])  # cmp eax,eax; jne
        path = self._create_file(data)
        try:
            result = self.engine.detect_opaque_predicates(path)
            self.assertTrue(result["success"])
            self.assertIn("total", result)
        finally:
            os.unlink(path)

    def test_detect_cff(self):
        data = b""
        for i in range(5):
            data += bytes([0xC7, 0x45, 0xF8]) + struct.pack("<I", i)
        path = self._create_file(data)
        try:
            result = self.engine.detect_cff(path)
            self.assertTrue(result["success"])
        finally:
            os.unlink(path)

    def test_get_entropy_analysis(self):
        import random
        data = bytes(random.randint(0, 255) for _ in range(1000))
        path = self._create_file(data)
        try:
            result = self.engine.get_entropy_analysis(path)
            self.assertTrue(result["success"])
            self.assertIn("entropy", result)
            self.assertIn("assessment", result)
        finally:
            os.unlink(path)

    def test_get_statistics(self):
        stats = self.engine.get_statistics()
        self.assertGreater(stats["total_signatures"], 0)
        self.assertIn("by_type", stats)
        self.assertIn("obfuscation_types", stats)

    def test_quick_analyze(self):
        data = b"UPX0\x00" + b"\x00" * 100
        path = self._create_file(data)
        try:
            result = quick_analyze(path)
            self.assertTrue(result["success"])
        finally:
            os.unlink(path)

    def test_quick_decrypt_strings(self):
        data = b"test_data_here" + b"\x00" * 10
        path = self._create_file(data)
        try:
            result = quick_decrypt_strings(path)
            self.assertTrue(result["success"])
        finally:
            os.unlink(path)

    def test_quick_entropy(self):
        data = b"\x00" * 256 + bytes(range(256))
        path = self._create_file(data)
        try:
            result = quick_entropy(path)
            self.assertTrue(result["success"])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)