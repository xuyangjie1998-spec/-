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
FACE_DIR = "Shape/GenFace"

# 物品图标参数
THING_ICON_SIZE = 64
THING_ICON_DIR = "Shape/ThingIcon"


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

    def load_shp_file_base64(self, filepath: str) -> str:
        """从文件路径读取SHP并返回base64编码的PNG数据"""
        if not os.path.exists(filepath):
            return ""
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            # 解析SHP
            w, h, header_size = self._detect_shp_size(data)
            pixel_data = self._decode_shp_pixels(data, header_size, w, h)
            img = Image.new("RGB", (w, h))
            img.putdata(list(pixel_data))
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return f"data:image/png;base64,{b64_data}"
        except Exception:
            return ""

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

    def get_pixel_data(self, shp_path: str) -> dict:
        """获取SHP文件的原始像素数据和调色板，用于像素编辑器"""
        self._check_pil()
        if not os.path.exists(shp_path):
            raise FileNotFoundError(f"SHP文件不存在: {shp_path}")

        with open(shp_path, "rb") as f:
            data = f.read()

        width, height, header_offset = self._detect_shp_format(data)
        pixel_data = data[header_offset:header_offset + width * height]

        if len(pixel_data) < width * height:
            raise ValueError("文件数据不完整")

        pixels = list(pixel_data)

        # 调色板转为RGB三元组列表
        palette_rgb = []
        if self.palette:
            for i in range(0, min(len(self.palette), 768), 3):
                palette_rgb.append([self.palette[i], self.palette[i+1], self.palette[i+2]])

        return {
            "width": width,
            "height": height,
            "header_offset": header_offset,
            "pixels": pixels,
            "palette": palette_rgb,
            "total_colors": len(palette_rgb),
            "file_size": len(data),
        }

    def save_pixel_data(self, shp_path: str, pixels: list, width: int = None, height: int = None) -> str:
        """将修改后的像素数据保存回SHP文件（自动备份原文件）"""
        self._check_pil()
        if not os.path.exists(shp_path):
            raise FileNotFoundError(f"SHP文件不存在: {shp_path}")

        # 自动备份
        backup_path = shp_path + ".bak"
        if not os.path.exists(backup_path):
            shutil.copy2(shp_path, backup_path)

        # 读取原始文件获取header信息
        with open(shp_path, "rb") as f:
            original_data = f.read()

        w, h, header_offset = self._detect_shp_format(original_data)
        if width:
            w = width
        if height:
            h = height

        # 截断/填充像素数据到正确长度
        expected_len = w * h
        if len(pixels) > expected_len:
            pixels = pixels[:expected_len]
        elif len(pixels) < expected_len:
            pixels = list(pixels) + [0] * (expected_len - len(pixels))

        # 写入SHP
        with open(shp_path, "wb") as f:
            if header_offset > 0:
                # 保留原始header
                f.write(original_data[:header_offset])
            else:
                # 写入新header
                f.write(struct.pack("<IHH", self.SHP_MAGIC_V1, w, h))
            f.write(struct.pack(f"{expected_len}B", *[int(p) & 0xFF for p in pixels]))

        return shp_path

    def get_palette_rgb(self) -> list:
        """获取调色板RGB列表"""
        palette_rgb = []
        if self.palette:
            for i in range(0, min(len(self.palette), 768), 3):
                palette_rgb.append([self.palette[i], self.palette[i+1], self.palette[i+2]])
        return palette_rgb

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

    # ============================================================
    # V3.11.0: SHP 批量处理流水线 — 尺寸标准化 / 调色板重映射 / 序列帧导入
    # ============================================================

    def analyze_shp_directory(self, directory: str = None) -> dict:
        """
        分析目录中所有 SHP 文件的尺寸分布和格式信息

        返回每个 SHP 文件的宽高、文件大小、格式变体，以及汇总统计
        """
        target_dir = directory if directory else self.face_root
        if not target_dir or not os.path.isdir(target_dir):
            return {"success": False, "message": "目录不存在或未配置", "files": []}

        files_info = []
        size_distribution = {}
        format_distribution = {}

        for fname in sorted(os.listdir(target_dir)):
            if not fname.lower().endswith(".shp"):
                continue
            fpath = os.path.join(target_dir, fname)
            try:
                with open(fpath, "rb") as f:
                    data = f.read()
                w, h, header_offset = self._detect_shp_format(data)
                file_size = len(data)

                # 格式分类
                if header_offset == 8:
                    fmt_type = "8字节头"
                elif header_offset == 4:
                    fmt_type = "4字节头"
                else:
                    fmt_type = "无头"

                size_key = f"{w}x{h}"
                size_distribution[size_key] = size_distribution.get(size_key, 0) + 1
                format_distribution[fmt_type] = format_distribution.get(fmt_type, 0) + 1

                files_info.append({
                    "name": fname,
                    "path": fpath,
                    "width": w,
                    "height": h,
                    "format": fmt_type,
                    "header_offset": header_offset,
                    "file_size": file_size,
                    "pixel_count": w * h,
                })
            except (IOError, OSError, struct.error):
                files_info.append({"name": fname, "path": fpath, "error": "读取失败"})

        # 判断是否统一尺寸
        is_uniform = len(size_distribution) <= 1
        dominant_size = max(size_distribution, key=size_distribution.get) if size_distribution else "N/A"

        return {
            "success": True,
            "directory": target_dir,
            "total_files": len(files_info),
            "is_uniform_size": is_uniform,
            "dominant_size": dominant_size,
            "size_distribution": size_distribution,
            "format_distribution": format_distribution,
            "files": files_info,
            "summary": f"共 {len(files_info)} 个SHP文件，{'统一尺寸 ' + dominant_size if is_uniform else '存在 ' + str(len(size_distribution)) + ' 种不同尺寸'}",
        }

    def batch_standardize_size(self, target_width: int = FACE_SIZE, target_height: int = FACE_SIZE,
                                directory: str = None, backup: bool = True) -> dict:
        """
        批量将目录中所有 SHP 文件标准化到统一尺寸

        对于非目标尺寸的 SHP，居中缩放后裁剪/填充到目标尺寸
        """
        if not HAS_PIL:
            return {"success": False, "message": "PIL库不可用，请安装: pip install Pillow"}

        target_dir = directory if directory else self.face_root
        if not target_dir or not os.path.isdir(target_dir):
            return {"success": False, "message": "目录不存在或未配置"}

        analysis = self.analyze_shp_directory(target_dir)
        if not analysis.get("success"):
            return analysis

        standardized = []
        skipped = []
        failed = []
        backup_dir = os.path.join(target_dir, "_backup") if backup else None

        if backup and not os.path.exists(backup_dir):
            os.makedirs(backup_dir, exist_ok=True)

        for finfo in analysis["files"]:
            if "error" in finfo:
                failed.append({"name": finfo["name"], "reason": finfo["error"]})
                continue

            if finfo["width"] == target_width and finfo["height"] == target_height:
                skipped.append({"name": finfo["name"], "size": f"{finfo['width']}x{finfo['height']}"})
                continue

            try:
                fpath = finfo["path"]

                # 备份原文件
                if backup and backup_dir:
                    shutil.copy2(fpath, os.path.join(backup_dir, finfo["name"]))

                # 解码原 SHP
                img = self._decode_shp_file(fpath)

                # 缩放并居中裁剪
                # 先等比缩放使长边对齐目标尺寸
                orig_w, orig_h = img.size
                scale = min(target_width / orig_w, target_height / orig_h)
                new_w = int(orig_w * scale)
                new_h = int(orig_h * scale)
                img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                # 居中放置到目标画布
                canvas = Image.new("RGB", (target_width, target_height), (0, 0, 0))
                paste_x = (target_width - new_w) // 2
                paste_y = (target_height - new_h) // 2
                canvas.paste(img_resized, (paste_x, paste_y))

                # 转换为 256 索引色
                pal_img = Image.new("P", (1, 1))
                if self.palette:
                    pal_img.putpalette(self.palette)
                img_p = canvas.quantize(colors=COLOR_COUNT, palette=pal_img, dither=Image.Dither.FLOYDSTEINBERG)
                pixels = list(img_p.getdata())

                # 写入标准 SHP
                with open(fpath, "wb") as f:
                    f.write(struct.pack("<IHH", self.SHP_MAGIC_V1, target_width, target_height))
                    f.write(struct.pack(f"{target_width * target_height}B", *pixels))

                standardized.append({
                    "name": finfo["name"],
                    "old_size": f"{finfo['width']}x{finfo['height']}",
                    "new_size": f"{target_width}x{target_height}",
                })
                self._log(f"尺寸标准化: {finfo['name']} ({finfo['width']}x{finfo['height']}) -> ({target_width}x{target_height})")
            except Exception as e:
                failed.append({"name": finfo["name"], "reason": str(e)})

        return {
            "success": True,
            "target_size": f"{target_width}x{target_height}",
            "directory": target_dir,
            "standardized": standardized,
            "standardized_count": len(standardized),
            "skipped": skipped,
            "skipped_count": len(skipped),
            "failed": failed,
            "failed_count": len(failed),
            "backup_dir": backup_dir if backup else None,
            "summary": f"标准化 {len(standardized)} 个文件到 {target_width}x{target_height}，跳过 {len(skipped)} 个，失败 {len(failed)} 个",
        }

    def remap_palette(self, shp_path: str, target_palette: List[int] = None,
                       output_path: str = None, backup: bool = True) -> dict:
        """
        将单个 SHP 文件的调色板重映射到目标调色板

        通过计算每个像素索引在原调色板中的 RGB 值，在目标调色板中找最接近的颜色索引
        用于统一不同来源 SHP 的调色板
        """
        if not HAS_PIL:
            return {"success": False, "message": "PIL库不可用，请安装: pip install Pillow"}

        if not os.path.exists(shp_path):
            return {"success": False, "message": f"SHP 文件不存在: {shp_path}"}

        tgt_pal = target_palette if target_palette else self.palette
        if not tgt_pal or len(tgt_pal) < 768:
            return {"success": False, "message": "目标调色板无效（需要至少 768 字节）"}

        out_path = output_path if output_path else shp_path

        try:
            # 备份
            if backup and out_path == shp_path:
                backup_path = shp_path + ".pal_bak"
                if not os.path.exists(backup_path):
                    shutil.copy2(shp_path, backup_path)

            # 解码原 SHP
            img = self._decode_shp_file(shp_path)

            # 量化到目标调色板
            pal_img = Image.new("P", (1, 1))
            pal_img.putpalette(tgt_pal)
            img_p = img.quantize(colors=COLOR_COUNT, palette=pal_img, dither=Image.Dither.FLOYDSTEINBERG)
            pixels = list(img_p.getdata())

            w, h = img.size

            # 写入
            with open(out_path, "wb") as f:
                f.write(struct.pack("<IHH", self.SHP_MAGIC_V1, w, h))
                f.write(struct.pack(f"{w * h}B", *pixels))

            self._log(f"调色板重映射: {os.path.basename(shp_path)} ({w}x{h})")
            return {
                "success": True,
                "file": os.path.basename(shp_path),
                "size": f"{w}x{h}",
                "output": out_path,
                "pixel_count": w * h,
            }
        except Exception as e:
            return {"success": False, "message": f"重映射失败: {str(e)}", "file": os.path.basename(shp_path)}

    def batch_remap_palette(self, directory: str = None, target_palette: List[int] = None,
                             backup: bool = True) -> dict:
        """
        批量将目录中所有 SHP 文件重映射到目标调色板

        适用于从其他来源导入的 SHP，统一为游戏调色板
        """
        target_dir = directory if directory else self.face_root
        if not target_dir or not os.path.isdir(target_dir):
            return {"success": False, "message": "目录不存在或未配置"}

        if not HAS_PIL:
            return {"success": False, "message": "PIL库不可用，请安装: pip install Pillow"}

        shp_files = [f for f in os.listdir(target_dir) if f.lower().endswith(".shp")]
        if not shp_files:
            return {"success": True, "message": "目录中没有 SHP 文件", "remapped": [], "remapped_count": 0}

        remapped = []
        failed = []

        for fname in sorted(shp_files):
            fpath = os.path.join(target_dir, fname)
            result = self.remap_palette(fpath, target_palette=target_palette, backup=backup)
            if result["success"]:
                remapped.append(result)
            else:
                failed.append(result)

        return {
            "success": True,
            "directory": target_dir,
            "remapped": remapped,
            "remapped_count": len(remapped),
            "failed": failed,
            "failed_count": len(failed),
            "summary": f"重映射 {len(remapped)} 个文件，失败 {len(failed)} 个",
        }

    def import_sequence_frames(self, frames_dir: str, output_dir: str = None,
                                start_id: int = None, target_width: int = None,
                                target_height: int = None, file_pattern: str = None) -> dict:
        """
        从序列帧图片目录批量导入 SHP

        支持:
        - 自动检测图片序号（从文件名中提取数字）
        - 自动缩放/裁剪到目标尺寸
        - 统一调色板量化

        参数:
            frames_dir: 序列帧图片目录
            output_dir: 输出目录（默认 face_root）
            start_id: 起始编号（默认自动检测）
            target_width: 目标宽度（默认 FACE_SIZE）
            target_height: 目标高度（默认 FACE_SIZE）
            file_pattern: 文件名匹配模式（如 "frame_*.png"，默认匹配所有图片）
        """
        if not HAS_PIL:
            return {"success": False, "message": "PIL库不可用，请安装: pip install Pillow"}

        if not os.path.isdir(frames_dir):
            return {"success": False, "message": f"序列帧目录不存在: {frames_dir}"}

        dest_dir = output_dir if output_dir else self.face_root
        if not dest_dir:
            return {"success": False, "message": "未指定输出目录"}

        os.makedirs(dest_dir, exist_ok=True)

        tgt_w = target_width if target_width else FACE_SIZE
        tgt_h = target_height if target_height else FACE_SIZE

        # 收集所有图片文件
        img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"}
        all_images = []

        if file_pattern:
            import fnmatch
            for fname in sorted(os.listdir(frames_dir)):
                if fnmatch.fnmatch(fname.lower(), file_pattern.lower()):
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in img_exts:
                        all_images.append(fname)
        else:
            for fname in sorted(os.listdir(frames_dir)):
                ext = os.path.splitext(fname)[1].lower()
                if ext in img_exts:
                    all_images.append(fname)

        if not all_images:
            return {"success": False, "message": f"目录中没有匹配的图片文件: {frames_dir}"}

        # 提取数字序号用于排序
        def extract_number(filename):
            import re
            nums = re.findall(r'\d+', filename)
            return int(nums[-1]) if nums else 0

        all_images.sort(key=extract_number)

        imported = []
        failed = []

        # 确定起始编号
        if start_id is None:
            # 从文件名中提取最小序号
            first_num = extract_number(all_images[0]) if all_images else 1
            start_id = first_num if first_num > 0 else 1

        for i, fname in enumerate(all_images):
            try:
                face_id = start_id + i
                fpath = os.path.join(frames_dir, fname)

                # 打开图片
                img = Image.open(fpath).convert("RGB")

                # 等比缩放并居中裁剪
                orig_w, orig_h = img.size
                scale = min(tgt_w / orig_w, tgt_h / orig_h)
                new_w = int(orig_w * scale)
                new_h = int(orig_h * scale)
                img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                canvas = Image.new("RGB", (tgt_w, tgt_h), (0, 0, 0))
                paste_x = (tgt_w - new_w) // 2
                paste_y = (tgt_h - new_h) // 2
                canvas.paste(img_resized, (paste_x, paste_y))

                # 量化到游戏调色板
                pal_img = Image.new("P", (1, 1))
                if self.palette:
                    pal_img.putpalette(self.palette)
                img_p = canvas.quantize(colors=COLOR_COUNT, palette=pal_img, dither=Image.Dither.FLOYDSTEINBERG)
                pixels = list(img_p.getdata())

                # 写入 SHP
                out_name = f"{face_id:04d}.shp"
                out_path = os.path.join(dest_dir, out_name)

                if os.path.exists(out_path):
                    backup_name = f"{face_id:04d}_backup_{int(os.path.getmtime(out_path))}.shp"
                    os.rename(out_path, os.path.join(dest_dir, backup_name))
                    self._log(f"已备份: {backup_name}")

                with open(out_path, "wb") as f:
                    f.write(struct.pack("<IHH", self.SHP_MAGIC_V1, tgt_w, tgt_h))
                    f.write(struct.pack(f"{tgt_w * tgt_h}B", *pixels))

                imported.append({
                    "face_id": face_id,
                    "source": fname,
                    "output": out_name,
                    "original_size": f"{orig_w}x{orig_h}",
                })
                self._log(f"序列帧导入: {fname} -> {out_name} (ID={face_id})")
            except Exception as e:
                failed.append({"source": fname, "reason": str(e)})

        return {
            "success": True,
            "frames_dir": frames_dir,
            "output_dir": dest_dir,
            "target_size": f"{tgt_w}x{tgt_h}",
            "imported": imported,
            "imported_count": len(imported),
            "failed": failed,
            "failed_count": len(failed),
            "total_frames": len(all_images),
            "start_id": start_id,
            "end_id": start_id + len(imported) - 1 if imported else start_id,
            "summary": f"成功导入 {len(imported)}/{len(all_images)} 个序列帧，编号 {start_id}-{start_id + len(imported) - 1 if imported else 'N/A'}",
        }

    def batch_resize_shp(self, target_width: int, target_height: int,
                          directory: str = None, backup: bool = True) -> dict:
        """
        批量将目录中所有 SHP 文件缩放到指定尺寸

        与 batch_standardize_size 的区别：此方法直接拉伸缩放，不保持比例
        适用于需要精确像素尺寸的批量处理
        """
        if not HAS_PIL:
            return {"success": False, "message": "PIL库不可用，请安装: pip install Pillow"}

        target_dir = directory if directory else self.face_root
        if not target_dir or not os.path.isdir(target_dir):
            return {"success": False, "message": "目录不存在或未配置"}

        shp_files = [f for f in os.listdir(target_dir) if f.lower().endswith(".shp")]
        if not shp_files:
            return {"success": True, "message": "目录中没有 SHP 文件", "resized": [], "resized_count": 0}

        resized = []
        failed = []
        backup_dir = os.path.join(target_dir, "_backup_resize") if backup else None

        if backup and not os.path.exists(backup_dir):
            os.makedirs(backup_dir, exist_ok=True)

        for fname in sorted(shp_files):
            fpath = os.path.join(target_dir, fname)
            try:
                # 备份
                if backup and backup_dir:
                    shutil.copy2(fpath, os.path.join(backup_dir, fname))

                # 解码
                img = self._decode_shp_file(fpath)
                orig_w, orig_h = img.size

                if orig_w == target_width and orig_h == target_height:
                    resized.append({
                        "name": fname,
                        "old_size": f"{orig_w}x{orig_h}",
                        "new_size": f"{target_width}x{target_height}",
                        "skipped": True,
                    })
                    continue

                # 直接缩放
                img_resized = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

                # 量化
                pal_img = Image.new("P", (1, 1))
                if self.palette:
                    pal_img.putpalette(self.palette)
                img_p = img_resized.quantize(colors=COLOR_COUNT, palette=pal_img, dither=Image.Dither.FLOYDSTEINBERG)
                pixels = list(img_p.getdata())

                with open(fpath, "wb") as f:
                    f.write(struct.pack("<IHH", self.SHP_MAGIC_V1, target_width, target_height))
                    f.write(struct.pack(f"{target_width * target_height}B", *pixels))

                resized.append({
                    "name": fname,
                    "old_size": f"{orig_w}x{orig_h}",
                    "new_size": f"{target_width}x{target_height}",
                })
                self._log(f"缩放: {fname} ({orig_w}x{orig_h}) -> ({target_width}x{target_height})")
            except Exception as e:
                failed.append({"name": fname, "reason": str(e)})

        return {
            "success": True,
            "target_size": f"{target_width}x{target_height}",
            "directory": target_dir,
            "resized": resized,
            "resized_count": len(resized),
            "failed": failed,
            "failed_count": len(failed),
            "backup_dir": backup_dir if backup else None,
            "summary": f"缩放 {len(resized)} 个文件到 {target_width}x{target_height}，失败 {len(failed)} 个",
        }

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