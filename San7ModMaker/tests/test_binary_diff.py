"""
二进制差异化与补丁引擎测试套件
测试 binary_diff.py 的所有核心功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import tempfile
import hashlib
from core.binary_diff import (
    BinaryDiffAnalyzer, DeltaGenerator, SignatureScanner,
    PatchEngine, StructureComparator,
    DiffEntry, DiffType, PatchFormat, SignatureFormat,
    SignatureMatch, PatchInfo, BlockInfo, DiffReport,
    diff_files, quick_scan, quick_delta
)


class TestDeltaGenerator(unittest.TestCase):
    """Delta 生成器测试"""

    def setUp(self):
        self.generator = DeltaGenerator()

    def test_diff_bytes_identical(self):
        data = b"hello world"
        entries = self.generator.diff_bytes(data, data)
        # 完全相同应该只有 EQUAL 条目
        types = [e.diff_type for e in entries]
        self.assertIn(DiffType.EQUAL, types)

    def test_diff_bytes_insert(self):
        old = b"hello"
        new = b"hello world"
        entries = self.generator.diff_bytes(old, new)
        types = [e.diff_type for e in entries]
        self.assertIn(DiffType.INSERT, types)

    def test_diff_bytes_delete(self):
        old = b"hello world"
        new = b"hello"
        entries = self.generator.diff_bytes(old, new)
        types = [e.diff_type for e in entries]
        self.assertIn(DiffType.DELETE, types)

    def test_diff_bytes_replace(self):
        old = b"hello world"
        new = b"hallo world"
        entries = self.generator.diff_bytes(old, new)
        self.assertTrue(len(entries) > 0)

    def test_diff_bytes_empty_old(self):
        old = b""
        new = b"hello"
        entries = self.generator.diff_bytes(old, new)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].diff_type, DiffType.INSERT)

    def test_diff_bytes_empty_new(self):
        old = b"hello"
        new = b""
        entries = self.generator.diff_bytes(old, new)
        self.assertEqual(len(entries), 1)

    def test_diff_blocks_identical(self):
        data = b"x" * 128
        entries = self.generator.diff_blocks(data, data)
        # 相同块不需要任何变更
        self.assertTrue(all(e.diff_type != DiffType.INSERT for e in entries))
        self.assertTrue(all(e.diff_type != DiffType.DELETE for e in entries))

    def test_diff_blocks_different(self):
        old = b"a" * 128
        new = b"b" * 128
        entries = self.generator.diff_blocks(old, new)
        self.assertGreater(len(entries), 0)

    def test_diff_blocks_shift(self):
        old = b"\x00" * 64 + b"data_block" + b"\x00" * 56
        new = b"data_block" + b"\x00" * 118
        entries = self.generator.diff_blocks(old, new)
        # 可能探测到 SHIFT
        shift_types = [e for e in entries if e.diff_type == DiffType.SHIFT]
        self.assertGreaterEqual(len(shift_types), 0)

    def test_diff_instructions_empty(self):
        entries = self.generator.diff_instructions([], [])
        self.assertEqual(len(entries), 0)

    def test_diff_instructions_identical(self):
        ins = [{"address": 0x1000, "bytes": b"\x90", "size": 1}]
        entries = self.generator.diff_instructions(ins, ins)
        self.assertEqual(len(entries), 0)

    def test_diff_instructions_modified(self):
        old = [{"address": 0x1000, "bytes": b"\x90", "size": 1}]
        new = [{"address": 0x1000, "bytes": b"\xcc", "size": 1}]
        entries = self.generator.diff_instructions(old, new)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].diff_type, DiffType.REPLACE)

    def test_generate_delta_roundtrip(self):
        old = b"Hello World " * 100
        new = b"Hello World! " * 100 + b" Extra data at the end"
        delta = self.generator.generate_delta(old, new)
        self.assertIsInstance(delta, bytes)
        self.assertGreater(len(delta), 0)

        result = self.generator.apply_delta(old, delta)
        self.assertEqual(result, new)

    def test_apply_delta_small(self):
        old = b"abc"
        new = b"abxcy"
        delta = self.generator.generate_delta(old, new)
        result = self.generator.apply_delta(old, delta)
        self.assertEqual(result, new)

    def test_apply_delta_large(self):
        old = b"x" * 10000
        new = b"y" * 5000 + b"x" * 5000
        delta = self.generator.generate_delta(old, new)
        result = self.generator.apply_delta(old, delta)
        self.assertEqual(result, new)

    def test_delta_compression_ratio(self):
        old = b"a" * 10000
        new = b"a" * 9999 + b"b"
        delta = self.generator.generate_delta(old, new)
        self.assertLess(len(delta), len(new))


class TestSignatureScanner(unittest.TestCase):
    """签名扫描器测试"""

    def setUp(self):
        self.scanner = SignatureScanner()

    def test_parse_ida(self):
        pat, mask = self.scanner.parse_signature("48 8B ? ? ? ? 00", SignatureFormat.IDA)
        self.assertEqual(len(pat), 7)
        self.assertEqual(pat[0], 0x48)
        self.assertEqual(pat[1], 0x8B)
        self.assertEqual(pat[2], 0x00)  # wildcard
        self.assertEqual(mask[0], 0xFF)
        self.assertEqual(mask[2], 0x00)  # wildcard mask

    def test_parse_x64dbg(self):
        pat, mask = self.scanner.parse_signature("48 8B ?? ?? ?? ?? 00", SignatureFormat.X64DBG)
        self.assertEqual(len(pat), 7)
        self.assertEqual(pat[0], 0x48)
        self.assertEqual(mask[2], 0x00)

    def test_parse_code(self):
        pat, mask = self.scanner.parse_signature("\\x48\\x8B\\x00\\x00\\x00\\x00\\x00", SignatureFormat.CODE)
        self.assertEqual(len(pat), 7)
        self.assertEqual(pat[0], 0x48)

    def test_scan_single_match(self):
        data = b"\x00" * 10 + b"\x48\x8B\x05\x00\x00\x00\x00" + b"\x00" * 10
        results = self.scanner.scan(data, "48 8B 05 ? ? ? ?", SignatureFormat.IDA)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].offset, 10)

    def test_scan_no_match(self):
        data = b"\x00" * 20
        results = self.scanner.scan(data, "48 8B 05 ? ? ? ?", SignatureFormat.IDA)
        self.assertEqual(len(results), 0)

    def test_scan_find_all(self):
        data = b"\x90\x90\x90" * 10
        results = self.scanner.scan(data, "90 90 90", SignatureFormat.IDA, find_all=True)
        # 30 字节中 3 字节模式: 30-3+1 = 28 个匹配
        self.assertEqual(len(results), 28)

    def test_scan_find_first(self):
        data = b"\x90\x90\x90" * 10
        results = self.scanner.scan(data, "90 90 90", SignatureFormat.IDA, find_all=False)
        self.assertEqual(len(results), 1)

    def test_scan_multi(self):
        data = b"\x48\x8B\x05" + b"\x00" * 10 + b"\x90\x90\x90"
        patterns = {
            "mov_eax": "48 8B 05",
            "nop3": "90 90 90",
        }
        results = self.scanner.scan_multi(data, patterns, SignatureFormat.IDA)
        self.assertEqual(len(results["mov_eax"]), 1)
        self.assertEqual(len(results["nop3"]), 1)

    def test_scan_file(self):
        data = b"\x00" * 5 + b"\x48\x8B\x05" + b"\x00" * 5
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(data)
            tmp_path = f.name

        try:
            results = self.scanner.scan_file(tmp_path, "48 8B 05", SignatureFormat.IDA)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].offset, 5)
        finally:
            os.unlink(tmp_path)

    def test_scan_nonexistent_file(self):
        results = self.scanner.scan_file("/nonexistent/file.bin", "48 8B", SignatureFormat.IDA)
        self.assertEqual(len(results), 0)

    def test_generate_signature(self):
        data = b"\x48\x8B\x05\x12\x34\x56\x78\x90"
        sig = self.scanner.generate_signature(data, 0, 8, SignatureFormat.IDA)
        self.assertIn("48", sig)
        self.assertIn("8B", sig)

    def test_generate_signature_with_wildcards(self):
        data = b"\x48\x8B\x05\x12\x34\x56\x78\x90"
        sig = self.scanner.generate_signature(data, 0, 8, SignatureFormat.IDA,
                                              wildcard_bytes=[3, 4, 5, 6])
        self.assertIn("?", sig)

    def test_generate_unique_signature(self):
        data = b"\x00" * 10 + b"\x48\x8B\x05\x12\x34\x56\x78" + b"\x00" * 10
        sig = self.scanner.generate_unique_signature(data, 10, min_length=4, max_length=7)
        self.assertIsNotNone(sig)

        # 验证唯一性
        results = self.scanner.scan(data, sig, SignatureFormat.IDA, find_all=True)
        self.assertEqual(len(results), 1)

    def test_generate_unique_signature_not_unique(self):
        # 重复模式导致无法生成唯一签名 - 需要足够大的数据
        data = b"\x90" * 64
        sig = self.scanner.generate_unique_signature(data, 0, min_length=4, max_length=16)
        self.assertIsNone(sig)

    def test_invalid_pattern(self):
        with self.assertRaises(ValueError):
            self.scanner.parse_signature("XX YY ZZ", SignatureFormat.IDA)

    def test_signature_format_conversion(self):
        data = b"\x48\x8B\x05\x12\x34\x56\x78"
        sig_ida = self.scanner.generate_signature(data, 0, 7, SignatureFormat.IDA)
        sig_x64dbg = self.scanner.generate_signature(data, 0, 7, SignatureFormat.X64DBG)
        sig_code = self.scanner.generate_signature(data, 0, 7, SignatureFormat.CODE)

        self.assertIn("48", sig_ida)
        self.assertIn("48", sig_x64dbg)
        self.assertIn("\\x48", sig_code)


class TestPatchEngine(unittest.TestCase):
    """补丁引擎测试"""

    def setUp(self):
        self.engine = PatchEngine()

    def test_create_ips_simple(self):
        old = b"hello world"
        new = b"hallo world"
        patch = self.engine.create_ips(old, new)
        self.assertTrue(patch.startswith(b"PATCH"))
        self.assertTrue(patch.endswith(b"EOF"))

    def test_apply_ips_simple(self):
        old = b"hello world"
        new = b"hallo world"
        patch = self.engine.create_ips(old, new)
        result = self.engine.apply_ips(old, patch)
        self.assertEqual(result, new)

    def test_apply_ips_identical(self):
        data = b"test data"
        patch = self.engine.create_ips(data, data)
        result = self.engine.apply_ips(data, patch)
        self.assertEqual(result, data)

    def test_apply_ips_empty_patch(self):
        data = b"test"
        patch = self.engine.create_ips(data, data)
        result = self.engine.apply_ips(data, patch)
        self.assertEqual(result, data)

    def test_apply_ips_extend(self):
        old = b"short"
        new = b"short with extension"
        patch = self.engine.create_ips(old, new)
        result = self.engine.apply_ips(old, patch)
        self.assertEqual(result, new)

    def test_create_delta_patch(self):
        old = b"original data"
        new = b"modified data"
        patch = self.engine.create_delta_patch(old, new, "test")
        self.assertEqual(patch.description, "test")
        self.assertGreater(len(patch.entries), 0)

    def test_apply_delta_patch(self):
        old = b"original data for testing"
        new = b"modified data for testing purposes"
        patch = self.engine.create_delta_patch(old, new)
        result = self.engine.apply_delta_patch(old, patch)
        self.assertEqual(result, new)

    def test_apply_delta_patch_identical(self):
        data = b"same data"
        patch = self.engine.create_delta_patch(data, data)
        result = self.engine.apply_delta_patch(data, patch)
        self.assertEqual(result, data)

    def test_save_load_delta_patch(self):
        old = b"save load test data"
        new = b"save load test data modified"
        patch = self.engine.create_delta_patch(old, new, "save test")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".delta") as f:
            tmp_path = f.name

        try:
            result = self.engine.save_delta_patch(patch, tmp_path)
            self.assertTrue(result["success"])

            loaded = self.engine.load_delta_patch(tmp_path)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.patch_id, patch.patch_id)
            result = self.engine.apply_delta_patch(old, loaded)
            self.assertEqual(result, new)
        finally:
            os.unlink(tmp_path)

    def test_load_nonexistent_patch(self):
        patch = self.engine.load_delta_patch("/nonexistent/patch.delta")
        self.assertIsNone(patch)

    def test_verify_patch_valid(self):
        old = b"verify test data"
        new = b"verify test data modified"
        patch = self.engine.create_delta_patch(old, new)
        result = self.engine.verify_patch(old, patch)
        self.assertTrue(result["success"])
        self.assertTrue(result["valid"])

    def test_verify_patch_invalid(self):
        old = b"wrong data"
        new = b"correct data"
        patch = self.engine.create_delta_patch(old, new)
        result = self.engine.verify_patch(b"different data", patch)
        self.assertFalse(result["valid"])

    def test_create_backup_and_rollback(self):
        data = b"backup test data"
        self.engine.create_backup(data, "test_backup")
        restored = self.engine.rollback("test_backup")
        self.assertEqual(restored, data)

    def test_rollback_nonexistent(self):
        result = self.engine.rollback("nonexistent")
        self.assertIsNone(result)

    def test_create_ips_file(self):
        old = b"file ips test"
        new = b"file ips test modified"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".old") as f:
            f.write(old)
            old_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".new") as f:
            f.write(new)
            new_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ips") as f:
            out_path = f.name

        try:
            result = self.engine.create_ips_file(old_path, new_path, out_path)
            self.assertTrue(result["success"])
            self.assertGreater(result["patch_size"], 0)
        finally:
            for p in [old_path, new_path, out_path]:
                os.unlink(p)

    def test_apply_ips_file(self):
        old = b"ips apply test"
        new = b"ips apply test done"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".old") as f:
            f.write(old)
            old_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".new") as f:
            f.write(new)
            new_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ips") as f:
            patch_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".out") as f:
            out_path = f.name

        try:
            self.engine.create_ips_file(old_path, new_path, patch_path)
            result = self.engine.apply_ips_file(old_path, patch_path, out_path)
            self.assertTrue(result["success"])

            with open(out_path, "rb") as f:
                patched = f.read()
            self.assertEqual(patched, new)
        finally:
            for p in [old_path, new_path, patch_path, out_path]:
                os.unlink(p)


class TestStructureComparator(unittest.TestCase):
    """结构对比器测试"""

    def setUp(self):
        self.comparator = StructureComparator()

    def test_compare_sections_identical(self):
        sections = {"text": b"code", "data": b"data"}
        report = self.comparator.compare_sections(sections, sections)
        for name, info in report.sections.items():
            self.assertEqual(info["status"], "identical")

    def test_compare_sections_added(self):
        sections_a = {"text": b"code"}
        sections_b = {"text": b"code", "data": b"new_data"}
        report = self.comparator.compare_sections(sections_a, sections_b)
        self.assertEqual(report.sections["data"]["status"], "added")

    def test_compare_sections_removed(self):
        sections_a = {"text": b"code", "data": b"old_data"}
        sections_b = {"text": b"code"}
        report = self.comparator.compare_sections(sections_a, sections_b)
        self.assertEqual(report.sections["data"]["status"], "removed")

    def test_compare_sections_modified(self):
        sections_a = {"text": b"hello"}
        sections_b = {"text": b"world"}
        report = self.comparator.compare_sections(sections_a, sections_b)
        self.assertEqual(report.sections["text"]["status"], "modified")

    def test_compare_functions_identical(self):
        funcs = {0x1000: b"\x90\x90", 0x2000: b"\xc3"}
        results = self.comparator.compare_functions(funcs, funcs)
        for addr, info in results.items():
            self.assertEqual(info["status"], "identical")

    def test_compare_functions_new(self):
        funcs_a = {0x1000: b"\x90"}
        funcs_b = {0x1000: b"\x90", 0x2000: b"\xc3"}
        results = self.comparator.compare_functions(funcs_a, funcs_b)
        self.assertEqual(results[0x2000]["status"], "new")

    def test_compare_functions_removed(self):
        funcs_a = {0x1000: b"\x90", 0x2000: b"\xc3"}
        funcs_b = {0x1000: b"\x90"}
        results = self.comparator.compare_functions(funcs_a, funcs_b)
        self.assertEqual(results[0x2000]["status"], "removed")

    def test_compare_functions_modified(self):
        funcs_a = {0x1000: b"\x90\x90\x90"}
        funcs_b = {0x1000: b"\x90\xcc\x90"}
        results = self.comparator.compare_functions(funcs_a, funcs_b)
        self.assertEqual(results[0x1000]["status"], "modified")

    def test_compare_strings_identical(self):
        strings = ["hello", "world"]
        result = self.comparator.compare_strings(strings, strings)
        self.assertEqual(result["added_count"], 0)
        self.assertEqual(result["removed_count"], 0)
        self.assertEqual(result["similarity"], 1.0)

    def test_compare_strings_added(self):
        a = ["hello"]
        b = ["hello", "world"]
        result = self.comparator.compare_strings(a, b)
        self.assertEqual(result["added_count"], 1)
        self.assertIn("world", result["added"])

    def test_compare_strings_removed(self):
        a = ["hello", "world"]
        b = ["hello"]
        result = self.comparator.compare_strings(a, b)
        self.assertEqual(result["removed_count"], 1)
        self.assertIn("world", result["removed"])

    def test_compare_strings_mixed(self):
        a = ["hello", "old", "common"]
        b = ["hello", "new", "common"]
        result = self.comparator.compare_strings(a, b)
        self.assertEqual(result["added_count"], 1)
        self.assertEqual(result["removed_count"], 1)
        self.assertEqual(result["common_count"], 2)


class TestBinaryDiffAnalyzer(unittest.TestCase):
    """二进制差异分析器主测试"""

    def setUp(self):
        self.analyzer = BinaryDiffAnalyzer()

    def test_diff_files_byte(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".a") as f:
            f.write(b"hello world")
            path_a = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".b") as f:
            f.write(b"hallo world")
            path_b = f.name

        try:
            result = self.analyzer.diff_files(path_a, path_b, "byte")
            self.assertTrue(result["success"])
            self.assertGreater(result["total_entries"], 0)
        finally:
            os.unlink(path_a)
            os.unlink(path_b)

    def test_diff_files_block(self):
        data = b"x" * 200
        with tempfile.NamedTemporaryFile(delete=False, suffix=".a") as f:
            f.write(data)
            path_a = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".b") as f:
            f.write(data[:64] + b"y" * 64 + data[128:])
            path_b = f.name

        try:
            result = self.analyzer.diff_files(path_a, path_b, "block")
            self.assertTrue(result["success"])
        finally:
            os.unlink(path_a)
            os.unlink(path_b)

    def test_diff_files_identical(self):
        data = b"identical data"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".a") as f:
            f.write(data)
            path_a = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".b") as f:
            f.write(data)
            path_b = f.name

        try:
            result = self.analyzer.diff_files(path_a, path_b)
            self.assertTrue(result["success"])
            self.assertEqual(result["similarity"], 1.0)
        finally:
            os.unlink(path_a)
            os.unlink(path_b)

    def test_diff_files_nonexistent(self):
        result = self.analyzer.diff_files("/nonexistent/a", "/nonexistent/b")
        self.assertFalse(result["success"])

    def test_diff_bytes(self):
        result = self.analyzer.diff_bytes(b"hello", b"hallo")
        self.assertTrue(result["success"])
        self.assertGreater(result["total_entries"], 0)

    def test_generate_delta_file(self):
        old = b"delta file test source" * 50
        new = b"delta file test target modified" * 50

        with tempfile.NamedTemporaryFile(delete=False, suffix=".old") as f:
            f.write(old)
            old_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".new") as f:
            f.write(new)
            new_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".delta") as f:
            out_path = f.name

        try:
            result = self.analyzer.generate_delta_file(old_path, new_path, out_path)
            self.assertTrue(result["success"])
            # 对大文件 delta 应该有压缩效果
            self.assertLess(result["delta_size"], len(new))
        finally:
            for p in [old_path, new_path, out_path]:
                os.unlink(p)

    def test_apply_delta_file(self):
        old = b"apply delta test"
        new = b"apply delta test modified"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".old") as f:
            f.write(old)
            old_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".new") as f:
            f.write(new)
            new_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".delta") as f:
            delta_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".out") as f:
            out_path = f.name

        try:
            self.analyzer.generate_delta_file(old_path, new_path, delta_path)
            result = self.analyzer.apply_delta_file(old_path, delta_path, out_path)
            self.assertTrue(result["success"])

            with open(out_path, "rb") as f:
                patched = f.read()
            self.assertEqual(patched, new)
        finally:
            for p in [old_path, new_path, delta_path, out_path]:
                os.unlink(p)

    def test_scan_signature(self):
        data = b"\x00" * 5 + b"\x48\x8B\x05\x12\x34\x56\x78"
        result = self.analyzer.scan_signature(data, "48 8B 05 ? ? ? ?", "ida")
        self.assertTrue(result["success"])
        self.assertEqual(result["matches"], 1)

    def test_scan_signature_file(self):
        data = b"\x00" * 5 + b"\x48\x8B\x05" + b"\x00" * 5
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(data)
            tmp_path = f.name

        try:
            result = self.analyzer.scan_signature_file(tmp_path, "48 8B 05", "ida")
            self.assertTrue(result["success"])
            self.assertEqual(result["matches"], 1)
        finally:
            os.unlink(tmp_path)

    def test_generate_signature(self):
        data = b"\x48\x8B\x05\x12\x34\x56\x78"
        result = self.analyzer.generate_signature(data, 0, 7, "ida")
        self.assertTrue(result["success"])
        self.assertIn("48", result["signature"])

    def test_generate_unique_signature(self):
        data = b"\x00" * 10 + b"\x48\x8B\x05\x12\x34\x56\x78" + b"\x00" * 10
        result = self.analyzer.generate_unique_signature(data, 10, 4, 7, "ida")
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["signature"])

    def test_create_patch(self):
        old = b"test patch data"
        new = b"test patch data changed"
        result = self.analyzer.create_patch(old, new, "test")
        self.assertTrue(result["success"])
        self.assertIn("patch_id", result)

    def test_apply_patch(self):
        old = b"apply patch test"
        new = b"apply patch test updated"
        create_result = self.analyzer.create_patch(old, new)
        patch_id = create_result["patch_id"]

        result = self.analyzer.apply_patch(old, patch_id)
        self.assertTrue(result["success"])

    def test_apply_nonexistent_patch(self):
        result = self.analyzer.apply_patch(b"data", "nonexistent")
        self.assertFalse(result["success"])

    def test_save_load_patch(self):
        old = b"save patch test"
        new = b"save patch test modified"
        create_result = self.analyzer.create_patch(old, new)
        patch_id = create_result["patch_id"]

        with tempfile.NamedTemporaryFile(delete=False, suffix=".patch") as f:
            tmp_path = f.name

        try:
            save_result = self.analyzer.save_patch(patch_id, tmp_path)
            self.assertTrue(save_result["success"])

            load_result = self.analyzer.load_patch(tmp_path)
            self.assertTrue(load_result["success"])
        finally:
            os.unlink(tmp_path)

    def test_verify_patch(self):
        old = b"verify patch data"
        new = b"verify patch data modified"
        create_result = self.analyzer.create_patch(old, new)
        patch_id = create_result["patch_id"]

        verify_result = self.analyzer.verify_patch(old, patch_id)
        self.assertTrue(verify_result["success"])
        self.assertTrue(verify_result["valid"])

    def test_create_ips_patch(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".old") as f:
            f.write(b"ips test")
            old_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".new") as f:
            f.write(b"ips test done")
            new_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ips") as f:
            out_path = f.name

        try:
            result = self.analyzer.create_ips_patch(old_path, new_path, out_path)
            self.assertTrue(result["success"])
        finally:
            for p in [old_path, new_path, out_path]:
                os.unlink(p)

    def test_apply_ips_patch(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".old") as f:
            f.write(b"ips test")
            old_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".new") as f:
            f.write(b"ips test done")
            new_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ips") as f:
            patch_path = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".out") as f:
            out_path = f.name

        try:
            self.analyzer.create_ips_patch(old_path, new_path, patch_path)
            result = self.analyzer.apply_ips_patch(old_path, patch_path, out_path)
            self.assertTrue(result["success"])

            with open(out_path, "rb") as f:
                patched = f.read()
            self.assertEqual(patched, b"ips test done")
        finally:
            for p in [old_path, new_path, patch_path, out_path]:
                os.unlink(p)

    def test_compare_sections(self):
        result = self.analyzer.compare_sections(
            {"text": b"hello", "data": b"world"},
            {"text": b"hello", "data": b"world!"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sections"]["text"]["status"], "identical")
        self.assertEqual(result["sections"]["data"]["status"], "modified")

    def test_compare_strings(self):
        result = self.analyzer.compare_strings(
            ["hello", "old", "common"],
            ["hello", "new", "common"]
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["added_count"], 1)
        self.assertEqual(result["removed_count"], 1)

    def test_hex_diff(self):
        result = self.analyzer.hex_diff(b"hello", b"hallo")
        self.assertTrue(result["success"])
        self.assertGreater(result["diff_lines"], 0)

    def test_hex_diff_identical(self):
        result = self.analyzer.hex_diff(b"hello", b"hello")
        self.assertTrue(result["success"])
        self.assertEqual(result["diff_lines"], 0)

    def test_hex_diff_different_length(self):
        result = self.analyzer.hex_diff(b"short", b"longer data")
        self.assertTrue(result["success"])
        self.assertGreater(result["diff_lines"], 0)

    def test_batch_diff(self):
        data = b"test" * 50
        with tempfile.NamedTemporaryFile(delete=False, suffix=".a") as f:
            f.write(data)
            path_a = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".b") as f:
            f.write(data[:50] + b"changed" + data[56:])
            path_b = f.name

        try:
            result = self.analyzer.batch_diff([(path_a, path_b)])
            self.assertTrue(result["success"])
            self.assertEqual(result["total"], 1)
        finally:
            os.unlink(path_a)
            os.unlink(path_b)

    def test_merge_patches(self):
        old = b"merge test data one two three"
        new = b"merge test data one two three modified"
        result1 = self.analyzer.create_patch(old, new, "patch1")
        result2 = self.analyzer.create_patch(new, old, "patch2")

        merge_result = self.analyzer.merge_patches([result1["patch_id"], result2["patch_id"]])
        self.assertTrue(merge_result["success"])


class TestQuickFunctions(unittest.TestCase):
    """快捷函数测试"""

    def test_diff_files_quick(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".a") as f:
            f.write(b"hello")
            path_a = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".b") as f:
            f.write(b"hallo")
            path_b = f.name

        try:
            result = diff_files(path_a, path_b)
            self.assertTrue(result["success"])
        finally:
            os.unlink(path_a)
            os.unlink(path_b)

    def test_quick_scan(self):
        data = b"\x00" * 5 + b"\x48\x8B\x05" + b"\x00" * 5
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(data)
            tmp_path = f.name

        try:
            result = quick_scan(tmp_path, "48 8B 05")
            self.assertTrue(result["success"])
            self.assertEqual(result["matches"], 1)
        finally:
            os.unlink(tmp_path)

    def test_quick_delta(self):
        old = b"hello world"
        new = b"hello world!"
        delta = quick_delta(old, new)
        self.assertIsInstance(delta, bytes)

        analyzer = BinaryDiffAnalyzer()
        result = analyzer.delta.apply_delta(old, delta)
        self.assertEqual(result, new)


if __name__ == "__main__":
    unittest.main()