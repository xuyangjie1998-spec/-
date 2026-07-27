"""
San7ModMaker 错误码模块测试
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.error_codes import (
    ErrorCode, error_response, success_response, safe_error_message
)


class TestErrorCodeEnum:
    """测试错误码枚举"""

    def test_all_codes_unique(self):
        codes = [e.code for e in ErrorCode]
        assert len(codes) == len(set(codes)), f"重复错误码: {codes}"

    def test_code_format(self):
        for e in ErrorCode:
            if e.code == "OK":
                continue
            assert e.code.startswith("E"), f"{e.code} 不以 E 开头"
            assert len(e.code) == 4, f"{e.code} 长度不为4"

    def test_message_not_empty(self):
        for e in ErrorCode:
            assert e.message, f"{e.code} 消息为空"


class TestErrorResponse:
    """测试错误响应函数"""

    def test_basic_error(self):
        result = error_response(ErrorCode.GAME_PATH_NOT_SET)
        assert result["success"] is False
        assert result["error_code"] == "E100"
        assert "请先设置游戏目录" in result["message"]

    def test_error_with_detail(self):
        result = error_response(ErrorCode.FILE_NOT_FOUND, detail="custom message")
        assert result["success"] is False
        assert result["message"] == "custom message"

    def test_error_with_data(self):
        result = error_response(ErrorCode.VALIDATION_ERROR, data={"errors": ["test"]})
        assert result["data"] == {"errors": ["test"]}


class TestSuccessResponse:
    """测试成功响应函数"""

    def test_basic_success(self):
        result = success_response()
        assert result["success"] is True
        assert result["message"] == "操作成功"

    def test_success_with_data(self):
        result = success_response(data={"count": 5}, message="ok")
        assert result["success"] is True
        assert result["count"] == 5
        assert result["message"] == "ok"


class TestSafeErrorMessage:
    """测试安全错误消息函数"""

    def test_safe_path_error(self):
        """路径错误应被过滤"""
        msg = safe_error_message(FileNotFoundError("/workspace/project/data/test.ini"))
        assert "文件操作失败" in msg
        assert "/workspace" not in msg

    def test_safe_windows_path_error(self):
        msg = safe_error_message(PermissionError("C:\\Users\\test\\file.txt"))
        assert "文件操作失败" in msg
        assert "C:\\" not in msg

    def test_safe_short_error(self):
        msg = safe_error_message(ValueError("invalid value"))
        assert "ValueError" in msg
        assert "invalid value" in msg

    def test_safe_long_error_truncation(self):
        long_msg = "x" * 300
        msg = safe_error_message(RuntimeError(long_msg))
        assert len(msg) <= 250  # 有类型名前缀

    def test_safe_no_path_leak(self):
        """确保不泄露任何路径信息"""
        msg = safe_error_message(OSError("Error opening /home/user/file.txt"))
        assert "文件操作失败" in msg
        assert "/home/" not in msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])