"""
脚本虚拟机逆向引擎测试套件
测试 script_vm.py 的所有核心功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import struct
import tempfile
from core.script_vm import (
    ScriptVMEngine, BytecodeParser, ControlFlowAnalyzer,
    PseudoCodeGenerator, VMStateSimulator, InstructionSetInferrer,
    VMType, OpcodeType, OperandType, VMOpcode, VMInstruction,
    VMConfig, VMState, LUA51_OPCODES, PYTHON3_OPCODES,
    quick_detect, quick_disassemble
)


def _make_lua_header(version=0x51):
    """生成 Lua 字节码头"""
    header = b"\x1bLua" + bytes([version])
    header += b"\x00"  # format
    header += b"\x00"  # endianness
    header += b"\x04"  # int size
    header += b"\x04"  # size_t size
    header += b"\x04"  # instruction size
    header += b"\x04"  # lua_Number size
    header += b"\x00"  # integral flag
    return header


def _make_lua_function(instructions: bytes, num_params=0, is_vararg=0, max_stack=8):
    """生成 Lua 函数字节码"""
    data = bytearray()
    # source name (empty)
    data.append(0x00)
    # line defined
    data.extend(struct.pack("<I", 0))
    # last line defined
    data.extend(struct.pack("<I", 0))
    # num upvalues
    data.append(0x00)
    # num params
    data.append(num_params)
    # is_vararg
    data.append(is_vararg)
    # max stack size
    data.append(max_stack)
    # code
    data.extend(struct.pack("<I", len(instructions) // 4))
    data.extend(instructions)
    # constants
    data.extend(struct.pack("<I", 0))
    # functions (nested)
    data.extend(struct.pack("<I", 0))
    # source lines
    data.extend(struct.pack("<I", 0))
    # locals
    data.extend(struct.pack("<I", 0))
    # upvalues
    data.extend(struct.pack("<I", 0))
    return bytes(data)


def _make_lua_instruction(opcode, a=0, b=0, c=0):
    """生成 Lua 指令 (32-bit)"""
    # Lua 指令格式: 6-bit opcode, 8-bit A, 9-bit B, 9-bit C
    ins = opcode | (a << 6) | (b << 14) | (c << 23)
    return struct.pack("<I", ins & 0xFFFFFFFF)


class TestBytecodeParser(unittest.TestCase):
    """字节码解析器测试"""

    def setUp(self):
        self.parser = BytecodeParser()

    def test_load_bytes(self):
        self.parser.load_bytes(b"\x1bLua\x51")
        self.assertEqual(len(self.parser._data), 5)

    def test_load_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".luac") as f:
            f.write(b"\x1bLua\x51")
            tmp_path = f.name

        try:
            result = self.parser.load_file(tmp_path)
            self.assertTrue(result["success"])
        finally:
            os.unlink(tmp_path)

    def test_load_nonexistent_file(self):
        result = self.parser.load_file("/nonexistent/file.luac")
        self.assertFalse(result["success"])

    def test_detect_lua_51(self):
        self.parser.load_bytes(b"\x1bLua\x51")
        result = self.parser.detect_vm_type()
        self.assertTrue(result["success"])
        self.assertEqual(result["vm_type"], "lua_5.1")
        self.assertEqual(result["confidence"], 1.0)

    def test_detect_lua_52(self):
        self.parser.load_bytes(b"\x1bLua\x52")
        result = self.parser.detect_vm_type()
        self.assertEqual(result["vm_type"], "lua_5.2")

    def test_detect_lua_53(self):
        self.parser.load_bytes(b"\x1bLua\x53")
        result = self.parser.detect_vm_type()
        self.assertEqual(result["vm_type"], "lua_5.3")

    def test_detect_lua_54(self):
        self.parser.load_bytes(b"\x1bLua\x54")
        result = self.parser.detect_vm_type()
        self.assertEqual(result["vm_type"], "lua_5.4")

    def test_detect_python_3x(self):
        # Python 3.x magic
        data = struct.pack("<H", 0x0A0D) + b"\x00" * 14
        self.parser.load_bytes(data)
        result = self.parser.detect_vm_type()
        self.assertEqual(result["vm_type"], "python_3.x")
        self.assertEqual(result["confidence"], 0.9)

    def test_detect_python_2x(self):
        data = struct.pack("<H", 0x03F3) + b"\x00" * 14
        self.parser.load_bytes(data)
        result = self.parser.detect_vm_type()
        self.assertEqual(result["vm_type"], "python_2.x")

    def test_detect_unknown(self):
        self.parser.load_bytes(b"\x00\x00\x00\x00\x00\x00\x00\x00")
        result = self.parser.detect_vm_type()
        self.assertTrue(result["success"])
        self.assertIn(result["vm_type"], ["custom", "unknown"])

    def test_detect_short_data(self):
        self.parser.load_bytes(b"\x00")
        result = self.parser.detect_vm_type()
        self.assertFalse(result["success"])

    def test_load_opcode_table_lua51(self):
        result = self.parser.load_opcode_table("lua_5.1")
        self.assertTrue(result["success"])
        self.assertEqual(result["vm_type"], "lua_5.1")
        self.assertGreater(result["opcode_count"], 0)

    def test_load_opcode_table_python3(self):
        result = self.parser.load_opcode_table("python_3.x")
        self.assertTrue(result["success"])
        self.assertEqual(result["vm_type"], "python_3.x")

    def test_load_opcode_table_unknown(self):
        result = self.parser.load_opcode_table("unknown_vm")
        self.assertFalse(result["success"])

    def test_add_custom_opcode(self):
        self.parser.load_opcode_table("lua_5.1")
        result = self.parser.add_custom_opcode(
            99, "CUSTOM_OP", "arithmetic",
            ["register", "immediate"], "Custom operation"
        )
        self.assertTrue(result["success"])

    def test_add_custom_opcode_invalid_type(self):
        self.parser.load_opcode_table("lua_5.1")
        result = self.parser.add_custom_opcode(99, "BAD", "invalid_type")
        self.assertFalse(result["success"])

    def test_add_custom_opcode_invalid_operand(self):
        self.parser.load_opcode_table("lua_5.1")
        result = self.parser.add_custom_opcode(99, "BAD", "arithmetic", ["invalid"])
        self.assertFalse(result["success"])

    def test_get_opcode_table(self):
        self.parser.load_opcode_table("lua_5.1")
        result = self.parser.get_opcode_table()
        self.assertTrue(result["success"])
        self.assertGreater(result["opcode_count"], 0)

    def test_disassemble_no_data(self):
        result = self.parser.disassemble()
        self.assertFalse(result["success"])

    def test_disassemble_no_table(self):
        self.parser.load_bytes(b"\x00" * 100)
        result = self.parser.disassemble()
        self.assertFalse(result["success"])

    def test_disassemble_lua_simple(self):
        # 创建简单的 Lua 函数: return 1, 2
        ins1 = _make_lua_instruction(1, 0, 0, 0)  # LOADK R0 K0
        ins2 = _make_lua_instruction(1, 1, 0, 1)  # LOADK R1 K1
        ins3 = _make_lua_instruction(30, 0, 3, 0)  # RETURN R0 3

        instructions = ins1 + ins2 + ins3
        # 直接使用指令字节码进行反汇编（跳过 Lua 文件头）
        self.parser.load_bytes(instructions)
        self.parser.load_opcode_table("lua_5.1")
        # 使用 4 字节对齐的指令大小
        self.parser._vm_config.opcode_size = 4  # 每条指令 4 字节
        self.parser._vm_config.operand_size = 0  # 操作数嵌入在指令中
        result = self.parser.disassemble()

        self.assertTrue(result["success"])
        self.assertEqual(result["instruction_count"], 3)

    def test_disassemble_count_limit(self):
        ins1 = _make_lua_instruction(1, 0, 0, 0)
        ins2 = _make_lua_instruction(1, 1, 0, 1)
        ins3 = _make_lua_instruction(30, 0, 3, 0)
        instructions = ins1 + ins2 + ins3
        func = _make_lua_function(instructions)
        header = _make_lua_header()

        self.parser.load_bytes(header + func)
        self.parser.load_opcode_table("lua_5.1")
        result = self.parser.disassemble(count=2)

        self.assertTrue(result["success"])
        self.assertEqual(result["instruction_count"], 2)

    def test_get_opcode_statistics(self):
        self.parser.load_opcode_table("lua_5.1")
        # 先反汇编一些数据
        ins1 = _make_lua_instruction(1, 0, 0, 0)  # LOADK
        ins2 = _make_lua_instruction(12, 2, 0, 1)  # ADD
        ins3 = _make_lua_instruction(30, 0, 3, 0)  # RETURN
        instructions = ins1 + ins2 + ins3
        func = _make_lua_function(instructions)
        header = _make_lua_header()
        self.parser.load_bytes(header + func)
        self.parser.disassemble()

        result = self.parser.get_opcode_statistics()
        self.assertTrue(result["success"])
        self.assertGreater(result["total_instructions"], 0)

    def test_get_opcode_statistics_no_disasm(self):
        result = self.parser.get_opcode_statistics()
        self.assertFalse(result["success"])


class TestControlFlowAnalyzer(unittest.TestCase):
    """控制流分析器测试"""

    def setUp(self):
        self.analyzer = ControlFlowAnalyzer()

    def test_build_cfg_empty(self):
        result = self.analyzer.build_cfg()
        self.assertFalse(result["success"])

    def test_build_cfg_simple(self):
        instructions = [
            {"address": 0, "name": "MOVE", "type": "move", "operands": [0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 4, "name": "ADD", "type": "arithmetic", "operands": [2, 0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 8, "name": "RETURN", "type": "return", "operands": [2, 2],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        self.analyzer.load_instructions(instructions)
        result = self.analyzer.build_cfg()
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["block_count"], 1)

    def test_build_cfg_with_jump(self):
        instructions = [
            {"address": 0, "name": "EQ", "type": "compare", "operands": [0, 0, 1],
             "is_jump": False, "is_conditional": True, "size": 4,
             "jump_target": 12, "fallthrough_target": 4},
            {"address": 4, "name": "MOVE", "type": "move", "operands": [2, 0],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 8, "name": "JMP", "type": "branch", "operands": [1],
             "is_jump": True, "is_conditional": False, "size": 4,
             "jump_target": 16},
            {"address": 12, "name": "MOVE", "type": "move", "operands": [2, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 16, "name": "RETURN", "type": "return", "operands": [2, 2],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        self.analyzer.load_instructions(instructions)
        result = self.analyzer.build_cfg()
        self.assertTrue(result["success"])
        self.assertGreater(result["block_count"], 1)

    def test_analyze_registers(self):
        instructions = [
            {"address": 0, "name": "MOVE", "type": "move", "operands": [0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 4, "name": "ADD", "type": "arithmetic", "operands": [2, 0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 8, "name": "RETURN", "type": "return", "operands": [2, 2],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        self.analyzer.load_instructions(instructions)
        result = self.analyzer.analyze_registers()
        self.assertTrue(result["success"])
        self.assertGreater(result["total_registers_used"], 0)

    def test_analyze_registers_empty(self):
        result = self.analyzer.analyze_registers()
        self.assertFalse(result["success"])

    def test_analyze_stack(self):
        instructions = [
            {"address": 0, "name": "LOADK", "type": "load", "operands": [0, 0],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 4, "name": "LOADK", "type": "load", "operands": [1, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 8, "name": "ADD", "type": "arithmetic", "operands": [2, 0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 12, "name": "RETURN", "type": "return", "operands": [2, 2],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        self.analyzer.load_instructions(instructions)
        result = self.analyzer.analyze_stack()
        self.assertTrue(result["success"])

    def test_analyze_stack_empty(self):
        result = self.analyzer.analyze_stack()
        self.assertFalse(result["success"])


class TestPseudoCodeGenerator(unittest.TestCase):
    """伪代码生成器测试"""

    def setUp(self):
        self.generator = PseudoCodeGenerator()

    def test_generate_empty(self):
        result = self.generator.generate()
        self.assertFalse(result["success"])

    def test_generate_simple(self):
        instructions = [
            {"address": 0, "name": "MOVE", "type": "move", "operands": [0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 4, "name": "ADD", "type": "arithmetic", "operands": [2, 0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 8, "name": "RETURN", "type": "return", "operands": [2, 2],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        self.generator.load_instructions(instructions)
        result = self.generator.generate()
        self.assertTrue(result["success"])
        self.assertGreater(result["line_count"], 0)
        self.assertIn("R0 = R1", result["code"])
        self.assertIn("R2 = R0 + R1", result["code"])

    def test_generate_with_jump(self):
        instructions = [
            {"address": 0, "name": "JMP", "type": "branch", "operands": [1],
             "is_jump": True, "is_conditional": False, "size": 4,
             "jump_target": 8},
            {"address": 4, "name": "MOVE", "type": "move", "operands": [0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 8, "name": "RETURN", "type": "return", "operands": [0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        self.generator.load_instructions(instructions)
        result = self.generator.generate()
        self.assertTrue(result["success"])
        self.assertIn("goto", result["code"])

    def test_generate_all_opcodes(self):
        """测试所有已知操作码的翻译"""
        for opcode, vm_op in LUA51_OPCODES.items():
            if vm_op.operands:
                operands = [0] * len(vm_op.operands)
            else:
                operands = []

            inst = {
                "address": opcode * 4,
                "name": vm_op.name,
                "type": vm_op.op_type.value,
                "operands": operands,
                "is_jump": vm_op.is_branch,
                "is_conditional": vm_op.is_conditional,
                "size": 4,
                "jump_target": None,
                "fallthrough_target": None,
            }
            self.generator.load_instructions([inst])
            result = self.generator.generate()
            self.assertTrue(result["success"], f"Failed for {vm_op.name}")


class TestVMStateSimulator(unittest.TestCase):
    """VM 状态模拟器测试"""

    def setUp(self):
        self.simulator = VMStateSimulator()

    def test_simulate_simple(self):
        instructions = [
            {"address": 0, "name": "LOADK", "type": "load", "operands": [0, 10],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 4, "name": "LOADK", "type": "load", "operands": [1, 20],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 8, "name": "ADD", "type": "arithmetic", "operands": [2, 0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 12, "name": "RETURN", "type": "return", "operands": [2, 2],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        self.simulator.load_instructions(instructions)
        result = self.simulator.simulate(max_steps=100)
        self.assertTrue(result["success"])
        self.assertEqual(result["total_steps"], 4)
        self.assertEqual(result["final_registers"].get(2), 30)

    def test_simulate_empty(self):
        result = self.simulator.simulate()
        self.assertTrue(result["success"])
        self.assertEqual(result["total_steps"], 0)

    def test_simulate_move(self):
        instructions = [
            {"address": 0, "name": "MOVE", "type": "move", "operands": [0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 4, "name": "RETURN", "type": "return", "operands": [0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        self.simulator.load_instructions(instructions)
        result = self.simulator.simulate(initial_state={"registers": {"1": 42}})
        self.assertTrue(result["success"])
        self.assertEqual(result["final_registers"].get(0), 42)

    def test_simulate_arithmetic(self):
        instructions = [
            {"address": 0, "name": "LOADK", "type": "load", "operands": [0, 6],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 4, "name": "LOADK", "type": "load", "operands": [1, 7],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 8, "name": "MUL", "type": "arithmetic", "operands": [2, 0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 12, "name": "RETURN", "type": "return", "operands": [2, 2],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        self.simulator.load_instructions(instructions)
        result = self.simulator.simulate()
        self.assertTrue(result["success"])
        self.assertEqual(result["final_registers"].get(2), 42)

    def test_simulate_conditional(self):
        instructions = [
            {"address": 0, "name": "LOADK", "type": "load", "operands": [0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 4, "name": "LOADK", "type": "load", "operands": [1, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 8, "name": "EQ", "type": "compare", "operands": [1, 0, 1],
             "is_jump": False, "is_conditional": True, "size": 4,
             "jump_target": 16, "fallthrough_target": 12},
            {"address": 12, "name": "JMP", "type": "branch", "operands": [1],
             "is_jump": True, "is_conditional": False, "size": 4,
             "jump_target": 20},
            {"address": 16, "name": "LOADK", "type": "load", "operands": [2, 100],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 20, "name": "RETURN", "type": "return", "operands": [2, 2],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        self.simulator.load_instructions(instructions)
        result = self.simulator.simulate()
        self.assertTrue(result["success"])

    def test_simulate_python_style(self):
        instructions = [
            {"address": 0, "name": "LOAD_CONST", "type": "load", "operands": [10],
             "is_jump": False, "is_conditional": False, "size": 2},
            {"address": 2, "name": "LOAD_CONST", "type": "load", "operands": [20],
             "is_jump": False, "is_conditional": False, "size": 2},
            {"address": 4, "name": "BINARY_ADD", "type": "arithmetic", "operands": [],
             "is_jump": False, "is_conditional": False, "size": 2},
            {"address": 6, "name": "STORE_FAST", "type": "store", "operands": [0],
             "is_jump": False, "is_conditional": False, "size": 2},
            {"address": 8, "name": "RETURN_VALUE", "type": "return", "operands": [],
             "is_jump": False, "is_conditional": False, "size": 2},
        ]
        self.simulator.load_instructions(instructions)
        result = self.simulator.simulate()
        self.assertTrue(result["success"])


class TestInstructionSetInferrer(unittest.TestCase):
    """指令集推断器测试"""

    def setUp(self):
        self.inferrer = InstructionSetInferrer()

    def test_infer_empty(self):
        result = self.inferrer.infer()
        self.assertFalse(result["success"])

    def test_infer_simple(self):
        # 创建一些模拟字节码
        data = bytearray()
        for i in range(100):
            opcode = i % 10
            operand = (i * 7) % 256
            data.append(opcode)
            data.extend(struct.pack("<i", operand))

        self.inferrer.load_bytes(bytes(data))
        result = self.inferrer.infer(opcode_size=1, operand_size=4)
        self.assertTrue(result["success"])
        self.assertIn("inferred_opcodes", result)

    def test_infer_with_control_flow(self):
        data = bytearray()
        for i in range(50):
            if i == 25:
                # 模拟跳转
                data.append(22)  # JMP opcode
                data.extend(struct.pack("<i", 10))
            else:
                data.append(1)  # MOVE-like
                data.extend(struct.pack("<i", i))

        self.inferrer.load_bytes(bytes(data))
        result = self.inferrer.infer()
        self.assertTrue(result["success"])
        self.assertIn("control_flow_ops", result)


class TestScriptVMEngine(unittest.TestCase):
    """脚本虚拟机逆向引擎主测试"""

    def setUp(self):
        self.engine = ScriptVMEngine()

    def test_detect_vm_type(self):
        result = self.engine.detect_vm_type(b"\x1bLua\x51")
        self.assertTrue(result["success"])
        self.assertEqual(result["vm_type"], "lua_5.1")

    def test_detect_vm_type_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".luac") as f:
            f.write(b"\x1bLua\x51")
            tmp_path = f.name

        try:
            result = self.engine.detect_vm_type_file(tmp_path)
            self.assertTrue(result["success"])
            self.assertEqual(result["vm_type"], "lua_5.1")
        finally:
            os.unlink(tmp_path)

    def test_detect_vm_type_nonexistent(self):
        result = self.engine.detect_vm_type_file("/nonexistent/file")
        self.assertFalse(result["success"])

    def test_load_opcode_table(self):
        result = self.engine.load_opcode_table("lua_5.1")
        self.assertTrue(result["success"])

    def test_add_custom_opcode(self):
        self.engine.load_opcode_table("lua_5.1")
        result = self.engine.add_custom_opcode(99, "TEST", "arithmetic", ["register"])
        self.assertTrue(result["success"])

    def test_get_opcode_table(self):
        self.engine.load_opcode_table("lua_5.1")
        result = self.engine.get_opcode_table()
        self.assertTrue(result["success"])

    def test_disassemble(self):
        ins1 = _make_lua_instruction(1, 0, 0, 0)  # LOADK
        ins2 = _make_lua_instruction(1, 1, 0, 1)  # LOADK
        ins3 = _make_lua_instruction(12, 2, 0, 1)  # ADD
        ins4 = _make_lua_instruction(30, 2, 3, 0)  # RETURN

        instructions = ins1 + ins2 + ins3 + ins4
        func = _make_lua_function(instructions)
        header = _make_lua_header()

        result = self.engine.disassemble(header + func, "lua_5.1")
        self.assertTrue(result["success"])
        self.assertGreater(result["instruction_count"], 0)

    def test_disassemble_file(self):
        ins1 = _make_lua_instruction(1, 0, 0, 0)
        ins2 = _make_lua_instruction(30, 1, 2, 0)
        instructions = ins1 + ins2
        func = _make_lua_function(instructions)
        header = _make_lua_header()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".luac") as f:
            f.write(header + func)
            tmp_path = f.name

        try:
            result = self.engine.disassemble_file(tmp_path, "lua_5.1")
            self.assertTrue(result["success"])
            self.assertGreater(result["instruction_count"], 0)
        finally:
            os.unlink(tmp_path)

    def test_build_cfg(self):
        instructions = [
            {"address": 0, "name": "MOVE", "type": "move", "operands": [0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 4, "name": "RETURN", "type": "return", "operands": [0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        result = self.engine.build_cfg(instructions)
        self.assertTrue(result["success"])

    def test_analyze_registers(self):
        instructions = [
            {"address": 0, "name": "MOVE", "type": "move", "operands": [0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 4, "name": "ADD", "type": "arithmetic", "operands": [2, 0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        result = self.engine.analyze_registers(instructions)
        self.assertTrue(result["success"])

    def test_analyze_stack(self):
        instructions = [
            {"address": 0, "name": "LOADK", "type": "load", "operands": [0, 0],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        result = self.engine.analyze_stack(instructions)
        self.assertTrue(result["success"])

    def test_generate_pseudo_code(self):
        instructions = [
            {"address": 0, "name": "MOVE", "type": "move", "operands": [0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 4, "name": "RETURN", "type": "return", "operands": [0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        result = self.engine.generate_pseudo_code(instructions)
        self.assertTrue(result["success"])
        self.assertIn("R0 = R1", result["code"])

    def test_simulate(self):
        instructions = [
            {"address": 0, "name": "LOADK", "type": "load", "operands": [0, 5],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 4, "name": "LOADK", "type": "load", "operands": [1, 3],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 8, "name": "ADD", "type": "arithmetic", "operands": [2, 0, 1],
             "is_jump": False, "is_conditional": False, "size": 4},
            {"address": 12, "name": "RETURN", "type": "return", "operands": [2, 2],
             "is_jump": False, "is_conditional": False, "size": 4},
        ]
        result = self.engine.simulate(instructions)
        self.assertTrue(result["success"])
        self.assertEqual(result["final_registers"].get(2), 8)

    def test_infer_instruction_set(self):
        data = bytearray()
        for i in range(50):
            opcode = i % 5
            operand = i * 3
            data.append(opcode)
            data.extend(struct.pack("<i", operand))

        result = self.engine.infer_instruction_set(bytes(data))
        self.assertTrue(result["success"])

    def test_analyze_file(self):
        ins1 = _make_lua_instruction(1, 0, 0, 0)
        ins2 = _make_lua_instruction(12, 2, 0, 1)
        ins3 = _make_lua_instruction(30, 2, 3, 0)
        instructions = ins1 + ins2 + ins3
        func = _make_lua_function(instructions)
        header = _make_lua_header()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".luac") as f:
            f.write(header + func)
            tmp_path = f.name

        try:
            result = self.engine.analyze(tmp_path, "lua_5.1")
            self.assertTrue(result["success"])
            self.assertIn("pseudo_code", result)
            self.assertIn("cfg", result)
        finally:
            os.unlink(tmp_path)

    def test_analyze_nonexistent(self):
        result = self.engine.analyze("/nonexistent/file")
        self.assertFalse(result["success"])


class TestQuickFunctions(unittest.TestCase):
    """快捷函数测试"""

    def test_quick_detect(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".luac") as f:
            f.write(b"\x1bLua\x51")
            tmp_path = f.name

        try:
            result = quick_detect(tmp_path)
            self.assertTrue(result["success"])
            self.assertEqual(result["vm_type"], "lua_5.1")
        finally:
            os.unlink(tmp_path)

    def test_quick_disassemble(self):
        ins1 = _make_lua_instruction(1, 0, 0, 0)
        ins2 = _make_lua_instruction(30, 1, 2, 0)
        instructions = ins1 + ins2
        func = _make_lua_function(instructions)
        header = _make_lua_header()

        result = quick_disassemble(header + func, "lua_5.1")
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()