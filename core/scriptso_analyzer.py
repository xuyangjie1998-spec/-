"""
Script.so 分析器
- 分析三国群英传7的 Script.so 共享库文件
- 提取可读字符串（函数名、技能引用等）
- 十六进制查看
- 已知结构标记识别

Script.so 是游戏引擎加载的编译后共享库，包含：
- 游戏脚本逻辑（编译后的字节码）
- 字符串表（技能名、特性名、事件引用等）
- 函数导出表

MOD创作者通常不直接修改 Script.so，但通过分析其字符串
可以了解游戏内部机制。部分高级MOD通过 hex 编辑 Script.so
来修改特定行为。

参考：
- 游侠论坛 3g 论坛：Script.so 中包含 GenSkillStart/BFMagic 等字符串引用
- 铁血丹心论坛：Script.so 放入 Script/ 文件夹可被游戏加载
"""

import os
import struct
import re
from typing import Dict, List, Optional, Tuple

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB
    from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_OP_REG
    HAS_CAPSTONE = True
except ImportError:
    HAS_CAPSTONE = False


class ScriptSOAnalyzer:
    """Script.so 分析器"""

    # 已知的 Script.so 中的字符串模式
    KNOWN_PATTERNS = [
        (r"GenSkillStart\d+", "个人特性引用"),
        (r"BFMagic\d+", "武将技引用"),
        (r"SFMagic\d+", "军师技引用"),
        (r"ArmySkill\d+", "主将特性引用"),
        (r"ArmyGroupSkill\d+", "元帅特性引用"),
        (r"General\d+", "武将编号引用"),
        (r"Soldier\d+", "兵种编号引用"),
        (r"Thing\d+", "物品编号引用"),
        (r"Title\d+", "官职编号引用"),
        (r"City\d+", "城池编号引用"),
        (r"Event\d+", "事件编号引用"),
        (r"History\d+", "历史事件引用"),
        (r"Formation\d+", "阵形引用"),
        (r"Weapon\d+", "武器引用"),
        (r"Horse\d+", "坐骑引用"),
        (r"SuperAtk\d+", "必杀技引用"),
        (r"Level\d+", "等级引用"),
        (r"Race\d+", "种族引用"),
        (r"Nation\d+", "势力引用"),
        (r"Script_\w+", "脚本函数"),
        (r"On\w+Event", "事件处理函数"),
        (r"Calc\w+", "计算函数"),
        (r"Get\w+", "取值函数"),
        (r"Set\w+", "设值函数"),
        (r"Check\w+", "检查函数"),
        (r"Battle\w+", "战斗相关"),
        (r"Map\w+", "地图相关"),
        (r"AI\w+", "AI相关"),
        (r"Load\w+", "加载函数"),
        (r"Save\w+", "保存函数"),
        (r"Init\w+", "初始化函数"),
        (r"Update\w+", "更新函数"),
        (r"Draw\w+", "绘制函数"),
        (r"Play\w+", "播放函数"),
        (r"Sound\w+", "音效相关"),
        (r"Effect\w+", "特效相关"),
    ]

    # ELF 魔数
    ELF_MAGIC = b"\x7fELF"

    def __init__(self, game_path: str = None):
        self.game_path = game_path
        self.script_dir = os.path.join(game_path, "Script") if game_path else ""
        self._script_so_path = os.path.join(self.script_dir, "Script.so") if game_path else ""

    def set_game_path(self, game_path: str):
        self.game_path = game_path
        self.script_dir = os.path.join(game_path, "Script")
        self._script_so_path = os.path.join(self.script_dir, "Script.so")

    def script_so_exists(self) -> bool:
        return os.path.exists(self._script_so_path)

    def get_script_so_info(self) -> dict:
        """获取 Script.so 基本信息"""
        if not self.script_so_exists():
            return {
                "exists": False,
                "path": self._script_so_path,
                "message": "Script.so 不存在",
            }

        size = os.path.getsize(self._script_so_path)
        mtime = os.path.getmtime(self._script_so_path)

        info = {
            "exists": True,
            "path": self._script_so_path,
            "size": size,
            "size_kb": round(size / 1024, 1),
            "size_mb": round(size / (1024 * 1024), 2),
            "modified": mtime,
            "is_elf": False,
            "elf_info": {},
            "has_strings": False,
            "string_count": 0,
            "known_patterns_found": [],
        }

        try:
            with open(self._script_so_path, "rb") as f:
                header = f.read(64)

            # 检测是否为 ELF 文件
            if header[:4] == self.ELF_MAGIC:
                info["is_elf"] = True
                info["elf_info"] = self._parse_elf_header(header)
        except (IOError, OSError):
            pass

        return info

    def _parse_elf_header(self, header: bytes) -> dict:
        """解析 ELF 头部"""
        elf = {}
        try:
            # e_ident[EI_CLASS] at offset 4
            elf_class = header[4]
            elf["class"] = {1: "ELF32", 2: "ELF64"}.get(elf_class, f"Unknown({elf_class})")

            # e_ident[EI_DATA] at offset 5
            elf_data = header[5]
            elf["endian"] = {1: "Little-Endian", 2: "Big-Endian"}.get(elf_data, f"Unknown({elf_data})")

            # e_ident[EI_VERSION] at offset 6
            elf["version"] = header[6]

            # e_ident[EI_OSABI] at offset 7
            osabi = header[7]
            elf["osabi"] = {0: "UNIX System V", 3: "Linux"}.get(osabi, f"Other({osabi})")

            # e_type at offset 16
            if elf["class"] == "ELF32":
                e_type = struct.unpack_from("<H", header, 16)[0]
                e_machine = struct.unpack_from("<H", header, 18)[0]
            else:
                e_type = struct.unpack_from("<H", header, 16)[0]
                e_machine = struct.unpack_from("<H", header, 18)[0]

            elf["type"] = {1: "REL (可重定位)", 2: "EXEC (可执行)", 3: "DYN (共享库)"}.get(e_type, f"Unknown({e_type})")
            elf["machine"] = {3: "i386 (x86)", 0x28: "ARM", 0x3E: "x86-64"}.get(e_machine, f"Unknown({e_machine})")

        except (struct.error, IndexError) as e:
            elf["parse_error"] = str(e)

        return elf

    def parse_sections(self) -> dict:
        """解析 ELF Section Header 段表，返回所有段信息"""
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}
        try:
            with open(self._script_so_path, "rb") as f:
                data = f.read()
        except (IOError, OSError) as e:
            return {"success": False, "message": f"读取失败: {e}"}
        if data[:4] != self.ELF_MAGIC:
            return {"success": False, "message": "不是有效的ELF文件"}

        ei_class = data[4]
        if ei_class == 1:
            is_64 = False
        elif ei_class == 2:
            is_64 = True
        else:
            return {"success": False, "message": "不支持的ELF类型"}

        if is_64:
            return self._parse_sections_64(data)
        else:
            return self._parse_sections_32(data)

    def _parse_sections_32(self, data: bytes) -> dict:
        import struct
        # ELF32 Header: e_shoff at offset 32 (4 bytes), e_shentsize at 46 (2), e_shnum at 48 (2), e_shstrndx at 50 (2)
        e_shoff = struct.unpack_from("<I", data, 32)[0]
        e_shentsize = struct.unpack_from("<H", data, 46)[0]
        e_shnum = struct.unpack_from("<H", data, 48)[0]
        e_shstrndx = struct.unpack_from("<H", data, 50)[0]

        sections = []
        shstrtab_offset = None
        for i in range(e_shnum):
            off = e_shoff + i * e_shentsize
            sh_name = struct.unpack_from("<I", data, off)[0]
            sh_type = struct.unpack_from("<I", data, off + 4)[0]
            sh_flags = struct.unpack_from("<I", data, off + 8)[0]
            sh_addr = struct.unpack_from("<I", data, off + 12)[0]
            sh_offset = struct.unpack_from("<I", data, off + 16)[0]
            sh_size = struct.unpack_from("<I", data, off + 20)[0]
            sh_link = struct.unpack_from("<I", data, off + 24)[0]
            sh_info = struct.unpack_from("<I", data, off + 28)[0]
            sh_addralign = struct.unpack_from("<I", data, off + 32)[0]
            sh_entsize = struct.unpack_from("<I", data, off + 36)[0]

            type_names = {0:"NULL",1:"PROGBITS",2:"SYMTAB",3:"STRTAB",4:"RELA",5:"HASH",6:"DYNAMIC",7:"NOTE",8:"NOBITS",9:"REL",10:"SHLIB",11:"DYNSYM",14:"INIT_ARRAY",15:"FINI_ARRAY",16:"PREINIT_ARRAY",17:"GROUP",18:"SYMTAB_SHNDX"}
            flag_names = []
            if sh_flags & 0x1: flag_names.append("W")
            if sh_flags & 0x2: flag_names.append("A")
            if sh_flags & 0x4: flag_names.append("X")

            sections.append({
                "index": i, "name_idx": sh_name,
                "type": sh_type, "type_name": type_names.get(sh_type, f"UNKNOWN({sh_type})"),
                "flags": sh_flags, "flags_str": "".join(flag_names),
                "addr": sh_addr, "addr_hex": "0x{:X}".format(sh_addr),
                "offset": sh_offset, "offset_hex": "0x{:X}".format(sh_offset),
                "size": sh_size, "size_kb": round(sh_size/1024,1),
                "link": sh_link, "info": sh_info,
                "addralign": sh_addralign, "entsize": sh_entsize,
            })
            if i == e_shstrndx:
                shstrtab_offset = sh_offset

        # 解析段名称
        if shstrtab_offset is not None:
            for s in sections:
                name_end = data.find(b'\x00', shstrtab_offset + s["name_idx"])
                if name_end > 0:
                    s["name"] = data[shstrtab_offset + s["name_idx"]:name_end].decode("ascii", errors="replace")
                else:
                    s["name"] = f"<unknown_{s['index']}>"

        return {
            "success": True,
            "sections": sections,
            "count": len(sections),
            "section_count": e_shnum,
            "shstrtab_index": e_shstrndx,
            "is_64bit": False,
        }

    def _parse_sections_64(self, data: bytes) -> dict:
        import struct
        e_shoff = struct.unpack_from("<Q", data, 40)[0]
        e_shentsize = struct.unpack_from("<H", data, 58)[0]
        e_shnum = struct.unpack_from("<H", data, 60)[0]
        e_shstrndx = struct.unpack_from("<H", data, 62)[0]

        sections = []
        shstrtab_offset = None
        for i in range(e_shnum):
            off = e_shoff + i * e_shentsize
            sh_name = struct.unpack_from("<I", data, off)[0]
            sh_type = struct.unpack_from("<I", data, off + 4)[0]
            sh_flags = struct.unpack_from("<Q", data, off + 8)[0]
            sh_addr = struct.unpack_from("<Q", data, off + 16)[0]
            sh_offset = struct.unpack_from("<Q", data, off + 24)[0]
            sh_size = struct.unpack_from("<Q", data, off + 32)[0]
            sh_link = struct.unpack_from("<I", data, off + 40)[0]
            sh_info = struct.unpack_from("<I", data, off + 44)[0]
            sh_addralign = struct.unpack_from("<Q", data, off + 48)[0]
            sh_entsize = struct.unpack_from("<Q", data, off + 56)[0]

            type_names = {0:"NULL",1:"PROGBITS",2:"SYMTAB",3:"STRTAB",4:"RELA",5:"HASH",6:"DYNAMIC",7:"NOTE",8:"NOBITS",9:"REL",10:"SHLIB",11:"DYNSYM",14:"INIT_ARRAY",15:"FINI_ARRAY"}
            sections.append({
                "index": i, "name_idx": sh_name,
                "type": sh_type, "type_name": type_names.get(sh_type, f"UNKNOWN({sh_type})"),
                "addr": sh_addr, "addr_hex": "0x{:X}".format(sh_addr),
                "offset": sh_offset, "offset_hex": "0x{:X}".format(sh_offset),
                "size": sh_size, "size_kb": round(sh_size/1024,1),
            })
            if i == e_shstrndx:
                shstrtab_offset = sh_offset

        if shstrtab_offset is not None:
            for s in sections:
                name_end = data.find(b'\x00', shstrtab_offset + s["name_idx"])
                s["name"] = data[shstrtab_offset + s["name_idx"]:name_end].decode("ascii", errors="replace") if name_end > 0 else f"<unknown>"

        return {"success": True, "sections": sections, "count": len(sections), "is_64bit": True}

    def parse_symbols(self) -> dict:
        """解析 ELF 符号表（.symtab 和 .dynsym），返回所有符号信息"""
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}
        try:
            with open(self._script_so_path, "rb") as f:
                data = f.read()
        except (IOError, OSError) as e:
            return {"success": False, "message": f"读取失败: {e}"}
        if data[:4] != self.ELF_MAGIC:
            return {"success": False, "message": "不是有效的ELF文件"}

        ei_class = data[4]
        is_64 = (ei_class == 2)

        # 先解析 sections 获取 strtab 和 symtab 位置
        sections_result = self.parse_sections()
        if not sections_result.get("success"):
            return {"success": False, "message": "无法解析段表"}

        sections = sections_result["sections"]
        symtabs = []
        for sec in sections:
            if sec["type"] in (2, 11):  # SYMTAB or DYNSYM
                strtab_sec = next((s for s in sections if s["index"] == sec["link"]), None)
                if strtab_sec:
                    symtabs.append({
                        "section": sec["name"],
                        "type": sec["type_name"],
                        "offset": sec["offset"],
                        "size": sec["size"],
                        "entsize": sec["entsize"],
                        "strtab_offset": strtab_sec["offset"],
                        "strtab_size": strtab_sec["size"],
                    })

        all_symbols = []
        for st in symtabs:
            syms = self._parse_symbol_table(data, st["offset"], st["size"], st["entsize"], st["strtab_offset"], is_64)
            for s in syms:
                s["section"] = st["section"]
                s["section_type"] = st["type"]
            all_symbols.extend(syms)

        # 分类统计
        func_count = sum(1 for s in all_symbols if s["bind"] == "GLOBAL" and s["type"] == "FUNC")
        obj_count = sum(1 for s in all_symbols if s["bind"] == "GLOBAL" and s["type"] == "OBJECT")
        local_count = sum(1 for s in all_symbols if s["bind"] == "LOCAL")

        return {
            "success": True,
            "symbols": all_symbols[:500],
            "total": len(all_symbols),
            "func_count": func_count,
            "object_count": obj_count,
            "local_count": local_count,
            "symtab_count": len(symtabs),
        }

    def _parse_symbol_table(self, data: bytes, offset: int, size: int, entsize: int, strtab_offset: int, is_64: bool) -> list:
        import struct
        symbols = []
        count = size // entsize if entsize > 0 else 0
        for i in range(count):
            sym_off = offset + i * entsize
            if is_64:
                st_name = struct.unpack_from("<I", data, sym_off)[0]
                st_info = data[sym_off + 4]
                st_other = data[sym_off + 5]
                st_shndx = struct.unpack_from("<H", data, sym_off + 6)[0]
                st_value = struct.unpack_from("<Q", data, sym_off + 8)[0]
                st_size = struct.unpack_from("<Q", data, sym_off + 16)[0]
            else:
                st_name = struct.unpack_from("<I", data, sym_off)[0]
                st_value = struct.unpack_from("<I", data, sym_off + 4)[0]
                st_size = struct.unpack_from("<I", data, sym_off + 8)[0]
                st_info = data[sym_off + 12]
                st_other = data[sym_off + 13]
                st_shndx = struct.unpack_from("<H", data, sym_off + 14)[0]

            st_bind = st_info >> 4
            st_type = st_info & 0xF
            bind_names = {0:"LOCAL",1:"GLOBAL",2:"WEAK",3:"NUM",10:"LOOS",12:"HIOS",13:"LOPROC",15:"HIPROC"}
            type_names = {0:"NOTYPE",1:"OBJECT",2:"FUNC",3:"SECTION",4:"FILE",5:"COMMON",6:"TLS",10:"LOOS",12:"HIOS",13:"LOPROC",15:"HIPROC"}

            # 解析符号名称
            name = ""
            if st_name > 0 and strtab_offset + st_name < len(data):
                name_end = data.find(b'\x00', strtab_offset + st_name)
                if name_end > 0:
                    name = data[strtab_offset + st_name:name_end].decode("ascii", errors="replace")

            if name:  # 只保留有名字的符号
                symbols.append({
                    "name": name,
                    "value": st_value, "value_hex": "0x{:X}".format(st_value),
                    "size": st_size,
                    "bind": bind_names.get(st_bind, f"UNKNOWN({st_bind})"),
                    "type": type_names.get(st_type, f"UNKNOWN({st_type})"),
                    "shndx": st_shndx,
                })

        return symbols

    # ============================================================
    # 反汇编引擎
    # ============================================================

    def _get_capstone_arch(self) -> tuple:
        """根据 ELF 头确定 Capstone 架构参数"""
        if not self.script_so_exists():
            return None, None
        try:
            with open(self._script_so_path, "rb") as f:
                header = f.read(64)
        except (IOError, OSError):
            return None, None
        if header[:4] != self.ELF_MAGIC:
            return None, None
        ei_class = header[4]
        e_machine = struct.unpack_from("<H", header, 18)[0]
        if e_machine == 3:  # i386
            return CS_ARCH_X86, CS_MODE_32
        elif e_machine == 0x28:  # ARM
            return CS_ARCH_ARM, CS_MODE_ARM
        elif e_machine == 0x3E:  # x86-64
            return CS_ARCH_X86, CS_MODE_32  # 通常32位兼容
        return None, None

    def disassemble(self, offset: int = None, length: int = 512) -> dict:
        """
        反汇编 Script.so 指定区域的代码
        如果不指定 offset，自动定位 .text 段
        """
        if not HAS_CAPSTONE:
            return {"success": False, "message": "Capstone 反汇编库未安装，请运行: pip install capstone"}
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}

        arch, mode = self._get_capstone_arch()
        if arch is None:
            return {"success": False, "message": "无法确定目标架构"}

        try:
            with open(self._script_so_path, "rb") as f:
                data = f.read()
        except (IOError, OSError) as e:
            return {"success": False, "message": f"读取失败: {e}"}

        # 如果未指定 offset，自动查找 .text 段
        if offset is None:
            sections = self.parse_sections()
            if sections.get("success"):
                text_sec = next((s for s in sections["sections"] if s.get("name") == ".text"), None)
                if text_sec:
                    offset = text_sec["offset"]
                    length = min(length, text_sec["size"])
                else:
                    # 找第一个可执行段
                    exec_sec = next((s for s in sections["sections"] if "X" in s.get("flags_str", "")), None)
                    if exec_sec:
                        offset = exec_sec["offset"]
                        length = min(length, exec_sec["size"])
                    else:
                        offset = 0

        if offset + length > len(data):
            length = len(data) - offset
        if length <= 0:
            return {"success": False, "message": "无效的偏移或长度"}

        code = data[offset:offset + length]
        md = Cs(arch, mode)
        md.detail = True

        instructions = []
        call_targets = []
        jump_targets = []
        refs_to = {}

        for insn in md.disasm(code, offset):
            # 解析操作数
            operands = []
            for op in insn.operands:
                if op.type == 1:  # register
                    operands.append({"type": "reg", "value": insn.reg_name(op.reg)})
                elif op.type == 2:  # immediate
                    operands.append({"type": "imm", "value": op.imm, "hex": "0x{:X}".format(op.imm)})
                elif op.type == 3:  # memory
                    mem_str = ""
                    if op.mem.base:
                        mem_str += insn.reg_name(op.mem.base)
                    if op.mem.index:
                        mem_str += f"+{insn.reg_name(op.mem.index)}"
                        if op.mem.scale > 1:
                            mem_str += f"*{op.mem.scale}"
                    if op.mem.disp:
                        if op.mem.disp > 0:
                            mem_str += f"+0x{op.mem.disp:X}"
                        else:
                            mem_str += f"-0x{-op.mem.disp:X}"
                    operands.append({"type": "mem", "value": f"[{mem_str}]"})

            inst = {
                "address": insn.address,
                "address_hex": "0x{:X}".format(insn.address),
                "size": insn.size,
                "mnemonic": insn.mnemonic,
                "op_str": insn.op_str,
                "bytes": code[insn.address - offset:insn.address - offset + insn.size].hex().upper(),
                "operands": operands,
                "groups": [insn.group_name(g) for g in insn.groups],
            }
            instructions.append(inst)

            # 追踪调用和跳转目标
            if insn.mnemonic in ("call", "jmp", "je", "jne", "jg", "jge", "jl", "jle", "ja", "jae", "jb", "jbe", "jz", "jnz", "jcxz", "loop", "loope", "loopne"):
                for op in insn.operands:
                    if op.type == 2:  # immediate
                        target = op.imm
                        if target not in refs_to:
                            refs_to[target] = []
                        refs_to[target].append({
                            "from": insn.address,
                            "from_hex": "0x{:X}".format(insn.address),
                            "type": insn.mnemonic,
                        })
                        if insn.mnemonic == "call":
                            call_targets.append(target)
                        else:
                            jump_targets.append(target)

        return {
            "success": True,
            "offset": offset,
            "offset_hex": "0x{:X}".format(offset),
            "length": len(code),
            "instruction_count": len(instructions),
            "instructions": instructions,
            "call_targets": list(set(call_targets)),
            "jump_targets": list(set(jump_targets)),
            "xrefs": {("0x{:X}".format(k)): v for k, v in refs_to.items()},
            "arch": "x86" if arch == CS_ARCH_X86 else "ARM",
            "mode": "32-bit" if mode in (CS_MODE_32, CS_MODE_ARM) else "thumb",
        }

    def find_functions(self) -> dict:
        """在 .text 段中检测函数边界（通过函数序言特征）"""
        import struct
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}

        try:
            with open(self._script_so_path, "rb") as f:
                data = f.read()
        except (IOError, OSError) as e:
            return {"success": False, "message": f"读取失败: {e}"}

        sections = self.parse_sections()
        if not sections.get("success"):
            return {"success": False, "message": "无法解析段表"}

        text_sec = next((s for s in sections["sections"] if s.get("name") == ".text"), None)
        if not text_sec:
            # 找第一个可执行段
            text_sec = next((s for s in sections["sections"] if "X" in s.get("flags_str", "")), None)
        if not text_sec:
            return {"success": False, "message": "未找到可执行段 (.text)"}

        offset = text_sec["offset"]
        size = text_sec["size"]
        code = data[offset:offset + size]

        arch, mode = self._get_capstone_arch()
        is_x86 = (arch == CS_ARCH_X86)

        functions = []
        if is_x86:
            # x86 函数序言: 55 8B EC (push ebp; mov ebp, esp) 或 55 89 E5
            prologues = [
                bytes([0x55, 0x8B, 0xEC]),  # push ebp; mov ebp, esp
                bytes([0x55, 0x89, 0xE5]),  # push ebp; mov ebp, esp (AT&T)
            ]
            epilogue_sigs = [
                bytes([0x5D, 0xC3]),  # pop ebp; ret
                bytes([0xC9, 0xC3]),  # leave; ret
                bytes([0x5D, 0xC2]),  # pop ebp; ret N
                bytes([0xC9, 0xC2]),  # leave; ret N
            ]

            # 使用符号表辅助
            symbols = self.parse_symbols()
            sym_funcs = {}
            if symbols.get("success"):
                for s in symbols.get("symbols", []):
                    if s.get("type") == "FUNC" and s.get("value", 0) > 0:
                        sym_funcs[s["value"]] = s.get("name", "")

            # 扫描函数序言
            for prologue in prologues:
                pos = 0
                while True:
                    pos = code.find(prologue, pos)
                    if pos < 0:
                        break
                    abs_addr = offset + pos
                    func_info = {
                        "address": abs_addr,
                        "address_hex": "0x{:X}".format(abs_addr),
                        "offset_in_section": pos,
                        "name": sym_funcs.get(abs_addr, ""),
                    }
                    if func_info not in functions:
                        functions.append(func_info)
                    pos += 1

            # 补充符号表中的函数
            for addr, name in sym_funcs.items():
                if addr >= offset and addr < offset + size:
                    fi = {
                        "address": addr,
                        "address_hex": "0x{:X}".format(addr),
                        "offset_in_section": addr - offset,
                        "name": name,
                    }
                    if fi not in functions:
                        functions.append(fi)

            # 按地址排序
            functions.sort(key=lambda f: f["address"])
        else:
            # ARM: 函数通常以 PUSH {..., lr} 或 STMFD sp!, {...} 开头
            functions = []
            symbols = self.parse_symbols()
            if symbols.get("success"):
                for s in symbols.get("symbols", []):
                    if s.get("type") == "FUNC" and s.get("value", 0) >= offset and s.get("value", 0) < offset + size:
                        functions.append({
                            "address": s["value"],
                            "address_hex": "0x{:X}".format(s["value"]),
                            "offset_in_section": s["value"] - offset,
                            "name": s.get("name", ""),
                        })
            functions.sort(key=lambda f: f["address"])

        return {
            "success": True,
            "functions": functions,
            "count": len(functions),
            "section": text_sec.get("name", ".text"),
            "section_offset": offset,
            "section_size": size,
            "arch": "x86" if is_x86 else "ARM",
        }

    def disassemble_function(self, address: int, max_instructions: int = 200) -> dict:
        """反汇编单个函数（从指定地址开始，直到遇到 ret 或达到最大指令数）"""
        if not HAS_CAPSTONE:
            return {"success": False, "message": "Capstone 未安装"}
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}

        arch, mode = self._get_capstone_arch()
        if arch is None:
            return {"success": False, "message": "无法确定目标架构"}

        try:
            with open(self._script_so_path, "rb") as f:
                data = f.read()
        except (IOError, OSError) as e:
            return {"success": False, "message": f"读取失败: {e}"}

        if address >= len(data):
            return {"success": False, "message": "地址超出文件范围"}

        # 读取足够多的代码（最多 4096 字节）
        read_size = min(4096, len(data) - address)
        code = data[address:address + read_size]
        md = Cs(arch, mode)
        md.detail = True

        instructions = []
        branch_targets = set()
        for insn in md.disasm(code, address):
            inst = {
                "address": insn.address,
                "address_hex": "0x{:X}".format(insn.address),
                "size": insn.size,
                "mnemonic": insn.mnemonic,
                "op_str": insn.op_str,
                "bytes": code[insn.address - address:insn.address - address + insn.size].hex().upper(),
            }
            instructions.append(inst)

            # 追踪分支目标
            if insn.mnemonic.startswith("j") or insn.mnemonic == "call":
                for op in insn.operands:
                    if op.type == 2:
                        branch_targets.add(op.imm)

            # 遇到 ret 停止
            if insn.mnemonic == "ret" or insn.mnemonic.startswith("ret"):
                break

            if len(instructions) >= max_instructions:
                break

        # 获取函数名
        func_name = ""
        symbols = self.parse_symbols()
        if symbols.get("success"):
            for s in symbols.get("symbols", []):
                if s.get("value") == address:
                    func_name = s.get("name", "")
                    break

        return {
            "success": True,
            "function_address": address,
            "function_address_hex": "0x{:X}".format(address),
            "function_name": func_name,
            "instructions": instructions,
            "instruction_count": len(instructions),
            "branch_targets": [{"address": t, "hex": "0x{:X}".format(t)} for t in sorted(branch_targets)],
            "arch": "x86" if arch == CS_ARCH_X86 else "ARM",
        }

    def find_xrefs_to(self, address: int) -> dict:
        """查找所有引用指定地址的指令（交叉引用）"""
        if not HAS_CAPSTONE:
            return {"success": False, "message": "Capstone 未安装"}
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}

        arch, mode = self._get_capstone_arch()
        if arch is None:
            return {"success": False, "message": "无法确定目标架构"}

        # 获取可执行段
        sections = self.parse_sections()
        if not sections.get("success"):
            return {"success": False, "message": "无法解析段表"}

        exec_sections = [s for s in sections["sections"] if "X" in s.get("flags_str", "")]
        if not exec_sections:
            exec_sections = [s for s in sections["sections"] if s.get("type_name") == "PROGBITS"]

        try:
            with open(self._script_so_path, "rb") as f:
                data = f.read()
        except (IOError, OSError) as e:
            return {"success": False, "message": f"读取失败: {e}"}

        md = Cs(arch, mode)
        refs = []

        for sec in exec_sections:
            if sec["size"] > 1024 * 1024:  # 跳过过大的段
                continue
            code = data[sec["offset"]:sec["offset"] + sec["size"]]
            for insn in md.disasm(code, sec["offset"]):
                if insn.mnemonic in ("call", "jmp", "je", "jne", "jg", "jge", "jl", "jle", "ja", "jae", "jb", "jbe", "jz", "jnz"):
                    for op in insn.operands:
                        if op.type == 2 and op.imm == address:
                            refs.append({
                                "from": insn.address,
                                "from_hex": "0x{:X}".format(insn.address),
                                "type": insn.mnemonic,
                                "section": sec.get("name", ""),
                                "instruction": f"{insn.mnemonic} {insn.op_str}",
                            })
                # 也检查内存操作数
                if insn.mnemonic in ("mov", "lea", "add", "sub", "cmp", "test", "xor", "and", "or"):
                    for op in insn.operands:
                        if op.type == 3:  # memory
                            if op.mem.disp == address or (hasattr(op.mem, 'base') and op.mem.base == 0 and op.mem.disp == address):
                                refs.append({
                                    "from": insn.address,
                                    "from_hex": "0x{:X}".format(insn.address),
                                    "type": "data_ref",
                                    "section": sec.get("name", ""),
                                    "instruction": f"{insn.mnemonic} {insn.op_str}",
                                })

        return {
            "success": True,
            "target": address,
            "target_hex": "0x{:X}".format(address),
            "refs": refs,
            "count": len(refs),
        }

    def instruction_patch(self, address: int, new_mnemonic: str, new_operands: str = "") -> dict:
        """
        指令级补丁：修改指定地址的指令
        将新指令汇编为机器码并写入（需要 keystone 库，如不可用则回退到手动NOP）
        """
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}

        try:
            from keystone import Ks, KS_ARCH_X86, KS_MODE_32, KS_ARCH_ARM, KS_MODE_ARM
            HAS_KEYSTONE = True
        except ImportError:
            HAS_KEYSTONE = False

        arch, mode = self._get_capstone_arch()
        if arch is None:
            return {"success": False, "message": "无法确定目标架构"}

        # 读取原始字节
        old_bytes = self.read_bytes(address, 16)  # 读取足够多
        if old_bytes is None:
            return {"success": False, "message": "读取原始数据失败"}

        # 旧指令反汇编
        old_asm = ""
        if HAS_CAPSTONE:
            md = Cs(arch, mode)
            for insn in md.disasm(old_bytes, address):
                old_asm = f"{insn.mnemonic} {insn.op_str}"
                break

        if new_mnemonic.upper() == "NOP":
            # NOP 填充：计算需要填充的字节数
            nop_count = len(old_bytes) if old_asm else 1
            # 找到原指令长度
            if HAS_CAPSTONE:
                md = Cs(arch, mode)
                for insn in md.disasm(old_bytes, address):
                    nop_count = insn.size
                    break
            # x86 NOP 序列
            nop_bytes = bytes([0x90] * nop_count)
            result = self.hex_write(address, nop_bytes.hex())
            if result.get("success"):
                result["instruction"] = f"NOP ×{nop_count}"
            return result

        if HAS_KEYSTONE:
            # 使用 Keystone 汇编
            ks_arch = KS_ARCH_X86 if arch == CS_ARCH_X86 else KS_ARCH_ARM
            ks_mode = KS_MODE_32 if mode in (CS_MODE_32, CS_MODE_ARM) else KS_MODE_ARM
            try:
                ks = Ks(ks_arch, ks_mode)
                asm_code = f"{new_mnemonic} {new_operands}".strip()
                encoding, count = ks.asm(asm_code, address)
                if encoding:
                    new_bytes = bytes(encoding)
                    result = self.hex_write(address, new_bytes.hex())
                    if result.get("success"):
                        result["instruction"] = asm_code
                    return result
            except Exception as e:
                return {"success": False, "message": f"汇编失败: {e}"}
        else:
            return {"success": False, "message": "Keystone 汇编库未安装，仅支持 NOP 补丁。请运行: pip install keystone-engine"}

    def extract_strings(self, min_length: int = 4, max_length: int = 256) -> List[dict]:
        """
        提取 Script.so 中的可读字符串
        返回字符串列表，包含偏移量和内容
        """
        if not self.script_so_exists():
            return []

        try:
            with open(self._script_so_path, "rb") as f:
                data = f.read()
        except (IOError, OSError):
            return []

        strings = []
        current = b""
        current_start = 0

        for i, byte in enumerate(data):
            if 32 <= byte < 127:  # 可打印 ASCII
                if not current:
                    current_start = i
                current += bytes([byte])
            else:
                if len(current) >= min_length and len(current) <= max_length:
                    try:
                        text = current.decode("ascii")
                        # 过滤纯数字/符号
                        if any(c.isalpha() for c in text):
                            strings.append({
                                "offset": current_start,
                                "offset_hex": "0x{:X}".format(current_start),
                                "length": len(current),
                                "text": text,
                            })
                    except UnicodeDecodeError:
                        pass
                current = b""

        # 处理最后一个字符串
        if len(current) >= min_length and len(current) <= max_length:
            try:
                text = current.decode("ascii")
                if any(c.isalpha() for c in text):
                    strings.append({
                        "offset": current_start,
                        "offset_hex": "0x{:X}".format(current_start),
                        "length": len(current),
                        "text": text,
                    })
            except UnicodeDecodeError:
                pass

        return strings

    def analyze_strings(self) -> dict:
        """
        分析 Script.so 字符串，匹配已知模式
        """
        strings = self.extract_strings()
        if not strings:
            return {"success": False, "message": "Script.so 不存在或无法读取", "strings": [], "patterns": {}}

        patterns = {}
        for pattern_name, pattern_desc in self.KNOWN_PATTERNS:
            matches = []
            for s in strings:
                if re.match(pattern_name, s["text"]):
                    matches.append(s)
            if matches:
                patterns[pattern_desc] = {
                    "pattern": pattern_name,
                    "count": len(matches),
                    "samples": [m["text"] for m in matches[:10]],
                    "matches": matches[:50],
                }

        return {
            "success": True,
            "total_strings": len(strings),
            "patterns": patterns,
            "pattern_count": len(patterns),
            "all_strings": strings[:500],  # 限制返回数量
        }

    def hex_view(self, offset: int = 0, length: int = 512) -> dict:
        """十六进制查看 Script.so"""
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}

        try:
            with open(self._script_so_path, "rb") as f:
                f.seek(offset)
                chunk = f.read(length)
        except (IOError, OSError) as e:
            return {"success": False, "message": f"读取失败: {e}"}

        if not chunk:
            return {"success": False, "message": "偏移超出文件范围"}

        lines = []
        for i in range(0, len(chunk), 16):
            row = chunk[i:i + 16]
            hex_part = " ".join("{:02X}".format(b) for b in row)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
            lines.append("{:08X}  {:48}  |{}|".format(offset + i, hex_part, ascii_part))

        return {
            "success": True,
            "offset": offset,
            "length": len(chunk),
            "total_size": os.path.getsize(self._script_so_path),
            "hex_lines": lines,
        }

    def hex_search(self, pattern_hex: str) -> dict:
        """在 Script.so 中搜索十六进制模式"""
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}

        try:
            pattern = bytes.fromhex(pattern_hex.replace(" ", ""))
        except ValueError:
            return {"success": False, "message": "无效的十六进制模式"}

        try:
            with open(self._script_so_path, "rb") as f:
                data = f.read()
        except (IOError, OSError) as e:
            return {"success": False, "message": f"读取失败: {e}"}

        positions = []
        start = 0
        while True:
            pos = data.find(pattern, start)
            if pos < 0:
                break
            positions.append("0x{:X}".format(pos))
            start = pos + 1

        return {
            "success": True,
            "pattern": pattern_hex,
            "match_count": len(positions),
            "positions": positions[:100],
        }

    def list_script_files(self) -> List[dict]:
        """列出 Script/ 目录下的所有文件"""
        if not self.script_dir or not os.path.exists(self.script_dir):
            return []

        files = []
        for fname in sorted(os.listdir(self.script_dir)):
            fpath = os.path.join(self.script_dir, fname)
            if os.path.isfile(fpath):
                size = os.path.getsize(fpath)
                ext = os.path.splitext(fname)[1].lower()
                files.append({
                    "name": fname,
                    "path": fpath,
                    "size": size,
                    "size_kb": round(size / 1024, 1),
                    "type": ext.lstrip(".") if ext else "unknown",
                    "is_script_so": fname == "Script.so",
                })

        return files

    def backup_script_so(self) -> dict:
        """备份 Script.so"""
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}

        import time
        backup_path = self._script_so_path + ".{}.bak".format(int(time.time()))
        try:
            with open(self._script_so_path, "rb") as src:
                with open(backup_path, "wb") as dst:
                    dst.write(src.read())
            return {"success": True, "message": "备份已创建: {}".format(os.path.basename(backup_path))}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ============================================================
    # 十六进制编辑功能
    # ============================================================

    def read_bytes(self, offset: int, size: int) -> Optional[bytes]:
        """读取指定偏移的原始字节"""
        if not self.script_so_exists():
            return None
        try:
            with open(self._script_so_path, "rb") as f:
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

    def read_float(self, offset: int) -> Optional[float]:
        data = self.read_bytes(offset, 4)
        if data and len(data) == 4:
            return struct.unpack("<f", data)[0]
        return None

    def hex_write(self, offset: int, data_hex: str) -> dict:
        """
        在指定偏移写入十六进制数据
        自动备份原始数据
        """
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}

        try:
            data = bytes.fromhex(data_hex.replace(" ", ""))
        except ValueError:
            return {"success": False, "message": "无效的十六进制数据"}

        file_size = os.path.getsize(self._script_so_path)
        if offset + len(data) > file_size:
            return {"success": False, "message": f"写入超出文件范围 (文件大小: {file_size})"}

        # 读取原始字节用于回滚
        old_bytes = self.read_bytes(offset, len(data))
        if old_bytes is None:
            return {"success": False, "message": "读取原始数据失败"}

        try:
            with open(self._script_so_path, "r+b") as f:
                f.seek(offset)
                f.write(data)
            return {
                "success": True,
                "message": f"已在 0x{offset:X} 写入 {len(data)} 字节",
                "offset": offset,
                "offset_hex": "0x{:X}".format(offset),
                "size": len(data),
                "old_hex": old_bytes.hex().upper(),
                "new_hex": data.hex().upper(),
            }
        except (IOError, OSError) as e:
            return {"success": False, "message": f"写入失败: {e}"}

    def hex_write_int32(self, offset: int, value: int) -> dict:
        return self.hex_write(offset, struct.pack("<i", value).hex())

    def hex_write_int16(self, offset: int, value: int) -> dict:
        return self.hex_write(offset, struct.pack("<H", value).hex())

    def hex_write_int8(self, offset: int, value: int) -> dict:
        return self.hex_write(offset, struct.pack("<B", value).hex())

    def hex_write_float(self, offset: int, value: float) -> dict:
        return self.hex_write(offset, struct.pack("<f", value).hex())

    def hex_patch(self, patches: List[dict]) -> dict:
        """
        批量应用十六进制补丁
        patches: [{"offset": int, "data_hex": str}, ...]
        """
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}

        results = []
        for p in patches:
            offset = p.get("offset", 0)
            data_hex = p.get("data_hex", "")
            r = self.hex_write(offset, data_hex)
            results.append(r)

        success_count = sum(1 for r in results if r.get("success"))
        return {
            "success": success_count > 0,
            "message": f"已应用 {success_count}/{len(patches)} 处补丁",
            "total": len(patches),
            "success_count": success_count,
            "results": results,
        }

    def string_replace(self, old_text: str, new_text: str, pad_byte: int = 0x00) -> dict:
        """
        替换 Script.so 中的字符串
        新字符串长度必须 <= 旧字符串长度（否则会被截断）
        """
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}

        try:
            with open(self._script_so_path, "rb") as f:
                data = f.read()
        except (IOError, OSError) as e:
            return {"success": False, "message": f"读取失败: {e}"}

        old_bytes = old_text.encode("ascii")
        new_bytes = new_text.encode("ascii")

        positions = []
        start = 0
        while True:
            pos = data.find(old_bytes, start)
            if pos < 0:
                break
            positions.append(pos)
            start = pos + 1

        if not positions:
            return {"success": False, "message": f"未找到字符串 '{old_text}'", "positions": []}

        if len(new_bytes) > len(old_bytes):
            return {
                "success": False,
                "message": f"新字符串({len(new_bytes)}字节)比旧字符串({len(old_bytes)}字节)长，无法替换",
                "positions": [hex(p) for p in positions],
            }

        # 填充到相同长度
        padded = new_bytes + bytes([pad_byte] * (len(old_bytes) - len(new_bytes)))

        replaced = 0
        for pos in positions:
            offset = data.find(old_bytes, pos)
            if offset >= 0:
                data = data[:offset] + padded + data[offset + len(old_bytes):]
                replaced += 1

        try:
            with open(self._script_so_path, "wb") as f:
                f.write(data)
        except (IOError, OSError) as e:
            return {"success": False, "message": f"写入失败: {e}"}

        return {
            "success": True,
            "message": f"已替换 {replaced} 处 '{old_text}' → '{new_text}'",
            "positions": [hex(p) for p in positions],
            "replaced": replaced,
            "old_text": old_text,
            "new_text": new_text,
        }

    # ============================================================
    # 已知 Script.so 补丁偏移数据库
    # ============================================================

    KNOWN_SCRIPT_PATCHES = {
        "skill_damage_multiplier": {
            "description": "技能伤害倍率（通用）",
            "search_pattern": "DamageMul",
            "value_type": "float",
            "note": "搜索字符串 DamageMul 附近浮点值",
        },
        "battle_speed": {
            "description": "战斗速度倍率",
            "search_pattern": "BattleSpeed",
            "value_type": "float",
            "note": "修改战斗动画速度，常见值 1.0 ~ 2.0",
        },
        "exp_rate": {
            "description": "经验获取倍率",
            "search_pattern": "ExpRate",
            "value_type": "float",
            "note": "修改经验获取倍率，常见值 1.0 ~ 5.0",
        },
        "drop_rate": {
            "description": "物品掉落率倍率",
            "search_pattern": "DropRate",
            "value_type": "float",
            "note": "修改物品掉落率，常见值 1.0 ~ 3.0",
        },
        "ai_aggression": {
            "description": "AI侵略性参数",
            "search_pattern": "AIAggr",
            "value_type": "float",
            "note": "AI主动进攻倾向，值越大越激进",
        },
        "ai_defense": {
            "description": "AI防守倾向参数",
            "search_pattern": "AIDefense",
            "value_type": "float",
            "note": "AI防守倾向，值越大越保守",
        },
        "event_trigger_interval": {
            "description": "事件触发间隔",
            "search_pattern": "EventInterval",
            "value_type": "int32",
            "note": "游戏内事件触发的最小间隔（帧数）",
        },
        "max_battle_time": {
            "description": "战斗最大时间",
            "search_pattern": "MaxBattleTime",
            "value_type": "int32",
            "note": "单场战斗最大时间限制（秒）",
        },
        "npc_spawn_rate": {
            "description": "NPC生成率",
            "search_pattern": "NPCSpawn",
            "value_type": "float",
            "note": "山贼/野怪刷新频率",
        },
        "economy_multiplier": {
            "description": "经济倍率",
            "search_pattern": "EcoMul",
            "value_type": "float",
            "note": "城池收入倍率，默认 1.0",
        },
    }

    def get_known_patches(self) -> dict:
        """获取已知 Script.so 补丁列表"""
        patches = []
        for key, info in self.KNOWN_SCRIPT_PATCHES.items():
            patches.append({
                "id": key,
                "description": info["description"],
                "search_pattern": info["search_pattern"],
                "value_type": info["value_type"],
                "note": info["note"],
            })
        return {"success": True, "patches": patches, "count": len(patches)}

    def search_patch_offset(self, patch_id: str) -> dict:
        """
        搜索已知补丁在 Script.so 中的可能偏移
        通过搜索相关字符串定位附近的可修改值
        """
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}

        if patch_id not in self.KNOWN_SCRIPT_PATCHES:
            return {"success": False, "message": f"未知补丁: {patch_id}"}

        patch_info = self.KNOWN_SCRIPT_PATCHES[patch_id]
        search_pattern = patch_info["search_pattern"]

        # 搜索相关字符串
        strings = self.extract_strings(min_length=3)
        candidates = [s for s in strings if search_pattern.lower() in s["text"].lower()]

        if not candidates:
            return {
                "success": True,
                "patch_id": patch_id,
                "description": patch_info["description"],
                "pattern": search_pattern,
                "candidates": [],
                "message": f"未找到包含 '{search_pattern}' 的字符串",
            }

        # 对每个候选，读取附近的值
        enriched = []
        for c in candidates[:10]:
            nearby = {
                "string_offset": c["offset_hex"],
                "string_text": c["text"],
                "nearby_values": [],
            }
            # 检查字符串前后各 64 字节范围内的值
            for delta in range(-64, 64, 4):
                off = c["offset"] + delta
                if off < 0:
                    continue
                val = self.read_int32(off)
                if val is not None and 0 < abs(val) < 1000000:
                    nearby["nearby_values"].append({
                        "offset": "0x{:X}".format(off),
                        "delta": delta,
                        "int32": val,
                        "float": round(struct.unpack("<f", struct.pack("<i", val))[0], 4),
                    })
            enriched.append(nearby)

        return {
            "success": True,
            "patch_id": patch_id,
            "description": patch_info["description"],
            "value_type": patch_info["value_type"],
            "pattern": search_pattern,
            "candidates": enriched,
            "note": patch_info["note"],
        }

    def apply_known_patch(self, patch_id: str, offset: int, new_value, value_type: str = None) -> dict:
        """
        应用已知补丁到指定偏移
        支持 int32, int16, int8, float 类型
        """
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}

        if patch_id not in self.KNOWN_SCRIPT_PATCHES:
            return {"success": False, "message": f"未知补丁: {patch_id}"}

        patch_info = self.KNOWN_SCRIPT_PATCHES[patch_id]
        vt = value_type or patch_info.get("value_type", "int32")

        # 备份
        backup_result = self.backup_script_so()
        if not backup_result["success"]:
            return {"success": False, "message": "自动备份失败: " + backup_result.get("message", "")}

        # 读取旧值
        old_val = None
        if vt == "float":
            old_val = self.read_float(offset)
        elif vt == "int16":
            old_val = self.read_int16(offset)
        elif vt == "int8":
            old_val = self.read_int8(offset)
        else:
            old_val = self.read_int32(offset)

        # 写入新值
        if vt == "float":
            if not isinstance(new_value, (int, float)):
                return {"success": False, "message": "浮点补丁需要数值类型"}
            result = self.hex_write_float(offset, float(new_value))
        elif vt == "int16":
            result = self.hex_write_int16(offset, int(new_value))
        elif vt == "int8":
            result = self.hex_write_int8(offset, int(new_value))
        else:
            result = self.hex_write_int32(offset, int(new_value))

        if result["success"]:
            result["patch_id"] = patch_id
            result["description"] = patch_info["description"]
            result["old_value"] = old_val
            result["new_value"] = new_value
            result["value_type"] = vt
            result["offset_hex"] = "0x{:X}".format(offset)

        return result

    # ============================================================
    # 社区教程补丁（基于游侠论坛/铁血丹心社区MOD教程）
    # ============================================================

    COMMUNITY_STRING_PATCHES = {
        "superatk_weapon_class": {
            "category": "必杀系别修改",
            "description": "修改必杀技触发的武器系别",
            "patches": [
                {"id": "superatk_sword", "desc": "剑系 → 枪系必杀", "old": "SuperAtkStart0", "new": "SuperAtkStart1", "note": "将剑系武器触发的必杀改为枪系"},
                {"id": "superatk_spear", "desc": "枪系 → 大刀系必杀", "old": "SuperAtkStart1", "new": "SuperAtkStart2", "note": "将枪系武器触发的必杀改为大刀系"},
                {"id": "superatk_blade", "desc": "大刀系 → 剑系必杀", "old": "SuperAtkStart2", "new": "SuperAtkStart0", "note": "将大刀系武器触发的必杀改为剑系"},
                {"id": "superatk_fan", "desc": "扇系 → 弓系必杀", "old": "SuperAtkStart3", "new": "SuperAtkStart4", "note": "将扇系武器触发的必杀改为弓系"},
                {"id": "superatk_bow", "desc": "弓系 → 扇系必杀", "old": "SuperAtkStart4", "new": "SuperAtkStart3", "note": "将弓系武器触发的必杀改为扇系"},
            ]
        },
        "dart_trigger": {
            "category": "暗器触发修改",
            "description": "修改暗器（镖）触发的技能效果",
            "patches": [
                {"id": "dart_magic", "desc": "暗器触发武将技", "old": "GenSkillStart014", "new": "BFMagic590", "note": "经典MOD补丁：使暗器（镖）触发武将技而非个人特性"},
                {"id": "dart_restore", "desc": "恢复暗器触发特性", "old": "BFMagic590", "new": "GenSkillStart014", "note": "恢复暗器触发个人特性（反向补丁）"},
            ]
        },
        "soldier_special": {
            "category": "士兵特殊攻击",
            "description": "修改士兵攻击类型为特殊攻击",
            "patches": [
                {"id": "soldier_special_1", "desc": "士兵攻击1 → 特殊攻击", "old": "SoldierStart1", "new": "SpecialStart1", "note": "将士兵1号攻击改为特殊攻击类型"},
                {"id": "soldier_special_2", "desc": "士兵攻击2 → 特殊攻击", "old": "SoldierStart2", "new": "SpecialStart2", "note": "将士兵2号攻击改为特殊攻击类型"},
                {"id": "soldier_special_3", "desc": "士兵攻击3 → 特殊攻击", "old": "SoldierStart3", "new": "SpecialStart3", "note": "将士兵3号攻击改为特殊攻击类型"},
                {"id": "soldier_restore_1", "desc": "恢复士兵攻击1", "old": "SpecialStart1", "new": "SoldierStart1", "note": "恢复士兵1号普通攻击（反向补丁）"},
                {"id": "soldier_restore_2", "desc": "恢复士兵攻击2", "old": "SpecialStart2", "new": "SoldierStart2", "note": "恢复士兵2号普通攻击（反向补丁）"},
                {"id": "soldier_restore_3", "desc": "恢复士兵攻击3", "old": "SpecialStart3", "new": "SoldierStart3", "note": "恢复士兵3号普通攻击（反向补丁）"},
            ]
        },
        "battle_magic": {
            "category": "战斗武将技修改",
            "description": "修改战斗中武将技的触发条件",
            "patches": [
                {"id": "magic_cooldown", "desc": "武将技冷却缩短", "old": "BFMagicCooldown", "new": "BFMagicCooldown", "note": "搜索 BFMagicCooldown 附近数值修改冷却时间"},
                {"id": "magic_range", "desc": "武将技范围扩大", "old": "BFMagicRange", "new": "BFMagicRange", "note": "搜索 BFMagicRange 附近数值修改技能范围"},
            ]
        },
    }

    def get_community_patches(self) -> dict:
        """获取社区教程补丁列表"""
        categories = []
        for key, info in self.COMMUNITY_STRING_PATCHES.items():
            categories.append({
                "id": key,
                "category": info["category"],
                "description": info["description"],
                "patches": info["patches"],
                "count": len(info["patches"]),
            })
        total = sum(c["count"] for c in categories)
        return {"success": True, "categories": categories, "count": total}

    def apply_community_patch(self, patch_id: str) -> dict:
        """
        应用社区教程补丁
        先备份 Script.so，再执行字符串替换
        """
        if not self.script_so_exists():
            return {"success": False, "message": "Script.so 不存在"}

        # 查找补丁
        found = None
        found_category = None
        for key, info in self.COMMUNITY_STRING_PATCHES.items():
            for p in info["patches"]:
                if p["id"] == patch_id:
                    found = p
                    found_category = info
                    break
            if found:
                break

        if not found:
            return {"success": False, "message": f"未知社区补丁: {patch_id}"}

        # 先备份
        backup_result = self.backup_script_so()
        if not backup_result["success"]:
            return {"success": False, "message": "自动备份失败: " + backup_result.get("message", "")}

        # 执行字符串替换
        result = self.string_replace(found["old"], found["new"])

        if result["success"]:
            result["patch_id"] = patch_id
            result["desc"] = found["desc"]
            result["category"] = found_category["category"]
            result["note"] = found["note"]
            result["backup"] = backup_result["message"]

        return result