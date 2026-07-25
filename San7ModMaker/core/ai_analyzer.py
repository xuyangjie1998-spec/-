"""
游戏AI行为分析器 (Game AI Behavior Analyzer)
提供AI决策树分析、行为模式识别、策略修改、概率建模、战斗AI/内政AI分析等功能。

引擎突破 10: 深度分析三国群英传7的AI行为系统，支持决策树逆向、策略修改、行为模拟
"""

import json
import math
import os
import struct
from typing import Dict, List, Optional, Tuple, Set, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict, Counter


# ============================================================
# 枚举定义
# ============================================================

class AIStrategy(Enum):
    """AI策略类型"""
    AGGRESSIVE = "aggressive"        # 攻击型
    DEFENSIVE = "defensive"          # 防守型
    BALANCED = "balanced"            # 平衡型
    EXPANSIONIST = "expansionist"    # 扩张型
    TURTLE = "turtle"                # 龟缩型
    DIPLOMATIC = "diplomatic"        # 外交型
    ECONOMIC = "economic"            # 经济型
    OPPORTUNISTIC = "opportunistic"  # 机会型
    CUSTOM = "custom"                # 自定义


class AIDecisionType(Enum):
    """AI决策类型"""
    ATTACK_CITY = "attack_city"           # 攻城
    DEFEND_CITY = "defend_city"           # 守城
    RECRUIT = "recruit"                   # 征兵
    DEVELOP = "develop"                   # 开发
    DIPLOMACY = "diplomacy"               # 外交
    RESEARCH = "research"                 # 研究
    MOVE_TROOPS = "move_troops"           # 调动
    USE_ITEM = "use_item"                 # 使用物品
    APPOINT_OFFICER = "appoint_officer"   # 任命
    FORM_ALLIANCE = "form_alliance"       # 结盟
    DECLARE_WAR = "declare_war"           # 宣战
    SURRENDER = "surrender"               # 投降
    BATTLE_TACTIC = "battle_tactic"       # 战斗策略
    RETREAT = "retreat"                   # 撤退
    SKILL_USE = "skill_use"               # 技能使用
    ECONOMIC = "economic"                 # 经济建设
    EXPANSION = "expansion"               # 扩张


class AIEventType(Enum):
    """AI触发事件类型"""
    ENEMY_NEARBY = "enemy_nearby"         # 敌军接近
    LOW_HP = "low_hp"                     # 低血量
    LOW_MP = "low_mp"                     # 低技力
    ALLY_NEED_HELP = "ally_need_help"     # 盟友求援
    RESOURCE_LOW = "resource_low"         # 资源不足
    RESOURCE_HIGH = "resource_high"       # 资源充足
    ENEMY_WEAK = "enemy_weak"             # 敌军虚弱
    ENEMY_STRONG = "enemy_strong"         # 敌军强大
    TURN_START = "turn_start"             # 回合开始
    TURN_END = "turn_end"                 # 回合结束
    WAR_START = "war_start"               # 战争开始
    PEACE_TIME = "peace_time"             # 和平时期
    CRITICAL_CITY = "critical_city"       # 关键城池
    SEASON_CHANGE = "season_change"       # 季节变化


class AIActionType(Enum):
    """AI动作类型"""
    ATTACK = "attack"                     # 攻击
    DEFEND = "defend"                     # 防守
    RETREAT = "retreat"                   # 撤退
    USE_SKILL = "use_skill"               # 使用技能
    USE_ITEM = "use_item"                 # 使用物品
    WAIT = "wait"                         # 等待
    MOVE = "move"                         # 移动
    CHARGE = "charge"                     # 冲锋
    FLANK = "flank"                       # 侧翼
    SUPPORT = "support"                   # 支援
    HEAL = "heal"                         # 治疗


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class AIDecision:
    """AI决策"""
    decision_id: str
    decision_type: AIDecisionType
    name: str = ""
    priority: float = 0.5
    weight: float = 1.0
    conditions: List[dict] = field(default_factory=list)
    actions: List[dict] = field(default_factory=list)
    probability: float = 1.0
    cooldown: int = 0
    description: str = ""


@dataclass
class AIBehavior:
    """AI行为模式"""
    behavior_id: str
    name: str
    event: AIEventType = None
    action: AIActionType = None
    conditions: List[dict] = field(default_factory=list)
    probability: float = 1.0
    priority: int = 50
    repeatable: bool = True
    cooldown_turns: int = 0


@dataclass
class AIDecisionNode:
    """AI决策树节点"""
    node_id: str
    node_type: str  # "condition", "action", "selector", "sequence", "probability"
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    condition: Optional[dict] = None
    action: Optional[dict] = None
    weight: float = 1.0
    probability: float = 1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class AIDecisionTree:
    """AI决策树"""
    tree_id: str
    name: str
    description: str = ""
    root_node_id: Optional[str] = None
    nodes: Dict[str, AIDecisionNode] = field(default_factory=dict)
    version: str = "1.0"


@dataclass
class AIProfile:
    """AI角色配置"""
    profile_id: str
    name: str
    strategy: AIStrategy = AIStrategy.BALANCED
    aggression: float = 0.5
    defense: float = 0.5
    economy: float = 0.5
    diplomacy: float = 0.5
    expansion: float = 0.5
    risk_tolerance: float = 0.5
    decision_trees: List[str] = field(default_factory=list)
    behavior_patterns: List[str] = field(default_factory=list)
    personality_traits: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class AIState:
    """AI状态快照"""
    state_id: str
    timestamp: float = 0.0
    hp_ratio: float = 1.0
    mp_ratio: float = 1.0
    soldier_ratio: float = 1.0
    morale: int = 100
    position: Tuple[int, int] = (0, 0)
    enemies_nearby: int = 0
    allies_nearby: int = 0
    current_action: Optional[AIActionType] = None
    target_id: Optional[str] = None
    flags: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AISimulationResult:
    """AI行为模拟结果"""
    simulation_id: str
    profile: AIProfile = None
    decisions_made: List[AIDecision] = field(default_factory=list)
    actions_taken: List[AIActionType] = field(default_factory=list)
    state_history: List[AIState] = field(default_factory=list)
    outcome: str = "unknown"
    score: float = 0.0
    turns: int = 0


# ============================================================
# AI决策树构建器
# ============================================================

class AIDecisionTreeBuilder:
    """AI决策树构建器"""

    def __init__(self):
        self._trees: Dict[str, AIDecisionTree] = {}
        self._node_counter = 0

    def create_tree(self, tree_id: str, name: str, description: str = "") -> AIDecisionTree:
        """创建决策树"""
        tree = AIDecisionTree(tree_id=tree_id, name=name, description=description)
        self._trees[tree_id] = tree
        return tree

    def add_node(self, tree_id: str, node_type: str, parent_id: str = None,
                 condition: dict = None, action: dict = None,
                 weight: float = 1.0, probability: float = 1.0,
                 metadata: dict = None) -> AIDecisionNode:
        """添加节点"""
        tree = self._trees.get(tree_id)
        if not tree:
            raise ValueError(f"决策树不存在: {tree_id}")

        node_id = f"{tree_id}_node_{self._node_counter}"
        self._node_counter += 1

        node = AIDecisionNode(
            node_id=node_id,
            node_type=node_type,
            parent_id=parent_id,
            condition=condition,
            action=action,
            weight=weight,
            probability=probability,
            metadata=metadata or {}
        )

        tree.nodes[node_id] = node

        if parent_id:
            parent = tree.nodes.get(parent_id)
            if parent:
                parent.children.append(node_id)

        if tree.root_node_id is None:
            tree.root_node_id = node_id

        return node

    def add_condition_node(self, tree_id: str, parent_id: str, condition: dict,
                           true_child: dict = None, false_child: dict = None,
                           weight: float = 1.0) -> AIDecisionNode:
        """添加条件节点，自动创建 true/false 子节点"""
        cond_node = self.add_node(
            tree_id, "condition", parent_id, condition=condition, weight=weight
        )
        return cond_node

    def add_action_node(self, tree_id: str, parent_id: str, action: dict,
                        weight: float = 1.0) -> AIDecisionNode:
        """添加动作节点"""
        return self.add_node(tree_id, "action", parent_id, action=action, weight=weight)

    def add_probability_node(self, tree_id: str, parent_id: str,
                             probability: float = 0.5, weight: float = 1.0) -> AIDecisionNode:
        """添加概率节点"""
        return self.add_node(
            tree_id, "probability", parent_id, probability=probability, weight=weight
        )

    def add_selector_node(self, tree_id: str, parent_id: str,
                          weight: float = 1.0) -> AIDecisionNode:
        """添加选择器节点（子节点中选最佳）"""
        return self.add_node(tree_id, "selector", parent_id, weight=weight)

    def add_sequence_node(self, tree_id: str, parent_id: str,
                          weight: float = 1.0) -> AIDecisionNode:
        """添加序列节点（子节点全部执行）"""
        return self.add_node(tree_id, "sequence", parent_id, weight=weight)

    def get_tree(self, tree_id: str) -> Optional[AIDecisionTree]:
        """获取决策树"""
        return self._trees.get(tree_id)

    def list_trees(self) -> List[dict]:
        """列出所有决策树"""
        return [
            {
                "tree_id": t.tree_id,
                "name": t.name,
                "description": t.description,
                "node_count": len(t.nodes),
                "version": t.version
            }
            for t in self._trees.values()
        ]

    def export_tree(self, tree_id: str) -> dict:
        """导出决策树为字典"""
        tree = self._trees.get(tree_id)
        if not tree:
            return {"success": False, "message": f"决策树不存在: {tree_id}"}

        nodes_data = {}
        for nid, node in tree.nodes.items():
            nodes_data[nid] = {
                "node_id": node.node_id,
                "node_type": node.node_type,
                "parent_id": node.parent_id,
                "children": node.children,
                "condition": node.condition,
                "action": node.action,
                "weight": node.weight,
                "probability": node.probability,
                "metadata": node.metadata
            }

        return {
            "success": True,
            "tree_id": tree.tree_id,
            "name": tree.name,
            "description": tree.description,
            "root_node_id": tree.root_node_id,
            "nodes": nodes_data,
            "version": tree.version
        }

    def import_tree(self, data: dict) -> dict:
        """从字典导入决策树"""
        try:
            tree = AIDecisionTree(
                tree_id=data["tree_id"],
                name=data["name"],
                description=data.get("description", ""),
                root_node_id=data.get("root_node_id"),
                version=data.get("version", "1.0")
            )

            for nid, ndata in data.get("nodes", {}).items():
                node = AIDecisionNode(
                    node_id=ndata["node_id"],
                    node_type=ndata["node_type"],
                    parent_id=ndata.get("parent_id"),
                    children=ndata.get("children", []),
                    condition=ndata.get("condition"),
                    action=ndata.get("action"),
                    weight=ndata.get("weight", 1.0),
                    probability=ndata.get("probability", 1.0),
                    metadata=ndata.get("metadata", {})
                )
                tree.nodes[nid] = node

            self._trees[tree.tree_id] = tree
            return {"success": True, "message": f"导入成功: {tree.name}", "tree_id": tree.tree_id}
        except Exception as e:
            return {"success": False, "message": f"导入失败: {str(e)}"}


# ============================================================
# AI行为模式识别器
# ============================================================

class AIBehaviorAnalyzer:
    """AI行为模式分析器"""

    # 已知的AI行为模式库
    KNOWN_PATTERNS = {
        "rush_attack": {
            "name": "闪电突袭",
            "event": "enemy_nearby",
            "conditions": [
                {"type": "hp_ratio", "operator": ">=", "value": 0.7},
                {"type": "soldier_ratio", "operator": ">=", "value": 0.6},
                {"type": "enemy_hp_ratio", "operator": "<", "value": 0.5},
            ],
            "action": "charge",
            "priority": 80,
            "probability": 0.8
        },
        "defensive_hold": {
            "name": "坚守阵地",
            "event": "enemy_nearby",
            "conditions": [
                {"type": "hp_ratio", "operator": "<", "value": 0.5},
                {"type": "allies_nearby", "operator": ">=", "value": 1},
            ],
            "action": "defend",
            "priority": 70,
            "probability": 0.9
        },
        "tactical_retreat": {
            "name": "战术撤退",
            "event": "low_hp",
            "conditions": [
                {"type": "hp_ratio", "operator": "<", "value": 0.2},
                {"type": "soldier_ratio", "operator": "<", "value": 0.3},
            ],
            "action": "retreat",
            "priority": 90,
            "probability": 0.95
        },
        "skill_burst": {
            "name": "技能爆发",
            "event": "enemy_nearby",
            "conditions": [
                {"type": "mp_ratio", "operator": ">=", "value": 0.5},
                {"type": "enemy_str", "operator": ">=", "value": 70},
            ],
            "action": "use_skill",
            "priority": 75,
            "probability": 0.7
        },
        "heal_priority": {
            "name": "优先治疗",
            "event": "low_hp",
            "conditions": [
                {"type": "hp_ratio", "operator": "<", "value": 0.4},
                {"type": "mp_ratio", "operator": ">=", "value": 0.3},
                {"type": "has_heal_skill", "operator": "==", "value": True},
            ],
            "action": "heal",
            "priority": 85,
            "probability": 0.9
        },
        "flank_maneuver": {
            "name": "侧翼包抄",
            "event": "enemy_nearby",
            "conditions": [
                {"type": "allies_nearby", "operator": ">=", "value": 2},
                {"type": "enemy_nearby", "operator": "==", "value": 1},
            ],
            "action": "flank",
            "priority": 65,
            "probability": 0.6
        },
        "support_ally": {
            "name": "支援友军",
            "event": "ally_need_help",
            "conditions": [
                {"type": "hp_ratio", "operator": ">=", "value": 0.6},
                {"type": "ally_hp_ratio", "operator": "<", "value": 0.3},
            ],
            "action": "support",
            "priority": 80,
            "probability": 0.75
        },
        "item_emergency": {
            "name": "紧急用药",
            "event": "low_hp",
            "conditions": [
                {"type": "hp_ratio", "operator": "<", "value": 0.15},
                {"type": "has_heal_item", "operator": "==", "value": True},
            ],
            "action": "use_item",
            "priority": 95,
            "probability": 0.98
        },
    }

    def __init__(self):
        self._behavior_patterns: Dict[str, AIBehavior] = {}
        self._load_known_patterns()

    def _load_known_patterns(self):
        """加载内置行为模式"""
        for pid, pdata in self.KNOWN_PATTERNS.items():
            event = None
            for e in AIEventType:
                if e.value == pdata.get("event"):
                    event = e
                    break

            action = None
            for a in AIActionType:
                if a.value == pdata.get("action"):
                    action = a
                    break

            behavior = AIBehavior(
                behavior_id=pid,
                name=pdata["name"],
                event=event,
                action=action,
                conditions=pdata["conditions"],
                probability=pdata["probability"],
                priority=pdata["priority"],
            )
            self._behavior_patterns[pid] = behavior

    def add_pattern(self, behavior_id: str, name: str, event: AIEventType,
                    action: AIActionType, conditions: List[dict],
                    probability: float = 1.0, priority: int = 50,
                    repeatable: bool = True, cooldown_turns: int = 0) -> dict:
        """添加行为模式"""
        behavior = AIBehavior(
            behavior_id=behavior_id,
            name=name,
            event=event,
            action=action,
            conditions=conditions,
            probability=probability,
            priority=priority,
            repeatable=repeatable,
            cooldown_turns=cooldown_turns
        )
        self._behavior_patterns[behavior_id] = behavior
        return {"success": True, "message": f"行为模式添加成功: {name}", "behavior_id": behavior_id}

    def match_patterns(self, state: AIState, event: AIEventType) -> List[dict]:
        """匹配当前状态下的行为模式"""
        matched = []

        for pid, behavior in self._behavior_patterns.items():
            if behavior.event != event:
                continue

            if not self._check_conditions(state, behavior.conditions):
                continue

            if not self._roll_probability(behavior.probability):
                continue

            matched.append({
                "behavior_id": behavior.behavior_id,
                "name": behavior.name,
                "action": behavior.action.value if behavior.action else None,
                "priority": behavior.priority,
                "probability": behavior.probability,
                "repeatable": behavior.repeatable,
                "cooldown_turns": behavior.cooldown_turns
            })

        # 按优先级排序
        matched.sort(key=lambda x: x["priority"], reverse=True)
        return matched

    def _check_conditions(self, state: AIState, conditions: List[dict]) -> bool:
        """检查条件是否满足"""
        state_dict = {
            "hp_ratio": state.hp_ratio,
            "mp_ratio": state.mp_ratio,
            "soldier_ratio": state.soldier_ratio,
            "morale": state.morale,
            "enemies_nearby": state.enemies_nearby,
            "allies_nearby": state.allies_nearby,
        }
        # 合并 flags
        state_dict.update(state.flags)

        for cond in conditions:
            cond_type = cond.get("type", "")
            operator = cond.get("operator", "==")
            value = cond.get("value")
            actual = state_dict.get(cond_type)

            if actual is None:
                return False

            if not self._evaluate_condition(actual, operator, value):
                return False

        return True

    def _evaluate_condition(self, actual, operator: str, value) -> bool:
        """评估单个条件"""
        if operator == "==":
            return actual == value
        elif operator == "!=":
            return actual != value
        elif operator == ">":
            return actual > value
        elif operator == ">=":
            return actual >= value
        elif operator == "<":
            return actual < value
        elif operator == "<=":
            return actual <= value
        elif operator == "in":
            return actual in value
        elif operator == "not_in":
            return actual not in value
        return False

    def _roll_probability(self, probability: float) -> bool:
        """概率判定"""
        import random
        return random.random() < probability

    def list_patterns(self) -> List[dict]:
        """列出所有行为模式"""
        return [
            {
                "behavior_id": b.behavior_id,
                "name": b.name,
                "event": b.event.value if b.event else None,
                "action": b.action.value if b.action else None,
                "condition_count": len(b.conditions),
                "probability": b.probability,
                "priority": b.priority
            }
            for b in self._behavior_patterns.values()
        ]

    def remove_pattern(self, behavior_id: str) -> dict:
        """移除行为模式"""
        if behavior_id in self._behavior_patterns:
            name = self._behavior_patterns[behavior_id].name
            del self._behavior_patterns[behavior_id]
            return {"success": True, "message": f"已移除: {name}"}
        return {"success": False, "message": f"行为模式不存在: {behavior_id}"}

    def get_pattern(self, behavior_id: str) -> Optional[dict]:
        """获取行为模式详情"""
        b = self._behavior_patterns.get(behavior_id)
        if not b:
            return None
        return {
            "behavior_id": b.behavior_id,
            "name": b.name,
            "event": b.event.value if b.event else None,
            "action": b.action.value if b.action else None,
            "conditions": b.conditions,
            "probability": b.probability,
            "priority": b.priority,
            "repeatable": b.repeatable,
            "cooldown_turns": b.cooldown_turns
        }


# ============================================================
# AI策略分析器
# ============================================================

class AIStrategyAnalyzer:
    """AI策略分析器 — 分析势力AI策略倾向"""

    # 策略特征维度权重
    STRATEGY_DIMENSIONS = {
        AIStrategy.AGGRESSIVE: {
            "aggression": 0.9, "defense": 0.2, "economy": 0.3,
            "diplomacy": 0.1, "expansion": 0.8, "risk_tolerance": 0.9
        },
        AIStrategy.DEFENSIVE: {
            "aggression": 0.1, "defense": 0.9, "economy": 0.5,
            "diplomacy": 0.3, "expansion": 0.2, "risk_tolerance": 0.2
        },
        AIStrategy.BALANCED: {
            "aggression": 0.5, "defense": 0.5, "economy": 0.5,
            "diplomacy": 0.5, "expansion": 0.5, "risk_tolerance": 0.5
        },
        AIStrategy.EXPANSIONIST: {
            "aggression": 0.7, "defense": 0.3, "economy": 0.4,
            "diplomacy": 0.2, "expansion": 0.95, "risk_tolerance": 0.8
        },
        AIStrategy.TURTLE: {
            "aggression": 0.05, "defense": 0.95, "economy": 0.8,
            "diplomacy": 0.4, "expansion": 0.05, "risk_tolerance": 0.1
        },
        AIStrategy.DIPLOMATIC: {
            "aggression": 0.2, "defense": 0.4, "economy": 0.4,
            "diplomacy": 0.95, "expansion": 0.3, "risk_tolerance": 0.3
        },
        AIStrategy.ECONOMIC: {
            "aggression": 0.2, "defense": 0.4, "economy": 0.95,
            "diplomacy": 0.5, "expansion": 0.2, "risk_tolerance": 0.2
        },
        AIStrategy.OPPORTUNISTIC: {
            "aggression": 0.6, "defense": 0.3, "economy": 0.4,
            "diplomacy": 0.6, "expansion": 0.6, "risk_tolerance": 0.7
        },
    }

    def __init__(self):
        self._profiles: Dict[str, AIProfile] = {}
        self._create_default_profiles()

    def _create_default_profiles(self):
        """创建默认AI角色"""
        defaults = [
            ("cunning_warlord", "奸雄", AIStrategy.AGGRESSIVE, 0.9, 0.3, 0.4, 0.2, 0.9, 0.9,
             ["power_hungry", "calculating", "ruthless"]),
            ("benevolent_ruler", "仁君", AIStrategy.DIPLOMATIC, 0.3, 0.5, 0.7, 0.9, 0.4, 0.3,
             ["benevolent", "trustworthy", "patient"]),
            ("warlord", "霸王", AIStrategy.AGGRESSIVE, 0.95, 0.2, 0.2, 0.05, 0.95, 0.95,
             ["fearless", "hot_tempered", "domineering"]),
            ("strategist", "军师", AIStrategy.BALANCED, 0.5, 0.6, 0.5, 0.6, 0.5, 0.4,
             ["intelligent", "cautious", "analytical"]),
            ("merchant_prince", "富商", AIStrategy.ECONOMIC, 0.2, 0.4, 0.95, 0.7, 0.2, 0.2,
             ["wealthy", "diplomatic", "pragmatic"]),
            ("turtle_defender", "铁壁", AIStrategy.TURTLE, 0.05, 0.95, 0.7, 0.3, 0.05, 0.05,
             ["stubborn", "loyal", "defensive"]),
            ("expansionist", "开拓者", AIStrategy.EXPANSIONIST, 0.75, 0.25, 0.35, 0.15, 0.95, 0.85,
             ["ambitious", "restless", "aggressive"]),
            ("diplomat", "纵横家", AIStrategy.DIPLOMATIC, 0.15, 0.35, 0.4, 0.95, 0.25, 0.25,
             ["charismatic", "manipulative", "patient"]),
        ]

        for pid, name, strategy, agg, def_, eco, dip, exp, risk, traits in defaults:
            dims = self.STRATEGY_DIMENSIONS.get(strategy, {})
            profile = AIProfile(
                profile_id=pid,
                name=name,
                strategy=strategy,
                aggression=agg,
                defense=def_,
                economy=eco,
                diplomacy=dip,
                expansion=exp,
                risk_tolerance=risk,
                personality_traits=list(traits),
                metadata={"default": True}
            )
            self._profiles[pid] = profile

    def create_profile(self, profile_id: str, name: str, strategy: AIStrategy = None,
                       aggression: float = 0.5, defense: float = 0.5,
                       economy: float = 0.5, diplomacy: float = 0.5,
                       expansion: float = 0.5, risk_tolerance: float = 0.5,
                       personality_traits: List[str] = None,
                       metadata: dict = None) -> dict:
        """创建AI角色配置"""
        if profile_id in self._profiles:
            return {"success": False, "message": f"配置已存在: {profile_id}"}

        if strategy is None:
            strategy = self._detect_strategy(aggression, defense, economy, diplomacy, expansion, risk_tolerance)

        profile = AIProfile(
            profile_id=profile_id,
            name=name,
            strategy=strategy,
            aggression=max(0.0, min(1.0, aggression)),
            defense=max(0.0, min(1.0, defense)),
            economy=max(0.0, min(1.0, economy)),
            diplomacy=max(0.0, min(1.0, diplomacy)),
            expansion=max(0.0, min(1.0, expansion)),
            risk_tolerance=max(0.0, min(1.0, risk_tolerance)),
            personality_traits=personality_traits or [],
            metadata=metadata or {}
        )
        self._profiles[profile_id] = profile
        return {
            "success": True,
            "message": f"AI角色创建成功: {name}",
            "profile_id": profile_id,
            "detected_strategy": strategy.value
        }

    def _detect_strategy(self, aggression: float, defense: float, economy: float,
                         diplomacy: float, expansion: float, risk_tolerance: float) -> AIStrategy:
        """根据维度值检测最匹配的策略类型"""
        current = {
            "aggression": aggression, "defense": defense, "economy": economy,
            "diplomacy": diplomacy, "expansion": expansion, "risk_tolerance": risk_tolerance
        }

        best_strategy = AIStrategy.BALANCED
        best_score = float("inf")

        for strategy, dims in self.STRATEGY_DIMENSIONS.items():
            # 计算欧几里得距离
            score = sum((current[k] - dims[k]) ** 2 for k in current)
            if score < best_score:
                best_score = score
                best_strategy = strategy

        return best_strategy

    def get_profile(self, profile_id: str) -> Optional[dict]:
        """获取AI角色配置"""
        p = self._profiles.get(profile_id)
        if not p:
            return None
        return {
            "profile_id": p.profile_id,
            "name": p.name,
            "strategy": p.strategy.value,
            "aggression": p.aggression,
            "defense": p.defense,
            "economy": p.economy,
            "diplomacy": p.diplomacy,
            "expansion": p.expansion,
            "risk_tolerance": p.risk_tolerance,
            "personality_traits": p.personality_traits,
            "decision_trees": p.decision_trees,
            "behavior_patterns": p.behavior_patterns,
            "metadata": p.metadata
        }

    def list_profiles(self) -> List[dict]:
        """列出所有AI角色"""
        return [
            {
                "profile_id": p.profile_id,
                "name": p.name,
                "strategy": p.strategy.value,
                "aggression": p.aggression,
                "defense": p.defense,
                "risk_tolerance": p.risk_tolerance
            }
            for p in self._profiles.values()
        ]

    def update_profile(self, profile_id: str, **kwargs) -> dict:
        """更新AI角色配置"""
        p = self._profiles.get(profile_id)
        if not p:
            return {"success": False, "message": f"配置不存在: {profile_id}"}

        dim_keys = ["aggression", "defense", "economy", "diplomacy", "expansion", "risk_tolerance"]

        for key, value in kwargs.items():
            if hasattr(p, key):
                if key in dim_keys:
                    value = max(0.0, min(1.0, float(value)))
                setattr(p, key, value)

        # 重新检测策略
        if any(k in dim_keys for k in kwargs):
            p.strategy = self._detect_strategy(
                p.aggression, p.defense, p.economy, p.diplomacy, p.expansion, p.risk_tolerance
            )

        return {"success": True, "message": f"更新成功: {p.name}", "strategy": p.strategy.value}

    def compare_profiles(self, profile_id1: str, profile_id2: str) -> dict:
        """比较两个AI角色"""
        p1 = self._profiles.get(profile_id1)
        p2 = self._profiles.get(profile_id2)

        if not p1 or not p2:
            return {"success": False, "message": "一个或多个配置不存在"}

        dims = ["aggression", "defense", "economy", "diplomacy", "expansion", "risk_tolerance"]
        comparison = {}

        for dim in dims:
            v1 = getattr(p1, dim)
            v2 = getattr(p2, dim)
            comparison[dim] = {
                "profile1": v1,
                "profile2": v2,
                "difference": round(v1 - v2, 3),
                "winner": p1.name if v1 > v2 else (p2.name if v2 > v1 else "平手")
            }

        return {
            "success": True,
            "profile1": {"id": p1.profile_id, "name": p1.name, "strategy": p1.strategy.value},
            "profile2": {"id": p2.profile_id, "name": p2.name, "strategy": p2.strategy.value},
            "comparison": comparison,
            "similarity": self._calculate_similarity(p1, p2)
        }

    def _calculate_similarity(self, p1: AIProfile, p2: AIProfile) -> float:
        """计算两个AI角色的相似度"""
        dims = ["aggression", "defense", "economy", "diplomacy", "expansion", "risk_tolerance"]
        diffs = [abs(getattr(p1, d) - getattr(p2, d)) for d in dims]
        avg_diff = sum(diffs) / len(diffs)
        return round(1.0 - avg_diff, 3)

    def delete_profile(self, profile_id: str) -> dict:
        """删除AI角色配置"""
        p = self._profiles.get(profile_id)
        if not p:
            return {"success": False, "message": f"配置不存在: {profile_id}"}
        if p.metadata.get("default"):
            return {"success": False, "message": f"不能删除默认配置: {p.name}"}
        del self._profiles[profile_id]
        return {"success": True, "message": f"已删除: {p.name}"}


# ============================================================
# AI决策优先级分析器
# ============================================================

class AIPriorityAnalyzer:
    """AI优先级分析器 — 分析决策权重和优先级排序"""

    def __init__(self):
        self._base_decision_weights: Dict[AIDecisionType, float] = {
            AIDecisionType.ATTACK_CITY: 0.5,
            AIDecisionType.DEFEND_CITY: 0.7,
            AIDecisionType.RECRUIT: 0.4,
            AIDecisionType.DEVELOP: 0.3,
            AIDecisionType.DIPLOMACY: 0.3,
            AIDecisionType.RESEARCH: 0.2,
            AIDecisionType.MOVE_TROOPS: 0.4,
            AIDecisionType.USE_ITEM: 0.3,
            AIDecisionType.APPOINT_OFFICER: 0.2,
            AIDecisionType.FORM_ALLIANCE: 0.3,
            AIDecisionType.DECLARE_WAR: 0.4,
            AIDecisionType.SURRENDER: 0.1,
            AIDecisionType.BATTLE_TACTIC: 0.6,
            AIDecisionType.RETREAT: 0.5,
            AIDecisionType.SKILL_USE: 0.5,
            AIDecisionType.ECONOMIC: 0.3,
            AIDecisionType.EXPANSION: 0.5,
        }

        # 情境修正因子
        self._context_modifiers: Dict[str, Dict[AIDecisionType, float]] = {
            "war": {
                AIDecisionType.ATTACK_CITY: 1.5,
                AIDecisionType.DEFEND_CITY: 1.3,
                AIDecisionType.RECRUIT: 1.4,
                AIDecisionType.BATTLE_TACTIC: 1.5,
                AIDecisionType.RETREAT: 1.2,
                AIDecisionType.DEVELOP: 0.5,
                AIDecisionType.DIPLOMACY: 0.4,
            },
            "peace": {
                AIDecisionType.DEVELOP: 1.5,
                AIDecisionType.DIPLOMACY: 1.5,
                AIDecisionType.RESEARCH: 1.3,
                AIDecisionType.ECONOMIC: 1.4,
                AIDecisionType.ATTACK_CITY: 0.3,
                AIDecisionType.DECLARE_WAR: 0.2,
            },
            "desperate": {
                AIDecisionType.SURRENDER: 1.5,
                AIDecisionType.RETREAT: 1.5,
                AIDecisionType.DEFEND_CITY: 1.3,
                AIDecisionType.RECRUIT: 1.3,
                AIDecisionType.DEVELOP: 0.3,
                AIDecisionType.DIPLOMACY: 0.5,
            },
            "dominant": {
                AIDecisionType.ATTACK_CITY: 1.5,
                AIDecisionType.EXPANSION: 1.5,
                AIDecisionType.DECLARE_WAR: 1.3,
                AIDecisionType.DEVELOP: 0.5,
                AIDecisionType.DEFEND_CITY: 0.5,
            },
        }

    def calculate_priority(self, decision_type: AIDecisionType, profile: AIProfile = None,
                           context: str = "peace", state: dict = None) -> dict:
        """计算决策优先级"""
        base_weight = self._base_decision_weights.get(decision_type, 0.3)

        # 情境修正
        context_mod = 1.0
        if context in self._context_modifiers:
            context_mod = self._context_modifiers[context].get(decision_type, 1.0)

        # 策略修正
        strategy_mod = 1.0
        if profile:
            strategy_mod = self._calculate_strategy_modifier(decision_type, profile)

        # 状态修正
        state_mod = 1.0
        if state:
            state_mod = self._calculate_state_modifier(decision_type, state)

        final_weight = base_weight * context_mod * strategy_mod * state_mod
        final_weight = max(0.01, min(1.0, final_weight))

        return {
            "decision_type": decision_type.value,
            "base_weight": round(base_weight, 3),
            "context_modifier": round(context_mod, 3),
            "strategy_modifier": round(strategy_mod, 3),
            "state_modifier": round(state_mod, 3),
            "final_priority": round(final_weight, 3),
            "context": context
        }

    def _calculate_strategy_modifier(self, decision_type: AIDecisionType, profile: AIProfile) -> float:
        """根据AI策略计算修正因子"""
        # 进攻型决策受 aggression 影响
        attack_types = {AIDecisionType.ATTACK_CITY, AIDecisionType.DECLARE_WAR,
                        AIDecisionType.BATTLE_TACTIC}
        defense_types = {AIDecisionType.DEFEND_CITY, AIDecisionType.RETREAT}
        economy_types = {AIDecisionType.DEVELOP, AIDecisionType.RECRUIT}
        diplomacy_types = {AIDecisionType.DIPLOMACY, AIDecisionType.FORM_ALLIANCE}

        if decision_type in attack_types:
            return 0.5 + profile.aggression * 1.0
        elif decision_type in defense_types:
            return 0.5 + profile.defense * 1.0
        elif decision_type in economy_types:
            return 0.5 + profile.economy * 1.0
        elif decision_type in diplomacy_types:
            return 0.5 + profile.diplomacy * 1.0
        return 1.0

    def _calculate_state_modifier(self, decision_type: AIDecisionType, state: dict) -> float:
        """根据当前状态计算修正因子"""
        mod = 1.0

        hp = state.get("hp_ratio", 1.0)
        mp = state.get("mp_ratio", 1.0)
        soldiers = state.get("soldier_ratio", 1.0)
        enemies = state.get("enemies_nearby", 0)

        if decision_type == AIDecisionType.RETREAT:
            if hp < 0.3:
                mod *= 2.0
            if soldiers < 0.3:
                mod *= 1.5

        elif decision_type == AIDecisionType.SKILL_USE:
            if mp >= 0.5 and enemies > 0:
                mod *= 1.5

        elif decision_type == AIDecisionType.ATTACK_CITY:
            if hp >= 0.7 and soldiers >= 0.6:
                mod *= 1.3
            if hp < 0.3:
                mod *= 0.3

        return max(0.1, mod)

    def rank_decisions(self, profile: AIProfile = None, context: str = "peace",
                       state: dict = None, limit: int = 10) -> List[dict]:
        """对所有决策类型排序"""
        results = []
        for dt in AIDecisionType:
            priority = self.calculate_priority(dt, profile, context, state)
            results.append(priority)

        results.sort(key=lambda x: x["final_priority"], reverse=True)
        return results[:limit]

    def get_context_analysis(self, context: str) -> dict:
        """获取情境分析"""
        if context not in self._context_modifiers:
            return {"success": False, "message": f"未知情境: {context}"}

        modifiers = self._context_modifiers[context]
        boosted = []
        nerfed = []

        for dt, mod in modifiers.items():
            if mod > 1.0:
                boosted.append({"type": dt.value, "modifier": mod})
            elif mod < 1.0:
                nerfed.append({"type": dt.value, "modifier": mod})

        boosted.sort(key=lambda x: x["modifier"], reverse=True)
        nerfed.sort(key=lambda x: x["modifier"])

        return {
            "success": True,
            "context": context,
            "boosted_decisions": boosted,
            "nerfed_decisions": nerfed,
            "total_modifiers": len(modifiers)
        }

    def set_base_weight(self, decision_type: AIDecisionType, weight: float) -> dict:
        """设置基础权重"""
        weight = max(0.0, min(1.0, weight))
        self._base_decision_weights[decision_type] = weight
        return {"success": True, "decision_type": decision_type.value, "weight": weight}

    def get_all_weights(self) -> dict:
        """获取所有权重"""
        return {
            dt.value: round(w, 3)
            for dt, w in self._base_decision_weights.items()
        }


# ============================================================
# AI行为模拟器
# ============================================================

class AIBehaviorSimulator:
    """AI行为模拟器 — 模拟AI在特定场景下的行为"""

    def __init__(self, behavior_analyzer: AIBehaviorAnalyzer = None,
                 priority_analyzer: AIPriorityAnalyzer = None):
        self._behavior_analyzer = behavior_analyzer or AIBehaviorAnalyzer()
        self._priority_analyzer = priority_analyzer or AIPriorityAnalyzer()
        self._simulation_results: Dict[str, AISimulationResult] = {}
        self._counter = 0

    def simulate(self, profile: AIProfile, initial_state: AIState,
                 num_turns: int = 10, events: List[AIEventType] = None) -> dict:
        """模拟AI行为"""
        self._counter += 1
        sim_id = f"sim_{self._counter}"

        result = AISimulationResult(
            simulation_id=sim_id,
            profile=profile,
            turns=num_turns
        )

        state = initial_state
        result.state_history.append(state)

        import random
        events = events or []

        for turn in range(num_turns):
            # 确定当前事件
            if turn < len(events):
                event = events[turn]
            else:
                event = random.choice(list(AIEventType))

            # 匹配行为模式
            matched = self._behavior_analyzer.match_patterns(state, event)

            if matched:
                # 选择最高优先级行为
                best = matched[0]
                action_type = AIActionType(best["action"]) if best["action"] else None
                result.actions_taken.append(action_type)

                # 应用行为效果
                state = self._apply_action(state, action_type, profile)

            result.state_history.append(state)

            # 检查终止条件
            if state.hp_ratio <= 0:
                result.outcome = "defeated"
                break

        if result.outcome == "unknown":
            if state.hp_ratio > 0.7:
                result.outcome = "victory"
            elif state.hp_ratio > 0.3:
                result.outcome = "survived"
            else:
                result.outcome = "barely_survived"

        result.score = self._calculate_score(result)
        self._simulation_results[sim_id] = result

        return {
            "success": True,
            "simulation_id": sim_id,
            "profile": profile.name,
            "strategy": profile.strategy.value,
            "turns": len(result.actions_taken),
            "outcome": result.outcome,
            "score": result.score,
            "actions": [a.value if a else None for a in result.actions_taken],
            "final_state": {
                "hp_ratio": round(state.hp_ratio, 3),
                "mp_ratio": round(state.mp_ratio, 3),
                "soldier_ratio": round(state.soldier_ratio, 3),
                "morale": state.morale
            }
        }

    def _apply_action(self, state: AIState, action: AIActionType, profile: AIProfile) -> AIState:
        """应用动作效果"""
        import copy
        new_state = copy.deepcopy(state)

        if action == AIActionType.ATTACK:
            new_state.mp_ratio = max(0, new_state.mp_ratio - 0.1)
            new_state.soldier_ratio = max(0, new_state.soldier_ratio - 0.05)
        elif action == AIActionType.DEFEND:
            new_state.mp_ratio = max(0, new_state.mp_ratio - 0.05)
        elif action == AIActionType.RETREAT:
            new_state.hp_ratio = min(1.0, new_state.hp_ratio + 0.05)
            new_state.morale = max(0, new_state.morale - 10)
        elif action == AIActionType.USE_SKILL:
            new_state.mp_ratio = max(0, new_state.mp_ratio - 0.2)
        elif action == AIActionType.HEAL:
            new_state.hp_ratio = min(1.0, new_state.hp_ratio + 0.15)
            new_state.mp_ratio = max(0, new_state.mp_ratio - 0.1)
        elif action == AIActionType.USE_ITEM:
            new_state.hp_ratio = min(1.0, new_state.hp_ratio + 0.2)
        elif action == AIActionType.SUPPORT:
            new_state.soldier_ratio = max(0, new_state.soldier_ratio - 0.03)
        elif action == AIActionType.WAIT:
            new_state.mp_ratio = min(1.0, new_state.mp_ratio + 0.05)

        return new_state

    def _calculate_score(self, result: AISimulationResult) -> float:
        """计算模拟得分"""
        if not result.state_history:
            return 0.0

        final = result.state_history[-1]
        score = (
            final.hp_ratio * 0.3 +
            final.mp_ratio * 0.1 +
            final.soldier_ratio * 0.3 +
            (final.morale / 100.0) * 0.1
        )

        # 行动多样性加分
        unique_actions = len(set(result.actions_taken))
        diversity = min(1.0, unique_actions / 5.0) * 0.2

        return round(score + diversity, 3)

    def batch_simulate(self, profile_ids: List[str], initial_state: AIState,
                       strategy_analyzer: "AIStrategyAnalyzer" = None,
                       num_turns: int = 10, runs: int = 3) -> dict:
        """批量模拟多个AI角色"""
        results = []

        for pid in profile_ids:
            if strategy_analyzer:
                profile = strategy_analyzer._profiles.get(pid)
            else:
                continue

            if not profile:
                continue

            run_results = []
            for _ in range(runs):
                sim = self.simulate(profile, initial_state, num_turns)
                run_results.append(sim)

            avg_score = sum(r["score"] for r in run_results) / len(run_results)
            outcomes = Counter(r["outcome"] for r in run_results)

            results.append({
                "profile_id": pid,
                "name": profile.name,
                "strategy": profile.strategy.value,
                "average_score": round(avg_score, 3),
                "outcomes": dict(outcomes),
                "runs": runs
            })

        results.sort(key=lambda x: x["average_score"], reverse=True)

        return {
            "success": True,
            "scenario": f"{num_turns} turns x {runs} runs",
            "results": results,
            "best_profile": results[0]["name"] if results else None
        }

    def get_simulation(self, sim_id: str) -> Optional[dict]:
        """获取模拟结果"""
        result = self._simulation_results.get(sim_id)
        if not result:
            return None

        return {
            "simulation_id": result.simulation_id,
            "profile": result.profile.name if result.profile else None,
            "turns": result.turns,
            "outcome": result.outcome,
            "score": result.score,
            "actions": [a.value if a else None for a in result.actions_taken],
            "final_state": {
                "hp_ratio": result.state_history[-1].hp_ratio if result.state_history else 0,
                "mp_ratio": result.state_history[-1].mp_ratio if result.state_history else 0,
                "soldier_ratio": result.state_history[-1].soldier_ratio if result.state_history else 0,
                "morale": result.state_history[-1].morale if result.state_history else 0,
            }
        }

    def list_simulations(self) -> List[dict]:
        """列出所有模拟结果"""
        return [
            {
                "simulation_id": r.simulation_id,
                "profile": r.profile.name if r.profile else None,
                "outcome": r.outcome,
                "score": r.score,
                "turns": r.turns
            }
            for r in self._simulation_results.values()
        ]


# ============================================================
# AI数据序列化器
# ============================================================

class AIDataSerializer:
    """AI数据序列化器 — 导出/导入AI配置"""

    @staticmethod
    def export_profile(profile: AIProfile) -> dict:
        """导出AI角色为字典"""
        return {
            "profile_id": profile.profile_id,
            "name": profile.name,
            "strategy": profile.strategy.value,
            "aggression": profile.aggression,
            "defense": profile.defense,
            "economy": profile.economy,
            "diplomacy": profile.diplomacy,
            "expansion": profile.expansion,
            "risk_tolerance": profile.risk_tolerance,
            "decision_trees": profile.decision_trees,
            "behavior_patterns": profile.behavior_patterns,
            "personality_traits": profile.personality_traits,
            "metadata": profile.metadata
        }

    @staticmethod
    def import_profile(data: dict) -> AIProfile:
        """从字典导入AI角色"""
        strategy = AIStrategy(data.get("strategy", "balanced"))
        return AIProfile(
            profile_id=data["profile_id"],
            name=data["name"],
            strategy=strategy,
            aggression=data.get("aggression", 0.5),
            defense=data.get("defense", 0.5),
            economy=data.get("economy", 0.5),
            diplomacy=data.get("diplomacy", 0.5),
            expansion=data.get("expansion", 0.5),
            risk_tolerance=data.get("risk_tolerance", 0.5),
            decision_trees=data.get("decision_trees", []),
            behavior_patterns=data.get("behavior_patterns", []),
            personality_traits=data.get("personality_traits", []),
            metadata=data.get("metadata", {})
        )

    @staticmethod
    def export_all(profiles: Dict[str, AIProfile],
                   trees: Dict[str, AIDecisionTree],
                   behaviors: List[dict]) -> dict:
        """导出全部AI配置"""
        return {
            "version": "1.0",
            "profiles": {
                pid: AIDataSerializer.export_profile(p)
                for pid, p in profiles.items()
            },
            "decision_trees": {
                tid: {
                    "tree_id": t.tree_id,
                    "name": t.name,
                    "description": t.description,
                    "root_node_id": t.root_node_id,
                    "nodes": {
                        nid: {
                            "node_id": n.node_id,
                            "node_type": n.node_type,
                            "parent_id": n.parent_id,
                            "children": n.children,
                            "condition": n.condition,
                            "action": n.action,
                            "weight": n.weight,
                            "probability": n.probability,
                            "metadata": n.metadata
                        }
                        for nid, n in t.nodes.items()
                    },
                    "version": t.version
                }
                for tid, t in trees.items()
            },
            "behavior_patterns": behaviors
        }

    @staticmethod
    def save_to_file(data: dict, file_path: str) -> dict:
        """保存到文件"""
        try:
            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return {"success": True, "message": f"保存成功: {file_path}"}
        except Exception as e:
            return {"success": False, "message": f"保存失败: {str(e)}"}

    @staticmethod
    def load_from_file(file_path: str) -> dict:
        """从文件加载"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "message": f"加载失败: {str(e)}"}


# ============================================================
# 主分析器
# ============================================================

class AIAnalyzer:
    """
    游戏AI行为分析器主类
    
    整合所有子模块:
    - 决策树构建与分析
    - 行为模式识别
    - 策略分析
    - 优先级计算
    - 行为模拟
    - 数据序列化
    """

    def __init__(self):
        self.tree_builder = AIDecisionTreeBuilder()
        self.behavior_analyzer = AIBehaviorAnalyzer()
        self.strategy_analyzer = AIStrategyAnalyzer()
        self.priority_analyzer = AIPriorityAnalyzer()
        self.simulator = AIBehaviorSimulator(
            self.behavior_analyzer, self.priority_analyzer
        )
        self.serializer = AIDataSerializer()

    # ============================================================
    # 决策树操作
    # ============================================================

    def create_decision_tree(self, tree_id: str, name: str, description: str = "") -> dict:
        """创建决策树"""
        tree = self.tree_builder.create_tree(tree_id, name, description)
        return {"success": True, "tree_id": tree.tree_id, "name": tree.name}

    def add_condition_node(self, tree_id: str, parent_id: str, condition: dict,
                           weight: float = 1.0) -> dict:
        """添加条件节点"""
        node = self.tree_builder.add_condition_node(tree_id, parent_id, condition, weight=weight)
        return {"success": True, "node_id": node.node_id, "node_type": node.node_type}

    def add_action_node(self, tree_id: str, parent_id: str, action: dict,
                        weight: float = 1.0) -> dict:
        """添加动作节点"""
        node = self.tree_builder.add_action_node(tree_id, parent_id, action, weight=weight)
        return {"success": True, "node_id": node.node_id, "node_type": node.node_type}

    def add_probability_node(self, tree_id: str, parent_id: str,
                             probability: float = 0.5) -> dict:
        """添加概率节点"""
        node = self.tree_builder.add_probability_node(tree_id, parent_id, probability)
        return {"success": True, "node_id": node.node_id, "node_type": node.node_type}

    def add_selector_node(self, tree_id: str, parent_id: str) -> dict:
        """添加选择器节点"""
        node = self.tree_builder.add_selector_node(tree_id, parent_id)
        return {"success": True, "node_id": node.node_id, "node_type": node.node_type}

    def add_sequence_node(self, tree_id: str, parent_id: str) -> dict:
        """添加序列节点"""
        node = self.tree_builder.add_sequence_node(tree_id, parent_id)
        return {"success": True, "node_id": node.node_id, "node_type": node.node_type}

    def export_decision_tree(self, tree_id: str) -> dict:
        """导出决策树"""
        return self.tree_builder.export_tree(tree_id)

    def import_decision_tree(self, data: dict) -> dict:
        """导入决策树"""
        return self.tree_builder.import_tree(data)

    def list_decision_trees(self) -> List[dict]:
        """列出所有决策树"""
        return self.tree_builder.list_trees()

    # ============================================================
    # 行为模式操作
    # ============================================================

    def add_behavior_pattern(self, behavior_id: str, name: str, event: str,
                             action: str, conditions: List[dict],
                             probability: float = 1.0, priority: int = 50,
                             repeatable: bool = True, cooldown_turns: int = 0) -> dict:
        """添加行为模式"""
        try:
            event_enum = AIEventType(event)
            action_enum = AIActionType(action)
        except ValueError:
            return {"success": False, "message": f"无效的事件或动作类型"}

        return self.behavior_analyzer.add_pattern(
            behavior_id, name, event_enum, action_enum,
            conditions, probability, priority, repeatable, cooldown_turns
        )

    def match_behaviors(self, state: dict, event: str) -> dict:
        """匹配行为模式"""
        try:
            event_enum = AIEventType(event)
        except ValueError:
            return {"success": False, "message": f"无效的事件类型: {event}"}

        ai_state = AIState(
            state_id="temp",
            hp_ratio=state.get("hp_ratio", 1.0),
            mp_ratio=state.get("mp_ratio", 1.0),
            soldier_ratio=state.get("soldier_ratio", 1.0),
            morale=state.get("morale", 100),
            enemies_nearby=state.get("enemies_nearby", 0),
            allies_nearby=state.get("allies_nearby", 0),
            flags=state.get("flags", {})
        )

        matched = self.behavior_analyzer.match_patterns(ai_state, event_enum)
        return {"success": True, "matched": matched, "count": len(matched)}

    def list_behavior_patterns(self) -> List[dict]:
        """列出所有行为模式"""
        return self.behavior_analyzer.list_patterns()

    def get_behavior_pattern(self, behavior_id: str) -> Optional[dict]:
        """获取行为模式"""
        return self.behavior_analyzer.get_pattern(behavior_id)

    def remove_behavior_pattern(self, behavior_id: str) -> dict:
        """移除行为模式"""
        return self.behavior_analyzer.remove_pattern(behavior_id)

    # ============================================================
    # 策略分析操作
    # ============================================================

    def create_ai_profile(self, profile_id: str, name: str, **kwargs) -> dict:
        """创建AI角色"""
        strategy = None
        if "strategy" in kwargs:
            try:
                strategy = AIStrategy(kwargs.pop("strategy"))
            except ValueError:
                pass
        return self.strategy_analyzer.create_profile(
            profile_id, name, strategy, **kwargs
        )

    def get_ai_profile(self, profile_id: str) -> Optional[dict]:
        """获取AI角色"""
        return self.strategy_analyzer.get_profile(profile_id)

    def list_ai_profiles(self) -> List[dict]:
        """列出所有AI角色"""
        return self.strategy_analyzer.list_profiles()

    def update_ai_profile(self, profile_id: str, **kwargs) -> dict:
        """更新AI角色"""
        return self.strategy_analyzer.update_profile(profile_id, **kwargs)

    def compare_ai_profiles(self, profile_id1: str, profile_id2: str) -> dict:
        """比较两个AI角色"""
        return self.strategy_analyzer.compare_profiles(profile_id1, profile_id2)

    def delete_ai_profile(self, profile_id: str) -> dict:
        """删除AI角色"""
        return self.strategy_analyzer.delete_profile(profile_id)

    # ============================================================
    # 优先级分析操作
    # ============================================================

    def calculate_decision_priority(self, decision_type: str, profile_id: str = None,
                                    context: str = "peace", state: dict = None) -> dict:
        """计算决策优先级"""
        try:
            dt = AIDecisionType(decision_type)
        except ValueError:
            return {"success": False, "message": f"无效的决策类型: {decision_type}"}

        profile = None
        if profile_id:
            profile = self.strategy_analyzer._profiles.get(profile_id)

        return self.priority_analyzer.calculate_priority(dt, profile, context, state)

    def rank_decisions(self, profile_id: str = None, context: str = "peace",
                       state: dict = None, limit: int = 10) -> List[dict]:
        """排序决策优先级"""
        profile = None
        if profile_id:
            profile = self.strategy_analyzer._profiles.get(profile_id)

        return self.priority_analyzer.rank_decisions(profile, context, state, limit)

    def get_context_analysis(self, context: str) -> dict:
        """获取情境分析"""
        return self.priority_analyzer.get_context_analysis(context)

    def get_all_decision_weights(self) -> dict:
        """获取所有决策权重"""
        return self.priority_analyzer.get_all_weights()

    def set_decision_weight(self, decision_type: str, weight: float) -> dict:
        """设置决策权重"""
        try:
            dt = AIDecisionType(decision_type)
        except ValueError:
            return {"success": False, "message": f"无效的决策类型: {decision_type}"}
        return self.priority_analyzer.set_base_weight(dt, weight)

    def list_decision_types(self) -> List[str]:
        """列出所有决策类型"""
        return [dt.value for dt in AIDecisionType]

    def list_event_types(self) -> List[str]:
        """列出所有事件类型"""
        return [e.value for e in AIEventType]

    def list_action_types(self) -> List[str]:
        """列出所有动作类型"""
        return [a.value for a in AIActionType]

    def list_strategy_types(self) -> List[str]:
        """列出所有策略类型"""
        return [s.value for s in AIStrategy]

    # ============================================================
    # 行为模拟操作
    # ============================================================

    def simulate_ai(self, profile_id: str, initial_state: dict,
                    num_turns: int = 10, events: List[str] = None) -> dict:
        """模拟AI行为"""
        profile = self.strategy_analyzer._profiles.get(profile_id)
        if not profile:
            return {"success": False, "message": f"AI角色不存在: {profile_id}"}

        state = AIState(
            state_id="sim",
            hp_ratio=initial_state.get("hp_ratio", 1.0),
            mp_ratio=initial_state.get("mp_ratio", 1.0),
            soldier_ratio=initial_state.get("soldier_ratio", 1.0),
            morale=initial_state.get("morale", 100),
            enemies_nearby=initial_state.get("enemies_nearby", 0),
            allies_nearby=initial_state.get("allies_nearby", 0),
            flags=initial_state.get("flags", {})
        )

        event_enums = None
        if events:
            event_enums = []
            for e in events:
                try:
                    event_enums.append(AIEventType(e))
                except ValueError:
                    pass

        return self.simulator.simulate(profile, state, num_turns, event_enums)

    def batch_simulate_ai(self, profile_ids: List[str], initial_state: dict,
                          num_turns: int = 10, runs: int = 3) -> dict:
        """批量模拟AI"""
        state = AIState(
            state_id="batch",
            hp_ratio=initial_state.get("hp_ratio", 1.0),
            mp_ratio=initial_state.get("mp_ratio", 1.0),
            soldier_ratio=initial_state.get("soldier_ratio", 1.0),
            morale=initial_state.get("morale", 100),
            enemies_nearby=initial_state.get("enemies_nearby", 0),
            allies_nearby=initial_state.get("allies_nearby", 0),
            flags=initial_state.get("flags", {})
        )

        return self.simulator.batch_simulate(
            profile_ids, state, self.strategy_analyzer, num_turns, runs
        )

    def get_simulation_result(self, sim_id: str) -> Optional[dict]:
        """获取模拟结果"""
        return self.simulator.get_simulation(sim_id)

    def list_simulations(self) -> List[dict]:
        """列出所有模拟"""
        return self.simulator.list_simulations()

    # ============================================================
    # 数据导入导出
    # ============================================================

    def export_all_ai_data(self) -> dict:
        """导出全部AI数据"""
        behaviors = self.behavior_analyzer.list_patterns()
        return self.serializer.export_all(
            self.strategy_analyzer._profiles,
            self.tree_builder._trees,
            behaviors
        )

    def save_ai_data(self, file_path: str) -> dict:
        """保存AI数据到文件"""
        data = self.export_all_ai_data()
        return self.serializer.save_to_file(data, file_path)

    def load_ai_data(self, file_path: str) -> dict:
        """从文件加载AI数据"""
        result = self.serializer.load_from_file(file_path)
        if not result["success"]:
            return result

        data = result["data"]
        loaded = {"profiles": 0, "trees": 0, "behaviors": 0}

        # 加载决策树
        for tid, tdata in data.get("decision_trees", {}).items():
            self.tree_builder.import_tree(tdata)
            loaded["trees"] += 1

        # 加载行为模式
        for bdata in data.get("behavior_patterns", []):
            self.behavior_analyzer._behavior_patterns[bdata["behavior_id"]] = AIBehavior(
                behavior_id=bdata["behavior_id"],
                name=bdata["name"],
                event=AIEventType(bdata["event"]) if bdata.get("event") else None,
                action=AIActionType(bdata["action"]) if bdata.get("action") else None,
                conditions=bdata.get("conditions", []),
                probability=bdata.get("probability", 1.0),
                priority=bdata.get("priority", 50),
                repeatable=bdata.get("repeatable", True),
                cooldown_turns=bdata.get("cooldown_turns", 0)
            )
            loaded["behaviors"] += 1

        # 加载AI角色
        for pid, pdata in data.get("profiles", {}).items():
            profile = self.serializer.import_profile(pdata)
            self.strategy_analyzer._profiles[pid] = profile
            loaded["profiles"] += 1

        return {
            "success": True,
            "message": "加载完成",
            "loaded": loaded
        }


# ============================================================
# 快捷函数
# ============================================================

def create_battle_ai_tree(analyzer: AIAnalyzer) -> dict:
    """创建标准战斗AI决策树"""
    tree_id = "battle_standard"
    tree = analyzer.tree_builder.create_tree(tree_id, "标准战斗AI", "战斗中的标准AI决策流程")

    # 根节点：选择器
    root = analyzer.tree_builder.add_selector_node(tree_id, None)

    # 存活检查
    hp_check = analyzer.tree_builder.add_condition_node(
        tree_id, root.node_id,
        {"type": "hp_ratio", "operator": ">", "value": 0}
    )

    # 低血量分支
    low_hp = analyzer.tree_builder.add_condition_node(
        tree_id, hp_check.node_id,
        {"type": "hp_ratio", "operator": "<", "value": 0.2}
    )

    # 撤退
    analyzer.tree_builder.add_action_node(
        tree_id, low_hp.node_id,
        {"type": "retreat", "priority": "high"}
    )

    # 有技能可用？
    has_mp = analyzer.tree_builder.add_condition_node(
        tree_id, hp_check.node_id,
        {"type": "mp_ratio", "operator": ">=", "value": 0.5}
    )

    # 使用技能
    analyzer.tree_builder.add_action_node(
        tree_id, has_mp.node_id,
        {"type": "use_skill", "priority": "high"}
    )

    # 默认攻击
    analyzer.tree_builder.add_action_node(
        tree_id, hp_check.node_id,
        {"type": "attack", "priority": "normal"}
    )

    return {"success": True, "tree_id": tree_id, "name": tree.name, "node_count": len(tree.nodes)}


def create_campaign_ai_tree(analyzer: AIAnalyzer) -> dict:
    """创建标准内政AI决策树"""
    tree_id = "campaign_standard"
    tree = analyzer.tree_builder.create_tree(tree_id, "标准内政AI", "回合制内政AI决策流程")

    root = analyzer.tree_builder.add_selector_node(tree_id, None)

    # 战争状态
    at_war = analyzer.tree_builder.add_condition_node(
        tree_id, root.node_id,
        {"type": "at_war", "operator": "==", "value": True}
    )

    # 征兵
    analyzer.tree_builder.add_action_node(
        tree_id, at_war.node_id,
        {"type": "recruit", "priority": "critical"}
    )

    # 守城
    analyzer.tree_builder.add_action_node(
        tree_id, at_war.node_id,
        {"type": "defend_city", "priority": "high"}
    )

    # 和平时期
    at_peace = analyzer.tree_builder.add_condition_node(
        tree_id, root.node_id,
        {"type": "at_war", "operator": "==", "value": False}
    )

    # 开发
    analyzer.tree_builder.add_action_node(
        tree_id, at_peace.node_id,
        {"type": "develop", "priority": "normal"}
    )

    # 外交
    analyzer.tree_builder.add_action_node(
        tree_id, at_peace.node_id,
        {"type": "diplomacy", "priority": "low"}
    )

    return {"success": True, "tree_id": tree_id, "name": tree.name, "node_count": len(tree.nodes)}