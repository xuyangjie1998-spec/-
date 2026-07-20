"""
游戏版本检测模块
- 检测 Sango7.exe 的版本（通过 MD5/SHA256 哈希）
- 检测游戏目录结构完整性
- 检测关键文件存在性
"""

import os
import hashlib
import struct
from typing import Dict, Optional


# 已知的游戏版本哈希（待社区贡献完善）
KNOWN_VERSIONS = {
    # 格式: MD5: { version, name, description }
    # 三国群英传7 繁体中文版常见版本
    # 注：以下哈希值为示例，实际值需通过社区收集
}


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
            "md5": "",
            "sha256": "",
            "exe_size": 0,
            "file_timestamp": "",
            "missing_files": [],
            "missing_dirs": [],
            "all_files": {},
            "integrity_score": 0,
            "recommendations": [],
        }

        # 检测 EXE
        if os.path.exists(exe_path):
            result["exe_size"] = os.path.getsize(exe_path)
            result["exe_size_mb"] = round(result["exe_size"] / (1024 * 1024), 2)
            result["md5"] = self._hash_file(exe_path, "md5")
            result["sha256"] = self._hash_file(exe_path, "sha256")

            # 检查已知版本
            if result["md5"] in KNOWN_VERSIONS:
                info = KNOWN_VERSIONS[result["md5"]]
                result["version"] = info.get("version", "unknown")
                result["version_name"] = info.get("name", "未知版本")

            # 提取 EXE 中的版本信息
            exe_info = self._read_exe_version(exe_path)
            result.update(exe_info)

            # 时间戳
            result["file_timestamp"] = self._get_file_timestamp(exe_path)

        # 检测必需文件
        for fname in self.REQUIRED_FILES:
            fpath = os.path.join(self.game_path, fname)
            if not os.path.exists(fpath):
                result["missing_files"].append(fname)
            else:
                result["all_files"][fname] = {
                    "size": os.path.getsize(fpath),
                    "size_mb": round(os.path.getsize(fpath) / (1024 * 1024), 2),
                }

        # 检测必需目录
        for dname in self.REQUIRED_DIRS:
            dpath = os.path.join(self.game_path, dname)
            if not os.path.isdir(dpath):
                result["missing_dirs"].append(dname)

        # 完整性评分
        total_checks = len(self.REQUIRED_FILES) + len(self.REQUIRED_DIRS)
        missing = len(result["missing_files"]) + len(result["missing_dirs"])
        result["integrity_score"] = round((total_checks - missing) / total_checks * 100)

        # 建议
        if result["missing_files"]:
            result["recommendations"].append(
                f"缺少 {len(result['missing_files'])} 个关键文件: {', '.join(result['missing_files'][:5])}"
            )
        if result["missing_dirs"]:
            result["recommendations"].append(
                f"缺少 {len(result['missing_dirs'])} 个关键目录: {', '.join(result['missing_dirs'])}"
            )
        if result["integrity_score"] < 100:
            result["recommendations"].append("请确保游戏安装完整，或从完整安装中复制缺失文件")
        if not result["exe_exists"]:
            result["recommendations"].append("未找到 Sango7.exe，请确认游戏目录路径正确")

        return result

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
        """尝试从 EXE 中读取版本信息"""
        info = {"exe_type": "unknown", "pe_timestamp": 0}
        try:
            with open(exe_path, "rb") as f:
                # 检查 PE 头
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
                # 读取 PE 时间戳
                f.seek(pe_offset + 8)
                ts_data = f.read(4)
                if len(ts_data) == 4:
                    info["pe_timestamp"] = struct.unpack("<I", ts_data)[0]

                # 读取 Machine 类型
                machine = struct.unpack("<H", f.read(2))[0]
                if machine == 0x014C:
                    info["exe_type"] = "PE32 (x86)"
                elif machine == 0x8664:
                    info["exe_type"] = "PE32+ (x64)"

                # 读取 NumberOfSections
                f.seek(pe_offset + 6)
                num_sections = struct.unpack("<H", f.read(2))[0]
                info["sections"] = num_sections

                # 读取 SizeOfImage
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
        return {
            "valid": True,
            "message": f"游戏目录有效" + (f"，缺少 {len(missing)} 个文件" if missing else ""),
            "missing_files": missing,
        }