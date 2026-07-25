"""
San7ModMaker DataValidator 测试
覆盖 ValidationResult / DataValidator
"""
import os
import sys
import unittest
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestValidationResult(unittest.TestCase):
    """验证 ValidationResult 数据类"""

    def test_validation_result_creation(self):
        """创建 ValidationResult 并验证属性"""
        from core.validator import ValidationResult
        result = ValidationResult(
            severity="error",
            category="duplicate_id",
            message="编号 1 重复",
            file_ref="General01.ini",
            section_ref="Entry_0",
            field_ref="No",
        )
        self.assertEqual(result.severity, "error")
        self.assertEqual(result.category, "duplicate_id")
        self.assertEqual(result.message, "编号 1 重复")
        self.assertEqual(result.file_ref, "General01.ini")
        self.assertEqual(result.section_ref, "Entry_0")
        self.assertEqual(result.field_ref, "No")

    def test_validation_result_to_dict(self):
        """to_dict 返回正确的字典结构"""
        from core.validator import ValidationResult
        result = ValidationResult(
            severity="warning",
            category="value_overflow",
            message="字段 WStr 值 999 超出范围",
            file_ref="General01.ini",
            section_ref="Entry_5",
            field_ref="WStr",
        )
        d = result.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["severity"], "warning")
        self.assertEqual(d["category"], "value_overflow")
        self.assertEqual(d["message"], "字段 WStr 值 999 超出范围")
        self.assertEqual(d["file_ref"], "General01.ini")
        self.assertEqual(d["section_ref"], "Entry_5")
        self.assertEqual(d["field_ref"], "WStr")
        self.assertEqual(len(d), 6)

    def test_validation_result_constants(self):
        """验证严重程度常量"""
        from core.validator import ValidationResult
        self.assertEqual(ValidationResult.SEVERITY_ERROR, "error")
        self.assertEqual(ValidationResult.SEVERITY_WARNING, "warning")
        self.assertEqual(ValidationResult.SEVERITY_INFO, "info")


class TestDataValidator(unittest.TestCase):
    """验证 DataValidator 校验器"""

    def setUp(self):
        from core.validator import DataValidator
        self.validator = DataValidator()
        self.validator.clear()

    # ---------- 初始化和基础操作 ----------

    def test_init(self):
        """创建 DataValidator 实例"""
        from core.validator import DataValidator
        v = DataValidator()
        self.assertIsInstance(v.results, list)
        self.assertEqual(len(v.results), 0)
        self.assertEqual(v._game_path, "")

    def test_clear(self):
        """clear 清空所有结果"""
        self.validator.add_result("error", "test", "test message")
        self.assertEqual(len(self.validator.results), 1)
        self.validator.clear()
        self.assertEqual(len(self.validator.results), 0)

    def test_add_result(self):
        """add_result 添加并验证结果"""
        self.validator.add_result(
            "error", "duplicate_id", "编号 5 重复",
            "General01.ini", "Entry_3", "No"
        )
        self.assertEqual(len(self.validator.results), 1)
        result = self.validator.results[0]
        self.assertEqual(result.severity, "error")
        self.assertEqual(result.category, "duplicate_id")
        self.assertEqual(result.message, "编号 5 重复")
        self.assertEqual(result.file_ref, "General01.ini")
        self.assertEqual(result.section_ref, "Entry_3")
        self.assertEqual(result.field_ref, "No")

    # ---------- 编号重复校验 ----------

    def test_check_duplicate_ids_no_dupes(self):
        """无重复编号时不产生错误"""
        entries = [
            {"No": "1", "Name": "刘备"},
            {"No": "2", "Name": "关羽"},
            {"No": "3", "Name": "张飞"},
        ]
        results = self.validator.check_duplicate_ids(entries, "general", "General01.ini")
        self.assertEqual(len(results), 0)

    def test_check_duplicate_ids_with_dupes(self):
        """有重复编号时产生错误"""
        entries = [
            {"No": "1", "Name": "刘备"},
            {"No": "2", "Name": "关羽"},
            {"No": "1", "Name": "张飞"},
        ]
        results = self.validator.check_duplicate_ids(entries, "general", "General01.ini")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].severity, "error")
        self.assertEqual(results[0].category, "duplicate_id")
        self.assertIn("1", results[0].message)

    # ---------- 编号缺失校验 ----------

    def test_check_missing_ids_all_present(self):
        """所有条目都有编号时不产生错误"""
        entries = [
            {"No": "1", "Name": "刘备"},
            {"No": "2", "Name": "关羽"},
        ]
        results = self.validator.check_missing_ids(entries, "general", "General01.ini")
        self.assertEqual(len(results), 0)

    def test_check_missing_ids_some_missing(self):
        """部分条目缺少编号时产生错误"""
        entries = [
            {"No": "1", "Name": "刘备"},
            {"Name": "关羽"},
            {"No": "", "Name": "张飞"},
        ]
        results = self.validator.check_missing_ids(entries, "general", "General01.ini")
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r.severity, "error")
            self.assertEqual(r.category, "missing_id")

    # ---------- 数值范围校验 ----------

    def test_check_value_ranges_valid(self):
        """所有值在范围内时不产生警告"""
        entries = [
            {"No": "1", "WStr": "98", "Int": "85", "HP": "200", "MP": "150"},
        ]
        results = self.validator.check_value_ranges(entries, "general", "General01.ini")
        self.assertEqual(len(results), 0)

    def test_check_value_ranges_overflow(self):
        """值超出范围时产生警告"""
        entries = [
            {"No": "1", "WStr": "999", "Sex": "5"},
        ]
        results = self.validator.check_value_ranges(entries, "general", "General01.ini")
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r.severity, "warning")
            self.assertEqual(r.category, "value_overflow")

    def test_check_value_ranges_non_numeric(self):
        """非数值字段被忽略"""
        entries = [
            {"No": "1", "WStr": "abc", "Name": "刘备"},
        ]
        results = self.validator.check_value_ranges(entries, "general", "General01.ini")
        self.assertEqual(len(results), 0)

    # ---------- 跨文件引用校验 ----------

    def test_check_cross_references_valid(self):
        """所有引用有效时不产生错误"""
        generals = [
            {"No": "1", "BFSoldier": "1", "Weapon": "10", "Horse": "20"},
        ]
        soldiers = [{"No": "1"}]
        things = [{"No": "10"}, {"No": "20"}]
        results = self.validator.check_cross_references(generals, soldiers, things)
        self.assertEqual(len(results), 0)

    def test_check_cross_references_broken_soldier(self):
        """兵种引用无效时产生错误"""
        generals = [
            {"No": "1", "BFSoldier": "999"},
        ]
        soldiers = [{"No": "1"}]
        things = []
        results = self.validator.check_cross_references(generals, soldiers, things)
        self.assertGreater(len(results), 0)
        found = any(r.category == "broken_reference" and "BFSoldier" in r.field_ref
                    for r in results)
        self.assertTrue(found, "应检测到无效兵种引用")

    def test_check_cross_references_broken_weapon(self):
        """武器引用无效时产生警告"""
        generals = [
            {"No": "1", "Weapon": "999"},
        ]
        soldiers = [{"No": "1"}]
        things = [{"No": "10"}]
        results = self.validator.check_cross_references(generals, soldiers, things)
        self.assertGreater(len(results), 0)
        found = any(r.severity == "warning" and "Weapon" in r.field_ref
                    for r in results)
        self.assertTrue(found, "应检测到无效武器引用")

    # ---------- DefSkill 引用校验 ----------

    def test_check_skill_references_valid(self):
        """武将和 DefSkill 一一对应时不产生警告"""
        generals = [{"No": "1", "Name": "刘备"}, {"No": "2", "Name": "关羽"}]
        defskill = [{"No": "1", "Name": "刘备"}, {"No": "2", "Name": "关羽"}]
        results = self.validator.check_skill_references(generals, defskill)
        self.assertEqual(len(results), 0)

    def test_check_skill_references_missing(self):
        """武将缺少 DefSkill 配置时产生警告"""
        generals = [{"No": "1", "Name": "刘备"}, {"No": "2", "Name": "关羽"}]
        defskill = [{"No": "1", "Name": "刘备"}]
        results = self.validator.check_skill_references(generals, defskill)
        self.assertGreater(len(results), 0)
        found = any("missing_defskill" in r.category for r in results)
        self.assertTrue(found, "应检测到缺少 DefSkill 配置")

    def test_check_skill_references_orphan(self):
        """DefSkill 存在但武将不存在时产生警告"""
        generals = [{"No": "1", "Name": "刘备"}]
        defskill = [{"No": "1", "Name": "刘备"}, {"No": "2", "Name": "关羽"}]
        results = self.validator.check_skill_references(generals, defskill)
        self.assertGreater(len(results), 0)
        found = any("orphan_defskill" in r.category for r in results)
        self.assertTrue(found, "应检测到孤儿 DefSkill 条目")

    # ---------- 出生地引用校验 ----------

    def test_check_birth_place_references_valid(self):
        """武将和 General02 一一对应时不产生警告"""
        generals = [{"No": "1", "Name": "刘备"}, {"No": "2", "Name": "关羽"}]
        general02 = [{"No": "1"}, {"No": "2"}]
        results = self.validator.check_birth_place_references(generals, general02)
        self.assertEqual(len(results), 0)

    def test_check_birth_place_references_missing(self):
        """武将缺少 General02 配置时产生警告"""
        generals = [{"No": "1", "Name": "刘备"}, {"No": "2", "Name": "关羽"}]
        general02 = [{"No": "1"}]
        results = self.validator.check_birth_place_references(generals, general02)
        self.assertGreater(len(results), 0)
        found = any("missing_birth_place" in r.category for r in results)
        self.assertTrue(found, "应检测到缺少出生地配置")

    # ---------- 物品数据完整性校验 ----------

    def test_check_thing_references_weapon_no_atk(self):
        """Type=2 的武器 ATK=0 时产生 info 提示"""
        things = [
            {"No": "1", "Name": "测试武器", "Type": "2", "ATK": "0"},
        ]
        results = self.validator.check_thing_references(things)
        self.assertGreater(len(results), 0)
        found = any("weapon_no_atk" in r.category for r in results)
        self.assertTrue(found, "应检测到武器攻击力为0")

    def test_check_thing_references_empty_name(self):
        """物品名称为空时产生警告"""
        things = [
            {"No": "1", "Name": "", "Type": "1"},
        ]
        results = self.validator.check_thing_references(things)
        self.assertGreater(len(results), 0)
        found = any("empty_name" in r.category for r in results)
        self.assertTrue(found, "应检测到空名称")

    # ---------- 兵种相克矩阵校验 ----------

    def test_check_soldier_matrix_valid(self):
        """所有 HitSol 值在 0-200 范围内时不产生警告"""
        soldiers = [
            {"No": "1", "HitSol1": "100", "HitSol2": "50"},
            {"No": "2", "HitSol1": "75", "HitSol2": "120"},
        ]
        results = self.validator.check_soldier_matrix(soldiers)
        self.assertEqual(len(results), 0)

    def test_check_soldier_matrix_overflow(self):
        """HitSol 值超过 200 时产生警告"""
        soldiers = [
            {"No": "1", "HitSol1": "999"},
        ]
        results = self.validator.check_soldier_matrix(soldiers)
        self.assertGreater(len(results), 0)
        found = any("invalid_hitsol" in r.category for r in results)
        self.assertTrue(found, "应检测到 HitSol 溢出")

    # ---------- 兵种上限校验 ----------

    def test_check_soldier_limit_ok(self):
        """兵种数量 <= 67 时不产生错误"""
        result = self.validator.check_soldier_limit(67, "Soldier.ini")
        self.assertIsNone(result)

    def test_check_soldier_limit_over(self):
        """兵种数量 > 67 时产生错误"""
        result = self.validator.check_soldier_limit(68, "Soldier.ini")
        self.assertIsNotNone(result)
        self.assertEqual(result.severity, "error")
        self.assertEqual(result.category, "soldier_limit")

    # ---------- TermText 引用校验 ----------

    def test_check_termtext_references_valid(self):
        """干净名称不产生警告"""
        entries = [
            {"Name": "刘备"},
            {"Name": "关羽"},
            {"Name": "张飞"},
        ]
        results = self.validator.check_termtext_references(entries, "general")
        self.assertEqual(len(results), 0)

    def test_check_termtext_references_control_chars(self):
        """名称包含控制字符时产生警告"""
        entries = [
            {"Name": "刘备\x00秘密"},
            {"Name": "关羽"},
        ]
        results = self.validator.check_termtext_references(entries, "general")
        self.assertGreater(len(results), 0)
        found = any("termtext_char" in r.category for r in results)
        self.assertTrue(found, "应检测到控制字符")

    # ---------- 势力与城池一致性校验 ----------

    def test_check_nation_city_consistency_valid(self):
        """城池君主都在势力中时不产生警告"""
        nations = [{"Lord": "1"}, {"Lord": "2"}]
        cities = [{"Lord": "1"}, {"Lord": "2"}, {"Lord": "1"}]
        results = self.validator.check_nation_city_consistency(nations, cities)
        self.assertEqual(len(results), 0)

    def test_check_nation_city_consistency_orphan(self):
        """城池君主不在势力中时产生警告"""
        nations = [{"Lord": "1"}]
        cities = [{"Lord": "1"}, {"Lord": "999"}]
        results = self.validator.check_nation_city_consistency(nations, cities)
        self.assertGreater(len(results), 0)
        found = any("orphan_city" in r.category for r in results)
        self.assertTrue(found, "应检测到孤儿城池君主")

    # ---------- 全面校验 ----------

    def test_validate_all_basic(self):
        """validate_all 基本校验流程不抛异常"""
        generals = [
            {"No": "1", "Name": "刘备", "WStr": "98", "Int": "85", "HP": "200",
             "MP": "150", "BFSoldier": "1", "Weapon": "10", "Horse": "20"},
        ]
        soldiers = [{"No": "1", "HitSol1": "100"}]
        things = [{"No": "10", "Name": "测试武器", "Type": "2", "ATK": "50"},
                  {"No": "20", "Name": "测试坐骑", "Type": "3"}]
        try:
            summary = self.validator.validate_all(generals, soldiers, things)
            self.assertIsInstance(summary, dict)
            self.assertIn("total", summary)
            self.assertIn("errors", summary)
            self.assertIn("warnings", summary)
            self.assertIn("infos", summary)
        except Exception as e:
            self.fail(f"validate_all 抛出异常: {e}")

    # ---------- 汇总方法 ----------

    def test_summary(self):
        """summary 返回正确的统计结构"""
        self.validator.add_result("error", "test", "err1")
        self.validator.add_result("error", "test", "err2")
        self.validator.add_result("warning", "test", "warn1")
        self.validator.add_result("info", "test", "info1")
        s = self.validator.summary()
        self.assertEqual(s["total"], 4)
        self.assertEqual(s["errors"], 2)
        self.assertEqual(s["warnings"], 1)
        self.assertEqual(s["infos"], 1)

    def test_get_errors_warnings(self):
        """get_errors 和 get_warnings 正确过滤结果"""
        self.validator.add_result("error", "test", "err1")
        self.validator.add_result("error", "test", "err2")
        self.validator.add_result("warning", "test", "warn1")
        self.validator.add_result("info", "test", "info1")

        errors = self.validator.get_errors()
        self.assertEqual(len(errors), 2)
        for e in errors:
            self.assertEqual(e.severity, "error")

        warnings = self.validator.get_warnings()
        self.assertEqual(len(warnings), 1)
        for w in warnings:
            self.assertEqual(w.severity, "warning")

        self.assertTrue(self.validator.has_errors())

        all_results = self.validator.get_all()
        self.assertEqual(len(all_results), 4)

    def test_to_dict_list(self):
        """to_dict_list 返回字典列表"""
        self.validator.add_result("error", "duplicate_id", "编号 1 重复",
                                  "General01.ini", "Entry_0", "No")
        self.validator.add_result("warning", "value_overflow", "超出范围",
                                  "Soldier.ini", "Entry_5", "Speed")
        dicts = self.validator.to_dict_list()
        self.assertEqual(len(dicts), 2)
        self.assertIsInstance(dicts[0], dict)
        self.assertEqual(dicts[0]["severity"], "error")
        self.assertEqual(dicts[0]["category"], "duplicate_id")
        self.assertIsInstance(dicts[1], dict)
        self.assertEqual(dicts[1]["severity"], "warning")


if __name__ == "__main__":
    unittest.main(verbosity=2)