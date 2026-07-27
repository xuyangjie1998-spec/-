"""
ini_template 模块测试
测试 core.ini_template.IniTemplateEngine 的所有公开方法

测试覆盖:
- 18 个公开方法，每个至少 2 个测试用例（正常 + 边界）
- 12 种表达式类型
- 跨文件生成（one_to_one / one_to_many / many_to_one）
- 7 个预设模板
- 6 种数据转换类型
"""
import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ini_template import IniTemplateEngine


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _make_sample_fields():
    """创建示例字段定义"""
    return [
        {"name": "No", "type": "int", "required": True, "default": "{{auto_increment:100,1}}", "description": "编号"},
        {"name": "Name", "type": "string", "required": True, "default": "测试{{counter:idx}}", "description": "名称"},
        {"name": "HP", "type": "int", "default": "{{random:100,500}}", "description": "体力"},
        {"name": "WStr", "type": "int", "default": "{{random:40,95}}", "description": "武力"},
    ]


# ---------------------------------------------------------------------------
# TestCreateTemplate
# ---------------------------------------------------------------------------

class TestCreateTemplate(unittest.TestCase):
    """测试 create_template 方法"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_template_normal(self):
        """正常创建模板 - 应返回成功"""
        fields = _make_sample_fields()
        result = self.engine.create_template("test_general", "general", fields)
        self.assertTrue(result["success"])
        self.assertEqual(result["template"]["name"], "test_general")
        self.assertEqual(result["template"]["data_type"], "general")
        self.assertEqual(len(result["template"]["fields"]), 4)
        self.assertIn("section_name", result["template"]["rules"])

    def test_create_template_with_rules(self):
        """带规则创建模板"""
        fields = _make_sample_fields()
        rules = {"start_id": 5000, "id_step": 2, "section_name": "CUSTOM"}
        result = self.engine.create_template("custom_tpl", "custom", fields, rules=rules)
        self.assertTrue(result["success"])
        self.assertEqual(result["template"]["rules"]["start_id"], 5000)
        self.assertEqual(result["template"]["rules"]["section_name"], "CUSTOM")

    def test_create_template_empty_name(self):
        """空模板名称 - 应返回错误"""
        result = self.engine.create_template("", "general", _make_sample_fields())
        self.assertFalse(result["success"])
        self.assertIn("模板名称不能为空", result["error"])

    def test_create_template_empty_fields(self):
        """空字段列表 - 应返回错误"""
        result = self.engine.create_template("bad", "general", [])
        self.assertFalse(result["success"])
        self.assertIn("字段定义不能为空", result["error"])

    def test_create_template_missing_field_name(self):
        """字段缺少 name - 应返回错误"""
        fields = [{"type": "int", "default": "1"}]
        result = self.engine.create_template("bad", "general", fields)
        self.assertFalse(result["success"])
        self.assertIn("缺少 name", result["error"])

    def test_create_template_invalid_type(self):
        """无效字段类型 - 应返回错误"""
        fields = [{"name": "x", "type": "unknown"}]
        result = self.engine.create_template("bad", "general", fields)
        self.assertFalse(result["success"])
        self.assertIn("类型", result["error"])


# ---------------------------------------------------------------------------
# TestSaveLoadTemplate
# ---------------------------------------------------------------------------

class TestSaveLoadTemplate(unittest.TestCase):
    """测试 save_template / load_template 方法"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_template_normal(self):
        """正常保存模板 - 应返回成功"""
        self.engine.create_template("saveme", "general", _make_sample_fields())
        tpl = self.engine._templates["saveme"]
        result = self.engine.save_template(tpl)
        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists(result["path"]))

    def test_save_template_custom_path(self):
        """保存到自定义路径"""
        self.engine.create_template("saveme2", "general", _make_sample_fields())
        custom_path = os.path.join(self.tmpdir, "custom", "my.json")
        result = self.engine.save_template(self.engine._templates["saveme2"], filepath=custom_path)
        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists(custom_path))

    def test_save_template_invalid(self):
        """保存无效模板 - 应返回错误"""
        result = self.engine.save_template({})
        self.assertFalse(result["success"])
        self.assertIn("无效的模板数据", result["error"])

    def test_load_template_normal(self):
        """从文件加载模板 - 应返回成功"""
        self.engine.create_template("loadme", "general", _make_sample_fields())
        self.engine.save_template(self.engine._templates["loadme"])
        filepath = os.path.join(self.tmpdir, "loadme.json")
        result = self.engine.load_template(filepath)
        self.assertTrue(result["success"])
        self.assertEqual(result["template"]["name"], "loadme")

    def test_load_template_file_not_found(self):
        """加载不存在的文件 - 应返回错误"""
        result = self.engine.load_template("/nonexistent/path.json")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["error"])

    def test_load_template_missing_name(self):
        """加载缺少 name 的 JSON - 应返回错误"""
        bad_path = os.path.join(self.tmpdir, "bad.json")
        with open(bad_path, "w", encoding="utf-8") as f:
            json.dump({"fields": []}, f)
        result = self.engine.load_template(bad_path)
        self.assertFalse(result["success"])
        self.assertIn("缺少 name", result["error"])


# ---------------------------------------------------------------------------
# TestListDeleteTemplate
# ---------------------------------------------------------------------------

class TestListDeleteTemplate(unittest.TestCase):
    """测试 list_templates / delete_template 方法"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list_templates_empty(self):
        """空模板列表"""
        result = self.engine.list_templates()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    def test_list_templates_with_data(self):
        """有模板时列出"""
        self.engine.create_template("a", "general", _make_sample_fields())
        self.engine.create_template("b", "soldier", _make_sample_fields())
        result = self.engine.list_templates()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertIn("a", result["templates"])
        self.assertIn("b", result["templates"])

    def test_delete_template_normal(self):
        """正常删除模板"""
        self.engine.create_template("delme", "general", _make_sample_fields())
        result = self.engine.delete_template("delme")
        self.assertTrue(result["success"])
        self.assertNotIn("delme", self.engine._templates)

    def test_delete_template_not_found(self):
        """删除不存在的模板 - 应返回错误"""
        result = self.engine.delete_template("nonexistent")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["error"])


# ---------------------------------------------------------------------------
# TestGenerateFromTemplate
# ---------------------------------------------------------------------------

class TestGenerateFromTemplate(unittest.TestCase):
    """测试 generate_from_template 方法"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_generate_single(self):
        """生成单条数据"""
        self.engine.create_template("gen1", "general", _make_sample_fields())
        result = self.engine.generate_from_template("gen1", 1)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(len(result["data"]), 1)
        entry = result["data"][0]
        self.assertIn("No", entry)
        self.assertIn("Name", entry)
        self.assertIn("HP", entry)

    def test_generate_multiple(self):
        """生成多条数据"""
        self.engine.create_template("gen2", "general", _make_sample_fields())
        result = self.engine.generate_from_template("gen2", 5)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 5)
        self.assertEqual(len(result["data"]), 5)

    def test_generate_with_overrides(self):
        """带覆盖字段生成"""
        self.engine.create_template("gen3", "general", _make_sample_fields())
        overrides = {"Name": "关羽"}
        result = self.engine.generate_from_template("gen3", 2, overrides=overrides)
        self.assertTrue(result["success"])
        for entry in result["data"]:
            self.assertEqual(entry["Name"], "关羽")

    def test_generate_not_found(self):
        """模板不存在 - 应返回错误"""
        result = self.engine.generate_from_template("noexist", 1)
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["error"])

    def test_generate_zero_count(self):
        """生成数量为 0 - 应返回错误"""
        self.engine.create_template("gen4", "general", _make_sample_fields())
        result = self.engine.generate_from_template("gen4", 0)
        self.assertFalse(result["success"])
        self.assertIn("必须大于0", result["error"])


# ---------------------------------------------------------------------------
# TestGenerateCrossFile
# ---------------------------------------------------------------------------

class TestGenerateCrossFile(unittest.TestCase):
    """测试 generate_cross_file 方法"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cross_file_one_to_one(self):
        """一对一关系跨文件生成"""
        self.engine.create_template("gen_a", "general", _make_sample_fields())
        self.engine.create_template("gen_b", "defskill", [
            {"name": "No", "type": "int", "default": "0"},
            {"name": "SkillName", "type": "string", "default": "技能{{counter:idx}}"},
        ])
        templates = [
            {"template": "gen_a", "count": 3, "output_label": "general"},
            {"template": "gen_b", "count": 3, "output_label": "defskill"},
        ]
        relationships = [
            {"source": "general", "target": "defskill", "source_field": "No", "target_field": "No", "type": "one_to_one"},
        ]
        result = self.engine.generate_cross_file(templates, relationships)
        self.assertTrue(result["success"])
        self.assertIn("general", result["data"])
        self.assertIn("defskill", result["data"])
        self.assertEqual(len(result["data"]["general"]), 3)
        self.assertEqual(len(result["data"]["defskill"]), 3)

    def test_cross_file_one_to_many(self):
        """一对多关系跨文件生成"""
        self.engine.create_template("gen_c", "general", _make_sample_fields())
        self.engine.create_template("gen_d", "defskill", [
            {"name": "No", "type": "int", "default": "0"},
            {"name": "SkillName", "type": "string", "default": "技能{{counter:idx}}"},
        ])
        templates = [
            {"template": "gen_c", "count": 2, "output_label": "general"},
            {"template": "gen_d", "count": 6, "output_label": "defskill"},
        ]
        relationships = [
            {"source": "general", "target": "defskill", "source_field": "No", "target_field": "No", "type": "one_to_many"},
        ]
        result = self.engine.generate_cross_file(templates, relationships)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["data"]["general"]), 2)
        self.assertEqual(len(result["data"]["defskill"]), 6)

    def test_cross_file_many_to_one(self):
        """多对一关系跨文件生成"""
        self.engine.create_template("gen_e", "general", _make_sample_fields())
        self.engine.create_template("gen_f", "defskill", [
            {"name": "No", "type": "int", "default": "0"},
            {"name": "SkillName", "type": "string", "default": "技能{{counter:idx}}"},
        ])
        templates = [
            {"template": "gen_e", "count": 5, "output_label": "general"},
            {"template": "gen_f", "count": 3, "output_label": "defskill"},
        ]
        relationships = [
            {"source": "general", "target": "defskill", "source_field": "No", "target_field": "No", "type": "many_to_one"},
        ]
        result = self.engine.generate_cross_file(templates, relationships)
        self.assertTrue(result["success"])

    def test_cross_file_empty_templates(self):
        """空模板列表 - 应返回错误"""
        result = self.engine.generate_cross_file([], [])
        self.assertFalse(result["success"])
        self.assertIn("不能为空", result["error"])

    def test_cross_file_bad_template(self):
        """包含不存在的模板 - 应返回错误"""
        templates = [
            {"template": "nonexistent", "count": 1, "output_label": "x"},
        ]
        result = self.engine.generate_cross_file(templates, [])
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# TestBatchGenerate
# ---------------------------------------------------------------------------

class TestBatchGenerate(unittest.TestCase):
    """测试 batch_generate 方法"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_batch_generate_normal(self):
        """正常批量生成"""
        self.engine.create_template("bt1", "general", _make_sample_fields())
        self.engine.create_template("bt2", "soldier", [
            {"name": "No", "type": "int", "default": "{{auto_increment:200,1}}"},
            {"name": "Name", "type": "string", "default": "兵种{{counter:idx}}"},
        ])
        requests = [
            {"template": "bt1", "count": 2, "output_target": "General01.ini"},
            {"template": "bt2", "count": 3, "output_target": "Soldier.ini"},
        ]
        result = self.engine.batch_generate(requests)
        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(result["results"][0]["success"])
        self.assertTrue(result["results"][1]["success"])

    def test_batch_generate_partial_failure(self):
        """部分失败 - 应返回混合结果"""
        self.engine.create_template("bt3", "general", _make_sample_fields())
        requests = [
            {"template": "bt3", "count": 1, "output_target": "ok.ini"},
            {"template": "nonexistent", "count": 1, "output_target": "fail.ini"},
        ]
        result = self.engine.batch_generate(requests)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(result["results"][0]["success"])
        self.assertFalse(result["results"][1]["success"])

    def test_batch_generate_empty_requests(self):
        """空请求列表 - 应返回错误"""
        result = self.engine.batch_generate([])
        self.assertFalse(result["success"])
        self.assertIn("不能为空", result["error"])


# ---------------------------------------------------------------------------
# TestEvaluateExpression - 12 种表达式类型
# ---------------------------------------------------------------------------

class TestEvaluateExpression(unittest.TestCase):
    """测试 evaluate_expression 方法（覆盖 12 种表达式类型）"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)
        self._reset_counters()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _reset_counters(self):
        self.engine._auto_increment_counters.clear()
        self.engine._named_counters.clear()

    # ---- auto_increment ----
    def test_expr_auto_increment_default(self):
        """auto_increment 默认参数"""
        self._reset_counters()
        v1 = self.engine.evaluate_expression("auto_increment", {})
        v2 = self.engine.evaluate_expression("auto_increment", {})
        self.assertEqual(v1, 0)
        self.assertEqual(v2, 1)

    def test_expr_auto_increment_custom(self):
        """auto_increment:start,step"""
        self._reset_counters()
        v1 = self.engine.evaluate_expression("auto_increment:100,5", {})
        v2 = self.engine.evaluate_expression("auto_increment:100,5", {})
        self.assertEqual(v1, 100)
        self.assertEqual(v2, 105)

    # ---- random ----
    def test_expr_random(self):
        """random:min,max"""
        for _ in range(10):
            v = self.engine.evaluate_expression("random:10,20", {})
            self.assertGreaterEqual(v, 10)
            self.assertLessEqual(v, 20)

    # ---- random_float ----
    def test_expr_random_float(self):
        """random_float:min,max"""
        for _ in range(10):
            v = self.engine.evaluate_expression("random_float:1.0,5.0", {})
            self.assertGreaterEqual(v, 1.0)
            self.assertLessEqual(v, 5.0)

    # ---- pick ----
    def test_expr_pick(self):
        """pick:a,b,c"""
        options = {"red", "blue", "green"}
        for _ in range(20):
            v = self.engine.evaluate_expression("pick:red,blue,green", {})
            self.assertIn(v, options)

    # ---- ref ----
    def test_expr_ref(self):
        """ref:template_name.field_name"""
        self.engine._generated_data_cache["gen_*"] = [{"Name": "关羽", "No": 100}]
        v = self.engine.evaluate_expression("ref:gen.Name", {"index": 0})
        self.assertEqual(v, "关羽")

    # ---- calc ----
    def test_expr_calc(self):
        """calc:expression"""
        v = self.engine.evaluate_expression("calc:2+3*4", {})
        self.assertEqual(v, 14)

    def test_expr_calc_with_context(self):
        """calc 带上下文变量"""
        v = self.engine.evaluate_expression("calc:index*10+5", {"index": 3})
        self.assertEqual(v, 35)

    # ---- sequence ----
    def test_expr_sequence(self):
        """sequence:start,step"""
        self._reset_counters()
        v1 = self.engine.evaluate_expression("sequence:0,2", {})
        v2 = self.engine.evaluate_expression("sequence:0,2", {})
        v3 = self.engine.evaluate_expression("sequence:0,2", {})
        self.assertEqual(v1, 0)
        self.assertEqual(v2, 2)
        self.assertEqual(v3, 4)

    # ---- uuid ----
    def test_expr_uuid(self):
        """uuid"""
        v = self.engine.evaluate_expression("uuid", {})
        self.assertIsInstance(v, str)
        self.assertEqual(len(v), 8)

    # ---- counter ----
    def test_expr_counter_default(self):
        """counter:name 默认参数"""
        self._reset_counters()
        v1 = self.engine.evaluate_expression("counter:mycnt", {})
        v2 = self.engine.evaluate_expression("counter:mycnt", {})
        self.assertEqual(v1, 0)
        self.assertEqual(v2, 1)

    def test_expr_counter_custom(self):
        """counter:name:start,step"""
        self._reset_counters()
        v1 = self.engine.evaluate_expression("counter:cc:10,5", {})
        v2 = self.engine.evaluate_expression("counter:cc:10,5", {})
        self.assertEqual(v1, 10)
        self.assertEqual(v2, 15)

    # ---- if ----
    def test_expr_if_true(self):
        """if:condition,true,false - 条件为真"""
        v = self.engine.evaluate_expression("if:1==1,yes,no", {})
        self.assertEqual(v, "yes")

    def test_expr_if_false(self):
        """if:condition,true,false - 条件为假"""
        v = self.engine.evaluate_expression("if:1==2,yes,no", {})
        self.assertEqual(v, "no")

    # ---- pad ----
    def test_expr_pad(self):
        """pad:width,value"""
        v = self.engine.evaluate_expression("pad:5,42", {})
        self.assertEqual(v, "00042")

    def test_expr_pad_with_variable(self):
        """pad 带内嵌表达式"""
        self._reset_counters()
        v = self.engine.evaluate_expression("pad:3,{{auto_increment:7,0}}", {})
        self.assertEqual(v, "007")

    # ---- concat ----
    def test_expr_concat(self):
        """concat:expr1,expr2,..."""
        v = self.engine.evaluate_expression("concat:hello,world", {})
        self.assertEqual(v, "helloworld")

    def test_expr_concat_with_variables(self):
        """concat 带内嵌表达式"""
        self._reset_counters()
        v = self.engine.evaluate_expression("concat:Item,{{auto_increment}}", {})
        self.assertEqual(v, "Item0")

    # ---- 边界/特殊 ----
    def test_expr_literal_number(self):
        """纯数字字面量"""
        v = self.engine.evaluate_expression("123", {})
        self.assertEqual(v, 123)

    def test_expr_literal_float(self):
        """纯浮点数字面量"""
        v = self.engine.evaluate_expression("3.14", {})
        self.assertEqual(v, 3.14)

    def test_expr_context_variable(self):
        """上下文变量引用"""
        v = self.engine.evaluate_expression("myvar", {"myvar": "hello"})
        self.assertEqual(v, "hello")


# ---------------------------------------------------------------------------
# TestResolveVariables
# ---------------------------------------------------------------------------

class TestResolveVariables(unittest.TestCase):
    """测试 resolve_variables 方法"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_resolve_simple(self):
        """解析简单表达式"""
        result = self.engine.resolve_variables("{{auto_increment:0,1}}", {})
        self.assertTrue(result.isdigit())

    def test_resolve_no_expression(self):
        """无表达式字符串原样返回"""
        result = self.engine.resolve_variables("hello world", {})
        self.assertEqual(result, "hello world")

    def test_resolve_mixed(self):
        """混合文本和表达式"""
        result = self.engine.resolve_variables("Value: {{random:10,10}}", {})
        self.assertEqual(result, "Value: 10")

    def test_resolve_non_string(self):
        """非字符串输入"""
        result = self.engine.resolve_variables(42, {})
        self.assertEqual(result, "42")


# ---------------------------------------------------------------------------
# TestValidateCrossFile
# ---------------------------------------------------------------------------

class TestValidateCrossFile(unittest.TestCase):
    """测试 validate_cross_file 方法"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_validate_clean_data(self):
        """验证无错误数据"""
        data = {
            "general": [{"No": 1, "Name": "A", "BFSoldier": "0", "Weapon": "0", "Horse": "0", "SuperSkill": "0"}],
            "soldier": [{"No": 1, "Name": "兵"}],
        }
        result = self.engine.validate_cross_file(data)
        self.assertTrue(result["success"])
        self.assertTrue(result["valid"])

    def test_validate_broken_reference(self):
        """验证断裂引用"""
        data = {
            "general": [{"No": 1, "Name": "A", "BFSoldier": "999", "Weapon": "0", "Horse": "0", "SuperSkill": "0"}],
            "soldier": [{"No": 1, "Name": "兵"}],
        }
        result = self.engine.validate_cross_file(data)
        self.assertTrue(result["success"])
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 0)

    def test_validate_duplicate_ids(self):
        """验证重复编号"""
        data = {
            "general": [
                {"No": 1, "Name": "A", "BFSoldier": "0", "Weapon": "0", "Horse": "0", "SuperSkill": "0"},
                {"No": 1, "Name": "B", "BFSoldier": "0", "Weapon": "0", "Horse": "0", "SuperSkill": "0"},
            ],
        }
        result = self.engine.validate_cross_file(data)
        self.assertTrue(result["success"])
        self.assertGreater(len(result["errors"]), 0)


# ---------------------------------------------------------------------------
# TestCheckReferences
# ---------------------------------------------------------------------------

class TestCheckReferences(unittest.TestCase):
    """测试 check_references 方法"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_check_references_valid(self):
        """有效引用检查"""
        data = {
            "general": [{"No": 1, "BFSoldier": "10"}],
            "soldier": [{"No": 10, "Name": "骑兵"}],
        }
        ref_map = {"general": {"BFSoldier": "soldier:No"}}
        result = self.engine.check_references(data, ref_map)
        self.assertTrue(result["success"])
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["broken_refs"]), 0)

    def test_check_references_broken(self):
        """断裂引用检查"""
        data = {
            "general": [{"No": 1, "BFSoldier": "999"}],
            "soldier": [{"No": 10, "Name": "骑兵"}],
        }
        ref_map = {"general": {"BFSoldier": "soldier:No"}}
        result = self.engine.check_references(data, ref_map)
        self.assertTrue(result["success"])
        self.assertFalse(result["valid"])
        self.assertEqual(len(result["broken_refs"]), 1)

    def test_check_references_bad_format(self):
        """错误格式的引用映射"""
        data = {"general": [{"No": 1, "BFSoldier": "10"}]}
        ref_map = {"general": {"BFSoldier": "bad_format"}}
        result = self.engine.check_references(data, ref_map)
        self.assertTrue(result["success"])
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["broken_refs"]), 0)


# ---------------------------------------------------------------------------
# TestConsistencyReport
# ---------------------------------------------------------------------------

class TestConsistencyReport(unittest.TestCase):
    """测试 consistency_report 方法"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_consistency_report_clean(self):
        """无错误数据的一致性报告"""
        data = {
            "general": [{"No": 1, "Name": "A", "BFSoldier": "0", "Weapon": "0", "Horse": "0", "SuperSkill": "0"}],
            "soldier": [{"No": 1}],
        }
        result = self.engine.consistency_report(data)
        self.assertTrue(result["success"])
        self.assertIn("report", result)
        self.assertIn("data_stats", result["report"])
        self.assertIn("general", result["report"]["data_stats"])

    def test_consistency_report_with_errors(self):
        """有错误数据的一致性报告"""
        data = {
            "general": [{"No": 1, "Name": "A", "BFSoldier": "999", "Weapon": "0", "Horse": "0", "SuperSkill": "0"}],
            "soldier": [{"No": 1}],
        }
        result = self.engine.consistency_report(data)
        self.assertTrue(result["success"])
        self.assertFalse(result["report"]["overall_valid"])


# ---------------------------------------------------------------------------
# TestMergeTemplates
# ---------------------------------------------------------------------------

class TestMergeTemplates(unittest.TestCase):
    """测试 merge_templates 方法"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_merge_normal(self):
        """正常合并两个模板"""
        self.engine.create_template("base", "general", [
            {"name": "No", "type": "int", "default": "0"},
            {"name": "Name", "type": "string", "default": "base"},
        ])
        self.engine.create_template("overlay", "general", [
            {"name": "Name", "type": "string", "default": "overridden"},
            {"name": "HP", "type": "int", "default": "100"},
        ])
        result = self.engine.merge_templates("base", ["overlay"])
        self.assertTrue(result["success"])
        merged = result["merged"]
        field_names = [f["name"] for f in merged["fields"]]
        self.assertIn("No", field_names)
        self.assertIn("Name", field_names)
        self.assertIn("HP", field_names)
        self.assertIn("merged_from", merged)

    def test_merge_missing_base(self):
        """基模板不存在 - 应返回错误"""
        result = self.engine.merge_templates("nonexistent", ["overlay"])
        self.assertFalse(result["success"])
        self.assertIn("基模板不存在", result["error"])

    def test_merge_skip_missing_overlay(self):
        """跳过不存在的覆盖模板"""
        self.engine.create_template("base2", "general", [
            {"name": "No", "type": "int", "default": "0"},
        ])
        result = self.engine.merge_templates("base2", ["nonexistent"])
        self.assertTrue(result["success"])


# ---------------------------------------------------------------------------
# TestApplyOverrides
# ---------------------------------------------------------------------------

class TestApplyOverrides(unittest.TestCase):
    """测试 apply_overrides 方法"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_apply_overrides_simple(self):
        """简单覆盖"""
        data = {"No": 1, "Name": "old"}
        overrides = {"Name": "new"}
        result = self.engine.apply_overrides(data, overrides)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["Name"], "new")
        self.assertEqual(result["data"]["No"], 1)

    def test_apply_overrides_nested(self):
        """嵌套点号路径覆盖"""
        data = {"general": {"Stats": {"WStr": 50}}}
        overrides = {"general.Stats.WStr": 99}
        result = self.engine.apply_overrides(data, overrides)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["general"]["Stats"]["WStr"], 99)

    def test_apply_overrides_empty_data(self):
        """空数据 - 应返回错误"""
        result = self.engine.apply_overrides({}, {"a": 1})
        self.assertFalse(result["success"])
        self.assertIn("数据不能为空", result["error"])


# ---------------------------------------------------------------------------
# TestTransformData - 6 种转换类型
# ---------------------------------------------------------------------------

class TestTransformData(unittest.TestCase):
    """测试 transform_data 方法（覆盖 6 种转换类型）"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_transform_type_cast(self):
        """type_cast 转换"""
        data = {"No": "123", "Name": "test"}
        transforms = [{"type": "type_cast", "field": "No", "cast_type": "int"}]
        result = self.engine.transform_data(data, transforms)
        self.assertTrue(result["success"])
        self.assertIsInstance(result["data"]["No"], int)
        self.assertEqual(result["data"]["No"], 123)

    def test_transform_value_map(self):
        """value_map 转换"""
        data = {"Status": "0"}
        transforms = [{"type": "value_map", "field": "Status", "mapping": {"0": "inactive", "1": "active"}}]
        result = self.engine.transform_data(data, transforms)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["Status"], "inactive")

    def test_transform_condition(self):
        """condition 转换"""
        data = {"HP": 0}
        transforms = [{"type": "condition", "condition": "HP == 0", "action": "set_field", "field": "HP", "value": "100"}]
        result = self.engine.transform_data(data, transforms)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["HP"], "100")

    def test_transform_rename(self):
        """rename 转换"""
        data = {"old_name": "value"}
        transforms = [{"type": "rename", "from": "old_name", "to": "new_name"}]
        result = self.engine.transform_data(data, transforms)
        self.assertTrue(result["success"])
        self.assertNotIn("old_name", result["data"])
        self.assertEqual(result["data"]["new_name"], "value")

    def test_transform_remove(self):
        """remove 转换"""
        data = {"keep": 1, "remove_me": 2}
        transforms = [{"type": "remove", "field": "remove_me"}]
        result = self.engine.transform_data(data, transforms)
        self.assertTrue(result["success"])
        self.assertIn("keep", result["data"])
        self.assertNotIn("remove_me", result["data"])

    def test_transform_format(self):
        """format 转换"""
        data = {"name": "Item"}
        transforms = [{"type": "format", "field": "name", "format": "[[{}]]"}]
        result = self.engine.transform_data(data, transforms)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["name"], "[[Item]]")

    def test_transform_empty_data(self):
        """空数据 - 应返回错误"""
        result = self.engine.transform_data({}, [{"type": "type_cast", "field": "x", "cast_type": "int"}])
        self.assertFalse(result["success"])
        self.assertIn("数据不能为空", result["error"])

    def test_transform_multiple(self):
        """多个转换同时应用"""
        data = {"No": "42", "old": "gone", "tag": "X"}
        transforms = [
            {"type": "type_cast", "field": "No", "cast_type": "int"},
            {"type": "rename", "from": "old", "to": "new"},
            {"type": "remove", "field": "tag"},
        ]
        result = self.engine.transform_data(data, transforms)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["No"], 42)
        self.assertEqual(result["data"]["new"], "gone")
        self.assertNotIn("tag", result["data"])
        self.assertEqual(result["applied"], 3)


# ---------------------------------------------------------------------------
# TestGetPresetTemplates - 7 个预设模板
# ---------------------------------------------------------------------------

class TestGetPresetTemplates(unittest.TestCase):
    """测试 get_preset_templates 方法（覆盖 7 个预设模板）"""

    def test_get_presets_success(self):
        """获取预设模板 - 应返回 7 个模板"""
        result = IniTemplateEngine.get_preset_templates()
        self.assertTrue(result["success"])
        self.assertIn("templates", result)
        self.assertEqual(len(result["templates"]), 7)

    def test_preset_new_general(self):
        """预设: new_general"""
        presets = IniTemplateEngine.get_preset_templates()
        tpl = presets["templates"]["new_general"]
        self.assertEqual(tpl["data_type"], "general")
        self.assertGreater(len(tpl["fields"]), 10)
        self.assertIn("WStr", [f["name"] for f in tpl["fields"]])
        self.assertIn("Int", [f["name"] for f in tpl["fields"]])

    def test_preset_new_soldier(self):
        """预设: new_soldier"""
        presets = IniTemplateEngine.get_preset_templates()
        tpl = presets["templates"]["new_soldier"]
        self.assertEqual(tpl["data_type"], "soldier")
        self.assertGreater(len(tpl["fields"]), 10)

    def test_preset_new_item(self):
        """预设: new_item"""
        presets = IniTemplateEngine.get_preset_templates()
        tpl = presets["templates"]["new_item"]
        self.assertEqual(tpl["data_type"], "thing")
        self.assertGreater(len(tpl["fields"]), 10)

    def test_preset_new_skill(self):
        """预设: new_skill"""
        presets = IniTemplateEngine.get_preset_templates()
        tpl = presets["templates"]["new_skill"]
        self.assertEqual(tpl["data_type"], "defskill")
        self.assertGreater(len(tpl["fields"]), 0)

    def test_preset_new_nation(self):
        """预设: new_nation"""
        presets = IniTemplateEngine.get_preset_templates()
        tpl = presets["templates"]["new_nation"]
        self.assertEqual(tpl["data_type"], "nation")
        self.assertIn("Lord", [f["name"] for f in tpl["fields"]])

    def test_preset_new_city(self):
        """预设: new_city"""
        presets = IniTemplateEngine.get_preset_templates()
        tpl = presets["templates"]["new_city"]
        self.assertEqual(tpl["data_type"], "city")
        self.assertGreater(len(tpl["fields"]), 0)

    def test_preset_new_superatk(self):
        """预设: new_superatk"""
        presets = IniTemplateEngine.get_preset_templates()
        tpl = presets["templates"]["new_superatk"]
        self.assertEqual(tpl["data_type"], "superatk")
        self.assertIn("NO", [f["name"] for f in tpl["fields"]])


# ---------------------------------------------------------------------------
# TestGetInfo
# ---------------------------------------------------------------------------

class TestGetInfo(unittest.TestCase):
    """测试 get_info 方法"""

    def test_get_info_basic(self):
        """获取模块信息 - 包含基础字段"""
        info = IniTemplateEngine.get_info()
        self.assertEqual(info["module"], "ini_template")
        self.assertEqual(info["version"], "1.0.0")
        self.assertIn("features", info)
        self.assertIn("supported_expressions", info)

    def test_get_info_features_count(self):
        """获取模块信息 - 功能列表正确"""
        info = IniTemplateEngine.get_info()
        self.assertGreaterEqual(len(info["features"]), 4)
        self.assertGreaterEqual(len(info["supported_expressions"]), 12)


# ---------------------------------------------------------------------------
# 整合测试
# ---------------------------------------------------------------------------

class TestIntegration(unittest.TestCase):
    """整合测试：模板创建 -> 保存 -> 加载 -> 生成 -> 验证"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_ini_tpl_")
        self.engine = IniTemplateEngine(template_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_full_workflow(self):
        """完整工作流测试"""
        # 1. 创建模板
        result = self.engine.create_template("my_gen", "general", _make_sample_fields())
        self.assertTrue(result["success"])

        # 2. 保存模板
        result = self.engine.save_template(result["template"])
        self.assertTrue(result["success"])

        # 3. 列出模板
        result = self.engine.list_templates()
        self.assertEqual(result["count"], 1)

        # 4. 生成数据
        result = self.engine.generate_from_template("my_gen", 3)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 3)

        # 5. 验证数据
        data = result["data"]
        for entry in data:
            self.assertIn("No", entry)
            self.assertIn("Name", entry)

        # 6. 删除模板
        result = self.engine.delete_template("my_gen")
        self.assertTrue(result["success"])
        self.assertEqual(self.engine.list_templates()["count"], 0)

    def test_preset_generation_workflow(self):
        """使用预设模板生成数据"""
        # 加载预设并注册
        presets = IniTemplateEngine.get_preset_templates()
        for name, tpl in presets["templates"].items():
            self.engine._templates[name] = tpl

        # 生成武将数据
        result = self.engine.generate_from_template("new_general", 3)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 3)
        for entry in result["data"]:
            self.assertIn("No", entry)
            self.assertIn("WStr", entry)
            self.assertIn("Int", entry)


if __name__ == "__main__":
    unittest.main()