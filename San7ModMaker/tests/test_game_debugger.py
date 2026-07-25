"""
游戏进程调试器测试套件
测试 game_debugger.py 的所有核心功能
"""
import unittest
import os
import sys
import struct

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.game_debugger import (
    GameDebugger, Breakpoint, RegisterSet, StackFrame, Watchpoint,
    DebugEvent, DebugState, StepType
)


class TestGameDebuggerInit(unittest.TestCase):
    """测试调试器初始化"""

    def test_init_default(self):
        debugger = GameDebugger()
        self.assertIsNotNone(debugger)
        self.assertFalse(debugger.is_attached())
        self.assertEqual(debugger._pid, 0)

    def test_get_state_idle(self):
        debugger = GameDebugger()
        state = debugger.get_state()
        self.assertTrue(state["success"])
        self.assertEqual(state["state"], "IDLE")

    def test_get_process_info_not_attached(self):
        debugger = GameDebugger()
        result = debugger.get_process_info()
        self.assertFalse(result["success"])


class TestGameDebuggerAttach(unittest.TestCase):
    """测试进程附加/分离"""

    def test_attach_nonexistent(self):
        debugger = GameDebugger()
        result = debugger.attach(99999999)
        self.assertFalse(result["success"])

    def test_detach_not_attached(self):
        debugger = GameDebugger()
        result = debugger.detach()
        self.assertFalse(result["success"])

    def test_is_attached_false(self):
        debugger = GameDebugger()
        self.assertFalse(debugger.is_attached())


class TestGameDebuggerBreakpoints(unittest.TestCase):
    """测试断点管理"""

    def setUp(self):
        self.debugger = GameDebugger()

    def test_set_breakpoint_not_attached(self):
        result = self.debugger.set_breakpoint(0x400000)
        self.assertFalse(result["success"])

    def test_list_breakpoints_empty(self):
        result = self.debugger.list_breakpoints()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    def test_remove_breakpoint_nonexistent(self):
        result = self.debugger.remove_breakpoint(999)
        self.assertFalse(result["success"])

    def test_enable_breakpoint_nonexistent(self):
        result = self.debugger.enable_breakpoint(999)
        self.assertFalse(result["success"])

    def test_disable_breakpoint_nonexistent(self):
        result = self.debugger.disable_breakpoint(999)
        self.assertFalse(result["success"])

    def test_set_hardware_breakpoint_not_attached(self):
        result = self.debugger.set_hardware_breakpoint(0x400000, 4, "execute")
        self.assertFalse(result["success"])

    def test_set_conditional_breakpoint_not_attached(self):
        result = self.debugger.set_conditional_breakpoint(0x400000, "eax == 1")
        self.assertFalse(result["success"])


class TestGameDebuggerRegisters(unittest.TestCase):
    """测试寄存器操作"""

    def setUp(self):
        self.debugger = GameDebugger()

    def test_get_registers_not_attached(self):
        result = self.debugger.get_registers()
        self.assertFalse(result["success"])

    def test_set_register_not_attached(self):
        result = self.debugger.set_register("eax", 0x1234)
        self.assertFalse(result["success"])


class TestGameDebuggerMemory(unittest.TestCase):
    """测试内存读写"""

    def setUp(self):
        self.debugger = GameDebugger()

    def test_read_memory_not_attached(self):
        result = self.debugger.read_memory(0x400000, 16)
        self.assertFalse(result["success"])

    def test_write_memory_not_attached(self):
        result = self.debugger.write_memory(0x400000, b"\x90\x90\x90")
        self.assertFalse(result["success"])

    def test_read_int32_not_attached(self):
        result = self.debugger.read_int32(0x400000)
        self.assertFalse(result["success"])

    def test_read_uint32_not_attached(self):
        result = self.debugger.read_uint32(0x400000)
        self.assertFalse(result["success"])

    def test_read_float_not_attached(self):
        result = self.debugger.read_float(0x400000)
        self.assertFalse(result["success"])

    def test_read_bytes_not_attached(self):
        result = self.debugger.read_bytes(0x400000, 16)
        self.assertFalse(result["success"])

    def test_read_string_not_attached(self):
        result = self.debugger.read_string(0x400000)
        self.assertFalse(result["success"])


class TestGameDebuggerExecution(unittest.TestCase):
    """测试执行控制"""

    def setUp(self):
        self.debugger = GameDebugger()

    def test_continue_not_attached(self):
        result = self.debugger.continue_execution()
        self.assertFalse(result["success"])

    def test_step_into_not_attached(self):
        result = self.debugger.step_into()
        self.assertFalse(result["success"])

    def test_step_over_not_attached(self):
        result = self.debugger.step_over()
        self.assertFalse(result["success"])

    def test_step_out_not_attached(self):
        result = self.debugger.step_out()
        self.assertFalse(result["success"])

    def test_pause_not_attached(self):
        result = self.debugger.pause()
        self.assertFalse(result["success"])


class TestGameDebuggerCallStack(unittest.TestCase):
    """测试调用栈"""

    def setUp(self):
        self.debugger = GameDebugger()

    def test_get_call_stack_not_attached(self):
        result = self.debugger.get_call_stack()
        self.assertFalse(result["success"])

    def test_get_modules_not_attached(self):
        result = self.debugger.get_modules()
        self.assertFalse(result["success"])

    def test_find_module_not_attached(self):
        result = self.debugger.find_module("test")
        self.assertFalse(result["success"])


class TestGameDebuggerWatchpoints(unittest.TestCase):
    """测试监视点"""

    def setUp(self):
        self.debugger = GameDebugger()

    def test_set_watchpoint_not_attached(self):
        result = self.debugger.set_watchpoint(0x400000, 4, "write")
        self.assertFalse(result["success"])

    def test_remove_watchpoint_nonexistent(self):
        result = self.debugger.remove_watchpoint(999)
        self.assertFalse(result["success"])

    def test_check_watchpoints_not_attached(self):
        result = self.debugger.check_watchpoints()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    def test_list_watchpoints_empty(self):
        result = self.debugger.list_watchpoints()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)


class TestGameDebuggerCallbacks(unittest.TestCase):
    """测试事件回调"""

    def setUp(self):
        self.debugger = GameDebugger()

    def test_on_event_valid(self):
        def dummy_callback(event):
            pass
        result = self.debugger.on_event("breakpoint", dummy_callback)
        self.assertTrue(result["success"])

    def test_on_event_invalid(self):
        def dummy_callback(event):
            pass
        result = self.debugger.on_event("invalid_event", dummy_callback)
        self.assertFalse(result["success"])

    def test_clear_callbacks_all(self):
        result = self.debugger.clear_callbacks()
        self.assertTrue(result["success"])

    def test_clear_callbacks_specific(self):
        result = self.debugger.clear_callbacks("breakpoint")
        self.assertTrue(result["success"])

    def test_clear_callbacks_invalid(self):
        result = self.debugger.clear_callbacks("invalid_event")
        self.assertFalse(result["success"])


class TestGameDebuggerDisassembly(unittest.TestCase):
    """测试反汇编"""

    def setUp(self):
        self.debugger = GameDebugger()

    def test_get_disassembly_not_attached(self):
        result = self.debugger.get_disassembly(0x400000, 10)
        self.assertFalse(result["success"])


class TestGameDebuggerStatus(unittest.TestCase):
    """测试状态查询"""

    def setUp(self):
        self.debugger = GameDebugger()

    def test_get_state(self):
        state = self.debugger.get_state()
        self.assertTrue(state["success"])
        self.assertEqual(state["pid"], 0)
        self.assertFalse(state["attached"])

    def test_get_full_status(self):
        status = self.debugger.get_full_status()
        self.assertTrue(status["success"])
        self.assertIn("state", status)
        self.assertIn("registers", status)
        self.assertIn("breakpoints", status)
        self.assertIn("watchpoints", status)
        self.assertIn("call_stack", status)
        self.assertIn("modules", status)


class TestDataClasses(unittest.TestCase):
    """测试数据类"""

    def test_breakpoint_create(self):
        bp = Breakpoint(id=1, address=0x400000, original_byte=0x55)
        self.assertEqual(bp.id, 1)
        self.assertEqual(bp.address, 0x400000)
        self.assertTrue(bp.enabled)
        self.assertEqual(bp.type, "software")

    def test_register_set_create(self):
        regs = RegisterSet(eax=0x100, ebx=0x200, eip=0x400000)
        self.assertEqual(regs.eax, 0x100)
        self.assertEqual(regs.eip, 0x400000)

    def test_stack_frame_create(self):
        sf = StackFrame(
            index=0, address=0x400000, return_address=0x500000,
            frame_pointer=0x1000, function_name="test_func"
        )
        self.assertEqual(sf.index, 0)
        self.assertEqual(sf.function_name, "test_func")

    def test_watchpoint_create(self):
        wp = Watchpoint(id=1, address=0x400000, size=4, type="write")
        self.assertEqual(wp.id, 1)
        self.assertEqual(wp.size, 4)
        self.assertTrue(wp.enabled)

    def test_watchpoint_with_old_value(self):
        wp = Watchpoint(id=2, address=0x400000, size=4, type="read",
                        old_value=b'\x01\x00\x00\x00')
        self.assertEqual(wp.old_value, b'\x01\x00\x00\x00')

    def test_debug_event_create(self):
        event = DebugEvent(
            type="breakpoint", pid=1234, tid=5678,
            address=0x400000, breakpoint_id=1
        )
        self.assertEqual(event.type, "breakpoint")
        self.assertEqual(event.pid, 1234)

    def test_debug_state_enum(self):
        self.assertEqual(DebugState.IDLE.name, "IDLE")
        self.assertEqual(DebugState.ATTACHED.name, "ATTACHED")
        self.assertEqual(DebugState.RUNNING.name, "RUNNING")

    def test_step_type_enum(self):
        self.assertEqual(StepType.INTO.value, "step_into")
        self.assertEqual(StepType.OVER.value, "step_over")
        self.assertEqual(StepType.OUT.value, "step_out")


class TestGameDebuggerConstants(unittest.TestCase):
    """测试常量"""

    def test_ptrace_constants(self):
        self.assertEqual(GameDebugger.PTRACE_ATTACH, 16)
        self.assertEqual(GameDebugger.PTRACE_DETACH, 17)
        self.assertEqual(GameDebugger.PTRACE_CONT, 7)
        self.assertEqual(GameDebugger.PTRACE_SINGLESTEP, 9)

    def test_signal_constants(self):
        self.assertEqual(GameDebugger.SIGTRAP, 5)
        self.assertEqual(GameDebugger.SIGSTOP, 19)
        self.assertEqual(GameDebugger.SIGSEGV, 11)

    def test_int3_opcode(self):
        self.assertEqual(GameDebugger.INT3_OPCODE, 0xCC)


if __name__ == "__main__":
    unittest.main()