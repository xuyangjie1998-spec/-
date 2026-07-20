"""
群7存档管理器 (v1.0)
- 存档文件浏览（SG7-0XX.sav / CustomGen.sav）
- 备份/还原
- 十六进制查看器
- 基本存档信息解析
"""

import os
import struct
import shutil
from datetime import datetime
from typing import Dict, List, Optional


class SaveManager:
    """群7存档文件管理器"""
    
    # 常见存档路径
    SAVE_PATHS = [
        "Save",
        os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "LocalLow", "UserJoy", "SANGO7", "Save"),
        os.path.join(os.environ.get("HOMEPATH", ""), "AppData", "LocalLow", "UserJoy", "SANGO7", "Save"),
    ]
    
    def __init__(self, game_path: str = None):
        self.game_path = game_path
        self._backup_dir = None
    
    def set_game_path(self, game_path: str):
        self.game_path = game_path
    
    def find_save_dir(self) -> Optional[str]:
        """查找存档目录"""
        if self.game_path:
            save_dir = os.path.join(self.game_path, "Save")
            if os.path.isdir(save_dir):
                return save_dir
        # 尝试常见位置
        for sp in self.SAVE_PATHS:
            if os.path.isdir(sp):
                return sp
        return None
    
    def list_saves(self) -> dict:
        """列出所有存档文件"""
        save_dir = self.find_save_dir()
        if not save_dir:
            return {"success": False, "message": "未找到存档目录", "saves": [], "save_dir": ""}
        
        saves = []
        for fname in sorted(os.listdir(save_dir)):
            fpath = os.path.join(save_dir, fname)
            if not os.path.isfile(fpath):
                continue
            fname_lower = fname.lower()
            if fname_lower.startswith("sg7-") and fname_lower.endswith(".sav"):
                sz = os.path.getsize(fpath)
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                saves.append({
                    "name": fname,
                    "path": fpath,
                    "size_kb": round(sz / 1024, 1),
                    "size_bytes": sz,
                    "modified": mtime.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": "game_save",
                    "slot": int(fname[4:7]) if fname[4:7].isdigit() else -1,
                })
            elif fname_lower == "customgen.sav":
                sz = os.path.getsize(fpath)
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                saves.append({
                    "name": fname,
                    "path": fpath,
                    "size_kb": round(sz / 1024, 1),
                    "size_bytes": sz,
                    "modified": mtime.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": "custom_gen",
                    "slot": -1,
                })
        
        return {
            "success": True,
            "save_dir": save_dir,
            "saves": sorted(saves, key=lambda s: s.get("slot", 99)),
            "count": len(saves),
        }
    
    def backup_save(self, save_name: str) -> dict:
        """备份存档文件"""
        save_dir = self.find_save_dir()
        if not save_dir:
            return {"success": False, "message": "未找到存档目录"}
        
        src = os.path.join(save_dir, save_name)
        if not os.path.exists(src):
            return {"success": False, "message": f"存档文件不存在: {save_name}"}
        
        # 创建备份目录
        backup_dir = os.path.join(self.game_path or os.path.dirname(save_dir), "SaveBackup")
        os.makedirs(backup_dir, exist_ok=True)
        self._backup_dir = backup_dir
        
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(backup_dir, f"{save_name}.{ts}.bak")
        shutil.copy2(src, dst)
        
        return {
            "success": True,
            "message": f"备份完成: {os.path.basename(dst)}",
            "backup_path": dst,
            "backup_dir": backup_dir,
        }
    
    def restore_save(self, backup_path: str, save_name: str) -> dict:
        """从备份还原存档"""
        save_dir = self.find_save_dir()
        if not save_dir:
            return {"success": False, "message": "未找到存档目录"}
        if not os.path.exists(backup_path):
            return {"success": False, "message": "备份文件不存在"}
        
        dst = os.path.join(save_dir, save_name)
        # 先备份当前存档
        if os.path.exists(dst):
            backup_dir = os.path.join(self.game_path or os.path.dirname(save_dir), "SaveBackup")
            os.makedirs(backup_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            cur_bak = os.path.join(backup_dir, f"{save_name}.restore_{ts}.bak")
            shutil.copy2(dst, cur_bak)
        
        shutil.copy2(backup_path, dst)
        return {"success": True, "message": f"还原完成: {save_name}"}
    
    def list_backups(self) -> dict:
        """列出所有备份文件"""
        save_dir = self.find_save_dir()
        if not save_dir:
            return {"success": False, "message": "未找到存档目录", "backups": []}
        backup_dir = os.path.join(self.game_path or os.path.dirname(save_dir), "SaveBackup")
        if not os.path.isdir(backup_dir):
            return {"success": True, "backup_dir": backup_dir, "backups": [], "count": 0}
        
        backups = []
        for fname in sorted(os.listdir(backup_dir), reverse=True):
            fpath = os.path.join(backup_dir, fname)
            if not os.path.isfile(fpath):
                continue
            sz = os.path.getsize(fpath)
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            # 解析备份文件名: SG7-001.sav.20260101_120000.bak
            parts = fname.rsplit(".", 2)
            orig_name = parts[0] if len(parts) > 1 else fname
            backups.append({
                "name": fname,
                "path": fpath,
                "orig_name": orig_name,
                "size_kb": round(sz / 1024, 1),
                "modified": mtime.strftime("%Y-%m-%d %H:%M:%S"),
            })
        
        return {
            "success": True,
            "backup_dir": backup_dir,
            "backups": backups,
            "count": len(backups),
        }
    
    def delete_backup(self, backup_path: str) -> dict:
        """删除备份文件"""
        if not os.path.exists(backup_path):
            return {"success": False, "message": "备份文件不存在"}
        try:
            os.remove(backup_path)
            return {"success": True, "message": "备份已删除"}
        except OSError as e:
            return {"success": False, "message": str(e)}
    
    def hex_view(self, save_name: str, offset: int = 0, length: int = 1024) -> dict:
        """十六进制查看器"""
        save_dir = self.find_save_dir()
        if not save_dir:
            return {"success": False, "message": "未找到存档目录"}
        
        src = os.path.join(save_dir, save_name)
        if not os.path.exists(src):
            return {"success": False, "message": f"存档文件不存在: {save_name}"}
        
        file_size = os.path.getsize(src)
        if offset >= file_size:
            return {"success": False, "message": "偏移超出文件大小"}
        
        actual_length = min(length, file_size - offset)
        
        try:
            with open(src, "rb") as f:
                f.seek(offset)
                data = f.read(actual_length)
            
            # 格式化为十六进制
            hex_lines = []
            ascii_lines = []
            for i in range(0, len(data), 16):
                chunk = data[i:i+16]
                hex_str = " ".join(f"{b:02X}" for b in chunk)
                ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                hex_lines.append(f"{offset+i:08X}  {hex_str:<48s}  {ascii_str}")
            
            return {
                "success": True,
                "save_name": save_name,
                "file_size": file_size,
                "offset": offset,
                "length": actual_length,
                "hex_dump": "\n".join(hex_lines),
                "raw_base64": __import__("base64").b64encode(data).decode(),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def analyze_save_header(self, save_name: str) -> dict:
        """分析存档文件头，尝试提取基本信息"""
        save_dir = self.find_save_dir()
        if not save_dir:
            return {"success": False, "message": "未找到存档目录"}
        
        src = os.path.join(save_dir, save_name)
        if not os.path.exists(src):
            return {"success": False, "message": f"存档文件不存在: {save_name}"}
        
        try:
            with open(src, "rb") as f:
                header = f.read(256)
            
            info = {
                "success": True,
                "save_name": save_name,
                "file_size": os.path.getsize(src),
                "header_magic": header[:4].hex().upper(),
                "first_bytes": " ".join(f"{b:02X}" for b in header[:32]),
            }
            
            # 尝试检测压缩/加密标记
            if header[:2] == b'\x1f\x8b':
                info["format"] = "GZip压缩"
            elif header[:2] == b'PK':
                info["format"] = "ZIP压缩"
            elif header[:4] == b'\x00\x00\x00\x00':
                info["format"] = "可能是未加密原始数据"
            else:
                info["format"] = "未知格式（可能是专有二进制）"
            
            # 尝试查找可读文本
            text_parts = []
            for i in range(0, len(header), 4):
                try:
                    chunk = header[i:i+4]
                    if all(32 <= b < 127 for b in chunk):
                        text_parts.append(chunk.decode("ascii"))
                except (UnicodeDecodeError, ValueError):
                    pass
            if text_parts:
                info["readable_text"] = " ".join(text_parts)
            
            return info
        except Exception as e:
            return {"success": False, "message": str(e)}