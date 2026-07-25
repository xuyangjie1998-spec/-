"""
字段映射工具：Schema内部名称 ↔ 游戏INI实际字段名
加载时：game_name → schema_name（反向映射）
保存时：schema_name → game_name（正向映射）
"""

import os
import json
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FieldMapper:
    """双向字段名映射器"""

    _instance = None
    _mappings: Dict[str, Dict[str, Dict[str, str]]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._mappings:
            self._load()

    def _load(self):
        """加载映射配置文件"""
        mapping_path = os.path.join(PROJECT_ROOT, "data", "field_mapping.json")
        if os.path.exists(mapping_path):
            with open(mapping_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for category in data:
                if category.startswith("_"):
                    continue
                self._mappings[category] = {
                    "schema_to_game": data[category].get("schema_to_game", {}),
                    "game_to_schema": data[category].get("game_to_schema", {}),
                }

    def reload(self):
        """重新加载映射配置"""
        self._mappings = {}
        self._load()

    def schema_to_game(self, category: str, schema_name: str) -> str:
        """Schema内部名 → 游戏INI字段名"""
        mapping = self._mappings.get(category, {}).get("schema_to_game", {})
        return mapping.get(schema_name, schema_name)

    def game_to_schema(self, category: str, game_name: str) -> str:
        """游戏INI字段名 → Schema内部名"""
        mapping = self._mappings.get(category, {}).get("game_to_schema", {})
        return mapping.get(game_name, game_name)

    def entry_to_game(self, category: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        """将整个条目从schema名映射到游戏名"""
        mapping = self._mappings.get(category, {}).get("schema_to_game", {})
        result = {}
        for key, value in entry.items():
            game_key = mapping.get(key, key)
            result[game_key] = value
        return result

    def entry_to_schema(self, category: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        """将整个条目从游戏名映射到schema名"""
        mapping = self._mappings.get(category, {}).get("game_to_schema", {})
        result = {}
        for key, value in entry.items():
            schema_key = mapping.get(key, key)
            result[schema_key] = value
        return result

    def entries_to_game(self, category: str, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量：schema名 → 游戏名"""
        return [self.entry_to_game(category, e) for e in entries]

    def entries_to_schema(self, category: str, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量：游戏名 → schema名"""
        return [self.entry_to_schema(category, e) for e in entries]

    def get_all_mappings(self, category: str) -> Dict[str, str]:
        """获取某类别的全部映射（schema→game）"""
        return dict(self._mappings.get(category, {}).get("schema_to_game", {}))

    def get_all_reverse_mappings(self, category: str) -> Dict[str, str]:
        """获取某类别的全部反向映射（game→schema）"""
        return dict(self._mappings.get(category, {}).get("game_to_schema", {}))