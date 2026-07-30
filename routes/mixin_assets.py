import os, json, re, shutil, base64, tempfile, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional

from core.config import WRITE_ROOT, PROJECT_ROOT, HAS_TK

from core.ini_parser import IniParser
from core.shp_converter import HAS_PIL

from core.error_codes import ErrorCode, safe_error_message, error_response, success_response

logger = logging.getLogger('San7ModMaker')

__all__ = ['San7ModMakerAssets']

class San7ModMakerAssets:
    """MOD制作器 - 资源管理 (SHP/头像/图标/模型/特效)"""

    # 资源缓存 (由 mixin_base.__init__ 初始化)
    _CACHE_TTL = 30  # 缓存有效期（秒）

    def _ensure_cache(self):
        """确保缓存字典已初始化"""
        if not hasattr(self, '_resource_cache'):
            self._resource_cache = {}

    def api_invalidate_cache(self, key: str = None) -> dict:
        """清除资源缓存"""
        self._ensure_cache()
        if key:
            self._resource_cache.pop(key, None)
            return {"success": True, "message": f"缓存已清除: {key}"}
        self._resource_cache.clear()
        return success_response(message="全部缓存已清除")

    def _cached(self, key: str, factory):
        """通用缓存获取器"""
        self._ensure_cache()
        import time
        if key in self._resource_cache:
            data, ts = self._resource_cache[key]
            if time.time() - ts < self._CACHE_TTL:
                return data
        data = factory()
        self._resource_cache[key] = (data, time.time())
        return data

    def _invalidate_asset_cache(self, *prefixes: str):
        """按前缀清除资源缓存（用于修改操作后失效）"""
        self._ensure_cache()
        if not prefixes:
            self._resource_cache.clear()
            return
        for key in list(self._resource_cache.keys()):
            for prefix in prefixes:
                if key.startswith(prefix):
                    self._resource_cache.pop(key, None)
                    break

    # ============================================================
    # API: SHP头像预览/转换
    # ============================================================

    def api_get_face_preview(self, face_id: int) -> dict:
        """获取头像base64预览数据（带缓存）"""
        if not self.game_path:
            return {"success": False, "imgData": "", "message": "请先设置游戏目录"}
        cache_key = f"face_preview_{face_id}"
        return self._cached(cache_key, lambda: self._get_face_preview_impl(face_id))

    def _get_face_preview_impl(self, face_id: int) -> dict:
        """头像预览实现（不含缓存逻辑）"""
        try:
            b64 = self.shp_converter.load_shp_base64(face_id)
            return {"success": True, "imgData": b64, "faceId": face_id}
        except ImportError:
            return {"success": False, "imgData": "", "message": "Pillow库未安装，请运行: pip install Pillow"}
        except Exception as e:
            return {"success": False, "imgData": "", "message": safe_error_message(e)}

    def api_convert_image_to_shp(self, src_path: str, face_id: int) -> dict:
        """导入图片转SHP（头像）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        try:
            out_path = self.shp_converter.image_to_shp(src_path, face_id)
            self._invalidate_asset_cache("face_preview_", "face_browse_")
            return {
                "success": True,
                "message": f"头像转换完成: {face_id:04d}.shp",
                "path": out_path,
                "log": self.shp_converter.get_log(),
            }
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_convert_image_to_bfobj_shp(self, src_path: str, bfobj_subdir: str = "") -> dict:
        """导入图片转为 BFObj 兵种模型 SHP"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            bfobj_dir = os.path.join(self.game_path, "Shape", "BFObj")
            if bfobj_subdir:
                bfobj_dir = os.path.join(bfobj_dir, bfobj_subdir)
            os.makedirs(bfobj_dir, exist_ok=True)
            existing = []
            if os.path.exists(bfobj_dir):
                for f in os.listdir(bfobj_dir):
                    if f.lower().endswith(".shp"):
                        num = ''.join(c for c in f if c.isdigit())
                        if num:
                            existing.append(int(num))
            next_id = max(existing) + 1 if existing else 1
            out_path = self.shp_converter.image_to_shp(src_path, next_id, bfobj_dir)
            self._invalidate_asset_cache("shape_resources_")
            rel_path = os.path.relpath(out_path, os.path.join(self.game_path, "Shape", "BFObj"))
            return {
                "success": True,
                "message": f"BFObj模型图片导入完成: {next_id:04d}.shp",
                "path": out_path,
                "relativePath": rel_path,
                "newId": next_id,
            }
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # API: 物品图标 (ThingIcon)
    # ============================================================

    def api_convert_image_to_thing_icon(self, src_path: str, icon_id: int) -> dict:
        """导入图片转为物品图标 SHP (支持 base64 data URL 或文件路径)"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            import tempfile
            actual_path = src_path
            # 处理 base64 data URL
            if src_path.startswith("data:image"):
                import base64
                header, encoded = src_path.split(",", 1)
                img_data = base64.b64decode(encoded)
                suffix = ".png" if "png" in header else ".jpg"
                tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
                tmp.write(img_data)
                tmp.close()
                actual_path = tmp.name

            icon_dir = os.path.join(self.game_path, "Shape", "ThingIcon")
            os.makedirs(icon_dir, exist_ok=True)
            out_path = self.shp_converter.image_to_shp(actual_path, icon_id, icon_dir)

            self._invalidate_asset_cache("thing_icon_preview_")

            # 清理临时文件
            if actual_path != src_path and os.path.exists(actual_path):
                os.unlink(actual_path)

            return {
                "success": True,
                "message": f"物品图标转换完成: {icon_id:04d}.shp",
                "path": out_path,
            }
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_export_thing_icon_to_png(self, icon_id: int) -> dict:
        """导出物品图标 SHP 为 PNG (返回 base64)"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            import base64
            icon_dir = os.path.join(self.game_path, "Shape", "ThingIcon")
            shp_path = os.path.join(icon_dir, f"{icon_id:04d}.shp")
            if not os.path.exists(shp_path):
                return {"success": False, "message": f"图标文件 {icon_id:04d}.shp 不存在"}
            # 解码 SHP 为图片
            with open(shp_path, "rb") as f:
                data = f.read()
            img = self.shp_converter.decode_shp_bytes(data)
            if img is None:
                return {"success": False, "message": "解码失败"}
            # 转为 PNG base64
            from io import BytesIO
            buf = BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            return {
                "success": True,
                "base64": "data:image/png;base64," + b64,
                "message": "物品图标导出成功",
            }
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_thing_icon_batch_import(self, file_map: dict) -> dict:
        """批量导入物品图标: {icon_id: src_path, ...}"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        results = []
        icon_dir = os.path.join(self.game_path, "Shape", "ThingIcon")
        os.makedirs(icon_dir, exist_ok=True)
        for icon_id, src_path in file_map.items():
            try:
                out_path = self.shp_converter.image_to_shp(src_path, int(icon_id), icon_dir)
                results.append({"icon_id": icon_id, "success": True, "path": out_path})
            except Exception as e:
                results.append({"icon_id": icon_id, "success": False, "message": safe_error_message(e)})
        self._invalidate_asset_cache("thing_icon_preview_")
        return {"success": True, "results": results}

    def api_thing_icon_batch_export(self, icon_ids: list) -> dict:
        """批量导出物品图标"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        results = []
        icon_dir = os.path.join(self.game_path, "Shape", "ThingIcon")
        for icon_id in icon_ids:
            try:
                out_path = self.shp_converter.shp_to_png(int(icon_id), icon_dir)
                results.append({"icon_id": icon_id, "success": True, "path": out_path})
            except Exception as e:
                results.append({"icon_id": icon_id, "success": False, "message": safe_error_message(e)})
        return {"success": True, "results": results}

    def api_get_thing_icon_preview(self, icon_id: int) -> dict:
        """获取物品图标 base64 预览（带缓存）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        cache_key = f"thing_icon_preview_{icon_id}"
        return self._cached(cache_key, lambda: self._get_thing_icon_preview_impl(icon_id))

    def _get_thing_icon_preview_impl(self, icon_id: int) -> dict:
        """物品图标预览实现（不含缓存逻辑）"""
        try:
            icon_dir = os.path.join(self.game_path, "Shape", "ThingIcon")
            if not os.path.exists(icon_dir):
                return {"success": False, "message": "ThingIcon目录不存在"}
            for fname in sorted(os.listdir(icon_dir)):
                match = re.match(r"^(\d+)", fname)
                if match and int(match.group(1)) == icon_id:
                    fpath = os.path.join(icon_dir, fname)
                    b64 = self.shp_converter.load_shp_file_base64(fpath)
                    return {"success": True, "icon_id": icon_id, "filename": fname, "base64": b64}
            return {"success": False, "message": f"未找到图标ID {icon_id}"}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_get_next_thing_icon_id(self) -> dict:
        """获取下一个可用的物品图标ID"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            icon_dir = os.path.join(self.game_path, "Shape", "ThingIcon")
            if not os.path.exists(icon_dir):
                return {"success": True, "next_id": 1, "message": "ThingIcon目录不存在，建议从1开始"}
            used_ids = set()
            for fname in os.listdir(icon_dir):
                match = re.match(r"^(\d+)", fname)
                if match:
                    used_ids.add(int(match.group(1)))
            next_id = 1
            while next_id in used_ids:
                next_id += 1
            return {"success": True, "next_id": next_id, "used_count": len(used_ids),
                    "message": f"下一个可用图标ID: {next_id}"}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_create_sh_dir(self, obd_type: str, number: str) -> dict:
        """创建兵种动画帧目录结构 Shape/BFObj/{type}/{number}/"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            number = str(number).strip().zfill(3)
            bfobj_dir = os.path.join(self.game_path, "Shape", "BFObj", obd_type, number)
            os.makedirs(bfobj_dir, exist_ok=True)
            # 创建各动画类型子目录和说明文件
            anim_types = ['Wait', 'Walk', 'Atk', 'Die', 'Hurt', 'Skill']
            for t in anim_types:
                anim_dir = os.path.join(bfobj_dir, t)
                os.makedirs(anim_dir, exist_ok=True)
            readme_path = os.path.join(bfobj_dir, 'README.txt')
            if not os.path.exists(readme_path):
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write(f"BFObj {obd_type} #{number} 动画帧目录\n")
                    f.write(f"每帧图片尺寸建议: {'128x128' if obd_type in ('BFSoldier','BFGen') else '64x64'}\n")
                    f.write(f"将各帧PNG放入对应子目录后，使用「帧导入」功能批量转换\n")
            return {
                "success": True,
                "message": f"目录已创建: Shape/BFObj/{obd_type}/{number}/",
                "path": bfobj_dir,
            }
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_import_sprite_frame(self, obd_type: str, number: str, anim_type: str, frame_idx: int) -> dict:
        """导入单个兵种动画帧：从 import 目录读取 PNG 并转为 SHP"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            number = str(number).strip().zfill(3)
            frame_idx = int(frame_idx)
            # 源图片路径: {PROJECT_ROOT}/import/{obdType}/{number}/{animType}{frameIdx}.png
            import_base = os.path.join(PROJECT_ROOT, "import", obd_type, number)
            src_name = f"{anim_type}{frame_idx}.png"
            src_path = os.path.join(import_base, src_name)
            if not os.path.exists(src_path):
                # 尝试在 import 根目录查找
                alt_src = os.path.join(PROJECT_ROOT, "import", f"{obd_type}_{number}_{anim_type}{frame_idx}.png")
                if os.path.exists(alt_src):
                    src_path = alt_src
                else:
                    return {"success": False, "message": f"源图片不存在: {src_name}\n请将图片放入: {import_base}/"}
            # 目标目录: Shape/BFObj/{obdType}/{number}/
            bfobj_dir = os.path.join(self.game_path, "Shape", "BFObj", obd_type, number)
            os.makedirs(bfobj_dir, exist_ok=True)
            # 转换 PNG → SHP
            out_path = self.shp_converter.image_to_shp(src_path, frame_idx, bfobj_dir, f"{anim_type}{frame_idx}")
            self._invalidate_asset_cache("shape_resources_")
            rel_path = os.path.relpath(out_path, os.path.join(self.game_path, "Shape", "BFObj"))
            return {
                "success": True,
                "message": f"帧导入完成: {anim_type}{frame_idx}.shp",
                "path": out_path,
                "relativePath": rel_path,
                "frameId": frame_idx,
            }
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_export_shp_to_png(self, face_id: int, save_path: str) -> dict:
        """导出SHP为PNG"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        try:
            out = self.shp_converter.shp_to_png(face_id, save_path)
            return {"success": True, "message": "导出成功", "path": out}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_select_image_file(self) -> dict:
        """选择图片文件"""
        if not HAS_TK:
            return {"success": False, "path": "", "message": "当前环境不支持文件对话框"}
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(
            title="选择头像图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif"), ("所有文件", "*.*")]
        )
        root.destroy()
        return {"success": bool(path), "path": path}

    def api_select_save_path(self) -> dict:
        """选择保存路径"""
        if not HAS_TK:
            return {"success": False, "path": "", "message": "当前环境不支持文件对话框"}
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.asksaveasfilename(
            title="导出PNG头像",
            defaultextension=".png",
            filetypes=[("PNG图片", "*.png"), ("所有文件", "*.*")]
        )
        root.destroy()
        return {"success": bool(path), "path": path}

    def api_select_csv_file(self) -> dict:
        """选择CSV文件"""
        if not HAS_TK:
            return {"success": False, "path": "", "message": "当前环境不支持文件对话框"}
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(
            title="选择CSV文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        root.destroy()
        return {"success": bool(path), "path": path}

    def api_shp_select_dir(self) -> dict:
        """选择SHP文件目录"""
        if not HAS_TK:
            return {"success": False, "path": "", "message": "当前环境不支持文件对话框"}
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askdirectory(title="选择SHP文件目录")
        root.destroy()
        return {"success": bool(path), "path": path}

    # ============================================================
    # API: 头像批量管理
    # ============================================================

    def api_face_batch_preview(self, start: int, count: int = 50) -> dict:
        """批量预览头像"""
        return self.shp_converter.batch_preview(start, count)

    def api_face_batch_delete(self, face_ids: list) -> dict:
        """批量删除头像"""
        result = self.shp_converter.batch_delete(face_ids)
        self._invalidate_asset_cache("face_preview_", "face_browse_")
        return result

    def api_face_batch_export(self, face_ids: list, output_dir: str) -> dict:
        """批量导出头像"""
        return self.shp_converter.batch_export(face_ids, output_dir)

    def api_face_stats(self) -> dict:
        """头像统计"""
        return self.shp_converter.get_face_stats()

    def api_get_next_face_id(self) -> dict:
        """获取下一个可用的 FaceID（扫描 Shape/GenFace/ 目录）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            face_dir = os.path.join(self.game_path, "Shape", "GenFace")
            if not os.path.exists(face_dir):
                return {"success": True, "next_id": 1, "message": "Face目录不存在，建议从1开始"}
            used_ids = set()
            for fname in os.listdir(face_dir):
                match = re.match(r"^(\d+)", fname)
                if match:
                    used_ids.add(int(match.group(1)))
            next_id = 1
            while next_id in used_ids:
                next_id += 1
            return {"success": True, "next_id": next_id, "used_count": len(used_ids),
                    "message": f"下一个可用FaceID: {next_id}"}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_face_browse(self, start: int = 1, count: int = 30) -> dict:
        """浏览可用头像列表（含base64缩略图，带缓存）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        cache_key = f"face_browse_{start}_{count}"
        return self._cached(cache_key, lambda: self._face_browse_impl(start, count))

    def _face_browse_impl(self, start: int, count: int) -> dict:
        """头像浏览实现（不含缓存逻辑）"""
        try:
            face_dir = os.path.join(self.game_path, "Shape", "GenFace")
            if not os.path.exists(face_dir):
                return {"success": True, "faces": [], "total": 0}
            all_faces = []
            for fname in sorted(os.listdir(face_dir)):
                match = re.match(r"^(\d+)", fname)
                if match:
                    fid = int(match.group(1))
                    if start <= fid < start + count:
                        fpath = os.path.join(face_dir, fname)
                        try:
                            b64 = self.shp_converter.load_shp_file_base64(fpath)
                            all_faces.append({"id": fid, "filename": fname, "base64": b64})
                        except Exception as e:
                            logger.error(f"操作失败: {e}")
                            all_faces.append({"id": fid, "filename": fname, "base64": None})
            return {"success": True, "faces": all_faces, "total": len(all_faces),
                    "start": start, "count": count}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # API: BFObj 兵种模型 SHP 管理
    # ============================================================

    def api_list_bfobj_shps(self) -> dict:
        """列出 Shape/BFObj/ 目录下的兵种模型 SHP 文件"""
        return self.shp_converter.list_bfobj_shps()

    def api_preview_bfobj_shp(self, rel_path: str) -> dict:
        """预览 BFObj 目录下的 SHP 文件"""
        return self.shp_converter.preview_bfobj_shp(rel_path)

    def api_preview_bfobj_animation(self, obd_type: str, number: str, anim_type: str = "Wait") -> dict:
        """预览兵种动画：将序列帧SHP转为GIF base64"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            from PIL import Image
            import base64
            from io import BytesIO

            number = str(number).strip().zfill(3)
            anim_dir = os.path.join(self.game_path, "Shape", "BFObj", obd_type, number, anim_type)
            if not os.path.exists(anim_dir):
                return {"success": False, "message": f"动画目录不存在: BFObj/{obd_type}/{number}/{anim_type}"}

            # 收集所有帧
            frames = []
            shp_files = sorted([f for f in os.listdir(anim_dir) if f.lower().endswith(".shp")])
            if not shp_files:
                return {"success": False, "message": "该目录下无SHP帧文件"}

            for fname in shp_files:
                fpath = os.path.join(anim_dir, fname)
                try:
                    img = self.shp_converter._decode_shp_file(fpath)
                    frames.append(img)
                except Exception as e:
                    logger.error(f"操作失败: {e}")
                    pass

            if not frames:
                return {"success": False, "message": "无法解码任何帧"}

            # 生成 GIF
            buf = BytesIO()
            frames[0].save(
                buf, format="GIF", save_all=True,
                append_images=frames[1:],
                duration=150, loop=0, disposal=2
            )
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            return {
                "success": True,
                "base64": "data:image/gif;base64," + b64,
                "frame_count": len(frames),
                "anim_type": anim_type,
                "message": f"动画预览: {anim_type} ({len(frames)}帧)",
            }
        except ImportError:
            return {"success": False, "message": "Pillow库未安装，请运行: pip install Pillow"}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_list_bfobj_anim_dirs(self, obd_type: str = "BFSoldier", number: str = None) -> dict:
        """列出兵种动画目录及其帧数"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            bfobj_dir = os.path.join(self.game_path, "Shape", "BFObj", obd_type)
            if not os.path.exists(bfobj_dir):
                return {"success": True, "dirs": [], "message": "目录不存在"}

            if number:
                number = str(number).strip().zfill(3)
                anim_base = os.path.join(bfobj_dir, number)
                if not os.path.exists(anim_base):
                    return {"success": False, "message": f"模型目录 {number} 不存在"}
                anims = []
                for anim_type in sorted(os.listdir(anim_base)):
                    anim_path = os.path.join(anim_base, anim_type)
                    if os.path.isdir(anim_path):
                        shp_count = len([f for f in os.listdir(anim_path) if f.lower().endswith(".shp")])
                        anims.append({"type": anim_type, "frame_count": shp_count})
                return {"success": True, "number": number, "anims": anims}

            # 列出所有模型编号
            dirs = []
            for d in sorted(os.listdir(bfobj_dir)):
                dpath = os.path.join(bfobj_dir, d)
                if os.path.isdir(dpath):
                    total_frames = 0
                    anim_types = []
                    for at in sorted(os.listdir(dpath)):
                        at_path = os.path.join(dpath, at)
                        if os.path.isdir(at_path):
                            fc = len([f for f in os.listdir(at_path) if f.lower().endswith(".shp")])
                            if fc > 0:
                                anim_types.append(at)
                                total_frames += fc
                    dirs.append({"number": d, "anim_types": anim_types, "total_frames": total_frames})
            return {"success": True, "dirs": dirs, "count": len(dirs)}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # API: genhalf 半身像 SHP 管理
    # ============================================================

    def api_list_genhalf_shps(self) -> dict:
        """列出 Shape/genhalf/ 目录下的半身像 SHP 文件"""
        if not self.game_path:
            return {"success": False, "message": "未配置游戏目录", "files": []}
        genhalf_dir = os.path.join(self.game_path, "Shape", "genhalf")
        if not os.path.exists(genhalf_dir):
            return {"success": True, "files": [], "message": "genhalf 目录不存在"}
        files = []
        for root, _, fnames in os.walk(genhalf_dir):
            for f in sorted(fnames):
                if f.lower().endswith(".shp"):
                    fpath = os.path.join(root, f)
                    rel = os.path.relpath(fpath, genhalf_dir)
                    files.append({
                        "name": f,
                        "path": rel,
                        "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                    })
        return {"success": True, "files": files, "count": len(files)}

    def api_preview_genhalf_shp(self, rel_path: str) -> dict:
        """预览 genhalf 目录下的 SHP 文件（返回 base64 PNG）"""
        if not HAS_PIL:
            return {"success": False, "message": "PIL库不可用"}
        if not self.game_path:
            return {"success": False, "message": "未配置游戏目录"}
        genhalf_dir = os.path.join(self.game_path, "Shape", "genhalf")
        safe_path = os.path.normpath(os.path.join(genhalf_dir, rel_path))
        if not safe_path.startswith(genhalf_dir) or not os.path.exists(safe_path):
            return {"success": False, "message": "文件不存在或路径无效"}
        try:
            img = self.shp_converter._load_shp_file(safe_path)
            if img:
                buf = BytesIO()
                img.save(buf, "PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                return {"success": True, "image_base64": b64, "size": f"{img.width}x{img.height}"}
            return {"success": False, "message": "解析失败"}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_import_image_to_genhalf(self, src_path: str, genhalf_subdir: str = "") -> dict:
        """导入图片转为 genhalf 半身像 SHP"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            genhalf_dir = os.path.join(self.game_path, "Shape", "genhalf")
            if genhalf_subdir:
                genhalf_dir = os.path.join(genhalf_dir, genhalf_subdir)
            os.makedirs(genhalf_dir, exist_ok=True)
            existing = []
            if os.path.exists(genhalf_dir):
                for f in os.listdir(genhalf_dir):
                    if f.lower().endswith(".shp"):
                        num = ''.join(c for c in f if c.isdigit())
                        if num:
                            existing.append(int(num))
            next_id = max(existing) + 1 if existing else 1
            out_path = self.shp_converter.image_to_shp(src_path, next_id, genhalf_dir)
            self._invalidate_asset_cache("shape_resources_")
            return {
                "success": True,
                "message": f"半身像导入完成: {next_id:04d}.shp",
                "path": out_path,
                "newId": next_id,
            }
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # API: Shape 资源统一浏览
    # ============================================================

    def api_browse_shape_resources(self, category: str = "all") -> dict:
        """统一浏览 Shape 资源（Face / BFObj / genhalf，带缓存）"""
        if not self.game_path:
            return {"success": False, "message": "未配置游戏目录", "categories": {}}
        cache_key = f"shape_resources_{category}"
        return self._cached(cache_key, lambda: self._browse_shape_resources_impl(category))

    def _browse_shape_resources_impl(self, category: str) -> dict:
        """Shape 资源浏览实现（不含缓存逻辑）"""
        result = {"success": True, "categories": {}}
        shape_dir = os.path.join(self.game_path, "Shape")
        if not os.path.exists(shape_dir):
            return {"success": False, "message": "Shape 目录不存在", "categories": {}}

        for cat in ("Face", "BFObj", "genhalf"):
            if category != "all" and cat != category:
                continue
            cat_dir = os.path.join(shape_dir, cat)
            if not os.path.exists(cat_dir):
                result["categories"][cat] = {"exists": False, "files": [], "count": 0}
                continue
            files = []
            for root, _, fnames in os.walk(cat_dir):
                for f in sorted(fnames):
                    if f.lower().endswith(".shp"):
                        fpath = os.path.join(root, f)
                        rel = os.path.relpath(fpath, cat_dir)
                        sz = os.path.getsize(fpath)
                        files.append({
                            "name": f,
                            "path": rel,
                            "size_kb": round(sz / 1024, 1),
                            "size_bytes": sz,
                        })
            result["categories"][cat] = {
                "exists": True,
                "files": files,
                "count": len(files),
                "dir": cat_dir,
            }
        return result

    def api_shape_resource_stats(self) -> dict:
        """Shape 资源统计概览"""
        browse = self.api_browse_shape_resources("all")
        stats = {"total_files": 0, "total_size_mb": 0.0, "categories": {}}
        for cat, data in browse.get("categories", {}).items():
            count = data.get("count", 0)
            total_kb = sum(f.get("size_kb", 0) for f in data.get("files", []))
            stats["categories"][cat] = {
                "exists": data.get("exists", False),
                "count": count,
                "size_mb": round(total_kb / 1024, 1),
            }
            stats["total_files"] += count
            stats["total_size_mb"] += total_kb / 1024
        stats["total_size_mb"] = round(stats["total_size_mb"], 1)
        return stats

    def api_shape_thumbnails(self, category: str, paths: list) -> dict:
        """批量生成 Shape 文件缩略图（base64）"""
        thumbnails = {}
        for path in paths:
            if not os.path.exists(path):
                thumbnails[path] = None
                continue
            try:
                img = self.shp_converter._decode_shp_file(path)
                thumb = img.copy()
                thumb.thumbnail((48, 48))
                buffer = BytesIO()
                thumb.save(buffer, format="PNG")
                b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
                thumbnails[path] = "data:image/png;base64," + b64
            except Exception as e:
                logger.warning(f"生成缩略图失败: {path}: {e}")
                thumbnails[path] = None
        return {"success": True, "thumbnails": thumbnails}

    def api_shape_batch_delete(self, category: str, paths: list) -> dict:
        """批量删除 Shape 资源文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        deleted = []
        failed = []
        for path in paths:
            if not os.path.exists(path):
                failed.append({"path": path, "reason": "文件不存在"})
                continue
            try:
                # 备份
                backup_path = path + ".modbak"
                if not os.path.exists(backup_path):
                    shutil.copy2(path, backup_path)
                os.remove(path)
                deleted.append(path)
            except Exception as e:
                failed.append({"path": path, "reason": str(e)})
        self._invalidate_asset_cache("shape_resources_")
        return {"success": True, "deleted": deleted, "failed": failed, "count": len(deleted)}

    def api_shape_batch_export(self, category: str, paths: list, output_dir: str = None) -> dict:
        """批量导出 Shape 资源为 PNG"""
        if not output_dir:
            output_dir = os.path.join(self.game_path or "", "ShapeExport")
        os.makedirs(output_dir, exist_ok=True)
        exported = []
        failed = []
        for path in paths:
            if not os.path.exists(path):
                failed.append({"path": path, "reason": "文件不存在"})
                continue
            try:
                img = self.shp_converter._decode_shp_file(path)
                out_name = os.path.splitext(os.path.basename(path))[0] + ".png"
                out_path = os.path.join(output_dir, out_name)
                img.save(out_path, "PNG")
                exported.append({"path": path, "output": out_path})
            except Exception as e:
                failed.append({"path": path, "reason": str(e)})
        return {"success": True, "exported": exported, "failed": failed, "output_dir": output_dir, "count": len(exported)}

    # ============================================================
    # V3.8.0: 素材资源管理增强 — 批量导入/搜索/分类
    # ============================================================

    def api_resource_search(self, keyword: str = "", category: str = "all", file_type: str = "all", sort_by: str = "name") -> dict:
        """全局素材搜索：按名称/类型/大小搜索Shape和Audio资源"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        results = []
        shape_dir = os.path.join(self.game_path, "Shape")
        audio_dir = os.path.join(self.game_path, "Music")

        # 搜索Shape资源
        if category in ("all", "shape") and os.path.exists(shape_dir):
            for root, _, files in os.walk(shape_dir):
                for fname in files:
                    if keyword and keyword.lower() not in fname.lower():
                        continue
                    fp = os.path.join(root, fname)
                    ext = os.path.splitext(fname)[1].lower()
                    if file_type != "all":
                        if file_type == "shp" and ext not in (".shp",):
                            continue
                        if file_type == "png" and ext not in (".png", ".bmp", ".jpg", ".jpeg"):
                            continue
                    try:
                        sz = os.path.getsize(fp)
                        mtime = os.path.getmtime(fp)
                    except OSError:
                        continue
                    results.append({
                        "name": fname,
                        "path": os.path.relpath(fp, self.game_path),
                        "category": "shape",
                        "subdir": os.path.relpath(root, shape_dir),
                        "size_kb": round(sz / 1024, 1),
                        "ext": ext,
                        "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)),
                    })

        # 搜索音频资源
        if category in ("all", "audio") and os.path.exists(audio_dir):
            audio_exts = (".wav", ".mp3", ".ogg", ".flac", ".mid", ".midi")
            for root, _, files in os.walk(audio_dir):
                for fname in files:
                    if keyword and keyword.lower() not in fname.lower():
                        continue
                    ext = os.path.splitext(fname)[1].lower()
                    if file_type != "all" and file_type != "audio":
                        continue
                    if ext not in audio_exts:
                        continue
                    fp = os.path.join(root, fname)
                    try:
                        sz = os.path.getsize(fp)
                        mtime = os.path.getmtime(fp)
                    except OSError:
                        continue
                    results.append({
                        "name": fname,
                        "path": os.path.relpath(fp, self.game_path),
                        "category": "audio",
                        "subdir": os.path.relpath(root, audio_dir),
                        "size_kb": round(sz / 1024, 1),
                        "ext": ext,
                        "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)),
                    })

        # 排序
        if sort_by == "size":
            results.sort(key=lambda x: x["size_kb"], reverse=True)
        elif sort_by == "date":
            results.sort(key=lambda x: x["mtime"], reverse=True)
        else:
            results.sort(key=lambda x: x["name"])

        total_size = sum(r["size_kb"] for r in results)
        return {
            "success": True,
            "results": results,
            "total": len(results),
            "total_size_mb": round(total_size / 1024, 1),
            "keyword": keyword,
            "category": category,
            "file_type": file_type,
        }

    def api_resource_batch_import(self, source_dir: str, target_category: str = "shape", naming: str = "keep") -> dict:
        """从外部目录批量导入素材资源到游戏目录"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if not os.path.exists(source_dir):
            return {"success": False, "message": f"源目录不存在: {source_dir}"}

        if target_category == "shape":
            target_base = os.path.join(self.game_path, "Shape")
        elif target_category == "audio":
            target_base = os.path.join(self.game_path, "Music")
        elif target_category == "face":
            target_base = os.path.join(self.game_path, "Shape", "GenFace")
        else:
            target_base = os.path.join(self.game_path, target_category)

        os.makedirs(target_base, exist_ok=True)

        imported = []
        skipped = []
        failed = []
        counter = 0

        # 支持的格式
        img_exts = (".shp", ".png", ".bmp", ".jpg", ".jpeg", ".gif", ".tga")
        audio_exts = (".wav", ".mp3", ".ogg", ".flac", ".mid")

        for root, _, files in os.walk(source_dir):
            for fname in sorted(files):
                ext = os.path.splitext(fname)[1].lower()
                src = os.path.join(root, fname)

                if target_category in ("shape", "face") and ext not in img_exts:
                    continue
                if target_category == "audio" and ext not in audio_exts:
                    continue

                # 确定目标名称
                if naming == "sequential":
                    counter += 1
                    new_name = f"{counter:04d}{ext}"
                elif naming == "prefix_date":
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    new_name = f"{ts}_{counter:03d}{ext}"
                    counter += 1
                else:  # keep
                    new_name = fname

                dst = os.path.join(target_base, new_name)

                # 冲突处理：自动重命名
                if os.path.exists(dst) and naming == "keep":
                    base, e = os.path.splitext(fname)
                    c = 1
                    while os.path.exists(dst):
                        new_name = f"{base}_{c}{e}"
                        dst = os.path.join(target_base, new_name)
                        c += 1

                try:
                    # 如果是SHP→PNG转换
                    if ext == ".shp" and target_category in ("shape", "face"):
                        if self.shp_converter:
                            img = self.shp_converter._decode_shp_file(src)
                            png_name = os.path.splitext(new_name)[0] + ".png"
                            png_dst = os.path.join(target_base, png_name)
                            img.save(png_dst, "PNG")
                            imported.append({"source": fname, "target": png_name, "size_kb": round(os.path.getsize(png_dst) / 1024, 1), "converted": True})
                            continue
                    shutil.copy2(src, dst)
                    imported.append({"source": fname, "target": new_name, "size_kb": round(os.path.getsize(dst) / 1024, 1), "converted": False})
                except Exception as e:
                    failed.append({"source": fname, "reason": str(e)})

        self._invalidate_asset_cache("shape_resources_", "face_browse_", "thing_icon_preview_")
        return {
            "success": True,
            "message": f"导入完成：{len(imported)} 个成功" + (f"，{len(failed)} 个失败" if failed else ""),
            "imported": imported,
            "failed": failed,
            "total": len(imported),
            "target_dir": target_base,
        }

    def api_resource_categorize(self, action: str = "list", category: str = "", items: list = None) -> dict:
        """资源分类/标签管理：列出/添加/移除资源分类标签"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        tags_file = os.path.join(WRITE_ROOT, "mods", ".resource_tags.json")
        tags = {}
        if os.path.exists(tags_file):
            try:
                with open(tags_file, "r", encoding="utf-8") as f:
                    tags = json.load(f)
            except Exception as e:
                logger.error(f"操作失败: {e}")
                tags = {}

        if action == "list":
            # 统计各分类
            categories = {}
            for path, tag_list in tags.items():
                for t in tag_list:
                    if t not in categories:
                        categories[t] = []
                    categories[t].append(path)
            return {
                "success": True,
                "categories": {k: {"count": len(v), "items": v} for k, v in categories.items()},
                "total_tagged": len(tags),
            }

        elif action == "add" and items:
            for item in items:
                path = item.get("path", "")
                tag = item.get("tag", "")
                if not path or not tag:
                    continue
                if path not in tags:
                    tags[path] = []
                if tag not in tags[path]:
                    tags[path].append(tag)
            with open(tags_file, "w", encoding="utf-8") as f:
                json.dump(tags, f, ensure_ascii=False, indent=2)
            return {"success": True, "message": f"已为 {len(items)} 个资源添加标签", "tags": tags}

        elif action == "remove" and items:
            for item in items:
                path = item.get("path", "")
                tag = item.get("tag", "")
                if path in tags and tag in tags[path]:
                    tags[path].remove(tag)
                    if not tags[path]:
                        del tags[path]
            with open(tags_file, "w", encoding="utf-8") as f:
                json.dump(tags, f, ensure_ascii=False, indent=2)
            return {"success": True, "message": f"已移除标签", "tags": tags}

        elif action == "clear":
            tags = {}
            if os.path.exists(tags_file):
                os.remove(tags_file)
            return success_response(message="已清空所有标签")

        return {"success": False, "message": "无效操作"}

    # ============================================================
    # API: 特效知识库
    # ============================================================

    def api_effect_get_all(self) -> dict:
        """获取全部特效知识库"""
        return self.effect_catalog.get_all_catalogs()

    def api_effect_ball_types(self) -> dict:
        """获取弹道类型列表"""
        return self.effect_catalog.get_ball_types()

    def api_effect_damage_types(self) -> dict:
        """获取伤害类型列表"""
        return self.effect_catalog.get_damage_types()

    def api_effect_element_types(self) -> dict:
        """获取属性类型列表"""
        return self.effect_catalog.get_element_types()

    def api_effect_item_scripts(self) -> dict:
        """获取物品特效代码列表"""
        return self.effect_catalog.get_item_scripts()

    def api_effect_weapon_glow(self) -> dict:
        """获取武器发光配置信息"""
        return self.effect_catalog.get_weapon_glow_info()

    def api_effect_atk_types(self) -> dict:
        """获取攻击类型列表"""
        return self.effect_catalog.get_atk_types()

    def api_effect_templates(self) -> dict:
        """获取特效模板/预设"""
        return self.effect_catalog.get_effect_templates()

    def api_effect_save_type(self, catalog_type: str, item_data: dict, item_id=None) -> dict:
        """添加或更新特效类型条目"""
        return self.effect_catalog.save_type(catalog_type, item_data, item_id)

    def api_effect_delete_type(self, catalog_type: str, item_id) -> dict:
        """删除特效类型条目"""
        return self.effect_catalog.delete_type(catalog_type, item_id)

    def api_effect_export_json(self) -> dict:
        """导出全部特效知识库为 JSON 字符串"""
        data = self.effect_catalog.get_all_catalogs()
        if data.get("success"):
            import json
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            return {"success": True, "json": json_str, "message": "导出成功"}
        return data

    def api_effect_import_json(self, json_str: str, merge: bool = True) -> dict:
        """从 JSON 字符串导入特效知识库
        Args:
            json_str: JSON 字符串
            merge: True=合并到现有数据（新数据覆盖同id），False=完全替换
        """
        try:
            import json
            new_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return {"success": False, "message": f"JSON 解析失败: {e}"}

        valid_keys = {'ball_types', 'damage_types', 'element_types', 'item_scripts',
                      'weapon_glow', 'weapon_glow_ids', 'atk_types', 'templates'}
        imported_keys = set(new_data.keys()) & valid_keys
        if not imported_keys:
            return {"success": False, "message": "未识别到有效的特效数据"}

        try:
            if merge:
                # 合并模式：对每个 list 类型按 id 合并
                list_keys = {'ball_types', 'damage_types', 'element_types', 'item_scripts',
                            'weapon_glow_ids', 'atk_types', 'templates'}
                for key in imported_keys:
                    if key in list_keys and key in new_data:
                        existing = getattr(self.effect_catalog, self.effect_catalog._ATTR_MAP.get(
                            key.replace('_types', '').replace('_ids', '').replace('_scripts', ''),
                            key.replace('_types', '').replace('_ids', '').replace('_scripts', '')))
                        # 对于 list 类型，查找正确的 attr 名
                        attr_map_rev = {
                            'ball_types': 'BALL_TYPES', 'damage_types': 'DAMAGE_TYPES',
                            'element_types': 'ELEMENT_TYPES', 'item_scripts': 'ITEM_SCRIPTS',
                            'weapon_glow_ids': 'WEAPON_GLOW_IDS', 'atk_types': 'ATK_TYPES',
                            'templates': 'EFFECT_TEMPLATES',
                        }
                        attr_name = attr_map_rev.get(key)
                        if attr_name:
                            existing = getattr(self.effect_catalog, attr_name)
                            existing_ids = {item.get('id') for item in existing}
                            for new_item in new_data[key]:
                                if new_item.get('id') in existing_ids:
                                    # 更新现有条目
                                    for i, item in enumerate(existing):
                                        if item.get('id') == new_item.get('id'):
                                            existing[i] = new_item
                                            break
                                else:
                                    existing.append(new_item)
                    elif key == 'weapon_glow':
                        # 直接覆盖
                        self.effect_catalog.WEAPON_GLOW_INFO = new_data[key]
            else:
                # 完全替换模式
                for key in imported_keys:
                    if key == 'ball_types':
                        self.effect_catalog.BALL_TYPES = new_data[key]
                    elif key == 'damage_types':
                        self.effect_catalog.DAMAGE_TYPES = new_data[key]
                    elif key == 'element_types':
                        self.effect_catalog.ELEMENT_TYPES = new_data[key]
                    elif key == 'item_scripts':
                        self.effect_catalog.ITEM_SCRIPTS = new_data[key]
                    elif key == 'weapon_glow':
                        self.effect_catalog.WEAPON_GLOW_INFO = new_data[key]
                    elif key == 'weapon_glow_ids':
                        self.effect_catalog.WEAPON_GLOW_IDS = new_data[key]
                    elif key == 'atk_types':
                        self.effect_catalog.ATK_TYPES = new_data[key]
                    elif key == 'templates':
                        self.effect_catalog.EFFECT_TEMPLATES = new_data[key]

            if self.effect_catalog._save_to_json():
                # 统计导入结果
                counts = {k: len(new_data[k]) if isinstance(new_data[k], list) else 1
                         for k in imported_keys if k in new_data}
                return {"success": True, "message": f"导入成功: {counts}", "imported": counts}
            return {"success": False, "message": "保存到 JSON 文件失败"}
        except Exception as e:
            logger.error(f"导入特效知识库失败: {e}")
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_effect_cross_ref(self, force: bool = False) -> dict:
        """获取特效交叉引用 — 统计每个特效被哪些技能/物品使用
        优先返回缓存，无缓存时扫描并缓存结果
        Args:
            force: 强制重新扫描，忽略缓存
        """
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        # 优先返回缓存（除非强制刷新）
        if not force and self.effect_catalog and self.effect_catalog.has_cross_ref_cache():
            cached = self.effect_catalog.get_cross_ref()
            cached["from_cache"] = True
            return cached
        result = {
            "ball": {},       # {ball_id: [skill_name, ...]}
            "damage": {},     # {damage_id: [skill_name, ...]}
            "atk": {},        # {atk_id: [skill_name, ...]}
            "script_no": {},  # {script_no: [item_name, ...]}
            "bfw_res_id": {}  # {bfw_res_id: [item_name, ...]}
        }
        try:
            # 扫描 BFMagic.ini
            bfmagic_path = os.path.join(self.game_path, "Setting", "BFMagic.ini")
            if os.path.exists(bfmagic_path):
                parser = IniParser()
                parser.load(bfmagic_path)
                for section in parser.sections:
                    name = section.entries.get("Name", f"技能{section.entries.get('No','?')}")
                    ball = section.entries.get("Ball", "")
                    damage = section.entries.get("DamageType", "")
                    atk = section.entries.get("Atk", "")
                    if ball and ball != "0":
                        bid = int(ball)
                        result["ball"].setdefault(bid, []).append(name)
                    if damage and damage != "0":
                        did = int(damage)
                        result["damage"].setdefault(did, []).append(name)
                    if atk and atk != "0":
                        aid = int(atk)
                        result["atk"].setdefault(aid, []).append(name)
            # 扫描 Thing.ini
            thing_path = os.path.join(self.game_path, "Setting", "Thing.ini")
            if os.path.exists(thing_path):
                parser = IniParser()
                parser.load(thing_path)
                for section in parser.sections:
                    ttype = int(section.entries.get("Type", 0))
                    if ttype != 2:  # 只统计武器
                        continue
                    name = section.entries.get("Name", f"物品{section.entries.get('No','?')}")
                    script = section.entries.get("ScriptNo", "")
                    bfw = section.entries.get("BFWResID", "")
                    if script and script != "0":
                        sid = int(script)
                        result["script_no"].setdefault(sid, []).append(name)
                    if bfw and bfw != "0":
                        bid = int(bfw)
                        result["bfw_res_id"].setdefault(bid, []).append(name)
            # 统计计数
            counts = {
                "ball": {str(k): len(v) for k, v in result["ball"].items()},
                "damage": {str(k): len(v) for k, v in result["damage"].items()},
                "atk": {str(k): len(v) for k, v in result["atk"].items()},
                "script_no": {str(k): len(v) for k, v in result["script_no"].items()},
                "bfw_res_id": {str(k): len(v) for k, v in result["bfw_res_id"].items()},
            }
            # 缓存到 effect_catalog
            if self.effect_catalog:
                self.effect_catalog.save_cross_ref(result, counts)
            return {"success": True, "refs": result, "counts": counts, "from_cache": False}
        except Exception as e:
            logger.error(f"特效交叉引用分析失败: {e}")
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_effect_batch_preview(self, field: str, old_value: int, file: str = "bfmagic") -> dict:
        """预览批量修改特效字段的影响范围
        Args:
            field: 'Ball'|'DamageType'|'Element'|'Atk'|'ScriptNo'|'BFWResID'
            old_value: 当前值
            file: 'bfmagic' (技能) 或 'thing' (物品)
        """
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        bf_fields = ('Ball', 'DamageType', 'Element', 'Atk')
        thing_fields = ('ScriptNo', 'BFWResID')
        if field not in bf_fields and field not in thing_fields:
            return {"success": False, "message": f"不支持的字段: {field}"}
        try:
            if file == 'thing':
                ini_path = os.path.join(self.game_path, "Setting", "Thing.ini")
                if not os.path.exists(ini_path):
                    return {"success": False, "message": "Thing.ini 不存在"}
                parser = IniParser()
                parser.load(ini_path)
                affected = []
                old_str = str(old_value)
                for section in parser.sections:
                    ttype = int(section.entries.get("Type", 0))
                    if ttype != 2 and field == 'BFWResID':  # BFWResID 只对武器有意义
                        continue
                    if section.entries.get(field, "") == old_str:
                        no = section.entries.get("No", "?")
                        name = section.entries.get("Name", f"物品{no}")
                        affected.append({"no": no, "name": name, "section": section.name})
                return {"success": True, "affected": affected, "count": len(affected)}
            else:
                ini_path = os.path.join(self.game_path, "Setting", "BFMagic.ini")
                if not os.path.exists(ini_path):
                    return {"success": False, "message": "BFMagic.ini 不存在"}
                parser = IniParser()
                parser.load(ini_path)
                affected = []
                old_str = str(old_value)
                for section in parser.sections:
                    if section.entries.get(field, "") == old_str:
                        no = section.entries.get("No", "?")
                        name = section.entries.get("Name", f"技能{no}")
                        affected.append({"no": no, "name": name, "section": section.name})
                return {"success": True, "affected": affected, "count": len(affected)}
        except Exception as e:
            logger.error(f"批量修改预览失败: {e}")
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_effect_batch_modify(self, field: str, old_value: int, new_value: int, file: str = "bfmagic") -> dict:
        """批量修改技能/物品特效字段
        Args:
            field: 'Ball'|'DamageType'|'Element'|'Atk'|'ScriptNo'|'BFWResID'
            old_value: 当前值（匹配条件）
            new_value: 新值
            file: 'bfmagic' (技能) 或 'thing' (物品)
        """
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        bf_fields = ('Ball', 'DamageType', 'Element', 'Atk')
        thing_fields = ('ScriptNo', 'BFWResID')
        if field not in bf_fields and field not in thing_fields:
            return {"success": False, "message": f"不支持的字段: {field}"}
        try:
            if file == 'thing':
                ini_path = os.path.join(self.game_path, "Setting", "Thing.ini")
                type_label = "物品"
            else:
                ini_path = os.path.join(self.game_path, "Setting", "BFMagic.ini")
                type_label = "技能"
            if not os.path.exists(ini_path):
                return {"success": False, "message": f"{ini_path} 不存在"}
            # 先备份
            if self.backup_mgr:
                self.backup_mgr.backup_all_settings()
            parser = IniParser()
            parser.load(ini_path)
            old_str = str(old_value)
            new_str = str(new_value)
            modified = []
            for section in parser.sections:
                if file == 'thing' and field == 'BFWResID':
                    ttype = int(section.entries.get("Type", 0))
                    if ttype != 2:
                        continue
                if section.entries.get(field, "") == old_str:
                    section.entries[field] = new_str
                    no = section.entries.get("No", "?")
                    name = section.entries.get("Name", f"{type_label}{no}")
                    modified.append({"no": no, "name": name})
            if modified:
                parser.save(ini_path)
            return {"success": True, "modified": modified, "count": len(modified),
                    "message": f"已修改 {len(modified)} 个{type_label}的 {field} 字段: {old_value} → {new_value}"}
        except Exception as e:
            logger.error(f"批量修改特效失败: {e}")
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
