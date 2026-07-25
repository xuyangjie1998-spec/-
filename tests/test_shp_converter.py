"""
San7ModMaker ShpConverter 类测试
覆盖 ShpConverter 的所有关键方法：初始化、格式检测、SHP解码、文件管理、批量操作等
"""
import os
import sys
import unittest
import tempfile
import shutil
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from core.shp_converter import (
    ShpConverter,
    FACE_SIZE,
    COLOR_COUNT,
    FACE_DIR,
    THING_ICON_SIZE,
    THING_ICON_DIR,
)


class TestShpConverter(unittest.TestCase):
    """验证 SHP 转换器"""

    @classmethod
    def setUpClass(cls):
        """创建临时游戏目录结构和两个 converter 实例"""
        cls.tmp_game_dir = tempfile.mkdtemp()
        cls.face_dir = os.path.join(cls.tmp_game_dir, FACE_DIR)
        os.makedirs(cls.face_dir, exist_ok=True)
        cls.converter_with_path = ShpConverter(cls.tmp_game_dir)
        cls.converter_no_path = ShpConverter()

    @classmethod
    def tearDownClass(cls):
        """清理临时目录"""
        shutil.rmtree(cls.tmp_game_dir)

    def setUp(self):
        """每个测试前清空日志和临时头像文件"""
        self.converter_no_path.clear_log()
        self.converter_with_path.clear_log()
        # 清理 face_dir 中残留的文件，确保测试隔离
        if os.path.exists(self.face_dir):
            for f in os.listdir(self.face_dir):
                fpath = os.path.join(self.face_dir, f)
                if os.path.isfile(fpath):
                    os.remove(fpath)

    # ============================================================
    # 初始化测试
    # ============================================================

    def test_init_no_path(self):
        """无路径初始化：game_path 为 None，face_root 为空字符串"""
        c = ShpConverter()
        self.assertIsNone(c.game_path)
        self.assertEqual(c.face_root, "")

    def test_init_with_temp_path(self):
        """带路径初始化：game_path 和 face_root 正确设置"""
        c = ShpConverter(self.tmp_game_dir)
        self.assertEqual(c.game_path, self.tmp_game_dir)
        expected_face = os.path.join(self.tmp_game_dir, FACE_DIR)
        self.assertEqual(c.face_root, expected_face)

    def test_set_game_path(self):
        """set_game_path 正确更新 game_path 和 face_root"""
        c = ShpConverter()
        c.set_game_path(self.tmp_game_dir)
        self.assertEqual(c.game_path, self.tmp_game_dir)
        expected_face = os.path.join(self.tmp_game_dir, FACE_DIR)
        self.assertEqual(c.face_root, expected_face)

    # ============================================================
    # 格式检测测试 (_detect_shp_format)
    # ============================================================

    def test_detect_shp_format_8byte_header(self):
        """8 字节头格式检测：magic(uint32) + width(uint16) + height(uint16)"""
        data = struct.pack("<IHH", ShpConverter.SHP_MAGIC_V1, 128, 128) + b'\x00' * (128 * 128)
        w, h, offset = self.converter_no_path._detect_shp_format(data)
        self.assertEqual(w, 128)
        self.assertEqual(h, 128)
        self.assertEqual(offset, 8)

    def test_detect_shp_format_4byte_header(self):
        """4 字节头格式检测：width(uint16) + height(uint16)"""
        data = struct.pack("<HH", 128, 128) + b'\x00' * (128 * 128)
        w, h, offset = self.converter_no_path._detect_shp_format(data)
        self.assertEqual(w, 128)
        self.assertEqual(h, 128)
        self.assertEqual(offset, 4)

    def test_detect_shp_format_no_header(self):
        """无头格式检测：128x128 原始像素数据"""
        data = b'\x00' * (128 * 128)
        w, h, offset = self.converter_no_path._detect_shp_format(data)
        self.assertEqual(w, 128)
        self.assertEqual(h, 128)
        self.assertEqual(offset, 0)

    def test_detect_shp_format_small_data(self):
        """小数据回退检测：64x64 数据识别为 64x64"""
        data = b'\x00' * (64 * 64)
        w, h, offset = self.converter_no_path._detect_shp_format(data)
        self.assertEqual(w, 64)
        self.assertEqual(h, 64)
        self.assertEqual(offset, 0)

    # ============================================================
    # SHP 解码测试
    # ============================================================

    @unittest.skipIf(not HAS_PIL, "PIL 库不可用")
    def test_decode_shp_bytes_valid(self):
        """解码有效的 128x128 无头 SHP 数据"""
        data = b'\x00' * (128 * 128)
        img = self.converter_no_path.decode_shp_bytes(data)
        self.assertIsNotNone(img)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (128, 128))

    @unittest.skipIf(not HAS_PIL, "PIL 库不可用")
    def test_decode_shp_bytes_with_8byte_header(self):
        """解码带 8 字节头的 SHP 数据"""
        data = struct.pack("<IHH", ShpConverter.SHP_MAGIC_V1, 128, 128) + b'\x00' * (128 * 128)
        img = self.converter_no_path.decode_shp_bytes(data)
        self.assertIsNotNone(img)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (128, 128))

    # ============================================================
    # face_exists 测试
    # ============================================================

    def test_face_exists_false(self):
        """无游戏路径时 face_exists 返回 False"""
        result = self.converter_no_path.face_exists(1)
        self.assertFalse(result)

    def test_face_exists_true(self):
        """头像文件存在时返回 True"""
        fname = os.path.join(self.face_dir, "0001.shp")
        with open(fname, "wb") as f:
            f.write(struct.pack("<IHH", ShpConverter.SHP_MAGIC_V1, 128, 128) + b'\x00' * (128 * 128))
        result = self.converter_with_path.face_exists(1)
        self.assertTrue(result)

    # ============================================================
    # load_shp_by_id 测试
    # ============================================================

    @unittest.skipIf(not HAS_PIL, "PIL 库不可用")
    def test_load_shp_by_id_no_path(self):
        """无游戏路径时返回占位图片"""
        img = self.converter_no_path.load_shp_by_id(1)
        self.assertIsNotNone(img)
        self.assertIsInstance(img, Image.Image)

    @unittest.skipIf(not HAS_PIL, "PIL 库不可用")
    def test_load_shp_by_id_not_exist(self):
        """头像文件不存在时返回占位图片"""
        img = self.converter_with_path.load_shp_by_id(9999)
        self.assertIsNotNone(img)
        self.assertIsInstance(img, Image.Image)

    @unittest.skipIf(not HAS_PIL, "PIL 库不可用")
    def test_load_shp_by_id_valid(self):
        """加载有效 SHP 文件返回 PIL Image"""
        fname = os.path.join(self.face_dir, "0001.shp")
        with open(fname, "wb") as f:
            f.write(struct.pack("<IHH", ShpConverter.SHP_MAGIC_V1, 128, 128) + b'\x00' * (128 * 128))
        img = self.converter_with_path.load_shp_by_id(1)
        self.assertIsNotNone(img)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (128, 128))

    # ============================================================
    # 调色板测试
    # ============================================================

    def test_get_palette_rgb(self):
        """get_palette_rgb 返回 256 个 RGB 三元组"""
        palette_rgb = self.converter_no_path.get_palette_rgb()
        self.assertEqual(len(palette_rgb), 256)
        for color in palette_rgb:
            self.assertIsInstance(color, list)
            self.assertEqual(len(color), 3)

    def test_generate_default_palette(self):
        """_generate_default_palette 返回 768 字节（256 色 × 3 字节 RGB）"""
        palette = self.converter_no_path._generate_default_palette()
        self.assertEqual(len(palette), 768)

    # ============================================================
    # list_faces 测试
    # ============================================================

    def test_list_faces_empty(self):
        """空目录返回空列表"""
        faces = self.converter_with_path.list_faces(1, 100)
        self.assertEqual(faces, [])

    def test_list_faces_with_files(self):
        """创建头像文件后正确列出"""
        for i in [1, 2, 5]:
            fname = os.path.join(self.face_dir, f"{i:04d}.shp")
            with open(fname, "wb") as f:
                f.write(struct.pack("<IHH", ShpConverter.SHP_MAGIC_V1, 128, 128) + b'\x00' * (128 * 128))
        faces = self.converter_with_path.list_faces(1, 10)
        self.assertEqual(len(faces), 3)
        face_ids = [f["id"] for f in faces]
        self.assertIn(1, face_ids)
        self.assertIn(2, face_ids)
        self.assertIn(5, face_ids)
        for f in faces:
            self.assertTrue(f["exists"])

    # ============================================================
    # 统计测试
    # ============================================================

    def test_get_face_stats_no_path(self):
        """无游戏路径时返回错误"""
        stats = self.converter_no_path.get_face_stats()
        self.assertFalse(stats["success"])
        self.assertIn("message", stats)

    def test_get_face_stats_with_files(self):
        """有头像文件时返回正确统计"""
        for i in [1, 2, 3]:
            fname = os.path.join(self.face_dir, f"{i:04d}.shp")
            with open(fname, "wb") as f:
                f.write(struct.pack("<IHH", ShpConverter.SHP_MAGIC_V1, 128, 128) + b'\x00' * (128 * 128))
        stats = self.converter_with_path.get_face_stats()
        self.assertTrue(stats["success"])
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["min_id"], 1)
        self.assertEqual(stats["max_id"], 3)
        self.assertGreater(stats["total_size"], 0)

    # ============================================================
    # 日志测试
    # ============================================================

    def test_clear_log(self):
        """clear_log 清空转换日志"""
        self.converter_with_path._log("测试日志1")
        self.converter_with_path._log("测试日志2")
        self.assertEqual(len(self.converter_with_path.get_log()), 2)
        self.converter_with_path.clear_log()
        self.assertEqual(len(self.converter_with_path.get_log()), 0)

    # ============================================================
    # get_info 静态方法测试
    # ============================================================

    def test_get_info(self):
        """get_info 返回预期的键"""
        info = ShpConverter.get_info()
        expected_keys = [
            "face_size", "color_count", "format", "header",
            "supported_input", "supported_output", "pil_available",
        ]
        for key in expected_keys:
            self.assertIn(key, info)
        self.assertEqual(info["face_size"], FACE_SIZE)
        self.assertEqual(info["color_count"], COLOR_COUNT)

    # ============================================================
    # 常量测试
    # ============================================================

    def test_constants(self):
        """验证所有模块级常量"""
        self.assertEqual(FACE_SIZE, 128)
        self.assertEqual(COLOR_COUNT, 256)
        self.assertEqual(FACE_DIR, "Shape/GenFace")
        self.assertEqual(THING_ICON_SIZE, 64)
        self.assertEqual(THING_ICON_DIR, "Shape/ThingIcon")
        self.assertEqual(ShpConverter.SHP_MAGIC_V1, 0x00000001)
        self.assertEqual(ShpConverter.SHP_MAGIC_V2, 0x53485001)

    # ============================================================
    # 批量删除测试
    # ============================================================

    def test_batch_delete_no_path(self):
        """无游戏路径时返回错误"""
        result = self.converter_no_path.batch_delete([1, 2])
        self.assertFalse(result["success"])
        self.assertIn("message", result)

    # ============================================================
    # 批量导出测试
    # ============================================================

    def test_batch_export_no_path(self):
        """无游戏路径时返回错误"""
        result = self.converter_no_path.batch_export([1, 2], "/tmp")
        self.assertFalse(result["success"])
        self.assertIn("message", result)

    # ============================================================
    # BFObj 相关测试
    # ============================================================

    def test_list_bfobj_shps_no_path(self):
        """无游戏路径时返回错误"""
        result = self.converter_no_path.list_bfobj_shps()
        self.assertFalse(result["success"])
        self.assertIn("message", result)

    def test_preview_bfobj_shp_no_path(self):
        """无游戏路径时返回错误"""
        result = self.converter_no_path.preview_bfobj_shp("test.shp")
        self.assertFalse(result["success"])
        self.assertIn("message", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)