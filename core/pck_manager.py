"""
PCK资源管理器 (v1.0)
- 检测游戏目录状态（有Setting文件夹 vs 仅PCK）
- PCK文件格式解析（奥汀科技专有格式）
- 引导用户完成PCK解包流程
- 管理Setting文件夹覆盖工作流

关键发现：群7引擎优先读取Setting/文件夹，不存在时才读Patch.pck
所以MOD制作只需提取Setting，无需重新打包PCK
"""

import os
import struct
import subprocess
import shutil
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PckManager:
    """
    群7 PCK文件管理器
    
    游戏文件结构:
    - Patch.pck: 游戏数据(Setting/ + OBD/等)
    - Shape00~06.pck: 图片资源(SHP格式)
    - ShapeFix.pck: SHP升级包
    - GameData.PCK: 声音字体大地图
    """
    
    # PCK文件魔数
    PCK_MAGIC = b'\x00\x00\x00\x02'  # 奥汀PCK格式标识
    
    # 关键PCK文件名
    PATCH_PCK = "Patch.pck"
    SHAPE_PCKS = [f"Shape{i:02d}.pck" for i in range(7)] + ["ShapeFix.pck"]
    GAMEDATA_PCK = "GameData.PCK"
    
    # 标准目录结构
    REQUIRED_DIRS = ["Setting", "Shape", "Script"]
    SETTING_SUBDIRS = ["bfdata", "HSData", "OBD", "var"]
    SHAPE_SUBDIRS = ["Face", "BFObj", "genhalf"]
    
    def __init__(self, game_path: str = None):
        self.game_path = game_path
        self._pck_cache: Dict[str, dict] = {}
    
    def set_game_path(self, game_path: str):
        self.game_path = game_path
        self._pck_cache.clear()
    
    # ============================================================
    # 游戏状态检测
    # ============================================================
    
    def detect_game_state(self) -> dict:
        """
        检测游戏目录的MOD就绪状态
        
        返回:
        {
            "state": "ready" | "need_extract" | "partial" | "empty",
            "has_setting": bool,
            "pck_files": [...],
            "recommendations": [...]
        }
        """
        if not self.game_path or not os.path.exists(self.game_path):
            return {"state": "empty", "has_setting": False, "pck_files": [], "recommendations": ["请先设置游戏目录"]}
        
        result = {
            "state": "empty",
            "has_setting": False,
            "has_shape": False,
            "pck_files": [],
            "ini_count": 0,
            "recommendations": []
        }
        
        # 检查Setting文件夹
        setting_dir = os.path.join(self.game_path, "Setting")
        if os.path.isdir(setting_dir):
            result["has_setting"] = True
            # 统计INI文件数量
            ini_count = 0
            for root, _, files in os.walk(setting_dir):
                ini_count += sum(1 for f in files if f.lower().endswith(".ini"))
            result["ini_count"] = ini_count
        
        # 检查Shape文件夹
        shape_dir = os.path.join(self.game_path, "Shape")
        if os.path.isdir(shape_dir):
            result["has_shape"] = True
        
        # 检查PCK文件
        pck_files = self._list_pck_files()
        result["pck_files"] = pck_files
        
        # 判定状态
        if result["has_setting"] and result["ini_count"] > 0:
            result["state"] = "ready"
            result["recommendations"].append("游戏目录已就绪，可直接开始MOD制作")
        elif result["has_setting"] and result["ini_count"] == 0:
            result["state"] = "partial"
            result["recommendations"].append("Setting文件夹为空，需要从PCK中提取")
        elif pck_files:
            result["state"] = "need_extract"
            result["recommendations"].append("检测到PCK文件，需要先解包Setting文件夹")
            result["recommendations"].append("提示：游戏优先读取Setting文件夹，解包后无需重新打包")
        else:
            result["state"] = "empty"
            result["recommendations"].append("未检测到游戏数据文件，请确认游戏目录正确")
        
        return result
    
    def _list_pck_files(self) -> List[dict]:
        """列出游戏目录中的所有PCK文件"""
        pck_files = []
        if not self.game_path:
            return pck_files
        
        for fname in os.listdir(self.game_path):
            if fname.lower().endswith(".pck"):
                fpath = os.path.join(self.game_path, fname)
                size_mb = os.path.getsize(fpath) / (1024 * 1024)
                info = self._analyze_pck_header(fpath)
                pck_files.append({
                    "name": fname,
                    "path": fpath,
                    "size_mb": round(size_mb, 2),
                    "type": info.get("type", "unknown"),
                    "file_count": info.get("file_count", 0),
                    "is_main": fname == self.PATCH_PCK,
                })
        
        return pck_files
    
    # ============================================================
    # PCK格式解析
    # ============================================================
    
    def _analyze_pck_header(self, pck_path: str) -> dict:
        """解析PCK文件头，获取基本信息"""
        if pck_path in self._pck_cache:
            return self._pck_cache[pck_path]
        
        result = {"type": "unknown", "file_count": 0, "files": []}
        
        try:
            with open(pck_path, "rb") as f:
                header = f.read(64)
            
            if len(header) < 16:
                return result
            
            # 尝试解析奥汀PCK格式
            # 格式: 4字节魔数 + 4字节文件数 + 4字节索引偏移 + ...
            magic = struct.unpack("<I", header[:4])[0]
            
            if magic == 0x02000000:  # 奥汀PCK魔数(小端)
                result["type"] = "audin_pck"
                result["magic"] = hex(magic)
                
                # 文件计数
                file_count = struct.unpack("<I", header[4:8])[0]
                result["file_count"] = file_count
                
                # 索引表偏移
                if len(header) >= 16:
                    index_offset = struct.unpack("<I", header[12:16])[0]
                    result["index_offset"] = index_offset
                    
                    # 尝试读取文件列表
                    try:
                        f.seek(index_offset)
                        for i in range(min(file_count, 500)):
                            entry = f.read(128)
                            if len(entry) < 12:
                                break
                            # 文件名(64字节) + 偏移(4字节) + 大小(4字节) + ...
                            name_bytes = entry[:64].split(b'\x00')[0]
                            try:
                                name = name_bytes.decode("big5", errors="replace")
                            except (UnicodeDecodeError, LookupError):
                                name = name_bytes.decode("latin-1", errors="replace")
                            offset = struct.unpack("<I", entry[64:68])[0]
                            size = struct.unpack("<I", entry[68:72])[0]
                            result["files"].append({
                                "name": name,
                                "offset": offset,
                                "size": size,
                            })
                    except Exception as e:
                        logger.warning(f"PCK文件条目解析失败: {e}")
            
            elif magic == 0x00000001:  # 另一种变体
                result["type"] = "audin_pck_v2"
                result["magic"] = hex(magic)
            
            else:
                # 尝试作为通用归档检测
                result["type"] = "generic_archive"
                result["magic"] = hex(magic)
        
        except Exception as e:
            result["error"] = str(e)
        
        self._pck_cache[pck_path] = result
        return result
    
    def get_pck_files_list(self, pck_path: str) -> List[dict]:
        """获取PCK包内的文件列表"""
        info = self._analyze_pck_header(pck_path)
        return info.get("files", [])
    
    def extract_pck_file(self, pck_path: str, internal_path: str, output_path: str) -> bool:
        """从PCK中提取单个文件"""
        info = self._analyze_pck_header(pck_path)
        files = info.get("files", [])
        
        target = None
        for f in files:
            if f["name"] == internal_path or f["name"].endswith(internal_path):
                target = f
                break
        
        if not target:
            return False
        
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(pck_path, "rb") as src:
                src.seek(target["offset"])
                data = src.read(target["size"])
            with open(output_path, "wb") as dst:
                dst.write(data)
            return True
        except (IOError, OSError):
            return False
    
    def extract_all_from_pck(self, pck_path: str, output_dir: str) -> dict:
        """从PCK中提取所有文件到指定目录"""
        info = self._analyze_pck_header(pck_path)
        files = info.get("files", [])
        
        if not files:
            return {"success": False, "message": "无法解析PCK文件或文件列表为空", "extracted": 0}
        
        extracted = 0
        errors = []
        
        for f in files:
            try:
                out_path = os.path.join(output_dir, f["name"])
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                
                with open(pck_path, "rb") as src:
                    src.seek(f["offset"])
                    data = src.read(f["size"])
                
                with open(out_path, "wb") as dst:
                    dst.write(data)
                
                extracted += 1
            except Exception as e:
                errors.append({"file": f["name"], "error": str(e)})
        
        return {
            "success": extracted > 0,
            "extracted": extracted,
            "total": len(files),
            "errors": errors,
            "output_dir": output_dir,
        }
    
    # ============================================================
    # Setting文件夹管理
    # ============================================================
    
    def prepare_setting_folder(self) -> dict:
        """
        准备Setting文件夹用于MOD制作
        
        策略:
        1. 如果Setting/已存在且有INI文件 → 直接使用
        2. 如果Patch.pck存在 → 尝试提取
        3. 否则 → 提示用户
        """
        state = self.detect_game_state()
        
        if state["state"] == "ready":
            return {
                "success": True,
                "message": "Setting文件夹已就绪",
                "state": "ready",
                "ini_count": state["ini_count"],
            }
        
        if state["state"] == "need_extract":
            # 尝试从Patch.pck提取
            pck_path = os.path.join(self.game_path, self.PATCH_PCK)
            if os.path.exists(pck_path):
                setting_dir = os.path.join(self.game_path, "Setting")
                result = self.extract_all_from_pck(pck_path, setting_dir)
                
                if result["success"]:
                    return {
                        "success": True,
                        "message": f"成功从Patch.pck提取 {result['extracted']} 个文件到Setting/",
                        "state": "ready",
                        "extracted": result["extracted"],
                    }
                else:
                    return {
                        "success": False,
                        "message": "无法自动提取PCK，请使用RPGViewer手动解包Patch.pck",
                        "state": "need_manual",
                        "help": "下载RPGViewer → 打开Patch.pck → 解包 → 将Setting文件夹放入游戏目录",
                    }
        
        return {
            "success": False,
            "message": "未找到游戏数据，请确认游戏目录正确",
            "state": state["state"],
        }
    
    def get_setting_status(self) -> dict:
        """获取Setting文件夹详细状态"""
        if not self.game_path:
            return {"exists": False, "files": []}
        
        setting_dir = os.path.join(self.game_path, "Setting")
        if not os.path.isdir(setting_dir):
            return {"exists": False, "files": [], "subdirs": []}
        
        files = []
        subdirs = []
        
        for item in sorted(os.listdir(setting_dir)):
            item_path = os.path.join(setting_dir, item)
            if os.path.isfile(item_path):
                files.append({
                    "name": item,
                    "size_kb": round(os.path.getsize(item_path) / 1024, 1),
                    "ext": os.path.splitext(item)[1].lower(),
                })
            elif os.path.isdir(item_path):
                sub_count = sum(1 for _ in os.listdir(item_path))
                subdirs.append({
                    "name": item,
                    "file_count": sub_count,
                })
        
        return {
            "exists": True,
            "path": setting_dir,
            "file_count": len(files),
            "subdir_count": len(subdirs),
            "files": files,
            "subdirs": subdirs,
        }
    
    # ============================================================
    # 工具集成
    # ============================================================
    
    def find_rpgviewer(self) -> Optional[str]:
        """查找系统中的RPGViewer"""
        common_names = [
            "RPGViewer.exe", "RPGViewerBuild.exe",
            "RPGViewer_build1220.exe", "RV.exe",
        ]
        
        # 在游戏目录中查找
        if self.game_path:
            for name in common_names:
                path = os.path.join(self.game_path, name)
                if os.path.exists(path):
                    return path
        
        # 在PATH中查找
        for name in common_names:
            found = shutil.which(name)
            if found:
                return found
        
        return None
    
    def launch_rpgviewer(self, pck_path: str = None) -> dict:
        """尝试启动RPGViewer"""
        rv_path = self.find_rpgviewer()
        if not rv_path:
            return {"success": False, "message": "未找到RPGViewer，请手动下载并放入游戏目录"}
        
        try:
            args = [rv_path]
            if pck_path:
                args.append(pck_path)
            subprocess.Popen(args, cwd=self.game_path)
            return {"success": True, "message": "RPGViewer已启动"}
        except Exception as e:
            return {"success": False, "message": f"启动失败: {e}"}

    # ============================================================
    # PCK 打包
    # ============================================================

    def repack_patch(self, output_path: str = None) -> dict:
        """
        将 Setting/ 文件夹重新打包为 Patch.pck

        格式:
        - 4字节: 魔数 0x02000000
        - 4字节: 文件数量
        - 4字节: 保留 (0)
        - 4字节: 索引表偏移
        - 索引表: 每个条目 128字节 (64字节文件名 + 4字节偏移 + 4字节大小 + 56字节填充)
        - 文件数据
        """
        if not self.game_path:
            return {"success": False, "message": "未设置游戏目录"}

        setting_dir = os.path.join(self.game_path, "Setting")
        if not os.path.isdir(setting_dir):
            return {"success": False, "message": "Setting 文件夹不存在，请先解包 PCK"}

        if not output_path:
            output_path = os.path.join(self.game_path, "Patch.pck")

        # 1. 收集所有文件
        file_list = []
        for root, _, files in os.walk(setting_dir):
            for fname in files:
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, setting_dir).replace("\\", "/")
                file_list.append({
                    "name": rel_path,
                    "path": full_path,
                    "size": os.path.getsize(full_path),
                })

        if not file_list:
            return {"success": False, "message": "Setting 文件夹为空，无文件可打包"}

        file_list.sort(key=lambda x: x["name"])

        # 2. 计算索引表大小
        INDEX_ENTRY_SIZE = 128  # 每个索引入口 128 字节
        HEADER_SIZE = 16        # 文件头 16 字节
        index_size = len(file_list) * INDEX_ENTRY_SIZE
        data_start = HEADER_SIZE + index_size

        # 3. 写入 PCK 文件
        try:
            # 备份原文件
            if os.path.exists(output_path):
                backup_path = output_path + ".bak"
                if not os.path.exists(backup_path):
                    shutil.copy2(output_path, backup_path)

            with open(output_path, "wb") as f:
                # 文件头
                f.write(struct.pack("<I", 0x02000000))  # 魔数
                f.write(struct.pack("<I", len(file_list)))  # 文件数量
                f.write(struct.pack("<I", 0))  # 保留
                f.write(struct.pack("<I", HEADER_SIZE))  # 索引表偏移

                # 索引表
                current_offset = data_start
                for entry in file_list:
                    # 文件名 (64字节, Big5编码)
                    name_bytes = entry["name"].encode("big5", errors="replace")
                    if len(name_bytes) > 63:
                        name_bytes = name_bytes[:63]
                    name_padded = name_bytes + b'\x00' * (64 - len(name_bytes))
                    f.write(name_padded)
                    f.write(struct.pack("<I", current_offset))  # 偏移
                    f.write(struct.pack("<I", entry["size"]))   # 大小
                    f.write(b'\x00' * 56)  # 填充
                    current_offset += entry["size"]

                # 文件数据
                for entry in file_list:
                    with open(entry["path"], "rb") as src:
                        f.write(src.read())

            return {
                "success": True,
                "message": f"打包完成: {len(file_list)} 个文件",
                "file_count": len(file_list),
                "output": output_path,
                "size_mb": round(os.path.getsize(output_path) / (1024 * 1024), 2),
            }
        except Exception as e:
            return {"success": False, "message": f"打包失败: {str(e)}"}

    # ============================================================
    # Shape PCK 解包/重新打包
    # ============================================================

    def extract_shape_pck(self, pck_name: str) -> dict:
        """
        从 ShapeXX.pck 中提取 SHP 资源到 Shape/ 目录
        Shape PCK 格式与 Patch.pck 相同，但内容为 SHP 图片
        """
        if not self.game_path:
            return {"success": False, "message": "未设置游戏目录"}

        pck_path = os.path.join(self.game_path, pck_name)
        if not os.path.exists(pck_path):
            return {"success": False, "message": f"PCK文件不存在: {pck_name}"}

        shape_dir = os.path.join(self.game_path, "Shape")
        os.makedirs(shape_dir, exist_ok=True)

        result = self.extract_all_from_pck(pck_path, shape_dir)
        result["pck_name"] = pck_name
        result["message"] = f"从 {pck_name} 提取了 {result['extracted']}/{result['total']} 个文件到 Shape/ 目录"
        return result

    def extract_all_shape_pcks(self) -> dict:
        """批量提取所有 Shape*.pck 文件"""
        if not self.game_path:
            return {"success": False, "message": "未设置游戏目录"}

        results = []
        total_extracted = 0
        for pck_name in self.SHAPE_PCKS:
            pck_path = os.path.join(self.game_path, pck_name)
            if not os.path.exists(pck_path):
                continue
            r = self.extract_shape_pck(pck_name)
            results.append(r)
            total_extracted += r.get("extracted", 0)

        return {
            "success": total_extracted > 0,
            "message": f"批量提取完成: {total_extracted} 个文件",
            "total_extracted": total_extracted,
            "results": results,
        }

    def repack_shape_pck(self, pck_name: str = "Shape00.pck") -> dict:
        """
        将 Shape/ 目录重新打包为 ShapeXX.pck
        注意：Shape 目录下可能有多个子目录，需要全部打包
        """
        if not self.game_path:
            return {"success": False, "message": "未设置游戏目录"}

        shape_dir = os.path.join(self.game_path, "Shape")
        if not os.path.isdir(shape_dir):
            return {"success": False, "message": "Shape 文件夹不存在"}

        output_path = os.path.join(self.game_path, pck_name)

        # 收集所有文件
        file_list = []
        for root, _, files in os.walk(shape_dir):
            for fname in files:
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, shape_dir).replace("\\", "/")
                file_list.append({
                    "name": rel_path,
                    "path": full_path,
                    "size": os.path.getsize(full_path),
                })

        if not file_list:
            return {"success": False, "message": "Shape 文件夹为空"}

        file_list.sort(key=lambda x: x["name"])

        INDEX_ENTRY_SIZE = 128
        HEADER_SIZE = 16
        index_size = len(file_list) * INDEX_ENTRY_SIZE
        data_start = HEADER_SIZE + index_size

        try:
            if os.path.exists(output_path):
                backup = output_path + ".bak"
                if not os.path.exists(backup):
                    shutil.copy2(output_path, backup)

            with open(output_path, "wb") as f:
                f.write(struct.pack("<I", 0x02000000))
                f.write(struct.pack("<I", len(file_list)))
                f.write(struct.pack("<I", 0))
                f.write(struct.pack("<I", HEADER_SIZE))

                current_offset = data_start
                for entry in file_list:
                    name_bytes = entry["name"].encode("big5", errors="replace")
                    if len(name_bytes) > 63:
                        name_bytes = name_bytes[:63]
                    name_padded = name_bytes + b'\x00' * (64 - len(name_bytes))
                    f.write(name_padded)
                    f.write(struct.pack("<I", current_offset))
                    f.write(struct.pack("<I", entry["size"]))
                    f.write(b'\x00' * 56)
                    current_offset += entry["size"]

                for entry in file_list:
                    with open(entry["path"], "rb") as src:
                        f.write(src.read())

            return {
                "success": True,
                "message": f"Shape PCK 打包完成: {len(file_list)} 个文件",
                "file_count": len(file_list),
                "output": output_path,
                "size_mb": round(os.path.getsize(output_path) / (1024 * 1024), 2),
            }
        except (IOError, OSError) as e:
            return {"success": False, "message": f"Shape PCK 打包失败: {str(e)}"}

    @staticmethod
    def get_info() -> dict:
        return {
            "format": "奥汀科技PCK归档格式",
            "supported_operations": ["解析文件列表", "提取单个文件", "批量提取", "游戏状态检测"],
            "key_finding": "游戏引擎优先读取Setting文件夹，MOD制作无需重新打包PCK",
            "pck_types": {
                "Patch.pck": "游戏数据(Setting/ + OBD/)",
                "Shape00~06.pck": "图片资源(SHP格式)",
                "ShapeFix.pck": "SHP升级包",
                "GameData.PCK": "声音字体大地图",
            },
        }