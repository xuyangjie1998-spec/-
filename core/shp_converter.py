"""
SHP头像解码、图片格式转换核心类 (v2.0 - 完整重写)
- 正确解析群7 SHP格式（含文件头）
- 正确加载ACT调色板（256色）
- PNG/JPG/BMP → 群7专用SHP批量转换
- SHP → 通用图片导出
- 武将头像预览渲染
"""

import os
import struct
import base64
import shutil
from io import BytesIO
from typing import Optional, Tuple, List

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# 群7头像标准参数
FACE_SIZE = 128
COLOR_COUNT = 256
FACE_DIR = "Shape/Face"


class ShpConverter:
    """
    群7 SHP头像格式转换器 (v2.0)
    
    游戏头像格式：
    - 文件头: 4字节 (uint16 width, uint16 height) 或 8字节 (uint32 magic, uint16 w, uint16 h)
    - 像素数据: width*height 字节，每字节为256色调色板索引
    - 调色板: 外部 .act 文件 (256色 × 3字节 RGB = 768字节)
    """

    # 已知的SHP魔数签名
    SHP_MAGIC_V1 = 0x00000001  # 变体1: 4字节 magic + 4字节 header
    SHP_MAGIC_V2 = 0x53485001  # 变体2: "SHP\1"

    def __init__(self, game_path: str = None):
        self.game_path = game_path
        self.face_root = os.path.join(game_path, FACE_DIR) if game_path else ""
        self.palette = self._load_standard_palette()
        self._conversion_log: list = []

    def _load_standard_palette(self) -> Optional[List[int]]:
        """加载内置256色游戏调色板（ACT格式：768字节原始RGB数据）"""
        if not HAS_PIL:
            return None

        pal_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "color_palette.act")
        if os.path.exists(pal_path):
            try:
                with open(pal_path, "rb") as f:
                    raw = f.read()
                if len(raw) >= 768:
                    # ACT格式: 256色 × 3字节RGB = 768字节
                    palette = list(raw[:768])
                    return palette
            except (IndexError, struct.error, IOError, OSError):
                pass  # 调色板加载失败，使用默认

        # 使用默认调色板
        return self._generate_default_palette()

    def _generate_default_palette(self) -> List[int]:
        """生成默认256色调色板"""
        palette = []
        for r_step in range(8):
            for g_step in range(8):
                for b_step in range(4):
                    palette.extend([
                        int(r_step * 255 / 7),
                        int(g_step * 255 / 7),
                        int(b_step * 255 / 3),
                    ])
        while len(palette) < 768:
            palette.extend([0, 0, 0])
        return palette[:768]

    def set_game_path(self, game_path: str):
        self.game_path = game_path
        self.face_root = os.path.join(game_path, FACE_DIR)

    def _check_pil(self):
        if not HAS_PIL:
            raise ImportError("Pillow库未安装，请运行: pip install Pillow")

    def _detect_shp_format(self, data: bytes) -> Tuple[int, int, int]:
        """
        检测SHP文件格式，返回 (width, height, header_offset)
        
        支持的格式:
        1. 无头格式: 数据 = 128*128字节纯像素 (header_offset=0)
        2. 4字节头: uint16 width, uint16 height (header_offset=4)
        3. 8字节头: uint32 magic, uint16 width, uint16 height (header_offset=8)
        """
        total = len(data)

        # 尝试解析8字节头
        if total >= 8:
            magic, w, h = struct.unpack("<IHH", data[:8])
            if magic in (self.SHP_MAGIC_V1, self.SHP_MAGIC_V2):
                if w > 0 and h > 0 and w <= 1024 and h <= 1024:
                    if total >= 8 + w * h:
                        return w, h, 8

        # 尝试解析4字节头
        if total >= 4:
            w, h = struct.unpack("<HH", data[:4])
            if w > 0 and h > 0 and w <= 1024 and h <= 1024:
                if total >= 4 + w * h:
                    return w, h, 4

        # 无头格式：假设128×128
        if total >= FACE_SIZE * FACE_SIZE:
            return FACE_SIZE, FACE_SIZE, 0

        # 最后尝试：计算可能的宽高
        pixel_count = total
        # 尝试找最接近128×128的
        for size in [128, 64, 256, 96, 48]:
            if pixel_count >= size * size:
                return size, size, 0

        return FACE_SIZE, FACE_SIZE, 0  # 回退

    def face_exists(self, face_id: int) -> bool:
        if not self.face_root:
            return False
        filename = f"{face_id:04d}.shp"
        return os.path.exists(os.path.join(self.face_root, filename))

    def load_shp_by_id(self, face_id: int) -> Optional[Image.Image]:
        """根据编号读取SHP，解码为PIL图片"""
        self._check_pil()
        if not self.face_root:
            return self._create_placeholder("请先设置游戏目录")

        filename = f"{face_id:04d}.shp"
        shp_path = os.path.join(self.face_root, filename)

        if not os.path.exists(shp_path):
            return self._create_placeholder(f"头像 {face_id:04d}.shp 不存在")

        try:
            return self._decode_shp_file(shp_path)
        except Exception as e:
            self._log(f"加载头像 {face_id:04d} 失败: {e}")
            return self._create_placeholder(f"解码失败: {str(e)[:30]}")

    def _decode_shp_file(self, shp_path: str) -> Image.Image:
        """解码单个SHP文件"""
        with open(shp_path, "rb") as f:
            data = f.read()
        return self.decode_shp_bytes(data)

    def decode_shp_bytes(self, data: bytes) -> Optional[Image.Image]:
        """从原始字节数据解码SHP图片（无需文件路径）"""
        self._check_pil()
        width, height, header_offset = self._detect_shp_format(data)
        pixel_data = data[header_offset:header_offset + width * height]

        if len(pixel_data) < width * height:
            return self._create_placeholder("文件数据不完整")

        img = Image.new("P", (width, height))
        if self.palette:
            img.putpalette(self.palette)
        img.putdata(list(pixel_data))

        return img.convert("RGB")

    def load_shp_base64(self, face_id: int) -> str:
        """读取SHP并返回base64编码的PNG数据"""
        img = self.load_shp_by_id(face_id)
        if img is None:
            return ""

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64_data}"

    def image_to_shp(self, src_img_path: str, output_face_id: int, output_dir: str = None) -> str:
        """
        通用图片(JPG/PNG/BMP)转游戏标准SHP
        输出格式: 8字节文件头 + 像素索引数据
        output_dir: 可选，指定输出目录（默认 face_root，可传 BFObj 路径）
        """
        self._check_pil()
        if not self.game_path:
            raise ValueError("请先设置游戏目录")
        dest_dir = output_dir if output_dir else self.face_root
        if not dest_dir:
            raise ValueError("未指定输出目录")

        self._log(f"开始转换图片: {src_img_path} -> 编号 {output_face_id:04d} -> {dest_dir}")

        img = Image.open(src_img_path).convert("RGB")
        orig_size = img.size
        self._log(f"原始尺寸: {orig_size[0]}x{orig_size[1]}")

        if img.size != (FACE_SIZE, FACE_SIZE):
            img = img.resize((FACE_SIZE, FACE_SIZE), Image.Resampling.LANCZOS)
            self._log(f"已缩放至: {FACE_SIZE}x{FACE_SIZE}")

        # 转为256索引色
        pal_img = Image.new("P", (1, 1))
        if self.palette:
            pal_img.putpalette(self.palette)
        img_p = img.quantize(colors=COLOR_COUNT, palette=pal_img, dither=Image.Dither.FLOYDSTEINBERG)
        self._log("已转换为256色索引调色板模式")

        pixels = list(img_p.getdata())

        out_name = f"{output_face_id:04d}.shp"
        out_path = os.path.join(dest_dir, out_name)

        if os.path.exists(out_path):
            backup_name = f"{output_face_id:04d}_backup_{int(os.path.getmtime(out_path))}.shp"
            backup_path = os.path.join(dest_dir, backup_name)
            os.rename(out_path, backup_path)
            self._log(f"已备份原头像: {backup_name}")

        # 写入标准SHP格式: 8字节头 + 像素数据
        with open(out_path, "wb") as f:
            # 文件头: magic(uint32) + width(uint16) + height(uint16)
            f.write(struct.pack("<IHH", self.SHP_MAGIC_V1, FACE_SIZE, FACE_SIZE))
            # 像素数据: 128*128 = 16384 字节索引
            f.write(struct.pack(f"{FACE_SIZE * FACE_SIZE}B", *pixels))

        self._log(f"转换完成: {out_path}")
        return out_path

    def shp_to_png(self, face_id: int, save_path: str) -> str:
        """SHP导出为通用PNG图片"""
        self._check_pil()
        img = self.load_shp_by_id(face_id)
        if img is None:
            raise ValueError(f"无法读取头像 {face_id:04d}")

        if not save_path.lower().endswith(".png"):
            save_path += ".png"

        img.save(save_path, "PNG")
        self._log(f"头像导出: {face_id:04d} -> {save_path}")
        return save_path

    def batch_convert_to_shp(self, image_files: list, start_id: int = None) -> list:
        """批量转换图片为SHP"""
        results = []
        for i, img_path in enumerate(image_files):
            try:
                face_id = (start_id + i) if start_id else self._find_free_id()
                out = self.image_to_shp(img_path, face_id)
                results.append({"success": True, "face_id": face_id, "path": out})
            except Exception as e:
                results.append({"success": False, "path": img_path, "error": str(e)})
        return results

    def _find_free_id(self, start: int = 1, end: int = 9999) -> int:
        if not self.face_root:
            return start
        for i in range(start, end + 1):
            if not self.face_exists(i):
                return i
        raise ValueError("头像编号已满（1-9999全部占用）")

    def _create_placeholder(self, message: str = "") -> Image.Image:
        img = Image.new("RGB", (FACE_SIZE, FACE_SIZE), (40, 40, 40))
        if not HAS_PIL:
            return img
        try:
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(img)
            draw.rectangle([0, 0, FACE_SIZE - 1, FACE_SIZE - 1], outline=(100, 100, 100))
            text = message or "无头像"
            bbox = draw.textbbox((0, 0), text)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text(((FACE_SIZE - tw) // 2, (FACE_SIZE - th) // 2), text, fill=(180, 180, 180))
        except (ValueError, TypeError, AttributeError):
            pass  # 占位文字绘制失败，返回空白头像
        return img

    def _log(self, message: str):
        self._conversion_log.append(message)

    def get_log(self) -> list:
        return self._conversion_log

    def clear_log(self):
        self._conversion_log.clear()

    # ============================================================
    # 批量管理
    # ============================================================

    def list_faces(self, start: int = 1, end: int = 100) -> list:
        """列出指定范围内的头像文件"""
        if not self.face_root or not os.path.exists(self.face_root):
            return []
        faces = []
        for i in range(start, end + 1):
            fname = f"{i:04d}.shp"
            fpath = os.path.join(self.face_root, fname)
            if os.path.exists(fpath):
                faces.append({
                    "id": i,
                    "name": fname,
                    "size": os.path.getsize(fpath),
                    "exists": True,
                })
        return faces

    def batch_preview(self, start: int, count: int = 50) -> dict:
        """批量预览头像（返回base64缩略图列表）"""
        if not HAS_PIL:
            return {"success": False, "message": "PIL库不可用"}
        if not self.face_root:
            return {"success": False, "message": "未配置游戏目录"}

        previews = []
        found = 0
        total = 0
        for i in range(start, start + count):
            total += 1
            try:
                fname = f"{i:04d}.shp"
                fpath = os.path.join(self.face_root, fname)
                if not os.path.exists(fpath):
                    continue
                found += 1
                img = self.load_shp_by_id(i)
                if img:
                    # 生成缩略图
                    thumb = img.copy()
                    thumb.thumbnail((64, 64))
                    buf = BytesIO()
                    thumb.save(buf, format="PNG")
                    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                    previews.append({
                        "id": i,
                        "name": fname,
                        "size": os.path.getsize(fpath),
                        "base64": "data:image/png;base64," + b64,
                    })
            except (IOError, OSError, ValueError):
                pass

        return {
            "success": True,
            "previews": previews,
            "total_scanned": total,
            "total_found": found,
            "start": start,
            "range": count,
        }

    def batch_delete(self, face_ids: list) -> dict:
        """批量删除头像"""
        if not self.face_root:
            return {"success": False, "message": "未配置游戏目录"}

        deleted = []
        failed = []
        for fid in face_ids:
            try:
                fname = f"{fid:04d}.shp"
                fpath = os.path.join(self.face_root, fname)
                if os.path.exists(fpath):
                    # 备份
                    backup_path = fpath + ".bak"
                    if not os.path.exists(backup_path):
                        shutil.copy2(fpath, backup_path)
                    os.remove(fpath)
                    deleted.append(fid)
                else:
                    failed.append({"id": fid, "reason": "文件不存在"})
            except Exception as e:
                failed.append({"id": fid, "reason": str(e)})

        return {
            "success": True,
            "deleted": deleted,
            "failed": failed,
            "count": len(deleted),
        }

    def batch_export(self, face_ids: list, output_dir: str) -> dict:
        """批量导出头像为PNG"""
        if not HAS_PIL:
            return {"success": False, "message": "PIL库不可用"}
        if not self.face_root:
            return {"success": False, "message": "未配置游戏目录"}

        os.makedirs(output_dir, exist_ok=True)
        exported = []
        failed = []
        for fid in face_ids:
            try:
                fname = f"{fid:04d}.shp"
                fpath = os.path.join(self.face_root, fname)
                if not os.path.exists(fpath):
                    failed.append({"id": fid, "reason": "文件不存在"})
                    continue
                img = self.load_shp_by_id(fid)
                if img:
                    out_path = os.path.join(output_dir, f"{fid:04d}.png")
                    img.save(out_path, "PNG")
                    exported.append({"id": fid, "path": out_path})
                else:
                    failed.append({"id": fid, "reason": "解码失败"})
            except Exception as e:
                failed.append({"id": fid, "reason": str(e)})

        return {
            "success": True,
            "exported": exported,
            "failed": failed,
            "count": len(exported),
        }

    def get_face_stats(self) -> dict:
        """获取头像统计信息"""
        if not self.face_root or not os.path.exists(self.face_root):
            return {"success": False, "message": "未配置游戏目录", "total": 0}

        files = [f for f in os.listdir(self.face_root) if f.endswith('.shp')]
        total_size = sum(os.path.getsize(os.path.join(self.face_root, f)) for f in files)
        ids = []
        for f in files:
            try:
                ids.append(int(f.replace('.shp', '')))
            except ValueError:
                pass

        return {
            "success": True,
            "total": len(files),
            "total_size": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "min_id": min(ids) if ids else 0,
            "max_id": max(ids) if ids else 0,
        }

    def list_bfobj_shps(self) -> dict:
        """列出 Shape/BFObj/ 目录下的兵种模型 SHP 文件"""
        if not self.game_path:
            return {"success": False, "message": "未配置游戏目录", "files": []}

        bfobj_dir = os.path.join(self.game_path, "Shape", "BFObj")
        if not os.path.exists(bfobj_dir):
            return {"success": True, "files": [], "message": "BFObj 目录不存在"}

        files = []
        for root, _, fnames in os.walk(bfobj_dir):
            for f in sorted(fnames):
                if f.lower().endswith(".shp"):
                    fpath = os.path.join(root, f)
                    rel = os.path.relpath(fpath, bfobj_dir)
                    files.append({
                        "name": f,
                        "path": rel,
                        "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                    })

        return {"success": True, "files": files, "count": len(files), "dir": bfobj_dir}

    def preview_bfobj_shp(self, rel_path: str) -> dict:
        """预览 BFObj 目录下的 SHP 文件（返回 base64 PNG）"""
        if not HAS_PIL:
            return {"success": False, "message": "PIL库不可用"}
        if not self.game_path:
            return {"success": False, "message": "未配置游戏目录"}

        bfobj_dir = os.path.join(self.game_path, "Shape", "BFObj")
        safe_path = os.path.normpath(os.path.join(bfobj_dir, rel_path))
        if not safe_path.startswith(bfobj_dir) or not os.path.exists(safe_path):
            return {"success": False, "message": "文件不存在或路径无效"}

        try:
            img = self._load_shp_file(safe_path)
            if img:
                buf = BytesIO()
                img.save(buf, "PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                return {"success": True, "image_base64": b64, "size": f"{img.width}x{img.height}"}
            return {"success": False, "message": "解析失败"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _load_shp_file(self, filepath: str):
        """加载单个 SHP 文件为 PIL Image（内部方法）"""
        if not HAS_PIL:
            return None
        try:
            return self._decode_shp_file(filepath)
        except (IOError, OSError):
            return None

    @staticmethod
    def get_info() -> dict:
        return {
            "face_size": FACE_SIZE,
            "color_count": COLOR_COUNT,
            "format": "SHP (群7专用二进制封装 v2.0)",
            "header": "8字节 (magic:uint32 + width:uint16 + height:uint16)",
            "supported_input": ["PNG", "JPG", "BMP", "GIF"],
            "supported_output": ["SHP", "PNG"],
            "pil_available": HAS_PIL,
        }