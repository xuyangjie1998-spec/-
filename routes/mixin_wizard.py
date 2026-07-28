import os, json, re, shutil, base64, tempfile, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional
from core.error_codes import safe_error_message, error_response, success_response, ErrorCode

from core.config import WRITE_ROOT, PROJECT_ROOT

from core.event_templates import EVENT_TEMPLATES, generate_event_section

logger = logging.getLogger('San7ModMaker')

__all__ = ['San7ModMakerWizard']

class San7ModMakerWizard:
    """MOD制作器 - 向导与高级编辑 (矩阵/向导/OBD/PCK/事件/代码注入)"""

    # ============================================================
    # API: 兵种相克矩阵
    # ============================================================

    def api_matrix_load(self, soldiers: list) -> dict:
        """加载兵种相克矩阵"""
        return self.soldier_matrix.load_from_soldiers(soldiers)

    def api_matrix_get(self) -> dict:
        """获取矩阵数据"""
        return {
            "success": True,
            "matrix": self.soldier_matrix.get_matrix(),
            "summary": self.soldier_matrix.get_summary(),
            "analysis": self.soldier_matrix.analyze(),
        }

    def api_matrix_update(self, attacker: int, defender: int, value: int) -> dict:
        """更新单个克制值"""
        return self.soldier_matrix.update_cell(attacker, defender, value)

    def api_matrix_get_soldiers(self) -> dict:
        """获取更新后的兵种数据"""
        return {"success": True, "data": self.soldier_matrix.get_soldiers_data()}

    # ============================================================
    # API: MOD制作向导
    # ============================================================

    def api_wizard_templates(self) -> dict:
        """获取所有制作模板"""
        return {"success": True, "templates": self.mod_wizard.get_templates()}

    def api_wizard_start(self, template_id: str) -> dict:
        """开始一个模板"""
        return self.mod_wizard.start_template(template_id)

    def api_wizard_step(self, template_id: str, step: int) -> dict:
        """标记步骤完成"""
        return self.mod_wizard.mark_step_complete(template_id, step)

    def api_wizard_progress(self, template_id: str = None) -> dict:
        """获取进度"""
        return self.mod_wizard.get_progress(template_id)

    # reserved: 预留给未来功能，暂无前端调用
    def api_wizard_dependencies(self, file: str) -> dict:
        """获取文件依赖"""
        return self.mod_wizard.get_file_dependencies(file)

    def api_wizard_get_sample(self, template_id: str) -> dict:
        """获取MOD模板的示例数据"""
        sample = self.mod_wizard.get_sample(template_id)
        return {"success": True, "data": sample}

    def api_wizard_create_general(self, no: int, name: str, str_val: int = 70,
                                   int_val: int = 50, hp: float = 100, mp: int = 30,
                                   justice: int = 80, personality: int = 50, morale: int = 70,
                                   weapon: int = 0, horse: int = 0, formation: int = 0,
                                   sol_type1: int = 1, sol_type2: int = 0,
                                   face_id: int = 0, sex: int = 1, default_title: int = 1,
                                   gen_skills: list = None, army_skills: list = None,
                                   ag_skills: list = None, bf_magic: list = None, sf_magic: list = None,
                                   city1: str = "", city2: str = "", city3: str = "",
                                   city4: str = "", city5: str = "", city6: str = "",
                                   city7: str = "", city8: str = "", city9: str = "", city10: str = "",
                                   lord: int = 0) -> dict:
        """
        一键创建武将：自动联动 General01 + DefSkill + General02 + TermText
        """
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        if no <= 0:
            return {"success": False, "message": "武将编号必须大于0"}

        results = {}
        no_str = str(no)

        # 1. General01.ini
        try:
            path = os.path.join(self.game_path, "Setting", "General01.ini")
            if self.backup_mgr:
                self.backup_mgr.backup_file(path)
            parser = IniParser()
            if os.path.exists(path):
                parser.load(path)
            # 检查是否已存在
            for s in parser.get_all_sections("GENERAL"):
                if str(s.entries.get("No", "")) == no_str:
                    return {"success": False, "message": f"武将编号 {no} 已存在于 General01.ini"}
            section = parser.add_section("GENERAL")
            section.set("No", no_str)
            section.set("Name", name)
            section.set("Str", str(str_val))
            section.set("Int", str(int_val))
            section.set("HP", str(hp))
            section.set("MP", str(mp))
            section.set("Justice", str(justice))
            section.set("Personality", str(personality))
            section.set("Morale", str(morale))
            if weapon: section.set("Weapon", str(weapon))
            if horse: section.set("Horse", str(horse))
            if formation: section.set("Formation", str(formation))
            section.set("SolType1", str(sol_type1))
            if sol_type2: section.set("SolType2", str(sol_type2))
            if face_id: section.set("FaceID", str(face_id))
            section.set("Sex", str(sex))
            if default_title: section.set("DefaultTitle", str(default_title))
            section.set("IsUsed", "1")
            parser.save(path)
            results["general01"] = "OK"
        except Exception as e:
            results["general01_error"] = str(e)

        # 2. DefSkill.ini
        try:
            path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
            if self.backup_mgr:
                self.backup_mgr.backup_file(path)
            parser = IniParser()
            if os.path.exists(path):
                parser.load(path)
            for s in parser.get_all_sections("GenSkill"):
                if str(s.entries.get("No", "")) == no_str:
                    return {"success": False, "message": f"武将编号 {no} 已存在于 DefSkill.ini"}
            section = parser.add_section("GenSkill")
            section.set("No", no_str)
            section.set("Name", name)
            gs = gen_skills or []
            section.set("GenSkill", ",".join(str(x) for x in gs))
            as_ = army_skills or []
            section.set("ArmySkill", ",".join(str(x) for x in as_))
            ags = ag_skills or []
            section.set("ArmyGroupSkill", ",".join(str(x) for x in ags))
            bm = bf_magic or []
            section.set("BFMagic", ",".join(str(x) for x in bm))
            sm = sf_magic or []
            section.set("SFMagic", ",".join(str(x) for x in sm))
            parser.save(path)
            results["defskill"] = "OK"
        except Exception as e:
            results["defskill_error"] = str(e)

        # 3. General02.ini
        try:
            path = os.path.join(self.game_path, "Setting", "General02.ini")
            if self.backup_mgr:
                self.backup_mgr.backup_file(path)
            parser = IniParser()
            if os.path.exists(path):
                parser.load(path)
            for s in parser.get_all_sections("GENERAL"):
                if str(s.entries.get("No", "")) == no_str:
                    return {"success": False, "message": f"武将编号 {no} 已存在于 General02.ini"}
            section = parser.add_section("GENERAL")
            section.set("No", no_str)
            section.set("Name", name)
            city_map = {1: city1, 2: city2, 3: city3, 4: city4, 5: city5,
                        6: city6, 7: city7, 8: city8, 9: city9, 10: city10}
            for i in range(1, 11):
                val = city_map.get(i, "")
                if val:
                    section.set(f"City{i}", val)
                else:
                    section.set(f"City{i}", "")
            section.set("IsUsed", "1")
            if lord:
                section.set("RLord", str(lord))
            parser.save(path)
            results["general02"] = "OK"
        except Exception as e:
            results["general02_error"] = str(e)

        # 4. TermText.ini
        try:
            if self.term_text.is_loaded():
                string_id = 25000 + no
                self.term_text.allocate_new_id(name)
                results["termtext"] = f"String={string_id}"
            else:
                results["termtext_skip"] = "TermText未加载"
        except Exception as e:
            results["termtext_error"] = str(e)

        results["success"] = (results.get("general01") == "OK" and
                              results.get("defskill") == "OK" and
                              results.get("general02") == "OK")
        results["message"] = f"已为武将 {name} (No.{no}) 创建 General01 + DefSkill + General02 + TermText"
        return results

    def api_wizard_create_soldier(self, no: int, name: str, level: int = 1,
                                   upgrade: int = 0, hp: int = 50, atk: int = 10,
                                   def_val: int = 5, speed: int = 6, range_val: int = 1,
                                   cost: int = 100, troop_count: int = 1,
                                   hit_sol1: int = 0, hit_sol2: int = 0,
                                   obj_id: int = 0, is_used: int = 1) -> dict:
        """
        一键创建兵种：自动联动 Soldier.ini + TermText.ini + OBD模型
        """
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)

        if no <= 0:
            return {"success": False, "message": "兵种编号必须大于0"}

        results = {}
        no_str = str(no)

        # 1. Soldier.ini（使用正确的字段名）
        try:
            path = os.path.join(self.game_path, "Setting", "Soldier.ini")
            if self.backup_mgr:
                self.backup_mgr.backup_file(path)
            parser = IniParser()
            if os.path.exists(path):
                parser.load(path)
            for s in parser.get_all_sections("SOLDIER"):
                if str(s.entries.get("No", "")) == no_str:
                    return {"success": False, "message": f"兵种编号 {no} 已存在于 Soldier.ini"}
            section = parser.add_section("SOLDIER")
            section.set("No", no_str)
            section.set("Name", name)
            section.set("Rank", str(level))
            section.set("Upgrade", str(upgrade))
            section.set("Life", str(hp))
            section.set("BasePower", str(atk))
            section.set("AddPower", str(def_val))
            section.set("Speed", str(speed))
            section.set("DetectRangeMax", str(range_val))
            section.set("IsUsed", str(is_used))
            # 默认值
            section.set("Str", "1.0")
            section.set("Int", "1.0")
            section.set("Interval", "65")
            section.set("DetectRangeMin", "1")
            section.set("Height", "150")
            section.set("Type", "1")
            section.set("Color", "10")
            section.set("SizeX", "1")
            section.set("Sex", "0")
            section.set("DieMode", "0")
            section.set("OffsetZ", "0")
            section.set("Horse", "0")
            section.set("Weapon", "0")
            section.set("WeaponSpeed", "0")
            section.set("SuperHit", "0")
            section.set("Feature", "0")
            section.set("Special", "0")
            section.set("OrderNo", "0")
            section.set("Data01", "0")
            section.set("Data02", "0")
            section.set("Data03", "0")
            if hit_sol1: section.set("HitSol1", str(hit_sol1))
            if hit_sol2: section.set("HitSol2", str(hit_sol2))
            parser.save(path)
            results["soldier"] = "OK"
        except Exception as e:
            results["soldier_error"] = str(e)

        # 2. TermText.ini (兵种名=13000+No, 说明=13500+No)
        try:
            if self.term_text.is_loaded():
                self.term_text.allocate_new_id(name)
                results["termtext"] = f"String={13000 + no}"
            else:
                results["termtext_skip"] = "TermText未加载"
        except Exception as e:
            results["termtext_error"] = str(e)

        # 3. OBD 模型联动创建
        actual_obj_id = obj_id
        try:
            self.obd_parser.load("bfsoldier")
            seq = self.obd_parser.find_free_sequence()
            obj = OBDObject()
            obj.sequence = seq
            obj.name = name
            obj.space = (0, 0, 0)
            self.obd_parser.objects.append(obj)
            self.obd_parser.save("bfsoldier", self.obd_parser.objects)
            actual_obj_id = seq % 100
            results["obd"] = f"Sequence={seq}, ObjID={actual_obj_id}"
            # 回写 ObjID 到 Soldier.ini
            if results.get("soldier") == "OK":
                try:
                    parser2 = IniParser()
                    parser2.load(path)
                    for s in parser2.get_all_sections("SOLDIER"):
                        if str(s.entries.get("No", "")) == no_str:
                            s.set("ObjID", str(actual_obj_id))
                            break
                    parser2.save(path)
                except Exception as e:
                    logger.error(f"操作失败: {e}")
                    pass
        except Exception as e:
            results["obd_error"] = str(e)
            if not actual_obj_id:
                actual_obj_id = no % 100

        # 如果传入了 obj_id 但 OBD 创建失败，回退
        if obj_id and not results.get("obd"):
            try:
                parser3 = IniParser()
                parser3.load(path)
                for s in parser3.get_all_sections("SOLDIER"):
                    if str(s.entries.get("No", "")) == no_str:
                        s.set("ObjID", str(obj_id))
                        break
                parser3.save(path)
            except Exception as e:
                logger.error(f"操作失败: {e}")
                pass
        elif actual_obj_id:
            try:
                parser3 = IniParser()
                parser3.load(path)
                for s in parser3.get_all_sections("SOLDIER"):
                    if str(s.entries.get("No", "")) == no_str:
                        s.set("ObjID", str(actual_obj_id))
                        break
                parser3.save(path)
            except Exception as e:
                logger.error(f"操作失败: {e}")
                pass

        results["success"] = results.get("soldier") == "OK"
        results["message"] = f"已为兵种 {name} (No.{no}) 创建 Soldier + TermText + OBD模型"
        if actual_obj_id:
            results["obj_id"] = actual_obj_id
        return results

    # ============================================================
    # API: 一键创建势力向导
    # ============================================================

    def api_wizard_create_nation(self, no: int, name: str, color: int = 0,
                                  lord: int = 0, advisor: int = 0, capital: int = 0,
                                  cities: str = "", generals: str = "",
                                  money: int = 10000, food: int = 50000,
                                  soldier: int = 10000, bgm: int = 8) -> dict:
        """
        一键创建势力：自动联动 Nation.ini + Color.ini + City.ini + City01-10.ini + General01.ini + TermText
        """
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if no <= 0:
            return {"success": False, "message": "势力编号必须大于0"}
        results = {}
        no_str = str(no)

        # 1. Nation.ini
        try:
            path = os.path.join(self.game_path, "Setting", "Nation.ini")
            if self.backup_mgr:
                self.backup_mgr.backup_file(path)
            parser = IniParser()
            if os.path.exists(path):
                parser.load(path)
            for s in parser.get_all_sections("NATION"):
                if str(s.entries.get("No", "")) == no_str:
                    return {"success": False, "message": f"势力编号 {no} 已存在"}
            section = parser.add_section("NATION")
            section.set("No", no_str)
            section.set("Name", name)
            section.set("Color", str(color))
            section.set("Lord", str(lord))
            section.set("Advisor", str(advisor))
            section.set("Capital", str(capital))
            section.set("Cities", cities)
            section.set("Generals", generals)
            section.set("Money", str(money))
            section.set("Food", str(food))
            section.set("Soldier", str(soldier))
            section.set("BGM", str(bgm))
            section.set("IsUsed", "1")
            parser.save(path)
            results["nation"] = "OK"
        except Exception as e:
            results["nation_error"] = str(e)

        # 2. Color.ini
        try:
            cpath = os.path.join(self.game_path, "Setting", "Color.ini")
            parser = IniParser()
            if os.path.exists(cpath):
                parser.load(cpath)
            section = parser.add_section("COLOR")
            section.set("No", no_str)
            section.set("R", "255")
            section.set("G", "0")
            section.set("B", "0")
            parser.save(cpath)
            results["color"] = "OK"
        except Exception as e:
            results["color_error"] = str(e)

        # 3. City.ini
        try:
            city_path = os.path.join(self.game_path, "Setting", "City.ini")
            parser = IniParser()
            if os.path.exists(city_path):
                parser.load(city_path)
            section = parser.add_section("CITY")
            section.set("No", str(capital or no))
            section.set("Name", name + "城")
            section.set("Owner", no_str)
            parser.save(city_path)
            results["city"] = "OK"
        except Exception as e:
            results["city_error"] = str(e)

        # 4. City01-10.ini (10个剧本)
        for i in range(1, 11):
            try:
                cpath = os.path.join(self.game_path, "Setting", f"City{i:02d}.ini")
                if os.path.exists(cpath):
                    parser = IniParser()
                    parser.load(cpath)
                    section = parser.add_section("CITY")
                    section.set("No", str(capital))
                    section.set("Owner", no_str)
                    section.set("Soldier", "500")
                    section.set("HP", "500")
                    parser.save(cpath)
            except Exception as e:
                logger.error(f"操作失败: {e}")
                pass
        results["city_periods"] = "OK"

        # 5. TermText
        try:
            if self.term_text.is_loaded():
                self.term_text.allocate_new_id(name)
                results["termtext"] = "OK"
        except Exception as e:
            logger.error(f"操作失败: {e}")
            results["termtext_skip"] = "TermText未加载"

        results["success"] = results.get("nation") == "OK"
        results["message"] = f"已为势力 {name} (No.{no}) 创建 Nation + Color + City + City01-10 + TermText"
        return results

    # ============================================================
    # API: 一键创建物品向导
    # ============================================================

    def api_wizard_create_item(self, no: int, name: str, item_type: int = 2,
                                price: int = 100, is_rare: int = 0,
                                icon_id: int = 0, script_no: int = 0,
                                level: int = 1, str_val: int = 0,
                                int_val: int = 0, hp_val: int = 0,
                                mp_val: int = 0, desc: str = "") -> dict:
        """
        一键创建物品：自动联动 Thing.ini + TermText(名称+描述)
        """
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if no <= 0:
            return {"success": False, "message": "物品编号必须大于0"}
        results = {}
        no_str = str(no)

        # 1. Thing.ini
        try:
            path = os.path.join(self.game_path, "Setting", "Thing.ini")
            if self.backup_mgr:
                self.backup_mgr.backup_file(path)
            parser = IniParser()
            if os.path.exists(path):
                parser.load(path)
            for s in parser.get_all_sections("THING"):
                if str(s.entries.get("No", "")) == no_str:
                    return {"success": False, "message": f"物品编号 {no} 已存在"}
            section = parser.add_section("THING")
            section.set("No", no_str)
            section.set("Name", name)
            section.set("Type", str(item_type))
            section.set("IconID", str(icon_id))
            section.set("Price", str(price))
            section.set("Level", str(level))
            section.set("IsRare", str(is_rare))
            section.set("Count", "1")
            section.set("ScriptNo", str(script_no))
            section.set("Str", str(str_val))
            section.set("Int", str(int_val))
            section.set("HP", str(hp_val))
            section.set("MP", str(mp_val))
            section.set("IsUsed", "1")
            parser.save(path)
            results["thing"] = "OK"
        except Exception as e:
            results["thing_error"] = str(e)

        # 2. TermText
        try:
            if self.term_text.is_loaded():
                self.term_text.set_item_name(no, name)
                item_desc = desc if desc else f"{name}的描述"
                self.term_text.set_item_desc(no, item_desc)
                results["termtext"] = "OK"
        except Exception as e:
            logger.error(f"操作失败: {e}")
            results["termtext_skip"] = "TermText未加载"

        results["success"] = results.get("thing") == "OK"
        results["message"] = f"已为物品 {name} (No.{no}) 创建 Thing + TermText"
        return results

    # ============================================================
    # API: OBD模型编辑
    # ============================================================

    def api_obd_load(self, obd_type: str = "bfsoldier") -> dict:
        """加载OBD模型数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            objects = self.obd_parser.load(obd_type)
            return {
                "success": True,
                "data": self.obd_parser.to_dict_list(),
                "count": len(objects),
                "sprite_types": self.obd_parser.get_sprite_types(),
            }
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_obd_save(self, obd_type: str, data: list) -> dict:
        """保存OBD模型数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            objects = [OBDObject.from_dict(d) for d in data]
            path = self.obd_parser.save(obd_type, objects)
            return {"success": True, "message": f"保存成功，共{len(objects)}个模型", "path": path}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_obd_new_object(self, obd_type: str = "bfsoldier") -> dict:
        """创建新OBD对象"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            self.obd_parser.load(obd_type)
            seq = self.obd_parser.find_free_sequence()
            obj = OBDObject()
            obj.sequence = seq
            obj.name = f"新模型_{seq}"
            return {"success": True, "data": obj.to_dict(), "sequence": seq}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_obd_delete(self, obd_type: str, sequence: int) -> dict:
        """删除指定OBD模型对象"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            self.obd_parser.load(obd_type)
            obj = self.obd_parser.find_by_sequence(sequence)
            if not obj:
                return {"success": False, "message": f"未找到 Sequence={sequence} 的模型"}
            if self.backup_mgr:
                file_path = os.path.join(self.game_path, "Setting", "OBD", self.obd_parser.OBD_FILES[obd_type])
                self.backup_mgr.backup_file(file_path)
            self.obd_parser.objects.remove(obj)
            self.obd_parser.save(obd_type)
            return {"success": True, "message": f"已删除模型 Sequence={sequence}"}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_list_obd_models(self, obd_type: str = "bfsoldier") -> dict:
        """列出指定OBD类型的所有模型（仅返回关键信息，供兵种编辑器使用）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            self.obd_parser.load(obd_type)
            models = []
            for obj in self.obd_parser.objects:
                models.append({
                    "sequence": obj.sequence,
                    "name": obj.name or "",
                    "obj_id": obj.sequence % 100,
                    "action_count": len(getattr(obj, 'sprites', {})),
                })
            return success_response({"data": models, "count": len(models)})
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_obd_get_info(self) -> dict:
        """获取OBD格式信息"""
        return OBDParser.get_info()

    def api_obd_get_sprites(self, obd_type: str, sequence: int) -> dict:
        """获取指定OBD对象的Sprite帧列表"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            self.obd_parser.load(obd_type)
            obj = self.obd_parser.find_by_sequence(sequence)
            if not obj:
                return {"success": False, "message": f"未找到Sequence={sequence}的对象"}
            return {
                "success": True,
                "sequence": sequence,
                "name": obj.name,
                "sprites": {k: v for k, v in obj.sprites.items()},
                "sprite_types": OBDObject.SPRITE_TYPES,
                "sprite_count": len(obj.sprites),
            }
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    # reserved: 预留给未来功能，暂无前端调用
    def api_obd_update_sprites(self, obd_type: str, sequence: int, sprites: dict) -> dict:
        """更新OBD对象的Sprite帧"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            self.obd_parser.load(obd_type)
            obj = self.obd_parser.find_by_sequence(sequence)
            if not obj:
                return {"success": False, "message": f"未找到Sequence={sequence}的对象"}
            obj.sprites = OrderedDict(sprites)
            self.obd_parser.save(obd_type, self.obd_parser.objects)
            return {"success": True, "message": f"已更新 {len(sprites)} 个Sprite帧"}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_obd_copy_to(self, source_type: str, target_type: str, sequence: int) -> dict:
        """跨文件复制OBD模型（如 NPC→武将）"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            self.obd_parser.load(source_type)
            src_obj = self.obd_parser.find_by_sequence(sequence)
            if not src_obj:
                return {"success": False, "message": f"源文件 {source_type} 中未找到 Sequence={sequence}"}
            # 在目标文件中分配新Sequence
            self.obd_parser.load(target_type)
            new_seq = self.obd_parser.find_free_sequence()
            new_obj = OBDObject()
            new_obj.sequence = new_seq
            new_obj.name = src_obj.name + "_导入"
            new_obj.space = src_obj.space
            new_obj.sprites = src_obj.sprites
            new_obj.extra = dict(src_obj.extra)
            self.obd_parser.objects.append(new_obj)
            self.obd_parser.save(target_type, self.obd_parser.objects)
            return {
                "success": True,
                "message": f"已从 {source_type} 复制到 {target_type}，新Sequence={new_seq}",
                "new_sequence": new_seq,
                "new_obj_id": new_obj.get_obj_id(),
                "data": new_obj.to_dict(),
            }
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_obd_preview_sprite_frame(self, obd_type: str, sequence: int, sprite_type: str, frame_index: int = 0) -> dict:
        """预览OBD中指定动作的指定帧图像（返回base64 PNG）"""
        if not HAS_PIL:
            return {"success": False, "message": "PIL库不可用"}
        if not self.game_path:
            return {"success": False, "message": "未配置游戏目录"}
        try:
            objects = self.obd_parser.load(obd_type)
            obj = None
            for o in objects:
                if o.sequence == sequence:
                    obj = o
                    break
            if not obj:
                return {"success": False, "message": f"未找到Sequence={sequence}的对象"}
            sprite_params = obj.get_sprite(sprite_type)
            if not sprite_params or frame_index >= len(sprite_params):
                return {"success": False, "message": f"动作{sprite_type}的第{frame_index}帧不存在"}
            # 帧参数格式: 文件名, #帧数, 文件名, #帧数, ...
            # 实际SHP文件名就是参数中的非#开头的条目
            frame_name = None
            frame_count = 0
            for param in sprite_params:
                if param.startswith('#'):
                    continue
                if param.startswith('@'):
                    continue
                if frame_count == frame_index:
                    frame_name = param
                    break
                frame_count += 1
            if not frame_name:
                # 尝试直接用第一个非#参数
                for param in sprite_params:
                    if not param.startswith('#') and not param.startswith('@'):
                        frame_name = param
                        break
            if not frame_name:
                return {"success": False, "message": "无法解析帧文件名"}
            # 查找帧文件: Shape/BFObj/BFSoldier/{sequence后两位}/{frame_name}.shp
            import os as _os
            obj_id = sequence % 100
            bfobj_dir = _os.path.join(self.game_path, "Shape", "BFObj", "BFSoldier", f"{obj_id:03d}")
            shp_path = _os.path.join(bfobj_dir, f"{frame_name}.shp")
            if not _os.path.exists(shp_path):
                # 尝试其他子目录
                for subdir in ["BFGen", "BFHorse", "BFWeapon", "BFSpec"]:
                    alt_dir = _os.path.join(self.game_path, "Shape", "BFObj", subdir, f"{obj_id:03d}")
                    alt_path = _os.path.join(alt_dir, f"{frame_name}.shp")
                    if _os.path.exists(alt_path):
                        shp_path = alt_path
                        break
            if not _os.path.exists(shp_path):
                return {"success": False, "message": f"帧文件不存在: {frame_name}.shp"}
            img = self.shp_converter._load_shp_file(shp_path)
            if img:
                buf = BytesIO()
                img.save(buf, "PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                return {"success": True, "image_base64": b64, "size": f"{img.width}x{img.height}", "frame_name": frame_name}
            return {"success": False, "message": "SHP解析失败"}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_obd_list_sprite_frames(self, obd_type: str, sequence: int) -> dict:
        """列出OBD对象所有动作的帧列表"""
        objects = self.obd_parser.load(obd_type)
        obj = None
        for o in objects:
            if o.sequence == sequence:
                obj = o
                break
        if not obj:
            return {"success": False, "message": f"未找到Sequence={sequence}的对象"}
        result = {"success": True, "sequence": sequence, "name": obj.name, "actions": {}}
        for sprite_type, params in obj.sprites.items():
            frames = [p for p in params if not p.startswith('#') and not p.startswith('@')]
            result["actions"][sprite_type] = {
                "frame_count": len(frames),
                "frames": frames,
                "all_params": params,
            }
        return result

    # ============================================================
    # API: PCK资源管理
    # ============================================================

    def api_pck_detect(self) -> dict:
        """检测游戏目录PCK状态"""
        return self.pck_mgr.detect_game_state()

    def api_pck_list_files(self, pck_name: str = "Patch.pck") -> dict:
        """列出PCK包内文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        # 路径遍历防护：只允许安全的PCK文件名
        safe_name = os.path.basename(pck_name)
        if safe_name != pck_name or '..' in pck_name:
            return {"success": False, "message": "无效的PCK文件名"}
        pck_path = os.path.join(self.game_path, safe_name)
        if not os.path.exists(pck_path):
            return {"success": False, "message": f"未找到 {pck_name}"}
        files = self.pck_mgr.get_pck_files_list(pck_path)
        return {"success": True, "files": files, "count": len(files)}

    def api_pck_extract_all(self, pck_name: str = "Patch.pck") -> dict:
        """从PCK提取所有文件到游戏目录"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        safe_name = os.path.basename(pck_name)
        if safe_name != pck_name or '..' in pck_name:
            return {"success": False, "message": "无效的PCK文件名"}
        pck_path = os.path.join(self.game_path, safe_name)
        if not os.path.exists(pck_path):
            return {"success": False, "message": f"未找到 {pck_name}"}
        result = self.pck_mgr.extract_all_from_pck(pck_path, self.game_path)
        return result

    # reserved: 预留给未来功能，暂无前端调用
    def api_pck_extract_file(self, pck_name: str, internal_path: str) -> dict:
        """从PCK提取单个文件"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        safe_name = os.path.basename(pck_name)
        safe_internal = os.path.basename(internal_path)
        if safe_name != pck_name or '..' in pck_name or '..' in internal_path:
            return {"success": False, "message": "无效的文件路径"}
        pck_path = os.path.join(self.game_path, safe_name)
        output_path = os.path.join(self.game_path, safe_internal)
        ok = self.pck_mgr.extract_pck_file(pck_path, internal_path, output_path)
        return {"success": ok, "extracted_path": output_path if ok else None}

    # reserved: 预留给未来功能，暂无前端调用
    def api_pck_prepare_setting(self) -> dict:
        """准备Setting文件夹（自动检测+提取）"""
        return self.pck_mgr.prepare_setting_folder()

    def api_pck_get_setting_status(self) -> dict:
        """获取Setting文件夹详细状态"""
        return self.pck_mgr.get_setting_status()

    def api_pck_get_info(self) -> dict:
        """获取PCK格式信息"""
        return PckManager.get_info()

    def api_pck_repack(self) -> dict:
        """重新打包 Setting/ 为 Patch.pck"""
        return self.pck_mgr.repack_patch()

    # reserved: 预留给未来功能，暂无前端调用
    def api_shape_pck_extract(self, pck_name: str) -> dict:
        """从 Shape*.pck 提取 SHP 资源"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.pck_mgr.extract_shape_pck(pck_name)

    def api_shape_pck_extract_all(self) -> dict:
        """批量提取所有 Shape*.pck"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.pck_mgr.extract_all_shape_pcks()

    def api_shape_pck_repack(self, pck_name: str = "Shape00.pck") -> dict:
        """将 Shape/ 目录重新打包为 Shape*.pck"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.pck_mgr.repack_shape_pck(pck_name)

    # ============================================================
    # CSV 导入导出
    # ============================================================

    def api_csv_export(self, setting_name: str, output_path: str = None) -> dict:
        """根据 setting_name 导出 INI 数据为 CSV 文件

        Args:
            setting_name: Schema 名称，对应 _get_batch_schemas() 的 key（如 "General01.ini"）
            output_path: 可选的输出路径，默认保存到 Setting 目录下同名 .csv
        """
        try:
            # 1. 查找 Schema
            schemas = self._get_batch_schemas()
            schema = schemas.get(setting_name)
            if not schema:
                # 尝试通过 label 前缀匹配
                for key, s in schemas.items():
                    if s.get("label", "").startswith(setting_name):
                        schema = s
                        setting_name = key
                        break
            if not schema:
                return {"success": False, "message": f"未找到对应的 Schema: {setting_name}"}

            section_name = schema.get("section", "")
            ini_path = os.path.join(self.game_path, "Setting", setting_name)
            if not os.path.exists(ini_path):
                return {"success": False, "message": f"INI 文件不存在: {ini_path}"}

            # 2. 加载 INI 数据
            parser = IniParser()
            parser.load(ini_path)
            sections = parser.get_all_sections(section_name)
            data = [dict(s.entries) for s in sections]

            if not data:
                return {"success": False, "message": "没有数据可导出"}

            # 3. 确定输出路径
            if output_path is None:
                output_path = os.path.join(
                    os.path.dirname(ini_path),
                    f"{setting_name.replace('.ini', '')}.csv"
                )

            # 4. 导出 CSV（utf-8-sig BOM）
            import csv
            fields = schema.get("fields", [])
            if not fields and data:
                fields = list(data[0].keys())

            with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(data)

            return {"success": True, "message": f"成功导出 {len(data)} 条记录", "path": output_path}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_csv_import(self, setting_name: str, csv_path: str) -> dict:
        """根据 setting_name 从 CSV 文件导入数据到对应 INI 文件

        Args:
            setting_name: Schema 名称，对应 _get_batch_schemas() 的 key（如 "General01.ini"）
            csv_path: CSV 文件路径，第一行为表头
        """
        try:
            # 1. 查找 Schema
            schemas = self._get_batch_schemas()
            schema = schemas.get(setting_name)
            if not schema:
                # 尝试通过 label 前缀匹配
                for key, s in schemas.items():
                    if s.get("label", "").startswith(setting_name):
                        schema = s
                        setting_name = key
                        break
            if not schema:
                return {"success": False, "message": f"未找到对应的 Schema: {setting_name}"}

            section_name = schema.get("section", "")
            ini_path = os.path.join(self.game_path, "Setting", setting_name)
            if not os.path.exists(ini_path):
                return {"success": False, "message": f"INI 文件不存在: {ini_path}"}
            if not os.path.exists(csv_path):
                return {"success": False, "message": f"CSV 文件不存在: {csv_path}"}

            # 2. 备份目标文件
            if self.backup_mgr:
                self.backup_mgr.backup_file(ini_path)

            # 3. 读取 CSV 文件（支持 utf-8 和 gbk 编码）
            import csv
            rows = None
            for encoding in ["utf-8", "gbk"]:
                try:
                    with open(csv_path, "r", encoding=encoding) as f:
                        reader = csv.DictReader(f)
                        rows = list(reader)
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            if rows is None:
                return {"success": False, "message": "无法读取 CSV 文件或文件编码不支持"}

            if not rows:
                return {"success": False, "message": "CSV 文件为空或无有效数据行"}

            # 4. 将 CSV 数据转换为 INI entries 列表
            entries = []
            for row in rows:
                entry = dict(row)
                entries.append(entry)

            # 5. 使用 IniParser 写入
            parser = IniParser()
            parser.load(ini_path)
            parser.replace_sections(section_name, entries, "No")
            parser.save(ini_path)

            return {"success": True, "message": f"成功导入 {len(entries)} 条记录", "count": len(entries)}
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_csv_confirm_import(self, data_type: str, file_path: str) -> dict:
        """确认导入 CSV 数据"""
        try:
            return self.csv_manager.import_csv(data_type, file_path)
        except Exception as e:
            return error_response(ErrorCode.INTERNAL, safe_error_message(e))

    def api_csv_get_fields(self, data_type: str) -> dict:
        """获取指定数据类型的标准字段列表"""
        fields = self.csv_manager.get_field_map(data_type)
        if fields:
            return {"success": True, "data": fields}
        return {"success": False, "message": f"不支持的数据类型: {data_type}"}

    def api_encoding_scan(self) -> dict:
        """扫描 Setting/ 目录下所有 INI 文件编码"""
        return self.encoding_converter.batch_scan()

    def api_encoding_preview(self, file_path: str, target_encoding: str = "gbk") -> dict:
        """预览文件编码转换"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if '..' in file_path or os.path.isabs(file_path):
            return {"success": False, "message": "非法的文件路径"}
        full_path = os.path.join(self.game_path, "Setting", file_path)
        if not os.path.realpath(full_path).startswith(os.path.realpath(self.game_path)):
            return {"success": False, "message": "非法的文件路径"}
        return self.encoding_converter.preview_conversion(full_path, target_encoding)

    def api_encoding_convert_file(self, file_path: str, target_encoding: str = "gbk") -> dict:
        """转换单个文件编码"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        if '..' in file_path or os.path.isabs(file_path):
            return {"success": False, "message": "非法的文件路径"}
        full_path = os.path.join(self.game_path, "Setting", file_path)
        if not os.path.realpath(full_path).startswith(os.path.realpath(self.game_path)):
            return {"success": False, "message": "非法的文件路径"}
        return self.encoding_converter.convert_file(full_path, target_encoding)

    def api_encoding_batch_convert(self, target_encoding: str = "gbk") -> dict:
        """批量转换所有 INI 文件编码"""
        return self.encoding_converter.batch_convert(target_encoding=target_encoding)

    # ============================================================
    # API: 剧情事件模板
    # ============================================================

    def api_event_templates(self) -> dict:
        """返回所有剧情事件模板"""
        return {"success": True, "templates": EVENT_TEMPLATES}

    def api_event_generate(self, class_type: str, params: dict) -> dict:
        """根据模板和参数生成 History.ini 片段"""
        if not class_type or class_type not in EVENT_TEMPLATES:
            return {"success": False, "message": "未知的 ClassType: " + str(class_type)}
        section = generate_event_section(class_type, params)
        return {"success": True, "section": section}

    def _get_data_by_type(self, data_type: str) -> list:
        """根据数据类型获取当前编辑器数据"""
        data_map = {
            "general": self._general_cache,
            "soldier": self._soldier_cache,
            "thing": self._thing_cache,
            "skill": self._skill_cache,
            "formation": self._formation_cache,
            "title": self._title_cache,
            "scenario": self._scenario_cache,
            "nation": self._nation_cache,
            "city": self._city_cache,
        }
        return data_map.get(data_type, [])

    # ============================================================
    # V3.12.0: MOD 打包分发系统 (mod_packager)
    # ============================================================

    def api_analyze_mod_structure(self, mod_path: str) -> dict:
        """分析 MOD 目录结构"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.mod_packager.analyze_mod(mod_path)

    def api_resolve_mod_deps(self, mod_path: str) -> dict:
        """解析 MOD 依赖关系"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.mod_packager.resolve_dependencies(mod_path, self.game_path)

    def api_generate_mod_installer(self, package_path: str, output_path: str = None) -> dict:
        """生成自解压安装器"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.mod_packager.generate_installer(package_path, output_path)

    def api_detect_mod_conflicts_v2(self, mod1_path: str, mod2_path: str) -> dict:
        """检测两个 MOD 之间的冲突"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.mod_packager.detect_conflicts(mod1_path, mod2_path)

    def api_resolve_mod_conflicts_v2(self, mod1_path: str, mod2_path: str, strategy: str = "auto") -> dict:
        """解决两个 MOD 之间的冲突"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.mod_packager.resolve_conflicts(mod1_path, mod2_path, strategy)

    def api_generate_mod_readme(self, mod_path: str, output_path: str = None) -> dict:
        """生成 MOD README 文档"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.mod_packager.generate_readme(mod_path, output_path)

    def api_version_bump_mod(self, mod_path: str, level: str = "patch") -> dict:
        """MOD 版本号升级"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.mod_packager.version_bump(mod_path, level)

    def api_create_mod_snapshot_v2(self, mod_path: str) -> dict:
        """创建 MOD 快照"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.mod_packager.create_snapshot(mod_path)

    def api_compare_mod_snapshots(self, snapshot1: str, snapshot2: str) -> dict:
        """对比两个 MOD 快照"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.mod_packager.compare_snapshots(snapshot1, snapshot2)

    # ============================================================
    # V3.12.0: TermText 智能编号分配器 (termtext_allocator)
    # ============================================================

    def api_allocate_termtext_id(self, content_type: str, preferred_text: str = None) -> dict:
        """分配 TermText 编号"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.termtext_allocator.allocate_id(content_type, preferred_text)

    def api_allocate_termtext_batch(self, requests) -> dict:
        """批量分配 TermText 编号"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.termtext_allocator.allocate_batch(requests)

    def api_detect_termtext_conflicts(self, termtext_path: str = None) -> dict:
        """检测 TermText 编号冲突"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.termtext_allocator.detect_conflicts(termtext_path)

    def api_resolve_termtext_conflicts(self, strategy: str = "auto") -> dict:
        """解决 TermText 编号冲突"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.termtext_allocator.resolve_conflicts(strategy)

    def api_migrate_termtext_ids(self, mapping) -> dict:
        """迁移 TermText 编号"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.termtext_allocator.migrate_ids(mapping)

    def api_get_termtext_segment_info(self, content_type: str) -> dict:
        """获取 TermText 编号段信息"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.termtext_allocator.get_segment_info(content_type)

    def api_get_termtext_all_segments(self) -> dict:
        """获取所有 TermText 编号段"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.termtext_allocator.get_all_segments()

    def api_smart_allocate_termtext(self, content_type: str, count: int, contiguous: bool = False) -> dict:
        """智能分配 TermText 编号"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.termtext_allocator.smart_allocate(content_type, count, contiguous)

    def api_cross_file_termtext_detect(self, file_paths) -> dict:
        """跨文件 TermText 编号检测"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.termtext_allocator.cross_file_detect(file_paths)

    def api_generate_termtext_report(self) -> dict:
        """生成 TermText 分配报告"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.termtext_allocator.generate_allocation_report()

    def api_auto_remediate_termtext(self) -> dict:
        """自动修复 TermText 编号问题"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.termtext_allocator.auto_remediate()

    # ============================================================
    # 启动
    # ============================================================

    def run(self):
        """启动应用"""
        try:
            import webview
        except ImportError:
            logger.error("请先安装 pywebview: pip install pywebview")
            sys.exit(1)

        # 创建API暴露对象
        api = _JsApi(self)
        html_path = os.path.join(PROJECT_ROOT, "web", "index.html")

        if not os.path.exists(html_path):
            logger.error(f"前端文件不存在: {html_path}")
            sys.exit(1)

        try:
            window = webview.create_window(
                title="San7ModMaker - 三国群英传7 MOD制作器 V3.13.0",
                url=html_path,
                js_api=api,
                width=1280,
                height=860,
                min_size=(1024, 700),
                resizable=True,
            )

            webview.start(debug=False)
        except Exception as e:
            logger.error(f"窗口启动失败: {e}")
            # 尝试弹窗报错
            try:
                import tkinter.messagebox as mb
                mb.showerror("启动失败", f"San7ModMaker 无法启动窗口:\n\n{str(e)[:200]}\n\n"
                           "请确认:\n"
                           "  Windows: 已安装 pythonnet 和 WebView2 Runtime\n"
                           "  Linux: 已安装 GTK3 或 Qt5")
            except Exception as e:
                logger.error(f"操作失败: {e}")
                pass
            sys.exit(1)


    # ============================================================
    # V3.12.0: INI 模板化数据生成引擎 (ini_template)
    # ============================================================

    def api_create_data_template(self, template_name: str, data_type: str, fields: list, rules: dict = None) -> dict:
        """创建数据模板"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.ini_template.create_template(template_name, data_type, fields, rules)

    def api_save_template(self, template: dict, filepath: str = None) -> dict:
        """保存模板到文件"""
        return self.ini_template.save_template(template, filepath)

    def api_load_template(self, filepath: str) -> dict:
        """从文件加载模板"""
        return self.ini_template.load_template(filepath)

    def api_list_templates(self) -> dict:
        """列出所有可用模板"""
        return self.ini_template.list_templates()

    def api_delete_template(self, template_name: str) -> dict:
        """删除模板"""
        return self.ini_template.delete_template(template_name)

    def api_generate_from_template(self, template_name: str, count: int, overrides: dict = None) -> dict:
        """从模板批量生成数据"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.ini_template.generate_from_template(template_name, count, overrides)

    def api_generate_cross_file(self, templates: list, relationships: list) -> dict:
        """跨文件批量生成"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.ini_template.generate_cross_file(templates, relationships)

    def api_batch_generate_templates(self, requests: list) -> dict:
        """批量生成请求"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.ini_template.batch_generate(requests)

    def api_validate_cross_file_data(self, generated_data: dict) -> dict:
        """验证跨文件数据一致性"""
        return self.ini_template.validate_cross_file(generated_data)

    def api_get_preset_templates(self) -> dict:
        """获取内置预设模板"""
        return self.ini_template.get_preset_templates()

    def api_merge_templates(self, base_template: str, overlay_templates: list) -> dict:
        """合并多个模板"""
        return self.ini_template.merge_templates(base_template, overlay_templates)

    def api_apply_template_overrides(self, data: dict, overrides: dict) -> dict:
        """应用字段覆盖"""
        return self.ini_template.apply_overrides(data, overrides)

    def api_transform_template_data(self, data: dict, transformations: list) -> dict:
        """数据转换"""
        return self.ini_template.transform_data(data, transformations)

    # ============================================================
    # V3.12.0: 引擎突破 — Script.so 深层逆向
    # ============================================================

    def api_build_scriptso_cfg(self, start_address: int = None, max_blocks: int = 500) -> dict:
        """构建 Script.so 控制流图"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.scriptso_analyzer.build_cfg(start_address, max_blocks)

    def api_find_scriptso_vtables(self) -> dict:
        """识别 Script.so 虚函数表"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.scriptso_analyzer.find_vtables()

    def api_inject_scriptso_code_cave(self, cave_address: int, machine_code_hex: str, hook_address: int = None) -> dict:
        """向 Script.so Code Cave 注入代码"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            machine_code = bytes.fromhex(machine_code_hex.replace(" ", ""))
        except ValueError:
            return {"success": False, "message": "无效的十六进制机器码"}
        return self.scriptso_analyzer.inject_code_cave(cave_address, machine_code, hook_address)

    # ============================================================
    # V3.12.0: 引擎突破 — SG7-XX.sav 深度格式逆向
    # ============================================================

    def api_deep_parse_sg7_save(self, save_name: str = None) -> dict:
        """深度解析 SG7-XX.sav 场景存档"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.deep_parse_sg7_save(save_name)

    def api_edit_save_general(self, save_name: str, general_index: int, field_updates: dict) -> dict:
        """编辑场景存档中指定武将的属性"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.edit_save_general(save_name, general_index, field_updates)

    # ============================================================
    # V3.12.0: 引擎突破 — EXE Code Cave 注入
    # ============================================================

    def api_find_exe_code_cave(self, min_size: int = 64, section_end: bool = True) -> dict:
        """搜索 EXE Code Cave"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.exe_patcher.set_game_path(self.game_path)
        return self.exe_patcher.find_code_cave(min_size, section_end)

    def api_inject_exe_code_cave(self, cave_offset: int, machine_code_hex: str, hook_offset: int = None, backup: bool = True) -> dict:
        """向 EXE Code Cave 注入代码"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        try:
            machine_code = bytes.fromhex(machine_code_hex.replace(" ", ""))
        except ValueError:
            return {"success": False, "message": "无效的十六进制机器码"}
        self.exe_patcher.set_game_path(self.game_path)
        return self.exe_patcher.inject_code_cave(cave_offset, machine_code, hook_offset, backup)

    def api_build_jump_stub(self, from_offset: int, to_offset: int, stub_type: str = "jmp") -> dict:
        """构建跳转桩代码"""
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        self.exe_patcher.set_game_path(self.game_path)
        return self.exe_patcher.build_jump_stub(from_offset, to_offset, stub_type)

