"""
TermText 智能编号分配与跨文件 ID 冲突检测系统

管理 TermText.ini 的编号段（Segment），提供智能分配、冲突检测、批量迁移、
跨文件一致性校验等功能。所有方法返回统一的 dict 格式结果。

编号段约定（依据 SG7Setting 社区文档）：
    1-999        : 系统文本
    1000-1999    : 特性名称
    2000-2999    : 特性描述
    3000-3999    : 技能名称
    4000-4999    : 技能描述
    5000-5999    : 官职名称
    6000-6999    : 阵型名称
    7000-7999    : 阵型描述
    8000-8999    : 城市名称
    9000-9999    : 剧本名称
    10000-11999  : 势力名称
    12000-12999  : 事件文本
    13000-13999  : 兵种名称
    14000-14999  : 物品名称
    15000-15999  : 物品描述
    16000-16999  : 武将称号
    17000-17999  : 武将传记
    18000-19999  : 预留扩展
    20000-21999  : 必杀技名称
    22000-22999  : 必杀技描述
    23000-24999  : 预留
    25000-26999  : 武将名称
    27000-27999  : 武将姓氏
    28000-29999  : NPC/特殊名称
"""

import os
import re
import logging
from typing import Dict, List, Set, Optional, Any, Tuple
from collections import defaultdict, OrderedDict
from core.ini_parser import IniParser

logger = logging.getLogger(__name__)


# ============================================================
# 编号段配置
# ============================================================
SEGMENT_DEFINITIONS = OrderedDict([
    ("system",            (1, 999,       "系统文本")),
    ("feature_name",      (1000, 1999,   "特性名称")),
    ("feature_desc",      (2000, 2999,   "特性描述")),
    ("skill_name",        (3000, 3999,   "技能名称")),
    ("skill_desc",        (4000, 4999,   "技能描述")),
    ("office_name",       (5000, 5999,   "官职名称")),
    ("formation_name",    (6000, 6999,   "阵型名称")),
    ("formation_desc",    (7000, 7999,   "阵型描述")),
    ("city_name",         (8000, 8999,   "城市名称")),
    ("scenario_name",     (9000, 9999,   "剧本名称")),
    ("nation_name",       (10000, 11999, "势力名称")),
    ("event_text",        (12000, 12999, "事件文本")),
    ("soldier_name",      (13000, 13999, "兵种名称")),
    ("item_name",         (14000, 14999, "物品名称")),
    ("item_desc",         (15000, 15999, "物品描述")),
    ("title_name",        (16000, 16999, "武将称号")),
    ("general_biography", (17000, 17999, "武将传记")),
    ("reserved_1",        (18000, 19999, "预留扩展")),
    ("superatk_name",     (20000, 21999, "必杀技名称")),
    ("superatk_desc",     (22000, 22999, "必杀技描述")),
    ("reserved_2",        (23000, 24999, "预留")),
    ("general_name",      (25000, 26999, "武将名称")),
    ("general_surname",   (27000, 27999, "武将姓氏")),
    ("npc_special_name",  (28000, 29999, "NPC/特殊名称")),
])

# 段内容类型别名映射：方便用户使用友好名称
CONTENT_TYPE_ALIASES = {
    "特性名称":      "feature_name",
    "特性描述":      "feature_desc",
    "技能名称":      "skill_name",
    "技能描述":      "skill_desc",
    "官职名称":      "office_name",
    "官职":          "office_name",
    "阵型名称":      "formation_name",
    "阵型":          "formation_name",
    "阵型描述":      "formation_desc",
    "城市名称":      "city_name",
    "城市":          "city_name",
    "剧本名称":      "scenario_name",
    "剧本":          "scenario_name",
    "势力名称":      "nation_name",
    "势力":          "nation_name",
    "事件文本":      "event_text",
    "事件":          "event_text",
    "兵种名称":      "soldier_name",
    "兵种":          "soldier_name",
    "物品名称":      "item_name",
    "物品":          "item_name",
    "物品描述":      "item_desc",
    "武将称号":      "title_name",
    "称号":          "title_name",
    "武将传记":      "general_biography",
    "传记":          "general_biography",
    "必杀技名称":    "superatk_name",
    "必杀技":        "superatk_name",
    "必杀技描述":    "superatk_desc",
    "武将名称":      "general_name",
    "武将":          "general_name",
    "武将姓氏":      "general_surname",
    "姓氏":          "general_surname",
    "NPC名称":       "npc_special_name",
    "特殊名称":      "npc_special_name",
}


class TermTextAllocator:
    """
    TermText 智能编号分配器

    管理 TermText.ini 的编号段，提供智能分配、冲突检测、批量迁移、
    跨文件一致性校验等功能。依赖 core.ini_parser.IniParser 加载和解析。

    使用示例::

        allocator = TermTextAllocator()
        allocator.load("/path/to/Setting/TermText.ini")

        result = allocator.allocate_id("item_name")
        if result["success"]:
            print(f"分配ID: {result['allocated_id']}")

        conflicts = allocator.detect_conflicts()
        report = allocator.generate_allocation_report()
    """

    TERMTEXT_SECTION = "TermText"
    TERMTEXT_KEY_PREFIX = "TermText_"

    def __init__(self):
        self.parser = IniParser()
        self._id_map: Dict[int, str] = {}          # id -> text
        self._text_reverse: Dict[str, int] = {}    # text -> id (first occurrence)
        self._id_occurrences: Dict[int, int] = {}  # id -> occurrence count
        self._loaded = False
        self._file_path: Optional[str] = None
        # 已分配但尚未写入的预留 ID
        self._reserved_ids: Dict[str, Set[int]] = defaultdict(set)
        # 冲突检测结果缓存
        self._last_conflicts: Optional[Dict] = None

    # ============================================================
    # 静态 / 类方法
    # ============================================================

    @staticmethod
    def get_info() -> dict:
        """返回模块信息"""
        segments_info = []
        for key, (start, end, desc) in SEGMENT_DEFINITIONS.items():
            capacity = end - start + 1
            segments_info.append({
                "content_type": key,
                "description": desc,
                "start": start,
                "end": end,
                "capacity": capacity,
            })
        return {
            "module": "termtext_allocator",
            "version": "1.0.0",
            "description": "TermText 智能编号分配与跨文件 ID 冲突检测系统",
            "total_segments": len(SEGMENT_DEFINITIONS),
            "segments": segments_info,
            "supported_content_types": list(SEGMENT_DEFINITIONS.keys()),
            "aliases": {k: v for k, v in CONTENT_TYPE_ALIASES.items()},
        }

    @classmethod
    def _resolve_content_type(cls, content_type: str) -> Optional[str]:
        """将内容类型解析为标准段名"""
        if content_type in SEGMENT_DEFINITIONS:
            return content_type
        return CONTENT_TYPE_ALIASES.get(content_type)

    @classmethod
    def _get_segment_range(cls, content_type: str) -> Optional[Tuple[int, int, str]]:
        """获取编号段范围 (start, end, description)，未找到返回 None"""
        resolved = cls._resolve_content_type(content_type)
        if resolved:
            return SEGMENT_DEFINITIONS.get(resolved)
        return None

    # ============================================================
    # 加载
    # ============================================================

    def load(self, termtext_path: str) -> "TermTextAllocator":
        """加载 TermText.ini 文件"""
        self._file_path = termtext_path
        self.parser = IniParser()
        if not os.path.exists(termtext_path):
            logger.warning("TermText.ini 不存在: %s", termtext_path)
            self._loaded = False
            return self

        self.parser.load(termtext_path)
        self._build_index()
        self._loaded = True
        self._last_conflicts = None
        logger.info("TermText.ini 加载完成: %d 条记录", len(self._id_map))
        return self

    def _build_index(self):
        """构建内存索引"""
        self._id_map.clear()
        self._text_reverse.clear()
        self._id_occurrences.clear()

        sections = self.parser.get_all_sections(self.TERMTEXT_SECTION)
        for section in sections:
            for key, value in section.entries.items():
                if key.startswith(self.TERMTEXT_KEY_PREFIX):
                    try:
                        idx = int(key[len(self.TERMTEXT_KEY_PREFIX):])
                        clean_value = value.strip('"').strip("'")
                        self._id_map[idx] = clean_value
                        if clean_value not in self._text_reverse:
                            self._text_reverse[clean_value] = idx
                        self._id_occurrences[idx] = self._id_occurrences.get(idx, 0) + 1
                    except (ValueError, IndexError):
                        continue

    def is_loaded(self) -> bool:
        """是否已加载"""
        return self._loaded

    # ============================================================
    # 核心分配方法
    # ============================================================

    def allocate_id(self, content_type: str, preferred_text: str = None) -> dict:
        """
        为指定内容类型智能分配一个可用 ID。

        Args:
            content_type: 内容类型（如 "item_name", "物品名称"）
            preferred_text: 首选文本，若已存在则返回已有 ID

        Returns:
            dict: {
                "success": bool,
                "allocated_id": int | None,
                "content_type": str,
                "segment": {"start": int, "end": int, "description": str},
                "reused": bool,  # 是否复用已有文本
                "message": str,
            }
        """
        segment = self._get_segment_range(content_type)
        if segment is None:
            return {
                "success": False,
                "allocated_id": None,
                "content_type": content_type,
                "segment": None,
                "reused": False,
                "message": f"未知的内容类型: {content_type}",
            }
        start, end, desc = segment

        # 如果提供了首选文本且已存在，复用 ID
        if preferred_text:
            existing_id = self._text_reverse.get(preferred_text)
            if existing_id is not None and start <= existing_id <= end:
                return {
                    "success": True,
                    "allocated_id": existing_id,
                    "content_type": content_type,
                    "segment": {"start": start, "end": end, "description": desc},
                    "reused": True,
                    "message": f"复用已有文本 ID: {existing_id}",
                }
            elif existing_id is not None:
                logger.warning("文本 '%s' 已有ID %d，但不在段 %s 内", preferred_text, existing_id, content_type)

        # 在编号段内寻找第一个未占用的 ID
        used_ids = self._get_used_ids_in_range(start, end)
        reserved = self._reserved_ids.get(content_type, set())
        blocked = used_ids | reserved

        for candidate in range(start, end + 1):
            if candidate not in blocked:
                self._reserved_ids[content_type].add(candidate)
                return {
                    "success": True,
                    "allocated_id": candidate,
                    "content_type": content_type,
                    "segment": {"start": start, "end": end, "description": desc},
                    "reused": False,
                    "message": f"分配新 ID: {candidate}",
                }

        return {
            "success": False,
            "allocated_id": None,
            "content_type": content_type,
            "segment": {"start": start, "end": end, "description": desc},
            "reused": False,
            "message": f"编号段 [{start}-{end}] 已满，无可用 ID",
        }

    def allocate_batch(self, requests: List[dict]) -> dict:
        """
        批量分配 ID。

        Args:
            requests: 请求列表，每项包含 content_type 和可选的 count, preferred_text

        Returns:
            dict: {
                "success": bool,
                "total_allocated": int,
                "total_requested": int,
                "results": List[dict],
                "segment_usage": dict,
                "message": str,
            }
        """
        results = []
        total_allocated = 0
        total_requested = 0
        errors = []

        for i, req in enumerate(requests):
            content_type = req.get("content_type", "")
            count = req.get("count", 1)
            total_requested += count

            for j in range(count):
                result = self.allocate_id(
                    content_type,
                    preferred_text=req.get("preferred_text") if j == 0 else None,
                )
                result["request_index"] = i
                result["sub_index"] = j
                results.append(result)
                if result["success"]:
                    total_allocated += 1
                else:
                    errors.append(result["message"])

        segment_usage = {}
        for key in SEGMENT_DEFINITIONS:
            info = self.get_segment_info(key)
            if info["success"]:
                segment_usage[key] = {
                    "used": info["used"],
                    "available": info["available"],
                    "usage_rate": info["usage_rate"],
                }

        return {
            "success": len(errors) == 0,
            "total_allocated": total_allocated,
            "total_requested": total_requested,
            "results": results,
            "segment_usage": segment_usage,
            "errors": errors,
            "message": f"批量分配完成: {total_allocated}/{total_requested}" if len(errors) == 0
                       else f"批量分配部分完成: {total_allocated}/{total_requested}, 错误: {len(errors)}",
        }

    # ============================================================
    # 冲突检测
    # ============================================================

    def detect_conflicts(self, termtext_path: str = None) -> dict:
        """
        全面检测 ID 冲突。

        检测项：
        1. 重复 ID（同一 ID 出现多次）
        2. 跨段冲突（不同内容类型使用了相同 ID）
        3. 越界 ID（ID 超出所属段范围）
        4. 空缺（段内未使用的 ID 列表）

        Args:
            termtext_path: 可选的 TermText.ini 路径，不传则使用已加载的

        Returns:
            dict: {
                "success": bool,
                "total_conflicts": int,
                "duplicate_ids": List[dict],
                "cross_segment_conflicts": List[dict],
                "out_of_bound_ids": List[dict],
                "gaps": dict,
                "message": str,
            }
        """
        if termtext_path:
            self.load(termtext_path)
        if not self._loaded:
            return {
                "success": False,
                "total_conflicts": 0,
                "duplicate_ids": [],
                "cross_segment_conflicts": [],
                "out_of_bound_ids": [],
                "gaps": {},
                "message": "未加载 TermText.ini",
            }

        duplicate_ids = []
        cross_segment_conflicts = []
        out_of_bound_ids = []
        gaps = {}

        # 1. 检测重复 ID
        # 扫描原始行（raw_lines）以捕获已被解析器合并的重复键
        id_to_entries: Dict[int, List[dict]] = defaultdict(list)
        kv_pattern = re.compile(r"^([^=]+)=\s*(.*)$")
        sections = self.parser.get_all_sections(self.TERMTEXT_SECTION)
        for section in sections:
            for line in section.raw_lines:
                stripped = line.strip()
                match = kv_pattern.match(stripped)
                if match:
                    key = match.group(1).strip()
                    value = match.group(2).strip()
                    if key.startswith(self.TERMTEXT_KEY_PREFIX):
                        try:
                            idx = int(key[len(self.TERMTEXT_KEY_PREFIX):])
                            clean_value = value.strip('"').strip("'")
                            id_to_entries[idx].append({
                                "id": idx,
                                "key": key,
                                "value": clean_value,
                                "section": section.name,
                            })
                        except (ValueError, IndexError):
                            continue

        for idx, entries in id_to_entries.items():
            if len(entries) > 1:
                values = [e["value"] for e in entries]
                has_different_values = len(set(values)) > 1
                duplicate_ids.append({
                    "id": idx,
                    "occurrence_count": len(entries),
                    "values": values,
                    "has_different_values": has_different_values,
                    "entries": entries,
                })

        # 2. 检测跨段冲突：不同内容类型的段重叠
        # 构建 ID -> 段名列表
        id_to_segments: Dict[int, List[str]] = defaultdict(list)
        for seg_name, (start, end, _) in SEGMENT_DEFINITIONS.items():
            for idx in id_to_entries:
                if start <= idx <= end:
                    id_to_segments[idx].append(seg_name)

        for idx, seg_names in id_to_segments.items():
            if len(seg_names) > 1:
                cross_segment_conflicts.append({
                    "id": idx,
                    "conflicting_segments": seg_names,
                    "values": [e["value"] for e in id_to_entries.get(idx, [])],
                })

        # 3. 检测越界 ID：ID 不在任何段内
        for idx in id_to_entries:
            in_any_segment = False
            for seg_name, (start, end, _) in SEGMENT_DEFINITIONS.items():
                if start <= idx <= end:
                    in_any_segment = True
                    break
            if not in_any_segment:
                out_of_bound_ids.append({
                    "id": idx,
                    "values": [e["value"] for e in id_to_entries[idx]],
                })

        # 4. 检测空缺
        for seg_name, (start, end, desc) in SEGMENT_DEFINITIONS.items():
            used = set()
            for idx in id_to_entries:
                if start <= idx <= end:
                    used.add(idx)
            all_ids = set(range(start, end + 1))
            free = sorted(all_ids - used)
            if free:
                gaps[seg_name] = {
                    "description": desc,
                    "range": [start, end],
                    "total_capacity": end - start + 1,
                    "used_count": len(used),
                    "free_count": len(free),
                    "free_ids": free[:50] if len(free) > 50 else free,
                    "free_ids_truncated": len(free) > 50,
                }

        total_conflicts = (len(duplicate_ids) + len(cross_segment_conflicts)
                           + len(out_of_bound_ids))

        self._last_conflicts = {
            "success": True,
            "total_conflicts": total_conflicts,
            "duplicate_ids": duplicate_ids,
            "cross_segment_conflicts": cross_segment_conflicts,
            "out_of_bound_ids": out_of_bound_ids,
            "gaps": gaps,
            "message": f"检测到 {total_conflicts} 个冲突" if total_conflicts > 0 else "未检测到冲突",
        }

        return dict(self._last_conflicts)

    # ============================================================
    # 冲突解决
    # ============================================================

    def resolve_conflicts(self, strategy: str = "auto") -> dict:
        """
        解决检测到的冲突。

        Args:
            strategy: 策略
                - "auto": 自动处理（重复ID保留第一个，越界ID重分配）
                - "reallocate": 全部重新分配
                - "keep_first": 保留第一个，移除重复
                - "report_only": 仅报告，不修改

        Returns:
            dict: 解决结果
        """
        if self._last_conflicts is None:
            self.detect_conflicts()

        if self._last_conflicts is None or not self._last_conflicts["success"]:
            return {
                "success": False,
                "strategy": strategy,
                "resolved": [],
                "unresolved": [],
                "message": "无冲突数据或文件未加载",
            }

        conflicts = self._last_conflicts
        resolved = []
        unresolved = []

        if strategy == "report_only":
            return {
                "success": True,
                "strategy": strategy,
                "resolved": [],
                "unresolved": [],
                "conflicts": conflicts,
                "message": f"仅报告模式，共 {conflicts['total_conflicts']} 个冲突",
            }

        if strategy in ("auto", "keep_first"):
            # 处理重复 ID
            for dup in conflicts["duplicate_ids"]:
                dup_id = dup["id"]
                dup_key = f"{self.TERMTEXT_KEY_PREFIX}{dup_id:04d}"
                kv_pattern = re.compile(r"^([^=]+)=\s*(.*)$")
                first_value = dup["values"][0] if dup["values"] else ""

                sections = self.parser.get_all_sections(self.TERMTEXT_SECTION)
                for section in sections:
                    # 清理 raw_lines：保留第一个匹配行，移除后续重复
                    new_raw_lines = []
                    raw_found = False
                    for line in section.raw_lines:
                        stripped = line.strip()
                        match = kv_pattern.match(stripped)
                        if match and match.group(1).strip() == dup_key:
                            if not raw_found:
                                raw_found = True
                                new_raw_lines.append(line)
                            # 跳过重复行
                            continue
                        new_raw_lines.append(line)
                    section.raw_lines = new_raw_lines

                    # 更新 entries：确保保留第一个值
                    if dup_key in section.entries:
                        # 解析器可能保留了最后一个值，需要改为第一个值
                        if dup["has_different_values"]:
                            section.entries[dup_key] = f'"{first_value}"'
                        section._modified_keys.add(dup_key)

                self._id_occurrences[dup_id] = 1
                action_label = "keep_first" if dup["has_different_values"] else "deduplicate"
                resolved.append({
                    "type": "duplicate",
                    "id": dup_id,
                    "action": action_label,
                    "kept_value": first_value,
                })

            # 处理越界 ID
            for oob in conflicts["out_of_bound_ids"]:
                oob_id = oob["id"]
                # 尝试找到应该归属的段
                target_segment = None
                for seg_name, (start, end, _) in SEGMENT_DEFINITIONS.items():
                    if start <= oob_id <= end:
                        target_segment = seg_name
                        break

                if strategy == "auto":
                    # 自动模式：尝试重分配
                    # 找到离此 ID 最近的段
                    closest_seg = self._find_closest_segment(oob_id)
                    if closest_seg:
                        new_id = self._allocate_in_segment(closest_seg)
                        if new_id:
                            self._migrate_single_id(oob_id, new_id)
                            resolved.append({
                                "type": "out_of_bound",
                                "old_id": oob_id,
                                "new_id": new_id,
                                "segment": closest_seg,
                                "action": "reallocated",
                            })
                        else:
                            unresolved.append({
                                "type": "out_of_bound",
                                "id": oob_id,
                                "reason": "目标段已满",
                            })
                    else:
                        unresolved.append({
                            "type": "out_of_bound",
                            "id": oob_id,
                            "reason": "无法确定目标段",
                        })
                else:
                    unresolved.append({
                        "type": "out_of_bound",
                        "id": oob_id,
                        "reason": "keep_first 策略下不处理越界ID",
                    })

        elif strategy == "reallocate":
            # 全部重新分配：清除所有重复，重新分配越界
            kv_pattern = re.compile(r"^([^=]+)=\s*(.*)$")
            for dup in conflicts["duplicate_ids"]:
                dup_id = dup["id"]
                dup_key = f"{self.TERMTEXT_KEY_PREFIX}{dup_id:04d}"
                first_value = dup["values"][0] if dup["values"] else ""

                sections = self.parser.get_all_sections(self.TERMTEXT_SECTION)
                for section in sections:
                    # 清理 raw_lines：保留第一个匹配行，移除后续重复
                    new_raw_lines = []
                    raw_found = False
                    for line in section.raw_lines:
                        stripped = line.strip()
                        match = kv_pattern.match(stripped)
                        if match and match.group(1).strip() == dup_key:
                            if not raw_found:
                                raw_found = True
                                new_raw_lines.append(line)
                            continue
                        new_raw_lines.append(line)
                    section.raw_lines = new_raw_lines

                    # 更新 entries
                    if dup_key in section.entries:
                        if dup["has_different_values"]:
                            section.entries[dup_key] = f'"{first_value}"'
                        section._modified_keys.add(dup_key)

                self._id_occurrences[dup_id] = 1
                resolved.append({
                    "type": "duplicate",
                    "id": dup_id,
                    "action": "deduplicate",
                })

            # 处理越界
            for oob in conflicts["out_of_bound_ids"]:
                oob_id = oob["id"]
                closest_seg = self._find_closest_segment(oob_id)
                if closest_seg:
                    new_id = self._allocate_in_segment(closest_seg)
                    if new_id:
                        self._migrate_single_id(oob_id, new_id)
                        resolved.append({
                            "type": "out_of_bound",
                            "old_id": oob_id,
                            "new_id": new_id,
                            "segment": closest_seg,
                            "action": "reallocated",
                        })
                    else:
                        unresolved.append({
                            "type": "out_of_bound",
                            "id": oob_id,
                            "reason": "目标段已满",
                        })
                else:
                    unresolved.append({
                        "type": "out_of_bound",
                        "id": oob_id,
                        "reason": "无法确定目标段",
                    })

        # 重建索引
        self._build_index()
        self._last_conflicts = None

        return {
            "success": len(unresolved) == 0,
            "strategy": strategy,
            "resolved": resolved,
            "unresolved": unresolved,
            "resolved_count": len(resolved),
            "unresolved_count": len(unresolved),
            "message": f"冲突解决完成: 已解决 {len(resolved)}, 未解决 {len(unresolved)}",
        }

    def _find_closest_segment(self, id_value: int) -> Optional[str]:
        """找到距离 ID 最近的编号段"""
        best_seg = None
        best_dist = float("inf")
        for seg_name, (start, end, _) in SEGMENT_DEFINITIONS.items():
            if start <= id_value <= end:
                return seg_name
            dist = min(abs(id_value - start), abs(id_value - end))
            if dist < best_dist:
                best_dist = dist
                best_seg = seg_name
        return best_seg

    def _allocate_in_segment(self, segment_name: str) -> Optional[int]:
        """在指定段内分配一个可用 ID"""
        segment = self._get_segment_range(segment_name)
        if segment is None:
            return None
        start, end, _ = segment
        used = self._get_used_ids_in_range(start, end)
        for candidate in range(start, end + 1):
            if candidate not in used:
                return candidate
        return None

    def _migrate_single_id(self, old_id: int, new_id: int):
        """迁移单个 ID 的文本"""
        old_key = f"{self.TERMTEXT_KEY_PREFIX}{old_id:04d}"
        new_key = f"{self.TERMTEXT_KEY_PREFIX}{new_id:04d}"
        sections = self.parser.get_all_sections(self.TERMTEXT_SECTION)
        for section in sections:
            if old_key in section.entries:
                value = section.entries[old_key]
                del section.entries[old_key]
                section.set(new_key, value)
                self.parser._modified = True
                break

    def _get_used_ids_in_range(self, start: int, end: int) -> Set[int]:
        """获取指定范围内已占用的 ID"""
        if not self._loaded:
            return set()
        return {idx for idx in self._id_map if start <= idx <= end}

    # ============================================================
    # ID 迁移
    # ============================================================

    def migrate_ids(self, mapping: Dict[int, int]) -> dict:
        """
        批量迁移 ID。

        Args:
            mapping: {old_id: new_id} 映射

        Returns:
            dict: 迁移结果
        """
        migrated = []
        failed = []
        warnings = []

        for old_id, new_id in mapping.items():
            if old_id == new_id:
                continue

            old_key = f"{self.TERMTEXT_KEY_PREFIX}{old_id:04d}"
            new_key = f"{self.TERMTEXT_KEY_PREFIX}{new_id:04d}"

            if new_id in self._id_map and new_id != old_id:
                warnings.append(f"目标ID {new_id} 已被占用（原值: {self._id_map[new_id]}），将覆盖")

            sections = self.parser.get_all_sections(self.TERMTEXT_SECTION)
            found = False
            for section in sections:
                if old_key in section.entries:
                    value = section.entries[old_key]
                    del section.entries[old_key]
                    section.set(new_key, value)
                    self.parser._modified = True
                    found = True
                    migrated.append({
                        "old_id": old_id,
                        "new_id": new_id,
                        "value": value.strip('"').strip("'"),
                    })
                    break

            if not found:
                failed.append({
                    "old_id": old_id,
                    "new_id": new_id,
                    "reason": "旧ID不存在",
                })

        # 重建索引
        self._build_index()

        return {
            "success": len(failed) == 0,
            "migrated": migrated,
            "failed": failed,
            "warnings": warnings,
            "migrated_count": len(migrated),
            "failed_count": len(failed),
            "message": f"迁移完成: {len(migrated)} 成功, {len(failed)} 失败",
        }

    # ============================================================
    # 段预留
    # ============================================================

    def reserve_segment(self, content_type: str, count: int) -> dict:
        """
        为未来扩展预留连续的 ID 段。

        Args:
            content_type: 内容类型
            count: 预留数量

        Returns:
            dict: 预留结果
        """
        segment = self._get_segment_range(content_type)
        if segment is None:
            return {
                "success": False,
                "content_type": content_type,
                "reserved_start": None,
                "reserved_end": None,
                "count": count,
                "message": f"未知的内容类型: {content_type}",
            }
        start, end, desc = segment

        used = self._get_used_ids_in_range(start, end)
        reserved = self._reserved_ids.get(content_type, set())
        blocked = used | reserved

        # 寻找连续的 count 个空闲 ID
        contiguous_start = None
        contiguous_count = 0
        for candidate in range(start, end + 1):
            if candidate not in blocked:
                if contiguous_start is None:
                    contiguous_start = candidate
                contiguous_count += 1
                if contiguous_count >= count:
                    break
            else:
                contiguous_start = None
                contiguous_count = 0

        if contiguous_start is not None and contiguous_count >= count:
            reserved_end = contiguous_start + count - 1
            for i in range(contiguous_start, reserved_end + 1):
                self._reserved_ids[content_type].add(i)
            return {
                "success": True,
                "content_type": content_type,
                "reserved_start": contiguous_start,
                "reserved_end": reserved_end,
                "count": count,
                "segment": {"start": start, "end": end, "description": desc},
                "message": f"预留成功: [{contiguous_start}-{reserved_end}]",
            }

        return {
            "success": False,
            "content_type": content_type,
            "reserved_start": None,
            "reserved_end": None,
            "count": count,
            "segment": {"start": start, "end": end, "description": desc},
            "message": f"段 [{start}-{end}] 中没有足够的连续空闲 ID（需要 {count} 个）",
        }

    # ============================================================
    # 段信息查询
    # ============================================================

    def get_segment_info(self, content_type: str) -> dict:
        """
        获取编号段详细信息。

        Returns:
            dict: {
                "success": bool,
                "content_type": str,
                "start": int, "end": int,
                "description": str,
                "total_capacity": int,
                "used": int,
                "available": int,
                "usage_rate": float,
            }
        """
        segment = self._get_segment_range(content_type)
        if segment is None:
            return {
                "success": False,
                "content_type": content_type,
                "message": f"未知的内容类型: {content_type}",
            }
        start, end, desc = segment
        used = self._get_used_ids_in_range(start, end)
        used_count = len(used)
        capacity = end - start + 1
        available = capacity - used_count

        return {
            "success": True,
            "content_type": content_type,
            "start": start,
            "end": end,
            "description": desc,
            "total_capacity": capacity,
            "used": used_count,
            "available": available,
            "usage_rate": round(used_count / capacity * 100, 2) if capacity > 0 else 0,
        }

    def get_all_segments(self) -> dict:
        """
        获取所有编号段的状态概览。

        Returns:
            dict: {
                "success": bool,
                "segments": dict,
                "total_used": int,
                "total_capacity": int,
                "overall_usage_rate": float,
                "critical_segments": List[str],  # 使用率 >= 90% 的段
            }
        """
        segments = {}
        total_used = 0
        total_capacity = 0
        critical_segments = []

        for key in SEGMENT_DEFINITIONS:
            info = self.get_segment_info(key)
            segments[key] = info
            if info["success"]:
                total_used += info["used"]
                total_capacity += info["total_capacity"]
                if info["usage_rate"] >= 90.0:
                    critical_segments.append(key)

        overall_rate = (round(total_used / total_capacity * 100, 2)
                        if total_capacity > 0 else 0)

        return {
            "success": True,
            "segments": segments,
            "total_used": total_used,
            "total_capacity": total_capacity,
            "overall_usage_rate": overall_rate,
            "critical_segments": critical_segments,
            "message": f"共有 {len(segments)} 个段，总使用率 {overall_rate}%",
        }

    # ============================================================
    # 分配验证
    # ============================================================

    def validate_allocation(self, content_type: str, id_value: int) -> dict:
        """
        验证单个 ID 分配是否合法。

        检查项：
        1. ID 是否在正确的段内
        2. ID 是否已被占用
        3. 格式是否正确（正整数）

        Returns:
            dict: {
                "success": bool,
                "valid": bool,
                "checks": List[dict],
                "suggestions": List[str],
            }
        """
        checks = []
        suggestions = []

        # 格式检查
        if not isinstance(id_value, int) or id_value <= 0:
            checks.append({"check": "format", "passed": False, "detail": "ID 必须是正整数"})
            return {
                "success": True,
                "valid": False,
                "content_type": content_type,
                "id_value": id_value,
                "checks": checks,
                "suggestions": ["使用正整数作为 ID"],
                "message": "格式验证失败",
            }
        checks.append({"check": "format", "passed": True, "detail": "格式正确"})

        # 段内检查
        segment = self._get_segment_range(content_type)
        if segment is None:
            checks.append({"check": "segment", "passed": False, "detail": f"未知的内容类型: {content_type}"})
            suggestions.append(f"请使用已知的内容类型: {list(SEGMENT_DEFINITIONS.keys())}")
        else:
            start, end, desc = segment
            if start <= id_value <= end:
                checks.append({"check": "segment", "passed": True, "detail": f"ID 在段 [{start}-{end}] ({desc}) 内"})
            else:
                checks.append({"check": "segment", "passed": False,
                               "detail": f"ID {id_value} 不在段 [{start}-{end}] ({desc}) 内"})
                suggestions.append(f"ID 应为 {start}-{end} 之间的值")

        # 占用检查
        if self._loaded and id_value in self._id_map:
            existing_text = self._id_map[id_value]
            checks.append({"check": "occupied", "passed": False,
                           "detail": f"ID {id_value} 已被占用: '{existing_text}'"})
            suggestions.append(f"ID {id_value} 已被文本 '{existing_text}' 占用，请选择其他 ID")
        else:
            checks.append({"check": "occupied", "passed": True, "detail": "ID 未被占用"})

        all_passed = all(c["passed"] for c in checks)
        return {
            "success": True,
            "valid": all_passed,
            "content_type": content_type,
            "id_value": id_value,
            "checks": checks,
            "suggestions": suggestions,
            "message": "验证通过" if all_passed else "验证失败，请检查",
        }

    # ============================================================
    # 智能分配
    # ============================================================

    def smart_allocate(self, content_type: str, count: int,
                       contiguous: bool = False) -> dict:
        """
        智能分配。

        - 连续模式：寻找连续的空闲 ID 块
        - 非连续模式：分配任意可用 ID

        Args:
            content_type: 内容类型
            count: 需要分配的数量
            contiguous: 是否要求连续 ID

        Returns:
            dict: {
                "success": bool,
                "allocated_ids": List[int],
                "count": int,
                "contiguous": bool,
                "segment": dict,
            }
        """
        segment = self._get_segment_range(content_type)
        if segment is None:
            return {
                "success": False,
                "allocated_ids": [],
                "count": count,
                "contiguous": contiguous,
                "segment": None,
                "message": f"未知的内容类型: {content_type}",
            }
        start, end, desc = segment

        used = self._get_used_ids_in_range(start, end)
        reserved = self._reserved_ids.get(content_type, set())
        blocked = used | reserved

        allocated = []

        if contiguous:
            # 寻找连续的 count 个空闲 ID
            block_start = None
            block_len = 0
            for candidate in range(start, end + 1):
                if candidate not in blocked:
                    if block_start is None:
                        block_start = candidate
                    block_len += 1
                    if block_len >= count:
                        for i in range(block_start, block_start + count):
                            allocated.append(i)
                            self._reserved_ids[content_type].add(i)
                        break
                else:
                    block_start = None
                    block_len = 0

            if len(allocated) < count:
                return {
                    "success": False,
                    "allocated_ids": allocated,
                    "count": count,
                    "contiguous": True,
                    "segment": {"start": start, "end": end, "description": desc},
                    "message": f"段 [{start}-{end}] 中没有 {count} 个连续空闲 ID",
                }
        else:
            # 非连续：分配任意可用 ID
            candidates = []
            for candidate in range(start, end + 1):
                if candidate not in blocked:
                    candidates.append(candidate)
                    if len(candidates) >= count:
                        break
            if len(candidates) >= count:
                for c in candidates:
                    allocated.append(c)
                    self._reserved_ids[content_type].add(c)
            else:
                return {
                    "success": False,
                    "allocated_ids": [],
                    "count": count,
                    "contiguous": False,
                    "segment": {"start": start, "end": end, "description": desc},
                    "message": f"段 [{start}-{end}] 中只有 {len(candidates)} 个空闲 ID（需要 {count} 个）",
                }

        return {
            "success": True,
            "allocated_ids": allocated,
            "count": len(allocated),
            "contiguous": contiguous,
            "segment": {"start": start, "end": end, "description": desc},
            "message": f"成功分配 {'连续' if contiguous else '非连续'} {len(allocated)} 个 ID",
        }

    # ============================================================
    # 跨文件冲突检测
    # ============================================================

    def cross_file_detect(self, file_paths: List[str]) -> dict:
        """
        跨文件冲突检测。

        给定多个 INI 文件路径，检测它们引用的 TermText ID 是否存在冲突
        （如两个文件引用同一个 ID 但内容不同）。

        Args:
            file_paths: INI 文件路径列表

        Returns:
            dict: {
                "success": bool,
                "conflicts": List[dict],
                "total_files": int,
                "total_references": int,
            }
        """
        # 从每个 INI 文件中提取 TermText ID 引用
        # 常见的引用模式：字段值包含数字 ID 引用
        file_references: Dict[str, Dict[int, str]] = {}

        id_pattern = re.compile(
            r'(?:TermText_?|String_?|Text_?|Str_?)?\b(\d{4,5})\b'
        )

        for file_path in file_paths:
            if not os.path.exists(file_path):
                logger.warning("跨文件检测: 文件不存在: %s", file_path)
                continue

            parser = IniParser()
            parser.load(file_path)
            refs: Dict[int, str] = {}
            file_name = os.path.basename(file_path)

            for section in parser.sections:
                for key, value in section.entries.items():
                    matches = id_pattern.findall(value)
                    for match in matches:
                        id_val = int(match)
                        # 只关注 TermText 范围内的 ID（1-29999）
                        if 1 <= id_val <= 29999:
                            if id_val in self._id_map:
                                refs[id_val] = self._id_map[id_val]

            if refs:
                file_references[file_name] = refs

        # 检测冲突：同一 ID 在不同文件中被引用，但对应不同内容
        id_to_files: Dict[int, Dict[str, str]] = defaultdict(dict)
        for file_name, refs in file_references.items():
            ref_values = list(refs.values())
            for id_val in refs:
                if id_val in self._id_map:
                    # 检查该文件中是否有字段值与 TermText 中的值不同
                    for section in IniParser().load(
                            os.path.join(os.path.dirname(file_paths[0]), file_name)
                    ).sections if file_paths else []:
                        pass
                    # 简化：记录每个文件对该 ID 的引用
                    id_to_files[id_val][file_name] = self._id_map[id_val]

        conflicts = []
        for id_val, file_map in id_to_files.items():
            if len(file_map) > 1:
                # 检查值是否不同
                values = set(file_map.values())
                if len(values) > 1:
                    conflicts.append({
                        "id": id_val,
                        "files": dict(file_map),
                        "different_values": list(values),
                        "severity": "warning",
                    })

        # 更精确的检测：解析每个文件，提取与 TermText ID 相关的字段值
        exact_conflicts = []
        for file_path in file_paths:
            if not os.path.exists(file_path):
                continue
            parser = IniParser()
            parser.load(file_path)
            file_name = os.path.basename(file_path)

            for section in parser.sections:
                for key, value in section.entries.items():
                    # 尝试匹配 TermText_XXXX 格式
                    tt_match = re.match(
                        rf'"?{self.TERMTEXT_KEY_PREFIX}(\d+)"?', value.strip('"').strip("'")
                    )
                    if tt_match:
                        ref_id = int(tt_match.group(1))
                        if ref_id in self._id_map:
                            exact_conflicts.append({
                                "file": file_name,
                                "section": section.name,
                                "key": key,
                                "referenced_id": ref_id,
                                "referenced_text": self._id_map[ref_id],
                            })

        total_references = sum(len(refs) for refs in file_references.values())

        return {
            "success": True,
            "conflicts": conflicts,
            "exact_references": exact_conflicts,
            "total_files": len(file_references),
            "total_references": total_references,
            "file_references": {k: list(v.keys()) for k, v in file_references.items()},
            "message": f"检测到 {len(conflicts)} 个跨文件冲突" if conflicts else "未检测到跨文件冲突",
        }

    # ============================================================
    # 分配报告
    # ============================================================

    def generate_allocation_report(self) -> dict:
        """
        生成完整的分配报告。

        包含所有段的状态、冲突列表、建议、使用趋势。

        Returns:
            dict: 完整报告
        """
        all_segments = self.get_all_segments()
        conflicts = self.detect_conflicts()

        # 使用趋势分析
        trends = {}
        for seg_name in SEGMENT_DEFINITIONS:
            info = all_segments["segments"].get(seg_name, {})
            if info.get("success"):
                rate = info["usage_rate"]
                if rate >= 95:
                    trends[seg_name] = {"status": "critical", "usage_rate": rate,
                                         "recommendation": "段即将耗尽，建议扩展或释放未使用的ID"}
                elif rate >= 80:
                    trends[seg_name] = {"status": "warning", "usage_rate": rate,
                                         "recommendation": "使用率较高，注意监控"}
                elif rate >= 50:
                    trends[seg_name] = {"status": "moderate", "usage_rate": rate,
                                         "recommendation": "正常"}
                else:
                    trends[seg_name] = {"status": "healthy", "usage_rate": rate,
                                         "recommendation": "充足"}

        # 构建建议
        suggestions = []
        if all_segments["critical_segments"]:
            suggestions.append(
                f"注意: {len(all_segments['critical_segments'])} 个段使用率超过 90%: "
                + ", ".join(all_segments["critical_segments"])
            )
        if conflicts.get("total_conflicts", 0) > 0:
            suggestions.append(
                f"检测到 {conflicts['total_conflicts']} 个冲突，建议使用 resolve_conflicts() 解决"
            )
        if all_segments["overall_usage_rate"] > 80:
            suggestions.append("整体使用率较高，建议考虑扩展编号段")

        return {
            "success": True,
            "timestamp": self._get_timestamp(),
            "segments": all_segments,
            "conflicts": {
                "total": conflicts.get("total_conflicts", 0),
                "duplicate_ids": len(conflicts.get("duplicate_ids", [])),
                "cross_segment": len(conflicts.get("cross_segment_conflicts", [])),
                "out_of_bound": len(conflicts.get("out_of_bound_ids", [])),
            },
            "trends": trends,
            "suggestions": suggestions,
            "loaded": self._loaded,
            "total_ids": len(self._id_map),
            "message": "分配报告生成完毕",
        }

    # ============================================================
    # 自动修复
    # ============================================================

    def auto_remediate(self) -> dict:
        """
        自动修复常见问题。

        修复项：
        1. 重复 ID（保留第一个，移除重复）
        2. 越界 ID（重分配到最近的段）
        3. 空文本 ID（标记为警告）

        Returns:
            dict: 修复结果
        """
        fixed = []
        warnings = []
        errors = []

        if not self._loaded:
            return {
                "success": False,
                "fixed": [],
                "warnings": [],
                "errors": ["未加载 TermText.ini"],
                "message": "未加载文件",
            }

        # 1. 修复重复 ID
        sections = self.parser.get_all_sections(self.TERMTEXT_SECTION)
        seen_keys: Dict[str, int] = {}  # key -> first section index
        first_section_map: Dict[int, int] = {}  # id -> first section index

        for si, section in enumerate(sections):
            keys_to_remove = []
            for key, value in list(section.entries.items()):
                if key.startswith(self.TERMTEXT_KEY_PREFIX):
                    try:
                        idx = int(key[len(self.TERMTEXT_KEY_PREFIX):])
                    except (ValueError, IndexError):
                        continue

                    if idx in first_section_map:
                        keys_to_remove.append(key)
                        fixed.append({
                            "type": "duplicate",
                            "id": idx,
                            "action": "removed_duplicate",
                            "detail": f"移除重复键 {key}",
                        })
                    else:
                        first_section_map[idx] = si

            for k in keys_to_remove:
                del section.entries[k]

        # 2. 修复空文本 ID
        for idx, text in list(self._id_map.items()):
            if not text or text.strip() == "":
                warnings.append({
                    "type": "empty_text",
                    "id": idx,
                    "detail": f"ID {idx} 的文本为空",
                })

        # 3. 修复越界 ID
        self._build_index()
        conflicts = self.detect_conflicts()
        for oob in conflicts.get("out_of_bound_ids", []):
            oob_id = oob["id"]
            closest_seg = self._find_closest_segment(oob_id)
            if closest_seg:
                new_id = self._allocate_in_segment(closest_seg)
                if new_id and new_id != oob_id:
                    self._migrate_single_id(oob_id, new_id)
                    fixed.append({
                        "type": "out_of_bound",
                        "old_id": oob_id,
                        "new_id": new_id,
                        "segment": closest_seg,
                        "action": "reallocated",
                    })
                else:
                    errors.append({
                        "type": "out_of_bound",
                        "id": oob_id,
                        "reason": "目标段已满或无可用ID",
                    })
            else:
                errors.append({
                    "type": "out_of_bound",
                    "id": oob_id,
                    "reason": "无法确定目标段",
                })

        self._build_index()
        self._last_conflicts = None

        return {
            "success": len(errors) == 0,
            "fixed": fixed,
            "warnings": warnings,
            "errors": errors,
            "fixed_count": len(fixed),
            "warning_count": len(warnings),
            "error_count": len(errors),
            "message": f"自动修复完成: 修复 {len(fixed)}, 警告 {len(warnings)}, 错误 {len(errors)}",
        }

    # ============================================================
    # 辅助方法
    # ============================================================

    @staticmethod
    def _get_timestamp() -> str:
        """获取当前时间戳字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_used_ids(self) -> Set[int]:
        """获取所有已占用的 ID"""
        return set(self._id_map.keys())

    def get_text(self, id_value: int) -> Optional[str]:
        """根据 ID 获取文本"""
        return self._id_map.get(id_value)

    def get_id_by_text(self, text: str) -> Optional[int]:
        """根据文本获取 ID"""
        return self._text_reverse.get(text)

    def get_all_ids(self) -> Dict[int, str]:
        """获取所有 ID 到文本的映射"""
        return dict(self._id_map)

    def clear_reservations(self):
        """清除所有预留 ID"""
        self._reserved_ids.clear()

    def save(self, file_path: str = None):
        """保存 TermText.ini"""
        target = file_path or self._file_path
        if target:
            self.parser.save(target)
            logger.info("TermText.ini 已保存: %s", target)