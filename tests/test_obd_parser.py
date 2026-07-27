"""
San7ModMaker OBD模型解析器测试套件
覆盖 OBDParser / OBDObject 核心路径：解析/序列化/查询/编辑
"""
import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestOBDObject(unittest.TestCase):
    """OBDObject 单元测试"""

    @classmethod
    def setUpClass(cls):
        from core.obd_parser import OBDObject
        cls.OBDObject = OBDObject

    def test_init(self):
        """初始化默认值"""
        obj = self.OBDObject()
        self.assertEqual(obj.name, "")
        self.assertEqual(obj.sequence, 0)
        self.assertEqual(obj.space, (0, 0, 0))
        self.assertEqual(obj.directory, "")
        self.assertEqual(obj.sprites, {})
        self.assertEqual(obj.extra, {})

    def test_get_obj_id(self):
        """从Sequence提取ObjID"""
        obj = self.OBDObject()
        obj.sequence = 70069
        self.assertEqual(obj.get_obj_id(), 69)

    def test_get_obj_id_zero(self):
        """Sequence=0"""
        obj = self.OBDObject()
        obj.sequence = 0
        self.assertEqual(obj.get_obj_id(), 0)

    def test_get_sprite(self):
        """获取Sprite"""
        obj = self.OBDObject()
        obj.sprites["Walk"] = ["file.shp", "8", "0"]
        sprite = obj.get_sprite("Walk")
        self.assertEqual(sprite, ["file.shp", "8", "0"])

    def test_get_sprite_none(self):
        """获取不存在的Sprite"""
        obj = self.OBDObject()
        self.assertIsNone(obj.get_sprite("Nonexistent"))

    def test_set_sprite(self):
        """设置Sprite"""
        obj = self.OBDObject()
        obj.set_sprite("Atk01", ["atk.shp", "10", "0"])
        self.assertIn("Atk01", obj.sprites)
        self.assertEqual(obj.sprites["Atk01"], ["atk.shp", "10", "0"])

    def test_to_dict(self):
        """序列化为字典"""
        obj = self.OBDObject()
        obj.name = "TestSoldier"
        obj.sequence = 70001
        obj.space = (10, 20, 30)
        obj.directory = r"\BFObj\BFSoldier\001"
        obj.sprites["Wait1"] = ["wait.shp", "4", "0"]
        obj.extra["Shadow"] = "1"

        d = obj.to_dict()
        self.assertEqual(d["name"], "TestSoldier")
        self.assertEqual(d["sequence"], 70001)
        self.assertEqual(d["space"], [10, 20, 30])
        self.assertEqual(d["obj_id"], 1)
        self.assertIn("Wait1", d["sprites"])
        self.assertEqual(d["extra"]["Shadow"], "1")

    def test_from_dict(self):
        """从字典反序列化"""
        data = {
            "name": "重骑兵",
            "sequence": 70010,
            "space": [0, 0, 0],
            "directory": r"\BFObj\BFSoldier\010",
            "sprites": {"Walk": ["walk.shp", "6", "0"]},
            "extra": {},
        }
        obj = self.OBDObject.from_dict(data)
        self.assertEqual(obj.name, "重骑兵")
        self.assertEqual(obj.sequence, 70010)
        self.assertEqual(obj.space, (0, 0, 0))
        self.assertEqual(obj.get_obj_id(), 10)

    def test_sprite_types(self):
        """Sprite类型常量完整"""
        types = self.OBDObject.SPRITE_TYPES
        self.assertIn("Wait1", types)
        self.assertIn("Walk", types)
        self.assertIn("Atk01", types)
        self.assertIn("Die", types)
        self.assertGreater(len(types), 15)


class TestOBDParser(unittest.TestCase):
    """OBDParser 单元测试"""

    @classmethod
    def setUpClass(cls):
        from core.obd_parser import OBDParser, OBDObject
        cls.OBDParser = OBDParser
        cls.OBDObject = OBDObject

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.obd_dir = os.path.join(self.tmpdir, "Setting", "OBD")
        os.makedirs(self.obd_dir, exist_ok=True)
        self.parser = self.OBDParser(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_obd_file(self, filename: str, content: str):
        """创建测试OBD文件"""
        path = os.path.join(self.obd_dir, filename)
        with open(path, "w", encoding="big5") as f:
            f.write(content)
        return path

    # ============================================================
    # 基础功能
    # ============================================================

    def test_import(self):
        """模块可导入"""
        from core.obd_parser import OBDParser
        self.assertTrue(callable(OBDParser))

    def test_init(self):
        """初始化正常"""
        self.assertEqual(self.parser.game_path, self.tmpdir)
        self.assertEqual(self.parser.obd_dir, self.obd_dir)
        self.assertEqual(self.parser.objects, [])

    def test_set_game_path(self):
        """设置游戏路径"""
        new_path = os.path.join(self.tmpdir, "newgame")
        os.makedirs(os.path.join(new_path, "Setting", "OBD"), exist_ok=True)
        self.parser.set_game_path(new_path)
        self.assertEqual(self.parser.game_path, new_path)

    def test_obd_files_registry(self):
        """OBD文件注册表完整"""
        files = self.OBDParser.OBD_FILES
        essential = ["bfsoldier", "bfgen", "bfevent", "bfspec"]
        for f in essential:
            self.assertIn(f, files)

    # ============================================================
    # 解析
    # ============================================================

    def test_parse_simple(self):
        """解析简单OBD文件"""
        content = """[OBJECT]
Name = TestSoldier
Sequence = 70001
Space = 0, 0, 0
Sprite = Wait1, wait.shp, 4, 0
Sprite = Walk, walk.shp, 6, 0
"""
        self._create_obd_file("BFSoldier.obd", content)
        objects = self.parser.load("bfsoldier")
        self.assertEqual(len(objects), 1)
        obj = objects[0]
        self.assertEqual(obj.name, "TestSoldier")
        self.assertEqual(obj.sequence, 70001)
        self.assertEqual(obj.space, (0, 0, 0))
        self.assertIn("Wait1", obj.sprites)
        self.assertIn("Walk", obj.sprites)

    def test_parse_multiple_objects(self):
        """解析多个对象"""
        content = """[OBJECT]
Name = Soldier1
Sequence = 70001
Space = 0, 0, 0

[OBJECT]
Name = Soldier2
Sequence = 70002
Space = 1, 2, 3
"""
        self._create_obd_file("BFSoldier.obd", content)
        objects = self.parser.load("bfsoldier")
        self.assertEqual(len(objects), 2)
        self.assertEqual(objects[0].name, "Soldier1")
        self.assertEqual(objects[1].name, "Soldier2")

    def test_parse_with_directory(self):
        """解析含Directory的对象"""
        content = """[OBJECT]
Name = General
Sequence = 70001
Space = 0, 0, 0
Directory = \\BFObj\\BFGen\\001
Sprite = Wait1, gen.shp, 4, 0
"""
        self._create_obd_file("BFGen.obd", content)
        objects = self.parser.load("bfgen")
        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0].directory, r"\BFObj\BFGen\001")

    def test_parse_empty_file(self):
        """解析空文件"""
        self._create_obd_file("BFSoldier.obd", "")
        objects = self.parser.load("bfsoldier")
        self.assertEqual(len(objects), 0)

    def test_parse_nonexistent_file(self):
        """解析不存在的文件"""
        objects = self.parser.load("bfsoldier")
        self.assertEqual(len(objects), 0)

    def test_parse_unknown_type(self):
        """未知OBD类型"""
        with self.assertRaises(ValueError):
            self.parser.load("nonexistent")

    def test_parse_with_comments(self):
        """解析含注释的OBD"""
        content = """; This is a comment
[OBJECT]
; Soldier comment
Name = Soldier
Sequence = 70001
Space = 0, 0, 0
"""
        self._create_obd_file("BFSoldier.obd", content)
        objects = self.parser.load("bfsoldier")
        self.assertEqual(len(objects), 1)

    # ============================================================
    # 保存
    # ============================================================

    def test_save_and_reload(self):
        """保存后重新加载一致性"""
        content = """[OBJECT]
Name = Test
Sequence = 70001
Space = 0, 0, 0
Sprite = Wait1, wait.shp, 4, 0
"""
        self._create_obd_file("BFSoldier.obd", content)
        objects = self.parser.load("bfsoldier")
        saved_path = self.parser.save("bfsoldier")
        self.assertTrue(os.path.exists(saved_path))

        # 重新加载
        parser2 = self.OBDParser(self.tmpdir)
        objects2 = parser2.load("bfsoldier")
        self.assertEqual(len(objects2), 1)
        self.assertEqual(objects2[0].name, "Test")
        self.assertEqual(objects2[0].sequence, 70001)

    def test_save_unknown_type(self):
        """保存未知类型"""
        with self.assertRaises(ValueError):
            self.parser.save("nonexistent")

    # ============================================================
    # 查询
    # ============================================================

    def test_get_objects_by_sequence(self):
        """按Sequence查找"""
        content = """[OBJECT]
Name = A
Sequence = 70001
Space = 0, 0, 0

[OBJECT]
Name = B
Sequence = 70002
Space = 0, 0, 0
"""
        self._create_obd_file("BFSoldier.obd", content)
        self.parser.load("bfsoldier")
        results = self.parser.get_objects_by_sequence(70001)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "A")

    def test_get_object_by_obj_id(self):
        """按ObjID查找"""
        content = """[OBJECT]
Name = Soldier69
Sequence = 70069
Space = 0, 0, 0
"""
        self._create_obd_file("BFSoldier.obd", content)
        self.parser.load("bfsoldier")
        obj = self.parser.get_object_by_obj_id(69)
        self.assertIsNotNone(obj)
        self.assertEqual(obj.name, "Soldier69")

    def test_get_object_by_obj_id_not_found(self):
        """ObjID不存在"""
        self._create_obd_file("BFSoldier.obd", "[OBJECT]\nName=A\nSequence=70001\nSpace=0,0,0\n")
        self.parser.load("bfsoldier")
        obj = self.parser.get_object_by_obj_id(99)
        self.assertIsNone(obj)

    def test_get_sprite_types(self):
        """获取所有Sprite类型"""
        content = """[OBJECT]
Name = A
Sequence = 70001
Space = 0, 0, 0
Sprite = Wait1, w.shp, 4, 0
Sprite = Walk, k.shp, 6, 0
Sprite = Atk01, a.shp, 8, 0
"""
        self._create_obd_file("BFSoldier.obd", content)
        self.parser.load("bfsoldier")
        types = self.parser.get_sprite_types()
        self.assertIn("Wait1", types)
        self.assertIn("Walk", types)
        self.assertIn("Atk01", types)

    def test_get_all_sequences(self):
        """获取所有Sequence"""
        content = """[OBJECT]
Name = A
Sequence = 70001
Space = 0, 0, 0

[OBJECT]
Name = B
Sequence = 70005
Space = 0, 0, 0
"""
        self._create_obd_file("BFSoldier.obd", content)
        self.parser.load("bfsoldier")
        seqs = self.parser.get_all_sequences()
        self.assertIn(70001, seqs)
        self.assertIn(70005, seqs)

    def test_find_free_sequence(self):
        """查找空闲Sequence"""
        content = """[OBJECT]
Name = A
Sequence = 70001
Space = 0, 0, 0
"""
        self._create_obd_file("BFSoldier.obd", content)
        self.parser.load("bfsoldier")
        free = self.parser.find_free_sequence(70001)
        self.assertNotEqual(free, 70001)

    def test_find_by_sequence(self):
        """根据Sequence查找"""
        content = """[OBJECT]
Name = Target
Sequence = 70042
Space = 0, 0, 0
"""
        self._create_obd_file("BFSoldier.obd", content)
        self.parser.load("bfsoldier")
        obj = self.parser.find_by_sequence(70042)
        self.assertIsNotNone(obj)
        self.assertEqual(obj.name, "Target")

    def test_find_by_sequence_not_found(self):
        """Sequence不存在"""
        self._create_obd_file("BFSoldier.obd", "[OBJECT]\nName=A\nSequence=70001\nSpace=0,0,0\n")
        self.parser.load("bfsoldier")
        obj = self.parser.find_by_sequence(99999)
        self.assertIsNone(obj)

    def test_to_dict_list(self):
        """导出为字典列表"""
        content = """[OBJECT]
Name = A
Sequence = 70001
Space = 0, 0, 0
"""
        self._create_obd_file("BFSoldier.obd", content)
        self.parser.load("bfsoldier")
        dl = self.parser.to_dict_list()
        self.assertEqual(len(dl), 1)
        self.assertEqual(dl[0]["name"], "A")

    def test_get_info(self):
        """获取OBD信息"""
        info = self.OBDParser.get_info()
        self.assertIn("format", info)
        self.assertIn("files", info)
        self.assertIn("sprite_types", info)

    # ============================================================
    # 边界情况
    # ============================================================

    def test_parse_extra_params(self):
        """解析额外参数"""
        content = """[OBJECT]
Name = Test
Sequence = 70001
Space = 0, 0, 0
Shadow = 1
Weapon = 5
"""
        self._create_obd_file("BFSoldier.obd", content)
        objects = self.parser.load("bfsoldier")
        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0].extra["Shadow"], "1")
        self.assertEqual(objects[0].extra["Weapon"], "5")

    def test_parse_malformed_lines(self):
        """解析异常行不崩溃"""
        content = """[OBJECT]
Name = Test
Sequence = 70001
Space = 0, 0, 0
BadLine
= missing key
Sprite=Walk,walk.shp,6,0
"""
        self._create_obd_file("BFSoldier.obd", content)
        objects = self.parser.load("bfsoldier")
        self.assertEqual(len(objects), 1)
        # 正常行应被解析
        self.assertTrue(objects[0].name == "Test" or "Walk" in objects[0].sprites)


if __name__ == "__main__":
    unittest.main()