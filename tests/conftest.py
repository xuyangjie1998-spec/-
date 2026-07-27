"""
San7ModMaker 测试共用 Fixtures
"""
import os
import sys
import tempfile
import shutil
import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_dir():
    """临时目录，测试后自动清理"""
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def mock_game_dir(temp_dir):
    """模拟游戏目录结构"""
    # 创建必要的子目录
    setting_dir = os.path.join(temp_dir, "Setting")
    shape_dir = os.path.join(temp_dir, "Shape", "Face")
    os.makedirs(setting_dir, exist_ok=True)
    os.makedirs(shape_dir, exist_ok=True)

    # 创建假的 Sango7.exe
    exe_path = os.path.join(temp_dir, "Sango7.exe")
    with open(exe_path, "wb") as f:
        f.write(b"MZ" + b"\x00" * 1024)

    return temp_dir


@pytest.fixture
def app_instance(mock_game_dir):
    """创建 San7ModMaker 实例（不加载完整游戏数据）"""
    from main import San7ModMaker
    # 设置环境变量抑制 tkinter
    os.environ.setdefault('DISPLAY', '')
    app = San7ModMaker.__new__(San7ModMaker)
    # 手动初始化基础属性（绕过 __init__ 中的完整初始化）
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
    return app


@pytest.fixture
def app_with_game(app_instance, mock_game_dir):
    """创建已设置游戏目录的实例"""
    # 设置游戏目录
    app_instance.game_path = mock_game_dir
    from core.backup_mgr import BackupManager
    from core.pck_manager import PckManager
    app_instance.backup_mgr = BackupManager(mock_game_dir)
    app_instance.pck_mgr = PckManager()
    app_instance.pck_mgr.set_game_path(mock_game_dir)
    return app_instance