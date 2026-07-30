import os, json, re, shutil, base64, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional
from core.error_codes import ErrorCode, safe_error_message, error_response, success_response

from core.config import WRITE_ROOT, PROJECT_ROOT

from core.ini_parser import IniParser

from core.event_templates import EVENT_TEMPLATES, generate_event_section

logger = logging.getLogger('San7ModMaker')

__all__ = ['San7ModMakerAdvanced']

__all__ = ['San7ModMakerMap']

class San7ModMakerMap:
    """MOD制作器 - 地图编辑 (区块/PCK/地形/Shape位移/城池连接/id.ini)"""

    # ============================================================
    # API: 区块定位计算器
    # ============================================================
    # 游戏大地图尺寸常量
    MAP_WIDTH = 17472
    MAP_HEIGHT = 12384
    BLOCK_SIZE = 32
    GRID_COLS = MAP_WIDTH // BLOCK_SIZE  # 546
    GRID_ROWS = MAP_HEIGHT // BLOCK_SIZE  # 387

    def api_block_calc(self, x: int, y: int) -> dict:
        """坐标→区块号转换"""
        if x < 0 or x >= self.MAP_WIDTH or y < 0 or y >= self.MAP_HEIGHT:
            return error_response(ErrorCode.INVALID_PARAM, f"坐标超出范围 (0~{self.MAP_WIDTH-1}, 0~{self.MAP_HEIGHT-1})")
        gx = x // self.BLOCK_SIZE
        gy = y // self.BLOCK_SIZE
        block_no = gy * self.GRID_COLS + gx
        return {"success": True, "x": x, "y": y, "grid_x": gx, "grid_y": gy,
                "block_no": block_no, "block_size": self.BLOCK_SIZE,
                "grid_cols": self.GRID_COLS, "grid_rows": self.GRID_ROWS}

    def api_block_inverse(self, block_no: int) -> dict:
        """区块号→坐标范围转换"""
        if block_no < 0 or block_no >= self.GRID_COLS * self.GRID_ROWS:
            return error_response(ErrorCode.INVALID_PARAM, f"区块号超出范围 (0~{self.GRID_COLS * self.GRID_ROWS - 1})")
        gy = block_no // self.GRID_COLS
        gx = block_no % self.GRID_COLS
        return {"success": True, "block_no": block_no, "grid_x": gx, "grid_y": gy,
                "x_min": gx * self.BLOCK_SIZE, "y_min": gy * self.BLOCK_SIZE,
                "x_max": (gx + 1) * self.BLOCK_SIZE - 1, "y_max": (gy + 1) * self.BLOCK_SIZE - 1,
                "block_size": self.BLOCK_SIZE, "grid_cols": self.GRID_COLS, "grid_rows": self.GRID_ROWS}

    def api_load_map_summary(self) -> dict:
        """加载地图摘要：城池坐标+建筑坐标+地形类型列表"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        summary = {"cities": [], "buildings": [], "terrains": [], "map_size": [self.MAP_WIDTH, self.MAP_HEIGHT],
                   "block_size": self.BLOCK_SIZE, "grid": [self.GRID_COLS, self.GRID_ROWS]}
        # 加载城池坐标
        citypos_path = os.path.join(self.game_path, "Setting", "CityPos.ini")
        if os.path.exists(citypos_path):
            parser = IniParser()
            parser.load(citypos_path)
            for s in parser.get_all_sections("CITYPOS"):
                e = dict(s.entries)
                x = int(e.get("PosX", 0))
                y = int(e.get("PosY", 0))
                summary["cities"].append({
                    "no": e.get("No", ""), "x": x, "y": y,
                    "grid_x": x // self.BLOCK_SIZE, "grid_y": y // self.BLOCK_SIZE,
                    "block_no": (y // self.BLOCK_SIZE) * self.GRID_COLS + (x // self.BLOCK_SIZE)
                })
        # 加载建筑坐标
        bld_path = os.path.join(self.game_path, "Setting", "BuildingPos.ini")
        if os.path.exists(bld_path):
            parser = IniParser()
            parser.load(bld_path)
            for s in parser.get_all_sections("CITY"):
                e = dict(s.entries)
                x = int(e.get("PosX", 0))
                y = int(e.get("PosY", 0))
                summary["buildings"].append({
                    "no": e.get("No", ""), "x": x, "y": y,
                    "grid_x": x // self.BLOCK_SIZE, "grid_y": y // self.BLOCK_SIZE,
                    "block_no": (y // self.BLOCK_SIZE) * self.GRID_COLS + (x // self.BLOCK_SIZE)
                })
        # 加载地形类型定义
        terrain_path = os.path.join(self.game_path, "Setting", "Terrain.ini")
        if os.path.exists(terrain_path):
            parser = IniParser()
            parser.load(terrain_path)
            for s in parser.get_all_sections("BRUSH_TO_TERRAIN"):
                e = dict(s.entries)
                summary["terrains"].append({"brush": e.get("No", ""), "terrain": e.get("Name", "")})
        return {"success": True, "summary": summary}

    def api_save_map_positions(self, cities: list) -> dict:
        """保存城池位置到 CityPos.ini"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        citypos_path = os.path.join(self.game_path, "Setting", "CityPos.ini")
        if not os.path.exists(citypos_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到 CityPos.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(citypos_path)
        try:
            parser = IniParser()
            parser.load(citypos_path)
            for cdata in cities:
                cno = str(cdata.get("no", ""))
                for section in parser.sections:
                    if section.name == "CITYPOS" and str(section.get("No", "")) == cno:
                        section.set("PosX", str(cdata.get("x", 0)))
                        section.set("PosY", str(cdata.get("y", 0)))
                        break
            parser.save(citypos_path)
            return success_response(message=f"已保存 {len(cities)} 个城池位置")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))


    # ============================================================
    # API: PCK 资源预览增强
    # ============================================================
    def api_pck_preview_shp(self, pck_name: str, internal_path: str) -> dict:
        """从PCK内直接预览SHP图片（返回base64 PNG）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        safe_pck = os.path.basename(pck_name)
        if safe_pck != pck_name or '..' in pck_name:
            return error_response(ErrorCode.INVALID_PARAM, "无效的PCK文件名")
        pck_path = os.path.join(self.game_path, safe_pck)
        if not os.path.exists(pck_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, f"未找到 {pck_name}")
        try:
            # 从PCK提取SHP二进制数据到内存
            with open(pck_path, "rb") as f:
                import struct
                magic = struct.unpack("<I", f.read(4))[0]
                if magic != 0x02000000:
                    return error_response(ErrorCode.INVALID_PARAM, "非标准PCK格式")
                file_count = struct.unpack("<I", f.read(4))[0]
                f.seek(12)
                index_offset = struct.unpack("<I", f.read(4))[0]
                f.seek(index_offset)
                for i in range(file_count):
                    name_raw = f.read(64)
                    name = name_raw.split(b'\x00')[0].decode('gbk', errors='replace')
                    data_offset = struct.unpack("<I", f.read(4))[0]
                    data_size = struct.unpack("<I", f.read(4))[0]
                    f.seek(56, 1)
                    if name.lower() == internal_path.lower() or name.replace('\\', '/').lower() == internal_path.lower():
                        f.seek(data_offset)
                        shp_data = f.read(data_size)
                        # 解析SHP为PNG
                        from core.shp_converter import ShpConverter
                        converter = ShpConverter(self.game_path)
                        img = converter.decode_shp_bytes(shp_data)
                        if img:
                            import io, base64
                            buf = io.BytesIO()
                            img.save(buf, format='PNG')
                            b64 = base64.b64encode(buf.getvalue()).decode('ascii')
                            return {"success": True, "name": name, "size": data_size,
                                    "width": img.width, "height": img.height,
                                    "base64": "data:image/png;base64," + b64}
                        return error_response(ErrorCode.INTERNAL, "无法解码SHP图片")
                return error_response(ErrorCode.FILE_NOT_FOUND, f"PCK中未找到: {internal_path}")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))


    # ============================================================
    # API: SANGO7.MPC 地形编辑器
    # ============================================================
    TERRAIN_NAMES = {0:"无",1:"草原",2:"乾草原",3:"荒地",4:"道路",5:"湿地",6:"森林",7:"丘陵",8:"高山",9:"沙漠",10:"河",11:"浅海",12:"深海",13:"残雪",14:"雪原",15:"雪丘",16:"雪山"}
    TERRAIN_COLORS = {0:"#2d5a27",1:"#4a8c3f",2:"#8b9a47",3:"#9e8b5e",4:"#c4a45a",5:"#5a7a3a",6:"#2d5a1e",7:"#7a8a5a",8:"#6a6a5a",9:"#d4c47a",10:"#3a6aaa",11:"#5a8aaa",12:"#2a4a7a",13:"#d4e4f4",14:"#e8f0f8",15:"#c8d8e8",16:"#f0f4f8"}

    def api_mpc_read(self, block_x: int = None, block_y: int = None, width: int = 546, height: int = 387) -> dict:
        """读取SANGO7.MPC地形数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        mpc_path = os.path.join(self.game_path, "map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            mpc_path = os.path.join(self.game_path, "Map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到 map/SANGO7.MPC")
        try:
            with open(mpc_path, "rb") as f:
                data = f.read()
            total = len(data)
            # 推断每条记录大小
            expected = self.GRID_COLS * self.GRID_ROWS
            if total >= expected:
                record_size = total // expected
            else:
                record_size = 1
            if block_x is not None and block_y is not None:
                idx = (block_y * self.GRID_COLS + block_x) * record_size
                if idx + record_size <= total:
                    val = data[idx]
                    return {"success": True, "x": block_x, "y": block_y, "terrain": val,
                            "terrain_name": self.TERRAIN_NAMES.get(val, f"未知({val})"),
                            "record_size": record_size, "total_bytes": total}
                return error_response(ErrorCode.INVALID_PARAM, "坐标超出范围")
            # 返回摘要
            terrain_counts = {}
            sample = []
            for gy in range(min(height, self.GRID_ROWS)):
                row = []
                for gx in range(min(width, self.GRID_COLS)):
                    idx = (gy * self.GRID_COLS + gx) * record_size
                    val = data[idx] if idx < total else 0
                    terrain_counts[val] = terrain_counts.get(val, 0) + 1
                    row.append(val)
                sample.append(row)
            summary = [{"id": k, "name": self.TERRAIN_NAMES.get(k, f"未知"), "count": v, "pct": round(v/expected*100,1)}
                       for k, v in sorted(terrain_counts.items())]
            return success_response({"data": sample, "summary": summary, "record_size": record_size, "total_bytes": total, "grid_cols": self.GRID_COLS, "grid_rows": self.GRID_ROWS, "expected_blocks": expected})
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_mpc_write(self, block_x: int, block_y: int, terrain: int) -> dict:
        """写入单个区块地形"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        mpc_path = os.path.join(self.game_path, "map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            mpc_path = os.path.join(self.game_path, "Map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到 map/SANGO7.MPC")
        try:
            if self.backup_mgr:
                self.backup_mgr.backup_file(mpc_path)
            with open(mpc_path, "rb") as f:
                data = bytearray(f.read())
            total = len(data)
            expected = self.GRID_COLS * self.GRID_ROWS
            record_size = total // expected if total >= expected else 1
            idx = (block_y * self.GRID_COLS + block_x) * record_size
            if idx + record_size <= total:
                data[idx] = terrain & 0xFF
                with open(mpc_path, "wb") as f:
                    f.write(data)
                return success_response(message=f"区块({block_x},{block_y})地形已设为{self.TERRAIN_NAMES.get(terrain,'?')}")
            return error_response(ErrorCode.INVALID_PARAM, "坐标超出范围")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_mpc_batch_write(self, changes: list) -> dict:
        """批量写入地形: [{x,y,terrain},...]"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        mpc_path = os.path.join(self.game_path, "map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            mpc_path = os.path.join(self.game_path, "Map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到 map/SANGO7.MPC")
        try:
            if self.backup_mgr:
                self.backup_mgr.backup_file(mpc_path)
            with open(mpc_path, "rb") as f:
                data = bytearray(f.read())
            total = len(data)
            expected = self.GRID_COLS * self.GRID_ROWS
            record_size = total // expected if total >= expected else 1
            count = 0
            for c in changes:
                idx = (c["y"] * self.GRID_COLS + c["x"]) * record_size
                if idx + record_size <= total:
                    data[idx] = c["terrain"] & 0xFF
                    count += 1
            with open(mpc_path, "wb") as f:
                f.write(data)
            return success_response({"count": count}, message=f"已更新{count}个区块")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))


    # ============================================================
    # API: Shape .info.ini 位移编辑器
    # ============================================================
    def api_shape_info_list(self, category: str = "all") -> dict:
        """列出所有 .info.ini 位移文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        shape_dir = os.path.join(self.game_path, "Shape")
        if not os.path.exists(shape_dir):
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到Shape目录")
        infos = []
        for root, dirs, files in os.walk(shape_dir):
            for f in files:
                if f.endswith(".info.ini"):
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, shape_dir)
                    # 读取X/Y偏移
                    parser = IniParser()
                    parser.load(full)
                    x = parser.get("Offset", "X", "0")
                    y = parser.get("Offset", "Y", "0")
                    cat = os.path.basename(os.path.dirname(full)) if os.path.dirname(full) != shape_dir else "root"
                    if category != "all" and cat.lower() != category.lower():
                        continue
                    infos.append({"path": rel, "category": cat, "x": int(x), "y": int(y), "file": f})
        return {"success": True, "infos": infos, "count": len(infos), "categories": list(set(i["category"] for i in infos))}

    def api_shape_info_save(self, rel_path: str, x: int, y: int) -> dict:
        """保存单个 .info.ini 的位移参数"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        full = os.path.join(self.game_path, "Shape", rel_path)
        if not os.path.exists(full):
            return error_response(ErrorCode.FILE_NOT_FOUND)
        if self.backup_mgr:
            self.backup_mgr.backup_file(full)
        parser = IniParser()
        parser.load(full)
        parser.set("Offset", "X", str(x))
        parser.set("Offset", "Y", str(y))
        parser.save(full)
        return success_response(message=f"已保存 {rel_path}: X={x}, Y={y}")

    def api_shape_info_delete(self, rel_path: str) -> dict:
        """删除指定的 .info.ini 文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        full = os.path.join(self.game_path, "Shape", rel_path)
        if not os.path.exists(full):
            return error_response(ErrorCode.FILE_NOT_FOUND)
        if self.backup_mgr:
            self.backup_mgr.backup_file(full)
        os.remove(full)
        return success_response(message=f"已删除 {rel_path}")

    def api_shape_info_clone(self, rel_path: str, new_name: str) -> dict:
        """克隆指定的 .info.ini 文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        full = os.path.join(self.game_path, "Shape", rel_path)
        if not os.path.exists(full):
            return error_response(ErrorCode.FILE_NOT_FOUND, "源文件不存在")
        new_path = os.path.join(os.path.dirname(full), new_name)
        if os.path.exists(new_path):
            return error_response(ErrorCode.FILE_ALREADY_EXISTS, f"目标文件 {new_name} 已存在")
        import shutil
        shutil.copy2(full, new_path)
        return success_response(message=f"已克隆为 {new_name}")

    def api_shape_info_new(self, rel_path: str, category: str = "root") -> dict:
        """创建新的 .info.ini 文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        shape_dir = os.path.join(self.game_path, "Shape")
        if category and category != "root":
            dest_dir = os.path.join(shape_dir, category)
            os.makedirs(dest_dir, exist_ok=True)
        else:
            dest_dir = shape_dir
        full = os.path.join(dest_dir, rel_path)
        if os.path.exists(full):
            return error_response(ErrorCode.FILE_ALREADY_EXISTS, f"文件 {rel_path} 已存在")
        parser = IniParser()
        parser.add_section("Offset")
        parser.set("Offset", "X", "0")
        parser.set("Offset", "Y", "0")
        parser.save(full)
        return success_response(message=f"已创建 {rel_path}")


    # ============================================================
    # API: SHP 批量改名
    # ============================================================
    def api_shp_batch_rename(self, directory: str, prefix: str, start_id: int, digits: int = 4) -> dict:
        """批量重命名SHP文件: prefix_0001.shp, prefix_0002.shp..."""
        if not os.path.isdir(directory):
            return error_response(ErrorCode.FILE_NOT_FOUND, "目录不存在")
        shp_files = sorted([f for f in os.listdir(directory) if f.lower().endswith('.shp')])
        if not shp_files:
            return error_response(ErrorCode.FILE_NOT_FOUND, "目录中没有SHP文件")
        renamed = []
        for i, old_name in enumerate(shp_files):
            new_name = f"{prefix}_{start_id + i:0{digits}d}.shp"
            old_path = os.path.join(directory, old_name)
            new_path = os.path.join(directory, new_name)
            if old_path != new_path:
                if os.path.exists(new_path):
                    return error_response(ErrorCode.FILE_ALREADY_EXISTS, f"目标文件已存在: {new_name}")
                os.rename(old_path, new_path)
                renamed.append({"from": old_name, "to": new_name})
        return success_response({"renamed": renamed, "count": len(renamed)}, message=f"已重命名{len(renamed)}个文件")


    # ============================================================
    # API: 城池连接关系
    # ============================================================
    def api_city_connections(self) -> dict:
        """获取所有城池连接关系（用于可视化）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        city_path = os.path.join(self.game_path, "Setting", "City.ini")
        citypos_path = os.path.join(self.game_path, "Setting", "CityPos.ini")
        if not os.path.exists(city_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到 City.ini")
        parser = IniParser()
        parser.load(city_path)
        cities = {}
        for s in parser.get_all_sections("CITY"):
            e = dict(s.entries)
            no = e.get("No", "")
            name = e.get("Name", "")
            conns = []
            for i in range(10):
                conn_key = f"Connect{i:02d}"
                conn_val = e.get(conn_key, "")
                if conn_val and conn_val.strip():
                    parts = conn_val.split(",")
                    if len(parts) >= 2:
                        conns.append({"target": parts[0].strip(), "distance": parts[1].strip()})
            cities[no] = {"no": no, "name": name, "connections": conns}
        # 加载坐标
        positions = {}
        if os.path.exists(citypos_path):
            pos_parser = IniParser()
            pos_parser.load(citypos_path)
            for s in pos_parser.get_all_sections("CITYPOS"):
                e = dict(s.entries)
                positions[e.get("No", "")] = {"x": int(e.get("PosX", 0)), "y": int(e.get("PosY", 0))}
        return {"success": True, "cities": cities, "positions": positions, "map_size": [self.MAP_WIDTH, self.MAP_HEIGHT]}

    def api_load_city_connect(self) -> dict:
        """加载城池连接数据（可编辑模式）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        city_path = os.path.join(self.game_path, "Setting", "City.ini")
        if not os.path.exists(city_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "未找到 City.ini")
        parser = IniParser()
        parser.load(city_path)
        data = []
        for s in parser.get_all_sections("CITY"):
            data.append(dict(s.entries))
        return success_response({"data": data, "count": len(data)})

    def api_save_city_connect(self, data: list) -> dict:
        """保存城池连接数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        city_path = os.path.join(self.game_path, "Setting", "City.ini")
        try:
            if self.backup_mgr:
                self.backup_mgr.backup_file(city_path)
            parser = IniParser()
            parser.load(city_path)
            # 更新 CITY sections
            for item in data:
                no = item.get("No", "")
                section = parser.get_section("CITY", no)
                if section:
                    for k, v in item.items():
                        section.set(k, str(v) if v is not None else "")
            parser.save(city_path)
            return success_response({"count": len(data)}, message="城池连接已保存")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_load_idini(self) -> dict:
        """加载 WinTest/id.ini"""
        if not self.game_path:

            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        idini_path = os.path.join(self.game_path, "WinTest", "id.ini")
        if not os.path.exists(idini_path):
            return success_response({"data": [], "count": 0, "message": "id.ini 不存在"})
        try:
            parser = IniParser()
            parser.load(idini_path)
            data = []
            for s in parser.get_all_sections("ID"):
                e = dict(s.entries)
                data.append({"key": e.get("key", ""), "value": e.get("value", "")})
            return success_response({"data": data, "count": len(data)})
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_save_idini(self, data: list) -> dict:
        """保存 WinTest/id.ini"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        idini_path = os.path.join(self.game_path, "WinTest", "id.ini")
        os.makedirs(os.path.dirname(idini_path), exist_ok=True)
        if self.backup_mgr:
            self.backup_mgr.backup_file(idini_path)
        try:
            parser = IniParser()
            for item in data:
                parser.add_section("ID", {"key": item.get("key", ""), "value": item.get("value", "")})
            parser.save(idini_path)
            return success_response(message=f"已保存 {len(data)} 条")
        except Exception as e:
            logger.error(f"操作失败: {e}", exc_info=True)
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # ============================================================
    # API: 脚本编辑器
    # ============================================================
