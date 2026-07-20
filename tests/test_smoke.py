"""
San7ModMaker 核心模块 Smoke Test
验证所有核心模块可导入且基本功能正常
"""
import os
import sys
import unittest
import tempfile
import shutil

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCoreImports(unittest.TestCase):
    """验证所有核心模块可导入"""

    def test_import_ini_parser(self):
        from core.ini_parser import IniParser
        self.assertTrue(callable(IniParser))

    def test_import_backup_mgr(self):
        from core.backup_mgr import BackupManager
        self.assertTrue(callable(BackupManager))

    def test_import_validator(self):
        from core.validator import DataValidator
        self.assertTrue(callable(DataValidator))

    def test_import_encoding_converter(self):
        from core.encoding_converter import EncodingConverter
        self.assertTrue(callable(EncodingConverter))

    def test_import_pck_manager(self):
        from core.pck_manager import PckManager
        self.assertTrue(callable(PckManager))

    def test_import_save_manager(self):
        from core.save_manager import SaveManager
        self.assertTrue(callable(SaveManager))

    def test_import_scriptso_analyzer(self):
        from core.scriptso_analyzer import ScriptSOAnalyzer
        self.assertTrue(callable(ScriptSOAnalyzer))

    def test_import_custom_leader(self):
        from core.custom_leader import CustomLeader, CustomLeaderParser
        self.assertTrue(callable(CustomLeader))
        self.assertTrue(callable(CustomLeaderParser))

    def test_import_shp_converter(self):
        from core.shp_converter import ShpConverter
        self.assertTrue(callable(ShpConverter))


class TestIniParser(unittest.TestCase):
    """验证 INI 解析器核心功能"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_basic_parse(self):
        from core.ini_parser import IniParser
        path = os.path.join(self.tmpdir, "test.ini")
        with open(path, "w", encoding="big5") as f:
            f.write("[GENERAL]\nNo = 1\nName = 測試\n")
        parser = IniParser(path)
        parser.load()
        self.assertGreaterEqual(len(parser.sections), 1)
        self.assertEqual(parser.sections[0].name, "GENERAL")

    def test_encoding_detection_big5(self):
        from core.ini_parser import IniParser
        path = os.path.join(self.tmpdir, "test_big5.ini")
        with open(path, "w", encoding="big5") as f:
            f.write("[GENERAL]\nNo = 1\nName = 關羽\n")
        parser = IniParser(path)
        parser.load()
        self.assertGreaterEqual(len(parser.sections), 1)

    def test_save_and_reload(self):
        from core.ini_parser import IniParser
        path = os.path.join(self.tmpdir, "test_save.ini")
        with open(path, "w", encoding="big5") as f:
            f.write("[GENERAL]\nNo = 1\nName = 測試\n")
        parser = IniParser(path)
        parser.load()
        parser.save()
        self.assertTrue(os.path.exists(path))
        # 验证原子写入没有留下 .tmp 文件
        tmp_files = [f for f in os.listdir(self.tmpdir) if f.endswith('.tmp')]
        self.assertEqual(len(tmp_files), 0)

    def test_comment_preservation(self):
        from core.ini_parser import IniParser
        path = os.path.join(self.tmpdir, "test_comment.ini")
        content = "; 這是註解\n[GENERAL]\nNo = 1\nName = 測試\n"
        with open(path, "w", encoding="big5") as f:
            f.write(content)
        parser = IniParser(path)
        parser.load()
        parser.save()
        with open(path, "r", encoding="big5") as f:
            saved = f.read()
        self.assertIn("; 這是註解", saved)


class TestBackupManager(unittest.TestCase):
    """验证备份管理器"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.backup_dir = os.path.join(self.tmpdir, "backup")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_backup_create(self):
        from core.backup_mgr import BackupManager
        bm = BackupManager(self.backup_dir)
        test_file = os.path.join(self.tmpdir, "test.dat")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("test data")
        result = bm.backup_file(test_file)
        self.assertTrue(result)
        count = bm.get_backup_count()
        self.assertGreaterEqual(count, 1)

    def test_backup_restore(self):
        from core.backup_mgr import BackupManager
        bm = BackupManager(self.backup_dir)
        test_file = os.path.join(self.tmpdir, "test_restore.dat")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("original")
        bm.backup_file(test_file)
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("modified")
        history = bm.get_backup_history(test_file)
        self.assertTrue(history)
        bm.restore_file(test_file, 0)
        with open(test_file, "r", encoding="utf-8") as f:
            restored = f.read()
        self.assertEqual(restored, "original")


class TestEncodingConverter(unittest.TestCase):
    """验证编码转换器"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_detect_big5(self):
        from core.encoding_converter import EncodingConverter
        ec = EncodingConverter()
        path = os.path.join(self.tmpdir, "big5_test.txt")
        with open(path, "w", encoding="big5") as f:
            f.write("關羽")
        result = ec.detect_encoding(path)
        self.assertTrue(result["success"])
        self.assertIn(result["encoding"].lower(), ["big5", "big5-tw", "cp950"])

    def test_big5_to_gbk_conversion(self):
        from core.encoding_converter import EncodingConverter
        ec = EncodingConverter()
        path = os.path.join(self.tmpdir, "big5_convert.txt")
        with open(path, "w", encoding="big5") as f:
            f.write("關羽")
        result = ec.convert_file(path, "big5", "gbk")
        self.assertTrue(result["success"])


class TestAtomicWrite(unittest.TestCase):
    """验证原子写入函数"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_atomic_write_no_tmp_leftover(self):
        from main import atomic_write
        path = os.path.join(self.tmpdir, "atomic_test.txt")
        atomic_write(path, "hello world", encoding="utf-8")
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "hello world")
        # 确保没有残留 .tmp 文件
        tmp_files = [f for f in os.listdir(self.tmpdir) if f.endswith('.tmp')]
        self.assertEqual(len(tmp_files), 0)

    def test_atomic_write_overwrite(self):
        from main import atomic_write
        path = os.path.join(self.tmpdir, "atomic_overwrite.txt")
        atomic_write(path, "first", encoding="utf-8")
        atomic_write(path, "second", encoding="utf-8")
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "second")


class TestDataValidator(unittest.TestCase):
    """验证数据校验器"""

    def test_duplicate_id_detection(self):
        from core.validator import DataValidator
        dv = DataValidator()
        duplicate = dv.check_duplicate_ids(
            [{"No": 1, "Name": "A"}, {"No": 1, "Name": "B"}],
            "GENERAL"
        )
        self.assertTrue(len(duplicate) > 0)

    def test_no_duplicate(self):
        from core.validator import DataValidator
        dv = DataValidator()
        duplicate = dv.check_duplicate_ids(
            [{"No": 1, "Name": "A"}, {"No": 2, "Name": "B"}],
            "GENERAL"
        )
        self.assertEqual(len(duplicate), 0)

    def test_value_range(self):
        from core.validator import DataValidator
        dv = DataValidator()
        issues = dv.check_value_ranges(
            [{"No": 1, "WStr": 999}, {"No": 2, "WStr": 50}],
            "GENERAL"
        )
        for issue in issues:
            if "WStr" in str(issue):
                self.assertIn("999", str(issue))


if __name__ == "__main__":
    unittest.main(verbosity=2)