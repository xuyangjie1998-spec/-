"""
特效知识库 - 三国群英传7 特效编辑参考数据
提供弹道类型、伤害类型、物品特效、武器发光等参考信息
"""


class EffectCatalog:
    """特效知识库，提供特效编辑所需的参考数据"""

    # ============================================================
    # 弹道类型 (Ball) - BFMagic.ini
    # ============================================================
    BALL_TYPES = [
        {"id": 0, "name": "默认/无弹道", "desc": "无特殊弹道，直接命中", "visual": "●", "color": "#888"},
        {"id": 1, "name": "直射弹道", "desc": "直线飞行弹道，如火箭", "visual": "→", "color": "#ff4444"},
        {"id": 2, "name": "弧形弹道", "desc": "抛物线弹道，如炬石", "visual": "⌒", "color": "#ff8800"},
        {"id": 3, "name": "散射弹道", "desc": "扇形散射，如连弩", "visual": "⋘", "color": "#44aaff"},
        {"id": 4, "name": "追踪弹道", "desc": "追踪目标，如神鸢", "visual": "↷", "color": "#ff44ff"},
        {"id": 5, "name": "范围落雷", "desc": "从天而降范围攻击，如雷击", "visual": "⚡", "color": "#ffff00"},
        {"id": 6, "name": "地面冲击", "desc": "地面冲击波，如大地狂啸", "visual": "≈", "color": "#aa8844"},
        {"id": 7, "name": "旋转攻击", "desc": "旋转类攻击，如旋灯", "visual": "◎", "color": "#ff6644"},
        {"id": 8, "name": "召唤弹道", "desc": "召唤物弹道，如尸兵", "visual": "◆", "color": "#8844ff"},
        {"id": 9, "name": "持续光束", "desc": "持续光束攻击，如激光", "visual": "━", "color": "#44ffff"},
        {"id": 10, "name": "爆炸弹道", "desc": "爆炸类弹道，如火球爆", "visual": "✱", "color": "#ff0000"},
        {"id": 11, "name": "穿透弹道", "desc": "穿透直线攻击，如贯穿", "visual": "⇨", "color": "#ffaa00"},
        {"id": 12, "name": "冰锥弹道", "desc": "冰系弹道，如冻血刀", "visual": "❄", "color": "#88ccff"},
        {"id": 13, "name": "旋风弹道", "desc": "旋风类弹道，如龙卷", "visual": "🌀", "color": "#aaffaa"},
        {"id": 14, "name": "毒雾弹道", "desc": "毒雾扩散，如毒烟", "visual": "☠", "color": "#88ff44"},
        {"id": 15, "name": "治疗弹道", "desc": "治疗类弹道，如回天", "visual": "✚", "color": "#44ff44"},
    ]

    # ============================================================
    # 伤害类型 (DamageType) - BFMagic.ini
    # ============================================================
    DAMAGE_TYPES = [
        {"id": 0, "name": "物理伤害", "desc": "普通物理攻击伤害", "icon": "⚔"},
        {"id": 1, "name": "火属性伤害", "desc": "火焰属性伤害，受火抗影响", "icon": "🔥"},
        {"id": 2, "name": "水属性伤害", "desc": "冰水属性伤害，受水抗影响", "icon": "💧"},
        {"id": 3, "name": "风属性伤害", "desc": "风属性伤害，受风抗影响", "icon": "🌪"},
        {"id": 4, "name": "雷属性伤害", "desc": "雷电属性伤害，受雷抗影响", "icon": "⚡"},
        {"id": 5, "name": "毒属性伤害", "desc": "毒素伤害，受毒抗影响", "icon": "☠"},
        {"id": 6, "name": "真实伤害", "desc": "无视防御的固定伤害", "icon": "💀"},
        {"id": 7, "name": "百分比伤害", "desc": "按目标生命百分比扣血", "icon": "📊"},
        {"id": 8, "name": "治疗", "desc": "恢复生命值", "icon": "💚"},
    ]

    # ============================================================
    # 属性类型 (Element) - 技能视觉效果
    # ============================================================
    ELEMENT_TYPES = [
        {"id": 0, "name": "无属性", "desc": "无特殊属性效果", "visual": "○", "color": "#888"},
        {"id": 1, "name": "火", "desc": "火焰视觉效果，红色粒子", "visual": "🔥", "color": "#ff4444"},
        {"id": 2, "name": "水/冰", "desc": "冰水视觉效果，蓝色粒子", "visual": "❄", "color": "#4488ff"},
        {"id": 3, "name": "风", "desc": "旋风视觉效果，绿色粒子", "visual": "🌀", "color": "#44ff44"},
        {"id": 4, "name": "雷", "desc": "雷电视觉效果，黄色粒子", "visual": "⚡", "color": "#ffdd00"},
        {"id": 5, "name": "毒", "desc": "毒雾视觉效果，紫色粒子", "visual": "☠", "color": "#aa44ff"},
    ]

    # ============================================================
    # 物品特效代码 (ScriptNo) - Thing.ini
    # ============================================================
    ITEM_SCRIPTS = [
        {"id": 0, "name": "无特效", "desc": "普通攻击，无特殊效果", "weapon_example": "普通武器"},
        {"id": 1, "name": "剑气", "desc": "远程剑气攻击，范围伤害", "weapon_example": "苍天帝剑"},
        {"id": 2, "name": "刀罡", "desc": "大范围刀气斩击", "weapon_example": "神鬼方天戟"},
        {"id": 3, "name": "贯穿", "desc": "直线贯穿攻击，可穿透多人", "weapon_example": "丈八蛇矛"},
        {"id": 4, "name": "横扫", "desc": "扇形横扫攻击，前方范围", "weapon_example": "青龙偃月刀"},
        {"id": 5, "name": "三连击", "desc": "连续三次快速攻击", "weapon_example": "双股剑"},
        {"id": 6, "name": "吸血", "desc": "攻击时吸取生命值", "weapon_example": "噬血魔剑"},
        {"id": 7, "name": "击退", "desc": "攻击附带击退效果", "weapon_example": "铁脊蛇矛"},
        {"id": 8, "name": "眩晕", "desc": "攻击附带眩晕效果", "weapon_example": "流星锤"},
        {"id": 9, "name": "中毒", "desc": "攻击附带中毒持续伤害", "weapon_example": "毒龙戟"},
        {"id": 10, "name": "冰冻", "desc": "攻击附带冰冻减速效果", "weapon_example": "寒冰剑"},
        {"id": 11, "name": "灼烧", "desc": "攻击附带灼烧持续伤害", "weapon_example": "朱雀羽扇"},
        {"id": 12, "name": "雷电", "desc": "攻击附带雷电麻痹效果", "weapon_example": "雷神锤"},
        {"id": 13, "name": "分裂", "desc": "攻击命中后分裂攻击附近敌人", "weapon_example": "方天画戟"},
        {"id": 14, "name": "溅射", "desc": "攻击造成溅射范围伤害", "weapon_example": "巨斧"},
        {"id": 15, "name": "破甲", "desc": "无视目标部分防御", "weapon_example": "破阵刀"},
        {"id": 16, "name": "回血", "desc": "击杀敌人恢复生命", "weapon_example": "倚天剑"},
        {"id": 17, "name": "特殊效果(通用)", "desc": "调用特殊效果代码", "weapon_example": "—"},
        {"id": 18, "name": "贯穿刺击(4人)", "desc": "霸王凤凰枪贯穿四人刺击", "weapon_example": "霸王凤凰枪"},
        {"id": 19, "name": "大范围挥斩", "desc": "大范围挥斩特效", "weapon_example": "神鬼方天戟"},
        {"id": 20, "name": "召唤", "desc": "攻击时召唤士兵", "weapon_example": "召唤类武器"},
    ]

    # ============================================================
    # 武器发光配置 (BFWLight.obd)
    # ============================================================
    WEAPON_GLOW_INFO = {
        "desc": "武器发光需要同时修改 Thing.ini 的 BFWResID 和 BFWLight.obd 文件",
        "steps": [
            "1. 在 Thing.ini 中找到目标武器，修改 BFWResID 字段（对应 BFWLight.obd 中的编号）",
            "2. 在 OBD 编辑器中选择 BFWeaponLight 类型，找到对应编号的发光模型",
            "3. 修改发光的颜色、大小、动画效果",
            "4. 保存两个文件即可生效",
        ],
        "known_glow_count": 38,
        "note": "游戏原版有 38 把发光武器，可通过修改 BFWLight.obd 自定义更多",
    }

    # ============================================================
    # 攻击类型 (Atk) - BFMagic.ini
    # ============================================================
    ATK_TYPES = [
        {"id": 0, "name": "单体攻击", "desc": "对单个目标造成伤害"},
        {"id": 1, "name": "群体攻击", "desc": "对范围内多个目标造成伤害"},
        {"id": 2, "name": "全军攻击", "desc": "对敌方全体造成伤害"},
        {"id": 3, "name": "持续伤害", "desc": "持续多回合造成伤害"},
        {"id": 4, "name": "治疗恢复", "desc": "恢复己方生命/技力"},
        {"id": 5, "name": "增益效果", "desc": "提升己方属性"},
        {"id": 6, "name": "减益效果", "desc": "降低敌方属性"},
        {"id": 7, "name": "召唤", "desc": "召唤士兵/召唤物"},
        {"id": 8, "name": "控制效果", "desc": "眩晕/冰冻/击退等控制"},
    ]

    def get_ball_types(self) -> dict:
        return {"success": True, "data": self.BALL_TYPES, "count": len(self.BALL_TYPES)}

    def get_damage_types(self) -> dict:
        return {"success": True, "data": self.DAMAGE_TYPES, "count": len(self.DAMAGE_TYPES)}

    def get_element_types(self) -> dict:
        return {"success": True, "data": self.ELEMENT_TYPES, "count": len(self.ELEMENT_TYPES)}

    def get_item_scripts(self) -> dict:
        return {"success": True, "data": self.ITEM_SCRIPTS, "count": len(self.ITEM_SCRIPTS)}

    def get_weapon_glow_info(self) -> dict:
        return {"success": True, "data": self.WEAPON_GLOW_INFO}

    def get_atk_types(self) -> dict:
        return {"success": True, "data": self.ATK_TYPES, "count": len(self.ATK_TYPES)}

    def get_all_catalogs(self) -> dict:
        """获取全部特效知识库数据"""
        return {
            "success": True,
            "ball_types": self.BALL_TYPES,
            "damage_types": self.DAMAGE_TYPES,
            "element_types": self.ELEMENT_TYPES,
            "item_scripts": self.ITEM_SCRIPTS,
            "weapon_glow": self.WEAPON_GLOW_INFO,
            "atk_types": self.ATK_TYPES,
        }