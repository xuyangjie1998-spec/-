"""
MemoryScanner 模块单元测试
==========================

测试 core.memory_scanner.MemoryScanner 的所有核心逻辑。
使用 mock 模拟平台 API，不依赖真实进程。
"""

import os
import sys
import struct
import unittest
from unittest.mock import patch, MagicMock, PropertyMock, call

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# 通用 Mock 工具
# ============================================================

def _make_scanner_mock():
    """
    创建一个已附加到进程的 MemoryScanner mock。
    模拟 is_attached() 返回 True，并注入可读内存区域。
    """
    scanner = MagicMock()
    scanner.is_attached.return_value = True
    scanner._process_id = 12345
    scanner._process_name = "Sango7.exe"
    scanner._process_handle = 0x100
    scanner._base_address = 0x400000
    scanner._platform = "windows"
    scanner._system_info = {
        "platform": "windows",
        "page_size": 4096,
        "allocation_granularity": 65536,
        "min_address": 0x10000,
        "max_address": 0x7FFFFFFF,
    }
    scanner._hooks = {}
    scanner._snapshots = {}
    scanner._scan_results = {}
    scanner._scan_previous = {}
    scanner._scan_initial = {}
    scanner._scan_round = 0
    scanner._memory_cache = {}
    scanner._write_backups = []
    scanner._module_list = []
    return scanner


# ============================================================
# TestCase: 模块信息
# ============================================================

class TestMemoryScannerInfo(unittest.TestCase):
    """测试模块信息相关方法"""

    def test_get_info(self):
        """get_info() 返回模块元数据"""
        from core.memory_scanner import MemoryScanner

        info = MemoryScanner.get_info()
        self.assertTrue(info["success"])
        self.assertEqual(info["name"], "MemoryScanner")
        self.assertEqual(info["version"], "1.0.0")
        self.assertIn("capabilities", info)
        self.assertIn("value_types", info)
        self.assertIn("preset_count", info)
        self.assertIn("preset_names", info)
        self.assertTrue(isinstance(info["capabilities"], dict))
        self.assertIn("process_management", info["capabilities"])
        self.assertIn("memory_rw", info["capabilities"])
        self.assertIn("exact_scan", info["capabilities"])
        self.assertIn("fuzzy_scan", info["capabilities"])
        self.assertIn("hooks", info["capabilities"])
        self.assertIn("presets", info["capabilities"])

    def test_get_presets(self):
        """get_presets() 返回内置预设"""
        from core.memory_scanner import MemoryScanner

        presets = MemoryScanner.get_presets()
        self.assertTrue(presets["success"])
        self.assertGreater(presets["count"], 0)
        self.assertIn("presets", presets)
        self.assertIn("money", presets["presets"])
        self.assertIn("hp", presets["presets"])
        self.assertIn("mp", presets["presets"])
        self.assertIn("level", presets["presets"])
        self.assertIn("exp", presets["presets"])
        self.assertIn("troops", presets["presets"])
        self.assertEqual(presets["presets"]["money"]["value_type"], "int32")
        self.assertEqual(presets["presets"]["money"]["default_value"], 1000)
        self.assertEqual(presets["presets"]["hp"]["value_type"], "int16")
        self.assertEqual(presets["presets"]["level"]["value_type"], "int16")


# ============================================================
# TestCase: 进程附加/断开
# ============================================================

class TestMemoryScannerAttach(unittest.TestCase):
    """测试进程附加/断开相关方法"""

    def setUp(self):
        from core.memory_scanner import MemoryScanner

        self.scanner = MemoryScanner()

    def test_is_attached_initial(self):
        """初始状态：未附加到任何进程"""
        self.assertFalse(self.scanner.is_attached())

    def test_detach_not_attached(self):
        """未附加时调用 detach()"""
        result = self.scanner.detach()
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_attach_process_not_found(self):
        """附加不存在的进程名"""
        # 模拟进程枚举返回空
        with patch.object(self.scanner, '_enumerate_modules', return_value=[]):
            result = self.scanner.attach("NonexistentProcess.exe")
        self.assertFalse(result["success"])
        self.assertIn("未找到", result["message"])

    def test_list_hooks_empty(self):
        """初始 Hook 列表为空"""
        result = self.scanner.list_hooks()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["hooks"], [])


# ============================================================
# TestCase: 未附加时的错误处理
# ============================================================

class TestMemoryScannerNotAttached(unittest.TestCase):
    """测试未附加到进程时各方法的错误处理"""

    def setUp(self):
        from core.memory_scanner import MemoryScanner

        self.scanner = MemoryScanner()

    def test_get_process_info_not_attached(self):
        """未附加时获取进程信息"""
        result = self.scanner.get_process_info()
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_read_memory_not_attached(self):
        """未附加时读取内存"""
        result = self.scanner.read_memory(0x400000, 16)
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_write_memory_not_attached(self):
        """未附加时写入内存"""
        result = self.scanner.write_memory(0x400000, b"\x90\x90\x90\x90")
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_read_pointer_not_attached(self):
        """未附加时读取指针链"""
        result = self.scanner.read_pointer(0x400000, [0x10, 0x4, 0x8])
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_write_pointer_not_attached(self):
        """未附加时写入指针链"""
        result = self.scanner.write_pointer(0x400000, [0x10, 0x4], b"\x01\x00\x00\x00")
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_scan_exact_value_not_attached(self):
        """未附加时精确值扫描"""
        result = self.scanner.scan_exact_value(999, "int32")
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_scan_exact_text_not_attached(self):
        """未附加时文本扫描"""
        result = self.scanner.scan_exact_text("测试文本", "gbk")
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_scan_pattern_not_attached(self):
        """未附加时 AOB 模式扫描"""
        result = self.scanner.scan_pattern(b"\x55\x8B\xEC", "xxx")
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_new_scan_not_attached(self):
        """未附加时新扫描"""
        result = self.scanner.new_scan()
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_next_scan_not_attached(self):
        """未附加时 next_scan 过滤"""
        result = self.scanner.next_scan("increased")
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_scan_increased_not_attached(self):
        """未附加时增大扫描"""
        result = self.scanner.scan_increased()
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_scan_decreased_not_attached(self):
        """未附加时减小扫描"""
        result = self.scanner.scan_decreased()
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_scan_unchanged_not_attached(self):
        """未附加时不变扫描"""
        result = self.scanner.scan_unchanged()
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_scan_changed_not_attached(self):
        """未附加时变化扫描"""
        result = self.scanner.scan_changed()
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_scan_range_not_attached(self):
        """未附加时范围扫描"""
        result = self.scanner.scan_range(0, 100, "int32")
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_enumerate_regions_not_attached(self):
        """未附加时枚举内存区域"""
        result = self.scanner.enumerate_regions()
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_find_code_cave_not_attached(self):
        """未附加时搜索 Code Cave"""
        result = self.scanner.find_code_cave(min_size=256)
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_inject_code_not_attached(self):
        """未附加时注入代码"""
        result = self.scanner.inject_code(0, b"\x90\x90\x90\x90\xC3")
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_inject_dll_not_attached(self):
        """未附加时注入 DLL"""
        result = self.scanner.inject_dll("C:\\test.dll")
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_install_hook_not_attached(self):
        """未附加时安装 Hook"""
        result = self.scanner.install_hook(0x401000, b"\xE9\x00\x00\x00\x00", "detour")
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_remove_hook_not_attached(self):
        """未附加时移除 Hook"""
        result = self.scanner.remove_hook(0x401000)
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_take_snapshot_not_attached(self):
        """未附加时创建快照"""
        result = self.scanner.take_snapshot("test_snap")
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])

    def test_run_preset_not_attached(self):
        """未附加时运行预设"""
        result = self.scanner.run_preset("money")
        self.assertFalse(result["success"])
        self.assertIn("未附加", result["message"])


# ============================================================
# TestCase: 快照对比
# ============================================================

class TestMemoryScannerSnapshots(unittest.TestCase):
    """测试快照对比逻辑"""

    def setUp(self):
        from core.memory_scanner import MemoryScanner

        self.scanner = MemoryScanner()

    def test_compare_snapshots_invalid(self):
        """对比不存在的快照"""
        self.scanner._snapshots = {}
        result = self.scanner.compare_snapshots("snapA", "snapB")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["message"])

    def test_compare_snapshots_valid(self):
        """对比两个有效快照"""
        self.scanner._snapshots = {
            "snap_before": {
                "name": "snap_before",
                "data": {
                    0x400000: {
                        "base": 0x400000,
                        "size": 4096,
                        "data": {
                            0x400000: b"AAAA",
                            0x400004: b"BBBB",
                        },
                    },
                },
                "timestamp": 1000.0,
                "region_count": 1,
                "total_bytes": 8,
            },
            "snap_after": {
                "name": "snap_after",
                "data": {
                    0x400000: {
                        "base": 0x400000,
                        "size": 4096,
                        "data": {
                            0x400000: b"AAAA",
                            0x400004: b"CCCC",
                        },
                    },
                },
                "timestamp": 2000.0,
                "region_count": 1,
                "total_bytes": 8,
            },
        }

        result = self.scanner.compare_snapshots("snap_before", "snap_after")
        self.assertTrue(result["success"])
        self.assertEqual(result["snapshot1"], "snap_before")
        self.assertEqual(result["snapshot2"], "snap_after")
        self.assertGreaterEqual(result["total_changes"], 1)


# ============================================================
# TestCase: 扫描模式与掩码
# ============================================================

class TestMemoryScannerPattern(unittest.TestCase):
    """测试模式匹配与掩码逻辑"""

    def setUp(self):
        from core.memory_scanner import MemoryScanner

        self.scanner = MemoryScanner()

    def test_scan_pattern_with_mask(self):
        """带掩码的 AOB 模式扫描：掩码长度不匹配应报错"""
        # 模拟已附加
        self.scanner._process_handle = 0x100
        self.scanner._process_id = 12345
        self.scanner._process_name = "Sango7.exe"
        self.scanner._platform = "windows"

        with patch.object(self.scanner, 'is_attached', return_value=True):
            # 掩码长度与 pattern 不匹配时 scan_pattern 直接返回错误
            result = self.scanner.scan_pattern(b"\x55\x8B\xEC", "xx")
        self.assertFalse(result["success"])
        self.assertIn("mask", result["message"].lower())

    def test_scan_pattern_empty(self):
        """空 pattern 扫描"""
        self.scanner._process_handle = 0x100
        self.scanner._process_id = 12345
        with patch.object(self.scanner, 'is_attached', return_value=True):
            result = self.scanner.scan_pattern(b"")
        self.assertFalse(result["success"])
        self.assertIn("不能为空", result["message"])

    def test_match_pattern_no_mask(self):
        """_match_pattern 精确匹配"""
        self.assertTrue(self.scanner._match_pattern(b"\x01\x02\x03", b"\x01\x02\x03"))
        self.assertFalse(self.scanner._match_pattern(b"\x01\x02\x03", b"\x01\x02\x04"))
        self.assertFalse(self.scanner._match_pattern(b"\x01", b"\x01\x02"))

    def test_match_pattern_with_mask(self):
        """_match_pattern 带掩码匹配"""
        mask = "x?x"
        self.assertTrue(self.scanner._match_pattern(b"\xAA\xBB\xCC", b"\xAA\x00\xCC", mask))
        self.assertTrue(self.scanner._match_pattern(b"\xAA\x11\xCC", b"\xAA\x00\xCC", mask))
        self.assertFalse(self.scanner._match_pattern(b"\xAA\xBB\xDD", b"\xAA\x00\xCC", mask))


# ============================================================
# TestCase: 指针链
# ============================================================

class TestMemoryScannerPointerChain(unittest.TestCase):
    """测试指针链逻辑"""

    def setUp(self):
        from core.memory_scanner import MemoryScanner

        self.scanner = MemoryScanner()

    def test_pointer_chain_simple(self):
        """简单指针链：验证 read_pointer 在模拟数据上正确解析"""
        # 模拟已附加 + 模拟 _native_read_memory
        self.scanner._process_handle = 0x100
        self.scanner._process_id = 12345
        self.scanner._process_name = "Sango7.exe"
        self.scanner._platform = "windows"

        # 模拟内存布局:
        # 0x400000 -> 0x500000 (指针)
        # 0x500010 -> 0x600000 (指针+0x10)
        # 0x600014 -> 0x700000 (指针+0x4)
        # 0x700008 -> 0x00112233 (最终值, 指针+0x8)
        mock_reads = {
            0x400000: struct.pack("<I", 0x500000),
            0x500010: struct.pack("<I", 0x600000),
            0x600004: struct.pack("<I", 0x700000),
            0x700008: struct.pack("<I", 0x00112233),
        }

        def _fake_read(addr, size):
            return mock_reads.get(addr)

        with patch.object(self.scanner, '_native_read_memory', side_effect=_fake_read):
            with patch.object(self.scanner, 'is_attached', return_value=True):
                result = self.scanner.read_pointer(0x400000, [0x10, 0x4, 0x8])

        self.assertTrue(result["success"])
        self.assertEqual(result["depth"], 3)
        self.assertEqual(result["base_address"], 0x400000)
        self.assertEqual(result["final_address"], 0x700008)
        self.assertEqual(result["value"], 0x00112233)
        self.assertEqual(len(result["pointer_chain"]), 3)


# ============================================================
# TestCase: 值类型与打包
# ============================================================

class TestMemoryScannerValueTypes(unittest.TestCase):
    """测试值类型格式与打包逻辑"""

    def setUp(self):
        from core.memory_scanner import MemoryScanner

        self.scanner = MemoryScanner()

    def test_value_type_formats(self):
        """VALUE_TYPE_FORMATS 包含所有支持的类型"""
        fmt = self.scanner.VALUE_TYPE_FORMATS
        self.assertIn("int8", fmt)
        self.assertIn("uint8", fmt)
        self.assertIn("int16", fmt)
        self.assertIn("uint16", fmt)
        self.assertIn("int32", fmt)
        self.assertIn("uint32", fmt)
        self.assertIn("int64", fmt)
        self.assertIn("uint64", fmt)
        self.assertIn("float32", fmt)
        self.assertIn("float64", fmt)
        self.assertEqual(fmt["int8"], ("b", 1))
        self.assertEqual(fmt["int32"], ("<i", 4))
        self.assertEqual(fmt["float32"], ("<f", 4))

    def test_scan_exact_value_invalid_type(self):
        """无效值类型应报错"""
        self.scanner._process_handle = 0x100
        self.scanner._process_id = 12345
        with patch.object(self.scanner, 'is_attached', return_value=True):
            result = self.scanner.scan_exact_value(100, "invalid_type")
        self.assertFalse(result["success"])
        self.assertIn("不支持", result["message"])

    def test_scan_exact_value_pack(self):
        """验证值打包逻辑正确"""
        # int32: 999 -> b'\xe7\x03\x00\x00'
        from core.memory_scanner import MemoryScanner
        fmt, size = MemoryScanner.VALUE_TYPE_FORMATS["int32"]
        packed = struct.pack(fmt, 999)
        self.assertEqual(len(packed), 4)
        self.assertEqual(struct.unpack("<i", packed)[0], 999)

        # int16: 100 -> b'\x64\x00'
        fmt, size = MemoryScanner.VALUE_TYPE_FORMATS["int16"]
        packed = struct.pack(fmt, 100)
        self.assertEqual(len(packed), 2)
        self.assertEqual(struct.unpack("<h", packed)[0], 100)

        # float32: 3.14
        fmt, size = MemoryScanner.VALUE_TYPE_FORMATS["float32"]
        packed = struct.pack(fmt, 3.14)
        self.assertAlmostEqual(struct.unpack("<f", packed)[0], 3.14, places=2)


# ============================================================
# TestCase: 内部辅助方法
# ============================================================

class TestMemoryScannerInternals(unittest.TestCase):
    """测试内部辅助方法"""

    def setUp(self):
        from core.memory_scanner import MemoryScanner

        self.scanner = MemoryScanner()

    def test_get_page_base(self):
        """_get_page_base 正确对齐到页边界"""
        self.assertEqual(self.scanner._get_page_base(0x400000), 0x400000)
        self.assertEqual(self.scanner._get_page_base(0x400001), 0x400000)
        self.assertEqual(self.scanner._get_page_base(0x400FFF), 0x400000)
        self.assertEqual(self.scanner._get_page_base(0x401000), 0x401000)
        self.assertEqual(self.scanner._get_page_base(0), 0)

    def test_is_address_valid(self):
        """_is_address_valid 地址范围检查"""
        self.assertTrue(self.scanner._is_address_valid(0x400000))
        self.assertTrue(self.scanner._is_address_valid(0x10000))
        self.assertFalse(self.scanner._is_address_valid(0))
        self.assertFalse(self.scanner._is_address_valid(0xFFFFFFFF))

    def test_invalidate_cache_full(self):
        """_invalidate_cache 清空全部缓存"""
        self.scanner._memory_cache = {0x1000: b"data", 0x2000: b"data2"}
        self.scanner._invalidate_cache()
        self.assertEqual(self.scanner._memory_cache, {})

    def test_invalidate_cache_partial(self):
        """_invalidate_cache 部分清空缓存"""
        self.scanner._memory_cache = {
            0x0000: b"page0",
            0x1000: b"page1",
            0x2000: b"page2",
            0x3000: b"page3",
        }
        # 使 0x1500-0x2500 范围的缓存失效
        self.scanner._invalidate_cache(0x1500, 0x1000)
        self.assertNotIn(0x1000, self.scanner._memory_cache)
        self.assertNotIn(0x2000, self.scanner._memory_cache)
        self.assertIn(0x0000, self.scanner._memory_cache)
        self.assertIn(0x3000, self.scanner._memory_cache)

    def test_get_protection_name(self):
        """_get_protection_name 返回正确的保护属性名"""
        from core.memory_scanner import PAGE_READONLY, PAGE_READWRITE, PAGE_EXECUTE_READ

        name = self.scanner._get_protection_name(PAGE_READONLY)
        self.assertIn("READONLY", name)

        name = self.scanner._get_protection_name(PAGE_READWRITE)
        self.assertIn("READWRITE", name)

        name = self.scanner._get_protection_name(PAGE_EXECUTE_READ)
        self.assertIn("EXECUTE", name)

    def test_group_addresses_by_region(self):
        """_group_addresses_by_region 正确按区域分组地址"""
        addrs = [0x400000, 0x400001, 0x401000, 0x500000, 0x500004]
        groups = self.scanner._group_addresses_by_region(addrs)
        self.assertIn(0x400000, groups)
        self.assertIn(0x401000, groups)
        self.assertIn(0x500000, groups)
        self.assertEqual(len(groups[0x400000]), 2)
        self.assertEqual(len(groups[0x401000]), 1)
        self.assertEqual(len(groups[0x500000]), 2)

    def test_search_in_buffer_exact(self):
        """_search_in_buffer 精确匹配搜索"""
        data = b"\x00\x01\x02\xAA\xBB\xCC\x01\x02\xAA\xBB\xCC\x00"
        pattern = b"\xAA\xBB\xCC"
        results = []
        self.scanner._search_in_buffer(data, pattern, 0x400000, results)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["address"], 0x400003)
        self.assertEqual(results[1]["address"], 0x400008)

    def test_search_in_buffer_with_mask(self):
        """_search_in_buffer 带掩码搜索"""
        data = b"\xAA\x11\xCC\xAA\x22\xCC\xAA\x33\xDD"
        pattern = b"\xAA\x00\xCC"
        mask = "x?x"
        results = []
        self.scanner._search_in_buffer(data, pattern, 0x400000, results, mask=mask)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["address"], 0x400000)
        self.assertEqual(results[1]["address"], 0x400003)

    def test_search_in_buffer_alt_pattern(self):
        """_search_in_buffer 替代模式搜索"""
        data = b"hello\x00world\x00"
        pattern = b"hello"
        alt = b"hello\x00"
        results = []
        self.scanner._search_in_buffer(data, pattern, 0x400000, results, alt_pattern=alt)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["address"], 0x400000)
        self.assertEqual(results[1]["address"], 0x400000)


# ============================================================
# TestCase: 预设
# ============================================================

class TestMemoryScannerPresets(unittest.TestCase):
    """测试预设系统"""

    def setUp(self):
        from core.memory_scanner import MemoryScanner

        self.scanner = MemoryScanner()

    def test_preset_count(self):
        """内置预设数量"""
        self.assertGreaterEqual(len(self.scanner.BUILTIN_PRESETS), 15)

    def test_preset_values(self):
        """预设值类型正确"""
        self.assertEqual(self.scanner.BUILTIN_PRESETS["money"]["value_type"], "int32")
        self.assertEqual(self.scanner.BUILTIN_PRESETS["hp"]["value_type"], "int16")
        self.assertEqual(self.scanner.BUILTIN_PRESETS["strength"]["value_type"], "int8")
        self.assertEqual(self.scanner.BUILTIN_PRESETS["year"]["value_type"], "int16")
        self.assertEqual(self.scanner.BUILTIN_PRESETS["month"]["value_type"], "int8")

    def test_run_preset_unknown(self):
        """运行未知预设"""
        self.scanner._process_handle = 0x100
        with patch.object(self.scanner, 'is_attached', return_value=True):
            result = self.scanner.run_preset("unknown_preset")
        self.assertFalse(result["success"])
        self.assertIn("未知预设", result["message"])
        self.assertIn("available_presets", result)


# ============================================================
# TestCase: Hook 管理
# ============================================================

class TestMemoryScannerHooks(unittest.TestCase):
    """测试 Hook 管理"""

    def setUp(self):
        from core.memory_scanner import MemoryScanner

        self.scanner = MemoryScanner()

    def test_list_hooks_with_data(self):
        """列出已安装的 Hook"""
        self.scanner._hooks = {
            0x401000: {
                "address": 0x401000,
                "original_bytes": b"\x55\x8B\xEC\x51\x52",
                "hook_code": b"\xE9\x00\x00\x00\x00",
                "hook_type": "detour",
                "old_protect": 0x20,
                "installed_at": 1234567890.0,
            },
            0x402000: {
                "address": 0x402000,
                "original_bytes": b"\x00\x00\x00\x00",
                "original_pointer": 0x700000,
                "hook_code": 0x800000,
                "hook_type": "iat",
                "old_protect": 0x04,
                "installed_at": 1234567891.0,
            },
        }
        result = self.scanner.list_hooks()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["hooks"]), 2)
        self.assertEqual(result["hooks"][0]["hook_type"], "detour")
        self.assertEqual(result["hooks"][1]["hook_type"], "iat")

    def test_remove_hook_not_found(self):
        """移除不存在的 Hook"""
        self.scanner._process_handle = 0x100
        with patch.object(self.scanner, 'is_attached', return_value=True):
            result = self.scanner.remove_hook(0x999999)
        self.assertFalse(result["success"])
        self.assertIn("未安装", result["message"])


# ============================================================
# TestCase: 边界条件
# ============================================================

class TestMemoryScannerEdgeCases(unittest.TestCase):
    """测试边界条件"""

    def setUp(self):
        from core.memory_scanner import MemoryScanner

        self.scanner = MemoryScanner()

    def test_hook_type_unsupported(self):
        """不支持的 Hook 类型"""
        self.scanner._process_handle = 0x100
        with patch.object(self.scanner, 'is_attached', return_value=True):
            result = self.scanner.install_hook(0x401000, b"\x00", "unknown_hook_type")
        self.assertFalse(result["success"])
        self.assertIn("不支持", result["message"])

    def test_hook_detour_short_code(self):
        """Detour hook 代码太短"""
        self.scanner._process_handle = 0x100
        with patch.object(self.scanner, 'is_attached', return_value=True):
            result = self.scanner.install_hook(0x401000, b"\x90", "detour")
        self.assertFalse(result["success"])
        self.assertIn("至少 5 字节", result["message"])

    def test_hook_duplicate(self):
        """重复安装 Hook"""
        self.scanner._process_handle = 0x100
        self.scanner._hooks = {0x401000: {"address": 0x401000}}
        with patch.object(self.scanner, 'is_attached', return_value=True):
            result = self.scanner.install_hook(0x401000, b"\xE9\x00\x00\x00\x00", "detour")
        self.assertFalse(result["success"])
        self.assertIn("已安装", result["message"])

    def test_inject_code_empty(self):
        """注入空机器码"""
        self.scanner._process_handle = 0x100
        with patch.object(self.scanner, 'is_attached', return_value=True):
            result = self.scanner.inject_code(0, b"")
        self.assertFalse(result["success"])
        self.assertIn("不能为空", result["message"])

    def test_read_memory_invalid_address(self):
        """读取无效地址"""
        self.scanner._process_handle = 0x100
        with patch.object(self.scanner, 'is_attached', return_value=True):
            result = self.scanner.read_memory(0, 16)
        self.assertFalse(result["success"])
        self.assertIn("无效", result["message"])

    def test_read_memory_zero_size(self):
        """读取大小为 0"""
        self.scanner._process_handle = 0x100
        with patch.object(self.scanner, 'is_attached', return_value=True):
            result = self.scanner.read_memory(0x400000, 0)
        self.assertFalse(result["success"])
        self.assertIn("size", result["message"].lower())

    def test_read_memory_too_large(self):
        """读取超过 1MB"""
        self.scanner._process_handle = 0x100
        with patch.object(self.scanner, 'is_attached', return_value=True):
            result = self.scanner.read_memory(0x400000, 2 * 1024 * 1024)
        self.assertFalse(result["success"])
        self.assertIn("1MB", result["message"])

    def test_write_memory_empty_data(self):
        """写入空数据"""
        self.scanner._process_handle = 0x100
        with patch.object(self.scanner, 'is_attached', return_value=True):
            result = self.scanner.write_memory(0x400000, b"")
        self.assertFalse(result["success"])
        self.assertIn("不能为空", result["message"])

    def test_write_memory_invalid_address(self):
        """写入无效地址"""
        self.scanner._process_handle = 0x100
        with patch.object(self.scanner, 'is_attached', return_value=True):
            result = self.scanner.write_memory(0, b"\x90\x90")
        self.assertFalse(result["success"])
        self.assertIn("无效", result["message"])

    def test_next_scan_unsupported_filter(self):
        """不支持的过滤类型"""
        self.scanner._process_handle = 0x100
        # 提供扫描结果并 mock 内存读取，确保内部循环执行
        self.scanner._scan_results = {0x400000: b"\x01\x00\x00\x00"}
        with patch.object(self.scanner, 'is_attached', return_value=True):
            with patch.object(self.scanner, '_native_read_memory', return_value=b"\x99\x00\x00\x00"):
                result = self.scanner.next_scan("unsupported_filter")
        self.assertFalse(result["success"])
        self.assertIn("不支持", result["message"])

    def test_next_scan_no_results(self):
        """next_scan 在无扫描结果时调用"""
        self.scanner._process_handle = 0x100
        self.scanner._scan_results = {}
        with patch.object(self.scanner, 'is_attached', return_value=True):
            result = self.scanner.next_scan("increased")
        self.assertFalse(result["success"])
        self.assertIn("new_scan", result["message"].lower())


# ============================================================
# 运行入口
# ============================================================

if __name__ == "__main__":
    unittest.main()