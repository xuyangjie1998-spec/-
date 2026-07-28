import os, json, re, shutil, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional
from core.error_codes import safe_error_message, error_response, success_response, ErrorCode

from core.config import WRITE_ROOT

logger = logging.getLogger('San7ModMaker')

__all__ = ['San7ModMakerMod']

class San7ModMakerMod:
    """MOD制作器 - MOD管理 (创建/打包/导入/安装/卸载/依赖)"""

    # ============================================================
    # API: MOD管理（增强版）
    # ============================================================

    def api_get_mod_list(self) -> dict:
        """获取MOD列表（含文件统计）"""
        mod_dir = os.path.join(WRITE_ROOT, "mods")
        if not os.path.exists(mod_dir):
            return {"success": True, "mods": []}

        mods = []
        for name in os.listdir(mod_dir):
            mod_path = os.path.join(mod_dir, name)
            if os.path.isdir(mod_path):
                info_path = os.path.join(mod_path, "mod_info.json")
                info = {}
                if os.path.exists(info_path):
                    with open(info_path, "r", encoding="utf-8") as f:
                        info = json.load(f)
                # 统计文件数
                file_count = 0
                data_dir = os.path.join(mod_path, "data")
                if os.path.exists(data_dir):
                    file_count = len([f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))])
                mods.append({
                    "name": name,
                    "path": mod_path,
                    "info": info,
                    "files": file_count,
                })
        return {"success": True, "mods": mods}

    def api_get_active_mod(self) -> dict:
        """获取当前活跃MOD"""
        active_path = os.path.join(WRITE_ROOT, "active_mod.txt")
        active = None
        if os.path.exists(active_path):
            with open(active_path, "r", encoding="utf-8") as f:
                active = f.read().strip()
        return {"success": True, "active": active}

    def api_set_active_mod(self, name: str) -> dict:
        """设置当前活跃MOD"""
        mod_dir = os.path.join(WRITE_ROOT, "mods", name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{name}' 不存在"}

        active_path = os.path.join(WRITE_ROOT, "active_mod.txt")
        with open(active_path, "w", encoding="utf-8") as f:
            f.write(name)

        # 更新MOD信息中的最后活跃时间
        info_path = os.path.join(mod_dir, "mod_info.json")
        if os.path.exists(info_path):
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            info["last_active"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)

        return {"success": True, "message": f"已切换到 MOD '{name}'"}

    def api_create_mod(self, name: str, description: str = "") -> dict:
        """创建新MOD工程"""
        if not name or not name.strip():
            return {"success": False, "message": "MOD名称不能为空"}
        # 安全名称：只保留字母、数字、中文、下划线
        safe_name = "".join(c for c in name if c.isalnum() or c in "_\u4e00-\u9fff")
        if not safe_name:
            return {"success": False, "message": "MOD名称无效"}

        mod_dir = os.path.join(WRITE_ROOT, "mods", safe_name)
        if os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{safe_name}' 已存在"}

        os.makedirs(mod_dir, exist_ok=True)
        os.makedirs(os.path.join(mod_dir, "data"), exist_ok=True)
        os.makedirs(os.path.join(mod_dir, "snapshots"), exist_ok=True)

        info = {
            "name": safe_name,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "description": description or "",
            "last_active": time.strftime("%Y-%m-%d %H:%M:%S"),
            "snapshot_count": 0,
        }
        with open(os.path.join(mod_dir, "mod_info.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        # 设置为活跃MOD
        self.api_set_active_mod(safe_name)

        return {"success": True, "message": f"MOD工程 '{safe_name}' 创建成功", "path": mod_dir}

    def api_delete_mod(self, name: str) -> dict:
        """删除MOD工程"""
        mod_dir = os.path.join(WRITE_ROOT, "mods", name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{name}' 不存在"}

        shutil.rmtree(mod_dir)

        # 如果删除的是活跃MOD，清除活跃状态
        active_path = os.path.join(WRITE_ROOT, "active_mod.txt")
        if os.path.exists(active_path):
            with open(active_path, "r", encoding="utf-8") as f:
                active = f.read().strip()
            if active == name:
                os.remove(active_path)

        return {"success": True, "message": f"MOD工程 '{name}' 已删除"}

    def api_mod_snapshot(self, name: str) -> dict:
        """创建当前游戏数据快照（用于增量对比）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        mod_dir = os.path.join(WRITE_ROOT, "mods", name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{name}' 不存在"}

        snap_dir = os.path.join(mod_dir, "snapshots")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        snap_name = f"snapshot_{timestamp}"
        snap_path = os.path.join(snap_dir, snap_name)
        os.makedirs(snap_path, exist_ok=True)

        # 复制所有INI文件作为快照
        setting_dir = os.path.join(self.game_path, "Setting")
        count = 0
        if os.path.exists(setting_dir):
            for f in os.listdir(setting_dir):
                if f.endswith(".ini"):
                    src = os.path.join(setting_dir, f)
                    dst = os.path.join(snap_path, f)
                    shutil.copy2(src, dst)
                    count += 1

        # 更新快照计数
        info_path = os.path.join(mod_dir, "mod_info.json")
        if os.path.exists(info_path):
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            info["snapshot_count"] = info.get("snapshot_count", 0) + 1
            info["last_snapshot"] = timestamp
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)

        return {"success": True, "message": f"快照创建成功，共 {count} 个文件", "count": count, "snapshot": snap_name}

    def api_pack_mod_incremental(self, mod_name: str) -> dict:
        """增量打包：只打包变更文件 + Shape资源 + 生成ZIP可分发包"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        mod_dir = os.path.join(WRITE_ROOT, "mods", mod_name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{mod_name}' 不存在"}

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if os.path.exists(export_dir):
            shutil.rmtree(export_dir)
        os.makedirs(export_dir, exist_ok=True)

        # 找到最新快照
        snap_dir = os.path.join(mod_dir, "snapshots")
        latest_snap = None
        if os.path.exists(snap_dir):
            snaps = sorted(os.listdir(snap_dir), reverse=True)
            if snaps:
                latest_snap = os.path.join(snap_dir, snaps[0])

        # 读取MOD元数据，自动递增版本号
        mod_info = {
            "name": mod_name,
            "packed": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0.0",
            "author": "",
            "description": "",
            "game_version": "Sango7",
            "files": [],
            "changed_files": [],
            "shape_files": [],
            "total_files": 0,
            "changed_count": 0,
            "dependencies": [],
            "install_instructions": "将 Setting/ 复制到游戏目录，Shape/ 合并到游戏目录 Shape/，Script/ 复制到游戏目录，如有 EXE 替换原文件",
        }
        info_path = os.path.join(mod_dir, "mod_info.json")
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                mod_info.update({k: v for k, v in existing.items() if k in mod_info})
                # 保留依赖信息
                if "dependencies" in existing:
                    mod_info["dependencies"] = existing["dependencies"]
                # 自动递增补丁版本号
                old_ver = existing.get("version", "1.0.0")
                try:
                    parts = [int(x) for x in old_ver.replace("v", "").split(".")]
                    if len(parts) >= 3:
                        parts[2] += 1
                        mod_info["version"] = ".".join(str(x) for x in parts)
                    elif len(parts) == 2:
                        parts[1] += 1
                        mod_info["version"] = ".".join(str(x) for x in parts) + ".0"
                    else:
                        mod_info["version"] = old_ver + ".1"
                except (ValueError, IndexError):
                    mod_info["version"] = old_ver + ".1"
            except Exception as e:
                logger.error(f"操作失败: {e}")
                logger.warning("读取已有mod_info.json失败，将使用新配置")
        all_files = []
        changed_files = []

        # 1. 打包 Setting/ 目录变更文件
        setting_dir = os.path.join(self.game_path, "Setting")
        subdirs = ["", "bfdata", "HSData", "OBD", "var"]

        if os.path.exists(setting_dir):
            for subdir in subdirs:
                scan_dir = os.path.join(setting_dir, subdir) if subdir else setting_dir
                if not os.path.exists(scan_dir):
                    continue
                for f in sorted(os.listdir(scan_dir)):
                    src = os.path.join(scan_dir, f)
                    if not os.path.isfile(src):
                        continue
                    rel_path = os.path.join(subdir, f) if subdir else f
                    all_files.append(rel_path)
                    changed = True
                    if latest_snap:
                        snap_file = os.path.join(latest_snap, rel_path)
                        if os.path.exists(snap_file):
                            with open(src, "rb") as fs:
                                changed = fs.read() != open(snap_file, "rb").read()
                    if changed:
                        changed_count += 1
                        changed_files.append(rel_path)
                        dest_dir = os.path.join(export_dir, "Setting", subdir) if subdir else os.path.join(export_dir, "Setting")
                        os.makedirs(dest_dir, exist_ok=True)
                        shutil.copy2(src, os.path.join(dest_dir, f))

        # 2. 打包 Shape/ 目录变更资源（头像、模型、半身像等）
        shape_dir = os.path.join(self.game_path, "Shape")
        shape_files = []
        shape_always = ["Face", "BFObj", "genhalf"]  # 核心资源目录
        if os.path.exists(shape_dir):
            # 扫描所有 Shape 子目录
            try:
                all_shape_subdirs = [d for d in os.listdir(shape_dir)
                                     if os.path.isdir(os.path.join(shape_dir, d))]
            except Exception as e:
                logger.warning(f"列出Shape子目录失败: {e}")
                all_shape_subdirs = []
            for sdir in all_shape_subdirs:
                scan = os.path.join(shape_dir, sdir)
                if not os.path.exists(scan):
                    continue
                for root, _, files in os.walk(scan):
                    for f in sorted(files):
                        src = os.path.join(root, f)
                        if not os.path.isfile(src):
                            continue
                        rel = os.path.relpath(src, shape_dir)
                        # 核心资源目录始终打包，其他目录按7天新鲜度
                        is_core = any(sdir.startswith(core) for core in shape_always)
                        try:
                            mtime = os.path.getmtime(src)
                            fresh = time.time() - mtime < 7 * 86400
                            if is_core or fresh or not latest_snap:
                                shape_files.append(rel)
                                dest = os.path.join(export_dir, "Shape", os.path.dirname(rel))
                                os.makedirs(dest, exist_ok=True)
                                shutil.copy2(src, os.path.join(dest, f))
                        except Exception as e:
                            logger.error(f"操作失败: {e}")
                            logger.warning(f"复制Shape文件失败: {src}")

        # 3. 打包 Script/ 目录
        script_dir = os.path.join(self.game_path, "Script")
        script_files = []
        if os.path.exists(script_dir):
            for root, _, files in os.walk(script_dir):
                for f in sorted(files):
                    src = os.path.join(root, f)
                    if not os.path.isfile(src):
                        continue
                    rel = os.path.relpath(src, script_dir)
                    changed = True
                    if latest_snap:
                        snap_file = os.path.join(latest_snap, "Script", rel)
                        if os.path.exists(snap_file):
                            with open(src, "rb") as fs:
                                changed = fs.read() != open(snap_file, "rb").read()
                    if changed:
                        script_files.append(rel)
                        dest = os.path.join(export_dir, "Script", os.path.dirname(rel))
                        os.makedirs(dest, exist_ok=True)
                        shutil.copy2(src, os.path.join(dest, f))

        # 4. 打包 EXE（如果已修改）
        exe_packed = False
        exe_name = "Sango7.exe"
        exe_src = os.path.join(self.game_path, exe_name)
        if os.path.exists(exe_src) and self.exe_patcher.exe_exists():
            changed = True
            if latest_snap:
                snap_exe = os.path.join(latest_snap, exe_name)
                if os.path.exists(snap_exe):
                    with open(exe_src, "rb") as fs:
                        changed = fs.read() != open(snap_exe, "rb").read()
            if changed:
                shutil.copy2(exe_src, os.path.join(export_dir, exe_name))
                exe_packed = True
        readme = f"""# {mod_name} v{mod_info['version']}

## 作者
{mod_info.get('author', '未知')}

## 描述
{mod_info.get('description', '无描述')}

## 安装方法
1. 将 Setting/ 文件夹复制到游戏目录
2. 将 Shape/ 文件夹（如有）合并到游戏目录的 Shape/ 文件夹
3. 将 Script/ 文件夹（如有）复制到游戏目录的 Script/ 文件夹
4. 如有 Sango7.exe，替换游戏目录中的原文件（已解除限制）
5. 启动游戏即可

## 卸载方法
使用 San7ModMaker 的"还原备份"功能，或手动替换回原始文件。

## 文件清单
### Setting 文件 ({len(changed_files)} 个变更)
{chr(10).join('- ' + f for f in changed_files[:50])}
{'' if len(changed_files) <= 50 else f'... 还有 {len(changed_files) - 50} 个文件'}

### Shape 资源 ({len(shape_files)} 个)
{chr(10).join('- ' + f for f in shape_files[:20])}
{'' if len(shape_files) <= 20 else f'... 还有 {len(shape_files) - 20} 个文件'}

### Script 脚本 ({len(script_files)} 个)
{chr(10).join('- ' + f for f in script_files[:20])}
{'' if len(script_files) <= 20 else f'... 还有 {len(script_files) - 20} 个文件'}

### EXE 补丁
{'已打包 Sango7.exe（含解除限制补丁）' if exe_packed else '未包含 EXE'}
"""
        with open(os.path.join(export_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme)

        # 4. 写入元数据
        mod_info["files"] = all_files
        mod_info["changed_files"] = changed_files
        mod_info["shape_files"] = shape_files
        mod_info["script_files"] = script_files
        mod_info["exe_packed"] = exe_packed
        mod_info["total_files"] = len(all_files) + len(shape_files) + len(script_files) + (1 if exe_packed else 0)
        mod_info["changed_count"] = changed_count

        with open(os.path.join(export_dir, "mod_info.json"), "w", encoding="utf-8") as f:
            json.dump(mod_info, f, ensure_ascii=False, indent=2)

        # 5. 生成 ZIP 可分发包
        zip_path = os.path.join(WRITE_ROOT, "exports", f"{mod_name}_v{mod_info['version']}.zip")
        try:
            import zipfile
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(export_dir):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        arcname = os.path.relpath(fpath, export_dir)
                        zf.write(fpath, arcname)
            zip_size = round(os.path.getsize(zip_path) / (1024 * 1024), 2)
        except Exception as e:
            zip_path = None
            zip_size = 0
            logger.error(f"ZIP打包失败: {e}")

        return {
            "success": True,
            "message": f"MOD发布完成：{changed_count}个文件变更 + {len(shape_files)}个资源 + {len(script_files)}个脚本{' + EXE' if exe_packed else ''}",
            "files": all_files,
            "changedFiles": changed_files,
            "shapeFiles": shape_files,
            "scriptFiles": script_files,
            "exePacked": exe_packed,
            "fileCount": len(all_files),
            "changedCount": changed_count,
            "exportPath": export_dir,
            "zipPath": zip_path,
            "zipSize": zip_size,
        }

    def api_pack_mod_one_click(self, mod_name: str) -> dict:
        """一键打包：自动创建快照 + 增量打包 + 生成ZIP"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        # 1. 先检查是否有活跃MOD
        if not mod_name:
            return {"success": False, "message": "请先创建或选择一个MOD工程"}
        # 2. 打包前校验
        validate_r = self.api_validate_all()
        if validate_r and validate_r.get("summary", {}).get("errors", 0) > 0:
            return {"success": False, "message": f"数据校验发现 {validate_r.get('summary', {}).get('errors', 0)} 个错误，请修复后再打包", "validation": validate_r}
        # 3. 自动创建快照
        snap_res = self.api_mod_snapshot(mod_name)
        if not snap_res.get("success"):
            return {"success": False, "message": f"快照创建失败: {snap_res.get('message', '')}"}
        # 3. 执行增量打包
        pack_res = self.api_pack_mod_incremental(mod_name)
        if pack_res.get("success"):
            pack_res["snapshot"] = snap_res.get("snapshot", "")
            pack_res["message"] = f"一键打包完成！共 {pack_res.get('changedCount', 0)} 个变更文件，{pack_res.get('zipSize', 0)}MB\nZIP: {pack_res.get('zipPath', '')}"
        return pack_res

    # V3.8.0: MOD打包增强
    def api_pack_mod_full(self, mod_name: str, include_shape: bool = True, include_script: bool = True, include_exe: bool = True, compress: bool = True) -> dict:
        """完整打包：全量打包MOD（非增量），包含所有指定资源"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        mod_dir = os.path.join(WRITE_ROOT, "mods", mod_name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{mod_name}' 不存在"}

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if os.path.exists(export_dir):
            shutil.rmtree(export_dir)
        os.makedirs(export_dir, exist_ok=True)

        stats = {"setting": 0, "shape": 0, "script": 0, "exe": 0}

        # 打包Setting
        setting_dir = os.path.join(self.game_path, "Setting")
        if os.path.exists(setting_dir):
            for root, _, files in os.walk(setting_dir):
                for fname in files:
                    src = os.path.join(root, fname)
                    rel = os.path.relpath(src, setting_dir)
                    dst = os.path.join(export_dir, "Setting", rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    stats["setting"] += 1

        # 打包Shape
        if include_shape:
            shape_dir = os.path.join(self.game_path, "Shape")
            if os.path.exists(shape_dir):
                for root, _, files in os.walk(shape_dir):
                    for fname in files:
                        src = os.path.join(root, fname)
                        rel = os.path.relpath(src, shape_dir)
                        dst = os.path.join(export_dir, "Shape", rel)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
                        stats["shape"] += 1

        # 打包Script
        if include_script:
            script_dir = os.path.join(self.game_path, "Script")
            if os.path.exists(script_dir):
                for root, _, files in os.walk(script_dir):
                    for fname in files:
                        src = os.path.join(root, fname)
                        rel = os.path.relpath(src, script_dir)
                        dst = os.path.join(export_dir, "Script", rel)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
                        stats["script"] += 1

        # 打包EXE
        if include_exe:
            exe_src = os.path.join(self.game_path, "Sango7.exe")
            if os.path.exists(exe_src):
                shutil.copy2(exe_src, os.path.join(export_dir, "Sango7.exe"))
                stats["exe"] = 1

        # 生成元数据
        mod_info = {
            "name": mod_name,
            "version": "1.0.0",
            "packed": time.strftime("%Y-%m-%d %H:%M:%S"),
            "type": "full",
            "stats": stats,
            "total_files": sum(stats.values()),
        }
        with open(os.path.join(export_dir, "mod_info.json"), "w", encoding="utf-8") as f:
            json.dump(mod_info, f, ensure_ascii=False, indent=2)

        with open(os.path.join(export_dir, "pack_meta.json"), "w", encoding="utf-8") as f:
            json.dump({"packed_at": time.strftime("%Y-%m-%d %H:%M:%S"), "type": "full", "source": "San7ModMaker V3.8.0"}, f, ensure_ascii=False, indent=2)

        # 压缩
        zip_path = ""
        zip_size = 0
        if compress:
            zip_path = os.path.join(WRITE_ROOT, "exports", f"{mod_name}_full.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(export_dir):
                    for fname in files:
                        if fname in ("mod_info.json", "pack_meta.json"):
                            continue
                        fp = os.path.join(root, fname)
                        zf.write(fp, os.path.relpath(fp, export_dir))
            zip_size = round(os.path.getsize(zip_path) / 1024 / 1024, 1)

        return {
            "success": True,
            "message": f"完整打包完成：{sum(stats.values())} 个文件",
            "stats": stats,
            "total_files": sum(stats.values()),
            "zip_path": zip_path,
            "zip_size_mb": zip_size,
            "export_dir": export_dir,
        }

    def api_pack_mod_distribution(self, mod_name: str, author: str = "", description: str = "", version: str = "1.0.0") -> dict:
        """生成MOD分发包：完整打包 + 安装说明 + 截图目录 + 版本信息"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        # 使用完整打包
        pack_result = self.api_pack_mod_full(mod_name, include_shape=True, include_script=True, include_exe=True, compress=True)
        if not pack_result.get("success"):
            return pack_result

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)

        # 更新元数据
        info_path = os.path.join(export_dir, "mod_info.json")
        if os.path.exists(info_path):
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            info["author"] = author
            info["description"] = description
            info["version"] = version
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)

        # 生成安装说明
        readme = f"""# {mod_name} v{version}
        
## 作者
{author or '未知'}

## 描述
{description or '无描述'}

## 安装方法
1. 将 Setting/ 文件夹复制到游戏目录
2. 将 Shape/ 文件夹（如有）合并到游戏目录的 Shape/ 文件夹
3. 将 Script/ 文件夹（如有）复制到游戏目录的 Script/ 文件夹
4. 如有 Sango7.exe，替换游戏目录中的原文件
5. 启动游戏即可

## 文件统计
- Setting: {pack_result['stats'].get('setting', 0)} 个文件
- Shape: {pack_result['stats'].get('shape', 0)} 个文件
- Script: {pack_result['stats'].get('script', 0)} 个文件
- EXE: {'是' if pack_result['stats'].get('exe', 0) > 0 else '否'}

## 打包信息
- 打包时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
- 工具: San7ModMaker V3.8.0
"""
        # 创建screenshots目录
        screenshots_dir = os.path.join(export_dir, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)

        with open(os.path.join(export_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme)

        return {
            "success": True,
            "message": f"MOD分发包生成完成: {mod_name} v{version}",
            "mod_name": mod_name,
            "version": version,
            "author": author,
            "export_dir": export_dir,
            "zip_path": pack_result.get("zip_path", ""),
            "zip_size_mb": pack_result.get("zip_size_mb", 0),
            "total_files": pack_result.get("total_files", 0),
            "screenshots_dir": screenshots_dir,
        }

    def api_pack_mod_preset(self, action: str = "list", name: str = "", config: dict = None) -> dict:
        """打包预设配置管理：save/load/list/delete预设"""
        preset_dir = os.path.join(WRITE_ROOT, "mods", ".pack_presets")
        os.makedirs(preset_dir, exist_ok=True)

        if action == "list":
            presets = []
            if os.path.exists(preset_dir):
                for fname in os.listdir(preset_dir):
                    if fname.endswith(".json"):
                        preset_path = os.path.join(preset_dir, fname)
                        try:
                            with open(preset_path, "r", encoding="utf-8") as f:
                                p = json.load(f)
                            presets.append({
                                "name": p.get("name", ""),
                                "include_shape": p.get("include_shape", True),
                                "include_script": p.get("include_script", True),
                                "include_exe": p.get("include_exe", True),
                                "compress": p.get("compress", True),
                                "created": p.get("created", ""),
                            })
                        except Exception as e:
                            logger.error(f"操作失败: {e}")
                            continue
            return {"success": True, "presets": presets}

        elif action == "save" and name and config:
            preset_path = os.path.join(preset_dir, f"{name}.json")
            config["name"] = name
            config["created"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(preset_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return {"success": True, "message": f"预设 '{name}' 已保存"}

        elif action == "load" and name:
            preset_path = os.path.join(preset_dir, f"{name}.json")
            if not os.path.exists(preset_path):
                return {"success": False, "message": f"预设 '{name}' 不存在"}
            with open(preset_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return {"success": True, "config": config}

        elif action == "delete" and name:
            preset_path = os.path.join(preset_dir, f"{name}.json")
            if os.path.exists(preset_path):
                os.remove(preset_path)
            return {"success": True, "message": f"预设 '{name}' 已删除"}

        return {"success": False, "message": "无效操作"}

    def api_import_mod(self, import_name: str = None, auto_remap: bool = True, backup_first: bool = True) -> dict:
        """导入MOD（从导出的MOD包导入）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        if not HAS_TK:
            return {"success": False, "message": "当前环境不支持文件对话框"}

        # 选择导出目录
        root = tk.Tk()
        root.withdraw()
        source_dir = filedialog.askdirectory(title="选择MOD导出目录（包含mod_pack_info.json的文件夹）")
        root.destroy()

        if not source_dir:
            return {"success": False, "message": "未选择目录"}

        info_file = os.path.join(source_dir, "mod_pack_info.json")
        if not os.path.exists(info_file):
            return {"success": False, "message": "所选目录不是有效的MOD包（缺少mod_pack_info.json）"}

        with open(info_file, "r", encoding="utf-8") as f:
            pack_info = json.load(f)

        final_name = import_name or pack_info.get("name", "imported_mod")

        # 备份当前数据
        if backup_first and self.backup_mgr:
            self.backup_mgr.backup_all_settings()

        # 检测冲突
        conflicts = []
        if auto_remap:
            setting_dir = os.path.join(self.game_path, "Setting")
            for ini_file in pack_info.get("changed_files", []):
                src_file = os.path.join(source_dir, ini_file)
                dst_file = os.path.join(setting_dir, ini_file)
                if os.path.exists(src_file) and os.path.exists(dst_file):
                    conflicts.extend(self._detect_ini_conflicts(src_file, dst_file, ini_file))

        # 如果无冲突或有冲突但已展示，直接复制文件
        if not conflicts:
            setting_dir = os.path.join(self.game_path, "Setting")
            for ini_file in pack_info.get("changed_files", []):
                src_file = os.path.join(source_dir, ini_file)
                dst_file = os.path.join(setting_dir, ini_file)
                if os.path.exists(src_file):
                    shutil.copy2(src_file, dst_file)

        # 创建MOD工程记录
        mod_dir = os.path.join(WRITE_ROOT, "mods", final_name)
        if not os.path.exists(mod_dir):
            os.makedirs(mod_dir, exist_ok=True)
            os.makedirs(os.path.join(mod_dir, "data"), exist_ok=True)
            os.makedirs(os.path.join(mod_dir, "snapshots"), exist_ok=True)
            info = {
                "name": final_name,
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "version": pack_info.get("version", "1.0"),
                "description": pack_info.get("description", "导入的MOD"),
                "imported_from": source_dir,
                "snapshot_count": 0,
            }
            with open(os.path.join(mod_dir, "mod_info.json"), "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": f"MOD '{final_name}' 导入成功",
            "conflicts": conflicts,
            "conflictCount": len(conflicts),
            "importName": final_name,
        }

    def _detect_ini_conflicts(self, src_file: str, dst_file: str, filename: str) -> List[dict]:
        """检测两个INI文件之间的ID冲突"""
        conflicts = []
        try:
            parser_src = IniParser()
            parser_src.load(src_file)
            parser_dst = IniParser()
            parser_dst.load(dst_file)

            # 获取所有section名
            src_nos = {}
            dst_nos = {}
            for s in parser_src.sections:
                no = s.entries.get("No", "")
                if no:
                    src_nos[no] = s.entries.get("Name", "")
            for s in parser_dst.sections:
                no = s.entries.get("No", "")
                if no:
                    dst_nos[no] = s.entries.get("Name", "")

            # 找冲突的ID
            for no in src_nos:
                if no in dst_nos:
                    # 找到一个新的未使用ID
                    all_nos = set(int(n) for n in dst_nos.keys() if n.isdigit())
                    suggested = 10000
                    while suggested in all_nos:
                        suggested += 1
                    conflicts.append({
                        "file": filename,
                        "existingId": no,
                        "importId": no,
                        "existingName": dst_nos[no],
                        "importName": src_nos[no],
                        "suggestedId": suggested,
                    })
        except Exception as e:
            logger.warning(f"冲突重映射失败: {e}")
        return conflicts

    def api_remap_conflicts(self, conflict_data: dict) -> dict:
        """重映射冲突ID"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        setting_dir = os.path.join(self.game_path, "Setting")
        remapped = 0

        for conflict in conflict_data.get("conflicts", []):
            filename = conflict.get("file", "")
            old_id = str(conflict.get("importId", ""))
            new_id = str(conflict.get("suggestedId", ""))
            if not filename or not old_id or not new_id:
                continue

            file_path = os.path.join(setting_dir, filename)
            if not os.path.exists(file_path):
                continue

            # 备份
            if self.backup_mgr:
                self.backup_mgr.backup_file(file_path)

            # 读取并重映射
            try:
                with open(file_path, "r", encoding="big5", errors="replace") as f:
                    content = f.read()

                # 替换 No=old_id 为 No=new_id（对 old_id 做正则转义）
                import re
                escaped_id = re.escape(str(old_id))
                content = re.sub(rf'(\bNo\s*=\s*){escaped_id}\b', rf'\g<1>{new_id}', content)

                with open(file_path, "w", encoding="big5", errors="replace") as f:
                    f.write(content)
                remapped += 1
            except Exception as e:
                logger.warning(f"重映射写入失败 {file_path}: {e}")
                continue

        return {"success": True, "message": f"已重映射 {remapped} 个冲突", "remapped": remapped}

    # ============================================================
    # API: MOD 安装/卸载
    # ============================================================

    def api_preview_mod_install(self, mod_name: str) -> dict:
        """预览MOD安装：列出MOD将修改/新增的所有文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if not os.path.exists(export_dir):
            return {"success": False, "message": f"MOD包 '{mod_name}' 不存在，请先打包"}

        # 读取MOD元数据
        info_path = os.path.join(export_dir, "mod_info.json")
        mod_info = {}
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    mod_info = json.load(f)
            except Exception as e:
                logger.error(f"操作失败: {e}")
                pass

        will_overwrite = []
        will_create = []
        setting_src = os.path.join(export_dir, "Setting")
        setting_dst = os.path.join(self.game_path, "Setting")
        if os.path.exists(setting_src):
            for root, _, files in os.walk(setting_src):
                for fname in files:
                    rel = os.path.join("Setting", os.path.relpath(os.path.join(root, fname), setting_src))
                    dst = os.path.join(self.game_path, rel)
                    entry = {"file": rel, "size_kb": round(os.path.getsize(os.path.join(root, fname)) / 1024, 1)}
                    if os.path.exists(dst):
                        entry["action"] = "覆盖"
                        will_overwrite.append(entry)
                    else:
                        entry["action"] = "新增"
                        will_create.append(entry)

        shape_src = os.path.join(export_dir, "Shape")
        shape_dst = os.path.join(self.game_path, "Shape")
        if os.path.exists(shape_src):
            for root, _, files in os.walk(shape_src):
                for fname in files:
                    rel = os.path.join("Shape", os.path.relpath(os.path.join(root, fname), shape_src))
                    dst = os.path.join(self.game_path, rel)
                    entry = {"file": rel, "size_kb": round(os.path.getsize(os.path.join(root, fname)) / 1024, 1)}
                    if os.path.exists(dst):
                        entry["action"] = "覆盖"
                        will_overwrite.append(entry)
                    else:
                        entry["action"] = "新增"
                        will_create.append(entry)

        total = len(will_overwrite) + len(will_create)
        return {
            "success": True,
            "mod_name": mod_name,
            "mod_info": mod_info,
            "will_overwrite": will_overwrite,
            "will_create": will_create,
            "total_files": total,
            "overwrite_count": len(will_overwrite),
            "create_count": len(will_create),
            "message": f"将{('覆盖'+str(len(will_overwrite))+'个' if will_overwrite else '')} {'新增' if will_create else ''}{len(will_create)}个文件" if total > 0 else "该MOD不包含任何文件",
        }

    def api_check_mod_compatibility(self, mod_name: str) -> dict:
        """检查MOD与当前游戏版本的兼容性"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if not os.path.exists(export_dir):
            return {"success": False, "message": f"MOD包 '{mod_name}' 不存在，请先打包"}

        # 读取MOD元数据
        info_path = os.path.join(export_dir, "mod_info.json")
        mod_info = {}
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    mod_info = json.load(f)
            except Exception as e:
                logger.error(f"操作失败: {e}")
                pass

        # 检测游戏版本
        game_info = self.api_get_game_info()
        version_info = self.version_detector.detect() if self.version_detector else {}

        # 检查兼容性
        warnings = []
        issues = []

        # 1. 检查 EXE 是否存在
        if not game_info.get("has_exe"):
            issues.append("未检测到 Sango7.exe，游戏可能未正确安装")

        # 2. 检查 MOD 声明的最低版本要求
        required_version = mod_info.get("min_game_version", "")
        if required_version and version_info:
            game_version = version_info.get("version", "")
            if game_version and game_version < required_version:
                issues.append(f"MOD要求游戏版本 ≥ {required_version}，当前版本: {game_version}")

        # 3. 检查 MOD 打包时间 vs 游戏文件时间
        mod_pack_time = mod_info.get("packed_at", "")
        if mod_pack_time and version_info.get("file_timestamp"):
            if version_info["file_timestamp"] > mod_pack_time:
                warnings.append("游戏文件比MOD打包时间更新，安装后可能覆盖游戏更新")

        # 4. 检查 MOD 声明的依赖
        mod_dependencies = mod_info.get("dependencies", [])
        if mod_dependencies:
            installed_log = os.path.join(WRITE_ROOT, "mods", ".installed_mods.json")
            installed = {}
            if os.path.exists(installed_log):
                try:
                    with open(installed_log, "r", encoding="utf-8") as f:
                        installed = json.load(f)
                except Exception as e:
                    logger.error(f"操作失败: {e}")
                    pass
            missing_deps = []
            for dep in mod_dependencies:
                dep_name = dep if isinstance(dep, str) else dep.get("name", "")
                if dep_name and dep_name not in installed:
                    missing_deps.append(dep_name)
            if missing_deps:
                issues.append(f"缺少依赖MOD: {', '.join(missing_deps)}")

        return {
            "success": True,
            "compatible": len(issues) == 0,
            "mod_name": mod_name,
            "mod_info": mod_info,
            "game_version": version_info.get("version", "unknown"),
            "game_version_name": version_info.get("version_name", "未知版本"),
            "warnings": warnings,
            "issues": issues,
            "message": "兼容性检查通过" if len(issues) == 0 else f"发现 {len(issues)} 个兼容性问题",
        }

    # ==================== MOD 依赖管理 ====================

    def api_set_mod_dependencies(self, mod_name: str, dependencies: List[dict] = None) -> dict:
        """设置MOD的依赖声明"""
        mod_dir = os.path.join(WRITE_ROOT, "mods", mod_name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{mod_name}' 不存在"}

        info_path = os.path.join(mod_dir, "mod_info.json")
        info = {}
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
            except Exception as e:
                logger.error(f"操作失败: {e}")
                pass

        # 规范化依赖格式
        normalized = []
        if dependencies:
            for dep in dependencies:
                if isinstance(dep, str):
                    normalized.append({"name": dep, "version": "*"})
                elif isinstance(dep, dict):
                    normalized.append({
                        "name": dep.get("name", ""),
                        "version": dep.get("version", "*"),
                        "required": dep.get("required", True),
                    })

        info["dependencies"] = normalized
        info["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(info_path), exist_ok=True)
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "dependencies": normalized,
            "message": f"已设置 {len(normalized)} 个依赖",
        }

    def api_get_mod_dependencies(self, mod_name: str) -> dict:
        """获取MOD的依赖列表及其满足状态"""
        mod_dir = os.path.join(WRITE_ROOT, "mods", mod_name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{mod_name}' 不存在"}

        info_path = os.path.join(mod_dir, "mod_info.json")
        info = {}
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
            except Exception as e:
                logger.error(f"操作失败: {e}")
                pass

        dependencies = info.get("dependencies", [])

        # 获取所有可用MOD列表
        mods_list = []
        mods_path = os.path.join(WRITE_ROOT, "mods")
        if os.path.exists(mods_path):
            for name in os.listdir(mods_path):
                mp = os.path.join(mods_path, name)
                if os.path.isdir(mp):
                    mi_path = os.path.join(mp, "mod_info.json")
                    mi = {}
                    if os.path.exists(mi_path):
                        try:
                            with open(mi_path, "r", encoding="utf-8") as f:
                                mi = json.load(f)
                        except Exception as e:
                            logger.error(f"操作失败: {e}")
                            pass
                    mods_list.append({
                        "name": name,
                        "version": mi.get("version", "1.0"),
                        "description": mi.get("description", ""),
                    })

        # 检查每个依赖是否满足
        satisfied_count = 0
        for dep in dependencies:
            dep_name = dep.get("name", dep) if isinstance(dep, dict) else dep
            dep_version = dep.get("version", "*") if isinstance(dep, dict) else "*"
            dep["satisfied"] = False
            dep["available_version"] = None
            for m in mods_list:
                if m["name"] == dep_name:
                    dep["available_version"] = m["version"]
                    if dep_version == "*" or dep_version == m["version"]:
                        dep["satisfied"] = True
                        satisfied_count += 1
                    break

        return {
            "success": True,
            "mod_name": mod_name,
            "dependencies": dependencies,
            "total": len(dependencies),
            "satisfied": satisfied_count,
            "all_satisfied": satisfied_count == len(dependencies) if dependencies else True,
            "available_mods": [m["name"] for m in mods_list],
            "message": f"依赖满足: {satisfied_count}/{len(dependencies)}" if dependencies else "该MOD无依赖声明",
        }

    def api_check_mod_dependencies(self, mod_name: str) -> dict:
        """检查MOD的所有依赖是否满足，返回详细的依赖报告"""
        result = self.api_get_mod_dependencies(mod_name)
        if not result.get("success"):
            return result

        dependencies = result.get("dependencies", [])
        missing = []
        warnings = []
        for dep in dependencies:
            if not dep.get("satisfied"):
                dep_name = dep.get("name", "?")
                if dep.get("available_version"):
                    warnings.append(f"依赖 '{dep_name}' 版本不匹配: 需要 {dep.get('version', '*')}, 可用 {dep['available_version']}")
                else:
                    missing.append(f"依赖 '{dep_name}' 不可用")

        result["missing"] = missing
        result["warnings"] = warnings
        result["ok"] = len(missing) == 0 and len(warnings) == 0
        result["message"] = "所有依赖已满足" if result["ok"] else (
            f"缺 {len(missing)} 个依赖" + (f", {len(warnings)} 个版本不匹配" if warnings else "")
        )
        return result

    def api_mod_conflict_detect(self, mod_a: str, mod_b: str) -> dict:
        """检测两个MOD之间的文件冲突"""
        mods_dir = os.path.join(WRITE_ROOT, "mods")
        mod_a_path = os.path.join(mods_dir, mod_a)
        mod_b_path = os.path.join(mods_dir, mod_b)
        if not os.path.exists(mod_a_path):
            return {"success": False, "message": f"MOD A 不存在: {mod_a}"}
        if not os.path.exists(mod_b_path):
            return {"success": False, "message": f"MOD B 不存在: {mod_b}"}

        # 获取两个MOD的文件列表
        def _get_files(mod_path):
            files = set()
            for sub in ["data", "exports"]:
                sub_path = os.path.join(mod_path, sub)
                if os.path.exists(sub_path):
                    for root, _, fnames in os.walk(sub_path):
                        for fn in fnames:
                            files.add(os.path.relpath(os.path.join(root, fn), mod_path))
            return files

        files_a = _get_files(mod_a_path)
        files_b = _get_files(mod_b_path)

        conflicts = sorted(files_a & files_b)
        summary = {
            "mod_a": mod_a,
            "mod_b": mod_b,
            "files_a_count": len(files_a),
            "files_b_count": len(files_b),
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
            "has_conflicts": len(conflicts) > 0,
        }

        return {
            "success": True,
            **summary,
            "message": f"检测到 {len(conflicts)} 个文件冲突" if conflicts else "无冲突",
        }

    def api_install_mod(self, mod_name: str) -> dict:
        """安装MOD：将 exports/ 中的MOD文件复制到游戏目录，并记录安装状态"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if not os.path.exists(export_dir):
            return {"success": False, "message": f"MOD包 '{mod_name}' 不存在，请先打包"}

        # 读取MOD元数据
        info_path = os.path.join(export_dir, "mod_info.json")
        mod_info = {}
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    mod_info = json.load(f)
            except Exception as e:
                logger.error(f"操作失败: {e}")
                logger.warning("读取mod_info.json失败，将使用默认配置")

        # 依赖检查：安装前检查依赖是否满足
        dep_check = self.api_check_mod_dependencies(mod_name)
        if dep_check.get("success") and not dep_check.get("ok"):
            missing = dep_check.get("missing", [])
            warnings = dep_check.get("warnings", [])
            dep_issues = []
            if missing:
                dep_issues.extend(missing)
            if warnings:
                dep_issues.extend(warnings)
            # 不阻止安装，但返回警告
            logger.warning(f"MOD '{mod_name}' 依赖检查发现问题: {'; '.join(dep_issues)}")

        installed_files = []
        install_backups = {}  # 记录每个文件对应的备份路径，用于精确还原
        setting_src = os.path.join(export_dir, "Setting")
        if os.path.exists(setting_src):
            setting_dst = os.path.join(self.game_path, "Setting")
            for root, _, files in os.walk(setting_src):
                for fname in files:
                    src = os.path.join(root, fname)
                    rel = os.path.relpath(src, setting_src)
                    dst = os.path.join(setting_dst, rel)
                    # 备份原始文件并记录备份路径
                    if os.path.exists(dst) and self.backup_mgr:
                        backup_path = self.backup_mgr.backup_file(dst)
                        install_backups[os.path.join("Setting", rel)] = backup_path
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    installed_files.append(os.path.join("Setting", rel))

        shape_src = os.path.join(export_dir, "Shape")
        if os.path.exists(shape_src):
            shape_dst = os.path.join(self.game_path, "Shape")
            for root, _, files in os.walk(shape_src):
                for fname in files:
                    src = os.path.join(root, fname)
                    rel = os.path.relpath(src, shape_src)
                    dst = os.path.join(shape_dst, rel)
                    if os.path.exists(dst) and self.backup_mgr:
                        backup_path = self.backup_mgr.backup_file(dst)
                        install_backups[os.path.join("Shape", rel)] = backup_path
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    installed_files.append(os.path.join("Shape", rel))

        # 记录安装状态（含备份路径用于精确还原）
        install_log = os.path.join(WRITE_ROOT, "mods", ".installed_mods.json")
        installed_mods = {}
        if os.path.exists(install_log):
            try:
                with open(install_log, "r", encoding="utf-8") as f:
                    installed_mods = json.load(f)
            except Exception as e:
                logger.error(f"操作失败: {e}")
                logger.warning("读取install_log.json失败，将创建新记录")
        installed_mods[mod_name] = {
            "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": mod_info.get("version", "1.0"),
            "files": installed_files,
            "file_count": len(installed_files),
            "backups": install_backups,  # 精确备份路径，用于卸载时还原
        }
        with open(install_log, "w", encoding="utf-8") as f:
            json.dump(installed_mods, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": f"MOD '{mod_name}' 安装成功，{len(installed_files)} 个文件已部署",
            "installedFiles": len(installed_files),
        }

    def api_uninstall_mod(self, mod_name: str) -> dict:
        """卸载MOD：通过备份还原MOD安装时被替换的文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        install_log = os.path.join(WRITE_ROOT, "mods", ".installed_mods.json")
        if not os.path.exists(install_log):
            return {"success": False, "message": "没有已安装的MOD记录"}

        try:
            with open(install_log, "r", encoding="utf-8") as f:
                installed_mods = json.load(f)
        except Exception as e:
            logger.error(f"操作失败: {e}")
            return {"success": False, "message": "安装记录文件损坏"}

        if mod_name not in installed_mods:
            return {"success": False, "message": f"MOD '{mod_name}' 未安装"}

        mod_record = installed_mods[mod_name]
        restored = 0
        failed = 0
        install_backups = mod_record.get("backups", {})

        for f in mod_record.get("files", []):
            file_path = os.path.join(self.game_path, f)
            # 优先使用安装时记录的精确备份路径
            backup_path = install_backups.get(f, "")
            if backup_path and os.path.exists(backup_path):
                try:
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    shutil.copy2(backup_path, file_path)
                    restored += 1
                    continue
                except Exception as e:
                    logger.warning(f"MOD卸载恢复失败: {e}")
            # 回退：使用最新备份
            if self.backup_mgr:
                backup_record = self.backup_mgr.get_latest_backup(file_path)
                if backup_record:
                    backup_file = backup_record.get("backup_path", "")
                    if backup_file and os.path.exists(backup_file):
                        try:
                            os.makedirs(os.path.dirname(file_path), exist_ok=True)
                            shutil.copy2(backup_file, file_path)
                            restored += 1
                        except Exception as e:
                            logger.warning(f"还原文件失败: {file_path}: {e}")
                            failed += 1

        # 删除安装记录
        del installed_mods[mod_name]
        with open(install_log, "w", encoding="utf-8") as f:
            json.dump(installed_mods, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": f"MOD '{mod_name}' 已卸载，还原 {restored} 个文件" + (f"，{failed} 个失败" if failed else ""),
            "restored": restored,
            "failed": failed,
        }

    def api_list_installed_mods(self) -> dict:
        """列出已安装的MOD"""
        install_log = os.path.join(WRITE_ROOT, "mods", ".installed_mods.json")
        if not os.path.exists(install_log):
            return {"success": True, "mods": {}}
        try:
            with open(install_log, "r", encoding="utf-8") as f:
                mods = json.load(f)
            return {"success": True, "mods": mods}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # V3.7.0: MOD 安装回滚 / 重新安装 / 打包校验
    # ============================================================

    def api_mod_rollback(self, mod_name: str) -> dict:
        """回滚MOD安装：使用安装记录中的备份精确还原文件，但保留安装记录"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        install_log = os.path.join(WRITE_ROOT, "mods", ".installed_mods.json")
        if not os.path.exists(install_log):
            return {"success": False, "message": "没有已安装的MOD记录"}

        try:
            with open(install_log, "r", encoding="utf-8") as f:
                installed_mods = json.load(f)
        except Exception as e:
            logger.error(f"操作失败: {e}")
            return {"success": False, "message": "安装记录文件损坏"}

        if mod_name not in installed_mods:
            return {"success": False, "message": f"MOD '{mod_name}' 未安装"}

        mod_record = installed_mods[mod_name]
        restored = 0
        failed = 0
        skipped = 0
        install_backups = mod_record.get("backups", {})

        for f in mod_record.get("files", []):
            file_path = os.path.join(self.game_path, f)
            backup_path = install_backups.get(f, "")
            if backup_path and os.path.exists(backup_path):
                try:
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    shutil.copy2(backup_path, file_path)
                    restored += 1
                except Exception as e:
                    logger.warning(f"回滚失败: {f}: {e}")
                    failed += 1
            elif self.backup_mgr:
                backup_record = self.backup_mgr.get_latest_backup(file_path)
                if backup_record:
                    backup_file = backup_record.get("backup_path", "")
                    if backup_file and os.path.exists(backup_file):
                        try:
                            os.makedirs(os.path.dirname(file_path), exist_ok=True)
                            shutil.copy2(backup_file, file_path)
                            restored += 1
                        except Exception as e:
                            logger.warning(f"回滚失败: {f}: {e}")
                            failed += 1
                    else:
                        skipped += 1
                else:
                    skipped += 1
            else:
                skipped += 1

        # 更新安装记录中的回滚计数
        installed_mods[mod_name]["rollback_count"] = installed_mods[mod_name].get("rollback_count", 0) + 1
        installed_mods[mod_name]["last_rollback"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(install_log, "w", encoding="utf-8") as f:
            json.dump(installed_mods, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": f"MOD '{mod_name}' 回滚完成，成功还原 {restored} 个文件" + (f"，{failed} 个失败" if failed else "") + (f"，{skipped} 个跳过" if skipped else ""),
            "restored": restored,
            "failed": failed,
            "skipped": skipped,
        }

    def api_mod_reinstall(self, mod_name: str) -> dict:
        """重新安装MOD：先回滚再重新安装，适用于MOD包更新后重装"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        # 先回滚
        rollback_result = self.api_mod_rollback(mod_name)
        if not rollback_result.get("success"):
            return {"success": False, "message": f"回滚失败，无法重新安装: {rollback_result.get('message')}"}

        # 重新安装
        install_result = self.api_install_mod(mod_name)
        if not install_result.get("success"):
            return {"success": False, "message": f"安装失败: {install_result.get('message')}"}

        return {
            "success": True,
            "message": f"MOD '{mod_name}' 重新安装完成，{install_result.get('installedFiles', 0)} 个文件已部署",
            "rollback": {"restored": rollback_result.get("restored", 0)},
            "install": {"installedFiles": install_result.get("installedFiles", 0)},
        }

    def api_mod_validate_pack(self, mod_name: str) -> dict:
        """验证MOD打包完整性：检查目录结构、必要文件、文件大小、引用完整性"""
        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if not os.path.exists(export_dir):
            return {"success": False, "message": f"MOD包 '{mod_name}' 不存在，请先打包"}

        issues = []
        warnings = []
        info = {}

        # 1. 检查必要文件
        required_files = ["mod_info.json", "pack_meta.json"]
        missing = []
        for f in required_files:
            if not os.path.exists(os.path.join(export_dir, f)):
                missing.append(f)
        if missing:
            issues.append(f"缺少必要文件: {', '.join(missing)}")

        # 2. 检查目录结构
        has_setting = os.path.exists(os.path.join(export_dir, "Setting"))
        has_shape = os.path.exists(os.path.join(export_dir, "Shape"))
        if not has_setting and not has_shape:
            issues.append("缺少Setting或Shape目录，MOD包为空")

        # 3. 统计文件
        file_count = 0
        total_size = 0
        large_files = []
        setting_count = 0
        shape_count = 0

        if has_setting:
            for root, _, files in os.walk(os.path.join(export_dir, "Setting")):
                for fname in files:
                    fp = os.path.join(root, fname)
                    sz = os.path.getsize(fp)
                    file_count += 1
                    total_size += sz
                    setting_count += 1
                    if sz > 50 * 1024 * 1024:  # 50MB
                        large_files.append({"file": os.path.relpath(fp, export_dir), "size_mb": round(sz / 1024 / 1024, 1)})

        if has_shape:
            for root, _, files in os.walk(os.path.join(export_dir, "Shape")):
                for fname in files:
                    fp = os.path.join(root, fname)
                    sz = os.path.getsize(fp)
                    file_count += 1
                    total_size += sz
                    shape_count += 1
                    if sz > 50 * 1024 * 1024:
                        large_files.append({"file": os.path.relpath(fp, export_dir), "size_mb": round(sz / 1024 / 1024, 1)})

        if large_files:
            warnings.append(f"{len(large_files)} 个大文件（>50MB），可能影响分发")

        info = {
            "file_count": file_count,
            "total_size_mb": round(total_size / 1024 / 1024, 1),
            "setting_files": setting_count,
            "shape_files": shape_count,
        }

        # 4. 检查mod_info.json内容
        info_path = os.path.join(export_dir, "mod_info.json")
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    mod_info = json.load(f)
                info["mod_name"] = mod_info.get("name", "")
                info["version"] = mod_info.get("version", "")
                info["author"] = mod_info.get("author", "")
                if not mod_info.get("name"):
                    warnings.append("mod_info.json中缺少name字段")
                if not mod_info.get("version"):
                    warnings.append("mod_info.json中缺少version字段")
            except Exception as e:
                logger.error(f"操作失败: {e}")
                issues.append("mod_info.json格式无效")

        # 5. 检查pack_meta.json内容
        meta_path = os.path.join(export_dir, "pack_meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                info["packed_at"] = meta.get("packed_at", "")
                info["source"] = meta.get("source", "")
            except Exception as e:
                logger.error(f"操作失败: {e}")
                warnings.append("pack_meta.json格式无效")

        valid = len(issues) == 0
        return {
            "success": True,
            "valid": valid,
            "message": "MOD包验证通过" if valid else f"发现 {len(issues)} 个问题，{len(warnings)} 个警告",
            "issues": issues,
            "warnings": warnings,
            "info": info,
            "large_files": large_files,
        }

    def api_launch_game(self, mod_name: str = None) -> dict:
        """启动游戏（可指定MOD名称）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        exe_path = os.path.join(self.game_path, "SG7.exe")
        if not os.path.exists(exe_path):
            # 尝试其他常见名称
            for alt in ["Sango7.exe", "Sango6.exe", "SG6.exe"]:
                alt_path = os.path.join(self.game_path, alt)
                if os.path.exists(alt_path):
                    exe_path = alt_path
                    break
            else:
                return {"success": False, "message": f"未找到游戏主程序，请确保游戏目录下有 SG7.exe"}
        try:
            cwd = self.game_path
            if mod_name:
                # 如果指定了MOD，先确保MOD已安装
                install_log = os.path.join(WRITE_ROOT, "mods", ".installed_mods.json")
                if os.path.exists(install_log):
                    with open(install_log, "r", encoding="utf-8") as f:
                        installed = json.load(f)
                    if mod_name not in installed:
                        return {"success": False, "message": f"MOD '{mod_name}' 未安装，请先安装"}
            # 使用 subprocess 启动游戏（非阻塞）
            import subprocess
            if os.name == 'nt':
                subprocess.Popen([exe_path], cwd=cwd, shell=False)
            else:
                subprocess.Popen([exe_path], cwd=cwd)
            return {"success": True, "message": "游戏已启动" + (f" (MOD: {mod_name})" if mod_name else "")}
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return {"success": False, "message": f"启动失败: {str(e)}"}


    # ============================================================
