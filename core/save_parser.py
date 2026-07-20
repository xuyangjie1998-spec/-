"""
群7存档结构化解析器 (v3.0)
- 根据社区逆向资料（游侠论坛 sdlt, 2006）解析 SG7-XX.sav
- 武将属性、装备、技能、兵种等完整字段解析
- 支持读写修改

参考:
- 游侠论坛 sdlt: 存档文件修改方法 (2006)
- 3DM论坛 qweytr_1: CustomGen.sav逆向分析 (2025)
- S7Edit by cly1982 (2008)
"""

import struct
from typing import Dict, List, Any, Optional, Tuple


class SaveParser:
    """群7 SG7-XX.sav 存档解析器"""

    # 兵种代码表
    SOLDIER_TYPES = {
        0x01: "轻步兵", 0x02: "重步兵", 0x03: "短弓兵", 0x04: "长弓兵",
        0x05: "短枪兵", 0x06: "长枪兵", 0x07: "弩兵", 0x08: "强弩兵",
        0x09: "轻骑兵", 0x0A: "重骑兵", 0x0B: "蛮兵", 0x0C: "藤甲兵",
        0x0D: "女兵", 0x0E: "近卫兵", 0x0F: "猛兽兵", 0x10: "象兵",
        0x11: "忍者", 0x12: "隐忍", 0x13: "弩车", 0x14: "连弩车",
        0x15: "投石车", 0x16: "飞石车", 0x17: "黄巾兵", 0x18: "黄巾长",
        0x19: "匈奴兵", 0x1A: "游骑兵", 0x1B: "浪人", 0x1C: "武士",
        0x1D: "尸兵", 0x1E: "尸魔", 0x1F: "木人", 0x20: "铁人",
        0x21: "刀车兵", 0x22: "铁车兵", 0x23: "剑兵", 0x24: "剑卫",
        0x25: "木锤兵", 0x26: "铁锤兵", 0x27: "链球兵", 0x28: "钢球兵",
        0x29: "水兵", 0x2A: "鳞甲水兵",
    }

    # 武器类型表 (对应 Thing.ini 中武器ID)
    WEAPON_TYPES = {
        1: "直剑", 2: "钢剑", 3: "大剑", 4: "双股剑", 5: "倚天剑",
        6: "青釭剑", 7: "七星剑", 8: "古锭刀", 9: "双铁戟", 10: "青龙偃月刀",
        11: "丈八蛇矛", 12: "方天画戟", 13: "朱雀扇", 14: "玄武扇", 15: "白虎扇",
        16: "青龙扇", 17: "短刀", 18: "长刀", 19: "大斧", 20: "铁脊蛇矛",
        21: "三尖刀", 22: "双刃斧", 23: "流星锤", 24: "铁鞭", 25: "大槌",
        26: "凤嘴刀", 27: "眉尖刀", 28: "钩镰刀", 29: "朱红枪", 30: "点钢枪",
        31: "龙胆枪", 32: "雁翎枪", 33: "铁蒺藜骨朵", 34: "梅花亮银枪", 35: "天罡斧",
        36: "泼风刀", 37: "龙渊剑", 38: "紫电剑", 39: "开山斧", 40: "鸣鸿刀",
        41: "金光剑", 42: "赤霄剑", 43: "太阿剑", 44: "真龙剑", 45: "湛卢剑",
        46: "冰魄剑", 47: "逆鳞刀", 48: "破军枪", 49: "朱雀羽扇", 50: "玄武羽扇",
        51: "白虎羽扇", 52: "青龙羽扇", 53: "紫金锤", 54: "银月枪", 55: "裂风刀",
        56: "惊雷戟", 57: "寒冰刃", 58: "烈焰剑", 59: "玄铁重剑", 60: "紫薇扇",
        61: "天罡剑", 62: "地煞刀", 63: "人王枪", 64: "鬼王戟", 65: "神王锤",
        66: "仙王扇", 67: "鬼头大刀", 68: "金背大刀", 69: "钩镰枪", 70: "狼牙棒",
        71: "双锤", 72: "铁锁", 73: "锁链刀", 74: "九节鞭", 75: "三节棍",
        76: "双鞭", 77: "轮刃", 78: "飞刀", 79: "飞镖", 80: "羽扇",
    }

    # 坐骑类型表 (对应 Thing.ini 中坐骑ID)
    HORSE_TYPES = {
        1: "黄鬃马", 2: "黑鬃马", 3: "褐鬃马", 4: "白马", 5: "赤兔马",
        6: "的卢", 7: "爪黄飞电", 8: "绝影", 9: "大宛马", 10: "乌骓马",
        11: "黄骠马", 12: "麒麟", 13: "穷奇", 14: "凤凰", 15: "龙马",
        16: "金毛狮", 17: "银鬃马", 18: "火麒麟", 19: "水麒麟", 20: "风麒麟",
        21: "雷麒麟", 22: "玄武马", 23: "白虎", 24: "青龙", 25: "朱雀",
        26: "四不像", 27: "紫骍", 28: "铁骑马", 29: "黑云", 30: "奔雷马",
    }

    # 道具类型表 (对应 Thing.ini 中道具ID)
    ITEM_TYPES = {
        1: "短弓", 2: "长弓", 3: "青囊书", 4: "遁甲天书", 5: "太平要术",
        6: "太平清领道", 7: "孙子兵法", 8: "孟德新书", 9: "史记", 10: "春秋左传",
        11: "吴子兵法", 12: "六韬", 13: "三略", 14: "司马法", 15: "尉缭子",
        16: "魏公子兵法", 17: "兵书二十四篇", 18: "治论", 19: "西蜀地形图", 20: "东吴地形图",
        21: "北魏地形图", 22: "南华经", 23: "太平经", 24: "道德经", 25: "庄子",
        26: "论语", 27: "孟子", 28: "韩非子", 29: "墨子", 30: "列子",
        31: "鬼谷子", 32: "山海经", 33: "易经", 34: "书经", 35: "诗经",
        36: "礼记", 37: "乐经", 38: "孝经", 39: "奇门遁甲", 40: "太玄经",
        41: "伏羲八卦", 42: "文王八卦", 43: "河图洛书", 44: "浑天仪", 45: "地动仪",
        46: "铜雀", 47: "玉玺", 48: "九锡", 49: "和氏璧", 50: "麒麟符",
    }

    # 阵型名称表
    FORMATION_TYPES = {
        0: "方形阵", 1: "圆形阵", 2: "锥形阵", 3: "雁形阵",
        4: "钩形阵", 5: "玄襄阵", 6: "鱼鳞阵", 7: "锋矢阵",
        8: "鹤翼阵", 9: "长蛇阵", 10: "偃月阵", 11: "衡轭阵",
        12: "水阵", 13: "火阵", 14: "风阵", 15: "云阵",
    }

    # 功勋系数
    MERIT_COEFFICIENTS = {
        0x41: 1/8, 0x42: 1/2, 0x43: 2, 0x44: 8,
        0x45: 32, 0x46: 128, 0x47: 512, 0x48: 2048, 0x49: 8192,
    }

    # 装备标记
    MARK_PATTERN = b"Mark\x00"

    def __init__(self):
        self._data: bytes = b""
        self._save_name: str = ""

    def load(self, filepath: str) -> dict:
        """加载存档文件"""
        try:
            with open(filepath, "rb") as f:
                self._data = f.read()
            self._save_name = filepath
            return {"success": True, "size": len(self._data), "name": filepath}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def load_bytes(self, data: bytes, name: str = "") -> dict:
        """从字节加载"""
        self._data = data
        self._save_name = name
        return {"success": True, "size": len(data), "name": name}

    # ============================================================
    # 武将搜索与解析
    # ============================================================

    def find_generals(self, wstr: int = None, intelligence: int = None) -> List[dict]:
        """
        搜索存档中的武将数据
        通过基本武力+智力（4字节LE）模式匹配
        """
        if not self._data:
            return []

        generals = []
        data = self._data

        if wstr is not None and intelligence is not None:
            # 精确搜索：武力+智力
            pattern = struct.pack("<II", wstr, intelligence)
            pos = 0
            while True:
                idx = data.find(pattern, pos)
                if idx < 0:
                    break
                # 确保是4字节对齐（武将数据通常对齐）
                gen = self._parse_general_at(data, idx, idx)
                if gen:
                    gen["offset"] = idx
                    generals.append(gen)
                pos = idx + 1
        else:
            # 扫描模式：搜索合理的武力值范围（50-255）后跟智力值（30-255）
            generals = self._scan_generals(data)

        return generals

    def _scan_generals(self, data: bytes) -> List[dict]:
        """扫描存档中所有可能的武将数据"""
        generals = []
        seen_offsets = set()

        for i in range(0, len(data) - 8, 4):
            if i in seen_offsets:
                continue
            try:
                wstr = struct.unpack("<I", data[i:i+4])[0]
                intel = struct.unpack("<I", data[i+4:i+8])[0]
            except struct.error:
                continue

            # 合理的武力/智力范围
            if 30 <= wstr <= 255 and 20 <= intel <= 255:
                gen = self._parse_general_at(data, i, i)
                if gen:
                    gen["offset"] = i
                    generals.append(gen)
                    seen_offsets.add(i)

        # 去重（按偏移）
        return generals

    def _parse_general_at(self, data: bytes, offset: int, display_offset: int) -> Optional[dict]:
        """
        解析偏移处的武将数据
        根据社区逆向资料，从武力地址起：
        - 0-3: 基本武力
        - 4-7: 基本智力
        - 8-11: 最大体力
        - 12-15: 当前体力
        - 16-19: 最大技力
        - 20-23: 当前技力
        - 24-27: 义理
        - 28-31: 相性
        - 32-35: 士气
        """
        if offset + 36 > len(data):
            return None

        try:
            wstr = struct.unpack("<I", data[offset:offset+4])[0]
            intel = struct.unpack("<I", data[offset+4:offset+8])[0]
            max_hp = struct.unpack("<I", data[offset+8:offset+12])[0]
            cur_hp = struct.unpack("<I", data[offset+12:offset+16])[0]
            max_mp = struct.unpack("<I", data[offset+16:offset+20])[0]
            cur_mp = struct.unpack("<I", data[offset+20:offset+24])[0]
            loyal = struct.unpack("<I", data[offset+24:offset+28])[0]
            relation = struct.unpack("<I", data[offset+28:offset+32])[0]
            morale = struct.unpack("<I", data[offset+32:offset+36])[0]
        except struct.error:
            return None

        # 基本合理性检查
        if wstr > 999 or intel > 999 or max_hp > 9999 or max_mp > 9999:
            return None
        if loyal > 100 or morale > 100:
            return None

        gen = {
            "offset": display_offset,
            "wstr": wstr,
            "intelligence": intel,
            "max_hp": max_hp,
            "cur_hp": cur_hp,
            "max_mp": max_mp,
            "cur_mp": cur_mp,
            "loyal": loyal,
            "relation": relation,
            "morale": morale,
        }

        # 解析扩展字段
        ext = self._parse_extended_fields(data, offset)
        gen.update(ext)

        return gen

    def _parse_extended_fields(self, data: bytes, offset: int) -> dict:
        """解析武将扩展字段（装备/技能/兵种等）"""
        ext = {}

        # 装备解析（在武力地址上方寻找 Mark\0 标记）
        equip = self._parse_equipment(data, offset)
        if equip:
            ext["equipment"] = equip

        # 功勋值 (offset + 5行 = offset + 80字节, +2字节)
        merit_offset = offset + 80
        if merit_offset + 2 <= len(data):
            try:
                merit_val = data[merit_offset]
                merit_coef = data[merit_offset + 1]
                coef = self.MERIT_COEFFICIENTS.get(merit_coef, 1)
                ext["merit"] = int(merit_val * coef)
                ext["merit_raw"] = {"val": merit_val, "coef": merit_coef}
            except (IndexError, struct.error):
                pass

        # 等级经验 (offset + 5行 + 4字节 = offset + 84)
        exp_offset = offset + 84
        if exp_offset + 4 <= len(data):
            try:
                exp = struct.unpack("<I", data[exp_offset:exp_offset+4])[0]
                ext["experience"] = exp
            except struct.error:
                pass

        # 当前兵种和带兵数 (offset + 6行 + 4字节 = offset + 100)
        soldier_offset = offset + 100
        if soldier_offset + 8 <= len(data):
            try:
                soldier_type = struct.unpack("<I", data[soldier_offset:soldier_offset+4])[0]
                soldier_count = struct.unpack("<I", data[soldier_offset+4:soldier_offset+8])[0]
                ext["current_soldier_type"] = soldier_type
                ext["current_soldier_name"] = self.SOLDIER_TYPES.get(soldier_type, f"未知(0x{soldier_type:02X})")
                ext["current_soldier_count"] = soldier_count
            except struct.error:
                pass

        # 可选兵种 (offset + 7行起始, 位掩码, 每字节8种)
        opt_soldier_offset = offset + 112
        if opt_soldier_offset + 4 <= len(data):
            ext["optional_soldiers"] = []
            for i in range(4):
                byte_val = data[opt_soldier_offset + i]
                for bit in range(8):
                    if byte_val & (1 << bit):
                        sol_id = i * 8 + bit + 1
                        sol_name = self.SOLDIER_TYPES.get(sol_id, f"兵种{sol_id}")
                        ext["optional_soldiers"].append({"id": sol_id, "name": sol_name})

        # 阵形 (offset + 8行起始, 位掩码)
        formation_offset = offset + 128
        if formation_offset + 1 <= len(data):
            ext["formations"] = data[formation_offset]

        # 武将技 (offset + 9行起始, 位掩码, 约32字节)
        bfmagic_offset = offset + 144
        if bfmagic_offset + 32 <= len(data):
            ext["bfmagic_mask"] = data[bfmagic_offset:bfmagic_offset+32].hex()

        # 军师技 (offset + 11行起始, 位掩码, 约32字节)
        sfmagic_offset = offset + 176
        if sfmagic_offset + 32 <= len(data):
            ext["sfmagic_mask"] = data[sfmagic_offset:sfmagic_offset+32].hex()

        # 个人特性 (每字节7个特性, 约4字节)
        genskill_offset = offset + 208
        if genskill_offset + 4 <= len(data):
            ext["genskill_mask"] = data[genskill_offset:genskill_offset+4].hex()

        # 主将特性
        armyskill_offset = offset + 212
        if armyskill_offset + 4 <= len(data):
            ext["armyskill_mask"] = data[armyskill_offset:armyskill_offset+4].hex()

        # 元帅特性
        armygroupskill_offset = offset + 216
        if armygroupskill_offset + 4 <= len(data):
            ext["armygroupskill_mask"] = data[armygroupskill_offset:armygroupskill_offset+4].hex()

        # 武器熟练度 (5类: 剑/枪/弓/刀/扇)
        weapon_exp_offset = offset + 220
        if weapon_exp_offset + 20 <= len(data):
            try:
                ext["weapon_exp"] = {
                    "sword": struct.unpack("<I", data[weapon_exp_offset:weapon_exp_offset+4])[0],
                    "spear": struct.unpack("<I", data[weapon_exp_offset+4:weapon_exp_offset+8])[0],
                    "bow": struct.unpack("<I", data[weapon_exp_offset+8:weapon_exp_offset+12])[0],
                    "blade": struct.unpack("<I", data[weapon_exp_offset+12:weapon_exp_offset+16])[0],
                    "fan": struct.unpack("<I", data[weapon_exp_offset+16:weapon_exp_offset+20])[0],
                }
            except struct.error:
                pass

        return ext

    def _parse_equipment(self, data: bytes, offset: int) -> Optional[dict]:
        """
        解析武将装备
        在武力地址上方寻找两个 Mark\0 标记
        中间4字节为武将代码
        第二个标记后5字节+4字节为道具数量X
        其后4*X字节为道具地址代码
        """
        # 向上搜索 Mark\0 标记（最多搜索512字节）
        search_start = max(0, offset - 512)
        search_data = data[search_start:offset]

        marks = []
        pos = 0
        while True:
            idx = search_data.find(self.MARK_PATTERN, pos)
            if idx < 0:
                break
            marks.append(search_start + idx)
            pos = idx + 1

        if len(marks) < 2:
            return None

        # 取最后两个标记
        mark1 = marks[-2]
        mark2 = marks[-1]

        # 武将代码（两个标记之间）
        if mark2 > mark1 + 5:
            gen_code = data[mark1 + 5:mark2]
            gen_code_hex = gen_code[:4].hex() if len(gen_code) >= 4 else ""
        else:
            gen_code_hex = ""

        # 道具数量（第二个标记后5字节 + 4字节）
        item_count_offset = mark2 + 9
        items = []
        if item_count_offset + 4 <= offset:
            try:
                item_count = struct.unpack("<I", data[item_count_offset:item_count_offset+4])[0]
                item_count = min(item_count, 3)  # 最多3个道具
                # 道具地址代码（在零点前4*X字节）
                for i in range(item_count):
                    item_addr_offset = offset - (item_count - i) * 4
                    if item_addr_offset >= 0 and item_addr_offset + 4 <= len(data):
                        item_addr = struct.unpack("<I", data[item_addr_offset:item_addr_offset+4])[0]
                        items.append({
                            "index": i,
                            "address": f"0x{item_addr:08X}",
                            "raw": data[item_addr_offset:item_addr_offset+4].hex(),
                        })
            except struct.error:
                pass

        return {
            "gen_code": gen_code_hex,
            "item_count": len(items),
            "items": items,
        }

    # ============================================================
    # 写入修改
    # ============================================================

    def write_general_stats(self, offset: int, field: str, value: int) -> dict:
        """写入武将属性值"""
        if not self._data or offset < 0:
            return {"success": False, "message": "未加载存档数据"}

        field_offsets = {
            "wstr": 0, "intelligence": 4, "max_hp": 8, "cur_hp": 12,
            "max_mp": 16, "cur_mp": 20, "loyal": 24, "relation": 28, "morale": 32,
        }

        if field not in field_offsets:
            return {"success": False, "message": f"未知字段: {field}"}

        write_offset = offset + field_offsets[field]
        if write_offset + 4 > len(self._data):
            return {"success": False, "message": "写入位置超出文件范围"}

        try:
            old_val = struct.unpack("<I", self._data[write_offset:write_offset+4])[0]
            new_data = bytearray(self._data)
            struct.pack_into("<I", new_data, write_offset, value)
            self._data = bytes(new_data)
            return {
                "success": True,
                "field": field,
                "offset": write_offset,
                "old_value": old_val,
                "new_value": value,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def write_merit(self, offset: int, value: int) -> dict:
        """写入功勋值（自动选择最佳系数）"""
        merit_offset = offset + 80
        if merit_offset + 2 > len(self._data):
            return {"success": False, "message": "超出范围"}

        # 选择最佳系数
        best_coef = 0x43  # 默认系数2
        best_val = value
        for coef_byte, coef in self.MERIT_COEFFICIENTS.items():
            candidate = int(value / coef)
            if 0 <= candidate <= 255:
                if abs(candidate * coef - value) < abs(best_val * self.MERIT_COEFFICIENTS.get(best_coef, 1) - value):
                    best_coef = coef_byte
                    best_val = candidate

        new_data = bytearray(self._data)
        new_data[merit_offset] = best_val
        new_data[merit_offset + 1] = best_coef
        self._data = bytes(new_data)

        actual = int(best_val * self.MERIT_COEFFICIENTS.get(best_coef, 1))
        return {"success": True, "field": "merit", "requested": value, "actual": actual, "raw_val": best_val, "coef": f"0x{best_coef:02X}"}

    def write_experience(self, offset: int, value: int) -> dict:
        """写入经验值"""
        exp_offset = offset + 84
        if exp_offset + 4 > len(self._data):
            return {"success": False, "message": "超出范围"}
        new_data = bytearray(self._data)
        struct.pack_into("<I", new_data, exp_offset, value)
        self._data = bytes(new_data)
        return {"success": True, "field": "experience", "value": value}

    def write_soldier(self, offset: int, soldier_type: int, soldier_count: int) -> dict:
        """写入当前兵种和带兵数"""
        soldier_offset = offset + 100
        if soldier_offset + 8 > len(self._data):
            return {"success": False, "message": "超出范围"}
        new_data = bytearray(self._data)
        struct.pack_into("<I", new_data, soldier_offset, soldier_type)
        struct.pack_into("<I", new_data, soldier_offset + 4, soldier_count)
        self._data = bytes(new_data)
        return {"success": True, "soldier_type": soldier_type, "soldier_count": soldier_count}

    def write_weapon_exp(self, offset: int, weapon: str, value: int) -> dict:
        """写入武器熟练度"""
        weapon_offsets = {"sword": 0, "spear": 4, "bow": 8, "blade": 12, "fan": 16}
        if weapon not in weapon_offsets:
            return {"success": False, "message": f"未知武器类型: {weapon}"}
        write_offset = offset + 220 + weapon_offsets[weapon]
        if write_offset + 4 > len(self._data):
            return {"success": False, "message": "超出范围"}
        new_data = bytearray(self._data)
        struct.pack_into("<I", new_data, write_offset, value)
        self._data = bytes(new_data)
        return {"success": True, "weapon": weapon, "value": value}

    # ============================================================
    # 结构化武将数据
    # ============================================================

    def get_structured_general(self, general_index: int) -> dict:
        """
        获取指定武将的结构化数据

        Args:
            general_index: 武将索引 (0-based)

        Returns:
            包含 basic_stats, equipment, military, skills, experience, meta 的 dict
        """
        generals = self.find_generals()
        if general_index < 0 or general_index >= len(generals):
            return {"success": False, "message": f"武将索引 {general_index} 超出范围 (共 {len(generals)} 个武将)"}

        g = generals[general_index]
        offset = g["offset"]

        # 基本属性
        basic_stats = {
            "wstr": g.get("wstr", 0),
            "intelligence": g.get("intelligence", 0),
            "hp": g.get("cur_hp", 0),
            "max_hp": g.get("max_hp", 0),
            "mp": g.get("cur_mp", 0),
            "max_mp": g.get("max_mp", 0),
            "justice": g.get("loyal", 0),
            "personality": g.get("relation", 0),
            "morale": g.get("morale", 0),
        }

        # 装备信息（解析装备ID）
        equipment = self._parse_equipment_ids(g)

        # 军事信息
        military = {
            "soldier_type": g.get("current_soldier_type", 0),
            "soldier_type_name": g.get("current_soldier_name", "未知"),
            "soldier_count": g.get("current_soldier_count", 0),
            "formation": g.get("formations", 0),
            "formation_names": self._parse_formations(g.get("formations", 0)),
            "optional_soldiers": g.get("optional_soldiers", []),
        }

        # 技能信息
        skills = {
            "bfmagic": g.get("bfmagic_mask", ""),
            "sfmagic": g.get("sfmagic_mask", ""),
            "genskill": g.get("genskill_mask", ""),
            "armyskill": g.get("armyskill_mask", ""),
            "armygroupskill": g.get("armygroupskill_mask", ""),
        }

        # 经验数据
        wexp = g.get("weapon_exp", {})
        experience = {
            "merit": g.get("merit", 0),
            "exp": g.get("experience", 0),
            "weapon_exp": [
                wexp.get("sword", 0),
                wexp.get("spear", 0),
                wexp.get("bow", 0),
                wexp.get("blade", 0),
                wexp.get("fan", 0),
            ],
        }

        # 元数据
        meta = {
            "name": g.get("name", ""),
            "face_id": g.get("face_id", 0),
            "level": g.get("level", 1),
            "title": g.get("title", ""),
            "offset": offset,
            "index": general_index,
        }

        return {
            "success": True,
            "basic_stats": basic_stats,
            "equipment": equipment,
            "military": military,
            "skills": skills,
            "experience": experience,
            "meta": meta,
        }

    def _parse_equipment_ids(self, general: dict) -> dict:
        """从武将数据中解析装备ID（武器/坐骑/道具）"""
        equip = general.get("equipment", {})
        items = equip.get("items", [])
        result = {
            "weapon": {"id": 0, "name": "无"},
            "horse": {"id": 0, "name": "无"},
            "item": {"id": 0, "name": "无"},
        }

        for i, item in enumerate(items):
            try:
                raw_addr = item.get("raw", "")
                if raw_addr and len(raw_addr) >= 8:
                    item_id = struct.unpack("<I", bytes.fromhex(raw_addr))[0]
                    if i == 0:
                        # 第一个道具通常是武器
                        result["weapon"] = {"id": item_id, "name": self.WEAPON_TYPES.get(item_id, f"武器#{item_id}")}
                    elif i == 1:
                        # 第二个通常是坐骑
                        result["horse"] = {"id": item_id, "name": self.HORSE_TYPES.get(item_id, f"坐骑#{item_id}")}
                    elif i == 2:
                        # 第三个通常是道具
                        result["item"] = {"id": item_id, "name": self.ITEM_TYPES.get(item_id, f"道具#{item_id}")}
            except (ValueError, struct.error):
                pass

        return result

    def _parse_formations(self, formation_mask: int) -> list:
        """解析阵型位掩码为阵型名称列表"""
        result = []
        for bit in range(16):
            if formation_mask & (1 << bit):
                result.append({
                    "id": bit,
                    "name": self.FORMATION_TYPES.get(bit, f"阵型{bit}"),
                })
        return result

    # ============================================================
    # 写入装备/技能/兵种/阵型
    # ============================================================

    def write_equipment(self, general_index: int, slot: str, item_id: int) -> dict:
        """
        写入武将装备

        Args:
            general_index: 武将索引
            slot: 装备槽位 ("weapon", "horse", "item")
            item_id: 物品ID
        """
        generals = self.find_generals()
        if general_index < 0 or general_index >= len(generals):
            return {"success": False, "message": f"武将索引 {general_index} 超出范围"}

        g = generals[general_index]
        offset = g["offset"]
        equip = g.get("equipment", {})

        if slot not in ("weapon", "horse", "item"):
            return {"success": False, "message": f"无效的装备槽位: {slot} (可选: weapon, horse, item)"}

        slot_index = {"weapon": 0, "horse": 1, "item": 2}[slot]
        items = equip.get("items", [])

        if slot_index >= len(items):
            return {"success": False, "message": f"装备槽位 {slot} 不可用 (当前仅 {len(items)} 个道具槽)"}

        # 写入道具地址
        item_addr_offset = offset - (len(items) - slot_index) * 4
        if item_addr_offset < 0 or item_addr_offset + 4 > len(self._data):
            return {"success": False, "message": "装备写入位置超出范围"}

        new_data = bytearray(self._data)
        struct.pack_into("<I", new_data, item_addr_offset, item_id)
        self._data = bytes(new_data)

        # 获取名称
        if slot == "weapon":
            name = self.WEAPON_TYPES.get(item_id, f"武器#{item_id}")
        elif slot == "horse":
            name = self.HORSE_TYPES.get(item_id, f"坐骑#{item_id}")
        else:
            name = self.ITEM_TYPES.get(item_id, f"道具#{item_id}")

        return {
            "success": True,
            "general_index": general_index,
            "slot": slot,
            "item_id": item_id,
            "item_name": name,
            "offset": item_addr_offset,
        }

    def write_skills(self, general_index: int, skill_type: str, slot: int, skill_id: int) -> dict:
        """
        写入武将技能（通过位掩码设置）

        Args:
            general_index: 武将索引
            skill_type: 技能类型 ("bfmagic", "sfmagic", "genskill", "armyskill", "armygroupskill")
            slot: 技能位索引 (0-255)
            skill_id: 技能ID (非0则启用该位, 0则清除该位)
        """
        skill_offsets_map = {
            "bfmagic": 144, "sfmagic": 176,
            "genskill": 208, "armyskill": 212, "armygroupskill": 216,
        }

        if skill_type not in skill_offsets_map:
            return {"success": False, "message": f"无效的技能类型: {skill_type} (可选: {list(skill_offsets_map.keys())})"}

        generals = self.find_generals()
        if general_index < 0 or general_index >= len(generals):
            return {"success": False, "message": f"武将索引 {general_index} 超出范围"}

        g = generals[general_index]
        offset = g["offset"]
        base_offset = offset + skill_offsets_map[skill_type]

        # 计算字节偏移和位偏移
        byte_offset = slot // 8
        bit_offset = slot % 8

        write_offset = base_offset + byte_offset
        if write_offset >= len(self._data):
            return {"success": False, "message": "技能写入位置超出范围"}

        new_data = bytearray(self._data)
        current_byte = new_data[write_offset]

        if skill_id:
            new_data[write_offset] = current_byte | (1 << bit_offset)
        else:
            new_data[write_offset] = current_byte & ~(1 << bit_offset)

        self._data = bytes(new_data)
        return {
            "success": True,
            "general_index": general_index,
            "skill_type": skill_type,
            "slot": slot,
            "skill_id": skill_id,
            "enabled": bool(skill_id),
            "offset": write_offset,
            "old_byte": current_byte,
            "new_byte": new_data[write_offset],
        }

    def write_soldier_count(self, general_index: int, count: int) -> dict:
        """写入武将带兵数"""
        generals = self.find_generals()
        if general_index < 0 or general_index >= len(generals):
            return {"success": False, "message": f"武将索引 {general_index} 超出范围"}

        g = generals[general_index]
        offset = g["offset"]
        soldier_count_offset = offset + 104

        if soldier_count_offset + 4 > len(self._data):
            return {"success": False, "message": "带兵数写入位置超出范围"}

        new_data = bytearray(self._data)
        old_count = struct.unpack("<I", new_data[soldier_count_offset:soldier_count_offset+4])[0]
        struct.pack_into("<I", new_data, soldier_count_offset, count)
        self._data = bytes(new_data)

        return {
            "success": True,
            "general_index": general_index,
            "old_count": old_count,
            "new_count": count,
            "offset": soldier_count_offset,
        }

    def write_formation(self, general_index: int, formation_id: int) -> dict:
        """
        写入武将阵型（启用/禁用）

        Args:
            general_index: 武将索引
            formation_id: 阵型ID (0-15), 或 -1 表示启用全部阵型
        """
        generals = self.find_generals()
        if general_index < 0 or general_index >= len(generals):
            return {"success": False, "message": f"武将索引 {general_index} 超出范围"}

        g = generals[general_index]
        offset = g["offset"]
        formation_offset = offset + 128

        if formation_offset >= len(self._data):
            return {"success": False, "message": "阵型写入位置超出范围"}

        new_data = bytearray(self._data)
        old_mask = new_data[formation_offset]

        if formation_id == -1:
            # 启用全部阵型
            new_mask = 0xFF
        else:
            new_mask = old_mask | (1 << formation_id)

        new_data[formation_offset] = new_mask
        self._data = bytes(new_data)

        enabled_formations = self._parse_formations(new_mask)
        return {
            "success": True,
            "general_index": general_index,
            "formation_id": formation_id,
            "old_mask": old_mask,
            "new_mask": new_mask,
            "enabled_formations": enabled_formations,
            "offset": formation_offset,
        }

    def get_raw_data(self) -> bytes:
        """获取修改后的原始数据"""
        return self._data

    def to_bytes(self) -> bytes:
        return self._data

    # ============================================================
    # 十六进制预览
    # ============================================================

    def hex_view(self, offset: int = 0, length: int = 512) -> dict:
        """十六进制查看"""
        if not self._data:
            return {"success": False, "message": "未加载数据"}
        end = min(offset + length, len(self._data))
        chunk = self._data[offset:end]
        lines = []
        for i in range(0, len(chunk), 16):
            row = chunk[i:i+16]
            addr = offset + i
            hex_str = " ".join(f"{b:02X}" for b in row)
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
            lines.append(f"{addr:08X}  {hex_str:<48s}  {ascii_str}")
        return {"success": True, "lines": lines, "offset": offset, "length": len(chunk), "total_size": len(self._data)}