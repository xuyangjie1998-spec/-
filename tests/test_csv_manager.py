"""
San7ModMaker CSV 管理器测试
覆盖 CsvManager 的编码检测、导入/导出、字段映射等核心功能
"""
import os
import sys
import unittest
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCsvManager(unittest.TestCase):
    """验证 CsvManager 的编码检测、导入导出与字段映射"""

    @classmethod
    def setUpClass(cls):
        from core.csv_manager import CsvManager
        cls.CsvManager = CsvManager
        cls.FIELD_MAPS = CsvManager.FIELD_MAPS
        cls.FIELD_ALIASES = CsvManager.FIELD_ALIASES

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = self.CsvManager()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    # ---------- 辅助方法 ----------

    def _write_temp_file(self, filename, content, mode="wb"):
        """在临时目录写入文件"""
        path = os.path.join(self.tmpdir, filename)
        if mode == "wb":
            with open(path, "wb") as f:
                f.write(content)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        return path

    def _write_csv(self, filename, content, encoding="utf-8"):
        """写入 CSV 文件（指定编码）"""
        path = os.path.join(self.tmpdir, filename)
        with open(path, "w", encoding=encoding) as f:
            f.write(content)
        return path

    def _sample_general_data(self):
        """返回示例武将数据"""
        return [
            {"No": "1", "Name": "关羽", "WStr": "98", "Int": "85"},
            {"No": "2", "Name": "赵云", "WStr": "96", "Int": "88"},
        ]

    # ---------- 基础属性测试 ----------

    def test_import(self):
        """模块可正常导入"""
        self.assertTrue(callable(self.CsvManager))

    def test_init(self):
        """初始化后 _encoding 应为 'gbk'"""
        self.assertEqual(self.manager._encoding, "gbk")

    def test_field_maps_has_all_types(self):
        """FIELD_MAPS 包含全部 9 种数据类型"""
        expected_types = ["general", "soldier", "thing", "skill", "formation",
                          "title", "scenario", "nation", "city"]
        for t in expected_types:
            self.assertIn(t, self.FIELD_MAPS, f"缺少数据类型: {t}")
            self.assertIsInstance(self.FIELD_MAPS[t], list)
            self.assertGreater(len(self.FIELD_MAPS[t]), 0, f"{t} 字段列表为空")

    def test_field_aliases(self):
        """FIELD_ALIASES 包含预期的别名映射"""
        self.assertIn("HP", self.FIELD_ALIASES)
        self.assertEqual(self.FIELD_ALIASES["HP"], "Life")
        self.assertIn("ATK", self.FIELD_ALIASES)
        self.assertEqual(self.FIELD_ALIASES["ATK"], "BasePower")

    # ---------- get_field_map 测试 ----------

    def test_get_field_map_valid(self):
        """有效类型返回字段列表"""
        result = self.manager.get_field_map("general")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIn("No", result)
        self.assertIn("Name", result)

    def test_get_field_map_invalid(self):
        """无效类型返回 None"""
        result = self.manager.get_field_map("nonexistent")
        self.assertIsNone(result)

    # ---------- _get_numeric_fields 测试 ----------

    def test_get_numeric_fields(self):
        """返回包含预期数值字段的集合"""
        result = self.manager._get_numeric_fields("general")
        self.assertIsInstance(result, set)
        expected = {"No", "WStr", "Int", "HP", "MP", "Morale", "Loyal", "Life"}
        for field in expected:
            self.assertIn(field, result, f"缺少数值字段: {field}")

    # ---------- _detect_encoding 测试 ----------

    def test_detect_encoding_utf8_bom(self):
        """BOM 头应检测为 utf-8-sig"""
        path = self._write_temp_file("bom.csv", b'\xef\xbb\xbfNo,Name\n1,CaoCao\n')
        result = self.manager._detect_encoding(path)
        self.assertEqual(result, "utf-8-sig")

    def test_detect_encoding_utf8(self):
        """纯 ASCII 内容应检测为 utf-8"""
        path = self._write_temp_file("utf8.csv", b'No,Name\n1,CaoCao\n')
        result = self.manager._detect_encoding(path)
        self.assertEqual(result, "utf-8")

    def test_detect_encoding_gbk(self):
        """GBK 编码的中文内容应检测为 gbk"""
        content = 'No,Name,WStr,Int\n1,关羽,98,85\n'.encode('gbk')
        path = self._write_temp_file("gbk.csv", content)
        result = self.manager._detect_encoding(path)
        self.assertEqual(result, "gbk")

    def test_detect_encoding_big5(self):
        """Big5 编码的繁体中文应检测为 big5"""
        # 使用 Big5 字节序列在 GBK 中无效的字符（如 一丁七 的 Big5 编码为 a440 a442 a443）
        content = 'No,Name,WStr,Int\n1,一丁七,98,85\n'.encode('big5')
        path = self._write_temp_file("big5.csv", content)
        result = self.manager._detect_encoding(path)
        self.assertEqual(result, "big5")

    def test_detect_encoding_fallback(self):
        """无法识别的编码回退到 gbk"""
        # 使用一段二进制数据使所有解码尝试都失败
        path = self._write_temp_file("fallback.csv", b'\x80\x81\x82\x83\x84\x85')
        result = self.manager._detect_encoding(path)
        self.assertEqual(result, "gbk")

    # ---------- 导出测试 ----------

    def test_export_csv_empty_data(self):
        """空数据导出仅包含表头"""
        path = os.path.join(self.tmpdir, "empty.csv")
        result = self.manager.export_csv("general", [], path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        self.assertIn("No", content)
        self.assertIn("Name", content)
        # 只有表头，没有数据行
        lines = content.strip().split("\n")
        self.assertEqual(len(lines), 1)

    def test_export_csv_with_data(self):
        """导出数据包含表头和数据行"""
        path = os.path.join(self.tmpdir, "export.csv")
        data = self._sample_general_data()
        result = self.manager.export_csv("general", data, path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        self.assertIn("关羽", content)
        self.assertIn("赵云", content)
        self.assertIn("98", content)

    def test_export_csv_invalid_type(self):
        """无效数据类型应抛出 ValueError"""
        path = os.path.join(self.tmpdir, "invalid.csv")
        with self.assertRaises(ValueError):
            self.manager.export_csv("nonexistent", [], path)

    def test_export_csv_string(self):
        """导出 CSV 字符串包含表头和数据"""
        data = self._sample_general_data()
        result = self.manager.export_csv_string("general", data)
        self.assertIsInstance(result, str)
        self.assertIn("No", result)
        self.assertIn("关羽", result)
        self.assertIn("赵云", result)

    def test_export_csv_string_invalid_type(self):
        """无效类型导出字符串应抛出 ValueError"""
        with self.assertRaises(ValueError):
            self.manager.export_csv_string("nonexistent", [])

    def test_export_csv_encoding(self):
        """导出文件应使用 UTF-8-sig 编码"""
        path = os.path.join(self.tmpdir, "encoding.csv")
        data = self._sample_general_data()
        self.manager.export_csv("general", data, path)
        with open(path, "rb") as f:
            raw = f.read(3)
        self.assertEqual(raw, b'\xef\xbb\xbf', "应包含 UTF-8 BOM")

    # ---------- 预览测试 ----------

    def test_preview_csv_empty(self):
        """空 CSV 预览应返回错误"""
        path = self._write_csv("empty.csv", "")
        result = self.manager.preview_csv("general", path)
        self.assertFalse(result["success"])
        self.assertIn("为空", result.get("message", ""))

    def test_preview_csv_valid(self):
        """有效 CSV 预览应返回字段映射和预览数据"""
        path = self._write_csv("preview.csv", "No,Name,WStr,Int\n1,关羽,98,85\n")
        result = self.manager.preview_csv("general", path)
        self.assertTrue(result["success"])
        self.assertIn("field_map", result)
        self.assertIn("preview", result)
        self.assertEqual(len(result["preview"]), 1)
        self.assertEqual(result["preview"][0]["Name"], "关羽")
        self.assertEqual(result["preview"][0]["WStr"], "98")

    def test_preview_csv_invalid_type(self):
        """无效类型预览应返回错误"""
        path = self._write_csv("preview.csv", "No,Name\n1,test\n")
        result = self.manager.preview_csv("nonexistent", path)
        self.assertFalse(result["success"])

    # ---------- 导入测试 ----------

    def test_import_csv_valid(self):
        """有效 CSV 导入应返回正确数据"""
        path = self._write_csv("import.csv", "No,Name,WStr,Int\n1,关羽,98,85\n")
        result = self.manager.import_csv("general", path)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["data"][0]["Name"], "关羽")
        self.assertEqual(result["data"][0]["WStr"], "98")
        self.assertEqual(len(result["errors"]), 0)

    def test_import_csv_empty(self):
        """空 CSV 导入应返回错误"""
        path = self._write_csv("empty.csv", "")
        result = self.manager.import_csv("general", path)
        self.assertFalse(result["success"])
        self.assertIn("为空", result.get("message", ""))

    def test_import_csv_duplicate_ids(self):
        """重复 No 应被检测到"""
        path = self._write_csv("dup.csv", "No,Name,WStr,Int\n1,关羽,98,85\n1,赵云,96,88\n")
        result = self.manager.import_csv("general", path)
        self.assertTrue(result["success"])
        self.assertGreater(len(result["errors"]), 0)
        duplicate_msgs = [e for e in result["errors"] if "重复" in e]
        self.assertGreater(len(duplicate_msgs), 0)

    def test_import_csv_missing_no(self):
        """缺少 No 字段应被检测到"""
        path = self._write_csv("missing.csv", "No,Name,WStr,Int\n,关羽,98,85\n")
        result = self.manager.import_csv("general", path)
        self.assertTrue(result["success"])
        self.assertGreater(len(result["errors"]), 0)
        missing_msgs = [e for e in result["errors"] if "缺少" in e]
        self.assertGreater(len(missing_msgs), 0)

    def test_import_csv_non_numeric(self):
        """非数值字段值应被检测到"""
        path = self._write_csv("nonnum.csv", "No,Name,WStr,Int\n1,关羽,abc,85\n")
        result = self.manager.import_csv("general", path)
        self.assertTrue(result["success"])
        self.assertGreater(len(result["errors"]), 0)
        non_num_msgs = [e for e in result["errors"] if "不是有效整数" in e]
        self.assertGreater(len(non_num_msgs), 0)

    def test_import_csv_invalid_type(self):
        """无效类型导入应返回错误"""
        path = self._write_csv("import.csv", "No,Name\n1,test\n")
        result = self.manager.import_csv("nonexistent", path)
        self.assertFalse(result["success"])

    # ---------- _build_field_map 测试 ----------

    def test_build_field_map_exact_match(self):
        """完全匹配的表头应正确映射"""
        header = ["No", "Name", "WStr", "Int"]
        standard = ["No", "Name", "WStr", "Int"]
        result = self.manager._build_field_map(header, standard)
        self.assertEqual(result["No"], "No")
        self.assertEqual(result["Name"], "Name")
        self.assertEqual(result["WStr"], "WStr")
        self.assertEqual(result["Int"], "Int")

    def test_build_field_map_alias(self):
        """别名映射应正确工作"""
        # HP 应映射到 Life
        header = ["No", "Name", "HP", "Int"]
        standard = ["No", "Name", "Life", "Int"]
        result = self.manager._build_field_map(header, standard)
        self.assertEqual(result["HP"], "Life")
        self.assertEqual(result["No"], "No")
        self.assertEqual(result["Name"], "Name")

    def test_build_field_map_id_to_no(self):
        """"ID" 表头应映射到 "No" """
        header = ["ID", "Name", "WStr"]
        standard = ["No", "Name", "WStr"]
        result = self.manager._build_field_map(header, standard)
        self.assertEqual(result["ID"], "No")

    def test_build_field_map_chinese_name(self):
        """"名称" 表头应映射到 "Name" """
        header = ["No", "名称", "WStr"]
        standard = ["No", "Name", "WStr"]
        result = self.manager._build_field_map(header, standard)
        self.assertEqual(result["名称"], "Name")


if __name__ == "__main__":
    unittest.main(verbosity=2)