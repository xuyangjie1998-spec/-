import os, json, re, shutil, base64, tempfile, time
from io import BytesIO
from typing import Any, Dict, List, Optional

# 从 main.py 导入模块级常量
try:
    from main import PROJECT_ROOT
except ImportError:
    import sys
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

__all__ = ['San7ModMakerGame']

class San7ModMakerGame:
    """MOD制作器 - 游戏系统 (阵型/官职/剧本/势力/城池/事件)"""

    # ============================================================
    # API: 全局游戏参数 (Variable.ini)
    # ============================================================

    def api_load_global_params(self) -> dict:
        """加载全局游戏参数 - 完整读取所有 [VARIABLE] 段"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Variable.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0, "message": "Variable.ini 不存在"}
        parser = IniParser()
        parser.load(path)
        # 读取所有 [VARIABLE] section，每个是一个参数组
        sections = parser.get_all_sections("VARIABLE")
        if not sections:
            return {"success": True, "data": [], "count": 0}
        data = []
        for s in sections:
            entry = dict(s.entries)
            # 确保关键字段存在
            data.append({
                "No": int(entry.get("No", 0)),
                "Name": entry.get("Name", ""),
                "EnumName": entry.get("EnumName", ""),
                "Int00": entry.get("Int00", "0"),
                "Int01": entry.get("Int01", "0"),
                "Int02": entry.get("Int02", "0"),
                "Int03": entry.get("Int03", "0"),
                "Int04": entry.get("Int04", "0"),
                "Int05": entry.get("Int05", "0"),
                "Int06": entry.get("Int06", "0"),
                "Int07": entry.get("Int07", "0"),
                "Int08": entry.get("Int08", "0"),
                "Int09": entry.get("Int09", "0"),
                "Float00": entry.get("Float00", "0"),
                "Float01": entry.get("Float01", "0"),
                "Float02": entry.get("Float02", "0"),
                "Float03": entry.get("Float03", "0"),
                "Float04": entry.get("Float04", "0"),
                "Float05": entry.get("Float05", "0"),
                "Float06": entry.get("Float06", "0"),
                "Float07": entry.get("Float07", "0"),
                "Float08": entry.get("Float08", "0"),
                "Float09": entry.get("Float09", "0"),
                # 保留原始所有字段以备扩展
                "_raw": entry,
            })
        self._global_params_cache = data
        return {"success": True, "data": data, "count": len(data)}

    def api_save_global_params(self, data: list) -> dict:
        """保存全局游戏参数 - 完整保存所有 [VARIABLE] 段"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Variable.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        if os.path.exists(path):
            parser.load(path)
        clean_entries = []
        for entry in data:
            clean = {k: v for k, v in entry.items() if k != "_raw"}
            clean_entries.append(clean)
        parser.replace_sections("VARIABLE", clean_entries, "No")
        parser.save(path)
        self._global_params_cache = data
        return {"success": True, "message": f"全局参数保存成功，共 {len(data)} 条"}

    def api_new_global_params(self) -> dict:
        return {"success": True, "data": {"No": "", "Name": "", "Int00": "0", "Int01": "0", "Int02": "0", "Int03": "0", "Int04": "0", "Int05": "0", "Int06": "0", "Int07": "0", "Int08": "0", "Int09": "0", "Float00": "0", "Float01": "0", "Float02": "0", "Float03": "0", "Float04": "0", "Float05": "0", "Float06": "0", "Float07": "0", "Float08": "0", "Float09": "0", "String": ""}}

    def api_search_global_params(self, keyword: str) -> dict:
        """搜索全局参数"""
        if not self._global_params_cache:
            return {"success": True, "data": [], "count": 0}
        keyword_lower = keyword.lower()
        results = []
        for p in self._global_params_cache:
            if (keyword_lower in p.get("Name", "").lower() or
                keyword_lower in p.get("EnumName", "").lower() or
                keyword_lower in str(p.get("No", ""))):
                results.append(p)
        return {"success": True, "data": results, "count": len(results)}

    # ============================================================
    # API: 势力 (Nation.ini)
    # ============================================================

    def api_load_nations(self) -> dict:
        """加载势力数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Nation.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("NATION")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_nations(self, data: list) -> dict:
        """保存势力数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Nation.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("NATION", data, "No")
        parser.save(path)
        # 同步势力名称到 TermText
        if self.term_text.is_loaded():
            for entry in data:
                name = entry.get("Name", "")
                if name:
                    self.term_text.allocate_new_id(name)
            self.term_text.save()
        return {"success": True, "message": f"保存成功，共{len(data)}个势力"}

    def api_new_nation(self) -> dict:
        """创建新势力模板"""
        data = self._load_schema("nation_schema")
        template = data["new_entry_template"] if data and "new_entry_template" in data else {}
        if not template:
            template = {"No": 0, "Name": "新势力", "Lord": 0, "Color": 0}
        return {"success": True, "data": template}

    def api_nation_linkage_check(self, nation_no: str) -> dict:
        """检查势力是否已有联动数据（Color + City）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        no = str(nation_no)
        result = {"nation_no": no, "color": None, "city": None}

        # 检查 Color.ini
        color_path = os.path.join(self.game_path, "Setting", "Color.ini")
        if os.path.exists(color_path):
            parser = IniParser()
            parser.load(color_path)
            for s in parser.get_all_sections("COLOR"):
                if str(s.entries.get("No", "")) == no:
                    result["color"] = dict(s.entries)
                    break

        # 检查 City.ini
        city_path = os.path.join(self.game_path, "Setting", "City.ini")
        if os.path.exists(city_path):
            parser = IniParser()
            parser.load(city_path)
            for s in parser.get_all_sections("CITY"):
                # 通过 Name 匹配（城池名通常包含国号）
                if str(s.entries.get("No", "")) == no:
                    result["city"] = dict(s.entries)
                    break

        result["linked"] = bool(result["color"] or result["city"])
        return {"success": True, "data": result}

    def api_nation_linkage_create(self, nation_no: str, nation_name: str = "",
                                   color_r: int = 255, color_g: int = 0, color_b: int = 0,
                                   city_name: str = "", lord: int = 0) -> dict:
        """
        为势力创建联动数据：Color + City
        自动在 Color.ini 和 City.ini 中创建对应条目
        """
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        results = {}
        no = str(nation_no)

        # 1. 创建 Color 条目
        color_path = os.path.join(self.game_path, "Setting", "Color.ini")
        color_created = False
        try:
            parser = IniParser()
            if os.path.exists(color_path):
                parser.load(color_path)
            # 检查是否已存在
            existing = False
            for s in parser.get_all_sections("COLOR"):
                if str(s.entries.get("No", "")) == no:
                    existing = True
                    break
            if not existing:
                section = parser.add_section("COLOR")
                section.set("No", no)
                section.set("Red", str(color_r))
                section.set("Green", str(color_g))
                section.set("Blue", str(color_b))
                parser.save(color_path)
                color_created = True
                results["color"] = {"No": no, "Red": color_r, "Green": color_g, "Blue": color_b}
            else:
                results["color"] = {"message": "已存在，跳过"}
        except Exception as e:
            results["color_error"] = str(e)

        # 2. 创建 City 条目
        city_name_final = city_name or nation_name or f"势力{no}"
        city_path = os.path.join(self.game_path, "Setting", "City.ini")
        city_created = False
        try:
            parser = IniParser()
            if os.path.exists(city_path):
                parser.load(city_path)
            # 检查是否已存在
            existing = False
            for s in parser.get_all_sections("CITY"):
                if str(s.entries.get("No", "")) == no:
                    existing = True
                    break
            if not existing:
                section = parser.add_section("CITY")
                section.set("No", no)
                section.set("Name", city_name_final)
                section.set("Lord", str(lord))
                section.set("People", "100000")
                section.set("PeopleHeart", "500")
                section.set("Money", "500")
                section.set("Defend", "100")
                section.set("Economics", "100")
                section.set("ReserveSoldierNumCur", "20")
                section.set("IsUsed", "1")
                parser.save(city_path)
                city_created = True
                results["city"] = {"No": no, "Name": city_name_final, "Lord": lord}
            else:
                results["city"] = {"message": "已存在，跳过"}
        except Exception as e:
            results["city_error"] = str(e)

        results["success"] = color_created or city_created
        if color_created and city_created:
            results["message"] = f"已为势力 {nation_name or no} 创建 Color + City 联动数据"
        elif color_created:
            results["message"] = f"已创建 Color 数据（City 已存在）"
        elif city_created:
            results["message"] = f"已创建 City 数据（Color 已存在）"
        else:
            results["message"] = "联动数据已存在，无需创建"

        # 3. City01-10.ini (10个剧本) 同步 Owner
        if city_created:
            try:
                for i in range(1, 11):
                    cpath = os.path.join(self.game_path, "Setting", f"City{i:02d}.ini")
                    if os.path.exists(cpath):
                        cp = IniParser()
                        cp.load(cpath)
                        found = False
                        for s in cp.get_all_sections("CITY"):
                            if str(s.entries.get("No", "")) == no:
                                found = True
                                break
                        if not found:
                            cs = cp.add_section("CITY")
                            cs.set("No", no)
                            cs.set("Owner", no)
                            cs.set("Soldier", "500")
                            cs.set("HP", "500")
                            cp.save(cpath)
                results["city_periods"] = "已同步10个剧本城池归属"
            except Exception as e:
                results["city_periods_error"] = str(e)

        # 4. General01.ini 更新 Lord 字段
        if lord and lord > 0:
            try:
                gpath = os.path.join(self.game_path, "Setting", "General01.ini")
                if os.path.exists(gpath):
                    gp = IniParser()
                    gp.load(gpath)
                    updated = False
                    for s in gp.get_all_sections("GENERAL"):
                        if str(s.entries.get("No", "")) == str(lord):
                            s.set("Lord", no)
                            updated = True
                            break
                    if updated:
                        gp.save(gpath)
                        results["general_lord"] = f"已更新武将 {lord} 的 Lord 字段为 {no}"
            except Exception as e:
                results["general_lord_error"] = str(e)

        return results

    # ============================================================
    # API: 城池 (City.ini)
    # ============================================================

    def api_load_cities(self) -> dict:
        """加载城池数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "City.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("CITY")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_cities(self, data: list) -> dict:
        """保存城池数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "City.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("CITY", data, "No")
        parser.save(path)
        # 同步城池名称到 TermText
        if self.term_text.is_loaded():
            for entry in data:
                name = entry.get("Name", "")
                if name:
                    self.term_text.allocate_new_id(name)
            self.term_text.save()
        return {"success": True, "message": f"保存成功，共{len(data)}座城池"}

    def api_new_city(self) -> dict:
        """创建新城池模板"""
        data = self._load_schema("city_schema")
        template = data["new_entry_template"] if data and "new_entry_template" in data else {}
        if not template:
            template = {"No": 0, "Name": "新城池", "Defense": 100, "Population": 10000}
        return {"success": True, "data": template}

    # ============================================================
    # API: 城池时期 (City01~City10.ini)
    # ============================================================

    def api_load_city_period(self, period: str = "01") -> dict:
        """加载城池时期数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", f"City{period}.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0, "period": period}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("CITY")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries), "period": period}

    def api_save_city_period(self, period: str = "01", data: list = None) -> dict:
        """保存城池时期数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if data is None:
            data = []
        path = os.path.join(self.game_path, "Setting", f"City{period}.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("CITY", data, "No")
        parser.save(path)
        return {"success": True, "message": f"City{period}.ini 保存成功，共{len(data)}条"}

    # ============================================================
    # API: 冲阵兵器/攻城器械 (BFFront.ini)
    # ============================================================

    def api_load_bffront(self) -> dict:
        """加载攻城器械数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "BFFront.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("BFFRONT")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_bffront(self, data: list) -> dict:
        """保存攻城器械数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "BFFront.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("BFFRONT", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}个器械"}

    def api_new_bffront(self) -> dict:
        """新增攻城器械"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "bffront_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: UI子系统 (Setting/UI/) 6个编辑器
    # ============================================================

    def _ui_load(self, filename: str, section_name: str, key_field: str = "ID") -> dict:
        """通用UI子系统加载"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "UI", filename)
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections(section_name)
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def _ui_save(self, filename: str, section_name: str, data: list, key_field: str = "ID", label: str = "") -> dict:
        """通用UI子系统保存"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "UI", filename)
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections(section_name, data, key_field)
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条{label}"}

    def api_load_buttonstyle(self) -> dict:
        return self._ui_load("ButtonStyle.ini", "ButtonStyle", "ID")

    def api_save_buttonstyle(self, data: list) -> dict:
        return self._ui_save("ButtonStyle.ini", "ButtonStyle", data, "ID", "按键样式")

    def api_new_buttonstyle(self) -> dict:
        return {"success": True, "data": {"ID": "", "Name": "", "Normal": "", "Hover": "", "Pressed": "", "Disabled": ""}}

    def api_load_fontsize(self) -> dict:
        return self._ui_load("FontSize.ini", "FontSize", "ID")

    def api_save_fontsize(self, data: list) -> dict:
        return self._ui_save("FontSize.ini", "FontSize", data, "ID", "字体大小")

    def api_new_fontsize(self) -> dict:
        return {"success": True, "data": {"ID": "", "Name": "", "Size": "0"}}

    def api_load_framestyle(self) -> dict:
        return self._ui_load("FrameStyle.ini", "FrameStyle", "ID")

    def api_save_framestyle(self, data: list) -> dict:
        return self._ui_save("FrameStyle.ini", "FrameStyle", data, "ID", "菜单边框")

    def api_new_framestyle(self) -> dict:
        return {"success": True, "data": {"ID": "", "Name": "", "Up": "", "Down": "", "Left": "", "Right": "", "UpLeft": "", "UpRight": "", "DownLeft": "", "DownRight": ""}}

    def api_load_liststyle(self) -> dict:
        return self._ui_load("ListStyle.ini", "ListStyle", "ID")

    def api_save_liststyle(self, data: list) -> dict:
        return self._ui_save("ListStyle.ini", "ListStyle", data, "ID", "列表样式")

    def api_new_liststyle(self) -> dict:
        return {"success": True, "data": {"ID": "", "Name": "", "ScrollBar": "", "ItemHeight": "0"}}

    def api_load_shapeui(self) -> dict:
        return self._ui_load("Shape.ini", "Shape", "ID")

    def api_save_shapeui(self, data: list) -> dict:
        return self._ui_save("Shape.ini", "Shape", data, "ID", "UI形状")

    def api_new_shapeui(self) -> dict:
        return {"success": True, "data": {"ID": "", "Name": "", "X": "0", "Y": "0", "Width": "0", "Height": "0"}}

    def api_load_textstyle(self) -> dict:
        return self._ui_load("TextStyle.ini", "TextStyle", "ID")

    def api_save_textstyle(self, data: list) -> dict:
        return self._ui_save("TextStyle.ini", "TextStyle", data, "ID", "对齐方式")

    def api_new_textstyle(self) -> dict:
        return {"success": True, "data": {"ID": "", "Name": "", "Align": "0", "Color": ""}}

    # ============================================================
    # API: Wnd子系统 (Setting/Wnd/) 2个编辑器
    # ============================================================

    def _wnd_load(self, filename: str, section_name: str) -> dict:
        """通用Wnd子系统加载"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Wnd", filename)
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections(section_name)
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def _wnd_save(self, filename: str, section_name: str, data: list, key_field: str, label: str) -> dict:
        """通用Wnd子系统保存"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Wnd", filename)
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections(section_name, data, key_field)
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条{label}"}

    def api_load_wincolor(self) -> dict:
        return self._wnd_load("WinColor.ini", "WinColor")

    def api_save_wincolor(self, data: list) -> dict:
        return self._wnd_save("WinColor.ini", "WinColor", data, "ID", "窗口颜色")

    def api_new_wincolor(self) -> dict:
        return {"success": True, "data": {"ID": "", "Name": "", "R": "0", "G": "0", "B": "0", "Alpha": "255"}}

    def api_load_winmainmenu(self) -> dict:
        return self._wnd_load("WinMainMenu.ini", "WinMainMenu")

    def api_save_winmainmenu(self, data: list) -> dict:
        return self._wnd_save("WinMainMenu.ini", "WinMainMenu", data, "ID", "主菜单")

    def api_new_winmainmenu(self) -> dict:
        return {"success": True, "data": {"ID": "", "Name": "", "X": "0", "Y": "0", "Width": "0", "Height": "0", "FontX": "0", "FontY": "0"}}

    # ============================================================
    # API: 配置覆盖缺失 (6个)
    # ============================================================

    def api_load_cdtable(self) -> dict:
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "CD_Table.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("CDTable")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_cdtable(self, data: list) -> dict:
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "CD_Table.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("CDTable", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}首战斗音乐"}

    def api_new_cdtable(self) -> dict:
        schema_path = os.path.join(PROJECT_ROOT, "data", "cdtable_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    def api_load_citytext(self) -> dict:
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "CityText.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("CityText")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_citytext(self, data: list) -> dict:
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "CityText.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("CityText", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条城市文本"}

    def api_new_citytext(self) -> dict:
        return {"success": True, "data": {"No": "", "Name": "", "Text": ""}}

    def api_load_postpatch(self) -> dict:
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "PostPatch.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("PostPatch")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_postpatch(self, data: list) -> dict:
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "PostPatch.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("PostPatch", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}个后补建筑"}

    def api_new_postpatch(self) -> dict:
        schema_path = os.path.join(PROJECT_ROOT, "data", "postpatch_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    def api_load_thingscriptno(self) -> dict:
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "ThingScriptNo.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("ThingScriptNo")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_thingscriptno(self, data: list) -> dict:
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "ThingScriptNo.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("ThingScriptNo", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条物品脚本编号"}

    def api_new_thingscriptno(self) -> dict:
        return {"success": True, "data": {"No": "", "ScriptNo": "", "Name": ""}}

    def api_load_fontmultilang(self) -> dict:
        """加载多语言font.ini变体"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        variants = {}
        for lang, fname in [("gb", "font.ini"), ("jp", "font.ini_jp"), ("eng", "font.ini_eng"), ("kor", "font.ini_kor")]:
            path = os.path.join(self.game_path, "Setting", fname)
            if os.path.exists(path):
                parser = IniParser()
                parser.load(path)
                sections = parser.get_all_sections("Font")
                variants[lang] = [dict(s.entries) for s in sections]
            else:
                variants[lang] = []
        return {"success": True, "data": variants, "message": f"已加载{len(variants)}个语言变体"}

    def api_save_fontmultilang(self, data: dict) -> dict:
        """保存多语言font.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        for lang, entries in data.items():
            fname = {"gb": "font.ini", "jp": "font.ini_jp", "eng": "font.ini_eng", "kor": "font.ini_kor"}.get(lang, f"font.ini_{lang}")
            path = os.path.join(self.game_path, "Setting", fname)
            if self.backup_mgr:
                self.backup_mgr.backup_file(path)
            parser = IniParser()
            parser.load(path)
            parser.replace_sections("Font", entries, "No")
            parser.save(path)
        return {"success": True, "message": "多语言字体配置保存成功"}

    # ============================================================
    # API: 系统界面文字 (SystemText.ini)
    # ============================================================

    def api_load_systemtext(self) -> dict:
        """加载系统界面文字"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "SystemText.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        entries = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_systemtext(self, data: list) -> dict:
        """保存系统界面文字"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "SystemText.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        section_name = "STRING"
        for s in parser.sections:
            if s.name in ("SYSTEMTEXT", "STRING"):
                section_name = s.name
                break
        parser.replace_sections(section_name, data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条"}

    def api_new_systemtext(self) -> dict:
        """新增系统文字"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "systemtext_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 游戏台词 (GossipText.ini)
    # ============================================================

    def api_load_gossiptext(self) -> dict:
        """加载游戏台词"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "GossipText.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        entries = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_gossiptext(self, data: list) -> dict:
        """保存游戏台词"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "GossipText.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        section_name = "STRING"
        for s in parser.sections:
            if s.name in ("GOSSIPTEXT", "STRING"):
                section_name = s.name
                break
        parser.replace_sections(section_name, data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条"}

    def api_new_gossiptext(self) -> dict:
        """新增台词"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "gossiptext_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 地形属性 (Terrain.ini)
    # ============================================================

    def api_load_terrain(self) -> dict:
        """加载地形属性"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Terrain.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        entries = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_terrain(self, data: list) -> dict:
        """保存地形属性"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Terrain.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("TERRAIN", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条"}

    def api_new_terrain(self) -> dict:
        """新增地形"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "terrain_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 特殊对话 (Dialogue.ini)
    # ============================================================

    def api_load_dialogue(self) -> dict:
        """加载特殊对话数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Dialogue.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("DIALOGUE")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_dialogue(self, data: list) -> dict:
        """保存特殊对话数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Dialogue.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("DIALOGUE", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条对话"}

    def api_new_dialogue(self) -> dict:
        """新增特殊对话"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "dialogue_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 势力颜色 (Color.ini)
    # ============================================================

    def api_load_color(self) -> dict:
        """加载势力颜色数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Color.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("COLOR")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_color(self, data: list) -> dict:
        """保存势力颜色数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Color.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("COLOR", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}个颜色"}

    def api_new_color(self) -> dict:
        """新增势力颜色"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "color_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 城池坐标 (CityPos.ini)
    # ============================================================

    def api_load_citypos(self) -> dict:
        """加载城池坐标数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "CityPos.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("CITYPOS")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_citypos(self, data: list) -> dict:
        """保存城池坐标数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "CityPos.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("CITYPOS", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条坐标"}

    def api_new_citypos(self) -> dict:
        """新增城池坐标"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "citypos_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 扩展地形 (ExtraTerrain.ini)
    # ============================================================

    def api_load_extraterrain(self) -> dict:
        """加载扩展地形"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "ExtraTerrain.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        entries = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_extraterrain(self, data: list) -> dict:
        """保存扩展地形"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "ExtraTerrain.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("EXTRATERRAIN", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条"}

    def api_new_extraterrain(self) -> dict:
        """新增扩展地形"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "extraterrain_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 士兵站位 (FormatOffsetPos.ini)
    # ============================================================

    def api_load_formatoffsetpos(self) -> dict:
        """加载士兵站位坐标"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "FormatOffsetPos.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        entries = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_formatoffsetpos(self, data: list) -> dict:
        """保存士兵站位坐标"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "FormatOffsetPos.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("FORMATOFFSETPOS", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条"}

    def api_new_formatoffsetpos(self) -> dict:
        """新增士兵站位"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "formatoffsetpos_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 建筑坐标 (BuildingPos.ini)
    # ============================================================

    def api_load_buildingpos(self) -> dict:
        """加载建筑坐标"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "BuildingPos.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        entries = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_buildingpos(self, data: list) -> dict:
        """保存建筑坐标"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "BuildingPos.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("BUILDINGPOS", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条"}

    def api_new_buildingpos(self) -> dict:
        """新增建筑坐标"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "buildingpos_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 桥梁坐标 (SFBridge.ini)
    # ============================================================

    def api_load_sfbridge(self) -> dict:
        """加载桥梁坐标"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "SFBridge.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        entries = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_sfbridge(self, data: list) -> dict:
        """保存桥梁坐标"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "SFBridge.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("SFBRIDGE", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条"}

    def api_new_sfbridge(self) -> dict:
        """新增桥梁坐标"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "sfbridge_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 路障坐标 (SFRoadBlock.ini)
    # ============================================================

    def api_load_sfroadblock(self) -> dict:
        """加载路障坐标"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "SFRoadBlock.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        entries = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_sfroadblock(self, data: list) -> dict:
        """保存路障坐标"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "SFRoadBlock.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("SFROADBLOCK", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条"}

    def api_new_sfroadblock(self) -> dict:
        """新增路障坐标"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "sfroadblock_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 路障分布区域 (SFRoadBlockPos.ini)
    # ============================================================

    def api_load_sfroadblockpos(self) -> dict:
        """加载路障分布区域"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "SFRoadBlockPos.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        entries = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_sfroadblockpos(self, data: list) -> dict:
        """保存路障分布区域"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "SFRoadBlockPos.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("SFROADBLOCKPOS", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条"}

    def api_new_sfroadblockpos(self) -> dict:
        """新增路障分布区域"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "sfroadblockpos_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 战场镜头 (Var.ini)
    # ============================================================

    def api_load_var(self) -> dict:
        """加载战场镜头变量"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Var.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        entries = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_var(self, data: list) -> dict:
        """保存战场镜头变量"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Var.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("VAR", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条"}

    def api_new_var(self) -> dict:
        """新增镜头变量"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "var_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 字体设置 (font.ini)
    # ============================================================

    def api_load_font(self) -> dict:
        """加载字体设置"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "font.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        entries = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_font(self, data: list) -> dict:
        """保存字体设置"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "font.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("FONT", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条"}

    def api_new_font(self) -> dict:
        """新增字体"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "font_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 系统链接 (system.ini)
    # ============================================================

    def api_load_systemini(self) -> dict:
        """加载系统链接配置"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "system.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        entries = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_systemini(self, data: list) -> dict:
        """保存系统链接配置"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "system.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("SYSTEM", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}条"}

    def api_new_systemini(self) -> dict:
        """新增系统链接"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "system_ini_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 阵型属性 (Format.ini)
    # ============================================================

    def api_load_format(self) -> dict:
        """加载阵型属性数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Format.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "message": "Format.ini 不存在"}
        parser = IniParser()
        parser.load(path)
        data = []
        for s in parser.get_all_sections("FORMAT"):
            data.append(dict(s.entries))
        return {"success": True, "data": data, "count": len(data)}

    def api_save_format(self, data: list) -> dict:
        """保存阵型属性数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Format.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        if os.path.exists(path):
            parser.load(path)
        parser.replace_sections("FORMAT", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}个阵型"}

    def api_new_format(self) -> dict:
        schema_path = os.path.join(PROJECT_ROOT, "data", "format_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 自设阵法 (ChessFormat.ini)
    # ============================================================

    def api_load_chessformat(self) -> dict:
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "ChessFormat.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "message": "ChessFormat.ini 不存在"}
        parser = IniParser()
        parser.load(path)
        data = []
        for s in parser.get_all_sections("CHESS"):
            data.append(dict(s.entries))
        return {"success": True, "data": data, "count": len(data)}

    def api_save_chessformat(self, data: list) -> dict:
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "ChessFormat.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        if os.path.exists(path):
            parser.load(path)
        parser.replace_sections("CHESS", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}个阵法"}

    def api_new_chessformat(self) -> dict:
        schema_path = os.path.join(PROJECT_ROOT, "data", "chessformat_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return {"success": True, "data": dict(schema["new_entry_template"])}

    # ============================================================
    # API: 历史事件 (History.ini)
    # ============================================================

    def api_load_histories(self) -> dict:
        """加载历史事件数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "History.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("HISTORY")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_histories(self, data: list) -> dict:
        """保存历史事件数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "History.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        if os.path.exists(path):
            parser.load(path)
        parser.replace_sections("HISTORY", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}个历史事件"}

    def api_new_history(self) -> dict:
        """新增历史事件（返回默认模板）"""
        return {
            "success": True,
            "data": {
                "No": "0", "ClassType": "1", "Priority": "0", "Age": "0",
                "S_Year": "-1", "S_Season": "-1", "E_Year": "-1", "E_Season": "-1",
                "PreHistory": "0", "NedHistory01": "0", "NedHistory02": "0", "NedHistory03": "0", "Pic": "0",
                "LordA": "0", "LordALv": "0", "bCustomA": "0",
                "LordB": "0", "LordBLv": "0", "bCustomB": "0",
                "LordC": "0", "LorCLv": "0", "bCustomC": "0",
                "S_ProposeGeneral": "0", "S_ProposeString": "0", "S_AnsProposeString": "0",
                "S_DiplomaticGeneral": "0", "S_DiplomaticString": "0",
                "S_General01": "0", "S_StringA01": "0", "S_StringD01": "0", "S_MinGenLv01": "0", "S_MinLoyal01": "0", "S_City01": "0",
                "S_General02": "0", "S_StringA02": "0", "S_StringD02": "0", "S_MinGenLv02": "0", "S_MinLoyal02": "0", "S_City02": "0",
                "S_General03": "0", "S_StringA03": "0", "S_StringD03": "0", "S_MinGenLv03": "0", "S_MinLoyal03": "0", "S_City03": "0",
                "S_General04": "0", "S_StringA04": "0", "S_StringD04": "0", "S_MinGenLv04": "0", "S_MinLoyal04": "0", "S_City04": "0",
                "S_General05": "0", "S_StringA05": "0", "S_StringD05": "0", "S_MinGenLv05": "0", "S_MinLoyal05": "0", "S_City05": "0",
                "S_General06": "0", "S_StringA06": "0", "S_StringD06": "0", "S_MinGenLv06": "0", "S_MinLoyal06": "0", "S_City06": "0",
                "S_General07": "0", "S_StringA07": "0", "S_StringD07": "0", "S_MinGenLv07": "0", "S_MinLoyal07": "0", "S_City07": "0",
                "S_General08": "0", "S_StringA08": "0", "S_StringD08": "0", "S_MinGenLv08": "0", "S_MinLoyal08": "0", "S_City08": "0",
                "S_General09": "0", "S_StringA09": "0", "S_StringD09": "0", "S_MinGenLv09": "0", "S_MinLoyal09": "0", "S_City09": "0",
                "S_General10": "0", "S_StringA10": "0", "S_StringD10": "0", "S_MinGenLv10": "0", "S_MinLoyal10": "0", "S_City10": "0",
                "D_LordBStringA": "0", "D_LordBStringD": "0",
                "D_General01": "0", "D_StringA01": "0", "D_StringD01": "0", "D_MinGenLv01": "0", "D_MinLoyal01": "0", "D_City01": "0",
                "D_General02": "0", "D_StringA02": "0", "D_StringD02": "0", "D_MinGenLv02": "0", "D_MinLoyal02": "0", "D_City02": "0",
                "D_General03": "0", "D_StringA03": "0", "D_StringD03": "0", "D_MinGenLv03": "0", "D_MinLoyal03": "0", "D_City03": "0",
                "D_General04": "0", "D_StringA04": "0", "D_StringD04": "0", "D_MinGenLv04": "0", "D_MinLoyal04": "0", "D_City04": "0",
                "D_General05": "0", "D_StringA05": "0", "D_StringD05": "0", "D_MinGenLv05": "0", "D_MinLoyal05": "0", "D_City05": "0",
                "D_General06": "0", "D_StringA06": "0", "D_StringD06": "0", "D_MinGenLv06": "0", "D_MinLoyal06": "0", "D_City06": "0",
                "D_General07": "0", "D_StringA07": "0", "D_StringD07": "0", "D_MinGenLv07": "0", "D_MinLoyal07": "0", "D_City07": "0",
                "D_General08": "0", "D_StringA08": "0", "D_StringD08": "0", "D_MinGenLv08": "0", "D_MinLoyal08": "0", "D_City08": "0",
                "D_General09": "0", "D_StringA09": "0", "D_StringD09": "0", "D_MinGenLv09": "0", "D_MinLoyal09": "0", "D_City09": "0",
                "D_General10": "0", "D_StringA10": "0", "D_StringD10": "0", "D_MinGenLv10": "0", "D_MinLoyal10": "0", "D_City10": "0",
                "O_LordString": "0", "O_ShowGeneral": "0", "O_ShowString": "0",
                "N_MinRelation": "0", "N_MinMoney": "0", "N_MaxMoney": "0",
                "N_MinGenNum": "0", "N_MinCityNum": "0", "N_MinPeopleHeart": "0",
                "N_SpecCity01": "0", "N_SpecCity02": "0", "N_SpecCity03": "0", "N_SpecCity04": "0", "N_SpecCity05": "0",
                "N_MinThingNum": "0", "N_OwnThing01": "0", "N_OwnThing02": "0", "N_OwnThing03": "0", "N_OwnThing04": "0", "N_OwnThing05": "0",
                "Thing01": "0", "ThingNum01": "0", "Thing02": "0", "ThingNum02": "0", "Thing03": "0", "ThingNum03": "0",
                "Thing04": "0", "ThingNum04": "0", "Thing05": "0", "ThingNum05": "0", "Thing06": "0", "ThingNum06": "0",
                "Thing07": "0", "ThingNum07": "0", "Thing08": "0", "ThingNum08": "0", "Thing09": "0", "ThingNum09": "0",
                "Thing10": "0", "ThingNum10": "0",
                "Money": "0", "MoneyRatio": "0", "People": "0", "PeopleHeart": "0", "ReserveSoldier": "0",
                "Str": "0", "Int": "0", "HP": "0", "MP": "0",
                "Title01": "0", "Title02": "0", "Title03": "0", "Title04": "0", "Title05": "0",
                "SFMagic": "0", "BFMagic": "0", "GenSkill": "0", "ArmySkill": "0", "ArmyGroupSkill": "0",
                "Relation": "0", "AllianceDay": "0", "BlockNo": "0", "BreakDays": "0", "BlockIndex": "0", "FreeDays": "0",
                "bDead": "0", "F_Relation": "0", "IsUsed": "1", "Version": "1"
            }
        }

