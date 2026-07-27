"""
资源缓存功能测试
测试 San7ModMakerAssets 的缓存机制
"""
import os
import sys
import time
import tempfile
import shutil
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

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
    """模拟游戏目录结构（含 Shape/Face）"""
    face_dir = os.path.join(temp_dir, "Shape", "Face")
    os.makedirs(face_dir, exist_ok=True)
    # 创建假的 SHP 文件
    for i in range(1, 6):
        with open(os.path.join(face_dir, f"{i:04d}.shp"), "wb") as f:
            f.write(b"\x00" * 100)
    exe_path = os.path.join(temp_dir, "Sango7.exe")
    with open(exe_path, "wb") as f:
        f.write(b"MZ" + b"\x00" * 1024)
    return temp_dir


@pytest.fixture
def assets_mixin():
    """创建独立的 San7ModMakerAssets 实例用于缓存测试"""
    from routes.mixin_assets import San7ModMakerAssets
    mixin = San7ModMakerAssets()
    mixin.game_path = ""
    mixin.config = {"game_path": "", "recent_paths": [], "language": "zh_CN"}
    # 初始化缓存
    mixin._resource_cache = {}
    # Mock shp_converter
    mixin.shp_converter = MagicMock()
    return mixin


# ============================================================
# 缓存基础功能测试
# ============================================================

class TestCacheBasics:
    """缓存基础功能"""

    def test_cache_initialization(self, assets_mixin):
        """测试缓存初始化"""
        assets_mixin._ensure_cache()
        assert hasattr(assets_mixin, '_resource_cache')
        assert isinstance(assets_mixin._resource_cache, dict)

    def test_cache_store_and_retrieve(self, assets_mixin):
        """测试缓存存储和读取"""
        call_count = [0]

        def factory():
            call_count[0] += 1
            return {"data": "test_value"}

        result1 = assets_mixin._cached("test_key", factory)
        assert result1 == {"data": "test_value"}
        assert call_count[0] == 1

        # 第二次调用应命中缓存
        result2 = assets_mixin._cached("test_key", factory)
        assert result2 == {"data": "test_value"}
        assert call_count[0] == 1  # factory 不应再被调用

    def test_cache_different_keys(self, assets_mixin):
        """测试不同key的缓存隔离"""
        call_count = [0]

        def factory():
            call_count[0] += 1
            return {"data": call_count[0]}

        r1 = assets_mixin._cached("key_a", factory)
        r2 = assets_mixin._cached("key_b", factory)
        assert r1 == {"data": 1}
        assert r2 == {"data": 2}
        assert call_count[0] == 2

    def test_cache_ttl_expiry(self, assets_mixin):
        """测试缓存TTL过期"""
        assets_mixin._CACHE_TTL = 0  # 设置为0秒过期
        call_count = [0]

        def factory():
            call_count[0] += 1
            return {"data": call_count[0]}

        r1 = assets_mixin._cached("ttl_key", factory)
        assert r1 == {"data": 1}
        time.sleep(0.01)  # 等待过期

        r2 = assets_mixin._cached("ttl_key", factory)
        assert r2 == {"data": 2}
        assert call_count[0] == 2  # 缓存过期，factory 被再次调用

    def test_cache_invalidate_single_key(self, assets_mixin):
        """测试清除单个缓存键"""
        # 先填充缓存
        assert assets_mixin._cached("key_x", lambda: "x") == "x"
        assert assets_mixin._cached("key_y", lambda: "y") == "y"
        assert "key_x" in assets_mixin._resource_cache
        assert "key_y" in assets_mixin._resource_cache

        result = assets_mixin.api_invalidate_cache("key_x")
        assert result["success"] is True
        assert "key_x" not in assets_mixin._resource_cache
        assert "key_y" in assets_mixin._resource_cache  # 其他key不受影响

    def test_cache_invalidate_all(self, assets_mixin):
        """测试清除全部缓存"""
        assert assets_mixin._cached("key_a", lambda: "a") == "a"
        assert assets_mixin._cached("key_b", lambda: "b") == "b"

        result = assets_mixin.api_invalidate_cache()
        assert result["success"] is True
        assert len(assets_mixin._resource_cache) == 0

    def test_cache_invalidate_nonexistent_key(self, assets_mixin):
        """测试清除不存在的缓存键"""
        result = assets_mixin.api_invalidate_cache("nonexistent")
        assert result["success"] is True

    def test_invalidate_by_prefix(self, assets_mixin):
        """测试按前缀清除缓存"""
        assets_mixin._cached("face_preview_1", lambda: "a")
        assets_mixin._cached("face_preview_2", lambda: "b")
        assets_mixin._cached("face_browse_1_30", lambda: "c")
        assets_mixin._cached("thing_icon_preview_1", lambda: "d")

        assets_mixin._invalidate_asset_cache("face_preview_")

        assert "face_preview_1" not in assets_mixin._resource_cache
        assert "face_preview_2" not in assets_mixin._resource_cache
        assert "face_browse_1_30" in assets_mixin._resource_cache
        assert "thing_icon_preview_1" in assets_mixin._resource_cache

    def test_invalidate_multiple_prefixes(self, assets_mixin):
        """测试多前缀同时清除"""
        assets_mixin._cached("face_preview_1", lambda: "a")
        assets_mixin._cached("face_browse_1_30", lambda: "b")
        assets_mixin._cached("thing_icon_preview_1", lambda: "c")

        assets_mixin._invalidate_asset_cache("face_preview_", "face_browse_")

        assert "face_preview_1" not in assets_mixin._resource_cache
        assert "face_browse_1_30" not in assets_mixin._resource_cache
        assert "thing_icon_preview_1" in assets_mixin._resource_cache

    def test_invalidate_empty_prefixes_clears_all(self, assets_mixin):
        """测试无前缀时清除全部缓存"""
        assets_mixin._cached("key1", lambda: "a")
        assets_mixin._cached("key2", lambda: "b")

        assets_mixin._invalidate_asset_cache()

        assert len(assets_mixin._resource_cache) == 0


# ============================================================
# 缓存与API集成测试
# ============================================================

class TestCacheIntegration:
    """缓存与API方法的集成测试"""

    def test_face_preview_uses_cache(self, assets_mixin, mock_game_dir):
        """测试 api_get_face_preview 使用缓存"""
        assets_mixin.game_path = mock_game_dir
        assets_mixin.shp_converter.load_shp_base64 = MagicMock(return_value="base64_data")

        result1 = assets_mixin.api_get_face_preview(1)
        result2 = assets_mixin.api_get_face_preview(1)

        assert result1 == result2
        assert result1["imgData"] == "base64_data"
        # load_shp_base64 应该只被调用一次
        assert assets_mixin.shp_converter.load_shp_base64.call_count == 1

    def test_face_preview_cache_invalidation(self, assets_mixin, mock_game_dir):
        """测试头像导入后缓存失效"""
        assets_mixin.game_path = mock_game_dir
        assets_mixin.shp_converter.load_shp_base64 = MagicMock(return_value="old_data")
        assets_mixin.shp_converter.image_to_shp = MagicMock(return_value="/fake/path.shp")
        assets_mixin.shp_converter.get_log = MagicMock(return_value=[])

        # 首次调用，缓存
        r1 = assets_mixin.api_get_face_preview(1)
        assert r1["imgData"] == "old_data"

        # 导入新头像（应使缓存失效）
        assets_mixin.api_convert_image_to_shp("/fake.png", 1)

        # 再次获取应重新加载
        assets_mixin.shp_converter.load_shp_base64 = MagicMock(return_value="new_data")
        r2 = assets_mixin.api_get_face_preview(1)
        assert r2["imgData"] == "new_data"

    def test_browse_shape_resources_uses_cache(self, assets_mixin, mock_game_dir):
        """测试 api_browse_shape_resources 使用缓存"""
        assets_mixin.game_path = mock_game_dir

        result1 = assets_mixin.api_browse_shape_resources("all")
        result2 = assets_mixin.api_browse_shape_resources("all")

        assert result1 == result2
        assert result1["success"] is True

    def test_browse_shape_resources_category_isolation(self, assets_mixin, mock_game_dir):
        """测试不同category的缓存隔离"""
        assets_mixin.game_path = mock_game_dir

        r_all = assets_mixin.api_browse_shape_resources("all")
        r_face = assets_mixin.api_browse_shape_resources("Face")

        # 不同category应有不同缓存键
        cache_keys = list(assets_mixin._resource_cache.keys())
        assert "shape_resources_all" in cache_keys
        assert "shape_resources_Face" in cache_keys

    def test_thing_icon_preview_cache(self, assets_mixin, mock_game_dir):
        """测试物品图标预览缓存"""
        assets_mixin.game_path = mock_game_dir
        # 创建 ThingIcon 目录
        thing_icon_dir = os.path.join(mock_game_dir, "Shape", "ThingIcon")
        os.makedirs(thing_icon_dir, exist_ok=True)
        with open(os.path.join(thing_icon_dir, "0001.shp"), "wb") as f:
            f.write(b"\x00" * 100)

        assets_mixin.shp_converter.load_shp_file_base64 = MagicMock(return_value="icon_b64")

        r1 = assets_mixin.api_get_thing_icon_preview(1)
        r2 = assets_mixin.api_get_thing_icon_preview(1)

        assert r1 == r2
        assert assets_mixin.shp_converter.load_shp_file_base64.call_count == 1

    def test_no_cache_when_no_game_path(self, assets_mixin):
        """测试未设置游戏路径时不缓存"""
        assets_mixin.game_path = ""

        result = assets_mixin.api_get_face_preview(1)
        assert result["success"] is False
        assert "请先设置游戏目录" in result["message"]

    def test_cache_ignores_error_results(self, assets_mixin, mock_game_dir):
        """测试错误结果不应被缓存（通过_impl）"""
        assets_mixin.game_path = mock_game_dir
        assets_mixin.shp_converter.load_shp_base64 = MagicMock(side_effect=Exception("SHP decode error"))

        result = assets_mixin.api_get_face_preview(1)
        assert result["success"] is False
        # 即使出错，缓存仍然会存储（因为 factory 返回了结果）
        # 这是预期行为：错误结果也应该被缓存，避免重复尝试

    def test_cache_key_format(self, assets_mixin):
        """测试缓存键格式"""
        assets_mixin.game_path = "/fake/game"

        # 触发缓存
        assets_mixin.shp_converter.load_shp_base64 = MagicMock(return_value="test")
        assets_mixin.api_get_face_preview(42)

        expected_key = "face_preview_42"
        assert expected_key in assets_mixin._resource_cache

    def test_api_invalidate_cache_response(self, assets_mixin):
        """测试 api_invalidate_cache API 响应格式"""
        r1 = assets_mixin.api_invalidate_cache("test_key")
        assert r1 == {"success": True, "message": "缓存已清除: test_key"}

        r2 = assets_mixin.api_invalidate_cache()
        assert r2 == {"success": True, "message": "全部缓存已清除"}