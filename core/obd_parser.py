"""
OBD模型文件解析器 (v1.0)
- 解析群7 OBD格式 (Object Binary Data)
- 支持 BFSoldier.obd / BFGen.obd / BFEvent.obd / BFSpec.obd
- 提供可视化编辑接口
- 序列化保持原始格式

OBD文件结构:
[OBJECT]
Name = 兵种名称 (注释用)
Sequence = 70069 (模型编号，后两位=ObjID)
Space = 0, 100, 0 (X,Y,Z位移)
Sprite = 动作名, 文件引用, 帧数, ... (动画帧定义)
"""

import os
import re
from collections import OrderedDict
from typing import Dict, List, Tuple, Any, Optional


class OBDObject:
    """单个OBD OBJECT条目"""

    # 已知的Sprite动作类型
    SPRITE_TYPES = [
        "Wait1", "Wait2", "Wait3",           # 等待动画
        "Walk",                                # 行走
        "Run",                                 # 奔跑
        "Atk01", "Atk02", "Atk03", "Atk04",   # 普通攻击
        "Atk05", "Atk06", "Atk07", "Atk08",
        "Atk09", "Atk10", "Atk11", "Atk12",
        "Atk13", "Atk14", "Atk15", "Atk16",   # 16种攻击
        "SAtk01", "SAtk02", "SAtk03",          # 特殊攻击
        "Defend",                              # 防御
        "Hurt",                                # 受伤
        "Die",                                 # 死亡
        "S6Atk1201", "S6Atk1202",             # 必杀技暴雨
        "S6Atk1301", "S6Atk1302",             # 必杀技
    ]

    def __init__(self):
        self.name: str = ""
        self.sequence: int = 0
        self.space: Tuple[int, int, int] = (0, 0, 0)
        self.directory: str = ""  # 模型存放路径，如 \BFObj\BFSoldier\001
        self.sprites: Dict[str, List[str]] = OrderedDict()  # 动作名 -> 帧参数列表
        self.extra: Dict[str, str] = OrderedDict()  # 其他未知参数
        self._raw_lines: List[str] = []  # 原始行

    def get_sprite(self, sprite_type: str) -> Optional[List[str]]:
        return self.sprites.get(sprite_type)

    def set_sprite(self, sprite_type: str, params: List[str]):
        self.sprites[sprite_type] = params

    def get_obj_id(self) -> int:
        """从Sequence获取ObjID（后两位）"""
        return self.sequence % 100

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "sequence": self.sequence,
            "space": list(self.space),
            "directory": self.directory,
            "sprites": {k: v for k, v in self.sprites.items()},
            "extra": dict(self.extra),
            "obj_id": self.get_obj_id(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OBDObject":
        obj = cls()
        obj.name = data.get("name", "")
        obj.sequence = data.get("sequence", 0)
        obj.space = tuple(data.get("space", [0, 0, 0]))
        obj.directory = data.get("directory", "")
        obj.sprites = OrderedDict(data.get("sprites", {}))
        obj.extra = OrderedDict(data.get("extra", {}))
        return obj


class OBDParser:
    """
    群7 OBD文件解析器

    支持读取和写入以下OBD文件:
    - BFSoldier.obd: 兵种战场模型
    - BFGen.obd: 武将千人战造型
    - BFEvent.obd: NPC千人战造型
    - BFSpec.obd: 特殊兵种模型
    """

    OBD_FILES = {
        "bfsoldier": "BFSoldier.obd",
        "bfgen": "BFGen.obd",
        "bfevent": "BFEvent.obd",
        "bfspec": "BFSpec.obd",
        "bfweapon": "BFWeapon.obd",
        "bfhorse": "BFHorse.obd",
        "bfweaponlight": "BFWeaponLight.obd",
        "sfgen": "SFGen.obd",
        "sfevent": "SFEvent.obd",
        "sfbase": "SFBase.obd",
        "sftest": "SFTest.obd",
        "sfobject": "SFObject.obd",
        "bfbase": "BFBase.obd",
        "bfmagic": "BFMagic.obd",
        "bfobject": "BFObject.obd",
        "bftest": "BFTest.obd",
        "sfship": "SFShip.obd",
    }

    def __init__(self, game_path: str = None):
        self.game_path = game_path
        self.obd_dir = os.path.join(game_path, "Setting", "OBD") if game_path else ""
        self.objects: List[OBDObject] = []
        self._encoding = "gbk"

    def set_game_path(self, game_path: str):
        self.game_path = game_path
        self.obd_dir = os.path.join(game_path, "Setting", "OBD")

    def load(self, obd_type: str) -> List[OBDObject]:
        """加载指定类型的OBD文件"""
        filename = self.OBD_FILES.get(obd_type.lower())
        if not filename:
            raise ValueError(f"未知OBD类型: {obd_type}，支持: {list(self.OBD_FILES.keys())}")

        file_path = os.path.join(self.obd_dir, filename)
        if not os.path.exists(file_path):
            return []

        self.objects = self._parse_obd_file(file_path)
        return self.objects

    def _parse_obd_file(self, file_path: str) -> List[OBDObject]:
        """解析OBD文件"""
        objects = []
        current_obj = None

        with open(file_path, "r", encoding=self._encoding, errors="replace") as f:
            lines = f.readlines()

        for line in lines:
            stripped = line.strip()
            line_stored = line

            # 空行
            if not stripped:
                if current_obj:
                    current_obj._raw_lines.append(line_stored)
                continue

            # 注释行
            if stripped.startswith(";") or stripped.startswith("#"):
                if current_obj:
                    current_obj._raw_lines.append(line_stored)
                continue

            # [OBJECT] 头
            if stripped == "[OBJECT]":
                current_obj = OBDObject()
                current_obj._raw_lines.append(line_stored)
                objects.append(current_obj)
                continue

            if not current_obj:
                continue

            # 键值对
            kv_match = re.match(r"^([^=]+)=\s*(.*)$", stripped)
            if kv_match:
                key = kv_match.group(1).strip()
                value = kv_match.group(2).strip()

                if key == "Name":
                    current_obj.name = value
                elif key == "Sequence":
                    try:
                        current_obj.sequence = int(value)
                    except ValueError:
                        current_obj.sequence = 0
                elif key == "Space":
                    parts = [p.strip() for p in value.split(",")]
                    try:
                        current_obj.space = (
                            int(parts[0]) if len(parts) > 0 else 0,
                            int(parts[1]) if len(parts) > 1 else 0,
                            int(parts[2]) if len(parts) > 2 else 0,
                        )
                    except ValueError:
                        current_obj.space = (0, 0, 0)
                elif key == "Directory":
                    current_obj.directory = value
                elif key == "Sprite":
                    # Sprite = 动作名, 文件引用, 帧数, ...
                    parts = [p.strip() for p in value.split(",")]
                    if parts:
                        sprite_type = parts[0]
                        current_obj.sprites[sprite_type] = parts[1:] if len(parts) > 1 else []
                else:
                    current_obj.extra[key] = value

                current_obj._raw_lines.append(line_stored)
            else:
                current_obj._raw_lines.append(line_stored)

        return objects

    def save(self, obd_type: str, objects: List[OBDObject] = None) -> str:
        """保存OBD文件"""
        filename = self.OBD_FILES.get(obd_type.lower())
        if not filename:
            raise ValueError(f"未知OBD类型: {obd_type}")

        if objects is not None:
            self.objects = objects

        file_path = os.path.join(self.obd_dir, filename)
        os.makedirs(self.obd_dir, exist_ok=True)

        out_lines = []

        for obj in self.objects:
            out_lines.append("[OBJECT]\n")
            if obj.name:
                out_lines.append(f"Name = {obj.name}\n")
            out_lines.append(f"Sequence = {obj.sequence}\n")
            out_lines.append(f"Space = {obj.space[0]}, {obj.space[1]}, {obj.space[2]}\n")
            if obj.directory:
                out_lines.append(f"Directory = {obj.directory}\n")
            for sprite_type, params in obj.sprites.items():
                all_params = [sprite_type] + params
                out_lines.append(f"Sprite = {', '.join(all_params)}\n")
            for key, value in obj.extra.items():
                out_lines.append(f"{key} = {value}\n")
            out_lines.append("\n")

        with open(file_path, "w", encoding=self._encoding, newline="") as f:
            f.writelines(out_lines)

        return file_path

    def get_objects_by_sequence(self, sequence: int) -> List[OBDObject]:
        return [o for o in self.objects if o.sequence == sequence]

    def get_object_by_obj_id(self, obj_id: int) -> Optional[OBDObject]:
        """通过ObjID（后两位）查找"""
        for o in self.objects:
            if o.get_obj_id() == obj_id:
                return o
        return None

    def get_sprite_types(self) -> List[str]:
        """获取所有出现过的Sprite类型"""
        types = set()
        for o in self.objects:
            types.update(o.sprites.keys())
        return sorted(types)

    def get_all_sequences(self) -> List[int]:
        return [o.sequence for o in self.objects]

    def find_free_sequence(self, start: int = 70001) -> int:
        existing = set(self.get_all_sequences())
        for i in range(start, 99999):
            if i not in existing:
                return i
        raise ValueError("OBD序列号已满")

    def find_by_sequence(self, sequence: int) -> Optional[OBDObject]:
        """根据Sequence查找对象"""
        for obj in self.objects:
            if obj.sequence == sequence:
                return obj
        return None

    def to_dict_list(self) -> List[dict]:
        return [o.to_dict() for o in self.objects]

    @classmethod
    def get_info(cls) -> dict:
        return {
            "format": "OBD (Object Binary Data - 群7模型描述)",
            "files": cls.OBD_FILES,
            "sprite_types": OBDObject.SPRITE_TYPES,
            "description": "定义兵种/武将/NPC的千人战模型动画序列",
        }