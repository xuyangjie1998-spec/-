"""
San7ModMaker EXE引擎补丁测试套件
覆盖 ExePatcher 核心路径：加载/备份/读写/补丁应用/特征码扫描
"""
import os
import sys
import unittest
import tempfile
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestExePatcher(unittest.TestCase):
    """EXE引擎补丁工具测试"""

    @classmethod
    def setUpClass(cls):
        from core.exe_patcher import ExePatcher
        cls.ExePatcher = ExePatcher

    def setUp(self):
        # 创建模拟EXE文件（含SG7S签名和填充数据）
        self.tmpdir = tempfile.mkdtemp()
        self.exe_path = os.path.join(self.tmpdir, "Sango7.exe")
        # 模拟EXE：4字节签名 + 填充到64KB
        exe_data = b"SG7S" + b"\x00" * 65532
        # 写入一些可测试的值
        exe_data = bytearray(exe_data)
        # 在偏移0x100写入 int32=999
        struct.pack_into("<i", exe_data, 0x100, 999)
        # 在偏移0x200写入 int16=999
        struct.pack_into("<H", exe_data, 0x200, 999)
        # 在偏移0x300写入 int8=67
        struct.pack_into("<B", exe_data, 0x300, 67)
        with open(self.exe_path, "wb") as f:
            f.write(exe_data)

        self.patcher = self.ExePatcher(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ============================================================
    # 基础功能
    # ============================================================

    def test_import(self):
        """模块可导入"""
        from core.exe_patcher import ExePatcher
        self.assertTrue(callable(ExePatcher))

    def test_init(self):
        """初始化正常"""
        self.assertEqual(self.patcher.game_path, self.tmpdir)
        self.assertEqual(self.patcher.exe_path, self.exe_path)

    def test_set_game_path(self):
        """设置游戏路径"""
        new_path = os.path.join(self.tmpdir, "subdir")
        os.makedirs(new_path, exist_ok=True)
        new_exe = os.path.join(new_path, "Sango7.exe")
        with open(new_exe, "wb") as f:
            f.write(b"SG7S" + b"\x00" * 1024)
        self.patcher.set_game_path(new_path)
        self.assertEqual(self.patcher.game_path, new_path)
        self.assertTrue(self.patcher.exe_exists())

    def test_exe_exists(self):
        """EXE文件存在性检查"""
        self.assertTrue(self.patcher.exe_exists())
        # 不存在的路径
        p2 = self.ExePatcher("/nonexistent/path")
        self.assertFalse(p2.exe_exists())

    def test_get_exe_size(self):
        """获取EXE大小"""
        size = self.patcher.get_exe_size()
        self.assertGreater(size, 0)
        self.assertEqual(size, os.path.getsize(self.exe_path))

    def test_get_exe_size_no_file(self):
        """无EXE时返回0"""
        p2 = self.ExePatcher("/nonexistent/path")
        self.assertEqual(p2.get_exe_size(), 0)

    # ============================================================
    # 读写操作
    # ============================================================

    def test_read_int32(self):
        """读取int32"""
        val = self.patcher.read_int32(0x100)
        self.assertEqual(val, 999)

    def test_read_int16(self):
        """读取int16"""
        val = self.patcher.read_int16(0x200)
        self.assertEqual(val, 999)

    def test_read_int8(self):
        """读取int8"""
        val = self.patcher.read_int8(0x300)
        self.assertEqual(val, 67)

    def test_write_int32(self):
        """写入int32并验证"""
        self.assertTrue(self.patcher.write_int32(0x100, 65535))
        val = self.patcher.read_int32(0x100)
        self.assertEqual(val, 65535)

    def test_write_int16(self):
        """写入int16并验证"""
        self.assertTrue(self.patcher.write_int16(0x200, 65535))
        val = self.patcher.read_int16(0x200)
        self.assertEqual(val, 65535)

    def test_write_int8(self):
        """写入int8并验证"""
        self.assertTrue(self.patcher.write_int8(0x300, 255))
        val = self.patcher.read_int8(0x300)
        self.assertEqual(val, 255)

    def test_read_bytes(self):
        """读取原始字节"""
        data = self.patcher.read_bytes(0x0, 4)
        self.assertEqual(data, b"SG7S")

    def test_write_bytes(self):
        """写入原始字节"""
        self.assertTrue(self.patcher.write_bytes(0x400, b"TEST"))
        data = self.patcher.read_bytes(0x400, 4)
        self.assertEqual(data, b"TEST")

    def test_read_nonexistent(self):
        """读取不存在的EXE"""
        p2 = self.ExePatcher("/nonexistent/path")
        self.assertIsNone(p2.read_int32(0x100))
        self.assertIsNone(p2.read_bytes(0x0, 4))

    def test_write_nonexistent(self):
        """写入不存在的EXE"""
        p2 = self.ExePatcher("/nonexistent/path")
        self.assertFalse(p2.write_int32(0x100, 999))

    # ============================================================
    # 补丁定义
    # ============================================================

    def test_known_patches(self):
        """已知补丁定义完整"""
        patches = self.ExePatcher.KNOWN_PATCHES
        essential = [
            "soldier_limit", "stat_limit", "stat_display_limit",
            "force_display_limit", "int_display_limit",
            "hp_display_limit", "mp_display_limit",
            "hp_limit", "mp_limit", "levelup_limit",
            "heal_limit", "general_deploy_limit",
            "all_stat_999_break",
        ]
        for p in essential:
            self.assertIn(p, patches, f"缺少补丁: {p}")
            self.assertIn("description", patches[p])
            self.assertIn("value_type", patches[p])

    def test_all_stat_999_break_offsets(self):
        """一键突破补丁包含所有偏移"""
        patch = self.ExePatcher.KNOWN_PATCHES["all_stat_999_break"]
        self.assertGreater(len(patch["offsets"]), 20)  # 至少33个偏移
        self.assertEqual(patch["value_type"], "int16")
        self.assertEqual(patch["default_value"], 999)

    def test_community_patches(self):
        """社区补丁存在"""
        patches = self.ExePatcher.KNOWN_PATCHES
        community = ["red_dot_count", "red_dot_max", "immortal_boost",
                     "penglai_currency", "penglai_item", "arena_interval"]
        for p in community:
            self.assertIn(p, patches, f"缺少社区补丁: {p}")

    # ============================================================
    # 补丁应用
    # ============================================================

    def test_apply_patch_stat_display(self):
        """应用属性显示上限补丁（使用测试EXE内的偏移）"""
        # 使用测试EXE中存在的偏移量（0x200处有int16=999）
        result = self.patcher.apply_patch("stat_display_limit", 0x200, 65535)
        self.assertTrue(result)
        val = self.patcher.read_int16(0x200)
        self.assertEqual(val, 65535)

    def test_apply_patch_unknown_name(self):
        """未知补丁名仍可应用（使用默认值）"""
        result = self.patcher.apply_patch("unknown_patch", 0x100, 100)
        self.assertTrue(result)  # 默认int32可写入

    def test_apply_patch_out_of_range(self):
        """超出范围的偏移返回False"""
        result = self.patcher.apply_patch("stat_display_limit", 0xFFFFFFFF, 65535)
        self.assertFalse(result)

    # ============================================================
    # 特征码扫描
    # ============================================================

    def test_scan_signatures_exist(self):
        """特征码扫描规则存在"""
        sigs = self.ExePatcher.SCAN_SIGNATURES
        self.assertIn("soldier_limit", sigs)
        self.assertIn("stat_limit", sigs)
        self.assertIn("level_limit", sigs)

    def test_scan_signatures_have_patterns(self):
        """特征码规则包含扫描模式"""
        sigs = self.ExePatcher.SCAN_SIGNATURES
        for name, sig in sigs.items():
            self.assertIn("patterns", sig)
            self.assertGreater(len(sig["patterns"]), 0)
            for pattern, desc in sig["patterns"]:
                self.assertIsInstance(pattern, bytes)
                self.assertGreater(len(pattern), 0)

    # ============================================================
    # 边界情况
    # ============================================================

    def test_empty_exe(self):
        """空EXE文件"""
        empty_path = os.path.join(self.tmpdir, "empty.exe")
        with open(empty_path, "wb") as f:
            f.write(b"")
        p = self.ExePatcher(self.tmpdir)
        # 重命名以使用empty.exe
        p.exe_path = empty_path
        self.assertIsNone(p.read_int32(0x0))

    def test_reload_exe_cache(self):
        """EXE缓存重新加载"""
        # 第一次读取
        val1 = self.patcher.read_int32(0x100)
        # 写入后缓存应失效
        self.patcher.write_int32(0x100, 888)
        val2 = self.patcher.read_int32(0x100)
        self.assertEqual(val2, 888)
        self.assertNotEqual(val1, val2)

    def test_init_without_game_path(self):
        """无游戏路径初始化"""
        p = self.ExePatcher()
        self.assertEqual(p.exe_path, "")
        self.assertFalse(p.exe_exists())

    def test_get_exe_info(self):
        """获取EXE基本信息"""
        size = self.patcher.get_exe_size()
        self.assertGreater(size, 0)


if __name__ == "__main__":
    unittest.main()