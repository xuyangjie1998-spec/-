"""
San7ModMaker MOD制作向导测试套件
覆盖 ModWizard 核心路径：模板管理/步骤跟踪/依赖检查/示例数据
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestModWizard(unittest.TestCase):
    """MOD制作向导测试"""

    @classmethod
    def setUpClass(cls):
        from core.mod_wizard import ModWizard
        cls.ModWizard = ModWizard

    def setUp(self):
        self.wizard = self.ModWizard()

    # ============================================================
    # 基础功能
    # ============================================================

    def test_import(self):
        """模块可导入"""
        from core.mod_wizard import ModWizard
        self.assertTrue(callable(ModWizard))

    def test_init(self):
        """初始化正常"""
        self.assertIsNone(self.wizard.active_template)
        self.assertEqual(self.wizard.progress, {})

    # ============================================================
    # 模板管理
    # ============================================================

    def test_get_templates(self):
        """获取所有模板"""
        templates = self.wizard.get_templates()
        self.assertGreaterEqual(len(templates), 4)
        # 检查必要模板
        template_ids = [t["id"] for t in templates]
        self.assertIn("new_general", template_ids)
        self.assertIn("new_nation", template_ids)
        self.assertIn("new_soldier", template_ids)
        self.assertIn("new_item", template_ids)
        self.assertIn("full_mod", template_ids)

    def test_template_structure(self):
        """模板结构正确"""
        templates = self.wizard.get_templates()
        for t in templates:
            self.assertIn("id", t)
            self.assertIn("name", t)
            self.assertIn("description", t)
            self.assertIn("step_count", t)
            self.assertIn("required_count", t)
            self.assertGreater(t["step_count"], 0)

    def test_start_template(self):
        """开始模板"""
        result = self.wizard.start_template("new_general")
        self.assertTrue(result["success"])
        self.assertEqual(result["template"], "新增武将")
        self.assertIn("steps", result)
        self.assertIn("checklist", result)
        self.assertIn("progress", result)
        self.assertEqual(len(result["steps"]), 5)

    def test_start_template_unknown(self):
        """未知模板"""
        result = self.wizard.start_template("nonexistent")
        self.assertFalse(result["success"])

    # ============================================================
    # 步骤跟踪
    # ============================================================

    def test_mark_step_complete(self):
        """标记步骤完成"""
        self.wizard.start_template("new_general")
        result = self.wizard.mark_step_complete("new_general", 0)
        self.assertTrue(result["success"])
        self.assertEqual(result["completed"], 1)
        self.assertEqual(result["total"], 5)

    def test_mark_all_steps(self):
        """标记所有步骤完成"""
        self.wizard.start_template("new_general")
        for i in range(5):
            result = self.wizard.mark_step_complete("new_general", i)
            self.assertTrue(result["success"])
        # 最后一步标记后应全部完成
        self.assertTrue(result["all_done"])
        self.assertEqual(result["pct"], 100)

    def test_mark_step_out_of_range(self):
        """超出范围的步骤"""
        self.wizard.start_template("new_general")
        result = self.wizard.mark_step_complete("new_general", 99)
        self.assertFalse(result["success"])

    def test_mark_step_no_template(self):
        """未开始模板"""
        result = self.wizard.mark_step_complete("new_general", 0)
        self.assertFalse(result["success"])

    # ============================================================
    # 进度查询
    # ============================================================

    def test_get_progress(self):
        """获取进度"""
        self.wizard.start_template("new_soldier")
        self.wizard.mark_step_complete("new_soldier", 0)
        self.wizard.mark_step_complete("new_soldier", 1)
        progress = self.wizard.get_progress("new_soldier")
        self.assertTrue(progress["active"])
        self.assertEqual(progress["completed"], 2)
        self.assertEqual(progress["total"], 5)
        self.assertEqual(progress["pct"], 40)

    def test_get_progress_default(self):
        """获取当前活动模板进度"""
        self.wizard.start_template("new_item")
        progress = self.wizard.get_progress()
        self.assertTrue(progress["active"])

    def test_get_progress_no_active(self):
        """无活动模板"""
        progress = self.wizard.get_progress()
        self.assertFalse(progress["active"])

    # ============================================================
    # 依赖检查
    # ============================================================

    def test_get_dependencies_general(self):
        """武将文件依赖"""
        deps = self.wizard.get_file_dependencies("General01.ini")
        self.assertIn("required", deps)
        self.assertIn("DefSkill.ini", deps["required"])
        self.assertIn("General02.ini", deps["required"])
        self.assertIn("TermText.ini", deps["required"])
        self.assertIn("optional", deps)
        self.assertIn("notes", deps)

    def test_get_dependencies_soldier(self):
        """兵种文件依赖"""
        deps = self.wizard.get_file_dependencies("Soldier.ini")
        self.assertIn("TermText.ini", deps["required"])
        self.assertIn("BFSoldier.obd", deps["optional"])

    def test_get_dependencies_thing(self):
        """物品文件依赖"""
        deps = self.wizard.get_file_dependencies("Thing.ini")
        self.assertIn("TermText.ini", deps["required"])
        self.assertIn("CitySellItem.ini", deps["optional"])

    def test_get_dependencies_nation(self):
        """势力文件依赖"""
        deps = self.wizard.get_file_dependencies("Nation.ini")
        self.assertIn("City01.ini", deps["required"])
        self.assertIn("City10.ini", deps["required"])

    def test_get_dependencies_unknown(self):
        """未知文件依赖"""
        deps = self.wizard.get_file_dependencies("Unknown.ini")
        self.assertEqual(deps["required"], [])
        self.assertEqual(deps["optional"], [])

    # ============================================================
    # 示例数据
    # ============================================================

    def test_sample_new_general(self):
        """新增武将示例数据"""
        sample = self.ModWizard.SAMPLES.get("new_general")
        self.assertIsNotNone(sample)
        self.assertEqual(sample["name"], "示例武将: 岳飞")
        data = sample["data"]
        self.assertIn("No", data)
        self.assertIn("Name", data)
        self.assertIn("WStr", data)

    def test_sample_new_soldier(self):
        """新增兵种示例数据"""
        sample = self.ModWizard.SAMPLES.get("new_soldier")
        self.assertIsNotNone(sample)
        self.assertIn("data", sample)

    def test_sample_new_soldier_cav(self):
        """骑兵模板示例"""
        sample = self.ModWizard.SAMPLES.get("new_soldier_cav")
        self.assertIsNotNone(sample)
        self.assertEqual(sample["data"]["Type"], "1")

    def test_sample_new_soldier_archer(self):
        """弓兵模板示例"""
        sample = self.ModWizard.SAMPLES.get("new_soldier_archer")
        self.assertIsNotNone(sample)
        self.assertEqual(sample["data"]["Type"], "2")

    # ============================================================
    # 模板完整性
    # ============================================================

    def test_template_checklist(self):
        """每个模板都有检查清单"""
        for tid, t in self.ModWizard.TEMPLATES.items():
            self.assertIn("checklist", t)
            self.assertGreater(len(t["checklist"]), 0)

    def test_template_steps_ordered(self):
        """模板步骤有序号"""
        for tid, t in self.ModWizard.TEMPLATES.items():
            steps = t["steps"]
            for i, s in enumerate(steps):
                self.assertEqual(s["order"], i + 1)

    def test_template_has_required_steps(self):
        """每个模板至少有一个必要步骤"""
        for tid, t in self.ModWizard.TEMPLATES.items():
            required = [s for s in t["steps"] if s["required"]]
            self.assertGreater(len(required), 0, f"{tid} 缺少必要步骤")

    # ============================================================
    # 多模板切换
    # ============================================================

    def test_switch_template(self):
        """切换模板不丢失进度"""
        self.wizard.start_template("new_general")
        self.wizard.mark_step_complete("new_general", 0)
        self.wizard.start_template("new_soldier")
        self.wizard.mark_step_complete("new_soldier", 0)
        # 检查原模板进度保留
        progress = self.wizard.get_progress("new_general")
        self.assertTrue(progress["active"])
        self.assertEqual(progress["completed"], 1)


if __name__ == "__main__":
    unittest.main()