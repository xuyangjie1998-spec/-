
__all__ = ["KNOWN_VERSIONS", "VERSION_HINTS", "EXE_SIZE_HINTS", "VersionDetector"]

"""
游戏版本检测模块
- 检测 Sango7.exe 的版本（多维度综合推断）
- 检测游戏目录结构完整性
- 检测关键文件存在性
- 检测游戏语言/区域（繁体/简体）
"""

import os
import hashlib
import struct
from typing import Dict, Optional


# ============================================================
# 已知版本哈希（仅供参考，实际值取决于发行批次）
# ============================================================
KNOWN_VERSIONS = {
    # 格式: MD5: { version, name, description, language }
    # 注：这些哈希值需要在用户实际使用中收集，不同来源的版本哈希不同
}

# ============================================================
# 基于 PE 时间戳的版本推断（主要检测手段）
# ============================================================
# 三国群英传7 发布时间线：
#   2007-12-19 繁体中文版首发
#   2008-01-03 简体中文版上市
#   2008-02-22 繁体中文版 1.1 补丁
#   2008-06-xx 繁体中文版 1.2 补丁
#   2009-01-xx 简体中文版 1.22 补丁
#   2010-xx-xx Steam 版本
#   2018-xx-xx Steam 简体中文版
#   2021-xx-xx Steam 繁体中文版
VERSION_HINTS = [
    # (timestamp_start, timestamp_end, version_hint, language)
    (1167609600, 1199145599, "繁体中文版 1.0 (2007年原始版)", "zh-TW"),
    (1199145600, 1207007999, "繁体中文版 1.0~1.1 (2008年初)", "zh-TW"),
    (1207008000, 1214870399, "繁体中文版 1.1 (2008年中)", "zh-TW"),
    (1214870400, 1230767999, "繁体中文版 1.1~1.2 (2008年后期)", "zh-TW"),
    (1230768000, 1246406399, "繁体中文版 1.2 / 简体中文版 (2009年)", "mixed"),
    (1246406400, 1293839999, "简体中文版 1.22 (2010年前后)", "zh-CN"),
    (1293840000, 1451606399, "简体中文版 (2011-2015年左右)", "zh-CN"),
    (1451606400, 1546300799, "Steam 版本 (2016-2018年)", "zh-CN"),
    (1546300800, 1609459199, "Steam 简体中文版 (2019-2020年)", "zh-CN"),
    (1609459200, 1893455999, "Steam 版本 (2021年及以后)", "mixed"),
]

# ============================================================
# 基于 EXE 文件大小的版本推断
# ============================================================
EXE_SIZE_HINTS = [
    # (min_bytes, max_bytes, hint, confidence)
    (1_000_000, 2_000_000, "可能是 1.0 原始版（较小）", "low"),
    (2_000_000, 3_500_000, "可能是 1.1~1.2 版本", "medium"),
    (3_500_000, 5_000_000, "可能是 1.22 或 Steam 版本", "medium"),
    (5_000_000, 10_000_000, "可能是 Steam 版本或修改版", "low"),
]


class VersionDetector:
    """游戏版本检测器"""

    REQUIRED_FILES = [
        "Sango7.exe",
        "Patch.pck",
        "Shape00.pck",
        "Shape01.pck",
        "Shape02.pck",
        "Shape03.pck",
        "Shape04.pck",
        "Shape05.pck",
        "Shape06.pck",
    ]

    REQUIRED_DIRS = [
        "Save",
        "Script",
        "Setting",
    ]

    # Setting 子目录（用于更精细的完整性检测）
    SETTING_SUBDIRS = [
        "OBD",
        "Data",
    ]

    # 关键 Setting 文件（用于判断游戏类型）
    KEY_SETTING_FILES = [
        "General01.ini",
        "Thing.ini",
        "TermText.ini",
        "BFSoldier.obd",
        "BFGen.obd",
        "BFMagic.ini",
        "Title.ini",
        "Nation.ini",
        "DefSkill.ini",
    ]

    def __init__(self, game_path: str = None):
        self.game_path = game_path

    def detect(self, game_path: str = None) -> Dict:
        """完整检测游戏版本和完整性"""
        if game_path:
            self.game_path = game_path
        if not self.game_path or not os.path.isdir(self.game_path):
            return {"success": False, "message": "游戏目录无效"}

        exe_path = os.path.join(self.game_path, "Sango7.exe")
        result = {
            "success": True,
            "path": self.game_path,
            "exe_exists": os.path.exists(exe_path),
            "exe_path": exe_path,
            "version": "unknown",
            "version_name": "未知版本",
            "version_hint": "",
            "version_confidence": "unknown",
            "language": "unknown",
            "language_name": "",
            "md5": "",
            "sha256": "",
            "exe_size": 0,
            "exe_size_mb": 0,
            "file_timestamp": "",
            "missing_files": [],
            "missing_dirs": [],
            "missing_setting_files": [],
            "all_files": {},
            "setting_files": {},
            "integrity_score": 0,
            "setting_integrity": 0,
            "recommendations": [],
        }

        # ---- 检测 EXE ----
        if os.path.exists(exe_path):
            result["exe_size"] = os.path.getsize(exe_path)
            result["exe_size_mb"] = round(result["exe_size"] / (1024 * 1024), 2)
            result["md5"] = self._hash_file(exe_path, "md5")
            result["sha256"] = self._hash_file(exe_path, "sha256")

            # 检查已知版本（MD5 精确匹配）
            if result["md5"] in KNOWN_VERSIONS:
                info = KNOWN_VERSIONS[result["md5"]]
                result["version"] = info.get("version", "unknown")
                result["version_name"] = info.get("name", "未知版本")
                result["version_confidence"] = "exact"
                if info.get("language"):
                    result["language"] = info["language"]
                    result["language_name"] = "繁体中文" if info["language"] == "zh-TW" else "简体中文"

            # 提取 PE 头信息
            exe_info = self._read_exe_version(exe_path)
            result.update(exe_info)

            # 基于 PE 时间戳推断版本
            ts = exe_info.get("pe_timestamp", 0)
            if result["version"] == "unknown" and ts:
                for start, end, hint, lang in VERSION_HINTS:
                    if start <= ts <= end:
                        result["version_hint"] = hint
                        result["version_confidence"] = "timestamp"
                        if lang != "mixed" and result["language"] == "unknown":
                            result["language"] = lang
                            result["language_name"] = "繁体中文" if lang == "zh-TW" else "简体中文"
                        break

            # 基于文件大小辅助推断
            if result["version"] == "unknown" and not result["version_hint"]:
                for min_sz, max_sz, hint, conf in EXE_SIZE_HINTS:
                    if min_sz <= result["exe_size"] <= max_sz:
                        result["version_hint"] = hint
                        result["version_confidence"] = "size"
                        break

            # 时间戳
            result["file_timestamp"] = self._get_file_timestamp(exe_path)

        # ---- 检测 Setting 目录编码（推断语言） ----
        setting_path = os.path.join(self.game_path, "Setting")
        if os.path.isdir(setting_path):
            encoding_info = self._detect_setting_encoding(setting_path)
            result["setting_encoding"] = encoding_info
            if result["language"] == "unknown" and encoding_info.get("detected_lang"):
                result["language"] = encoding_info["detected_lang"]
                result["language_name"] = "繁体中文" if encoding_info["detected_lang"] == "zh-TW" else "简体中文"

        # ---- 检测 Setting 子目录 ----
        if os.path.isdir(setting_path):
            for subdir in self.SETTING_SUBDIRS:
                subpath = os.path.join(setting_path, subdir)
                if not os.path.isdir(subpath):
                    result["missing_dirs"].append(f"Setting/{subdir}")

        # ---- 检测 Setting 关键文件 ----
        if os.path.isdir(setting_path):
            for fname in self.KEY_SETTING_FILES:
                fpath = os.path.join(setting_path, fname)
                if os.path.exists(fpath):
                    result["setting_files"][fname] = {
                        "size": os.path.getsize(fpath),
                        "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                    }
                else:
                    result["missing_setting_files"].append(fname)

        # ---- 检测必需文件 ----
        for fname in self.REQUIRED_FILES:
            fpath = os.path.join(self.game_path, fname)
            if not os.path.exists(fpath):
                result["missing_files"].append(fname)
            else:
                result["all_files"][fname] = {
                    "size": os.path.getsize(fpath),
                    "size_mb": round(os.path.getsize(fpath) / (1024 * 1024), 2),
                }

        # ---- 检测必需目录 ----
        for dname in self.REQUIRED_DIRS:
            dpath = os.path.join(self.game_path, dname)
            if not os.path.isdir(dpath):
                result["missing_dirs"].append(dname)

        # ---- 检测 Script 目录 ----
        script_path = os.path.join(self.game_path, "Script")
        if os.path.isdir(script_path):
            script_contents = os.listdir(script_path)
            has_script_so = "Script.so" in script_contents or "script.so" in script_contents
            result["has_script_so"] = has_script_so
            if not has_script_so:
                result["recommendations"].append("Script 目录下未找到 Script.so，脚本系统可能不完整")
        else:
            result["has_script_so"] = False

        # ---- 完整性评分 ----
        total_checks = len(self.REQUIRED_FILES) + len(self.REQUIRED_DIRS)
        missing = len(result["missing_files"]) + len(result["missing_dirs"])
        result["integrity_score"] = round((total_checks - missing) / total_checks * 100)

        # Setting 完整性
        total_setting = len(self.KEY_SETTING_FILES) + len(self.SETTING_SUBDIRS)
        missing_setting = len(result["missing_setting_files"]) + len(
            [d for d in result["missing_dirs"] if d.startswith("Setting/")]
        )
        result["setting_integrity"] = round(
            (total_setting - missing_setting) / total_setting * 100
        ) if total_setting > 0 else 0

        # ---- 建议 ----
        if result["missing_files"]:
            result["recommendations"].append(
                f"缺少 {len(result['missing_files'])} 个关键文件: {', '.join(result['missing_files'][:5])}"
            )
        if result["missing_dirs"]:
            result["recommendations"].append(
                f"缺少 {len(result['missing_dirs'])} 个关键目录: {', '.join(result['missing_dirs'])}"
            )
        if result["missing_setting_files"]:
            result["recommendations"].append(
                f"Setting 目录缺少 {len(result['missing_setting_files'])} 个关键文件，请先解包 PCK 资源"
            )
        if result["integrity_score"] < 100:
            result["recommendations"].append("请确保游戏安装完整，或从完整安装中复制缺失文件")
        if not result["exe_exists"]:
            result["recommendations"].append("未找到 Sango7.exe，请确认游戏目录路径正确")
        if result["setting_integrity"] < 100 and result["setting_integrity"] > 0:
            result["recommendations"].append(
                f"Setting 目录完整性 {result['setting_integrity']}%，"
                "请使用 RPGViewer 解包 Patch.pck 到 Setting 目录"
            )

        return result

    def _detect_setting_encoding(self, setting_path: str) -> Dict:
        """检测 Setting 目录的编码（推断语言版本）"""
        info = {
            "detected_lang": "",
            "encoding": "",
            "confidence": "",
        }
        # 优先检查 TermText.ini（最可靠的编码判断依据）
        termtext_path = os.path.join(setting_path, "TermText.ini")
        if os.path.exists(termtext_path):
            try:
                with open(termtext_path, "rb") as f:
                    raw = f.read(4096)  # 读前4KB就够了
                # 检测 BOM
                if raw[:3] == b"\xef\xbb\xbf":
                    info["encoding"] = "UTF-8-BOM"
                    info["detected_lang"] = "zh-CN"
                    info["confidence"] = "high"
                elif raw[:2] == b"\xff\xfe":
                    info["encoding"] = "UTF-16-LE"
                    info["detected_lang"] = "zh-CN"
                    info["confidence"] = "high"
                else:
                    # 尝试 Big5 解码
                    try:
                        raw.decode("big5")
                        info["encoding"] = "Big5"
                        info["detected_lang"] = "zh-TW"
                        info["confidence"] = "high"
                    except UnicodeDecodeError:
                        try:
                            raw.decode("gbk")
                            info["encoding"] = "GBK"
                            info["detected_lang"] = "zh-CN"
                            info["confidence"] = "high"
                        except UnicodeDecodeError:
                            info["encoding"] = "unknown"
                            info["confidence"] = "low"
            except (IOError, OSError):
                info["confidence"] = "error"
        else:
            # 检查 General01.ini 作为备选
            gen_path = os.path.join(setting_path, "General01.ini")
            if os.path.exists(gen_path):
                try:
                    with open(gen_path, "rb") as f:
                        raw = f.read(4096)
                    try:
                        raw.decode("big5")
                        info["encoding"] = "Big5"
                        info["detected_lang"] = "zh-TW"
                        info["confidence"] = "medium"
                    except UnicodeDecodeError:
                        try:
                            raw.decode("gbk")
                            info["encoding"] = "GBK"
                            info["detected_lang"] = "zh-CN"
                            info["confidence"] = "medium"
                        except UnicodeDecodeError:
                            pass
                except (IOError, OSError):
                    pass

        if not info["detected_lang"]:
            info["detected_lang"] = "unknown"
            info["confidence"] = "none"

        return info

    def _hash_file(self, file_path: str, algo: str = "md5") -> str:
        """计算文件哈希"""
        try:
            h = hashlib.new(algo)
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except (IOError, OSError):
            return ""

    def _read_exe_version(self, exe_path: str) -> Dict:
        """尝试从 EXE 中读取 PE 版本信息（始终返回所有字段）"""
        info = {
            "exe_type": "unknown",
            "pe_timestamp": 0,
            "sections": 0,
            "image_size": 0,
            "image_size_mb": 0,
        }
        try:
            with open(exe_path, "rb") as f:
                f.seek(0x3C)
                pe_offset_data = f.read(4)
                if len(pe_offset_data) < 4:
                    return info
                pe_offset = struct.unpack("<I", pe_offset_data)[0]
                f.seek(pe_offset)
                pe_sig = f.read(4)
                if pe_sig != b"PE\x00\x00":
                    return info

                info["exe_type"] = "PE32"
                f.seek(pe_offset + 8)
                ts_data = f.read(4)
                if len(ts_data) == 4:
                    info["pe_timestamp"] = struct.unpack("<I", ts_data)[0]

                machine = struct.unpack("<H", f.read(2))[0]
                if machine == 0x014C:
                    info["exe_type"] = "PE32 (x86)"
                elif machine == 0x8664:
                    info["exe_type"] = "PE32+ (x64)"

                f.seek(pe_offset + 6)
                num_sections = struct.unpack("<H", f.read(2))[0]
                info["sections"] = num_sections

                f.seek(pe_offset + 80)
                size_of_image = struct.unpack("<I", f.read(4))[0]
                info["image_size"] = size_of_image
                info["image_size_mb"] = round(size_of_image / (1024 * 1024), 2)
        except (struct.error, IndexError, IOError, OSError):
            pass
        return info

    def _get_file_timestamp(self, file_path: str) -> str:
        """获取文件修改时间"""
        try:
            import datetime
            ts = os.path.getmtime(file_path)
            return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except (OSError, IOError):
            return ""

    def quick_check(self, game_path: str = None) -> Dict:
        """快速检查（仅检查必要文件存在性）"""
        if game_path:
            self.game_path = game_path
        if not self.game_path:
            return {"valid": False, "message": "未设置游戏目录"}

        exe = os.path.join(self.game_path, "Sango7.exe")
        if not os.path.exists(exe):
            return {"valid": False, "message": "未找到 Sango7.exe"}

        missing = [f for f in self.REQUIRED_FILES
                   if not os.path.exists(os.path.join(self.game_path, f))]
        missing_dirs = [d for d in self.REQUIRED_DIRS
                       if not os.path.isdir(os.path.join(self.game_path, d))]
        return {
            "valid": True,
            "message": "游戏目录有效" + (f"，缺少 {len(missing)} 个文件" if missing else ""),
            "missing_files": missing,
            "missing_dirs": missing_dirs,
        }