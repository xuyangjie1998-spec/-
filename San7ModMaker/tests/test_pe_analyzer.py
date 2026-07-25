"""
San7ModMaker PeAnalyzer 测试套件
覆盖 PeAnalyzer 核心路径：DOS Header / NT Headers / File Header / Optional Header /
节表 / Data Directories / 导入表 / 导出表 / 重定位表 / Code Cave / 版本检测
"""
import os
import sys
import unittest
import tempfile
import struct
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# PE 常量 (与 core.pe_analyzer 保持一致)
# ============================================================

IMAGE_DOS_SIGNATURE = 0x5A4D          # MZ
IMAGE_NT_SIGNATURE = 0x00004550       # PE\0\0
IMAGE_NT_OPTIONAL_HDR32_MAGIC = 0x10B  # PE32


class TestPeAnalyzer(unittest.TestCase):
    """PE 解析器测试"""

    @classmethod
    def setUpClass(cls):
        from core.pe_analyzer import PeAnalyzer
        cls.PeAnalyzer = PeAnalyzer

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.pe_path = os.path.join(self.tmpdir, "test_pe.exe")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ============================================================
    # PE 构建辅助方法
    # ============================================================

    def _build_pe(self, **overrides):
        """
        构建标准 32位 PE 文件，返回 bytes。

        可覆盖的字段 (通过 overrides 字典):
          - dos_e_lfanew: int, e_lfanew 偏移 (默认 0x80)
          - dos_magic: int, DOS 魔数 (默认 0x5A4D)
          - pe_sig: int, PE 签名 (默认 0x00004550)
          - machine: int, 机器类型 (默认 0x014C)
          - num_sections: int, 节数 (默认 3)
          - time_stamp: int, 时间戳 (默认 0x12345678)
          - size_opt_header: int, Optional Header 大小 (默认 0xE0)
          - characteristics: int, 文件特性 (默认 0x102)
          - magic: int, Optional Header Magic (默认 0x10B)
          - entry_point: int, 入口点 (默认 0x1000)
          - image_base: int, 映像基址 (默认 0x400000)
          - section_align: int, 节对齐 (默认 0x1000)
          - file_align: int, 文件对齐 (默认 0x200)
          - size_of_image: int, 映像大小 (默认 0x5000)
          - size_of_headers: int, 头大小 (默认 0x200)
          - subsystem: int, 子系统 (默认 2)
          - dll_chars: int, DLL 特性 (默认 0)
          - num_rva: int, NumberOfRvaAndSizes (默认 16)
          - data_directories: bytes, 数据目录区 (默认全零 128 字节)
          - sections: list of tuples, 自定义节表
          - pad_to: int, 文件扩充到的总大小 (默认 0x800)
          - extra_data: dict, 在指定偏移写入额外数据

        默认节表:
          .text:  VA=0x1000, Raw=0x200,  Chars=0x60000020
          .rdata: VA=0x2000, Raw=0x400,  Chars=0x40000040
          .data:  VA=0x3000, Raw=0x600,  Chars=0xC0000040

        注意: 构建顺序是先写节数据区域，再写头部区域。
        因为节表头 (0x1F8) 与 .text 节数据 (0x200) 有重叠，
        头部必须在最后写入以覆盖重叠区中正确的节表头字节。
        """
        dos_magic = overrides.get("dos_magic", IMAGE_DOS_SIGNATURE)
        dos_lfanew = overrides.get("dos_e_lfanew", 0x80)
        pe_sig = overrides.get("pe_sig", IMAGE_NT_SIGNATURE)
        machine = overrides.get("machine", 0x014C)
        num_sections = overrides.get("num_sections", 3)
        time_stamp = overrides.get("time_stamp", 0x12345678)
        size_opt_header = overrides.get("size_opt_header", 0xE0)
        characteristics = overrides.get("characteristics", 0x102)
        magic = overrides.get("magic", IMAGE_NT_OPTIONAL_HDR32_MAGIC)
        entry_point = overrides.get("entry_point", 0x1000)
        image_base = overrides.get("image_base", 0x400000)
        section_align = overrides.get("section_align", 0x1000)
        file_align = overrides.get("file_align", 0x200)
        size_of_image = overrides.get("size_of_image", 0x5000)
        size_of_headers = overrides.get("size_of_headers", 0x200)
        subsystem = overrides.get("subsystem", 2)
        dll_chars = overrides.get("dll_chars", 0)
        num_rva = overrides.get("num_rva", 16)
        pad_to = overrides.get("pad_to", 0x800)
        extra = overrides.get("extra_data", {})

        default_sections = [
            (b".text\x00\x00\x00", 0x1000, 0x1000, 0x200, 0x200, 0x60000020),
            (b".rdata\x00\x00",   0x1000, 0x2000, 0x200, 0x400, 0x40000040),
            (b".data\x00\x00\x00", 0x1000, 0x3000, 0x200, 0x600, 0xC0000040),
        ]
        sections = overrides.get("sections", default_sections)

        dd = overrides.get("data_directories", b"\x00" * 128)
        if len(dd) < 128:
            dd = dd + b"\x00" * (128 - len(dd))
        dd = bytes(dd[:128])

        # 计算节表头结束位置
        # pe_offset(0x80) + Signature(4) + FileHeader(20) + OptionalHeader(0xE0=224) = 0x178
        section_header_start = 0x178
        section_header_end = section_header_start + len(sections) * 40

        # =========================================================
        # 阶段 1: 创建全零填充的 bytearray (最终大小)
        # =========================================================
        pe = bytearray(pad_to)

        # =========================================================
        # 阶段 2: 填充节数据区域 (section data areas)
        # =========================================================
        # 在 .text 节数据中写入 NOP、Code Cave 区域
        text_raw = 0x200
        text_size = 0x200
        for i in range(text_raw, text_raw + text_size):
            pe[i] = 0x90  # NOP

        # 创建一段 0x00 区域 (code cave)
        cave_start = text_raw + 0x10
        cave_size = 0x80
        for i in range(cave_start, cave_start + cave_size):
            pe[i] = 0x00

        # 创建一段 0xCC 区域
        cc_start = text_raw + 0xA0
        cc_size = 0x40
        for i in range(cc_start, cc_start + cc_size):
            pe[i] = 0xCC

        # 创建一段 0x90 区域 (会被头部覆盖一部分，但剩余部分仍可测试)
        nop_start = text_raw + 0xF0
        nop_size = 0x50
        for i in range(nop_start, nop_start + nop_size):
            pe[i] = 0x90

        # =========================================================
        # 阶段 3: 写入额外数据 (在头部写入前，避免被覆盖)
        # =========================================================
        for offset, data in extra.items():
            end = min(offset + len(data), pad_to)
            pe[offset:end] = data[:end - offset]

        # =========================================================
        # 阶段 4: 写入头部 (必须在最后，覆盖节数据区中重叠的头部字节)
        # =========================================================
        # DOS Header
        struct.pack_into("<H", pe, 0, dos_magic)
        struct.pack_into("<I", pe, 0x3C, dos_lfanew)

        # NT Headers: PE Signature
        struct.pack_into("<I", pe, dos_lfanew, pe_sig)

        # File Header
        fh_off = dos_lfanew + 4
        struct.pack_into("<H", pe, fh_off, machine)
        struct.pack_into("<H", pe, fh_off + 2, num_sections)
        struct.pack_into("<I", pe, fh_off + 4, time_stamp)
        struct.pack_into("<I", pe, fh_off + 8, 0)  # PointerToSymbolTable
        struct.pack_into("<I", pe, fh_off + 12, 0)  # NumberOfSymbols
        struct.pack_into("<H", pe, fh_off + 16, size_opt_header)
        struct.pack_into("<H", pe, fh_off + 18, characteristics)

        # Optional Header
        oh_off = fh_off + 20
        struct.pack_into("<H", pe, oh_off, magic)
        struct.pack_into("<I", pe, oh_off + 16, entry_point)
        struct.pack_into("<I", pe, oh_off + 28, image_base)
        struct.pack_into("<I", pe, oh_off + 32, section_align)
        struct.pack_into("<I", pe, oh_off + 36, file_align)
        struct.pack_into("<I", pe, oh_off + 56, size_of_image)
        struct.pack_into("<I", pe, oh_off + 60, size_of_headers)
        struct.pack_into("<H", pe, oh_off + 68, subsystem)
        struct.pack_into("<H", pe, oh_off + 70, dll_chars)
        struct.pack_into("<I", pe, oh_off + 92, num_rva)

        # Data Directories
        dd_off = oh_off + 96
        pe[dd_off:dd_off + 128] = dd

        # Section Headers
        sec_off = section_header_start
        for s in sections:
            name, vsize, va, rawsize, rawoff, chars = s
            name_bytes = name[:8].ljust(8, b"\x00")
            pe[sec_off:sec_off + 8] = name_bytes
            struct.pack_into("<I", pe, sec_off + 8, vsize)
            struct.pack_into("<I", pe, sec_off + 12, va)
            struct.pack_into("<I", pe, sec_off + 16, rawsize)
            struct.pack_into("<I", pe, sec_off + 20, rawoff)
            struct.pack_into("<I", pe, sec_off + 36, chars)
            sec_off += 40

        return bytes(pe)

    def _build_pe_with_imports(self):
        """
        构建包含导入表的 PE 文件。

        在 .rdata 节 (RVA 0x2000, 文件偏移 0x400) 放置导入表数据。
        在 .data 节 (RVA 0x3000, 文件偏移 0x600) 放置 IAT/INT 条目。
        """
        # 导入表布局 (文件偏移 0x400, RVA 0x2000):
        #   RVA 0x2000: IMAGE_IMPORT_DESCRIPTOR (kernel32.dll) 20 bytes
        #   RVA 0x2014: 终止条目 (全零) 20 bytes
        #   RVA 0x2028: DLL 名称 "kernel32.dll\0" (14 bytes)
        #   RVA 0x2038: IMAGE_IMPORT_BY_NAME GetProcAddress (Hint=0, "GetProcAddress\0")
        #   RVA 0x2050: IMAGE_IMPORT_BY_NAME LoadLibraryA (Hint=0, "LoadLibraryA\0")

        import_desc_offset = 0x400  # RVA 0x2000
        dll_name_offset = 0x428     # RVA 0x2028
        func1_offset = 0x438        # RVA 0x2038
        func2_offset = 0x450        # RVA 0x2050
        iat_offset = 0x600          # RVA 0x3000, in .data

        extra = {}

        # IMAGE_IMPORT_DESCRIPTOR for kernel32.dll
        desc = struct.pack("<I", 0x3000)  # OriginalFirstThunk -> RVA 0x3000 (INT)
        desc += struct.pack("<I", 0)       # TimeDateStamp
        desc += struct.pack("<I", 0)       # ForwarderChain
        desc += struct.pack("<I", 0x2028)  # NameRVA -> DLL name
        desc += struct.pack("<I", 0x3000)  # FirstThunk -> RVA 0x3000 (IAT)
        extra[import_desc_offset] = desc

        # Terminator entry (20 bytes of zeros)
        extra[import_desc_offset + 20] = b"\x00" * 20

        # DLL name string
        extra[dll_name_offset] = b"kernel32.dll\x00"

        # IMAGE_IMPORT_BY_NAME for GetProcAddress
        ibn1 = struct.pack("<H", 0) + b"GetProcAddress\x00"
        extra[func1_offset] = ibn1

        # IMAGE_IMPORT_BY_NAME for LoadLibraryA
        ibn2 = struct.pack("<H", 0) + b"LoadLibraryA\x00"
        extra[func2_offset] = ibn2

        # INT/IAT entries (RVA 0x3000, file offset 0x600)
        iat_data = struct.pack("<I", 0x2038)  # -> GetProcAddress
        iat_data += struct.pack("<I", 0x2050)  # -> LoadLibraryA
        iat_data += struct.pack("<I", 0)       # Terminator
        extra[iat_offset] = iat_data

        # 在 Data Directories 中设置 IMPORT 条目
        dd = bytearray(128)
        # IMPORT 目录 (索引 1): VirtualAddress=0x2000, Size=0x100
        struct.pack_into("<I", dd, 8, 0x2000)   # VA
        struct.pack_into("<I", dd, 12, 0x100)   # Size

        return self._build_pe(
            data_directories=bytes(dd),
            extra_data=extra,
            pad_to=0x800,
        )

    def _build_pe_with_exports(self):
        """
        构建包含导出表的 PE 文件。

        在 .rdata 节 (RVA 0x2000, 文件偏移 0x400) 放置导出表。
        """
        exp_dir_offset = 0x400   # RVA 0x2000
        dll_name_offset = 0x440  # RVA 0x2040
        func_names_offset = 0x460  # RVA 0x2060
        name_ordinals_offset = 0x480  # RVA 0x2080
        func_rvas_offset = 0x490  # RVA 0x2090

        # 函数表在 .data 节 (RVA 0x3000, 文件偏移 0x600)
        func1_rva = 0x3100  # RVA of function 1
        func2_rva = 0x3200  # RVA of function 2

        extra = {}

        # IMAGE_EXPORT_DIRECTORY (40 bytes)
        exp_dir = struct.pack("<I", 0)           # Characteristics
        exp_dir += struct.pack("<I", 0x12345678)  # TimeDateStamp
        exp_dir += struct.pack("<H", 0)           # MajorVersion
        exp_dir += struct.pack("<H", 0)           # MinorVersion
        exp_dir += struct.pack("<I", 0x2040)      # NameRVA
        exp_dir += struct.pack("<I", 1)           # Base (ordinal base)
        exp_dir += struct.pack("<I", 2)           # NumberOfFunctions
        exp_dir += struct.pack("<I", 2)           # NumberOfNames
        exp_dir += struct.pack("<I", 0x2090)      # AddressOfFunctions
        exp_dir += struct.pack("<I", 0x2060)      # AddressOfNames
        exp_dir += struct.pack("<I", 0x2080)      # AddressOfNameOrdinals
        extra[exp_dir_offset] = exp_dir

        # DLL name
        extra[dll_name_offset] = b"test_pe.dll\x00"

        # 函数名数组 (RVA 0x2060): 指向函数名 RVA 的指针数组
        name1_rva = 0x204C  # RVA of "ExportedFunc1"
        extra[func_names_offset] = struct.pack("<I", name1_rva)
        extra[func_names_offset + 4] = struct.pack("<I", func1_rva)  # second name points to func1_rva string

        # 函数名字符串
        extra[dll_name_offset + 12] = b"ExportedFunc1\x00"
        extra[0x600] = b"ExportedFunc2\x00"  # at func1_rva file offset

        # 名称序号数组 (RVA 0x2080): WORD 数组
        extra[name_ordinals_offset] = struct.pack("<H", 0)  # ordinal 0
        extra[name_ordinals_offset + 2] = struct.pack("<H", 1)  # ordinal 1

        # 函数地址数组 (RVA 0x2090): DWORD 数组
        extra[func_rvas_offset] = struct.pack("<I", func1_rva)
        extra[func_rvas_offset + 4] = struct.pack("<I", func2_rva)

        # 在 Data Directories 中设置 EXPORT 条目
        dd = bytearray(128)
        struct.pack_into("<I", dd, 0, 0x2000)   # VA
        struct.pack_into("<I", dd, 4, 0x100)    # Size

        return self._build_pe(
            data_directories=bytes(dd),
            extra_data=extra,
            pad_to=0x800,
        )

    def _build_pe_with_relocations(self):
        """
        构建包含重定位表的 PE 文件。

        在 .rdata 节 (RVA 0x2000, 文件偏移 0x400) 放置重定位块。
        """
        reloc_offset = 0x400  # RVA 0x2000

        extra = {}

        # IMAGE_BASE_RELOCATION block
        block = struct.pack("<I", 0x1000)  # PageRVA
        block += struct.pack("<I", 16)      # BlockSize (8 header + 4 entries * 2 bytes)
        block += struct.pack("<H", 0x3020)  # Type=3 (HIGHLOW), Offset=0x020
        block += struct.pack("<H", 0x3040)  # Type=3 (HIGHLOW), Offset=0x040
        block += struct.pack("<H", 0x3060)  # Type=3 (HIGHLOW), Offset=0x060
        block += struct.pack("<H", 0x0000)  # Type=0 (ABSOLUTE), Offset=0x000 (padding)
        extra[reloc_offset] = block

        # 在 Data Directories 中设置 BASERELOC 条目
        dd = bytearray(128)
        struct.pack_into("<I", dd, 5 * 8, 0x2000)   # VA (index 5 = BASERELOC)
        struct.pack_into("<I", dd, 5 * 8 + 4, 16)    # Size

        return self._build_pe(
            data_directories=bytes(dd),
            extra_data=extra,
            pad_to=0x800,
        )

    def _write_pe(self, data: bytes):
        """将 PE 数据写入临时文件"""
        with open(self.pe_path, "wb") as f:
            f.write(data)

    def _make_analyzer(self, pe_data: bytes = None) -> "PeAnalyzer":
        """创建并返回一个已加载 PE 的 PeAnalyzer 实例"""
        if pe_data is not None:
            self._write_pe(pe_data)
        return self.PeAnalyzer(self.pe_path)

    # ============================================================
    # 1. DOS Header 解析
    # ============================================================

    def test_parse_dos_header(self):
        """验证 MZ 签名和 e_lfanew"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_dos_header()

        self.assertTrue(result["success"])
        self.assertEqual(result["e_magic"], IMAGE_DOS_SIGNATURE)
        self.assertEqual(result["e_magic_str"], "MZ")
        self.assertEqual(result["e_lfanew"], 0x80)
        self.assertEqual(result["e_lfanew_hex"], "0x80")
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["size"], 64)

    def test_parse_dos_header_invalid_magic(self):
        """无效 DOS 魔数"""
        pe = self._build_pe(dos_magic=0x1234)
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_dos_header()

        self.assertTrue(result["success"])
        self.assertEqual(result["e_magic"], 0x1234)
        self.assertEqual(result["e_magic_str"], "INVALID")
        self.assertFalse(result["is_valid"])

    def test_parse_dos_header_custom_lfanew(self):
        """自定义 e_lfanew 偏移"""
        pe = self._build_pe(dos_e_lfanew=0x100)
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_dos_header()

        self.assertTrue(result["success"])
        self.assertEqual(result["e_lfanew"], 0x100)
        self.assertEqual(result["e_lfanew_hex"], "0x100")

    # ============================================================
    # 2. NT Headers 解析
    # ============================================================

    def test_parse_nt_headers(self):
        """验证 PE 签名"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_nt_headers()

        self.assertTrue(result["success"])
        self.assertEqual(result["Signature"], IMAGE_NT_SIGNATURE)
        self.assertEqual(result["Signature_str"], "PE\\0\\0")
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["pe_offset"], 0x80)

    def test_parse_nt_headers_invalid(self):
        """无效 PE 签名"""
        pe = self._build_pe(pe_sig=0xDEADBEEF)
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_nt_headers()

        self.assertTrue(result["success"])
        self.assertEqual(result["Signature"], 0xDEADBEEF)
        self.assertFalse(result["is_valid"])

    # ============================================================
    # 3. File Header 解析
    # ============================================================

    def test_parse_file_header(self):
        """验证 Machine / NumberOfSections / Characteristics"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_file_header()

        self.assertTrue(result["success"])
        self.assertEqual(result["Machine"], 0x014C)
        self.assertEqual(result["MachineName"], "I386 (x86)")
        self.assertEqual(result["NumberOfSections"], 3)
        self.assertEqual(result["Characteristics"], 0x102)
        self.assertTrue(result["is_exe"])
        self.assertFalse(result["is_dll"])
        self.assertTrue(result["is_32bit"])
        self.assertEqual(result["SizeOfOptionalHeader"], 0xE0)
        self.assertEqual(result["TimeDateStamp"], 0x12345678)
        self.assertEqual(result["size"], 20)

    def test_parse_file_header_dll(self):
        """DLL 类型的 Characteristics"""
        pe = self._build_pe(characteristics=0x2102)  # DLL + EXECUTABLE_IMAGE + 32BIT
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_file_header()

        self.assertTrue(result["success"])
        self.assertTrue(result["is_dll"])
        self.assertTrue(result["is_exe"])
        self.assertIn("DLL", result["CharacteristicsFlags"])

    # ============================================================
    # 4. Optional Header 解析
    # ============================================================

    def test_parse_optional_header(self):
        """验证 Magic / ImageBase / EntryPoint / Subsystem"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_optional_header()

        self.assertTrue(result["success"])
        self.assertEqual(result["Magic"], IMAGE_NT_OPTIONAL_HDR32_MAGIC)
        self.assertEqual(result["MagicName"], "PE32")
        self.assertEqual(result["AddressOfEntryPoint"], 0x1000)
        self.assertEqual(result["ImageBase"], 0x400000)
        self.assertEqual(result["SectionAlignment"], 0x1000)
        self.assertEqual(result["FileAlignment"], 0x200)
        self.assertEqual(result["Subsystem"], 2)
        self.assertEqual(result["SubsystemName"], "WINDOWS_GUI")
        self.assertTrue(result["is_gui"])
        self.assertFalse(result["is_console"])
        self.assertEqual(result["SizeOfImage"], 0x5000)
        self.assertEqual(result["SizeOfHeaders"], 0x200)
        self.assertEqual(result["NumberOfRvaAndSizes"], 16)
        self.assertEqual(result["size"], 224)

    def test_parse_optional_header_console(self):
        """控制台子系统"""
        pe = self._build_pe(subsystem=3)
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_optional_header()

        self.assertTrue(result["success"])
        self.assertEqual(result["Subsystem"], 3)
        self.assertEqual(result["SubsystemName"], "WINDOWS_CUI")
        self.assertTrue(result["is_console"])
        self.assertFalse(result["is_gui"])

    def test_parse_optional_header_custom_values(self):
        """自定义 EntryPoint 和 ImageBase"""
        pe = self._build_pe(entry_point=0x5678, image_base=0x10000000)
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_optional_header()

        self.assertTrue(result["success"])
        self.assertEqual(result["AddressOfEntryPoint"], 0x5678)
        self.assertEqual(result["ImageBase"], 0x10000000)
        self.assertEqual(result["ImageBase_hex"], "0x10000000")

    # ============================================================
    # 5. 节表解析
    # ============================================================

    def test_parse_section_headers(self):
        """验证节名 / 数量 / 特性"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_section_headers()

        self.assertTrue(result["success"])
        self.assertEqual(result["section_count"], 3)
        sections = result["sections"]
        self.assertEqual(len(sections), 3)

        # .text
        self.assertEqual(sections[0]["Name"], ".text")
        self.assertEqual(sections[0]["VirtualAddress"], 0x1000)
        self.assertEqual(sections[0]["VirtualSize"], 0x1000)
        self.assertEqual(sections[0]["PointerToRawData"], 0x200)
        self.assertEqual(sections[0]["SizeOfRawData"], 0x200)
        self.assertTrue(sections[0]["is_code"])
        self.assertTrue(sections[0]["is_executable"])
        self.assertTrue(sections[0]["is_readable"])
        self.assertFalse(sections[0]["is_writable"])
        self.assertIn("MEM_EXECUTE", sections[0]["CharacteristicsFlags"])
        self.assertIn("MEM_READ", sections[0]["CharacteristicsFlags"])

        # .rdata
        self.assertEqual(sections[1]["Name"], ".rdata")
        self.assertEqual(sections[1]["VirtualAddress"], 0x2000)
        self.assertTrue(sections[1]["is_readable"])
        self.assertFalse(sections[1]["is_executable"])
        self.assertFalse(sections[1]["is_writable"])

        # .data
        self.assertEqual(sections[2]["Name"], ".data")
        self.assertEqual(sections[2]["VirtualAddress"], 0x3000)
        self.assertTrue(sections[2]["is_readable"])
        self.assertTrue(sections[2]["is_writable"])
        self.assertFalse(sections[2]["is_executable"])
        self.assertIn("MEM_WRITE", sections[2]["CharacteristicsFlags"])

    def test_parse_section_headers_cache(self):
        """节表解析结果缓存 (内部 _sections 列表复用)"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result1 = analyzer.parse_section_headers()
        result2 = analyzer.parse_section_headers()
        # 返回的 dict 每次都可能新建，但内部的 sections 列表应同一对象
        self.assertIs(result1["sections"], result2["sections"])
        self.assertEqual(result1["section_count"], result2["section_count"])

    # ============================================================
    # 6. Data Directories 解析
    # ============================================================

    def test_parse_data_directories(self):
        """验证 16 个目录"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_data_directories()

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 16)
        directories = result["directories"]
        self.assertEqual(len(directories), 16)

        # 检查名称
        self.assertEqual(directories[0]["name"], "EXPORT")
        self.assertEqual(directories[1]["name"], "IMPORT")
        self.assertEqual(directories[2]["name"], "RESOURCE")
        self.assertEqual(directories[5]["name"], "BASERELOC")
        self.assertEqual(directories[15]["name"], "RESERVED")

        # 全部为零，所以 is_present 为 False
        for d in directories:
            self.assertFalse(d["is_present"])

    def test_parse_data_directories_with_data(self):
        """有数据的数据目录"""
        dd = bytearray(128)
        struct.pack_into("<I", dd, 1 * 8, 0x2000)      # IMPORT VA
        struct.pack_into("<I", dd, 1 * 8 + 4, 0x100)   # IMPORT Size
        pe = self._build_pe(data_directories=bytes(dd))
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_data_directories()

        self.assertTrue(result["success"])
        self.assertTrue(result["directories"][1]["is_present"])
        self.assertFalse(result["directories"][0]["is_present"])

    # ============================================================
    # 7. 有效性检查
    # ============================================================

    def test_is_valid_pe(self):
        """有效 PE 返回 True"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        self.assertTrue(analyzer.is_valid_pe())

    def test_not_valid_pe(self):
        """无效文件返回 False"""
        # 写入纯文本
        self._write_pe(b"This is not a PE file at all")
        analyzer = self.PeAnalyzer(self.pe_path)
        self.assertFalse(analyzer.is_valid_pe())

    def test_not_valid_pe_empty(self):
        """空文件返回 False"""
        self._write_pe(b"")
        analyzer = self.PeAnalyzer(self.pe_path)
        self.assertFalse(analyzer.is_valid_pe())

    def test_not_valid_pe_too_small(self):
        """文件太小返回 False"""
        self._write_pe(b"MZ" + b"\x00" * 30)
        analyzer = self.PeAnalyzer(self.pe_path)
        self.assertFalse(analyzer.is_valid_pe())

    def test_not_valid_pe_wrong_dos_sig(self):
        """错误 DOS 签名"""
        self._write_pe(b"XX" + b"\x00" * 62)
        analyzer = self.PeAnalyzer(self.pe_path)
        self.assertFalse(analyzer.is_valid_pe())

    def test_not_valid_pe_wrong_pe_sig(self):
        """错误 PE 签名"""
        pe = self._build_pe(pe_sig=0xDEADBEEF)
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        self.assertFalse(analyzer.is_valid_pe())

    # ============================================================
    # 8. 节信息查找
    # ============================================================

    def test_get_section_info(self):
        """按名称查找节"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.get_section_info(".text")

        self.assertTrue(result["success"])
        self.assertEqual(result["section"]["Name"], ".text")
        self.assertEqual(result["section"]["VirtualAddress"], 0x1000)
        self.assertTrue(result["section"]["is_executable"])

    def test_get_section_info_case_insensitive(self):
        """大小写不敏感匹配"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.get_section_info(".TEXT")

        self.assertTrue(result["success"])
        self.assertEqual(result["section"]["Name"], ".text")

    def test_get_section_info_not_found(self):
        """查找不存在的节"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.get_section_info(".nonexistent")

        self.assertFalse(result["success"])
        self.assertIn("未找到节", result["message"])

    def test_get_section_info_rdata(self):
        """查找 .rdata 节"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.get_section_info(".rdata")

        self.assertTrue(result["success"])
        self.assertEqual(result["section"]["Name"], ".rdata")

    def test_get_section_info_data(self):
        """查找 .data 节"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.get_section_info(".data")

        self.assertTrue(result["success"])
        self.assertEqual(result["section"]["Name"], ".data")

    # ============================================================
    # 9. 可执行节过滤
    # ============================================================

    def test_get_executable_sections(self):
        """过滤可执行节"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.get_executable_sections()

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["sections"][0]["Name"], ".text")

    def test_get_executable_sections_multiple(self):
        """多个可执行节"""
        custom_sections = [
            (b".text\x00\x00\x00", 0x1000, 0x1000, 0x200, 0x200, 0x60000020),
            (b".rdata\x00\x00",   0x1000, 0x2000, 0x200, 0x400, 0x40000040),
            (b".data\x00\x00\x00", 0x1000, 0x3000, 0x200, 0x600, 0xC0000040),
            (b".xcode\x00\x00",   0x1000, 0x4000, 0x200, 0x800, 0x60000020),
        ]
        pe = self._build_pe(sections=custom_sections, num_sections=4, pad_to=0xA00)
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.get_executable_sections()

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        names = [s["Name"] for s in result["sections"]]
        self.assertIn(".text", names)
        self.assertIn(".xcode", names)

    # ============================================================
    # 10. Code Cave 搜索
    # ============================================================

    def test_find_code_caves_in_sections(self):
        """搜索 Code Cave"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.find_code_caves_in_sections(min_size=32)

        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["cave_count"], 1)
        self.assertIn("caves", result)
        self.assertIn("total_available", result)

        # 至少应该有一个足够大的 cave
        caves = result["caves"]
        for cave in caves:
            self.assertIn("offset", cave)
            self.assertIn("size", cave)
            self.assertIn("fill_type", cave)
            self.assertIn("section", cave)
            self.assertGreaterEqual(cave["size"], 32)

    def test_find_code_caves_min_size_filter(self):
        """Code Cave 最小尺寸过滤"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result_large = analyzer.find_code_caves_in_sections(min_size=128)
        result_small = analyzer.find_code_caves_in_sections(min_size=16)

        # 大尺寸过滤应该返回更少的结果
        self.assertLessEqual(
            result_large.get("cave_count", 0),
            result_small.get("cave_count", 999),
        )

    # ============================================================
    # 11. 版本检测
    # ============================================================

    def test_detect_exe_version(self):
        """版本检测"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.detect_exe_version()

        self.assertTrue(result["success"])
        self.assertIn("file_size", result)
        self.assertEqual(result["time_date_stamp"], 0x12345678)
        self.assertEqual(result["machine"], "I386 (x86)")
        self.assertEqual(result["section_count"], 3)
        self.assertEqual(result["entry_point"], 0x1000)
        self.assertEqual(result["image_base"], 0x400000)
        self.assertEqual(result["subsystem"], "WINDOWS_GUI")
        self.assertTrue(result["is_gui"])
        self.assertIn("compile_date", result)
        self.assertIn("compile_year", result)

    def test_detect_exe_version_with_imports(self):
        """带导入表的版本检测"""
        pe = self._build_pe_with_imports()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.detect_exe_version()

        self.assertTrue(result["success"])
        self.assertIn("imported_dll_count", result)
        self.assertIn("imported_function_count", result)

    # ============================================================
    # 12. 模块信息
    # ============================================================

    def test_get_info(self):
        """验证模块信息"""
        result = self.PeAnalyzer.get_info()

        self.assertTrue(result["success"])
        self.assertEqual(result["module_name"], "pe_analyzer")
        self.assertEqual(result["version"], "1.0.0")
        self.assertIn("description", result)
        self.assertIn("capabilities", result)
        self.assertIsInstance(result["capabilities"], list)
        self.assertGreater(len(result["capabilities"]), 0)
        self.assertIn("supported_formats", result)
        self.assertIn("dependencies", result)

    # ============================================================
    # 13. 导入表解析
    # ============================================================

    def test_parse_import_table(self):
        """导入表解析"""
        pe = self._build_pe_with_imports()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_import_table()

        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["dll_count"], 1)
        self.assertIn("imports", result)
        self.assertIn("kernel32.dll", result["imports"])

        kernel32 = result["imports"]["kernel32.dll"]
        self.assertGreaterEqual(kernel32["function_count"], 1)

        func_names = [f["name"] for f in kernel32["functions"]]
        self.assertIn("GetProcAddress", func_names)

    def test_parse_import_table_no_imports(self):
        """没有导入表的 PE"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_import_table()

        self.assertFalse(result["success"])
        self.assertIn("没有导入表", result["message"])

    def test_list_imported_dlls(self):
        """解析导入 DLL 列表"""
        pe = self._build_pe_with_imports()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.list_imported_dlls()

        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["dll_count"], 1)
        self.assertGreaterEqual(result["total_functions"], 1)
        dll_names = [d["name"] for d in result["dlls"]]
        self.assertIn("kernel32.dll", dll_names)

    def test_list_imported_dlls_no_imports(self):
        """没有导入表时返回空列表"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.list_imported_dlls()

        self.assertFalse(result["success"])

    def test_find_import_by_name(self):
        """按名称查找导入函数"""
        pe = self._build_pe_with_imports()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.find_import_by_name("kernel32.dll", "GetProcAddress")

        self.assertTrue(result["success"])
        self.assertEqual(result["dll_name"], "kernel32.dll")
        self.assertEqual(result["func_name"], "GetProcAddress")

    def test_find_import_by_name_not_found(self):
        """查找不存在的导入函数"""
        pe = self._build_pe_with_imports()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.find_import_by_name("kernel32.dll", "NonExistentFunc")

        self.assertFalse(result["success"])

    # ============================================================
    # 14. 导出表解析
    # ============================================================

    def test_parse_export_table(self):
        """导出表解析"""
        pe = self._build_pe_with_exports()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_export_table()

        self.assertTrue(result["success"])
        self.assertEqual(result["dll_name"], "test_pe.dll")
        self.assertGreaterEqual(result["number_of_functions"], 1)
        self.assertGreaterEqual(result["number_of_names"], 1)
        self.assertGreaterEqual(result["export_count"], 1)

    def test_parse_export_table_no_exports(self):
        """没有导出表"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_export_table()

        self.assertFalse(result["success"])
        self.assertIn("没有导出表", result["message"])

    # ============================================================
    # 15. 重定位表解析
    # ============================================================

    def test_parse_relocations(self):
        """重定位表解析"""
        pe = self._build_pe_with_relocations()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_relocations()

        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["block_count"], 1)
        self.assertIn("entries", result)
        self.assertIn("total_entries", result)
        self.assertGreaterEqual(result["total_entries"], 1)

        # 检查条目类型
        for entry in result["entries"]:
            self.assertIn("type", entry)
            self.assertIn("type_name", entry)
            self.assertIn("rva", entry)

    def test_parse_relocations_no_relocs(self):
        """没有重定位表"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_relocations()

        self.assertFalse(result["success"])
        self.assertIn("没有重定位表", result["message"])

    def test_get_relocation_count(self):
        """重定位条目统计"""
        pe = self._build_pe_with_relocations()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.get_relocation_count()

        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["total_entries"], 1)
        self.assertGreaterEqual(result["block_count"], 1)

    # ============================================================
    # 16. 综合视图
    # ============================================================

    def test_get_full_analysis(self):
        """综合视图"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.get_full_analysis()

        self.assertTrue(result["success"])
        self.assertEqual(result["exe_path"], self.pe_path)
        self.assertIn("exe_size", result)
        self.assertTrue(result["is_valid_pe"])
        self.assertIn("dos_header", result)
        self.assertIn("nt_headers", result)
        self.assertIn("file_header", result)
        self.assertIn("optional_header", result)
        self.assertIn("sections", result)
        self.assertIn("data_directories", result)
        self.assertIn("imports", result)
        self.assertIn("exports", result)
        self.assertIn("relocations", result)
        self.assertIn("resources", result)
        self.assertIn("version_info", result)

    # ============================================================
    # 17. 路径切换
    # ============================================================

    def test_set_exe_path(self):
        """切换路径"""
        pe1 = self._build_pe()
        pe2 = self._build_pe(entry_point=0x9999, time_stamp=0xDEADBEEF)

        path1 = os.path.join(self.tmpdir, "pe1.exe")
        path2 = os.path.join(self.tmpdir, "pe2.exe")
        with open(path1, "wb") as f:
            f.write(pe1)
        with open(path2, "wb") as f:
            f.write(pe2)

        analyzer = self.PeAnalyzer(path1)
        result1 = analyzer.parse_optional_header()
        self.assertEqual(result1["AddressOfEntryPoint"], 0x1000)

        analyzer.set_exe_path(path2)
        result2 = analyzer.parse_optional_header()
        self.assertEqual(result2["AddressOfEntryPoint"], 0x9999)

        fh = analyzer.parse_file_header()
        self.assertEqual(fh["TimeDateStamp"], 0xDEADBEEF)

    def test_set_exe_path_resets_cache(self):
        """切换路径后重置缓存"""
        pe1 = self._build_pe()
        pe2 = self._build_pe(entry_point=0x7777)
        path1 = os.path.join(self.tmpdir, "pe1.exe")
        path2 = os.path.join(self.tmpdir, "pe2.exe")
        with open(path1, "wb") as f:
            f.write(pe1)
        with open(path2, "wb") as f:
            f.write(pe2)

        analyzer = self.PeAnalyzer(path1)
        analyzer.parse_dos_header()
        analyzer.parse_file_header()
        analyzer.parse_optional_header()

        # 切换到 path2 后，_load_and_parse 会重新解析，缓存应指向新数据
        analyzer.set_exe_path(path2)
        oh = analyzer.parse_optional_header()
        self.assertEqual(oh["AddressOfEntryPoint"], 0x7777)

    # ============================================================
    # 18. 路径不存在
    # ============================================================

    def test_exe_not_exists(self):
        """路径不存在"""
        nonexistent = os.path.join(self.tmpdir, "does_not_exist.exe")
        analyzer = self.PeAnalyzer(nonexistent)

        self.assertFalse(analyzer.is_valid_pe())
        result = analyzer.parse_dos_header()
        self.assertFalse(result["success"])
        self.assertIn("EXE 未加载", result["message"])

        result = analyzer.parse_nt_headers()
        self.assertFalse(result["success"])

        result = analyzer.parse_optional_header()
        self.assertFalse(result["success"])

    def test_init_no_path(self):
        """不提供路径的初始化"""
        analyzer = self.PeAnalyzer()
        self.assertFalse(analyzer.is_valid_pe())
        result = analyzer.parse_dos_header()
        self.assertFalse(result["success"])

    # ============================================================
    # 19. 资源表解析
    # ============================================================

    def test_parse_resource_table_no_resources(self):
        """没有资源表"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.parse_resource_table()

        self.assertFalse(result["success"])
        self.assertIn("没有资源表", result["message"])

    # ============================================================
    # 20. 更多边界情况
    # ============================================================

    def test_get_section_info_data_with_summary(self):
        """获取节信息含数据摘要"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        result = analyzer.get_section_info(".data")

        self.assertTrue(result["success"])
        self.assertIn("data_summary", result)
        self.assertIn("zero_bytes", result["data_summary"])

    def test_parse_section_headers_cache_reuse(self):
        """节表缓存重复使用 (内部 _sections 列表)"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        r1 = analyzer.parse_section_headers()
        r2 = analyzer.parse_section_headers()
        # 内部的 sections 列表应被缓存复用
        self.assertIs(r1["sections"], r2["sections"])

    def test_parse_file_header_cache(self):
        """File Header 缓存"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        r1 = analyzer.parse_file_header()
        r2 = analyzer.parse_file_header()
        self.assertIs(r1, r2)

    def test_parse_dos_header_cache(self):
        """DOS Header 缓存"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        r1 = analyzer.parse_dos_header()
        r2 = analyzer.parse_dos_header()
        self.assertIs(r1, r2)

    def test_parse_optional_header_cache(self):
        """Optional Header 缓存"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        r1 = analyzer.parse_optional_header()
        r2 = analyzer.parse_optional_header()
        self.assertIs(r1, r2)

    def test_pe32_detection(self):
        """PE32 格式检测"""
        pe = self._build_pe()
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        # _is_pe32 是内部方法，通过 optional header 的 Magic 判断
        self.assertTrue(analyzer._is_pe32())

    def test_pe32plus_detection(self):
        """PE32+ 格式检测"""
        pe = self._build_pe(magic=0x20B)
        self._write_pe(pe)
        analyzer = self.PeAnalyzer(self.pe_path)
        self.assertFalse(analyzer._is_pe32())
        result = analyzer.parse_optional_header()
        self.assertFalse(result["success"])
        self.assertIn("x64", result["message"])


if __name__ == "__main__":
    unittest.main()