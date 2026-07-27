"""
San7ModMaker 结构化错误码
用于 API 返回统一错误格式，避免泄露内部路径信息
"""

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(Enum):
    """API 错误码枚举"""
    # 通用
    SUCCESS = ("OK", "操作成功")
    UNKNOWN = ("E000", "未知错误")
    INTERNAL = ("E001", "内部服务器错误")

    # 游戏目录
    GAME_PATH_NOT_SET = ("E100", "请先设置游戏目录")
    GAME_PATH_INVALID = ("E101", "游戏目录无效")
    GAME_PATH_NOT_FOUND = ("E102", "游戏目录不存在")
    GAME_PATH_NO_SETTING = ("E103", "未检测到 Setting 目录，请解包资源")
    GAME_PATH_NO_EXE = ("E104", "未找到 Sango7.exe")

    # 文件操作
    FILE_NOT_FOUND = ("E200", "文件不存在")
    FILE_READ_ERROR = ("E201", "文件读取失败")
    FILE_WRITE_ERROR = ("E202", "文件写入失败")
    FILE_FORMAT_ERROR = ("E203", "文件格式错误")
    FILE_PERMISSION_ERROR = ("E204", "文件权限不足")

    # 数据校验
    VALIDATION_ERROR = ("E300", "数据校验未通过")
    DUPLICATE_ID = ("E301", "存在重复 ID")
    MISSING_ID = ("E302", "缺少必要 ID")
    VALUE_RANGE_ERROR = ("E303", "数值超出范围")
    REFERENCE_ERROR = ("E304", "引用完整性检查失败")

    # MOD 操作
    MOD_NOT_FOUND = ("E400", "MOD 不存在")
    MOD_ALREADY_EXISTS = ("E401", "MOD 已存在")
    MOD_NAME_INVALID = ("E402", "MOD 名称无效")
    MOD_CREATE_FAILED = ("E403", "MOD 创建失败")

    # 参数校验
    INVALID_PARAM = ("E500", "参数无效")
    MISSING_PARAM = ("E501", "缺少必要参数")
    PARAM_TYPE_ERROR = ("E502", "参数类型错误")

    # 安全
    PATH_TRAVERSAL = ("E600", "检测到路径遍历攻击")
    UNSAFE_OPERATION = ("E601", "不安全的操作")

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message


def error_response(
    error: ErrorCode,
    detail: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """生成标准错误响应，不泄露内部路径信息"""
    result: Dict[str, Any] = {
        "success": False,
        "error_code": error.code,
        "message": detail if detail else error.message,
    }
    if data:
        result["data"] = data
    return result


def success_response(
    data: Optional[Dict[str, Any]] = None,
    message: str = "操作成功"
) -> Dict[str, Any]:
    """生成标准成功响应"""
    result: Dict[str, Any] = {
        "success": True,
        "message": message,
    }
    if data:
        result.update(data)
    return result


def safe_error_message(error: Exception) -> str:
    """安全地提取错误信息，不泄露内部路径"""
    error_type = type(error).__name__
    error_msg = str(error)

    # 如果是文件路径相关的错误，只返回类型信息
    if any(keyword in error_msg.lower() for keyword in
           ['/workspace', '/home/', '/Users/', 'c:\\', 'd:\\', 'path', 'directory']):
        return f"{error_type}: 文件操作失败"

    # 限制错误消息长度
    if len(error_msg) > 200:
        return f"{error_type}: {error_msg[:200]}..."

    return f"{error_type}: {error_msg}"