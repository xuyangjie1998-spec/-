"""
San7ModMaker ScriptSOAnalyzer 测试
覆盖 ScriptSOAnalyzer 的初始化、ELF 解析、反汇编、字符串提取、十六进制查看等功能
"""
import os
import sys
import unittest
import tempfile
import shutil
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestScriptSOAnalyzer(unittest.TestCase):
    """验证 ScriptSOAnalyzer 分析器"""

    @classmethod
    def setUpClass(cls):
        from core.scriptso_analyzer import ScriptSOAnalyzer, HAS_CAPSTONE
        cls.ScriptSOAnalyzer = ScriptSOAnalyzer
        cls.HAS_CAPSTONE = HAS_CAPSTONE

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # 创建 Script 子目录
        self.script_dir = os.path.join(self.tmpdir, "Script")
        os.makedirs(self.script_dir, exist_ok=True)
        self.script_so_path = os.path.join(self.script_dir, "Script.so")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    # ============================================================
    # 辅助方法
    # ============================================================

    def _create_script_so(self, content: bytes):
        """在 Script/ 目录下创建 Script.so"""
        with open(self.script_so_path, "wb") as f:
            f.write(content)

    def _make_elf32_header(self):
        """创建最小 ELF32 头部（仅 64 字节，用于 get_script_so_info）"""
        return (
            b'\x7fELF\x01\x01\x01\x00' + b'\x00' * 8 +
            b'\x02\x00\x03\x00' + b'\x00' * 36
        )

    def _make_elf64_header(self):
        """创建最小 ELF64 头部（仅 64 字节，用于 get_script_so_info）"""
        return (
            b'\x7fELF\x02\x01\x01\x00' + b'\x00' * 8 +
            b'\x02\x00\x3E\x00' + b'\x00' * 48
        )

    def _make_minimal_elf32_with_sections(self):
        """创建带段表的最小 ELF32 文件，用于 parse_sections 测试"""
        # ELF header (52 bytes)
        e_ident = b'\x7fELF\x01\x01\x01\x00' + b'\x00' * 8
        e_type = struct.pack('<H', 3)          # ET_DYN
        e_machine = struct.pack('<H', 3)       # EM_386
        e_version = struct.pack('<I', 1)
        e_entry = struct.pack('<I', 0)
        e_phoff = struct.pack('<I', 0)
        e_shoff = struct.pack('<I', 52)        # 段表紧跟在 ELF 头之后
        e_flags = struct.pack('<I', 0)
        e_ehsize = struct.pack('<H', 52)
        e_phentsize = struct.pack('<H', 0)
        e_phnum = struct.pack('<H', 0)
        e_shentsize = struct.pack('<H', 40)
        e_shnum = struct.pack('<H', 3)         # 3 个段（NULL + .text + .shstrtab）
        e_shstrndx = struct.pack('<H', 2)      # 段 2 是 .shstrtab

        elf_header = (e_ident + e_type + e_machine + e_version + e_entry +
                      e_phoff + e_shoff + e_flags + e_ehsize + e_phentsize +
                      e_phnum + e_shentsize + e_shnum + e_shstrndx)
        assert len(elf_header) == 52

        # SHDR 0: NULL 段（40 字节全零）
        shdr0 = b'\x00' * 40

        # .shstrtab 数据
        shstrtab_data = b'\x00.text\x00.shstrtab\x00'
        shstrtab_offset = 52 + 40 + 40 + 40   # ELF头 + 3个段表项之后
        shstrtab_size = len(shstrtab_data)

        # .text 段数据
        text_offset = shstrtab_offset + shstrtab_size
        text_data = b'\x90' * 64  # NOP 填充

        # SHDR 1: .text 段
        shdr1 = struct.pack('<I', 1)           # sh_name = 1 (".text")
        shdr1 += struct.pack('<I', 1)          # sh_type = PROGBITS
        shdr1 += struct.pack('<I', 6)          # sh_flags = SHF_ALLOC | SHF_EXEC
        shdr1 += struct.pack('<I', 0x1000)     # sh_addr
        shdr1 += struct.pack('<I', text_offset) # sh_offset
        shdr1 += struct.pack('<I', 64)         # sh_size
        shdr1 += struct.pack('<I', 0)          # sh_link
        shdr1 += struct.pack('<I', 0)          # sh_info
        shdr1 += struct.pack('<I', 16)         # sh_addralign
        shdr1 += struct.pack('<I', 0)          # sh_entsize
        assert len(shdr1) == 40

        # SHDR 2: .shstrtab 段
        shdr2 = struct.pack('<I', 7)           # sh_name = 7 (".shstrtab")
        shdr2 += struct.pack('<I', 3)          # sh_type = STRTAB
        shdr2 += struct.pack('<I', 0)          # sh_flags
        shdr2 += struct.pack('<I', 0)          # sh_addr
        shdr2 += struct.pack('<I', shstrtab_offset)  # sh_offset
        shdr2 += struct.pack('<I', shstrtab_size)    # sh_size
        shdr2 += struct.pack('<I', 0)          # sh_link
        shdr2 += struct.pack('<I', 0)          # sh_info
        shdr2 += struct.pack('<I', 1)          # sh_addralign
        shdr2 += struct.pack('<I', 0)          # sh_entsize
        assert len(shdr2) == 40

        return elf_header + shdr0 + shdr1 + shdr2 + shstrtab_data + text_data

    # ============================================================
    # 1-2. 初始化测试
    # ============================================================

    def test_init_no_path(self):
        """无路径初始化"""
        analyzer = self.ScriptSOAnalyzer()
        self.assertIsNone(analyzer.game_path)
        self.assertEqual(analyzer.script_dir, "")
        self.assertEqual(analyzer._script_so_path, "")

    def test_init_with_path(self):
        """带路径初始化"""
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        self.assertEqual(analyzer.game_path, self.tmpdir)
        self.assertEqual(analyzer.script_dir, self.script_dir)
        self.assertEqual(analyzer._script_so_path, self.script_so_path)

    # ============================================================
    # 3. set_game_path 测试
    # ============================================================

    def test_set_game_path(self):
        """set_game_path 更新路径"""
        analyzer = self.ScriptSOAnalyzer()
        analyzer.set_game_path(self.tmpdir)
        self.assertEqual(analyzer.game_path, self.tmpdir)
        self.assertEqual(analyzer.script_dir, self.script_dir)
        self.assertEqual(analyzer._script_so_path, self.script_so_path)

    # ============================================================
    # 4-5. script_so_exists 测试
    # ============================================================

    def test_script_so_exists_false(self):
        """Script.so 不存在时返回 False"""
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        self.assertFalse(analyzer.script_so_exists())

    def test_script_so_exists_true(self):
        """创建 Script.so 后返回 True"""
        self._create_script_so(b'\x00' * 100)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        self.assertTrue(analyzer.script_so_exists())

    # ============================================================
    # 6-8. get_script_so_info 测试
    # ============================================================

    def test_get_script_so_info_no_file(self):
        """无文件时返回 exists=False"""
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        info = analyzer.get_script_so_info()
        self.assertFalse(info["exists"])
        self.assertEqual(info["path"], self.script_so_path)
        self.assertIn("message", info)

    def test_get_script_so_info_not_elf(self):
        """非 ELF 文件时 is_elf=False"""
        self._create_script_so(b'NOT_AN_ELF_FILE' * 10)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        info = analyzer.get_script_so_info()
        self.assertTrue(info["exists"])
        self.assertFalse(info["is_elf"])
        self.assertGreater(info["size"], 0)
        self.assertIn("size_kb", info)
        self.assertIn("size_mb", info)

    def test_get_script_so_info_elf(self):
        """ELF 文件时正确识别并解析头部"""
        self._create_script_so(self._make_elf32_header())
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        info = analyzer.get_script_so_info()
        self.assertTrue(info["exists"])
        self.assertTrue(info["is_elf"])
        self.assertEqual(info["elf_info"]["class"], "ELF32")
        self.assertEqual(info["elf_info"]["endian"], "Little-Endian")
        self.assertIn("machine", info["elf_info"])

    # ============================================================
    # 9-10. _parse_elf_header 测试
    # ============================================================

    def test_parse_elf_header_32bit(self):
        """解析 ELF32 头部"""
        header = self._make_elf32_header()
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        elf = analyzer._parse_elf_header(header)
        self.assertEqual(elf["class"], "ELF32")
        self.assertEqual(elf["endian"], "Little-Endian")
        self.assertEqual(elf["version"], 1)
        self.assertIn("EXEC", elf["type"])
        self.assertIn("i386", elf["machine"])

    def test_parse_elf_header_64bit(self):
        """解析 ELF64 头部"""
        header = self._make_elf64_header()
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        elf = analyzer._parse_elf_header(header)
        self.assertEqual(elf["class"], "ELF64")
        self.assertEqual(elf["endian"], "Little-Endian")
        self.assertIn("EXEC", elf["type"])
        self.assertIn("x86-64", elf["machine"])

    # ============================================================
    # 11-13. parse_sections 测试
    # ============================================================

    def test_parse_sections_no_file(self):
        """无文件时返回错误"""
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.parse_sections()
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    def test_parse_sections_not_elf(self):
        """非 ELF 文件时返回错误"""
        self._create_script_so(b'NOT_ELF' * 10)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.parse_sections()
        self.assertFalse(result["success"])
        self.assertIn("ELF", result["message"])

    def test_parse_sections_32bit(self):
        """解析 ELF32 段表"""
        self._create_script_so(self._make_minimal_elf32_with_sections())
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.parse_sections()
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["count"], 2)
        self.assertFalse(result["is_64bit"])
        # 验证段名称已解析
        names = [s.get("name", "") for s in result["sections"]]
        self.assertIn(".text", names)
        self.assertIn(".shstrtab", names)

    # ============================================================
    # 14-15. parse_symbols 测试
    # ============================================================

    def test_parse_symbols_no_file(self):
        """无文件时返回错误"""
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.parse_symbols()
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    def test_parse_symbols_invalid(self):
        """非 ELF 文件时返回错误"""
        self._create_script_so(b'NOT_ELF' * 10)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.parse_symbols()
        self.assertFalse(result["success"])
        self.assertIn("ELF", result["message"])

    # ============================================================
    # 16-18. disassemble 测试
    # ============================================================

    def test_disassemble_no_file(self):
        """无文件时返回错误"""
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.disassemble()
        if self.HAS_CAPSTONE:
            self.assertFalse(result["success"])
            self.assertIn("不存在", result["message"])
        else:
            self.assertFalse(result["success"])
            self.assertIn("Capstone", result["message"])

    def test_disassemble_not_elf(self):
        """非 ELF 文件时返回错误"""
        self._create_script_so(b'NOT_ELF' * 10)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.disassemble()
        if self.HAS_CAPSTONE:
            self.assertFalse(result["success"])
            self.assertIn("无法确定目标架构", result["message"])
        else:
            self.assertFalse(result["success"])
            self.assertIn("Capstone", result["message"])

    def test_disassemble_no_capstone(self):
        """未安装 Capstone 时返回提示"""
        self._create_script_so(self._make_elf32_header())
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.disassemble()
        if not self.HAS_CAPSTONE:
            self.assertFalse(result["success"])
            self.assertIn("Capstone", result["message"])
        else:
            # Capstone 已安装，至少会尝试反汇编
            self.assertIn("success", result)

    # ============================================================
    # 19-20. _get_capstone_arch 测试
    # ============================================================

    def test_get_capstone_arch_no_file(self):
        """无文件时返回 (None, None)"""
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        arch, mode = analyzer._get_capstone_arch()
        self.assertIsNone(arch)
        self.assertIsNone(mode)

    def test_get_capstone_arch_invalid(self):
        """非 ELF 文件时返回 (None, None)"""
        self._create_script_so(b'NOT_ELF' * 10)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        arch, mode = analyzer._get_capstone_arch()
        self.assertIsNone(arch)
        self.assertIsNone(mode)

    # ============================================================
    # 21-22. extract_strings 测试
    # ============================================================

    def test_extract_strings_no_file(self):
        """无文件时返回空列表"""
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.extract_strings()
        self.assertEqual(result, [])

    def test_extract_strings_basic(self):
        """从测试数据中提取 ASCII 字符串"""
        test_data = b'Hello\x00World\x00GenSkillStart123\x00\x00\x00Test\x00'
        self._create_script_so(test_data)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.extract_strings(min_length=4)
        texts = [s["text"] for s in result]
        self.assertIn("Hello", texts)
        self.assertIn("World", texts)
        self.assertIn("GenSkillStart123", texts)
        self.assertIn("Test", texts)
        # 验证偏移量
        for s in result:
            self.assertIn("offset", s)
            self.assertIn("offset_hex", s)
            self.assertIn("length", s)
            self.assertEqual(s["length"], len(s["text"]))
            self.assertGreaterEqual(s["length"], 4)

    # ============================================================
    # 23-24. hex_view 测试
    # ============================================================

    def test_hex_view_no_file(self):
        """无文件时返回错误"""
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.hex_view()
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    def test_hex_view_valid(self):
        """有效文件返回十六进制 dump"""
        self._create_script_so(b'\x00\x01\x02\x03' * 16)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.hex_view(offset=0, length=32)
        self.assertTrue(result["success"])
        self.assertEqual(result["offset"], 0)
        self.assertEqual(result["length"], 32)
        self.assertGreater(len(result["hex_lines"]), 0)
        self.assertIn("total_size", result)

    # ============================================================
    # 25-26. hex_search 测试
    # ============================================================

    def test_hex_search_no_file(self):
        """无文件时返回错误"""
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.hex_search("AABB")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    def test_hex_search_valid(self):
        """搜索十六进制模式"""
        self._create_script_so(
            b'\x00' * 10 + b'\xDE\xAD\xBE\xEF' + b'\x00' * 10 +
            b'\xDE\xAD\xBE\xEF' + b'\x00' * 10
        )
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.hex_search("DEADBEEF")
        self.assertTrue(result["success"])
        self.assertEqual(result["match_count"], 2)
        self.assertEqual(len(result["positions"]), 2)

    # ============================================================
    # 27. KNOWN_PATTERNS 类属性测试
    # ============================================================

    def test_get_known_patterns(self):
        """KNOWN_PATTERNS 类属性是一个非空列表"""
        patterns = self.ScriptSOAnalyzer.KNOWN_PATTERNS
        self.assertIsInstance(patterns, list)
        self.assertGreater(len(patterns), 0)
        # 每个模式是一个 (pattern, description) 元组
        for p in patterns:
            self.assertIsInstance(p, tuple)
            self.assertEqual(len(p), 2)
            self.assertIsInstance(p[0], str)
            self.assertIsInstance(p[1], str)

    # ============================================================
    # 28. analyze_strings 测试（等效于 find_known_patterns）
    # ============================================================

    def test_analyze_strings_no_file(self):
        """无文件时 analyze_strings 返回错误"""
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.analyze_strings()
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    # ============================================================
    # 29. list_script_files 测试
    # ============================================================

    def test_list_script_files_empty(self):
        """空 Script 目录返回空列表"""
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        files = analyzer.list_script_files()
        self.assertEqual(files, [])

    def test_list_script_files_with_files(self):
        """Script 目录中有文件时正确列出"""
        # 创建几个文件
        self._create_script_so(b'\x00' * 100)
        with open(os.path.join(self.script_dir, "readme.txt"), "w") as f:
            f.write("test")
        with open(os.path.join(self.script_dir, "data.bin"), "wb") as f:
            f.write(b'\x00' * 50)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        files = analyzer.list_script_files()
        self.assertEqual(len(files), 3)
        names = [f["name"] for f in files]
        self.assertIn("Script.so", names)
        self.assertIn("readme.txt", names)
        self.assertIn("data.bin", names)
        # 验证 Script.so 标记
        for f in files:
            self.assertIn("name", f)
            self.assertIn("path", f)
            self.assertIn("size", f)
            self.assertIn("type", f)
            if f["name"] == "Script.so":
                self.assertTrue(f["is_script_so"])
            else:
                self.assertFalse(f["is_script_so"])

    # ============================================================
    # 30. 常量测试
    # ============================================================

    def test_constants(self):
        """ELF_MAGIC 和 KNOWN_PATTERNS 常量正确"""
        self.assertEqual(self.ScriptSOAnalyzer.ELF_MAGIC, b"\x7fELF")
        self.assertIsInstance(self.ScriptSOAnalyzer.KNOWN_PATTERNS, list)
        self.assertGreater(len(self.ScriptSOAnalyzer.KNOWN_PATTERNS), 0)

    # ============================================================
    # 补充测试：_parse_sections_64
    # ============================================================

    def test_parse_sections_64bit(self):
        """解析 ELF64 段表"""
        # 创建最小 ELF64 文件（带段表）
        e_ident = b'\x7fELF\x02\x01\x01\x00' + b'\x00' * 8
        e_type = struct.pack('<H', 3)
        e_machine = struct.pack('<H', 0x3E)
        e_version = struct.pack('<I', 1)
        e_entry = struct.pack('<Q', 0)
        e_phoff = struct.pack('<Q', 0)
        e_shoff = struct.pack('<Q', 64)       # 段表在 ELF64 头之后
        e_flags = struct.pack('<I', 0)
        e_ehsize = struct.pack('<H', 64)
        e_phentsize = struct.pack('<H', 0)
        e_phnum = struct.pack('<H', 0)
        e_shentsize = struct.pack('<H', 64)
        e_shnum = struct.pack('<H', 3)
        e_shstrndx = struct.pack('<H', 2)

        elf_header = (e_ident + e_type + e_machine + e_version + e_entry +
                      e_phoff + e_shoff + e_flags + e_ehsize + e_phentsize +
                      e_phnum + e_shentsize + e_shnum + e_shstrndx)
        assert len(elf_header) == 64

        # SHDR 0: NULL（64 字节全零）
        shdr0 = b'\x00' * 64

        # .shstrtab 数据
        shstrtab_data = b'\x00.text\x00.shstrtab\x00'
        shstrtab_offset = 64 + 64 + 64 + 64  # ELF头 + 3个64字节段表项
        shstrtab_size = len(shstrtab_data)

        text_offset = shstrtab_offset + shstrtab_size
        text_data = b'\x90' * 32

        # SHDR 1: .text
        shdr1 = struct.pack('<I', 1)
        shdr1 += struct.pack('<I', 1)
        shdr1 += struct.pack('<Q', 6)
        shdr1 += struct.pack('<Q', 0x1000)
        shdr1 += struct.pack('<Q', text_offset)
        shdr1 += struct.pack('<Q', 32)
        shdr1 += struct.pack('<I', 0)
        shdr1 += struct.pack('<I', 0)
        shdr1 += struct.pack('<Q', 16)
        shdr1 += struct.pack('<Q', 0)
        assert len(shdr1) == 64

        # SHDR 2: .shstrtab
        shdr2 = struct.pack('<I', 7)
        shdr2 += struct.pack('<I', 3)
        shdr2 += struct.pack('<Q', 0)
        shdr2 += struct.pack('<Q', 0)
        shdr2 += struct.pack('<Q', shstrtab_offset)
        shdr2 += struct.pack('<Q', shstrtab_size)
        shdr2 += struct.pack('<I', 0)
        shdr2 += struct.pack('<I', 0)
        shdr2 += struct.pack('<Q', 1)
        shdr2 += struct.pack('<Q', 0)
        assert len(shdr2) == 64

        elf_data = elf_header + shdr0 + shdr1 + shdr2 + shstrtab_data + text_data
        self._create_script_so(elf_data)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.parse_sections()
        self.assertTrue(result["success"])
        self.assertTrue(result["is_64bit"])
        self.assertGreaterEqual(result["count"], 2)
        names = [s.get("name", "") for s in result["sections"]]
        self.assertIn(".text", names)

    # ============================================================
    # 补充测试：hex_view 带偏移
    # ============================================================

    def test_hex_view_with_offset(self):
        """hex_view 从指定偏移量开始"""
        self._create_script_so(b'\x00' * 100 + b'\xAA' * 28)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.hex_view(offset=100, length=28)
        self.assertTrue(result["success"])
        self.assertEqual(result["offset"], 100)
        self.assertEqual(result["length"], 28)

    def test_hex_view_offset_beyond_file(self):
        """hex_view 偏移超出文件范围"""
        self._create_script_so(b'\x00' * 50)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.hex_view(offset=100, length=16)
        self.assertFalse(result["success"])
        self.assertIn("超出", result["message"])

    # ============================================================
    # 补充测试：hex_search 无效模式
    # ============================================================

    def test_hex_search_invalid_pattern(self):
        """无效的十六进制模式返回错误"""
        self._create_script_so(b'\x00' * 100)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.hex_search("ZZZ")
        self.assertFalse(result["success"])
        self.assertIn("无效", result["message"])

    def test_hex_search_no_match(self):
        """搜索不存在的模式返回0条匹配"""
        self._create_script_so(b'\x00' * 100)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.hex_search("DEADBEEF")
        self.assertTrue(result["success"])
        self.assertEqual(result["match_count"], 0)

    # ============================================================
    # 补充测试：list_script_files 无路径
    # ============================================================

    def test_list_script_files_no_path(self):
        """未设置路径时返回空列表"""
        analyzer = self.ScriptSOAnalyzer()
        files = analyzer.list_script_files()
        self.assertEqual(files, [])

    # ============================================================
    # 补充测试：extract_strings 空文件
    # ============================================================

    def test_extract_strings_empty_file(self):
        """空文件提取字符串返回空列表"""
        self._create_script_so(b'')
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.extract_strings()
        self.assertEqual(result, [])

    # ============================================================
    # 补充测试：_parse_elf_header 损坏数据
    # ============================================================

    def test_parse_elf_header_corrupted(self):
        """损坏的 ELF 头部不应抛出异常"""
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        # 只给 4 字节（刚好是魔数，但后续字段不足）
        elf = analyzer._parse_elf_header(b'\x7fELF')
        # 可能包含 parse_error 或部分字段
        self.assertIsInstance(elf, dict)
        # 至少不会崩溃
        if "parse_error" in elf:
            self.assertIsInstance(elf["parse_error"], str)

    # ============================================================
    # 补充测试：analyze_strings 有数据
    # ============================================================

    def test_analyze_strings_with_data(self):
        """analyze_strings 匹配已知模式"""
        test_data = (
            b'GenSkillStart001\x00GenSkillStart002\x00'
            b'BFMagic100\x00BFMagic200\x00'
            b'Soldier001\x00SomeRandomText\x00'
        )
        self._create_script_so(test_data)
        analyzer = self.ScriptSOAnalyzer(self.tmpdir)
        result = analyzer.analyze_strings()
        self.assertTrue(result["success"])
        self.assertGreater(result["total_strings"], 0)
        self.assertIn("patterns", result)
        # 应该匹配到 GenSkillStart 和 BFMagic 模式
        pattern_descs = list(result["patterns"].keys())
        self.assertTrue(any("个人特性" in d for d in pattern_descs))
        self.assertTrue(any("武将技" in d for d in pattern_descs))


if __name__ == "__main__":
    unittest.main(verbosity=2)