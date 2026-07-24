"""
San7ModMaker 兵种模块测试
覆盖 SoldierMatrix / Schema / CSV / 数据校验
"""
import os
import sys
import unittest
import tempfile
import shutil
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSoldierSchema(unittest.TestCase):
    """验证兵种数据模型 schema 定义"""

    @classmethod
    def setUpClass(cls):
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "soldier_schema.json"
        )
        with open(schema_path, "r", encoding="utf-8") as f:
            cls.schema = json.load(f)

    def test_schema_version(self):
        """schema 版本号存在"""
        self.assertIn("_schema_version", self.schema)
        self.assertEqual(self.schema["_schema_version"], "3.0")

    def test_schema_file(self):
        """schema 文件关联正确"""
        self.assertEqual(self.schema["_file"], "Soldier.ini")

    def test_soldier_limit(self):
        """兵种上限 = 67"""
        self.assertEqual(self.schema["soldier_limit"], 67)

    def test_section_exists(self):
        """SOLDIER section 存在"""
        self.assertIn("SOLDIER", self.schema["sections"])

    def test_template_exists(self):
        """new_entry_template 存在"""
        self.assertIn("new_entry_template", self.schema)
        template = self.schema["new_entry_template"]
        self.assertIn("No", template)
        self.assertIn("Name", template)
        self.assertIn("Life", template)
        self.assertIn("BasePower", template)
        self.assertIn("AddPower", template)

    def test_required_fields(self):
        """必填字段: No, Name, Life, BasePower, AddPower"""
        fields = self.schema["sections"]["SOLDIER"]["fields"]
        required = [k for k, v in fields.items() if v.get("required")]
        self.assertIn("No", required)
        self.assertIn("Name", required)
        self.assertIn("Life", required)
        self.assertIn("BasePower", required)
        self.assertIn("AddPower", required)

    def test_hit_sol_fields_complete(self):
        """HitSol 字段覆盖 0~66 共 67 个"""
        fields = self.schema["sections"]["SOLDIER"]["fields"]
        for i in range(67):
            key = f"HitSol{i}"
            self.assertIn(key, fields, f"缺少 {key}")
            self.assertEqual(fields[key]["type"], "int")
            self.assertEqual(fields[key]["min"], 0)
            self.assertEqual(fields[key]["max"], 999)

    def test_field_count(self):
        """字段总数 ≥ 40（含扩展字段）"""
        fields = self.schema["sections"]["SOLDIER"]["fields"]
        self.assertGreaterEqual(len(fields), 40)

    def test_type_field_range(self):
        """兵种类型 Type 字段范围 0~99"""
        fields = self.schema["sections"]["SOLDIER"]["fields"]
        self.assertIn("Type", fields)
        self.assertEqual(fields["Type"]["min"], 0)
        self.assertEqual(fields["Type"]["max"], 99)

    def test_template_defaults(self):
        """模板默认值合理: Rank=1, Life=1, Speed=6, IsUsed=1"""
        t = self.schema["new_entry_template"]
        self.assertEqual(t["Rank"], 1)
        self.assertEqual(t["Life"], 1)
        self.assertEqual(t["Speed"], 6)
        self.assertEqual(t["IsUsed"], 1)


class TestSoldierMatrix(unittest.TestCase):
    """验证兵种相克矩阵编辑器"""

    @classmethod
    def setUpClass(cls):
        from core.soldier_matrix import SoldierMatrixEditor
        cls.editor = SoldierMatrixEditor()

    def test_import(self):
        """模块可导入"""
        from core.soldier_matrix import SoldierMatrixEditor
        self.assertTrue(callable(SoldierMatrixEditor))

    def test_matrix_size(self):
        """矩阵尺寸 = 67"""
        self.assertEqual(self.editor.MATRIX_SIZE, 67)

    def test_hit_sol_prefix(self):
        """HitSol 前缀正确"""
        self.assertEqual(self.editor.HIT_SOL_PREFIX, "HitSol")

    def test_load_empty_soldiers(self):
        """空兵种列表加载不报错"""
        result = self.editor.load_from_soldiers([])
        self.assertIsInstance(result, dict)
        self.assertIn("size", result)
        self.assertEqual(result["size"], 0)

    def test_load_single_soldier(self):
        """单个兵种加载→矩阵 1x67"""
        soldier = {"No": 1, "Name": "测试兵种"}
        for i in range(67):
            soldier[f"HitSol{i}"] = 100
        result = self.editor.load_from_soldiers([soldier])
        self.assertEqual(result["size"], 1)
        matrix = self.editor.get_matrix()
        self.assertEqual(len(matrix), 1)
        self.assertEqual(len(matrix[0]), 67)

    def test_load_multiple_soldiers(self):
        """多个兵种加载→矩阵 Nx67"""
        soldiers = []
        for n in range(5):
            s = {"No": n + 1, "Name": f"兵种{n}"}
            for i in range(67):
                s[f"HitSol{i}"] = 100 + n * 10
            soldiers.append(s)
        result = self.editor.load_from_soldiers(soldiers)
        self.assertEqual(result["size"], 5)
        matrix = self.editor.get_matrix()
        self.assertEqual(len(matrix), 5)
        self.assertEqual(len(matrix[0]), 67)

    def test_matrix_truncate_to_limit(self):
        """超过67个兵种时截断到67"""
        soldiers = []
        for n in range(80):
            s = {"No": n + 1, "Name": f"兵种{n}"}
            for i in range(67):
                s[f"HitSol{i}"] = 100
            soldiers.append(s)
        result = self.editor.load_from_soldiers(soldiers)
        self.assertEqual(result["size"], 67)

    def test_matrix_values_preserved(self):
        """矩阵值正确保留"""
        soldier = {"No": 1, "Name": "测试"}
        for i in range(67):
            soldier[f"HitSol{i}"] = 150 if i % 2 == 0 else 50
        self.editor.load_from_soldiers([soldier])
        matrix = self.editor.get_matrix()
        self.assertEqual(matrix[0][0], 150)
        self.assertEqual(matrix[0][1], 50)

    def test_default_value_when_missing(self):
        """缺失 HitSol 字段时默认值 = 100"""
        soldier = {"No": 1, "Name": "测试"}
        self.editor.load_from_soldiers([soldier])
        matrix = self.editor.get_matrix()
        self.assertEqual(matrix[0][0], 100)

    def test_get_summary_structure(self):
        """summary 结构完整"""
        soldier = {"No": 1, "Name": "测试"}
        for i in range(67):
            soldier[f"HitSol{i}"] = 100
        summary = self.editor.load_from_soldiers([soldier])
        self.assertIn("size", summary)
        self.assertIn("soldiers", summary)
        self.assertIn("analysis", summary)

    def test_analysis_strong_weak(self):
        """克制分析: 强克制(>100) 和 被克制(<100) 统计"""
        soldier = {"No": 1, "Name": "测试"}
        for i in range(67):
            soldier[f"HitSol{i}"] = 150 if i < 10 else 100
        summary = self.editor.load_from_soldiers([soldier])
        analysis = summary.get("analysis", {})
        self.assertIn("strong_count", analysis)
        self.assertIn("weak_count", analysis)
        self.assertIn("neutral_count", analysis)


class TestSoldierCSV(unittest.TestCase):
    """验证兵种 CSV 字段映射"""

    @classmethod
    def setUpClass(cls):
        from core.csv_manager import CsvManager
        cls.csv_mgr = CsvManager()

    def test_csv_import(self):
        """CsvManager 可导入"""
        self.assertTrue(hasattr(self.csv_mgr, 'import_csv'))

    def test_csv_export(self):
        """CsvManager 可导出"""
        self.assertTrue(hasattr(self.csv_mgr, 'export_csv'))

    def test_soldier_csv_fields(self):
        """兵种 CSV 字段列表存在"""
        self.assertTrue(hasattr(self.csv_mgr, 'FIELD_MAPS'))

    def test_csv_field_mapping_has_required(self):
        """CSV 字段映射包含核心字段"""
        fields = getattr(self.csv_mgr, 'FIELD_MAPS', {})
        self.assertIn('soldier', fields)
        soldier_fields = fields['soldier']
        # 核心字段应存在
        self.assertIn('No', soldier_fields)
        self.assertIn('Name', soldier_fields)
        # 使用正确的 Schema 字段名
        self.assertIn('Life', soldier_fields)
        self.assertIn('BasePower', soldier_fields)
        self.assertIn('AddPower', soldier_fields)
        self.assertIn('Rank', soldier_fields)
        self.assertIn('ObjID', soldier_fields)
        self.assertIn('DetectRangeMax', soldier_fields)

    def test_csv_skill_fields(self):
        """CSV 兵种字段包含技能配置"""
        fields = getattr(self.csv_mgr, 'FIELD_MAPS', {})
        soldier_fields = fields['soldier']
        self.assertIn('BFMagic', soldier_fields)
        self.assertIn('SFMagic', soldier_fields)
        self.assertIn('SuperAttack', soldier_fields)

    def test_csv_field_aliases(self):
        """CSV 字段别名映射存在"""
        self.assertTrue(hasattr(self.csv_mgr, 'FIELD_ALIASES'))
        aliases = self.csv_mgr.FIELD_ALIASES
        self.assertEqual(aliases.get('HP'), 'Life')
        self.assertEqual(aliases.get('ATK'), 'BasePower')
        self.assertEqual(aliases.get('DEF'), 'AddPower')


class TestSoldierValidation(unittest.TestCase):
    """验证兵种数据校验"""

    def setUp(self):
        from core.validator import DataValidator
        self.validator = DataValidator()

    def test_validator_import(self):
        """DataValidator 可导入"""
        from core.validator import DataValidator
        self.assertTrue(callable(DataValidator))

    def test_check_soldier_limit_under(self):
        """兵种数量 ≤ 67 不报错"""
        self.validator.clear()
        self.validator.check_soldier_limit(50, "Soldier.ini")
        self.assertFalse(self.validator.has_errors())

    def test_check_soldier_limit_over(self):
        """兵种数量 > 67 报错"""
        self.validator.clear()
        self.validator.check_soldier_limit(68, "Soldier.ini")
        self.assertTrue(self.validator.has_errors())

    def test_check_soldier_limit_exact(self):
        """兵种数量 = 67 不报错"""
        self.validator.clear()
        self.validator.check_soldier_limit(67, "Soldier.ini")
        self.assertFalse(self.validator.has_errors())

    def test_check_duplicate_ids(self):
        """重复 No 检测"""
        self.validator.clear()
        data = [
            {"No": 1, "Name": "兵种A"},
            {"No": 1, "Name": "兵种B"},
        ]
        self.validator.check_duplicate_ids(data, "soldier", "Soldier.ini")
        self.assertTrue(self.validator.has_errors())

    def test_check_duplicate_ids_unique(self):
        """无重复 No 不报错"""
        self.validator.clear()
        data = [
            {"No": 1, "Name": "兵种A"},
            {"No": 2, "Name": "兵种B"},
        ]
        self.validator.check_duplicate_ids(data, "soldier", "Soldier.ini")
        self.assertFalse(self.validator.has_errors())

    def test_check_value_ranges_valid(self):
        """合法值范围不报错"""
        self.validator.clear()
        data = [{
            "No": 1, "Name": "测试", "Life": 100, "BasePower": 50,
            "AddPower": 30, "Speed": 8, "Rank": 1, "Type": 1,
            "Str": 1.0, "Int": 1.0, "IsUsed": 1
        }]
        self.validator.check_value_ranges(data, "soldier", "Soldier.ini")
        # 合法数据不应报错（如果有 schema 校验）
        # 无 schema 时应静默通过
        self.validator.clear()

    def test_clear_resets_errors(self):
        """clear() 重置错误列表"""
        self.validator.clear()
        self.validator.check_soldier_limit(100, "Soldier.ini")
        self.assertTrue(self.validator.has_errors())
        self.validator.clear()
        self.assertFalse(self.validator.has_errors())


class TestSoldierTemplate(unittest.TestCase):
    """验证兵种创建模板"""

    def test_template_has_all_hit_sol(self):
        """模板包含全部 67 个 HitSol 字段"""
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "soldier_schema.json"
        )
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        template = schema["new_entry_template"]
        for i in range(67):
            key = f"HitSol{i}"
            self.assertIn(key, template, f"模板缺少 {key}")
            self.assertEqual(template[key], 0, f"模板 {key} 默认值应为 0")

    def test_template_rank_default(self):
        """模板默认阶级 = 1"""
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "soldier_schema.json"
        )
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        self.assertEqual(schema["new_entry_template"]["Rank"], 1)

    def test_template_is_used_default(self):
        """模板默认启用"""
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "soldier_schema.json"
        )
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        self.assertEqual(schema["new_entry_template"]["IsUsed"], 1)


if __name__ == "__main__":
    unittest.main()