#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
San7ModMaker vuln_discovery 测试套件

覆盖 VulnerabilityDiscoveryEngine 及所有子分析器的完整路径：
- 枚举类型 (VulnerabilityType, SeverityLevel, ExploitDifficulty)
- 数据类 (Vulnerability, VulnerabilityReport)
- 不安全函数检测器 (UnsafeFunctionDetector)
- 缓冲区溢出分析器 (BufferOverflowAnalyzer)
- 整数溢出分析器 (IntegerOverflowAnalyzer)
- 内存安全分析器 (MemorySafetyAnalyzer)
- 二进制保护分析器 (BinaryProtectionAnalyzer)
- SEH 分析器 (SEHAnalyzer)
- 漏洞挖掘引擎 (VulnerabilityDiscoveryEngine)
- 便捷函数 (quick_scan, quick_scan_unsafe, quick_check_protections)
"""

import os
import sys
import json
import unittest
import tempfile
import struct
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.vuln_discovery import (
    VulnerabilityDiscoveryEngine,
    VulnerabilityType,
    SeverityLevel,
    ExploitDifficulty,
    Vulnerability,
    VulnerabilityReport,
    UnsafeFunctionDetector,
    BufferOverflowAnalyzer,
    IntegerOverflowAnalyzer,
    MemorySafetyAnalyzer,
    BinaryProtectionAnalyzer,
    SEHAnalyzer,
    quick_scan,
    quick_scan_unsafe,
    quick_check_protections,
    get_cwe_id,
)


# ============================================================================
# PE 常量
# ============================================================================

IMAGE_DOS_SIGNATURE = 0x5A4D       # MZ
IMAGE_NT_SIGNATURE = 0x00004550    # PE\0\0
IMAGE_NT_OPTIONAL_HDR32_MAGIC = 0x10B
IMAGE_NT_OPTIONAL_HDR64_MAGIC = 0x20B

# PE DLL Characteristics
DYNAMIC_BASE = 0x0040
NX_COMPAT = 0x0100
NO_SEH = 0x0400
GUARD_CF = 0x4000
HIGH_ENTROPY_VA = 0x0020


# ============================================================================
# PE 构建辅助函数
# ============================================================================

def _build_minimal_pe(dll_characteristics=0, is_64bit=False):
    """构建最小 PE 文件，用于二进制保护测试。

    Args:
        dll_characteristics: DLL Characteristics 标志组合
        is_64bit: 是否为 64位 PE

    Returns:
        bytes: PE 文件二进制数据
    """
    magic = IMAGE_NT_OPTIONAL_HDR64_MAGIC if is_64bit else IMAGE_NT_OPTIONAL_HDR32_MAGIC
    opt_header_size = 112 if is_64bit else 96  # 不含前 24 字节 COFF

    # DOS Header
    dos_stub = b"\x0e\x1f\xba\x0e\x00\xb4\x09\xcd\x21\xb8\x01\x4c\xcd\x21"  # 最小 stub
    # e_lfanew 指向 PE 签名位置: DOS header(64) + DOS stub(13) = 0x4D
    e_lfanew = 0x40 + len(dos_stub)
    dos_header = struct.pack("<H", IMAGE_DOS_SIGNATURE)  # e_magic
    dos_header += b"\x00" * 58                           # padding
    dos_header += struct.pack("<I", e_lfanew)             # e_lfanew

    # PE Signature
    pe_sig = struct.pack("<I", IMAGE_NT_SIGNATURE)

    # COFF Header (20 bytes)
    coff = struct.pack("<HHIIIHH", 0x014C, 0, 0, 0, 0, 0, 0)

    # Optional Header
    if is_64bit:
        opt = struct.pack("<H", IMAGE_NT_OPTIONAL_HDR64_MAGIC)
        opt += b"\x00" * 2                                 # lmaj/min
        opt += struct.pack("<I", 0)                         # size_of_code
        opt += struct.pack("<I", 0)                         # size_of_init_data
        opt += struct.pack("<I", 0)                         # size_of_uninit_data
        opt += struct.pack("<I", 0x1000)                    # entry_point
        opt += struct.pack("<I", 0)                         # base_of_code
        opt += struct.pack("<Q", 0x400000)                  # image_base
        opt += struct.pack("<I", 0x1000)                    # section_align
        opt += struct.pack("<I", 0x200)                     # file_align
        opt += b"\x00" * 8                                  # os ver
        opt += b"\x00" * 8                                  # image ver
        opt += struct.pack("<H", 4)                          # subsystem_major
        opt += b"\x00" * 2                                   # subsystem_minor
        opt += b"\x00" * 4                                   # reserved
        opt += struct.pack("<I", 0x4000)                    # size_of_image
        opt += struct.pack("<I", 0x200)                     # size_of_headers
        opt += struct.pack("<I", 0)                         # checksum
        opt += struct.pack("<H", 2)                          # subsystem (GUI)
        opt += struct.pack("<H", dll_characteristics)        # dll_characteristics
        opt += struct.pack("<Q", 0x100000)                  # stack_reserve
        opt += struct.pack("<Q", 0x1000)                    # stack_commit
        opt += struct.pack("<Q", 0x100000)                  # heap_reserve
        opt += struct.pack("<Q", 0x1000)                    # heap_commit
        opt += struct.pack("<I", 0)                          # loader_flags
        opt += struct.pack("<I", 16)                         # num_data_dirs
        opt += b"\x00" * 128                                # data dirs (16*8)
    else:
        opt = struct.pack("<H", IMAGE_NT_OPTIONAL_HDR32_MAGIC)
        opt += b"\x00" * 2                                  # lmaj/min
        opt += struct.pack("<I", 0)                          # size_of_code
        opt += struct.pack("<I", 0)                          # size_of_init_data
        opt += struct.pack("<I", 0)                          # size_of_uninit_data
        opt += struct.pack("<I", 0x1000)                     # entry_point
        opt += struct.pack("<I", 0)                          # base_of_code
        opt += struct.pack("<I", 0x400000)                   # image_base
        opt += struct.pack("<I", 0x1000)                     # section_align
        opt += struct.pack("<I", 0x200)                      # file_align
        opt += b"\x00" * 8                                   # os ver
        opt += b"\x00" * 8                                   # image ver
        opt += struct.pack("<H", 4)                           # subsystem_major
        opt += b"\x00" * 2                                    # subsystem_minor
        opt += b"\x00" * 4                                    # reserved
        opt += struct.pack("<I", 0x4000)                     # size_of_image
        opt += struct.pack("<I", 0x200)                      # size_of_headers
        opt += struct.pack("<I", 0)                           # checksum
        opt += struct.pack("<H", 2)                           # subsystem (GUI)
        opt += struct.pack("<H", dll_characteristics)         # dll_characteristics
        opt += struct.pack("<I", 0x100000)                   # stack_reserve
        opt += struct.pack("<I", 0x1000)                     # stack_commit
        opt += struct.pack("<I", 0x100000)                   # heap_reserve
        opt += struct.pack("<I", 0x1000)                     # heap_commit
        opt += struct.pack("<I", 0)                           # loader_flags
        opt += struct.pack("<I", 16)                          # num_data_dirs
        opt += b"\x00" * 128                                 # data dirs (16*8)

    # 组装 PE 文件: DOS header + DOS stub + PE sig + COFF + Optional Header
    pe = dos_header + dos_stub + pe_sig + coff + opt

    # 填充到至少 0x200 (512) 字节
    if len(pe) < 0x200:
        pe += b"\x00" * (0x200 - len(pe))

    return pe


def _build_pe_with_imports(dll_characteristics=0, imports=None):
    """构建带导入表的最小 PE 文件。

    Args:
        dll_characteristics: DLL Characteristics 标志
        imports: 要导入的字符串列表，以 \x00 分隔

    Returns:
        bytes: PE 文件二进制数据
    """
    pe = _build_minimal_pe(dll_characteristics)
    if imports:
        import_data = b"\x00".join(imports) + b"\x00"
        pe += import_data
    return pe


# ============================================================================
# TestVulnerabilityType - 漏洞类型枚举测试
# ============================================================================

class TestVulnerabilityType(unittest.TestCase):
    """测试 VulnerabilityType 枚举"""

    def test_all_18_types_exist(self):
        """验证所有 18 种漏洞类型均已定义"""
        expected_types = [
            "BUFFER_OVERFLOW", "FORMAT_STRING", "INTEGER_OVERFLOW",
            "USE_AFTER_FREE", "DOUBLE_FREE", "NULL_POINTER_DEREF",
            "RACE_CONDITION", "STACK_OVERFLOW", "HEAP_OVERFLOW",
            "COMMAND_INJECTION", "PATH_TRAVERSAL", "INSECURE_API",
            "MISSING_STACK_COOKIE", "DEP_DISABLED", "ASLR_DISABLED",
            "SEH_OVERWRITE", "UNINITIALIZED_MEMORY", "TYPE_CONFUSION",
        ]
        for name in expected_types:
            self.assertIn(name, VulnerabilityType.__members__,
                          f"Missing VulnerabilityType: {name}")
        self.assertEqual(len(VulnerabilityType), 18)

    def test_type_is_enum(self):
        """验证 VulnerabilityType 是枚举类型"""
        self.assertTrue(isinstance(VulnerabilityType.BUFFER_OVERFLOW, VulnerabilityType))

    def test_cwe_id_buffer_overflow(self):
        """验证 BUFFER_OVERFLOW 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.BUFFER_OVERFLOW), "CWE-120")

    def test_cwe_id_format_string(self):
        """验证 FORMAT_STRING 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.FORMAT_STRING), "CWE-134")

    def test_cwe_id_integer_overflow(self):
        """验证 INTEGER_OVERFLOW 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.INTEGER_OVERFLOW), "CWE-190")

    def test_cwe_id_use_after_free(self):
        """验证 USE_AFTER_FREE 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.USE_AFTER_FREE), "CWE-416")

    def test_cwe_id_double_free(self):
        """验证 DOUBLE_FREE 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.DOUBLE_FREE), "CWE-415")

    def test_cwe_id_null_pointer_deref(self):
        """验证 NULL_POINTER_DEREF 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.NULL_POINTER_DEREF), "CWE-476")

    def test_cwe_id_race_condition(self):
        """验证 RACE_CONDITION 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.RACE_CONDITION), "CWE-362")

    def test_cwe_id_stack_overflow(self):
        """验证 STACK_OVERFLOW 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.STACK_OVERFLOW), "CWE-121")

    def test_cwe_id_heap_overflow(self):
        """验证 HEAP_OVERFLOW 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.HEAP_OVERFLOW), "CWE-122")

    def test_cwe_id_command_injection(self):
        """验证 COMMAND_INJECTION 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.COMMAND_INJECTION), "CWE-77")

    def test_cwe_id_path_traversal(self):
        """验证 PATH_TRAVERSAL 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.PATH_TRAVERSAL), "CWE-22")

    def test_cwe_id_insecure_api(self):
        """验证 INSECURE_API 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.INSECURE_API), "CWE-676")

    def test_cwe_id_missing_stack_cookie(self):
        """验证 MISSING_STACK_COOKIE 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.MISSING_STACK_COOKIE), "CWE-693")

    def test_cwe_id_dep_disabled(self):
        """验证 DEP_DISABLED 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.DEP_DISABLED), "CWE-693")

    def test_cwe_id_aslr_disabled(self):
        """验证 ASLR_DISABLED 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.ASLR_DISABLED), "CWE-693")

    def test_cwe_id_seh_overwrite(self):
        """验证 SEH_OVERWRITE 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.SEH_OVERWRITE), "CWE-122")

    def test_cwe_id_uninitialized_memory(self):
        """验证 UNINITIALIZED_MEMORY 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.UNINITIALIZED_MEMORY), "CWE-457")

    def test_cwe_id_type_confusion(self):
        """验证 TYPE_CONFUSION 的 CWE 编号"""
        self.assertEqual(get_cwe_id(VulnerabilityType.TYPE_CONFUSION), "CWE-843")


# ============================================================================
# TestSeverityLevel - 严重等级测试
# ============================================================================

class TestSeverityLevel(unittest.TestCase):
    """测试 SeverityLevel 枚举"""

    def test_five_levels(self):
        """验证 5 个严重等级"""
        self.assertEqual(len(SeverityLevel), 5)
        self.assertIn(SeverityLevel.CRITICAL, SeverityLevel)
        self.assertIn(SeverityLevel.HIGH, SeverityLevel)
        self.assertIn(SeverityLevel.MEDIUM, SeverityLevel)
        self.assertIn(SeverityLevel.LOW, SeverityLevel)
        self.assertIn(SeverityLevel.INFO, SeverityLevel)

    def test_numeric_score_critical(self):
        """验证 CRITICAL 的数值评分"""
        self.assertEqual(SeverityLevel.CRITICAL.numeric_score, 10.0)

    def test_numeric_score_high(self):
        """验证 HIGH 的数值评分"""
        self.assertEqual(SeverityLevel.HIGH.numeric_score, 8.0)

    def test_numeric_score_medium(self):
        """验证 MEDIUM 的数值评分"""
        self.assertEqual(SeverityLevel.MEDIUM.numeric_score, 5.5)

    def test_numeric_score_low(self):
        """验证 LOW 的数值评分"""
        self.assertEqual(SeverityLevel.LOW.numeric_score, 3.0)

    def test_numeric_score_info(self):
        """验证 INFO 的数值评分"""
        self.assertEqual(SeverityLevel.INFO.numeric_score, 1.0)

    def test_chinese_label(self):
        """验证中文标签"""
        self.assertEqual(SeverityLevel.CRITICAL.chinese_label, "严重")
        self.assertEqual(SeverityLevel.HIGH.chinese_label, "高危")
        self.assertEqual(SeverityLevel.MEDIUM.chinese_label, "中危")
        self.assertEqual(SeverityLevel.LOW.chinese_label, "低危")
        self.assertEqual(SeverityLevel.INFO.chinese_label, "信息")


# ============================================================================
# TestExploitDifficulty - 利用难度测试
# ============================================================================

class TestExploitDifficulty(unittest.TestCase):
    """测试 ExploitDifficulty 枚举"""

    def test_five_levels(self):
        """验证 5 个利用难度等级"""
        self.assertEqual(len(ExploitDifficulty), 5)
        self.assertIn(ExploitDifficulty.TRIVIAL, ExploitDifficulty)
        self.assertIn(ExploitDifficulty.EASY, ExploitDifficulty)
        self.assertIn(ExploitDifficulty.MODERATE, ExploitDifficulty)
        self.assertIn(ExploitDifficulty.HARD, ExploitDifficulty)
        self.assertIn(ExploitDifficulty.EXTREME, ExploitDifficulty)

    def test_numeric_rating_trivial(self):
        """验证 TRIVIAL 的数值评分"""
        self.assertEqual(ExploitDifficulty.TRIVIAL.numeric_rating, 1.0)

    def test_numeric_rating_easy(self):
        """验证 EASY 的数值评分"""
        self.assertEqual(ExploitDifficulty.EASY.numeric_rating, 2.0)

    def test_numeric_rating_moderate(self):
        """验证 MODERATE 的数值评分"""
        self.assertEqual(ExploitDifficulty.MODERATE.numeric_rating, 3.0)

    def test_numeric_rating_hard(self):
        """验证 HARD 的数值评分"""
        self.assertEqual(ExploitDifficulty.HARD.numeric_rating, 4.0)

    def test_numeric_rating_extreme(self):
        """验证 EXTREME 的数值评分"""
        self.assertEqual(ExploitDifficulty.EXTREME.numeric_rating, 5.0)


# ============================================================================
# TestVulnerability - 漏洞数据类测试
# ============================================================================

class TestVulnerability(unittest.TestCase):
    """测试 Vulnerability 数据类"""

    def test_create_minimal(self):
        """创建最小 Vulnerability"""
        v = Vulnerability(
            vuln_type=VulnerabilityType.BUFFER_OVERFLOW,
            severity=SeverityLevel.HIGH,
            description="Test vulnerability",
            location="0x1000",
            confidence=0.85,
            exploit_difficulty=ExploitDifficulty.EASY,
            cwe_id="CWE-120",
            fix_suggestion="Use safe functions",
        )
        self.assertEqual(v.vuln_type, VulnerabilityType.BUFFER_OVERFLOW)
        self.assertEqual(v.severity, SeverityLevel.HIGH)
        self.assertEqual(v.description, "Test vulnerability")
        self.assertEqual(v.location, "0x1000")
        self.assertEqual(v.confidence, 0.85)
        self.assertEqual(v.exploit_difficulty, ExploitDifficulty.EASY)
        self.assertEqual(v.cwe_id, "CWE-120")
        self.assertEqual(v.fix_suggestion, "Use safe functions")
        self.assertIsNone(v.affected_code)
        self.assertIsNone(v.line_number)
        self.assertEqual(v.extra_info, {})

    def test_create_with_fix_suggestion(self):
        """创建带修复建议的 Vulnerability"""
        v = Vulnerability(
            vuln_type=VulnerabilityType.FORMAT_STRING,
            severity=SeverityLevel.CRITICAL,
            description="Format string vulnerability",
            location="0x2000",
            confidence=0.95,
            exploit_difficulty=ExploitDifficulty.TRIVIAL,
            cwe_id="CWE-134",
            fix_suggestion='Use printf("%s", input)',
        )
        self.assertIn("printf", v.fix_suggestion)

    def test_create_without_fix_suggestion(self):
        """创建不带修复建议的 Vulnerability（空字符串）"""
        v = Vulnerability(
            vuln_type=VulnerabilityType.INSECURE_API,
            severity=SeverityLevel.LOW,
            description="Insecure API",
            location="func",
            confidence=0.5,
            exploit_difficulty=ExploitDifficulty.HARD,
            cwe_id="CWE-676",
            fix_suggestion="",
        )
        self.assertEqual(v.fix_suggestion, "")

    def test_create_with_extra_info(self):
        """创建带额外信息的 Vulnerability"""
        v = Vulnerability(
            vuln_type=VulnerabilityType.STACK_OVERFLOW,
            severity=SeverityLevel.HIGH,
            description="Stack overflow",
            location="0x3000",
            confidence=0.7,
            exploit_difficulty=ExploitDifficulty.MODERATE,
            cwe_id="CWE-121",
            fix_suggestion="Increase buffer size",
            extra_info={"stack_size": 64, "copy_size": 256},
        )
        self.assertEqual(v.extra_info["stack_size"], 64)
        self.assertEqual(v.extra_info["copy_size"], 256)

    def test_create_with_affected_code(self):
        """创建带受影响代码的 Vulnerability"""
        v = Vulnerability(
            vuln_type=VulnerabilityType.BUFFER_OVERFLOW,
            severity=SeverityLevel.HIGH,
            description="Buffer overflow",
            location="0x4000",
            confidence=0.8,
            exploit_difficulty=ExploitDifficulty.EASY,
            cwe_id="CWE-120",
            fix_suggestion="Use strncpy",
            affected_code="strcpy(buf, input)",
        )
        self.assertEqual(v.affected_code, "strcpy(buf, input)")

    def test_to_dict(self):
        """测试 to_dict() 方法"""
        v = Vulnerability(
            vuln_type=VulnerabilityType.BUFFER_OVERFLOW,
            severity=SeverityLevel.HIGH,
            description="Test",
            location="0x1000",
            confidence=0.85,
            exploit_difficulty=ExploitDifficulty.EASY,
            cwe_id="CWE-120",
            fix_suggestion="Fix it",
        )
        d = v.to_dict()
        self.assertEqual(d["vuln_type"], "BUFFER_OVERFLOW")
        self.assertEqual(d["severity"], "HIGH")
        self.assertEqual(d["severity_score"], 8.0)
        self.assertEqual(d["exploit_difficulty"], "EASY")
        self.assertEqual(d["exploit_difficulty_rating"], 2.0)
        self.assertEqual(d["cwe_id"], "CWE-120")
        self.assertEqual(d["confidence"], 0.85)
        self.assertNotIn("affected_code", d)
        self.assertNotIn("line_number", d)

    def test_to_dict_with_optional_fields(self):
        """测试 to_dict() 包含可选字段"""
        v = Vulnerability(
            vuln_type=VulnerabilityType.STACK_OVERFLOW,
            severity=SeverityLevel.CRITICAL,
            description="Test",
            location="0x2000",
            confidence=0.9,
            exploit_difficulty=ExploitDifficulty.MODERATE,
            cwe_id="CWE-121",
            fix_suggestion="Fix",
            affected_code="mov eax, [ebp-0x40]",
            line_number=42,
            extra_info={"key": "value"},
        )
        d = v.to_dict()
        self.assertEqual(d["affected_code"], "mov eax, [ebp-0x40]")
        self.assertEqual(d["line_number"], 42)
        self.assertEqual(d["extra_info"]["key"], "value")

    def test_to_json(self):
        """测试 to_json() 方法（通过 json.dumps(to_dict())）"""
        v = Vulnerability(
            vuln_type=VulnerabilityType.BUFFER_OVERFLOW,
            severity=SeverityLevel.HIGH,
            description="Test JSON",
            location="0x1000",
            confidence=0.85,
            exploit_difficulty=ExploitDifficulty.EASY,
            cwe_id="CWE-120",
            fix_suggestion="Fix it",
        )
        json_str = json.dumps(v.to_dict(), ensure_ascii=False)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["vuln_type"], "BUFFER_OVERFLOW")
        self.assertEqual(parsed["severity"], "HIGH")
        self.assertEqual(parsed["cwe_id"], "CWE-120")

    def test_str_representation(self):
        """测试 __str__ 方法"""
        v = Vulnerability(
            vuln_type=VulnerabilityType.BUFFER_OVERFLOW,
            severity=SeverityLevel.HIGH,
            description="Test",
            location="0x1000",
            confidence=0.85,
            exploit_difficulty=ExploitDifficulty.EASY,
            cwe_id="CWE-120",
            fix_suggestion="Fix it",
        )
        s = str(v)
        self.assertIn("HIGH", s)
        self.assertIn("BUFFER_OVERFLOW", s)
        self.assertIn("0x1000", s)
        self.assertIn("CWE-120", s)
        self.assertIn("85%", s)


# ============================================================================
# TestVulnerabilityReport - 漏洞报告测试
# ============================================================================

class TestVulnerabilityReport(unittest.TestCase):
    """测试 VulnerabilityReport 数据类"""

    def _make_vuln(self, severity=SeverityLevel.HIGH, vuln_type=VulnerabilityType.BUFFER_OVERFLOW):
        return Vulnerability(
            vuln_type=vuln_type,
            severity=severity,
            description="Test vuln",
            location="0x1000",
            confidence=0.8,
            exploit_difficulty=ExploitDifficulty.EASY,
            cwe_id="CWE-120",
            fix_suggestion="Fix",
        )

    def test_create_empty(self):
        """创建空报告"""
        report = VulnerabilityReport(target_file="test.exe")
        self.assertEqual(report.target_file, "test.exe")
        self.assertEqual(report.vulns, [])
        self.assertEqual(report.risk_score, 0.0)
        self.assertEqual(report.total_vulns, 0)

    def test_create_with_vulnerabilities(self):
        """创建包含漏洞的报告"""
        vulns = [self._make_vuln() for _ in range(3)]
        report = VulnerabilityReport(target_file="test.exe", vulns=vulns)
        self.assertEqual(len(report.vulns), 3)

    def test_update_statistics(self):
        """测试统计信息更新"""
        vulns = [
            self._make_vuln(SeverityLevel.CRITICAL),
            self._make_vuln(SeverityLevel.HIGH),
            self._make_vuln(SeverityLevel.HIGH),
            self._make_vuln(SeverityLevel.MEDIUM),
            self._make_vuln(SeverityLevel.LOW),
            self._make_vuln(SeverityLevel.INFO),
        ]
        report = VulnerabilityReport(target_file="test.exe", vulns=vulns)
        report.update_statistics()
        self.assertEqual(report.total_vulns, 6)
        self.assertEqual(report.critical_count, 1)
        self.assertEqual(report.high_count, 2)
        self.assertEqual(report.medium_count, 1)
        self.assertEqual(report.low_count, 1)
        self.assertEqual(report.info_count, 1)

    def test_update_statistics_empty(self):
        """测试空报告统计"""
        report = VulnerabilityReport(target_file="test.exe")
        report.update_statistics()
        self.assertEqual(report.total_vulns, 0)
        self.assertEqual(report.critical_count, 0)
        self.assertEqual(report.high_count, 0)

    def test_to_dict(self):
        """测试报告 to_dict()"""
        vulns = [self._make_vuln()]
        report = VulnerabilityReport(
            target_file="test.exe",
            vulns=vulns,
            risk_score=45.5,
            summary="Test summary",
            recommendations=["Fix it"],
            scan_timestamp="2024-01-01",
            scan_duration_ms=150.0,
            file_hash="abc123",
            file_size=1024,
        )
        d = report.to_dict()
        self.assertEqual(d["target_file"], "test.exe")
        self.assertEqual(d["risk_score"], 45.5)
        self.assertEqual(d["total_vulns"], 1)
        self.assertEqual(d["recommendations"], ["Fix it"])
        self.assertEqual(len(d["vulns"]), 1)
        self.assertEqual(d["scan_timestamp"], "2024-01-01")
        self.assertEqual(d["scan_duration_ms"], 150.0)
        self.assertEqual(d["file_hash"], "abc123")
        self.assertEqual(d["file_size"], 1024)

    def test_to_json(self):
        """测试报告 to_json()"""
        vulns = [self._make_vuln()]
        report = VulnerabilityReport(
            target_file="test.exe",
            vulns=vulns,
            risk_score=50.0,
            summary="Summary",
            recommendations=["Rec1"],
        )
        json_str = report.to_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["target_file"], "test.exe")
        self.assertEqual(parsed["risk_score"], 50.0)
        self.assertEqual(len(parsed["vulns"]), 1)

    def test_to_json_indent(self):
        """测试 to_json() 缩进参数"""
        vulns = [self._make_vuln()]
        report = VulnerabilityReport(target_file="test.exe", vulns=vulns)
        json_str = report.to_json(indent=4)
        self.assertIn('    "target_file"', json_str)

    def test_summary_stats_zero_vulns(self):
        """测试无漏洞时的统计摘要"""
        report = VulnerabilityReport(target_file="test.exe")
        report.update_statistics()
        self.assertEqual(report.total_vulns, 0)
        self.assertEqual(report.critical_count, 0)

    def test_summary_stats_mixed(self):
        """测试混合严重等级的统计"""
        vulns = [
            self._make_vuln(SeverityLevel.CRITICAL),
            self._make_vuln(SeverityLevel.CRITICAL),
            self._make_vuln(SeverityLevel.HIGH),
            self._make_vuln(SeverityLevel.MEDIUM),
            self._make_vuln(SeverityLevel.LOW),
            self._make_vuln(SeverityLevel.LOW),
            self._make_vuln(SeverityLevel.LOW),
            self._make_vuln(SeverityLevel.INFO),
        ]
        report = VulnerabilityReport(target_file="test.exe", vulns=vulns)
        report.update_statistics()
        self.assertEqual(report.total_vulns, 8)
        self.assertEqual(report.critical_count, 2)
        self.assertEqual(report.high_count, 1)
        self.assertEqual(report.medium_count, 1)
        self.assertEqual(report.low_count, 3)
        self.assertEqual(report.info_count, 1)


# ============================================================================
# TestUnsafeFunctionDetector - 不安全函数检测器测试
# ============================================================================

class TestUnsafeFunctionDetector(unittest.TestCase):
    """测试 UnsafeFunctionDetector"""

    def setUp(self):
        self.detector = UnsafeFunctionDetector()

    def test_scan_unsafe_functions_strcpy(self):
        """检测 strcpy 调用"""
        data = b"some code\x00strcpy\x00more code"
        vulns = self.detector.scan_unsafe_functions(data)
        self.assertTrue(any("strcpy" in v.description for v in vulns))

    def test_scan_unsafe_functions_strcat(self):
        """检测 strcat 调用"""
        data = b"a\x00strcat\x00b"
        vulns = self.detector.scan_unsafe_functions(data)
        self.assertTrue(any("strcat" in v.description for v in vulns))

    def test_scan_unsafe_functions_sprintf(self):
        """检测 sprintf 调用"""
        data = b"code\x00sprintf\x00more"
        vulns = self.detector.scan_unsafe_functions(data)
        self.assertTrue(any("sprintf" in v.description for v in vulns))

    def test_scan_unsafe_functions_gets(self):
        """检测 gets 调用（CRITICAL 级别）"""
        data = b"code\x00gets\x00more"
        vulns = self.detector.scan_unsafe_functions(data)
        gets_vulns = [v for v in vulns if "gets" in v.description]
        self.assertTrue(len(gets_vulns) > 0)
        self.assertEqual(gets_vulns[0].severity, SeverityLevel.CRITICAL)

    def test_scan_unsafe_functions_scanf(self):
        """检测 scanf 调用"""
        data = b"code\x00scanf\x00more"
        vulns = self.detector.scan_unsafe_functions(data)
        self.assertTrue(any("scanf" in v.description for v in vulns))

    def test_scan_unsafe_functions_memcpy(self):
        """检测 memcpy 调用"""
        data = b"code\x00memcpy\x00more"
        vulns = self.detector.scan_unsafe_functions(data)
        self.assertTrue(any("memcpy" in v.description for v in vulns))

    def test_scan_unsafe_functions_system(self):
        """检测 system 调用"""
        data = b"prefix\x00system\x00suffix"
        vulns = self.detector.scan_unsafe_functions(data)
        system_vulns = [v for v in vulns if "system" in v.description]
        self.assertTrue(len(system_vulns) > 0)
        self.assertEqual(system_vulns[0].severity, SeverityLevel.CRITICAL)

    def test_scan_unsafe_functions_popen(self):
        """检测 popen 调用"""
        data = b"code\x00popen\x00more"
        vulns = self.detector.scan_unsafe_functions(data)
        popen_vulns = [v for v in vulns if "popen" in v.description]
        self.assertTrue(len(popen_vulns) > 0)
        self.assertEqual(popen_vulns[0].severity, SeverityLevel.CRITICAL)

    def test_scan_unsafe_functions_none_data(self):
        """测试 None 数据输入"""
        vulns = self.detector.scan_unsafe_functions(None)
        self.assertEqual(vulns, [])

    def test_scan_unsafe_functions_empty_data(self):
        """测试空数据"""
        vulns = self.detector.scan_unsafe_functions(b"")
        self.assertEqual(vulns, [])

    def test_scan_unsafe_functions_no_unsafe(self):
        """测试无不安全函数的数据"""
        data = b"safe code only, no dangerous functions here"
        vulns = self.detector.scan_unsafe_functions(data)
        self.assertEqual(vulns, [])

    def test_scan_unsafe_functions_with_asm_text(self):
        """测试包含汇编文本的扫描"""
        data = b"strcpy"
        text = "call strcpy\npush eax"
        vulns = self.detector.scan_unsafe_functions(data, text)
        # 应同时检测到二进制和汇编中的调用
        self.assertTrue(len(vulns) >= 2)

    def test_detect_missing_size_check(self):
        """检测缺失边界检查"""
        # memcpy 前无 cmp 指令
        data = b"\x00" * 80 + b"memcpy\x00\x00" + b"\x00" * 40
        vulns = self.detector.detect_missing_size_check(data)
        self.assertTrue(len(vulns) > 0)
        for v in vulns:
            self.assertIn("边界检查", v.description)

    def test_detect_missing_size_check_with_cmp(self):
        """存在边界检查时不应误报"""
        # 在 memcpy 前面放置 cmp 指令字节
        data = b"\x3b\xc0\x00" * 10 + b"memcpy\x00\x00"
        vulns = self.detector.detect_missing_size_check(data)
        # 有 cmp 指令，不应报告
        self.assertEqual(vulns, [])

    def test_analyze_function_usage(self):
        """测试综合分析函数使用情况"""
        data = b"strcpy\x00sprintf\x00gets\x00system\x00popen\x00lstrcpy"
        result = self.detector.analyze_function_usage(data)
        self.assertGreater(result["total_unsafe_calls"], 0)
        self.assertIn("functions_found", result)
        self.assertIn("critical_functions", result)
        self.assertIn("high_risk_functions", result)
        self.assertIn("by_category", result)
        self.assertIn("by_severity", result)
        self.assertGreater(result["deprecated_api_count"], 0)

    def test_analyze_function_usage_none_data(self):
        """测试 None 数据的综合分析"""
        result = self.detector.analyze_function_usage(None)
        self.assertEqual(result["total_unsafe_calls"], 0)

    def test_get_unsafe_function_list(self):
        """测试获取不安全函数列表"""
        func_list = self.detector.get_unsafe_function_list()
        self.assertIsInstance(func_list, dict)
        self.assertIn("strcpy", func_list)
        self.assertIn("gets", func_list)
        self.assertIn("system", func_list)
        self.assertIn("popen", func_list)
        self.assertIn("memcpy", func_list)
        self.assertEqual(func_list["gets"]["risk"], SeverityLevel.CRITICAL)
        self.assertEqual(func_list["strcpy"]["replacement"], "strncpy / strcpy_s")

    def test_detect_deprecated_apis(self):
        """测试检测已废弃 API"""
        apis = self.detector.detect_deprecated_apis()
        self.assertIsInstance(apis, dict)
        self.assertIn("lstrcpy", apis)
        self.assertIn("lstrcat", apis)
        self.assertIn("wsprintf", apis)
        self.assertEqual(apis["lstrcpy"]["replacement"], "StringCchCopy")

    def test_scan_detects_deprecated_api(self):
        """测试在二进制数据中检测废弃 API"""
        data = b"some code\x00lstrcpy\x00more code\x00wsprintf\x00end"
        vulns = self.detector.scan_unsafe_functions(data)
        deprecated = [v for v in vulns if "废弃" in v.description]
        self.assertTrue(len(deprecated) > 0)


# ============================================================================
# TestBufferOverflowAnalyzer - 缓冲区溢出分析器测试
# ============================================================================

class TestBufferOverflowAnalyzer(unittest.TestCase):
    """测试 BufferOverflowAnalyzer"""

    def setUp(self):
        self.analyzer = BufferOverflowAnalyzer()

    def test_detect_stack_buffer_overflow(self):
        """检测栈缓冲区溢出模式"""
        # sub esp, 0x40 (64字节) 后跟 memcpy 调用
        data = b"sub esp, 0x40\x00\x00" + b"\x00" * 50 + b"call memcpy\x00"
        vulns = self.analyzer.detect_stack_buffer_overflow(data)
        self.assertTrue(len(vulns) > 0)
        for v in vulns:
            self.assertEqual(v.vuln_type, VulnerabilityType.STACK_OVERFLOW)

    def test_detect_stack_buffer_overflow_none(self):
        """测试 None 数据"""
        vulns = self.analyzer.detect_stack_buffer_overflow(None)
        self.assertEqual(vulns, [])

    def test_detect_stack_buffer_overflow_with_asm(self):
        """通过汇编文本检测栈缓冲区溢出"""
        asm = """sub esp, 0x40
        push eax
        call memcpy"""
        vulns = self.analyzer.detect_stack_buffer_overflow(b"test", asm)
        self.assertTrue(len(vulns) > 0)

    def test_detect_heap_buffer_overflow(self):
        """检测堆缓冲区溢出"""
        # push 0x64 (100字节分配); call malloc; 然后 push 0x200 (512字节复制); call memcpy
        data = b"push 0x64\ncall malloc\x00\x00" + b"\x00" * 50 + b"push 0x200\ncall memcpy\x00"
        vulns = self.analyzer.detect_heap_buffer_overflow(data)
        self.assertTrue(len(vulns) > 0)
        for v in vulns:
            self.assertEqual(v.vuln_type, VulnerabilityType.HEAP_OVERFLOW)

    def test_detect_heap_buffer_overflow_none(self):
        """测试 None 数据"""
        vulns = self.analyzer.detect_heap_buffer_overflow(None)
        self.assertEqual(vulns, [])

    def test_detect_off_by_one(self):
        """检测 off-by-one 错误"""
        asm = """call strlen
        push eax
        call memcpy"""
        vulns = self.analyzer.detect_off_by_one(b"test", asm)
        self.assertTrue(len(vulns) > 0)
        for v in vulns:
            self.assertIn("off-by-one", v.description.lower())

    def test_detect_off_by_one_none_text(self):
        """测试无文本的 off-by-one 检测"""
        vulns = self.analyzer.detect_off_by_one(b"test")
        self.assertEqual(vulns, [])

    def test_analyze_copy_size(self):
        """测试复制操作分析"""
        data = b"memcpy\x00memmove\x00strcpy\x00strncpy\x00strcat\x00"
        result = self.analyzer.analyze_copy_size(data)
        self.assertGreater(result["total_copy_operations"], 0)
        self.assertIn("copy_details", result)

    def test_analyze_copy_size_none(self):
        """测试 None 数据的复制分析"""
        result = self.analyzer.analyze_copy_size(None)
        self.assertEqual(result["total_copy_operations"], 0)

    def test_detect_format_string_vuln(self):
        """检测格式字符串漏洞"""
        # 无 push 立即数前缀的 printf 调用
        data = b"mov eax, [ebp-8]\ncall printf\x00\x00"
        vulns = self.analyzer.detect_format_string_vuln(data)
        self.assertTrue(len(vulns) > 0)
        for v in vulns:
            self.assertEqual(v.vuln_type, VulnerabilityType.FORMAT_STRING)

    def test_detect_format_string_vuln_with_asm(self):
        """通过汇编文本检测格式字符串漏洞"""
        asm = """push eax
        call printf"""
        vulns = self.analyzer.detect_format_string_vuln(b"test", asm)
        self.assertTrue(len(vulns) > 0)

    def test_detect_sprintf_overflow(self):
        """检测 sprintf 溢出"""
        data = b"code\x00sprintf\x00more"
        vulns = self.analyzer.detect_sprintf_overflow(data)
        self.assertTrue(len(vulns) > 0)
        for v in vulns:
            self.assertIn("sprintf", v.description.lower())

    def test_detect_sprintf_overflow_none(self):
        """测试 None 数据的 sprintf 检测"""
        vulns = self.analyzer.detect_sprintf_overflow(None)
        self.assertEqual(vulns, [])


# ============================================================================
# TestIntegerOverflowAnalyzer - 整数溢出分析器测试
# ============================================================================

class TestIntegerOverflowAnalyzer(unittest.TestCase):
    """测试 IntegerOverflowAnalyzer"""

    def setUp(self):
        self.analyzer = IntegerOverflowAnalyzer()

    def test_detect_integer_overflow_add(self):
        """检测加法溢出（add 后无溢出检查）"""
        asm = "add eax, ebx\nmov ecx, eax"
        vulns = self.analyzer.detect_integer_overflow(b"test", asm)
        self.assertTrue(len(vulns) > 0)
        for v in vulns:
            self.assertEqual(v.vuln_type, VulnerabilityType.INTEGER_OVERFLOW)

    def test_detect_integer_overflow_mul(self):
        """检测乘法溢出（mul 后无溢出检查）"""
        asm = "mul ebx\nmov ecx, eax"
        vulns = self.analyzer.detect_integer_overflow(b"test", asm)
        self.assertTrue(len(vulns) > 0)

    def test_detect_integer_overflow_none(self):
        """测试 None 文本"""
        vulns = self.analyzer.detect_integer_overflow(b"test")
        self.assertEqual(vulns, [])

    def test_detect_signed_unsigned_mismatch(self):
        """检测有符号/无符号比较混用"""
        asm = "jg short_label\njb short_label"
        vulns = self.analyzer.detect_signed_unsigned_mismatch(b"test", asm)
        self.assertTrue(len(vulns) > 0)

    def test_detect_signed_unsigned_mismatch_none(self):
        """测试 None 文本"""
        vulns = self.analyzer.detect_signed_unsigned_mismatch(b"test")
        self.assertEqual(vulns, [])

    def test_detect_size_multiplication_overflow(self):
        """检测乘法溢出导致的分配不足"""
        asm = "imul ebx\ncall malloc"
        vulns = self.analyzer.detect_size_multiplication_overflow(b"test", asm)
        self.assertTrue(len(vulns) > 0)
        for v in vulns:
            self.assertEqual(v.vuln_type, VulnerabilityType.INTEGER_OVERFLOW)
            self.assertEqual(v.severity, SeverityLevel.HIGH)

    def test_detect_size_multiplication_overflow_none(self):
        """测试 None 文本"""
        vulns = self.analyzer.detect_size_multiplication_overflow(b"test")
        self.assertEqual(vulns, [])

    def test_detect_truncation(self):
        """检测数值截断"""
        asm = "mov ax, eax"
        vulns = self.analyzer.detect_truncation(b"test", asm)
        self.assertTrue(len(vulns) > 0)

    def test_detect_truncation_none(self):
        """测试 None 文本"""
        vulns = self.analyzer.detect_truncation(b"test")
        self.assertEqual(vulns, [])

    def test_detect_negative_allocation(self):
        """检测负值分配"""
        asm = "mov eax, [ebp-8]\npush eax\ncall malloc"
        vulns = self.analyzer.detect_negative_allocation(b"test", asm)
        self.assertTrue(len(vulns) > 0)

    def test_detect_negative_allocation_none(self):
        """测试 None 文本"""
        vulns = self.analyzer.detect_negative_allocation(b"test")
        self.assertEqual(vulns, [])


# ============================================================================
# TestMemorySafetyAnalyzer - 内存安全分析器测试
# ============================================================================

class TestMemorySafetyAnalyzer(unittest.TestCase):
    """测试 MemorySafetyAnalyzer"""

    def setUp(self):
        self.analyzer = MemorySafetyAnalyzer()

    def test_detect_use_after_free(self):
        """检测释放后使用 (UAF)"""
        asm = """call free
        mov eax, [ebx]"""
        vulns = self.analyzer.detect_use_after_free(b"test", asm)
        self.assertTrue(len(vulns) > 0)
        for v in vulns:
            self.assertEqual(v.vuln_type, VulnerabilityType.USE_AFTER_FREE)
            self.assertEqual(v.severity, SeverityLevel.CRITICAL)

    def test_detect_use_after_free_none(self):
        """测试 None 文本"""
        vulns = self.analyzer.detect_use_after_free(b"test")
        self.assertEqual(vulns, [])

    def test_detect_double_free(self):
        """检测双重释放"""
        asm = """push eax
        call free
        push eax
        call free"""
        vulns = self.analyzer.detect_double_free(b"test", asm)
        self.assertTrue(len(vulns) > 0)
        for v in vulns:
            self.assertEqual(v.vuln_type, VulnerabilityType.DOUBLE_FREE)
            self.assertEqual(v.severity, SeverityLevel.CRITICAL)

    def test_detect_double_free_none(self):
        """测试 None 文本"""
        vulns = self.analyzer.detect_double_free(b"test")
        self.assertEqual(vulns, [])

    def test_detect_null_pointer_deref(self):
        """检测空指针解引用"""
        asm = """call malloc
        mov eax, [eax]"""
        vulns = self.analyzer.detect_null_pointer_deref(b"test", asm)
        self.assertTrue(len(vulns) > 0)
        for v in vulns:
            self.assertEqual(v.vuln_type, VulnerabilityType.NULL_POINTER_DEREF)

    def test_detect_null_pointer_deref_none(self):
        """测试 None 文本"""
        vulns = self.analyzer.detect_null_pointer_deref(b"test")
        self.assertEqual(vulns, [])

    def test_detect_uninitialized_memory(self):
        """检测未初始化内存使用"""
        asm = """call malloc
        mov eax, [eax]"""
        vulns = self.analyzer.detect_uninitialized_memory(b"test", asm)
        self.assertTrue(len(vulns) > 0)
        for v in vulns:
            self.assertEqual(v.vuln_type, VulnerabilityType.UNINITIALIZED_MEMORY)

    def test_detect_uninitialized_memory_none(self):
        """测试 None 文本"""
        vulns = self.analyzer.detect_uninitialized_memory(b"test")
        self.assertEqual(vulns, [])

    def test_detect_type_confusion(self):
        """检测类型混淆"""
        asm = "reinterpret_cast<char*>(ptr)"
        vulns = self.analyzer.detect_type_confusion(b"test", asm)
        self.assertTrue(len(vulns) > 0)
        for v in vulns:
            self.assertEqual(v.vuln_type, VulnerabilityType.TYPE_CONFUSION)

    def test_detect_type_confusion_none(self):
        """测试 None 文本"""
        vulns = self.analyzer.detect_type_confusion(b"test")
        self.assertEqual(vulns, [])


# ============================================================================
# TestBinaryProtectionAnalyzer - 二进制保护分析器测试
# ============================================================================

class TestBinaryProtectionAnalyzer(unittest.TestCase):
    """测试 BinaryProtectionAnalyzer"""

    def setUp(self):
        self.analyzer = BinaryProtectionAnalyzer()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_check_stack_cookie_present(self):
        """检测栈金丝雀保护（PE with /GS）"""
        data = _build_minimal_pe() + b"__security_cookie\x00"
        result = self.analyzer.check_stack_cookie(data)
        self.assertTrue(result["enabled"])
        self.assertIn("检测到栈金丝雀", result["details"])

    def test_check_stack_cookie_absent(self):
        """检测栈金丝雀保护缺失"""
        data = _build_minimal_pe()
        result = self.analyzer.check_stack_cookie(data)
        self.assertFalse(result["enabled"])
        self.assertEqual(result["risk"], SeverityLevel.MEDIUM)

    def test_check_stack_cookie_none(self):
        """测试 None 数据"""
        result = self.analyzer.check_stack_cookie(None)
        self.assertFalse(result["enabled"])

    def test_check_dep_pe_enabled(self):
        """检测 DEP 保护（PE with NX_COMPAT）"""
        data = _build_minimal_pe(dll_characteristics=NX_COMPAT)
        result = self.analyzer.check_dep(data)
        self.assertTrue(result["enabled"])
        self.assertIn("DEP", result["details"])

    def test_check_dep_pe_disabled(self):
        """检测 DEP 未启用"""
        data = _build_minimal_pe(dll_characteristics=0)
        result = self.analyzer.check_dep(data)
        self.assertFalse(result["enabled"])
        self.assertEqual(result["risk"], SeverityLevel.HIGH)

    def test_check_dep_none(self):
        """测试 None 数据"""
        result = self.analyzer.check_dep(None)
        self.assertFalse(result["enabled"])

    def test_check_aslr_pe_enabled(self):
        """检测 ASLR 保护（PE with DYNAMIC_BASE）"""
        data = _build_minimal_pe(dll_characteristics=DYNAMIC_BASE)
        result = self.analyzer.check_aslr(data)
        self.assertTrue(result["enabled"])
        self.assertIn("ASLR", result["details"])

    def test_check_aslr_pe_disabled(self):
        """检测 ASLR 未启用"""
        data = _build_minimal_pe(dll_characteristics=0)
        result = self.analyzer.check_aslr(data)
        self.assertFalse(result["enabled"])
        self.assertEqual(result["risk"], SeverityLevel.HIGH)

    def test_check_aslr_none(self):
        """测试 None 数据"""
        result = self.analyzer.check_aslr(None)
        self.assertFalse(result["enabled"])

    def test_check_safe_seh_present(self):
        """检测 SafeSEH 保护"""
        data = _build_minimal_pe() + b"__safe_se_handler_table\x00"
        result = self.analyzer.check_safe_seh(data)
        self.assertTrue(result["enabled"])

    def test_check_safe_seh_no_seh_flag(self):
        """检测 NO_SEH 标志"""
        data = _build_minimal_pe(dll_characteristics=NO_SEH)
        result = self.analyzer.check_safe_seh(data)
        self.assertTrue(result["enabled"])

    def test_check_safe_seh_absent(self):
        """检测 SafeSEH 缺失"""
        data = _build_minimal_pe(dll_characteristics=0)
        result = self.analyzer.check_safe_seh(data)
        self.assertFalse(result["enabled"])

    def test_check_control_flow_guard_enabled(self):
        """检测 CFG 保护（PE with GUARD_CF）"""
        data = _build_minimal_pe(dll_characteristics=GUARD_CF)
        result = self.analyzer.check_control_flow_guard(data)
        self.assertTrue(result["enabled"])

    def test_check_control_flow_guard_by_function(self):
        """检测 CFG 保护（通过函数引用）"""
        data = _build_minimal_pe() + b"__guard_check_icall\x00"
        result = self.analyzer.check_control_flow_guard(data)
        self.assertTrue(result["enabled"])

    def test_check_control_flow_guard_disabled(self):
        """检测 CFG 未启用"""
        data = _build_minimal_pe(dll_characteristics=0)
        result = self.analyzer.check_control_flow_guard(data)
        self.assertFalse(result["enabled"])

    def test_check_high_entropy_aslr_64bit_enabled(self):
        """检测高熵 ASLR（64位 PE）"""
        data = _build_minimal_pe(
            dll_characteristics=HIGH_ENTROPY_VA,
            is_64bit=True,
        )
        result = self.analyzer.check_high_entropy_aslr(data)
        self.assertTrue(result["enabled"])

    def test_check_high_entropy_aslr_32bit(self):
        """检测高熵 ASLR（32位不支持）"""
        data = _build_minimal_pe(dll_characteristics=HIGH_ENTROPY_VA, is_64bit=False)
        result = self.analyzer.check_high_entropy_aslr(data)
        self.assertFalse(result["enabled"])
        self.assertIn("非 64位", result["details"])

    def test_analyze_all_protections_all_enabled(self):
        """分析所有保护（PE with all protections）"""
        dll_chars = DYNAMIC_BASE | NX_COMPAT | GUARD_CF | HIGH_ENTROPY_VA
        data = (
            _build_minimal_pe(dll_characteristics=dll_chars, is_64bit=True)
            + b"__security_cookie\x00"
            + b"__safe_se_handler_table\x00"
        )
        result = self.analyzer.analyze_all_protections(data)
        self.assertEqual(result["stack_cookie"]["enabled"], True)
        self.assertEqual(result["dep"]["enabled"], True)
        self.assertEqual(result["aslr"]["enabled"], True)
        self.assertEqual(result["safe_seh"]["enabled"], True)
        self.assertEqual(result["control_flow_guard"]["enabled"], True)
        self.assertEqual(result["high_entropy_aslr"]["enabled"], True)
        self.assertIn("summary", result)
        self.assertGreater(result["summary"]["enabled_count"], 0)
        self.assertIn("coverage_percent", result["summary"])

    def test_analyze_all_protections_none_disabled(self):
        """分析所有保护（PE without any protections）"""
        data = _build_minimal_pe(dll_characteristics=0)
        result = self.analyzer.analyze_all_protections(data)
        self.assertEqual(result["stack_cookie"]["enabled"], False)
        self.assertEqual(result["dep"]["enabled"], False)
        self.assertEqual(result["aslr"]["enabled"], False)
        self.assertIn("summary", result)
        self.assertIn("status", result["summary"])
        self.assertEqual(result["summary"]["status"], "保护不足")

    def test_analyze_all_protections_none_data(self):
        """测试 None 数据"""
        result = self.analyzer.analyze_all_protections(None)
        self.assertFalse(result["stack_cookie"]["enabled"])


# ============================================================================
# TestSEHAnalyzer - SEH 分析器测试
# ============================================================================

class TestSEHAnalyzer(unittest.TestCase):
    """测试 SEHAnalyzer"""

    def setUp(self):
        self.analyzer = SEHAnalyzer()

    def test_find_seh_handlers(self):
        """查找 SEH 处理器"""
        data = b"__except_handler\x00" + b"\x00" * 10 + b"AddVectoredExceptionHandler\x00"
        handlers = self.analyzer.find_seh_handlers(data)
        self.assertTrue(len(handlers) >= 2)
        types = [h["type"] for h in handlers]
        self.assertIn("SEH", types)
        self.assertIn("VEH", types)

    def test_find_seh_handlers_none(self):
        """测试 None 数据"""
        handlers = self.analyzer.find_seh_handlers(None)
        self.assertEqual(handlers, [])

    def test_find_seh_handlers_empty(self):
        """测试空数据"""
        handlers = self.analyzer.find_seh_handlers(b"")
        self.assertEqual(handlers, [])

    def test_detect_seh_overwrite(self):
        """检测 SEH 覆写漏洞"""
        data = b"__except_handler\x00\x00" + b"\x00" * 20
        vulns = self.analyzer.detect_seh_overwrite(data)
        self.assertTrue(len(vulns) > 0)
        for v in vulns:
            self.assertEqual(v.vuln_type, VulnerabilityType.SEH_OVERWRITE)

    def test_detect_seh_overwrite_with_safe_seh(self):
        """有 SafeSEH 保护时不应报告覆写"""
        data = b"__except_handler\x00__safe_se_handler_table\x00"
        vulns = self.analyzer.detect_seh_overwrite(data)
        self.assertEqual(vulns, [])

    def test_detect_seh_overwrite_none(self):
        """测试 None 数据"""
        vulns = self.analyzer.detect_seh_overwrite(None)
        self.assertEqual(vulns, [])

    def test_analyze_exception_flow(self):
        """分析异常处理流程"""
        data = b"__except_handler\x00" + b"\x00" * 20
        result = self.analyzer.analyze_exception_flow(data)
        self.assertIn("handler_count", result)
        self.assertIn("safe_seh_enabled", result)
        self.assertIn("veh_handler_count", result)
        self.assertIn("risk_assessment", result)
        self.assertGreater(result["handler_count"], 0)
        self.assertFalse(result["safe_seh_enabled"])

    def test_analyze_exception_flow_none(self):
        """测试 None 数据"""
        result = self.analyzer.analyze_exception_flow(None)
        self.assertEqual(result["handler_count"], 0)

    def test_detect_catch_all(self):
        """检测 catch-all 模式"""
        data = b"__catch\x00\x00__except\x00\x00"
        vulns = self.analyzer.detect_catch_all(data)
        self.assertTrue(len(vulns) > 0)

    def test_detect_catch_all_none(self):
        """测试 None 数据"""
        vulns = self.analyzer.detect_catch_all(None)
        self.assertEqual(vulns, [])


# ============================================================================
# TestVulnerabilityDiscoveryEngine - 漏洞挖掘引擎测试
# ============================================================================

class TestVulnerabilityDiscoveryEngine(unittest.TestCase):
    """测试 VulnerabilityDiscoveryEngine"""

    def setUp(self):
        self.engine = VulnerabilityDiscoveryEngine()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_test_file(self, filename, content):
        """创建测试文件"""
        path = os.path.join(self.tmpdir, filename)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def test_scan_file_pe_with_unsafe_functions(self):
        """扫描包含不安全函数的 PE 文件"""
        data = _build_minimal_pe() + b"strcpy\x00gets\x00sprintf\x00system\x00popen\x00"
        path = self._create_test_file("test_unsafe.exe", data)
        report = self.engine.scan_file(path)
        self.assertIsInstance(report, VulnerabilityReport)
        self.assertGreater(report.total_vulns, 0)
        self.assertGreater(report.risk_score, 0)

    def test_scan_file_pe_with_protections_disabled(self):
        """扫描无保护的 PE 文件"""
        data = _build_minimal_pe(dll_characteristics=0)
        path = self._create_test_file("test_noprot.exe", data)
        report = self.engine.scan_file(path)
        # 应检测到 DEP/ASLR/StackCookie 缺失
        self.assertGreater(report.total_vulns, 0)

    def test_scan_file_nonexistent(self):
        """测试不存在的文件"""
        with self.assertRaises(FileNotFoundError):
            self.engine.scan_file("/nonexistent/path.exe")

    def test_scan_asm_with_buffer_overflow(self):
        """通过汇编文本扫描缓冲区溢出"""
        asm = """sub esp, 0x40
        push eax
        push ebx
        call strcpy
        push eax
        call printf"""
        report = self.engine.scan_asm(asm)
        self.assertIsInstance(report, VulnerabilityReport)
        self.assertGreater(report.total_vulns, 0)

    def test_scan_asm_empty(self):
        """扫描空汇编文本"""
        report = self.engine.scan_asm("")
        self.assertEqual(report.total_vulns, 0)

    def test_scan_unsafe_functions(self):
        """仅扫描不安全函数"""
        data = _build_minimal_pe() + b"strcpy\x00gets\x00system\x00"
        path = self._create_test_file("test_unsafe2.exe", data)
        report = self.engine.scan_unsafe_functions(path)
        self.assertIsInstance(report, VulnerabilityReport)
        self.assertGreater(report.total_vulns, 0)

    def test_scan_buffer_overflow(self):
        """仅扫描缓冲区溢出"""
        data = _build_minimal_pe() + b"sub esp, 0x40\x00call memcpy\x00sprintf\x00"
        path = self._create_test_file("test_buf.exe", data)
        report = self.engine.scan_buffer_overflow(path)
        self.assertIsInstance(report, VulnerabilityReport)

    def test_scan_integer_overflow(self):
        """仅扫描整数溢出"""
        asm = "add eax, ebx\nmul ecx\nimul ebx\ncall malloc"
        data = asm.encode()
        path = self._create_test_file("test_int.exe", data)
        report = self.engine.scan_integer_overflow(path)
        self.assertIsInstance(report, VulnerabilityReport)

    def test_scan_memory_safety(self):
        """仅扫描内存安全"""
        asm = """call free
        mov eax, [ebx]
        call malloc
        mov eax, [eax]
        reinterpret_cast<char*>"""
        data = asm.encode()
        path = self._create_test_file("test_mem.exe", data)
        report = self.engine.scan_memory_safety(path)
        self.assertIsInstance(report, VulnerabilityReport)

    def test_scan_binary_protections(self):
        """检查二进制保护"""
        data = _build_minimal_pe(dll_characteristics=DYNAMIC_BASE | NX_COMPAT)
        path = self._create_test_file("test_prot.exe", data)
        result = self.engine.scan_binary_protections(path)
        self.assertIsInstance(result, dict)
        self.assertIn("stack_cookie", result)
        self.assertIn("dep", result)
        self.assertIn("aslr", result)
        self.assertIn("safe_seh", result)
        self.assertIn("control_flow_guard", result)
        self.assertIn("high_entropy_aslr", result)
        self.assertIn("summary", result)

    def test_scan_binary_protections_nonexistent(self):
        """检查不存在文件的保护"""
        result = self.engine.scan_binary_protections("/nonexistent.exe")
        self.assertIn("error", result)

    def test_scan_seh(self):
        """扫描 SEH"""
        data = _build_minimal_pe() + b"__except_handler\x00"
        path = self._create_test_file("test_seh.exe", data)
        report = self.engine.scan_seh(path)
        self.assertIsInstance(report, VulnerabilityReport)

    def test_generate_report(self):
        """生成报告（等同于 scan_file）"""
        data = _build_minimal_pe() + b"strcpy\x00"
        path = self._create_test_file("test_gen.exe", data)
        report = self.engine.generate_report(path)
        self.assertIsInstance(report, VulnerabilityReport)

    def test_get_risk_score(self):
        """获取风险评分"""
        data = _build_minimal_pe(dll_characteristics=0) + b"strcpy\x00gets\x00system\x00popen\x00"
        path = self._create_test_file("test_risk.exe", data)
        score = self.engine.get_risk_score(path)
        self.assertIsInstance(score, float)
        self.assertGreater(score, 0)

    def test_get_risk_score_no_vulns(self):
        """获取无漏洞的风险评分"""
        # 仅包含安全代码的 PE
        data = _build_minimal_pe(dll_characteristics=DYNAMIC_BASE | NX_COMPAT | GUARD_CF)
        data += b"__security_cookie\x00"
        path = self._create_test_file("test_safe.exe", data)
        score = self.engine.get_risk_score(path)
        self.assertIsInstance(score, float)

    def test_get_statistics(self):
        """获取引擎统计信息"""
        stats = self.engine.get_statistics()
        self.assertIn("total_scans", stats)
        self.assertIn("total_vulns_found", stats)
        self.assertIn("components", stats)
        self.assertIn("supported_vuln_types", stats)
        self.assertIn("cwe_coverage", stats)
        self.assertIn("scan_history", stats)
        self.assertEqual(stats["supported_vuln_types"], 18)
        self.assertEqual(stats["components"]["unsafe_function_detector"], "ready")
        self.assertEqual(stats["components"]["buffer_overflow_analyzer"], "ready")
        self.assertEqual(stats["components"]["integer_overflow_analyzer"], "ready")
        self.assertEqual(stats["components"]["memory_safety_analyzer"], "ready")
        self.assertEqual(stats["components"]["binary_protection_analyzer"], "ready")
        self.assertEqual(stats["components"]["seh_analyzer"], "ready")

    def test_get_statistics_after_scan(self):
        """扫描后统计信息应更新"""
        data = _build_minimal_pe() + b"strcpy\x00"
        path = self._create_test_file("test_stats.exe", data)
        self.engine.scan_file(path)
        stats = self.engine.get_statistics()
        self.assertGreater(stats["total_scans"], 0)
        self.assertGreater(stats["total_vulns_found"], 0)

    def test_scan_file_returns_structured_report(self):
        """验证 scan_file 返回结构化的报告"""
        data = _build_minimal_pe() + b"strcpy\x00sprintf\x00"
        path = self._create_test_file("test_struct.exe", data)
        report = self.engine.scan_file(path)
        # 验证报告结构
        self.assertIsNotNone(report.summary)
        self.assertIsNotNone(report.recommendations)
        self.assertGreater(report.scan_duration_ms, 0)
        self.assertGreater(len(report.file_hash), 0)
        self.assertGreater(report.file_size, 0)


# ============================================================================
# TestConvenienceFunctions - 便捷函数测试
# ============================================================================

class TestConvenienceFunctions(unittest.TestCase):
    """测试便捷函数"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_test_file(self, filename, content):
        path = os.path.join(self.tmpdir, filename)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def test_quick_scan(self):
        """测试 quick_scan"""
        data = _build_minimal_pe() + b"strcpy\x00gets\x00"
        path = self._create_test_file("quick_scan.exe", data)
        result = quick_scan(path)
        self.assertIsInstance(result, dict)
        self.assertIn("target_file", result)
        self.assertIn("vulns", result)
        self.assertIn("risk_score", result)
        self.assertIn("total_vulns", result)

    def test_quick_scan_unsafe(self):
        """测试 quick_scan_unsafe"""
        data = _build_minimal_pe() + b"strcpy\x00system\x00popen\x00"
        path = self._create_test_file("quick_unsafe.exe", data)
        result = quick_scan_unsafe(path)
        self.assertIsInstance(result, dict)
        self.assertIn("vulns", result)
        self.assertGreater(result["total_vulns"], 0)

    def test_quick_check_protections(self):
        """测试 quick_check_protections"""
        data = _build_minimal_pe(dll_characteristics=DYNAMIC_BASE | NX_COMPAT)
        path = self._create_test_file("quick_prot.exe", data)
        result = quick_check_protections(path)
        self.assertIsInstance(result, dict)
        self.assertIn("stack_cookie", result)
        self.assertIn("dep", result)
        self.assertIn("aslr", result)
        self.assertIn("summary", result)

    def test_quick_check_protections_no_prot(self):
        """测试无保护文件的 quick_check_protections"""
        data = _build_minimal_pe(dll_characteristics=0)
        path = self._create_test_file("quick_noprot.exe", data)
        result = quick_check_protections(path)
        self.assertFalse(result["dep"]["enabled"])
        self.assertFalse(result["aslr"]["enabled"])


# ============================================================================
# 主入口
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)