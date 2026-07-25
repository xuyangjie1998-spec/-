"""
MOD制作向导 (v1.0)
- 提供标准MOD制作流程引导
- 预设模板：新增武将/势力/兵种/物品
- 自动处理文件关联和依赖关系
- 生成MOD制作检查清单

标准MOD制作流程:
1. 新增武将: General01.ini → DefSkill.ini → General02.ini → TermText.ini
2. 新增势力: Nation.ini → City01~10.ini → General01.ini
3. 新增兵种: Soldier.ini → BFSoldier.obd → TermText.ini
4. 新增物品: Thing.ini → CitySellItem.ini → TermText.ini
"""

import os
import json
from typing import Dict, List, Any, Optional, Callable


class ModWizard:
    """
    MOD制作向导
    
    提供常见MOD制作的完整流程引导，确保不遗漏关联文件。
    """

    # 制作流程模板
    TEMPLATES = {
        "new_general": {
            "name": "新增武将",
            "description": "创建一个全新的历史武将，包括属性、特性、出生地、名称文本",
            "steps": [
                {"order": 1, "file": "General01.ini", "action": "添加武将数据", "required": True},
                {"order": 2, "file": "DefSkill.ini", "action": "设置武将特性/技能", "required": True},
                {"order": 3, "file": "General02.ini", "action": "设置出生地（10个剧本）", "required": True},
                {"order": 4, "file": "TermText.ini", "action": "注册武将姓名文本", "required": True},
                {"order": 5, "file": "Nation.ini", "action": "分配至势力（可选）", "required": False},
            ],
            "checklist": [
                "武将编号唯一且不冲突",
                "头像编号FaceID对应Shape/Face/下的SHP文件",
                "所有10个剧本出生地已设置",
                "TermText中姓名已注册",
                "OBD/中对应造型存在",
            ]
        },
        "new_nation": {
            "name": "新增势力",
            "description": "创建新的势力，包括君主、城市、友好度",
            "steps": [
                {"order": 1, "file": "General01.ini", "action": "确认君主武将已存在", "required": True},
                {"order": 2, "file": "Nation.ini", "action": "添加势力定义", "required": True},
                {"order": 3, "file": "City01~10.ini", "action": "分配城池和武将", "required": True},
                {"order": 4, "file": "TermText.ini", "action": "注册势力名称", "required": True},
            ],
            "checklist": [
                "君主武将已创建并可用",
                "势力编号唯一",
                "城池Lord字段已更新",
                "友好度设置合理",
            ]
        },
        "new_soldier": {
            "name": "新增兵种",
            "description": "创建新的兵种类型，包括属性、模型、升级路径",
            "steps": [
                {"order": 1, "file": "Soldier.ini", "action": "添加兵种数据", "required": True},
                {"order": 2, "file": "BFSoldier.obd", "action": "设置兵种战场模型", "required": True},
                {"order": 3, "file": "TermText.ini", "action": "注册兵种名称", "required": True},
                {"order": 4, "file": "Thing.ini", "action": "创建兵符物品（可选）", "required": False},
                {"order": 5, "file": "Shape003.pck", "action": "替换兵种模型图片", "required": False},
            ],
            "checklist": [
                "兵种编号不超过67上限",
                "ObjID与OBD中Sequence后两位匹配",
                "升级路径Level和Upgrade设置正确",
                "HitSol克制系数已设置",
                "模型图片已替换",
            ]
        },
        "new_item": {
            "name": "新增物品",
            "description": "创建新物品（武器/道具/坐骑/兵符）",
            "steps": [
                {"order": 1, "file": "Thing.ini", "action": "添加物品数据", "required": True},
                {"order": 2, "file": "TermText.ini", "action": "注册物品名称", "required": True},
                {"order": 3, "file": "CitySellItem.ini", "action": "添加到城池商店（可选）", "required": False},
                {"order": 4, "file": "Variable.ini", "action": "添加到蓬莱/聚宝洞府（可选）", "required": False},
            ],
            "checklist": [
                "物品编号唯一",
                "Type设置正确(1消耗品2武器3坐骑4道具)",
                "IconID对应图标存在",
                "ScriptNo和ScriptHit特殊效果正确",
                "使用等级合理",
            ]
        },
        "full_mod": {
            "name": "完整MOD制作",
            "description": "从零开始制作一个完整MOD的全流程",
            "steps": [
                {"order": 1, "file": "规划", "action": "确定MOD主题和修改范围", "required": True},
                {"order": 2, "file": "备份", "action": "备份所有原始文件", "required": True},
                {"order": 3, "file": "新增武将", "action": "按新增武将模板操作", "required": False},
                {"order": 4, "file": "新增势力", "action": "按新增势力模板操作", "required": False},
                {"order": 5, "file": "新增兵种", "action": "按新增兵种模板操作", "required": False},
                {"order": 6, "file": "修改参数", "action": "调整Variable.ini/GenLV.ini等全局参数", "required": False},
                {"order": 7, "file": "修改事件", "action": "编辑Scenario.ini剧本事件", "required": False},
                {"order": 8, "file": "测试", "action": "进入游戏测试所有修改", "required": True},
                {"order": 9, "file": "打包", "action": "导出MOD文件", "required": True},
            ],
            "checklist": [
                "所有原始文件已备份",
                "所有新增武将数据完整(5个文件)",
                "所有新增势力数据完整(4个文件)",
                "所有新增兵种数据完整(5个文件)",
                "无ID冲突",
                "所有TermText文本已注册",
                "游戏可正常启动",
                "新增内容可在游戏中正常显示",
            ]
        },
    }

    def __init__(self):
        self.active_template: Optional[str] = None
        self.progress: Dict[str, List[bool]] = {}  # 模板名 -> 步骤完成状态

    def get_templates(self) -> List[dict]:
        """获取所有可用模板"""
        return [
            {
                "id": tid,
                "name": t["name"],
                "description": t["description"],
                "step_count": len(t["steps"]),
                "required_count": sum(1 for s in t["steps"] if s["required"]),
            }
            for tid, t in self.TEMPLATES.items()
        ]

    def start_template(self, template_id: str) -> dict:
        """开始一个制作模板"""
        if template_id not in self.TEMPLATES:
            return {"success": False, "message": "未知模板"}

        template = self.TEMPLATES[template_id]
        self.active_template = template_id
        self.progress[template_id] = [False] * len(template["steps"])

        return {
            "success": True,
            "template": template["name"],
            "steps": template["steps"],
            "checklist": template["checklist"],
            "progress": self.progress[template_id],
        }

    def mark_step_complete(self, template_id: str, step_index: int) -> dict:
        """标记步骤完成"""
        if template_id not in self.progress:
            return {"success": False, "message": "模板未开始"}

        if step_index >= len(self.progress[template_id]):
            return {"success": False, "message": "步骤索引超出范围"}

        self.progress[template_id][step_index] = True

        template = self.TEMPLATES[template_id]
        completed = sum(self.progress[template_id])
        total = len(self.progress[template_id])

        return {
            "success": True,
            "completed": completed,
            "total": total,
            "pct": round(completed / total * 100),
            "all_done": completed == total,
            "all_required_done": all(
                self.progress[template_id][i]
                for i, s in enumerate(template["steps"])
                if s["required"]
            ),
        }

    def get_progress(self, template_id: str = None) -> dict:
        """获取进度"""
        tid = template_id or self.active_template
        if not tid or tid not in self.progress:
            return {"active": False}

        template = self.TEMPLATES[tid]
        completed = sum(self.progress[tid])
        total = len(self.progress[tid])

        return {
            "active": True,
            "template": template["name"],
            "completed": completed,
            "total": total,
            "pct": round(completed / total * 100) if total > 0 else 0,
            "steps": [
                {
                    **s,
                    "done": self.progress[tid][i],
                }
                for i, s in enumerate(template["steps"])
            ],
            "checklist": template["checklist"],
        }

    def get_file_dependencies(self, target_file: str) -> dict:
        """获取文件依赖关系"""
        # 定义文件关联
        dependencies = {
            "General01.ini": {
                "required": ["DefSkill.ini", "General02.ini", "TermText.ini"],
                "optional": ["Nation.ini", "Thing.ini"],
                "notes": "修改武将后必须同步更新特性和出生地"
            },
            "Soldier.ini": {
                "required": ["TermText.ini"],
                "optional": ["BFSoldier.obd", "Thing.ini"],
                "notes": "修改兵种后需同步OBD模型和兵符"
            },
            "Thing.ini": {
                "required": ["TermText.ini"],
                "optional": ["CitySellItem.ini", "Variable.ini"],
                "notes": "修改物品后需同步商店和文本"
            },
            "Nation.ini": {
                "required": ["City01.ini", "City02.ini", "City03.ini", "City04.ini", "City05.ini",
                           "City06.ini", "City07.ini", "City08.ini", "City09.ini", "City10.ini"],
                "optional": ["General01.ini"],
                "notes": "修改势力后需更新所有剧本的城池归属"
            },
        }

        return dependencies.get(target_file, {
            "required": [],
            "optional": [],
            "notes": "未找到该文件的依赖信息"
        })

    # 示例数据模板
    SAMPLES = {
        "new_general": {
            "name": "示例武将: 岳飞",
            "data": {
                "No": "1700",
                "Name": "岳飞",
                "FaceID": "1700",
                "WStr": "97",
                "Int": "92",
                "HP": "280",
                "MP": "180",
                "Morale": "95",
                "Loyal": "99",
                "Life": "5",
                "Sex": "0",
                "Weapon": "1",
                "Horse": "1",
                "Formation": "1",
                "BFSoldier": "1",
                "SuperSkill": "1",
                "IsFamous": "1",
                "AppearYear": "1140",
                "Lord": "1700",
                "IsUsed": "1",
            },
            "notes": "请根据实际游戏编号调整No和FaceID，确保不冲突"
        },
        "new_soldier": {
            "name": "示例兵种: 背嵬军",
            "data": {
                "No": "100",
                "Name": "背嵬军",
                "HP": "8",
                "ATK": "7",
                "DEF": "6",
                "Speed": "8",
                "Level": "3",
                "Type": "1",
                "IsUsed": "1",
            },
            "notes": "请确保BFSoldier.obd中有对应的兵种模型"
        },
        "new_soldier_cav": {
            "name": "骑兵模板: 铁骑",
            "data": {
                "No": "101",
                "Name": "铁骑",
                "HP": "6",
                "ATK": "9",
                "DEF": "5",
                "Speed": "10",
                "Level": "3",
                "Type": "1",
                "IsUsed": "1",
            },
            "notes": "骑兵模板: 高攻高速低防。适合冲锋陷阵"
        },
        "new_soldier_archer": {
            "name": "弓兵模板: 神射手",
            "data": {
                "No": "102",
                "Name": "神射手",
                "HP": "4",
                "ATK": "8",
                "DEF": "3",
                "Speed": "6",
                "Level": "2",
                "Type": "2",
                "IsUsed": "1",
            },
            "notes": "弓兵模板: 远程高攻低血。适合后排输出"
        },
        "new_soldier_infantry": {
            "name": "步兵模板: 重甲兵",
            "data": {
                "No": "103",
                "Name": "重甲兵",
                "HP": "10",
                "ATK": "5",
                "DEF": "9",
                "Speed": "4",
                "Level": "2",
                "Type": "1",
                "IsUsed": "1",
            },
            "notes": "步兵模板: 高血高防低速。适合前排肉盾"
        },
        "new_soldier_caster": {
            "name": "法师模板: 军师团",
            "data": {
                "No": "104",
                "Name": "军师团",
                "HP": "3",
                "ATK": "4",
                "DEF": "2",
                "Speed": "5",
                "Level": "3",
                "Type": "3",
                "IsUsed": "1",
            },
            "notes": "法师模板: 特殊兵种。适合辅助/施法"
        },
        "new_item": {
            "name": "示例物品: 沥泉枪",
            "data": {
                "No": "900",
                "Name": "沥泉枪",
                "Type": "1",
                "Price": "8000",
                "WStr": "25",
                "HP": "30",
                "Level": "30",
                "IsUsed": "1",
            },
            "notes": "物品编号范围通常为 1-999"
        },
        "new_nation": {
            "name": "示例势力: 大宋",
            "data": {
                "No": "20",
                "Name": "大宋",
                "Color": "5",
                "Lord": "1700",
                "IsUsed": "1",
            },
            "notes": "创建势力后需更新所有10个剧本的City.ini城池归属"
        },
    }

    def get_sample(self, template_id: str) -> dict:
        """获取模板的示例数据"""
        return self.SAMPLES.get(template_id, {"name": "无示例", "data": {}})