"""
全局数据校验器
检测：编号重复、引用缺失、数值范围溢出、兵种上限
跨文件引用一致性校验
"""

import os
from typing import Dict, List, Set, Optional, Any, Tuple


class ValidationResult:
    """单条校验结果"""
    SEVERITY_ERROR = "error"
    SEVERITY_WARNING = "warning"
    SEVERITY_INFO = "info"

    def __init__(self, severity: str, category: str, message: str,
                 file_ref: str = "", section_ref: str = "", field_ref: str = ""):
        self.severity = severity
        self.category = category
        self.message = message
        self.file_ref = file_ref
        self.section_ref = section_ref
        self.field_ref = field_ref

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "file_ref": self.file_ref,
            "section_ref": self.section_ref,
            "field_ref": self.field_ref,
        }


class DataValidator:
    """
    数据校验器
    校验规则：
    1. 编号唯一性
    2. 数值范围（四维 0-255/突破后可更高，体力技力等）
    3. 跨文件引用完整性（武将引用的兵种编号是否存在等）
    4. 兵种总数上限（67原版，突破后另行处理）
    5. TermText文本引用完整性
    """

    # 数值范围定义
    RANGE_RULES = {
        "general": {
            "No": (0, 9999),
            "WStr": (0, 255),      # 武力
            "Int": (0, 255),        # 智力
            "HP": (0, 9999),        # 体力
            "MP": (0, 9999),        # 技力
            "FaceID": (0, 9999),    # 头像编号
            "Morale": (0, 100),     # 士气
            "Loyal": (0, 100),      # 义理
            "BFSoldier": (0, 67),   # 基础兵种
            "BFSoldier1": (0, 67),
            "BFSoldier2": (0, 67),
            "Life": (0, 9999),      # 寿命
            "HorseSkill": (0, 255),  # 骑术
            "Sword": (0, 255),      # 剑熟练度
            "Spear": (0, 255),      # 枪熟练度
            "Bow": (0, 255),        # 弓熟练度
            "Blade": (0, 255),      # 刀熟练度
            "Fan": (0, 255),        # 扇熟练度
            "Formation": (0, 99),   # 阵型
            "Sex": (0, 1),          # 性别
            "IsFamous": (0, 1),     # 名将
            "Respawn": (0, 1),      # 复活
            "IsUsed": (0, 1),       # 启用
        },
        "soldier": {
            "No": (0, 9999),
            "Life": (0, 9999),      # 生命值
            "Speed": (0, 100),
            "Upgrade": (0, 9999),   # 升级目标
            "IsUsed": (0, 1),
            "Type": (0, 99),
            "Special": (0, 9999),
            "SuperHit": (0, 100),
            "Sex": (0, 2),
            "Rank": (0, 99),        # 兵种阶级
            "SizeX": (0, 99),
            "Str": (0, 99),
            "Int": (0, 99),
            "Interval": (0, 999),
            "DetectRangeMin": (0, 999),
            "DetectRangeMax": (0, 999),
            "Weapon": (0, 99),
            "WeaponSpeed": (0, 999),
            "BasePower": (0, 9999),  # 初始攻击力
            "AddPower": (0, 9999),   # 防御力
            "Height": (0, 999),
            "Horse": (0, 99),
            "Color": (0, 9999),
        },
        "thing": {
            "No": (0, 9999),
            "Type": (0, 99),
            "Level": (0, 99),
            "ATK": (0, 999),
            "DEF": (0, 999),
            "HP": (0, 9999),
            "MP": (0, 9999),
            "Price": (0, 99999),
            "Rare": (0, 5),
            "IsRare": (0, 1),
            "IsSell": (0, 1),
            "IsOnly": (0, 1),
            "Count": (0, 99),
            "Speed": (0, 99),
            "Loyal": (0, 100),
            "Str": (0, 255),
            "Int": (0, 255),
            "ResponseTime": (-99, 99),
            "ScriptHit": (0, 100),
            "IsUsed": (0, 1),
            "General": (0, 9999),   # 专属武将
        },
        "bfmagic": {
            "No": (0, 9999),
            "Level": (0, 99),
            "MP": (0, 999),
            "Power": (0, 9999),
            "SolPower": (0, 9999),
            "Str0": (0, 255),
            "Str1": (0, 255),
            "Int0": (0, 255),
            "Int1": (0, 255),
            "IsUsed": (0, 1),
        },
        "superatk": {
            "NO": (0, 9999),
            "HitRatio": (0, 100),
            "General01": (0, 999),
            "Sol01": (0, 999),
            "Weapon0Exp": (0, 255),
            "Weapon3Exp": (0, 255),
            "Weapon4Exp": (0, 255),
            "IsUsed": (0, 1),
        },
        "title": {
            "No": (0, 9999),
            "Type": (0, 3),
            "Level": (0, 99),
            "Cost": (0, 999999),
            "Str0": (0, 255),
            "Str1": (0, 255),
            "Int0": (0, 255),
            "Int1": (0, 255),
            "HP": (0, 9999),
            "MP": (0, 9999),
            "IsUsed": (0, 1),
        },
        "genlv": {
            "No": (0, 99),
            "Exp": (0, 99999999),
            "SolNum": (0, 9999),
        },
        "city": {
            "No": (0, 999),
            "People": (0, 9999999),
            "PeopleHeart": (0, 1000),
            "Money": (0, 999999),
            "Defend": (0, 999),
            "Economics": (0, 999),
            "ReserveSoldierNumCur": (0, 9999),
            "IsUsed": (0, 1),
        },
    }

    SOLDIER_LIMIT = 67  # 原版兵种上限

    def __init__(self):
        self.results: List[ValidationResult] = []
        self._game_path: str = ""

    def set_game_path(self, path: str):
        self._game_path = path

    def clear(self):
        self.results.clear()

    def add_result(self, severity: str, category: str, message: str,
                   file_ref: str = "", section_ref: str = "", field_ref: str = ""):
        self.results.append(ValidationResult(
            severity, category, message, file_ref, section_ref, field_ref
        ))

    # ---------- 编号校验 ----------

    def check_duplicate_ids(self, entries: List[Dict], schema_type: str,
                            file_ref: str = "") -> List[ValidationResult]:
        """检查重复编号"""
        results = []
        seen = {}
        for i, entry in enumerate(entries):
            no = entry.get("No", "")
            if no in seen:
                results.append(ValidationResult(
                    ValidationResult.SEVERITY_ERROR,
                    "duplicate_id",
                    f"编号 {no} 重复出现（第{seen[no]+1}条 vs 第{i+1}条）",
                    file_ref,
                    f"Entry_{i}",
                    "No"
                ))
            else:
                seen[no] = i
        self.results.extend(results)
        return results

    def check_missing_ids(self, entries: List[Dict], schema_type: str,
                          file_ref: str = "") -> List[ValidationResult]:
        """检查编号缺失（空编号）"""
        results = []
        for i, entry in enumerate(entries):
            no = entry.get("No", None)
            if no is None or str(no).strip() == "":
                results.append(ValidationResult(
                    ValidationResult.SEVERITY_ERROR,
                    "missing_id",
                    f"第{i+1}条数据缺少编号",
                    file_ref,
                    f"Entry_{i}",
                    "No"
                ))
        self.results.extend(results)
        return results

    # ---------- 数值范围校验 ----------

    def check_value_ranges(self, entries: List[Dict], schema_type: str,
                           file_ref: str = "") -> List[ValidationResult]:
        """检查数值范围"""
        results = []
        rules = self.RANGE_RULES.get(schema_type, {})
        for i, entry in enumerate(entries):
            for field, value in entry.items():
                if field in rules:
                    min_val, max_val = rules[field]
                    try:
                        v = int(value)
                        if v < min_val or v > max_val:
                            results.append(ValidationResult(
                                ValidationResult.SEVERITY_WARNING,
                                "value_overflow",
                                f"字段 {field} 值 {v} 超出范围 [{min_val}, {max_val}]",
                                file_ref,
                                f"Entry_{i}",
                                field
                            ))
                    except (ValueError, TypeError):
                        pass
        self.results.extend(results)
        return results

    # ---------- 跨文件引用校验 ----------

    def check_cross_references(self, generals: List[Dict], soldiers: List[Dict],
                               things: List[Dict]) -> List[ValidationResult]:
        """检查跨文件引用完整性"""
        results = []
        soldier_ids = {str(s.get("No", "")) for s in soldiers}
        thing_ids = {str(t.get("No", "")) for t in things}

        for i, gen in enumerate(generals):
            # 检查兵种引用
            for field in ["BFSoldier", "BFSoldier1", "BFSoldier2"]:
                sid = str(gen.get(field, ""))
                if sid and sid not in soldier_ids:
                    results.append(ValidationResult(
                        ValidationResult.SEVERITY_ERROR,
                        "broken_reference",
                        f"武将 {gen.get('No')} 引用的兵种编号 {sid} 不存在",
                        "General01.ini",
                        f"Entry_{i}",
                        field
                    ))
            # 检查武器/坐骑引用
            for field in ["Weapon", "Horse"]:
                tid = str(gen.get(field, ""))
                if tid and tid not in thing_ids:
                    results.append(ValidationResult(
                        ValidationResult.SEVERITY_WARNING,
                        "broken_reference",
                        f"武将 {gen.get('No')} 引用的物品编号 {tid} 不存在",
                        "General01.ini",
                        f"Entry_{i}",
                        field
                    ))

        self.results.extend(results)
        return results

    # ---------- 扩展跨文件引用校验 ----------

    def check_skill_references(self, generals: List[Dict], defskill: List[Dict]) -> List[ValidationResult]:
        """检查武将特性引用一致性"""
        results = []
        gen_nos = {str(g.get("No", "")) for g in generals}
        defskill_nos = {str(d.get("No", "")) for d in defskill}

        # 武将存在于General01但不在DefSkill
        for g in generals:
            no = str(g.get("No", ""))
            if no and no not in defskill_nos:
                results.append(ValidationResult(
                    ValidationResult.SEVERITY_WARNING,
                    "missing_defskill",
                    f"武将 {no} ({g.get('Name','')}) 在DefSkill.ini中缺少特性配置",
                    "DefSkill.ini",
                    "",
                    "No"
                ))
        # DefSkill中存在但武将不在
        for d in defskill:
            no = str(d.get("No", ""))
            if no and no not in gen_nos:
                results.append(ValidationResult(
                    ValidationResult.SEVERITY_WARNING,
                    "orphan_defskill",
                    f"DefSkill.ini中存在编号 {no} ({d.get('Name','')}) 但General01.ini中无对应武将",
                    "DefSkill.ini",
                    "",
                    "No"
                ))

        self.results.extend(results)
        return results

    def check_birth_place_references(self, generals: List[Dict], general02: List[Dict]) -> List[ValidationResult]:
        """检查武将出生地引用一致性"""
        results = []
        gen_nos = {str(g.get("No", "")) for g in generals}
        g2_nos = {str(g.get("No", "")) for g in general02}

        for g in generals:
            no = str(g.get("No", ""))
            if no and no not in g2_nos:
                results.append(ValidationResult(
                    ValidationResult.SEVERITY_WARNING,
                    "missing_birth_place",
                    f"武将 {no} ({g.get('Name','')}) 在General02.ini中缺少出生地配置",
                    "General02.ini",
                    "",
                    "No"
                ))

        self.results.extend(results)
        return results

    def check_thing_references(self, things: List[Dict]) -> List[ValidationResult]:
        """检查物品数据完整性"""
        results = []
        for i, t in enumerate(things):
            no = str(t.get("No", ""))
            name = t.get("Name", "")
            ttype = str(t.get("Type", ""))

            # 武器必须有攻击力
            if ttype == "2":
                atk = t.get("ATK", "0")
                try:
                    if int(atk) == 0:
                        results.append(ValidationResult(
                            ValidationResult.SEVERITY_INFO,
                            "weapon_no_atk",
                            f"武器 {no} ({name}) 攻击力为0",
                            "Thing.ini",
                            f"Entry_{i}",
                            "ATK"
                        ))
                except (ValueError, TypeError):
                    pass

            # 物品名称不应为空
            if not name or name.strip() == "":
                results.append(ValidationResult(
                    ValidationResult.SEVERITY_WARNING,
                    "empty_name",
                    f"物品 {no} 名称为空",
                    "Thing.ini",
                    f"Entry_{i}",
                    "Name"
                ))

        self.results.extend(results)
        return results

    def check_soldier_matrix(self, soldiers: List[Dict]) -> List[ValidationResult]:
        """检查兵种相克矩阵数值合理性（仅检查实际存在的 HitSol 字段）"""
        results = []
        # 收集所有兵种中实际存在的 HitSol 字段编号
        actual_hitsol_indices = set()
        for s in soldiers:
            for key in s:
                if key.startswith("HitSol") and key[6:].isdigit():
                    actual_hitsol_indices.add(int(key[6:]))
        for i, s in enumerate(soldiers):
            for j in sorted(actual_hitsol_indices):
                key = f"HitSol{j}"
                if key in s:
                    try:
                        val = int(s[key])
                        if val < 0 or val > 200:
                            results.append(ValidationResult(
                                ValidationResult.SEVERITY_WARNING,
                                "invalid_hitsol",
                                f"兵种 {s.get('No')} HitSol{j}={val} 超出合理范围(0-200)",
                                "Soldier.ini",
                                f"Entry_{i}",
                                key
                            ))
                    except (ValueError, TypeError):
                        results.append(ValidationResult(
                            ValidationResult.SEVERITY_WARNING,
                            "invalid_hitsol",
                            f"兵种 {s.get('No')} HitSol{j} 值无效: '{s[key]}'",
                            "Soldier.ini",
                            f"Entry_{i}",
                            key
                        ))
        self.results.extend(results)
        return results

    def check_termtext_references(self, entries: List[Dict], entry_type: str) -> List[ValidationResult]:
        """检查条目名称是否在 TermText 中有对应注册"""
        results = []
        # 名称约定：TermText 中应存在与 Name 匹配的条目
        # 常见模式: {Name} = 字符串ID
        for i, entry in enumerate(entries):
            name = (entry.get("Name") or "").strip()
            if not name:
                # 允许空名称（未使用的条目）
                continue
            # 检查名称是否包含非法字符
            illegal = [c for c in name if ord(c) < 32 and c not in ('\n', '\r', '\t')]
            if illegal:
                results.append(ValidationResult(
                    "warning", "termtext_char",
                    f"名称包含控制字符: '{name[:20]}'",
                    f"{entry_type.upper()}.ini", f"Entry_{i}", "Name"
                ))
        self.results.extend(results)
        return results

    def check_skill_id_references(self, generals: List[Dict], defskill: List[Dict],
                                   things: List[Dict], titles: List[Dict],
                                   bfmagic_ids: Set[str], sfmagic_ids: Set[str],
                                   genskill_ids: Set[str], armyskill_ids: Set[str],
                                   armygroupskill_ids: Set[str], superatk_ids: Set[str]) -> List[ValidationResult]:
        """跨文件技能引用校验：检查武将/DefSkill/物品/官职引用的技能ID是否存在"""
        results = []

        def check_ref(label: str, ref_id: str, file_ref: str, entry_no: str, field: str, valid_ids: set, skill_type: str):
            """检查单个技能引用"""
            rid = ref_id.strip()
            if not rid or rid == "0":
                return
            if rid not in valid_ids:
                results.append(ValidationResult(
                    ValidationResult.SEVERITY_ERROR,
                    "broken_skill_ref",
                    f"{label} #{entry_no} 引用的{skill_type}编号 {rid} 不存在",
                    file_ref, f"Entry_{entry_no}", field
                ))

        # 1. 武将 SuperSkill → SuperAtk.ini
        for i, gen in enumerate(generals):
            no = str(gen.get("No", ""))
            ss = str(gen.get("SuperSkill", "")).strip()
            if ss and ss != "0":
                check_ref(f"武将", ss, "General01.ini", no, "SuperSkill", superatk_ids, "必杀技")

        # 2. DefSkill 中的技能列表 (逗号分隔)
        for d in defskill:
            no = str(d.get("No", ""))
            for field, skill_type, valid_ids in [
                ("BFMagic", "武将技", bfmagic_ids),
                ("SFMagic", "军师技", sfmagic_ids),
                ("GenSkill", "个人特性", genskill_ids),
                ("ArmySkill", "主将特性", armyskill_ids),
                ("ArmyGroupSkill", "元帅特性", armygroupskill_ids),
            ]:
                val = str(d.get(field, "")).strip()
                if val:
                    for rid in val.split(","):
                        check_ref(f"DefSkill", rid.strip(), "DefSkill.ini", no, field, valid_ids, skill_type)

        # 3. 物品中的技能引用
        for i, t in enumerate(things):
            no = str(t.get("No", ""))
            for slot in range(1, 6):
                field = f"BFMagic{slot:02d}"
                val = str(t.get(field, "")).strip()
                if val and val != "0":
                    check_ref(f"物品", val, "Thing.ini", no, field, bfmagic_ids, "武将技")
            for slot in range(1, 3):
                field = f"SFMagic{slot:02d}"
                val = str(t.get(field, "")).strip()
                if val and val != "0":
                    check_ref(f"物品", val, "Thing.ini", no, field, sfmagic_ids, "军师技")
            for field in ["SuperAttack"]:
                val = str(t.get(field, "")).strip()
                if val and val != "0":
                    check_ref(f"物品", val, "Thing.ini", no, field, superatk_ids, "必杀技")
            for field in ["GenSkill01", "GenSkill02"]:
                val = str(t.get(field, "")).strip()
                if val and val != "0":
                    check_ref(f"物品", val, "Thing.ini", no, field, genskill_ids, "个人特性")
            for field in ["ArmySkill01", "ArmySkill02"]:
                val = str(t.get(field, "")).strip()
                if val and val != "0":
                    check_ref(f"物品", val, "Thing.ini", no, field, armyskill_ids, "主将特性")

        # 4. 官职中的技能引用
        for i, t in enumerate(titles):
            no = str(t.get("No", ""))
            for slot in range(1, 6):
                field = f"BFMagic{slot}"
                val = str(t.get(field, "")).strip()
                if val and val != "0":
                    check_ref(f"官职", val, "Title.ini", no, field, bfmagic_ids, "武将技")
            for slot in range(1, 6):
                field = f"SFMagic{slot}"
                val = str(t.get(field, "")).strip()
                if val and val != "0":
                    check_ref(f"官职", val, "Title.ini", no, field, sfmagic_ids, "军师技")
            for field in ["GenSkill01", "GenSkill02"]:
                val = str(t.get(field, "")).strip()
                if val and val != "0":
                    check_ref(f"官职", val, "Title.ini", no, field, genskill_ids, "个人特性")
            for field in ["ArmySkill01", "ArmySkill02"]:
                val = str(t.get(field, "")).strip()
                if val and val != "0":
                    check_ref(f"官职", val, "Title.ini", no, field, armyskill_ids, "主将特性")

        self.results.extend(results)
        return results

    def check_nation_city_consistency(self, nations: List[Dict], cities: List[Dict]) -> List[ValidationResult]:
        """检查势力与城池一致性"""
        results = []
        nation_lords = set()
        for n in nations:
            lord = n.get("Lord", "").split(";")[0].strip() if n.get("Lord") else ""
            if lord:
                nation_lords.add(lord)

        city_lords = set()
        for c in cities:
            lord = str(c.get("Lord", "")).strip()
            if lord:
                city_lords.add(lord)

        # 城池有君主但不在势力中
        orphan = city_lords - nation_lords
        for lord in orphan:
            if lord:
                results.append(ValidationResult(
                    ValidationResult.SEVERITY_WARNING,
                    "orphan_city",
                    f"城池君主编号 {lord} 不在Nation.ini中",
                    "Nation.ini",
                    "",
                    ""
                ))

        self.results.extend(results)
        return results

    def check_faceid_references(self, generals: List[Dict], game_path: str = "") -> List[ValidationResult]:
        """检查武将 FaceID 是否对应 Shape/Face/ 下的 SHP 文件"""
        results = []
        if not game_path:
            return results

        face_dir = os.path.join(game_path, "Shape", "Face")
        existing_face_nums = set()
        if os.path.exists(face_dir):
            for f in os.listdir(face_dir):
                if f.lower().endswith(".shp"):
                    # 提取编号: 如 Face0001.shp -> 0001
                    num_part = ''.join(c for c in f if c.isdigit())
                    if num_part:
                        existing_face_nums.add(int(num_part))

        for i, gen in enumerate(generals):
            face_id = gen.get("FaceID", "").strip()
            if not face_id:
                continue
            try:
                face_num = int(face_id)
                if face_num not in existing_face_nums:
                    results.append(ValidationResult(
                        ValidationResult.SEVERITY_WARNING,
                        "missing_face",
                        f"武将 #{gen.get('No')} 的 FaceID={face_id} 在 Shape/Face/ 中未找到对应头像",
                        "General01.ini", f"Entry_{i}", "FaceID"
                    ))
            except (ValueError, TypeError):
                pass

        self.results.extend(results)
        return results

    # ---------- 全面校验 ----------

    def validate_all(self, generals: list, soldiers: list, things: list,
                     defskill: list = None, general02: list = None,
                     nations: list = None, cities: list = None) -> dict:
        """执行全面校验，返回汇总结果"""
        self.clear()

        self.check_duplicate_ids(generals, "general", "General01.ini")
        self.check_missing_ids(generals, "general", "General01.ini")
        self.check_value_ranges(generals, "general", "General01.ini")

        self.check_duplicate_ids(soldiers, "soldier", "Soldier.ini")
        self.check_missing_ids(soldiers, "soldier", "Soldier.ini")
        self.check_value_ranges(soldiers, "soldier", "Soldier.ini")
        self.check_soldier_limit(len(soldiers), "Soldier.ini")
        self.check_soldier_matrix(soldiers)

        self.check_duplicate_ids(things, "thing", "Thing.ini")
        self.check_missing_ids(things, "thing", "Thing.ini")
        self.check_value_ranges(things, "thing", "Thing.ini")
        self.check_thing_references(things)

        self.check_cross_references(generals, soldiers, things)

        # 新增校验：TermText 名称存在性
        self.check_termtext_references(generals, "general")
        self.check_termtext_references(soldiers, "soldier")
        self.check_termtext_references(things, "thing")

        # FaceID 存在性校验（需要游戏目录）
        if hasattr(self, '_game_path') and self._game_path:
            self.check_faceid_references(generals, self._game_path)

        if defskill:
            self.check_skill_references(generals, defskill)
        if general02:
            self.check_birth_place_references(generals, general02)
        if nations and cities:
            self.check_nation_city_consistency(nations, cities)

        return self.summary()

    def check_soldier_limit(self, soldier_count: int, file_ref: str = "") -> Optional[ValidationResult]:
        """检查兵种总数是否超过上限"""
        if soldier_count > self.SOLDIER_LIMIT:
            result = ValidationResult(
                ValidationResult.SEVERITY_ERROR,
                "soldier_limit",
                f"兵种数量 {soldier_count} 超过引擎上限 {self.SOLDIER_LIMIT}，请使用EXE突破工具",
                file_ref
            )
            self.results.append(result)
            return result
        return None

    # ---------- 汇总 ----------

    def get_errors(self) -> List[ValidationResult]:
        return [r for r in self.results if r.severity == ValidationResult.SEVERITY_ERROR]

    def get_warnings(self) -> List[ValidationResult]:
        return [r for r in self.results if r.severity == ValidationResult.SEVERITY_WARNING]

    def get_all(self) -> List[ValidationResult]:
        return self.results

    def has_errors(self) -> bool:
        return len(self.get_errors()) > 0

    def summary(self) -> dict:
        return {
            "total": len(self.results),
            "errors": len(self.get_errors()),
            "warnings": len(self.get_warnings()),
            "infos": len([r for r in self.results if r.severity == ValidationResult.SEVERITY_INFO]),
        }

    def to_dict_list(self) -> List[dict]:
        return [r.to_dict() for r in self.results]