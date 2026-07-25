"""
San7ModMaker SaveEditor 模块测试
覆盖 SaveEditor 类的所有关键方法
"""
import os
import sys
import unittest
import tempfile
import shutil
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSaveEditor(unittest.TestCase):
    """验证存档编辑器 SaveEditor"""

    def setUp(self):
        from core.save_editor import SaveEditor
        self.tmpdir = tempfile.mkdtemp()
        self.save_dir = os.path.join(self.tmpdir, "Save")
        os.makedirs(self.save_dir, exist_ok=True)
        self.editor = SaveEditor(self.tmpdir)
        self.editor_no_path = SaveEditor()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_customgen(self, count=1):
        """创建测试用的 CustomGen.sav

        格式: magic(4B) + count(4B) + 每个武将: id_len(1B) + id + b"0" + 200零字节
        """
        data = struct.pack("<I", 0x0C11F84E)
        data += struct.pack("<I", count)
        for i in range(count):
            gid = f"NWJ{i}"
            gid_bytes = gid.encode("gbk")
            data += bytes([len(gid_bytes)])
            data += gid_bytes
            data += b"0"
            data += b'\x00' * 200
        path = os.path.join(self.save_dir, "CustomGen.sav")
        with open(path, "wb") as f:
            f.write(data)
        return path

    def _create_scenario_save(self, index=0):
        """创建测试用的 SG7-XX.sav"""
        name = f"SG7-{index:02d}.sav"
        path = os.path.join(self.save_dir, name)
        with open(path, "wb") as f:
            f.write(b"SG7" + b'\x00' * 100)
        return path

    # ============================================================
    # 初始化测试
    # ============================================================

    def test_init_no_path(self):
        """无参数初始化，game_path 为 None，save_dir 为空"""
        from core.save_editor import SaveEditor
        editor = SaveEditor()
        self.assertIsNone(editor.game_path)
        self.assertEqual(editor.save_dir, "")

    def test_init_with_path(self):
        """带路径初始化，game_path 和 save_dir 正确设置"""
        self.assertEqual(self.editor.game_path, self.tmpdir)
        self.assertEqual(self.editor.save_dir, self.save_dir)

    def test_set_game_path(self):
        """set_game_path 正确更新 game_path 和 save_dir"""
        new_path = os.path.join(self.tmpdir, "NewGame")
        self.editor.set_game_path(new_path)
        self.assertEqual(self.editor.game_path, new_path)
        self.assertEqual(self.editor.save_dir, os.path.join(new_path, "Save"))

    # ============================================================
    # 常量测试
    # ============================================================

    def test_constants(self):
        """验证所有类常量"""
        from core.save_editor import SaveEditor
        self.assertEqual(SaveEditor.SAVE_EXT, ".sav")
        self.assertEqual(SaveEditor.CUSTOM_GEN, "CustomGen.sav")
        self.assertEqual(SaveEditor.SCENARIO_SAVE, "SG7-{:02d}.sav")
        self.assertEqual(SaveEditor.CUSTOMGEN_MAGIC, 0x0C11F84E)

    # ============================================================
    # list_saves 测试
    # ============================================================

    def test_list_saves_empty(self):
        """空目录返回空列表"""
        from core.save_editor import SaveEditor
        empty_dir = os.path.join(self.tmpdir, "EmptySave")
        os.makedirs(empty_dir, exist_ok=True)
        editor = SaveEditor()
        editor.save_dir = empty_dir
        result = editor.list_saves()
        self.assertEqual(result, [])

    def test_list_saves_with_files(self):
        """有 .sav 文件时返回正确列表"""
        for i in range(3):
            path = os.path.join(self.save_dir, f"test_{i}.sav")
            with open(path, "wb") as f:
                f.write(b'\x00' * 100)
        result = self.editor.list_saves()
        self.assertEqual(len(result), 3)
        names = [s["name"] for s in result]
        for i in range(3):
            self.assertIn(f"test_{i}.sav", names)

    def test_list_saves_with_customgen(self):
        """CustomGen.sav 被识别为 custom_general 类型"""
        self._create_customgen()
        result = self.editor.list_saves()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "custom_general")
        self.assertEqual(result[0]["name"], "CustomGen.sav")

    def test_list_saves_with_scenario(self):
        """SG7-00.sav 被识别为 scenario 类型"""
        self._create_scenario_save(0)
        result = self.editor.list_saves()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "scenario")
        self.assertEqual(result[0]["name"], "SG7-00.sav")

    # ============================================================
    # load_save 测试
    # ============================================================

    def test_load_save_no_game_path(self):
        """未设置游戏目录时返回错误"""
        result = self.editor_no_path.load_save("test.sav")
        self.assertFalse(result["success"])
        self.assertIn("游戏目录", result["message"])

    def test_load_save_not_exist(self):
        """存档不存在时返回错误"""
        result = self.editor.load_save("nonexistent.sav")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    def test_load_save_customgen(self):
        """正确加载 CustomGen.sav 并识别魔数"""
        self._create_customgen()
        result = self.editor.load_save("CustomGen.sav")
        self.assertTrue(result["success"])
        self.assertEqual(result["name"], "CustomGen.sav")
        self.assertGreater(result["size"], 0)
        info = result["info"]
        self.assertEqual(info["type"], "custom_general")
        self.assertTrue(info["is_customgen"])
        self.assertEqual(info["raw_structure"]["declared_count"], 1)
        self.assertTrue(info["raw_structure"]["is_known_magic"])

    def test_load_save_scenario(self):
        """正确加载 SG7 剧本存档"""
        self._create_scenario_save(0)
        result = self.editor.load_save("SG7-00.sav")
        self.assertTrue(result["success"])
        self.assertEqual(result["info"]["type"], "scenario")
        self.assertIn("剧本存档", result["info"]["description"])

    # ============================================================
    # hex_view 测试
    # ============================================================

    def test_hex_view_no_game_path(self):
        """未设置游戏目录时返回错误"""
        result = self.editor_no_path.hex_view("test.sav")
        self.assertFalse(result["success"])
        self.assertIn("游戏目录", result["message"])

    def test_hex_view_not_exist(self):
        """存档不存在时返回错误"""
        result = self.editor.hex_view("nonexistent.sav")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    def test_hex_view_valid(self):
        """有效存档返回正确十六进制数据"""
        self._create_customgen()
        result = self.editor.hex_view("CustomGen.sav", offset=0, length=64)
        self.assertTrue(result["success"])
        self.assertEqual(result["offset"], 0)
        self.assertGreater(len(result["hex_lines"]), 0)
        self.assertIn("raw_hex", result)
        self.assertGreater(result["total_size"], 0)

    # ============================================================
    # hex_search 测试
    # ============================================================

    def test_hex_search_no_game_path(self):
        """未设置游戏目录时返回错误"""
        result = self.editor_no_path.hex_search("test.sav", "4EF8110C")
        self.assertFalse(result["success"])
        self.assertIn("游戏目录", result["message"])

    def test_hex_search_valid(self):
        """搜索已知魔数模式返回正确结果"""
        self._create_customgen()
        # 搜索 CustomGen 魔数 4E F8 11 0C
        result = self.editor.hex_search("CustomGen.sav", "4EF8110C")
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["match_count"], 1)

    def test_hex_search_invalid_pattern(self):
        """无效十六进制模式返回错误"""
        self._create_customgen()
        result = self.editor.hex_search("CustomGen.sav", "ZZZZ")
        self.assertFalse(result["success"])
        self.assertIn("无效", result["message"])

    # ============================================================
    # parse_customgen 测试
    # ============================================================

    def test_parse_customgen_empty(self):
        """无 save_dir 时返回空列表"""
        result = self.editor_no_path.parse_customgen()
        self.assertEqual(result, [])

    def test_parse_customgen_valid(self):
        """解析有效 CustomGen.sav 返回武将列表"""
        self._create_customgen()
        result = self.editor.parse_customgen()
        self.assertGreaterEqual(len(result), 1)
        self.assertIn("Name", result[0])
        self.assertIn("index", result[0])
        self.assertIn("offset", result[0])
        self.assertIn("size", result[0])

    # ============================================================
    # add_customgen 测试
    # ============================================================

    def test_add_customgen_new_file(self):
        """无现有文件时创建新 CustomGen.sav"""
        result = self.editor.add_customgen("测试武将")
        self.assertTrue(result["success"])
        self.assertIn("count", result)
        self.assertEqual(result["count"], 1)
        sav_path = os.path.join(self.save_dir, "CustomGen.sav")
        self.assertTrue(os.path.exists(sav_path))

    def test_add_customgen_existing(self):
        """向已有 CustomGen.sav 追加武将"""
        self._create_customgen(count=1)
        result = self.editor.add_customgen("新武将")
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)

    # ============================================================
    # clone_custom_general 测试
    # ============================================================

    def test_clone_custom_general(self):
        """克隆自定义武将"""
        self._create_customgen(count=1)
        result = self.editor.clone_custom_general("CustomGen.sav", 0, clone_count=2)
        self.assertTrue(result["success"])
        self.assertEqual(result["new_count"], 3)

    # ============================================================
    # save_save / backup / restore 测试
    # ============================================================

    def test_save_save(self):
        """保存存档数据"""
        test_data = b"test save data content"
        result = self.editor.save_save("test_save.sav", test_data)
        self.assertTrue(result["success"])
        sav_path = os.path.join(self.save_dir, "test_save.sav")
        self.assertTrue(os.path.exists(sav_path))
        with open(sav_path, "rb") as f:
            self.assertEqual(f.read(), test_data)

    def test_backup_save(self):
        """创建存档备份"""
        sav_path = os.path.join(self.save_dir, "test_backup.sav")
        with open(sav_path, "wb") as f:
            f.write(b"original data")
        result = self.editor.backup_save("test_backup.sav")
        self.assertTrue(result["success"])
        backups = [f for f in os.listdir(self.save_dir) if f.endswith(".bak")]
        self.assertGreaterEqual(len(backups), 1)

    def test_restore_backup(self):
        """从备份恢复存档"""
        sav_path = os.path.join(self.save_dir, "test_restore.sav")
        with open(sav_path, "wb") as f:
            f.write(b"original data")
        backup_result = self.editor.backup_save("test_restore.sav")
        self.assertTrue(backup_result["success"])
        # 修改原文件
        with open(sav_path, "wb") as f:
            f.write(b"modified data")
        # 找到备份文件
        backups = [f for f in os.listdir(self.save_dir)
                   if f.endswith(".bak") and "test_restore" in f]
        self.assertTrue(len(backups) > 0)
        backup_name = backups[0]
        # 恢复
        result = self.editor.restore_backup("test_restore.sav", backup_name)
        self.assertTrue(result["success"])
        with open(sav_path, "rb") as f:
            self.assertEqual(f.read(), b"original data")

    # ============================================================
    # get_save_info 测试
    # ============================================================

    def test_get_save_info(self):
        """返回存档系统信息"""
        self._create_customgen()
        info = self.editor.get_save_info()
        self.assertEqual(info["save_dir"], self.save_dir)
        self.assertTrue(info["exists"])
        self.assertTrue(info["custom_gen_exists"])
        self.assertGreaterEqual(info["count"], 1)
        self.assertEqual(len(info["saves"]), info["count"])

    # ============================================================
    # 内部方法测试
    # ============================================================

    def test_find_all(self):
        """_find_all 正确查找所有匹配位置"""
        from core.save_editor import SaveEditor
        editor = SaveEditor()
        data = b"ABABABAB"
        positions = editor._find_all(data, b"AB")
        self.assertEqual(len(positions), 4)
        self.assertEqual(positions, [0, 2, 4, 6])
        # 无匹配
        positions2 = editor._find_all(data, b"ZZ")
        self.assertEqual(positions2, [])

    def test_find_next_nwj(self):
        """_find_next_nwj 正确查找 NWJ 标记"""
        from core.save_editor import SaveEditor
        editor = SaveEditor()
        # 0x03 前缀
        data1 = b'\x00' * 10 + b'\x03NWJ' + b'\x00' * 10
        pos1 = editor._find_next_nwj(data1, 0)
        self.assertEqual(pos1, 10)
        # 0x04 前缀
        data2 = b'\x00' * 5 + b'\x04NWJ' + b'\x00' * 5
        pos2 = editor._find_next_nwj(data2, 0)
        self.assertEqual(pos2, 5)
        # 无 NWJ 标记
        data3 = b'\x00' * 20
        pos3 = editor._find_next_nwj(data3, 0)
        self.assertEqual(pos3, -1)

    def test_parse_customgen_v2(self):
        """_parse_customgen_v2 正确解析 CustomGen v2 格式"""
        from core.save_editor import SaveEditor
        editor = SaveEditor()
        # 使用指定格式创建测试数据
        data = struct.pack("<I", 0x0C11F84E)
        data += struct.pack("<I", 1)
        data += bytes([3]) + b"NWJ" + b"0" + b'\x00' * 200
        result = editor._parse_customgen_v2(data)
        self.assertEqual(result["format_version"], "v2")
        self.assertEqual(result["general_count"], 1)
        self.assertEqual(result["raw_structure"]["declared_count"], 1)
        self.assertTrue(result["raw_structure"]["is_known_magic"])
        self.assertEqual(result["raw_structure"]["magic"], "0x0C11F84E")
        self.assertEqual(len(result["generals"]), 1)
        self.assertEqual(result["generals"][0]["id"], "NWJ")


if __name__ == "__main__":
    unittest.main(verbosity=2)