import os, json, re, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional
from core.error_codes import safe_error_message, error_response, success_response, ErrorCode

from core.config import WRITE_ROOT, PROJECT_ROOT

logger = logging.getLogger('San7ModMaker')

__all__ = ['San7ModMakerScriptSO']

class San7ModMakerScriptSO:
    """MOD制作器 - Script.so 分析器 (ELF解析/反汇编/补丁/字符串)"""

    # ============================================================
    # API: Script.so 分析器
    # ============================================================

    def api_scriptso_info(self) -> dict:
        """获取 Script.so 基本信息"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.get_script_so_info()

    def api_scriptso_strings(self) -> dict:
        """分析 Script.so 字符串"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.analyze_strings()

    def api_scriptso_hex_view(self, offset: int = 0, length: int = 512) -> dict:
        """十六进制查看 Script.so"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.hex_view(offset, length)

    def api_scriptso_hex_search(self, pattern_hex: str) -> dict:
        """在 Script.so 中搜索十六进制模式"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.hex_search(pattern_hex)

    def api_scriptso_list_files(self) -> dict:
        """列出 Script/ 目录文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        files = self.scriptso_analyzer.list_script_files()
        return {"success": True, "files": files, "count": len(files)}

    def api_scriptso_backup(self) -> dict:
        """备份 Script.so"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.backup_script_so()

    def api_scriptso_hex_write(self, offset: int, data_hex: str) -> dict:
        """十六进制写入 Script.so"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.hex_write(offset, data_hex)

    def api_scriptso_hex_patch(self, patches: list) -> dict:
        """批量十六进制补丁"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.hex_patch(patches)

    def api_scriptso_sections(self) -> dict:
        """解析 Script.so ELF 段表"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.parse_sections()

    def api_scriptso_symbols(self) -> dict:
        """解析 Script.so 符号表"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.parse_symbols()

    def api_scriptso_string_replace(self, old_text: str, new_text: str) -> dict:
        """替换 Script.so 中的字符串"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.string_replace(old_text, new_text)

    def api_scriptso_get_patches(self) -> dict:
        """获取已知 Script.so 补丁列表"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.get_known_patches()

    def api_scriptso_search_patch(self, patch_id: str) -> dict:
        """搜索已知补丁偏移"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.search_patch_offset(patch_id)

    def api_scriptso_apply_patch(self, patch_id: str, offset: int, new_value, value_type: str = None) -> dict:
        """应用已知补丁到指定偏移"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.apply_known_patch(patch_id, offset, new_value, value_type)

    def api_scriptso_community_patches(self) -> dict:
        """获取社区教程补丁列表"""
        return self.scriptso_analyzer.get_community_patches()

    def api_scriptso_apply_community_patch(self, patch_id: str) -> dict:
        """应用社区教程补丁（字符串替换）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.apply_community_patch(patch_id)

    def api_scriptso_disassemble(self, offset: int = None, length: int = 512) -> dict:
        """反汇编 Script.so"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.disassemble(offset, length)

    def api_scriptso_find_functions(self) -> dict:
        """检测 Script.so 函数边界"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.find_functions()

    def api_scriptso_disasm_func(self, address: int) -> dict:
        """反汇编单个函数"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.disassemble_function(address)

    def api_scriptso_find_xrefs(self, address: int) -> dict:
        """查找交叉引用"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.find_xrefs_to(address)

    def api_scriptso_instruction_patch(self, address: int, mnemonic: str, operands: str = "") -> dict:
        """指令级补丁"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.instruction_patch(address, mnemonic, operands)

