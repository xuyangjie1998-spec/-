"""
History.ini 剧情事件模板引擎
基于社区"常用剧情模板.xls"的8种ClassType定义
"""

EVENT_TEMPLATES = {
    "3": {
        "name": "事件建物（物）",
        "description": "攻略特殊地点获得物品",
        "fields": {
            "LordA": "君主A编号",
            "LordALv": "君主A等级条件",
            "LordB": "君主B编号",
            "LordBLv": "君主B等级条件",
            "S_ProposeGeneral": "触发武将",
            "S_ProposeString": "触发对话",
            "data01": "目标城池编号",
            "data02": "获得物品编号",
            "data03": "物品数量",
            "S_General01": "对话武将1",
            "S_StringA01": "武将1发言",
            "S_StringD01": "对话显示文本1",
        }
    },
    "5": {
        "name": "发现宝物（臣）",
        "description": "武将特定城池/等级触发获得物品",
        "fields": {
            "LordA": "君主A编号",
            "S_ProposeGeneral": "触发武将",
            "S_ProposeString": "触发对话",
            "data01": "目标城池编号",
            "data02": "获得物品编号",
            "data03": "物品数量",
            "S_MinGenLv": "最低等级要求",
            "S_General01": "对话武将",
            "S_StringA01": "武将发言",
            "S_StringD01": "对话显示文本",
        }
    },
    "20": {
        "name": "武将强化",
        "description": "多个武将对话获得强化",
        "fields": {
            "LordA": "君主A编号",
            "S_ProposeGeneral": "触发武将",
            "S_ProposeString": "触发对话",
            "data01": "目标城池编号",
            "S_General01": "对话武将1",
            "S_General02": "对话武将2",
            "S_General03": "对话武将3",
            "S_StringA01": "武将1发言",
            "S_StringA02": "武将2发言",
            "S_StringA03": "武将3发言",
            "data10": "强化武力值",
            "data11": "强化智力值",
            "data12": "强化体力值",
            "data13": "强化技力值",
        }
    },
    "33": {
        "name": "武将死亡",
        "description": "君主、城池条件触发武将死亡",
        "fields": {
            "LordA": "君主A编号",
            "LordALv": "君主A等级条件",
            "S_ProposeGeneral": "触发武将",
            "S_ProposeString": "触发对话",
            "data01": "目标城池编号",
            "data02": "死亡武将编号",
            "S_General01": "对话武将",
            "S_StringA01": "对话内容",
            "S_StringD01": "显示文本",
        }
    },
    "34": {
        "name": "建物损毁",
        "description": "君主、洛阳条件触发建物损毁",
        "fields": {
            "LordA": "君主A编号",
            "S_ProposeGeneral": "触发武将",
            "S_ProposeString": "触发对话",
            "data01": "洛阳城池编号",
            "data02": "损毁建筑编号",
            "S_General01": "对话武将",
            "S_StringA01": "对话内容",
        }
    },
    "37": {
        "name": "事件强化",
        "description": "至少占领城池数、民心等条件触发",
        "fields": {
            "LordA": "君主A编号",
            "S_ProposeGeneral": "触发武将",
            "S_ProposeString": "触发对话",
            "data01": "至少占领城池数",
            "data02": "民心条件",
            "data03": "强化武力值",
            "data04": "强化智力值",
            "data05": "强化体力值",
            "data06": "强化技力值",
            "S_General01": "对话武将",
            "S_StringA01": "对话内容",
        }
    },
    "38": {
        "name": "女将登场",
        "description": "曹操/特定武将登场事件",
        "fields": {
            "LordA": "君主A编号（曹操）",
            "S_ProposeGeneral": "触发武将",
            "S_ProposeString": "触发对话",
            "data01": "目标城池编号",
            "data02": "登场武将编号",
            "S_General01": "对话武将1",
            "S_General02": "对话武将2",
            "S_StringA01": "武将1发言",
            "S_StringA02": "武将2发言",
        }
    },
    "40": {
        "name": "三顾茅庐",
        "description": "君主所在地、人物A/B/C对话",
        "fields": {
            "LordA": "君主A编号",
            "LordALv": "君主A等级条件",
            "S_ProposeGeneral": "触发武将",
            "S_ProposeString": "触发对话",
            "data01": "目标城池编号",
            "S_General01": "诸葛武将编号",
            "S_General02": "对话武将B",
            "S_General03": "对话武将C",
            "S_StringA01": "诸葛发言",
            "S_StringA02": "武将B发言",
            "S_StringA03": "武将C发言",
            "S_StringD01": "显示文本1",
            "S_StringD02": "显示文本2",
            "S_StringD03": "显示文本3",
        }
    },
}


def generate_event_section(class_type: str, params: dict) -> str:
    """根据模板和参数生成 History.ini 的一个 section 字符串"""
    template = EVENT_TEMPLATES.get(class_type)
    if not template:
        return "; Error: 未知的 ClassType: " + class_type

    lines = ["[HISTORY]"]
    lines.append("No = " + str(params.get("No", "0")))
    lines.append("ClassType = " + class_type)
    lines.append("Priority = " + str(params.get("Priority", "0")))
    lines.append("Age = " + str(params.get("Age", "1")))
    lines.append("S_Year = " + str(params.get("S_Year", "-1")))
    lines.append("S_Season = " + str(params.get("S_Season", "-1")))
    lines.append("E_Year = " + str(params.get("E_Year", "-1")))
    lines.append("E_Season = " + str(params.get("E_Season", "-1")))
    lines.append("PreHistory = " + str(params.get("PreHistory", "0")))
    lines.append("NedHistory01 = " + str(params.get("NedHistory01", "0")))
    lines.append("NedHistory02 = " + str(params.get("NedHistory02", "0")))
    lines.append("NedHistory03 = " + str(params.get("NedHistory03", "0")))
    lines.append("Pic = " + str(params.get("Pic", "0")))
    lines.append("IsUsed = " + str(params.get("IsUsed", "1")))
    lines.append("Version = " + str(params.get("Version", "1")))

    # 写入模板定义的字段
    for field_name in template["fields"]:
        value = params.get(field_name, "0")
        lines.append(f"{field_name} = {value}")

    lines.append("")
    return "\n".join(lines)