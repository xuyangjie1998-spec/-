
__all__ = ["ModPackager"]

"""
MOD 打包分发系统 (v1.0)
- MOD 目录结构分析与分类
- 跨文件依赖关系解析
- 一键打包、完整打包、增量打包
- 自解压安装器生成（安装/卸载/回滚）
- 多 MOD 冲突检测与解决
- README 自动生成、版本号管理
- 包完整性校验、快照对比

标准 MOD 目录结构:
  ModName/
    Setting/    -- INI 配置文件
    Shape/      -- 图片/模型资源
    Script/     -- 脚本文件
    游戏主程序   -- 可选 EXE 文件
    mod_info.json -- MOD 描述信息
"""

import os
import re
import json
import time
import shutil
import zipfile
import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _ensure_dir(path: str) -> None:
    """确保目录存在，不存在则创建"""
    os.makedirs(path, exist_ok=True)


def _get_file_hash(filepath: str, algorithm: str = "sha256") -> str:
    """计算文件哈希值"""
    if not os.path.isfile(filepath):
        return ""
    h = hashlib.new(algorithm)
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
    except (IOError, OSError) as e:
        logger.warning(f"计算文件哈希失败: {filepath} - {e}")
        return ""
    return h.hexdigest()


def _format_size(size_bytes: int) -> str:
    """格式化文件大小显示"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _classify_file(filepath: str) -> str:
    """将文件归类为 setting / shape / script / other"""
    rel = filepath.replace("\\", "/").lower()
    parts = rel.split("/")
    for i, part in enumerate(parts):
        if part == "setting":
            return "setting"
        if part == "shape":
            return "shape"
        if part == "script":
            return "script"
    return "other"


def _walk_mod_files(mod_path: str) -> List[dict]:
    """遍历 MOD 目录，返回文件信息列表"""
    files = []
    for root, dirs, filenames in os.walk(mod_path):
        for fn in filenames:
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, mod_path)
            try:
                stat = os.stat(fp)
            except OSError:
                stat = None
            files.append({
                "path": fp,
                "relative": rel,
                "size": stat.st_size if stat else 0,
                "mtime": stat.st_mtime if stat else 0,
                "category": _classify_file(rel),
            })
    return files


def _load_ini_sections(filepath: str, encoding: str = "gbk") -> List[Dict[str, Any]]:
    """从 INI 文件加载所有 section 数据，返回 section 列表"""
    sections = []
    if not os.path.isfile(filepath):
        return sections
    current_section = None
    try:
        with open(filepath, "r", encoding=encoding, errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                m = re.match(r"^\[(.+)\]$", line)
                if m:
                    current_section = {"name": m.group(1), "entries": {}}
                    sections.append(current_section)
                elif current_section is not None and "=" in line:
                    key, _, value = line.partition("=")
                    current_section["entries"][key.strip()] = value.strip()
    except (IOError, OSError, UnicodeDecodeError) as e:
        logger.warning(f"读取 INI 文件失败: {filepath} - {e}")
    return sections


def _extract_refs_from_ini(filepath: str, ref_fields: Dict[str, List[str]]) -> Dict[str, Set[str]]:
    """从 INI 文件中提取指定字段的引用值"""
    refs: Dict[str, Set[str]] = {}
    sections = _load_ini_sections(filepath)
    for section in sections:
        for field, target in ref_fields.items():
            if field in section["entries"]:
                if target not in refs:
                    refs[target] = set()
                refs[target].add(section["entries"][field])
    return refs


# ---------------------------------------------------------------------------
# ModPackager
# ---------------------------------------------------------------------------

class ModPackager:
    """
    MOD 打包分发系统

    提供 MOD 从分析到打包到分发的完整流程：
    - 目录分析、依赖解析、冲突检测
    - 一键打包、完整打包、增量打包
    - 安装器生成、README 生成、版本号管理
    """

    # 类型分类规则
    CATEGORY_SETTING = "setting"
    CATEGORY_SHAPE = "shape"
    CATEGORY_SCRIPT = "script"
    CATEGORY_OTHER = "other"

    # 冲突严重程度
    CONFLICT_CRITICAL = "critical"
    CONFLICT_MAJOR = "major"
    CONFLICT_MINOR = "minor"

    # 冲突策略
    STRATEGY_KEEP_FIRST = "keep_first"
    STRATEGY_KEEP_SECOND = "keep_second"
    STRATEGY_MERGE = "merge"
    STRATEGY_AUTO = "auto"

    # 版本递增级别
    VERSION_MAJOR = "major"
    VERSION_MINOR = "minor"
    VERSION_PATCH = "patch"

    # 默认 mod_info 格式
    DEFAULT_MOD_INFO = {
        "name": "",
        "version": "1.0.0",
        "author": "",
        "description": "",
        "dependencies": [],
        "compatibility": "Sango7 v1.0",
        "files": [],
        "created": "",
        "updated": "",
    }

    def __init__(self):
        self._last_result: Optional[dict] = None

    # ------------------------------------------------------------------
    # 1. analyze_mod
    # ------------------------------------------------------------------

    def analyze_mod(self, mod_path: str) -> dict:
        """
        分析 MOD 目录结构

        返回所有文件列表、类型分类、总大小、文件数量、依赖文件列表
        """
        if not os.path.isdir(mod_path):
            return {
                "success": False,
                "message": f"MOD 目录不存在: {mod_path}",
            }

        try:
            all_files = _walk_mod_files(mod_path)
            categories: Dict[str, List[dict]] = {
                "setting": [],
                "shape": [],
                "script": [],
                "other": [],
            }
            total_size = 0
            for f in all_files:
                cat = f["category"]
                categories.setdefault(cat, [])
                categories[cat].append(f)
                total_size += f["size"]

            # 识别依赖文件
            dependency_files = []
            for f in all_files:
                if f["relative"].lower().endswith(".ini"):
                    dependency_files.append(f["relative"])

            # 查找 mod_info.json
            info_path = os.path.join(mod_path, "mod_info.json")
            mod_info = None
            if os.path.isfile(info_path):
                try:
                    with open(info_path, "r", encoding="utf-8") as fh:
                        mod_info = json.load(fh)
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"mod_info.json 读取失败: {e}")

            result = {
                "success": True,
                "mod_path": os.path.abspath(mod_path),
                "mod_name": os.path.basename(mod_path),
                "total_files": len(all_files),
                "total_size": total_size,
                "total_size_display": _format_size(total_size),
                "categories": {
                    cat: {
                        "count": len(files),
                        "size": sum(f["size"] for f in files),
                        "size_display": _format_size(sum(f["size"] for f in files)),
                        "files": [f["relative"] for f in files],
                    }
                    for cat, files in categories.items()
                },
                "file_list": [f["relative"] for f in all_files],
                "file_details": all_files,
                "dependency_files": dependency_files,
                "mod_info": mod_info,
            }
            self._last_result = result
            return result
        except Exception as e:
            logger.exception(f"分析 MOD 失败: {e}")
            return {"success": False, "message": str(e)}

    # ------------------------------------------------------------------
    # 2. resolve_dependencies
    # ------------------------------------------------------------------

    def resolve_dependencies(self, mod_path: str, game_path: str) -> dict:
        """
        解析 MOD 的跨文件依赖关系

        检查 MOD 中 INI 字段引用的其他 ID 是否在 MOD 或原版中存在。
        返回依赖关系图、缺失依赖列表、外部依赖列表。
        """
        if not os.path.isdir(mod_path):
            return {"success": False, "message": f"MOD 目录不存在: {mod_path}"}

        # 定义跨文件引用规则
        # key: 源文件名, value: { 字段名: (目标文件名, Section名, 描述) }
        ref_rules = {
            "General01.ini": {
                "BFSoldier": ("Soldier.ini", "SOLDIER", "No", "武将基础兵种"),
                "BFSoldier1": ("Soldier.ini", "SOLDIER", "No", "武将进阶兵种1"),
                "BFSoldier2": ("Soldier.ini", "SOLDIER", "No", "武将进阶兵种2"),
                "Formation": ("Format.ini", "FORMAT", "No", "武将阵型"),
                "Lord": ("Nation.ini", "NATION", "No", "武将所属势力"),
                "SuperSkill": ("SuperAtk.ini", "SUPERATK", "No", "武将必杀技"),
            },
            "Soldier.ini": {
                "Upgrade": ("Soldier.ini", "SOLDIER", "No", "兵种升级目标"),
            },
            "Thing.ini": {
                "ScriptNo": ("Script.so", "SCRIPT", "id", "物品脚本"),
            },
            "Nation.ini": {
                "Lord": ("General01.ini", "GENERAL", "No", "势力君主"),
            },
            "City01.ini": {
                "Lord": ("General01.ini", "GENERAL", "No", "城池君主"),
            },
            "City02.ini": {
                "Lord": ("General01.ini", "GENERAL", "No", "城池君主"),
            },
            "City03.ini": {
                "Lord": ("General01.ini", "GENERAL", "No", "城池君主"),
            },
            "City04.ini": {
                "Lord": ("General01.ini", "GENERAL", "No", "城池君主"),
            },
            "City05.ini": {
                "Lord": ("General01.ini", "GENERAL", "No", "城池君主"),
            },
            "City06.ini": {
                "Lord": ("General01.ini", "GENERAL", "No", "城池君主"),
            },
            "City07.ini": {
                "Lord": ("General01.ini", "GENERAL", "No", "城池君主"),
            },
            "City08.ini": {
                "Lord": ("General01.ini", "GENERAL", "No", "城池君主"),
            },
            "City09.ini": {
                "Lord": ("General01.ini", "GENERAL", "No", "城池君主"),
            },
            "City10.ini": {
                "Lord": ("General01.ini", "GENERAL", "No", "城池君主"),
            },
        }

        # 收集 MOD 中所有可用的引用目标
        mod_ids: Dict[str, Dict[str, Set[str]]] = {}
        mod_files = _walk_mod_files(mod_path)
        for f in mod_files:
            if f["relative"].lower().endswith(".ini"):
                basename = os.path.basename(f["relative"])
                sections = _load_ini_sections(f["path"])
                if basename not in mod_ids:
                    mod_ids[basename] = {}
                for sec in sections:
                    if "No" in sec["entries"]:
                        if sec["name"] not in mod_ids[basename]:
                            mod_ids[basename][sec["name"]] = set()
                        mod_ids[basename][sec["name"]].add(sec["entries"]["No"])

        # 收集原版游戏中的引用目标
        game_ids: Dict[str, Dict[str, Set[str]]] = {}
        if game_path and os.path.isdir(game_path):
            game_setting = os.path.join(game_path, "Setting")
            if os.path.isdir(game_setting):
                for fn in os.listdir(game_setting):
                    if fn.lower().endswith(".ini"):
                        fp = os.path.join(game_setting, fn)
                        sections = _load_ini_sections(fp)
                        if fn not in game_ids:
                            game_ids[fn] = {}
                        for sec in sections:
                            if "No" in sec["entries"]:
                                if sec["name"] not in game_ids[fn]:
                                    game_ids[fn][sec["name"]] = set()
                                game_ids[fn][sec["name"]].add(sec["entries"]["No"])

        # 解析 MOD 中每个文件的对其他文件的引用
        dependency_graph: Dict[str, List[dict]] = {}
        missing_deps: List[dict] = []
        external_deps: List[dict] = []
        internal_deps: List[dict] = []

        for f in mod_files:
            if not f["relative"].lower().endswith(".ini"):
                continue
            basename = os.path.basename(f["relative"])
            if basename not in ref_rules:
                continue
            rules = ref_rules[basename]
            sections = _load_ini_sections(f["path"])
            for sec in sections:
                for field, (target_file, target_section, target_key, desc) in rules.items():
                    if field not in sec["entries"]:
                        continue
                    ref_value = sec["entries"][field]
                    dep_entry = {
                        "source_file": basename,
                        "source_section": sec["name"],
                        "source_field": field,
                        "ref_value": ref_value,
                        "target_file": target_file,
                        "target_section": target_section,
                        "target_key": target_key,
                        "description": desc,
                    }

                    if basename not in dependency_graph:
                        dependency_graph[basename] = []

                    # 检查 MOD 内部是否满足
                    mod_satisfied = False
                    mod_target = mod_ids.get(target_file, {}).get(target_section, set())
                    if ref_value in mod_target:
                        dep_entry["status"] = "internal"
                        internal_deps.append(dep_entry)
                        mod_satisfied = True

                    # 检查原版是否满足
                    game_satisfied = False
                    game_target = game_ids.get(target_file, {}).get(target_section, set())
                    if ref_value in game_target:
                        dep_entry["status"] = "external"
                        external_deps.append(dep_entry)
                        game_satisfied = True

                    if not mod_satisfied and not game_satisfied:
                        dep_entry["status"] = "missing"
                        missing_deps.append(dep_entry)

                    dependency_graph[basename].append(dep_entry)

        result = {
            "success": True,
            "mod_path": os.path.abspath(mod_path),
            "game_path": os.path.abspath(game_path) if game_path else None,
            "dependency_graph": dependency_graph,
            "internal_dependencies": internal_deps,
            "external_dependencies": external_deps,
            "missing_dependencies": missing_deps,
            "missing_count": len(missing_deps),
            "total_dependencies": len(internal_deps) + len(external_deps) + len(missing_deps),
            "is_resolved": len(missing_deps) == 0,
        }
        self._last_result = result
        return result

    # ------------------------------------------------------------------
    # 3. pack_one_click
    # ------------------------------------------------------------------

    def pack_one_click(self, mod_path: str, output_path: str = None) -> dict:
        """
        一键打包：自动分析 → 校验 → 打包 → 生成 ZIP
        """
        if not os.path.isdir(mod_path):
            return {"success": False, "message": f"MOD 目录不存在: {mod_path}"}

        # 步骤1: 分析
        analysis = self.analyze_mod(mod_path)
        if not analysis["success"]:
            return {"success": False, "message": "分析 MOD 失败", "analysis": analysis}

        # 步骤2: 基础校验
        validation_errors = []
        if analysis["total_files"] == 0:
            validation_errors.append("MOD 目录为空，没有文件可打包")

        # 检查是否有 mod_info.json
        mod_info = analysis.get("mod_info")
        if not mod_info:
            validation_errors.append("缺少 mod_info.json，将使用默认信息")

        # 步骤3: 确定输出路径
        if output_path is None:
            mod_name = os.path.basename(mod_path)
            output_path = os.path.join(os.path.dirname(os.path.abspath(mod_path)),
                                       f"{mod_name}_packed.zip")
        output_path = os.path.abspath(output_path)

        # 步骤4: 打包 ZIP
        try:
            _ensure_dir(os.path.dirname(output_path))
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, filenames in os.walk(mod_path):
                    for fn in filenames:
                        fp = os.path.join(root, fn)
                        arcname = os.path.relpath(fp, mod_path)
                        zf.write(fp, arcname)
        except Exception as e:
            logger.exception(f"打包 ZIP 失败: {e}")
            return {"success": False, "message": f"打包失败: {e}"}

        # 步骤5: 计算打包结果
        zip_size = os.path.getsize(output_path) if os.path.isfile(output_path) else 0

        file_manifest = []
        for root, dirs, filenames in os.walk(mod_path):
            for fn in filenames:
                fp = os.path.join(root, fn)
                rel = os.path.relpath(fp, mod_path)
                try:
                    fhash = _get_file_hash(fp)
                except Exception:
                    fhash = ""
                file_manifest.append({
                    "relative": rel,
                    "size": os.path.getsize(fp),
                    "sha256": fhash,
                })

        if not mod_info:
            mod_info = {
                "name": os.path.basename(mod_path),
                "version": "1.0.0",
                "author": "Unknown",
                "description": "",
                "dependencies": [],
                "compatibility": "Sango7 v1.0",
                "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        result = {
            "success": True,
            "zip_path": output_path,
            "zip_size": zip_size,
            "zip_size_display": _format_size(zip_size),
            "file_count": analysis["total_files"],
            "file_manifest": file_manifest,
            "mod_info": mod_info,
            "validation_errors": validation_errors,
            "validation_warnings": [],
            "categories": analysis["categories"],
        }
        self._last_result = result
        return result

    # ------------------------------------------------------------------
    # 4. pack_full
    # ------------------------------------------------------------------

    def pack_full(self, mod_path: str, output_path: str = None,
                  compress: bool = True) -> dict:
        """
        完整打包：打包 Setting/Shape/Script/EXE 所有文件，
        生成 mod_info.json + 文件清单，支持可选的压缩
        """
        if not os.path.isdir(mod_path):
            return {"success": False, "message": f"MOD 目录不存在: {mod_path}"}

        # 分析
        analysis = self.analyze_mod(mod_path)
        if not analysis["success"]:
            return {"success": False, "message": "分析 MOD 失败"}

        # 读取或生成 mod_info
        mod_info = analysis.get("mod_info") or {}
        info_path = os.path.join(mod_path, "mod_info.json")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        updated_info = {
            "name": mod_info.get("name", os.path.basename(mod_path)),
            "version": mod_info.get("version", "1.0.0"),
            "author": mod_info.get("author", ""),
            "description": mod_info.get("description", ""),
            "dependencies": mod_info.get("dependencies", []),
            "compatibility": mod_info.get("compatibility", "Sango7 v1.0"),
            "files": analysis["file_list"],
            "total_files": analysis["total_files"],
            "total_size": analysis["total_size"],
            "total_size_display": _format_size(analysis["total_size"]),
            "created": mod_info.get("created", now_str),
            "updated": now_str,
        }

        # 写入 mod_info.json
        try:
            with open(info_path, "w", encoding="utf-8") as fh:
                json.dump(updated_info, fh, ensure_ascii=False, indent=2)
        except (IOError, OSError) as e:
            logger.warning(f"写入 mod_info.json 失败: {e}")

        # 确定输出路径
        if output_path is None:
            mod_name = updated_info["name"] or os.path.basename(mod_path)
            version = updated_info["version"]
            output_path = os.path.join(
                os.path.dirname(os.path.abspath(mod_path)),
                f"{mod_name}_v{version}_full.zip"
            )
        output_path = os.path.abspath(output_path)

        # 打包
        try:
            _ensure_dir(os.path.dirname(output_path))
            compression = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
            with zipfile.ZipFile(output_path, "w", compression) as zf:
                for root, dirs, filenames in os.walk(mod_path):
                    for fn in filenames:
                        fp = os.path.join(root, fn)
                        arcname = os.path.relpath(fp, mod_path)
                        zf.write(fp, arcname)
        except Exception as e:
            logger.exception(f"完整打包失败: {e}")
            return {"success": False, "message": f"打包失败: {e}"}

        zip_size = os.path.getsize(output_path) if os.path.isfile(output_path) else 0

        # 生成文件清单
        manifest = []
        for f in analysis["file_details"]:
            try:
                fhash = _get_file_hash(f["path"])
            except Exception:
                fhash = ""
            manifest.append({
                "relative": f["relative"],
                "size": f["size"],
                "category": f["category"],
                "sha256": fhash,
            })

        result = {
            "success": True,
            "zip_path": output_path,
            "zip_size": zip_size,
            "zip_size_display": _format_size(zip_size),
            "mod_info": updated_info,
            "file_manifest": manifest,
            "file_count": len(manifest),
            "compressed": compress,
            "categories": analysis["categories"],
        }
        self._last_result = result
        return result

    # ------------------------------------------------------------------
    # 5. pack_incremental
    # ------------------------------------------------------------------

    def pack_incremental(self, mod_path: str, snapshot_path: str,
                         output_path: str = None) -> dict:
        """
        增量打包：对比快照，仅打包变更的文件
        """
        if not os.path.isdir(mod_path):
            return {"success": False, "message": f"MOD 目录不存在: {mod_path}"}
        if not os.path.isfile(snapshot_path):
            return {"success": False, "message": f"快照文件不存在: {snapshot_path}"}

        # 加载快照
        try:
            with open(snapshot_path, "r", encoding="utf-8") as fh:
                snapshot = json.load(fh)
        except (json.JSONDecodeError, IOError) as e:
            return {"success": False, "message": f"快照文件读取失败: {e}"}

        snapshot_files = snapshot.get("files", {})
        snapshot_files_by_rel = {f["relative"]: f for f in snapshot_files}

        # 分析当前状态
        current_files = _walk_mod_files(mod_path)
        current_files_by_rel = {f["relative"]: f for f in current_files}

        # 对比变更
        added = []
        modified = []
        deleted = []
        unchanged = []

        # 检查新增和修改
        for rel, cf in current_files_by_rel.items():
            if rel not in snapshot_files_by_rel:
                added.append(cf)
            else:
                sf = snapshot_files_by_rel[rel]
                if cf["size"] != sf.get("size", -1) or cf["mtime"] != sf.get("mtime", -1):
                    # 进一步检查哈希确认
                    try:
                        cf_hash = _get_file_hash(cf["path"])
                    except Exception:
                        cf_hash = ""
                    if cf_hash != sf.get("sha256", ""):
                        modified.append(cf)
                    else:
                        unchanged.append(cf)
                else:
                    unchanged.append(cf)

        # 检查删除
        for rel, sf in snapshot_files_by_rel.items():
            if rel not in current_files_by_rel:
                deleted.append({
                    "relative": rel,
                    "size": sf.get("size", 0),
                    "category": sf.get("category", "other"),
                })

        changed_files = [f["relative"] for f in added + modified]
        changed_count = len(changed_files)

        if changed_count == 0:
            return {
                "success": True,
                "message": "没有检测到文件变更，无需打包",
                "changed_files": [],
                "added": [],
                "modified": [],
                "deleted": [],
                "unchanged": len(unchanged),
                "has_changes": False,
            }

        # 确定输出路径
        if output_path is None:
            mod_name = os.path.basename(mod_path)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(
                os.path.dirname(os.path.abspath(mod_path)),
                f"{mod_name}_incremental_{ts}.zip"
            )
        output_path = os.path.abspath(output_path)

        # 打包变更文件
        try:
            _ensure_dir(os.path.dirname(output_path))
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in added + modified:
                    zf.write(f["path"], f["relative"])
                # 添加变更清单
                changelog = {
                    "snapshot": os.path.basename(snapshot_path),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "added": [f["relative"] for f in added],
                    "modified": [f["relative"] for f in modified],
                    "deleted": [f["relative"] for f in deleted],
                }
                zf.writestr("_changelog.json", json.dumps(changelog, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.exception(f"增量打包失败: {e}")
            return {"success": False, "message": f"打包失败: {e}"}

        zip_size = os.path.getsize(output_path) if os.path.isfile(output_path) else 0

        result = {
            "success": True,
            "zip_path": output_path,
            "zip_size": zip_size,
            "zip_size_display": _format_size(zip_size),
            "changed_files": changed_files,
            "changed_count": changed_count,
            "added": [f["relative"] for f in added],
            "added_count": len(added),
            "modified": [f["relative"] for f in modified],
            "modified_count": len(modified),
            "deleted": [f["relative"] for f in deleted],
            "deleted_count": len(deleted),
            "unchanged": len(unchanged),
            "has_changes": True,
        }
        self._last_result = result
        return result

    # ------------------------------------------------------------------
    # 6. generate_installer
    # ------------------------------------------------------------------

    def generate_installer(self, package_path: str,
                           output_path: str = None) -> dict:
        """
        生成自解压安装器

        创建 Python 安装脚本 + 批处理文件，支持安装/卸载/回滚。
        安装器功能：备份原文件 → 复制 MOD 文件 → 记录安装日志 → 支持卸载回滚
        """
        if not os.path.isfile(package_path):
            return {"success": False, "message": f"包文件不存在: {package_path}"}

        # 读取包信息
        mod_info = {}
        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                if "mod_info.json" in zf.namelist():
                    mod_info = json.loads(zf.read("mod_info.json").decode("utf-8"))
        except (zipfile.BadZipFile, json.JSONDecodeError) as e:
            logger.warning(f"读取包信息失败: {e}")

        mod_name = mod_info.get("name", os.path.splitext(os.path.basename(package_path))[0])
        mod_version = mod_info.get("version", "1.0.0")

        # 确定输出目录
        if output_path is None:
            output_path = os.path.join(
                os.path.dirname(os.path.abspath(package_path)),
                f"{mod_name}_v{mod_version}_installer"
            )
        output_path = os.path.abspath(output_path)
        _ensure_dir(output_path)

        # 复制包文件到安装器目录
        dest_pkg = os.path.join(output_path, os.path.basename(package_path))
        if os.path.abspath(dest_pkg) != os.path.abspath(package_path):
            shutil.copy2(package_path, dest_pkg)

        # 生成 install.py
        install_py = self._generate_install_py(mod_name, mod_version, package_path)
        install_py_path = os.path.join(output_path, "install.py")
        with open(install_py_path, "w", encoding="utf-8") as fh:
            fh.write(install_py)

        # 生成 install.bat
        install_bat = self._generate_install_bat(mod_name)
        install_bat_path = os.path.join(output_path, "install.bat")
        with open(install_bat_path, "w", encoding="utf-8") as fh:
            fh.write(install_bat)

        # 生成 uninstall.bat
        uninstall_bat = self._generate_uninstall_bat(mod_name)
        uninstall_bat_path = os.path.join(output_path, "uninstall.bat")
        with open(uninstall_bat_path, "w", encoding="utf-8") as fh:
            fh.write(uninstall_bat)

        result = {
            "success": True,
            "installer_dir": output_path,
            "package_name": os.path.basename(package_path),
            "mod_name": mod_name,
            "mod_version": mod_version,
            "files": {
                "install_py": install_py_path,
                "install_bat": install_bat_path,
                "uninstall_bat": uninstall_bat_path,
                "package": dest_pkg,
            },
            "instructions": (
                f"安装器已生成在: {output_path}\n"
                f"安装: 双击 install.bat 或运行 python install.py install\n"
                f"卸载: 双击 uninstall.bat 或运行 python install.py uninstall\n"
                f"回滚: 运行 python install.py rollback"
            ),
        }
        self._last_result = result
        return result

    def _generate_install_py(self, mod_name: str, mod_version: str,
                             package_path: str) -> str:
        """生成安装 Python 脚本内容"""
        pkg_basename = os.path.basename(package_path)
        return f'''"""
{mod_name} v{mod_version} - 安装器
用法:
  python install.py install    -- 安装 MOD
  python install.py uninstall  -- 卸载 MOD
  python install.py rollback   -- 回滚到安装前状态
"""

import os
import sys
import json
import shutil
import zipfile
import hashlib
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_FILE = os.path.join(SCRIPT_DIR, "{pkg_basename}")
LOG_FILE = os.path.join(SCRIPT_DIR, "install_log.json")
BACKUP_DIR = os.path.join(SCRIPT_DIR, "backup")

# 游戏目录，可通过命令行参数或环境变量指定
GAME_DIR = os.environ.get("SANGO7_DIR", os.path.join(SCRIPT_DIR, "game"))


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{{ts}}] {{msg}}")


def backup_file(filepath):
    """备份原文件"""
    if not os.path.exists(filepath):
        return None
    rel = os.path.relpath(filepath, GAME_DIR)
    safe_name = rel.replace(os.sep, "_").replace("\\\\", "_")
    backup_path = os.path.join(BACKUP_DIR, safe_name + ".bak")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copy2(filepath, backup_path)
    return backup_path


def restore_backup(backup_path, original_path):
    """从备份还原文件"""
    if os.path.exists(backup_path):
        os.makedirs(os.path.dirname(original_path), exist_ok=True)
        shutil.copy2(backup_path, original_path)
        return True
    return False


def install():
    """安装 MOD 到游戏目录"""
    if not os.path.exists(PACKAGE_FILE):
        log(f"错误: 找不到包文件 {{PACKAGE_FILE}}")
        return False

    log(f"开始安装 {mod_name} v{mod_version}...")
    log(f"游戏目录: {{GAME_DIR}}")

    if not os.path.isdir(GAME_DIR):
        log(f"错误: 游戏目录不存在 {{GAME_DIR}}")
        log("请设置 SANGO7_DIR 环境变量，或将游戏放在 game/ 目录下")
        return False

    install_log = {{"mod_name": "{mod_name}", "mod_version": "{mod_version}",
                   "installed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   "backups": [], "files": []}}

    try:
        with zipfile.ZipFile(PACKAGE_FILE, "r") as zf:
            file_list = [n for n in zf.namelist() if not n.startswith("_")]

            for name in file_list:
                dest = os.path.join(GAME_DIR, name)
                if name.startswith("mod_info"):
                    dest = os.path.join(SCRIPT_DIR, "mod_info_installed.json")
                    continue

                # 备份原文件
                if os.path.exists(dest):
                    bak = backup_file(dest)
                    if bak:
                        install_log["backups"].append({{"original": dest, "backup": bak}})

                # 解压文件
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with zf.open(name) as src:
                    with open(dest, "wb") as dst:
                        dst.write(src.read())

                install_log["files"].append(dest)
                log(f"  已安装: {{name}}")

        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(install_log, f, ensure_ascii=False, indent=2)

        log("安装完成!")
        return True
    except Exception as e:
        log(f"安装失败: {{e}}")
        return False


def uninstall():
    """卸载 MOD，从备份还原"""
    if not os.path.exists(LOG_FILE):
        log("没有找到安装日志，无法卸载")
        return False

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        install_log = json.load(f)

    log(f"开始卸载 {mod_name}...")

    # 还原备份文件
    for entry in install_log.get("backups", []):
        backup_path = entry["backup"]
        original_path = entry["original"]
        if restore_backup(backup_path, original_path):
            log(f"  已还原: {{os.path.relpath(original_path, GAME_DIR)}}")

    # 删除 MOD 文件（未被备份覆盖的）
    for fp in install_log.get("files", []):
        if os.path.exists(fp) and not any(
            b["original"] == fp for b in install_log.get("backups", [])
        ):
            os.remove(fp)
            log(f"  已删除: {{os.path.relpath(fp, GAME_DIR)}}")

    # 清理空目录
    for fp in install_log.get("files", []):
        d = os.path.dirname(fp)
        while d.startswith(GAME_DIR) and d != GAME_DIR:
            try:
                if not os.listdir(d):
                    os.rmdir(d)
            except OSError:
                break
            d = os.path.dirname(d)

    log("卸载完成!")
    return True


def rollback():
    """回滚到安装前状态"""
    log("执行回滚...")
    return uninstall()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python install.py <install|uninstall|rollback>")
        sys.exit(1)

    action = sys.argv[1].lower()
    if action == "install":
        success = install()
    elif action == "uninstall":
        success = uninstall()
    elif action == "rollback":
        success = rollback()
    else:
        print(f"未知操作: {{action}}")
        sys.exit(1)

    sys.exit(0 if success else 1)
'''

    def _generate_install_bat(self, mod_name: str) -> str:
        """生成安装批处理文件"""
        return f'''@echo off
chcp 65001 >nul
title {mod_name} - 安装器
echo ====================================
echo   {mod_name} 安装器
echo ====================================
echo.
echo 正在安装 MOD...
python install.py install
echo.
if %ERRORLEVEL% EQU 0 (
    echo 安装成功!
) else (
    echo 安装失败，请查看上方错误信息。
)
echo.
pause
'''

    def _generate_uninstall_bat(self, mod_name: str) -> str:
        """生成卸载批处理文件"""
        return f'''@echo off
chcp 65001 >nul
title {mod_name} - 卸载器
echo ====================================
echo   {mod_name} 卸载器
echo ====================================
echo.
echo 正在卸载 MOD...
python install.py uninstall
echo.
if %ERRORLEVEL% EQU 0 (
    echo 卸载成功!
) else (
    echo 卸载失败，请查看上方错误信息。
)
echo.
pause
'''

    # ------------------------------------------------------------------
    # 7. detect_conflicts
    # ------------------------------------------------------------------

    def detect_conflicts(self, mod1_path: str, mod2_path: str) -> dict:
        """
        检测两个 MOD 的文件冲突

        返回冲突文件列表、冲突类型、冲突严重程度
        """
        if not os.path.isdir(mod1_path):
            return {"success": False, "message": f"MOD1 目录不存在: {mod1_path}"}
        if not os.path.isdir(mod2_path):
            return {"success": False, "message": f"MOD2 目录不存在: {mod2_path}"}

        mod1_files = _walk_mod_files(mod1_path)
        mod2_files = _walk_mod_files(mod2_path)

        mod1_by_rel = {f["relative"]: f for f in mod1_files}
        mod2_by_rel = {f["relative"]: f for f in mod2_files}

        conflicts = []
        common_files = set(mod1_by_rel.keys()) & set(mod2_by_rel.keys())

        for rel in common_files:
            f1 = mod1_by_rel[rel]
            f2 = mod2_by_rel[rel]

            # 跳过 mod_info.json
            if rel.lower() == "mod_info.json":
                continue

            is_identical = False
            try:
                h1 = _get_file_hash(f1["path"])
                h2 = _get_file_hash(f2["path"])
                is_identical = h1 and h2 and h1 == h2
            except Exception:
                pass

            if is_identical:
                continue

            ext = os.path.splitext(rel)[1].lower()

            if ext == ".ini":
                conflict_type = "mergeable"
                severity = self.CONFLICT_MAJOR
            elif ext in (".obd", ".so", ".pck"):
                conflict_type = "unmergeable"
                severity = self.CONFLICT_CRITICAL
            elif ext in (".shp", ".png", ".jpg", ".bmp"):
                conflict_type = "overwrite"
                severity = self.CONFLICT_MINOR
            else:
                conflict_type = "overwrite"
                severity = self.CONFLICT_MAJOR

            conflicts.append({
                "file": rel,
                "mod1_size": f1["size"],
                "mod2_size": f2["size"],
                "mod1_category": f1["category"],
                "mod2_category": f2["category"],
                "conflict_type": conflict_type,
                "severity": severity,
            })

        critical_count = sum(1 for c in conflicts if c["severity"] == self.CONFLICT_CRITICAL)
        major_count = sum(1 for c in conflicts if c["severity"] == self.CONFLICT_MAJOR)
        minor_count = sum(1 for c in conflicts if c["severity"] == self.CONFLICT_MINOR)

        result = {
            "success": True,
            "mod1_path": os.path.abspath(mod1_path),
            "mod2_path": os.path.abspath(mod2_path),
            "mod1_name": os.path.basename(mod1_path),
            "mod2_name": os.path.basename(mod2_path),
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
            "critical_count": critical_count,
            "major_count": major_count,
            "minor_count": minor_count,
            "has_conflicts": len(conflicts) > 0,
            "common_files": sorted(common_files),
            "common_count": len(common_files),
        }
        self._last_result = result
        return result

    # ------------------------------------------------------------------
    # 8. resolve_conflicts
    # ------------------------------------------------------------------

    def resolve_conflicts(self, mod1_path: str, mod2_path: str,
                          strategy: str = "auto") -> dict:
        """
        冲突解决

        strategy:
          - "keep_first": 保留 MOD1 的文件
          - "keep_second": 保留 MOD2 的文件
          - "merge": 尝试 INI 合并
          - "auto": 自动选择（INI 合并，其他保留 MOD1）
        """
        if strategy not in (self.STRATEGY_KEEP_FIRST, self.STRATEGY_KEEP_SECOND,
                            self.STRATEGY_MERGE, self.STRATEGY_AUTO):
            return {"success": False, "message": f"未知策略: {strategy}"}

        # 先检测冲突
        detection = self.detect_conflicts(mod1_path, mod2_path)
        if not detection["success"]:
            return detection

        if not detection["has_conflicts"]:
            return {
                "success": True,
                "message": "没有冲突需要解决",
                "resolved": [],
                "unresolved": [],
            }

        resolved = []
        unresolved = []

        for conf in detection["conflicts"]:
            rel = conf["file"]
            f1_path = os.path.join(mod1_path, rel)
            f2_path = os.path.join(mod2_path, rel)

            effective_strategy = strategy
            if strategy == self.STRATEGY_AUTO:
                if conf["conflict_type"] == "mergeable":
                    effective_strategy = self.STRATEGY_MERGE
                else:
                    effective_strategy = self.STRATEGY_KEEP_FIRST

            if effective_strategy == self.STRATEGY_KEEP_FIRST:
                resolved.append({**conf, "action": "keep_first", "note": "保留 MOD1 版本"})

            elif effective_strategy == self.STRATEGY_KEEP_SECOND:
                # 用 MOD2 的文件覆盖 MOD1
                try:
                    dst = os.path.join(mod1_path, rel)
                    _ensure_dir(os.path.dirname(dst))
                    shutil.copy2(f2_path, dst)
                    resolved.append({**conf, "action": "keep_second", "note": "已用 MOD2 版本覆盖"})
                except Exception as e:
                    unresolved.append({**conf, "action": "keep_second", "error": str(e)})

            elif effective_strategy == self.STRATEGY_MERGE:
                if conf["conflict_type"] == "mergeable":
                    try:
                        merge_result = self._merge_ini_files(f1_path, f2_path)
                        if merge_result["success"]:
                            resolved.append({**conf, "action": "merge",
                                             "note": f"合并了 {merge_result['merged_sections']} 个 Section"})
                        else:
                            unresolved.append({**conf, "action": "merge",
                                               "error": merge_result.get("message", "合并失败")})
                    except Exception as e:
                        unresolved.append({**conf, "action": "merge", "error": str(e)})
                else:
                    unresolved.append({**conf, "action": "merge",
                                       "error": "非 INI 文件无法合并",
                                       "fallback": "keep_first"})

        result = {
            "success": True,
            "strategy": strategy,
            "resolved": resolved,
            "resolved_count": len(resolved),
            "unresolved": unresolved,
            "unresolved_count": len(unresolved),
            "total_conflicts": len(detection["conflicts"]),
            "all_resolved": len(unresolved) == 0,
        }
        self._last_result = result
        return result

    def _merge_ini_files(self, file1: str, file2: str) -> dict:
        """
        合并两个 INI 文件

        策略：将 file2 中 file1 没有的 Section 追加到 file1 末尾
        """
        if not os.path.isfile(file1) or not os.path.isfile(file2):
            return {"success": False, "message": "文件不存在"}

        try:
            sections1 = _load_ini_sections(file1)
            sections2 = _load_ini_sections(file2)
        except Exception as e:
            return {"success": False, "message": f"读取 INI 文件失败: {e}"}

        # 收集 file1 已有 section 名称
        existing_names = set()
        for s in sections1:
            existing_names.add(s["name"])

        # 找出 file2 中独有的 section
        new_sections = [s for s in sections2 if s["name"] not in existing_names]
        if not new_sections:
            return {"success": True, "merged_sections": 0, "new_sections": [],
                    "message": "没有新的 Section 需要合并"}

        # 追加到 file1 末尾（保留 file1 原有内容不变）
        # 读取 file2 原始内容，找到需要追加的 section 块
        try:
            with open(file2, "r", encoding="gbk", errors="replace") as f:
                lines2 = f.readlines()
        except (IOError, UnicodeDecodeError):
            try:
                with open(file2, "r", encoding="utf-8", errors="replace") as f:
                    lines2 = f.readlines()
            except (IOError, UnicodeDecodeError) as e:
                return {"success": False, "message": f"无法读取 file2: {e}"}

        # 提取需要追加的 section 块
        append_lines = []
        new_section_names = {s["name"] for s in new_sections}
        in_target = False
        for line in lines2:
            m = re.match(r"^\s*\[(.+)\]\s*$", line)
            if m:
                in_target = m.group(1) in new_section_names
            if in_target:
                append_lines.append(line)

        if append_lines:
            try:
                # 读取 file1 编码
                with open(file1, "r", encoding="gbk", errors="replace") as f:
                    pass
                encoding = "gbk"
            except (IOError, UnicodeDecodeError):
                encoding = "utf-8"

            try:
                with open(file1, "a", encoding=encoding) as f:
                    f.write("\n")
                    for line in append_lines:
                        f.write(line)
            except (IOError, OSError) as e:
                return {"success": False, "message": f"写入 file1 失败: {e}"}

        new_names = [s["name"] for s in new_sections]
        return {
            "success": True,
            "merged_sections": len(new_sections),
            "new_sections": new_names,
            "message": f"成功合并 {len(new_sections)} 个新 Section: {', '.join(new_names)}",
        }

    # ------------------------------------------------------------------
    # 9. generate_readme
    # ------------------------------------------------------------------

    def generate_readme(self, mod_path: str, output_path: str = None) -> dict:
        """
        自动生成 README.md

        包含 MOD 名称、版本、功能列表、安装说明、兼容性、文件清单、更新日志
        """
        if not os.path.isdir(mod_path):
            return {"success": False, "message": f"MOD 目录不存在: {mod_path}"}

        # 分析 MOD
        analysis = self.analyze_mod(mod_path)
        if not analysis["success"]:
            return {"success": False, "message": "分析 MOD 失败"}

        mod_info = analysis.get("mod_info") or {}
        mod_name = mod_info.get("name", os.path.basename(mod_path))
        mod_version = mod_info.get("version", "1.0.0")
        author = mod_info.get("author", "")
        description = mod_info.get("description", "")
        compatibility = mod_info.get("compatibility", "Sango7 v1.0")
        dependencies = mod_info.get("dependencies", [])
        created = mod_info.get("created", "")
        updated = mod_info.get("updated", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # 按类别整理文件清单
        cats = analysis.get("categories", {})
        file_list_md = ""
        for cat_name, cat_data in cats.items():
            if cat_data["count"] == 0:
                continue
            file_list_md += f"\n### {cat_name.upper()} ({cat_data['count']} 个文件, {cat_data['size_display']})\n\n"
            for fn in cat_data["files"]:
                file_list_md += f"- `{fn}`\n"

        # 功能描述
        features = []
        if cats.get("setting", {}).get("count", 0) > 0:
            features.append("配置文件修改")
        if cats.get("shape", {}).get("count", 0) > 0:
            features.append("图形资源修改")
        if cats.get("script", {}).get("count", 0) > 0:
            features.append("脚本修改")
        if cats.get("other", {}).get("count", 0) > 0:
            features.append("其他文件修改")

        features_md = ""
        if description:
            features_md += f"{description}\n\n"
        for i, feat in enumerate(features, 1):
            features_md += f"{i}. {feat}\n"

        # 依赖
        deps_md = ""
        if dependencies:
            for dep in dependencies:
                deps_md += f"- {dep}\n"
        else:
            deps_md = "无外部依赖\n"

        readme_content = f"""# {mod_name}

> 版本: {mod_version} | 作者: {author} | 兼容: {compatibility}

---

## 简介

{features_md}

## 安装说明

### 自动安装
1. 将 MOD 包解压到游戏目录
2. 运行 `install.bat` 或执行 `python install.py install`
3. 等待安装完成

### 手动安装
1. 将 `Setting/` 目录下的文件复制到游戏目录 `Setting/`
2. 将 `Shape/` 目录下的文件复制到游戏目录 `Shape/`
3. 将 `Script/` 目录下的文件复制到游戏目录 `Script/`
4. 如有 EXE 文件，复制到游戏根目录

### 卸载
1. 运行 `uninstall.bat` 或执行 `python install.py uninstall`
2. 或执行 `python install.py rollback` 回滚

## 兼容性

- {compatibility}
- 建议在安装前备份游戏原始文件

## 依赖

{deps_md}

## 文件清单

> 共 {analysis['total_files']} 个文件，总大小 {analysis['total_size_display']}
{file_list_md}

## 更新日志

- **{updated}** - v{mod_version}: 当前版本
- **{created}** - 初始版本

---

*由 San7ModMaker MOD 打包系统自动生成*
"""

        # 确定输出路径
        if output_path is None:
            output_path = os.path.join(mod_path, "README.md")
        output_path = os.path.abspath(output_path)

        try:
            with open(output_path, "w", encoding="utf-8") as fh:
                fh.write(readme_content)
        except (IOError, OSError) as e:
            return {"success": False, "message": f"写入 README.md 失败: {e}"}

        result = {
            "success": True,
            "readme_path": output_path,
            "mod_name": mod_name,
            "mod_version": mod_version,
            "file_count": analysis["total_files"],
        }
        self._last_result = result
        return result

    # ------------------------------------------------------------------
    # 10. version_bump
    # ------------------------------------------------------------------

    def version_bump(self, mod_path: str, level: str = "patch") -> dict:
        """
        版本号递增

        level: major / minor / patch
        从 mod_info.json 读取当前版本，递增后写回
        """
        if level not in (self.VERSION_MAJOR, self.VERSION_MINOR, self.VERSION_PATCH):
            return {"success": False, "message": f"未知版本级别: {level}，可选: major/minor/patch"}

        info_path = os.path.join(mod_path, "mod_info.json")
        if not os.path.isfile(info_path):
            return {
                "success": False,
                "message": "mod_info.json 不存在，无法递增版本",
                "hint": "请先使用 pack_full 生成 mod_info.json",
            }

        try:
            with open(info_path, "r", encoding="utf-8") as fh:
                mod_info = json.load(fh)
        except (json.JSONDecodeError, IOError) as e:
            return {"success": False, "message": f"读取 mod_info.json 失败: {e}"}

        old_version = mod_info.get("version", "1.0.0")
        parts = old_version.split(".")
        if len(parts) != 3:
            return {"success": False, "message": f"版本号格式不正确: {old_version}，应为 x.y.z"}

        try:
            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2])
        except ValueError:
            return {"success": False, "message": f"版本号格式不正确: {old_version}"}

        if level == self.VERSION_MAJOR:
            major += 1
            minor = 0
            patch = 0
        elif level == self.VERSION_MINOR:
            minor += 1
            patch = 0
        elif level == self.VERSION_PATCH:
            patch += 1

        new_version = f"{major}.{minor}.{patch}"
        mod_info["version"] = new_version
        mod_info["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            with open(info_path, "w", encoding="utf-8") as fh:
                json.dump(mod_info, fh, ensure_ascii=False, indent=2)
        except (IOError, OSError) as e:
            return {"success": False, "message": f"写入 mod_info.json 失败: {e}"}

        result = {
            "success": True,
            "old_version": old_version,
            "new_version": new_version,
            "level": level,
            "info_path": os.path.abspath(info_path),
        }
        self._last_result = result
        return result

    # ------------------------------------------------------------------
    # 11. validate_package
    # ------------------------------------------------------------------

    def validate_package(self, package_path: str) -> dict:
        """
        验证 MOD 包完整性

        检查必要文件、目录结构、mod_info.json 格式、文件完整性
        """
        if not os.path.isfile(package_path):
            return {"success": False, "message": f"包文件不存在: {package_path}"}

        errors = []
        warnings = []
        info = {}

        try:
            zf = zipfile.ZipFile(package_path, "r")
        except zipfile.BadZipFile as e:
            return {"success": False, "message": f"无效的 ZIP 文件: {e}"}

        try:
            namelist = zf.namelist()
            file_count = len(namelist)
            total_size_compressed = sum(zf.getinfo(n).compress_size for n in namelist)
            total_size_uncompressed = sum(zf.getinfo(n).file_size for n in namelist)

            info["file_count"] = file_count
            info["total_size_compressed"] = total_size_compressed
            info["total_size_compr_display"] = _format_size(total_size_compressed)
            info["total_size_uncompressed"] = total_size_uncompressed
            info["total_size_uncompr_display"] = _format_size(total_size_uncompressed)

            # 检查目录结构
            has_setting = any(n.startswith("Setting/") or n == "Setting/" for n in namelist)
            has_shape = any(n.startswith("Shape/") or n == "Shape/" for n in namelist)
            has_script = any(n.startswith("Script/") or n == "Script/" for n in namelist)
            has_mod_info = "mod_info.json" in namelist

            info["has_setting"] = has_setting
            info["has_shape"] = has_shape
            info["has_script"] = has_script
            info["has_mod_info"] = has_mod_info

            if not has_mod_info:
                warnings.append("缺少 mod_info.json 文件")
            if not has_setting and not has_shape and not has_script:
                warnings.append("包中未发现标准的 Setting/Shape/Script 目录结构")

            # 验证 mod_info.json 格式
            if has_mod_info:
                try:
                    mod_info = json.loads(zf.read("mod_info.json").decode("utf-8"))
                    info["mod_info"] = mod_info

                    required_fields = ["name", "version"]
                    for field in required_fields:
                        if field not in mod_info:
                            warnings.append(f"mod_info.json 缺少必要字段: {field}")

                    # 检查版本格式
                    version = mod_info.get("version", "")
                    if version and not re.match(r"^\d+\.\d+\.\d+$", version):
                        warnings.append(f"版本号格式不符合 semver: {version}")

                    # 检查文件清单一致性
                    expected_files = mod_info.get("files", [])
                    if expected_files:
                        missing_from_pkg = [f for f in expected_files if f not in namelist]
                        extra_in_pkg = [n for n in namelist
                                        if n not in expected_files
                                        and n != "mod_info.json"
                                        and not n.endswith("/")]
                        if missing_from_pkg:
                            warnings.append(f"mod_info.json 列出的文件在包中缺失: {len(missing_from_pkg)} 个")
                        if extra_in_pkg:
                            warnings.append(f"包中存在但 mod_info.json 未列出的文件: {len(extra_in_pkg)} 个")

                except json.JSONDecodeError as e:
                    errors.append(f"mod_info.json 解析失败: {e}")
                except Exception as e:
                    errors.append(f"mod_info.json 读取失败: {e}")

            # 检查文件完整性（测试解压）
            try:
                test_result = zf.testzip()
                if test_result:
                    errors.append(f"ZIP 文件损坏，第一个损坏的文件: {test_result}")
            except Exception as e:
                errors.append(f"ZIP 完整性测试失败: {e}")

            # 检查是否有空文件
            for n in namelist:
                if not n.endswith("/"):
                    try:
                        if zf.getinfo(n).file_size == 0:
                            warnings.append(f"空文件: {n}")
                    except Exception:
                        pass

            # 检查是否有危险文件
            danger_patterns = [r"\.exe$", r"\.dll$", r"\.bat$", r"\.cmd$", r"\.ps1$", r"\.vbs$"]
            dangerous_files = []
            for n in namelist:
                for pat in danger_patterns:
                    if re.search(pat, n, re.IGNORECASE):
                        dangerous_files.append(n)
                        break
            if dangerous_files:
                info["dangerous_files"] = dangerous_files
                warnings.append(f"包中含有可执行文件: {len(dangerous_files)} 个")

        finally:
            zf.close()

        is_valid = len(errors) == 0

        result = {
            "success": True,
            "is_valid": is_valid,
            "errors": errors,
            "error_count": len(errors),
            "warnings": warnings,
            "warning_count": len(warnings),
            "info": info,
            "package_path": os.path.abspath(package_path),
        }
        self._last_result = result
        return result

    # ------------------------------------------------------------------
    # 12. create_snapshot
    # ------------------------------------------------------------------

    def create_snapshot(self, mod_path: str) -> dict:
        """
        创建 MOD 快照，用于后续增量对比

        保存每个文件的路径、大小、修改时间、SHA256 哈希
        """
        if not os.path.isdir(mod_path):
            return {"success": False, "message": f"MOD 目录不存在: {mod_path}"}

        files = _walk_mod_files(mod_path)
        snapshot_files = []
        for f in files:
            try:
                fhash = _get_file_hash(f["path"])
            except Exception:
                fhash = ""
            snapshot_files.append({
                "relative": f["relative"],
                "path": f["path"],
                "size": f["size"],
                "mtime": f["mtime"],
                "sha256": fhash,
                "category": f["category"],
            })

        snapshot = {
            "mod_path": os.path.abspath(mod_path),
            "mod_name": os.path.basename(mod_path),
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": datetime.now().isoformat(),
            "file_count": len(snapshot_files),
            "total_size": sum(f["size"] for f in snapshot_files),
            "files": snapshot_files,
        }

        # 保存快照到 MOD 目录
        snapshot_filename = f".snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        snapshot_path = os.path.join(mod_path, snapshot_filename)
        try:
            with open(snapshot_path, "w", encoding="utf-8") as fh:
                json.dump(snapshot, fh, ensure_ascii=False, indent=2)
        except (IOError, OSError) as e:
            return {"success": False, "message": f"保存快照失败: {e}"}

        result = {
            "success": True,
            "snapshot_path": snapshot_path,
            "file_count": snapshot["file_count"],
            "total_size": snapshot["total_size"],
            "total_size_display": _format_size(snapshot["total_size"]),
            "created": snapshot["created"],
        }
        self._last_result = result
        return result

    # ------------------------------------------------------------------
    # 13. compare_snapshots
    # ------------------------------------------------------------------

    def compare_snapshots(self, snapshot1_path: str,
                          snapshot2_path: str) -> dict:
        """
        对比两个快照的差异
        """
        if not os.path.isfile(snapshot1_path):
            return {"success": False, "message": f"快照1不存在: {snapshot1_path}"}
        if not os.path.isfile(snapshot2_path):
            return {"success": False, "message": f"快照2不存在: {snapshot2_path}"}

        try:
            with open(snapshot1_path, "r", encoding="utf-8") as fh:
                snap1 = json.load(fh)
            with open(snapshot2_path, "r", encoding="utf-8") as fh:
                snap2 = json.load(fh)
        except (json.JSONDecodeError, IOError) as e:
            return {"success": False, "message": f"读取快照失败: {e}"}

        files1 = {f["relative"]: f for f in snap1.get("files", [])}
        files2 = {f["relative"]: f for f in snap2.get("files", [])}

        all_rels = set(files1.keys()) | set(files2.keys())

        added = []
        deleted = []
        modified = []
        unchanged = []

        for rel in sorted(all_rels):
            in_1 = rel in files1
            in_2 = rel in files2

            if in_1 and not in_2:
                deleted.append({"relative": rel, "snapshot1_info": files1[rel]})
            elif not in_1 and in_2:
                added.append({"relative": rel, "snapshot2_info": files2[rel]})
            elif in_1 and in_2:
                f1 = files1[rel]
                f2 = files2[rel]
                if f1.get("sha256") != f2.get("sha256") or f1.get("size") != f2.get("size"):
                    modified.append({
                        "relative": rel,
                        "snapshot1_info": f1,
                        "snapshot2_info": f2,
                        "size_diff": f2.get("size", 0) - f1.get("size", 0),
                    })
                else:
                    unchanged.append({"relative": rel, "snapshot1_info": f1, "snapshot2_info": f2})

        total_changes = len(added) + len(deleted) + len(modified)

        result = {
            "success": True,
            "snapshot1": os.path.basename(snapshot1_path),
            "snapshot1_time": snap1.get("created", ""),
            "snapshot2": os.path.basename(snapshot2_path),
            "snapshot2_time": snap2.get("created", ""),
            "added": added,
            "added_count": len(added),
            "deleted": deleted,
            "deleted_count": len(deleted),
            "modified": modified,
            "modified_count": len(modified),
            "unchanged": len(unchanged),
            "total_changes": total_changes,
            "has_changes": total_changes > 0,
            "summary": {
                "snapshot1_files": len(files1),
                "snapshot2_files": len(files2),
                "added": len(added),
                "deleted": len(deleted),
                "modified": len(modified),
                "unchanged": len(unchanged),
            },
        }
        self._last_result = result
        return result

    # ------------------------------------------------------------------
    # 14. get_info
    # ------------------------------------------------------------------

    @staticmethod
    def get_info() -> dict:
        """返回模块信息"""
        return {
            "module": "mod_packager",
            "version": "1.0.0",
            "description": "MOD 打包分发系统",
            "author": "San7ModMaker",
            "capabilities": [
                "analyze_mod",
                "resolve_dependencies",
                "pack_one_click",
                "pack_full",
                "pack_incremental",
                "generate_installer",
                "detect_conflicts",
                "resolve_conflicts",
                "generate_readme",
                "version_bump",
                "validate_package",
                "create_snapshot",
                "compare_snapshots",
            ],
            "dependencies": ["zipfile", "json", "hashlib", "shutil", "os", "logging"],
            "output_format": "dict (with 'success' field)",
        }