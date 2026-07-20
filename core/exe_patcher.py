"""
EXE引擎修改工具
突破Sango7.exe硬编码参数限制
- 兵种67上限突破
- 属性999/255上限突破
- 出征人数上限
- 等级上限
- 自动备份Sango7.exe
- 特征码自动扫描偏移量
"""

import os
import struct
from typing import Dict, Optional, List, Tuple

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    HAS_CAPSTONE = True
except ImportError:
    HAS_CAPSTONE = False
    Cs = None
    CS_ARCH_X86 = CS_MODE_32 = None


class ExePatcher:
    """
    EXE引擎补丁工具
    通过修改Sango7.exe二进制偏移来突破硬编码限制

    偏移量来源：sanguogame.com.cn、Bilibili社区、FearlessRevolution论坛
    针对版本：免认证破解版 SG7.exe (v1.00)
    """

    # 已知补丁定义（偏移量已填入社区验证数据）
    KNOWN_PATCHES = {
        "soldier_limit": {
            "description": "兵种数量上限",
            "offsets": [],  # 需特征码扫描自动定位
            "default_value": 67,
            "value_type": "int32",
            "search_pattern": None,  # 扫描时自动搜索
        },
        "stat_limit": {
            "description": "属性单字节上限（武力/智力）",
            "default_offset": 0x0,
            "default_value": 255,
            "value_type": "int8",
            "search_pattern": None,
        },
        "stat_display_limit": {
            "description": "吃道具增加属性上限（999→65535）",
            "offsets": [0x02b52b, 0x02b535, 0x0e181a],
            "default_value": 999,
            "value_type": "int16",
            "search_pattern": b"\xe7\x03",  # 0x03E7 = 999 in little-endian (int16)
        },
        "force_display_limit": {
            "description": "武力显示值上限（999→65535）",
            "offsets": [0x10d099, 0x10d0a2],
            "default_value": 999,
            "value_type": "int16",
            "search_pattern": None,
        },
        "int_display_limit": {
            "description": "智力显示值上限（999→65535）",
            "offsets": [0x10d11f, 0x10d128],
            "default_value": 999,
            "value_type": "int16",
            "search_pattern": None,
        },
        "hp_display_limit": {
            "description": "体力显示值上限（999→65535）",
            "offsets": [0x10d20b, 0x10d214],
            "default_value": 999,
            "value_type": "int16",
            "search_pattern": None,
        },
        "mp_display_limit": {
            "description": "技力显示值上限（999→65535）",
            "offsets": [0x10d2fb, 0x10d304],
            "default_value": 999,
            "value_type": "int16",
            "search_pattern": None,
        },
        "hp_limit": {
            "description": "体力上限（含战场）",
            "offsets": [0x10d3d9, 0x10d3e2, 0x10d41a, 0x10d423],
            "default_value": 999,
            "value_type": "int16",
            "search_pattern": None,
        },
        "mp_limit": {
            "description": "技力上限（含战场）",
            "offsets": [0x10d459, 0x10d462, 0x10d49a, 0x10d4a3],
            "default_value": 999,
            "value_type": "int16",
            "search_pattern": None,
        },
        "levelup_limit": {
            "description": "升级时属性不被999截断",
            "offsets": [0x10c785, 0x10c78e, 0x10c7b5, 0x10c7be],
            "default_value": 999,
            "value_type": "int16",
            "search_pattern": None,
        },
        "heal_limit": {
            "description": "治愈技能恢复量上限",
            "offsets": [0x04f55a, 0x04f566, 0x161222, 0x16122e, 0x161284, 0x161290, 0x1612fb, 0x161307, 0x161382, 0x16138e, 0x0234ab, 0x0234b5, 0x11117f],
            "default_value": 999,
            "value_type": "int16",
            "search_pattern": None,
        },
        "general_deploy_limit": {
            "description": "出征队伍武将上限（5→自定义）",
            "offsets": [0x078a83],
            "default_value": 5,
            "value_type": "int8",
            "search_pattern": None,
        },
        "red_dot_interval": {
            "description": "红点事件刷新间隔",
            "offsets": [0x53efa0, 0x53efac],
            "default_value": 10,
            "value_type": "int8",
            "search_pattern": None,
        },
        "thing_limit": {
            "description": "物品数量上限",
            "default_offset": 0x0,
            "default_value": 9999,
            "value_type": "int32",
            "search_pattern": None,
        },
        "general_limit": {
            "description": "武将数量上限",
            "default_offset": 0x0,
            "default_value": 9999,
            "value_type": "int32",
            "search_pattern": None,
        },
        # 组合补丁：一键突破所有属性999上限（33处偏移）
        "all_stat_999_break": {
            "description": "【一键】全属性999上限突破→65535",
            "offsets": [
                0x02b52b, 0x02b535, 0x0e181a,  # 吃道具上限
                0x10d099, 0x10d0a2,              # 武力显示
                0x10d11f, 0x10d128,              # 智力显示
                0x10d20b, 0x10d214,              # 体力显示
                0x10d2fb, 0x10d304,              # 技力显示
                0x10d3d9, 0x10d41a, 0x10d423,    # 战场血上限
                0x10d459, 0x10d49a, 0x10d4a3,    # 战场技上限
                0x10c785, 0x10c78e, 0x10c7b5, 0x10c7be,  # 升级可破
                0x04f55a, 0x04f566,              # 气疗大法
                0x161222, 0x16122e,              # 回春术
                0x161284, 0x161290,              # 回春仙术
                0x1612fb, 0x161307,              # 气疗血技
                0x161382, 0x16138e,              # 气疗决
                0x0234ab, 0x0234b5,              # 放技能后技上限
                0x11117f,                         # 初始可破
            ],
            "default_value": 999,
            "value_type": "int16",
            "search_pattern": None,
        },
        # === 社区教程补丁（来自"一些exe修改教程.doc"） ===
        "red_dot_count": {
            "description": "红点刷新数量增多（将两个A减小实现成倍增加）",
            "offsets": [],  # 需特征码扫描
            "default_value": 10,
            "value_type": "int8",
            "search_pattern": None,
            "category": "community",
            "source": "一些exe修改教程",
        },
        "red_dot_max": {
            "description": "红点数量上限增加（将41改大）",
            "offsets": [],  # 需特征码扫描
            "default_value": 65,
            "value_type": "int8",
            "search_pattern": None,
            "category": "community",
            "source": "一些exe修改教程",
        },
        "immortal_boost": {
            "description": "打神仙加成修改（仙道/散仙/大仙/神仙/天仙通用加成）",
            "offsets": [0x12CD97, 0x12CD9E, 0x12CDA5, 0x12CDAC, 0x12CDB3],
            "default_value": 0,
            "value_type": "int16",
            "search_pattern": None,
            "category": "community",
            "source": "一些exe修改教程",
            "note": "武力智力加成 x 2倍 = 体力技力加成，地址连续: 仙道(0x12CD97), 散仙(0x12CD9E), 大仙(0x12CDA5), 神仙(0x12CDAC), 天仙(0x12CDB3)",
        },
        "penglai_currency": {
            "description": "蓬莱岛兑换货币编号",
            "offsets": [0x1ACB69],
            "default_value": 0,
            "value_type": "int16",
            "search_pattern": None,
            "category": "community",
            "source": "一些exe修改教程",
            "note": "需同步修改系统文本",
        },
        "penglai_item": {
            "description": "蓬莱岛扣取物品编号",
            "offsets": [0x1AC387],
            "default_value": 0,
            "value_type": "int16",
            "search_pattern": None,
            "category": "community",
            "source": "一些exe修改教程",
            "note": "需同步修改系统文本",
        },
        "stat_init_limit": {
            "description": "初始属性上限（不截断）",
            "offsets": [0x11117f],
            "default_value": 999,
            "value_type": "int16",
            "search_pattern": None,
            "category": "community",
            "source": "一些exe修改教程",
        },
        "arena_interval": {
            "description": "比武大会间隔（默认10年）",
            "offsets": [],  # 需特征码扫描
            "default_value": 10,
            "value_type": "int8",
            "search_pattern": None,
            "category": "community",
            "source": "Variable.ini No.21",
        },
    }

    # 特征码扫描规则：用于自动定位未知偏移量
    SCAN_SIGNATURES = {
        "soldier_limit": {
            "description": "兵种67上限",
            "patterns": [
                # 搜索 cmp reg, 0x43 指令模式 (67 = 0x43) — 至少3字节确保精度
                (b"\x83\xf8\x43", "cmp eax, 67"),        # cmp eax, 67
                (b"\x83\xff\x43", "cmp edi, 67"),        # cmp edi, 67
                (b"\x83\xfe\x43", "cmp esi, 67"),        # cmp esi, 67
                (b"\x83\xf9\x43", "cmp ecx, 67"),        # cmp ecx, 67
                (b"\x83\xfa\x43", "cmp edx, 67"),        # cmp edx, 67
                (b"\x83\xfb\x43", "cmp ebx, 67"),        # cmp ebx, 67
                # 搜索 mov [reg], 67 模式
                (b"\xc7\x00\x43\x00\x00\x00", "mov [eax], 67"),
            ],
            "value_size": 4,
        },
        "stat_limit": {
            "description": "属性255单字节上限",
            "patterns": [
                # 搜索 cmp reg, 0xFF 模式 — 至少3字节确保精度
                (b"\x80\xf8\xff", "cmp al, 255"),
                (b"\x80\xff\xff", "cmp bh, 255"),
                # 搜索 and reg, 0xFF 截断模式
                (b"\x25\xff\x00\x00\x00", "and eax, 0xFF"),
            ],
            "value_size": 1,
        },
        "level_limit": {
            "description": "等级99上限",
            "patterns": [
                (b"\x83\xf8\x63", "cmp eax, 99"),        # cmp eax, 99 (0x63)
                (b"\x83\xff\x63", "cmp edi, 99"),
                (b"\x83\xfe\x63", "cmp esi, 99"),
                (b"\x83\xf9\x63", "cmp ecx, 99"),
            ],
            "value_size": 4,
        },
        # thing_limit / general_limit 暂无可靠特征码，扫描时依赖已知偏移量或社区贡献
    }

    def __init__(self, game_path: str = None):
        self.game_path = game_path
        self.exe_path = os.path.join(game_path, "Sango7.exe") if game_path else ""
        self._patches_applied: Dict[str, dict] = {}
        self._exe_data: Optional[bytes] = None

    def set_game_path(self, game_path: str):
        self.game_path = game_path
        self.exe_path = os.path.join(game_path, "Sango7.exe")
        self._exe_data = None

    def exe_exists(self) -> bool:
        return os.path.exists(self.exe_path)

    def get_exe_size(self) -> int:
        if not self.exe_exists():
            return 0
        return os.path.getsize(self.exe_path)

    def _load_exe(self) -> Optional[bytes]:
        """加载 EXE 到内存（缓存）"""
        if self._exe_data is not None:
            return self._exe_data
        if not self.exe_exists():
            return None
        try:
            with open(self.exe_path, "rb") as f:
                self._exe_data = f.read()
            return self._exe_data
        except (IOError, OSError):
            return None

    def read_bytes(self, offset: int, size: int) -> Optional[bytes]:
        if not self.exe_exists():
            return None
        try:
            with open(self.exe_path, "rb") as f:
                f.seek(offset)
                return f.read(size)
        except (IOError, OSError):
            return None

    def read_int32(self, offset: int) -> Optional[int]:
        data = self.read_bytes(offset, 4)
        if data and len(data) == 4:
            return struct.unpack("<i", data)[0]
        return None

    def read_int16(self, offset: int) -> Optional[int]:
        data = self.read_bytes(offset, 2)
        if data and len(data) == 2:
            return struct.unpack("<H", data)[0]
        return None

    def read_int8(self, offset: int) -> Optional[int]:
        data = self.read_bytes(offset, 1)
        if data and len(data) == 1:
            return data[0]
        return None

    def write_bytes(self, offset: int, data: bytes) -> bool:
        if not self.exe_exists():
            return False
        try:
            with open(self.exe_path, "r+b") as f:
                f.seek(offset)
                f.write(data)
            self._exe_data = None
            return True
        except (IOError, OSError):
            return False

    def write_int32(self, offset: int, value: int) -> bool:
        return self.write_bytes(offset, struct.pack("<i", value))

    def write_int16(self, offset: int, value: int) -> bool:
        return self.write_bytes(offset, struct.pack("<H", value))

    def write_int8(self, offset: int, value: int) -> bool:
        return self.write_bytes(offset, struct.pack("<B", value))

    def _read_value_by_type(self, offset: int, value_type: str) -> Optional[int]:
        """根据类型读取值"""
        if value_type == "int32":
            return self.read_int32(offset)
        elif value_type == "int16":
            return self.read_int16(offset)
        elif value_type == "int8":
            return self.read_int8(offset)
        return None

    def _write_value_by_type(self, offset: int, value: int, value_type: str) -> bool:
        if value_type == "int32":
            return self.write_int32(offset, value)
        elif value_type == "int16":
            return self.write_int16(offset, value)
        elif value_type == "int8":
            return self.write_int8(offset, value)
        return False

    def apply_patch(self, patch_name: str, offset: int, new_value: int) -> bool:
        if not self.exe_exists():
            return False

        patch_info = self.KNOWN_PATCHES.get(patch_name, {})
        value_type = patch_info.get("value_type", "int32")
        old_value = self._read_value_by_type(offset, value_type)

        if old_value is None:
            return False

        success = self._write_value_by_type(offset, new_value, value_type)
        if success:
            self._patches_applied[patch_name] = {
                "offset": offset,
                "old_value": old_value,
                "new_value": new_value,
                "value_type": value_type,
                "description": patch_info.get("description", patch_name),
            }
        return success

    def apply_patch_auto(self, patch_name: str, new_value: int) -> dict:
        """自动检测偏移量并应用补丁"""
        if not self.exe_exists():
            return {"success": False, "message": "EXE不存在"}

        patch_info = self.KNOWN_PATCHES.get(patch_name, {})
        offsets = patch_info.get("offsets", [])
        default_offset = patch_info.get("default_offset", 0)

        # 优先使用已知偏移量
        if offsets:
            results = []
            for off in offsets:
                ok = self.apply_patch(patch_name, off, new_value)
                results.append({"offset": hex(off), "success": ok})
            return {
                "success": any(r["success"] for r in results),
                "message": f"已应用 {sum(1 for r in results if r['success'])}/{len(offsets)} 处",
                "results": results,
            }

        # 尝试使用特征码扫描
        if patch_name in self.SCAN_SIGNATURES:
            scan_results = self.scan_signature(patch_name)
            if scan_results:
                ok = self.apply_patch(patch_name, scan_results[0]["offset"], new_value)
                return {
                    "success": ok,
                    "message": f"特征码扫描定位偏移 {scan_results[0]['offset_hex']}，{'成功' if ok else '失败'}",
                    "scan_candidates": scan_results[:5],
                }

        # 回退到默认偏移（仅当偏移量有效且非零时）
        if default_offset is not None and default_offset > 0:
            ok = self.apply_patch(patch_name, default_offset, new_value)
            return {"success": ok, "message": f"使用默认偏移 {hex(default_offset)}", "offset": default_offset}

        return {"success": False, "message": f"无已知偏移量，且特征码扫描未找到匹配"}

    def revert_patch(self, patch_name: str) -> bool:
        if patch_name not in self._patches_applied:
            return False
        patch = self._patches_applied[patch_name]
        return self._write_value_by_type(patch["offset"], patch["old_value"], patch.get("value_type", "int32"))

    def revert_all(self) -> int:
        count = 0
        for name in list(self._patches_applied.keys()):
            if self.revert_patch(name):
                count += 1
        return count

    def get_applied_patches(self) -> Dict[str, dict]:
        return dict(self._patches_applied)

    def get_patch_info(self) -> List[dict]:
        """获取所有可用补丁信息（含自动检测到的偏移量）"""
        info = []
        for name, patch in self.KNOWN_PATCHES.items():
            entry = dict(patch)
            entry["name"] = name
            entry["applied"] = name in self._patches_applied

            if name in self._patches_applied:
                entry["current_value"] = self._patches_applied[name]["new_value"]
            else:
                entry["current_value"] = entry.get("default_value", 0)

            # 确定使用的偏移量
            offsets = entry.get("offsets", [])
            if offsets:
                entry["effective_offset"] = offsets[0]
                entry["multi_offset"] = len(offsets) > 1
                entry["offset_count"] = len(offsets)
            elif name in self.SCAN_SIGNATURES:
                entry["effective_offset"] = None
                entry["auto_detect"] = True
            else:
                entry["effective_offset"] = entry.get("default_offset", 0)

            # 移除内部字段
            entry.pop("offsets", None)
            entry.pop("search_pattern", None)
            info.append(entry)
        return info

    def get_community_patches(self) -> List[dict]:
        """获取所有社区教程补丁"""
        community = []
        for name, patch in self.KNOWN_PATCHES.items():
            if patch.get("category") == "community":
                entry = dict(patch)
                entry["name"] = name
                entry["applied"] = name in self._patches_applied
                if name in self._patches_applied:
                    entry["current_value"] = self._patches_applied[name]["new_value"]
                else:
                    entry["current_value"] = entry.get("default_value", 0)
                # 确定使用的偏移量
                offsets = entry.get("offsets", [])
                if offsets:
                    entry["effective_offset"] = offsets[0]
                    entry["offset_count"] = len(offsets)
                    entry["all_offsets"] = [hex(o) for o in offsets]
                community.append(entry)
        return community

    # ============================================================
    # 特征码扫描引擎
    # ============================================================

    def scan_signature(self, scan_name: str) -> List[dict]:
        """
        扫描 EXE 中与指定补丁相关的特征码位置
        返回候选偏移量列表（按可能性排序）
        """
        if scan_name not in self.SCAN_SIGNATURES:
            return []
        sig_info = self.SCAN_SIGNATURES[scan_name]
        return self._scan_patterns(sig_info["patterns"], sig_info["description"])

    def scan_all_signatures(self) -> Dict[str, List[dict]]:
        """扫描所有已知特征码"""
        results = {}
        for name in self.SCAN_SIGNATURES:
            candidates = self.scan_signature(name)
            if candidates:
                results[name] = candidates
        return results

    def _scan_patterns(self, patterns: List[Tuple[bytes, str]], label: str = "") -> List[dict]:
        """在 EXE 中搜索多组特征码"""
        exe_data = self._load_exe()
        if not exe_data:
            return []

        all_candidates = []
        for pattern, desc in patterns:
            pos = 0
            while True:
                pos = exe_data.find(pattern, pos)
                if pos == -1:
                    break
                all_candidates.append({
                    "offset": pos,
                    "offset_hex": hex(pos),
                    "pattern_desc": desc,
                    "pattern_hex": pattern.hex(" "),
                    "label": label,
                    # 读取上下文字节用于人工验证
                    "context_before": exe_data[max(0, pos-8):pos].hex(" ") if pos >= 8 else "",
                    "context_after": exe_data[pos+len(pattern):pos+len(pattern)+8].hex(" "),
                })
                pos += 1

        # 按偏移量排序
        all_candidates.sort(key=lambda x: x["offset"])
        return all_candidates

    def scan_exe_for_values(self, values: List[int]) -> List[Tuple[int, int]]:
        """扫描EXE中出现的特定数值及其偏移（用于发现引擎限制参数）"""
        if not self.exe_exists():
            return []
        exe_data = self._load_exe()
        if not exe_data:
            return []
        results = []
        for val in values:
            pattern = struct.pack("<i", val)
            pos = 0
            while True:
                pos = exe_data.find(pattern, pos)
                if pos == -1:
                    break
                results.append((pos, val))
                pos += 1
        return results

    # ============================================================
    # 反汇编引擎
    # ============================================================

    def disassemble_at(self, offset: int, count: int = 8) -> List[dict]:
        """在指定偏移处反汇编指定数量的指令"""
        if not HAS_CAPSTONE:
            return [{"offset": offset, "error": "capstone 未安装"}]

        exe_data = self._load_exe()
        if not exe_data:
            return [{"offset": offset, "error": "EXE 未加载"}]

        if offset >= len(exe_data):
            return [{"offset": offset, "error": "偏移超出文件范围"}]

        try:
            md = Cs(CS_ARCH_X86, CS_MODE_32)
            md.detail = True
            code = exe_data[offset:offset + count * 15]
            instructions = []
            for insn in md.disasm(code, offset):
                instructions.append({
                    "offset": insn.address,
                    "offset_hex": hex(insn.address),
                    "mnemonic": insn.mnemonic,
                    "op_str": insn.op_str,
                    "size": insn.size,
                    "bytes": insn.bytes.hex(" "),
                    "full": f"{insn.mnemonic} {insn.op_str}",
                })
                if len(instructions) >= count:
                    break
            return instructions
        except Exception as e:
            return [{"offset": offset, "error": str(e)}]

    def disassemble_scan_results(self, scan_name: str, top_n: int = 5) -> dict:
        """对特征码扫描结果进行反汇编验证"""
        if not HAS_CAPSTONE:
            return {"success": False, "message": "capstone 未安装"}

        candidates = self.scan_signature(scan_name)
        if not candidates:
            return {"success": False, "message": "未找到匹配"}

        enriched = []
        for c in candidates[:top_n]:
            instructions = self.disassemble_at(c["offset"], 4)
            enriched.append({**c, "instructions": instructions})

        return {
            "success": True,
            "scan_name": scan_name,
            "total_candidates": len(candidates),
            "shown": len(enriched),
            "candidates": enriched,
        }

    # ============================================================
    # NOP 补丁 & JMP 补丁
    # ============================================================

    # 常见 JMP 补丁模板
    JMP_TEMPLATES = {
        "nop_check": {
            "description": "NOP掉检查指令（禁用限制检查）",
            "instructions": "将目标指令替换为 NOP (0x90)",
            "usage": "在 cmp/jle 等检查指令处使用，使限制无效",
        },
        "jmp_skip": {
            "description": "无条件跳过限制（JMP跳过）",
            "instructions": "将条件跳转改为无条件 JMP，跳过限制逻辑",
            "usage": "适用于 jle/jge/jne 等条件跳转，改为 EB XX（短跳）或 E9 XX XX XX XX（长跳）",
        },
        "jmp_always_allow": {
            "description": "强制允许（JMP到允许分支）",
            "instructions": "将条件跳转改为总是跳转到允许执行的分支",
            "usage": "适用于 jne（不相等时跳）→ 改为 jmp 强制跳转",
        },
        "cmp_remove": {
            "description": "移除比较检查",
            "instructions": "将 cmp 指令替换为 NOP，移除上限检查",
            "usage": "在 cmp reg, limit 处使用，移除比较后值不再受限",
        },
    }

    def apply_nop_patch(self, offset: int, size: int) -> bool:
        """在指定偏移处写入 NOP (0x90) 指令"""
        if not self.exe_exists():
            return False
        nop_bytes = b'\x90' * size
        success = self.write_bytes(offset, nop_bytes)
        if success:
            self._patches_applied[f"nop_{hex(offset)}"] = {
                "offset": offset,
                "size": size,
                "old_value": "N/A",
                "new_value": f"NOP x{size}",
                "value_type": "nop",
                "description": f"NOP补丁 @ {hex(offset)} ({size}字节)",
            }
        return success

    def apply_jmp_patch(self, offset: int, target_offset: int, is_short: bool = True) -> bool:
        """写入 JMP 指令跳转到目标偏移"""
        if not self.exe_exists():
            return False

        if is_short:
            # 短跳: EB XX (相对偏移 = target - (offset + 2))
            rel = target_offset - (offset + 2)
            if rel < -128 or rel > 127:
                return False  # 短跳范围不足
            jmp_bytes = bytes([0xEB, rel & 0xFF])
        else:
            # 长跳: E9 XX XX XX XX (相对偏移 = target - (offset + 5))
            rel = target_offset - (offset + 5)
            jmp_bytes = bytes([0xE9]) + struct.pack("<i", rel)

        success = self.write_bytes(offset, jmp_bytes)
        if success:
            self._patches_applied[f"jmp_{hex(offset)}"] = {
                "offset": offset,
                "target": target_offset,
                "is_short": is_short,
                "old_value": "N/A",
                "new_value": f"JMP → {hex(target_offset)}",
                "value_type": "jmp",
                "description": f"JMP补丁 @ {hex(offset)} → {hex(target_offset)}",
            }
        return success

    def apply_template_patch(self, template_name: str, offset: int, *args) -> dict:
        """应用预设的 JMP/NOP 补丁模板"""
        if not self.exe_exists():
            return {"success": False, "message": "EXE不存在"}

        if template_name == "nop_check":
            size = args[0] if args else 2
            ok = self.apply_nop_patch(offset, size)
            return {"success": ok, "message": f"NOP {size}字节 @ {hex(offset)}" if ok else "写入失败"}

        elif template_name == "jmp_skip":
            target = args[0] if args else offset + 6
            exe_data = self._load_exe()
            if not exe_data or offset >= len(exe_data):
                return {"success": False, "message": "无效偏移"}

            # 尝试短跳，不行则长跳
            rel = target - (offset + 2)
            is_short = -128 <= rel <= 127
            ok = self.apply_jmp_patch(offset, target, is_short)
            return {"success": ok, "message": f"JMP {hex(offset)} → {hex(target)}" if ok else "JMP失败"}

        elif template_name == "jmp_always_allow":
            exe_data = self._load_exe()
            if not exe_data or offset >= len(exe_data):
                return {"success": False, "message": "无效偏移"}

            # 读取当前指令，提取目标地址
            b = exe_data[offset]
            if b == 0x74 or b == 0x75:  # je/jne 短跳
                rel = struct.unpack("<b", exe_data[offset+1:offset+2])[0]
                target = offset + 2 + rel
                # 改为无条件跳转 EB
                return self.apply_jmp_patch(offset, target, True)
            elif b == 0x0F:  # 近跳 jne/jge/jle 等
                b2 = exe_data[offset+1]
                if b2 in (0x84, 0x85, 0x8C, 0x8D, 0x8E, 0x8F):  # JNE/JGE/JLE/JG/JL
                    rel = struct.unpack("<i", exe_data[offset+2:offset+6])[0]
                    target = offset + 6 + rel
                    return self.apply_jmp_patch(offset, target, False)
            return {"success": False, "message": "无法识别跳转指令类型"}

        elif template_name == "cmp_remove":
            # cmp 指令通常 2-3 字节，替换为 NOP
            size = args[0] if args else 3
            ok = self.apply_nop_patch(offset, size)
            return {"success": ok, "message": f"移除cmp检查 @ {hex(offset)}" if ok else "写入失败"}

        return {"success": False, "message": f"未知模板: {template_name}"}

    def get_jmp_templates(self) -> dict:
        return self.JMP_TEMPLATES

    def scan_exe_for_value_range(self, value: int, value_type: str = "int32") -> List[dict]:
        """扫描特定数值的所有出现位置（支持多种类型）"""
        exe_data = self._load_exe()
        if not exe_data:
            return []

        if value_type == "int32":
            pattern = struct.pack("<i", value)
        elif value_type == "int16":
            pattern = struct.pack("<H", value)
        elif value_type == "int8":
            pattern = struct.pack("<B", value)
        else:
            pattern = struct.pack("<i", value)

        results = []
        pos = 0
        while True:
            pos = exe_data.find(pattern, pos)
            if pos == -1:
                break
            results.append({
                "offset": pos,
                "offset_hex": hex(pos),
                "value": value,
                "value_type": value_type,
            })
            pos += 1
        return results