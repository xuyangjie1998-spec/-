"""
存档加密/解密引擎测试套件
测试 save_crypto.py 的所有核心功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import struct
import tempfile
import zlib
import hashlib
from core.save_crypto import (
    EntropyAnalyzer, XORCryptoAnalyzer, ChecksumAnalyzer,
    CompressionDetector, SaveFormatParser, SaveFileAnalyzer,
    EncryptionType, ChecksumType, CompressionType,
    KeyDerivationMethod, SaveFormat, SaveSection,
    CryptoAnalysisResult, XORKeyResult
)


class TestEntropyAnalyzer(unittest.TestCase):
    """熵分析器测试"""

    def setUp(self):
        self.analyzer = EntropyAnalyzer()

    def test_calculate_entropy_empty(self):
        entropy = self.analyzer.calculate_entropy(b"")
        self.assertEqual(entropy, 0.0)

    def test_calculate_entropy_uniform(self):
        """均匀分布数据应有高熵"""
        data = bytes(range(256)) * 4  # 1024 bytes, each byte appears 4 times
        entropy = self.analyzer.calculate_entropy(data)
        self.assertGreater(entropy, 7.5)

    def test_calculate_entropy_low(self):
        """重复数据应有低熵"""
        data = b"\x00" * 1000
        entropy = self.analyzer.calculate_entropy(data)
        self.assertLess(entropy, 1.0)

    def test_calculate_entropy_text(self):
        """文本数据应有中等熵"""
        data = b"Hello World! " * 100
        entropy = self.analyzer.calculate_entropy(data)
        self.assertGreater(entropy, 3.0)
        self.assertLess(entropy, 6.0)

    def test_detect_encryption_high_entropy(self):
        """高熵数据应检测为加密"""
        data = bytes(range(256)) * 4
        is_encrypted, confidence = self.analyzer.detect_encryption(data)
        self.assertTrue(is_encrypted)
        self.assertGreater(confidence, 0.9)

    def test_detect_encryption_low_entropy(self):
        """低熵数据不应检测为加密"""
        data = b"Hello World! " * 100
        is_encrypted, confidence = self.analyzer.detect_encryption(data)
        self.assertFalse(is_encrypted)

    def test_byte_distribution(self):
        data = b"\x00\x00\x01\x02"
        dist = self.analyzer.calculate_byte_distribution(data)
        self.assertEqual(dist[0], 0.5)
        self.assertEqual(dist[1], 0.25)
        self.assertEqual(dist[2], 0.25)

    def test_find_anomalies(self):
        """包含大量零字节的数据应有异常"""
        data = b"\x00" * 500 + bytes(range(256)) * 2
        anomalies = self.analyzer.find_anomalies(data)
        self.assertGreater(len(anomalies), 0)
        zero_anomaly = next((a for a in anomalies if a["byte"] == "0x0"), None)
        self.assertIsNotNone(zero_anomaly)

    def test_find_anomalies_small_data(self):
        """小数据不应有异常"""
        anomalies = self.analyzer.find_anomalies(b"\x00\x01")
        self.assertEqual(len(anomalies), 0)


class TestXORCryptoAnalyzer(unittest.TestCase):
    """XOR加密分析器测试"""

    def setUp(self):
        self.analyzer = XORCryptoAnalyzer()

    def test_decrypt_xor_single(self):
        plaintext = b"Hello World! This is a test message."
        key = b"\x55"
        encrypted = self.analyzer.encrypt_xor(plaintext, key)
        decrypted = self.analyzer.decrypt_xor(encrypted, key)
        self.assertEqual(decrypted, plaintext)

    def test_decrypt_xor_multi(self):
        plaintext = b"Hello World! This is a longer test message for multi-byte XOR key testing."
        key = b"\x12\x34\x56\x78"
        encrypted = self.analyzer.encrypt_xor(plaintext, key)
        decrypted = self.analyzer.decrypt_xor(encrypted, key)
        self.assertEqual(decrypted, plaintext)

    def test_detect_xor_single(self):
        """检测单字节 XOR"""
        plaintext = b"This is a test message with enough text to detect the XOR key pattern."
        key = b"\xAA"
        encrypted = self.analyzer.encrypt_xor(plaintext, key)
        result = self.analyzer.detect_xor_single(encrypted)
        self.assertIsNotNone(result)
        self.assertEqual(result.key, key)

    def test_detect_xor_single_short_data(self):
        """短数据不应检测"""
        result = self.analyzer.detect_xor_single(b"\x12\x34")
        self.assertIsNone(result)

    def test_detect_xor_multi(self):
        """检测多字节 XOR"""
        plaintext = b"AAAA" * 100 + b"BBBB" * 100 + b"CCCC" * 100
        key = b"\x12\x34"
        encrypted = self.analyzer.encrypt_xor(plaintext, key)
        results = self.analyzer.detect_xor_multi(encrypted, max_key_len=4)
        self.assertGreater(len(results), 0)

    def test_detect_xor_rolling(self):
        """检测滚动 XOR"""
        data = bytes(range(256)) * 8
        result = self.analyzer.detect_xor_rolling(data)
        # 滚动 XOR 检测可能返回 None 或结果
        self.assertTrue(result is None or isinstance(result, XORKeyResult))

    def test_encrypt_decrypt_roundtrip(self):
        """加密解密回环"""
        original = bytes(range(256)) * 4
        key = b"\xDE\xAD\xBE\xEF"
        encrypted = self.analyzer.encrypt_xor(original, key)
        decrypted = self.analyzer.decrypt_xor(encrypted, key)
        self.assertEqual(decrypted, original)

    def test_score_plaintext_english(self):
        """英文文本应得高分"""
        score = self.analyzer._score_plaintext(b"The quick brown fox jumps over the lazy dog. " * 10)
        self.assertGreater(score, 0.5)

    def test_score_plaintext_binary(self):
        """二进制数据应得低分"""
        score = self.analyzer._score_plaintext(bytes(range(256)))
        self.assertLess(score, 0.5)

    def test_validate_key(self):
        """验证密钥"""
        plaintext = b"Hello World! " * 20
        key = b"\x55"
        encrypted = self.analyzer.encrypt_xor(plaintext, key)
        self.assertTrue(self.analyzer._validate_xor_key(encrypted, key))

    def test_known_headers(self):
        """已知文件头测试"""
        self.assertIn(b'\x7fELF', self.analyzer.KNOWN_HEADERS)
        self.assertIn(b'PK\x03\x04', self.analyzer.KNOWN_HEADERS)


class TestChecksumAnalyzer(unittest.TestCase):
    """校验和分析器测试"""

    def setUp(self):
        self.analyzer = ChecksumAnalyzer()

    def test_calculate_crc32(self):
        data = b"Hello World"
        cs = self.analyzer.calculate_checksum(data, ChecksumType.CRC32)
        self.assertEqual(len(cs), 4)

    def test_calculate_adler32(self):
        data = b"Hello World"
        cs = self.analyzer.calculate_checksum(data, ChecksumType.ADLER32)
        self.assertEqual(len(cs), 4)

    def test_calculate_md5(self):
        data = b"Hello World"
        cs = self.analyzer.calculate_checksum(data, ChecksumType.MD5)
        self.assertEqual(len(cs), 16)
        self.assertEqual(cs, hashlib.md5(data).digest())

    def test_calculate_sha1(self):
        data = b"Hello World"
        cs = self.analyzer.calculate_checksum(data, ChecksumType.SHA1)
        self.assertEqual(len(cs), 20)

    def test_calculate_sha256(self):
        data = b"Hello World"
        cs = self.analyzer.calculate_checksum(data, ChecksumType.SHA256)
        self.assertEqual(len(cs), 32)

    def test_calculate_xor_sum(self):
        data = b"\x01\x02\x03"
        cs = self.analyzer.calculate_checksum(data, ChecksumType.XOR_SUM)
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0], 0x01 ^ 0x02 ^ 0x03)  # = 0x00

    def test_calculate_crc16(self):
        data = b"Hello World"
        cs = self.analyzer.calculate_checksum(data, ChecksumType.CRC16)
        self.assertEqual(len(cs), 2)

    def test_calculate_crc8(self):
        data = b"Hello World"
        cs = self.analyzer.calculate_checksum(data, ChecksumType.CRC8)
        self.assertEqual(len(cs), 1)

    def test_calculate_additive(self):
        data = b"\x01\x02\x03"
        cs = self.analyzer.calculate_checksum(data, ChecksumType.ADDITIVE)
        self.assertEqual(len(cs), 4)

    def test_verify_checksum(self):
        data = b"Hello World"
        cs = self.analyzer.calculate_checksum(data, ChecksumType.CRC32)
        self.assertTrue(self.analyzer.verify_checksum(data, cs, ChecksumType.CRC32))

    def test_verify_checksum_fail(self):
        data = b"Hello World"
        cs = b"\x00\x00\x00\x00"
        self.assertFalse(self.analyzer.verify_checksum(data, cs, ChecksumType.CRC32))

    def test_detect_checksum_crc32(self):
        """检测 CRC32 校验和"""
        data = b"Hello World"
        cs = self.analyzer.calculate_checksum(data, ChecksumType.CRC32)
        data_with_cs = data + cs
        result = self.analyzer.detect_checksum(data_with_cs)
        self.assertTrue(result["success"])
        types = [r["type"] for r in result["results"]]
        self.assertIn("crc32", types)

    def test_detect_checksum_xor_sum(self):
        """检测 XOR 校验和"""
        data = b"\x01\x02\x03"
        cs = self.analyzer.calculate_checksum(data, ChecksumType.XOR_SUM)
        data_with_cs = data + cs
        result = self.analyzer.detect_checksum(data_with_cs)
        self.assertTrue(result["success"])
        types = [r["type"] for r in result["results"]]
        self.assertIn("xor_sum", types)

    def test_patch_checksum(self):
        data = b"Hello World"
        cs = self.analyzer.calculate_checksum(data, ChecksumType.CRC32)
        data_with_cs = data + cs
        # 修改数据
        modified = bytearray(data_with_cs)
        modified[0] = ord('X')
        # 修补校验和
        patched = self.analyzer.patch_checksum(
            bytes(modified), ChecksumType.CRC32, len(data)
        )
        new_data = patched[:len(data)]
        new_cs = patched[len(data):len(data) + 4]
        self.assertTrue(self.analyzer.verify_checksum(new_data, new_cs, ChecksumType.CRC32))


class TestCompressionDetector(unittest.TestCase):
    """压缩检测器测试"""

    def setUp(self):
        self.detector = CompressionDetector()

    def test_detect_zlib(self):
        data = b"Hello World! " * 100
        compressed = zlib.compress(data)
        comp_type, confidence = self.detector.detect(compressed)
        self.assertEqual(comp_type, CompressionType.ZLIB)

    def test_detect_none(self):
        comp_type, confidence = self.detector.detect(b"Hello World")
        self.assertEqual(comp_type, CompressionType.UNKNOWN)

    def test_detect_gzip(self):
        import gzip
        import io
        data = b"Hello World! " * 100
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write(data)
        compressed = buf.getvalue()
        comp_type, confidence = self.detector.detect(compressed)
        self.assertEqual(comp_type, CompressionType.GZIP)

    def test_decompress_zlib(self):
        data = b"Hello World! " * 50
        compressed = zlib.compress(data)
        result = self.detector.decompress(compressed)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"], data)

    def test_decompress_gzip(self):
        import gzip
        import io
        data = b"Hello World! " * 50
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write(data)
        compressed = buf.getvalue()
        result = self.detector.decompress(compressed)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"], data)

    def test_decompress_fail(self):
        result = self.detector.decompress(b"\x00\x01\x02\x03")
        self.assertFalse(result["success"])

    def test_compress_zlib(self):
        data = b"Hello World! " * 50
        result = self.detector.compress(data, CompressionType.ZLIB)
        self.assertTrue(result["success"])
        # 解压验证
        decompressed = zlib.decompress(result["data"])
        self.assertEqual(decompressed, data)

    def test_compress_gzip(self):
        data = b"Hello World! " * 50
        result = self.detector.compress(data, CompressionType.GZIP)
        self.assertTrue(result["success"])

    def test_compress_invalid(self):
        result = self.detector.compress(b"test", CompressionType.NONE)
        self.assertFalse(result["success"])


class TestSaveFormatParser(unittest.TestCase):
    """存档格式解析器测试"""

    def setUp(self):
        self.parser = SaveFormatParser()

    def test_default_formats(self):
        formats = self.parser.list_formats()
        self.assertGreaterEqual(len(formats), 2)
        format_ids = [f["format_id"] for f in formats]
        self.assertIn("sg7_save", format_ids)
        self.assertIn("generic_save", format_ids)

    def test_register_format(self):
        result = self.parser.register_format(
            "test_format", "测试格式",
            magic=b"TEST",
            header_size=32,
            encryption="xor_single",
            checksum="crc32",
            compression="zlib",
            description="测试格式描述"
        )
        self.assertTrue(result["success"])

    def test_register_format_invalid(self):
        result = self.parser.register_format(
            "test", "测试", encryption="invalid"
        )
        self.assertFalse(result["success"])

    def test_get_format(self):
        fmt = self.parser.get_format("sg7_save")
        self.assertIsNotNone(fmt)
        self.assertEqual(fmt["name"], "三国群英传7 存档")

    def test_get_nonexistent_format(self):
        fmt = self.parser.get_format("nonexistent")
        self.assertIsNone(fmt)

    def test_add_section(self):
        result = self.parser.add_section(
            "sg7_save", "test_section", 128, 256,
            "测试区域", is_encrypted=True
        )
        self.assertTrue(result["success"])

    def test_add_section_nonexistent(self):
        result = self.parser.add_section("nonexistent", "test", 0, 100)
        self.assertFalse(result["success"])


class TestSaveFileAnalyzer(unittest.TestCase):
    """存档文件分析器测试"""

    def setUp(self):
        self.analyzer = SaveFileAnalyzer()

    def test_analyze_plaintext_file(self):
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".sav", delete=False) as f:
            f.write(b"Hello World! This is a test save file." * 20)
            path = f.name
        try:
            result = self.analyzer.analyze(path)
            self.assertTrue(result["success"])
            self.assertIn("entropy", result)
            self.assertIn("file_size", result)
            self.assertIn("md5", result)
        finally:
            os.unlink(path)

    def test_analyze_encrypted_file(self):
        data = bytes(range(256)) * 16  # 高熵数据
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".sav", delete=False) as f:
            f.write(data)
            path = f.name
        try:
            result = self.analyzer.analyze(path)
            self.assertTrue(result["success"])
            self.assertGreater(result["entropy"], 7.0)
        finally:
            os.unlink(path)

    def test_analyze_nonexistent(self):
        result = self.analyzer.analyze("/nonexistent/path.sav")
        self.assertFalse(result["success"])

    def test_analyze_bytes(self):
        data = b"Hello World! " * 50
        result = self.analyzer.analyze_bytes(data)
        self.assertTrue(result["success"])
        self.assertIn("entropy", result)

    def test_decrypt_xor(self):
        plaintext = b"Hello World! This is a test save file." * 10
        key = b"\xAA"
        encrypted = XORCryptoAnalyzer.encrypt_xor(plaintext, key)

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".sav", delete=False) as f:
            f.write(encrypted)
            in_path = f.name
        out_path = in_path + ".decrypted"
        try:
            result = self.analyzer.decrypt_xor(in_path, key, out_path)
            self.assertTrue(result["success"])
            with open(out_path, "rb") as f:
                decrypted = f.read()
            self.assertEqual(decrypted, plaintext)
        finally:
            os.unlink(in_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_encrypt_xor(self):
        plaintext = b"Hello World! " * 20
        key = b"\x55"
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".sav", delete=False) as f:
            f.write(plaintext)
            in_path = f.name
        out_path = in_path + ".encrypted"
        try:
            result = self.analyzer.encrypt_xor(in_path, key, out_path)
            self.assertTrue(result["success"])
        finally:
            os.unlink(in_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_brute_force_xor_key(self):
        plaintext = b"AAAA" * 100
        key = b"\x12"
        encrypted = XORCryptoAnalyzer.encrypt_xor(plaintext, key)

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".sav", delete=False) as f:
            f.write(encrypted)
            path = f.name
        try:
            result = self.analyzer.brute_force_xor_key(path, max_key_len=4)
            self.assertTrue(result["success"])
            self.assertGreater(len(result["results"]), 0)
        finally:
            os.unlink(path)

    def test_brute_force_nonexistent(self):
        result = self.analyzer.brute_force_xor_key("/nonexistent/path.sav")
        self.assertFalse(result["success"])

    def test_patch_save(self):
        data = b"AAAA" * 50
        # 添加 CRC32 校验和
        cs = ChecksumAnalyzer.calculate_checksum(data, ChecksumType.CRC32)
        data_with_cs = data + cs

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".sav", delete=False) as f:
            f.write(data_with_cs)
            path = f.name
        out_path = path + ".patched"
        try:
            result = self.analyzer.patch_save(
                path, 0, b"BBBB",
                fix_checksum=True, checksum_type="crc32",
                output_path=out_path
            )
            self.assertTrue(result["success"])
        finally:
            os.unlink(path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_patch_save_out_of_range(self):
        data = b"AAAA"
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".sav", delete=False) as f:
            f.write(data)
            path = f.name
        try:
            result = self.analyzer.patch_save(path, 100, b"BBBB")
            self.assertFalse(result["success"])
        finally:
            os.unlink(path)

    def test_extract_sections(self):
        data = b"HEAD" + b"BODY" * 20 + b"TAIL"
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".sav", delete=False) as f:
            f.write(data)
            path = f.name
        try:
            sections = [
                {"name": "header", "offset": 0, "size": 4},
                {"name": "body", "offset": 4, "size": 80},
            ]
            result = self.analyzer.extract_sections(path, sections)
            self.assertTrue(result["success"])
            self.assertEqual(len(result["sections"]), 2)
        finally:
            os.unlink(path)

    def test_hex_dump(self):
        data = b"Hello World! " * 10
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".sav", delete=False) as f:
            f.write(data)
            path = f.name
        try:
            result = self.analyzer.hex_dump(path, offset=0, size=64)
            self.assertTrue(result["success"])
            self.assertIn("hex_dump", result)
        finally:
            os.unlink(path)

    def test_hex_dump_nonexistent(self):
        result = self.analyzer.hex_dump("/nonexistent/path.sav")
        self.assertFalse(result["success"])

    def test_compare_saves(self):
        data1 = b"AAAA" * 50
        data2 = b"BBBB" * 50

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".sav", delete=False) as f:
            f.write(data1)
            path1 = f.name
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".sav", delete=False) as f:
            f.write(data2)
            path2 = f.name
        try:
            result = self.analyzer.compare_saves(path1, path2)
            self.assertTrue(result["success"])
            self.assertGreater(result["total_differences"], 0)
        finally:
            os.unlink(path1)
            os.unlink(path2)

    def test_compare_saves_identical(self):
        data = b"AAAA" * 50
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".sav", delete=False) as f:
            f.write(data)
            path1 = f.name
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".sav", delete=False) as f:
            f.write(data)
            path2 = f.name
        try:
            result = self.analyzer.compare_saves(path1, path2)
            self.assertTrue(result["success"])
            self.assertEqual(result["total_differences"], 0)
        finally:
            os.unlink(path1)
            os.unlink(path2)

    def test_compare_saves_nonexistent(self):
        result = self.analyzer.compare_saves("/nonexistent/1.sav", "/nonexistent/2.sav")
        self.assertFalse(result["success"])

    def test_get_info(self):
        info = self.analyzer.get_info()
        self.assertEqual(info["name"], "存档加密/解密引擎")
        self.assertIn("capabilities", info)

    def test_header_analysis(self):
        result = self.analyzer._analyze_header(b"Hello World!")
        self.assertIn("header_hex", result)
        self.assertIn("first_bytes", result)

    def test_match_format(self):
        result = self.analyzer._match_format(b"SG7" + b"\x00" * 100)
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()