"""
PE (Portable Executable) 结构解析器
用于解析三国群英传7的 32位 Windows PE 文件 (Sango7.exe)

功能:
- 解析 DOS Header, NT Headers, File Header, Optional Header
- 解析节表 (Section Headers)
- 解析 Data Directories (导出/导入/资源/重定位等)
- 解析导入表 (IAT) — 按 DLL 分组提取函数
- 解析导出表
- 解析重定位表
- 解析资源表
- IAT Hook 支持 (修改/恢复 IAT 中的函数地址)
- Code Cave 搜索 (利用节表精确确定搜索范围)
- 版本/特征检测

参考: Microsoft PE/COFF 规范
"""

import os
import struct
import logging
from typing import Dict, Optional, List, Tuple, Any

logger = logging.getLogger(__name__)

# ============================================================
# PE 结构常量
# ============================================================

IMAGE_DOS_SIGNATURE = 0x5A4D          # MZ
IMAGE_NT_SIGNATURE = 0x00004550       # PE\0\0
IMAGE_NT_OPTIONAL_HDR32_MAGIC = 0x10B  # PE32
IMAGE_NT_OPTIONAL_HDR64_MAGIC = 0x20B  # PE32+

# Data Directory 索引
IMAGE_DIRECTORY_ENTRY_EXPORT = 0
IMAGE_DIRECTORY_ENTRY_IMPORT = 1
IMAGE_DIRECTORY_ENTRY_RESOURCE = 2
IMAGE_DIRECTORY_ENTRY_EXCEPTION = 3
IMAGE_DIRECTORY_ENTRY_SECURITY = 4
IMAGE_DIRECTORY_ENTRY_BASERELOC = 5
IMAGE_DIRECTORY_ENTRY_DEBUG = 6
IMAGE_DIRECTORY_ENTRY_ARCHITECTURE = 7
IMAGE_DIRECTORY_ENTRY_GLOBALPTR = 8
IMAGE_DIRECTORY_ENTRY_TLS = 9
IMAGE_DIRECTORY_ENTRY_LOAD_CONFIG = 10
IMAGE_DIRECTORY_ENTRY_BOUND_IMPORT = 11
IMAGE_DIRECTORY_ENTRY_IAT = 12
IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT = 13
IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR = 14

# Data Directory 名称映射
DATA_DIRECTORY_NAMES = {
    0: "EXPORT",
    1: "IMPORT",
    2: "RESOURCE",
    3: "EXCEPTION",
    4: "SECURITY",
    5: "BASERELOC",
    6: "DEBUG",
    7: "ARCHITECTURE",
    8: "GLOBALPTR",
    9: "TLS",
    10: "LOAD_CONFIG",
    11: "BOUND_IMPORT",
    12: "IAT",
    13: "DELAY_IMPORT",
    14: "COM_DESCRIPTOR",
    15: "RESERVED",
}

# Section Characteristics
IMAGE_SCN_CNT_CODE = 0x00000020
IMAGE_SCN_CNT_INITIALIZED_DATA = 0x00000040
IMAGE_SCN_CNT_UNINITIALIZED_DATA = 0x00000080
IMAGE_SCN_MEM_EXECUTE = 0x20000000
IMAGE_SCN_MEM_READ = 0x40000000
IMAGE_SCN_MEM_WRITE = 0x80000000
IMAGE_SCN_MEM_SHARED = 0x10000000

# Subsystem 值
SUBSYSTEM_NAMES = {
    0: "UNKNOWN",
    1: "NATIVE",
    2: "WINDOWS_GUI",
    3: "WINDOWS_CUI",
    5: "OS2_CUI",
    7: "POSIX_CUI",
    9: "WINDOWS_CE_GUI",
    10: "EFI_APPLICATION",
    11: "EFI_BOOT_SERVICE_DRIVER",
    12: "EFI_RUNTIME_DRIVER",
    13: "EFI_ROM",
    14: "XBOX",
    16: "WINDOWS_BOOT_APPLICATION",
}

# Machine 类型
MACHINE_NAMES = {
    0x014C: "I386 (x86)",
    0x0200: "IA64",
    0x8664: "AMD64 (x64)",
    0x01C0: "ARM",
    0x01C4: "ARM64",
    0xAA64: "ARM64 (EC)",
}

# IMAGE_IMPORT_DESCRIPTOR 大小
IMAGE_IMPORT_DESCRIPTOR_SIZE = 20

# IMAGE_THUNK_DATA 大小 (32位)
IMAGE_THUNK_DATA_SIZE = 4

# IMAGE_EXPORT_DIRECTORY 大小
IMAGE_EXPORT_DIRECTORY_SIZE = 40

# IMAGE_BASE_RELOCATION 块头大小
IMAGE_BASE_RELOCATION_HEADER_SIZE = 8

# IMAGE_RESOURCE_DIRECTORY 大小
IMAGE_RESOURCE_DIRECTORY_SIZE = 16
IMAGE_RESOURCE_DIRECTORY_ENTRY_SIZE = 8


class PeAnalyzer:
    """
    PE (Portable Executable) 结构解析器

    解析 32位 Windows PE 文件 (PE32) 的完整结构，
    包括 DOS Header、NT Headers、节表、导入表、导出表、
    重定位表、资源表等。支持 IAT Hook 和 Code Cave 搜索。

    所有方法返回 dict 格式，包含 success 字段。
    """

    # ============================================================
    # 初始化
    # ============================================================

    def __init__(self, exe_path: str = None):
        """
        初始化 PE 解析器

        参数:
            exe_path: PE 文件路径 (如 Sango7.exe)
        """
        self.exe_path = exe_path
        self._exe_data: Optional[bytes] = None

        # 解析后的缓存结构
        self._dos_header: Optional[dict] = None
        self._file_header: Optional[dict] = None
        self._optional_header: Optional[dict] = None
        self._nt_headers: Optional[dict] = None
        self._sections: Optional[List[dict]] = None
        self._data_directories: Optional[List[dict]] = None
        self._import_table: Optional[dict] = None
        self._export_table: Optional[dict] = None
        self._relocations: Optional[dict] = None
        self._resource_table: Optional[dict] = None

        # PE 头偏移 (e_lfanew)
        self._pe_offset: int = 0

        # IAT Hook 记录
        self._iat_hooks: Dict[str, dict] = {}

        if exe_path:
            self._load_and_parse()

    def _load_and_parse(self):
        """加载文件并解析 PE 结构"""
        if not self._load_exe():
            return
        self._pe_offset = self._read_pe_offset()
        if self._pe_offset == 0:
            return
        self._parse_all()

    def _load_exe(self) -> bool:
        """加载 EXE 文件到内存"""
        if self._exe_data is not None:
            return True
        if not self.exe_path or not os.path.isfile(self.exe_path):
            return False
        try:
            with open(self.exe_path, "rb") as f:
                self._exe_data = f.read()
            return True
        except (IOError, OSError) as e:
            logger.error("加载 EXE 失败: %s", e)
            return False

    def _parse_all(self):
        """解析所有 PE 结构"""
        self.parse_dos_header()
        self.parse_nt_headers()
        self.parse_file_header()
        self.parse_optional_header()
        self.parse_section_headers()
        self.parse_data_directories()

    # ============================================================
    # 工具方法
    # ============================================================

    def _read_at(self, offset: int, size: int) -> Optional[bytes]:
        """从 EXE 数据中读取指定偏移的字节"""
        if self._exe_data is None:
            return None
        if offset < 0 or offset + size > len(self._exe_data):
            return None
        return self._exe_data[offset:offset + size]

    def _read_pe_offset(self) -> int:
        """从 DOS Header 读取 e_lfanew (PE 头偏移)"""
        data = self._read_at(0x3C, 4)
        if data is None:
            return 0
        return struct.unpack("<I", data)[0]

    def _rva_to_offset(self, rva: int) -> int:
        """
        将 RVA (Relative Virtual Address) 转换为文件偏移

        在 PE 文件中，RVA 是相对于 ImageBase 的虚拟地址。
        需要根据节表将 RVA 映射到文件中的实际偏移。

        参数:
            rva: 相对虚拟地址

        返回:
            文件偏移，如果 RVA 无效则返回 0
        """
        if self._sections is None:
            return 0
        for section in self._sections:
            sec_va = section.get("VirtualAddress", 0)
            sec_size = section.get("VirtualSize", 0)
            sec_raw = section.get("PointerToRawData", 0)
            if sec_va <= rva < sec_va + sec_size:
                return rva - sec_va + sec_raw
        return 0

    def _read_string_at_rva(self, rva: int) -> Optional[str]:
        """
        从 RVA 指向的位置读取以 null 结尾的字符串

        参数:
            rva: 字符串的 RVA

        返回:
            解码后的字符串，如果无法读取则返回 None
        """
        offset = self._rva_to_offset(rva)
        if offset == 0:
            return None
        try:
            end = self._exe_data.index(b"\x00", offset)
            return self._exe_data[offset:end].decode("ascii", errors="replace")
        except (ValueError, IndexError):
            return None

    def _read_dword_at_rva(self, rva: int) -> Optional[int]:
        """从 RVA 位置读取一个 DWORD (4 字节)"""
        offset = self._rva_to_offset(rva)
        if offset == 0:
            return None
        data = self._read_at(offset, 4)
        if data is None:
            return None
        return struct.unpack("<I", data)[0]

    def _is_pe32(self) -> bool:
        """检查是否为 PE32 格式"""
        if self._optional_header:
            return self._optional_header.get("Magic") == IMAGE_NT_OPTIONAL_HDR32_MAGIC
        return False

    def set_exe_path(self, exe_path: str):
        """设置新的 EXE 路径并重新解析"""
        self.exe_path = exe_path
        self._exe_data = None
        self._reset_cache()
        self._load_and_parse()

    def _reset_cache(self):
        """重置所有解析缓存"""
        self._dos_header = None
        self._file_header = None
        self._optional_header = None
        self._nt_headers = None
        self._sections = None
        self._data_directories = None
        self._import_table = None
        self._export_table = None
        self._relocations = None
        self._resource_table = None
        self._pe_offset = 0
        self._iat_hooks = {}

    def is_valid_pe(self) -> bool:
        """检查文件是否为有效的 PE 文件"""
        if self._exe_data is None:
            return False
        if len(self._exe_data) < 64:
            return False
        # 检查 DOS 签名
        dos_sig = struct.unpack("<H", self._exe_data[0:2])[0]
        if dos_sig != IMAGE_DOS_SIGNATURE:
            return False
        # 检查 PE 签名
        pe_sig_data = self._read_at(self._pe_offset, 4)
        if pe_sig_data is None:
            return False
        pe_sig = struct.unpack("<I", pe_sig_data)[0]
        return pe_sig == IMAGE_NT_SIGNATURE

    # ============================================================
    # 1. DOS Header 解析
    # ============================================================

    def parse_dos_header(self) -> dict:
        """
        解析 DOS Header (IMAGE_DOS_HEADER)

        关键字段:
        - e_magic: 魔数 "MZ" (0x5A4D)
        - e_lfanew: PE 头偏移 (位于 0x3C)

        返回:
            {success, e_magic, e_magic_str, e_lfanew, e_lfanew_hex, ...}
        """
        if self._dos_header is not None:
            return self._dos_header

        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        if len(self._exe_data) < 64:
            return {"success": False, "message": "文件太小，无法解析 DOS Header"}

        try:
            dos_data = self._exe_data[0:64]

            e_magic = struct.unpack_from("<H", dos_data, 0)[0]
            # 解析常用 DOS Header 字段
            e_cblp = struct.unpack_from("<H", dos_data, 2)[0]
            e_cp = struct.unpack_from("<H", dos_data, 4)[0]
            e_crlc = struct.unpack_from("<H", dos_data, 6)[0]
            e_cparhdr = struct.unpack_from("<H", dos_data, 8)[0]
            e_minalloc = struct.unpack_from("<H", dos_data, 10)[0]
            e_maxalloc = struct.unpack_from("<H", dos_data, 12)[0]
            e_ss = struct.unpack_from("<H", dos_data, 14)[0]
            e_sp = struct.unpack_from("<H", dos_data, 16)[0]
            e_csum = struct.unpack_from("<H", dos_data, 18)[0]
            e_ip = struct.unpack_from("<H", dos_data, 20)[0]
            e_cs = struct.unpack_from("<H", dos_data, 22)[0]
            e_lfarlc = struct.unpack_from("<H", dos_data, 24)[0]
            e_ovno = struct.unpack_from("<H", dos_data, 26)[0]
            # 保留字段 e_res[4]
            e_oemid = struct.unpack_from("<H", dos_data, 36)[0]
            e_oeminfo = struct.unpack_from("<H", dos_data, 38)[0]
            # 保留字段 e_res2[10]
            e_lfanew = struct.unpack_from("<I", dos_data, 60)[0]

            is_valid = e_magic == IMAGE_DOS_SIGNATURE

            self._dos_header = {
                "success": True,
                "e_magic": e_magic,
                "e_magic_str": "MZ" if is_valid else "INVALID",
                "e_magic_hex": "0x{:04X}".format(e_magic),
                "e_lfanew": e_lfanew,
                "e_lfanew_hex": "0x{:X}".format(e_lfanew),
                "e_cblp": e_cblp,
                "e_cp": e_cp,
                "e_crlc": e_crlc,
                "e_cparhdr": e_cparhdr,
                "e_minalloc": e_minalloc,
                "e_maxalloc": e_maxalloc,
                "e_ss": e_ss,
                "e_sp": e_sp,
                "e_csum": e_csum,
                "e_ip": e_ip,
                "e_cs": e_cs,
                "e_lfarlc": e_lfarlc,
                "e_ovno": e_ovno,
                "e_oemid": e_oemid,
                "e_oeminfo": e_oeminfo,
                "is_valid": is_valid,
                "size": 64,
            }
            self._pe_offset = e_lfanew
            return self._dos_header

        except (struct.error, IndexError) as e:
            return {"success": False, "message": "解析 DOS Header 失败: {}".format(e)}

    # ============================================================
    # 2. NT Headers 解析
    # ============================================================

    def parse_nt_headers(self) -> dict:
        """
        解析 NT Headers (IMAGE_NT_HEADERS)

        包含:
        - Signature (PE\0\0)
        - FileHeader (IMAGE_FILE_HEADER)
        - OptionalHeader (IMAGE_OPTIONAL_HEADER32)

        返回:
            {success, Signature, Signature_hex, pe_offset, ...}
        """
        if self._nt_headers is not None:
            return self._nt_headers

        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        pe_offset = self._pe_offset
        sig_data = self._read_at(pe_offset, 4)
        if sig_data is None:
            return {"success": False, "message": "无法读取 NT Headers"}

        signature = struct.unpack("<I", sig_data)[0]
        is_valid = signature == IMAGE_NT_SIGNATURE

        self._nt_headers = {
            "success": True,
            "Signature": signature,
            "Signature_hex": "0x{:08X}".format(signature),
            "Signature_str": "PE\\0\\0" if is_valid else "INVALID",
            "is_valid": is_valid,
            "pe_offset": pe_offset,
            "pe_offset_hex": "0x{:X}".format(pe_offset),
        }
        return self._nt_headers

    # ============================================================
    # 3. File Header 解析
    # ============================================================

    def parse_file_header(self) -> dict:
        """
        解析 COFF File Header (IMAGE_FILE_HEADER)

        位于 e_lfanew + 4 处，共 20 字节

        返回:
            {success, Machine, MachineName, NumberOfSections,
             TimeDateStamp, SizeOfOptionalHeader, Characteristics, ...}
        """
        if self._file_header is not None:
            return self._file_header

        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        # File Header 位于 PE Signature 之后 (+4)
        fh_offset = self._pe_offset + 4
        data = self._read_at(fh_offset, 20)
        if data is None:
            return {"success": False, "message": "无法读取 File Header"}

        try:
            machine = struct.unpack_from("<H", data, 0)[0]
            num_sections = struct.unpack_from("<H", data, 2)[0]
            time_date_stamp = struct.unpack_from("<I", data, 4)[0]
            ptr_sym_table = struct.unpack_from("<I", data, 8)[0]
            num_symbols = struct.unpack_from("<I", data, 12)[0]
            size_opt_header = struct.unpack_from("<H", data, 16)[0]
            characteristics = struct.unpack_from("<H", data, 18)[0]

            # 解析 Characteristics
            char_flags = self._parse_characteristics(characteristics)

            self._file_header = {
                "success": True,
                "Machine": machine,
                "Machine_hex": "0x{:04X}".format(machine),
                "MachineName": MACHINE_NAMES.get(machine, "UNKNOWN"),
                "NumberOfSections": num_sections,
                "TimeDateStamp": time_date_stamp,
                "TimeDateStamp_hex": "0x{:08X}".format(time_date_stamp),
                "PointerToSymbolTable": ptr_sym_table,
                "NumberOfSymbols": num_symbols,
                "SizeOfOptionalHeader": size_opt_header,
                "Characteristics": characteristics,
                "Characteristics_hex": "0x{:04X}".format(characteristics),
                "CharacteristicsFlags": char_flags,
                "is_exe": bool(characteristics & 0x0002),
                "is_dll": bool(characteristics & 0x2000),
                "is_32bit": bool(characteristics & 0x0100),
                "size": 20,
            }
            return self._file_header

        except (struct.error, IndexError) as e:
            return {"success": False, "message": "解析 File Header 失败: {}".format(e)}

    @staticmethod
    def _parse_characteristics(characteristics: int) -> List[str]:
        """解析 COFF Characteristics 位标志"""
        flags = []
        if characteristics & 0x0001:
            flags.append("RELOCS_STRIPPED")
        if characteristics & 0x0002:
            flags.append("EXECUTABLE_IMAGE")
        if characteristics & 0x0004:
            flags.append("LINE_NUMS_STRIPPED")
        if characteristics & 0x0008:
            flags.append("LOCAL_SYMS_STRIPPED")
        if characteristics & 0x0010:
            flags.append("AGGRESSIVE_WS_TRIM")
        if characteristics & 0x0020:
            flags.append("LARGE_ADDRESS_AWARE")
        if characteristics & 0x0080:
            flags.append("BYTES_REVERSED_LO")
        if characteristics & 0x0100:
            flags.append("32BIT_MACHINE")
        if characteristics & 0x0200:
            flags.append("DEBUG_STRIPPED")
        if characteristics & 0x0400:
            flags.append("REMOVABLE_RUN_FROM_SWAP")
        if characteristics & 0x0800:
            flags.append("NET_RUN_FROM_SWAP")
        if characteristics & 0x1000:
            flags.append("SYSTEM")
        if characteristics & 0x2000:
            flags.append("DLL")
        if characteristics & 0x4000:
            flags.append("UP_SYSTEM_ONLY")
        if characteristics & 0x8000:
            flags.append("BYTES_REVERSED_HI")
        return flags

    # ============================================================
    # 4. Optional Header 解析
    # ============================================================

    def parse_optional_header(self) -> dict:
        """
        解析 Optional Header (IMAGE_OPTIONAL_HEADER32)

        位于 File Header 之后，大小由 SizeOfOptionalHeader 指定。
        对于 PE32，Magic = 0x10B。

        返回:
            {success, Magic, AddressOfEntryPoint, ImageBase,
             SectionAlignment, FileAlignment, SizeOfImage,
             Subsystem, DllCharacteristics, ...}
        """
        if self._optional_header is not None:
            return self._optional_header

        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        # Optional Header 位于 File Header 之后
        oh_offset = self._pe_offset + 4 + 20  # Signature(4) + FileHeader(20)

        # 先读取 Magic 判断是 PE32 还是 PE32+
        magic_data = self._read_at(oh_offset, 2)
        if magic_data is None:
            return {"success": False, "message": "无法读取 Optional Header Magic"}

        magic = struct.unpack("<H", magic_data)[0]

        if magic == IMAGE_NT_OPTIONAL_HDR32_MAGIC:
            return self._parse_optional_header_pe32(oh_offset)
        elif magic == IMAGE_NT_OPTIONAL_HDR64_MAGIC:
            return {"success": False, "message": "PE32+ (x64) 格式当前不支持"}
        else:
            return {"success": False, "message": "未知的 Optional Header Magic: 0x{:04X}".format(magic)}

    def _parse_optional_header_pe32(self, offset: int) -> dict:
        """解析 PE32 Optional Header"""
        data = self._read_at(offset, 224)
        if data is None:
            return {"success": False, "message": "无法读取 PE32 Optional Header"}

        try:
            magic = struct.unpack_from("<H", data, 0)[0]
            major_linker = data[2]
            minor_linker = data[3]
            size_of_code = struct.unpack_from("<I", data, 4)[0]
            size_of_init_data = struct.unpack_from("<I", data, 8)[0]
            size_of_uninit_data = struct.unpack_from("<I", data, 12)[0]
            address_of_entry = struct.unpack_from("<I", data, 16)[0]
            base_of_code = struct.unpack_from("<I", data, 20)[0]
            base_of_data = struct.unpack_from("<I", data, 24)[0]
            image_base = struct.unpack_from("<I", data, 28)[0]
            section_align = struct.unpack_from("<I", data, 32)[0]
            file_align = struct.unpack_from("<I", data, 36)[0]
            major_os = struct.unpack_from("<H", data, 40)[0]
            minor_os = struct.unpack_from("<H", data, 42)[0]
            major_image = struct.unpack_from("<H", data, 44)[0]
            minor_image = struct.unpack_from("<H", data, 46)[0]
            major_subsys = struct.unpack_from("<H", data, 48)[0]
            minor_subsys = struct.unpack_from("<H", data, 50)[0]
            win32_version = struct.unpack_from("<I", data, 52)[0]
            size_of_image = struct.unpack_from("<I", data, 56)[0]
            size_of_headers = struct.unpack_from("<I", data, 60)[0]
            checksum = struct.unpack_from("<I", data, 64)[0]
            subsystem = struct.unpack_from("<H", data, 68)[0]
            dll_chars = struct.unpack_from("<H", data, 70)[0]
            size_of_stack_reserve = struct.unpack_from("<I", data, 72)[0]
            size_of_stack_commit = struct.unpack_from("<I", data, 76)[0]
            size_of_heap_reserve = struct.unpack_from("<I", data, 80)[0]
            size_of_heap_commit = struct.unpack_from("<I", data, 84)[0]
            loader_flags = struct.unpack_from("<I", data, 88)[0]
            num_rva_and_sizes = struct.unpack_from("<I", data, 92)[0]

            # 解析 DLL Characteristics
            dll_char_flags = self._parse_dll_characteristics(dll_chars)

            self._optional_header = {
                "success": True,
                "Magic": magic,
                "Magic_hex": "0x{:04X}".format(magic),
                "MagicName": "PE32",
                "MajorLinkerVersion": major_linker,
                "MinorLinkerVersion": minor_linker,
                "LinkerVersion": "{}.{}".format(major_linker, minor_linker),
                "SizeOfCode": size_of_code,
                "SizeOfCode_hex": "0x{:X}".format(size_of_code),
                "SizeOfInitializedData": size_of_init_data,
                "SizeOfUninitializedData": size_of_uninit_data,
                "AddressOfEntryPoint": address_of_entry,
                "AddressOfEntryPoint_hex": "0x{:X}".format(address_of_entry),
                "BaseOfCode": base_of_code,
                "BaseOfCode_hex": "0x{:X}".format(base_of_code),
                "BaseOfData": base_of_data,
                "ImageBase": image_base,
                "ImageBase_hex": "0x{:X}".format(image_base),
                "SectionAlignment": section_align,
                "SectionAlignment_hex": "0x{:X}".format(section_align),
                "FileAlignment": file_align,
                "FileAlignment_hex": "0x{:X}".format(file_align),
                "MajorOperatingSystemVersion": major_os,
                "MinorOperatingSystemVersion": minor_os,
                "OSVersion": "{}.{}".format(major_os, minor_os),
                "MajorImageVersion": major_image,
                "MinorImageVersion": minor_image,
                "ImageVersion": "{}.{}".format(major_image, minor_image),
                "MajorSubsystemVersion": major_subsys,
                "MinorSubsystemVersion": minor_subsys,
                "SubsystemVersion": "{}.{}".format(major_subsys, minor_subsys),
                "Win32VersionValue": win32_version,
                "SizeOfImage": size_of_image,
                "SizeOfImage_hex": "0x{:X}".format(size_of_image),
                "SizeOfHeaders": size_of_headers,
                "SizeOfHeaders_hex": "0x{:X}".format(size_of_headers),
                "CheckSum": checksum,
                "CheckSum_hex": "0x{:X}".format(checksum),
                "Subsystem": subsystem,
                "Subsystem_hex": "0x{:04X}".format(subsystem),
                "SubsystemName": SUBSYSTEM_NAMES.get(subsystem, "UNKNOWN"),
                "DllCharacteristics": dll_chars,
                "DllCharacteristics_hex": "0x{:04X}".format(dll_chars),
                "DllCharacteristicsFlags": dll_char_flags,
                "SizeOfStackReserve": size_of_stack_reserve,
                "SizeOfStackReserve_hex": "0x{:X}".format(size_of_stack_reserve),
                "SizeOfStackCommit": size_of_stack_commit,
                "SizeOfHeapReserve": size_of_heap_reserve,
                "SizeOfHeapCommit": size_of_heap_commit,
                "LoaderFlags": loader_flags,
                "NumberOfRvaAndSizes": num_rva_and_sizes,
                "is_gui": subsystem == 2,
                "is_console": subsystem == 3,
                "is_dll": bool(dll_chars & 0x2000),
                "size": 224,
            }
            return self._optional_header

        except (struct.error, IndexError) as e:
            return {"success": False, "message": "解析 Optional Header 失败: {}".format(e)}

    @staticmethod
    def _parse_dll_characteristics(dll_chars: int) -> List[str]:
        """解析 DLL Characteristics 位标志"""
        flags = []
        if dll_chars & 0x0020:
            flags.append("HIGH_ENTROPY_VA")
        if dll_chars & 0x0040:
            flags.append("DYNAMIC_BASE (ASLR)")
        if dll_chars & 0x0080:
            flags.append("FORCE_INTEGRITY")
        if dll_chars & 0x0100:
            flags.append("NX_COMPAT (DEP)")
        if dll_chars & 0x0200:
            flags.append("NO_ISOLATION")
        if dll_chars & 0x0400:
            flags.append("NO_SEH")
        if dll_chars & 0x0800:
            flags.append("NO_BIND")
        if dll_chars & 0x1000:
            flags.append("APPCONTAINER")
        if dll_chars & 0x2000:
            flags.append("WDM_DRIVER")
        if dll_chars & 0x4000:
            flags.append("GUARD_CF")
        if dll_chars & 0x8000:
            flags.append("TERMINAL_SERVER_AWARE")
        return flags

    # ============================================================
    # 5. 节表 (Section Headers) 解析
    # ============================================================

    def parse_section_headers(self) -> dict:
        """
        解析所有节表 (IMAGE_SECTION_HEADER)

        每个节表头 40 字节，包含节的名称、虚拟地址、虚拟大小、
        原始大小、原始偏移、以及 Characteristics 标志。

        返回:
            {success, section_count, sections: [{Name, VirtualAddress, ...}], ...}
        """
        if self._sections is not None:
            return {
                "success": True,
                "section_count": len(self._sections),
                "sections": self._sections,
            }

        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        if self._file_header is None:
            self.parse_file_header()

        if self._file_header is None or not self._file_header.get("success"):
            return {"success": False, "message": "需要先解析 File Header"}

        num_sections = self._file_header.get("NumberOfSections", 0)
        if num_sections == 0:
            return {"success": False, "message": "NumberOfSections 为 0"}

        # 节表起始位置 = pe_offset + 4(签名) + 20(FileHeader) + SizeOfOptionalHeader
        opt_header_size = self._file_header.get("SizeOfOptionalHeader", 224)
        section_offset = self._pe_offset + 4 + 20 + opt_header_size

        self._sections = []
        try:
            for i in range(num_sections):
                sec_off = section_offset + i * 40
                data = self._read_at(sec_off, 40)
                if data is None:
                    break

                # Section Name 是 8 字节的 UTF-8 字符串，不以 null 结尾
                name_raw = data[0:8]
                name = name_raw.rstrip(b"\x00").decode("ascii", errors="replace")

                virtual_size = struct.unpack_from("<I", data, 8)[0]
                virtual_address = struct.unpack_from("<I", data, 12)[0]
                size_of_raw = struct.unpack_from("<I", data, 16)[0]
                ptr_raw = struct.unpack_from("<I", data, 20)[0]
                ptr_reloc = struct.unpack_from("<I", data, 24)[0]
                ptr_linenum = struct.unpack_from("<I", data, 28)[0]
                num_reloc = struct.unpack_from("<H", data, 32)[0]
                num_linenum = struct.unpack_from("<H", data, 34)[0]
                characteristics = struct.unpack_from("<I", data, 36)[0]

                sec_flags = self._parse_section_characteristics(characteristics)

                section = {
                    "Name": name,
                    "VirtualSize": virtual_size,
                    "VirtualSize_hex": "0x{:X}".format(virtual_size),
                    "VirtualAddress": virtual_address,
                    "VirtualAddress_hex": "0x{:X}".format(virtual_address),
                    "SizeOfRawData": size_of_raw,
                    "SizeOfRawData_hex": "0x{:X}".format(size_of_raw),
                    "PointerToRawData": ptr_raw,
                    "PointerToRawData_hex": "0x{:X}".format(ptr_raw),
                    "PointerToRelocations": ptr_reloc,
                    "PointerToLinenumbers": ptr_linenum,
                    "NumberOfRelocations": num_reloc,
                    "NumberOfLinenumbers": num_linenum,
                    "Characteristics": characteristics,
                    "Characteristics_hex": "0x{:08X}".format(characteristics),
                    "CharacteristicsFlags": sec_flags,
                    "is_code": bool(characteristics & IMAGE_SCN_CNT_CODE),
                    "is_executable": bool(characteristics & IMAGE_SCN_MEM_EXECUTE),
                    "is_readable": bool(characteristics & IMAGE_SCN_MEM_READ),
                    "is_writable": bool(characteristics & IMAGE_SCN_MEM_WRITE),
                    "index": i,
                    "file_range_start": ptr_raw,
                    "file_range_end": ptr_raw + size_of_raw,
                    "virtual_range_start": virtual_address,
                    "virtual_range_end": virtual_address + virtual_size,
                }
                self._sections.append(section)

            return {
                "success": True,
                "section_count": len(self._sections),
                "sections": self._sections,
            }
        except (struct.error, IndexError) as e:
            return {"success": False, "message": "解析节表失败: {}".format(e)}

    @staticmethod
    def _parse_section_characteristics(characteristics: int) -> List[str]:
        """解析 Section Characteristics 位标志"""
        flags = []
        if characteristics & 0x00000008:
            flags.append("TYPE_NO_PAD")
        if characteristics & IMAGE_SCN_CNT_CODE:
            flags.append("CNT_CODE")
        if characteristics & IMAGE_SCN_CNT_INITIALIZED_DATA:
            flags.append("CNT_INITIALIZED_DATA")
        if characteristics & IMAGE_SCN_CNT_UNINITIALIZED_DATA:
            flags.append("CNT_UNINITIALIZED_DATA")
        if characteristics & 0x00000100:
            flags.append("LNK_OTHER")
        if characteristics & 0x00000200:
            flags.append("LNK_INFO")
        if characteristics & 0x00000800:
            flags.append("LNK_REMOVE")
        if characteristics & 0x00001000:
            flags.append("LNK_COMDAT")
        if characteristics & 0x00004000:
            flags.append("GPREL")
        if characteristics & 0x00008000:
            flags.append("MEM_PURGEABLE")
        if characteristics & 0x00020000:
            flags.append("MEM_16BIT")
        if characteristics & 0x00040000:
            flags.append("MEM_LOCKED")
        if characteristics & 0x00080000:
            flags.append("MEM_PRELOAD")
        if characteristics & 0x00100000:
            flags.append("ALIGN_1BYTES")
        if characteristics & 0x00200000:
            flags.append("ALIGN_2BYTES")
        if characteristics & 0x00300000:
            flags.append("ALIGN_4BYTES")
        if characteristics & 0x00400000:
            flags.append("ALIGN_8BYTES")
        if characteristics & 0x00500000:
            flags.append("ALIGN_16BYTES")
        if characteristics & 0x00600000:
            flags.append("ALIGN_32BYTES")
        if characteristics & 0x00700000:
            flags.append("ALIGN_64BYTES")
        if characteristics & 0x00800000:
            flags.append("ALIGN_128BYTES")
        if characteristics & 0x00900000:
            flags.append("ALIGN_256BYTES")
        if characteristics & 0x00A00000:
            flags.append("ALIGN_512BYTES")
        if characteristics & 0x00B00000:
            flags.append("ALIGN_1024BYTES")
        if characteristics & 0x00C00000:
            flags.append("ALIGN_2048BYTES")
        if characteristics & 0x00D00000:
            flags.append("ALIGN_4096BYTES")
        if characteristics & 0x00E00000:
            flags.append("ALIGN_8192BYTES")
        if characteristics & 0x01000000:
            flags.append("LNK_NRELOC_OVFL")
        if characteristics & IMAGE_SCN_MEM_SHARED:
            flags.append("MEM_SHARED")
        if characteristics & IMAGE_SCN_MEM_EXECUTE:
            flags.append("MEM_EXECUTE")
        if characteristics & IMAGE_SCN_MEM_READ:
            flags.append("MEM_READ")
        if characteristics & IMAGE_SCN_MEM_WRITE:
            flags.append("MEM_WRITE")
        return flags

    # ============================================================
    # 6. Data Directories 解析
    # ============================================================

    def parse_data_directories(self) -> dict:
        """
        解析 16 个 Data Directory 条目

        每个条目 8 字节 (VirtualAddress + Size)，
        位于 Optional Header 末尾。

        返回:
            {success, count, directories: [{index, name, VirtualAddress, Size, ...}]}
        """
        if self._data_directories is not None:
            return {
                "success": True,
                "count": len(self._data_directories),
                "directories": self._data_directories,
            }

        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        # Data Directories 位于 Optional Header 末尾
        # 偏移 = pe_offset + 4 + 20 + 96 (Standard fields before DataDirectory)
        # DataDirectory 数组从 Optional Header 偏移 + 96 处开始
        oh_offset = self._pe_offset + 4 + 20
        dd_offset = oh_offset + 96

        # 读取 NumberOfRvaAndSizes
        num_rva_raw = self._read_at(oh_offset + 92, 4)
        num_rva = 16
        if num_rva_raw:
            num_rva = struct.unpack("<I", num_rva_raw)[0]

        self._data_directories = []
        try:
            for i in range(16):
                dd_off = dd_offset + i * 8
                data = self._read_at(dd_off, 8)
                if data is None:
                    break

                va = struct.unpack_from("<I", data, 0)[0]
                size = struct.unpack_from("<I", data, 4)[0]

                self._data_directories.append({
                    "index": i,
                    "name": DATA_DIRECTORY_NAMES.get(i, "UNKNOWN"),
                    "VirtualAddress": va,
                    "VirtualAddress_hex": "0x{:X}".format(va),
                    "Size": size,
                    "Size_hex": "0x{:X}".format(size),
                    "is_present": va != 0 and size != 0,
                })

            return {
                "success": True,
                "count": len(self._data_directories),
                "directories": self._data_directories,
            }
        except (struct.error, IndexError) as e:
            return {"success": False, "message": "解析 Data Directories 失败: {}".format(e)}

    def _get_data_directory(self, entry_index: int) -> Optional[dict]:
        """获取指定索引的 Data Directory 条目"""
        if self._data_directories is None:
            self.parse_data_directories()
        if self._data_directories is None:
            return None
        if entry_index < len(self._data_directories):
            return self._data_directories[entry_index]
        return None

    # ============================================================
    # 7. 导入表 (Import Table) 解析
    # ============================================================

    def parse_import_table(self) -> dict:
        """
        解析完整的导入表 (IMAGE_IMPORT_DESCRIPTOR)

        遍历所有导入 DLL，提取每个 DLL 的导入函数名。
        支持按名称导入和按序号导入。

        返回:
            {success, dll_count, total_imports, imports: {dll_name: {functions: [...]}}}
        """
        if self._import_table is not None:
            return self._import_table

        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        import_dir = self._get_data_directory(IMAGE_DIRECTORY_ENTRY_IMPORT)
        if import_dir is None or not import_dir.get("is_present"):
            return {"success": False, "message": "没有导入表"}

        import_rva = import_dir["VirtualAddress"]
        imports = {}
        total_imports = 0

        try:
            idx = 0
            while True:
                # 每个 IMAGE_IMPORT_DESCRIPTOR 20 字节
                desc_offset = self._rva_to_offset(import_rva + idx * IMAGE_IMPORT_DESCRIPTOR_SIZE)
                if desc_offset == 0:
                    break

                desc_data = self._read_at(desc_offset, IMAGE_IMPORT_DESCRIPTOR_SIZE)
                if desc_data is None:
                    break

                # 检查是否到达终止条目 (全零)
                original_first_thunk = struct.unpack_from("<I", desc_data, 0)[0]
                time_date_stamp = struct.unpack_from("<I", desc_data, 4)[0]
                forwarder_chain = struct.unpack_from("<I", desc_data, 8)[0]
                name_rva = struct.unpack_from("<I", desc_data, 12)[0]
                first_thunk = struct.unpack_from("<I", desc_data, 16)[0]

                if original_first_thunk == 0 and first_thunk == 0:
                    break

                dll_name = self._read_string_at_rva(name_rva)
                if dll_name is None:
                    dll_name = "<unknown>"

                # 使用 OriginalFirstThunk (INT) 来获取函数名
                # 如果 INT 为 0，则使用 FirstThunk (IAT)
                thunk_rva = original_first_thunk if original_first_thunk != 0 else first_thunk
                functions = []

                if thunk_rva != 0:
                    func_idx = 0
                    while True:
                        thunk_offset = self._rva_to_offset(thunk_rva + func_idx * IMAGE_THUNK_DATA_SIZE)
                        if thunk_offset == 0:
                            break

                        thunk_data = self._read_at(thunk_offset, IMAGE_THUNK_DATA_SIZE)
                        if thunk_data is None:
                            break

                        thunk_value = struct.unpack("<I", thunk_data)[0]
                        if thunk_value == 0:
                            break

                        # 检查是按名称导入还是按序号导入
                        # 高位 (bit 31) 为 1 表示按序号导入
                        if thunk_value & 0x80000000:
                            ordinal = thunk_value & 0x7FFFFFFF
                            functions.append({
                                "ordinal": ordinal,
                                "name": "Ordinal_{}".format(ordinal),
                                "by_ordinal": True,
                                "thunk_rva": thunk_rva + func_idx * IMAGE_THUNK_DATA_SIZE,
                                "iat_rva": first_thunk + func_idx * IMAGE_THUNK_DATA_SIZE,
                            })
                        else:
                            # 按名称导入: thunk_value 指向 IMAGE_IMPORT_BY_NAME
                            # IMAGE_IMPORT_BY_NAME: Hint(2) + Name(null-terminated)
                            hint_offset = self._rva_to_offset(thunk_value)
                            if hint_offset:
                                hint_data = self._read_at(hint_offset, 2)
                                hint = struct.unpack("<H", hint_data)[0] if hint_data else 0
                                func_name = self._read_string_at_rva(thunk_value + 2)
                                if func_name is None:
                                    func_name = "<unknown>"
                                functions.append({
                                    "hint": hint,
                                    "name": func_name,
                                    "by_ordinal": False,
                                    "name_rva": thunk_value,
                                    "thunk_rva": thunk_rva + func_idx * IMAGE_THUNK_DATA_SIZE,
                                    "iat_rva": first_thunk + func_idx * IMAGE_THUNK_DATA_SIZE,
                                })
                        func_idx += 1

                imports[dll_name] = {
                    "function_count": len(functions),
                    "functions": functions,
                    "TimeDateStamp": time_date_stamp,
                    "ForwarderChain": forwarder_chain,
                    "NameRVA": name_rva,
                    "OriginalFirstThunk": original_first_thunk,
                    "FirstThunk": first_thunk,
                }
                total_imports += len(functions)
                idx += 1

            self._import_table = {
                "success": True,
                "dll_count": len(imports),
                "total_imports": total_imports,
                "imports": imports,
            }
            return self._import_table

        except (struct.error, IndexError) as e:
            return {"success": False, "message": "解析导入表失败: {}".format(e)}

    # ============================================================
    # 8. 按名称查找导入函数
    # ============================================================

    def find_import_by_name(self, dll_name: str, func_name: str) -> dict:
        """
        按名称查找导入函数，返回其 IAT 地址

        参数:
            dll_name: DLL 名称 (如 "kernel32.dll")
            func_name: 函数名称 (如 "GetProcAddress")

        返回:
            {success, dll_name, func_name, iat_rva, thunk_rva, ...}
        """
        imports = self.parse_import_table()
        if not imports.get("success"):
            return {"success": False, "message": "导入表解析失败"}

        dll_key = dll_name.lower()
        func_key = func_name.lower()

        for dll, info in imports.get("imports", {}).items():
            if dll.lower() == dll_key:
                for func in info.get("functions", []):
                    if func.get("name", "").lower() == func_key:
                        return {
                            "success": True,
                            "dll_name": dll,
                            "func_name": func.get("name"),
                            "ordinal": func.get("ordinal"),
                            "hint": func.get("hint"),
                            "by_ordinal": func.get("by_ordinal", False),
                            "iat_rva": func.get("iat_rva"),
                            "iat_rva_hex": "0x{:X}".format(func.get("iat_rva", 0)),
                            "thunk_rva": func.get("thunk_rva"),
                            "thunk_rva_hex": "0x{:X}".format(func.get("thunk_rva", 0)),
                        }

        return {
            "success": False,
            "message": "未找到导入函数: {}!{}".format(dll_name, func_name),
        }

    # ============================================================
    # 9. 获取 IAT 地址
    # ============================================================

    def get_iat_address(self, dll_name: str, func_name: str) -> dict:
        """
        获取 IAT 中函数的实际地址（运行时地址）

        在 PE 文件未加载时，IAT 中存储的是与 INT 相同的值
        (RVA 指向 IMAGE_IMPORT_BY_NAME 或序号)。
        运行时由 Windows Loader 填充为实际函数地址。

        返回:
            {success, iat_rva, iat_file_offset, current_value, ...}
        """
        func_info = self.find_import_by_name(dll_name, func_name)
        if not func_info.get("success"):
            return func_info

        iat_rva = func_info.get("iat_rva")
        if iat_rva is None:
            return {"success": False, "message": "无法获取 IAT RVA"}

        iat_file_offset = self._rva_to_offset(iat_rva)
        current_value = self._read_dword_at_rva(iat_rva)

        return {
            "success": True,
            "dll_name": dll_name,
            "func_name": func_name,
            "iat_rva": iat_rva,
            "iat_rva_hex": "0x{:X}".format(iat_rva),
            "iat_file_offset": iat_file_offset,
            "iat_file_offset_hex": "0x{:X}".format(iat_file_offset),
            "current_value": current_value,
            "current_value_hex": "0x{:X}".format(current_value) if current_value else "0x0",
        }

    # ============================================================
    # 10. 列出所有导入的 DLL
    # ============================================================

    def list_imported_dlls(self) -> dict:
        """
        列出所有导入的 DLL 及函数数

        返回:
            {success, dll_count, total_functions, dlls: [{name, function_count}]}
        """
        imports = self.parse_import_table()
        if not imports.get("success"):
            return {"success": False, "message": "导入表解析失败"}

        dlls = []
        for dll_name, info in imports.get("imports", {}).items():
            dlls.append({
                "name": dll_name,
                "function_count": info.get("function_count", 0),
            })

        dlls.sort(key=lambda x: x["function_count"], reverse=True)

        return {
            "success": True,
            "dll_count": len(dlls),
            "total_functions": imports.get("total_imports", 0),
            "dlls": dlls,
        }

    # ============================================================
    # 11. 导出表解析
    # ============================================================

    def parse_export_table(self) -> dict:
        """
        解析导出表 (IMAGE_EXPORT_DIRECTORY)

        通常 EXE 文件没有导出表，但 DLL 有。
        此方法检查 Data Directory 中的导出表条目。

        返回:
            {success, export_count, exports: [{name, ordinal, rva, ...}]}
        """
        if self._export_table is not None:
            return self._export_table

        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        export_dir = self._get_data_directory(IMAGE_DIRECTORY_ENTRY_EXPORT)
        if export_dir is None or not export_dir.get("is_present"):
            return {"success": False, "message": "没有导出表"}

        export_rva = export_dir["VirtualAddress"]
        export_offset = self._rva_to_offset(export_rva)
        if export_offset == 0:
            return {"success": False, "message": "导出表 RVA 无效"}

        try:
            exp_data = self._read_at(export_offset, IMAGE_EXPORT_DIRECTORY_SIZE)
            if exp_data is None:
                return {"success": False, "message": "无法读取导出表"}

            characteristics = struct.unpack_from("<I", exp_data, 0)[0]
            time_date_stamp = struct.unpack_from("<I", exp_data, 4)[0]
            major_version = struct.unpack_from("<H", exp_data, 8)[0]
            minor_version = struct.unpack_from("<H", exp_data, 10)[0]
            name_rva = struct.unpack_from("<I", exp_data, 12)[0]
            base = struct.unpack_from("<I", exp_data, 16)[0]
            num_functions = struct.unpack_from("<I", exp_data, 20)[0]
            num_names = struct.unpack_from("<I", exp_data, 24)[0]
            addr_of_functions = struct.unpack_from("<I", exp_data, 28)[0]
            addr_of_names = struct.unpack_from("<I", exp_data, 32)[0]
            addr_of_name_ordinals = struct.unpack_from("<I", exp_data, 36)[0]

            dll_name = self._read_string_at_rva(name_rva) or "<unknown>"

            exports = []
            for i in range(num_names):
                # 读取名称序号 (WORD)
                ord_offset = self._rva_to_offset(addr_of_name_ordinals + i * 2)
                if ord_offset == 0:
                    continue
                ord_data = self._read_at(ord_offset, 2)
                if ord_data is None:
                    continue
                ordinal = struct.unpack("<H", ord_data)[0]

                # 读取名称 RVA
                name_ptr_offset = self._rva_to_offset(addr_of_names + i * 4)
                if name_ptr_offset == 0:
                    continue
                name_ptr_data = self._read_at(name_ptr_offset, 4)
                if name_ptr_data is None:
                    continue
                func_name_rva = struct.unpack("<I", name_ptr_data)[0]
                func_name = self._read_string_at_rva(func_name_rva) or "<unknown>"

                # 读取函数 RVA
                func_offset = self._rva_to_offset(addr_of_functions + ordinal * 4)
                if func_offset == 0:
                    continue
                func_data = self._read_at(func_offset, 4)
                if func_data is None:
                    continue
                func_rva = struct.unpack("<I", func_data)[0]

                # 检查是否为转发导出
                is_forwarded = False
                forwarded_name = None
                if export_rva <= func_rva < export_rva + export_dir["Size"]:
                    is_forwarded = True
                    forwarded_name = self._read_string_at_rva(func_rva)

                exports.append({
                    "ordinal": base + ordinal,
                    "name": func_name,
                    "rva": func_rva,
                    "rva_hex": "0x{:X}".format(func_rva),
                    "is_forwarded": is_forwarded,
                    "forwarded_name": forwarded_name,
                })

            self._export_table = {
                "success": True,
                "dll_name": dll_name,
                "characteristics": characteristics,
                "time_date_stamp": time_date_stamp,
                "major_version": major_version,
                "minor_version": minor_version,
                "base": base,
                "number_of_functions": num_functions,
                "number_of_names": num_names,
                "export_count": len(exports),
                "exports": exports,
            }
            return self._export_table

        except (struct.error, IndexError) as e:
            return {"success": False, "message": "解析导出表失败: {}".format(e)}

    # ============================================================
    # 12. 按名称查找导出函数
    # ============================================================

    def find_export_by_name(self, func_name: str) -> dict:
        """
        按名称查找导出函数

        参数:
            func_name: 函数名称

        返回:
            {success, name, ordinal, rva, ...}
        """
        exports = self.parse_export_table()
        if not exports.get("success"):
            return {"success": False, "message": "导出表解析失败"}

        func_key = func_name.lower()
        for exp in exports.get("exports", []):
            if exp.get("name", "").lower() == func_key:
                return {
                    "success": True,
                    "name": exp.get("name"),
                    "ordinal": exp.get("ordinal"),
                    "rva": exp.get("rva"),
                    "rva_hex": exp.get("rva_hex"),
                    "is_forwarded": exp.get("is_forwarded", False),
                    "forwarded_name": exp.get("forwarded_name"),
                }

        return {"success": False, "message": "未找到导出函数: {}".format(func_name)}

    # ============================================================
    # 13. 重定位表解析
    # ============================================================

    def parse_relocations(self) -> dict:
        """
        解析重定位表 (IMAGE_BASE_RELOCATION)

        重定位表由多个重定位块组成，每个块包含:
        - VirtualAddress (4 字节): 页的基地址 RVA
        - SizeOfBlock (4 字节): 块的总大小
        - 条目数组: 每个 2 字节 (高 4 位 = 类型, 低 12 位 = 偏移)

        返回:
            {success, block_count, total_entries, blocks: [...], entries: [...]}
        """
        if self._relocations is not None:
            return self._relocations

        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        reloc_dir = self._get_data_directory(IMAGE_DIRECTORY_ENTRY_BASERELOC)
        if reloc_dir is None or not reloc_dir.get("is_present"):
            return {"success": False, "message": "没有重定位表"}

        reloc_rva = reloc_dir["VirtualAddress"]
        reloc_size = reloc_dir["Size"]

        try:
            all_entries = []
            blocks = []
            current_offset = self._rva_to_offset(reloc_rva)
            end_offset = current_offset + reloc_size
            total_entries = 0

            while current_offset < end_offset:
                block_data = self._read_at(current_offset, IMAGE_BASE_RELOCATION_HEADER_SIZE)
                if block_data is None:
                    break

                page_rva = struct.unpack_from("<I", block_data, 0)[0]
                block_size = struct.unpack_from("<I", block_data, 4)[0]

                if block_size == 0:
                    break

                # 条目数 = (block_size - 8) / 2
                entry_count = (block_size - IMAGE_BASE_RELOCATION_HEADER_SIZE) // 2
                block_entries = []
                block_entry_offset = current_offset + IMAGE_BASE_RELOCATION_HEADER_SIZE

                for j in range(entry_count):
                    entry_data = self._read_at(block_entry_offset + j * 2, 2)
                    if entry_data is None:
                        break
                    entry = struct.unpack("<H", entry_data)[0]
                    reloc_type = (entry >> 12) & 0xF
                    reloc_offset = entry & 0xFFF

                    entry_info = {
                        "type": reloc_type,
                        "type_name": self._get_relocation_type_name(reloc_type),
                        "offset": reloc_offset,
                        "rva": page_rva + reloc_offset,
                        "rva_hex": "0x{:X}".format(page_rva + reloc_offset),
                    }
                    block_entries.append(entry_info)
                    all_entries.append(entry_info)

                blocks.append({
                    "page_rva": page_rva,
                    "page_rva_hex": "0x{:X}".format(page_rva),
                    "block_size": block_size,
                    "entry_count": len(block_entries),
                    "entries": block_entries,
                })
                total_entries += len(block_entries)
                current_offset += block_size

            self._relocations = {
                "success": True,
                "block_count": len(blocks),
                "total_entries": total_entries,
                "blocks": blocks,
                "entries": all_entries,
            }
            return self._relocations

        except (struct.error, IndexError) as e:
            return {"success": False, "message": "解析重定位表失败: {}".format(e)}

    @staticmethod
    def _get_relocation_type_name(reloc_type: int) -> str:
        """获取重定位类型名称"""
        type_names = {
            0: "IMAGE_REL_BASED_ABSOLUTE",
            1: "IMAGE_REL_BASED_HIGH",
            2: "IMAGE_REL_BASED_LOW",
            3: "IMAGE_REL_BASED_HIGHLOW",
            4: "IMAGE_REL_BASED_HIGHADJ",
            5: "IMAGE_REL_BASED_MIPS_JMPADDR",
            7: "IMAGE_REL_BASED_THUMB_MOV32",
            9: "IMAGE_REL_BASED_MIPS_JMPADDR16",
            10: "IMAGE_REL_BASED_DIR64",
        }
        return type_names.get(reloc_type, "UNKNOWN")

    # ============================================================
    # 14. 获取重定位条目数
    # ============================================================

    def get_relocation_count(self) -> dict:
        """
        统计重定位条目数

        返回:
            {success, total_entries, block_count, ...}
        """
        relocs = self.parse_relocations()
        if not relocs.get("success"):
            return {"success": False, "message": relocs.get("message", "解析失败"), "total_entries": 0, "block_count": 0}

        return {
            "success": True,
            "total_entries": relocs.get("total_entries", 0),
            "block_count": relocs.get("block_count", 0),
        }

    # ============================================================
    # 15. 资源表解析
    # ============================================================

    def parse_resource_table(self) -> dict:
        """
        解析资源表的基本结构

        资源表是一个三层树结构:
        - 第一层: 资源类型 (RT_ICON, RT_BITMAP, RT_STRING, 等)
        - 第二层: 资源名称/ID
        - 第三层: 语言

        返回:
            {success, resource_types: [{type_id, type_name, entry_count}]}
        """
        if self._resource_table is not None:
            return self._resource_table

        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        res_dir = self._get_data_directory(IMAGE_DIRECTORY_ENTRY_RESOURCE)
        if res_dir is None or not res_dir.get("is_present"):
            return {"success": False, "message": "没有资源表"}

        res_rva = res_dir["VirtualAddress"]
        res_offset = self._rva_to_offset(res_rva)
        if res_offset == 0:
            return {"success": False, "message": "资源表 RVA 无效"}

        try:
            resource_types = self._parse_resource_directory(res_offset, 0)
            total_entries = sum(t.get("entry_count", 0) for t in resource_types)

            self._resource_table = {
                "success": True,
                "type_count": len(resource_types),
                "total_entries": total_entries,
                "resource_types": resource_types,
            }
            return self._resource_table

        except (struct.error, IndexError) as e:
            return {"success": False, "message": "解析资源表失败: {}".format(e)}

    def _parse_resource_directory(self, offset: int, level: int) -> List[dict]:
        """递归解析资源目录"""
        result = []
        dir_data = self._read_at(offset, IMAGE_RESOURCE_DIRECTORY_SIZE)
        if dir_data is None:
            return result

        num_named = struct.unpack_from("<H", dir_data, 12)[0]
        num_id = struct.unpack_from("<H", dir_data, 14)[0]
        total_entries = num_named + num_id

        entry_offset = offset + IMAGE_RESOURCE_DIRECTORY_SIZE

        for i in range(total_entries):
            entry_off = entry_offset + i * IMAGE_RESOURCE_DIRECTORY_ENTRY_SIZE
            entry_data = self._read_at(entry_off, IMAGE_RESOURCE_DIRECTORY_ENTRY_SIZE)
            if entry_data is None:
                continue

            name_or_id = struct.unpack_from("<I", entry_data, 0)[0]
            offset_to_data = struct.unpack_from("<I", entry_data, 4)[0]

            # 最高位为 1 表示这是一个子目录
            is_directory = (offset_to_data & 0x80000000) != 0

            if level == 0:
                entry_info = {
                    "type_id": name_or_id,
                    "type_name": self._get_resource_type_name(name_or_id),
                    "is_directory": is_directory,
                }

                if is_directory:
                    child_offset = self._rva_to_offset(res_rva=offset_to_data & 0x7FFFFFFF)
                    if child_offset:
                        children = self._parse_resource_directory(child_offset, level + 1)
                        entry_info["entry_count"] = len(children)
                        # 统计语言数
                        lang_count = 0
                        for child in children:
                            lang_count += child.get("entry_count", 0)
                        entry_info["language_count"] = lang_count
                result.append(entry_info)

        return result

    def _rva_to_offset_with_base(self, rva: int, base_rva: int) -> int:
        """将基于资源表基址的偏移转换为文件偏移"""
        # 资源目录中的 offset_to_data 的低 31 位是相对于资源表起始的偏移
        actual_rva = base_rva + (rva & 0x7FFFFFFF)
        return self._rva_to_offset(actual_rva)

    def _parse_resource_directory(self, offset: int, level: int) -> List[dict]:
        """递归解析资源目录"""
        result = []
        res_dir = self._get_data_directory(IMAGE_DIRECTORY_ENTRY_RESOURCE)
        if res_dir is None:
            return result
        base_rva = res_dir.get("VirtualAddress", 0)

        dir_data = self._read_at(offset, IMAGE_RESOURCE_DIRECTORY_SIZE)
        if dir_data is None:
            return result

        num_named = struct.unpack_from("<H", dir_data, 12)[0]
        num_id = struct.unpack_from("<H", dir_data, 14)[0]
        total_entries = num_named + num_id

        entry_offset = offset + IMAGE_RESOURCE_DIRECTORY_SIZE

        for i in range(total_entries):
            entry_off = entry_offset + i * IMAGE_RESOURCE_DIRECTORY_ENTRY_SIZE
            entry_data = self._read_at(entry_off, IMAGE_RESOURCE_DIRECTORY_ENTRY_SIZE)
            if entry_data is None:
                continue

            name_or_id = struct.unpack_from("<I", entry_data, 0)[0]
            offset_to_data = struct.unpack_from("<I", entry_data, 4)[0]

            is_directory = (offset_to_data & 0x80000000) != 0

            if level == 0:
                entry_info = {
                    "type_id": name_or_id,
                    "type_name": self._get_resource_type_name(name_or_id),
                    "is_directory": is_directory,
                }

                if is_directory:
                    child_real_offset = offset_to_data & 0x7FFFFFFF
                    child_file_offset = self._rva_to_offset(base_rva + child_real_offset)
                    if child_file_offset:
                        children = self._parse_resource_directory(child_file_offset, level + 1)
                        entry_info["entry_count"] = len(children)
                        lang_count = 0
                        for child in children:
                            lang_count += child.get("entry_count", 0)
                        entry_info["language_count"] = lang_count
                result.append(entry_info)

        return result

    @staticmethod
    def _get_resource_type_name(type_id: int) -> str:
        """获取资源类型名称"""
        type_names = {
            1: "RT_CURSOR",
            2: "RT_BITMAP",
            3: "RT_ICON",
            4: "RT_MENU",
            5: "RT_DIALOG",
            6: "RT_STRING",
            7: "RT_FONTDIR",
            8: "RT_FONT",
            9: "RT_ACCELERATOR",
            10: "RT_RCDATA",
            11: "RT_MESSAGETABLE",
            12: "RT_GROUP_CURSOR",
            14: "RT_GROUP_ICON",
            16: "RT_VERSION",
            17: "RT_DLGINCLUDE",
            19: "RT_PLUGPLAY",
            20: "RT_VXD",
            21: "RT_ANICURSOR",
            22: "RT_ANIICON",
            23: "RT_HTML",
            24: "RT_MANIFEST",
        }
        return type_names.get(type_id, "TYPE_{}".format(type_id))

    # ============================================================
    # 16. IAT Hook 支持 — build_iat_hook
    # ============================================================

    def build_iat_hook(self, dll_name: str, func_name: str, hook_address: int) -> dict:
        """
        构建 IAT Hook — 修改 IAT 中指定函数的地址指向我们的代码

        参数:
            dll_name: DLL 名称 (如 "kernel32.dll")
            func_name: 函数名称 (如 "GetTickCount")
            hook_address: 新的钩子地址 (RVA 或绝对地址)

        返回:
            {success, original_address, new_address, iat_rva, ...}
        """
        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        # 获取 IAT 信息
        iat_info = self.get_iat_address(dll_name, func_name)
        if not iat_info.get("success"):
            return {"success": False, "message": "无法获取 IAT 地址: {}".format(iat_info.get("message"))}

        iat_file_offset = iat_info.get("iat_file_offset")
        original_value = iat_info.get("current_value")

        if iat_file_offset is None:
            return {"success": False, "message": "无效的 IAT 文件偏移"}

        # 写入新的钩子地址
        try:
            hook_key = "{}!{}".format(dll_name.lower(), func_name)
            self._iat_hooks[hook_key] = {
                "dll_name": dll_name,
                "func_name": func_name,
                "original_value": original_value,
                "hook_address": hook_address,
                "iat_file_offset": iat_file_offset,
                "iat_rva": iat_info.get("iat_rva"),
            }
            return {
                "success": True,
                "dll_name": dll_name,
                "func_name": func_name,
                "original_address": original_value,
                "original_address_hex": "0x{:X}".format(original_value) if original_value else "0x0",
                "new_address": hook_address,
                "new_address_hex": "0x{:X}".format(hook_address),
                "iat_rva": iat_info.get("iat_rva"),
                "iat_rva_hex": iat_info.get("iat_rva_hex"),
                "iat_file_offset": iat_file_offset,
                "iat_file_offset_hex": iat_info.get("iat_file_offset_hex"),
                "note": "IAT Hook 已记录，调用 apply_iat_hooks() 写入文件",
            }
        except Exception as e:
            return {"success": False, "message": "构建 IAT Hook 失败: {}".format(e)}

    def apply_iat_hooks(self) -> dict:
        """
        将所有已构建的 IAT Hook 写入文件

        返回:
            {success, applied_count, hooks: [...]}
        """
        if not self._iat_hooks:
            return {"success": False, "message": "没有待应用的 IAT Hook"}

        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        applied = []
        try:
            for hook_key, hook_info in self._iat_hooks.items():
                file_offset = hook_info.get("iat_file_offset")
                hook_addr = hook_info.get("hook_address")

                if file_offset is None or hook_addr is None:
                    applied.append({
                        "key": hook_key,
                        "success": False,
                        "message": "无效的偏移或地址",
                    })
                    continue

                # 写入新的 IAT 值
                self._exe_data = (
                    self._exe_data[:file_offset] +
                    struct.pack("<I", hook_addr) +
                    self._exe_data[file_offset + 4:]
                )

                applied.append({
                    "key": hook_key,
                    "success": True,
                    "dll_name": hook_info["dll_name"],
                    "func_name": hook_info["func_name"],
                    "original": hook_info["original_value"],
                    "new": hook_addr,
                })

            return {
                "success": True,
                "applied_count": sum(1 for a in applied if a["success"]),
                "total": len(applied),
                "hooks": applied,
            }
        except Exception as e:
            return {"success": False, "message": "应用 IAT Hook 失败: {}".format(e)}

    # ============================================================
    # 17. 恢复 IAT Hook
    # ============================================================

    def restore_iat(self, dll_name: str, func_name: str) -> dict:
        """
        恢复 IAT 中被 Hook 的原始地址

        参数:
            dll_name: DLL 名称
            func_name: 函数名称

        返回:
            {success, restored_address, ...}
        """
        hook_key = "{}!{}".format(dll_name.lower(), func_name)

        if hook_key not in self._iat_hooks:
            return {"success": False, "message": "未找到 IAT Hook 记录: {}".format(hook_key)}

        hook_info = self._iat_hooks[hook_key]
        file_offset = hook_info.get("iat_file_offset")
        original_value = hook_info.get("original_value")

        if file_offset is None or original_value is None:
            return {"success": False, "message": "Hook 记录不完整"}

        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        try:
            # 恢复原始值
            self._exe_data = (
                self._exe_data[:file_offset] +
                struct.pack("<I", original_value) +
                self._exe_data[file_offset + 4:]
            )

            del self._iat_hooks[hook_key]

            return {
                "success": True,
                "dll_name": dll_name,
                "func_name": func_name,
                "restored_address": original_value,
                "restored_address_hex": "0x{:X}".format(original_value),
                "iat_file_offset": file_offset,
                "iat_file_offset_hex": "0x{:X}".format(file_offset),
            }
        except Exception as e:
            return {"success": False, "message": "恢复 IAT 失败: {}".format(e)}

    def get_iat_hooks(self) -> dict:
        """获取所有已记录的 IAT Hook"""
        hooks = []
        for key, info in self._iat_hooks.items():
            hooks.append({
                "key": key,
                "dll_name": info["dll_name"],
                "func_name": info["func_name"],
                "original_value": info["original_value"],
                "hook_address": info["hook_address"],
                "iat_rva": info.get("iat_rva"),
            })
        return {
            "success": True,
            "hook_count": len(hooks),
            "hooks": hooks,
        }

    # ============================================================
    # 18. Code Cave 搜索 (增强版，利用节表)
    # ============================================================

    def find_code_caves_in_sections(self, min_size: int = 64) -> dict:
        """
        在可执行节中搜索 Code Cave

        利用 PE 节表精确确定搜索范围，比全文件搜索更精确:
        - 仅在可执行节 (.text) 中搜索
        - 搜索连续的 0x00 (零填充) 和 0xCC (INT3) 区域
        - 返回按大小排序的可用 Cave 列表

        参数:
            min_size: 最小需要的空间（字节）

        返回:
            {success, cave_count, total_available, caves: [...]}
        """
        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        if self._sections is None:
            self.parse_section_headers()

        if self._sections is None:
            return {"success": False, "message": "节表解析失败"}

        all_caves = []

        # 优先搜索可执行节
        executable_sections = [
            s for s in self._sections if s.get("is_executable")
        ]

        for section in executable_sections:
            raw_start = section.get("PointerToRawData", 0)
            raw_size = section.get("SizeOfRawData", 0)
            raw_end = raw_start + raw_size

            if raw_size == 0:
                continue

            # 搜索 0x00 填充区域
            i = raw_start
            while i < raw_end:
                if i < len(self._exe_data) and self._exe_data[i] == 0x00:
                    start = i
                    while i < raw_end and i < len(self._exe_data) and self._exe_data[i] == 0x00:
                        i += 1
                    size = i - start
                    if size >= min_size:
                        all_caves.append({
                            "offset": start,
                            "offset_hex": "0x{:X}".format(start),
                            "size": size,
                            "fill_byte": "0x00",
                            "fill_type": "ZERO",
                            "section": section.get("Name"),
                            "rva": section.get("VirtualAddress", 0) + (start - raw_start),
                            "rva_hex": "0x{:X}".format(section.get("VirtualAddress", 0) + (start - raw_start)),
                        })
                else:
                    i += 1

            # 搜索 0xCC 填充区域 (INT3)
            i = raw_start
            while i < raw_end:
                if i < len(self._exe_data) and self._exe_data[i] == 0xCC:
                    start = i
                    while i < raw_end and i < len(self._exe_data) and self._exe_data[i] == 0xCC:
                        i += 1
                    size = i - start
                    if size >= min_size:
                        all_caves.append({
                            "offset": start,
                            "offset_hex": "0x{:X}".format(start),
                            "size": size,
                            "fill_byte": "0xCC",
                            "fill_type": "INT3",
                            "section": section.get("Name"),
                            "rva": section.get("VirtualAddress", 0) + (start - raw_start),
                            "rva_hex": "0x{:X}".format(section.get("VirtualAddress", 0) + (start - raw_start)),
                        })
                else:
                    i += 1

            # 搜索 0x90 填充区域 (NOP)
            i = raw_start
            while i < raw_end:
                if i < len(self._exe_data) and self._exe_data[i] == 0x90:
                    start = i
                    while i < raw_end and i < len(self._exe_data) and self._exe_data[i] == 0x90:
                        i += 1
                    size = i - start
                    if size >= min_size:
                        all_caves.append({
                            "offset": start,
                            "offset_hex": "0x{:X}".format(start),
                            "size": size,
                            "fill_byte": "0x90",
                            "fill_type": "NOP",
                            "section": section.get("Name"),
                            "rva": section.get("VirtualAddress", 0) + (start - raw_start),
                            "rva_hex": "0x{:X}".format(section.get("VirtualAddress", 0) + (start - raw_start)),
                        })
                else:
                    i += 1

        # 排序：按大小降序
        all_caves.sort(key=lambda c: -c["size"])
        total = sum(c["size"] for c in all_caves)

        return {
            "success": True,
            "exe_size": len(self._exe_data),
            "cave_count": len(all_caves),
            "total_available": total,
            "total_available_kb": round(total / 1024, 2),
            "caves": all_caves[:20],
            "largest": all_caves[0] if all_caves else None,
        }

    # ============================================================
    # 19. 获取节信息
    # ============================================================

    def get_section_info(self, section_name: str) -> dict:
        """
        获取指定节的详细信息

        参数:
            section_name: 节名称，支持模糊匹配 (如 ".text")

        返回:
            {success, section: {...}}
        """
        if self._sections is None:
            self.parse_section_headers()

        if self._sections is None:
            return {"success": False, "message": "节表解析失败"}

        search_name = section_name.lower().strip(".")
        for section in self._sections:
            sec_name = section.get("Name", "").lower().strip(".")
            if sec_name == search_name:
                # 计算节内数据摘要
                raw_start = section.get("PointerToRawData", 0)
                raw_size = section.get("SizeOfRawData", 0)
                raw_end = raw_start + raw_size

                data_summary = {}
                if self._exe_data and raw_size > 0 and raw_end <= len(self._exe_data):
                    section_data = self._exe_data[raw_start:raw_end]
                    # 统计零字节比例
                    zero_count = section_data.count(0)
                    data_summary["zero_bytes"] = zero_count
                    data_summary["zero_percent"] = round(zero_count / raw_size * 100, 2)
                    data_summary["non_zero_bytes"] = raw_size - zero_count
                    # 第一个和最后一个非零字节偏移
                    data_summary["first_non_zero"] = next(
                        (i for i, b in enumerate(section_data) if b != 0), None
                    )
                    data_summary["last_non_zero"] = next(
                        (i for i, b in enumerate(reversed(section_data)) if b != 0), None
                    )
                    if data_summary["last_non_zero"] is not None:
                        data_summary["last_non_zero"] = raw_size - 1 - data_summary["last_non_zero"]

                return {
                    "success": True,
                    "section": dict(section),
                    "data_summary": data_summary,
                }

        return {"success": False, "message": "未找到节: {}".format(section_name)}

    # ============================================================
    # 20. 获取所有可执行节
    # ============================================================

    def get_executable_sections(self) -> dict:
        """
        获取所有可执行节 (Characteristics 包含 MEM_EXECUTE)

        返回:
            {success, count, sections: [...]}
        """
        if self._sections is None:
            self.parse_section_headers()

        if self._sections is None:
            return {"success": False, "message": "节表解析失败"}

        exec_sections = [s for s in self._sections if s.get("is_executable")]

        return {
            "success": True,
            "count": len(exec_sections),
            "sections": exec_sections,
        }

    # ============================================================
    # 21. 版本/特征检测
    # ============================================================

    def detect_exe_version(self) -> dict:
        """
        通过 PE 头信息检测 EXE 版本

        分析以下特征:
        - TimeDateStamp: 编译时间戳
        - SizeOfImage: 映像大小
        - AddressOfEntryPoint: 入口点
        - CheckSum: 校验和
        - 节的数量和名称
        - 导入的 DLL 数量

        返回:
            {success, time_date_stamp, compile_date, size_of_image, ...}
        """
        if self._exe_data is None:
            return {"success": False, "message": "EXE 未加载"}

        result = {
            "success": True,
            "file_size": len(self._exe_data),
            "file_size_kb": round(len(self._exe_data) / 1024, 2),
            "file_size_mb": round(len(self._exe_data) / (1024 * 1024), 2),
        }

        # 从 File Header 获取 TimeDateStamp
        fh = self.parse_file_header()
        if fh.get("success"):
            ts = fh.get("TimeDateStamp", 0)
            result["time_date_stamp"] = ts
            result["time_date_stamp_hex"] = "0x{:08X}".format(ts)

            # 转换时间戳为日期
            import datetime
            try:
                compile_dt = datetime.datetime.fromtimestamp(ts)
                result["compile_date"] = compile_dt.strftime("%Y-%m-%d %H:%M:%S")
                result["compile_year"] = compile_dt.year
            except (ValueError, OSError):
                result["compile_date"] = "Invalid timestamp"
                result["compile_year"] = 0

            result["machine"] = fh.get("MachineName", "UNKNOWN")
            result["section_count"] = fh.get("NumberOfSections", 0)

        # 从 Optional Header 获取更多信息
        oh = self.parse_optional_header()
        if oh.get("success"):
            result["entry_point"] = oh.get("AddressOfEntryPoint", 0)
            result["entry_point_hex"] = oh.get("AddressOfEntryPoint_hex", "0x0")
            result["image_base"] = oh.get("ImageBase", 0)
            result["image_base_hex"] = oh.get("ImageBase_hex", "0x0")
            result["size_of_image"] = oh.get("SizeOfImage", 0)
            result["size_of_image_hex"] = oh.get("SizeOfImage_hex", "0x0")
            result["size_of_image_mb"] = round(oh.get("SizeOfImage", 0) / (1024 * 1024), 2)
            result["checksum"] = oh.get("CheckSum", 0)
            result["checksum_hex"] = oh.get("CheckSum_hex", "0x0")
            result["subsystem"] = oh.get("SubsystemName", "UNKNOWN")
            result["linker_version"] = oh.get("LinkerVersion", "unknown")
            result["os_version"] = oh.get("OSVersion", "unknown")
            result["image_version"] = oh.get("ImageVersion", "unknown")
            result["is_gui"] = oh.get("is_gui", False)
            result["is_console"] = oh.get("is_console", False)

            # DLL Characteristics
            dll_flags = oh.get("DllCharacteristicsFlags", [])
            result["has_aslr"] = "DYNAMIC_BASE (ASLR)" in dll_flags
            result["has_dep"] = "NX_COMPAT (DEP)" in dll_flags
            result["dll_characteristics"] = dll_flags

        # 节信息
        sections = self.parse_section_headers()
        if sections.get("success"):
            sec_names = [s.get("Name", "") for s in sections.get("sections", [])]
            result["section_names"] = sec_names

        # 导入信息
        dlls = self.list_imported_dlls()
        if dlls.get("success"):
            result["imported_dll_count"] = dlls.get("dll_count", 0)
            result["imported_function_count"] = dlls.get("total_functions", 0)

        return result

    # ============================================================
    # 22. get_info — 模块信息
    # ============================================================

    @staticmethod
    def get_info() -> dict:
        """
        返回模块信息

        返回:
            {success, module_name, version, description, capabilities, ...}
        """
        return {
            "success": True,
            "module_name": "pe_analyzer",
            "version": "1.0.0",
            "description": "PE (Portable Executable) 结构解析器",
            "capabilities": [
                "DOS Header 解析",
                "NT Headers 解析",
                "File Header 解析",
                "Optional Header 解析",
                "节表 (Section Headers) 解析",
                "Data Directories 解析",
                "导入表 (IAT) 解析",
                "导出表解析",
                "重定位表解析",
                "资源表解析",
                "IAT Hook 构建与恢复",
                "Code Cave 搜索 (节表精确定位)",
                "版本/特征检测",
                "RVA 到文件偏移转换",
            ],
            "supported_formats": ["PE32 (32位 Windows PE)"],
            "pe_signature": "0x{:04X} (MZ), 0x{:08X} (PE\\0\\0)".format(
                IMAGE_DOS_SIGNATURE, IMAGE_NT_SIGNATURE
            ),
            "optional_header_magic": "0x{:04X} (PE32)".format(IMAGE_NT_OPTIONAL_HDR32_MAGIC),
            "dependencies": ["struct", "os", "logging"],
        }

    # ============================================================
    # 综合信息导出
    # ============================================================

    def get_full_analysis(self) -> dict:
        """
        获取完整的 PE 分析结果

        一次性返回所有解析结果的综合视图。

        返回:
            {success, dos_header, file_header, optional_header,
             sections, data_directories, imports, exports,
             relocations, resources, version_info, ...}
        """
        return {
            "success": True,
            "exe_path": self.exe_path,
            "exe_size": len(self._exe_data) if self._exe_data else 0,
            "is_valid_pe": self.is_valid_pe(),
            "dos_header": self.parse_dos_header(),
            "nt_headers": self.parse_nt_headers(),
            "file_header": self.parse_file_header(),
            "optional_header": self.parse_optional_header(),
            "sections": self.parse_section_headers(),
            "data_directories": self.parse_data_directories(),
            "imports": self.parse_import_table(),
            "exports": self.parse_export_table(),
            "relocations": self.parse_relocations(),
            "resources": self.parse_resource_table(),
            "version_info": self.detect_exe_version(),
        }