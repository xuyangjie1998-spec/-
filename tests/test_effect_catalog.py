"""
effect_catalog 模块单元测试
验证特效知识库的加载、CRUD 操作、JSON 持久化
"""
import os
import sys
import json
import unittest
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEffectCatalogLoad(unittest.TestCase):
    """验证数据加载和 JSON 持久化"""

    def setUp(self):
        from core.effect_catalog import EffectCatalog
        self.catalog = EffectCatalog()

    def test_ball_types_loaded(self):
        data = self.catalog.get_ball_types()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['count'], 16)
        self.assertEqual(data['data'][0]['id'], 0)
        self.assertEqual(data['data'][0]['name'], '默认/无弹道')

    def test_damage_types_loaded(self):
        data = self.catalog.get_damage_types()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 9)

    def test_element_types_loaded(self):
        data = self.catalog.get_element_types()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 6)

    def test_item_scripts_loaded(self):
        data = self.catalog.get_item_scripts()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['count'], 20)

    def test_weapon_glow_loaded(self):
        data = self.catalog.get_weapon_glow_info()
        self.assertTrue(data['success'])
        self.assertIn('known_glow_count', data['data'])

    def test_atk_types_loaded(self):
        data = self.catalog.get_atk_types()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 9)

    def test_templates_loaded(self):
        data = self.catalog.get_effect_templates()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['count'], 16)

    def test_get_all_catalogs(self):
        data = self.catalog.get_all_catalogs()
        self.assertTrue(data['success'])
        self.assertIn('ball_types', data)
        self.assertIn('damage_types', data)
        self.assertIn('templates', data)

    def test_json_file_exists(self):
        json_path = self.catalog._get_json_path()
        self.assertTrue(os.path.exists(json_path), f"JSON 文件不存在: {json_path}")

    def test_json_file_valid(self):
        json_path = self.catalog._get_json_path()
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertIn('ball_types', data)
        self.assertIn('templates', data)
        self.assertIsInstance(data['ball_types'], list)
        self.assertIsInstance(data['templates'], list)


class TestEffectCatalogCRUD(unittest.TestCase):
    """验证 CRUD 操作"""

    def setUp(self):
        from core.effect_catalog import EffectCatalog
        self.catalog = EffectCatalog()

    def tearDown(self):
        # 清理测试数据
        self.catalog.delete_type('ball', 999)
        self.catalog.delete_type('templates', 'test_unit_tpl')

    def test_add_ball_type(self):
        result = self.catalog.save_type('ball', {
            'id': 999, 'name': '单元测试弹道', 'desc': '测试',
            'visual': 'T', 'color': '#ff00ff'
        })
        self.assertTrue(result['success'], f"添加失败: {result}")
        data = self.catalog.get_ball_types()
        self.assertIn(999, [d['id'] for d in data['data']])

    def test_delete_ball_type(self):
        # 先添加
        self.catalog.save_type('ball', {
            'id': 999, 'name': '单元测试弹道', 'desc': '测试',
            'visual': 'T', 'color': '#ff00ff'
        })
        result = self.catalog.delete_type('ball', 999)
        self.assertTrue(result['success'], f"删除失败: {result}")
        data = self.catalog.get_ball_types()
        self.assertNotIn(999, [d['id'] for d in data['data']])

    def test_update_ball_type(self):
        original = self.catalog.get_ball_types()['data'][0].copy()
        result = self.catalog.save_type('ball', {
            'id': 0, 'name': '已修改名称', 'desc': '已修改描述',
            'visual': 'M', 'color': '#00ff00'
        }, item_id=0)
        self.assertTrue(result['success'], f"更新失败: {result}")
        # 恢复
        self.catalog.save_type('ball', original, item_id=0)

    def test_add_template(self):
        result = self.catalog.save_type('templates', {
            'id': 'test_unit_tpl', 'name': '测试模板',
            'desc': '单元测试', 'example': 'test',
            'tags': ['test'],
            'params': {'Ball': 0, 'DamageType': 0, 'Element': 0,
                       'Atk': 0, 'MP': 0, 'ATK': 0, 'Level': 1,
                       'Range': 1, 'Target': 0, 'Damage': 1.0}
        })
        self.assertTrue(result['success'], f"模板添加失败: {result}")

    def test_delete_template(self):
        self.catalog.save_type('templates', {
            'id': 'test_unit_tpl', 'name': '测试模板',
            'desc': '单元测试', 'example': 'test',
            'tags': ['test'],
            'params': {'Ball': 0, 'DamageType': 0, 'Element': 0,
                       'Atk': 0, 'MP': 0, 'ATK': 0, 'Level': 1,
                       'Range': 1, 'Target': 0, 'Damage': 1.0}
        })
        result = self.catalog.delete_type('templates', 'test_unit_tpl')
        self.assertTrue(result['success'], f"模板删除失败: {result}")

    def test_duplicate_id_rejected(self):
        result = self.catalog.save_type('ball', {
            'id': 0, 'name': '重复', 'desc': '不应成功',
            'visual': 'X', 'color': '#000'
        })
        self.assertFalse(result['success'])

    def test_unknown_type_rejected(self):
        result = self.catalog.save_type('nonexistent', {'id': 1})
        self.assertFalse(result['success'])

    def test_delete_nonexistent(self):
        result = self.catalog.delete_type('ball', 99999)
        self.assertFalse(result['success'])

    def test_add_glow_id(self):
        result = self.catalog.save_type('glow', {
            'id': 999, 'name': '测试发光', 'desc': '测试',
            'color': '#ff0000', 'example': '测试武器'
        })
        self.assertTrue(result['success'], f"发光添加失败: {result}")
        self.catalog.delete_type('glow', 999)

    def test_add_item_script(self):
        result = self.catalog.save_type('items', {
            'id': 999, 'name': '测试特效', 'desc': '测试',
            'weapon_example': '测试武器'
        })
        self.assertTrue(result['success'], f"物品特效添加失败: {result}")
        self.catalog.delete_type('items', 999)


class TestEffectCatalogPersistence(unittest.TestCase):
    """验证 JSON 持久化"""

    def setUp(self):
        from core.effect_catalog import EffectCatalog, _FALLBACK_BALL_TYPES
        self.catalog = EffectCatalog()
        self._FALLBACK_BALL_TYPES = _FALLBACK_BALL_TYPES
        self.EffectCatalog = EffectCatalog

    def tearDown(self):
        # 确保清理残留
        self.catalog.delete_type('ball', 999)
        self.catalog.delete_type('glow', 999)
        self.catalog.delete_type('items', 999)
        self.catalog.delete_type('templates', 'test_unit_tpl')

    def test_save_to_json_creates_file(self):
        result = self.catalog._save_to_json()
        self.assertTrue(result)
        json_path = self.catalog._get_json_path()
        self.assertTrue(os.path.exists(json_path))

    def test_save_and_reload_preserves_data(self):
        # 记录原始数据
        original_balls = [b.copy() for b in self.catalog.BALL_TYPES]
        # 修改
        self.catalog.BALL_TYPES.append({'id': 999, 'name': '持久化测试', 'desc': 'test',
                                        'visual': 'P', 'color': '#ff0000'})
        self.catalog._save_to_json()
        # 重新加载
        new_catalog = self.EffectCatalog()
        ids = [b['id'] for b in new_catalog.BALL_TYPES]
        self.assertIn(999, ids)
        # 清理
        self.catalog.BALL_TYPES = original_balls
        self.catalog._save_to_json()
        # 验证已清理
        verify = self.EffectCatalog()
        verify_ids = [b['id'] for b in verify.BALL_TYPES]
        self.assertNotIn(999, verify_ids)

    def test_atomic_write_no_tmp_leftover(self):
        self.catalog._save_to_json()
        json_dir = os.path.dirname(self.catalog._get_json_path())
        tmp_files = [f for f in os.listdir(json_dir) if f.endswith('.tmp')]
        self.assertEqual(len(tmp_files), 0, f"残留 .tmp 文件: {tmp_files}")


if __name__ == '__main__':
    unittest.main()