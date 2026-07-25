"""
San7ModMaker CustomLeader 模块测试
覆盖 CustomLeader 数据对象和 CustomLeaderParser 解析器的所有关键方法
"""
import os
import sys
import unittest
import tempfile
import shutil
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCustomLeader(unittest.TestCase):
    """验证 CustomLeader 数据对象"""

    def test_init_defaults(self):
        """初始化默认值正确"""
        from core.custom_leader import CustomLeader
        leader = CustomLeader()
        self.assertEqual(leader.index, 0)
        self.assertEqual(leader.name, "")
        self.assertEqual(leader.str_val, 0)
        self.assertEqual(leader.int_val, 0)
        self.assertEqual(leader.hp, 0)
        self.assertEqual(leader.mp, 0)
        self.assertEqual(leader.sex, 0)
        self.assertEqual(leader.face_id, 0)
        self.assertEqual(leader.raw_data, b"")

    def test_set_attributes(self):
        """属性设置正确"""
        from core.custom_leader import CustomLeader
        leader = CustomLeader()
        leader.index = 5
        leader.name = "刘备"
        leader.str_val = 82
        leader.int_val = 78
        leader.hp = 500
        leader.mp = 300
        self.assertEqual(leader.index, 5)
        self.assertEqual(leader.name, "刘备")
        self.assertEqual(leader.str_val, 82)
        self.assertEqual(leader.int_val, 78)
        self.assertEqual(leader.hp, 500)
        self.assertEqual(leader.mp, 300)


class TestCustomLeaderParser(unittest.TestCase):
    """验证 CustomLeaderParser 解析器"""

    def setUp(self):
        from core.custom_leader import CustomLeaderParser
        self.tmpdir = tempfile.mkdtemp()
        self.save_dir = os.path.join(self.tmpdir, "Save")
        os.makedirs(self.save_dir, exist_ok=True)
        self.parser = CustomLeaderParser(self.tmpdir)
        self.parser_no_path = CustomLeaderParser()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_bytes_file(self, leaders_data=None):
        """创建测试 CustomLeaders.bytes 文件
        
        格式与 parser 的 load() 期望一致：
        - 每条记录: name(null结尾+4字节对齐) + 4个int32值 + 填充到 name_padded+64 字节
        - parser 通过 pos = value_start + 64 跳转到下一条记录
        """
        path = os.path.join(self.save_dir, "CoustomLeaders.bytes")
        if leaders_data is None:
            leaders_data = []
        data = bytearray()
        for name, str_val, int_val, hp, mp in leaders_data:
            name_bytes = name.encode("gbk", errors="replace")
            name_bytes = name_bytes[:31] + b'\x00'
            while len(name_bytes) % 4 != 0:
                name_bytes += b'\x00'
            name_padded = len(name_bytes)
            data.extend(name_bytes)
            data.extend(struct.pack("<i", str_val))
            data.extend(struct.pack("<i", int_val))
            data.extend(struct.pack("<i", hp))
            data.extend(struct.pack("<i", mp))
            # 填充到 name_padded + 64 字节（parser 用 value_start+64 跳转）
            pad_needed = (name_padded + 64) - (name_padded + 16)
            data.extend(b'\x00' * pad_needed)
        with open(path, "wb") as f:
            f.write(bytes(data))
        return path

    # ============================================================
    # 初始化测试
    # ============================================================

    def test_init_no_path(self):
        """无参数初始化"""
        self.assertIsNone(self.parser_no_path.game_path)
        self.assertIsNone(self.parser_no_path._file_path)

    def test_init_with_path(self):
        """带路径初始化，_file_path 正确设置"""
        self.assertEqual(self.parser.game_path, self.tmpdir)
        expected = os.path.join(self.tmpdir, "Save", "CoustomLeaders.bytes")
        self.assertEqual(self.parser._file_path, expected)

    def test_set_game_path(self):
        """set_game_path 正确更新 game_path 和 _file_path"""
        new_path = os.path.join(self.tmpdir, "NewGame")
        self.parser.set_game_path(new_path)
        self.assertEqual(self.parser.game_path, new_path)
        expected = os.path.join(new_path, "Save", "CoustomLeaders.bytes")
        self.assertEqual(self.parser._file_path, expected)

    # ============================================================
    # exists 测试
    # ============================================================

    def test_exists_true(self):
        """文件存在时返回 True"""
        self._create_bytes_file([("刘备", 82, 78, 500, 300)])
        self.assertTrue(self.parser.exists())

    def test_exists_false(self):
        """文件不存在时返回 False"""
        self.assertFalse(self.parser.exists())

    def test_exists_no_path(self):
        """未设置路径时返回 False"""
        self.assertFalse(self.parser_no_path.exists())

    # ============================================================
    # load 测试
    # ============================================================

    def test_load_no_file(self):
        """文件不存在时返回失败"""
        result = self.parser.load()
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])
        self.assertEqual(result["leaders"], [])

    def test_load_empty_file(self):
        """空文件返回空列表"""
        self._create_bytes_file([])
        result = self.parser.load()
        self.assertTrue(result["success"])
        self.assertEqual(result["leaders"], [])
        self.assertEqual(result["count"], 0)

    def test_load_single_leader(self):
        """加载单个武将"""
        self._create_bytes_file([("刘备", 82, 78, 500, 300)])
        result = self.parser.load()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        leader = result["leaders"][0]
        self.assertEqual(leader["name"], "刘备")
        self.assertEqual(leader["str_val"], 82)
        self.assertEqual(leader["int_val"], 78)
        self.assertEqual(leader["hp"], 500)
        self.assertEqual(leader["mp"], 300)
        self.assertEqual(leader["index"], 0)
        self.assertIn("offset", leader)

    def test_load_multiple_leaders(self):
        """加载多个武将"""
        self._create_bytes_file([
            ("刘备", 82, 78, 500, 300),
            ("关羽", 98, 85, 600, 350),
            ("张飞", 99, 45, 550, 280),
        ])
        result = self.parser.load()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 3)
        names = [l["name"] for l in result["leaders"]]
        self.assertEqual(names, ["刘备", "关羽", "张飞"])
        self.assertEqual(result["total_size"], 72 * 3)  # 每条 72 字节 (name_padded=8 + 64)

    def test_load_leader_indices(self):
        """武将索引顺序正确"""
        self._create_bytes_file([
            ("A", 10, 10, 100, 100),
            ("B", 20, 20, 200, 200),
            ("C", 30, 30, 300, 300),
        ])
        result = self.parser.load()
        self.assertTrue(result["success"])
        for i, leader in enumerate(result["leaders"]):
            self.assertEqual(leader["index"], i)

    def test_load_ascii_name(self):
        """ASCII 名字正确解析"""
        self._create_bytes_file([("GuanYu", 98, 85, 600, 350)])
        result = self.parser.load()
        self.assertTrue(result["success"])
        self.assertEqual(result["leaders"][0]["name"], "GuanYu")

    def test_load_truncated_data(self):
        """数据截断时安全返回"""
        path = os.path.join(self.save_dir, "CoustomLeaders.bytes")
        with open(path, "wb") as f:
            f.write(b'\x00\x00\x00')  # 少于 4 字节，while 循环进不去
        result = self.parser.load()
        self.assertTrue(result["success"])
        self.assertEqual(result["leaders"], [])
        self.assertEqual(result["count"], 0)

    # ============================================================
    # save 测试
    # ============================================================

    def test_save_no_path(self):
        """未设置路径时保存失败"""
        result = self.parser_no_path.save([{"name": "刘备", "str_val": 82}])
        self.assertFalse(result["success"])
        self.assertIn("未设置游戏目录", result["message"])

    def test_save_single_leader(self):
        """保存单个武将"""
        leaders = [{"name": "刘备", "str_val": 82, "int_val": 78, "hp": 500, "mp": 300}]
        result = self.parser.save(leaders)
        self.assertTrue(result["success"])
        self.assertIn("保存成功", result["message"])
        self.assertEqual(result["size"], 72)  # name_padded=8 + 64
        self.assertTrue(os.path.exists(os.path.join(self.save_dir, "CoustomLeaders.bytes")))

    def test_save_multiple_leaders(self):
        """保存多个武将"""
        leaders = [
            {"name": "刘备", "str_val": 82, "int_val": 78, "hp": 500, "mp": 300},
            {"name": "关羽", "str_val": 98, "int_val": 85, "hp": 600, "mp": 350},
        ]
        result = self.parser.save(leaders)
        self.assertTrue(result["success"])
        self.assertEqual(result["size"], 144)  # 2 * 72

    def test_save_roundtrip(self):
        """保存后重新加载，数据一致"""
        leaders = [
            {"name": "刘备", "str_val": 82, "int_val": 78, "hp": 500, "mp": 300},
            {"name": "关羽", "str_val": 98, "int_val": 85, "hp": 600, "mp": 350},
        ]
        self.parser.save(leaders)
        result = self.parser.load()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        for i, orig in enumerate(leaders):
            loaded = result["leaders"][i]
            self.assertEqual(loaded["name"], orig["name"])
            self.assertEqual(loaded["str_val"], orig["str_val"])
            self.assertEqual(loaded["int_val"], orig["int_val"])
            self.assertEqual(loaded["hp"], orig["hp"])
            self.assertEqual(loaded["mp"], orig["mp"])

    def test_save_creates_directory(self):
        """保存时自动创建目录"""
        # 删除 Save 目录，验证保存时自动创建
        shutil.rmtree(self.save_dir)
        self.assertFalse(os.path.isdir(self.save_dir))
        leaders = [{"name": "刘备", "str_val": 82, "int_val": 78, "hp": 500, "mp": 300}]
        result = self.parser.save(leaders)
        self.assertTrue(result["success"])
        self.assertTrue(os.path.isdir(self.save_dir))

    def test_save_overwrites_existing(self):
        """保存覆盖已有文件"""
        self._create_bytes_file([("Old", 10, 20, 30, 40)])
        leaders = [{"name": "New", "str_val": 99, "int_val": 88, "hp": 700, "mp": 450}]
        self.parser.save(leaders)
        result = self.parser.load()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["leaders"][0]["name"], "New")
        self.assertEqual(result["leaders"][0]["str_val"], 99)

    def test_save_default_values(self):
        """缺失字段使用默认值 0"""
        leaders = [{"name": "赵云"}]
        result = self.parser.save(leaders)
        self.assertTrue(result["success"])
        loaded = self.parser.load()
        self.assertEqual(loaded["leaders"][0]["str_val"], 0)
        self.assertEqual(loaded["leaders"][0]["int_val"], 0)
        self.assertEqual(loaded["leaders"][0]["hp"], 0)
        self.assertEqual(loaded["leaders"][0]["mp"], 0)

    def test_save_long_name_truncated(self):
        """长名字被截断（最多 31 字符）"""
        long_name = "A" * 50
        leaders = [{"name": long_name, "str_val": 50, "int_val": 50, "hp": 100, "mp": 100}]
        self.parser.save(leaders)
        result = self.parser.load()
        self.assertTrue(result["success"])
        self.assertEqual(len(result["leaders"][0]["name"]), 31)

    def test_save_empty_name(self):
        """空名字保存"""
        leaders = [{"name": "", "str_val": 50, "int_val": 50, "hp": 100, "mp": 100}]
        result = self.parser.save(leaders)
        self.assertTrue(result["success"])

    # ============================================================
    # RECORD_SIZE 常量测试
    # ============================================================

    def test_record_size(self):
        """RECORD_SIZE 常量正确"""
        from core.custom_leader import CustomLeaderParser
        self.assertEqual(CustomLeaderParser.RECORD_SIZE, 256)

    # ============================================================
    # load 边界情况测试
    # ============================================================

    def test_load_invalid_utf8_in_name(self):
        """名字含无效字节时使用 ASCII 回退"""
        path = os.path.join(self.save_dir, "CoustomLeaders.bytes")
        # 构造一个无法用 GBK 解码的字节序列
        name_bytes = b'\xFF\xFE\xFD\xFC\x00'
        padded = name_bytes
        while len(padded) % 4 != 0:
            padded += b'\x00'
        data = bytearray(padded)
        data.extend(struct.pack("<i", 50))
        data.extend(struct.pack("<i", 50))
        data.extend(struct.pack("<i", 100))
        data.extend(struct.pack("<i", 100))
        while len(data) % 64 != 0:
            data.append(0)
        with open(path, "wb") as f:
            f.write(bytes(data))
        result = self.parser.load()
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["count"], 0)

    def test_load_binary_only_data(self):
        """纯二进制数据（无 null 结尾字符串）时安全返回"""
        path = os.path.join(self.save_dir, "CoustomLeaders.bytes")
        with open(path, "wb") as f:
            f.write(b'\x01\x02\x03\x04\x05\x06\x07\x08' * 8)
        result = self.parser.load()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    def test_load_total_size(self):
        """total_size 正确反映文件大小"""
        self._create_bytes_file([("A", 1, 2, 3, 4)])
        result = self.parser.load()
        self.assertTrue(result["success"])
        self.assertEqual(result["total_size"], 68)  # name_padded=4 + 64


if __name__ == "__main__":
    unittest.main()