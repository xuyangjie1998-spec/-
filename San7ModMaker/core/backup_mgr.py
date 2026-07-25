"""
全局备份还原系统
文件修改前自动备份，EXE修改单独备份程序本体
支持多版本备份、一键还原
"""

import os
import shutil
import time
import json
from datetime import datetime
from typing import List, Optional, Dict


class BackupManager:
    """
    备份管理器
    - 自动备份：修改文件前调用backup_file()
    - 版本管理：按时间戳组织备份
    - 一键还原：restore_all() / restore_file()
    - EXE独立备份：backup_exe()
    """

    BACKUP_ROOT = "backup"
    BACKUP_INDEX = "backup_index.json"

    def __init__(self, game_path: str, backup_dir: str = None):
        self.game_path = game_path
        # 默认使用项目workspace下的backup目录，而非游戏目录
        if backup_dir is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            backup_dir = os.path.join(project_root, "backup")
        self.backup_dir = backup_dir
        self.index: Dict[str, List[dict]] = {}  # 文件路径 -> 备份记录列表
        self._ensure_backup_dir()
        self._load_index()

    def _ensure_backup_dir(self):
        os.makedirs(self.backup_dir, exist_ok=True)

    def _load_index(self):
        index_path = os.path.join(self.backup_dir, self.BACKUP_INDEX)
        if os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    self.index = json.load(f)
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.warning(f"备份索引文件损坏，将重建: {e}")
                self.index = {}
        else:
            self.index = {}

    def _save_index(self):
        index_path = os.path.join(self.backup_dir, self.BACKUP_INDEX)
        try:
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(self.index, f, ensure_ascii=False, indent=2)
        except (IOError, OSError) as e:
            logger.error(f"保存备份索引失败: {e}")

    def backup_file(self, file_path: str) -> str:
        """
        备份单个文件
        返回备份文件路径
        """
        if not os.path.exists(file_path):
            return ""

        rel_path = os.path.relpath(file_path, self.game_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        # 使用相对路径 + 文件名避免不同目录同名文件冲突
        safe_name = rel_path.replace(os.sep, "_").replace("\\", "_")
        backup_name = f"{safe_name}.{timestamp}.bak"
        backup_path = os.path.join(self.backup_dir, backup_name)

        shutil.copy2(file_path, backup_path)

        record = {
            "timestamp": timestamp,
            "backup_path": backup_path,
            "original_path": file_path,
            "rel_path": rel_path,
            "size": os.path.getsize(file_path),
        }

        if rel_path not in self.index:
            self.index[rel_path] = []
        self.index[rel_path].append(record)
        self._save_index()

        # 自动清理：每个文件最多保留 10 个历史备份
        if len(self.index[rel_path]) > 10:
            oldest = self.index[rel_path].pop(0)
            if os.path.exists(oldest["backup_path"]):
                os.remove(oldest["backup_path"])
            self._save_index()

        return backup_path

    def backup_exe(self) -> str:
        """备份Sango7.exe"""
        exe_path = os.path.join(self.game_path, "Sango7.exe")
        return self.backup_file(exe_path)

    def backup_all_settings(self) -> List[str]:
        """备份所有Setting目录下的INI文件"""
        setting_dir = os.path.join(self.game_path, "Setting")
        if not os.path.exists(setting_dir):
            return []

        backed = []
        for root, _, files in os.walk(setting_dir):
            for f in files:
                if f.lower().endswith(".ini"):
                    fp = os.path.join(root, f)
                    bp = self.backup_file(fp)
                    if bp:
                        backed.append(bp)
        return backed

    def restore_file(self, file_path: str, backup_index: int = -1) -> bool:
        """
        还原单个文件
        backup_index: -1表示还原最新备份
        """
        rel_path = os.path.relpath(file_path, self.game_path)
        records = self.index.get(rel_path, [])
        if not records:
            return False

        record = records[backup_index]
        backup_path = record["backup_path"]
        if not os.path.exists(backup_path):
            return False

        shutil.copy2(backup_path, file_path)
        return True

    def restore_all(self) -> Dict[str, bool]:
        """一键还原所有文件"""
        results = {}
        for rel_path in self.index:
            orig_path = os.path.join(self.game_path, rel_path)
            results[rel_path] = self.restore_file(orig_path)
        return results

    def get_backup_history(self, file_path: str = None) -> List[dict]:
        """获取备份历史"""
        if file_path:
            rel_path = os.path.relpath(file_path, self.game_path)
            return self.index.get(rel_path, [])
        # 返回所有备份记录
        all_records = []
        for rel_path, records in self.index.items():
            for r in records:
                all_records.append(r)
        all_records.sort(key=lambda x: x["timestamp"], reverse=True)
        return all_records

    def get_latest_backup(self, file_path: str) -> Optional[dict]:
        """获取文件最新备份"""
        records = self.get_backup_history(file_path)
        return records[-1] if records else None

    def cleanup_old_backups(self, keep_count: int = 10):
        """清理旧备份，每个文件保留最近N个"""
        for rel_path, records in self.index.items():
            if len(records) > keep_count:
                old = records[:-keep_count]
                for r in old:
                    if os.path.exists(r["backup_path"]):
                        os.remove(r["backup_path"])
                self.index[rel_path] = records[-keep_count:]
        self._save_index()

    def get_backup_count(self) -> int:
        """获取总备份数量"""
        return sum(len(v) for v in self.index.values())

    def get_backup_list(self, filename: str) -> List[dict]:
        """获取指定文件名的备份列表（用于差异对比选择）"""
        result = []
        for rel_path, records in self.index.items():
            if os.path.basename(rel_path) == filename:
                for i, r in enumerate(records):
                    result.append({
                        "id": r["timestamp"],
                        "time": r["timestamp"],
                        "label": f"备份 #{len(records) - i}",
                        "size": r.get("size", 0),
                    })
        return result

    def get_backup_path(self, filename: str, backup_id: str) -> Optional[str]:
        """根据文件名和备份ID获取备份文件路径"""
        for rel_path, records in self.index.items():
            if os.path.basename(rel_path) == filename:
                for r in records:
                    if r["timestamp"] == backup_id:
                        return r["backup_path"]
        return None