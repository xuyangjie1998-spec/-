import os, json, re, shutil, base64, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional
from core.error_codes import ErrorCode, safe_error_message, error_response, success_response

from core.config import WRITE_ROOT, PROJECT_ROOT

from core.event_templates import EVENT_TEMPLATES, generate_event_section

logger = logging.getLogger('San7ModMaker')

__all__ = ['San7ModMakerAdvanced']

__all__ = ['San7ModMakerSandbox']

class San7ModMakerSandbox:
    """MOD制作器 - 沙盒测试/操作历史/分辨率"""

    # ============================================================
    # API: 沙盒测试模式
    # ============================================================
    def api_create_sandbox(self) -> dict:
        """创建沙盒环境：复制游戏文件到临时目录用于测试"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        sandbox_dir = os.path.join(WRITE_ROOT, "sandbox")
        # 如果已有沙盒，询问
        if os.path.exists(sandbox_dir):
            return error_response(ErrorCode.INVALID_PARAM, "沙盒已存在，请先清理旧沙盒", {"sandbox_exists": True})

        try:
            os.makedirs(sandbox_dir, exist_ok=True)

            # 只复制必要的目录（不复制巨型Shape/文件夹，只创建符号链接或minimal副本）
            dirs_to_copy = ["Setting", "Script"]
            dirs_to_link = ["Shape", "Music", "Sound"]

            copied = []
            for d in dirs_to_copy:
                src = os.path.join(self.game_path, d)
                if os.path.exists(src):
                    dst = os.path.join(sandbox_dir, d)
                    shutil.copytree(src, dst)
                    copied.append(d)

            linked = []
            for d in dirs_to_link:
                src = os.path.join(self.game_path, d)
                if os.path.exists(src):
                    dst = os.path.join(sandbox_dir, d)
                    try:
                        os.symlink(src, dst, target_is_directory=True)
                        linked.append(d)
                    except OSError:
                        # 符号链接失败则复制
                        shutil.copytree(src, dst)
                        copied.append(d)

            # 复制 EXE
            exe_src = os.path.join(self.game_path, "Sango7.exe")
            if os.path.exists(exe_src):
                shutil.copy2(exe_src, os.path.join(sandbox_dir, "Sango7.exe"))
                copied.append("Sango7.exe")

            # 保存沙盒元数据
            meta = {
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "game_path": self.game_path,
                "copied": copied,
                "linked": linked,
                "mods_installed": [],
            }
            with open(os.path.join(sandbox_dir, "sandbox_meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            return {
                "success": True,
                "sandbox_dir": sandbox_dir,
                "copied": copied,
                "linked": linked,
                "message": f"沙盒已创建 (复制: {len(copied)}个, 链接: {len(linked)}个)",
            }
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_install_to_sandbox(self, mod_name: str) -> dict:
        """将MOD安装到沙盒中测试"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        sandbox_dir = os.path.join(WRITE_ROOT, "sandbox")
        if not os.path.exists(sandbox_dir):
            return error_response(ErrorCode.FILE_NOT_FOUND, "沙盒不存在，请先创建沙盒")

        export_dir = os.path.join(WRITE_ROOT, "exports", mod_name)
        if not os.path.exists(export_dir):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"MOD包 '{mod_name}' 不存在，请先打包")

        try:
            installed = []
            for sub in ["Setting", "Shape", "Music", "Sound", "Script"]:
                src = os.path.join(export_dir, sub)
                if os.path.exists(src):
                    dst = os.path.join(sandbox_dir, sub)
                    os.makedirs(dst, exist_ok=True)
                    for root, _, files in os.walk(src):
                        for fname in files:
                            s = os.path.join(root, fname)
                            rel = os.path.relpath(s, src)
                            d = os.path.join(dst, rel)
                            os.makedirs(os.path.dirname(d), exist_ok=True)
                            shutil.copy2(s, d)
                            installed.append(os.path.join(sub, rel))

            # 更新沙盒元数据
            meta_path = os.path.join(sandbox_dir, "sandbox_meta.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if mod_name not in meta.get("mods_installed", []):
                    meta["mods_installed"].append(mod_name)
                meta["last_install"] = time.strftime("%Y-%m-%d %H:%M:%S")
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)

            return {
                "success": True,
                "installed": len(installed),
                "message": f"MOD '{mod_name}' 已安装到沙盒 ({len(installed)} 个文件)",
            }
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_launch_sandbox(self) -> dict:
        """从沙盒启动游戏"""
        sandbox_dir = os.path.join(WRITE_ROOT, "sandbox")
        exe_path = os.path.join(sandbox_dir, "Sango7.exe")
        if not os.path.exists(exe_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "沙盒中未找到Sango7.exe，请先创建沙盒")

        try:
            import subprocess
            subprocess.Popen(exe_path, cwd=sandbox_dir,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return success_response(message="游戏已从沙盒启动")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_cleanup_sandbox(self) -> dict:
        """清理沙盒环境"""
        sandbox_dir = os.path.join(WRITE_ROOT, "sandbox")
        if not os.path.exists(sandbox_dir):
            return success_response(message="沙盒不存在，无需清理")

        try:
            # 先删除符号链接目录中的文件，再删除目录
            meta_path = os.path.join(sandbox_dir, "sandbox_meta.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                # 对于链接目录，只删除新文件（即MOD安装的文件）
                for d in meta.get("linked", []):
                    linked_dir = os.path.join(sandbox_dir, d)
                    if os.path.islink(linked_dir):
                        os.unlink(linked_dir)
                    elif os.path.isdir(linked_dir):
                        # 如果是复制而非链接的，整体删除
                        shutil.rmtree(linked_dir, ignore_errors=True)

            shutil.rmtree(sandbox_dir, ignore_errors=True)
            return success_response(message="沙盒已清理")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_get_sandbox_status(self) -> dict:
        """获取沙盒状态"""
        sandbox_dir = os.path.join(WRITE_ROOT, "sandbox")
        if not os.path.exists(sandbox_dir):
            return {"success": True, "exists": False, "message": "沙盒未创建"}

        meta_path = os.path.join(sandbox_dir, "sandbox_meta.json")
        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception as e:
                logger.error(f"操作失败: {e}")
                pass

        # 统计沙盒中的文件
        file_count = 0
        total_size = 0
        for root, _, files in os.walk(sandbox_dir):
            for f in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
                file_count += 1

        return {
            "success": True,
            "exists": True,
            "created": meta.get("created", ""),
            "mods_installed": meta.get("mods_installed", []),
            "last_install": meta.get("last_install", ""),
            "file_count": file_count,
            "total_size_mb": round(total_size / 1024 / 1024, 1),
            "message": f"沙盒: {file_count} 个文件, {round(total_size / 1024 / 1024, 1)}MB",
        }

    # ============================================================
    # API: 操作历史记录
    # ============================================================
    def _log_operation(self, action: str, target: str, detail: str = ""):
        """记录操作到历史日志"""
        log_path = os.path.join(WRITE_ROOT, "data", "operation_history.json")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        history = []
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception as e:
                logger.error(f"操作失败: {e}")
                pass

        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "target": target,
            "detail": detail,
        }
        history.append(entry)

        # 保留最近 500 条记录
        if len(history) > 500:
            history = history[-500:]

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def api_get_operation_history(self, limit: int = 50, action_filter: str = None) -> dict:
        """获取操作历史记录"""
        log_path = os.path.join(WRITE_ROOT, "data", "operation_history.json")
        if not os.path.exists(log_path):
            return {"success": True, "history": [], "total": 0, "message": "无操作记录"}

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception as e:
            logger.error(f"操作失败: {e}")
            return {"success": True, "history": [], "total": 0, "message": "读取失败"}

        # 过滤
        if action_filter:
            history = [h for h in history if action_filter.lower() in h.get("action", "").lower()]

        # 取最近 N 条
        recent = history[-limit:]
        recent.reverse()  # 最新的在前

        return {
            "success": True,
            "history": recent,
            "total": len(history),
            "shown": len(recent),
            "message": f"共 {len(history)} 条记录，显示最近 {len(recent)} 条",
        }

    def api_clear_operation_history(self) -> dict:
        """清空操作历史记录"""
        log_path = os.path.join(WRITE_ROOT, "data", "operation_history.json")
        if os.path.exists(log_path):
            os.remove(log_path)
        return success_response(message="操作历史已清空")

    # ============================================================
    # API: 窗口模式分辨率预设
    # ============================================================
    def api_apply_resolution_preset(self, preset: str) -> dict:
        """应用分辨率预设: 1024x768/1280x720/1366x768/1440x900/1600x900/1920x1080/fullscreen"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        presets = {
            "1024x768": (1024, 768, False),
            "1280x720": (1280, 720, False),
            "1366x768": (1366, 768, False),
            "1440x900": (1440, 900, False),
            "1600x900": (1600, 900, False),
            "1920x1080": (1920, 1080, False),
            "fullscreen": (0, 0, True),
        }
        if preset not in presets:
            return error_response(ErrorCode.INVALID_PARAM, f"不支持的预设: {preset}，可用: {list(presets.keys())}")
        w, h, fullscreen = presets[preset]
        ini_path = os.path.join(self.game_path, "Sango7.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(ini_path)
        parser = IniParser()
        if os.path.exists(ini_path):
            parser.load(ini_path)
        else:
            parser.add_section("Sango7")
        parser.set("Sango7", "m_nWidth", str(w))
        parser.set("Sango7", "m_nHeight", str(h))
        parser.set("Sango7", "m_bFullScreen", "1" if fullscreen else "0")
        parser.set("Sango7", "m_bWindow", "0" if fullscreen else "0")
        parser.save(ini_path)
        label = "全屏" if fullscreen else f"{w}×{h}"
        return success_response({"width": w, "height": h, "fullscreen": fullscreen}, message=f"分辨率已设置为 {label}")

