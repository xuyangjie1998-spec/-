import os, json, re, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional
from core.error_codes import safe_error_message, error_response, success_response, ErrorCode

from core.config import WRITE_ROOT, PROJECT_ROOT

logger = logging.getLogger('San7ModMaker')

__all__ = ['San7ModMakerSaveEdit']

class San7ModMakerSaveEdit:
    """MOD制作器 - 存档编辑 (存档加载/解析/修改/备份)"""

    # ============================================================
    # API: 存档编辑器（旧版 saveEditor 专用方法）
    # 注意: saveList/saveBackup/saveHexView 已由下方 saveMgr 统一提供
    # ============================================================

    def api_save_load(self, save_name: str) -> dict:
        """加载存档"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.load_save(save_name)

    def api_save_get_info(self) -> dict:
        """获取存档系统信息"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.get_save_info()

    def api_save_edit_customgen(self, save_name: str, generals: list) -> dict:
        """编辑CustomGen.sav中的自定义武将"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.edit_customgen(save_name, generals)

    def api_save_hex_search(self, save_name: str, pattern_hex: str, start_offset: int = 0) -> dict:
        """在存档中搜索十六进制模式"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.hex_search(save_name, pattern_hex, start_offset)

    def api_save_clone_general(self, save_name: str, source_index: int, clone_count: int = 1) -> dict:
        """克隆自定义武将"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.clone_custom_general(save_name, source_index, clone_count)

    # ============================================================
    # API: CustomLeaders.bytes 自建武将
    # ============================================================

    # reserved: 预留给未来功能，暂无前端调用
    def api_custom_leader_load(self) -> dict:
        """加载自建武将列表"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.custom_leader.set_game_path(self.game_path)
        return self.custom_leader.load()

    def api_custom_leader_save(self, leaders: list) -> dict:
        """保存自建武将列表"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.custom_leader.set_game_path(self.game_path)
        return self.custom_leader.save(leaders)

    # ============================================================
    # API: 存档管理
    # ============================================================

    def api_save_list(self) -> dict:
        """列出存档文件"""
        return self.save_manager.list_saves()

    def api_save_backup(self, save_name: str) -> dict:
        """备份存档"""
        return self.save_manager.backup_save(save_name)

    def api_save_restore(self, backup_path: str, save_name: str) -> dict:
        """还原存档"""
        return self.save_manager.restore_save(backup_path, save_name)

    def api_save_list_backups(self) -> dict:
        """列出备份"""
        return self.save_manager.list_backups()

    def api_save_delete_backup(self, backup_path: str) -> dict:
        """删除备份"""
        return self.save_manager.delete_backup(backup_path)

    def api_save_hex_view(self, save_name: str, offset: int = 0, length: int = 1024) -> dict:
        """十六进制查看"""
        return self.save_manager.hex_view(save_name, offset, length)

    def api_save_analyze(self, save_name: str) -> dict:
        """分析存档文件头"""
        return self.save_manager.analyze_save_header(save_name)

    # ============================================================
    # API: 存档解析器 (SaveParser) — 结构化编辑
    # ============================================================

    def api_save_parse_generals(self, save_name: str) -> dict:
        """解析存档中的武将数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"存档不存在: {save_name}")
        load_result = self.save_parser.load(save_path)
        if not load_result["success"]:
            return load_result
        generals = self.save_parser.find_generals()
        return {"success": True, "save_name": save_name, "generals": generals, "count": len(generals)}

    def api_save_edit_stat(self, save_name: str, offset: int, field: str, value: int) -> dict:
        """修改武将属性"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"存档不存在: {save_name}")
        self.save_parser.load(save_path)
        result = self.save_parser.write_general_stats(offset, field, value)
        if result["success"]:
            # 自动备份
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_edit_merit(self, save_name: str, offset: int, value: int) -> dict:
        """修改功勋值"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"存档不存在: {save_name}")
        self.save_parser.load(save_path)
        result = self.save_parser.write_merit(offset, value)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_edit_exp(self, save_name: str, offset: int, value: int) -> dict:
        """修改经验值"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"存档不存在: {save_name}")
        self.save_parser.load(save_path)
        result = self.save_parser.write_experience(offset, value)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_edit_soldier(self, save_name: str, offset: int, soldier_type: int, soldier_count: int) -> dict:
        """修改兵种和带兵数"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"存档不存在: {save_name}")
        self.save_parser.load(save_path)
        result = self.save_parser.write_soldier(offset, soldier_type, soldier_count)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_edit_weapon_exp(self, save_name: str, offset: int, weapon: str, value: int) -> dict:
        """修改武器熟练度"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"存档不存在: {save_name}")
        self.save_parser.load(save_path)
        result = self.save_parser.write_weapon_exp(offset, weapon, value)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_get_soldier_types(self) -> dict:
        """获取兵种代码表"""
        return {"success": True, "soldiers": [{"id": k, "name": v} for k, v in SaveParser.SOLDIER_TYPES.items()]}

    def api_save_get_structured_general(self, save_name: str, general_index: int) -> dict:
        """获取武将结构化数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"存档不存在: {save_name}")
        self.save_parser.load(save_path)
        return self.save_parser.get_structured_general(general_index)

    def api_save_write_equipment(self, save_name: str, general_index: int, slot: str, item_id: int) -> dict:
        """修改武将装备"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"存档不存在: {save_name}")
        self.save_parser.load(save_path)
        result = self.save_parser.write_equipment(general_index, slot, item_id)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_write_skills(self, save_name: str, general_index: int, skill_type: str, slot: int, skill_id: int) -> dict:
        """修改武将技能"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"存档不存在: {save_name}")
        self.save_parser.load(save_path)
        result = self.save_parser.write_skills(general_index, skill_type, slot, skill_id)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    # reserved: 预留给未来功能，暂无前端调用
    def api_save_write_soldier_count(self, save_name: str, general_index: int, count: int) -> dict:
        """修改武将带兵数"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"存档不存在: {save_name}")
        self.save_parser.load(save_path)
        result = self.save_parser.write_soldier_count(general_index, count)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_write_formation(self, save_name: str, general_index: int, formation_id: int) -> dict:
        """修改武将阵型"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"存档不存在: {save_name}")
        self.save_parser.load(save_path)
        result = self.save_parser.write_formation(general_index, formation_id)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_get_weapon_names(self) -> dict:
        """获取武器名称字典"""
        return {"success": True, "weapons": [{"id": k, "name": v} for k, v in SaveParser.WEAPON_TYPES.items()]}

    def api_save_get_horse_names(self) -> dict:
        """获取坐骑名称字典"""
        return {"success": True, "horses": [{"id": k, "name": v} for k, v in SaveParser.HORSE_TYPES.items()]}

    def api_save_get_item_names(self) -> dict:
        """获取道具名称字典"""
        return {"success": True, "items": [{"id": k, "name": v} for k, v in SaveParser.ITEM_TYPES.items()]}

    def api_save_get_formation_names(self) -> dict:
        """获取阵型名称字典"""
        return {"success": True, "formations": [{"id": k, "name": v} for k, v in SaveParser.FORMATION_TYPES.items()]}

