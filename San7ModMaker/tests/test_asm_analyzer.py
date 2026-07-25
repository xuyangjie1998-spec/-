"""
汇编级代码分析器测试套件
测试 asm_analyzer.py 的所有核心功能
"""
import unittest
import os
import sys
import struct

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.asm_analyzer import (
    AsmAnalyzer, Instruction, Function, BasicBlock, HookTemplate,
    Arch, CallingConvention
)


class TestAsmAnalyzerInit(unittest.TestCase):
    """测试初始化"""

    def test_init_default(self):
        analyzer = AsmAnalyzer()
        self.assertIsNotNone(analyzer)
        self.assertEqual(analyzer.get_arch(), "UNKNOWN")

    def test_init_capstone_check(self):
        analyzer = AsmAnalyzer()
        # Capstone 可用性检查
        result = analyzer.is_capstone_available()
        self.assertIsInstance(result, bool)

    def test_get_data_info_empty(self):
        analyzer = AsmAnalyzer()
        info = analyzer.get_data_info()
        self.assertEqual(info["size"], 0)
        self.assertFalse(info["disassembled"])


class TestAsmAnalyzerLoad(unittest.TestCase):
    """测试数据加载"""

    def test_load_bytes(self):
        analyzer = AsmAnalyzer()
        data = b'\x55\x89\xe5\x83\xec\x10\xc9\xc3'
        result = analyzer.load_bytes(data, 0x400000, "x86")
        self.assertIs(result, analyzer)
        info = analyzer.get_data_info()
        self.assertEqual(info["size"], 8)
        self.assertEqual(info["arch"], "X86")

    def test_load_bytes_x64(self):
        analyzer = AsmAnalyzer()
        data = b'\x48\x83\xec\x28\x48\x83\xc4\x28\xc3'
        result = analyzer.load_bytes(data, 0x1000, "x64")
        info = analyzer.get_data_info()
        self.assertEqual(info["arch"], "X64")

    def test_load_file_nonexistent(self):
        analyzer = AsmAnalyzer()
        result = analyzer.load_file("/nonexistent/file.bin")
        self.assertFalse(result["success"])

    def test_load_file(self):
        analyzer = AsmAnalyzer()
        temp_path = "/tmp/test_asm.bin"
        with open(temp_path, "wb") as f:
            f.write(b'\x55\x89\xe5\xc9\xc3')
        result = analyzer.load_file(temp_path, 0x400000, "x86")
        self.assertTrue(result["success"])
        self.assertEqual(result["size"], 5)
        os.unlink(temp_path)

    def test_parse_arch_variants(self):
        analyzer = AsmAnalyzer()
        # 测试各种架构
        for arch_str, expected in [
            ("x86", "X86"), ("x32", "X86"), ("i386", "X86"), ("i686", "X86"),
            ("x64", "X64"), ("x86-64", "X64"), ("amd64", "X64"), ("x86_64", "X64"),
            ("arm", "ARM"), ("arm32", "ARM"),
            ("arm64", "ARM64"), ("aarch64", "ARM64"),
        ]:
            analyzer.load_bytes(b'\x00', 0, arch_str)
            self.assertEqual(analyzer.get_arch(), expected)


class TestAsmAnalyzerDisassemble(unittest.TestCase):
    """测试反汇编"""

    def setUp(self):
        self.analyzer = AsmAnalyzer()
        # 一个简单函数: push ebp; mov ebp, esp; sub esp, 0x10; leave; ret
        self.data = b'\x55\x89\xe5\x83\xec\x10\xc9\xc3'
        self.analyzer.load_bytes(self.data, 0x400000, "x86")

    def test_disassemble(self):
        result = self.analyzer.disassemble()
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_disassemble_range(self):
        result = self.analyzer.disassemble(start=0, end=4)
        self.assertTrue(result["success"])

    def test_disassemble_count(self):
        result = self.analyzer.disassemble(count=3)
        self.assertTrue(result["success"])
        self.assertLessEqual(result["count"], 3)

    def test_disassemble_empty_data(self):
        analyzer = AsmAnalyzer()
        result = analyzer.disassemble()
        self.assertFalse(result["success"])

    def test_get_instruction_at(self):
        self.analyzer.disassemble()
        inst = self.analyzer.get_instruction_at(0x400000)
        self.assertIsNotNone(inst)
        self.assertEqual(inst.mnemonic.lower(), "push")

    def test_get_instructions_in_range(self):
        self.analyzer.disassemble()
        insts = self.analyzer.get_instructions_in_range(0x400000, 0x400005)
        self.assertGreater(len(insts), 0)


class TestAsmAnalyzerPatternMatch(unittest.TestCase):
    """测试模式匹配"""

    def setUp(self):
        self.analyzer = AsmAnalyzer()
        self.data = b'\x90\x90\x90\xe8\x00\x00\x00\x00\xe9\x00\x00\x00\x00\x55\x89\xe5\xc3'
        self.analyzer.load_bytes(self.data, 0x400000, "x86")

    def test_find_pattern_exact(self):
        result = self.analyzer.find_pattern(b'\x55\x89\xe5')
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)

    def test_find_pattern_nonexistent(self):
        result = self.analyzer.find_pattern(b'\xDE\xAD\xBE\xEF')
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    def test_find_pattern_with_mask(self):
        result = self.analyzer.find_pattern(b'\xe8\x00\x00\x00\x00', mask=b'x????')
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_find_pattern_mask_mismatch(self):
        result = self.analyzer.find_pattern(b'\xe8\x00', mask=b'x')
        self.assertFalse(result["success"])

    def test_find_pattern_empty_data(self):
        analyzer = AsmAnalyzer()
        result = analyzer.find_pattern(b'\x55')
        self.assertFalse(result["success"])

    def test_match_known_patterns(self):
        result = self.analyzer.match_known_patterns()
        self.assertTrue(result["success"])
        self.assertIn("total_matched", result)

    def test_scan_for_patterns(self):
        patterns = {"test": b'\x55\x89\xe5'}
        result = self.analyzer.scan_for_patterns(patterns)
        self.assertTrue(result["success"])
        self.assertIn("test", result["patterns"])


class TestAsmAnalyzerFunctionDetection(unittest.TestCase):
    """测试函数检测"""

    def setUp(self):
        self.analyzer = AsmAnalyzer()
        # 两个函数
        self.data = (
            b'\x55\x89\xe5\x83\xec\x08\xc9\xc3'  # func1: push ebp; mov ebp, esp; sub esp, 8; leave; ret
            b'\x90\x90\x90'                       # padding
            b'\x55\x8b\xec\xb8\x01\x00\x00\x00\x5d\xc3'  # func2: push ebp; mov ebp, esp; mov eax, 1; pop ebp; ret
        )
        self.analyzer.load_bytes(self.data, 0x400000, "x86")
        self.analyzer.disassemble()

    def test_detect_functions(self):
        result = self.analyzer.detect_functions()
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_get_function_at(self):
        self.analyzer.detect_functions()
        func = self.analyzer.get_function_at(0x400000)
        self.assertIsNotNone(func)

    def test_get_function_at_range(self):
        self.analyzer.detect_functions()
        func = self.analyzer.get_function_at(0x400001)
        self.assertIsNotNone(func)

    def test_get_function_at_nonexistent(self):
        self.analyzer.detect_functions()
        func = self.analyzer.get_function_at(0x999999)
        self.assertIsNone(func)

    def test_get_all_functions(self):
        self.analyzer.detect_functions()
        funcs = self.analyzer.get_all_functions()
        self.assertGreater(len(funcs), 0)


class TestAsmAnalyzerCFG(unittest.TestCase):
    """测试控制流图"""

    def setUp(self):
        self.analyzer = AsmAnalyzer()
        # 带条件跳转的函数
        self.data = (
            b'\x55\x89\xe5'          # push ebp; mov ebp, esp
            b'\x83\x7d\x08\x00'      # cmp dword [ebp+8], 0
            b'\x74\x05'              # je +5
            b'\xb8\x01\x00\x00\x00'  # mov eax, 1
            b'\xeb\x03'              # jmp +3
            b'\xb8\x00\x00\x00\x00'  # mov eax, 0
            b'\x5d\xc3'              # pop ebp; ret
        )
        self.analyzer.load_bytes(self.data, 0x400000, "x86")

    def test_build_cfg_all(self):
        self.analyzer.disassemble()
        self.analyzer.detect_functions()
        result = self.analyzer.build_cfg()
        self.assertTrue(result["success"])

    def test_build_cfg_specific(self):
        self.analyzer.disassemble()
        self.analyzer.detect_functions()
        result = self.analyzer.build_cfg(function_address=0x400000)
        self.assertTrue(result["success"])

    def test_build_cfg_nonexistent(self):
        self.analyzer.disassemble()
        result = self.analyzer.build_cfg(function_address=0x999999)
        self.assertFalse(result["success"])


class TestAsmAnalyzerHookGeneration(unittest.TestCase):
    """测试 Hook 生成"""

    def setUp(self):
        self.analyzer = AsmAnalyzer()
        self.data = b'\x55\x89\xe5\x83\xec\x10\xc9\xc3' * 10
        self.analyzer.load_bytes(self.data, 0x400000, "x86")

    def test_generate_detour_hook_x86(self):
        result = self.analyzer.generate_detour_hook(0x400000, 0x500000, "x86")
        self.assertTrue(result["success"])
        self.assertEqual(result["size"], 5)
        self.assertEqual(result["hook_type"], "detour")

    def test_generate_detour_hook_x64(self):
        result = self.analyzer.generate_detour_hook(0x400000, 0x500000, "x64")
        self.assertTrue(result["success"])
        self.assertEqual(result["size"], 14)

    def test_generate_trampoline(self):
        result = self.analyzer.generate_trampoline(0x400000, 0x500000, 5, "x86")
        self.assertTrue(result["success"])
        self.assertIn("trampoline_code", result)

    def test_generate_trampoline_out_of_range(self):
        result = self.analyzer.generate_trampoline(0x999999, 0x500000, 5, "x86")
        self.assertFalse(result["success"])

    def test_generate_trampoline_no_data(self):
        analyzer = AsmAnalyzer()
        result = analyzer.generate_trampoline(0x400000, 0x500000, 5, "x86")
        self.assertFalse(result["success"])

    def test_generate_inline_hook(self):
        result = self.analyzer.generate_inline_hook(0x400000, 0x500000, 0x600000, 5, "x86")
        self.assertTrue(result["success"])
        self.assertEqual(result["hook_type"], "inline")

    def test_generate_vtable_hook(self):
        result = self.analyzer.generate_vtable_hook(0x400000, 3, 0x500000, "x86")
        self.assertTrue(result["success"])
        self.assertEqual(result["method_index"], 3)

    def test_generate_code_cave_jump(self):
        result = self.analyzer.generate_code_cave_jump(0x400000, 0x500000, "x86")
        self.assertTrue(result["success"])


class TestAsmAnalyzerStatistics(unittest.TestCase):
    """测试统计信息"""

    def setUp(self):
        self.analyzer = AsmAnalyzer()
        self.data = (
            b'\x55\x89\xe5\x83\xec\x10'  # prologue
            b'\xb8\x01\x00\x00\x00'      # mov eax, 1
            b'\x83\xc0\x02'              # add eax, 2
            b'\x50'                      # push eax
            b'\xe8\x00\x00\x00\x00'      # call
            b'\x85\xc0'                  # test eax, eax
            b'\x74\x03'                  # je +3
            b'\xc9\xc3'                  # leave; ret
        )
        self.analyzer.load_bytes(self.data, 0x400000, "x86")
        self.analyzer.disassemble()

    def test_get_instruction_statistics(self):
        result = self.analyzer.get_instruction_statistics()
        self.assertTrue(result["success"])
        self.assertGreater(result["total_instructions"], 0)
        self.assertIn("group_distribution", result)

    def test_get_cross_references(self):
        result = self.analyzer.get_cross_references()
        self.assertTrue(result["success"])

    def test_find_string_references(self):
        result = self.analyzer.find_string_references()
        self.assertTrue(result["success"])

    def test_get_full_analysis(self):
        result = self.analyzer.get_full_analysis()
        self.assertTrue(result["success"])
        self.assertIn("arch", result)
        self.assertIn("instruction_count", result)


class TestAsmAnalyzerStackFrame(unittest.TestCase):
    """测试栈帧分析"""

    def setUp(self):
        self.analyzer = AsmAnalyzer()
        self.data = (
            b'\x55\x89\xe5\x83\xec\x20'  # push ebp; mov ebp, esp; sub esp, 0x20
            b'\x53\x56\x57'              # push ebx, esi, edi
            b'\xc7\x45\xfc\x01\x00\x00\x00'  # mov [ebp-4], 1
            b'\x5f\x5e\x5b'              # pop edi, esi, ebx
            b'\xc9\xc3'                  # leave; ret
        )
        self.analyzer.load_bytes(self.data, 0x400000, "x86")
        self.analyzer.disassemble()
        self.analyzer.detect_functions()

    def test_analyze_stack_frame(self):
        result = self.analyzer.analyze_stack_frame(0x400000)
        self.assertTrue(result["success"])
        self.assertIn("stack_frame_size", result)

    def test_analyze_stack_frame_nonexistent(self):
        result = self.analyzer.analyze_stack_frame(0x999999)
        self.assertFalse(result["success"])


class TestInstructionDataclass(unittest.TestCase):
    """测试 Instruction 数据类"""

    def test_create_instruction(self):
        inst = Instruction(
            address=0x400000, mnemonic="push", op_str="ebp",
            size=1, bytes=b'\x55', group="data_transfer"
        )
        self.assertEqual(inst.address, 0x400000)
        self.assertEqual(inst.mnemonic, "push")
        self.assertEqual(inst.size, 1)

    def test_create_jump_instruction(self):
        inst = Instruction(
            address=0x400000, mnemonic="jmp", op_str="0x500000",
            size=5, bytes=b'\xe9\x00\x00\x00\x00',
            is_jump=True, target=0x500000
        )
        self.assertTrue(inst.is_jump)
        self.assertFalse(inst.is_conditional)
        self.assertEqual(inst.target, 0x500000)

    def test_create_conditional_jump(self):
        inst = Instruction(
            address=0x400000, mnemonic="je", op_str="0x400010",
            size=2, bytes=b'\x74\x0e',
            is_jump=True, is_conditional=True, target=0x400010
        )
        self.assertTrue(inst.is_jump)
        self.assertTrue(inst.is_conditional)

    def test_create_call_instruction(self):
        inst = Instruction(
            address=0x400000, mnemonic="call", op_str="0x500000",
            size=5, bytes=b'\xe8\x00\x00\x00\x00',
            is_call=True, target=0x500000
        )
        self.assertTrue(inst.is_call)
        self.assertFalse(inst.is_ret)


class TestFunctionDataclass(unittest.TestCase):
    """测试 Function 数据类"""

    def test_create_function(self):
        func = Function(address=0x400000, end_address=0x400050, size=80)
        self.assertEqual(func.address, 0x400000)
        self.assertEqual(func.size, 80)
        self.assertEqual(func.calling_convention, "unknown")

    def test_function_with_blocks(self):
        func = Function(address=0x400000)
        bb = BasicBlock(start_address=0x400000, end_address=0x400010, is_entry=True)
        func.basic_blocks.append(bb)
        self.assertEqual(len(func.basic_blocks), 1)
        self.assertTrue(func.basic_blocks[0].is_entry)


class TestHookTemplateDataclass(unittest.TestCase):
    """测试 HookTemplate 数据类"""

    def test_create_hook_template(self):
        ht = HookTemplate(
            name="test_hook", hook_type="detour",
            original_address=0x400000, hook_address=0x500000,
            machine_code=b'\xe9\x00\x00\x00\x00',
            overwritten_bytes=b'\x55\x89\xe5\x83\xec',
            description="Test hook"
        )
        self.assertEqual(ht.name, "test_hook")
        self.assertEqual(ht.hook_type, "detour")
        self.assertEqual(ht.original_address, 0x400000)


if __name__ == "__main__":
    unittest.main()