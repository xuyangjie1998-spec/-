"""
San7ModMaker SaveManager 模块测试
覆盖 SaveManager 存档管理器的所有关键方法
"""
import os
import sys
import unittest
import tempfile
import shutil
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSaveManager(unittest.TestCase):
    """验证存档管理器 SaveManager"""

    def setUp(self):
        from core.save_manager import SaveManager
        self.tmpdir = tempfile.mkdtemp()
        self.save_dir = os.path.join(self.tmpdir, "Save")
        os.makedirs(self.save_dir, exist_ok=True)
        self.mgr = SaveManager(self.tmpdir)
        self.mgr_no_path = SaveManager()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_save(self, name="SG7-001.sav", size=1024):
        """创建测试存档文件"""
        path = os.path.join(self.save_dir, name)
        with open(path, "wb") as f:
            f.write(b'\x00' * size)
        return path

    def _create_customgen(self):
        """创建测试 CustomGen.sav"""
        path = os.path.join(self.save_dir, "CustomGen.sav")
        with open(path, "wb") as f:
            f.write(b'\x00' * 512)
        return path

    # ============================================================
    # 初始化测试
    # ============================================================

    def test_init_no_path(self):
        """无参数初始化，game_path 为 None"""
        self.assertIsNone(self.mgr_no_path.game_path)
        self.assertIsNone(self.mgr_no_path._backup_dir)

    def test_init_with_path(self):
        """带路径初始化，game_path 正确设置"""
        self.assertEqual(self.mgr.game_path, self.tmpdir)

    def test_set_game_path(self):
        """set_game_path 正确更新 game_path"""
        new_path = os.path.join(self.tmpdir, "NewGame")
        self.mgr.set_game_path(new_path)
        self.assertEqual(self.mgr.game_path, new_path)

    # ============================================================
    # find_save_dir 测试
    # ============================================================

    def test_find_save_dir_exists(self):
        """game_path 下有 Save 目录时返回正确路径"""
        result = self.mgr.find_save_dir()
        self.assertEqual(result, os.path.join(self.tmpdir, "Save"))

    def test_find_save_dir_no_game_path(self):
        """无 game_path 时返回 None（无SAVE_PATHS匹配）"""
        self.mgr_no_path.game_path = None
        result = self.mgr_no_path.find_save_dir()
        # 在测试环境中无常见保存路径，应返回 None
        self.assertIsNone(result)

    def test_find_save_dir_missing_save_dir(self):
        """game_path 下无 Save 目录时返回 None"""
        from core.save_manager import SaveManager
        empty_path = os.path.join(self.tmpdir, "Empty")
        os.makedirs(empty_path, exist_ok=True)
        mgr = SaveManager(empty_path)
        result = mgr.find_save_dir()
        self.assertIsNone(result)

    # ============================================================
    # list_saves 测试
    # ============================================================

    def test_list_saves_empty(self):
        """空存档目录返回空列表"""
        result = self.mgr.list_saves()
        self.assertTrue(result["success"])
        self.assertEqual(result["saves"], [])
        self.assertEqual(result["count"], 0)

    def test_list_saves_with_game_saves(self):
        """包含游戏存档时的列表"""
        self._create_save("SG7-001.sav", 2048)
        self._create_save("SG7-002.sav", 4096)
        result = self.mgr.list_saves()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        saves = result["saves"]
        self.assertEqual(len(saves), 2)
        self.assertEqual(saves[0]["name"], "SG7-001.sav")
        self.assertEqual(saves[0]["type"], "game_save")
        self.assertEqual(saves[0]["slot"], 1)
        self.assertEqual(saves[0]["size_bytes"], 2048)
        self.assertEqual(saves[1]["name"], "SG7-002.sav")
        self.assertEqual(saves[1]["slot"], 2)

    def test_list_saves_with_customgen(self):
        """包含 CustomGen.sav 时的列表"""
        self._create_customgen()
        result = self.mgr.list_saves()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["saves"][0]["name"], "CustomGen.sav")
        self.assertEqual(result["saves"][0]["type"], "custom_gen")
        self.assertEqual(result["saves"][0]["slot"], -1)

    def test_list_saves_mixed(self):
        """混合存档类型列表"""
        self._create_save("SG7-001.sav")
        self._create_customgen()
        self._create_save("SG7-005.sav")
        result = self.mgr.list_saves()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 3)
        types = [s["type"] for s in result["saves"]]
        self.assertIn("game_save", types)
        self.assertIn("custom_gen", types)

    def test_list_saves_ignores_non_sav(self):
        """忽略非存档文件"""
        self._create_save("SG7-001.sav")
        with open(os.path.join(self.save_dir, "readme.txt"), "w") as f:
            f.write("hello")
        with open(os.path.join(self.save_dir, "config.ini"), "w") as f:
            f.write("data")
        result = self.mgr.list_saves()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)

    def test_list_saves_no_save_dir(self):
        """无存档目录时返回失败"""
        self.mgr_no_path.game_path = None
        result = self.mgr_no_path.list_saves()
        self.assertFalse(result["success"])
        self.assertIn("未找到存档目录", result["message"])

    def test_list_saves_slot_parsing(self):
        """slot 解析正确（SG7-XXX 中间三位数字）"""
        self._create_save("SG7-099.sav")
        result = self.mgr.list_saves()
        self.assertTrue(result["success"])
        self.assertEqual(result["saves"][0]["slot"], 99)

    def test_list_saves_invalid_slot(self):
        """非数字 slot 返回 -1"""
        self._create_save("SG7-ABC.sav")
        result = self.mgr.list_saves()
        self.assertTrue(result["success"])
        self.assertEqual(result["saves"][0]["slot"], -1)

    def test_list_saves_has_modified(self):
        """存档包含修改时间戳"""
        self._create_save("SG7-001.sav")
        result = self.mgr.list_saves()
        self.assertTrue(result["success"])
        self.assertIn("modified", result["saves"][0])
        self.assertIsInstance(result["saves"][0]["modified"], str)

    # ============================================================
    # backup_save 测试
    # ============================================================

    def test_backup_save_success(self):
        """备份存档成功"""
        self._create_save("SG7-001.sav", 2048)
        result = self.mgr.backup_save("SG7-001.sav")
        self.assertTrue(result["success"])
        self.assertIn("备份完成", result["message"])
        self.assertTrue(os.path.exists(result["backup_path"]))
        self.assertEqual(result["backup_dir"],
                         os.path.join(self.tmpdir, "SaveBackup"))

    def test_backup_save_creates_dir(self):
        """备份时自动创建备份目录"""
        self._create_save("SG7-001.sav")
        bak_dir = os.path.join(self.tmpdir, "SaveBackup")
        self.assertFalse(os.path.isdir(bak_dir))
        self.mgr.backup_save("SG7-001.sav")
        self.assertTrue(os.path.isdir(bak_dir))

    def test_backup_save_file_not_found(self):
        """备份不存在的存档返回失败"""
        result = self.mgr.backup_save("SG7-999.sav")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    def test_backup_save_no_save_dir(self):
        """无存档目录时备份失败"""
        self.mgr_no_path.game_path = None
        result = self.mgr_no_path.backup_save("SG7-001.sav")
        self.assertFalse(result["success"])
        self.assertIn("未找到存档目录", result["message"])

    def test_backup_save_has_timestamp(self):
        """备份文件名包含时间戳"""
        self._create_save("SG7-001.sav")
        result = self.mgr.backup_save("SG7-001.sav")
        bak_name = os.path.basename(result["backup_path"])
        self.assertIn("SG7-001.sav.", bak_name)
        self.assertTrue(bak_name.endswith(".bak"))

    # ============================================================
    # restore_save 测试
    # ============================================================

    def test_restore_save_success(self):
        """从备份还原存档成功"""
        self._create_save("SG7-001.sav", 2048)
        bak = self.mgr.backup_save("SG7-001.sav")
        # 修改原文件
        with open(os.path.join(self.save_dir, "SG7-001.sav"), "wb") as f:
            f.write(b'\xFF' * 1024)
        result = self.mgr.restore_save(bak["backup_path"], "SG7-001.sav")
        self.assertTrue(result["success"])
        self.assertIn("还原完成", result["message"])
        # 验证文件已还原
        with open(os.path.join(self.save_dir, "SG7-001.sav"), "rb") as f:
            data = f.read()
        self.assertEqual(len(data), 2048)
        self.assertEqual(data, b'\x00' * 2048)

    def test_restore_save_no_save_dir(self):
        """无存档目录时还原失败"""
        self.mgr_no_path.game_path = None
        result = self.mgr_no_path.restore_save("/tmp/fake.bak", "SG7-001.sav")
        self.assertFalse(result["success"])
        self.assertIn("未找到存档目录", result["message"])

    def test_restore_save_backup_not_found(self):
        """备份文件不存在时还原失败"""
        self._create_save("SG7-001.sav")
        result = self.mgr.restore_save("/tmp/nonexistent.bak", "SG7-001.sav")
        self.assertFalse(result["success"])
        self.assertIn("备份文件不存在", result["message"])

    def test_restore_save_auto_backup_current(self):
        """还原前自动备份当前存档"""
        self._create_save("SG7-001.sav", 2048)
        bak = self.mgr.backup_save("SG7-001.sav")
        # 修改原文件
        with open(os.path.join(self.save_dir, "SG7-001.sav"), "wb") as f:
            f.write(b'\xFF' * 1024)
        self.mgr.restore_save(bak["backup_path"], "SG7-001.sav")
        # 检查备份目录中是否有 restore_ 前缀的备份
        bak_dir = os.path.join(self.tmpdir, "SaveBackup")
        restore_baks = [f for f in os.listdir(bak_dir) if "restore_" in f]
        self.assertGreaterEqual(len(restore_baks), 1)

    # ============================================================
    # list_backups 测试
    # ============================================================

    def test_list_backups_empty(self):
        """无备份时返回空列表"""
        result = self.mgr.list_backups()
        if result["success"]:
            self.assertEqual(result["backups"], [])
            self.assertEqual(result["count"], 0)

    def test_list_backups_with_backups(self):
        """有备份时返回列表"""
        self._create_save("SG7-001.sav")
        self.mgr.backup_save("SG7-001.sav")
        result = self.mgr.list_backups()
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["count"], 1)
        self.assertEqual(result["backups"][0]["orig_name"], "SG7-001.sav")
        self.assertIn("size_kb", result["backups"][0])
        self.assertIn("modified", result["backups"][0])

    def test_list_backups_no_save_dir(self):
        """无存档目录时返回失败"""
        self.mgr_no_path.game_path = None
        result = self.mgr_no_path.list_backups()
        self.assertFalse(result["success"])
        self.assertIn("未找到存档目录", result["message"])

    # ============================================================
    # delete_backup 测试
    # ============================================================

    def test_delete_backup_success(self):
        """删除备份成功"""
        self._create_save("SG7-001.sav")
        bak = self.mgr.backup_save("SG7-001.sav")
        self.assertTrue(os.path.exists(bak["backup_path"]))
        result = self.mgr.delete_backup(bak["backup_path"])
        self.assertTrue(result["success"])
        self.assertFalse(os.path.exists(bak["backup_path"]))

    def test_delete_backup_not_found(self):
        """删除不存在的备份返回失败"""
        result = self.mgr.delete_backup("/tmp/nonexistent.bak")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    # ============================================================
    # hex_view 测试
    # ============================================================

    def test_hex_view_success(self):
        """十六进制查看成功"""
        data = b'\x00\x01\x02\x03\x04\x05\x06\x07' * 64  # 512 bytes
        path = os.path.join(self.save_dir, "SG7-001.sav")
        with open(path, "wb") as f:
            f.write(data)
        result = self.mgr.hex_view("SG7-001.sav", offset=0, length=256)
        self.assertTrue(result["success"])
        self.assertEqual(result["save_name"], "SG7-001.sav")
        self.assertEqual(result["file_size"], 512)
        self.assertEqual(result["offset"], 0)
        self.assertEqual(result["length"], 256)
        self.assertIn("hex_dump", result)
        self.assertIn("raw_base64", result)

    def test_hex_view_with_offset(self):
        """从指定偏移量查看"""
        data = b'\x00' * 100 + b'\xDE\xAD\xBE\xEF' + b'\x00' * 400
        path = os.path.join(self.save_dir, "SG7-001.sav")
        with open(path, "wb") as f:
            f.write(data)
        result = self.mgr.hex_view("SG7-001.sav", offset=100, length=16)
        self.assertTrue(result["success"])
        self.assertEqual(result["offset"], 100)
        self.assertEqual(result["length"], 16)

    def test_hex_view_offset_exceeds(self):
        """偏移超出文件大小时返回失败"""
        path = os.path.join(self.save_dir, "SG7-001.sav")
        with open(path, "wb") as f:
            f.write(b'\x00' * 100)
        result = self.mgr.hex_view("SG7-001.sav", offset=200, length=256)
        self.assertFalse(result["success"])
        self.assertIn("偏移超出", result["message"])

    def test_hex_view_length_clamped(self):
        """length 超出文件大小时自动截断"""
        path = os.path.join(self.save_dir, "SG7-001.sav")
        with open(path, "wb") as f:
            f.write(b'\x00' * 100)
        result = self.mgr.hex_view("SG7-001.sav", offset=50, length=200)
        self.assertTrue(result["success"])
        self.assertEqual(result["length"], 50)  # 100 - 50

    def test_hex_view_no_save_dir(self):
        """无存档目录时失败"""
        self.mgr_no_path.game_path = None
        result = self.mgr_no_path.hex_view("SG7-001.sav")
        self.assertFalse(result["success"])
        self.assertIn("未找到存档目录", result["message"])

    def test_hex_view_file_not_found(self):
        """存档文件不存在时失败"""
        result = self.mgr.hex_view("SG7-999.sav")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    def test_hex_view_format(self):
        """hex_dump 格式正确（含地址、十六进制、ASCII）"""
        path = os.path.join(self.save_dir, "SG7-001.sav")
        with open(path, "wb") as f:
            f.write(b'ABCDEFGHIJKLMNOP' * 2)
        result = self.mgr.hex_view("SG7-001.sav", offset=0, length=32)
        self.assertTrue(result["success"])
        hex_dump = result["hex_dump"]
        self.assertIn("00000000", hex_dump)  # 起始地址
        self.assertIn("41 42 43", hex_dump)  # 'A'=0x41, 'B'=0x42, 'C'=0x43

    # ============================================================
    # analyze_save_header 测试
    # ============================================================

    def test_analyze_header_success(self):
        """分析存档头成功"""
        header = b'\x00' * 256
        header = b'\x00\x00\x00\x00' + header[4:]  # 全零魔数
        path = os.path.join(self.save_dir, "SG7-001.sav")
        with open(path, "wb") as f:
            f.write(header + b'\x00' * 256)
        result = self.mgr.analyze_save_header("SG7-001.sav")
        self.assertTrue(result["success"])
        self.assertEqual(result["save_name"], "SG7-001.sav")
        self.assertIn("header_magic", result)
        self.assertIn("first_bytes", result)
        self.assertIn("format", result)

    def test_analyze_header_gzip_format(self):
        """检测 GZip 压缩格式"""
        path = os.path.join(self.save_dir, "SG7-001.sav")
        with open(path, "wb") as f:
            f.write(b'\x1f\x8b' + b'\x00' * 254)
        result = self.mgr.analyze_save_header("SG7-001.sav")
        self.assertTrue(result["success"])
        self.assertEqual(result["format"], "GZip压缩")

    def test_analyze_header_zip_format(self):
        """检测 ZIP 压缩格式"""
        path = os.path.join(self.save_dir, "SG7-001.sav")
        with open(path, "wb") as f:
            f.write(b'PK' + b'\x00' * 254)
        result = self.mgr.analyze_save_header("SG7-001.sav")
        self.assertTrue(result["success"])
        self.assertEqual(result["format"], "ZIP压缩")

    def test_analyze_header_zeros_format(self):
        """检测全零原始数据格式"""
        path = os.path.join(self.save_dir, "SG7-001.sav")
        with open(path, "wb") as f:
            f.write(b'\x00\x00\x00\x00' + b'\x00' * 252)
        result = self.mgr.analyze_save_header("SG7-001.sav")
        self.assertTrue(result["success"])
        self.assertEqual(result["format"], "可能是未加密原始数据")

    def test_analyze_header_unknown_format(self):
        """检测未知格式"""
        path = os.path.join(self.save_dir, "SG7-001.sav")
        with open(path, "wb") as f:
            f.write(b'\x01\x02\x03\x04' + b'\x00' * 252)
        result = self.mgr.analyze_save_header("SG7-001.sav")
        self.assertTrue(result["success"])
        self.assertEqual(result["format"], "未知格式（可能是专有二进制）")

    def test_analyze_header_readable_text(self):
        """检测可读文本"""
        path = os.path.join(self.save_dir, "SG7-001.sav")
        with open(path, "wb") as f:
            f.write(b'\x00\x00\x00\x00' + b'ABCD' + b'\x00' * 248)
        result = self.mgr.analyze_save_header("SG7-001.sav")
        self.assertTrue(result["success"])
        self.assertIn("readable_text", result)
        self.assertIn("ABCD", result["readable_text"])

    def test_analyze_header_no_save_dir(self):
        """无存档目录时失败"""
        self.mgr_no_path.game_path = None
        result = self.mgr_no_path.analyze_save_header("SG7-001.sav")
        self.assertFalse(result["success"])
        self.assertIn("未找到存档目录", result["message"])

    def test_analyze_header_file_not_found(self):
        """存档文件不存在时失败"""
        result = self.mgr.analyze_save_header("SG7-999.sav")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    def test_analyze_header_file_size(self):
        """包含正确的文件大小"""
        path = os.path.join(self.save_dir, "SG7-001.sav")
        with open(path, "wb") as f:
            f.write(b'\x00' * 512)
        result = self.mgr.analyze_save_header("SG7-001.sav")
        self.assertTrue(result["success"])
        self.assertEqual(result["file_size"], 512)

    def test_analyze_header_magic_hex(self):
        """header_magic 为大写十六进制"""
        path = os.path.join(self.save_dir, "SG7-001.sav")
        with open(path, "wb") as f:
            f.write(b'\xDE\xAD\xBE\xEF' + b'\x00' * 252)
        result = self.mgr.analyze_save_header("SG7-001.sav")
        self.assertTrue(result["success"])
        self.assertEqual(result["header_magic"], "DEADBEEF")

    # ============================================================
    # SAVE_PATHS 常量测试
    # ============================================================

    def test_save_paths_is_list(self):
        """SAVE_PATHS 是列表"""
        from core.save_manager import SaveManager
        self.assertIsInstance(SaveManager.SAVE_PATHS, list)
        self.assertGreaterEqual(len(SaveManager.SAVE_PATHS), 1)


if __name__ == "__main__":
    unittest.main()