"""
San7ModMaker API 路由模块测试
测试重构后的 Mixin 类 API 方法
"""
import os
import sys
import tempfile
import shutil
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def temp_dir():
    """临时目录，测试后自动清理"""
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def mock_game_dir(temp_dir):
    """模拟游戏目录结构"""
    setting_dir = os.path.join(temp_dir, "Setting")
    shape_dir = os.path.join(temp_dir, "Shape", "Face")
    os.makedirs(setting_dir, exist_ok=True)
    os.makedirs(shape_dir, exist_ok=True)
    exe_path = os.path.join(temp_dir, "Sango7.exe")
    with open(exe_path, "wb") as f:
        f.write(b"MZ" + b"\x00" * 1024)
    return temp_dir


@pytest.fixture
def app_instance(mock_game_dir):
    """创建 San7ModMaker 实例，手动初始化所有必要属性"""
    from main import San7ModMaker
    from core.ini_parser import IniParser
    from core.term_text import TermTextManager
    from core.backup_mgr import BackupManager
    from core.validator import DataValidator
    from core.shp_converter import ShpConverter
    from core.exe_patcher import ExePatcher
    from core.field_mapper import FieldMapper
    from core.pck_manager import PckManager
    from core.obd_parser import OBDParser
    from core.save_editor import SaveEditor
    from core.scriptso_analyzer import ScriptSOAnalyzer
    from core.soldier_matrix import SoldierMatrixEditor
    from core.mod_wizard import ModWizard
    from core.csv_manager import CsvManager
    from core.version_detect import VersionDetector
    from core.custom_leader import CustomLeaderParser
    from core.save_manager import SaveManager
    from core.effect_catalog import EffectCatalog
    from core.save_parser import SaveParser
    from core.encoding_converter import EncodingConverter
    from core.ini_template import IniTemplateEngine
    from core.mod_packager import ModPackager
    from core.termtext_allocator import TermTextAllocator

    os.environ.setdefault('DISPLAY', '')
    app = San7ModMaker.__new__(San7ModMaker)

    # 初始化所有属性
    app.game_path = ""
    app.config = {"game_path": "", "recent_paths": [], "language": "zh_CN"}
    app._general_cache = []
    app._soldier_cache = []
    app._thing_cache = []
    app._skill_cache = []
    app._formation_cache = []
    app._title_cache = []
    app._scenario_cache = []
    app._nation_cache = []
    app._city_cache = []
    app._defskill_cache = {}
    app._global_params_cache = None
    app._store_config_cache = None
    app._mod_custom_ids = {}

    # 初始化核心引擎实例
    app.ini_parser = IniParser()
    app.term_text = TermTextManager()
    app.backup_mgr = BackupManager(mock_game_dir)
    app.validator = DataValidator()
    app.shp_converter = ShpConverter()
    app.exe_patcher = ExePatcher()
    app.field_mapper = FieldMapper()
    app.pck_mgr = PckManager()
    app.pck_mgr.set_game_path(mock_game_dir)
    app.obd_parser = OBDParser()
    app.save_editor = SaveEditor()
    app.scriptso_analyzer = ScriptSOAnalyzer()
    app.soldier_matrix = SoldierMatrixEditor()
    app.mod_wizard = ModWizard()
    app.csv_manager = CsvManager()
    app.version_detector = VersionDetector()
    app.custom_leader = CustomLeaderParser()
    app.save_manager = SaveManager()
    app.effect_catalog = EffectCatalog()
    app.save_parser = SaveParser()
    app.encoding_converter = EncodingConverter()
    app.encoding_converter.set_game_path(mock_game_dir)
    app.ini_template = IniTemplateEngine()
    app.mod_packager = ModPackager()
    app.termtext_allocator = TermTextAllocator()

    return app


@pytest.fixture
def app_with_game(app_instance, mock_game_dir):
    """创建已设置游戏目录的实例"""
    app_instance.game_path = mock_game_dir
    app_instance.shp_converter.set_game_path(mock_game_dir)
    app_instance.exe_patcher.set_game_path(mock_game_dir)
    app_instance.obd_parser.set_game_path(mock_game_dir)
    app_instance.validator.set_game_path(mock_game_dir)
    app_instance.save_editor.set_game_path(mock_game_dir)
    app_instance.custom_leader.set_game_path(mock_game_dir)
    app_instance.scriptso_analyzer.set_game_path(mock_game_dir)
    app_instance.ini_template.game_path = mock_game_dir
    return app_instance


# ============================================================
# 测试类
# ============================================================

class TestMixinImports:
    """验证所有 Mixin 类可正常导入"""

    def test_import_mixin_base(self):
        from routes.mixin_base import San7ModMakerBase
        assert callable(San7ModMakerBase)

    def test_import_mixin_core(self):
        from routes.mixin_core import San7ModMakerCore
        assert callable(San7ModMakerCore)

    def test_import_mixin_game(self):
        from routes.mixin_game import San7ModMakerGame
        assert callable(San7ModMakerGame)

    def test_import_mixin_assets(self):
        from routes.mixin_assets import San7ModMakerAssets
        assert callable(San7ModMakerAssets)

    def test_import_mixin_tools(self):
        from routes.mixin_tools import San7ModMakerTools
        assert callable(San7ModMakerTools)

    def test_import_mixin_advanced(self):
        from routes.mixin_advanced import San7ModMakerAdvanced
        assert callable(San7ModMakerAdvanced)

    def test_import_main_app(self):
        from main import San7ModMaker
        assert callable(San7ModMaker)

    def test_mro_chain(self):
        from main import San7ModMaker
        from routes import (
            San7ModMakerBase, San7ModMakerCore, San7ModMakerGame,
            San7ModMakerAssets, San7ModMakerTools, San7ModMakerAdvanced
        )
        mro = San7ModMaker.__mro__
        for cls in [San7ModMakerBase, San7ModMakerCore, San7ModMakerGame,
                    San7ModMakerAssets, San7ModMakerTools, San7ModMakerAdvanced]:
            assert cls in mro, f"{cls.__name__} 不在 MRO 中"


class TestGamePathManagement:
    """测试游戏目录管理 API"""

    def test_set_game_path_invalid(self, app_instance):
        result = app_instance.api_set_game_path("/nonexistent/path/xyz")
        assert result["success"] is False

    def test_set_game_path_valid(self, app_instance, mock_game_dir):
        result = app_instance.api_set_game_path(mock_game_dir)
        assert result["success"] is True
        assert result["path"] == mock_game_dir

    def test_get_game_info_unconfigured(self, app_instance):
        app_instance.game_path = ""
        info = app_instance.api_get_game_info()
        assert info["configured"] is False

    def test_get_game_info_configured(self, app_with_game, mock_game_dir):
        info = app_with_game.api_get_game_info()
        assert info["configured"] is True
        assert info["has_exe"] is True

    def test_detect_game_version_no_path(self, app_instance):
        app_instance.game_path = ""
        result = app_instance.api_detect_game_version()
        assert result["success"] is False


class TestGeneralAPI:
    """测试武将编辑 API"""

    def test_load_generals_no_game_path(self, app_instance):
        app_instance.game_path = ""
        result = app_instance.api_load_generals()
        assert result["success"] is False

    def test_load_generals_no_file(self, app_with_game):
        result = app_with_game.api_load_generals()
        assert result["success"] is False

    def test_load_generals_with_data(self, app_with_game, mock_game_dir):
        import io
        general_path = os.path.join(mock_game_dir, "Setting", "General01.ini")
        with io.open(general_path, "w", encoding="big5") as f:
            f.write("[GENERAL]\nNo = 1\nName = 關羽\nStr = 98\nInt = 82\n")
        result = app_with_game.api_load_generals()
        assert result["success"] is True
        assert result["count"] >= 1


class TestModManagement:
    """测试 MOD 管理 API"""

    def test_create_mod_success(self, app_with_game, mock_game_dir):
        import time
        unique_name = f"TestMod_{int(time.time())}"
        result = app_with_game.api_create_mod(unique_name, "测试MOD")
        assert result["success"] is True

    def test_create_mod_empty_name(self, app_with_game):
        result = app_with_game.api_create_mod("", "")
        assert result["success"] is False

    def test_get_mod_list(self, app_with_game):
        result = app_with_game.api_get_mod_list()
        assert result["success"] is True
        assert isinstance(result["mods"], list)


class TestDashboardAPI:
    """测试仪表盘统计 API"""

    def test_dashboard_stats_no_game(self, app_instance):
        app_instance.game_path = ""
        result = app_instance.api_dashboard_stats()
        assert result["success"] is True

    def test_dashboard_stats_with_game(self, app_with_game):
        result = app_with_game.api_dashboard_stats()
        assert result["success"] is True
        assert "stats" in result


class TestBackupAPI:
    """测试备份管理 API"""

    def test_backup_all_no_game(self, app_instance):
        # backup_mgr 已初始化，即使 game_path 为空也能执行
        result = app_instance.api_backup_all()
        assert result["success"] is True

    def test_backup_all_with_game(self, app_with_game):
        result = app_with_game.api_backup_all()
        assert result["success"] is True

    def test_backup_status(self, app_with_game):
        result = app_with_game.api_auto_backup_status()
        assert result["success"] is True


class TestBatchOperations:
    """测试批量操作 API"""

    def test_batch_search_no_pattern(self, app_with_game):
        # 空模式返回空结果，但依然是成功响应
        result = app_with_game.api_batch_search("", "general")
        assert result["success"] is True
        assert "results" in result

    def test_batch_search_with_pattern(self, app_with_game):
        result = app_with_game.api_batch_search("test", "general")
        assert result["success"] is True


class TestValidationAPI:
    """测试数据校验 API"""

    def test_check_references_no_game(self, app_instance):
        app_instance.game_path = ""
        result = app_instance.api_check_references()
        assert result["success"] is False

    def test_check_references_with_game(self, app_with_game):
        result = app_with_game.api_check_references()
        assert result["success"] is True


class TestShpConversion:
    """测试 SHP 转换 API"""

    def test_export_shp_to_png_no_game(self, app_instance):
        app_instance.game_path = ""
        result = app_instance.api_export_shp_to_png("1", "general")
        assert result["success"] is False


class TestEncodingAPI:
    """测试编码转换 API"""

    def test_encoding_scan_no_game(self, app_instance):
        # encoding_converter 已初始化，即使 game_path 为空也能执行
        result = app_instance.api_encoding_scan()
        assert result["success"] is True

    def test_encoding_scan_with_game(self, app_with_game, mock_game_dir):
        test_file = os.path.join(mock_game_dir, "Setting", "test.ini")
        with open(test_file, "w", encoding="big5") as f:
            f.write("測試")
        result = app_with_game.api_encoding_scan()
        assert result["success"] is True


class TestEventTemplates:
    """测试事件模板 API"""

    def test_event_templates_list(self, app_instance):
        result = app_instance.api_event_templates()
        assert result["success"] is True
        assert "templates" in result

    def test_event_generate_invalid(self, app_instance):
        result = app_instance.api_event_generate("nonexistent", {})
        assert result["success"] is False


class TestExePatching:
    """测试 EXE 补丁 API"""

    def test_apply_exe_patch_no_game(self, app_instance):
        app_instance.game_path = ""
        result = app_instance.api_apply_exe_patch("test", "test", "test")
        assert result["success"] is False


class TestDevelopmentProgress:
    """测试开发进度数据结构"""

    def test_progress_milestones(self):
        from main import DEVELOPMENT_PROGRESS
        assert len(DEVELOPMENT_PROGRESS["milestones"]) == 12
        for ms in DEVELOPMENT_PROGRESS["milestones"]:
            assert ms["status"] == "completed"
            assert ms["progress"] == 100

    def test_progress_version(self):
        from main import DEVELOPMENT_PROGRESS
        assert DEVELOPMENT_PROGRESS["version"] == "3.13.0"


class TestAtomicWrite:
    """测试原子写入工具函数"""

    def test_atomic_write_basic(self, temp_dir):
        from main import atomic_write
        path = os.path.join(temp_dir, "test.txt")
        atomic_write(path, "hello world", encoding="utf-8")
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            assert f.read() == "hello world"

    def test_atomic_write_no_tmp_leftover(self, temp_dir):
        from main import atomic_write
        path = os.path.join(temp_dir, "test.txt")
        atomic_write(path, "test", encoding="utf-8")
        tmp_files = [f for f in os.listdir(temp_dir) if f.endswith('.tmp')]
        assert len(tmp_files) == 0

    def test_atomic_write_overwrite(self, temp_dir):
        from main import atomic_write
        path = os.path.join(temp_dir, "test.txt")
        atomic_write(path, "first", encoding="utf-8")
        atomic_write(path, "second", encoding="utf-8")
        with open(path, "r", encoding="utf-8") as f:
            assert f.read() == "second"

    def test_atomic_write_gbk(self, temp_dir):
        from main import atomic_write
        path = os.path.join(temp_dir, "test_gbk.txt")
        atomic_write(path, "測試", encoding="gbk")
        with open(path, "r", encoding="gbk") as f:
            assert f.read() == "測試"


class TestJsApiMap:
    """测试 JS API 映射表"""

    def test_api_map_completeness(self):
        from main import _JsApi, San7ModMaker
        missing = []
        for js_name, py_name in _JsApi._API_MAP.items():
            for cls in San7ModMaker.__mro__:
                if py_name in cls.__dict__:
                    break
            else:
                missing.append(py_name)
        assert len(missing) == 0, f"未定义的 API 方法: {missing}"

    def test_js_names_no_duplicates(self):
        """JS API 名称无重复"""
        from main import _JsApi
        from collections import Counter
        js_names = list(_JsApi._API_MAP.keys())
        dups = [n for n, c in Counter(js_names).items() if c > 1]
        assert len(dups) == 0, f"重复的 JS API 名称: {dups}"

    def test_py_methods_aliases_allowed(self):
        """Python 方法可以有别名（多个 JS 名称映射到同一方法）"""
        from main import _JsApi
        from collections import Counter
        py_names = list(_JsApi._API_MAP.values())
        dups = {n: c for n, c in Counter(py_names).items() if c > 1}
        # 允许别名，但记录它们
        assert len(dups) <= 5, f"别名过多: {dups}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])