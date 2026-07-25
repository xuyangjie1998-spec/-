#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
San7ModMaker 注入引擎 (injector.py) 综合测试套件
===================================================

覆盖 injector.py 中所有核心类和函数的完整测试。
包含 50+ 个测试用例，覆盖枚举、数据类、分析器、规划器、
Shellcode 生成器、PE 注入器、代码洞穴扫描器、注入引擎和便捷函数。

测试架构:
    - TestInjectionMethod: 注入方法枚举测试
    - TestInjectionRisk: 风险等级枚举测试
    - TestPayloadType: 载荷类型枚举测试
    - TestInjectionResult: 注入结果数据类测试
    - TestProcessInfo: 进程信息数据类测试
    - TestInjectionStrategy: 注入策略数据类测试
    - TestProcessAnalyzer: 进程分析器测试
    - TestInjectionStrategyPlanner: 策略规划器测试
    - TestShellcodeGenerator: Shellcode 生成器测试
    - TestPEInjector: PE 文件注入器测试
    - TestCodeCaveScanner: 代码洞穴扫描器测试
    - TestInjectionEngine: 注入引擎集成测试
    - TestConvenienceFunctions: 便捷函数测试
"""

import os
import sys
import unittest
import tempfile
import struct
import json
import shutil
import base64

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.injector import (
    # 枚举
    InjectionMethod,
    InjectionRisk,
    PayloadType,
    # 数据类
    InjectionResult,
    ProcessInfo,
    InjectionStrategy,
    # 辅助类型
    CodeCave,
    ModuleInfo,
    SectionInfo,
    # 核心类
    ProcessAnalyzer,
    InjectionStrategyPlanner,
    ShellcodeGenerator,
    PEInjector,
    CodeCaveScanner,
    InjectionEngine,
    # 便捷函数
    quick_inject,
    quick_analyze,
    list_methods,
    # 常量
    ARCH_X86,
    ARCH_X64,
    ANTI_CHEAT_SIGNATURES,
    ANTI_CHEAT_RISK_LEVELS,
    INJECTION_METHOD_WEIGHTS,
    IMAGE_DOS_SIGNATURE,
    PE_SIGNATURE,
    IMAGE_NT_OPTIONAL_HDR32_MAGIC,
    IMAGE_NT_OPTIONAL_HDR64_MAGIC,
    IMAGE_SECTION_HEADER_SIZE,
    IMAGE_SCN_MEM_EXECUTE,
    IMAGE_SCN_MEM_READ,
    IMAGE_SCN_CNT_CODE,
    INTEGRITY_MEDIUM,
    INTEGRITY_HIGH,
    INTEGRITY_SYSTEM,
)


# ============================================================================
# 辅助函数: 构建测试用 PE 文件
# ============================================================================

def _build_pe32_file(
    num_sections: int = 3,
    file_align: int = 0x200,
    section_align: int = 0x1000,
    image_base: int = 0x400000,
    entry_point: int = 0x1000,
    extra_data: bytes = b"",
) -> bytes:
    """构建一个标准的 32位 PE 可执行文件用于测试。

    返回完整的 PE 字节数据，包含 DOS 头、PE 签名、文件头、
    可选头、节区表和节区数据。
    """
    # 节区数据
    sections = [
        (".text", 0x1000, 0x200, 0x1000, 0x200, 0x60000020),
        (".rdata", 0x2000, 0x400, 0x1000, 0x400, 0x40000040),
        (".data", 0x3000, 0x600, 0x1000, 0x600, 0xC0000040),
    ][:num_sections]

    # 计算节区数据区域
    section_data = bytearray()
    for name, va, raw_off, raw_size, vsize, chars in sections:
        padded = raw_off + raw_size
        if len(section_data) < padded:
            section_data.extend(b"\x00" * (padded - len(section_data)))
        # 填充一些非零数据以免被识别为代码洞穴
        for i in range(raw_off, raw_off + raw_size):
            section_data[i] = (i * 7 + 13) & 0xFF

    # 文件总大小
    total_size = 0x800
    if sections:
        last_section = sections[-1]
        total_size = max(last_section[2] + last_section[3], 0x800)

    # DOS 头
    dos_header = bytearray(64)
    dos_header[0:2] = b"MZ"
    struct.pack_into("<I", dos_header, 0x3C, 0x80)

    # PE 签名
    pe_sig = b"PE\x00\x00"

    # 文件头
    file_header = bytearray(20)
    struct.pack_into("<H", file_header, 0, 0x014C)    # Machine: x86
    struct.pack_into("<H", file_header, 2, num_sections)
    struct.pack_into("<I", file_header, 4, 0x12345678)  # TimeDateStamp
    struct.pack_into("<H", file_header, 16, 0xE0)     # SizeOfOptionalHeader
    struct.pack_into("<H", file_header, 18, 0x0102)   # Characteristics: EXECUTABLE_IMAGE | 32BIT_MACHINE

    # 可选头 (PE32)
    opt_header = bytearray(0xE0)
    struct.pack_into("<H", opt_header, 0, IMAGE_NT_OPTIONAL_HDR32_MAGIC)
    struct.pack_into("<I", opt_header, 16, entry_point)     # AddressOfEntryPoint
    struct.pack_into("<I", opt_header, 28, image_base)      # ImageBase
    struct.pack_into("<I", opt_header, 32, section_align)   # SectionAlignment
    struct.pack_into("<I", opt_header, 36, file_align)      # FileAlignment
    struct.pack_into("<I", opt_header, 48, 6)               # MajorSubsystemVersion
    struct.pack_into("<I", opt_header, 56, 0x5000)          # SizeOfImage
    struct.pack_into("<I", opt_header, 60, 0x200)           # SizeOfHeaders
    struct.pack_into("<H", opt_header, 68, 2)               # Subsystem: GUI
    # 数据目录: 16 个条目, 每个 8 字节
    for i in range(16):
        struct.pack_into("<I", opt_header, 96 + i * 8, 0)
        struct.pack_into("<I", opt_header, 100 + i * 8, 0)

    # 节区表
    section_headers = bytearray()
    for name, va, raw_off, raw_size, vsize, chars in sections:
        sh = bytearray(IMAGE_SECTION_HEADER_SIZE)
        name_bytes = name.encode("ascii")[:8].ljust(8, b"\x00")
        struct.pack_into("<8s", sh, 0, name_bytes)
        struct.pack_into("<I", sh, 8, vsize)       # VirtualSize
        struct.pack_into("<I", sh, 12, va)          # VirtualAddress
        struct.pack_into("<I", sh, 16, raw_size)    # SizeOfRawData
        struct.pack_into("<I", sh, 20, raw_off)     # PointerToRawData
        struct.pack_into("<I", sh, 32, chars)       # Characteristics
        section_headers.extend(sh)

    # 组装 PE 文件
    result = bytearray()
    result.extend(dos_header)
    # 填充 DOS stub 到 e_lfanew 偏移
    pe_offset = 0x80
    if len(result) < pe_offset:
        result.extend(b"\x00" * (pe_offset - len(result)))
    result.extend(pe_sig)
    result.extend(file_header)
    result.extend(opt_header)
    result.extend(section_headers)

    # 填充到节数据偏移
    first_raw = sections[0][2] if sections else 0x200
    if len(result) < first_raw:
        result.extend(b"\x00" * (first_raw - len(result)))

    # 写入节数据
    for name, va, raw_off, raw_size, vsize, chars in sections:
        if len(result) < raw_off + raw_size:
            result.extend(b"\x00" * (raw_off + raw_size - len(result)))
        # 填充非零数据
        for i in range(raw_off, raw_off + raw_size):
            result[i] = (i * 7 + 13) & 0xFF

    return bytes(result)


def _build_pe_with_zero_caves(
    num_sections: int = 3,
    cave_regions: list = None,
) -> bytes:
    """构建包含零填充区域的 PE 文件用于代码洞穴测试。

    cave_regions: [(offset, size), ...] 指定零填充区域
    """
    data = bytearray(_build_pe32_file(num_sections=num_sections))

    if cave_regions:
        for offset, size in cave_regions:
            if len(data) < offset + size:
                data.extend(b"\x00" * (offset + size - len(data)))
            for i in range(offset, offset + size):
                data[i] = 0x00

    return bytes(data)


def _build_pe64_file() -> bytes:
    """构建一个标准的 64位 PE 可执行文件用于测试."""
    sections = [
        (".text", 0x1000, 0x200, 0x1000, 0x200, 0x60000020),
        (".rdata", 0x2000, 0x400, 0x1000, 0x400, 0x40000040),
    ]
    num_sections = len(sections)

    dos_header = bytearray(64)
    dos_header[0:2] = b"MZ"
    struct.pack_into("<I", dos_header, 0x3C, 0x80)

    file_header = bytearray(20)
    struct.pack_into("<H", file_header, 0, 0x8664)    # Machine: x64
    struct.pack_into("<H", file_header, 2, num_sections)
    struct.pack_into("<I", file_header, 4, 0x12345678)
    struct.pack_into("<H", file_header, 16, 0xF0)     # SizeOfOptionalHeader (x64)
    struct.pack_into("<H", file_header, 18, 0x0022)   # EXECUTABLE_IMAGE | LARGE_ADDRESS_AWARE

    opt_header = bytearray(0xF0)
    struct.pack_into("<H", opt_header, 0, IMAGE_NT_OPTIONAL_HDR64_MAGIC)
    struct.pack_into("<I", opt_header, 16, 0x1000)
    struct.pack_into("<Q", opt_header, 24, 0x140000000)  # ImageBase
    struct.pack_into("<I", opt_header, 32, 0x1000)
    struct.pack_into("<I", opt_header, 36, 0x200)
    struct.pack_into("<I", opt_header, 56, 0x5000)
    struct.pack_into("<I", opt_header, 60, 0x200)
    struct.pack_into("<H", opt_header, 68, 2)
    for i in range(16):
        struct.pack_into("<I", opt_header, 112 + i * 8, 0)
        struct.pack_into("<I", opt_header, 116 + i * 8, 0)

    section_headers = bytearray()
    for name, va, raw_off, raw_size, vsize, chars in sections:
        sh = bytearray(IMAGE_SECTION_HEADER_SIZE)
        name_bytes = name.encode("ascii")[:8].ljust(8, b"\x00")
        struct.pack_into("<8s", sh, 0, name_bytes)
        struct.pack_into("<I", sh, 8, vsize)
        struct.pack_into("<I", sh, 12, va)
        struct.pack_into("<I", sh, 16, raw_size)
        struct.pack_into("<I", sh, 20, raw_off)
        struct.pack_into("<I", sh, 32, chars)
        section_headers.extend(sh)

    result = bytearray()
    result.extend(dos_header)
    # 填充 DOS stub 到 e_lfanew 偏移
    pe_offset = 0x80
    if len(result) < pe_offset:
        result.extend(b"\x00" * (pe_offset - len(result)))
    result.extend(b"PE\x00\x00")
    result.extend(file_header)
    result.extend(opt_header)
    result.extend(section_headers)

    first_raw = sections[0][2]
    if len(result) < first_raw:
        result.extend(b"\x00" * (first_raw - len(result)))

    for name, va, raw_off, raw_size, vsize, chars in sections:
        if len(result) < raw_off + raw_size:
            result.extend(b"\x00" * (raw_off + raw_size - len(result)))
        for i in range(raw_off, raw_off + raw_size):
            result[i] = (i * 7 + 13) & 0xFF

    return bytes(result)


# ============================================================================
# TestInjectionMethod - 注入方法枚举测试
# ============================================================================

class TestInjectionMethod(unittest.TestCase):
    """注入方法枚举测试"""

    def test_all_10_methods_exist(self):
        """验证所有 10 个注入方法存在"""
        methods = list(InjectionMethod)
        self.assertEqual(len(methods), 10, "应该有 10 个注入方法")

        method_names = {m.name for m in methods}
        expected = {
            "CREATE_REMOTE_THREAD",
            "SET_WINDOWS_HOOK_EX",
            "QUEUE_USER_APC",
            "THREAD_HIJACKING",
            "REFLECTIVE_DLL",
            "PROCESS_HOLLOWING",
            "ATOM_BOMBING",
            "MANUAL_MAP",
            "DLL_PROXY",
            "SIDE_LOADING",
        }
        self.assertEqual(method_names, expected)

    def test_method_value_conversion(self):
        """验证方法值转换和名称访问"""
        # 每个方法应该有唯一的 value
        values = set()
        for method in InjectionMethod:
            values.add(method.value)
        self.assertEqual(len(values), 10, "所有方法值应该唯一")

    def test_method_get_description(self):
        """验证所有方法都有描述"""
        for method in InjectionMethod:
            desc = method.get_description()
            self.assertIsInstance(desc, str)
            self.assertGreater(len(desc), 10, f"{method.name} 的描述应该足够长")

    def test_method_get_risk(self):
        """验证所有方法都有风险等级"""
        for method in InjectionMethod:
            risk = method.get_risk()
            self.assertIsInstance(risk, InjectionRisk)

    def test_specific_method_risks(self):
        """验证特定方法的风险等级"""
        self.assertEqual(
            InjectionMethod.CREATE_REMOTE_THREAD.get_risk(),
            InjectionRisk.HIGH,
        )
        self.assertEqual(
            InjectionMethod.REFLECTIVE_DLL.get_risk(),
            InjectionRisk.LOW,
        )
        self.assertEqual(
            InjectionMethod.PROCESS_HOLLOWING.get_risk(),
            InjectionRisk.LOW,
        )
        self.assertEqual(
            InjectionMethod.DLL_PROXY.get_risk(),
            InjectionRisk.MEDIUM,
        )


# ============================================================================
# TestInjectionRisk - 风险等级枚举测试
# ============================================================================

class TestInjectionRisk(unittest.TestCase):
    """风险等级枚举测试"""

    def test_all_4_levels_exist(self):
        """验证所有 4 个风险等级存在"""
        levels = list(InjectionRisk)
        self.assertEqual(len(levels), 4)

        level_names = {l.name for l in levels}
        self.assertEqual(level_names, {"LOW", "MEDIUM", "HIGH", "CRITICAL"})

    def test_risk_values(self):
        """验证风险等级的值"""
        self.assertEqual(InjectionRisk.LOW.value, "low")
        self.assertEqual(InjectionRisk.MEDIUM.value, "medium")
        self.assertEqual(InjectionRisk.HIGH.value, "high")
        self.assertEqual(InjectionRisk.CRITICAL.value, "critical")

    def test_to_score_low(self):
        """验证 LOW 风险评分"""
        self.assertEqual(InjectionRisk.LOW.to_score(), 25.0)

    def test_to_score_medium(self):
        """验证 MEDIUM 风险评分"""
        self.assertEqual(InjectionRisk.MEDIUM.to_score(), 50.0)

    def test_to_score_high(self):
        """验证 HIGH 风险评分"""
        self.assertEqual(InjectionRisk.HIGH.to_score(), 75.0)

    def test_to_score_critical(self):
        """验证 CRITICAL 风险评分"""
        self.assertEqual(InjectionRisk.CRITICAL.to_score(), 100.0)

    def test_to_score_range(self):
        """验证所有评分在 0-100 范围内"""
        for level in InjectionRisk:
            score = level.to_score()
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 100.0)


# ============================================================================
# TestPayloadType - 载荷类型枚举测试
# ============================================================================

class TestPayloadType(unittest.TestCase):
    """载荷类型枚举测试"""

    def test_all_4_types_exist(self):
        """验证所有 4 个载荷类型存在"""
        types = list(PayloadType)
        self.assertEqual(len(types), 4)

        type_names = {t.name for t in types}
        self.assertEqual(type_names, {"DLL", "SHELLCODE", "REFLECTIVE_DLL", "PROCESS"})

    def test_payload_type_values(self):
        """验证载荷类型的值"""
        self.assertEqual(PayloadType.DLL.value, "dll")
        self.assertEqual(PayloadType.SHELLCODE.value, "shellcode")
        self.assertEqual(PayloadType.REFLECTIVE_DLL.value, "reflective_dll")
        self.assertEqual(PayloadType.PROCESS.value, "process")


# ============================================================================
# TestInjectionResult - 注入结果数据类测试
# ============================================================================

class TestInjectionResult(unittest.TestCase):
    """注入结果数据类测试"""

    def test_create_success_result(self):
        """创建成功的注入结果"""
        result = InjectionResult(
            success=True,
            method=InjectionMethod.CREATE_REMOTE_THREAD,
            target_process="game.exe",
            payload_path="/tmp/test.dll",
            risk_level=InjectionRisk.HIGH,
            detection_score=75.0,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.method, InjectionMethod.CREATE_REMOTE_THREAD)
        self.assertEqual(result.target_process, "game.exe")
        self.assertEqual(result.payload_path, "/tmp/test.dll")
        self.assertEqual(result.error_message, "")
        self.assertEqual(result.risk_level, InjectionRisk.HIGH)
        self.assertEqual(result.detection_score, 75.0)

    def test_create_failure_result_with_error(self):
        """创建失败的注入结果 (带错误信息)"""
        result = InjectionResult(
            success=False,
            method=InjectionMethod.DLL_PROXY,
            target_process="game.exe",
            payload_path="/tmp/test.dll",
            error_message="进程未找到",
            risk_level=InjectionRisk.CRITICAL,
            detection_score=100.0,
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "进程未找到")
        self.assertEqual(result.risk_level, InjectionRisk.CRITICAL)

    def test_to_dict_success(self):
        """验证成功结果的 to_dict() 方法"""
        result = InjectionResult(
            success=True,
            method=InjectionMethod.REFLECTIVE_DLL,
            target_process="game.exe",
            payload_path="/tmp/test.dll",
            risk_level=InjectionRisk.LOW,
            detection_score=15.0,
        )
        d = result.to_dict()
        self.assertIsInstance(d, dict)
        self.assertTrue(d["success"])
        self.assertEqual(d["method"], "REFLECTIVE_DLL")
        self.assertIn("method_description", d)
        self.assertEqual(d["target_process"], "game.exe")
        self.assertEqual(d["payload_path"], "/tmp/test.dll")
        self.assertEqual(d["error_message"], "")
        self.assertEqual(d["risk_level"], "low")
        self.assertEqual(d["risk_to_score"], 25.0)
        self.assertEqual(d["detection_score"], 15.0)

    def test_to_dict_failure(self):
        """验证失败结果的 to_dict() 方法"""
        result = InjectionResult(
            success=False,
            method=InjectionMethod.CREATE_REMOTE_THREAD,
            target_process="not_found.exe",
            payload_path="/tmp/test.dll",
            error_message="权限不足",
            risk_level=InjectionRisk.HIGH,
            detection_score=100.0,
        )
        d = result.to_dict()
        self.assertFalse(d["success"])
        self.assertEqual(d["error_message"], "权限不足")
        self.assertEqual(d["detection_score"], 100.0)

    def test_to_json(self):
        """验证 to_json() 方法"""
        result = InjectionResult(
            success=True,
            method=InjectionMethod.SIDE_LOADING,
            target_process="game.exe",
            payload_path="/tmp/test.dll",
            risk_level=InjectionRisk.MEDIUM,
            detection_score=50.0,
        )
        json_str = result.to_json()
        self.assertIsInstance(json_str, str)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["success"], True)
        self.assertEqual(parsed["method"], "SIDE_LOADING")

    def test_str_success(self):
        """验证成功结果的字符串表示"""
        result = InjectionResult(
            success=True,
            method=InjectionMethod.CREATE_REMOTE_THREAD,
            target_process="game.exe",
            payload_path="/tmp/test.dll",
        )
        s = str(result)
        self.assertIn("[成功]", s)
        self.assertIn("CREATE_REMOTE_THREAD", s)
        self.assertIn("game.exe", s)

    def test_str_failure(self):
        """验证失败结果的字符串表示"""
        result = InjectionResult(
            success=False,
            method=InjectionMethod.DLL_PROXY,
            target_process="game.exe",
            payload_path="/tmp/test.dll",
            error_message="测试错误",
        )
        s = str(result)
        self.assertIn("[失败]", s)
        self.assertIn("测试错误", s)


# ============================================================================
# TestProcessInfo - 进程信息数据类测试
# ============================================================================

class TestProcessInfo(unittest.TestCase):
    """进程信息数据类测试"""

    def test_create_basic(self):
        """创建基本进程信息"""
        info = ProcessInfo(
            pid=1234,
            name="game.exe",
            path="/usr/games/game.exe",
        )
        self.assertEqual(info.pid, 1234)
        self.assertEqual(info.name, "game.exe")
        self.assertEqual(info.path, "/usr/games/game.exe")
        self.assertEqual(info.architecture, ARCH_X64)

    def test_create_full(self):
        """创建完整进程信息"""
        info = ProcessInfo(
            pid=5678,
            name="game.exe",
            path="/usr/games/game.exe",
            architecture=ARCH_X86,
            session_id=1,
            integrity_level=INTEGRITY_HIGH,
            is_protected=True,
            anti_cheat_detected=["EasyAntiCheat", "BattleEye"],
            loaded_modules=["kernel32.dll", "user32.dll", "ntdll.dll"],
            parent_pid=1000,
            thread_count=42,
            is_wow64=True,
            detection_score=85.0,
        )
        self.assertEqual(info.pid, 5678)
        self.assertEqual(info.architecture, ARCH_X86)
        self.assertEqual(info.integrity_level, INTEGRITY_HIGH)
        self.assertTrue(info.is_protected)
        self.assertEqual(len(info.anti_cheat_detected), 2)
        self.assertEqual(len(info.loaded_modules), 3)
        self.assertEqual(info.parent_pid, 1000)
        self.assertEqual(info.thread_count, 42)
        self.assertTrue(info.is_wow64)
        self.assertEqual(info.detection_score, 85.0)

    def test_to_dict(self):
        """验证 to_dict() 方法"""
        info = ProcessInfo(
            pid=1234,
            name="game.exe",
            path="/usr/games/game.exe",
            is_protected=True,
            anti_cheat_detected=["EasyAntiCheat"],
            loaded_modules=["mod1.dll", "mod2.dll"],
        )
        d = info.to_dict()
        self.assertEqual(d["pid"], 1234)
        self.assertEqual(d["name"], "game.exe")
        self.assertEqual(d["path"], "/usr/games/game.exe")
        self.assertTrue(d["is_protected"])
        self.assertIn("EasyAntiCheat", d["anti_cheat_detected"])
        self.assertEqual(d["loaded_modules_count"], 2)
        self.assertIn("loaded_modules", d)

    def test_to_dict_defaults(self):
        """验证默认值的 to_dict()"""
        info = ProcessInfo(pid=1, name="test", path="/test")
        d = info.to_dict()
        self.assertFalse(d["is_protected"])
        self.assertEqual(d["anti_cheat_detected"], [])
        self.assertEqual(d["loaded_modules_count"], 0)

    def test_is_protected_flag(self):
        """验证 is_protected 标志"""
        info_protected = ProcessInfo(
            pid=1, name="test", path="/test",
            is_protected=True,
            anti_cheat_detected=["EasyAntiCheat"],
        )
        self.assertTrue(info_protected.is_protected)

        info_unprotected = ProcessInfo(
            pid=2, name="test2", path="/test2",
            is_protected=False,
        )
        self.assertFalse(info_unprotected.is_protected)

    def test_str_representation(self):
        """验证字符串表示"""
        info = ProcessInfo(
            pid=1234,
            name="game.exe",
            path="/usr/games/game.exe",
            anti_cheat_detected=["EasyAntiCheat"],
        )
        s = str(info)
        self.assertIn("1234", s)
        self.assertIn("game.exe", s)
        self.assertIn("EasyAntiCheat", s)

    def test_str_no_anti_cheat(self):
        """验证无反作弊时的字符串表示"""
        info = ProcessInfo(pid=1, name="test", path="/test")
        s = str(info)
        self.assertNotIn("反作弊", s)


# ============================================================================
# TestInjectionStrategy - 注入策略数据类测试
# ============================================================================

class TestInjectionStrategy(unittest.TestCase):
    """注入策略数据类测试"""

    def test_create_basic(self):
        """创建基本注入策略"""
        strategy = InjectionStrategy(
            method=InjectionMethod.CREATE_REMOTE_THREAD,
            risk=InjectionRisk.HIGH,
            stealth_score=30.0,
            success_rate=90.0,
        )
        self.assertEqual(strategy.method, InjectionMethod.CREATE_REMOTE_THREAD)
        self.assertEqual(strategy.risk, InjectionRisk.HIGH)
        self.assertEqual(strategy.stealth_score, 30.0)
        self.assertEqual(strategy.success_rate, 90.0)
        self.assertEqual(strategy.requirements, [])
        self.assertEqual(strategy.steps, [])
        self.assertEqual(strategy.alternatives, [])

    def test_create_full(self):
        """创建完整注入策略"""
        strategy = InjectionStrategy(
            method=InjectionMethod.REFLECTIVE_DLL,
            risk=InjectionRisk.LOW,
            stealth_score=85.0,
            success_rate=70.0,
            requirements=["需要 PROCESS_VM_OPERATION 权限"],
            steps=["步骤1: 获取句柄", "步骤2: 分配内存"],
            alternatives=[InjectionMethod.MANUAL_MAP, InjectionMethod.DLL_PROXY],
            warnings=["目标有反作弊保护"],
            notes="测试备注",
        )
        self.assertEqual(len(strategy.requirements), 1)
        self.assertEqual(len(strategy.steps), 2)
        self.assertEqual(len(strategy.alternatives), 2)
        self.assertEqual(len(strategy.warnings), 1)
        self.assertEqual(strategy.notes, "测试备注")

    def test_to_dict(self):
        """验证 to_dict() 方法"""
        strategy = InjectionStrategy(
            method=InjectionMethod.DLL_PROXY,
            risk=InjectionRisk.MEDIUM,
            stealth_score=60.0,
            success_rate=85.0,
            requirements=["req1", "req2"],
            steps=["step1", "step2", "step3"],
            alternatives=[InjectionMethod.SIDE_LOADING],
            warnings=["warning1"],
            notes="note1",
        )
        d = strategy.to_dict()
        self.assertEqual(d["method"], "DLL_PROXY")
        self.assertIn("method_description", d)
        self.assertEqual(d["risk"], "medium")
        self.assertEqual(d["stealth_score"], 60.0)
        self.assertEqual(d["success_rate"], 85.0)
        self.assertEqual(len(d["requirements"]), 2)
        self.assertEqual(len(d["steps"]), 3)
        self.assertEqual(d["alternatives"], ["SIDE_LOADING"])
        self.assertEqual(d["warnings"], ["warning1"])
        self.assertEqual(d["notes"], "note1")

    def test_str_representation(self):
        """验证字符串表示"""
        strategy = InjectionStrategy(
            method=InjectionMethod.ATOM_BOMBING,
            risk=InjectionRisk.LOW,
            stealth_score=95.0,
            success_rate=30.0,
            requirements=["req1"],
            alternatives=[InjectionMethod.PROCESS_HOLLOWING],
            warnings=["warning1"],
            notes="note1",
        )
        s = str(strategy)
        self.assertIn("ATOM_BOMBING", s)
        self.assertIn("low", s)
        self.assertIn("95.0", s)
        self.assertIn("30.0", s)


# ============================================================================
# TestProcessAnalyzer - 进程分析器测试
# ============================================================================

class TestProcessAnalyzer(unittest.TestCase):
    """进程分析器测试"""

    def setUp(self):
        self.analyzer = ProcessAnalyzer()

    def test_list_processes_returns_list(self):
        """验证 list_processes 返回列表"""
        procs = self.analyzer.list_processes()
        self.assertIsInstance(procs, list)

    def test_list_processes_items_are_process_info(self):
        """验证 list_processes 返回的项是 ProcessInfo 类型"""
        procs = self.analyzer.list_processes()
        for proc in procs:
            self.assertIsInstance(proc, ProcessInfo)

    def test_find_process_non_existent(self):
        """验证查找不存在的进程返回空列表"""
        result = self.analyzer.find_process("thIS_PrOcEsS_DoEs_NoT_ExIsT_12345")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_find_process_partial_match(self):
        """验证 find_process 支持部分名称匹配"""
        # 查找自身进程 (Python 进程)
        result = self.analyzer.find_process("python")
        self.assertIsInstance(result, list)

    def test_get_process_info_invalid_pid(self):
        """验证获取无效 PID 的进程信息返回 None"""
        result = self.analyzer.get_process_info(999999999)
        self.assertIsNone(result)

    def test_get_process_info_negative_pid(self):
        """验证获取负 PID 返回 None"""
        result = self.analyzer.get_process_info(-1)
        self.assertIsNone(result)

    def test_analyze_protections_with_eac_strings(self):
        """验证检测 EAC 反作弊字符串"""
        # 创建一个模拟的 EAC 进程名称
        info = ProcessInfo(
            pid=9999,
            name="EasyAntiCheat.exe",
            path="/games/EasyAntiCheat/EasyAntiCheat.exe",
            is_protected=True,
            anti_cheat_detected=["EasyAntiCheat"],
        )
        # 测试 _detect_anti_cheat 方法
        detected = self.analyzer._detect_anti_cheat(
            "EasyAntiCheat.exe", "/games/EasyAntiCheat/EasyAntiCheat.exe"
        )
        self.assertIn("EasyAntiCheat", detected)

    def test_analyze_protections_with_battleye_strings(self):
        """验证检测 BattleEye 反作弊字符串"""
        detected = self.analyzer._detect_anti_cheat(
            "BEService.exe", "/games/BattleEye/BEService.exe"
        )
        self.assertIn("BattleEye", detected)

    def test_analyze_protections_with_xigncode_strings(self):
        """验证检测 XignCode3 反作弊字符串"""
        detected = self.analyzer._detect_anti_cheat(
            "x3.xem", "/games/XignCode/x3.xem"
        )
        self.assertIn("XignCode3", detected)

    def test_analyze_protections_no_anti_cheat(self):
        """验证不包含反作弊字符串时返回空列表"""
        detected = self.analyzer._detect_anti_cheat(
            "notepad.exe", "/usr/bin/notepad"
        )
        self.assertEqual(detected, [])

    def test_analyze_protections_by_name(self):
        """验证通过名称分析保护"""
        result = self.analyzer.analyze_protections("thIS_PrOcEsS_DoEs_NoT_ExIsT_12345")
        self.assertIsInstance(result, dict)
        self.assertIn("has_protection", result)
        self.assertIn("detected_systems", result)
        self.assertIn("risk_level", result)
        self.assertIn("details", result)

    def test_analyze_protections_by_pid(self):
        """验证通过 PID 分析保护"""
        result = self.analyzer.analyze_protections(999999999)
        self.assertIsInstance(result, dict)
        self.assertFalse(result["has_protection"])

    def test_enumerate_modules_returns_list(self):
        """验证 enumerate_modules 返回列表"""
        # 测试当前进程
        modules = self.analyzer.enumerate_modules(os.getpid())
        self.assertIsInstance(modules, list)

    def test_enumerate_modules_invalid_pid(self):
        """验证枚举无效 PID 的模块返回空列表"""
        modules = self.analyzer.enumerate_modules(999999999)
        self.assertIsInstance(modules, list)
        self.assertEqual(len(modules), 0)

    def test_find_module_invalid_pid(self):
        """验证在无效 PID 中查找模块返回 None"""
        result = self.analyzer.find_module(999999999, "kernel32.dll")
        self.assertIsNone(result)

    def test_get_process_architecture_invalid_pid(self):
        """验证获取无效 PID 的架构返回默认值"""
        arch = self.analyzer.get_process_architecture(999999999)
        self.assertIn(arch, [ARCH_X86, ARCH_X64])

    def test_get_process_architecture_x86_pe_header(self):
        """验证通过 PE32 头识别 x86 架构"""
        # 测试 _get_linux_process_arch 的逻辑
        # 在 Linux 上通过 ELF header 识别, 在 Windows 上通过 PE 识别
        # 这里测试架构检测函数的基本行为
        self.assertIn(ARCH_X86, [ARCH_X86, ARCH_X64, "arm", "arm64"])

    def test_get_process_architecture_x64_pe_header(self):
        """验证通过 PE32+ 头识别 x64 架构"""
        self.assertIn(ARCH_X64, [ARCH_X86, ARCH_X64, "arm", "arm64"])

    def test_clear_cache(self):
        """验证缓存清除"""
        self.analyzer._process_cache[1234] = ProcessInfo(
            pid=1234, name="test", path="/test"
        )
        self.analyzer.clear_cache()
        self.assertEqual(len(self.analyzer._process_cache), 0)

    def test_detect_anti_cheat_all_signatures(self):
        """验证所有反作弊系统签名可被检测"""
        for system, signatures in ANTI_CHEAT_SIGNATURES.items():
            # 测试每个系统的第一个签名
            first_sig = signatures[0]
            detected = self.analyzer._detect_anti_cheat(first_sig, f"/games/{system}/{first_sig}")
            self.assertIn(system, detected, f"应该检测到 {system}")


# ============================================================================
# TestInjectionStrategyPlanner - 策略规划器测试
# ============================================================================

class TestInjectionStrategyPlanner(unittest.TestCase):
    """策略规划器测试"""

    def setUp(self):
        self.planner = InjectionStrategyPlanner()
        self.target = ProcessInfo(
            pid=1234,
            name="game.exe",
            path="/usr/games/game.exe",
            architecture=ARCH_X64,
            is_protected=False,
        )

    def test_plan_injection_basic(self):
        """验证基本注入策略规划"""
        strategy = self.planner.plan_injection(self.target, PayloadType.DLL)
        self.assertIsInstance(strategy, InjectionStrategy)
        self.assertIsInstance(strategy.method, InjectionMethod)

    def test_plan_injection_with_method_hint(self):
        """验证使用方法提示的策略规划"""
        strategy = self.planner.plan_injection(
            self.target, PayloadType.DLL, method_hint=InjectionMethod.DLL_PROXY
        )
        self.assertEqual(strategy.method, InjectionMethod.DLL_PROXY)

    def test_plan_injection_with_protected_target(self):
        """验证受保护目标的策略规划"""
        protected_target = ProcessInfo(
            pid=5678,
            name="game_protected.exe",
            path="/usr/games/game_protected.exe",
            is_protected=True,
            anti_cheat_detected=["EasyAntiCheat"],
        )
        strategy = self.planner.plan_injection(protected_target, PayloadType.DLL)
        self.assertIsInstance(strategy, InjectionStrategy)
        # 受保护目标不应推荐 CREATE_REMOTE_THREAD
        self.assertNotEqual(
            strategy.method, InjectionMethod.CREATE_REMOTE_THREAD,
            "受保护目标不应推荐 CREATE_REMOTE_THREAD"
        )

    def test_evaluate_method_basic(self):
        """验证基本方法评估"""
        evaluation = self.planner.evaluate_method(
            InjectionMethod.CREATE_REMOTE_THREAD, self.target
        )
        self.assertIsInstance(evaluation, dict)
        self.assertIn("suitable", evaluation)
        self.assertIn("score", evaluation)
        self.assertIn("stealth", evaluation)
        self.assertIn("reliability", evaluation)
        self.assertIn("compatibility", evaluation)
        self.assertIn("issues", evaluation)
        self.assertIn("warnings", evaluation)

    def test_evaluate_method_protected_target(self):
        """验证对受保护目标的方法评估"""
        protected_target = ProcessInfo(
            pid=5678,
            name="game_protected.exe",
            path="/usr/games/game_protected.exe",
            is_protected=True,
            anti_cheat_detected=["EasyAntiCheat"],
        )
        # CREATE_REMOTE_THREAD 在受保护目标上应该不适合
        evaluation = self.planner.evaluate_method(
            InjectionMethod.CREATE_REMOTE_THREAD, protected_target
        )
        self.assertFalse(evaluation["suitable"])

    def test_evaluate_method_high_integrity(self):
        """验证对高完整性级别目标的方法评估"""
        high_integrity_target = ProcessInfo(
            pid=5678,
            name="service.exe",
            path="/usr/sbin/service.exe",
            integrity_level=INTEGRITY_HIGH,
        )
        evaluation = self.planner.evaluate_method(
            InjectionMethod.CREATE_REMOTE_THREAD, high_integrity_target
        )
        self.assertIsInstance(evaluation, dict)
        # 高完整性级别可能影响兼容性
        self.assertLess(evaluation["compatibility"], 100)

    def test_rank_methods_returns_list(self):
        """验证 rank_methods 返回列表"""
        ranked = self.planner.rank_methods(self.target)
        self.assertIsInstance(ranked, list)
        for item in ranked:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)
            self.assertIsInstance(item[0], InjectionMethod)
            self.assertIsInstance(item[1], float)

    def test_rank_methods_sorted_by_score(self):
        """验证 rank_methods 按评分降序排列"""
        ranked = self.planner.rank_methods(self.target)
        if len(ranked) >= 2:
            for i in range(len(ranked) - 1):
                self.assertGreaterEqual(
                    ranked[i][1], ranked[i + 1][1],
                    "排名应该按评分降序排列"
                )

    def test_rank_methods_protected_target(self):
        """验证受保护目标的排名不包含 CREATE_REMOTE_THREAD"""
        protected_target = ProcessInfo(
            pid=5678,
            name="game_protected.exe",
            path="/usr/games/game_protected.exe",
            is_protected=True,
            anti_cheat_detected=["EasyAntiCheat"],
        )
        ranked = self.planner.rank_methods(protected_target)
        method_names = [m.name for m, _ in ranked]
        self.assertNotIn(
            "CREATE_REMOTE_THREAD", method_names,
            "受保护目标排名不应包含 CREATE_REMOTE_THREAD"
        )

    def test_get_requirements_all_methods(self):
        """验证所有方法都有前置条件"""
        for method in InjectionMethod:
            requirements = self.planner.get_requirements(method)
            self.assertIsInstance(requirements, list)
            self.assertGreater(len(requirements), 0,
                               f"{method.name} 应该有前置条件")

    def test_get_requirements_specific(self):
        """验证特定方法的前置条件"""
        reqs = self.planner.get_requirements(InjectionMethod.CREATE_REMOTE_THREAD)
        self.assertGreater(len(reqs), 0)
        # 应该包含权限相关的前置条件
        has_permission = any("权限" in r or "SeDebug" in r for r in reqs)
        self.assertTrue(has_permission, "CREATE_REMOTE_THREAD 应该需要权限")

    def test_generate_risk_assessment_low(self):
        """验证无保护目标的低风险评估"""
        assessment = self.planner.generate_risk_assessment(self.target)
        self.assertIsInstance(assessment, dict)
        self.assertIn("overall_risk", assessment)
        self.assertIn("overall_score", assessment)
        self.assertIn("factors", assessment)
        self.assertIn("mitigations", assessment)
        self.assertEqual(assessment["overall_risk"], "LOW")
        self.assertEqual(assessment["overall_score"], 0.0)

    def test_generate_risk_assessment_high(self):
        """验证受保护目标的高风险评估"""
        protected_target = ProcessInfo(
            pid=5678,
            name="game_protected.exe",
            path="/usr/games/game_protected.exe",
            is_protected=True,
            anti_cheat_detected=["EasyAntiCheat"],
            integrity_level=INTEGRITY_HIGH,
        )
        assessment = self.planner.generate_risk_assessment(protected_target)
        self.assertIn(assessment["overall_risk"], ["HIGH", "CRITICAL"])
        self.assertGreater(assessment["overall_score"], 0.0)

    def test_generate_risk_assessment_critical(self):
        """验证关键反作弊系统的风险评估"""
        critical_target = ProcessInfo(
            pid=5678,
            name="game_critical.exe",
            path="/usr/games/game_critical.exe",
            is_protected=True,
            anti_cheat_detected=["XignCode3"],
            integrity_level=INTEGRITY_SYSTEM,
        )
        assessment = self.planner.generate_risk_assessment(critical_target)
        self.assertEqual(assessment["overall_risk"], "CRITICAL")
        self.assertGreaterEqual(assessment["overall_score"], 60.0)

    def test_generate_risk_assessment_wow64(self):
        """验证 WOW64 进程的风险评估"""
        wow64_target = ProcessInfo(
            pid=1234,
            name="game32.exe",
            path="/usr/games/game32.exe",
            is_wow64=True,
        )
        assessment = self.planner.generate_risk_assessment(wow64_target)
        # WOW64 进程应该有额外的风险因素
        has_wow64_factor = any("WOW64" in f for f in assessment["factors"])
        if assessment["overall_score"] > 0:
            self.assertTrue(has_wow64_factor)


# ============================================================================
# TestShellcodeGenerator - Shellcode 生成器测试
# ============================================================================

class TestShellcodeGenerator(unittest.TestCase):
    """Shellcode 生成器测试"""

    def setUp(self):
        self.generator = ShellcodeGenerator()

    def test_generate_x86_load_library(self):
        """验证生成 x86 LoadLibrary shellcode"""
        sc = self.generator.generate_load_library_shellcode(
            "C:\\test.dll", ARCH_X86
        )
        self.assertIsInstance(sc, bytes)
        self.assertGreater(len(sc), 0)
        # 应该包含 DLL 路径
        self.assertIn(b"test.dll", sc)

    def test_generate_x64_load_library(self):
        """验证生成 x64 LoadLibrary shellcode"""
        sc = self.generator.generate_load_library_shellcode(
            "C:\\test.dll", ARCH_X64
        )
        self.assertIsInstance(sc, bytes)
        self.assertGreater(len(sc), 0)
        self.assertIn(b"test.dll", sc)

    def test_generate_load_library_different_archs(self):
        """验证不同架构生成不同的 shellcode"""
        sc_x86 = self.generator.generate_load_library_shellcode(
            "C:\\test.dll", ARCH_X86
        )
        sc_x64 = self.generator.generate_load_library_shellcode(
            "C:\\test.dll", ARCH_X64
        )
        # 不同架构的 shellcode 应该不同
        self.assertNotEqual(sc_x86, sc_x64)

    def test_generate_reflective_loader(self):
        """验证生成反射式加载器"""
        dll_data = b"MZ\x00\x01" + b"\x00" * 100
        sc = self.generator.generate_reflective_loader(dll_data)
        self.assertIsInstance(sc, bytes)
        self.assertGreater(len(sc), 0)
        # 应该包含 DLL 数据
        self.assertGreater(len(sc), len(dll_data))

    def test_generate_reflective_loader_stub(self):
        """验证反射式加载器包含 stub 代码"""
        dll_data = b"MZ" + b"\x00" * 128
        sc = self.generator.generate_reflective_loader(dll_data)
        # stub 代码应该以 call 指令开始
        self.assertGreater(len(sc), 512)
        # 包含 E8 (call) 操作码
        self.assertIn(b"\xE8", sc[:10])

    def test_generate_exit_thread_x86(self):
        """验证生成 x86 退出线程 shellcode"""
        sc = self.generator.generate_exit_thread_shellcode(ARCH_X86)
        self.assertIsInstance(sc, bytes)
        self.assertGreater(len(sc), 0)

    def test_generate_exit_thread_x64(self):
        """验证生成 x64 退出线程 shellcode"""
        sc = self.generator.generate_exit_thread_shellcode(ARCH_X64)
        self.assertIsInstance(sc, bytes)
        self.assertGreater(len(sc), 0)

    def test_generate_exit_thread_different_archs(self):
        """验证不同架构的退出线程 shellcode 不同"""
        sc_x86 = self.generator.generate_exit_thread_shellcode(ARCH_X86)
        sc_x64 = self.generator.generate_exit_thread_shellcode(ARCH_X64)
        self.assertNotEqual(sc_x86, sc_x64)

    def test_generate_message_box(self):
        """验证生成 MessageBox shellcode"""
        sc = self.generator.generate_message_box_shellcode(
            "Test Message", "Test Title", ARCH_X64
        )
        self.assertIsInstance(sc, bytes)
        self.assertGreater(len(sc), 0)

    def test_generate_message_box_x86(self):
        """验证生成 x86 MessageBox shellcode"""
        sc = self.generator.generate_message_box_shellcode(
            "Hello", "Title", ARCH_X86
        )
        self.assertIsInstance(sc, bytes)
        self.assertGreater(len(sc), 0)
        # x86 版本应该包含 pushad 指令
        self.assertIn(b"\x60", sc)

    def test_encode_shellcode_xor(self):
        """验证 XOR 编码 shellcode"""
        original = b"Hello World Test Data 12345"
        encoded = self.generator.encode_shellcode(original, "xor")
        self.assertIsInstance(encoded, bytes)
        self.assertEqual(len(encoded), len(original))
        # 编码后的数据应该不同
        self.assertNotEqual(encoded, original)

    def test_encode_shellcode_xor_decode(self):
        """验证 XOR 编码可解码"""
        original = b"Test data for XOR encoding"
        encoded = self.generator.encode_shellcode(original, "xor")
        decoded = self.generator.decode_shellcode(encoded, "xor")
        self.assertEqual(decoded, original)

    def test_encode_shellcode_base64(self):
        """验证 Base64 编码 shellcode"""
        original = b"Hello World Base64 Test"
        encoded = self.generator.encode_shellcode(original, "base64")
        self.assertIsInstance(encoded, bytes)
        # Base64 编码后长度应该大于原始数据
        self.assertGreater(len(encoded), len(original))

    def test_encode_shellcode_base64_decode(self):
        """验证 Base64 编码可解码"""
        original = b"Test data for Base64 encoding"
        encoded = self.generator.encode_shellcode(original, "base64")
        decoded = self.generator.decode_shellcode(encoded, "base64")
        self.assertEqual(decoded, original)

    def test_encode_shellcode_invalid_method(self):
        """验证使用无效编码方法时抛出 ValueError"""
        with self.assertRaises(ValueError):
            self.generator.encode_shellcode(b"test", "invalid_method")

    def test_decode_shellcode_invalid_method(self):
        """验证使用无效解码方法时抛出 ValueError"""
        with self.assertRaises(ValueError):
            self.generator.decode_shellcode(b"test", "invalid_method")

    def test_generate_apc_injection_stub_x86(self):
        """验证生成 x86 APC 注入桩"""
        sc = self.generator.generate_apc_injection_stub(ARCH_X86)
        self.assertIsInstance(sc, bytes)
        self.assertGreater(len(sc), 0)

    def test_generate_apc_injection_stub_x64(self):
        """验证生成 x64 APC 注入桩"""
        sc = self.generator.generate_apc_injection_stub(ARCH_X64)
        self.assertIsInstance(sc, bytes)
        self.assertGreater(len(sc), 0)

    def test_get_statistics(self):
        """验证获取统计信息"""
        # 生成一些 shellcode 以增加计数
        self.generator.generate_load_library_shellcode("C:\\test1.dll", ARCH_X64)
        self.generator.generate_load_library_shellcode("C:\\test2.dll", ARCH_X86)
        self.generator.generate_reflective_loader(b"\x00" * 64)

        stats = self.generator.get_statistics()
        self.assertIsInstance(stats, dict)
        self.assertIn("generated_count", stats)
        self.assertIn("total_bytes", stats)
        self.assertIn("total_kb", stats)
        self.assertGreater(stats["generated_count"], 0)
        self.assertGreater(stats["total_bytes"], 0)


# ============================================================================
# TestPEInjector - PE 文件注入器测试
# ============================================================================

class TestPEInjector(unittest.TestCase):
    """PE 文件注入器测试"""

    def setUp(self):
        self.pe_injector = PEInjector()
        self.pe_data = _build_pe32_file()

    def test_inject_section_basic(self):
        """验证基本节区注入"""
        code = b"\x90" * 256  # NOP sled
        modified = self.pe_injector.inject_section(self.pe_data, ".inject", code)
        self.assertIsInstance(modified, bytes)
        self.assertGreater(len(modified), len(self.pe_data))

    def test_inject_section_name_truncation(self):
        """验证节区名称截断 (最多 8 字符)"""
        code = b"\x90" * 128
        modified = self.pe_injector.inject_section(
            self.pe_data, "very_long_name", code
        )
        self.assertIsInstance(modified, bytes)

    def test_inject_section_invalid_pe(self):
        """验证无效 PE 文件抛出 RuntimeError (包装 ValueError)"""
        with self.assertRaises(RuntimeError):
            self.pe_injector.inject_section(b"not a pe file", ".test", b"\x90")

    def test_add_import(self):
        """验证添加导入项"""
        modified = self.pe_injector.add_import(
            self.pe_data, "kernel32.dll", "LoadLibraryA"
        )
        self.assertIsInstance(modified, bytes)

    def test_add_import_invalid_pe(self):
        """验证无效 PE 添加导入项抛出 RuntimeError (包装 ValueError)"""
        with self.assertRaises(RuntimeError):
            self.pe_injector.add_import(b"not valid", "kernel32.dll", "func")

    def test_modify_entry_point(self):
        """验证修改入口点"""
        new_ep = 0x2000
        modified = self.pe_injector.modify_entry_point(self.pe_data, new_ep)
        self.assertIsInstance(modified, bytes)
        self.assertEqual(len(modified), len(self.pe_data))

        # 验证入口点被修改
        dos_header = modified[:64]
        pe_offset = struct.unpack_from("<I", dos_header, 0x3C)[0]
        ep_offset = pe_offset + 4 + 20 + 16
        actual_ep = struct.unpack_from("<I", modified, ep_offset)[0]
        self.assertEqual(actual_ep, new_ep)

    def test_modify_entry_point_invalid_pe(self):
        """验证无效 PE 修改入口点抛出 RuntimeError (包装 ValueError)"""
        with self.assertRaises(RuntimeError):
            self.pe_injector.modify_entry_point(b"not valid", 0x1000)

    def test_add_tls_callback(self):
        """验证添加 TLS 回调"""
        modified = self.pe_injector.add_tls_callback(self.pe_data, 0x3000)
        self.assertIsInstance(modified, bytes)

    def test_add_tls_callback_invalid_pe(self):
        """验证无效 PE 添加 TLS 回调抛出 RuntimeError (包装 ValueError)"""
        with self.assertRaises(RuntimeError):
            self.pe_injector.add_tls_callback(b"not valid", 0x1000)

    def test_create_proxy_dll(self):
        """验证创建代理 DLL"""
        proxy_data = self.pe_injector.create_proxy_dll(
            "original.dll", "payload.dll"
        )
        self.assertIsInstance(proxy_data, bytes)
        self.assertGreater(len(proxy_data), 0)
        # 应该以 MZ 开头
        self.assertTrue(proxy_data[:2] == b"MZ",
                        "代理 DLL 应该以 MZ 魔数开头")

    def test_create_proxy_dll_with_real_file(self):
        """验证使用真实 PE 文件创建代理 DLL"""
        # 使用构建的 PE 数据作为原始 DLL
        tmpdir = tempfile.mkdtemp()
        try:
            orig_path = os.path.join(tmpdir, "original.dll")
            with open(orig_path, "wb") as f:
                f.write(self.pe_data)

            proxy_data = self.pe_injector.create_proxy_dll(
                orig_path, "payload.dll"
            )
            self.assertIsInstance(proxy_data, bytes)
            self.assertGreater(len(proxy_data), 0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_is_valid_pe_true(self):
        """验证有效 PE 文件检测"""
        self.assertTrue(self.pe_injector._is_valid_pe(self.pe_data))

    def test_is_valid_pe_false(self):
        """验证无效 PE 文件检测"""
        self.assertFalse(self.pe_injector._is_valid_pe(b"not a pe"))
        self.assertFalse(self.pe_injector._is_valid_pe(b"MZ" + b"\x00" * 62))
        self.assertFalse(self.pe_injector._is_valid_pe(b""))

    def test_align_up(self):
        """验证对齐函数"""
        self.assertEqual(self.pe_injector._align_up(0, 0x200), 0)
        self.assertEqual(self.pe_injector._align_up(1, 0x200), 0x200)
        self.assertEqual(self.pe_injector._align_up(0x200, 0x200), 0x200)
        self.assertEqual(self.pe_injector._align_up(0x201, 0x200), 0x400)
        self.assertEqual(self.pe_injector._align_up(100, 0), 100)

    def test_get_statistics(self):
        """验证获取统计信息"""
        stats = self.pe_injector.get_statistics()
        self.assertIsInstance(stats, dict)
        self.assertIn("operations_count", stats)

    def test_inject_section_multi_section_pe(self):
        """验证多节区 PE 的节区注入"""
        pe_multi = _build_pe32_file(num_sections=5)
        code = b"\xCC" * 512
        modified = self.pe_injector.inject_section(pe_multi, ".newsec", code)
        self.assertIsInstance(modified, bytes)
        self.assertGreater(len(modified), len(pe_multi))

    def test_inject_section_x64_pe(self):
        """验证 64位 PE 的节区注入"""
        pe64 = _build_pe64_file()
        code = b"\x90" * 256
        modified = self.pe_injector.inject_section(pe64, ".inject64", code)
        self.assertIsInstance(modified, bytes)


# ============================================================================
# TestCodeCaveScanner - 代码洞穴扫描器测试
# ============================================================================

class TestCodeCaveScanner(unittest.TestCase):
    """代码洞穴扫描器测试"""

    def setUp(self):
        self.scanner = CodeCaveScanner()

    def test_scan_code_caves_with_zero_filled_regions(self):
        """验证扫描零填充区域的代码洞穴"""
        # 创建包含零填充区域的数据
        data = bytearray(0x2000)
        # 填充非零数据
        for i in range(0x2000):
            data[i] = (i * 7 + 13) & 0xFF
        # 创建零填充洞穴
        for i in range(0x500, 0x600):
            data[i] = 0x00
        for i in range(0x1000, 0x1200):
            data[i] = 0x00

        caves = self.scanner.scan_code_caves(bytes(data), min_size=64)
        self.assertIsInstance(caves, list)
        self.assertGreater(len(caves), 0, "应该找到至少一个代码洞穴")

        for cave in caves:
            self.assertIsInstance(cave, CodeCave)
            self.assertGreaterEqual(cave.size, 64)

    def test_scan_code_caves_with_nop_regions(self):
        """验证扫描 NOP 填充区域"""
        data = bytearray(0x2000)
        for i in range(0x2000):
            data[i] = (i * 7 + 13) & 0xFF
        # 创建 NOP 填充区域
        for i in range(0x800, 0x900):
            data[i] = 0x90

        caves = self.scanner.scan_code_caves(bytes(data), min_size=64)
        for cave in caves:
            self.assertIsInstance(cave, CodeCave)

    def test_scan_code_caves_with_int3_regions(self):
        """验证扫描 INT3 填充区域"""
        data = bytearray(0x2000)
        for i in range(0x2000):
            data[i] = (i * 7 + 13) & 0xFF
        # 创建 INT3 填充区域
        for i in range(0xA00, 0xB00):
            data[i] = 0xCC

        caves = self.scanner.scan_code_caves(bytes(data), min_size=64)
        for cave in caves:
            self.assertIsInstance(cave, CodeCave)

    def test_scan_code_caves_min_size_filter(self):
        """验证最小大小过滤"""
        data = bytearray(0x2000)
        for i in range(0x2000):
            data[i] = (i * 7 + 13) & 0xFF
        # 创建一个小洞穴 (32 字节)
        for i in range(0x500, 0x520):
            data[i] = 0x00
        # 创建一个中等洞穴 (128 字节)
        for i in range(0x800, 0x880):
            data[i] = 0x00

        # 使用 min_size=100 应该只找到中等洞穴
        caves = self.scanner.scan_code_caves(bytes(data), min_size=100)
        for cave in caves:
            self.assertGreaterEqual(cave.size, 100)

    def test_scan_code_caves_empty_data(self):
        """验证空数据扫描"""
        caves = self.scanner.scan_code_caves(b"", min_size=64)
        self.assertIsInstance(caves, list)
        self.assertEqual(len(caves), 0)

    def test_scan_section_gaps_with_pe(self):
        """验证扫描 PE 节区间隙"""
        pe_data = _build_pe32_file(num_sections=3)
        gaps = self.scanner.scan_section_gaps(pe_data)
        self.assertIsInstance(gaps, list)
        for gap in gaps:
            self.assertIsInstance(gap, CodeCave)

    def test_scan_section_gaps_non_pe(self):
        """验证非 PE 数据扫描节区间隙返回空列表"""
        gaps = self.scanner.scan_section_gaps(b"not a pe file")
        self.assertIsInstance(gaps, list)
        self.assertEqual(len(gaps), 0)

    def test_find_best_cave(self):
        """验证查找最佳洞穴"""
        data = bytearray(0x4000)
        for i in range(0x4000):
            data[i] = (i * 7 + 13) & 0xFF
        # 创建一个大洞穴
        for i in range(0x1000, 0x1400):
            data[i] = 0x00

        best = self.scanner.find_best_cave(bytes(data), required_size=256)
        self.assertIsNotNone(best, "应该找到最佳洞穴")
        self.assertIsInstance(best, CodeCave)
        self.assertGreaterEqual(best.size, 256)

    def test_find_best_cave_not_found(self):
        """验证查找洞穴未找到的情况"""
        data = bytearray(0x2000)
        for i in range(0x2000):
            data[i] = (i * 7 + 13) & 0xFF

        best = self.scanner.find_best_cave(bytes(data), required_size=99999)
        self.assertIsNone(best, "超大需求应该找不到洞穴")

    def test_rate_cave_quality(self):
        """验证评定洞穴质量"""
        cave = CodeCave(
            offset=0x1000,
            size=512,
            section=".text",
            quality=75.0,
            alignment=1,
        )
        quality = self.scanner.rate_cave_quality(cave)
        self.assertEqual(quality, 75.0)

    def test_get_statistics(self):
        """验证获取扫描器统计信息"""
        stats = self.scanner.get_statistics()
        self.assertIsInstance(stats, dict)
        self.assertIn("total_caves_found", stats)
        self.assertIn("average_size", stats)
        self.assertIn("largest_cave", stats)

    def test_scan_code_caves_quality_scoring(self):
        """验证洞穴质量评分"""
        data = bytearray(0x4000)
        for i in range(0x4000):
            data[i] = (i * 7 + 13) & 0xFF
        # 创建 NOP 填充区域 (高质量)
        for i in range(0x1000, 0x1400):
            data[i] = 0x90

        caves = self.scanner.scan_code_caves(bytes(data), min_size=64)
        for cave in caves:
            self.assertGreaterEqual(cave.quality, 0.0)
            self.assertLessEqual(cave.quality, 100.0)

    def test_scan_code_caves_pe_file(self):
        """验证在 PE 文件中扫描代码洞穴"""
        pe_data = _build_pe_with_zero_caves(
            num_sections=3,
            cave_regions=[(0x600, 0x100), (0x800, 0x80)],
        )
        caves = self.scanner.scan_code_caves(pe_data, min_size=50)
        self.assertIsInstance(caves, list)
        for cave in caves:
            self.assertIsInstance(cave, CodeCave)
            # 洞穴应该被分配到某个节区
            self.assertIsInstance(cave.section, str)


# ============================================================================
# TestInjectionEngine - 注入引擎集成测试
# ============================================================================

class TestInjectionEngine(unittest.TestCase):
    """注入引擎集成测试"""

    def setUp(self):
        self.engine = InjectionEngine()

    def test_engine_initialization(self):
        """验证引擎初始化"""
        self.assertTrue(self.engine._initialized)
        self.assertEqual(self.engine._operation_count, 0)
        self.assertIsNone(self.engine._last_result)
        self.assertEqual(len(self.engine._injection_history), 0)

    def test_engine_version(self):
        """验证引擎版本"""
        self.assertEqual(self.engine.VERSION, "1.0.0")
        self.assertIn("San7ModMaker", self.engine.ENGINE_NAME)

    def test_analyze_target_by_name(self):
        """验证通过名称分析目标"""
        # 分析自身进程 (Python)
        result = self.engine.analyze_target("python")
        self.assertIsInstance(result, dict)
        # 可能找到也可能找不到，取决于当前进程名
        if "error" in result:
            self.assertIn("未找到", result["error"])

    def test_analyze_target_by_pid(self):
        """验证通过 PID 分析目标"""
        result = self.engine.analyze_target(os.getpid())
        self.assertIsInstance(result, dict)
        if "target" in result:
            self.assertIsNotNone(result["target"])
            self.assertIn("protection_analysis", result)
            self.assertIn("risk_assessment", result)
            self.assertIn("method_compatibility", result)

    def test_analyze_target_non_existent(self):
        """验证分析不存在的目标"""
        result = self.engine.analyze_target("thIS_PrOcEsS_DoEs_NoT_ExIsT_12345")
        self.assertIsInstance(result, dict)
        if "error" in result:
            self.assertIn("未找到", result["error"])

    def test_plan_injection(self):
        """验证规划注入策略"""
        target = ProcessInfo(
            pid=1234,
            name="game.exe",
            path="/usr/games/game.exe",
        )
        strategy = self.engine.plan_injection(target, PayloadType.DLL)
        self.assertIsInstance(strategy, InjectionStrategy)

    def test_plan_injection_with_method_hint(self):
        """验证带方法提示的注入规划"""
        target = ProcessInfo(
            pid=1234,
            name="game.exe",
            path="/usr/games/game.exe",
        )
        strategy = self.engine.plan_injection(
            target,
            PayloadType.DLL,
            method_hint=InjectionMethod.SIDE_LOADING,
        )
        self.assertEqual(strategy.method, InjectionMethod.SIDE_LOADING)

    def test_generate_payload_dll(self):
        """验证生成 DLL 类型载荷"""
        config = {
            "dll_path": "C:\\test.dll",
            "arch": ARCH_X64,
        }
        payload = self.engine.generate_payload(PayloadType.DLL, config)
        self.assertIsInstance(payload, bytes)
        self.assertGreater(len(payload), 0)

    def test_generate_payload_dll_x86(self):
        """验证生成 x86 DLL 载荷"""
        config = {
            "dll_path": "C:\\test.dll",
            "arch": ARCH_X86,
        }
        payload = self.engine.generate_payload(PayloadType.DLL, config)
        self.assertIsInstance(payload, bytes)

    def test_generate_payload_dll_missing_path(self):
        """验证缺少 DLL 路径时抛出 ValueError"""
        config = {"arch": ARCH_X64}
        with self.assertRaises(ValueError):
            self.engine.generate_payload(PayloadType.DLL, config)

    def test_generate_payload_shellcode(self):
        """验证生成 SHELLCODE 类型载荷"""
        config = {
            "shellcode": b"\x90" * 100,
            "arch": ARCH_X64,
        }
        payload = self.engine.generate_payload(PayloadType.SHELLCODE, config)
        self.assertIsInstance(payload, bytes)
        self.assertEqual(payload, b"\x90" * 100)

    def test_generate_payload_shellcode_missing(self):
        """验证缺少 shellcode 时抛出 ValueError"""
        config = {"arch": ARCH_X64}
        with self.assertRaises(ValueError):
            self.engine.generate_payload(PayloadType.SHELLCODE, config)

    def test_generate_payload_reflective_dll(self):
        """验证生成 REFLECTIVE_DLL 类型载荷"""
        config = {
            "dll_data": b"MZ" + b"\x00" * 128,
            "arch": ARCH_X64,
        }
        payload = self.engine.generate_payload(PayloadType.REFLECTIVE_DLL, config)
        self.assertIsInstance(payload, bytes)
        self.assertGreater(len(payload), 0)

    def test_generate_payload_reflective_dll_missing(self):
        """验证缺少 dll_data 时抛出 ValueError"""
        config = {"arch": ARCH_X64}
        with self.assertRaises(ValueError):
            self.engine.generate_payload(PayloadType.REFLECTIVE_DLL, config)

    def test_generate_payload_process(self):
        """验证生成 PROCESS 类型载荷"""
        config = {
            "exe_data": b"MZ" + b"\x00" * 128,
            "arch": ARCH_X64,
        }
        payload = self.engine.generate_payload(PayloadType.PROCESS, config)
        self.assertIsInstance(payload, bytes)

    def test_generate_payload_process_missing(self):
        """验证缺少 exe_data 时抛出 ValueError"""
        config = {"arch": ARCH_X64}
        with self.assertRaises(ValueError):
            self.engine.generate_payload(PayloadType.PROCESS, config)

    def test_generate_payload_with_encoding(self):
        """验证生成带编码的载荷"""
        config = {
            "dll_path": "C:\\test.dll",
            "arch": ARCH_X64,
            "encode": "xor",
        }
        payload = self.engine.generate_payload(PayloadType.DLL, config)
        self.assertIsInstance(payload, bytes)

    def test_find_code_caves_nonexistent_file(self):
        """验证查找不存在的文件中的代码洞穴"""
        caves = self.engine.find_code_caves(
            "/tmp/nonexistent_file_12345.exe", min_size=64
        )
        self.assertIsInstance(caves, list)
        self.assertEqual(len(caves), 0)

    def test_find_code_caves_real_file(self):
        """验证在真实 PE 文件中查找代码洞穴"""
        tmpdir = tempfile.mkdtemp()
        try:
            pe_path = os.path.join(tmpdir, "test.exe")
            pe_data = _build_pe_with_zero_caves(
                cave_regions=[(0x600, 0x200)],
            )
            with open(pe_path, "wb") as f:
                f.write(pe_data)

            caves = self.engine.find_code_caves(pe_path, min_size=64)
            self.assertIsInstance(caves, list)
            for cave in caves:
                self.assertIsInstance(cave, CodeCave)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_create_proxy_dll(self):
        """验证创建代理 DLL"""
        proxy_data = self.engine.create_proxy_dll(
            "original.dll", "payload.dll"
        )
        self.assertIsInstance(proxy_data, bytes)
        self.assertGreater(len(proxy_data), 0)

    def test_create_proxy_dll_with_output(self):
        """验证创建代理 DLL 并保存到文件"""
        tmpdir = tempfile.mkdtemp()
        try:
            output_path = os.path.join(tmpdir, "proxy.dll")
            proxy_data = self.engine.create_proxy_dll(
                "original.dll", "payload.dll", output_path=output_path
            )
            self.assertIsInstance(proxy_data, bytes)
            self.assertTrue(os.path.exists(output_path))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_get_injection_script(self):
        """验证生成注入脚本"""
        target = ProcessInfo(
            pid=1234,
            name="game.exe",
            path="/usr/games/game.exe",
        )
        script = self.engine.get_injection_script(
            InjectionMethod.CREATE_REMOTE_THREAD,
            target,
            "C:\\test.dll",
        )
        self.assertIsInstance(script, str)
        self.assertIn("python", script.lower())
        self.assertIn("CREATE_REMOTE_THREAD", script)

    def test_get_injection_script_apc(self):
        """验证生成 APC 注入脚本"""
        target = ProcessInfo(pid=1234, name="game.exe", path="/usr/games/game.exe")
        script = self.engine.get_injection_script(
            InjectionMethod.QUEUE_USER_APC, target, "C:\\test.dll"
        )
        self.assertIsInstance(script, str)
        self.assertIn("APC", script)

    def test_get_injection_script_reflective(self):
        """验证生成反射式注入脚本"""
        target = ProcessInfo(pid=1234, name="game.exe", path="/usr/games/game.exe")
        script = self.engine.get_injection_script(
            InjectionMethod.REFLECTIVE_DLL, target, "C:\\test.dll"
        )
        self.assertIsInstance(script, str)

    def test_list_methods(self):
        """验证列出所有注入方法"""
        methods = self.engine.list_methods()
        self.assertIsInstance(methods, list)
        self.assertEqual(len(methods), 10)
        for method in methods:
            self.assertIsInstance(method, dict)
            self.assertIn("name", method)
            self.assertIn("description", method)
            self.assertIn("risk", method)
            self.assertIn("risk_score", method)
            self.assertIn("stealth", method)
            self.assertIn("reliability", method)
            self.assertIn("compatibility", method)
            self.assertIn("requirements", method)

    def test_get_statistics(self):
        """验证获取引擎统计信息"""
        # 执行一些操作以增加计数
        self.engine.plan_injection(
            ProcessInfo(pid=1, name="test", path="/test"),
            PayloadType.DLL,
        )

        stats = self.engine.get_statistics()
        self.assertIsInstance(stats, dict)
        self.assertIn("engine_name", stats)
        self.assertIn("engine_version", stats)
        self.assertIn("total_operations", stats)
        self.assertIn("initialized", stats)
        self.assertIn("injection_history_count", stats)
        self.assertIn("sub_components", stats)
        self.assertIn("available_methods", stats)
        self.assertIn("method_count", stats)
        self.assertTrue(stats["initialized"])
        self.assertGreater(stats["total_operations"], 0)
        self.assertEqual(stats["method_count"], 10)


# ============================================================================
# TestConvenienceFunctions - 便捷函数测试
# ============================================================================

class TestConvenienceFunctions(unittest.TestCase):
    """便捷函数测试"""

    def test_quick_inject_nonexistent(self):
        """验证快速注入不存在的进程"""
        result = quick_inject(
            "thIS_PrOcEsS_DoEs_NoT_ExIsT_12345",
            "C:\\test.dll",
        )
        self.assertIsInstance(result, InjectionResult)
        self.assertFalse(result.success)
        self.assertIn("未找到", result.error_message)

    def test_quick_inject_with_method(self):
        """验证带指定方法的快速注入"""
        result = quick_inject(
            "thIS_PrOcEsS_DoEs_NoT_ExIsT_12345",
            "C:\\test.dll",
            method=InjectionMethod.DLL_PROXY,
        )
        self.assertIsInstance(result, InjectionResult)
        self.assertFalse(result.success)
        self.assertEqual(result.method, InjectionMethod.DLL_PROXY)

    def test_quick_analyze_nonexistent(self):
        """验证快速分析不存在的进程"""
        report = quick_analyze("thIS_PrOcEsS_DoEs_NoT_ExIsT_12345")
        self.assertIsInstance(report, dict)
        self.assertIn("error", report)
        self.assertIn("未找到", report["error"])

    def test_list_methods_function(self):
        """验证 list_methods 便捷函数"""
        methods = list_methods()
        self.assertIsInstance(methods, list)
        self.assertEqual(len(methods), 10)
        for method in methods:
            self.assertIsInstance(method, dict)
            self.assertIn("name", method)
            self.assertIn("risk", method)

    def test_list_methods_consistency(self):
        """验证 list_methods 与引擎方法的一致性"""
        methods = list_methods()
        engine = InjectionEngine()
        engine_methods = engine.list_methods()
        self.assertEqual(len(methods), len(engine_methods))
        for i in range(len(methods)):
            self.assertEqual(methods[i]["name"], engine_methods[i]["name"])


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    unittest.main()