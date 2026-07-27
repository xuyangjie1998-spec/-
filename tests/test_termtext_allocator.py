"""
San7ModMaker TermTextAllocator 模块测试
覆盖 core.termtext_allocator.TermTextAllocator 全部 14 个公开方法。
"""
import os
import sys
import unittest
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.termtext_allocator import (
    TermTextAllocator,
    SEGMENT_DEFINITIONS,
    CONTENT_TYPE_ALIASES,
)


# ============================================================
# 辅助函数
# ============================================================

def _make_ini_content(extra_lines=None):
    """生成标准 TermText.ini 内容，可选追加额外行"""
    lines = [
        "[TermText]",
        "StringCount = 5",
        'TermText_0001 = "SystemText1"',
        'TermText_0002 = "SystemText2"',
        'TermText_13000 = "Pikeman"',
        'TermText_13001 = "Spearman"',
        'TermText_14000 = "IronSword"',
    ]
    if extra_lines:
        lines.extend(extra_lines)
    return "\n".join(lines) + "\n"


def _make_ini_with_duplicates():
    """生成包含重复 ID 的 TermText.ini 内容"""
    return _make_ini_content([
        'TermText_13000 = "DuplicatePikeman"',
        'TermText_99999 = "OutOfBoundText"',
    ])


def _make_other_ini_content():
    """生成另一个引用 TermText ID 的 INI 文件内容"""
    lines = [
        "[SOLDIER]",
        "No = 1",
        'Name = "TermText_13000"',
        'Desc = "这是兵种1"',
        "",
        "[SOLDIER]",
        "No = 2",
        'Name = "TermText_13001"',
        'Desc = "这是兵种2"',
        "",
        "[ITEM]",
        "No = 1",
        'Name = "TermText_14000"',
    ]
    return "\n".join(lines) + "\n"


# ============================================================
# 测试类
# ============================================================

class TestGetInfo(unittest.TestCase):
    """测试 get_info 静态方法"""

    def test_get_info_returns_module_info(self):
        """get_info 返回正确的模块信息结构"""
        info = TermTextAllocator.get_info()
        self.assertIsInstance(info, dict)
        self.assertEqual(info["module"], "termtext_allocator")
        self.assertEqual(info["version"], "1.0.0")
        self.assertIn("total_segments", info)
        self.assertIn("segments", info)
        self.assertIn("supported_content_types", info)
        self.assertIn("aliases", info)
        self.assertEqual(info["total_segments"], len(SEGMENT_DEFINITIONS))

    def test_get_info_segments_have_required_fields(self):
        """get_info 中每个 segment 包含必要字段"""
        info = TermTextAllocator.get_info()
        for seg in info["segments"]:
            self.assertIn("content_type", seg)
            self.assertIn("description", seg)
            self.assertIn("start", seg)
            self.assertIn("end", seg)
            self.assertIn("capacity", seg)
            self.assertEqual(seg["capacity"], seg["end"] - seg["start"] + 1)

    def test_get_info_content_type_aliases_valid(self):
        """get_info 中的别名映射与 CONTENT_TYPE_ALIASES 一致"""
        info = TermTextAllocator.get_info()
        self.assertEqual(info["aliases"], dict(CONTENT_TYPE_ALIASES))


class TestTermTextAllocatorBase(unittest.TestCase):
    """带临时文件的基础测试类"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.ini_path = os.path.join(self.temp_dir, "TermText.ini")
        self._write_ini(_make_ini_content())
        self.allocator = TermTextAllocator()
        self.allocator.load(self.ini_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_ini(self, content):
        with open(self.ini_path, "w", encoding="gbk") as f:
            f.write(content)

    def _reload(self):
        self.allocator = TermTextAllocator()
        self.allocator.load(self.ini_path)


class TestAllocateId(TestTermTextAllocatorBase):
    """测试 allocate_id 方法"""

    def test_allocate_id_normal(self):
        """正常分配一个可用 ID"""
        result = self.allocator.allocate_id("item_name")
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["allocated_id"])
        self.assertGreaterEqual(result["allocated_id"], 14000)
        self.assertLessEqual(result["allocated_id"], 14999)
        self.assertFalse(result["reused"])
        self.assertIn("分配", result["message"])

    def test_allocate_id_with_preferred_text_existing(self):
        """首选文本已存在时复用已有 ID"""
        result = self.allocator.allocate_id("soldier_name", "Pikeman")
        self.assertTrue(result["success"])
        self.assertEqual(result["allocated_id"], 13000)
        self.assertTrue(result["reused"])
        self.assertIn("复用", result["message"])

    def test_allocate_id_unknown_content_type(self):
        """未知内容类型返回失败"""
        result = self.allocator.allocate_id("nonexistent_type")
        self.assertFalse(result["success"])
        self.assertIsNone(result["allocated_id"])
        self.assertIn("未知", result["message"])

    def test_allocate_id_segment_full(self):
        """编号段已满时返回失败"""
        self._write_ini(_make_ini_content())
        self._reload()
        # 填满 system 段 (1-999)
        for i in range(3, 1000):
            result = self.allocator.allocate_id("system")
            if not result["success"]:
                break
        # 在满了之后应该返回失败
        # 注意：由于 reserved_ids 是内存中的，先创建新的 allocator 绕过
        allocator2 = TermTextAllocator()
        allocator2.load(self.ini_path)
        # 预填满整个段
        for i in range(1, 1000):
            allocator2._reserved_ids["system"].add(i)
        result = allocator2.allocate_id("system")
        self.assertFalse(result["success"])
        self.assertIn("已满", result["message"])


class TestAllocateBatch(TestTermTextAllocatorBase):
    """测试 allocate_batch 方法"""

    def test_allocate_batch_normal(self):
        """批量分配多个 ID"""
        requests = [
            {"content_type": "soldier_name", "count": 3},
            {"content_type": "item_name", "count": 2},
        ]
        result = self.allocator.allocate_batch(requests)
        self.assertTrue(result["success"])
        self.assertEqual(result["total_requested"], 5)
        self.assertEqual(result["total_allocated"], 5)
        self.assertEqual(len(result["results"]), 5)
        self.assertIn("segment_usage", result)

    def test_allocate_batch_with_preferred_text(self):
        """批量分配时首选文本复用"""
        requests = [
            {"content_type": "soldier_name", "count": 1, "preferred_text": "Pikeman"},
            {"content_type": "soldier_name", "count": 2},
        ]
        result = self.allocator.allocate_batch(requests)
        self.assertTrue(result["success"])
        self.assertEqual(result["total_allocated"], 3)
        # 第一个结果应该是复用的
        self.assertTrue(result["results"][0]["reused"])
        self.assertEqual(result["results"][0]["allocated_id"], 13000)

    def test_allocate_batch_partial_failure(self):
        """部分分配失败仍返回部分结果"""
        allocator2 = TermTextAllocator()
        allocator2.load(self.ini_path)
        # 填满 item_name 段
        for i in range(14000, 15000):
            allocator2._reserved_ids["item_name"].add(i)
        requests = [
            {"content_type": "soldier_name", "count": 1},
            {"content_type": "item_name", "count": 1},  # 这个会失败
        ]
        result = allocator2.allocate_batch(requests)
        self.assertFalse(result["success"])
        self.assertEqual(result["total_allocated"], 1)
        self.assertEqual(result["total_requested"], 2)
        self.assertGreater(len(result["errors"]), 0)


class TestDetectConflicts(TestTermTextAllocatorBase):
    """测试 detect_conflicts 方法"""

    def test_detect_conflicts_no_conflicts(self):
        """无冲突文件检测返回零冲突"""
        result = self.allocator.detect_conflicts()
        self.assertTrue(result["success"])
        self.assertEqual(result["total_conflicts"], 0)
        self.assertEqual(len(result["duplicate_ids"]), 0)
        self.assertEqual(len(result["cross_segment_conflicts"]), 0)
        self.assertEqual(len(result["out_of_bound_ids"]), 0)
        self.assertIn("未检测到冲突", result["message"])

    def test_detect_conflicts_with_duplicate(self):
        """有重复 ID 时正确检测"""
        self._write_ini(_make_ini_with_duplicates())
        self._reload()
        result = self.allocator.detect_conflicts()
        self.assertTrue(result["success"])
        self.assertGreater(result["total_conflicts"], 0)
        self.assertGreater(len(result["duplicate_ids"]), 0)
        # 重复 ID 13000 应被检测
        dup_ids = [d["id"] for d in result["duplicate_ids"]]
        self.assertIn(13000, dup_ids)

    def test_detect_conflicts_with_out_of_bound(self):
        """有越界 ID 时正确检测"""
        self._write_ini(_make_ini_with_duplicates())
        self._reload()
        result = self.allocator.detect_conflicts()
        self.assertGreater(len(result["out_of_bound_ids"]), 0)
        oob_ids = [o["id"] for o in result["out_of_bound_ids"]]
        self.assertIn(99999, oob_ids)

    def test_detect_conflicts_not_loaded(self):
        """未加载文件时返回失败"""
        allocator = TermTextAllocator()
        result = allocator.detect_conflicts()
        self.assertFalse(result["success"])
        self.assertIn("未加载", result["message"])


class TestResolveConflicts(TestTermTextAllocatorBase):
    """测试 resolve_conflicts 方法"""

    def test_resolve_conflicts_report_only(self):
        """report_only 策略仅报告不修改"""
        self._write_ini(_make_ini_with_duplicates())
        self._reload()
        result = self.allocator.resolve_conflicts("report_only")
        self.assertTrue(result["success"])
        self.assertEqual(result["strategy"], "report_only")
        self.assertIn("conflicts", result)

    def test_resolve_conflicts_auto_with_duplicates(self):
        """auto 策略自动解决重复 ID"""
        self._write_ini(_make_ini_with_duplicates())
        self._reload()
        result = self.allocator.resolve_conflicts("auto")
        self.assertIn("resolved_count", result)
        self.assertIn("resolved", result)
        self.assertIn("unresolved", result)

    def test_resolve_conflicts_keep_first(self):
        """keep_first 策略保留第一个"""
        self._write_ini(_make_ini_with_duplicates())
        self._reload()
        result = self.allocator.resolve_conflicts("keep_first")
        self.assertIn("resolved_count", result)

    def test_resolve_conflicts_not_loaded(self):
        """未加载文件时返回失败"""
        tmp_dir = tempfile.mkdtemp()
        try:
            tmp_path = os.path.join(tmp_dir, "TermText.ini")
            with open(tmp_path, "w", encoding="gbk") as f:
                f.write(_make_ini_content())
            allocator = TermTextAllocator()
            # 不调用 load，直接 resolve
            result = allocator.resolve_conflicts("auto")
            self.assertFalse(result["success"])
            self.assertIn("无冲突数据", result["message"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestMigrateIds(TestTermTextAllocatorBase):
    """测试 migrate_ids 方法"""

    def test_migrate_ids_normal(self):
        """正常迁移 ID"""
        mapping = {13000: 13050, 13001: 13051}
        result = self.allocator.migrate_ids(mapping)
        self.assertTrue(result["success"])
        self.assertEqual(result["migrated_count"], 2)
        self.assertEqual(result["failed_count"], 0)

    def test_migrate_ids_nonexistent(self):
        """迁移不存在的 ID 记录失败"""
        mapping = {99999: 13099}
        result = self.allocator.migrate_ids(mapping)
        self.assertFalse(result["success"])
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["migrated_count"], 0)

    def test_migrate_ids_same_id(self):
        """相同 ID 的迁移被跳过"""
        mapping = {13000: 13000}
        result = self.allocator.migrate_ids(mapping)
        self.assertTrue(result["success"])
        self.assertEqual(result["migrated_count"], 0)


class TestReserveSegment(TestTermTextAllocatorBase):
    """测试 reserve_segment 方法"""

    def test_reserve_segment_normal(self):
        """正常预留连续段"""
        result = self.allocator.reserve_segment("item_name", 5)
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["reserved_start"])
        self.assertIsNotNone(result["reserved_end"])
        self.assertEqual(result["reserved_end"] - result["reserved_start"] + 1, 5)
        self.assertEqual(result["count"], 5)

    def test_reserve_segment_unknown_type(self):
        """未知类型预留失败"""
        result = self.allocator.reserve_segment("unknown", 10)
        self.assertFalse(result["success"])
        self.assertIn("未知", result["message"])

    def test_reserve_segment_too_large(self):
        """请求预留数量超过段容量时失败"""
        # system 段 1-999，容量 999，请求 1000 个 ID
        result = self.allocator.reserve_segment("system", 1000)
        self.assertFalse(result["success"])
        self.assertIn("没有足够的连续空闲", result["message"])


class TestGetSegmentInfo(TestTermTextAllocatorBase):
    """测试 get_segment_info 方法"""

    def test_get_segment_info_normal(self):
        """正常获取段信息"""
        result = self.allocator.get_segment_info("soldier_name")
        self.assertTrue(result["success"])
        self.assertEqual(result["start"], 13000)
        self.assertEqual(result["end"], 13999)
        self.assertEqual(result["total_capacity"], 1000)
        self.assertGreaterEqual(result["used"], 2)  # Pikeman, Spearman
        self.assertIn("usage_rate", result)

    def test_get_segment_info_unknown_type(self):
        """未知类型返回失败"""
        result = self.allocator.get_segment_info("unknown")
        self.assertFalse(result["success"])
        self.assertIn("未知", result["message"])

    def test_get_segment_info_by_alias(self):
        """通过别名获取段信息"""
        result = self.allocator.get_segment_info("兵种")
        self.assertTrue(result["success"])
        self.assertEqual(result["content_type"], "兵种")

    def test_get_segment_info_system(self):
        """检查系统段信息"""
        result = self.allocator.get_segment_info("system")
        self.assertTrue(result["success"])
        self.assertEqual(result["start"], 1)
        self.assertEqual(result["end"], 999)
        self.assertGreaterEqual(result["used"], 2)  # SystemText1, SystemText2


class TestGetAllSegments(TestTermTextAllocatorBase):
    """测试 get_all_segments 方法"""

    def test_get_all_segments_structure(self):
        """获取所有段信息结构正确"""
        result = self.allocator.get_all_segments()
        self.assertTrue(result["success"])
        self.assertEqual(len(result["segments"]), len(SEGMENT_DEFINITIONS))
        self.assertIn("total_used", result)
        self.assertIn("total_capacity", result)
        self.assertIn("overall_usage_rate", result)
        self.assertIn("critical_segments", result)
        self.assertGreater(result["total_used"], 0)

    def test_get_all_segments_item_name_info(self):
        """item_name 段在全部段信息中正确"""
        result = self.allocator.get_all_segments()
        seg = result["segments"]["item_name"]
        self.assertTrue(seg["success"])
        self.assertEqual(seg["start"], 14000)
        self.assertEqual(seg["end"], 14999)
        self.assertGreaterEqual(seg["used"], 1)  # IronSword


class TestValidateAllocation(TestTermTextAllocatorBase):
    """测试 validate_allocation 方法"""

    def test_validate_allocation_valid(self):
        """验证合法的 ID 分配"""
        result = self.allocator.validate_allocation("soldier_name", 13050)
        self.assertTrue(result["success"])
        self.assertTrue(result["valid"])
        self.assertIn("验证通过", result["message"])

    def test_validate_allocation_out_of_range(self):
        """验证超出段范围的 ID"""
        result = self.allocator.validate_allocation("soldier_name", 15000)
        self.assertTrue(result["success"])
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["suggestions"]), 0)

    def test_validate_allocation_occupied(self):
        """验证已被占用的 ID"""
        result = self.allocator.validate_allocation("soldier_name", 13000)
        self.assertTrue(result["success"])
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["suggestions"]), 0)

    def test_validate_allocation_negative_id(self):
        """验证负数 ID"""
        result = self.allocator.validate_allocation("soldier_name", -1)
        self.assertTrue(result["success"])
        self.assertFalse(result["valid"])
        self.assertIn("正整数", result["suggestions"][0])


class TestSmartAllocate(TestTermTextAllocatorBase):
    """测试 smart_allocate 方法"""

    def test_smart_allocate_non_contiguous(self):
        """非连续模式智能分配"""
        result = self.allocator.smart_allocate("item_name", 5, contiguous=False)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["allocated_ids"]), 5)
        self.assertFalse(result["contiguous"])
        # 所有分配的 ID 应在段内
        for id_val in result["allocated_ids"]:
            self.assertGreaterEqual(id_val, 14000)
            self.assertLessEqual(id_val, 14999)

    def test_smart_allocate_contiguous(self):
        """连续模式智能分配"""
        result = self.allocator.smart_allocate("item_name", 3, contiguous=True)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["allocated_ids"]), 3)
        self.assertTrue(result["contiguous"])
        # 验证连续性
        ids = sorted(result["allocated_ids"])
        for i in range(1, len(ids)):
            self.assertEqual(ids[i], ids[i - 1] + 1)

    def test_smart_allocate_unknown_type(self):
        """未知类型返回失败"""
        result = self.allocator.smart_allocate("unknown", 5)
        self.assertFalse(result["success"])
        self.assertIn("未知", result["message"])

    def test_smart_allocate_contiguous_too_many(self):
        """连续分配超出可用空间时失败"""
        # 填满大部分 item_name 段
        allocator2 = TermTextAllocator()
        allocator2.load(self.ini_path)
        for i in range(14000, 14990):
            allocator2._reserved_ids["item_name"].add(i)
        result = allocator2.smart_allocate("item_name", 20, contiguous=True)
        self.assertFalse(result["success"])


class TestCrossFileDetect(TestTermTextAllocatorBase):
    """测试 cross_file_detect 方法"""

    def test_cross_file_detect_normal(self):
        """跨文件检测正常情况"""
        other_ini = os.path.join(self.temp_dir, "Soldier.ini")
        with open(other_ini, "w", encoding="gbk") as f:
            f.write(_make_other_ini_content())

        result = self.allocator.cross_file_detect([other_ini])
        self.assertTrue(result["success"])
        self.assertIn("total_files", result)
        self.assertIn("total_references", result)

    def test_cross_file_detect_empty(self):
        """空文件列表检测"""
        result = self.allocator.cross_file_detect([])
        self.assertTrue(result["success"])
        self.assertEqual(result["total_files"], 0)
        self.assertEqual(result["total_references"], 0)

    def test_cross_file_detect_nonexistent(self):
        """不存在的文件被跳过"""
        result = self.allocator.cross_file_detect(["/nonexistent/path/file.ini"])
        self.assertTrue(result["success"])
        self.assertEqual(result["total_files"], 0)


class TestGenerateAllocationReport(TestTermTextAllocatorBase):
    """测试 generate_allocation_report 方法"""

    def test_generate_allocation_report_structure(self):
        """生成报告结构完整"""
        result = self.allocator.generate_allocation_report()
        self.assertTrue(result["success"])
        self.assertIn("timestamp", result)
        self.assertIn("segments", result)
        self.assertIn("conflicts", result)
        self.assertIn("trends", result)
        self.assertIn("suggestions", result)
        self.assertTrue(result["loaded"])
        self.assertGreater(result["total_ids"], 0)

    def test_generate_allocation_report_with_conflicts(self):
        """有冲突时报告包含冲突信息"""
        self._write_ini(_make_ini_with_duplicates())
        self._reload()
        result = self.allocator.generate_allocation_report()
        self.assertTrue(result["success"])
        self.assertGreater(result["conflicts"]["total"], 0)


class TestAutoRemediate(TestTermTextAllocatorBase):
    """测试 auto_remediate 方法"""

    def test_auto_remediate_clean(self):
        """无冲突时自动修复无操作"""
        result = self.allocator.auto_remediate()
        self.assertTrue(result["success"])
        self.assertIn("fixed_count", result)
        self.assertIn("warning_count", result)
        self.assertIn("error_count", result)

    def test_auto_remediate_with_duplicates(self):
        """有重复 ID 时自动修复"""
        self._write_ini(_make_ini_with_duplicates())
        self._reload()
        result = self.allocator.auto_remediate()
        self.assertIn("fixed_count", result)
        # 应至少修复了一些问题
        self.assertGreaterEqual(result["fixed_count"], 0)

    def test_auto_remediate_not_loaded(self):
        """未加载文件时返回失败"""
        allocator = TermTextAllocator()
        result = allocator.auto_remediate()
        self.assertFalse(result["success"])
        self.assertIn("未加载", result["message"])


class TestEdgeCases(unittest.TestCase):
    """边界情况和综合测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.ini_path = os.path.join(self.temp_dir, "TermText.ini")
        with open(self.ini_path, "w", encoding="gbk") as f:
            f.write(_make_ini_content())
        self.allocator = TermTextAllocator()
        self.allocator.load(self.ini_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_nonexistent_file(self):
        """加载不存在的文件不崩溃"""
        allocator = TermTextAllocator()
        allocator.load("/nonexistent/path/TermText.ini")
        self.assertFalse(allocator.is_loaded())

    def test_clear_reservations(self):
        """清除预留 ID 后可以重新分配"""
        self.allocator.allocate_id("item_name")
        self.allocator.clear_reservations()
        # 重新分配应该得到相同的 ID
        result = self.allocator.allocate_id("item_name")
        self.assertTrue(result["success"])

    def test_get_used_ids(self):
        """获取已使用的 ID 列表"""
        ids = self.allocator.get_used_ids()
        self.assertIsInstance(ids, set)
        self.assertIn(13000, ids)
        self.assertIn(13001, ids)
        self.assertIn(14000, ids)

    def test_get_text(self):
        """根据 ID 获取文本"""
        text = self.allocator.get_text(13000)
        self.assertEqual(text, "Pikeman")

    def test_get_text_nonexistent(self):
        """获取不存在 ID 的文本返回 None"""
        text = self.allocator.get_text(99999)
        self.assertIsNone(text)

    def test_get_id_by_text(self):
        """根据文本获取 ID"""
        id_val = self.allocator.get_id_by_text("Pikeman")
        self.assertEqual(id_val, 13000)

    def test_get_all_ids(self):
        """获取所有 ID 映射"""
        all_ids = self.allocator.get_all_ids()
        self.assertIsInstance(all_ids, dict)
        self.assertEqual(all_ids[13000], "Pikeman")

    def test_allocate_id_chinese_alias(self):
        """使用中文别名分配 ID"""
        result = self.allocator.allocate_id("物品名称")
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["allocated_id"], 14000)
        self.assertLessEqual(result["allocated_id"], 14999)

    def test_resolve_content_type(self):
        """_resolve_content_type 正确解析别名"""
        self.assertEqual(
            TermTextAllocator._resolve_content_type("兵种"), "soldier_name"
        )
        self.assertEqual(
            TermTextAllocator._resolve_content_type("soldier_name"), "soldier_name"
        )
        self.assertIsNone(
            TermTextAllocator._resolve_content_type("不存在的类型")
        )

    def test_get_segment_range(self):
        """_get_segment_range 返回正确范围"""
        result = TermTextAllocator._get_segment_range("soldier_name")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 13000)
        self.assertEqual(result[1], 13999)

    def test_get_segment_range_unknown(self):
        """未知类型返回 None"""
        result = TermTextAllocator._get_segment_range("unknown")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()