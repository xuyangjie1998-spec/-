"""
Script.so PLT/GOT 深度动态分析模块

实现 Script.so 的 ELF 动态段、PLT/GOT、重定位表、导入依赖图、
GOT 覆写、段权限、符号版本等深度分析能力。

Script.so 是三国群英传7的核心游戏逻辑共享库（Linux ELF 格式），
运行在 Wine 环境下。本模块填补 scriptso_analyzer.py 中缺少的
动态链接分析能力。

依赖: core.scriptso_analyzer.ScriptSOAnalyzer
"""

import os
import struct
import logging
from typing import Dict, List, Optional, Tuple, Any

# 尝试导入本项目的 ScriptSOAnalyzer
try:
    from core.scriptso_analyzer import ScriptSOAnalyzer
except ImportError:
    try:
        from scriptso_analyzer import ScriptSOAnalyzer
    except ImportError:
        ScriptSOAnalyzer = None

logger = logging.getLogger(__name__)


# ============================================================
# ELF 常量定义
# ============================================================

# Dynamic 标签 (DT_*)
DT_NULL = 0
DT_NEEDED = 1
DT_PLTRELSZ = 2
DT_PLTGOT = 3
DT_HASH = 4
DT_STRTAB = 5
DT_SYMTAB = 6
DT_RELA = 7
DT_RELASZ = 8
DT_RELAENT = 9
DT_STRSZ = 10
DT_SYMENT = 11
DT_INIT = 12
DT_FINI = 13
DT_SONAME = 14
DT_RPATH = 15
DT_SYMBOLIC = 16
DT_REL = 17
DT_RELSZ = 18
DT_RELENT = 19
DT_PLTREL = 20
DT_DEBUG = 21
DT_TEXTREL = 22
DT_JMPREL = 23
DT_BIND_NOW = 24
DT_INIT_ARRAY = 25
DT_FINI_ARRAY = 26
DT_INIT_ARRAYSZ = 27
DT_FINI_ARRAYSZ = 28
DT_RUNPATH = 29
DT_FLAGS = 30
DT_ENCODING = 32
DT_PREINIT_ARRAY = 32
DT_PREINIT_ARRAYSZ = 33
DT_GNU_HASH = 0x6ffffef5
DT_VERSYM = 0x6ffffff0
DT_VERNEED = 0x6ffffffe
DT_VERNEEDNUM = 0x6fffffff

# 重定位类型 (R_386_*)
R_386_NONE = 0
R_386_32 = 1
R_386_PC32 = 2
R_386_GOT32 = 3
R_386_PLT32 = 4
R_386_COPY = 5
R_386_GLOB_DAT = 6
R_386_JMP_SLOT = 7
R_386_RELATIVE = 8
R_386_GOTOFF = 9
R_386_GOTPC = 10

# Section Header 类型
SHT_NULL = 0
SHT_PROGBITS = 1
SHT_SYMTAB = 2
SHT_STRTAB = 3
SHT_RELA = 4
SHT_HASH = 5
SHT_DYNAMIC = 6
SHT_NOTE = 7
SHT_NOBITS = 8
SHT_REL = 9
SHT_SHLIB = 10
SHT_DYNSYM = 11
SHT_GNU_HASH = 0x6ffffff6
SHT_GNU_VERNEED = 0x6ffffffe
SHT_GNU_VERSYM = 0x6fffffff

# Program Header 类型
PT_NULL = 0
PT_LOAD = 1
PT_DYNAMIC = 2
PT_INTERP = 3
PT_NOTE = 4
PT_SHLIB = 5
PT_PHDR = 6
PT_TLS = 7
PT_GNU_EH_FRAME = 0x6474e550
PT_GNU_STACK = 0x6474e551
PT_GNU_RELRO = 0x6474e552

# Program Header 标志
PF_X = 0x1
PF_W = 0x2
PF_R = 0x4

# ELF 魔数
ELF_MAGIC = b"\x7fELF"

# x86 PLT 条目 16 字节模板
# 标准 i386 PLT 条目:
#   jmp *GOT[n]          ; ff 25 XX XX XX XX  (6 bytes)
#   push $reloc_index    ; 68 XX XX XX XX     (5 bytes)
#   jmp PLT[0]           ; e9 XX XX XX XX     (5 bytes)
#   共 16 字节
PLT_ENTRY_SIZE_32 = 16
PLT0_ENTRY_SIZE_32 = 16  # PLT[0] 也是 16 字节

# x86-64 PLT 条目
PLT_ENTRY_SIZE_64 = 16
PLT0_ENTRY_SIZE_64 = 16

# 动态段条目大小
DYNAMIC_ENTRY_SIZE_32 = 8   # d_tag(4) + d_val/d_ptr(4)
DYNAMIC_ENTRY_SIZE_64 = 16  # d_tag(8) + d_val/d_ptr(8)

# 重定位条目大小
REL_ENTRY_SIZE_32 = 8       # r_offset(4) + r_info(4)
RELA_ENTRY_SIZE_32 = 12     # r_offset(4) + r_info(4) + r_addend(4)
REL_ENTRY_SIZE_64 = 16      # r_offset(8) + r_info(8)
RELA_ENTRY_SIZE_64 = 24     # r_offset(8) + r_info(8) + r_addend(8)

# 符号表条目大小
SYM_ENTRY_SIZE_32 = 16
SYM_ENTRY_SIZE_64 = 24

# GOT 保留条目
GOT_RESERVED_ENTRIES = 3  # GOT[0]=.dynamic, GOT[1]=link_map, GOT[2]=_dl_runtime_resolve

# DT_* 标签名称映射
DT_TAG_NAMES = {
    DT_NULL: "DT_NULL",
    DT_NEEDED: "DT_NEEDED",
    DT_PLTRELSZ: "DT_PLTRELSZ",
    DT_PLTGOT: "DT_PLTGOT",
    DT_HASH: "DT_HASH",
    DT_STRTAB: "DT_STRTAB",
    DT_SYMTAB: "DT_SYMTAB",
    DT_RELA: "DT_RELA",
    DT_RELASZ: "DT_RELASZ",
    DT_RELAENT: "DT_RELAENT",
    DT_STRSZ: "DT_STRSZ",
    DT_SYMENT: "DT_SYMENT",
    DT_INIT: "DT_INIT",
    DT_FINI: "DT_FINI",
    DT_SONAME: "DT_SONAME",
    DT_RPATH: "DT_RPATH",
    DT_SYMBOLIC: "DT_SYMBOLIC",
    DT_REL: "DT_REL",
    DT_RELSZ: "DT_RELSZ",
    DT_RELENT: "DT_RELENT",
    DT_PLTREL: "DT_PLTREL",
    DT_DEBUG: "DT_DEBUG",
    DT_TEXTREL: "DT_TEXTREL",
    DT_JMPREL: "DT_JMPREL",
    DT_BIND_NOW: "DT_BIND_NOW",
    DT_INIT_ARRAY: "DT_INIT_ARRAY",
    DT_FINI_ARRAY: "DT_FINI_ARRAY",
    DT_INIT_ARRAYSZ: "DT_INIT_ARRAYSZ",
    DT_FINI_ARRAYSZ: "DT_FINI_ARRAYSZ",
    DT_RUNPATH: "DT_RUNPATH",
    DT_FLAGS: "DT_FLAGS",
    DT_ENCODING: "DT_ENCODING",
    DT_PREINIT_ARRAY: "DT_PREINIT_ARRAY",
    DT_PREINIT_ARRAYSZ: "DT_PREINIT_ARRAYSZ",
    DT_GNU_HASH: "DT_GNU_HASH",
    DT_VERSYM: "DT_VERSYM",
    DT_VERNEED: "DT_VERNEED",
    DT_VERNEEDNUM: "DT_VERNEEDNUM",
}


class ScriptSODynamic:
    """Script.so 的 PLT/GOT 动态分析器

    使用组合模式，内部持有 ScriptSOAnalyzer 实例以复用其 ELF 解析能力。
    提供动态段、PLT/GOT、重定位、导入依赖、GOT 覆写等深度分析功能。
    """

    def __init__(self, game_path: str = None):
        """初始化动态分析器

        Args:
            game_path: 游戏安装路径，如不提供则后续通过 set_game_path 设置
        """
        self.game_path = game_path
        self._analyzer = ScriptSOAnalyzer(game_path) if ScriptSOAnalyzer is not None else None
        self._script_so_path = ""
        self._data: Optional[bytes] = None
        self._is_64bit: bool = False
        self._cached_dynamic: Optional[Dict[int, int]] = None
        self._cached_strtab_offset: Optional[int] = None
        self._cached_symtab_offset: Optional[int] = None

        if game_path:
            self._script_so_path = os.path.join(game_path, "Script", "Script.so")
            self._load_file()

    # ============================================================
    # 内部辅助方法
    # ============================================================

    def set_game_path(self, game_path: str):
        """设置游戏路径并重新加载 Script.so"""
        self.game_path = game_path
        self._script_so_path = os.path.join(game_path, "Script", "Script.so")
        self._data = None
        self._cached_dynamic = None
        self._load_file()

    def _load_file(self) -> bool:
        """加载 Script.so 到内存"""
        self._data = None
        if not self._script_so_path or not os.path.exists(self._script_so_path):
            return False
        try:
            with open(self._script_so_path, "rb") as f:
                self._data = f.read()
            if self._data[:4] == ELF_MAGIC:
                self._is_64bit = (self._data[4] == 2)
            return True
        except (IOError, OSError) as e:
            logger.error("Failed to load Script.so: %s", e)
            return False

    def _check_loaded(self) -> bool:
        """确保文件已加载"""
        if self._data is None:
            if not self._load_file():
                return False
        return True

    def _read_struct(self, offset: int, fmt: str) -> tuple:
        """从数据中读取结构体"""
        size = struct.calcsize(fmt)
        if offset < 0 or offset + size > len(self._data):
            return None
        return struct.unpack_from(fmt, self._data, offset)

    def _read_bytes(self, offset: int, size: int) -> Optional[bytes]:
        """读取指定偏移的字节"""
        if offset < 0 or offset + size > len(self._data):
            return None
        return self._data[offset:offset + size]

    def _read_cstr(self, offset: int, max_len: int = 1024) -> str:
        """从指定偏移读取 C 字符串（以 null 结尾）"""
        if offset < 0 or offset >= len(self._data):
            return ""
        end = self._data.find(b'\x00', offset)
        if end < 0 or end - offset > max_len:
            end = min(offset + max_len, len(self._data))
        try:
            return self._data[offset:end].decode("ascii", errors="replace")
        except (UnicodeDecodeError, ValueError):
            return ""

    def _read_elf32_addr(self, offset: int) -> Optional[int]:
        """读取 ELF32 地址（4 字节小端）"""
        result = self._read_struct(offset, "<I")
        return result[0] if result else None

    def _read_elf64_addr(self, offset: int) -> Optional[int]:
        """读取 ELF64 地址（8 字节小端）"""
        result = self._read_struct(offset, "<Q")
        return result[0] if result else None

    def _read_addr(self, offset: int) -> Optional[int]:
        """根据 ELF 类型读取地址"""
        if self._is_64bit:
            return self._read_elf64_addr(offset)
        return self._read_elf32_addr(offset)

    def _read_elf32_ehdr(self) -> Optional[dict]:
        """解析 ELF32 头部"""
        if len(self._data) < 52:
            return None
        e_type = struct.unpack_from("<H", self._data, 16)[0]
        e_machine = struct.unpack_from("<H", self._data, 18)[0]
        e_entry = self._read_elf32_addr(24)
        e_phoff = self._read_elf32_addr(28)
        e_shoff = self._read_elf32_addr(32)
        e_flags = struct.unpack_from("<I", self._data, 36)[0]
        e_ehsize = struct.unpack_from("<H", self._data, 40)[0]
        e_phentsize = struct.unpack_from("<H", self._data, 42)[0]
        e_phnum = struct.unpack_from("<H", self._data, 44)[0]
        e_shentsize = struct.unpack_from("<H", self._data, 46)[0]
        e_shnum = struct.unpack_from("<H", self._data, 48)[0]
        e_shstrndx = struct.unpack_from("<H", self._data, 50)[0]
        return {
            "type": e_type, "machine": e_machine, "entry": e_entry,
            "phoff": e_phoff, "shoff": e_shoff, "flags": e_flags,
            "ehsize": e_ehsize, "phentsize": e_phentsize, "phnum": e_phnum,
            "shentsize": e_shentsize, "shnum": e_shnum, "shstrndx": e_shstrndx,
        }

    def _read_elf64_ehdr(self) -> Optional[dict]:
        """解析 ELF64 头部"""
        if len(self._data) < 64:
            return None
        e_type = struct.unpack_from("<H", self._data, 16)[0]
        e_machine = struct.unpack_from("<H", self._data, 18)[0]
        e_entry = self._read_elf64_addr(24)
        e_phoff = self._read_elf64_addr(32)
        e_shoff = self._read_elf64_addr(40)
        e_flags = struct.unpack_from("<I", self._data, 48)[0]
        e_ehsize = struct.unpack_from("<H", self._data, 52)[0]
        e_phentsize = struct.unpack_from("<H", self._data, 54)[0]
        e_phnum = struct.unpack_from("<H", self._data, 56)[0]
        e_shentsize = struct.unpack_from("<H", self._data, 58)[0]
        e_shnum = struct.unpack_from("<H", self._data, 60)[0]
        e_shstrndx = struct.unpack_from("<H", self._data, 62)[0]
        return {
            "type": e_type, "machine": e_machine, "entry": e_entry,
            "phoff": e_phoff, "shoff": e_shoff, "flags": e_flags,
            "ehsize": e_ehsize, "phentsize": e_phentsize, "phnum": e_phnum,
            "shentsize": e_shentsize, "shnum": e_shnum, "shstrndx": e_shstrndx,
        }

    def _get_ehdr(self) -> Optional[dict]:
        """获取 ELF 头部"""
        if not self._check_loaded():
            return None
        if self._is_64bit:
            return self._read_elf64_ehdr()
        return self._read_elf32_ehdr()

    def _get_sections(self) -> List[dict]:
        """获取所有 section header"""
        ehdr = self._get_ehdr()
        if not ehdr:
            return []
        sections = []
        for i in range(ehdr["shnum"]):
            if self._is_64bit:
                off = ehdr["shoff"] + i * ehdr["shentsize"]
                sh_name = struct.unpack_from("<I", self._data, off)[0]
                sh_type = struct.unpack_from("<I", self._data, off + 4)[0]
                sh_flags = struct.unpack_from("<Q", self._data, off + 8)[0]
                sh_addr = self._read_elf64_addr(off + 16)
                sh_offset = self._read_elf64_addr(off + 24)
                sh_size = self._read_elf64_addr(off + 32)
                sh_link = struct.unpack_from("<I", self._data, off + 40)[0]
                sh_info = struct.unpack_from("<I", self._data, off + 44)[0]
                sh_addralign = self._read_elf64_addr(off + 48)
                sh_entsize = self._read_elf64_addr(off + 56)
            else:
                off = ehdr["shoff"] + i * ehdr["shentsize"]
                sh_name = struct.unpack_from("<I", self._data, off)[0]
                sh_type = struct.unpack_from("<I", self._data, off + 4)[0]
                sh_flags = struct.unpack_from("<I", self._data, off + 8)[0]
                sh_addr = self._read_elf32_addr(off + 12)
                sh_offset = self._read_elf32_addr(off + 16)
                sh_size = self._read_elf32_addr(off + 20)
                sh_link = struct.unpack_from("<I", self._data, off + 24)[0]
                sh_info = struct.unpack_from("<I", self._data, off + 28)[0]
                sh_addralign = self._read_elf32_addr(off + 32)
                sh_entsize = self._read_elf32_addr(off + 36)
            sections.append({
                "index": i, "name_idx": sh_name, "type": sh_type,
                "flags": sh_flags, "addr": sh_addr, "offset": sh_offset,
                "size": sh_size, "link": sh_link, "info": sh_info,
                "addralign": sh_addralign, "entsize": sh_entsize,
            })

        # 解析段名称
        shstrtab_sec = sections[ehdr["shstrndx"]] if ehdr["shstrndx"] < len(sections) else None
        if shstrtab_sec and shstrtab_sec["offset"]:
            for s in sections:
                name_end = self._data.find(b'\x00', shstrtab_sec["offset"] + s["name_idx"])
                if name_end > 0:
                    s["name"] = self._data[shstrtab_sec["offset"] + s["name_idx"]:name_end].decode("ascii", errors="replace")
                else:
                    s["name"] = f"<unknown_{s['index']}>"
        return sections

    def _get_section_by_name(self, name: str) -> Optional[dict]:
        """按名称获取 section"""
        sections = self._get_sections()
        for s in sections:
            if s.get("name") == name:
                return s
        return None

    def _get_program_headers(self) -> List[dict]:
        """获取所有 program header"""
        ehdr = self._get_ehdr()
        if not ehdr:
            return []
        phdrs = []
        for i in range(ehdr["phnum"]):
            if self._is_64bit:
                off = ehdr["phoff"] + i * ehdr["phentsize"]
                p_type = struct.unpack_from("<I", self._data, off)[0]
                p_flags = struct.unpack_from("<I", self._data, off + 4)[0]
                p_offset = self._read_elf64_addr(off + 8)
                p_vaddr = self._read_elf64_addr(off + 16)
                p_paddr = self._read_elf64_addr(off + 24)
                p_filesz = self._read_elf64_addr(off + 32)
                p_memsz = self._read_elf64_addr(off + 40)
                p_align = self._read_elf64_addr(off + 48)
            else:
                off = ehdr["phoff"] + i * ehdr["phentsize"]
                p_type = struct.unpack_from("<I", self._data, off)[0]
                p_offset = self._read_elf32_addr(off + 4)
                p_vaddr = self._read_elf32_addr(off + 8)
                p_paddr = self._read_elf32_addr(off + 12)
                p_filesz = self._read_elf32_addr(off + 16)
                p_memsz = self._read_elf32_addr(off + 20)
                p_flags = struct.unpack_from("<I", self._data, off + 24)[0]
                p_align = self._read_elf32_addr(off + 28)
            phdrs.append({
                "index": i, "type": p_type, "flags": p_flags,
                "offset": p_offset, "vaddr": p_vaddr, "paddr": p_paddr,
                "filesz": p_filesz, "memsz": p_memsz, "align": p_align,
            })
        return phdrs

    def _vaddr_to_offset(self, vaddr: int) -> Optional[int]:
        """将虚拟地址转换为文件偏移"""
        phdrs = self._get_program_headers()
        for ph in phdrs:
            if ph["type"] == PT_LOAD:
                if ph["vaddr"] <= vaddr < ph["vaddr"] + ph["memsz"]:
                    return ph["offset"] + (vaddr - ph["vaddr"])
        return None

    def _parse_dynamic_section_internal(self) -> Optional[Dict[int, int]]:
        """内部：解析 .dynamic 段，返回 {tag: value} 字典"""
        if self._cached_dynamic is not None:
            return self._cached_dynamic

        # 先尝试从 section 获取
        dynamic = {}
        dyn_sec = self._get_section_by_name(".dynamic")
        if dyn_sec and dyn_sec["offset"] and dyn_sec["size"]:
            entry_size = DYNAMIC_ENTRY_SIZE_64 if self._is_64bit else DYNAMIC_ENTRY_SIZE_32
            off = dyn_sec["offset"]
            end = off + dyn_sec["size"]
            while off + entry_size <= end:
                if self._is_64bit:
                    d_tag = struct.unpack_from("<q", self._data, off)[0]
                    d_val = struct.unpack_from("<Q", self._data, off + 8)[0]
                else:
                    d_tag = struct.unpack_from("<i", self._data, off)[0]
                    d_val = struct.unpack_from("<I", self._data, off + 4)[0]
                if d_tag == DT_NULL:
                    break
                dynamic[d_tag] = d_val
                off += entry_size

        # 如果 section 方式失败，尝试从 PT_DYNAMIC program header 获取
        if not dynamic:
            phdrs = self._get_program_headers()
            for ph in phdrs:
                if ph["type"] == PT_DYNAMIC and ph["offset"]:
                    entry_size = DYNAMIC_ENTRY_SIZE_64 if self._is_64bit else DYNAMIC_ENTRY_SIZE_32
                    off = ph["offset"]
                    end = off + ph["filesz"]
                    while off + entry_size <= end:
                        if self._is_64bit:
                            d_tag = struct.unpack_from("<q", self._data, off)[0]
                            d_val = struct.unpack_from("<Q", self._data, off + 8)[0]
                        else:
                            d_tag = struct.unpack_from("<i", self._data, off)[0]
                            d_val = struct.unpack_from("<I", self._data, off + 4)[0]
                        if d_tag == DT_NULL:
                            break
                        dynamic[d_tag] = d_val
                        off += entry_size
                    break

        self._cached_dynamic = dynamic
        return dynamic

    def _get_dynamic_tag(self, tag: int) -> Optional[int]:
        """获取动态标签值"""
        dyn = self._parse_dynamic_section_internal()
        if dyn is None:
            return None
        return dyn.get(tag)

    def _get_dynstr(self, offset: int) -> str:
        """从动态字符串表读取字符串"""
        strtab = self._get_dynamic_tag(DT_STRTAB)
        if strtab is None:
            return ""
        file_off = self._vaddr_to_offset(strtab)
        if file_off is None:
            return ""
        return self._read_cstr(file_off + offset)

    def _read_dynsym_entry(self, index: int) -> Optional[dict]:
        """读取动态符号表条目"""
        symtab = self._get_dynamic_tag(DT_SYMTAB)
        if symtab is None:
            return None
        symtab_off = self._vaddr_to_offset(symtab)
        if symtab_off is None:
            return None
        entsize = SYM_ENTRY_SIZE_64 if self._is_64bit else SYM_ENTRY_SIZE_32
        off = symtab_off + index * entsize
        if self._is_64bit:
            st_name = struct.unpack_from("<I", self._data, off)[0]
            st_info = self._data[off + 4]
            st_other = self._data[off + 5]
            st_shndx = struct.unpack_from("<H", self._data, off + 6)[0]
            st_value = self._read_elf64_addr(off + 8)
            st_size = self._read_elf64_addr(off + 16)
        else:
            st_name = struct.unpack_from("<I", self._data, off)[0]
            st_value = self._read_elf32_addr(off + 4)
            st_size = self._read_elf32_addr(off + 8)
            st_info = self._data[off + 12]
            st_other = self._data[off + 13]
            st_shndx = struct.unpack_from("<H", self._data, off + 14)[0]
        st_bind = st_info >> 4
        st_type = st_info & 0xF
        name = self._get_dynstr(st_name) if st_name > 0 else ""
        return {
            "name": name, "value": st_value, "size": st_size,
            "bind": st_bind, "type": st_type, "shndx": st_shndx,
            "other": st_other,
        }

    def _get_plt_entry_size(self) -> int:
        """获取 PLT 条目大小"""
        return PLT_ENTRY_SIZE_64 if self._is_64bit else PLT_ENTRY_SIZE_32

    def _get_got_entry_size(self) -> int:
        """获取 GOT 条目大小"""
        return 8 if self._is_64bit else 4

    def _get_rel_entry_size(self) -> int:
        """获取 REL 条目大小"""
        return REL_ENTRY_SIZE_64 if self._is_64bit else REL_ENTRY_SIZE_32

    def _get_rela_entry_size(self) -> int:
        """获取 RELA 条目大小"""
        return RELA_ENTRY_SIZE_64 if self._is_64bit else RELA_ENTRY_SIZE_32

    # ============================================================
    # 1. 动态段解析
    # ============================================================

    def parse_dynamic_section(self) -> dict:
        """解析 ELF .dynamic 段，提取所有 DT_* 标签

        Returns:
            dict: {
                "success": bool,
                "entries": [{"tag": int, "tag_name": str, "value": int, "value_hex": str}, ...],
                "count": int,
                "libraries": [str, ...],  # DT_NEEDED 库名列表
                "is_64bit": bool,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        dyn = self._parse_dynamic_section_internal()
        if dyn is None or not dyn:
            return {"success": False, "message": "无法解析 .dynamic 段"}

        entries = []
        libraries = []
        for tag, value in sorted(dyn.items()):
            tag_name = DT_TAG_NAMES.get(tag, f"DT_UNKNOWN(0x{tag:X})")
            entry = {
                "tag": tag,
                "tag_name": tag_name,
                "value": value,
                "value_hex": "0x{:X}".format(value) if isinstance(value, int) else str(value),
            }
            # 如果是 DT_NEEDED，解析库名
            if tag == DT_NEEDED:
                lib_name = self._get_dynstr(value)
                entry["library_name"] = lib_name
                libraries.append(lib_name)
            entries.append(entry)

        return {
            "success": True,
            "entries": entries,
            "count": len(entries),
            "libraries": libraries,
            "library_count": len(libraries),
            "is_64bit": self._is_64bit,
        }

    def get_dynamic_entry(self, tag: str) -> dict:
        """获取指定动态标签的值

        Args:
            tag: 标签名称字符串（如 "DT_NEEDED", "DT_PLTGOT", "DT_JMPREL"）

        Returns:
            dict: {"success": bool, "tag": str, "tag_value": int, "value": int, "value_hex": str}
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        # 将标签名转换为数值
        tag_num = None
        for num, name in DT_TAG_NAMES.items():
            if name == tag:
                tag_num = num
                break

        if tag_num is None:
            # 尝试直接解析为整数
            try:
                tag_num = int(tag, 0)
            except (ValueError, TypeError):
                return {"success": False, "message": f"未知的动态标签: {tag}"}

        value = self._get_dynamic_tag(tag_num)
        if value is None:
            return {"success": False, "message": f"动态段中未找到标签 {tag}"}

        result = {
            "success": True,
            "tag": tag,
            "tag_value": tag_num,
            "value": value,
            "value_hex": "0x{:X}".format(value),
        }

        # 如果是 DT_NEEDED，解析库名
        if tag_num == DT_NEEDED:
            result["library_name"] = self._get_dynstr(value)

        return result

    # ============================================================
    # 2. PLT 分析
    # ============================================================

    def parse_plt(self) -> dict:
        """解析 PLT (Procedure Linkage Table)

        识别 PLT 条目，返回每个条目的地址和对应函数猜测。
        x86 PLT 条目结构（16 字节）:
          jmp *GOT[n]          ; ff 25 XX XX XX XX
          push $reloc_index    ; 68 XX XX XX XX
          jmp PLT[0]           ; e9 XX XX XX XX

        Returns:
            dict: {
                "success": bool,
                "plt_address": int,
                "plt_size": int,
                "entry_count": int,
                "entry_size": int,
                "entries": [{"index": int, "address": int, "address_hex": str,
                             "got_address": int, "reloc_index": int,
                             "function_name": str, "bytes": str}, ...],
                "plt0_bytes": str,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        # 获取 .plt section
        plt_sec = self._get_section_by_name(".plt")
        if not plt_sec or not plt_sec["offset"] or not plt_sec["size"]:
            return {"success": False, "message": "未找到 .plt 段"}

        plt_addr = plt_sec["addr"] or 0
        plt_size = plt_sec["size"]
        plt_offset = plt_sec["offset"]
        entry_size = self._get_plt_entry_size()

        entries = []
        plt0_bytes = ""

        # PLT[0] 是特殊的（调用动态链接器）
        plt0_data = self._read_bytes(plt_offset, entry_size)
        if plt0_data:
            plt0_bytes = plt0_data.hex().upper()

        # 从 PLT[1] 开始解析
        off = plt_offset + entry_size
        idx = 1
        while off + entry_size <= plt_offset + plt_size:
            entry_data = self._read_bytes(off, entry_size)
            if not entry_data:
                break

            got_addr = None
            reloc_index = None
            func_name = ""

            # 解析 PLT 条目
            if not self._is_64bit:
                # i386 PLT 条目:
                # ff 25 XX XX XX XX  -> jmp *GOT[n]
                # 68 XX XX XX XX     -> push $reloc_index
                # e9 XX XX XX XX     -> jmp PLT[0]
                if entry_data[0] == 0xFF and entry_data[1] == 0x25:
                    got_addr = struct.unpack_from("<I", entry_data, 2)[0]
                if len(entry_data) >= 11 and entry_data[6] == 0x68:
                    reloc_index = struct.unpack_from("<I", entry_data, 7)[0]
            else:
                # x86-64 PLT 条目:
                # ff 25 XX XX XX XX  -> jmp *GOT[n](%rip)
                if entry_data[0] == 0xFF and entry_data[1] == 0x25:
                    got_offset = struct.unpack_from("<i", entry_data, 2)[0]
                    got_addr = off + 6 + got_offset

            # 尝试解析函数名
            func_name = self._resolve_plt_entry_name(idx)

            entries.append({
                "index": idx,
                "address": plt_addr + (idx * entry_size),
                "address_hex": "0x{:X}".format(plt_addr + (idx * entry_size)),
                "got_address": got_addr,
                "got_address_hex": "0x{:X}".format(got_addr) if got_addr else None,
                "reloc_index": reloc_index,
                "function_name": func_name,
                "bytes": entry_data.hex().upper(),
            })

            idx += 1
            off += entry_size

        return {
            "success": True,
            "plt_address": plt_addr,
            "plt_address_hex": "0x{:X}".format(plt_addr),
            "plt_size": plt_size,
            "entry_count": len(entries),
            "entry_size": entry_size,
            "entries": entries,
            "plt0_bytes": plt0_bytes,
            "plt0_address": plt_addr,
            "plt0_address_hex": "0x{:X}".format(plt_addr),
        }

    def _resolve_plt_entry_name(self, plt_index: int) -> str:
        """通过重定位表解析 PLT 条目对应的函数名"""
        jmprel_addr = self._get_dynamic_tag(DT_JMPREL)
        if jmprel_addr is None:
            return ""

        jmprel_off = self._vaddr_to_offset(jmprel_addr)
        if jmprel_off is None:
            return ""

        pltrel = self._get_dynamic_tag(DT_PLTREL)
        if pltrel is None:
            # 默认假设为 REL
            pltrel = DT_REL

        if pltrel == DT_RELA:
            entry_size = self._get_rela_entry_size()
        else:
            entry_size = self._get_rel_entry_size()

        pltrelsz = self._get_dynamic_tag(DT_PLTRELSZ) or self._get_dynamic_tag(DT_RELASZ) or 0
        count = pltrelsz // entry_size if entry_size > 0 else 0

        for i in range(count):
            off = jmprel_off + i * entry_size
            if pltrel == DT_RELA:
                if self._is_64bit:
                    r_offset = self._read_elf64_addr(off)
                    r_info = self._read_elf64_addr(off + 8)
                else:
                    r_offset = self._read_elf32_addr(off)
                    r_info = struct.unpack_from("<I", self._data, off + 4)[0]
            else:
                if self._is_64bit:
                    r_offset = self._read_elf64_addr(off)
                    r_info = self._read_elf64_addr(off + 8)
                else:
                    r_offset = self._read_elf32_addr(off)
                    r_info = struct.unpack_from("<I", self._data, off + 4)[0]

            r_sym = r_info >> 8 if self._is_64bit else (r_info >> 8)
            sym = self._read_dynsym_entry(r_sym)
            if sym and sym.get("name"):
                # 检查是否匹配 PLT 索引
                # 重定位表条目顺序与 PLT 条目顺序一致
                if i + 1 == plt_index:
                    return sym["name"]

        return ""

    # ============================================================
    # 3. GOT 分析
    # ============================================================

    def parse_got(self) -> dict:
        """解析 GOT (Global Offset Table)

        从 .got.plt 读取当前 GOT 条目值。
        GOT 布局:
          GOT[0] = _DYNAMIC 地址
          GOT[1] = link_map 指针
          GOT[2] = _dl_runtime_resolve 地址
          GOT[3+] = 导入函数地址（lazy binding 下初始指向 PLT 桩代码）

        Returns:
            dict: {
                "success": bool,
                "got_address": int,
                "got_size": int,
                "entry_count": int,
                "entry_size": int,
                "reserved": [dict, ...],   # GOT[0..2]
                "entries": [{"index": int, "address": int, "address_hex": str,
                             "value": int, "value_hex": str, "function_name": str}, ...],
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        got_plt_sec = self._get_section_by_name(".got.plt")
        if not got_plt_sec or not got_plt_sec["offset"] or not got_plt_sec["size"]:
            # 尝试 .got section
            got_plt_sec = self._get_section_by_name(".got")
        if not got_plt_sec or not got_plt_sec["offset"] or not got_plt_sec["size"]:
            return {"success": False, "message": "未找到 .got.plt 或 .got 段"}

        got_addr = got_plt_sec["addr"] or 0
        got_size = got_plt_sec["size"]
        got_offset = got_plt_sec["offset"]
        entry_size = self._get_got_entry_size()

        total_entries = got_size // entry_size if entry_size > 0 else 0

        reserved = []
        entries = []

        for i in range(total_entries):
            off = got_offset + i * entry_size
            if self._is_64bit:
                value = self._read_elf64_addr(off)
            else:
                value = self._read_elf32_addr(off)

            if value is None:
                break

            entry_addr = got_addr + i * entry_size
            entry_data = {
                "index": i,
                "address": entry_addr,
                "address_hex": "0x{:X}".format(entry_addr),
                "value": value,
                "value_hex": "0x{:X}".format(value),
            }

            if i < GOT_RESERVED_ENTRIES:
                role = {0: "_DYNAMIC", 1: "link_map", 2: "_dl_runtime_resolve"}.get(i, "reserved")
                entry_data["role"] = role
                reserved.append(entry_data)
            else:
                # 尝试解析函数名
                func_name = self._resolve_plt_entry_name(i - GOT_RESERVED_ENTRIES + 1)
                entry_data["function_name"] = func_name
                entries.append(entry_data)

        return {
            "success": True,
            "got_address": got_addr,
            "got_address_hex": "0x{:X}".format(got_addr),
            "got_size": got_size,
            "entry_count": len(entries),
            "total_entries": total_entries,
            "entry_size": entry_size,
            "reserved": reserved,
            "entries": entries,
        }

    def parse_pltgot(self) -> dict:
        """解析 .plt.got 段（如果存在）

        .plt.got 是某些编译器生成的额外 PLT 条目，用于处理
        通过 GOT 间接调用的函数。

        Returns:
            dict: {
                "success": bool,
                "exists": bool,
                "address": int,
                "size": int,
                "entry_count": int,
                "entries": [...],
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        pltgot_sec = self._get_section_by_name(".plt.got")
        if not pltgot_sec or not pltgot_sec["offset"] or not pltgot_sec["size"]:
            return {"success": True, "exists": False, "message": ".plt.got 段不存在"}

        pltgot_addr = pltgot_sec["addr"] or 0
        pltgot_size = pltgot_sec["size"]
        pltgot_offset = pltgot_sec["offset"]
        entry_size = self._get_plt_entry_size()

        entries = []
        off = pltgot_offset
        idx = 0
        while off + entry_size <= pltgot_offset + pltgot_size:
            entry_data = self._read_bytes(off, entry_size)
            if not entry_data:
                break
            entries.append({
                "index": idx,
                "offset": off,
                "address": pltgot_addr + (idx * entry_size) if pltgot_addr else off,
                "address_hex": "0x{:X}".format(pltgot_addr + (idx * entry_size) if pltgot_addr else off),
                "bytes": entry_data.hex().upper(),
            })
            idx += 1
            off += entry_size

        return {
            "success": True,
            "exists": True,
            "name": ".plt.got",
            "address": pltgot_addr,
            "address_hex": "0x{:X}".format(pltgot_addr),
            "size": pltgot_size,
            "entry_count": len(entries),
            "section_offset": pltgot_offset,
            "entries": entries,
        }

    def resolve_plt_to_function(self, plt_index: int) -> dict:
        """将 PLT 条目索引映射到对应的导入函数名

        通过解析 .rel.plt 或 .rela.plt 中的重定位条目实现。

        Args:
            plt_index: PLT 条目索引（从 1 开始，PLT[0] 是解析器桩）

        Returns:
            dict: {
                "success": bool,
                "plt_index": int,
                "function_name": str,
                "plt_address": int,
                "got_address": int,
                "source_library": str,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        if plt_index < 1:
            return {"success": False, "message": "PLT 索引必须 >= 1 (PLT[0] 是动态链接器桩)"}

        func_name = self._resolve_plt_entry_name(plt_index)
        if not func_name:
            return {"success": False, "message": f"无法解析 PLT[{plt_index}] 对应的函数名"}

        # 获取 PLT 地址
        plt_sec = self._get_section_by_name(".plt")
        plt_addr = (plt_sec["addr"] or 0) if plt_sec else 0
        entry_size = self._get_plt_entry_size()
        plt_entry_addr = plt_addr + plt_index * entry_size

        # 获取 GOT 地址
        got_sec = self._get_section_by_name(".got.plt") or self._get_section_by_name(".got")
        got_addr = (got_sec["addr"] or 0) if got_sec else 0
        got_entry_size = self._get_got_entry_size()
        got_entry_addr = got_addr + (GOT_RESERVED_ENTRIES + plt_index - 1) * got_entry_size

        # 尝试确定来源库
        source_lib = self._find_function_source_library(func_name)

        return {
            "success": True,
            "plt_index": plt_index,
            "function_name": func_name,
            "plt_address": plt_entry_addr,
            "plt_address_hex": "0x{:X}".format(plt_entry_addr),
            "got_address": got_entry_addr,
            "got_address_hex": "0x{:X}".format(got_entry_addr),
            "source_library": source_lib,
        }

    # ============================================================
    # 4. 导入依赖分析
    # ============================================================

    def parse_imported_libraries(self) -> dict:
        """解析所有 DT_NEEDED 条目，列出 Script.so 依赖的所有共享库

        Returns:
            dict: {
                "success": bool,
                "libraries": [{"name": str, "exports_guess": [str, ...]}, ...],
                "count": int,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        dyn = self._parse_dynamic_section_internal()
        if dyn is None:
            return {"success": False, "message": "无法解析动态段"}

        libraries = []
        for tag, value in dyn.items():
            if tag == DT_NEEDED:
                lib_name = self._get_dynstr(value)
                # 猜测导出函数（基于常见库的已知导出）
                exports_guess = self._guess_library_exports(lib_name)
                libraries.append({
                    "name": lib_name,
                    "strtab_offset": value,
                    "exports_guess": exports_guess,
                    "exports_count": len(exports_guess),
                })

        return {
            "success": True,
            "libraries": libraries,
            "count": len(libraries),
        }

    def _guess_library_exports(self, lib_name: str) -> List[str]:
        """根据库名猜测可能用到的导出函数"""
        common_exports = {
            "libc.so.6": ["printf", "malloc", "free", "memcpy", "memset", "strcmp",
                          "strlen", "fopen", "fclose", "fread", "fwrite", "sprintf",
                          "atoi", "atof", "rand", "srand", "qsort", "time", "exit"],
            "libm.so.6": ["sin", "cos", "tan", "sqrt", "pow", "log", "exp",
                          "floor", "ceil", "fabs", "atan2", "fmod"],
            "libpthread.so.0": ["pthread_create", "pthread_mutex_lock",
                                "pthread_mutex_unlock", "pthread_join"],
            "libdl.so.2": ["dlopen", "dlsym", "dlclose", "dlerror"],
            "libstdc++.so.6": ["_Znwj", "_ZdlPv", "_Znam", "_ZdaPv",
                               "__cxa_atexit", "__cxa_pure_virtual"],
            "libgcc_s.so.1": ["_Unwind_Resume", "__divdi3", "__moddi3"],
            "libwine.so.1": ["wine_init", "wine_main", "WineDbgOutput"],
            "libntdll.dll.so": ["NtCreateFile", "NtClose", "RtlAllocateHeap"],
            "libkernel32.dll.so": ["GetModuleHandleA", "LoadLibraryA",
                                   "GetProcAddress", "VirtualAlloc", "VirtualFree"],
            "libuser32.dll.so": ["MessageBoxA", "GetMessageA", "DispatchMessageA"],
            "libgdi32.dll.so": ["CreateCompatibleDC", "BitBlt", "DeleteDC"],
            "libopengl32.dll.so": ["glClear", "glBegin", "glEnd", "glVertex3f"],
            "libglu32.dll.so": ["gluPerspective", "gluLookAt"],
            "libdirectx.dll.so": ["DirectDrawCreate", "DirectSoundCreate"],
        }

        # 尝试匹配
        for pattern, exports in common_exports.items():
            if pattern in lib_name or lib_name in pattern:
                return exports

        # 通用猜测
        return []

    def build_import_dependency_graph(self) -> dict:
        """构建导入依赖图

        返回节点（库名）和边（依赖关系），支持拓扑排序。

        Returns:
            dict: {
                "success": bool,
                "nodes": [{"id": str, "label": str, "type": str}, ...],
                "edges": [{"from": str, "to": str, "relation": str}, ...],
                "topological_order": [str, ...],
                "root": str,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        libraries_result = self.parse_imported_libraries()
        if not libraries_result.get("success"):
            return libraries_result

        libraries = libraries_result["libraries"]

        # 构建节点
        root_name = "Script.so"
        nodes = [{"id": root_name, "label": root_name, "type": "root"}]

        for lib in libraries:
            nodes.append({
                "id": lib["name"],
                "label": lib["name"],
                "type": "shared_library",
                "exports_count": lib.get("exports_count", 0),
            })

        # 构建边
        edges = []
        for lib in libraries:
            edges.append({
                "from": root_name,
                "to": lib["name"],
                "relation": "DT_NEEDED",
            })

        # 假如有库间依赖的已知信息，可以添加
        known_deps = {
            "libstdc++.so.6": ["libc.so.6", "libm.so.6", "libgcc_s.so.1"],
            "libgcc_s.so.1": ["libc.so.6"],
        }
        for lib in libraries:
            lib_name = lib["name"]
            if lib_name in known_deps:
                for dep in known_deps[lib_name]:
                    if any(l["name"] == dep for l in libraries):
                        edges.append({
                            "from": lib_name,
                            "to": dep,
                            "relation": "known_dependency",
                        })

        # 拓扑排序
        topological_order = self._topological_sort(nodes, edges)

        return {
            "success": True,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "topological_order": topological_order,
            "root": root_name,
        }

    def _topological_sort(self, nodes: List[dict], edges: List[dict]) -> List[str]:
        """对依赖图进行拓扑排序"""
        node_ids = {n["id"] for n in nodes}
        adj = {nid: [] for nid in node_ids}
        in_degree = {nid: 0 for nid in node_ids}

        for edge in edges:
            if edge["from"] in node_ids and edge["to"] in node_ids:
                adj[edge["from"]].append(edge["to"])
                in_degree[edge["to"]] = in_degree.get(edge["to"], 0) + 1

        queue = [nid for nid in node_ids if in_degree.get(nid, 0) == 0]
        result = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result

    def find_external_function(self, lib_name: str, func_name: str) -> dict:
        """在指定导入库中查找函数，返回其 PLT 条目和 GOT 地址

        Args:
            lib_name: 库名（如 "libc.so.6"）
            func_name: 函数名（如 "printf"）

        Returns:
            dict: {
                "success": bool,
                "library": str,
                "function": str,
                "plt_entry": dict or None,
                "got_entry": dict or None,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        # 验证库是否在依赖中
        libraries = self.parse_imported_libraries()
        if not libraries.get("success"):
            return libraries
        lib_names = [l["name"] for l in libraries["libraries"]]
        if lib_name not in lib_names:
            return {
                "success": False,
                "message": f"库 '{lib_name}' 不在 Script.so 的依赖列表中",
                "available_libraries": lib_names,
            }

        # 解析 PLT 和重定位表
        plt_result = self.parse_plt()
        if not plt_result.get("success"):
            return plt_result

        got_result = self.parse_got()
        if not got_result.get("success"):
            return got_result

        # 查找函数
        plt_entry = None
        got_entry = None
        for entry in plt_result.get("entries", []):
            if entry.get("function_name") == func_name:
                plt_entry = entry
                break

        for entry in got_result.get("entries", []):
            if entry.get("function_name") == func_name:
                got_entry = entry
                break

        if not plt_entry and not got_entry:
            return {
                "success": False,
                "message": f"未找到函数 '{func_name}' 的 PLT/GOT 条目",
                "library": lib_name,
                "function": func_name,
            }

        return {
            "success": True,
            "library": lib_name,
            "function": func_name,
            "plt_entry": plt_entry,
            "got_entry": got_entry,
        }

    # ============================================================
    # 5. 重定位分析
    # ============================================================

    def parse_rel_dyn(self) -> dict:
        """解析 .rel.dyn 重定位表

        列出所有动态重定位条目（类型、偏移、符号）。
        这些是运行时由动态链接器处理的非 PLT 重定位。

        Returns:
            dict: {
                "success": bool,
                "entries": [{"offset": int, "type": int, "type_name": str,
                             "symbol": str, "symbol_index": int}, ...],
                "count": int,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        rel_sec = self._get_section_by_name(".rel.dyn")
        if not rel_sec or not rel_sec["offset"] or not rel_sec["size"]:
            return {"success": False, "message": "未找到 .rel.dyn 段"}

        entry_size = self._get_rel_entry_size()
        count = rel_sec["size"] // entry_size if entry_size > 0 else 0
        entries = []

        for i in range(count):
            off = rel_sec["offset"] + i * entry_size
            if self._is_64bit:
                r_offset = self._read_elf64_addr(off)
                r_info = self._read_elf64_addr(off + 8)
                r_type = r_info & 0xFFFFFFFF
                r_sym = r_info >> 32
            else:
                r_offset = self._read_elf32_addr(off)
                r_info = struct.unpack_from("<I", self._data, off + 4)[0]
                r_type = r_info & 0xFF
                r_sym = r_info >> 8

            type_name = self._get_reloc_type_name(r_type)
            sym = self._read_dynsym_entry(r_sym)
            sym_name = sym["name"] if sym else ""

            entries.append({
                "index": i,
                "offset": r_offset,
                "offset_hex": "0x{:X}".format(r_offset),
                "type": r_type,
                "type_name": type_name,
                "symbol_index": r_sym,
                "symbol": sym_name,
            })

        return {
            "success": True,
            "entries": entries,
            "count": len(entries),
            "section": ".rel.dyn",
        }

    def parse_rel_plt(self) -> dict:
        """解析 .rel.plt 重定位表

        这是 PLT 重定位，直接关联到导入函数。
        返回每个导入函数的 PLT 偏移和符号名。

        Returns:
            dict: {
                "success": bool,
                "entries": [{"index": int, "plt_index": int, "offset": int,
                             "offset_hex": str, "type": int, "type_name": str,
                             "symbol": str, "symbol_index": int}, ...],
                "count": int,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        rel_plt_sec = self._get_section_by_name(".rel.plt")
        if not rel_plt_sec or not rel_plt_sec["offset"] or not rel_plt_sec["size"]:
            # 尝试 .rela.plt
            rel_plt_sec = self._get_section_by_name(".rela.plt")
            if not rel_plt_sec or not rel_plt_sec["offset"] or not rel_plt_sec["size"]:
                return {"success": False, "message": "未找到 .rel.plt 或 .rela.plt 段"}

        is_rela = rel_plt_sec["type"] == SHT_RELA
        entry_size = self._get_rela_entry_size() if is_rela else self._get_rel_entry_size()
        count = rel_plt_sec["size"] // entry_size if entry_size > 0 else 0
        entries = []

        for i in range(count):
            off = rel_plt_sec["offset"] + i * entry_size
            if is_rela:
                if self._is_64bit:
                    r_offset = self._read_elf64_addr(off)
                    r_info = self._read_elf64_addr(off + 8)
                    r_addend = self._read_elf64_addr(off + 16) if off + 16 + 8 <= len(self._data) else 0
                    r_type = r_info & 0xFFFFFFFF
                    r_sym = r_info >> 32
                else:
                    r_offset = self._read_elf32_addr(off)
                    r_info = struct.unpack_from("<I", self._data, off + 4)[0]
                    r_addend = struct.unpack_from("<i", self._data, off + 8)[0]
                    r_type = r_info & 0xFF
                    r_sym = r_info >> 8
            else:
                if self._is_64bit:
                    r_offset = self._read_elf64_addr(off)
                    r_info = self._read_elf64_addr(off + 8)
                    r_type = r_info & 0xFFFFFFFF
                    r_sym = r_info >> 32
                else:
                    r_offset = self._read_elf32_addr(off)
                    r_info = struct.unpack_from("<I", self._data, off + 4)[0]
                    r_type = r_info & 0xFF
                    r_sym = r_info >> 8
                r_addend = None

            type_name = self._get_reloc_type_name(r_type)
            sym = self._read_dynsym_entry(r_sym)
            sym_name = sym["name"] if sym else ""

            entries.append({
                "index": i,
                "plt_index": i + 1,  # PLT[0] is reserved
                "offset": r_offset,
                "offset_hex": "0x{:X}".format(r_offset),
                "type": r_type,
                "type_name": type_name,
                "symbol_index": r_sym,
                "symbol": sym_name,
                "addend": r_addend,
                "addend_hex": "0x{:X}".format(r_addend) if r_addend is not None else None,
            })

        return {
            "success": True,
            "entries": entries,
            "count": len(entries),
            "section": rel_plt_sec.get("name", ".rel.plt"),
            "is_rela": is_rela,
        }

    def _get_reloc_type_name(self, r_type: int) -> str:
        """获取重定位类型名称"""
        names = {
            R_386_NONE: "R_386_NONE",
            R_386_32: "R_386_32",
            R_386_PC32: "R_386_PC32",
            R_386_GOT32: "R_386_GOT32",
            R_386_PLT32: "R_386_PLT32",
            R_386_COPY: "R_386_COPY",
            R_386_GLOB_DAT: "R_386_GLOB_DAT",
            R_386_JMP_SLOT: "R_386_JMP_SLOT",
            R_386_RELATIVE: "R_386_RELATIVE",
            R_386_GOTOFF: "R_386_GOTOFF",
            R_386_GOTPC: "R_386_GOTPC",
        }
        return names.get(r_type, f"R_UNKNOWN(0x{r_type:X})")

    def get_imported_functions(self) -> dict:
        """汇总所有通过 PLT 导入的函数列表，按库分组

        Returns:
            dict: {
                "success": bool,
                "total": int,
                "by_library": {lib_name: [{"name": str, "plt_index": int, ...}, ...]},
                "all_functions": [{"name": str, "plt_index": int, "library": str}, ...],
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        rel_plt = self.parse_rel_plt()
        if not rel_plt.get("success"):
            return rel_plt

        # 已知的库-函数映射（基于常见符号前缀）
        lib_patterns = {
            "libc.so.6": ["printf", "malloc", "free", "memcpy", "memset", "strcmp",
                          "strlen", "fopen", "fclose", "fread", "fwrite", "sprintf",
                          "atoi", "atof", "rand", "srand", "qsort", "time", "exit",
                          "puts", "scanf", "sscanf", "calloc", "realloc", "strcpy",
                          "strncpy", "strcat", "strncat", "strchr", "strrchr",
                          "strstr", "memmove", "memcmp", "memchr", "perror", "abort"],
            "libm.so.6": ["sin", "cos", "tan", "sqrt", "pow", "log", "exp",
                          "floor", "ceil", "fabs", "atan2", "fmod", "sinf",
                          "cosf", "sqrtf", "powf", "logf", "expf"],
            "libstdc++.so.6": ["_Znwj", "_ZdlPv", "_Znam", "_ZdaPv",
                               "__cxa_atexit", "__cxa_pure_virtual",
                               "_Znwm", "_ZdlPvm", "_ZSt9terminatev"],
            "libgcc_s.so.1": ["_Unwind_Resume", "__divdi3", "__moddi3",
                              "__udivdi3", "__umoddi3"],
            "libpthread.so.0": ["pthread_create", "pthread_mutex_lock",
                                "pthread_mutex_unlock", "pthread_join",
                                "pthread_detach", "pthread_self"],
        }

        by_library = {}
        all_functions = []
        unmatched = []

        for entry in rel_plt.get("entries", []):
            func_name = entry.get("symbol", "")
            if not func_name:
                continue

            func_info = {
                "name": func_name,
                "plt_index": entry.get("plt_index"),
                "offset": entry.get("offset"),
                "offset_hex": entry.get("offset_hex"),
                "type": entry.get("type_name"),
                "symbol_index": entry.get("symbol_index"),
            }

            # 尝试按库分类
            matched = False
            for lib, patterns in lib_patterns.items():
                if func_name in patterns:
                    if lib not in by_library:
                        by_library[lib] = []
                    func_info["library"] = lib
                    by_library[lib].append(func_info)
                    matched = True
                    break

            if not matched:
                unmatched.append(func_name)
                func_info["library"] = "unknown"
                if "unknown" not in by_library:
                    by_library["unknown"] = []
                by_library["unknown"].append(func_info)

            all_functions.append(func_info)

        return {
            "success": True,
            "total": len(all_functions),
            "by_library": by_library,
            "library_count": len(by_library),
            "all_functions": all_functions,
            "unmatched_count": len(unmatched),
            "unmatched": unmatched[:50],
        }

    def _find_function_source_library(self, func_name: str) -> str:
        """尝试确定函数来源库"""
        common_mapping = {
            "printf": "libc.so.6", "malloc": "libc.so.6", "free": "libc.so.6",
            "memcpy": "libc.so.6", "memset": "libc.so.6", "strcmp": "libc.so.6",
            "strlen": "libc.so.6", "fopen": "libc.so.6", "fclose": "libc.so.6",
            "sin": "libm.so.6", "cos": "libm.so.6", "sqrt": "libm.so.6",
            "pow": "libm.so.6", "log": "libm.so.6", "exp": "libm.so.6",
            "_Znwj": "libstdc++.so.6", "_ZdlPv": "libstdc++.so.6",
            "_Unwind_Resume": "libgcc_s.so.1",
            "pthread_create": "libpthread.so.0",
        }
        return common_mapping.get(func_name, "unknown")

    # ============================================================
    # 6. GOT 覆写 (GOT Overwrite)
    # ============================================================

    def build_got_overwrite(self, func_name: str, new_address: int) -> dict:
        """构建 GOT 覆写补丁

        修改 GOT 中指定函数的条目指向新地址。
        这是比 Code Cave 更轻量级的运行时修改方式。

        Args:
            func_name: 目标函数名（如 "printf"）
            new_address: 新地址（虚拟地址）

        Returns:
            dict: {
                "success": bool,
                "function": str,
                "got_entry": int,
                "old_value": int,
                "new_value": int,
                "file_offset": int,
                "patch_bytes": str,
                "message": str,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        # 查找函数在 GOT 中的条目
        got_result = self.parse_got()
        if not got_result.get("success"):
            return got_result

        target_entry = None
        for entry in got_result.get("entries", []):
            if entry.get("function_name") == func_name:
                target_entry = entry
                break

        if not target_entry:
            # 尝试通过重定位表查找
            rel_plt = self.parse_rel_plt()
            if rel_plt.get("success"):
                for entry in rel_plt.get("entries", []):
                    if entry.get("symbol") == func_name:
                        got_addr = self._get_dynamic_tag(DT_PLTGOT)
                        if got_addr:
                            got_entry_size = self._get_got_entry_size()
                            got_entry_addr = got_addr + (GOT_RESERVED_ENTRIES + entry["plt_index"] - 1) * got_entry_size
                            got_entry_off = self._vaddr_to_offset(got_entry_addr)
                            if got_entry_off is not None:
                                old_value = self._read_addr(got_entry_off)
                                target_entry = {
                                    "index": GOT_RESERVED_ENTRIES + entry["plt_index"] - 1,
                                    "address": got_entry_addr,
                                    "address_hex": "0x{:X}".format(got_entry_addr),
                                    "value": old_value,
                                    "value_hex": "0x{:X}".format(old_value) if old_value else "",
                                    "function_name": func_name,
                                }
                        break

        if not target_entry:
            return {"success": False, "message": f"未找到函数 '{func_name}' 的 GOT 条目"}

        # 将 GOT 虚拟地址转换为文件偏移
        file_offset = self._vaddr_to_offset(target_entry["address"])
        if file_offset is None:
            return {"success": False, "message": "无法将 GOT 虚拟地址转换为文件偏移"}

        old_value = target_entry["value"]
        new_value = new_address

        # 构建补丁字节
        if self._is_64bit:
            patch_bytes = struct.pack("<Q", new_value)
        else:
            patch_bytes = struct.pack("<I", new_value)

        return {
            "success": True,
            "function": func_name,
            "got_entry": target_entry["address"],
            "got_entry_hex": target_entry["address_hex"],
            "got_index": target_entry["index"],
            "old_value": old_value,
            "old_value_hex": "0x{:X}".format(old_value) if old_value else "",
            "new_value": new_value,
            "new_value_hex": "0x{:X}".format(new_value),
            "file_offset": file_offset,
            "file_offset_hex": "0x{:X}".format(file_offset),
            "patch_bytes": patch_bytes.hex().upper(),
            "patch_size": len(patch_bytes),
            "message": f"GOT 覆写补丁: {func_name} @ GOT[{target_entry['index']}] -> 0x{new_value:X}",
        }

    def restore_got_entry(self, func_name: str) -> dict:
        """恢复被覆写的 GOT 条目到原始值

        原始值是 PLT 桩代码中的 push 指令后面的地址
        （即 PLT[func_index] + 6）

        Args:
            func_name: 目标函数名

        Returns:
            dict: {
                "success": bool,
                "function": str,
                "got_entry": int,
                "restored_value": int,
                "file_offset": int,
                "patch_bytes": str,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        # 查找函数在 PLT 中的条目
        plt_result = self.parse_plt()
        if not plt_result.get("success"):
            return plt_result

        plt_entry = None
        for entry in plt_result.get("entries", []):
            if entry.get("function_name") == func_name:
                plt_entry = entry
                break

        if not plt_entry:
            return {"success": False, "message": f"未找到函数 '{func_name}' 的 PLT 条目"}

        # 原始 GOT 值 = PLT 条目地址 + 6（指向 push 指令后的地址）
        plt_addr = plt_entry["address"]
        original_value = plt_addr + 6

        # 获取 GOT 条目地址
        got_result = self.parse_got()
        got_entry = None
        for entry in got_result.get("entries", []):
            if entry.get("function_name") == func_name:
                got_entry = entry
                break

        if not got_entry:
            return {"success": False, "message": f"未找到函数 '{func_name}' 的 GOT 条目"}

        file_offset = self._vaddr_to_offset(got_entry["address"])
        if file_offset is None:
            return {"success": False, "message": "无法将 GOT 虚拟地址转换为文件偏移"}

        if self._is_64bit:
            patch_bytes = struct.pack("<Q", original_value)
        else:
            patch_bytes = struct.pack("<I", original_value)

        return {
            "success": True,
            "function": func_name,
            "got_entry": got_entry["address"],
            "got_entry_hex": got_entry["address_hex"],
            "restored_value": original_value,
            "restored_value_hex": "0x{:X}".format(original_value),
            "file_offset": file_offset,
            "file_offset_hex": "0x{:X}".format(file_offset),
            "patch_bytes": patch_bytes.hex().upper(),
            "patch_size": len(patch_bytes),
            "message": f"GOT 恢复: {func_name} -> PLT 桩 0x{original_value:X}",
        }

    def list_hookable_functions(self) -> dict:
        """列出所有可以被 GOT 覆写的函数

        即所有通过 PLT 导入的函数。对每个函数给出其 PLT 地址、
        GOT 地址、来源库和函数签名猜测。

        Returns:
            dict: {
                "success": bool,
                "functions": [{"name": str, "plt_index": int, "plt_address": int,
                               "got_address": int, "got_file_offset": int,
                               "library": str, "signature_guess": str}, ...],
                "count": int,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        # 获取所有信息
        imported = self.get_imported_functions()
        if not imported.get("success"):
            return imported

        plt_result = self.parse_plt()
        got_result = self.parse_got()

        functions = []
        for func in imported.get("all_functions", []):
            func_name = func["name"]
            plt_index = func.get("plt_index", 0)

            # 获取 PLT 地址
            plt_addr = None
            if plt_result.get("success"):
                for entry in plt_result.get("entries", []):
                    if entry["index"] == plt_index:
                        plt_addr = entry["address"]
                        break

            # 获取 GOT 地址和文件偏移
            got_addr = None
            got_file_offset = None
            if got_result.get("success"):
                for entry in got_result.get("entries", []):
                    if entry.get("function_name") == func_name:
                        got_addr = entry["address"]
                        got_file_offset = self._vaddr_to_offset(got_addr)
                        break

            # 签名猜测
            signature = self._guess_function_signature(func_name)

            # 来源库
            library = func.get("library", "unknown")

            functions.append({
                "name": func_name,
                "plt_index": plt_index,
                "plt_address": plt_addr,
                "plt_address_hex": "0x{:X}".format(plt_addr) if plt_addr else None,
                "got_address": got_addr,
                "got_address_hex": "0x{:X}".format(got_addr) if got_addr else None,
                "got_file_offset": got_file_offset,
                "got_file_offset_hex": "0x{:X}".format(got_file_offset) if got_file_offset else None,
                "library": library,
                "signature_guess": signature,
                "hookable": True,
            })

        return {
            "success": True,
            "functions": functions,
            "count": len(functions),
        }

    def _guess_function_signature(self, func_name: str) -> str:
        """猜测函数签名（基于常见 C 库函数）"""
        signatures = {
            "printf": "int printf(const char *format, ...)",
            "sprintf": "int sprintf(char *str, const char *format, ...)",
            "malloc": "void *malloc(size_t size)",
            "free": "void free(void *ptr)",
            "calloc": "void *calloc(size_t nmemb, size_t size)",
            "realloc": "void *realloc(void *ptr, size_t size)",
            "memcpy": "void *memcpy(void *dest, const void *src, size_t n)",
            "memset": "void *memset(void *s, int c, size_t n)",
            "memmove": "void *memmove(void *dest, const void *src, size_t n)",
            "strcmp": "int strcmp(const char *s1, const char *s2)",
            "strlen": "size_t strlen(const char *s)",
            "strcpy": "char *strcpy(char *dest, const char *src)",
            "fopen": "FILE *fopen(const char *pathname, const char *mode)",
            "fclose": "int fclose(FILE *stream)",
            "fread": "size_t fread(void *ptr, size_t size, size_t nmemb, FILE *stream)",
            "fwrite": "size_t fwrite(const void *ptr, size_t size, size_t nmemb, FILE *stream)",
            "atoi": "int atoi(const char *nptr)",
            "atof": "double atof(const char *nptr)",
            "rand": "int rand(void)",
            "srand": "void srand(unsigned int seed)",
            "qsort": "void qsort(void *base, size_t nmemb, size_t size, int (*compar)(const void *, const void *))",
            "time": "time_t time(time_t *tloc)",
            "exit": "void exit(int status)",
            "sin": "double sin(double x)",
            "cos": "double cos(double x)",
            "sqrt": "double sqrt(double x)",
            "pow": "double pow(double x, double y)",
            "floor": "double floor(double x)",
            "ceil": "double ceil(double x)",
            "pthread_create": "int pthread_create(pthread_t *thread, const pthread_attr_t *attr, void *(*start)(void *), void *arg)",
            "pthread_mutex_lock": "int pthread_mutex_lock(pthread_mutex_t *mutex)",
            "pthread_mutex_unlock": "int pthread_mutex_unlock(pthread_mutex_t *mutex)",
            "dlopen": "void *dlopen(const char *filename, int flags)",
            "dlsym": "void *dlsym(void *handle, const char *symbol)",
        }
        return signatures.get(func_name, "unknown")

    # ============================================================
    # 7. 运行时模拟
    # ============================================================

    def simulate_plt_call(self, plt_index: int) -> dict:
        """模拟 PLT 调用过程

        追踪 PLT -> GOT -> 动态链接器解析 -> 目标函数的完整流程。

        Args:
            plt_index: PLT 条目索引（从 1 开始）

        Returns:
            dict: {
                "success": bool,
                "plt_index": int,
                "simulation": [{"step": int, "stage": str, "description": str}, ...],
                "final_target": str,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        if plt_index < 1:
            return {"success": False, "message": "PLT 索引必须 >= 1"}

        func_name = self._resolve_plt_entry_name(plt_index)

        plt_sec = self._get_section_by_name(".plt")
        plt_addr = (plt_sec["addr"] or 0) if plt_sec else 0
        entry_size = self._get_plt_entry_size()
        plt_entry_addr = plt_addr + plt_index * entry_size

        got_plt_sec = self._get_section_by_name(".got.plt") or self._get_section_by_name(".got")
        got_addr = (got_plt_sec["addr"] or 0) if got_plt_sec else 0
        got_entry_size = self._get_got_entry_size()
        got_entry_addr = got_addr + (GOT_RESERVED_ENTRIES + plt_index - 1) * got_entry_size

        simulation = [
            {
                "step": 1,
                "stage": "CALL_PLT",
                "description": f"代码执行 CALL 指令，跳转到 PLT[{plt_index}] (0x{plt_entry_addr:X})",
                "address": plt_entry_addr,
                "address_hex": "0x{:X}".format(plt_entry_addr),
            },
            {
                "step": 2,
                "stage": "PLT_JMP_GOT",
                "description": f"PLT[{plt_index}] 执行 JMP *GOT[{GOT_RESERVED_ENTRIES + plt_index - 1}] (0x{got_entry_addr:X})",
                "address": got_entry_addr,
                "address_hex": "0x{:X}".format(got_entry_addr),
            },
        ]

        # 检查 GOT 条目当前值
        got_entry_off = self._vaddr_to_offset(got_entry_addr)
        got_value = None
        if got_entry_off is not None:
            got_value = self._read_addr(got_entry_off)

        if got_value is not None and got_value != plt_entry_addr + 6:
            # GOT 已被解析，直接跳转
            simulation.append({
                "step": 3,
                "stage": "GOT_RESOLVED",
                "description": f"GOT 条目已被解析为 0x{got_value:X}，直接跳转到目标函数",
                "address": got_value,
                "address_hex": "0x{:X}".format(got_value),
            })
            simulation.append({
                "step": 4,
                "stage": "EXECUTE_FUNCTION",
                "description": f"执行目标函数: {func_name or 'unknown'}",
                "function": func_name or "unknown",
            })
        else:
            # 首次调用，需要动态链接器解析
            simulation.append({
                "step": 3,
                "stage": "GOT_NOT_RESOLVED",
                "description": f"GOT 条目指向 PLT[{plt_index}]+6 (0x{plt_entry_addr + 6:X})，需要动态链接器解析",
                "address": plt_entry_addr + 6,
                "address_hex": "0x{:X}".format(plt_entry_addr + 6),
            })
            simulation.append({
                "step": 4,
                "stage": "PUSH_RELOC_INDEX",
                "description": f"PLT[{plt_index}] 执行 PUSH 指令，将重定位索引压栈",
            })
            simulation.append({
                "step": 5,
                "stage": "JMP_PLT0",
                "description": f"PLT[{plt_index}] 执行 JMP PLT[0]，跳转到动态链接器解析例程",
                "address": plt_addr,
                "address_hex": "0x{:X}".format(plt_addr),
            })
            simulation.append({
                "step": 6,
                "stage": "RESOLVER",
                "description": f"PLT[0] 压入 link_map 指针，跳转到 _dl_runtime_resolve",
            })
            simulation.append({
                "step": 7,
                "stage": "SYMBOL_RESOLUTION",
                "description": f"_dl_runtime_resolve 查找符号 '{func_name or 'unknown'}'，解析其地址",
            })
            simulation.append({
                "step": 8,
                "stage": "GOT_UPDATE",
                "description": f"解析结果写入 GOT[{GOT_RESERVED_ENTRIES + plt_index - 1}]，后续调用将直接跳转",
            })
            simulation.append({
                "step": 9,
                "stage": "EXECUTE_FUNCTION",
                "description": f"跳转到解析后的函数: {func_name or 'unknown'}",
                "function": func_name or "unknown",
            })

        return {
            "success": True,
            "plt_index": plt_index,
            "function_name": func_name or "unknown",
            "simulation": simulation,
            "step_count": len(simulation),
            "final_target": func_name or "unknown",
        }

    def trace_function_dependencies(self, func_name: str) -> dict:
        """追踪指定函数的调用链

        通过分析 PLT 调用和代码反汇编，构建函数调用图。

        Args:
            func_name: 目标函数名

        Returns:
            dict: {
                "success": bool,
                "function": str,
                "direct_calls": [str, ...],
                "callers": [str, ...],
                "call_graph": dict,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        # 查找函数的 PLT 条目
        plt_result = self.parse_plt()
        if not plt_result.get("success"):
            return plt_result

        plt_entry = None
        for entry in plt_result.get("entries", []):
            if entry.get("function_name") == func_name:
                plt_entry = entry
                break

        if not plt_entry:
            return {"success": False, "message": f"未找到函数 '{func_name}' 的 PLT 条目"}

        # 尝试通过 ScriptSOAnalyzer 反汇编 .text 段来查找调用者
        callers = []
        direct_calls = []

        if self._analyzer:
            try:
                # 查找对 PLT 条目的交叉引用
                xrefs = self._analyzer.find_xrefs_to(plt_entry["address"])
                if xrefs.get("success"):
                    for ref in xrefs.get("refs", []):
                        callers.append({
                            "address": ref.get("from_hex"),
                            "type": ref.get("type"),
                            "instruction": ref.get("instruction"),
                            "section": ref.get("section"),
                        })
            except Exception as e:
                logger.warning("Failed to find xrefs: %s", e)

        # 获取该函数依赖的其他函数
        # （通过分析 PLT 重定位，找到来自同一库的其他函数）
        imported = self.get_imported_functions()
        if imported.get("success"):
            for func in imported.get("all_functions", []):
                if func.get("library") == self._find_function_source_library(func_name):
                    if func["name"] != func_name:
                        direct_calls.append(func["name"])

        return {
            "success": True,
            "function": func_name,
            "function_address": plt_entry["address"],
            "function_address_hex": plt_entry["address_hex"],
            "direct_calls": direct_calls[:50],
            "callers": callers,
            "caller_count": len(callers),
            "call_graph": {
                "node": func_name,
                "dependencies": direct_calls[:50],
                "dependents": [c.get("address") for c in callers],
            },
        }

    # ============================================================
    # 8. 段权限分析
    # ============================================================

    def analyze_segment_permissions(self) -> dict:
        """分析 Program Header 中各段的权限

        标记哪些段可写（可用于 GOT 覆写）、哪些段可执行。

        Returns:
            dict: {
                "success": bool,
                "segments": [{"index": int, "type": int, "type_name": str,
                              "vaddr": int, "memsz": int, "flags": int,
                              "permissions": str, "rwx": {"R": bool, "W": bool, "X": bool}}, ...],
                "count": int,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        phdrs = self._get_program_headers()

        type_names = {
            PT_NULL: "PT_NULL",
            PT_LOAD: "PT_LOAD",
            PT_DYNAMIC: "PT_DYNAMIC",
            PT_INTERP: "PT_INTERP",
            PT_NOTE: "PT_NOTE",
            PT_SHLIB: "PT_SHLIB",
            PT_PHDR: "PT_PHDR",
            PT_TLS: "PT_TLS",
            PT_GNU_EH_FRAME: "PT_GNU_EH_FRAME",
            PT_GNU_STACK: "PT_GNU_STACK",
            PT_GNU_RELRO: "PT_GNU_RELRO",
        }

        segments = []
        for ph in phdrs:
            flags = ph["flags"]
            r = bool(flags & PF_R)
            w = bool(flags & PF_W)
            x = bool(flags & PF_X)
            perm_str = ("R" if r else "-") + ("W" if w else "-") + ("X" if x else "-")

            # 判断段用途
            got_overwritable = False
            if ph["type"] == PT_LOAD and w:
                # 可写段可能包含 GOT
                got_overwritable = True

            executable = x
            writable = w

            segments.append({
                "index": ph["index"],
                "type": ph["type"],
                "type_name": type_names.get(ph["type"], f"PT_UNKNOWN(0x{ph['type']:X})"),
                "vaddr": ph["vaddr"],
                "vaddr_hex": "0x{:X}".format(ph["vaddr"]),
                "offset": ph["offset"],
                "offset_hex": "0x{:X}".format(ph["offset"]),
                "filesz": ph["filesz"],
                "memsz": ph["memsz"],
                "flags": flags,
                "permissions": perm_str,
                "rwx": {"R": r, "W": w, "X": x},
                "executable": executable,
                "writable": writable,
                "got_overwritable": got_overwritable,
            })

        return {
            "success": True,
            "segments": segments,
            "count": len(segments),
        }

    def find_writable_executable(self) -> dict:
        """查找可写可执行段（W^X 违规）

        这些是潜在的安全问题或可利用区域。
        正常的 ELF 不应该存在同时具有 W 和 X 权限的段。

        Returns:
            dict: {
                "success": bool,
                "wx_segments": [...],
                "count": int,
                "has_violation": bool,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        permissions = self.analyze_segment_permissions()
        if not permissions.get("success"):
            return permissions

        wx_segments = []
        for seg in permissions.get("segments", []):
            rwx = seg.get("rwx", {})
            if rwx.get("W") and rwx.get("X"):
                wx_segments.append({
                    "index": seg["index"],
                    "type": seg["type_name"],
                    "vaddr": seg["vaddr"],
                    "vaddr_hex": seg["vaddr_hex"],
                    "memsz": seg["memsz"],
                    "permissions": seg["permissions"],
                    "risk": "high" if seg["type"] == PT_LOAD else "medium",
                    "note": "可写可执行段 (W^X violation) - 可用于代码注入",
                })

        return {
            "success": True,
            "wx_segments": wx_segments,
            "count": len(wx_segments),
            "has_violation": len(wx_segments) > 0,
        }

    # ============================================================
    # 9. 符号版本
    # ============================================================

    def parse_gnu_version(self) -> dict:
        """解析 GNU 符号版本信息

        解析 .gnu.version 和 .gnu.version_r 段。

        Returns:
            dict: {
                "success": bool,
                "version_definitions": [...],
                "version_requirements": [{"library": str, "versions": [str, ...]}, ...],
                "count": int,
            }
        """
        if not self._check_loaded():
            return {"success": False, "message": "Script.so 不存在或无法读取"}

        version_requirements = []

        # 解析 .gnu.version_r (Verneed)
        verneed_sec = self._get_section_by_name(".gnu.version_r")
        if verneed_sec and verneed_sec["offset"] and verneed_sec["size"]:
            off = verneed_sec["offset"]
            end = off + verneed_sec["size"]
            while off + 16 <= end:
                vn_version = struct.unpack_from("<H", self._data, off)[0]
                vn_cnt = struct.unpack_from("<H", self._data, off + 2)[0]
                vn_file = struct.unpack_from("<I", self._data, off + 4)[0]
                vn_aux = struct.unpack_from("<I", self._data, off + 8)[0]
                vn_next = struct.unpack_from("<I", self._data, off + 12)[0]

                # 读取库名（从动态字符串表）
                lib_name = self._get_dynstr(vn_file)

                # 解析 Vernaux 条目
                versions = []
                aux_off = off + vn_aux
                for _ in range(vn_cnt):
                    if aux_off + 16 > end:
                        break
                    vna_hash = struct.unpack_from("<I", self._data, aux_off)[0]
                    vna_flags = struct.unpack_from("<H", self._data, aux_off + 4)[0]
                    vna_other = struct.unpack_from("<H", self._data, aux_off + 6)[0]
                    vna_name = struct.unpack_from("<I", self._data, aux_off + 8)[0]
                    vna_next = struct.unpack_from("<I", self._data, aux_off + 12)[0]

                    version_name = self._get_dynstr(vna_name)
                    versions.append({
                        "hash": vna_hash,
                        "flags": vna_flags,
                        "other": vna_other,
                        "name": version_name,
                    })

                    if vna_next == 0:
                        break
                    aux_off += vna_next

                version_requirements.append({
                    "library": lib_name,
                    "version_count": vn_cnt,
                    "versions": versions,
                    "file_offset": vn_file,
                })

                if vn_next == 0:
                    break
                off += vn_next

        # 解析 .gnu.version (Versym)
        versym_sec = self._get_section_by_name(".gnu.version")
        versym_count = 0
        if versym_sec and versym_sec["offset"] and versym_sec["size"]:
            versym_count = versym_sec["size"] // 2  # 每个条目 2 字节

        # 解析 .gnu.version_d (Verdef) - 如果存在
        version_definitions = []
        verdef_sec = self._get_section_by_name(".gnu.version_d")
        if verdef_sec and verdef_sec["offset"] and verdef_sec["size"]:
            off = verdef_sec["offset"]
            end = off + verdef_sec["size"]
            while off + 20 <= end:
                vd_version = struct.unpack_from("<H", self._data, off)[0]
                vd_flags = struct.unpack_from("<H", self._data, off + 2)[0]
                vd_ndx = struct.unpack_from("<H", self._data, off + 4)[0]
                vd_cnt = struct.unpack_from("<H", self._data, off + 6)[0]
                vd_hash = struct.unpack_from("<I", self._data, off + 8)[0]
                vd_aux = struct.unpack_from("<I", self._data, off + 12)[0]
                vd_next = struct.unpack_from("<I", self._data, off + 16)[0]

                version_definitions.append({
                    "version": vd_version,
                    "flags": vd_flags,
                    "index": vd_ndx,
                    "count": vd_cnt,
                    "hash": vd_hash,
                })

                if vd_next == 0:
                    break
                off += vd_next

        return {
            "success": True,
            "version_definitions": version_definitions,
            "version_requirements": version_requirements,
            "version_req_count": len(version_requirements),
            "versym_count": versym_count,
            "has_gnu_version": len(version_requirements) > 0 or len(version_definitions) > 0,
        }

    # ============================================================
    # 10. 工具方法
    # ============================================================

    @staticmethod
    def get_info() -> dict:
        """返回模块信息

        Returns:
            dict: {
                "name": str,
                "version": str,
                "description": str,
                "author": str,
                "capabilities": [str, ...],
            }
        """
        return {
            "name": "ScriptSO Dynamic Analyzer",
            "version": "1.0.0",
            "description": "Script.so PLT/GOT 深度动态分析模块 - 动态段、PLT/GOT、重定位、导入依赖、GOT 覆写、段权限、符号版本分析",
            "author": "San7ModMaker",
            "module": "core.scriptso_dynamic.ScriptSODynamic",
            "capabilities": [
                "parse_dynamic_section - 解析 .dynamic 段",
                "get_dynamic_entry - 获取指定动态标签",
                "parse_plt - 解析 PLT 过程链接表",
                "parse_got - 解析 GOT 全局偏移表",
                "parse_pltgot - 解析 .plt.got 段",
                "resolve_plt_to_function - PLT 条目到函数名映射",
                "parse_imported_libraries - 解析导入库列表",
                "build_import_dependency_graph - 构建导入依赖图",
                "find_external_function - 在导入库中查找函数",
                "parse_rel_dyn - 解析 .rel.dyn 重定位表",
                "parse_rel_plt - 解析 .rel.plt 重定位表",
                "get_imported_functions - 汇总所有导入函数",
                "build_got_overwrite - 构建 GOT 覆写补丁",
                "restore_got_entry - 恢复 GOT 条目",
                "list_hookable_functions - 列出可 Hook 函数",
                "simulate_plt_call - 模拟 PLT 调用过程",
                "trace_function_dependencies - 追踪函数调用链",
                "analyze_segment_permissions - 分析段权限",
                "find_writable_executable - 查找 W^X 违规段",
                "parse_gnu_version - 解析 GNU 符号版本",
            ],
            "dependencies": [
                "core.scriptso_analyzer.ScriptSOAnalyzer",
            ],
            "target_file": "Script.so",
            "target_format": "ELF (32-bit/64-bit Linux shared library)",
            "target_environment": "Wine (Windows compatibility layer)",
        }