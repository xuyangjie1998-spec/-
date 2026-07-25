"""
San7ModMaker 存档解析器测试套件
覆盖 SaveParser 核心路径：加载/解析/武将搜索/扩展字段/装备解析
"""
import os
import sys
import unittest
import tempfile
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSaveParser(unittest.TestCase):
    """存档解析器测试"""

    @classmethod
    def setUpClass(cls):
        from core.save_parser import SaveParser
        cls.SaveParser = SaveParser

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.parser = self.SaveParser()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_save(self, data: bytes) -> str:
        """创建测试存档文件"""
        path = os.path.join(self.tmpdir, "SG7-001.sav")
        with open(path, "wb") as f:
            f.write(data)
        return path

    def _create_mock_general_data(self, offset: int = 0x200) -> bytes:
        """创建模拟武将数据块"""
        data = bytearray(4096)
        # 武将数量=1
        struct.pack_into("<I", data, offset, 1)
        gen_start = offset + 4
        # 基本武力=99
        struct.pack_into("<I", data, gen_start, 99)
        # 基本智力=85
        struct.pack_into("<I", data, gen_start + 4, 85)
        # 最大体力=300
        struct.pack_into("<I", data, gen_start + 8, 300)
        # 当前体力=280
        struct.pack_into("<I", data, gen_start + 12, 280)
        # 最大技力=150
        struct.pack_into("<I", data, gen_start + 16, 150)
        # 当前技力=120
        struct.pack_into("<I", data, gen_start + 20, 120)
        # 义理=80
        struct.pack_into("<I", data, gen_start + 24, 80)
        # 相性=50
        struct.pack_into("<I", data, gen_start + 28, 50)
        # 士气=90
        struct.pack_into("<I", data, gen_start + 32, 90)
        return bytes(data)

    # ============================================================
    # 基础功能
    # ============================================================

    def test_import(self):
        """模块可导入"""
        from core.save_parser import SaveParser
        self.assertTrue(callable(SaveParser))

    def test_init(self):
        """初始化正常"""
        self.assertEqual(self.parser._data, b"")
        self.assertEqual(self.parser._save_name, "")

    def test_load_bytes(self):
        """从字节加载"""
        result = self.parser.load_bytes(b"TEST_DATA", "test.sav")
        self.assertTrue(result["success"])
        self.assertEqual(result["size"], 9)
        self.assertEqual(result["name"], "test.sav")

    def test_load_file(self):
        """从文件加载"""
        path = self._create_save(b"SG7S_TEST_DATA")
        result = self.parser.load(path)
        self.assertTrue(result["success"])
        self.assertGreater(result["size"], 0)

    def test_load_nonexistent(self):
        """加载不存在的文件"""
        result = self.parser.load("/nonexistent/path.sav")
        self.assertFalse(result["success"])

    # ============================================================
    # 武将搜索
    # ============================================================

    def test_find_generals_by_stat(self):
        """按武力+智力精确搜索武将"""
        mock = self._create_mock_general_data()
        self.parser.load_bytes(mock, "test.sav")
        generals = self.parser.find_generals(wstr=99, intelligence=85)
        self.assertGreaterEqual(len(generals), 1)
        gen = generals[0]
        self.assertEqual(gen["wstr"], 99)
        self.assertEqual(gen["intelligence"], 85)

    def test_find_generals_scan(self):
        """扫描模式搜索武将"""
        mock = self._create_mock_general_data()
        self.parser.load_bytes(mock, "test.sav")
        generals = self.parser.find_generals()
        self.assertGreaterEqual(len(generals), 1)

    def test_find_generals_empty(self):
        """空数据无武将"""
        self.parser.load_bytes(b"", "empty.sav")
        generals = self.parser.find_generals()
        self.assertEqual(len(generals), 0)

    def test_find_generals_none_match(self):
        """无匹配的武力智力"""
        mock = self._create_mock_general_data()
        self.parser.load_bytes(mock, "test.sav")
        generals = self.parser.find_generals(wstr=1, intelligence=1)
        self.assertEqual(len(generals), 0)

    # ============================================================
    # 武将属性解析
    # ============================================================

    def test_parse_general_basic_stats(self):
        """解析武将基本属性"""
        mock = self._create_mock_general_data()
        self.parser.load_bytes(mock, "test.sav")
        generals = self.parser.find_generals(wstr=99, intelligence=85)
        self.assertGreaterEqual(len(generals), 1)
        gen = generals[0]
        self.assertEqual(gen["max_hp"], 300)
        self.assertEqual(gen["cur_hp"], 280)
        self.assertEqual(gen["max_mp"], 150)
        self.assertEqual(gen["cur_mp"], 120)
        self.assertEqual(gen["loyal"], 80)
        self.assertEqual(gen["relation"], 50)
        self.assertEqual(gen["morale"], 90)

    def test_parse_general_has_offset(self):
        """解析结果包含偏移量"""
        mock = self._create_mock_general_data()
        self.parser.load_bytes(mock, "test.sav")
        generals = self.parser.find_generals(wstr=99, intelligence=85)
        self.assertGreaterEqual(len(generals), 1)
        self.assertIn("offset", generals[0])

    # ============================================================
    # 边界情况
    # ============================================================

    def test_invalid_stat_range(self):
        """超出合理范围的武力值不匹配"""
        data = bytearray(4096)
        # 写入超出范围的武力（>999）
        struct.pack_into("<I", data, 0x200, 4)
        struct.pack_into("<I", data, 0x204, 1)
        struct.pack_into("<I", data, 0x208, 10000)  # 超出范围
        struct.pack_into("<I", data, 0x20C, 100)
        # ...更多字段
        self.parser.load_bytes(bytes(data), "test.sav")
        generals = self.parser.find_generals(wstr=10000, intelligence=100)
        # 应被基本检查过滤
        self.assertEqual(len(generals), 0)

    def test_truncated_data(self):
        """截断数据不崩溃"""
        self.parser.load_bytes(b"\x01\x02", "truncated.sav")
        generals = self.parser.find_generals()
        self.assertEqual(len(generals), 0)

    def test_large_data(self):
        """大数据量不崩溃"""
        large = bytearray(1024 * 1024)  # 1MB
        self.parser.load_bytes(bytes(large), "large.sav")
        generals = self.parser.find_generals()
        # 大数据量扫描可能产生一些结果，但不应崩溃
        self.assertIsInstance(generals, list)

    # ============================================================
    # 数据表常量
    # ============================================================

    def test_soldier_types(self):
        """兵种类型表完整"""
        st = self.SaveParser.SOLDIER_TYPES
        self.assertGreater(len(st), 20)
        self.assertIn(0x01, st)
        self.assertEqual(st[0x01], "轻步兵")

    def test_weapon_types(self):
        """武器类型表完整"""
        wt = self.SaveParser.WEAPON_TYPES
        self.assertGreater(len(wt), 30)
        self.assertIn(1, wt)
        self.assertEqual(wt[1], "直剑")

    def test_horse_types(self):
        """坐骑类型表完整"""
        ht = self.SaveParser.HORSE_TYPES
        self.assertGreater(len(ht), 10)
        self.assertIn(1, ht)
        self.assertEqual(ht[1], "黄鬃马")

    def test_item_types(self):
        """道具类型表完整"""
        it = self.SaveParser.ITEM_TYPES
        self.assertGreater(len(it), 20)
        self.assertIn(1, it)

    def test_formation_types(self):
        """阵型类型表完整"""
        ft = self.SaveParser.FORMATION_TYPES
        self.assertGreaterEqual(len(ft), 16)
        self.assertEqual(ft[0], "方形阵")

    def test_merit_coefficients(self):
        """功勋系数表完整"""
        mc = self.SaveParser.MERIT_COEFFICIENTS
        self.assertGreater(len(mc), 5)
        self.assertIn(0x41, mc)

    def test_mark_pattern(self):
        """装备标记常量"""
        self.assertEqual(self.SaveParser.MARK_PATTERN, b"Mark\x00")


if __name__ == "__main__":
    unittest.main()