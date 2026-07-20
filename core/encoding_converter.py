"""
编码转换器
- 批量子目录 INI 文件编码转换（GBK ↔ Big5）
- 编码自动检测
- 转换预览
- 自动备份
"""

import os
import chardet
from typing import Dict, List, Optional


class EncodingConverter:
    """编码转换器 - GBK / Big5 互转"""
    
    # 支持的编码
    SUPPORTED_ENCODINGS = ["gbk", "big5", "utf-8"]
    
    # 编码别名
    ENCODING_ALIASES = {
        "gb2312": "gbk",
        "gb18030": "gbk",
        "cp936": "gbk",
        "cp950": "big5",
        "big5-hkscs": "big5",
    }
    
    def __init__(self, game_path: str = None):
        self.game_path = game_path
    
    def set_game_path(self, game_path: str):
        self.game_path = game_path
    
    def detect_encoding(self, file_path: str) -> dict:
        """检测文件编码"""
        if not os.path.exists(file_path):
            return {"success": False, "message": "文件不存在"}
        
        try:
            with open(file_path, "rb") as f:
                raw = f.read()
            
            result = chardet.detect(raw)
            encoding = result.get("encoding", "unknown")
            confidence = result.get("confidence", 0)
            
            # 规范化编码名
            canonical = self.ENCODING_ALIASES.get(encoding.lower() if encoding else "", encoding.lower() if encoding else "unknown")
            
            return {
                "success": True,
                "file": file_path,
                "encoding": encoding,
                "canonical": canonical,
                "confidence": round(confidence * 100, 1),
                "size_kb": round(len(raw) / 1024, 1),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def preview_conversion(self, file_path: str, target_encoding: str = "gbk") -> dict:
        """预览转换结果（前10行）"""
        if not os.path.exists(file_path):
            return {"success": False, "message": "文件不存在"}
        
        detect_result = self.detect_encoding(file_path)
        if not detect_result["success"]:
            return detect_result
        
        source_encoding = detect_result["canonical"]
        if source_encoding == target_encoding:
            return {"success": True, "same_encoding": True, "message": f"文件已是 {target_encoding} 编码，无需转换"}
        
        try:
            with open(file_path, "rb") as f:
                raw = f.read()
            
            text = raw.decode(source_encoding, errors="replace")
            lines = text.split("\n")
            preview_lines = []
            
            for i, line in enumerate(lines[:10]):
                try:
                    converted = line.encode(target_encoding, errors="replace").decode(target_encoding, errors="replace")
                    preview_lines.append({
                        "line": i + 1,
                        "original": line[:200],
                        "converted": converted[:200],
                        "changed": line != converted,
                    })
                except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
                    preview_lines.append({
                        "line": i + 1,
                        "original": line[:200],
                        "converted": "[编码错误]",
                        "changed": True,
                    })
            
            return {
                "success": True,
                "file": os.path.basename(file_path),
                "source_encoding": source_encoding,
                "target_encoding": target_encoding,
                "total_lines": len(lines),
                "preview": preview_lines,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def convert_file(self, file_path: str, target_encoding: str = "gbk", backup: bool = True) -> dict:
        """转换单个文件编码"""
        if not os.path.exists(file_path):
            return {"success": False, "message": "文件不存在"}
        
        detect_result = self.detect_encoding(file_path)
        if not detect_result["success"]:
            return detect_result
        
        source_encoding = detect_result["canonical"]
        if source_encoding == target_encoding:
            return {"success": True, "skipped": True, "message": f"文件已是 {target_encoding} 编码，跳过"}
        
        try:
            with open(file_path, "rb") as f:
                raw = f.read()
            
            text = raw.decode(source_encoding, errors="replace")
            
            if backup:
                import time
                backup_path = file_path + f".{target_encoding}_bak_{int(time.time())}"
                with open(backup_path, "wb") as f:
                    f.write(raw)
            
            converted = text.encode(target_encoding, errors="replace")
            with open(file_path, "wb") as f:
                f.write(converted)
            
            return {
                "success": True,
                "file": os.path.basename(file_path),
                "source_encoding": source_encoding,
                "target_encoding": target_encoding,
                "backup": backup,
                "message": f"转换成功: {source_encoding} → {target_encoding}",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def batch_scan(self, directory: str = None) -> dict:
        """扫描目录下所有INI文件的编码"""
        if directory is None:
            if not self.game_path:
                return {"success": False, "message": "未设置游戏目录"}
            directory = os.path.join(self.game_path, "Setting")
        
        if not os.path.isdir(directory):
            return {"success": False, "message": f"目录不存在: {directory}"}
        
        files_info = []
        gbk_count = 0
        big5_count = 0
        utf8_count = 0
        unknown_count = 0
        
        for root, _, files in os.walk(directory):
            for fname in files:
                if fname.lower().endswith(".ini"):
                    fpath = os.path.join(root, fname)
                    r = self.detect_encoding(fpath)
                    if r["success"]:
                        rel_path = os.path.relpath(fpath, directory)
                        files_info.append({
                            "file": rel_path,
                            "encoding": r["canonical"],
                            "confidence": r["confidence"],
                            "size_kb": r["size_kb"],
                        })
                        if r["canonical"] == "gbk":
                            gbk_count += 1
                        elif r["canonical"] == "big5":
                            big5_count += 1
                        elif r["canonical"] == "utf-8":
                            utf8_count += 1
                        else:
                            unknown_count += 1
        
        return {
            "success": True,
            "directory": directory,
            "total": len(files_info),
            "gbk_count": gbk_count,
            "big5_count": big5_count,
            "utf8_count": utf8_count,
            "unknown_count": unknown_count,
            "files": sorted(files_info, key=lambda x: x["file"]),
        }
    
    def batch_convert(self, directory: str = None, target_encoding: str = "gbk", backup: bool = True) -> dict:
        """批量转换目录下所有INI文件编码"""
        scan_result = self.batch_scan(directory)
        if not scan_result["success"]:
            return scan_result
        
        target_dir = directory or os.path.join(self.game_path, "Setting")
        
        results = []
        converted = 0
        skipped = 0
        errors = []
        
        for f_info in scan_result["files"]:
            if f_info["encoding"] == target_encoding:
                skipped += 1
                continue
            
            fpath = os.path.join(target_dir, f_info["file"])
            r = self.convert_file(fpath, target_encoding, backup)
            results.append(r)
            if r["success"] and not r.get("skipped"):
                converted += 1
            elif not r["success"]:
                errors.append(r)
        
        return {
            "success": True,
            "total": scan_result["total"],
            "converted": converted,
            "skipped": skipped,
            "errors": len(errors),
            "target_encoding": target_encoding,
            "results": results,
            "message": f"转换完成: {converted} 个文件 → {target_encoding}, {skipped} 个跳过",
        }