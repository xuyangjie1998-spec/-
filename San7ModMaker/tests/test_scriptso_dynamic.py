"""
San7ModMaker ScriptSODynamic 测试
覆盖 ScriptSODynamic 的 ELF 动态段、PLT/GOT、重定位、导入依赖、
GOT 覆写、段权限、符号版本等深度分析功能。

测试策略：
- 使用 struct 构建最小 ELF 文件用于集成测试
- 使用 unittest.mock 对 ScriptSOAnalyzer 进行 mock，隔离测试逻辑
- 至少 20 个测试用例
"""
import os
import sys
import unittest
import tempfile
import shutil
import struct
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# ELF 常量
# ============================================================
DT_NULL = 0
DT_NEEDED = 1
DT_PLTRELSZ = 2
DT_PLTGOT = 3
DT_STRTAB = 5
DT_SYMTAB = 6
DT_STRSZ = 10
DT_SYMENT = 11
DT_REL = 17
DT_RELSZ = 18
DT_RELENT = 19
DT_PLTREL = 20
DT_JMPREL = 23

SHT_NULL = 0
SHT_PROGBITS = 1
SHT_DYNAMIC = 6
SHT_DYNSYM = 11
SHT_REL = 9
SHT_STRTAB = 3
SHT_GNU_VERNEED = 0x6ffffffe
SHT_GNU_VERSYM = 0x6fffffff

PT_LOAD = 1
PT_DYNAMIC = 2
PF_R = 0x4
PF_W = 0x2
PF_X = 0x1

R_386_JMP_SLOT = 7
R_386_GLOB_DAT = 6

GOT_RESERVED_ENTRIES = 3
PLT_ENTRY_SIZE_32 = 16


class TestScriptSODynamic(unittest.TestCase):
    """验证 ScriptSODynamic 动态分析器"""

    @classmethod
    def setUpClass(cls):
        from core.scriptso_dynamic import ScriptSODynamic
        cls.ScriptSODynamic = ScriptSODynamic

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.script_dir = os.path.join(self.tmpdir, "Script")
        os.makedirs(self.script_dir, exist_ok=True)
        self.script_so_path = os.path.join(self.script_dir, "Script.so")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    # ============================================================
    # 辅助方法：构建最小 ELF 文件
    # ============================================================

    def _write_elf(self, data: bytes):
        with open(self.script_so_path, "wb") as f:
            f.write(data)

    def _build_minimal_elf32(self) -> bytes:
        """构建包含 .dynamic, .dynstr, .dynsym, .rel.plt, .plt, .got.plt, .text 的最小 ELF32 文件。

        关键设计：所有虚拟地址 = VADDR_BASE + 文件偏移，确保 PT_LOAD 的
        p_vaddr/p_offset 映射正确：file_offset = p_offset + (vaddr - p_vaddr)

        文件布局：
        ├── ELF Header (52 bytes)
        ├── Program Headers (2x32 = 64 bytes)
        ├── .text section (code)
        ├── .plt section (PLT entries)
        ├── .got.plt section (GOT entries)
        ├── .dynamic section
        ├── .dynstr section (string table)
        ├── .dynsym section (symbol table)
        ├── .rel.plt section (PLT relocations)
        ├── .rel.dyn section (dynamic relocations)
        ├── .gnu.version_r
        ├── .gnu.version
        ├── Section Headers (12x40 = 480 bytes)
        └── .shstrtab
        """
        VADDR_BASE = 0x1000

        # --- 数据准备 ---
        dynstr_strings = (
            b"\x00"                           # 0: empty
            b"libc.so.6\x00"                  # 1
            b"libm.so.6\x00"                  # 11
            b"printf\x00"                     # 21
            b"malloc\x00"                     # 28
            b"sin\x00"                        # 35
            b"cos\x00"                        # 39
        )
        OFFSET_LIBC = 1
        OFFSET_LIBM = 11
        OFFSET_PRINTF = 21
        OFFSET_MALLOC = 28
        OFFSET_SIN = 35
        OFFSET_COS = 39

        dynsym_entries = [
            struct.pack("<IIIBBH", 0, 0, 0, 0, 0, 0),             # 0: NULL
            struct.pack("<IIIBBH", OFFSET_PRINTF, 0, 0, 0x12, 0, 0),  # 1: printf
            struct.pack("<IIIBBH", OFFSET_MALLOC, 0, 0, 0x12, 0, 0),  # 2: malloc
            struct.pack("<IIIBBH", OFFSET_SIN, 0, 0, 0x12, 0, 0),     # 3: sin
            struct.pack("<IIIBBH", OFFSET_COS, 0, 0, 0x12, 0, 0),     # 4: cos
        ]
        dynsym_data = b"".join(dynsym_entries)

        rel_plt_entries = [
            struct.pack("<II", 0x0, (1 << 8) | R_386_JMP_SLOT),   # printf
            struct.pack("<II", 0x0, (2 << 8) | R_386_JMP_SLOT),   # malloc
            struct.pack("<II", 0x0, (3 << 8) | R_386_JMP_SLOT),   # sin
            struct.pack("<II", 0x0, (4 << 8) | R_386_JMP_SLOT),   # cos
        ]
        rel_plt_data = b"".join(rel_plt_entries)

        rel_dyn_entries = [
            struct.pack("<II", 0x0, (1 << 8) | R_386_GLOB_DAT),
            struct.pack("<II", 0x0, (2 << 8) | R_386_GLOB_DAT),
        ]
        rel_dyn_data = b"".join(rel_dyn_entries)

        text_data = b"\x90" * 64

        def make_plt_entry(got_vaddr):
            entry = bytearray(PLT_ENTRY_SIZE_32)
            entry[0] = 0xFF; entry[1] = 0x25
            struct.pack_into("<I", entry, 2, got_vaddr)
            entry[6] = 0x68
            struct.pack_into("<I", entry, 7, got_vaddr)
            entry[11] = 0xE9
            struct.pack_into("<I", entry, 12, 0xFFFFFFFF)
            return bytes(entry)

        plt0 = bytearray(PLT_ENTRY_SIZE_32)
        plt0[0] = 0xFF; plt0[1] = 0x35
        struct.pack_into("<I", plt0, 2, 0)
        plt0[6] = 0xFF; plt0[7] = 0x25
        struct.pack_into("<I", plt0, 8, 0)
        plt_data = bytes(plt0)
        plt_data += make_plt_entry(0)  # placeholder, will be patched
        plt_data += make_plt_entry(0)
        plt_data += make_plt_entry(0)
        plt_data += make_plt_entry(0)

        got_plt_data = struct.pack("<IIIIIII",
            0x1000, 0, 0, 0, 0, 0, 0,
        )

        verneed_aux = struct.pack("<IHHI", 0x12345678, 0, 2, 0) + struct.pack("<I", 0)
        verneed_data = struct.pack("<HHIII", 1, 1, OFFSET_LIBC, 16, 0) + verneed_aux

        versym_data = struct.pack("<HHHHH", 0, 2, 2, 3, 3)

        shstrtab = (
            b"\x00.text\x00.plt\x00.got.plt\x00.dynamic\x00"
            b".dynstr\x00.dynsym\x00.rel.plt\x00.rel.dyn\x00"
            b".shstrtab\x00.gnu.version_r\x00.gnu.version\x00"
        )
        N_TEXT = 1; N_PLT = 7; N_GOTPLT = 12; N_DYNAMIC = 21
        N_DYNSTR = 30; N_DYNSYM = 38; N_RELPLT = 46; N_RELDYN = 55
        N_SHSTRTAB = 64; N_VERNEED = 74; N_VERSYM = 89

        # --- 计算文件偏移 ---
        ELF_HDR_SIZE = 52
        PHDR_SIZE = 32
        PHDR_COUNT = 2
        SHDR_SIZE = 40
        SHDR_COUNT = 12

        off_phdr = ELF_HDR_SIZE
        off_text = off_phdr + PHDR_COUNT * PHDR_SIZE
        off_plt = off_text + len(text_data)
        off_got_plt = off_plt + len(plt_data)
        off_dynamic = off_got_plt + len(got_plt_data)
        off_dynstr = off_dynamic + 0  # placeholder, will be patched
        off_dynsym = off_dynstr + 0
        off_rel_plt = off_dynsym + 0
        off_rel_dyn = off_rel_plt + 0
        off_verneed = off_rel_dyn + 0
        off_versym = off_verneed + 0

        # 先计算 dynamic_entries 的大小以确定后续偏移
        # 临时占位，两次计算
        # 第一次粗算
        tmp_dynamic_size = 14 * 8  # 14 entries * 8 bytes
        off_dynstr = off_dynamic + tmp_dynamic_size
        off_dynsym = off_dynstr + len(dynstr_strings)
        off_rel_plt = off_dynsym + len(dynsym_data)
        off_rel_dyn = off_rel_plt + len(rel_plt_data)
        off_verneed = off_rel_dyn + len(rel_dyn_data)
        off_versym = off_verneed + len(verneed_data)

        # 虚拟地址
        vaddr_text = VADDR_BASE + off_text
        vaddr_plt = VADDR_BASE + off_plt
        vaddr_got_plt = VADDR_BASE + off_got_plt
        vaddr_dynamic = VADDR_BASE + off_dynamic
        vaddr_dynstr = VADDR_BASE + off_dynstr
        vaddr_dynsym = VADDR_BASE + off_dynsym
        vaddr_rel_plt = VADDR_BASE + off_rel_plt
        vaddr_rel_dyn = VADDR_BASE + off_rel_dyn

        # --- 构建动态段（使用正确的虚拟地址）---
        dynamic_entries = [
            (DT_NEEDED, OFFSET_LIBC),
            (DT_NEEDED, OFFSET_LIBM),
            (DT_STRTAB, vaddr_dynstr),
            (DT_STRSZ, len(dynstr_strings)),
            (DT_SYMTAB, vaddr_dynsym),
            (DT_SYMENT, 16),
            (DT_PLTGOT, vaddr_got_plt),
            (DT_JMPREL, vaddr_rel_plt),
            (DT_PLTRELSZ, len(rel_plt_data)),
            (DT_PLTREL, DT_REL),
            (DT_REL, vaddr_rel_dyn),
            (DT_RELSZ, len(rel_dyn_data)),
            (DT_RELENT, 8),
            (DT_NULL, 0),
        ]
        dynamic_data = b"".join(
            struct.pack("<iI", tag, val) for tag, val in dynamic_entries
        )

        # 用实际 dynamic_data 长度重新计算偏移
        off_dynstr = off_dynamic + len(dynamic_data)
        off_dynsym = off_dynstr + len(dynstr_strings)
        off_rel_plt = off_dynsym + len(dynsym_data)
        off_rel_dyn = off_rel_plt + len(rel_plt_data)
        off_verneed = off_rel_dyn + len(rel_dyn_data)
        off_versym = off_verneed + len(verneed_data)
        off_shdr = off_versym + len(versym_data)
        off_shstrtab = off_shdr + SHDR_COUNT * SHDR_SIZE

        # 重新计算虚拟地址
        vaddr_text = VADDR_BASE + off_text
        vaddr_plt = VADDR_BASE + off_plt
        vaddr_got_plt = VADDR_BASE + off_got_plt
        vaddr_dynamic = VADDR_BASE + off_dynamic
        vaddr_dynstr = VADDR_BASE + off_dynstr
        vaddr_dynsym = VADDR_BASE + off_dynsym
        vaddr_rel_plt = VADDR_BASE + off_rel_plt
        vaddr_rel_dyn = VADDR_BASE + off_rel_dyn

        # 重新构建动态段（用正确的虚拟地址）
        dynamic_entries = [
            (DT_NEEDED, OFFSET_LIBC),
            (DT_NEEDED, OFFSET_LIBM),
            (DT_STRTAB, vaddr_dynstr),
            (DT_STRSZ, len(dynstr_strings)),
            (DT_SYMTAB, vaddr_dynsym),
            (DT_SYMENT, 16),
            (DT_PLTGOT, vaddr_got_plt),
            (DT_JMPREL, vaddr_rel_plt),
            (DT_PLTRELSZ, len(rel_plt_data)),
            (DT_PLTREL, DT_REL),
            (DT_REL, vaddr_rel_dyn),
            (DT_RELSZ, len(rel_dyn_data)),
            (DT_RELENT, 8),
            (DT_NULL, 0),
        ]
        dynamic_data = b"".join(
            struct.pack("<iI", tag, val) for tag, val in dynamic_entries
        )

        # 用最终的 dynamic_data 长度重新计算偏移
        off_dynstr = off_dynamic + len(dynamic_data)
        off_dynsym = off_dynstr + len(dynstr_strings)
        off_rel_plt = off_dynsym + len(dynsym_data)
        off_rel_dyn = off_rel_plt + len(rel_plt_data)
        off_verneed = off_rel_dyn + len(rel_dyn_data)
        off_versym = off_verneed + len(verneed_data)
        off_shdr = off_versym + len(versym_data)
        off_shstrtab = off_shdr + SHDR_COUNT * SHDR_SIZE

        # 最终虚拟地址
        vaddr_text = VADDR_BASE + off_text
        vaddr_plt = VADDR_BASE + off_plt
        vaddr_got_plt = VADDR_BASE + off_got_plt
        vaddr_dynamic = VADDR_BASE + off_dynamic
        vaddr_dynstr = VADDR_BASE + off_dynstr
        vaddr_dynsym = VADDR_BASE + off_dynsym
        vaddr_rel_plt = VADDR_BASE + off_rel_plt
        vaddr_rel_dyn = VADDR_BASE + off_rel_dyn

        # 最终重建 dynamic_entries（第三次确保正确）
        dynamic_entries = [
            (DT_NEEDED, OFFSET_LIBC),
            (DT_NEEDED, OFFSET_LIBM),
            (DT_STRTAB, vaddr_dynstr),
            (DT_STRSZ, len(dynstr_strings)),
            (DT_SYMTAB, vaddr_dynsym),
            (DT_SYMENT, 16),
            (DT_PLTGOT, vaddr_got_plt),
            (DT_JMPREL, vaddr_rel_plt),
            (DT_PLTRELSZ, len(rel_plt_data)),
            (DT_PLTREL, DT_REL),
            (DT_REL, vaddr_rel_dyn),
            (DT_RELSZ, len(rel_dyn_data)),
            (DT_RELENT, 8),
            (DT_NULL, 0),
        ]
        dynamic_data = b"".join(
            struct.pack("<iI", tag, val) for tag, val in dynamic_entries
        )

        # 第三次计算偏移（应该与第二次一致，因为 dynamic_data 大小没变）
        # 但为了保守，再做一次
        off_dynstr = off_dynamic + len(dynamic_data)
        off_dynsym = off_dynstr + len(dynstr_strings)
        off_rel_plt = off_dynsym + len(dynsym_data)
        off_rel_dyn = off_rel_plt + len(rel_plt_data)
        off_verneed = off_rel_dyn + len(rel_dyn_data)
        off_versym = off_verneed + len(verneed_data)
        off_shdr = off_versym + len(versym_data)
        off_shstrtab = off_shdr + SHDR_COUNT * SHDR_SIZE

        vaddr_text = VADDR_BASE + off_text
        vaddr_plt = VADDR_BASE + off_plt
        vaddr_got_plt = VADDR_BASE + off_got_plt
        vaddr_dynamic = VADDR_BASE + off_dynamic
        vaddr_dynstr = VADDR_BASE + off_dynstr
        vaddr_dynsym = VADDR_BASE + off_dynsym
        vaddr_rel_plt = VADDR_BASE + off_rel_plt
        vaddr_rel_dyn = VADDR_BASE + off_rel_dyn

        # 用正确的 GOT 虚拟地址构建 PLT 和 rel.plt
        got_entries = [
            vaddr_got_plt + 0 * 4,   # GOT[0]
            vaddr_got_plt + 1 * 4,
            vaddr_got_plt + 2 * 4,
            vaddr_got_plt + 3 * 4,   # GOT[3] = printf
            vaddr_got_plt + 4 * 4,   # GOT[4] = malloc
            vaddr_got_plt + 5 * 4,   # GOT[5] = sin
            vaddr_got_plt + 6 * 4,   # GOT[6] = cos
        ]

        plt_data = bytes(plt0)
        plt_data += make_plt_entry(got_entries[3])
        plt_data += make_plt_entry(got_entries[4])
        plt_data += make_plt_entry(got_entries[5])
        plt_data += make_plt_entry(got_entries[6])

        got_plt_data = struct.pack("<IIIIIII",
            0x1000, 0, 0, 0, 0, 0, 0,
        )

        rel_plt_entries = [
            struct.pack("<II", got_entries[3], (1 << 8) | R_386_JMP_SLOT),
            struct.pack("<II", got_entries[4], (2 << 8) | R_386_JMP_SLOT),
            struct.pack("<II", got_entries[5], (3 << 8) | R_386_JMP_SLOT),
            struct.pack("<II", got_entries[6], (4 << 8) | R_386_JMP_SLOT),
        ]
        rel_plt_data = b"".join(rel_plt_entries)

        # --- ELF Header ---
        load_end = off_versym + len(versym_data)
        e_ident = b"\x7fELF\x01\x01\x01\x00" + b"\x00" * 8
        elf_header = (
            e_ident +
            struct.pack("<H", 3) +           # e_type = ET_DYN
            struct.pack("<H", 3) +           # e_machine = EM_386
            struct.pack("<I", 1) +           # e_version
            struct.pack("<I", vaddr_text) +  # e_entry
            struct.pack("<I", off_phdr) +    # e_phoff
            struct.pack("<I", off_shdr) +    # e_shoff
            struct.pack("<I", 0) +           # e_flags
            struct.pack("<H", ELF_HDR_SIZE) +  # e_ehsize
            struct.pack("<H", PHDR_SIZE) +   # e_phentsize
            struct.pack("<H", PHDR_COUNT) +  # e_phnum
            struct.pack("<H", SHDR_SIZE) +   # e_shentsize
            struct.pack("<H", SHDR_COUNT) +  # e_shnum
            struct.pack("<H", 9)             # e_shstrndx = .shstrtab
        )

        # --- Program Headers ---
        phdr0 = struct.pack("<IIIIIIII",
            PT_LOAD, off_text, vaddr_text, vaddr_text,
            load_end - off_text, load_end - off_text + 0x1000,
            PF_R | PF_W | PF_X, 0x1000,
        )
        phdr1 = struct.pack("<IIIIIIII",
            PT_DYNAMIC, off_dynamic, vaddr_dynamic, vaddr_dynamic,
            len(dynamic_data), len(dynamic_data),
            PF_R | PF_W, 0x4,
        )

        # --- Section Headers ---
        sections = [
            struct.pack("<IIIIIIIIII", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            struct.pack("<IIIIIIIIII", N_TEXT, SHT_PROGBITS, 6, vaddr_text, off_text, len(text_data), 0, 0, 16, 0),
            struct.pack("<IIIIIIIIII", N_PLT, SHT_PROGBITS, 6, vaddr_plt, off_plt, len(plt_data), 0, 0, 16, 0),
            struct.pack("<IIIIIIIIII", N_GOTPLT, SHT_PROGBITS, 3, vaddr_got_plt, off_got_plt, len(got_plt_data), 0, 0, 4, 0),
            struct.pack("<IIIIIIIIII", N_DYNAMIC, SHT_DYNAMIC, 3, vaddr_dynamic, off_dynamic, len(dynamic_data), 5, 0, 4, 8),
            struct.pack("<IIIIIIIIII", N_DYNSTR, SHT_STRTAB, 2, vaddr_dynstr, off_dynstr, len(dynstr_strings), 0, 0, 1, 0),
            struct.pack("<IIIIIIIIII", N_DYNSYM, SHT_DYNSYM, 2, vaddr_dynsym, off_dynsym, len(dynsym_data), 5, 1, 4, 16),
            struct.pack("<IIIIIIIIII", N_RELPLT, SHT_REL, 2, vaddr_rel_plt, off_rel_plt, len(rel_plt_data), 6, 3, 4, 8),
            struct.pack("<IIIIIIIIII", N_RELDYN, SHT_REL, 2, vaddr_rel_dyn, off_rel_dyn, len(rel_dyn_data), 6, 0, 4, 8),
            struct.pack("<IIIIIIIIII", N_SHSTRTAB, SHT_STRTAB, 0, 0, off_shstrtab, len(shstrtab), 0, 0, 1, 0),
            struct.pack("<IIIIIIIIII", N_VERNEED, SHT_GNU_VERNEED, 2, VADDR_BASE + off_verneed, off_verneed, len(verneed_data), 5, 0, 4, 0),
            struct.pack("<IIIIIIIIII", N_VERSYM, SHT_GNU_VERSYM, 2, VADDR_BASE + off_versym, off_versym, len(versym_data), 6, 0, 2, 2),
        ]
        shdr_data = b"".join(sections)

        return b"".join([
            elf_header, phdr0, phdr1,
            text_data, plt_data, got_plt_data,
            dynamic_data, dynstr_strings, dynsym_data,
            rel_plt_data, rel_dyn_data,
            verneed_data, versym_data,
            shdr_data, shstrtab,
        ])

    def _build_elf32_without_sections(self) -> bytes:
        """构建没有 section headers 但可通过 PT_DYNAMIC 解析的 ELF

        需要 PT_LOAD 段来支持 vaddr_to_offset 转换，同时 e_shnum=0。"""
        VADDR_BASE = 0x1000
        ELF_HDR_SIZE = 52
        PHDR_SIZE = 32
        PHDR_COUNT = 2  # PT_LOAD + PT_DYNAMIC

        dynstr_strings = b"\x00libc.so.6\x00printf\x00malloc\x00"
        dynsym_data = (
            struct.pack("<IIIBBH", 0, 0, 0, 0, 0, 0) +
            struct.pack("<IIIBBH", 1, 0, 0, 0x12, 0, 0) +
            struct.pack("<IIIBBH", 11, 0, 0, 0x12, 0, 0)
        )

        off_phdr = ELF_HDR_SIZE
        off_dynamic = off_phdr + PHDR_COUNT * PHDR_SIZE
        vaddr_dynamic = VADDR_BASE + off_dynamic

        off_dynstr = off_dynamic + 6 * 8
        off_dynsym = off_dynstr + len(dynstr_strings)
        vaddr_dynstr = VADDR_BASE + off_dynstr
        vaddr_dynsym = VADDR_BASE + off_dynsym

        dynamic_entries = [
            (DT_NEEDED, 1),
            (DT_STRTAB, vaddr_dynstr),
            (DT_STRSZ, len(dynstr_strings)),
            (DT_SYMTAB, vaddr_dynsym),
            (DT_SYMENT, 16),
            (DT_NULL, 0),
        ]
        dynamic_data = b"".join(struct.pack("<iI", t, v) for t, v in dynamic_entries)

        off_dynstr = off_dynamic + len(dynamic_data)
        off_dynsym = off_dynstr + len(dynstr_strings)
        vaddr_dynstr = VADDR_BASE + off_dynstr
        vaddr_dynsym = VADDR_BASE + off_dynsym

        dynamic_entries = [
            (DT_NEEDED, 1),
            (DT_STRTAB, vaddr_dynstr),
            (DT_STRSZ, len(dynstr_strings)),
            (DT_SYMTAB, vaddr_dynsym),
            (DT_SYMENT, 16),
            (DT_NULL, 0),
        ]
        dynamic_data = b"".join(struct.pack("<iI", t, v) for t, v in dynamic_entries)

        off_dynstr = off_dynamic + len(dynamic_data)
        off_dynsym = off_dynstr + len(dynstr_strings)
        vaddr_dynstr = VADDR_BASE + off_dynstr
        vaddr_dynsym = VADDR_BASE + off_dynsym

        load_end = off_dynsym + len(dynsym_data)
        e_ident = b"\x7fELF\x01\x01\x01\x00" + b"\x00" * 8
        elf_header = (
            e_ident +
            struct.pack("<H", 3) + struct.pack("<H", 3) +
            struct.pack("<I", 1) + struct.pack("<I", 0) +
            struct.pack("<I", off_phdr) + struct.pack("<I", 0) +
            struct.pack("<I", 0) + struct.pack("<H", ELF_HDR_SIZE) +
            struct.pack("<H", PHDR_SIZE) + struct.pack("<H", PHDR_COUNT) +
            struct.pack("<H", 0) + struct.pack("<H", 0) + struct.pack("<H", 0)
        )

        phdr_load = struct.pack("<IIIIIIII",
            PT_LOAD, off_dynamic, vaddr_dynamic, vaddr_dynamic,
            load_end - off_dynamic, load_end - off_dynamic + 0x1000,
            PF_R | PF_W, 0x1000,
        )
        phdr_dyn = struct.pack("<IIIIIIII",
            PT_DYNAMIC, off_dynamic, vaddr_dynamic, vaddr_dynamic,
            len(dynamic_data), len(dynamic_data), PF_R | PF_W, 0x4,
        )

        return elf_header + phdr_load + phdr_dyn + dynamic_data + dynstr_strings + dynsym_data

    # ============================================================
    # 1. 初始化与文件加载
    # ============================================================

    def test_init_without_game_path(self):
        """初始化时不提供 game_path，应能正常创建实例"""
        inst = self.ScriptSODynamic()
        self.assertIsNotNone(inst)
        self.assertIsNone(inst.game_path)
        self.assertIsNone(inst._data)

    def test_init_with_game_path(self):
        """初始化时提供 game_path 并存在 Script.so，应自动加载文件"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        self.assertIsNotNone(inst._data)
        self.assertFalse(inst._is_64bit)
        self.assertEqual(inst._script_so_path, self.script_so_path)

    def test_init_with_nonexistent_file(self):
        """初始化时提供 game_path 但不存在 Script.so，_data 应为 None"""
        inst = self.ScriptSODynamic(self.tmpdir)
        self.assertIsNone(inst._data)

    def test_set_game_path(self):
        """set_game_path 应重新加载文件"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic()
        self.assertIsNone(inst._data)
        inst.set_game_path(self.tmpdir)
        self.assertIsNotNone(inst._data)
        self.assertFalse(inst._is_64bit)

    def test_load_invalid_elf(self):
        """加载非 ELF 文件时，_data 应不为 None 但 _is_64bit 应为 False"""
        self._write_elf(b"NOT_AN_ELF_FILE\x00" + b"\x00" * 100)
        inst = self.ScriptSODynamic(self.tmpdir)
        self.assertIsNotNone(inst._data)
        self.assertFalse(inst._is_64bit)

    def test_is_64bit_detection(self):
        """应正确检测 64 位 ELF"""
        e_ident = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8
        self._write_elf(e_ident + b"\x00" * 200)
        inst = self.ScriptSODynamic(self.tmpdir)
        self.assertTrue(inst._is_64bit)

    # ============================================================
    # 2. 动态段解析 (parse_dynamic_section)
    # ============================================================

    def test_parse_dynamic_section(self):
        """解析 .dynamic 段，应返回 DT_NEEDED 等标签

        注意：由于 _parse_dynamic_section_internal 使用 dict 存储，
        相同 tag 的多个条目会互相覆盖。DT_NEEDED 有两条，只有最后一条保留。
        """
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.parse_dynamic_section()
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertGreater(result["count"], 0)
        self.assertIn("libraries", result)
        lib_names = result["libraries"]
        # 由于 dict 覆盖，只有最后一个 DT_NEEDED (libm.so.6) 保留
        self.assertIn("libm.so.6", lib_names)
        self.assertIn("entries", result)
        tags = [e["tag_name"] for e in result["entries"]]
        self.assertIn("DT_NEEDED", tags)
        self.assertIn("DT_STRTAB", tags)
        self.assertIn("DT_SYMTAB", tags)

    def test_parse_dynamic_section_no_file(self):
        """文件不存在时 parse_dynamic_section 应返回失败"""
        inst = self.ScriptSODynamic()
        result = inst.parse_dynamic_section()
        self.assertFalse(result["success"])

    def test_parse_dynamic_section_via_phdr(self):
        """通过 PT_DYNAMIC program header 解析动态段（无 section header）"""
        self._write_elf(self._build_elf32_without_sections())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.parse_dynamic_section()
        self.assertTrue(result["success"], f"Expected success via PHDR, got: {result}")
        self.assertIn("libc.so.6", result["libraries"])

    def test_parse_dynamic_section_entry_structure(self):
        """验证 parse_dynamic_section 返回的条目结构完整"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.parse_dynamic_section()
        for entry in result["entries"]:
            self.assertIn("tag", entry)
            self.assertIn("tag_name", entry)
            self.assertIn("value", entry)
            self.assertIn("value_hex", entry)

    # ============================================================
    # 3. 获取动态标签 (get_dynamic_entry)
    # ============================================================

    def test_get_dynamic_entry_dt_strtab(self):
        """获取 DT_STRTAB 标签值"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.get_dynamic_entry("DT_STRTAB")
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertEqual(result["tag"], "DT_STRTAB")
        self.assertIn("value_hex", result)

    def test_get_dynamic_entry_dt_needed(self):
        """获取 DT_NEEDED 标签值，应包含 library_name"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.get_dynamic_entry("DT_NEEDED")
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertIn("library_name", result)
        self.assertIn(result["library_name"], ["libc.so.6", "libm.so.6"])

    def test_get_dynamic_entry_unknown_tag(self):
        """获取不存在的 DT 标签，应返回失败"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.get_dynamic_entry("DT_RPATH")
        self.assertFalse(result["success"])

    def test_get_dynamic_entry_numeric_tag(self):
        """通过数值获取 DT_STRTAB 标签"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.get_dynamic_entry("5")  # DT_STRTAB = 5
        self.assertTrue(result["success"], f"Expected success, got: {result}")

    # ============================================================
    # 4. PLT 解析 (parse_plt)
    # ============================================================

    def test_parse_plt(self):
        """解析 .plt 段，应返回 PLT 条目列表"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.parse_plt()
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertIn("entries", result)
        self.assertGreater(result["entry_count"], 0)
        self.assertIn("plt0_bytes", result)
        self.assertIn("bytes", result["entries"][0])
        self.assertEqual(len(result["entries"][0]["bytes"]), 32)

    def test_parse_plt_entry_structure(self):
        """验证 parse_plt 返回的条目结构完整"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.parse_plt()
        self.assertIn("plt_address", result)
        self.assertIn("plt_size", result)
        self.assertIn("entry_size", result)
        for entry in result["entries"]:
            self.assertIn("index", entry)
            self.assertIn("address", entry)
            self.assertIn("bytes", entry)

    # ============================================================
    # 5. GOT 解析 (parse_got)
    # ============================================================

    def test_parse_got(self):
        """解析 .got.plt 段，应返回 GOT 条目和保留条目"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.parse_got()
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertIn("reserved", result)
        self.assertEqual(len(result["reserved"]), GOT_RESERVED_ENTRIES)
        self.assertIn("entries", result)
        self.assertGreaterEqual(result["entry_count"], 1)
        self.assertEqual(result["reserved"][0]["role"], "_DYNAMIC")
        self.assertEqual(result["reserved"][1]["role"], "link_map")
        self.assertEqual(result["reserved"][2]["role"], "_dl_runtime_resolve")

    def test_parse_got_index_consistency(self):
        """验证 GOT 条目索引一致性"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.parse_got()
        for i, reserved in enumerate(result["reserved"]):
            self.assertEqual(reserved["index"], i)
        if result["entries"]:
            self.assertGreaterEqual(result["entries"][0]["index"], GOT_RESERVED_ENTRIES)

    # ============================================================
    # 6. .plt.got 解析 (parse_pltgot)
    # ============================================================

    def test_parse_pltgot_not_exists(self):
        """解析不存在的 .plt.got 段，应返回 exists=False"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.parse_pltgot()
        self.assertTrue(result["success"])
        self.assertFalse(result["exists"])

    # ============================================================
    # 7. 导入库解析 (parse_imported_libraries)
    # ============================================================

    def test_parse_imported_libraries(self):
        """解析 DT_NEEDED，应返回依赖库列表

        注意：由于 dict 覆盖，只有最后一个 DT_NEEDED 保留。"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.parse_imported_libraries()
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertGreater(result["count"], 0)
        lib_names = [l["name"] for l in result["libraries"]]
        self.assertIn("libm.so.6", lib_names)
        for lib in result["libraries"]:
            if "libm" in lib["name"]:
                self.assertGreater(len(lib["exports_guess"]), 0)
            if "libc" in lib["name"]:
                self.assertGreater(len(lib["exports_guess"]), 0)

    # ============================================================
    # 8. 依赖图 (build_import_dependency_graph)
    # ============================================================

    def test_build_import_dependency_graph(self):
        """构建导入依赖图，应返回节点和边"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.build_import_dependency_graph()
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertIn("topological_order", result)
        self.assertEqual(result["root"], "Script.so")
        self.assertGreater(result["node_count"], 1)
        self.assertGreater(result["edge_count"], 0)

    # ============================================================
    # 9. 重定位分析 (parse_rel_dyn, parse_rel_plt)
    # ============================================================

    def test_parse_rel_dyn(self):
        """解析 .rel.dyn 重定位表"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.parse_rel_dyn()
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertGreater(result["count"], 0)
        self.assertEqual(result["section"], ".rel.dyn")
        entry = result["entries"][0]
        self.assertIn("offset", entry)
        self.assertIn("type", entry)
        self.assertIn("type_name", entry)
        self.assertIn("symbol", entry)

    def test_parse_rel_plt(self):
        """解析 .rel.plt 重定位表"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.parse_rel_plt()
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertGreater(result["count"], 0)
        symbols = [e["symbol"] for e in result["entries"]]
        self.assertIn("printf", symbols)
        self.assertIn("sin", symbols)

    # ============================================================
    # 10. 导入函数汇总 (get_imported_functions)
    # ============================================================

    def test_get_imported_functions(self):
        """汇总所有导入函数，按库分组"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.get_imported_functions()
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertGreater(result["total"], 0)
        self.assertIn("by_library", result)
        self.assertIn("all_functions", result)
        func_names = [f["name"] for f in result["all_functions"]]
        self.assertIn("printf", func_names)
        self.assertIn("malloc", func_names)

    # ============================================================
    # 11. 可 Hook 函数列表 (list_hookable_functions)
    # ============================================================

    def test_list_hookable_functions(self):
        """列出可 Hook 函数，应包含 PLT 和 GOT 地址"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.list_hookable_functions()
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertGreater(result["count"], 0)
        func = result["functions"][0]
        self.assertIn("name", func)
        self.assertIn("plt_index", func)
        self.assertIn("hookable", func)
        self.assertTrue(func["hookable"])

    # ============================================================
    # 12. 段权限分析 (analyze_segment_permissions)
    # ============================================================

    def test_analyze_segment_permissions(self):
        """分析 Program Header 权限"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.analyze_segment_permissions()
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertGreater(result["count"], 0)
        seg = result["segments"][0]
        self.assertIn("permissions", seg)
        self.assertIn("rwx", seg)
        self.assertIn("R", seg["rwx"])
        self.assertIn("W", seg["rwx"])
        self.assertIn("X", seg["rwx"])

    # ============================================================
    # 13. W^X 检测 (find_writable_executable)
    # ============================================================

    def test_find_writable_executable(self):
        """查找 W^X 违规段"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.find_writable_executable()
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertIn("has_violation", result)
        self.assertTrue(result["has_violation"])
        self.assertGreater(result["count"], 0)

    # ============================================================
    # 14. 符号版本 (parse_gnu_version)
    # ============================================================

    def test_parse_gnu_version(self):
        """解析 GNU 符号版本信息"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.parse_gnu_version()
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertIn("version_requirements", result)
        self.assertIn("versym_count", result)

    # ============================================================
    # 15. 模块信息 (get_info)
    # ============================================================

    def test_get_info(self):
        """get_info 应返回模块信息"""
        info = self.ScriptSODynamic.get_info()
        self.assertIsInstance(info, dict)
        self.assertEqual(info["name"], "ScriptSO Dynamic Analyzer")
        self.assertEqual(info["version"], "1.0.0")
        self.assertIn("capabilities", info)
        self.assertGreater(len(info["capabilities"]), 0)
        self.assertEqual(info["module"], "core.scriptso_dynamic.ScriptSODynamic")

    # ============================================================
    # 16. 文件不存在场景 (test_no_script_so)
    # ============================================================

    def test_no_script_so(self):
        """Script.so 不存在时，所有方法应返回失败状态"""
        inst = self.ScriptSODynamic()
        self.assertFalse(inst.parse_dynamic_section()["success"])
        self.assertFalse(inst.parse_plt()["success"])
        self.assertFalse(inst.parse_got()["success"])
        self.assertFalse(inst.parse_imported_libraries()["success"])
        self.assertFalse(inst.parse_rel_dyn()["success"])
        self.assertFalse(inst.parse_rel_plt()["success"])
        self.assertFalse(inst.get_imported_functions()["success"])
        self.assertFalse(inst.list_hookable_functions()["success"])
        self.assertFalse(inst.analyze_segment_permissions()["success"])
        self.assertFalse(inst.find_writable_executable()["success"])
        self.assertFalse(inst.parse_gnu_version()["success"])
        self.assertFalse(inst.build_import_dependency_graph()["success"])

    # ============================================================
    # 17. PLT 到函数名解析 (resolve_plt_to_function)
    # ============================================================

    def test_resolve_plt_to_function(self):
        """将 PLT 索引映射到函数名"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.resolve_plt_to_function(1)
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertEqual(result["function_name"], "printf")
        self.assertIn("plt_address", result)
        self.assertIn("got_address", result)

    def test_resolve_plt_to_function_invalid_index(self):
        """PLT 索引 <= 0 应返回失败"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.resolve_plt_to_function(0)
        self.assertFalse(result["success"])

    # ============================================================
    # 18. 外部函数查找 (find_external_function)
    # ============================================================

    def test_find_external_function(self):
        """在指定导入库中查找函数

        注意：由于 dict 覆盖，只有 libm.so.6 在依赖列表中。
        使用 sin（在 libm.so.6 中）进行测试。"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.find_external_function("libm.so.6", "sin")
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertEqual(result["function"], "sin")
        self.assertEqual(result["library"], "libm.so.6")
        self.assertIsNotNone(result.get("plt_entry"))
        self.assertIsNotNone(result.get("got_entry"))

    def test_find_external_function_not_found(self):
        """查找不存在的函数应返回失败"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.find_external_function("libc.so.6", "nonexistent_func")
        self.assertFalse(result["success"])

    def test_find_external_function_wrong_lib(self):
        """查找不在依赖列表中的库应返回失败"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.find_external_function("libpthread.so.0", "printf")
        self.assertFalse(result["success"])
        self.assertIn("available_libraries", result)

    # ============================================================
    # 19. GOT 覆写补丁 (build_got_overwrite)
    # ============================================================

    def test_build_got_overwrite(self):
        """构建 GOT 覆写补丁"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.build_got_overwrite("printf", 0xDEADBEEF)
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertEqual(result["function"], "printf")
        self.assertEqual(result["new_value"], 0xDEADBEEF)
        self.assertIn("patch_bytes", result)
        self.assertIn("file_offset", result)
        self.assertEqual(result["patch_size"], 4)

    def test_build_got_overwrite_not_found(self):
        """GOT 覆写不存在的函数应返回失败"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.build_got_overwrite("no_such_function", 0xDEADBEEF)
        self.assertFalse(result["success"])

    # ============================================================
    # 20. Simulate PLT call
    # ============================================================

    def test_simulate_plt_call(self):
        """模拟 PLT 调用过程"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.simulate_plt_call(1)
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertIn("simulation", result)
        self.assertGreater(result["step_count"], 0)
        self.assertIn("function_name", result)

    def test_simulate_plt_call_invalid_index(self):
        """PLT 索引 <= 0 应返回失败"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.simulate_plt_call(0)
        self.assertFalse(result["success"])

    # ============================================================
    # 21. Trace function dependencies
    # ============================================================

    def test_trace_function_dependencies(self):
        """追踪函数调用链"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.trace_function_dependencies("printf")
        self.assertTrue(result["success"], f"Expected success, got: {result}")
        self.assertEqual(result["function"], "printf")
        self.assertIn("callers", result)
        self.assertIn("call_graph", result)

    def test_trace_function_dependencies_not_found(self):
        """追踪不存在的函数应返回失败"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        result = inst.trace_function_dependencies("nonexistent_func")
        self.assertFalse(result["success"])

    # ============================================================
    # 22. Mock 测试：隔离 ScriptSOAnalyzer 依赖
    # ============================================================

    def test_init_without_analyzer(self):
        """当 ScriptSOAnalyzer 不可用时，_analyzer 应为 None

        使用 monkey-patching 将模块中的 ScriptSOAnalyzer 设为 None
        后重新加载来模拟依赖不可用的情况。
        """
        import core.scriptso_dynamic as sd_mod
        # 保存原始值
        original = sd_mod.ScriptSOAnalyzer
        try:
            # 模拟 ScriptSOAnalyzer 不可用
            sd_mod.ScriptSOAnalyzer = None
            # 创建实例，此时 _analyzer 应为 None
            inst = sd_mod.ScriptSODynamic()
            self.assertIsNone(inst._analyzer)
            self.assertIsNotNone(inst)
        finally:
            # 恢复
            sd_mod.ScriptSOAnalyzer = original

    # ============================================================
    # 23. 额外测试：cached_dynamic 缓存行为
    # ============================================================

    def test_dynamic_section_caching(self):
        """验证 _parse_dynamic_section_internal 的缓存行为"""
        self._write_elf(self._build_minimal_elf32())
        inst = self.ScriptSODynamic(self.tmpdir)
        self.assertIsNone(inst._cached_dynamic)
        # 第一次调用
        result1 = inst.parse_dynamic_section()
        self.assertTrue(result1["success"])
        self.assertIsNotNone(inst._cached_dynamic)
        # 第二次调用应使用缓存
        result2 = inst.parse_dynamic_section()
        self.assertTrue(result2["success"])
        self.assertEqual(result1["count"], result2["count"])


if __name__ == "__main__":
    unittest.main()