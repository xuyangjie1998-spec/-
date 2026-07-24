"""
TermText文本映射管理器
管理TermText.ini文本映射，新增内容自动分配文本偏移，改名双向同步
"""

import os
import re
from typing import Dict, Optional, Tuple
from core.ini_parser import IniParser


class TermTextManager:
    """
    TermText.ini 文本管理器
    群7的TermText.ini格式: [TermText]
    StringCount = N
    TermText_0001 = "武将名"
    TermText_0002 = "兵种名"
    ...
    """

    TERMTEXT_SECTION = "TermText"
    TERMTEXT_KEY_PREFIX = "TermText_"

    def __init__(self, game_path: str = None):
        self.game_path = game_path
        self.parser = IniParser()
        self._text_cache: Dict[int, str] = {}
        self._reverse_cache: Dict[str, int] = {}
        self._max_id = 0
        self._loaded = False

    def load(self, game_path: str = None):
        """加载TermText.ini"""
        if game_path:
            self.game_path = game_path
        term_path = os.path.join(self.game_path, "Setting", "TermText.ini") if self.game_path else None
        if not term_path or not os.path.exists(term_path):
            self._loaded = False
            return self

        self.parser.load(term_path)
        self._build_cache()
        self._loaded = True
        return self

    def _build_cache(self):
        """构建内存缓存（处理重复文本：保留第一个，后续跳过）"""
        self._text_cache.clear()
        self._reverse_cache.clear()
        sections = self.parser.get_all_sections(self.TERMTEXT_SECTION)
        for section in sections:
            for key, value in section.entries.items():
                if key.startswith(self.TERMTEXT_KEY_PREFIX):
                    try:
                        idx = int(key[len(self.TERMTEXT_KEY_PREFIX):])
                        # 去掉引号
                        clean_value = value.strip('"').strip("'")
                        # 避免重复文本覆盖之前的映射
                        if clean_value not in self._reverse_cache:
                            self._reverse_cache[clean_value] = idx
                        self._text_cache[idx] = clean_value
                        if idx > self._max_id:
                            self._max_id = idx
                    except (ValueError, IndexError):
                        continue

    def get_text(self, text_id: int) -> str:
        """根据ID获取文本"""
        if not self._loaded:
            return f"Text_{text_id:04d}"
        return self._text_cache.get(text_id, f"Text_{text_id:04d}")

    def get_id_by_text(self, text: str) -> Optional[int]:
        """根据文本内容查找ID"""
        return self._reverse_cache.get(text)

    def set_text(self, text_id: int, text: str):
        """设置指定ID的文本"""
        key = f"{self.TERMTEXT_KEY_PREFIX}{text_id:04d}"
        self.parser.set_value(self.TERMTEXT_SECTION, key, f'"{text}"')
        self._text_cache[text_id] = text
        self._reverse_cache[text] = text_id
        if text_id > self._max_id:
            self._max_id = text_id

    def allocate_new_id(self, text: str) -> int:
        """为新内容分配文本ID"""
        # 检查是否已存在
        existing = self.get_id_by_text(text)
        if existing is not None:
            return existing

        new_id = self._max_id + 1
        self.set_text(new_id, text)
        # 更新StringCount为实际条目数（而非最大ID）
        self.parser.set_value(self.TERMTEXT_SECTION, "StringCount", str(len(self._text_cache)))
        return new_id

    def rename(self, old_text: str, new_text: str):
        """改名：双向同步"""
        text_id = self.get_id_by_text(old_text)
        if text_id is None:
            return
        self.set_text(text_id, new_text)
        del self._reverse_cache[old_text]

    def release_by_name(self, name: str):
        """根据名称释放文本条目（删除武将时使用）"""
        text_id = self.get_id_by_text(name)
        if text_id is not None:
            key = f"{self.TERMTEXT_KEY_PREFIX}{text_id:04d}"
            section = self.parser.get_section(self.TERMTEXT_SECTION)
            if section and key in section.entries:
                del section.entries[key]
            if text_id in self._text_cache:
                del self._text_cache[text_id]
            if name in self._reverse_cache:
                del self._reverse_cache[name]
            self.parser._modified = True

    def delete(self, text_id: int):
        """根据ID删除文本条目"""
        key = f"{self.TERMTEXT_KEY_PREFIX}{text_id:04d}"
        section = self.parser.get_section(self.TERMTEXT_SECTION)
        if section and key in section.entries:
            old_text = section.entries[key].strip('"')
            del section.entries[key]
            if text_id in self._text_cache:
                del self._text_cache[text_id]
            if old_text in self._reverse_cache:
                del self._reverse_cache[old_text]
            self.parser._modified = True
            return True
        return False

    def save(self):
        """保存TermText.ini"""
        if self._loaded and self.game_path:
            term_path = os.path.join(self.game_path, "Setting", "TermText.ini")
            self.parser.save(term_path)

    def get_all_texts(self) -> Dict[int, str]:
        """获取所有文本映射"""
        return dict(self._text_cache)

    def search_text(self, keyword: str) -> Dict[int, str]:
        """搜索文本"""
        result = {}
        for idx, text in self._text_cache.items():
            if keyword.lower() in text.lower():
                result[idx] = text
        return result

    def is_loaded(self) -> bool:
        return self._loaded

    # ============================================================
    # 游戏约定ID方法：物品名=14000+No, 物品描述=15000+No
    # ============================================================

    ITEM_NAME_OFFSET = 14000
    ITEM_DESC_OFFSET = 15000

    def get_item_name(self, item_no: int) -> str:
        """获取物品名称文本（14000 + 物品编号）"""
        if not self._loaded:
            return ""
        return self._text_cache.get(self.ITEM_NAME_OFFSET + item_no, "")

    def get_item_desc(self, item_no: int) -> str:
        """获取物品描述文本（15000 + 物品编号）"""
        if not self._loaded:
            return ""
        return self._text_cache.get(self.ITEM_DESC_OFFSET + item_no, "")

    def set_item_name(self, item_no: int, name: str):
        """设置物品名称文本"""
        if name:
            self.set_text(self.ITEM_NAME_OFFSET + item_no, name)

    def set_item_desc(self, item_no: int, desc: str):
        """设置物品描述文本"""
        if desc:
            self.set_text(self.ITEM_DESC_OFFSET + item_no, desc)

    # ============================================================
    # 游戏约定ID方法：兵种名=13000+No, 兵种描述=13500+No
    # 必杀名=23000+No, 必杀描述=23500+No, 武将姓氏=27000+No
    # ============================================================

    SOLDIER_NAME_OFFSET = 13000
    SOLDIER_DESC_OFFSET = 13500
    SUPERATK_NAME_OFFSET = 23000
    SUPERATK_DESC_OFFSET = 23500
    GENERAL_NAME_OFFSET = 25000
    GENERAL_SURNAME_OFFSET = 27000

    def get_soldier_name(self, soldier_no: int) -> str:
        if not self._loaded: return ""
        return self._text_cache.get(self.SOLDIER_NAME_OFFSET + soldier_no, "")

    def get_soldier_desc(self, soldier_no: int) -> str:
        if not self._loaded: return ""
        return self._text_cache.get(self.SOLDIER_DESC_OFFSET + soldier_no, "")

    def set_soldier_name(self, soldier_no: int, name: str):
        if name: self.set_text(self.SOLDIER_NAME_OFFSET + soldier_no, name)

    def set_soldier_desc(self, soldier_no: int, desc: str):
        if desc: self.set_text(self.SOLDIER_DESC_OFFSET + soldier_no, desc)

    def get_superatk_name(self, atk_no: int) -> str:
        if not self._loaded: return ""
        return self._text_cache.get(self.SUPERATK_NAME_OFFSET + atk_no, "")

    def get_superatk_desc(self, atk_no: int) -> str:
        if not self._loaded: return ""
        return self._text_cache.get(self.SUPERATK_DESC_OFFSET + atk_no, "")

    def set_superatk_name(self, atk_no: int, name: str):
        if name: self.set_text(self.SUPERATK_NAME_OFFSET + atk_no, name)

    def set_superatk_desc(self, atk_no: int, desc: str):
        if desc: self.set_text(self.SUPERATK_DESC_OFFSET + atk_no, desc)

    def get_surname(self, general_no: int) -> str:
        if not self._loaded: return ""
        return self._text_cache.get(self.GENERAL_SURNAME_OFFSET + general_no, "")

    def set_surname(self, general_no: int, surname: str):
        if surname: self.set_text(self.GENERAL_SURNAME_OFFSET + general_no, surname)