"""
三国群英传7 INI结构化解析器
支持多重复Section群7特殊格式，保留原始排版、注释、空行
支持GBK/Big5编码自动检测
"""

import re
import os
import logging
import tempfile
from collections import OrderedDict
from typing import Dict, List, Tuple, Any, Optional

logger = logging.getLogger(__name__)


class SectionData:
    """单个INI Section的数据容器"""
    def __init__(self, name: str, line_number: int = 0):
        self.name = name
        self.line_number = line_number
        self.entries: Dict[str, str] = OrderedDict()
        self.comments: List[str] = []  # section前的注释
        self.raw_lines: List[str] = []  # 原始行保留
        self._modified_keys: set = set()  # 记录被修改过的key

    def get(self, key: str, default: Any = None) -> Optional[str]:
        return self.entries.get(key, default)

    def set(self, key: str, value: Any):
        self.entries[key] = str(value)
        self._modified_keys.add(key)

    def is_key_modified(self, key: str) -> bool:
        return key in self._modified_keys

    def __repr__(self):
        return f"SectionData(name={self.name}, entries={len(self.entries)})"


class IniParser:
    """
    群7专用INI解析器
    特性：
    - 支持同名Section重复出现（群7特殊格式，如[GENERAL]多个）
    - 保留原始注释、空行、格式
    - GBK/Big5编码自动检测
    - 结构化读写
    """

    def __init__(self, file_path: str = None):
        self.file_path = file_path
        self.sections: List[SectionData] = []
        self._encoding = "gbk"
        self._raw_header = ""  # 文件头部（第一个section之前的注释等）
        self._raw_header_lines: List[str] = []  # 原始头部行（含换行）
        self._line_ending = "\n"  # 检测到的行尾换行符（\n 或 \r\n）
        self._warnings: List[str] = []  # 加载过程中的警告（如重复key）
        self._modified = False

    def _detect_encoding(self, file_path: str) -> str:
        """检测文件编码：优先Big5（繁体中文，游戏原生编码），其次GBK（简体中文）"""
        try:
            with open(file_path, "rb") as f:
                raw = f.read()

            # 检测BOM标记
            if raw.startswith(b'\xef\xbb\xbf'):
                return "utf-8-sig"
            if raw.startswith(b'\xff\xfe'):
                return "utf-16-le"
            if raw.startswith(b'\xfe\xff'):
                return "utf-16-be"

            # 尝试Big5（繁体中文，游戏原生编码，优先）
            try:
                raw.decode("big5")
                return "big5"
            except (UnicodeDecodeError, UnicodeError):
                pass

            # 尝试GBK（简体中文）
            try:
                raw.decode("gbk")
                return "gbk"
            except (UnicodeDecodeError, UnicodeError):
                pass

            # 回退到GBK + replace
            return "gbk"
        except (UnicodeDecodeError, LookupError):
            return "gbk"

    def _detect_line_ending(self, file_path: str) -> str:
        """检测文件行尾换行符：\r\n (Windows) 或 \n (Unix)"""
        try:
            with open(file_path, "rb") as f:
                raw = f.read(8192)  # 只读前 8KB
            crlf_count = raw.count(b'\r\n')
            lf_count = raw.count(b'\n')
            # 如果 \r\n 出现次数 >= 单独的 \n (减去 \r\n 中的 \n)，判断为 Windows 风格
            if crlf_count > 0 and crlf_count >= (lf_count - crlf_count) / 2:
                return "\r\n"
            return "\n"
        except Exception:
            return "\n"

    def load(self, file_path: str = None) -> "IniParser":
        """加载INI文件"""
        if file_path:
            self.file_path = file_path
        if not self.file_path or not os.path.exists(self.file_path):
            return self

        self.sections = []
        self._raw_header = ""
        self._raw_header_lines = []
        self._warnings = []

        # 自动检测编码
        self._encoding = self._detect_encoding(self.file_path)

        # 检测行尾换行符
        self._line_ending = self._detect_line_ending(self.file_path)

        with open(self.file_path, "r", encoding=self._encoding, errors="replace") as f:
            lines = f.readlines()

        current_section = None
        header_lines = []
        line_idx = 0

        for line in lines:
            line_idx += 1
            stripped = line.strip()

            # 空行
            if not stripped:
                if current_section:
                    current_section.raw_lines.append(line)
                else:
                    header_lines.append(line)
                continue

            # 注释行
            if stripped.startswith(";") or stripped.startswith("#"):
                if current_section:
                    current_section.comments.append(stripped)
                    current_section.raw_lines.append(line)
                else:
                    header_lines.append(line)
                continue

            # Section头 [NAME]
            section_match = re.match(r"^\[(.+)\]$", stripped)
            if section_match:
                section_name = section_match.group(1).strip()
                current_section = SectionData(section_name, line_idx)
                current_section.raw_lines.append(line)
                self.sections.append(current_section)
                continue

            # 键值对 key = value
            kv_match = re.match(r"^([^=]+)=\s*(.*)$", stripped)
            if kv_match and current_section:
                key = kv_match.group(1).strip()
                value = kv_match.group(2).strip()
                # 去掉行尾注释
                comment_pos = value.find(";")
                if comment_pos > 0 and not value[:comment_pos].strip().endswith("\\"):
                    value = value[:comment_pos].strip()
                # 重复 key 检测
                if key in current_section.entries:
                    self._warnings.append(
                        f"[{current_section.name}] 第{line_idx}行: key \"{key}\" 重复"
                        f"（原值={current_section.entries[key]}, 新值={value}），后值覆盖前值"
                    )
                current_section.entries[key] = value
                current_section.raw_lines.append(line)
            elif current_section:
                current_section.raw_lines.append(line)

        self._raw_header = "".join(header_lines)
        self._raw_header_lines = header_lines
        return self

    def save(self, file_path: str = None) -> str:
        """保存INI文件，保留原始格式（注释、空行、未修改字段的原始行）"""
        if file_path:
            self.file_path = file_path
        if not self.file_path:
            raise ValueError("未指定保存路径")

        LE = self._line_ending
        out_lines = []

        # 写入文件头部（原始注释、空行等）
        out_lines.extend(self._raw_header_lines)
        if self._raw_header_lines and not self._raw_header_lines[-1].endswith("\n"):
            out_lines.append(LE)

        for section in self.sections:
            has_any_mod = bool(section._modified_keys)

            if has_any_mod and section.raw_lines:
                # 有修改：基于原始行重写，保留注释和空行，仅更新修改过的 key=value
                out_lines.extend(self._rebuild_section_lines(section))
            elif has_any_mod:
                # 新section（无原始行），直接写入
                out_lines.append(f"[{section.name}]{LE}")
                for key, value in section.entries.items():
                    out_lines.append(f"{key} = {value}{LE}")
                if not section.entries:
                    out_lines.append(LE)
            else:
                # 无修改：直接使用原始行
                raw_header = section.raw_lines[0] if section.raw_lines else ""
                if section.raw_lines and not raw_header.strip().startswith("["):
                    out_lines.append(f"[{section.name}]{LE}")
                out_lines.extend(section.raw_lines)
                if section.raw_lines and not section.raw_lines[-1].endswith("\n"):
                    out_lines.append(LE)
                elif not section.raw_lines:
                    out_lines.append(f"[{section.name}]{LE}")

        # 预检测编码兼容性
        all_text = "".join(out_lines)
        if not self._verify_encoding(all_text):
            logger.warning(f"文件 {self.file_path} 包含当前编码 ({self._encoding}) 不支持的字符，将尝试 GBK")
            self._encoding = "gbk"
            if not self._verify_encoding(all_text):
                logger.warning(f"文件 {self.file_path} 仍无法用 GBK 编码，回退到 UTF-8")
                self._encoding = "utf-8"

        # 原子写入：先写临时文件，再原子替换，防止写入中断导致文件损坏
        dir_name = os.path.dirname(self.file_path)
        with tempfile.NamedTemporaryFile(mode='w', encoding=self._encoding,
                                         dir=dir_name, delete=False, suffix='.tmp') as tmp:
            tmp.write(all_text)
            tmp_path = tmp.name
        os.replace(tmp_path, self.file_path)

        self._modified = False
        return self.file_path

    def _verify_encoding(self, text: str) -> bool:
        """验证文本是否可用当前编码无损编码"""
        try:
            text.encode(self._encoding)
            return True
        except UnicodeEncodeError:
            return False

    def _rebuild_section_lines(self, section: SectionData) -> List[str]:
        """基于原始行重建section内容，保留注释和空行，仅更新已修改的key"""
        LE = self._line_ending
        result = []
        written_keys = set()
        modified_keys = section._modified_keys
        kv_pattern = re.compile(r"^([^=]+)=\s*(.*)$")

        for line in section.raw_lines:
            stripped = line.strip()
            # 空行 / 注释行 / section头 — 原样保留
            if not stripped or stripped.startswith(";") or stripped.startswith("#") or stripped.startswith("["):
                result.append(line)
                continue

            match = kv_pattern.match(stripped)
            if match:
                key = match.group(1).strip()
                if key in modified_keys:
                    # 修改过的key：用新值替换
                    new_value = section.entries.get(key, "")
                    result.append(f"{key} = {new_value}{LE}")
                    written_keys.add(key)
                else:
                    # 未修改的key：原样保留
                    result.append(line)
                    written_keys.add(key)
            else:
                # 无法解析的行，原样保留
                result.append(line)

        # 追加新增的key（在raw_lines中不存在的）
        for key, value in section.entries.items():
            if key not in written_keys:
                result.append(f"{key} = {value}{LE}")

        return result

    # ---------- 高层API ----------

    def get_all_sections(self, section_name: str = None) -> List[SectionData]:
        """获取所有section，可按名称过滤"""
        if section_name:
            return [s for s in self.sections if s.name == section_name]
        return self.sections

    def get_section(self, section_name: str, index: int = 0) -> Optional[SectionData]:
        """获取指定名称的第index个section"""
        matches = self.get_all_sections(section_name)
        if 0 <= index < len(matches):
            return matches[index]
        return None

    def get_value(self, section_name: str, key: str, default: Any = None, section_index: int = 0) -> Optional[str]:
        """获取指定section中key的值"""
        section = self.get_section(section_name, section_index)
        if section:
            return section.get(key, default)
        return default

    def set_value(self, section_name: str, key: str, value: Any, section_index: int = 0):
        """设置指定section中key的值，自动创建section"""
        section = self.get_section(section_name, section_index)
        if not section:
            section = SectionData(section_name)
            self.sections.append(section)
        section.set(key, value)
        self._modified = True

    def add_section(self, section_name: str) -> SectionData:
        """新增一个section"""
        section = SectionData(section_name)
        self.sections.append(section)
        self._modified = True
        return section

    def replace_sections(self, section_name: str, data: list, id_field: str = "No") -> None:
        """原地替换指定名称的所有section，保留匹配ID的section的raw_lines以保留注释和格式

        与 "清空旧section + 新建section" 模式不同，此方法会：
        1. 对已有的section（通过id_field匹配），原地更新entries，保留raw_lines
        2. 移除不再存在的section
        3. 为新增的entry创建新section

        Args:
            section_name: section名称（如 "GENERAL", "SOLDIER", "THING"）
            data: 新数据列表，每个元素是dict（如 {"No": "1", "Name": "刘备", ...}）
            id_field: 用于匹配的ID字段名，默认 "No"
        """
        # 构建新数据的ID映射
        new_ids = {}
        for entry in data:
            eid = str(entry.get(id_field, ""))
            new_ids[eid] = entry

        kept_sections = []
        consumed_ids = set()

        for section in self.sections:
            if section.name != section_name:
                kept_sections.append(section)
                continue
            section_id = str(section.get(id_field, ""))
            if section_id and section_id in new_ids:
                # 已有section：原地更新entries，保留raw_lines
                entry = new_ids[section_id]
                for key, value in entry.items():
                    section.set(key, value)
                kept_sections.append(section)
                consumed_ids.add(section_id)
            # 不匹配的section被丢弃（已删除的条目）

        # 为未匹配到的新条目创建section
        for entry in data:
            eid = str(entry.get(id_field, ""))
            if eid and eid not in consumed_ids:
                section = self.add_section(section_name)
                for key, value in entry.items():
                    section.set(key, value)

        self.sections = kept_sections
        self._modified = True

    def remove_section(self, section_name: str, section_index: int = 0):
        """删除指定section"""
        matches = self.get_all_sections(section_name)
        if 0 <= section_index < len(matches):
            self.sections.remove(matches[section_index])
            self._modified = True

    def get_section_count(self, section_name: str) -> int:
        """获取指定名称section的数量"""
        return len(self.get_all_sections(section_name))

    def get_all_entries(self) -> Dict[str, List[Dict[str, str]]]:
        """获取所有section的所有entries，返回结构化数据"""
        result = OrderedDict()
        for section in self.sections:
            if section.name not in result:
                result[section.name] = []
            result[section.name].append(dict(section.entries))
        return result

    def get_section_names(self) -> List[str]:
        """获取所有section名称列表"""
        names = []
        for s in self.sections:
            if s.name not in names:
                names.append(s.name)
        return names

    def is_modified(self) -> bool:
        return self._modified

    def get_warnings(self) -> List[str]:
        """获取加载过程中检测到的警告（如重复key）"""
        return self._warnings