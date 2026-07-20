"""
兵种相克矩阵编辑器 (v1.0)
- 管理67个兵种之间的相互克制关系
- 基于Soldier.ini中的HitSolXX系列字段
- 提供可视化矩阵和批量编辑
"""

import os
import json
from typing import Dict, List, Tuple, Any, Optional


class SoldierMatrixEditor:
    """
    兵种相克矩阵编辑器
    
    每个兵种有67个克制系数(HitSol0~HitSol66)，表示对每个兵种的伤害倍率。
    默认值100表示无克制，>100表示克制，<100表示被克制。
    """

    MATRIX_SIZE = 67  # 群7最多67个兵种
    HIT_SOL_PREFIX = "HitSol"

    def __init__(self):
        self.soldiers: List[dict] = []
        self.matrix: List[List[int]] = []  # 67x67 矩阵

    def load_from_soldiers(self, soldiers: List[dict]) -> dict:
        """从兵种数据加载相克矩阵"""
        self.soldiers = soldiers[:self.MATRIX_SIZE]
        self._build_matrix()
        return self.get_summary()

    def _build_matrix(self):
        """构建67x67相克矩阵"""
        self.matrix = []
        for i, soldier in enumerate(self.soldiers):
            row = []
            for j in range(self.MATRIX_SIZE):
                key = f"{self.HIT_SOL_PREFIX}{j}"
                value = int(soldier.get(key, 100))
                row.append(value)
            self.matrix.append(row)

    def get_matrix(self) -> List[List[int]]:
        return self.matrix

    def get_summary(self) -> dict:
        """获取矩阵摘要"""
        if not self.matrix:
            return {"size": 0, "soldiers": []}

        soldier_names = []
        for i, s in enumerate(self.soldiers):
            name = s.get("Name", f"兵种{i}")
            soldier_names.append({"index": i, "name": name, "no": s.get("No", i)})

        # 找克制关系
        strong_relations = []  # 克制(>150)
        weak_relations = []    # 被克制(<50)

        for i in range(len(self.matrix)):
            for j in range(len(self.matrix[i])):
                val = self.matrix[i][j]
                if val > 150 and i != j:
                    strong_relations.append({
                        "attacker": soldier_names[i]["name"],
                        "attacker_idx": i,
                        "defender": soldier_names[j]["name"],
                        "defender_idx": j,
                        "value": val,
                    })
                elif val < 50 and val > 0 and i != j:
                    weak_relations.append({
                        "attacker": soldier_names[i]["name"],
                        "defender": soldier_names[j]["name"],
                        "value": val,
                    })

        return {
            "size": len(self.matrix),
            "soldiers": soldier_names,
            "strong_count": len(strong_relations),
            "weak_count": len(weak_relations),
            "strong_relations": strong_relations[:20],  # 前20条
            "weak_relations": weak_relations[:20],
        }

    def update_cell(self, attacker_idx: int, defender_idx: int, value: int) -> dict:
        """更新单个相克值"""
        if attacker_idx >= len(self.matrix) or defender_idx >= self.MATRIX_SIZE:
            return {"success": False, "message": "索引超出范围"}

        self.matrix[attacker_idx][defender_idx] = value

        if attacker_idx < len(self.soldiers):
            key = f"{self.HIT_SOL_PREFIX}{defender_idx}"
            self.soldiers[attacker_idx][key] = value

        return {"success": True, "attacker": attacker_idx, "defender": defender_idx, "value": value}

    def batch_set(self, attacker_idx: int, values: List[int]) -> dict:
        """批量设置一个兵种对所有兵种的克制值"""
        if attacker_idx >= len(self.matrix):
            return {"success": False, "message": "索引超出范围"}

        for j in range(min(len(values), self.MATRIX_SIZE)):
            self.matrix[attacker_idx][j] = values[j]
            if attacker_idx < len(self.soldiers):
                key = f"{self.HIT_SOL_PREFIX}{j}"
                self.soldiers[attacker_idx][key] = values[j]

        return {"success": True, "count": min(len(values), self.MATRIX_SIZE)}

    def get_soldiers_data(self) -> List[dict]:
        """获取更新后的兵种数据（包含HitSol字段）"""
        return self.soldiers

    def analyze(self) -> dict:
        """分析相克关系"""
        if not self.matrix:
            return {}

        total = 0
        strong = 0
        neutral = 0
        weak = 0

        for i in range(len(self.matrix)):
            for j in range(len(self.matrix[i])):
                if i == j:
                    continue
                total += 1
                val = self.matrix[i][j]
                if val > 150:
                    strong += 1
                elif val < 50:
                    weak += 1
                else:
                    neutral += 1

        return {
            "total_relations": total,
            "strong": strong,
            "neutral": neutral,
            "weak": weak,
            "strong_pct": round(strong / total * 100, 1) if total > 0 else 0,
            "neutral_pct": round(neutral / total * 100, 1) if total > 0 else 0,
            "weak_pct": round(weak / total * 100, 1) if total > 0 else 0,
        }