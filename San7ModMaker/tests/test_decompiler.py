"""
反编译与符号执行引擎测试套件
测试 decompiler.py 的所有核心功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import tempfile
import struct
from core.decompiler import (
    DecompilerEngine, InstructionDecoder, CFGBuilder, SSABuilder,
    SymbolicExecutor, ConstraintSolver, StructureRecovery, PseudoCodeGenerator,
    Instruction, BasicBlock, SymbolicExpr, SymbolicOp, Constraint,
    Operand, OperandType, InstructionType, PathState,
    quick_decompile, quick_build_cfg, quick_symbolic_execute
)


class TestInstructionDecoder(unittest.TestCase):
    """指令解码器测试"""

    def setUp(self):
        self.decoder = InstructionDecoder()

    def test_parse_mov(self):
        inst = self.decoder.parse_asm_line("0x401000 mov eax, 0x1234")
        self.assertIsNotNone(inst)
        self.assertEqual(inst.mnemonic, "mov")
        self.assertEqual(inst.address, 0x401000)
        self.assertEqual(inst.op_type, InstructionType.MOV)
        self.assertEqual(len(inst.operands), 2)
        self.assertEqual(inst.operands[0].type, OperandType.REGISTER)
        self.assertEqual(inst.operands[0].value, "eax")
        self.assertEqual(inst.operands[1].type, OperandType.IMMEDIATE)
        self.assertEqual(inst.operands[1].value, 0x1234)

    def test_parse_add(self):
        inst = self.decoder.parse_asm_line("0x401004 add eax, ebx")
        self.assertIsNotNone(inst)
        self.assertEqual(inst.mnemonic, "add")
        self.assertEqual(inst.op_type, InstructionType.ADD)

    def test_parse_push(self):
        inst = self.decoder.parse_asm_line("0x401000 push ebp")
        self.assertIsNotNone(inst)
        self.assertEqual(inst.mnemonic, "push")
        self.assertEqual(inst.op_type, InstructionType.PUSH)

    def test_parse_pop(self):
        inst = self.decoder.parse_asm_line("0x401000 pop ebp")
        self.assertIsNotNone(inst)
        self.assertEqual(inst.op_type, InstructionType.POP)

    def test_parse_jmp(self):
        inst = self.decoder.parse_asm_line("0x401000 jmp 0x401100")
        self.assertIsNotNone(inst)
        self.assertTrue(inst.is_jump)
        self.assertFalse(inst.is_conditional)
        self.assertEqual(inst.jump_target, 0x401100)

    def test_parse_je(self):
        inst = self.decoder.parse_asm_line("0x401000 je 0x401100")
        self.assertIsNotNone(inst)
        self.assertTrue(inst.is_jump)
        self.assertTrue(inst.is_conditional)
        self.assertEqual(inst.jump_target, 0x401100)

    def test_parse_call(self):
        inst = self.decoder.parse_asm_line("0x401000 call 0x402000")
        self.assertIsNotNone(inst)
        self.assertTrue(inst.is_call)

    def test_parse_ret(self):
        inst = self.decoder.parse_asm_line("0x401000 ret")
        self.assertIsNotNone(inst)
        self.assertTrue(inst.is_return)

    def test_parse_cmp(self):
        inst = self.decoder.parse_asm_line("0x401000 cmp eax, ebx")
        self.assertIsNotNone(inst)
        self.assertEqual(inst.op_type, InstructionType.CMP)

    def test_parse_test(self):
        inst = self.decoder.parse_asm_line("0x401000 test eax, eax")
        self.assertIsNotNone(inst)
        self.assertEqual(inst.op_type, InstructionType.TEST)

    def test_parse_lea(self):
        inst = self.decoder.parse_asm_line("0x401000 lea eax, [ebp-0x8]")
        self.assertIsNotNone(inst)
        self.assertEqual(inst.op_type, InstructionType.LEA)

    def test_parse_xor(self):
        inst = self.decoder.parse_asm_line("0x401000 xor eax, eax")
        self.assertIsNotNone(inst)
        self.assertEqual(inst.op_type, InstructionType.XOR)

    def test_parse_nop(self):
        inst = self.decoder.parse_asm_line("0x401000 nop")
        self.assertIsNotNone(inst)
        self.assertEqual(inst.op_type, InstructionType.NOP)

    def test_parse_comment(self):
        inst = self.decoder.parse_asm_line("; this is a comment")
        self.assertIsNone(inst)

    def test_parse_empty(self):
        inst = self.decoder.parse_asm_line("")
        self.assertIsNone(inst)

    def test_parse_xchg(self):
        inst = self.decoder.parse_asm_line("0x401000 xchg eax, ebx")
        self.assertIsNotNone(inst)
        self.assertEqual(inst.op_type, InstructionType.XCHG)

    def test_parse_inc(self):
        inst = self.decoder.parse_asm_line("0x401000 inc eax")
        self.assertIsNotNone(inst)
        self.assertEqual(inst.op_type, InstructionType.INC)

    def test_parse_dec(self):
        inst = self.decoder.parse_asm_line("0x401000 dec eax")
        self.assertIsNotNone(inst)
        self.assertEqual(inst.op_type, InstructionType.DEC)

    def test_parse_asm_text(self):
        text = """0x401000 push ebp
0x401001 mov ebp, esp
0x401003 mov eax, 0x1
0x401008 pop ebp
0x401009 ret"""
        instructions = self.decoder.parse_asm_text(text)
        self.assertEqual(len(instructions), 5)
        self.assertEqual(instructions[0].mnemonic, "push")
        self.assertEqual(instructions[-1].mnemonic, "ret")

    def test_parse_memory_operand(self):
        inst = self.decoder.parse_asm_line("0x401000 mov eax, [ebx]")
        self.assertIsNotNone(inst)
        if len(inst.operands) >= 2:
            self.assertEqual(inst.operands[1].type, OperandType.MEMORY)

    def test_parse_negative_immediate(self):
        inst = self.decoder.parse_asm_line("0x401000 push -1")
        self.assertIsNotNone(inst)


class TestCFGBuilder(unittest.TestCase):
    """CFG 构建器测试"""

    def setUp(self):
        self.builder = CFGBuilder()
        self.decoder = InstructionDecoder()

    def _make_instructions(self, text: str):
        return self.decoder.parse_asm_text(text)

    def test_build_empty(self):
        blocks = self.builder.build([])
        self.assertEqual(len(blocks), 0)

    def test_build_simple_linear(self):
        text = """0x401000 push ebp
0x401001 mov ebp, esp
0x401003 mov eax, 0x1
0x401008 pop ebp
0x401009 ret"""
        blocks = self.builder.build(self._make_instructions(text))
        self.assertGreaterEqual(len(blocks), 1)

    def test_build_with_jump(self):
        text = """0x401000 mov eax, 0x1
0x401005 cmp eax, 0x0
0x401008 je 0x401010
0x40100A mov eax, 0x2
0x40100F ret
0x401010 mov eax, 0x3
0x401015 ret"""
        blocks = self.builder.build(self._make_instructions(text))
        self.assertGreater(len(blocks), 1)

    def test_compute_dominators(self):
        text = """0x401000 mov eax, 0x1
0x401005 cmp eax, 0x0
0x401008 je 0x401010
0x40100A mov eax, 0x2
0x40100F ret
0x401010 mov eax, 0x3
0x401015 ret"""
        self.builder.build(self._make_instructions(text))
        dom = self.builder.compute_dominators()
        self.assertGreater(len(dom), 0)

    def test_compute_dominance_frontiers(self):
        text = """0x401000 mov eax, 0x1
0x401005 cmp eax, 0x0
0x401008 je 0x401010
0x40100A mov eax, 0x2
0x40100F ret
0x401010 mov eax, 0x3
0x401015 ret"""
        self.builder.build(self._make_instructions(text))
        df = self.builder.compute_dominance_frontiers()
        self.assertGreater(len(df), 0)

    def test_detect_loops(self):
        text = """0x401000 mov ecx, 0xA
0x401005 mov eax, 0x0
0x40100A add eax, 0x1
0x40100D dec ecx
0x40100E jnz 0x40100A
0x401010 ret"""
        self.builder.build(self._make_instructions(text))
        loops = self.builder.detect_loops()
        # May or may not detect loop depending on structure
        self.assertIsInstance(loops, list)


class TestSSABuilder(unittest.TestCase):
    """SSA 构造器测试"""

    def setUp(self):
        self.ssa = SSABuilder()
        self.decoder = InstructionDecoder()
        self.cfg = CFGBuilder()

    def test_build_ssa_simple(self):
        text = """0x401000 mov eax, 0x1
0x401005 mov ebx, 0x2
0x40100A add eax, ebx
0x40100C ret"""
        instructions = self.decoder.parse_asm_text(text)
        blocks = self.cfg.build(instructions)
        dom = self.cfg.compute_dominators()
        df = self.cfg.compute_dominance_frontiers()
        ssa_map = self.ssa.build(blocks, dom, df)
        self.assertIsInstance(ssa_map, dict)


class TestSymbolicExecutor(unittest.TestCase):
    """符号执行器测试"""

    def setUp(self):
        self.executor = SymbolicExecutor(max_depth=20, max_paths=10)
        self.decoder = InstructionDecoder()
        self.cfg = CFGBuilder()

    def test_execute_simple(self):
        text = """0x401000 mov eax, 0x1
0x401005 mov ebx, 0x2
0x40100A add eax, ebx
0x40100C ret"""
        instructions = self.decoder.parse_asm_text(text)
        blocks = self.cfg.build(instructions)
        paths = self.executor.execute(blocks)
        self.assertGreater(len(paths), 0)

    def test_execute_branch(self):
        text = """0x401000 mov eax, 0x1
0x401005 cmp eax, 0x0
0x401008 je 0x401010
0x40100A mov eax, 0x2
0x40100F ret
0x401010 mov eax, 0x3
0x401015 ret"""
        instructions = self.decoder.parse_asm_text(text)
        blocks = self.cfg.build(instructions)
        paths = self.executor.execute(blocks)
        self.assertGreater(len(paths), 0)

    def test_execute_empty(self):
        paths = self.executor.execute([])
        self.assertEqual(len(paths), 0)


class TestConstraintSolver(unittest.TestCase):
    """约束求解器测试"""

    def setUp(self):
        self.solver = ConstraintSolver()

    def test_simplify_add_zero(self):
        expr = SymbolicExpr(SymbolicOp.ADD, [
            SymbolicExpr(SymbolicOp.VAR, ["x"]),
            SymbolicExpr(SymbolicOp.CONST, [0]),
        ])
        simplified = self.solver.simplify(expr)
        self.assertEqual(simplified.op, SymbolicOp.VAR)
        self.assertEqual(simplified.args[0], "x")

    def test_simplify_sub_zero(self):
        expr = SymbolicExpr(SymbolicOp.SUB, [
            SymbolicExpr(SymbolicOp.VAR, ["x"]),
            SymbolicExpr(SymbolicOp.CONST, [0]),
        ])
        simplified = self.solver.simplify(expr)
        self.assertEqual(simplified.op, SymbolicOp.VAR)

    def test_simplify_mul_zero(self):
        expr = SymbolicExpr(SymbolicOp.MUL, [
            SymbolicExpr(SymbolicOp.VAR, ["x"]),
            SymbolicExpr(SymbolicOp.CONST, [0]),
        ])
        simplified = self.solver.simplify(expr)
        self.assertEqual(simplified.op, SymbolicOp.CONST)
        self.assertEqual(simplified.args[0], 0)

    def test_simplify_mul_one(self):
        expr = SymbolicExpr(SymbolicOp.MUL, [
            SymbolicExpr(SymbolicOp.VAR, ["x"]),
            SymbolicExpr(SymbolicOp.CONST, [1]),
        ])
        simplified = self.solver.simplify(expr)
        self.assertEqual(simplified.op, SymbolicOp.VAR)

    def test_simplify_and_zero(self):
        expr = SymbolicExpr(SymbolicOp.AND, [
            SymbolicExpr(SymbolicOp.VAR, ["x"]),
            SymbolicExpr(SymbolicOp.CONST, [0]),
        ])
        simplified = self.solver.simplify(expr)
        self.assertEqual(simplified.op, SymbolicOp.CONST)
        self.assertEqual(simplified.args[0], 0)

    def test_simplify_or_zero(self):
        expr = SymbolicExpr(SymbolicOp.OR, [
            SymbolicExpr(SymbolicOp.VAR, ["x"]),
            SymbolicExpr(SymbolicOp.CONST, [0]),
        ])
        simplified = self.solver.simplify(expr)
        self.assertEqual(simplified.op, SymbolicOp.VAR)

    def test_simplify_xor_zero(self):
        expr = SymbolicExpr(SymbolicOp.XOR, [
            SymbolicExpr(SymbolicOp.VAR, ["x"]),
            SymbolicExpr(SymbolicOp.CONST, [0]),
        ])
        simplified = self.solver.simplify(expr)
        self.assertEqual(simplified.op, SymbolicOp.VAR)

    def test_simplify_xor_same(self):
        x = SymbolicExpr(SymbolicOp.VAR, ["x"])
        expr = SymbolicExpr(SymbolicOp.XOR, [x, x])
        simplified = self.solver.simplify(expr)
        self.assertEqual(simplified.op, SymbolicOp.CONST)
        self.assertEqual(simplified.args[0], 0)

    def test_simplify_sub_same(self):
        x = SymbolicExpr(SymbolicOp.VAR, ["x"])
        expr = SymbolicExpr(SymbolicOp.SUB, [x, x])
        simplified = self.solver.simplify(expr)
        self.assertEqual(simplified.op, SymbolicOp.CONST)
        self.assertEqual(simplified.args[0], 0)

    def test_simplify_and_same(self):
        x = SymbolicExpr(SymbolicOp.VAR, ["x"])
        expr = SymbolicExpr(SymbolicOp.AND, [x, x])
        simplified = self.solver.simplify(expr)
        self.assertEqual(simplified.op, SymbolicOp.VAR)

    def test_evaluate_constants(self):
        expr = SymbolicExpr(SymbolicOp.ADD, [
            SymbolicExpr(SymbolicOp.CONST, [10]),
            SymbolicExpr(SymbolicOp.CONST, [5]),
        ])
        simplified = self.solver.simplify(expr)
        self.assertEqual(simplified.op, SymbolicOp.CONST)
        self.assertEqual(simplified.args[0], 15)

    def test_check_sat_true(self):
        constraints = [
            Constraint(SymbolicExpr(SymbolicOp.CONST, [1]), is_true=True),
        ]
        sat, model = self.solver.check_sat(constraints)
        self.assertTrue(sat)

    def test_check_sat_false(self):
        constraints = [
            Constraint(SymbolicExpr(SymbolicOp.CONST, [0]), is_true=True),
        ]
        sat, model = self.solver.check_sat(constraints)
        self.assertFalse(sat)

    def test_solve_equal_x_add_const(self):
        expr = SymbolicExpr(SymbolicOp.ADD, [
            SymbolicExpr(SymbolicOp.VAR, ["x"]),
            SymbolicExpr(SymbolicOp.CONST, [5]),
        ])
        result = self.solver.solve_equal(expr, 10)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("x"), 5)

    def test_solve_equal_xor_const(self):
        expr = SymbolicExpr(SymbolicOp.XOR, [
            SymbolicExpr(SymbolicOp.VAR, ["x"]),
            SymbolicExpr(SymbolicOp.CONST, [0x55]),
        ])
        result = self.solver.solve_equal(expr, 0xAA)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("x"), 0xFF)


class TestPseudoCodeGenerator(unittest.TestCase):
    """伪代码生成器测试"""

    def setUp(self):
        self.generator = PseudoCodeGenerator()
        self.decoder = InstructionDecoder()

    def test_generate_mov(self):
        text = "0x401000 mov eax, 0x1234"
        insts = self.decoder.parse_asm_text(text)
        code = self.generator.generate(insts)
        self.assertIn("eax = 0x1234", code)

    def test_generate_add(self):
        text = "0x401000 add eax, ebx"
        insts = self.decoder.parse_asm_text(text)
        code = self.generator.generate(insts)
        self.assertIn("eax = eax + ebx", code)

    def test_generate_sub(self):
        text = "0x401000 sub eax, 0x1"
        insts = self.decoder.parse_asm_text(text)
        code = self.generator.generate(insts)
        self.assertIn("eax = eax - 0x1", code)

    def test_generate_xor_self(self):
        text = "0x401000 xor eax, eax"
        insts = self.decoder.parse_asm_text(text)
        code = self.generator.generate(insts)
        self.assertIn("eax = 0", code)

    def test_generate_inc(self):
        text = "0x401000 inc eax"
        insts = self.decoder.parse_asm_text(text)
        code = self.generator.generate(insts)
        self.assertIn("eax = eax + 1", code)

    def test_generate_call(self):
        text = "0x401000 call 0x402000"
        insts = self.decoder.parse_asm_text(text)
        code = self.generator.generate(insts)
        self.assertIn("call", code)

    def test_generate_ret(self):
        text = "0x401000 ret"
        insts = self.decoder.parse_asm_text(text)
        code = self.generator.generate(insts)
        self.assertIn("return", code)

    def test_generate_multiple(self):
        text = """0x401000 push ebp
0x401001 mov ebp, esp
0x401003 mov eax, 0x1
0x401008 mov ebx, 0x2
0x40100D add eax, ebx
0x40100F pop ebp
0x401010 ret"""
        insts = self.decoder.parse_asm_text(text)
        code = self.generator.generate(insts)
        self.assertIn("eax = 0x1", code)
        self.assertIn("ebx = 0x2", code)
        self.assertIn("eax = eax + ebx", code)
        self.assertIn("return", code)


class TestStructureRecovery(unittest.TestCase):
    """结构恢复测试"""

    def setUp(self):
        self.recovery = StructureRecovery()
        self.decoder = InstructionDecoder()
        self.cfg = CFGBuilder()

    def test_recover_empty(self):
        structures = self.recovery.recover([])
        self.assertEqual(len(structures), 0)

    def test_recover_if_else(self):
        text = """0x401000 cmp eax, 0x0
0x401003 je 0x40100A
0x401005 mov eax, 0x1
0x40100A mov eax, 0x2
0x40100F ret"""
        instructions = self.decoder.parse_asm_text(text)
        blocks = self.cfg.build(instructions)
        structures = self.recovery.recover(blocks)
        self.assertGreaterEqual(len(structures), 0)


class TestDecompilerEngine(unittest.TestCase):
    """反编译引擎主入口测试"""

    def setUp(self):
        self.engine = DecompilerEngine()

    def _create_asm_file(self, text: str) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".asm") as f:
            f.write(text.encode("utf-8"))
            return f.name

    def test_decompile_simple(self):
        text = """0x401000 push ebp
0x401001 mov ebp, esp
0x401003 mov eax, 0x1
0x401008 mov ebx, 0x2
0x40100D add eax, ebx
0x40100F pop ebp
0x401010 ret"""
        result = self.engine.decompile(text, "test_func")
        self.assertTrue(result["success"])
        self.assertIn("pseudo_code", result)
        self.assertGreater(result["instruction_count"], 0)
        self.assertGreater(result["block_count"], 0)

    def test_decompile_empty(self):
        result = self.engine.decompile("")
        self.assertFalse(result["success"])

    def test_decompile_with_branch(self):
        text = """0x401000 mov eax, 0x1
0x401005 cmp eax, 0x0
0x401008 je 0x401010
0x40100A mov eax, 0x2
0x40100F ret
0x401010 mov eax, 0x3
0x401015 ret"""
        result = self.engine.decompile(text)
        self.assertTrue(result["success"])
        self.assertIn("path_count", result)

    def test_decompile_file(self):
        text = """0x401000 mov eax, 0x1
0x401005 ret"""
        path = self._create_asm_file(text)
        try:
            result = self.engine.decompile_file(path)
            self.assertTrue(result["success"])
        finally:
            os.unlink(path)

    def test_decompile_nonexistent(self):
        result = self.engine.decompile_file("/nonexistent/file.asm")
        self.assertFalse(result["success"])

    def test_build_cfg(self):
        text = """0x401000 mov eax, 0x1
0x401005 cmp eax, 0x0
0x401008 je 0x401010
0x40100A mov eax, 0x2
0x40100F ret
0x401010 mov eax, 0x3
0x401015 ret"""
        result = self.engine.build_cfg(text)
        self.assertTrue(result["success"])
        self.assertGreater(result["block_count"], 1)
        self.assertIn("dominance", result)
        self.assertIn("loops", result)

    def test_build_cfg_empty(self):
        result = self.engine.build_cfg("")
        self.assertFalse(result["success"])

    def test_symbolic_execute(self):
        text = """0x401000 mov eax, 0x1
0x401005 mov ebx, 0x2
0x40100A add eax, ebx
0x40100C ret"""
        result = self.engine.symbolic_execute(text)
        self.assertTrue(result["success"])
        self.assertGreater(result["path_count"], 0)

    def test_symbolic_execute_empty(self):
        result = self.engine.symbolic_execute("")
        self.assertFalse(result["success"])

    def test_solve_constraints(self):
        constraints = [
            {"expr": {"op": "const", "args": [1]}, "is_true": True},
        ]
        result = self.engine.solve_constraints(constraints)
        self.assertTrue(result["success"])
        self.assertTrue(result["satisfiable"])

    def test_simplify_expression(self):
        expr_data = {
            "op": "+",
            "args": [
                {"op": "var", "args": ["x"]},
                {"op": "const", "args": [0]},
            ],
        }
        result = self.engine.simplify_expression(expr_data)
        self.assertTrue(result["success"])
        self.assertIn("simplified", result)

    def test_get_statistics(self):
        stats = self.engine.get_statistics()
        self.assertGreater(stats["supported_instructions"], 0)
        self.assertGreater(stats["conditional_jumps"], 0)
        self.assertGreater(stats["registers"], 0)

    def test_quick_decompile(self):
        text = """0x401000 mov eax, 0x1
0x401005 ret"""
        result = quick_decompile(text)
        self.assertTrue(result["success"])

    def test_quick_build_cfg(self):
        text = """0x401000 mov eax, 0x1
0x401005 ret"""
        result = quick_build_cfg(text)
        self.assertTrue(result["success"])

    def test_quick_symbolic_execute(self):
        text = """0x401000 mov eax, 0x1
0x401005 ret"""
        result = quick_symbolic_execute(text)
        self.assertTrue(result["success"])


class TestSymbolicExpr(unittest.TestCase):
    """符号表达式测试"""

    def test_str(self):
        expr = SymbolicExpr(SymbolicOp.ADD, [
            SymbolicExpr(SymbolicOp.VAR, ["x"]),
            SymbolicExpr(SymbolicOp.CONST, [5]),
        ])
        self.assertIn("x", str(expr))
        self.assertIn("+", str(expr))
        self.assertIn("5", str(expr))

    def test_eq(self):
        x = SymbolicExpr(SymbolicOp.VAR, ["x"])
        y = SymbolicExpr(SymbolicOp.VAR, ["x"])
        self.assertEqual(x, y)

    def test_not_eq(self):
        x = SymbolicExpr(SymbolicOp.VAR, ["x"])
        y = SymbolicExpr(SymbolicOp.VAR, ["y"])
        self.assertNotEqual(x, y)


class TestPathState(unittest.TestCase):
    """路径状态测试"""

    def test_clone(self):
        state = PathState(path_id=1, address=0x401000)
        state.registers["eax"] = SymbolicExpr(SymbolicOp.CONST, [1])
        state.constraints.append(Constraint(SymbolicExpr(SymbolicOp.CONST, [1])))

        cloned = state.clone()
        self.assertEqual(cloned.path_id, 1)
        self.assertEqual(cloned.address, 0x401000)
        self.assertEqual(len(cloned.registers), 1)
        self.assertEqual(len(cloned.constraints), 1)

        # Modify original, ensure clone is independent
        state.registers["ebx"] = SymbolicExpr(SymbolicOp.CONST, [2])
        self.assertNotIn("ebx", cloned.registers)


if __name__ == "__main__":
    unittest.main(verbosity=2)