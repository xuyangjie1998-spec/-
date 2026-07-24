"""
San7ModMaker 核心模块深度测试
覆盖 FieldMapper / TermTextManager / VersionDetector
"""
import os
import sys
import unittest
import tempfile
import shutil
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFieldMapper(unittest.TestCase):
    """验证字段映射器"""

    @classmethod
    def setUpClass(cls):
        from core.field_mapper import FieldMapper
        # 重置单例以获取干净实例
        FieldMapper._instance = None
        FieldMapper._mappings = {}
        cls.mapper = FieldMapper()

    def test_singleton(self):
        from core.field_mapper import FieldMapper
        fm2 = FieldMapper()
        self.assertIs(self.mapper, fm2)

    def test_import(self):
        from core.field_mapper import FieldMapper
        self.assertTrue(callable(FieldMapper))

    def test_schema_to_game_identity(self):
        """未映射字段直接返回原名"""
        result = self.mapper.schema_to_game("nonexistent", "SomeField")
        self.assertEqual(result, "SomeField")

    def test_game_to_schema_identity(self):
        """未映射字段直接返回原名"""
        result = self.mapper.game_to_schema("nonexistent", "SomeField")
        self.assertEqual(result, "SomeField")

    def test_entry_to_game_identity(self):
        """无映射类别的条目保持不变"""
        entry = {"Name": "关羽", "Str": 98}
        result = self.mapper.entry_to_game("nonexistent", entry)
        self.assertEqual(result, {"Name": "关羽", "Str": 98})

    def test_entry_to_schema_identity(self):
        """无映射类别的条目保持不变"""
        entry = {"Name": "关羽", "Str": 98}
        result = self.mapper.entry_to_schema("nonexistent", entry)
        self.assertEqual(result, {"Name": "关羽", "Str": 98})

    def test_entries_to_game_batch(self):
        """批量映射"""
        entries = [{"Name": "A"}, {"Name": "B"}]
        result = self.mapper.entries_to_game("nonexistent", entries)
        self.assertEqual(len(result), 2)

    def test_entries_to_schema_batch(self):
        """批量反向映射"""
        entries = [{"Name": "A"}, {"Name": "B"}]
        result = self.mapper.entries_to_schema("nonexistent", entries)
        self.assertEqual(len(result), 2)

    def test_get_all_mappings_empty(self):
        """不存在的类别返回空字典"""
        result = self.mapper.get_all_mappings("nonexistent")
        self.assertEqual(result, {})

    def test_get_all_reverse_mappings_empty(self):
        """不存在的类别返回空字典"""
        result = self.mapper.get_all_reverse_mappings("nonexistent")
        self.assertEqual(result, {})

    def test_reload(self):
        """reload 不抛异常"""
        try:
            self.mapper.reload()
        except Exception as e:
            self.fail(f"reload 抛出异常: {e}")

    def test_mapping_file_exists(self):
        """field_mapping.json 存在"""
        mapping_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "field_mapping.json"
        )
        self.assertTrue(os.path.exists(mapping_path), f"映射文件不存在: {mapping_path}")


class TestTermTextManager(unittest.TestCase):
    """验证 TermText 文本管理器"""

    def setUp(self):
        from core.term_text import TermTextManager
        self.tmpdir = tempfile.mkdtemp()
        self.setting_dir = os.path.join(self.tmpdir, "Setting")
        os.makedirs(self.setting_dir, exist_ok=True)
        self.tm = TermTextManager(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_term_text(self, entries=None):
        """创建测试用的 TermText.ini"""
        if entries is None:
            entries = {
                1: "TestGuanYu",
                2: "TestZhangFei",
                3: "TestLiuBei",
                4: "TestZhugeLiang",
                5: "TestZhaoYun",
            }
        path = os.path.join(self.setting_dir, "TermText.ini")
        with open(path, "w", encoding="gbk") as f:
            f.write("[TermText]\n")
            f.write(f"StringCount = {len(entries)}\n")
            for idx, text in sorted(entries.items()):
                f.write(f"TermText_{idx:04d} = \"{text}\"\n")
        return path

    def test_import(self):
        from core.term_text import TermTextManager
        self.assertTrue(callable(TermTextManager))

    def test_load_empty(self):
        """无 TermText.ini 时加载不抛异常"""
        try:
            self.tm.load()
        except Exception as e:
            self.fail(f"空加载抛出异常: {e}")
        self.assertFalse(self.tm._loaded)

    def test_load_and_get_text(self):
        """加载后正确获取文本"""
        self._create_term_text()
        self.tm.load()
        self.assertTrue(self.tm._loaded)
        self.assertEqual(self.tm.get_text(1), "TestGuanYu")
        self.assertEqual(self.tm.get_text(2), "TestZhangFei")
        self.assertEqual(self.tm.get_text(5), "TestZhaoYun")

    def test_get_text_unloaded(self):
        """未加载时返回默认格式"""
        result = self.tm.get_text(42)
        self.assertEqual(result, "Text_0042")

    def test_get_text_missing_id(self):
        """不存在的ID返回默认格式"""
        self._create_term_text()
        self.tm.load()
        result = self.tm.get_text(999)
        self.assertEqual(result, "Text_0999")

    def test_get_id_by_text(self):
        """根据文本查找ID"""
        self._create_term_text()
        self.tm.load()
        self.assertEqual(self.tm.get_id_by_text("TestGuanYu"), 1)
        self.assertEqual(self.tm.get_id_by_text("TestZhaoYun"), 5)
        self.assertIsNone(self.tm.get_id_by_text("不存在"))

    def test_set_text(self):
        """设置文本"""
        self._create_term_text()
        self.tm.load()
        self.tm.set_text(6, "TestMaChao")
        self.assertEqual(self.tm.get_text(6), "TestMaChao")
        self.assertEqual(self.tm.get_id_by_text("TestMaChao"), 6)

    def test_allocate_new_id(self):
        """分配新ID"""
        self._create_term_text()
        self.tm.load()
        new_id = self.tm.allocate_new_id("TestMaChao")
        self.assertGreater(new_id, 5)
        self.assertEqual(self.tm.get_text(new_id), "TestMaChao")

    def test_allocate_existing_text(self):
        """已存在文本返回已有ID"""
        self._create_term_text()
        self.tm.load()
        existing_id = self.tm.allocate_new_id("TestGuanYu")
        self.assertEqual(existing_id, 1)

    def test_rename(self):
        """改名同步"""
        self._create_term_text()
        self.tm.load()
        self.tm.rename("TestGuanYu", "TestGuanYunChang")
        self.assertEqual(self.tm.get_text(1), "TestGuanYunChang")
        self.assertIsNone(self.tm.get_id_by_text("TestGuanYu"))
        self.assertEqual(self.tm.get_id_by_text("TestGuanYunChang"), 1)

    def test_rename_nonexistent(self):
        """改名不存在文本不抛异常"""
        self._create_term_text()
        self.tm.load()
        try:
            self.tm.rename("不存在", "新名称")
        except Exception as e:
            self.fail(f"改名不存在文本抛出异常: {e}")

    def test_release_by_name(self):
        """释放文本条目"""
        self._create_term_text()
        self.tm.load()
        self.tm.release_by_name("TestGuanYu")
        self.assertIsNone(self.tm.get_id_by_text("TestGuanYu"))

    def test_search_text(self):
        """搜索文本"""
        self._create_term_text()
        self.tm.load()
        results = self.tm.search_text("Liu")
        self.assertIn(3, results)
        self.assertEqual(results[3], "TestLiuBei")

    def test_search_text_case_insensitive(self):
        """搜索不区分大小写"""
        self._create_term_text({1: "GUANYU", 2: "ZhangFei"})
        self.tm.load()
        results = self.tm.search_text("guan")
        self.assertIn(1, results)

    def test_get_all_texts(self):
        """获取全部文本"""
        self._create_term_text()
        self.tm.load()
        all_texts = self.tm.get_all_texts()
        self.assertEqual(len(all_texts), 5)

    def test_duplicate_text_handling(self):
        """重复文本只保留第一个"""
        self._create_term_text({
            1: "TestGuanYu",
            2: "TestGuanYu",  # 重复
            3: "TestLiuBei",
        })
        self.tm.load()
        self.assertEqual(self.tm.get_id_by_text("TestGuanYu"), 1)


class TestVersionDetector(unittest.TestCase):
    """验证版本检测器"""

    def setUp(self):
        from core.version_detect import VersionDetector
        self.tmpdir = tempfile.mkdtemp()
        self.detector = VersionDetector(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_import(self):
        from core.version_detect import VersionDetector
        self.assertTrue(callable(VersionDetector))

    def test_detect_invalid_path(self):
        """无效路径返回错误"""
        detector = self.detector
        detector.game_path = "/nonexistent/path"
        result = detector.detect()
        self.assertFalse(result["success"])

    def test_detect_empty_dir(self):
        """空目录检测完整性"""
        result = self.detector.detect()
        self.assertTrue(result["success"])
        self.assertFalse(result["exe_exists"])
        self.assertGreater(len(result["missing_files"]), 0)

    def test_detect_with_exe(self):
        """有EXE文件时检测"""
        exe_path = os.path.join(self.tmpdir, "Sango7.exe")
        with open(exe_path, "wb") as f:
            f.write(b"MZ" + b"\x00" * 1024)  # 最小 PE 头
        # 创建必要目录
        for d in self.detector.REQUIRED_DIRS:
            os.makedirs(os.path.join(self.tmpdir, d), exist_ok=True)
        result = self.detector.detect()
        self.assertTrue(result["success"])
        self.assertTrue(result["exe_exists"])
        self.assertGreater(result["exe_size"], 0)
        self.assertIn("exe_size_mb", result)

    def test_detect_with_all_files(self):
        """完整文件检测"""
        exe_path = os.path.join(self.tmpdir, "Sango7.exe")
        with open(exe_path, "wb") as f:
            f.write(b"MZ" + b"\x00" * 1024)
        for fname in self.detector.REQUIRED_FILES:
            with open(os.path.join(self.tmpdir, fname), "wb") as f:
                f.write(b"\x00" * 100)
        for d in self.detector.REQUIRED_DIRS:
            os.makedirs(os.path.join(self.tmpdir, d), exist_ok=True)
        result = self.detector.detect()
        self.assertTrue(result["success"])
        self.assertEqual(len(result["missing_files"]), 0)
        self.assertEqual(len(result["missing_dirs"]), 0)
        self.assertEqual(result["integrity_score"], 100)

    def test_hash_file_md5(self):
        """MD5哈希计算"""
        exe_path = os.path.join(self.tmpdir, "test.bin")
        with open(exe_path, "wb") as f:
            f.write(b"hello world")
        h = self.detector._hash_file(exe_path, "md5")
        self.assertEqual(len(h), 32)

    def test_hash_file_sha256(self):
        """SHA256哈希计算"""
        exe_path = os.path.join(self.tmpdir, "test.bin")
        with open(exe_path, "wb") as f:
            f.write(b"hello world")
        h = self.detector._hash_file(exe_path, "sha256")
        self.assertEqual(len(h), 64)

    def test_required_files_list(self):
        """必需文件列表不为空"""
        self.assertGreater(len(self.detector.REQUIRED_FILES), 0)
        self.assertIn("Sango7.exe", self.detector.REQUIRED_FILES)

    def test_required_dirs_list(self):
        """必需目录列表不为空"""
        self.assertGreater(len(self.detector.REQUIRED_DIRS), 0)
        self.assertIn("Setting", self.detector.REQUIRED_DIRS)


if __name__ == "__main__":
    unittest.main(verbosity=2)