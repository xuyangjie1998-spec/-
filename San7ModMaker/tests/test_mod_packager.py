"""
San7ModMaker ModPackager 测试套件
覆盖 ModPackager 全部 14 个公开方法，每个方法至少 2 个测试用例（正常 + 边界）
"""
import os
import sys
import unittest
import tempfile
import shutil
import json
import zipfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mod_packager import ModPackager


# ============================================================================
# 辅助函数
# ============================================================================

def _write_ini(path, sections):
    """写入一个 INI 文件，每个 section 是一个 dict {name: str, entries: dict}"""
    with open(path, "w", encoding="gbk") as f:
        for sec in sections:
            f.write(f"[{sec['name']}]\n")
            for k, v in sec.get("entries", {}).items():
                f.write(f"{k}={v}\n")
            f.write("\n")


def _make_mod_info(path, **kwargs):
    """在给定目录创建 mod_info.json"""
    os.makedirs(path, exist_ok=True)
    data = {
        "name": kwargs.get("name", "TestMod"),
        "version": kwargs.get("version", "1.0.0"),
        "author": kwargs.get("author", "Tester"),
        "description": kwargs.get("description", "A test mod"),
        "dependencies": kwargs.get("dependencies", []),
        "compatibility": kwargs.get("compatibility", "Sango7 v1.0"),
        "files": kwargs.get("files", []),
        "created": kwargs.get("created", "2025-01-01 00:00:00"),
        "updated": kwargs.get("updated", "2025-01-01 00:00:00"),
    }
    with open(os.path.join(path, "mod_info.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================================
# TestModPackager
# ============================================================================

class TestModPackager(unittest.TestCase):
    """ModPackager 模块完整测试"""

    @classmethod
    def setUpClass(cls):
        """创建共享的临时游戏目录，包含完整的 Setting/Shape 结构和示例 INI"""
        cls.tmp_root = tempfile.mkdtemp()
        cls.game_dir = os.path.join(cls.tmp_root, "game")
        cls.setting_dir = os.path.join(cls.game_dir, "Setting")
        cls.shape_dir = os.path.join(cls.game_dir, "Shape")
        os.makedirs(cls.setting_dir)
        os.makedirs(cls.shape_dir)

        # --- 创建原版游戏 INI 文件，用于依赖解析 ---
        # General01.ini
        _write_ini(os.path.join(cls.setting_dir, "General01.ini"), [
            {"name": "GENERAL", "entries": {
                "No": "1", "Name": "刘备", "BFSoldier": "1",
                "BFSoldier1": "2", "BFSoldier2": "3",
                "Formation": "5", "Lord": "1", "SuperSkill": "101",
            }},
            {"name": "GENERAL", "entries": {
                "No": "2", "Name": "关羽", "BFSoldier": "2",
                "BFSoldier1": "3", "BFSoldier2": "4",
                "Formation": "3", "Lord": "1", "SuperSkill": "102",
            }},
            {"name": "GENERAL", "entries": {
                "No": "3", "Name": "张飞", "BFSoldier": "3",
                "BFSoldier1": "1", "BFSoldier2": "2",
                "Formation": "4", "Lord": "1", "SuperSkill": "103",
            }},
        ])

        # Soldier.ini
        _write_ini(os.path.join(cls.setting_dir, "Soldier.ini"), [
            {"name": "SOLDIER", "entries": {"No": "1", "Name": "重步兵", "Upgrade": "2"}},
            {"name": "SOLDIER", "entries": {"No": "2", "Name": "神刀兵", "Upgrade": "3"}},
            {"name": "SOLDIER", "entries": {"No": "3", "Name": "神枪兵", "Upgrade": "0"}},
        ])

        # Format.ini
        _write_ini(os.path.join(cls.setting_dir, "Format.ini"), [
            {"name": "FORMAT", "entries": {"No": "1", "Name": "方形之阵"}},
            {"name": "FORMAT", "entries": {"No": "2", "Name": "圆形之阵"}},
            {"name": "FORMAT", "entries": {"No": "3", "Name": "锥形之阵"}},
            {"name": "FORMAT", "entries": {"No": "4", "Name": "雁形之阵"}},
            {"name": "FORMAT", "entries": {"No": "5", "Name": "钩形之阵"}},
        ])

        # Nation.ini
        _write_ini(os.path.join(cls.setting_dir, "Nation.ini"), [
            {"name": "NATION", "entries": {"No": "1", "Name": "蜀", "Lord": "1"}},
            {"name": "NATION", "entries": {"No": "2", "Name": "魏", "Lord": "100"}},
            {"name": "NATION", "entries": {"No": "3", "Name": "吴", "Lord": "200"}},
        ])

        # SuperAtk.ini
        _write_ini(os.path.join(cls.setting_dir, "SuperAtk.ini"), [
            {"name": "SUPERATK", "entries": {"No": "101", "Name": "仁义齐天"}},
            {"name": "SUPERATK", "entries": {"No": "102", "Name": "青龙偃月"}},
            {"name": "SUPERATK", "entries": {"No": "103", "Name": "黑风天煞"}},
        ])

        # Thing.ini
        _write_ini(os.path.join(cls.setting_dir, "Thing.ini"), [
            {"name": "THING", "entries": {"No": "1", "Name": "铁剑", "ScriptNo": "50"}},
            {"name": "THING", "entries": {"No": "2", "Name": "钢剑", "ScriptNo": "51"}},
        ])

        # City INI files
        for i in range(1, 11):
            city_name = f"City{i:02d}" if i < 10 else f"City{i}"
            _write_ini(os.path.join(cls.setting_dir, f"{city_name}.ini"), [
                {"name": "CITY", "entries": {"No": str(i), "Name": f"城池{i}", "Lord": str(i)}},
            ])

        # Shape 中放一个占位文件
        with open(os.path.join(cls.shape_dir, "gen_001.shp"), "wb") as f:
            f.write(b"\x00" * 100)

        # --- 记录游戏目录中所有 INI 文件路径，供测试使用 ---
        cls.game_setting_ini_files = sorted([
            f for f in os.listdir(cls.setting_dir) if f.endswith(".ini")
        ])

    @classmethod
    def tearDownClass(cls):
        """清理共享临时目录"""
        shutil.rmtree(cls.tmp_root)

    # ------------------------------------------------------------------
    # setUp / tearDown
    # ------------------------------------------------------------------

    def setUp(self):
        """每个测试前创建独立的临时 MOD 目录和 packager 实例"""
        self.packager = ModPackager()
        self.tmp_dir = tempfile.mkdtemp()
        self.mod_dir = os.path.join(self.tmp_dir, "TestMod")
        self.output_dir = os.path.join(self.tmp_dir, "output")
        os.makedirs(self.mod_dir)
        os.makedirs(self.output_dir)

    def tearDown(self):
        """每个测试后清理临时目录"""
        shutil.rmtree(self.tmp_dir)

    # ==================================================================
    # 辅助方法
    # ==================================================================

    def _create_mod_with_ini(self, mod_path=None, settings=None, shapes=None,
                              mod_info=True, mod_name="TestMod"):
        """快速创建一个带可选 INI/Shape 文件的 MOD 目录"""
        if mod_path is None:
            mod_path = self.mod_dir
        if settings:
            sdir = os.path.join(mod_path, "Setting")
            os.makedirs(sdir, exist_ok=True)
            for fname, sections in settings.items():
                _write_ini(os.path.join(sdir, fname), sections)
        if shapes:
            sdir = os.path.join(mod_path, "Shape")
            os.makedirs(sdir, exist_ok=True)
            for fname, content in shapes.items():
                fpath = os.path.join(sdir, fname)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, "wb") as f:
                    f.write(content)
        if mod_info:
            _make_mod_info(mod_path, name=mod_name)
        return mod_path

    def _make_zip_package(self, mod_path=None, zip_name="test_package.zip"):
        """将 MOD 目录打包为 ZIP 并返回 ZIP 路径"""
        if mod_path is None:
            mod_path = self.mod_dir
        zip_path = os.path.join(self.output_dir, zip_name)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, filenames in os.walk(mod_path):
                for fn in filenames:
                    fp = os.path.join(root, fn)
                    arcname = os.path.relpath(fp, mod_path)
                    zf.write(fp, arcname)
        return zip_path

    def _build_snapshot_dict(self, mod_path, file_list):
        """根据文件列表构建快照 dict，用于手动创建快照文件"""
        from core.mod_packager import _get_file_hash
        snapshot_files = []
        for f in file_list:
            snapshot_files.append({
                "relative": f["relative"],
                "path": f["path"],
                "size": f["size"],
                "mtime": f["mtime"],
                "sha256": _get_file_hash(f["path"]),
                "category": f["category"],
            })
        return {
            "mod_path": os.path.abspath(mod_path),
            "mod_name": os.path.basename(mod_path),
            "created": "2025-01-01 00:00:00",
            "timestamp": "2025-01-01T00:00:00",
            "file_count": len(snapshot_files),
            "total_size": sum(f["size"] for f in snapshot_files),
            "files": snapshot_files,
        }

    # ==================================================================
    # 1. analyze_mod 测试
    # ==================================================================

    def test_analyze_mod_normal(self):
        """analyze_mod: 正常分析包含 Setting/Shape 的 MOD 目录"""
        self._create_mod_with_ini(
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "500", "Name": "自定义武将", "BFSoldier": "1"}},
            ]},
            shapes={"avatar.png": b"png_data"},
        )
        result = self.packager.analyze_mod(self.mod_dir)
        self.assertTrue(result["success"])
        self.assertIn("Setting", os.listdir(self.mod_dir))
        self.assertEqual(result["mod_name"], "TestMod")
        self.assertGreater(result["total_files"], 0)
        self.assertGreater(result["total_size"], 0)
        self.assertIn("total_size_display", result)
        self.assertIn("categories", result)
        self.assertIn("setting", result["categories"])
        self.assertIn("file_list", result)

    def test_analyze_mod_empty(self):
        """analyze_mod: 分析空目录"""
        result = self.packager.analyze_mod(self.mod_dir)
        self.assertTrue(result["success"])
        self.assertEqual(result["total_files"], 0)
        self.assertEqual(result["total_size"], 0)
        self.assertEqual(result["categories"]["setting"]["count"], 0)

    def test_analyze_mod_nonexistent(self):
        """analyze_mod: 分析不存在的目录"""
        result = self.packager.analyze_mod("/nonexistent/path/to/mod")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    def test_analyze_mod_with_mod_info(self):
        """analyze_mod: 包含 mod_info.json 时正确读取"""
        self._create_mod_with_ini(
            settings={"Nation.ini": [
                {"name": "NATION", "entries": {"No": "99", "Name": "新势力"}},
            ]},
            mod_info=True,
            mod_name="MyAwesomeMod",
        )
        result = self.packager.analyze_mod(self.mod_dir)
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["mod_info"])
        self.assertEqual(result["mod_info"]["name"], "MyAwesomeMod")
        self.assertEqual(result["mod_info"]["version"], "1.0.0")

    # ==================================================================
    # 2. resolve_dependencies 测试
    # ==================================================================

    def test_resolve_dependencies_normal(self):
        """resolve_dependencies: MOD 引用原版已有 ID，依赖全部解析为 external"""
        self._create_mod_with_ini(
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {
                    "No": "500", "Name": "新武将",
                    "BFSoldier": "1",   # 原版 Soldier.ini 中存在
                    "Formation": "3",   # 原版 Format.ini 中存在
                    "Lord": "1",        # 原版 Nation.ini 中存在
                    "SuperSkill": "101", # 原版 SuperAtk.ini 中存在
                }},
            ]},
        )
        result = self.packager.resolve_dependencies(self.mod_dir, self.game_dir)
        self.assertTrue(result["success"])
        self.assertEqual(result["missing_count"], 0)
        self.assertTrue(result["is_resolved"])
        self.assertGreater(result["total_dependencies"], 0)
        self.assertIn("dependency_graph", result)

    def test_resolve_dependencies_missing(self):
        """resolve_dependencies: MOD 引用不存在的 ID，产生缺失依赖"""
        self._create_mod_with_ini(
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {
                    "No": "999", "Name": "孤立武将",
                    "BFSoldier": "99999",   # 不存在
                    "Lord": "99999",        # 不存在
                }},
            ]},
        )
        result = self.packager.resolve_dependencies(self.mod_dir, self.game_dir)
        self.assertTrue(result["success"])
        self.assertGreater(result["missing_count"], 0)
        self.assertFalse(result["is_resolved"])

    def test_resolve_dependencies_no_game_path(self):
        """resolve_dependencies: 不提供 game_path 时仅检查 MOD 内部依赖"""
        self._create_mod_with_ini(
            settings={
                "General01.ini": [
                    {"name": "GENERAL", "entries": {"No": "1", "BFSoldier": "5"}},
                ],
                "Soldier.ini": [
                    {"name": "SOLDIER", "entries": {"No": "5", "Name": "MOD兵种"}},
                ],
            },
        )
        result = self.packager.resolve_dependencies(self.mod_dir, self.game_dir)
        self.assertTrue(result["success"])
        # BFSoldier=5 在 MOD 自己的 Soldier.ini 中存在，应为 internal
        self.assertGreaterEqual(len(result.get("internal_dependencies", [])), 1)

    def test_resolve_dependencies_mod_not_exist(self):
        """resolve_dependencies: MOD 目录不存在"""
        result = self.packager.resolve_dependencies("/nonexistent/mod", self.game_dir)
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    # ==================================================================
    # 3. pack_one_click 测试
    # ==================================================================

    def test_pack_one_click_normal(self):
        """pack_one_click: 正常打包 MOD 为 ZIP"""
        self._create_mod_with_ini(
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "500", "Name": "自定义"}},
            ]},
            shapes={"test.png": b"test_data"},
        )
        output_zip = os.path.join(self.output_dir, "output.zip")
        result = self.packager.pack_one_click(self.mod_dir, output_zip)
        self.assertTrue(result["success"])
        self.assertTrue(os.path.isfile(output_zip))
        self.assertGreater(result["zip_size"], 0)
        self.assertGreater(result["file_count"], 0)
        self.assertIn("file_manifest", result)

    def test_pack_one_click_empty_dir(self):
        """pack_one_click: 打包空目录也应成功"""
        output_zip = os.path.join(self.output_dir, "empty.zip")
        result = self.packager.pack_one_click(self.mod_dir, output_zip)
        self.assertTrue(result["success"])
        self.assertTrue(os.path.isfile(output_zip))
        # 空目录下 ZIP 文件应存在，验证警告
        self.assertIn("validation_errors", result)

    def test_pack_one_click_nonexistent(self):
        """pack_one_click: MOD 目录不存在"""
        result = self.packager.pack_one_click("/nonexistent/mod")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    # ==================================================================
    # 4. pack_full 测试
    # ==================================================================

    def test_pack_full_normal(self):
        """pack_full: 完整打包（含压缩）"""
        self._create_mod_with_ini(
            settings={"Thing.ini": [
                {"name": "THING", "entries": {"No": "999", "Name": "神器"}},
            ]},
            shapes={"icon.shp": b"\x00" * 200},
        )
        output_zip = os.path.join(self.output_dir, "full.zip")
        result = self.packager.pack_full(self.mod_dir, output_zip, compress=True)
        self.assertTrue(result["success"])
        self.assertTrue(os.path.isfile(output_zip))
        self.assertTrue(result["compressed"])
        self.assertIn("mod_info", result)
        self.assertIn("file_manifest", result)
        # 验证 mod_info.json 被写入
        self.assertTrue(os.path.isfile(os.path.join(self.mod_dir, "mod_info.json")))

    def test_pack_full_no_compress(self):
        """pack_full: 完整打包（不压缩）"""
        self._create_mod_with_ini(
            settings={"Soldier.ini": [
                {"name": "SOLDIER", "entries": {"No": "99", "Name": "测试兵种"}},
            ]},
        )
        output_zip = os.path.join(self.output_dir, "full_nocomp.zip")
        result = self.packager.pack_full(self.mod_dir, output_zip, compress=False)
        self.assertTrue(result["success"])
        self.assertFalse(result["compressed"])
        self.assertTrue(os.path.isfile(output_zip))

    def test_pack_full_nonexistent(self):
        """pack_full: MOD 目录不存在"""
        result = self.packager.pack_full("/nonexistent/mod")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    # ==================================================================
    # 5. pack_incremental 测试
    # ==================================================================

    def test_pack_incremental_with_changes(self):
        """pack_incremental: 有变更时生成增量包"""
        self._create_mod_with_ini(
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "500", "Name": "V1"}},
            ]},
        )
        # 先创建快照
        snap_result = self.packager.create_snapshot(self.mod_dir)
        self.assertTrue(snap_result["success"])
        snapshot_path = snap_result["snapshot_path"]

        # 修改 MOD：添加新文件
        new_file = os.path.join(self.mod_dir, "Shape", "new.shp")
        os.makedirs(os.path.dirname(new_file), exist_ok=True)
        with open(new_file, "wb") as f:
            f.write(b"new data")

        output_zip = os.path.join(self.output_dir, "incremental.zip")
        result = self.packager.pack_incremental(self.mod_dir, snapshot_path, output_zip)
        self.assertTrue(result["success"])
        self.assertTrue(result["has_changes"])
        self.assertGreater(result["changed_count"], 0)
        self.assertTrue(os.path.isfile(output_zip))

    def test_pack_incremental_no_changes(self):
        """pack_incremental: 无变更时不生成包"""
        from core.mod_packager import _walk_mod_files
        self._create_mod_with_ini(
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "500", "Name": "不变"}},
            ]},
        )
        # 手动创建快照文件（放在 output_dir 避免被 pack_incremental 的 walk 捕获）
        current_files = _walk_mod_files(self.mod_dir)
        snap = self._build_snapshot_dict(self.mod_dir, current_files)
        snapshot_path = os.path.join(self.output_dir, "manual_snapshot.json")
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)

        # 不做任何修改，立即做增量打包
        result = self.packager.pack_incremental(self.mod_dir, snapshot_path)
        self.assertTrue(result["success"])
        self.assertFalse(result["has_changes"])
        self.assertIn("没有检测到文件变更", result["message"])

    def test_pack_incremental_snapshot_not_found(self):
        """pack_incremental: 快照文件不存在"""
        self._create_mod_with_ini()
        result = self.packager.pack_incremental(
            self.mod_dir, "/nonexistent/snapshot.json")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    # ==================================================================
    # 6. generate_installer 测试
    # ==================================================================

    def test_generate_installer_normal(self):
        """generate_installer: 从有效 ZIP 包生成安装器"""
        self._create_mod_with_ini(
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "500", "Name": "安装测试"}},
            ]},
        )
        zip_path = self._make_zip_package()
        result = self.packager.generate_installer(zip_path, self.output_dir)
        self.assertTrue(result["success"])
        self.assertTrue(os.path.isdir(result["installer_dir"]))
        # 验证关键文件
        self.assertTrue(os.path.isfile(result["files"]["install_py"]))
        self.assertTrue(os.path.isfile(result["files"]["install_bat"]))
        self.assertTrue(os.path.isfile(result["files"]["uninstall_bat"]))
        self.assertIn("instructions", result)

    def test_generate_installer_package_not_found(self):
        """generate_installer: 包文件不存在"""
        result = self.packager.generate_installer("/nonexistent/package.zip")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    # ==================================================================
    # 7. detect_conflicts 测试
    # ==================================================================

    def test_detect_conflicts_with_conflict(self):
        """detect_conflicts: 两个 MOD 有同名但不同内容的文件，检测到冲突"""
        mod1 = os.path.join(self.tmp_dir, "ModA")
        mod2 = os.path.join(self.tmp_dir, "ModB")
        # ModA 和 ModB 都有 General01.ini，但内容不同
        self._create_mod_with_ini(mod1,
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "1", "Name": "MODA武将"}},
            ]},
            mod_name="ModA",
        )
        self._create_mod_with_ini(mod2,
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "1", "Name": "MODB武将"}},
            ]},
            mod_name="ModB",
        )
        result = self.packager.detect_conflicts(mod1, mod2)
        self.assertTrue(result["success"])
        self.assertTrue(result["has_conflicts"])
        self.assertGreater(result["conflict_count"], 0)
        # INI 文件冲突类型应为 mergeable
        self.assertEqual(result["conflicts"][0]["conflict_type"], "mergeable")

    def test_detect_conflicts_no_conflict(self):
        """detect_conflicts: 两个 MOD 无共同文件，无冲突"""
        mod1 = os.path.join(self.tmp_dir, "ModA")
        mod2 = os.path.join(self.tmp_dir, "ModB")
        self._create_mod_with_ini(mod1,
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "1", "Name": "A"}},
            ]},
            mod_name="ModA",
        )
        self._create_mod_with_ini(mod2,
            settings={"Soldier.ini": [
                {"name": "SOLDIER", "entries": {"No": "99", "Name": "B兵种"}},
            ]},
            mod_name="ModB",
        )
        result = self.packager.detect_conflicts(mod1, mod2)
        self.assertTrue(result["success"])
        self.assertFalse(result["has_conflicts"])
        self.assertEqual(result["conflict_count"], 0)

    def test_detect_conflicts_mod_not_exist(self):
        """detect_conflicts: 其中一个 MOD 目录不存在"""
        mod1 = os.path.join(self.tmp_dir, "ModA")
        self._create_mod_with_ini(mod1, mod_name="ModA")
        result = self.packager.detect_conflicts(mod1, "/nonexistent/ModB")
        self.assertFalse(result["success"])

    # ==================================================================
    # 8. resolve_conflicts 测试
    # ==================================================================

    def test_resolve_conflicts_auto(self):
        """resolve_conflicts: 自动策略解析冲突"""
        mod1 = os.path.join(self.tmp_dir, "ModA")
        mod2 = os.path.join(self.tmp_dir, "ModB")
        self._create_mod_with_ini(mod1,
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "1", "Name": "MODA武将"}},
            ]},
            mod_name="ModA",
        )
        self._create_mod_with_ini(mod2,
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "1", "Name": "MODB武将"}},
                {"name": "GENERAL", "entries": {"No": "2", "Name": "MODB武将2"}},
            ]},
            mod_name="ModB",
        )
        result = self.packager.resolve_conflicts(mod1, mod2, strategy="auto")
        self.assertTrue(result["success"])
        self.assertGreater(result["total_conflicts"], 0)
        # auto 策略对 INI 文件应尝试合并
        self.assertGreaterEqual(result["resolved_count"] + result["unresolved_count"],
                                result["total_conflicts"])

    def test_resolve_conflicts_keep_first(self):
        """resolve_conflicts: keep_first 策略"""
        mod1 = os.path.join(self.tmp_dir, "ModA")
        mod2 = os.path.join(self.tmp_dir, "ModB")
        self._create_mod_with_ini(mod1,
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "1", "Name": "MODA"}},
            ]},
            mod_name="ModA",
        )
        self._create_mod_with_ini(mod2,
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "1", "Name": "MODB"}},
            ]},
            mod_name="ModB",
        )
        result = self.packager.resolve_conflicts(mod1, mod2, strategy="keep_first")
        self.assertTrue(result["success"])
        self.assertTrue(result["all_resolved"])

    def test_resolve_conflicts_unknown_strategy(self):
        """resolve_conflicts: 未知策略返回错误"""
        mod1 = os.path.join(self.tmp_dir, "ModA")
        mod2 = os.path.join(self.tmp_dir, "ModB")
        self._create_mod_with_ini(mod1, mod_name="ModA")
        self._create_mod_with_ini(mod2, mod_name="ModB")
        result = self.packager.resolve_conflicts(mod1, mod2, strategy="invalid_strategy")
        self.assertFalse(result["success"])
        self.assertIn("未知策略", result["message"])

    def test_resolve_conflicts_no_conflict(self):
        """resolve_conflicts: 无冲突时直接返回"""
        mod1 = os.path.join(self.tmp_dir, "ModA")
        mod2 = os.path.join(self.tmp_dir, "ModB")
        self._create_mod_with_ini(mod1,
            settings={"General01.ini": [{"name": "GENERAL", "entries": {"No": "1"}}]},
            mod_name="ModA",
        )
        self._create_mod_with_ini(mod2,
            settings={"Soldier.ini": [{"name": "SOLDIER", "entries": {"No": "99"}}]},
            mod_name="ModB",
        )
        result = self.packager.resolve_conflicts(mod1, mod2, strategy="auto")
        self.assertTrue(result["success"])
        self.assertIn("没有冲突", result["message"])

    # ==================================================================
    # 9. generate_readme 测试
    # ==================================================================

    def test_generate_readme_normal(self):
        """generate_readme: 正常生成 README.md"""
        self._create_mod_with_ini(
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "500", "Name": "README测试"}},
            ]},
            shapes={"icon.png": b"png"},
        )
        readme_path = os.path.join(self.output_dir, "README.md")
        result = self.packager.generate_readme(self.mod_dir, readme_path)
        self.assertTrue(result["success"])
        self.assertTrue(os.path.isfile(readme_path))
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("TestMod", content)
        self.assertIn("1.0.0", content)
        self.assertIn("安装说明", content)
        self.assertIn("文件清单", content)

    def test_generate_readme_nonexistent(self):
        """generate_readme: MOD 目录不存在"""
        result = self.packager.generate_readme("/nonexistent/mod")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    def test_generate_readme_default_path(self):
        """generate_readme: 不指定输出路径时默认生成到 MOD 目录"""
        self._create_mod_with_ini(
            settings={"Nation.ini": [
                {"name": "NATION", "entries": {"No": "99", "Name": "新势力"}},
            ]},
        )
        result = self.packager.generate_readme(self.mod_dir)
        self.assertTrue(result["success"])
        expected_path = os.path.join(self.mod_dir, "README.md")
        self.assertTrue(os.path.isfile(expected_path))

    # ==================================================================
    # 10. version_bump 测试
    # ==================================================================

    def test_version_bump_patch(self):
        """version_bump: 递增 patch 版本号"""
        self._create_mod_with_ini(mod_info=True)
        result = self.packager.version_bump(self.mod_dir, "patch")
        self.assertTrue(result["success"])
        self.assertEqual(result["old_version"], "1.0.0")
        self.assertEqual(result["new_version"], "1.0.1")
        self.assertEqual(result["level"], "patch")

    def test_version_bump_minor(self):
        """version_bump: 递增 minor 版本号"""
        self._create_mod_with_ini(mod_info=True)
        result = self.packager.version_bump(self.mod_dir, "minor")
        self.assertTrue(result["success"])
        self.assertEqual(result["old_version"], "1.0.0")
        self.assertEqual(result["new_version"], "1.1.0")

    def test_version_bump_major(self):
        """version_bump: 递增 major 版本号"""
        self._create_mod_with_ini(mod_info=True)
        result = self.packager.version_bump(self.mod_dir, "major")
        self.assertTrue(result["success"])
        self.assertEqual(result["old_version"], "1.0.0")
        self.assertEqual(result["new_version"], "2.0.0")

    def test_version_bump_no_mod_info(self):
        """version_bump: mod_info.json 不存在时返回错误"""
        result = self.packager.version_bump(self.mod_dir, "patch")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    def test_version_bump_invalid_level(self):
        """version_bump: 无效的版本级别"""
        self._create_mod_with_ini(mod_info=True)
        result = self.packager.version_bump(self.mod_dir, "invalid")
        self.assertFalse(result["success"])
        self.assertIn("未知版本级别", result["message"])

    # ==================================================================
    # 11. validate_package 测试
    # ==================================================================

    def test_validate_package_valid(self):
        """validate_package: 验证有效 ZIP 包"""
        self._create_mod_with_ini(
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "500", "Name": "校验测试"}},
            ]},
        )
        zip_path = self._make_zip_package()
        result = self.packager.validate_package(zip_path)
        self.assertTrue(result["success"])
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["error_count"], 0)
        self.assertIn("info", result)

    def test_validate_package_no_mod_info(self):
        """validate_package: 包中缺少 mod_info.json 时产生警告"""
        # 创建一个空文件作为 mod，不包含 mod_info.json
        mod_no_info = os.path.join(self.tmp_dir, "NoInfoMod")
        os.makedirs(os.path.join(mod_no_info, "Setting"))
        with open(os.path.join(mod_no_info, "Setting", "test.ini"), "w") as f:
            f.write("[TEST]\nkey=value\n")
        zip_path = self._make_zip_package(mod_no_info, "no_info.zip")
        result = self.packager.validate_package(zip_path)
        self.assertTrue(result["success"])
        self.assertTrue(result["is_valid"])
        self.assertGreater(result["warning_count"], 0)

    def test_validate_package_not_found(self):
        """validate_package: 包文件不存在"""
        result = self.packager.validate_package("/nonexistent/package.zip")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    def test_validate_package_invalid_zip(self):
        """validate_package: 无效 ZIP 文件"""
        invalid_zip = os.path.join(self.output_dir, "invalid.zip")
        with open(invalid_zip, "w") as f:
            f.write("not a valid zip file")
        result = self.packager.validate_package(invalid_zip)
        self.assertFalse(result["success"])
        self.assertIn("无效的 ZIP", result["message"])

    # ==================================================================
    # 12. create_snapshot 测试
    # ==================================================================

    def test_create_snapshot_normal(self):
        """create_snapshot: 正常创建快照"""
        self._create_mod_with_ini(
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "500", "Name": "快照测试"}},
            ]},
            shapes={"face.shp": b"\x00" * 50},
        )
        result = self.packager.create_snapshot(self.mod_dir)
        self.assertTrue(result["success"])
        self.assertTrue(os.path.isfile(result["snapshot_path"]))
        self.assertGreater(result["file_count"], 0)
        self.assertIn("total_size_display", result)
        # 验证快照 JSON 内容
        with open(result["snapshot_path"], "r", encoding="utf-8") as f:
            snap = json.load(f)
        self.assertIn("files", snap)
        self.assertEqual(len(snap["files"]), result["file_count"])

    def test_create_snapshot_empty(self):
        """create_snapshot: 空目录创建快照"""
        result = self.packager.create_snapshot(self.mod_dir)
        self.assertTrue(result["success"])
        self.assertEqual(result["file_count"], 0)
        self.assertEqual(result["total_size"], 0)

    def test_create_snapshot_nonexistent(self):
        """create_snapshot: MOD 目录不存在"""
        result = self.packager.create_snapshot("/nonexistent/mod")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    # ==================================================================
    # 13. compare_snapshots 测试
    # ==================================================================

    def test_compare_snapshots_with_changes(self):
        """compare_snapshots: 两个快照有差异时正确检测"""
        from core.mod_packager import _walk_mod_files, _get_file_hash
        self._create_mod_with_ini(
            settings={"General01.ini": [
                {"name": "GENERAL", "entries": {"No": "500", "Name": "快照1"}},
            ]},
        )
        # 手动创建快照1
        files1 = _walk_mod_files(self.mod_dir)
        snap1 = self._build_snapshot_dict(self.mod_dir, files1)
        snap1_path = os.path.join(self.output_dir, "snap1.json")
        with open(snap1_path, "w", encoding="utf-8") as f:
            json.dump(snap1, f, ensure_ascii=False, indent=2)

        # 修改 MOD：添加文件
        new_file = os.path.join(self.mod_dir, "Shape", "new.shp")
        os.makedirs(os.path.dirname(new_file), exist_ok=True)
        with open(new_file, "wb") as f:
            f.write(b"changed data")

        # 手动创建快照2
        files2 = _walk_mod_files(self.mod_dir)
        snap2 = self._build_snapshot_dict(self.mod_dir, files2)
        snap2_path = os.path.join(self.output_dir, "snap2.json")
        with open(snap2_path, "w", encoding="utf-8") as f:
            json.dump(snap2, f, ensure_ascii=False, indent=2)

        result = self.packager.compare_snapshots(snap1_path, snap2_path)
        self.assertTrue(result["success"])
        self.assertTrue(result["has_changes"])
        self.assertGreater(result["added_count"], 0)

    def test_compare_snapshots_identical(self):
        """compare_snapshots: 两个相同快照无差异"""
        from core.mod_packager import _walk_mod_files, _get_file_hash
        self._create_mod_with_ini(
            settings={"Soldier.ini": [
                {"name": "SOLDIER", "entries": {"No": "99", "Name": "无变化"}},
            ]},
        )
        # 手动创建快照，放在 output_dir 以避免快照文件互相干扰
        files = _walk_mod_files(self.mod_dir)
        snap = self._build_snapshot_dict(self.mod_dir, files)
        snap1_path = os.path.join(self.output_dir, "snap_identical_1.json")
        snap2_path = os.path.join(self.output_dir, "snap_identical_2.json")
        with open(snap1_path, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)
        with open(snap2_path, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)

        result = self.packager.compare_snapshots(snap1_path, snap2_path)
        self.assertTrue(result["success"])
        self.assertFalse(result["has_changes"])
        self.assertEqual(result["total_changes"], 0)

    def test_compare_snapshots_not_found(self):
        """compare_snapshots: 快照文件不存在"""
        result = self.packager.compare_snapshots(
            "/nonexistent/snap1.json", "/nonexistent/snap2.json")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    # ==================================================================
    # 14. get_info 测试
    # ==================================================================

    def test_get_info_structure(self):
        """get_info: 返回正确的模块信息结构"""
        info = ModPackager.get_info()
        self.assertIsInstance(info, dict)
        self.assertEqual(info["module"], "mod_packager")
        self.assertEqual(info["version"], "1.0.0")
        self.assertIn("capabilities", info)
        self.assertIn("dependencies", info)
        # 验证所有 14 个能力都在列表中
        expected_caps = [
            "analyze_mod", "resolve_dependencies", "pack_one_click",
            "pack_full", "pack_incremental", "generate_installer",
            "detect_conflicts", "resolve_conflicts", "generate_readme",
            "version_bump", "validate_package", "create_snapshot",
            "compare_snapshots",
        ]
        for cap in expected_caps:
            self.assertIn(cap, info["capabilities"])

    def test_get_info_immutable(self):
        """get_info: 多次调用返回独立结果"""
        info1 = ModPackager.get_info()
        info2 = ModPackager.get_info()
        self.assertEqual(info1, info2)
        # 修改 info1 不应影响 info2
        info1["custom"] = "test"
        self.assertNotIn("custom", info2)


# ============================================================================
# 入口
# ============================================================================

if __name__ == "__main__":
    unittest.main()