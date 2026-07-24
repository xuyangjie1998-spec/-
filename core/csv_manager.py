"""
CSV 批量导入/导出管理器
- 支持武将/兵种/物品/技能/阵型/称号/剧本/势力/城池数据
- 自动检测编码 (GBK/Big5/UTF-8)
- 导入时支持字段映射和校验
"""

import csv
import os
import io
from typing import Dict, List, Any, Optional


class CsvManager:
    """群7 MOD 数据 CSV 导入导出"""

    # 各数据类型的标准字段列表
    FIELD_MAPS = {
        "general": [
            "No", "Name", "FaceID", "WStr", "Int", "HP", "MP",
            "Morale", "Loyal", "Life", "Sex", "Weapon", "Horse",
            "Formation", "BFSoldier", "BFSoldier1", "BFSoldier2",
            "Sword", "Spear", "Bow", "HorseSkill", "Blade", "Fan",
            "SuperSkill", "SuperSkillExp", "IsFamous", "City1", "City2",
            "City3", "City4", "City5", "Father", "Spouse", "AppearYear",
            "Lord", "Respawn", "Relation", "IsEvent", "IsUsed"
        ],
        "soldier": [
            "No", "Name", "Special", "OrderNo", "ObjID",
            "Data01", "Data02", "Data03", "SuperHit", "Feature",
            "Sex", "DieMode", "Rank", "Upgrade", "OffsetZ", "SizeX",
            "Str", "Int", "Life", "Speed", "Interval",
            "DetectRangeMin", "DetectRangeMax", "Weapon", "WeaponSpeed",
            "BasePower", "AddPower", "Height", "Horse", "Type", "Color",
            "IsUsed", "BFMagic", "SFMagic", "SuperAttack"
        ],
        "thing": [
            "No", "Name", "Type", "Price", "HP", "MP", "WStr", "Int",
            "Speed", "Morale", "Loyal", "Life", "ATK", "DEF",
            "Level", "Magic", "Skill", "IsUsed", "Desc", "IconID"
        ],
        "skill": [
            "No", "Name", "Level", "MP", "Target", "Range", "AttackType",
            "Damage", "StrMode", "IntMode", "IsUsed", "Desc"
        ],
        "formation": [
            "No", "Name", "Type", "ATK", "DEF", "Speed", "Range", "IsUsed", "Desc"
        ],
        "title": [
            "No", "Name", "Level", "WStr", "Int", "HP", "MP", "Morale",
            "Loyal", "IsUsed", "Desc"
        ],
        "scenario": [
            "No", "Name", "Year", "Month", "Day", "IsUsed", "Desc"
        ],
        "nation": [
            "No", "Name", "Color", "Lord", "IsUsed", "Desc"
        ],
        "city": [
            "No", "Name", "Type", "Population", "Defense", "Gold",
            "Food", "Morale", "IsUsed", "Desc"
        ],
    }

    # 字段别名映射（旧字段名→新字段名），用于向后兼容旧CSV文件
    FIELD_ALIASES = {
        "HP": "Life",
        "ATK": "BasePower",
        "DEF": "AddPower",
        "Level": "Rank",
        "Range": "DetectRangeMax",
        "ItemID": "ObjID",
        "AttackType": "Weapon",
    }

    def __init__(self):
        self._encoding = "gbk"

    def _detect_encoding(self, file_path: str) -> str:
        """检测 CSV 文件编码（优先 UTF-8 BOM → UTF-8 → GBK → Big5）"""
        try:
            with open(file_path, "rb") as f:
                raw = f.read(4096)
            if raw.startswith(b'\xef\xbb\xbf'):
                return "utf-8-sig"
            # 尝试 UTF-8
            try:
                raw.decode("utf-8")
                return "utf-8"
            except UnicodeDecodeError:
                pass
            # 尝试 GBK（简体中文）
            try:
                raw.decode("gbk")
                return "gbk"
            except UnicodeDecodeError:
                pass
            # 尝试 Big5（繁体中文）
            try:
                raw.decode("big5")
                return "big5"
            except UnicodeDecodeError:
                pass
            return "gbk"
        except (UnicodeDecodeError, LookupError):
            return "gbk"

    def export_csv(self, data_type: str, data: List[Dict], file_path: str) -> bool:
        """导出数据到 CSV 文件"""
        fields = self.FIELD_MAPS.get(data_type)
        if not fields:
            raise ValueError(f"不支持的数据类型: {data_type}")
        if not data:
            # 空数据也导出表头
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(fields)
            return True

        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(fields)
            for row in data:
                writer.writerow([row.get(f, "") for f in fields])
        return True

    def export_csv_string(self, data_type: str, data: List[Dict]) -> str:
        """导出数据为 CSV 字符串（用于前端下载）"""
        fields = self.FIELD_MAPS.get(data_type)
        if not fields:
            raise ValueError(f"不支持的数据类型: {data_type}")

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(fields)
        for row in data:
            writer.writerow([row.get(f, "") for f in fields])
        return output.getvalue()

    def preview_csv(self, data_type: str, file_path: str) -> Dict:
        """预览 CSV 文件内容，返回字段映射和预览数据"""
        fields = self.FIELD_MAPS.get(data_type)
        if not fields:
            return {"success": False, "message": f"不支持的数据类型: {data_type}"}

        encoding = self._detect_encoding(file_path)
        try:
            with open(file_path, "r", encoding=encoding, errors="replace") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    return {"success": False, "message": "CSV 文件为空"}

                # 字段映射：CSV头 -> 标准字段
                field_map = self._build_field_map(header, fields)

                rows = []
                for row in reader:
                    if not any(row):
                        continue
                    mapped = {}
                    for i, val in enumerate(row):
                        if i < len(header) and header[i] in field_map:
                            mapped[field_map[header[i]]] = val.strip()
                    rows.append(mapped)

                return {
                    "success": True,
                    "encoding": encoding,
                    "csv_header": header,
                    "field_map": field_map,
                    "unmapped": [h for h in header if h not in field_map],
                    "preview": rows[:10],
                    "total_rows": len(rows),
                    "standard_fields": fields,
                }
        except Exception as e:
            return {"success": False, "message": f"读取 CSV 失败: {str(e)}"}

    def import_csv(self, data_type: str, file_path: str) -> Dict:
        """导入 CSV 文件，返回解析后的数据（含 Big5 编码检测、字段验证、重复 ID 检测）"""
        fields = self.FIELD_MAPS.get(data_type)
        if not fields:
            return {"success": False, "message": f"不支持的数据类型: {data_type}"}

        encoding = self._detect_encoding(file_path)
        try:
            with open(file_path, "r", encoding=encoding, errors="replace") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    return {"success": False, "message": "CSV 文件为空"}

                field_map = self._build_field_map(header, fields)

                rows = []
                errors = []
                seen_ids = {}  # 用于重复 ID 检测
                numeric_fields = self._get_numeric_fields(data_type)

                for line_no, row in enumerate(reader, start=2):
                    if not any(row):
                        continue
                    mapped = {}
                    for i, val in enumerate(row):
                        if i < len(header) and header[i] in field_map:
                            mapped[field_map[header[i]]] = val.strip()
                    if not mapped:
                        continue

                    # 必填字段检查
                    no_val = mapped.get("No", "")
                    if not no_val:
                        errors.append(f"第 {line_no} 行缺少编号(No)")
                        continue

                    # 重复 ID 检测
                    if no_val in seen_ids:
                        errors.append(f"第 {line_no} 行编号 {no_val} 与第 {seen_ids[no_val]} 行重复")
                        continue
                    seen_ids[no_val] = line_no

                    # 字段值验证
                    for field_name, value in mapped.items():
                        if not value:
                            continue
                        if field_name in numeric_fields:
                            try:
                                int(value)
                            except (ValueError, TypeError):
                                errors.append(f"第 {line_no} 行字段 {field_name} 值 '{value}' 不是有效整数")

                    rows.append(mapped)

                return {
                    "success": True,
                    "encoding": encoding,
                    "data": rows,
                    "count": len(rows),
                    "errors": errors,
                    "field_map": field_map,
                    "duplicate_ids": [e for e in errors if "重复" in e],
                }
        except Exception as e:
            return {"success": False, "message": f"导入 CSV 失败: {str(e)}"}

    def _get_numeric_fields(self, data_type: str) -> set:
        """获取需要数值验证的字段集合"""
        numeric = {
            "No", "FaceID", "WStr", "Int", "HP", "MP",
            "Morale", "Loyal", "Life", "Sex", "Weapon", "Horse",
            "Formation", "BFSoldier", "BFSoldier1", "BFSoldier2",
            "Sword", "Spear", "Bow", "HorseSkill", "Blade", "Fan",
            "SuperSkill", "IsFamous", "Father", "Spouse", "Lord",
            "Respawn", "Relation", "IsEvent", "IsUsed", "Speed",
            "Level", "ATK", "DEF", "Price", "Type", "Range",
            "Magic", "Skill", "Target", "AttackType", "Year",
            "Month", "Day", "Color", "Population", "Defense",
            "Gold", "Food", "Morale", "Rank", "StrMode", "IntMode",
            "Damage", "IconID", "ItemID", "Desc",
        }
        return numeric

    def _build_field_map(self, csv_header: List[str], standard_fields: List[str]) -> Dict[str, str]:
        """构建 CSV 表头到标准字段的映射（支持别名向后兼容）"""
        field_map = {}
        csv_lower = {h.strip().lower(): h.strip() for h in csv_header if h.strip()}

        for sf in standard_fields:
            sf_lower = sf.lower()
            if sf_lower in csv_lower:
                field_map[csv_lower[sf_lower]] = sf
            elif sf_lower == "no" and "id" in csv_lower:
                field_map[csv_lower["id"]] = sf
            elif sf_lower == "name" and "名称" in csv_lower:
                field_map[csv_lower["名称"]] = sf

        # 别名映射：旧CSV字段名 → 新标准字段名
        for alias_from, alias_to in self.FIELD_ALIASES.items():
            alias_lower = alias_from.lower()
            if alias_lower in csv_lower and alias_to not in field_map.values():
                field_map[csv_lower[alias_lower]] = alias_to

        return field_map

    def get_field_map(self, data_type: str) -> Optional[List[str]]:
        """获取数据类型的标准字段列表"""
        return self.FIELD_MAPS.get(data_type)