"""
event_templates 模块测试
验证 EVENT_TEMPLATES 结构和 generate_event_section() 函数
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.event_templates import EVENT_TEMPLATES, generate_event_section


class TestEventTemplatesStructure(unittest.TestCase):
    """验证模板数据结构"""

    def test_template_count(self):
        """应有 8 种 ClassType 模板"""
        self.assertEqual(len(EVENT_TEMPLATES), 8)

    def test_all_known_types(self):
        """验证所有已知模板类型"""
        expected = ["3", "5", "20", "33", "34", "37", "38", "40"]
        for t in expected:
            self.assertIn(t, EVENT_TEMPLATES, f"缺少 ClassType {t}")

    def test_template_has_name_and_fields(self):
        """每个模板应有 name 和 fields"""
        for class_type, template in EVENT_TEMPLATES.items():
            self.assertIn("name", template, f"ClassType {class_type} 缺少 name")
            self.assertIn("fields", template, f"ClassType {class_type} 缺少 fields")
            self.assertIsInstance(template["fields"], dict)
            self.assertGreater(len(template["fields"]), 0,
                               f"ClassType {class_type} fields 为空")

    def test_template_names(self):
        """验证模板名称"""
        names = {
            "3": "事件建物（物）",
            "5": "发现宝物（臣）",
            "20": "武将强化",
            "33": "武将死亡",
            "34": "建物损毁",
            "37": "事件强化",
            "38": "女将登场",
            "40": "三顾茅庐",
        }
        for class_type, expected_name in names.items():
            self.assertEqual(EVENT_TEMPLATES[class_type]["name"], expected_name)


class TestGenerateEventSection(unittest.TestCase):
    """验证 generate_event_section() 函数"""

    def test_unknown_class_type(self):
        """未知 ClassType 应返回错误注释"""
        result = generate_event_section("99", {})
        self.assertIn("Error", result)
        self.assertIn("99", result)

    def test_known_class_type_basic(self):
        """已知 ClassType 应生成有效 section"""
        result = generate_event_section("3", {"No": "100"})
        self.assertIn("[HISTORY]", result)
        self.assertIn("No = 100", result)
        self.assertIn("ClassType = 3", result)

    def test_default_values(self):
        """默认值应正确填充"""
        result = generate_event_section("5", {})
        self.assertIn("No = 0", result)
        self.assertIn("Priority = 0", result)
        self.assertIn("Age = 1", result)
        self.assertIn("S_Year = -1", result)
        self.assertIn("S_Season = -1", result)
        self.assertIn("E_Year = -1", result)
        self.assertIn("E_Season = -1", result)
        self.assertIn("PreHistory = 0", result)
        self.assertIn("IsUsed = 1", result)
        self.assertIn("Version = 1", result)

    def test_custom_params(self):
        """自定义参数应覆盖默认值"""
        params = {"No": "200", "S_Year": "192", "S_Season": "3", "Age": "4"}
        result = generate_event_section("3", params)
        self.assertIn("No = 200", result)
        self.assertIn("S_Year = 192", result)
        self.assertIn("S_Season = 3", result)
        self.assertIn("Age = 4", result)

    def test_template_fields_in_output(self):
        """模板字段应出现在输出中"""
        result = generate_event_section("3", {"No": "1"})
        # ClassType 3 的字段
        for field in ["LordA", "LordALv", "LordB", "LordBLv",
                      "S_ProposeGeneral", "S_ProposeString",
                      "data01", "data02", "data03",
                      "S_General01", "S_StringA01", "S_StringD01"]:
            self.assertIn(f"{field} = 0", result,
                          f"缺少字段 {field}")

    def test_template_fields_with_custom_values(self):
        """模板字段自定义值应生效"""
        params = {"No": "1", "LordA": "579", "data01": "42", "data02": "100"}
        result = generate_event_section("3", params)
        self.assertIn("LordA = 579", result)
        self.assertIn("data01 = 42", result)
        self.assertIn("data02 = 100", result)

    def test_ends_with_newline(self):
        """输出应以空行结尾"""
        result = generate_event_section("3", {"No": "1"})
        self.assertTrue(result.endswith("\n"))

    def test_section_starts_with_history(self):
        """所有有效生成应以 [HISTORY] 开头"""
        for class_type in EVENT_TEMPLATES:
            result = generate_event_section(class_type, {"No": "1"})
            self.assertTrue(result.startswith("[HISTORY]"),
                            f"ClassType {class_type} 不以 [HISTORY] 开头")

    def test_all_eight_types_generate(self):
        """所有 8 种模板类型应生成非空输出"""
        for class_type in EVENT_TEMPLATES:
            result = generate_event_section(class_type, {"No": "1"})
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 50,
                               f"ClassType {class_type} 输出过短")
            self.assertIn("ClassType = " + class_type, result)

    def test_type_20_has_strength_fields(self):
        """武将强化 (Type 20) 应包含强化属性"""
        params = {"No": "1", "data10": "15", "data11": "10", "data12": "50", "data13": "30"}
        result = generate_event_section("20", params)
        self.assertIn("data10 = 15", result)
        self.assertIn("data11 = 10", result)
        self.assertIn("data12 = 50", result)
        self.assertIn("data13 = 30", result)

    def test_type_33_has_death_general(self):
        """武将死亡 (Type 33) 应包含死亡武将编号"""
        result = generate_event_section("33", {"No": "1", "data02": "561"})
        self.assertIn("data02 = 561", result)

    def test_type_40_has_three_generals(self):
        """三顾茅庐 (Type 40) 应包含三个武将"""
        params = {"No": "1", "S_General01": "579", "S_General02": "580", "S_General03": "581"}
        result = generate_event_section("40", params)
        self.assertIn("S_General01 = 579", result)
        self.assertIn("S_General02 = 580", result)
        self.assertIn("S_General03 = 581", result)


if __name__ == "__main__":
    unittest.main()