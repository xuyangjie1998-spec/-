"""
游戏资源文件格式深度逆向测试套件
测试 resource_reverse.py 的所有核心功能
"""
import unittest
import os
import sys
import struct

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.resource_reverse import (
    FormatDetector, SHPReverser, PCKReverser, OBDReverser,
    CrossFormatMapper, BinaryTemplateGenerator, IntegrityChecker,
    ResourceReverseEngine, SHP_FORMAT, PCK_FORMAT, OBD_FORMAT,
    INI_FORMAT, SCRIPTSO_FORMAT, FileValidationResult
)


class TestFormatDetector(unittest.TestCase):
    """测试格式检测器"""

    def test_detect_nonexistent_file(self):
        result = FormatDetector.detect("/nonexistent/file.bin")
        self.assertIsNone(result)

    def test_detect_from_bytes_elf(self):
        result = FormatDetector.detect_from_bytes(b"\x7fELF\x01\x01\x01")
        self.assertEqual(result, "scriptso")

    def test_detect_from_bytes_pck(self):
        result = FormatDetector.detect_from_bytes(b"PCK\x00\x01\x00\x00\x00")
        self.assertEqual(result, "pck")

    def test_detect_from_bytes_ini(self):
        result = FormatDetector.detect_from_bytes(b"[Section]\nkey=value")
        self.assertEqual(result, "ini")

    def test_detect_from_bytes_empty(self):
        result = FormatDetector.detect_from_bytes(b"")
        self.assertIsNone(result)

    def test_detect_unknown(self):
        result = FormatDetector.detect_from_bytes(b"\x00\x01\x02\x03\x04")
        self.assertEqual(result, "unknown")


class TestSHPReverser(unittest.TestCase):
    """测试 SHP 格式逆向"""

    def setUp(self):
        self.reverser = SHPReverser()

    def _create_shp_data(self, frame_count=2):
        """创建测试 SHP 数据"""
        # 帧数据
        frames = []
        frame_data = b""
        for i in range(frame_count):
            w = 32 - i * 8
            h = 32 - i * 8
            fh = struct.pack("<HH", w, h)
            fdata = b'\x00' * (w * h)
            frames.append(fh + fdata)

        # 偏移表
        header_size = 8 + frame_count * 8
        offsets = []
        sizes = []
        current_offset = header_size
        for f in frames:
            offsets.append(current_offset)
            sizes.append(len(f))
            current_offset += len(f)

        data = struct.pack("<II", frame_count, header_size)
        for i in range(frame_count):
            data += struct.pack("<II", offsets[i], sizes[i])
        for f in frames:
            data += f
        return data

    def test_load_bytes(self):
        data = self._create_shp_data()
        result = self.reverser.load_bytes(data)
        self.assertTrue(result["success"])
        self.assertEqual(result["size"], len(data))

    def test_parse_header(self):
        data = self._create_shp_data()
        self.reverser.load_bytes(data)
        result = self.reverser.parse_header()
        self.assertTrue(result["success"])
        self.assertEqual(result["frame_count"], 2)

    def test_parse_header_empty(self):
        result = self.reverser.parse_header()
        self.assertFalse(result["success"])

    def test_parse_header_too_small(self):
        self.reverser.load_bytes(b'\x00' * 4)
        result = self.reverser.parse_header()
        self.assertFalse(result["success"])

    def test_extract_frame(self):
        data = self._create_shp_data()
        self.reverser.load_bytes(data)
        self.reverser.parse_header()
        result = self.reverser.extract_frame(0)
        self.assertTrue(result["success"])
        self.assertEqual(result["frame_index"], 0)

    def test_extract_frame_out_of_range(self):
        data = self._create_shp_data()
        self.reverser.load_bytes(data)
        self.reverser.parse_header()
        result = self.reverser.extract_frame(99)
        self.assertFalse(result["success"])

    def test_extract_all_frames(self):
        data = self._create_shp_data(3)
        self.reverser.load_bytes(data)
        result = self.reverser.extract_all_frames()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 3)

    def test_get_format_specification(self):
        spec = self.reverser.get_format_specification()
        self.assertEqual(spec["format"], "SHP")
        self.assertIn("sections", spec)

    def test_get_info(self):
        data = self._create_shp_data()
        self.reverser.load_bytes(data)
        info = self.reverser.get_info()
        self.assertEqual(info["format"], "SHP")
        self.assertEqual(info["frame_count"], 2)


class TestPCKReverser(unittest.TestCase):
    """测试 PCK 格式逆向"""

    def setUp(self):
        self.reverser = PCKReverser()

    def _create_pck_data(self, file_count=2):
        """创建测试 PCK 数据"""
        # 文件数据
        file1 = b"Hello, World!"
        file2 = b"PCK Test Data"

        # 构建条目表
        entries = []
        for i, (name, data) in enumerate([("test.txt", file1), ("data.bin", file2)]):
            entries.append({
                "name": name,
                "data": data,
                "name_len": len(name),
                "data_size": len(data),
                "compressed_size": 0
            })

        # 计算头部大小
        header_size = 16
        for e in entries:
            header_size += 16 + e["name_len"]

        # 计算数据偏移
        data_offset = header_size
        for e in entries:
            e["data_offset"] = data_offset
            data_offset += e["data_size"]

        # 构建完整 PCK
        data = struct.pack("<4sIII", b"PCK\x00", file_count, header_size, 0)

        for e in entries:
            data += struct.pack("<IIII", e["name_len"], e["data_offset"],
                               e["data_size"], e["compressed_size"])
            data += e["name"].encode("utf-8")

        for e in entries:
            data += e["data"]

        return data

    def test_load_bytes(self):
        data = self._create_pck_data()
        result = self.reverser.load_bytes(data)
        self.assertTrue(result["success"])

    def test_parse_header(self):
        data = self._create_pck_data()
        self.reverser.load_bytes(data)
        result = self.reverser.parse_header()
        self.assertTrue(result["success"])
        self.assertEqual(result["file_count"], 2)

    def test_parse_header_invalid_magic(self):
        self.reverser.load_bytes(b'\x00' * 16)
        result = self.reverser.parse_header()
        self.assertFalse(result["success"])

    def test_parse_header_too_small(self):
        self.reverser.load_bytes(b'\x00' * 8)
        result = self.reverser.parse_header()
        self.assertFalse(result["success"])

    def test_parse_entries(self):
        data = self._create_pck_data()
        self.reverser.load_bytes(data)
        self.reverser.parse_header()
        result = self.reverser.parse_entries()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)

    def test_extract_file(self):
        data = self._create_pck_data()
        self.reverser.load_bytes(data)
        self.reverser.parse_header()
        self.reverser.parse_entries()
        result = self.reverser.extract_file(0)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"], b"Hello, World!")

    def test_extract_file_out_of_range(self):
        data = self._create_pck_data()
        self.reverser.load_bytes(data)
        self.reverser.parse_entries()
        result = self.reverser.extract_file(99)
        self.assertFalse(result["success"])

    def test_validate(self):
        data = self._create_pck_data()
        self.reverser.load_bytes(data)
        result = self.reverser.validate()
        self.assertTrue(result["valid"])

    def test_validate_invalid(self):
        self.reverser.load_bytes(b'\x00' * 16)
        result = self.reverser.validate()
        self.assertFalse(result["valid"])

    def test_get_format_specification(self):
        spec = self.reverser.get_format_specification()
        self.assertEqual(spec["format"], "PCK")
        self.assertIn("sections", spec)

    def test_get_info(self):
        data = self._create_pck_data()
        self.reverser.load_bytes(data)
        info = self.reverser.get_info()
        self.assertEqual(info["format"], "PCK")
        self.assertEqual(info["file_count"], 2)


class TestOBDReverser(unittest.TestCase):
    """测试 OBD 格式逆向"""

    def setUp(self):
        self.reverser = OBDReverser()

    def _create_obd_data(self):
        """创建测试 OBD 数据"""
        return (
            b"[Soldier_001]\n"
            b"ObjID = 1\n"
            b"Sequence = idle\n"
            b"Sequence = attack\n"
            b"Sprite = 001\n"
            b"Sprite = 002\n"
            b"Interval = 100\n"
            b"Loop = 1\n"
            b"\n"
            b"[Soldier_002]\n"
            b"ObjID = 2\n"
            b"Sequence = walk\n"
            b"Sprite = 010\n"
            b"Sprite = 011\n"
        )

    def test_load_bytes(self):
        data = self._create_obd_data()
        result = self.reverser.load_bytes(data)
        self.assertTrue(result["success"])

    def test_parse(self):
        data = self._create_obd_data()
        self.reverser.load_bytes(data)
        result = self.reverser.parse()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)

    def test_parse_empty(self):
        result = self.reverser.parse()
        self.assertFalse(result["success"])

    def test_get_object(self):
        data = self._create_obd_data()
        self.reverser.load_bytes(data)
        self.reverser.parse()
        obj = self.reverser.get_object("Soldier_001")
        self.assertIsNotNone(obj)
        self.assertEqual(obj["name"], "Soldier_001")

    def test_get_object_nonexistent(self):
        data = self._create_obd_data()
        self.reverser.load_bytes(data)
        self.reverser.parse()
        obj = self.reverser.get_object("Nonexistent")
        self.assertIsNone(obj)

    def test_get_all_sequences(self):
        data = self._create_obd_data()
        self.reverser.load_bytes(data)
        self.reverser.parse()
        seqs = self.reverser.get_all_sequences()
        self.assertIn("idle", seqs)
        self.assertIn("attack", seqs)
        self.assertIn("walk", seqs)

    def test_get_all_sprites(self):
        data = self._create_obd_data()
        self.reverser.load_bytes(data)
        self.reverser.parse()
        sprites = self.reverser.get_all_sprites()
        self.assertIn("001", sprites)
        self.assertIn("010", sprites)

    def test_get_format_specification(self):
        spec = self.reverser.get_format_specification()
        self.assertEqual(spec["format"], "OBD")

    def test_get_info(self):
        data = self._create_obd_data()
        self.reverser.load_bytes(data)
        info = self.reverser.get_info()
        self.assertEqual(info["format"], "OBD")
        self.assertEqual(info["object_count"], 2)


class TestCrossFormatMapper(unittest.TestCase):
    """测试跨格式映射"""

    def setUp(self):
        self.mapper = CrossFormatMapper()

    def test_register_file(self):
        self.mapper.register_file("/test/file.obd", "obd", {"sprites": ["001", "002"]})
        reg = self.mapper.get_registry()
        self.assertEqual(reg["count"], 1)

    def test_map_references(self):
        self.mapper.register_file("/test/file.obd", "obd", {"sprites": ["001", "002"]})
        self.mapper.register_file("/test/file.pck", "pck", {"entries": [{"name": "test.ini"}, {"name": "data.bin"}]})
        result = self.mapper.map_references()
        self.assertTrue(result["success"])
        self.assertEqual(result["total_files"], 2)

    def test_map_references_empty(self):
        result = self.mapper.map_references()
        self.assertTrue(result["success"])
        self.assertEqual(result["total_files"], 0)


class TestBinaryTemplateGenerator(unittest.TestCase):
    """测试二进制模板生成器"""

    def test_generate_shp_template(self):
        tmpl = BinaryTemplateGenerator.generate_shp_template()
        self.assertIsNotNone(tmpl)
        self.assertIn("SHP", tmpl)

    def test_generate_pck_template(self):
        tmpl = BinaryTemplateGenerator.generate_pck_template()
        self.assertIsNotNone(tmpl)
        self.assertIn("PCK", tmpl)

    def test_generate_elf_template(self):
        tmpl = BinaryTemplateGenerator.generate_elf_template()
        self.assertIsNotNone(tmpl)
        self.assertIn("ELF", tmpl)

    def test_generate_template_unknown(self):
        tmpl = BinaryTemplateGenerator.generate_template("unknown")
        self.assertIsNone(tmpl)

    def test_generate_template_shp(self):
        tmpl = BinaryTemplateGenerator.generate_template("shp")
        self.assertIsNotNone(tmpl)

    def test_list_templates(self):
        tmpls = BinaryTemplateGenerator.list_templates()
        self.assertIn("shp", tmpls)
        self.assertIn("pck", tmpls)


class TestIntegrityChecker(unittest.TestCase):
    """测试完整性校验器"""

    def _create_temp_file(self, name, data):
        path = f"/tmp/{name}"
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_verify_shp_valid(self):
        # 创建有效 SHP
        frame_count = 2
        header_size = 8 + frame_count * 8
        frame1 = b'\x20\x00\x20\x00' + b'\x00' * 100
        frame2 = b'\x10\x00\x10\x00' + b'\x00' * 50
        data = struct.pack("<II", frame_count, header_size)
        data += struct.pack("<II", header_size, len(frame1))
        data += struct.pack("<II", header_size + len(frame1), len(frame2))
        data += frame1 + frame2

        path = self._create_temp_file("test.shp", data)
        result = IntegrityChecker.verify_shp(path)
        self.assertTrue(result.is_valid)
        os.unlink(path)

    def test_verify_shp_nonexistent(self):
        result = IntegrityChecker.verify_shp("/nonexistent/file.shp")
        self.assertFalse(result.is_valid)

    def test_verify_shp_too_small(self):
        path = self._create_temp_file("test_small.shp", b'\x00' * 4)
        result = IntegrityChecker.verify_shp(path)
        self.assertFalse(result.is_valid)
        os.unlink(path)

    def test_verify_pck_valid(self):
        file_count = 1
        header_size = 16 + 16 + 8  # header + entry + name
        file_data = b"test"
        data = struct.pack("<4sIII", b"PCK\x00", file_count, header_size, 0)
        data += struct.pack("<IIII", 8, header_size, len(file_data), 0)
        data += b"test.txt"
        data += file_data

        path = self._create_temp_file("test.pck", data)
        result = IntegrityChecker.verify_pck(path)
        self.assertTrue(result.is_valid)
        os.unlink(path)

    def test_verify_pck_invalid_magic(self):
        path = self._create_temp_file("test_bad.pck", b"BAD\x00" + b'\x00' * 12)
        result = IntegrityChecker.verify_pck(path)
        self.assertFalse(result.is_valid)
        os.unlink(path)

    def test_verify_pck_nonexistent(self):
        result = IntegrityChecker.verify_pck("/nonexistent/file.pck")
        self.assertFalse(result.is_valid)

    def test_verify_scriptso_valid(self):
        data = b'\x7fELF' + b'\x01' * 48  # 最小 ELF 头
        path = self._create_temp_file("test.so", data)
        result = IntegrityChecker.verify_scriptso(path)
        self.assertTrue(result.is_valid)
        os.unlink(path)

    def test_verify_scriptso_invalid_magic(self):
        data = b'BAD\x00' + b'\x00' * 48
        path = self._create_temp_file("test_bad.so", data)
        result = IntegrityChecker.verify_scriptso(path)
        self.assertFalse(result.is_valid)
        os.unlink(path)

    def test_verify_file(self):
        data = b'\x7fELF' + b'\x01' * 48
        path = self._create_temp_file("test_verify.so", data)
        result = IntegrityChecker.verify_file(path)
        self.assertIsInstance(result, FileValidationResult)
        os.unlink(path)


class TestResourceReverseEngine(unittest.TestCase):
    """测试资源逆向综合引擎"""

    def setUp(self):
        self.engine = ResourceReverseEngine()

    def _create_temp_file(self, name, data):
        path = f"/tmp/{name}"
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_analyze_file_nonexistent(self):
        result = self.engine.analyze_file("/nonexistent/file.bin")
        self.assertFalse(result["success"])

    def test_analyze_file_shp(self):
        frame_count = 1
        header_size = 8 + 8
        frame = b'\x20\x00\x20\x00' + b'\x00' * 100
        data = struct.pack("<II", frame_count, header_size)
        data += struct.pack("<II", header_size, len(frame))
        data += frame

        path = self._create_temp_file("test_engine.shp", data)
        result = self.engine.analyze_file(path)
        self.assertTrue(result["success"])
        self.assertIn("info", result)
        os.unlink(path)

    def test_analyze_file_pck(self):
        data = struct.pack("<4sIII", b"PCK\x00", 0, 16, 0)
        path = self._create_temp_file("test_engine.pck", data)
        result = self.engine.analyze_file(path)
        self.assertTrue(result["success"])
        os.unlink(path)

    def test_analyze_file_obd(self):
        data = b"[Object]\nObjID = 1\nSprite = 001\n"
        path = self._create_temp_file("test_engine.obd", data)
        result = self.engine.analyze_file(path)
        self.assertTrue(result["success"])
        os.unlink(path)

    def test_get_format_specification(self):
        result = self.engine.get_format_specification("shp")
        self.assertTrue(result["success"])
        self.assertEqual(result["format"], "SHP Image")

    def test_get_format_specification_unknown(self):
        result = self.engine.get_format_specification("unknown")
        self.assertFalse(result["success"])

    def test_generate_binary_template(self):
        result = self.engine.generate_binary_template("shp")
        self.assertTrue(result["success"])
        self.assertIn("template", result)

    def test_generate_binary_template_unknown(self):
        result = self.engine.generate_binary_template("unknown")
        self.assertFalse(result["success"])

    def test_get_all_formats(self):
        result = self.engine.get_all_formats()
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_analyze_directory(self):
        # 创建临时目录
        tmp_dir = "/tmp/test_res_dir"
        os.makedirs(tmp_dir, exist_ok=True)
        with open(f"{tmp_dir}/test.ini", "w") as f:
            f.write("[Section]\nkey=value\n")
        result = self.engine.analyze_directory(tmp_dir)
        self.assertTrue(result["success"])
        # 清理
        os.unlink(f"{tmp_dir}/test.ini")
        os.rmdir(tmp_dir)


class TestFileValidationResult(unittest.TestCase):
    """测试文件校验结果"""

    def test_create_valid_result(self):
        result = FileValidationResult(
            file_path="/test/file.shp",
            is_valid=True,
            format_type="SHP"
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.format_type, "SHP")

    def test_create_invalid_result(self):
        result = FileValidationResult(
            file_path="/test/file.bad",
            is_valid=False,
            format_type="unknown",
            errors=["无效魔数"],
            warnings=["文件较大"]
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(len(result.warnings), 1)


if __name__ == "__main__":
    unittest.main()