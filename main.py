"""
San7ModMaker - 三国群英传7 MOD制作器
主入口程序，PyWebView前后端API调度
"""

import os
import sys
import json
import time
import re
import shutil
import base64
import tempfile
from io import BytesIO
from typing import Any, Dict, List, Optional

# tkinter 仅在桌面端需要（文件对话框），无GUI环境跳过
try:
    import tkinter as tk
    from tkinter import filedialog
    HAS_TK = True
except ImportError:
    HAS_TK = False

# 确保项目根目录在sys.path中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from core.ini_parser import IniParser
from core.term_text import TermTextManager
from core.backup_mgr import BackupManager
from core.validator import DataValidator
from core.shp_converter import ShpConverter
from core.exe_patcher import ExePatcher
from core.field_mapper import FieldMapper
from core.pck_manager import PckManager
from core.obd_parser import OBDParser, OBDObject
from core.save_editor import SaveEditor
from core.scriptso_analyzer import ScriptSOAnalyzer
from core.soldier_matrix import SoldierMatrixEditor
from core.mod_wizard import ModWizard
from core.csv_manager import CsvManager
from core.version_detect import VersionDetector
from core.custom_leader import CustomLeaderParser
from core.save_manager import SaveManager
from core.effect_catalog import EffectCatalog
from core.save_parser import SaveParser
from core.encoding_converter import EncodingConverter
from core.event_templates import EVENT_TEMPLATES, generate_event_section

import logging

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('San7ModMaker')


# ============================================================
# 开发进度状态
# ============================================================
DEVELOPMENT_PROGRESS = {
    "milestones": [
        {
            "id": 1,
            "name": "底层核心引擎",
            "progress": 100,
            "status": "completed",
            "tasks": [
                {"name": "PyWebView窗口框架", "done": True},
                {"name": "前后端JS-Python双向通信", "done": True},
                {"name": "游戏目录检测与路径记忆", "done": True},
                {"name": "全局自动备份/还原接口", "done": True},
                {"name": "GBK/Big5双编码检测", "done": True},
            ]
        },
        {
            "id": 2,
            "name": "INI读写引擎+文本系统",
            "progress": 100,
            "status": "completed",
            "tasks": [
                {"name": "群7特殊INI解析/写入器(注释保留)", "done": True},
                {"name": "TermText统一文本管理", "done": True},
                {"name": "字段名映射层(Schema↔Game)", "done": True},
                {"name": "GameText/CitySellItem编辑器", "done": True},
            ]
        },
        {
            "id": 3,
            "name": "武将完整编辑模块",
            "progress": 100,
            "status": "completed",
            "tasks": [
                {"name": "武将全字段编辑页面", "done": True},
                {"name": "DefSkill.ini读写联动", "done": True},
                {"name": "SHP解码器+头像预览面板", "done": True},
                {"name": "图片双向转换(PNG↔SHP)", "done": True},
            ]
        },
        {
            "id": 4,
            "name": "兵种+物品编辑模块",
            "progress": 100,
            "status": "completed",
            "tasks": [
                {"name": "兵种全字段编辑/新增", "done": True},
                {"name": "兵种相克矩阵编辑器(67×67)", "done": True},
                {"name": "物品分类管理/新增", "done": True},
                {"name": "物品强化合成配方编辑", "done": True},
            ]
        },
        {
            "id": 5,
            "name": "战斗进阶系统",
            "progress": 100,
            "status": "completed",
            "tasks": [
                {"name": "武将技/军师技编辑器(BF/SFMagic)", "done": True},
                {"name": "必杀技/特性/主将特性/元帅特性", "done": True},
                {"name": "阵型/官职/等级/年代编辑器", "done": True},
            ]
        },
        {
            "id": 6,
            "name": "剧本世界编辑器",
            "progress": 100,
            "status": "completed",
            "tasks": [
                {"name": "剧本城池数据编辑(CityXX.ini)", "done": True},
                {"name": "自定义势力/城池属性编辑", "done": True},
                {"name": "全局参数编辑(Variable.ini)", "done": True},
            ]
        },
        {
            "id": 7,
            "name": "高级工具集",
            "progress": 100,
            "status": "completed",
            "tasks": [
                {"name": "EXE引擎限制突破", "done": True},
                {"name": "批量修改/搜索替换工具", "done": True},
                {"name": "原版MOD差异对比", "done": True},
                {"name": "全局数据校验器(9类规则)", "done": True},
            ]
        },
        {
            "id": 8,
            "name": "MOD管理与发布",
            "progress": 100,
            "status": "completed",
            "tasks": [
                {"name": "多MOD独立工程隔离", "done": True},
                {"name": "MOD增量打包/导入", "done": True},
                {"name": "冲突重映射", "done": True},
                {"name": "MOD制作向导(5套模板)", "done": True},
            ]
        },
        {
            "id": 9,
            "name": "资源与档案管理",
            "progress": 100,
            "status": "completed",
            "tasks": [
                {"name": "PCK资源解包/提取/状态检测", "done": True},
                {"name": "OBD模型编辑器(17种类型)", "done": True},
                {"name": "存档管理器(备份/分析)", "done": True},
            ]
        },
        {
            "id": 10,
            "name": "Schema与校验体系",
            "progress": 100,
            "status": "completed",
            "tasks": [
                {"name": "20个INI Schema定义", "done": True},
                {"name": "跨文件引用完整性检查", "done": True},
                {"name": "出生地/特性/势力城池一致性", "done": True},
            ]
        },
        {
            "id": 11,
            "name": "UI子系统编辑器",
            "progress": 100,
            "status": "completed",
            "tasks": [
                {"name": "ButtonStyle/FontSize/FrameStyle 按键样式编辑", "done": True},
                {"name": "ListStyle/Shape/TextStyle 列表与文本编辑", "done": True},
                {"name": "WinColor/WinMainMenu 窗口颜色与菜单位置", "done": True},
            ]
        },
        {
            "id": 12,
            "name": "配置扩展与辅助工具",
            "progress": 100,
            "status": "completed",
            "tasks": [
                {"name": "CD_Table战斗音乐/CityText城市文本", "done": True},
                {"name": "PostPatch后补建筑/ThingScriptNo物品脚本", "done": True},
                {"name": "font多语言变体/一键启动游戏", "done": True},
            ]
        },
    ],
    "version": "2.3",
    "last_updated": "2026-07-16",
    "known_issues": [
        "Script.so 共享库解析/编辑尚未支持",
        "language.DAT 二进制格式编辑器待开发",
    ]
}


# ============================================================
# 原子写入工具函数
# ============================================================

def atomic_write(file_path, content, encoding='big5'):
    """原子写入文件：先写入临时文件，再原子替换，防止写入中断导致文件损坏"""
    dir_name = os.path.dirname(file_path)
    with tempfile.NamedTemporaryFile(mode='w', encoding=encoding,
                                     dir=dir_name, delete=False, suffix='.tmp') as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    os.replace(tmp_path, file_path)  # 原子替换（POSIX兼容）


# ============================================================
# 应用主类
# ============================================================
class San7ModMaker:
    """MOD制作器主应用"""

    CONFIG_FILE = "san7mod_config.json"

    def __init__(self):
        self.game_path: str = ""
        self.config: Dict[str, Any] = self._load_config()
        self._restore_state()

        # 核心引擎实例
        self.ini_parser = IniParser()
        self.term_text = TermTextManager()
        self.backup_mgr: Optional[BackupManager] = None
        self.validator = DataValidator()
        self.shp_converter = ShpConverter()
        self.exe_patcher = ExePatcher()
        self.field_mapper = FieldMapper()
        self.pck_mgr = PckManager()
        self.obd_parser = OBDParser()
        self.save_editor = SaveEditor()
        self.scriptso_analyzer = ScriptSOAnalyzer()
        self.soldier_matrix = SoldierMatrixEditor()
        self.mod_wizard = ModWizard()
        self.csv_manager = CsvManager()
        self.version_detector = VersionDetector()
        self.custom_leader = CustomLeaderParser()
        self.save_manager = SaveManager()
        self.effect_catalog = EffectCatalog()
        self.save_parser = SaveParser()
        self.encoding_converter = EncodingConverter()

        # 内存缓存
        self._general_cache: List[Dict] = []
        self._soldier_cache: List[Dict] = []
        self._thing_cache: List[Dict] = []
        self._skill_cache: List[Dict] = []
        self._formation_cache: List[Dict] = []
        self._title_cache: List[Dict] = []
        self._scenario_cache: List[Dict] = []
        self._nation_cache: List[Dict] = []
        self._city_cache: List[Dict] = []
        self._defskill_cache: Dict = {}
        self._global_params_cache: Optional[Dict] = None
        self._store_config_cache: Optional[Dict] = None
        self._mod_custom_ids: Dict[str, set] = {}  # MOD自定义ID追踪

        # 初始化游戏路径
        if self.game_path:
            self._init_game_engines()

    def _load_config(self) -> dict:
        config_path = os.path.join(PROJECT_ROOT, self.CONFIG_FILE)
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"配置文件读取失败: {e}")
        return {"game_path": "", "recent_paths": [], "language": "zh_CN"}

    def _save_config(self):
        config_path = os.path.join(PROJECT_ROOT, self.CONFIG_FILE)
        self.config["game_path"] = self.game_path
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"配置文件保存失败: {e}")

    def _restore_state(self):
        self.game_path = self.config.get("game_path", "")

    def _init_game_engines(self):
        if self.game_path and os.path.exists(self.game_path):
            self.backup_mgr = BackupManager(self.game_path)
            self.term_text.load(self.game_path)
            self.shp_converter.set_game_path(self.game_path)
            self.exe_patcher.set_game_path(self.game_path)
            self.obd_parser.set_game_path(self.game_path)

    # ============================================================
    # API: 游戏目录管理
    # ============================================================

    def api_set_game_path(self, path: str = None) -> dict:
        """设置游戏目录"""
        if path is None:
            if not HAS_TK:
                return {"success": False, "message": "当前环境不支持文件对话框，请手动输入路径"}
            root = tk.Tk()
            root.withdraw()
            path = filedialog.askdirectory(title="选择三国群英传7游戏根目录")
            root.destroy()
            if not path:
                return {"success": False, "message": "未选择目录"}

        self.game_path = path
        self.pck_mgr.set_game_path(path)
        if hasattr(self, 'save_manager'):
            self.save_manager.set_game_path(self.game_path)
        self.encoding_converter.set_game_path(self.game_path)

        # 检测PCK状态
        pck_state = self.pck_mgr.detect_game_state()

        # 检测关键目录
        setting_dir = os.path.join(path, "Setting")
        shape_face = os.path.join(path, "Shape", "Face")
        exe_file = os.path.join(path, "Sango7.exe")

        checks = {
            "Setting": os.path.exists(setting_dir),
            "Shape/Face": os.path.exists(shape_face),
            "Sango7.exe": os.path.exists(exe_file),
        }

        # 处理PCK状态
        if not checks["Setting"] and pck_state["state"] == "need_extract":
            # 尝试自动提取PCK
            extract_result = self.pck_mgr.prepare_setting_folder()
            if extract_result["success"]:
                checks["Setting"] = True
            else:
                return {
                    "success": False,
                    "message": "未检测到Setting目录，且自动提取PCK失败。请使用RPGViewer解包Patch.pck的Setting文件夹到游戏目录",
                    "checks": checks,
                    "pck_state": pck_state,
                    "help": "游戏优先读取Setting文件夹，解包后无需重新打包",
                }
        elif not checks["Setting"]:
            return {
                "success": False,
                "message": "未检测到Setting目录，请确认游戏目录正确或使用RPGViewer解包Setting资源",
                "checks": checks,
                "pck_state": pck_state,
            }

        # 记录最近路径（先更新再统一保存一次）
        if path not in self.config.get("recent_paths", []):
            recent = self.config.setdefault("recent_paths", [])
            recent.insert(0, path)
            self.config["recent_paths"] = recent[:10]

        self._save_config()
        self._init_game_engines()

        return {
            "success": True,
            "message": "游戏目录设置成功",
            "checks": checks,
            "path": path,
            "face_warning": not checks["Shape/Face"],
            "pck_state": pck_state,
        }

    def api_get_game_info(self) -> dict:
        """获取游戏目录信息"""
        return {
            "game_path": self.game_path,
            "configured": bool(self.game_path),
            "has_setting": os.path.exists(os.path.join(self.game_path, "Setting")) if self.game_path else False,
            "has_face": os.path.exists(os.path.join(self.game_path, "Shape", "Face")) if self.game_path else False,
            "has_exe": os.path.exists(os.path.join(self.game_path, "Sango7.exe")) if self.game_path else False,
            "recent_paths": self.config.get("recent_paths", []),
            "pck_state": self.pck_mgr.detect_game_state() if self.game_path else None,
            "setting_status": self.pck_mgr.get_setting_status() if self.game_path else None,
        }

    def api_detect_game_version(self) -> dict:
        """检测游戏版本和完整性"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.version_detector.detect(self.game_path)

    # ============================================================
    # API: 武将编辑
    # ============================================================

    def api_load_generals(self) -> dict:
        """加载所有武将数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        general_path = os.path.join(self.game_path, "Setting", "General01.ini")
        if not os.path.exists(general_path):
            return {"success": False, "message": "未找到General01.ini，请先解包Setting资源"}

        parser = IniParser()
        parser.load(general_path)
        sections = parser.get_all_sections("GENERAL")
        # 反向映射：游戏INI字段名 → Schema内部名
        entries = [self.field_mapper.entry_to_schema("general", dict(s.entries)) for s in sections]

        self._general_cache = entries
        return {
            "success": True,
            "count": len(entries),
            "data": entries,
        }

    def api_save_generals(self, data: list) -> dict:
        """保存武将数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        general_path = os.path.join(self.game_path, "Setting", "General01.ini")

        # 自动备份
        if self.backup_mgr:
            self.backup_mgr.backup_file(general_path)

        # 校验
        self.validator.clear()
        self.validator.check_duplicate_ids(data, "general", "General01.ini")
        self.validator.check_missing_ids(data, "general", "General01.ini")
        self.validator.check_value_ranges(data, "general", "General01.ini")

        if self.validator.has_errors():
            return {
                "success": False,
                "message": "数据校验未通过",
                "errors": self.validator.to_dict_list(),
            }

        # 检测编号变更，同步关联文件
        old_cache = {int(g.get("No", 0)): g for g in self._general_cache}
        num_changes = []  # [(old_no, new_no), ...]
        for entry in data:
            new_no = int(entry.get("No", 0))
            # 在旧缓存中查找同名武将（通过原始No匹配）
            # 由于顺序可能改变，我们用Name匹配
            for old_g in self._general_cache:
                old_no = int(old_g.get("No", 0))
                if old_no == new_no:
                    continue
                # 找到同名但编号不同的情况
                if old_g.get("Name") == entry.get("Name") and old_no != new_no and old_no in old_cache:
                    num_changes.append((old_no, new_no))
                    break

        # 编号变更同步
        sync_results = []
        for old_no, new_no in num_changes:
            sync_results.append(self._sync_general_no_in_related(old_no, new_no))

        # 正向映射：Schema内部名 → 游戏INI字段名
        mapped_data = self.field_mapper.entries_to_game("general", data)

        # 写入（带缓存回滚保护）
        old_cache = self._general_cache.copy() if self._general_cache else []
        try:
            parser = IniParser()
            parser.load(general_path)
            # 清空现有GENERAL section
            # 写入新数据
            parser.replace_sections("GENERAL", mapped_data, "No")

            parser.save(general_path)
            self._general_cache = data
        except Exception as e:
            self._general_cache = old_cache
            return {"success": False, "message": f"保存失败: {str(e)}"}

        # 同步TermText
        for entry in data:
            name = entry.get("Name", "")
            if name and self.term_text.is_loaded():
                self.term_text.allocate_new_id(name)
        self.term_text.save()

        result = {"success": True, "message": f"保存成功，共{len(data)}条武将数据"}
        if sync_results:
            result["num_sync"] = sync_results
        return result

    def api_new_general(self) -> dict:
        """新增武将 - 联动创建 DefSkill / General02 / TermText 条目"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "general_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        template = dict(schema["new_entry_template"])

        # 自动分配空编号
        used_ids = {int(g.get("No", 0)) for g in self._general_cache}
        new_id = 0
        for i in range(1, 10000):
            if i not in used_ids:
                new_id = i
                break

        template["No"] = new_id
        template["Name"] = f"新武将_{new_id:04d}"

        # 联动: TermText
        if self.term_text.is_loaded():
            self.term_text.allocate_new_id(template["Name"])

        # 联动: DefSkill.ini - 在第一个 GenSkill 组中创建空条目
        linkage_info = self._create_defskill_entry(new_id)
        # 联动: General02.ini - 创建默认出生地
        g2_info = self._create_general02_entry(new_id)

        return {
            "success": True,
            "data": template,
            "new_id": new_id,
            "linkage": {
                "term_text": template["Name"],
                "defskill": linkage_info,
                "general02": g2_info,
            }
        }

    def _create_defskill_entry(self, general_no: int) -> dict:
        """为新增武将创建 DefSkill.ini 空条目"""
        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if not os.path.exists(defskill_path):
            return {"created": False, "reason": "DefSkill.ini 不存在"}
        try:
            from core.ini_parser import IniParser
            if self.backup_mgr:
                self.backup_mgr.backup_file(defskill_path)
            parser = IniParser()
            parser.load(defskill_path)
            # 找到第一个 GenSkill 组
            gen_skill_sections = [s for s in parser.sections if s.name.startswith("GenSkill")]
            target = gen_skill_sections[0] if gen_skill_sections else parser.add_section("GenSkill01")
            # 添加空技能条目
            target.set(str(general_no), "")
            parser.save(defskill_path)
            return {"created": True, "section": target.name, "general_no": general_no}
        except Exception as e:
            return {"created": False, "reason": str(e)}

    def _create_general02_entry(self, general_no: int) -> dict:
        """为新增武将创建 General02.ini 默认出生地"""
        g2_path = os.path.join(self.game_path, "Setting", "General02.ini")
        if not os.path.exists(g2_path):
            return {"created": False, "reason": "General02.ini 不存在"}
        try:
            from core.ini_parser import IniParser
            if self.backup_mgr:
                self.backup_mgr.backup_file(g2_path)
            parser = IniParser()
            parser.load(g2_path)
            section = parser.add_section("GENERAL")
            section.set("No", str(general_no))
            for i in range(1, 11):
                section.set(f"City{i}", "0, 0")
            parser.save(g2_path)
            return {"created": True, "general_no": general_no}
        except Exception as e:
            return {"created": False, "reason": str(e)}

    def api_clone_general(self, source_no: int) -> dict:
        """克隆武将 - 联动创建 DefSkill / General02 / TermText 条目"""
        source = None
        for g in self._general_cache:
            if int(g.get("No", 0)) == source_no:
                source = dict(g)
                break

        if not source:
            return {"success": False, "message": f"未找到编号 {source_no} 的武将"}

        # 分配新编号
        used_ids = {int(g.get("No", 0)) for g in self._general_cache}
        new_id = 0
        for i in range(1, 10000):
            if i not in used_ids:
                new_id = i
                break

        source["No"] = new_id
        source["Name"] = f"{source.get('Name', '克隆')}_副本"

        # 联动: TermText
        if self.term_text.is_loaded():
            self.term_text.allocate_new_id(source["Name"])

        # 联动: DefSkill.ini - 复制源武将的技能
        linkage_info = self._clone_defskill_entry(source_no, new_id)
        # 联动: General02.ini
        g2_info = self._clone_general02_entry(source_no, new_id)

        return {
            "success": True,
            "data": source,
            "new_id": new_id,
            "linkage": {
                "term_text": source["Name"],
                "defskill": linkage_info,
                "general02": g2_info,
            }
        }

    def _clone_defskill_entry(self, source_no: int, new_no: int) -> dict:
        """克隆武将的 DefSkill.ini 条目"""
        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if not os.path.exists(defskill_path):
            return {"created": False, "reason": "DefSkill.ini 不存在"}
        try:
            from core.ini_parser import IniParser
            if self.backup_mgr:
                self.backup_mgr.backup_file(defskill_path)
            parser = IniParser()
            parser.load(defskill_path)
            cloned = False
            for section in parser.sections:
                if str(source_no) in section.entries:
                    section.set(str(new_no), section.entries[str(source_no)])
                    cloned = True
            if cloned:
                parser.save(defskill_path)
            return {"created": cloned, "general_no": new_no}
        except Exception as e:
            return {"created": False, "reason": str(e)}

    def _clone_general02_entry(self, source_no: int, new_no: int) -> dict:
        """克隆武将的 General02.ini 条目"""
        g2_path = os.path.join(self.game_path, "Setting", "General02.ini")
        if not os.path.exists(g2_path):
            return {"created": False, "reason": "General02.ini 不存在"}
        try:
            from core.ini_parser import IniParser
            if self.backup_mgr:
                self.backup_mgr.backup_file(g2_path)
            parser = IniParser()
            parser.load(g2_path)
            source_section = None
            for s in parser.get_all_sections("GENERAL"):
                if s.get("No") == str(source_no):
                    source_section = s
                    break
            if source_section:
                new_section = parser.add_section("GENERAL")
                new_section.set("No", str(new_no))
                for key in ["City1", "City2", "City3", "City4", "City5",
                            "City6", "City7", "City8", "City9", "City10"]:
                    new_section.set(key, source_section.get(key, "0, 0"))
                parser.save(g2_path)
                return {"created": True, "general_no": new_no}
            return {"created": False, "reason": f"未找到源武将 {source_no} 的出生地数据"}
        except Exception as e:
            return {"created": False, "reason": str(e)}

    def _sync_general_no_in_related(self, old_no: int, new_no: int) -> dict:
        """武将编号变更后，同步更新所有关联文件中的编号引用"""
        if not self.game_path:
            return {"synced": False, "reason": "未设置游戏目录"}

        results = {"old_no": old_no, "new_no": new_no, "files": {}}

        # 1. DefSkill.ini - 更新 GenSkill 组中的编号
        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if os.path.exists(defskill_path):
            if self.backup_mgr:
                self.backup_mgr.backup_file(defskill_path)
            try:
                parser = IniParser()
                parser.load(defskill_path)
                for section in parser.sections:
                    if section.name.startswith("GenSkill"):
                        if str(old_no) in section.entries:
                            section.set(str(new_no), section.entries[str(old_no)])
                            del section.entries[str(old_no)]
                            results["files"]["DefSkill.ini"] = "updated"
                parser.save(defskill_path)
            except Exception as e:
                results["files"]["DefSkill.ini"] = f"error: {e}"

        # 2. General02.ini - 更新出生地
        g2_path = os.path.join(self.game_path, "Setting", "General02.ini")
        if os.path.exists(g2_path):
            if self.backup_mgr:
                self.backup_mgr.backup_file(g2_path)
            try:
                parser = IniParser()
                parser.load(g2_path)
                for section in parser.get_all_sections("GENERAL"):
                    if section.get("No") == str(old_no):
                        section.set("No", str(new_no))
                        results["files"]["General02.ini"] = "updated"
                parser.save(g2_path)
            except Exception as e:
                results["files"]["General02.ini"] = f"error: {e}"

        # 3. Nation.ini - 更新势力武将引用
        nation_path = os.path.join(self.game_path, "Setting", "Nation.ini")
        if os.path.exists(nation_path):
            if self.backup_mgr:
                self.backup_mgr.backup_file(nation_path)
            try:
                parser = IniParser()
                parser.load(nation_path)
                for section in parser.sections:
                    if section.name == "GENERAL" or section.name == "NATION":
                        for key, value in list(section.entries.items()):
                            if str(old_no) in value:
                                section.set(key, value.replace(str(old_no), str(new_no)))
                                results["files"]["Nation.ini"] = "updated"
                parser.save(nation_path)
            except Exception as e:
                results["files"]["Nation.ini"] = f"error: {e}"

        # 4. Thing.ini - 更新物品关联（专属武器等）
        thing_path = os.path.join(self.game_path, "Setting", "Thing.ini")
        if os.path.exists(thing_path):
            if self.backup_mgr:
                self.backup_mgr.backup_file(thing_path)
            try:
                parser = IniParser()
                parser.load(thing_path)
                for section in parser.get_all_sections("THING"):
                    if section.get("General") == str(old_no):
                        section.set("General", str(new_no))
                        results["files"]["Thing.ini"] = "updated"
                parser.save(thing_path)
            except Exception as e:
                results["files"]["Thing.ini"] = f"error: {e}"

        # 5. City01~City10.ini - 更新城池占领/太守/军师引用
        for period in range(1, 11):
            period_str = f"{period:02d}"
            city_path = os.path.join(self.game_path, "Setting", f"City{period_str}.ini")
            if not os.path.exists(city_path):
                continue
            if self.backup_mgr:
                self.backup_mgr.backup_file(city_path)
            try:
                parser = IniParser()
                parser.load(city_path)
                updated = False
                for section in parser.get_all_sections("CITY"):
                    for field in ["Lord", "Chief", "Adviser"]:
                        val = str(section.get(field, "")).strip()
                        if val == str(old_no):
                            section.set(field, str(new_no))
                            updated = True
                if updated:
                    parser.save(city_path)
                    results["files"][f"City{period_str}.ini"] = "updated"
            except Exception as e:
                results["files"][f"City{period_str}.ini"] = f"error: {e}"

        results["synced"] = True
        return results

    def api_delete_general(self, general_no: int) -> dict:
        """删除武将 - 联动清理 DefSkill / General02 / TermText / Nation"""
        cascaded = {}

        # 1. 清理 DefSkill.ini
        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if os.path.exists(defskill_path):
            if self.backup_mgr:
                self.backup_mgr.backup_file(defskill_path)
            try:
                parser = IniParser()
                parser.load(defskill_path)
                for section in parser.sections:
                    if section.name.startswith("GenSkill"):
                        if str(general_no) in section.entries:
                            del section.entries[str(general_no)]
                            cascaded["DefSkill.ini"] = "removed"
                parser.save(defskill_path)
            except Exception as e:
                cascaded["DefSkill.ini"] = f"error: {e}"

        # 2. 清理 General02.ini
        g2_path = os.path.join(self.game_path, "Setting", "General02.ini")
        if os.path.exists(g2_path):
            if self.backup_mgr:
                self.backup_mgr.backup_file(g2_path)
            try:
                parser = IniParser()
                parser.load(g2_path)
                for section in list(parser.get_all_sections("GENERAL")):
                    if section.get("No") == str(general_no):
                        parser.sections.remove(section)
                        cascaded["General02.ini"] = "removed"
                parser.save(g2_path)
            except Exception as e:
                cascaded["General02.ini"] = f"error: {e}"

        # 3. 清理 TermText.ini
        if self.term_text.is_loaded():
            general_name = ""
            for g in self._general_cache:
                if int(g.get("No", 0)) == general_no:
                    general_name = g.get("Name", "")
                    break
            if general_name:
                self.term_text.release_by_name(general_name)
                cascaded["TermText.ini"] = "removed"

        # 4. 清理 Nation.ini 中的武将引用
        nation_path = os.path.join(self.game_path, "Setting", "Nation.ini")
        if os.path.exists(nation_path):
            if self.backup_mgr:
                self.backup_mgr.backup_file(nation_path)
            try:
                parser = IniParser()
                parser.load(nation_path)
                for section in parser.sections:
                    if section.name == "GENERAL" or section.name == "NATION":
                        for key, value in list(section.entries.items()):
                            if str(general_no) in value.split(","):
                                # 移除该编号，保留其他编号
                                vals = [v.strip() for v in value.split(",") if v.strip() != str(general_no)]
                                section.set(key, ",".join(vals) if vals else "")
                                cascaded["Nation.ini"] = "updated"
                parser.save(nation_path)
            except Exception as e:
                cascaded["Nation.ini"] = f"error: {e}"

        # 5. 清理 City01~City10.ini 中的城池引用
        for period in range(1, 11):
            period_str = f"{period:02d}"
            city_path = os.path.join(self.game_path, "Setting", f"City{period_str}.ini")
            if not os.path.exists(city_path):
                continue
            if self.backup_mgr:
                self.backup_mgr.backup_file(city_path)
            try:
                parser = IniParser()
                parser.load(city_path)
                updated = False
                for section in parser.get_all_sections("CITY"):
                    for field in ["Lord", "Chief", "Adviser"]:
                        val = str(section.get(field, "")).strip()
                        if val == str(general_no):
                            section.set(field, "0")
                            updated = True
                if updated:
                    parser.save(city_path)
                    cascaded[f"City{period_str}.ini"] = "cleared"
            except Exception as e:
                cascaded[f"City{period_str}.ini"] = f"error: {e}"

        # 6. 清除内存缓存
        self._general_cache = [g for g in self._general_cache if int(g.get("No", 0)) != general_no]

        return {
            "success": True, 
            "message": f"武将 {general_no} 已删除",
            "count": len(self._general_cache),
            "cascaded": cascaded
        }

    def api_check_references(self) -> dict:
        """跨文件引用完整性检查"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        issues = []
        refs = {}  # 收集所有引用关系

        # 1. 加载武将列表
        general_ids = set()
        general_names = {}
        for g in self._general_cache:
            no = int(g.get("No", 0))
            general_ids.add(no)
            general_names[no] = g.get("Name", "")

        # 2. 检查 Nation.ini 引用
        nation_path = os.path.join(self.game_path, "Setting", "Nation.ini")
        if os.path.exists(nation_path):
            try:
                parser = IniParser()
                parser.load(nation_path)
                for s in parser.get_all_sections("NATION"):
                    lord = s.get("Lord", "")
                    if lord and lord != "0":
                        lord_no = int(lord)
                        refs.setdefault(f"general_{lord_no}", []).append(f"Nation.ini [NATION] Lord={lord}")
                        if lord_no not in general_ids:
                            issues.append({"type": "broken_ref", "file": "Nation.ini", "section": s.name,
                                           "field": "Lord", "value": lord, "detail": f"君主 #{lord} 不存在于 General01.ini"})
                    advisor = s.get("Advisor", "")
                    if advisor and advisor != "0":
                        adv_no = int(advisor)
                        refs.setdefault(f"general_{adv_no}", []).append(f"Nation.ini [NATION] Advisor={advisor}")
                        if adv_no not in general_ids:
                            issues.append({"type": "broken_ref", "file": "Nation.ini", "section": s.name,
                                           "field": "Advisor", "value": advisor, "detail": f"军师 #{advisor} 不存在于 General01.ini"})
                    # 检查 Cities 列表中的武将
                    cities = s.get("Cities", "")
                    for cid in cities.split(","):
                        cid = cid.strip()
                        if cid.isdigit() and int(cid) > 0:
                            cno = int(cid)
                            refs.setdefault(f"city_{cno}", []).append(f"Nation.ini [NATION] {s.get('Name','')}")
            except Exception as e:
                issues.append({"type": "error", "file": "Nation.ini", "detail": str(e)})

        # 3. 检查 Thing.ini 的武将引用
        thing_path = os.path.join(self.game_path, "Setting", "Thing.ini")
        if os.path.exists(thing_path):
            try:
                parser = IniParser()
                parser.load(thing_path)
                for s in parser.get_all_sections("THING"):
                    gen_no = s.get("General", "")
                    if gen_no and gen_no != "0" and gen_no != "-1":
                        try:
                            gn = int(gen_no)
                            refs.setdefault(f"general_{gn}", []).append(f"Thing.ini [THING] {s.get('Name','')}")
                            if gn not in general_ids:
                                issues.append({"type": "broken_ref", "file": "Thing.ini", "section": s.get("Name", ""),
                                               "field": "General", "value": gen_no, "detail": f"专属武将 #{gen_no} 不存在"})
                        except ValueError:
                            pass
            except Exception as e:
                issues.append({"type": "error", "file": "Thing.ini", "detail": str(e)})

        # 4. 检查 DefSkill.ini 引用
        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if os.path.exists(defskill_path):
            try:
                parser = IniParser()
                parser.load(defskill_path)
                for s in parser.sections:
                    for key in s.entries:
                        if key.isdigit():
                            kn = int(key)
                            refs.setdefault(f"general_{kn}", []).append(f"DefSkill.ini [{s.name}]")
                            if kn not in general_ids:
                                issues.append({"type": "broken_ref", "file": "DefSkill.ini", "section": s.name,
                                               "field": key, "value": key, "detail": f"武将 #{key} 不存在于 General01.ini"})
            except Exception as e:
                issues.append({"type": "error", "file": "DefSkill.ini", "detail": str(e)})

        # 5. 检查 General02.ini 引用
        g2_path = os.path.join(self.game_path, "Setting", "General02.ini")
        if os.path.exists(g2_path):
            try:
                parser = IniParser()
                parser.load(g2_path)
                g2_ids = set()
                for s in parser.get_all_sections("GENERAL"):
                    no = s.get("No", "")
                    if no:
                        g2_ids.add(int(no))
                        refs.setdefault(f"general_{int(no)}", []).append("General02.ini [GENERAL]")
                # 检查哪些武将没有 General02 条目
                for gid in general_ids:
                    if gid not in g2_ids:
                        issues.append({"type": "missing_entry", "file": "General02.ini",
                                       "detail": f"武将 #{gid} ({general_names.get(gid, '')}) 缺少出生地数据"})
            except Exception as e:
                issues.append({"type": "error", "file": "General02.ini", "detail": str(e)})

        # 6. 检查 DefSkill 缺失
        if os.path.exists(defskill_path):
            try:
                parser = IniParser()
                parser.load(defskill_path)
                all_ds_keys = set()
                for s in parser.sections:
                    for key in s.entries:
                        if key.isdigit():
                            all_ds_keys.add(int(key))
                for gid in general_ids:
                    if gid not in all_ds_keys:
                        issues.append({"type": "missing_entry", "file": "DefSkill.ini",
                                       "detail": f"武将 #{gid} ({general_names.get(gid, '')}) 缺少技能/特性数据"})
            except Exception as e:
                logger.warning(f"DefSkill引号校验失败: {e}")

        # 7. 统计引用关系
        ref_summary = {}
        for key, sources in refs.items():
            ref_summary[key] = {"count": len(sources), "sources": sources[:5]}  # 最多5个来源

        return {
            "success": True,
            "total_issues": len(issues),
            "issues": issues,
            "broken_refs": [i for i in issues if i["type"] == "broken_ref"],
            "missing_entries": [i for i in issues if i["type"] == "missing_entry"],
            "reference_summary": ref_summary,
            "general_count": len(general_ids),
        }

    # ============================================================
    # API: 技能/特性 (DefSkill.ini)
    # ============================================================

    def api_load_defskill(self) -> dict:
        """加载DefSkill.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if not os.path.exists(defskill_path):
            return {"success": False, "message": "未找到DefSkill.ini"}

        parser = IniParser()
        parser.load(defskill_path)
        self._defskill_cache = parser.get_all_entries()

        return {"success": True, "data": self._defskill_cache}

    def api_save_defskill(self, data: dict) -> dict:
        """保存DefSkill.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if not os.path.exists(defskill_path):
            return {"success": False, "message": "未找到DefSkill.ini"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(defskill_path)

        try:
            parser = IniParser()
            parser.load(defskill_path)

            for section_name, entries_list in data.items():
                parser.replace_sections(section_name, entries_list, "No")

            parser.save(defskill_path)
            self._defskill_cache = data
            return {"success": True, "message": "DefSkill.ini 保存成功"}
        except Exception as e:
            return {"success": False, "message": f"保存失败: {str(e)}"}

    def api_new_defskill_entry(self, general_no: str) -> dict:
        """在 DefSkill.ini 中为指定武将添加空条目"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if not os.path.exists(defskill_path):
            return {"success": False, "message": "未找到DefSkill.ini"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(defskill_path)
        parser = IniParser()
        parser.load(defskill_path)
        # 为所有 GenSkill/GenFeature section 添加此武将的空条目
        for section in parser.sections:
            section.set(str(general_no), "0")
        parser.save(defskill_path)
        self._defskill_cache = parser.get_all_entries()
        return {"success": True, "message": f"已为武将 {general_no} 添加 DefSkill 条目", "data": self._defskill_cache}

    def api_delete_defskill_entry(self, general_no: str) -> dict:
        """从 DefSkill.ini 中删除指定武将的条目"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        defskill_path = os.path.join(self.game_path, "Setting", "DefSkill.ini")
        if not os.path.exists(defskill_path):
            return {"success": False, "message": "未找到DefSkill.ini"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(defskill_path)
        parser = IniParser()
        parser.load(defskill_path)
        # 删除所有 section 中此武将的 key
        for section in parser.sections:
            if section.get(str(general_no)) is not None:
                section.entries.pop(str(general_no), None)
                section._modified_keys.add(str(general_no))
        parser.save(defskill_path)
        self._defskill_cache = parser.get_all_entries()
        return {"success": True, "message": f"已删除武将 {general_no} 的 DefSkill 条目", "data": self._defskill_cache}

    def api_delete_ini_item(self, file_path: str, section_name: str, id_field: str, item_id: str) -> dict:
        """通用INI条目删除 - 删除指定section中id_field=item_id的条目"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        full_path = os.path.join(self.game_path, file_path)
        if not os.path.exists(full_path):
            return {"success": False, "message": f"未找到文件: {file_path}"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(full_path)
        parser = IniParser()
        parser.load(full_path)
        removed = False
        item_str = str(item_id)
        for section in list(parser.sections):
            if section.name == section_name:
                if str(section.get(id_field, "")) == item_str:
                    parser.sections.remove(section)
                    removed = True
                    break
        if not removed:
            return {"success": False, "message": f"未找到 {section_name} 中 {id_field}={item_id} 的条目"}
        parser.save(full_path)
        return {"success": True, "message": f"已删除 {section_name} #{item_id}"}

    # ============================================================
    # API: 兵种编辑
    # ============================================================

    def api_load_soldiers(self) -> dict:
        """加载所有兵种数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        soldier_path = os.path.join(self.game_path, "Setting", "Soldier.ini")
        if not os.path.exists(soldier_path):
            return {"success": False, "message": "未找到Soldier.ini"}

        parser = IniParser()
        parser.load(soldier_path)
        sections = parser.get_all_sections("SOLDIER")
        entries = [dict(s.entries) for s in sections]

        self._soldier_cache = entries
        return {
            "success": True,
            "count": len(entries),
            "data": entries,
            "limit": 67,
            "over_limit": len(entries) > 67,
        }

    def api_save_soldiers(self, data: list) -> dict:
        """保存兵种数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        soldier_path = os.path.join(self.game_path, "Setting", "Soldier.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(soldier_path)

        self.validator.clear()
        self.validator.check_duplicate_ids(data, "soldier", "Soldier.ini")
        self.validator.check_value_ranges(data, "soldier", "Soldier.ini")
        self.validator.check_soldier_limit(len(data), "Soldier.ini")

        if self.validator.has_errors():
            return {
                "success": False,
                "message": "数据校验未通过",
                "errors": self.validator.to_dict_list(),
            }

        # 缓存回滚保护：先保存旧缓存，写入失败时恢复
        old_cache = self._soldier_cache.copy() if self._soldier_cache else []
        try:
            parser = IniParser()
            parser.load(soldier_path)
            parser.replace_sections("SOLDIER", data, "No")
            parser.save(soldier_path)

            # 自动联动：检测新增兵种，自动创建兵符物品
            # 注意：必须在覆盖缓存之前计算 old_ids，否则永远检测不到新兵种
            old_ids = {int(s.get("No", 0)) for s in self._soldier_cache if s.get("No")}
            self._soldier_cache = data
            new_entries = [s for s in data if int(s.get("No", 0)) not in old_ids]
            linkages = []
            for entry in new_entries[:5]:
                sid = entry.get("No")
                sname = entry.get("Name", f"兵种{sid}")
                try:
                    thing_path = os.path.join(self.game_path, "Setting", "Thing.ini")
                    if os.path.exists(thing_path):
                        tp = IniParser()
                        tp.load(thing_path)
                        used = {int(t.get("No", 0)) for t in tp.sections if t.get("No")}
                        tid = 0
                        for i in range(900, 10000):
                            if i not in used:
                                tid = i
                                break
                        if tid:
                            sec = tp.add_section("THING")
                            sec["No"] = str(tid)
                            sec["Name"] = sname + "兵符"
                            sec["Type"] = "2"
                            sec["IsUsed"] = "1"
                            sec["Price"] = "100"
                            tp.save(thing_path)
                            if self.term_text.is_loaded():
                                self.term_text.allocate_new_id(sname + "兵符")
                            linkages.append(f"兵符已创建(No={tid})")
                except Exception as e:
                    linkages.append(f"兵符创建失败: {e}")

            result = {"success": True, "message": f"保存成功，共{len(data)}条兵种数据", "count": len(data)}
            if linkages:
                result["linkages"] = linkages
                result["message"] += " | " + "; ".join(linkages)
            return result
        except Exception as e:
            self._soldier_cache = old_cache
            return {"success": False, "message": f"保存失败: {str(e)}"}

    def api_new_soldier(self) -> dict:
        """新增兵种（含ObjID自动分配 + OBD模型联动）"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "soldier_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        template = dict(schema["new_entry_template"])
        used_ids = {int(s.get("No", 0)) for s in self._soldier_cache}
        new_id = 0
        for i in range(1, 10000):
            if i not in used_ids:
                new_id = i
                break

        # 自动分配 ObjID：查找 OBD 中空闲的 Sequence
        obj_id = 0
        try:
            self.obd_parser.load("bfsoldier")
            existing_objs = self.obd_parser.get_all_sequences()
            # ObjID = Sequence % 100, 从 1 开始查找
            used_obj_ids = {s % 100 for s in existing_objs}
            for oid in range(1, 100):
                if oid not in used_obj_ids:
                    obj_id = oid
                    break
        except Exception as e:
            logger.warning(f"读取OBJ ID失败: {e}")
            obj_id = new_id % 100  # 回退方案

        template["No"] = new_id
        template["Name"] = f"新兵种_{new_id:04d}"
        template["ObjID"] = obj_id

        if self.term_text.is_loaded():
            self.term_text.allocate_new_id(template["Name"])

        # 自动在 OBD 中创建模型条目
        linkage = None
        try:
            self.obd_parser.load("bfsoldier")
            seq = self.obd_parser.find_free_sequence()
            obj = OBDObject()
            obj.sequence = seq
            obj.name = template["Name"]
            obj.space = (0, 0, 0)
            self.obd_parser.objects.append(obj)
            self.obd_parser.save("bfsoldier", self.obd_parser.objects)
            template["ObjID"] = seq % 100
            linkage = f"OBD模型已创建(Sequence={seq}, ObjID={seq % 100})"
        except Exception as e:
            linkage = f"OBD模型创建失败: {e}"

        result = {"success": True, "data": template, "new_id": new_id}
        if linkage:
            result["linkage"] = linkage
        return result

    # ============================================================
    # API: 物品编辑
    # ============================================================

    def api_load_things(self) -> dict:
        """加载所有物品数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        thing_path = os.path.join(self.game_path, "Setting", "Thing.ini")
        if not os.path.exists(thing_path):
            return {"success": False, "message": "未找到Thing.ini"}

        parser = IniParser()
        parser.load(thing_path)
        sections = parser.get_all_sections("THING")
        entries = [dict(s.entries) for s in sections]

        self._thing_cache = entries
        return {"success": True, "count": len(entries), "data": entries}

    def api_save_things(self, data: list) -> dict:
        """保存物品数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        thing_path = os.path.join(self.game_path, "Setting", "Thing.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(thing_path)

        self.validator.clear()
        self.validator.check_duplicate_ids(data, "thing", "Thing.ini")
        self.validator.check_value_ranges(data, "thing", "Thing.ini")

        if self.validator.has_errors():
            return {
                "success": False,
                "message": "数据校验未通过",
                "errors": self.validator.to_dict_list(),
            }

        # 缓存回滚保护：先保存旧缓存，写入失败时恢复
        old_cache = self._thing_cache.copy() if self._thing_cache else []
        try:
            parser = IniParser()
            parser.load(thing_path)
            parser.replace_sections("THING", data, "No")
            parser.save(thing_path)

            # 自动联动：同步物品名称到 TermText (14000+No)
            if self.term_text.is_loaded():
                for entry in data:
                    tname = entry.get("Name", "")
                    tno = int(entry.get("No", 0))
                    if tname and tno > 0:
                        self.term_text.set_item_name(tno, tname)
                self.term_text.save()

            # 自动联动：检测新增物品，选择性添加到商店
            # 注意：必须在覆盖缓存之前计算 old_thing_ids，否则永远检测不到新物品
            old_thing_ids = {int(t.get("No", 0)) for t in self._thing_cache if t.get("No")}
            self._thing_cache = data
            new_things = [t for t in data if int(t.get("No", 0)) not in old_thing_ids]
            linkages = []
            for entry in new_things[:5]:
                tname = entry.get("Name", "")
                ttype = entry.get("Type", "0")
                if ttype in ("1", "2"):  # 消耗品(兵符)或武器，添加到商店
                    try:
                        city_path = os.path.join(self.game_path, "Setting", "CitySellItem.ini")
                        if os.path.exists(city_path):
                            cp = IniParser()
                            cp.load(city_path)
                            tid = entry.get("No")
                            # 添加到最后一项后面
                            last_section = cp.sections[-1] if cp.sections else None
                            if last_section:
                                new_sec = cp.add_section("CITY_SELL_ITEM")
                                new_sec["No"] = str(int(last_section.get("No", "0")) + 1)
                                new_sec["ItemID"] = str(tid)
                                new_sec["CityID"] = "1"
                                new_sec["IsUsed"] = "1"
                                cp.save(city_path)
                                linkages.append(f"{tname}已上架商店")
                    except Exception as e:
                        linkages.append(f"商店上架失败: {e}")

            result = {"success": True, "message": f"保存成功，共{len(data)}条物品数据", "count": len(data)}
            if linkages:
                result["linkages"] = linkages
                result["message"] += " | " + "; ".join(linkages)
            return result
        except Exception as e:
            self._thing_cache = old_cache
            return {"success": False, "message": f"保存失败: {str(e)}"}

    def api_new_thing(self) -> dict:
        """新增物品"""
        schema_path = os.path.join(PROJECT_ROOT, "data", "thing_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        template = dict(schema["new_entry_template"])
        used_ids = {int(t.get("No", 0)) for t in self._thing_cache}
        new_id = 0
        for i in range(1, 10000):
            if i not in used_ids:
                new_id = i
                break

        template["No"] = new_id
        template["Name"] = f"新物品_{new_id:04d}"

        if self.term_text.is_loaded():
            self.term_text.set_item_name(new_id, template["Name"])
            self.term_text.set_item_desc(new_id, f"{template['Name']}的描述")

        return {"success": True, "data": template, "new_id": new_id}

    # ============================================================
    # API: ItemEnhance 合成配方
    # ============================================================

    def api_load_item_enhance(self) -> dict:
        """加载 ItemEnhance.ini 合成配方"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "ItemEnhance.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0, "message": "ItemEnhance.ini 不存在"}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("ITEMENHANCE")
        recipes = [dict(s.entries) for s in sections]
        return {"success": True, "data": recipes, "count": len(recipes)}

    def api_save_item_enhance(self, data: list) -> dict:
        """保存 ItemEnhance.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "ItemEnhance.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        try:
            parser = IniParser()
            parser.load(path)
            parser.replace_sections("ITEMENHANCE", data, "No")
            parser.save(path)
            return {"success": True, "message": f"保存成功，共{len(data)}个配方"}
        except Exception as e:
            return {"success": False, "message": f"保存失败: {str(e)}"}

    # ============================================================
    # API: 商店配置 (CitySellItem.ini / Thing.ini 中Sell字段)
    # ============================================================

    def api_load_store_config(self) -> dict:
        """加载商店售卖配置"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        # 群7商店配置可能在 CitySellItem.ini 中
        path = os.path.join(self.game_path, "Setting", "CitySellItem.ini")
        if not os.path.exists(path):
            return {"success": True, "data": {}, "message": "CitySellItem.ini 不存在"}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("CITYSELLITEM")
        config = {}
        for s in sections:
            config.update(dict(s.entries))
        return {"success": True, "data": config}

    def api_save_store_config(self, data) -> dict:
        """保存商店售卖配置 - 接受 list 或 dict 格式"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "CitySellItem.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        try:
            parser = IniParser()
            if os.path.exists(path):
                parser.load(path)
            section = parser.get_section("CITYSELLITEM")
            if section:
                section.entries.clear()
                section._modified_keys = set()
            else:
                section = parser.add_section("CITYSELLITEM")
            if isinstance(data, list):
                for entry in data:
                    city_name = entry.get("name", entry.get("city", ""))
                    items = entry.get("items", "")
                    section.set(str(city_name), str(items))
            else:
                for key, value in data.items():
                    section.set(str(key), str(value))
            parser.save(path)
            return {"success": True, "message": "商店配置保存成功"}
        except Exception as e:
            return {"success": False, "message": f"保存失败: {str(e)}"}

    # ============================================================
    # API: 武将技/军师技 (BFMagic.ini / SFMagic.ini)
    # ============================================================

    def api_load_skills(self) -> dict:
        """加载技能数据（BFMagic.ini=武将技, SFMagic.ini=军师技）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        skills = []
        for fname, stype in [("BFMagic.ini", "magic"), ("SFMagic.ini", "strategy")]:
            path = os.path.join(self.game_path, "Setting", fname)
            if os.path.exists(path):
                parser = IniParser()
                parser.load(path)
                for section in parser.sections:
                    entry = dict(section.entries)
                    entry["SkillType"] = stype
                    entry["_source"] = fname
                    skills.append(entry)
        return {"success": True, "data": skills, "count": len(skills)}

    def api_save_skills(self, data: list) -> dict:
        """保存技能数据（BFMagic.ini=武将技, SFMagic.ini=军师技）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        skill_entries = [d for d in data if d.get("_source") == "BFMagic.ini"]
        magic_entries = [d for d in data if d.get("_source") == "SFMagic.ini"]
        saved = 0
        for fname, entries in [("BFMagic.ini", skill_entries), ("SFMagic.ini", magic_entries)]:
            path = os.path.join(self.game_path, "Setting", fname)
            if entries:
                if self.backup_mgr:
                    self.backup_mgr.backup_file(path)
                parser = IniParser()
                parser.load(path)
                section_name = parser.sections[0].name if parser.sections else "BFMAGIC"
                clean_entries = []
                for entry in entries:
                    clean = {k: v for k, v in entry.items() if k not in ("SkillType", "_source")}
                    clean_entries.append(clean)
                parser.replace_sections(section_name, clean_entries, "No")
                parser.save(path)
                saved += len(entries)
        # 同步技能名称到 TermText
        if self.term_text.is_loaded():
            for entry in data:
                name = entry.get("Name", "")
                if name:
                    self.term_text.allocate_new_id(name)
            self.term_text.save()
        return {"success": True, "message": f"保存成功，共{saved}个技能"}

    def api_new_skill(self) -> dict:
        """新增技能（默认武将技）"""
        return {
            "success": True,
            "data": {
                "No": 0, "Name": "新技能", "SkillType": "magic",
                "MP": 50, "ATK": 100, "Level": 1, "Range": 1,
                "Target": 0, "Damage": 1.0, "Effect": 0, "Element": 0,
                "IsUsed": 1, "Desc": "", "_source": "BFMagic.ini"
            }
        }

    # ============================================================
    # API: 必杀技 (SuperAtk.ini)
    # ============================================================

    def api_load_super_atk(self) -> dict:
        """加载必杀技数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "SuperAtk.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        data = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": data, "count": len(data)}

    def api_save_super_atk(self, data: list) -> dict:
        """保存必杀技数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "SuperAtk.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        try:
            parser = IniParser()
            parser.load(path)
            parser.replace_sections("SuperAtk", data, "No")
            parser.save(path)
            # 同步必杀技名称到 TermText
            if self.term_text.is_loaded():
                for entry in data:
                    name = entry.get("Name", "")
                    if name:
                        self.term_text.allocate_new_id(name)
                self.term_text.save()
            return {"success": True, "message": f"保存成功，共{len(data)}个必杀技"}
        except Exception as e:
            return {"success": False, "message": f"保存失败: {str(e)}"}

    def api_new_super_atk(self) -> dict:
        """新增必杀技"""
        return {"success": True, "data": {"NO": 0, "Name": "新必杀技", "HitRatio": 25, "General01": 1, "General02": 1, "IsUsed": 1}}

    # ============================================================
    # API: 特性定义 (GenSkill.ini / ArmySkill.ini / ArmyGroupSkill.ini)
    # ============================================================

    def api_load_gen_skills(self) -> dict:
        """加载所有特性定义"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        result = {}
        for fname, key in [("GenSkill.ini", "gen"), ("ArmySkill.ini", "army"), ("ArmyGroupSkill.ini", "group")]:
            path = os.path.join(self.game_path, "Setting", fname)
            if os.path.exists(path):
                parser = IniParser()
                parser.load(path)
                result[key] = {"label": fname, "sections": [dict(s.entries) for s in parser.sections]}
            else:
                result[key] = {"label": fname, "sections": []}
        return {"success": True, "data": result}

    def api_save_gen_skills(self, data: dict) -> dict:
        """保存特性定义"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if not isinstance(data, dict):
            return {"success": False, "message": "数据格式错误，应为字典"}
        try:
            for fname, key in [("GenSkill.ini", "gen"), ("ArmySkill.ini", "army"), ("ArmyGroupSkill.ini", "group")]:
                if key not in data:
                    continue
                sections_data = data[key]
                if isinstance(sections_data, dict):
                    sections_data = sections_data.get("sections", [])
                if not isinstance(sections_data, list):
                    return {"success": False, "message": f"{key} 数据格式错误"}
                path = os.path.join(self.game_path, "Setting", fname)
                if not os.path.exists(path):
                    continue
                if self.backup_mgr:
                    self.backup_mgr.backup_file(path)
                parser = IniParser()
                parser.load(path)
                section_name = parser.sections[0].name if parser.sections else key.upper()
                clean_entries = []
                for entry in sections_data:
                    clean = {k: v for k, v in entry.items() if k != "_id"}
                    clean_entries.append(clean)
                parser.replace_sections(section_name, clean_entries, "No")
                parser.save(path)
            return {"success": True, "message": "特性定义保存成功"}
        except Exception as e:
            return {"success": False, "message": f"保存失败: {str(e)}"}

    # ============================================================
    # API: TermText 文本管理
    # ============================================================

    def api_load_term_text_full(self) -> dict:
        """加载 TermText.ini 全部数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "TermText.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        entries = []
        for section in parser.sections:
            for key, value in section.entries.items():
                if re.match(r'^String\d+$', key):
                    no = key.replace("String", "").strip()
                    entries.append({"id": no, "key": key, "value": value})
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_term_text(self, data: list) -> dict:
        """保存 TermText.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "TermText.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        # 删除所有已有的 String 键（保留 StringCount 等非数字后缀键）
        for section in parser.sections:
            string_keys = [k for k in section.entries if re.match(r'^String\d+$', k)]
            for k in string_keys:
                del section.entries[k]
        # 定位 TermText section（优先按名称匹配，否则用第一个 section）
        target_section = None
        for s in parser.sections:
            if s.name.lower() == "termtext":
                target_section = s
                break
        if not target_section:
            target_section = parser.sections[0] if parser.sections else parser.add_section("TermText")
        # 写入所有条目
        for entry in data:
            string_id = entry.get("id", "")
            value = entry.get("value", "")
            if string_id and value:
                target_section.set(f"String{string_id}", value)
        parser.save(path)
        return {"success": True, "message": f"TermText保存成功，共{len(data)}条"}

    def api_get_thing_termtext(self, item_no: int) -> dict:
        """获取物品的 TermText 名称和描述"""
        if not self.term_text.is_loaded():
            return {"success": True, "name": "", "desc": ""}
        name = self.term_text.get_item_name(item_no)
        desc = self.term_text.get_item_desc(item_no)
        return {"success": True, "name": name, "desc": desc}

    def api_set_thing_termtext(self, item_no: int, name: str = "", desc: str = "") -> dict:
        """设置物品的 TermText 名称和描述，并保存"""
        if not self.term_text.is_loaded():
            return {"success": False, "message": "TermText 未加载"}
        if name:
            self.term_text.set_item_name(item_no, name)
        if desc:
            self.term_text.set_item_desc(item_no, desc)
        self.term_text.save()
        return {"success": True, "message": "物品文本已保存"}

    # ============================================================
    # API: 等级经验/带兵数 (GenLV.ini)
    # ============================================================

    def api_load_gen_lv(self) -> dict:
        """加载 GenLV.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "GenLV.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        data = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": data, "count": len(data)}

    def api_save_gen_lv(self, data: list) -> dict:
        """保存 GenLV.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "GenLV.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("GenLV", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}级"}

    # ============================================================
    # API: 剧本年代 (Age.ini)
    # ============================================================

    def api_load_age(self) -> dict:
        """加载 Age.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Age.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        data = [dict(s.entries) for s in parser.sections]
        return {"success": True, "data": data, "count": len(data)}

    def api_save_age(self, data: list) -> dict:
        """保存 Age.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Age.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("AGE", data, "No")
        parser.save(path)
        return {"success": True, "message": "剧本年代保存成功"}

    # ============================================================
    # API: 城池商店 (CitySellItem.ini)
    # ============================================================

    def api_load_city_sell_items(self) -> dict:
        """加载城池商店数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "CitySellItem.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        data = []
        for s in parser.get_all_sections("CITY_ITEM"):
            entry = dict(s.entries)
            # 解析 item[1]~item[10] 为数组
            items = []
            for i in range(1, 11):
                key = f"item[{i}]"
                if key in entry:
                    items.append({"index": i, "item_id": entry.pop(key)})
            entry["items"] = items
            data.append(entry)
        return {"success": True, "data": data, "count": len(data)}

    def api_save_city_sell_items(self, data: list) -> dict:
        """保存城池商店数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "CitySellItem.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        clean_entries = []
        for entry in data:
            clean = {"City": entry.get("City", "")}
            items = entry.get("items", [])
            for item in items:
                clean[f"item[{item['index']}]"] = item.get("item_id", "")
            for k, v in entry.items():
                if k not in ("City", "items"):
                    clean[k] = str(v)
            clean_entries.append(clean)
        parser.replace_sections("CITY_ITEM", clean_entries, "City")
        parser.save(path)
        # 同步到 storeConfig
        self._store_config_cache = data
        return {"success": True, "message": f"城池商店保存成功，{len(data)}个城池"}

    # ============================================================
    # API: 游戏文本 (GameText.ini)
    # ============================================================

    def api_load_game_text(self) -> dict:
        """加载游戏文本"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "GameText.ini")
        if not os.path.exists(path):
            return {"success": True, "data": {}, "sections": []}
        parser = IniParser()
        parser.load(path)
        sections = []
        for s in parser.sections:
            sections.append({
                "name": s.name,
                "entries": dict(s.entries),
                "count": len(s.entries),
            })
        return {"success": True, "sections": sections, "count": len(sections)}

    def api_save_game_text(self, data: list) -> dict:
        """保存游戏文本"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "GameText.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        # 保留原始section，更新entries
        for section_data in data:
            section = parser.get_section(section_data["name"])
            if not section:
                section = parser.add_section(section_data["name"])
            for k, v in section_data.get("entries", {}).items():
                section.set(k, str(v))
        parser.save(path)
        return {"success": True, "message": "游戏文本保存成功"}

    # ============================================================
    # API: 武将出生地 (General02.ini)
    # ============================================================

    def api_load_general02(self) -> dict:
        """加载 General02.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "General02.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        data = [dict(s.entries) for s in parser.get_all_sections("GENERAL")]
        return {"success": True, "data": data, "count": len(data)}

    def api_save_general02(self, data: list) -> dict:
        """保存 General02.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "General02.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("GENERAL", data, "No")
        parser.save(path)
        return {"success": True, "message": f"保存成功，共{len(data)}个武将出生地"}

    # ============================================================
    # API: 阵型 (Formation.ini)
    # ============================================================

    def api_load_formations(self) -> dict:
        """加载阵型数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Formation.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("FORMATION")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_formations(self, data: list) -> dict:
        """保存阵型数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Formation.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("FORMATION", data, "No")
        parser.save(path)
        # 同步阵型名称到 TermText
        if self.term_text.is_loaded():
            for entry in data:
                name = entry.get("Name", "")
                if name:
                    self.term_text.allocate_new_id(name)
            self.term_text.save()
        return {"success": True, "message": f"保存成功，共{len(data)}个阵型"}

    def api_new_formation(self) -> dict:
        """创建新阵型模板"""
        data = self._load_schema("formation_schema")
        template = data["new_entry_template"] if data and "new_entry_template" in data else {}
        if not template:
            template = {"No": 0, "Name": "新阵型", "SoldierCount": 5, "GenSkill1": 0, "GenSkill2": 0}
        return {"success": True, "data": template}

    # ============================================================
    # API: 官职 (Title.ini)
    # ============================================================

    def api_load_titles(self) -> dict:
        """加载官职数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Title.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("TITLE")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_titles(self, data: list) -> dict:
        """保存官职数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Title.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        parser.load(path)
        parser.replace_sections("TITLE", data, "No")
        parser.save(path)
        # 同步官职名称到 TermText
        if self.term_text.is_loaded():
            for entry in data:
                name = entry.get("Name", "")
                if name:
                    self.term_text.allocate_new_id(name)
            self.term_text.save()
        return {"success": True, "message": f"保存成功，共{len(data)}个官职"}

    def api_new_title(self) -> dict:
        """新增官职"""
        return {
            "success": True,
            "data": {
                "No": 0, "Name": "新官职", "Rank": 9,
                "WStr": 0, "Int": 0, "HP": 0, "MP": 0,
                "GeneralCount": 1, "Exp": 100, "ATK": 0, "DEF": 0,
                "Speed": 0, "Skill": 0, "Upgrade": 0, "IsUsed": 1
            }
        }

    # ============================================================
    # API: 剧本 (Scenario.ini)
    # ============================================================

    def api_load_scenarios(self) -> dict:
        """加载剧本数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Scenario.ini")
        if not os.path.exists(path):
            return {"success": True, "data": [], "count": 0}
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections("SCENARIO")
        entries = [dict(s.entries) for s in sections]
        return {"success": True, "data": entries, "count": len(entries)}

    def api_save_scenarios(self, data: list) -> dict:
        """保存剧本数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Setting", "Scenario.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        try:
            parser = IniParser()
            parser.load(path)
            parser.replace_sections("SCENARIO", data, "No")
            parser.save(path)
            # 同步剧本名称到 TermText
            if self.term_text.is_loaded():
                for entry in data:
                    name = entry.get("Name", "")
                    if name:
                        self.term_text.allocate_new_id(name)
                self.term_text.save()
            return {"success": True, "message": f"保存成功，共{len(data)}个剧本"}
        except Exception as e:
            return {"success": False, "message": f"保存失败: {str(e)}"}

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

    def api_new_global_params(self) -> dict:
        return {"success": True, "data": {"No": "", "Name": "", "Int00": "0", "Int01": "0", "Int02": "0", "Int03": "0", "Int04": "0", "Int05": "0", "Int06": "0", "Int07": "0", "Int08": "0", "Int09": "0", "Float00": "0", "Float01": "0", "Float02": "0", "Float03": "0", "Float04": "0", "Float05": "0", "Float06": "0", "Float07": "0", "Float08": "0", "Float09": "0", "String": ""}}
        clean_entries = []
        for entry in data:
            clean = {k: v for k, v in entry.items() if k != "_raw"}
            clean_entries.append(clean)
        parser.replace_sections("VARIABLE", clean_entries, "No")
        parser.save(path)
        self._global_params_cache = data
        return {"success": True, "message": f"全局参数保存成功，共 {len(data)} 条"}

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

    # ============================================================
    # API: SHP头像预览/转换
    # ============================================================

    def api_get_face_preview(self, face_id: int) -> dict:
        """获取头像base64预览数据"""
        if not self.game_path:
            return {"success": False, "imgData": "", "message": "请先设置游戏目录"}

        try:
            b64 = self.shp_converter.load_shp_base64(face_id)
            return {"success": True, "imgData": b64, "faceId": face_id}
        except ImportError:
            return {"success": False, "imgData": "", "message": "Pillow库未安装，请运行: pip install Pillow"}
        except Exception as e:
            return {"success": False, "imgData": "", "message": str(e)}

    def api_convert_image_to_shp(self, src_path: str, face_id: int) -> dict:
        """导入图片转SHP（头像）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        try:
            out_path = self.shp_converter.image_to_shp(src_path, face_id)
            return {
                "success": True,
                "message": f"头像转换完成: {face_id:04d}.shp",
                "path": out_path,
                "log": self.shp_converter.get_log(),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_convert_image_to_bfobj_shp(self, src_path: str, bfobj_subdir: str = "") -> dict:
        """导入图片转为 BFObj 兵种模型 SHP"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            rel_path = os.path.relpath(out_path, os.path.join(self.game_path, "Shape", "BFObj"))
            return {
                "success": True,
                "message": f"BFObj模型图片导入完成: {next_id:04d}.shp",
                "path": out_path,
                "relativePath": rel_path,
                "newId": next_id,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ============================================================
    # API: 物品图标 (ThingIcon)
    # ============================================================

    def api_convert_image_to_thing_icon(self, src_path: str, icon_id: int) -> dict:
        """导入图片转为物品图标 SHP (支持 base64 data URL 或文件路径)"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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

            # 清理临时文件
            if actual_path != src_path and os.path.exists(actual_path):
                os.unlink(actual_path)

            return {
                "success": True,
                "message": f"物品图标转换完成: {icon_id:04d}.shp",
                "path": out_path,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_export_thing_icon_to_png(self, icon_id: int) -> dict:
        """导出物品图标 SHP 为 PNG (返回 base64)"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": str(e)}

    def api_thing_icon_batch_import(self, file_map: dict) -> dict:
        """批量导入物品图标: {icon_id: src_path, ...}"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        results = []
        icon_dir = os.path.join(self.game_path, "Shape", "ThingIcon")
        os.makedirs(icon_dir, exist_ok=True)
        for icon_id, src_path in file_map.items():
            try:
                out_path = self.shp_converter.image_to_shp(src_path, int(icon_id), icon_dir)
                results.append({"icon_id": icon_id, "success": True, "path": out_path})
            except Exception as e:
                results.append({"icon_id": icon_id, "success": False, "message": str(e)})
        return {"success": True, "results": results}

    def api_thing_icon_batch_export(self, icon_ids: list) -> dict:
        """批量导出物品图标"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        results = []
        icon_dir = os.path.join(self.game_path, "Shape", "ThingIcon")
        for icon_id in icon_ids:
            try:
                out_path = self.shp_converter.shp_to_png(int(icon_id), icon_dir)
                results.append({"icon_id": icon_id, "success": True, "path": out_path})
            except Exception as e:
                results.append({"icon_id": icon_id, "success": False, "message": str(e)})
        return {"success": True, "results": results}

    def api_create_sh_dir(self, obd_type: str, number: str) -> dict:
        """创建兵种动画帧目录结构 Shape/BFObj/{type}/{number}/"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": str(e)}

    def api_import_sprite_frame(self, obd_type: str, number: str, anim_type: str, frame_idx: int) -> dict:
        """导入单个兵种动画帧：从 import 目录读取 PNG 并转为 SHP"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            rel_path = os.path.relpath(out_path, os.path.join(self.game_path, "Shape", "BFObj"))
            return {
                "success": True,
                "message": f"帧导入完成: {anim_type}{frame_idx}.shp",
                "path": out_path,
                "relativePath": rel_path,
                "frameId": frame_idx,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_export_shp_to_png(self, face_id: int, save_path: str) -> dict:
        """导出SHP为PNG"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        try:
            out = self.shp_converter.shp_to_png(face_id, save_path)
            return {"success": True, "message": "导出成功", "path": out}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_select_image_file(self) -> dict:
        """选择图片文件"""
        if not HAS_TK:
            return {"success": False, "path": "", "message": "当前环境不支持文件对话框"}
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
        return self.shp_converter.batch_delete(face_ids)

    def api_face_batch_export(self, face_ids: list, output_dir: str) -> dict:
        """批量导出头像"""
        return self.shp_converter.batch_export(face_ids, output_dir)

    def api_face_stats(self) -> dict:
        """头像统计"""
        return self.shp_converter.get_face_stats()

    # ============================================================
    # API: BFObj 兵种模型 SHP 管理
    # ============================================================

    def api_list_bfobj_shps(self) -> dict:
        """列出 Shape/BFObj/ 目录下的兵种模型 SHP 文件"""
        return self.shp_converter.list_bfobj_shps()

    def api_preview_bfobj_shp(self, rel_path: str) -> dict:
        """预览 BFObj 目录下的 SHP 文件"""
        return self.shp_converter.preview_bfobj_shp(rel_path)

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
            return {"success": False, "message": str(e)}

    def api_import_image_to_genhalf(self, src_path: str, genhalf_subdir: str = "") -> dict:
        """导入图片转为 genhalf 半身像 SHP"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {
                "success": True,
                "message": f"半身像导入完成: {next_id:04d}.shp",
                "path": out_path,
                "newId": next_id,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ============================================================
    # API: Shape 资源统一浏览
    # ============================================================

    def api_browse_shape_resources(self, category: str = "all") -> dict:
        """统一浏览 Shape 资源（Face / BFObj / genhalf）"""
        if not self.game_path:
            return {"success": False, "message": "未配置游戏目录", "categories": {}}
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
            return {"success": False, "message": "请先设置游戏目录"}
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

    # ============================================================
    # API: 备份还原
    # ============================================================

    def api_backup_all(self) -> dict:
        """全量备份"""
        if not self.backup_mgr:
            return {"success": False, "message": "请先设置游戏目录"}
        backed = self.backup_mgr.backup_all_settings()
        return {"success": True, "message": f"备份完成，共{len(backed)}个文件", "count": len(backed)}

    def api_restore_all(self) -> dict:
        """一键还原"""
        if not self.backup_mgr:
            return {"success": False, "message": "请先设置游戏目录"}
        results = self.backup_mgr.restore_all()
        success_count = sum(1 for v in results.values() if v)
        return {"success": True, "message": f"还原完成，成功{success_count}个", "details": results}

    def api_get_backup_history(self) -> dict:
        """获取备份历史"""
        if not self.backup_mgr:
            return {"success": True, "history": [], "count": 0}
        history = self.backup_mgr.get_backup_history()
        return {"success": True, "history": history, "count": len(history)}

    # ============================================================
    # API: 数据校验
    # ============================================================

    def api_validate_all(self) -> dict:
        """全量数据校验（含技能引用校验）"""
        self.validator.clear()
        if self.game_path:
            self.validator.set_game_path(self.game_path)

        # 校验武将
        if self._general_cache:
            self.validator.check_duplicate_ids(self._general_cache, "general", "General01.ini")
            self.validator.check_value_ranges(self._general_cache, "general", "General01.ini")

        # 校验兵种
        if self._soldier_cache:
            self.validator.check_duplicate_ids(self._soldier_cache, "soldier", "Soldier.ini")
            self.validator.check_value_ranges(self._soldier_cache, "soldier", "Soldier.ini")
            self.validator.check_soldier_limit(len(self._soldier_cache), "Soldier.ini")

        # 校验物品
        if self._thing_cache:
            self.validator.check_duplicate_ids(self._thing_cache, "thing", "Thing.ini")
            self.validator.check_value_ranges(self._thing_cache, "thing", "Thing.ini")

        # 跨文件引用校验
        if self._general_cache and self._soldier_cache and self._thing_cache:
            self.validator.check_cross_references(
                self._general_cache, self._soldier_cache, self._thing_cache
            )

        # 6类技能引用校验
        if self.game_path:
            bfmagic_ids = self._load_skill_ids("BFMagic.ini")
            sfmagic_ids = self._load_skill_ids("SFMagic.ini")
            genskill_ids = self._load_skill_ids("GenSkill.ini")
            armyskill_ids = self._load_skill_ids("ArmySkill.ini")
            armygroupskill_ids = self._load_skill_ids("ArmyGroupSkill.ini")
            superatk_ids = self._load_skill_ids("SuperAtk.ini")

            generals = self._general_cache if self._general_cache else []
            defskill = self._defskill_cache if self._defskill_cache else []
            things = self._thing_cache if self._thing_cache else []
            titles = self._title_cache if self._title_cache else []

            # 如果defskill是dict格式，提取sections
            if isinstance(defskill, dict):
                defskill_entries = []
                for sections in defskill.values():
                    if isinstance(sections, list):
                        defskill_entries.extend(sections)
                defskill = defskill_entries

            self.validator.check_skill_id_references(
                generals, defskill, things, titles,
                bfmagic_ids, sfmagic_ids, genskill_ids,
                armyskill_ids, armygroupskill_ids, superatk_ids
            )

        return {
            "success": True,
            "summary": self.validator.summary(),
            "results": self.validator.to_dict_list(),
        }

    def _load_skill_ids(self, filename: str) -> set:
        """从技能INI文件中加载所有技能ID集合"""
        path = os.path.join(self.game_path, "Setting", filename)
        if not os.path.exists(path):
            return set()
        parser = IniParser()
        parser.load(path)
        ids = set()
        for section in parser.sections:
            sid = str(section.get("No", section.get("NO", ""))).strip()
            if sid:
                ids.add(sid)
        return ids

    # ============================================================
    # API: TermText
    # ============================================================

    def api_search_termtext(self, keyword: str) -> dict:
        """搜索TermText"""
        if not self.term_text.is_loaded():
            return {"success": False, "message": "请先加载游戏数据"}
        results = self.term_text.search_text(keyword)
        return {"success": True, "results": results, "count": len(results)}

    def api_get_all_termtext(self) -> dict:
        """获取所有TermText"""
        if not self.term_text.is_loaded():
            return {"success": False, "message": "请先加载游戏数据"}
        texts = self.term_text.get_all_texts()
        return {"success": True, "data": texts, "count": len(texts)}

    # ============================================================
    # API: EXE修改
    # ============================================================

    def api_get_exe_info(self) -> dict:
        """获取EXE信息"""
        return {
            "exists": self.exe_patcher.exe_exists(),
            "size": self.exe_patcher.get_exe_size(),
            "patches": self.exe_patcher.get_patch_info(),
            "applied": self.exe_patcher.get_applied_patches(),
        }

    def api_apply_exe_patch(self, patch_name: str, offset: int, value: int) -> dict:
        """应用EXE补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        # 先备份EXE
        if self.backup_mgr:
            self.backup_mgr.backup_exe()

        success = self.exe_patcher.apply_patch(patch_name, offset, value)
        if success:
            return {"success": True, "message": f"补丁 {patch_name} 应用成功"}
        return {"success": False, "message": f"补丁 {patch_name} 应用失败"}

    def api_revert_exe_patches(self) -> dict:
        """撤销所有EXE补丁"""
        count = self.exe_patcher.revert_all()
        return {"success": True, "message": f"已撤销{count}个补丁", "count": count}

    def api_scan_exe_signatures(self) -> dict:
        """扫描EXE中所有已知特征码"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        results = self.exe_patcher.scan_all_signatures()
        return {
            "success": len(results) > 0,
            "message": f"扫描完成，发现 {len(results)} 组特征码",
            "signatures": {k: len(v) for k, v in results.items()},
            "candidates": {k: v[:10] for k, v in results.items()},
        }

    def api_scan_exe_value(self, value: int, value_type: str = "int32") -> dict:
        """扫描EXE中特定数值的出现位置"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        results = self.exe_patcher.scan_exe_for_value_range(value, value_type)
        return {
            "success": True,
            "message": f"找到 {len(results)} 处匹配",
            "value": value,
            "value_type": value_type,
            "count": len(results),
            "offsets": results[:50],  # 最多返回50个
        }

    def api_apply_exe_patch_auto(self, patch_name: str, new_value: int) -> dict:
        """自动检测偏移量并应用EXE补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if self.backup_mgr:
            self.backup_mgr.backup_exe()
        return self.exe_patcher.apply_patch_auto(patch_name, new_value)

    def api_disassemble_exe(self, offset: int, count: int = 8) -> dict:
        """反汇编 EXE 指定偏移处的指令"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        instructions = self.exe_patcher.disassemble_at(offset, count)
        has_capstone = getattr(self.exe_patcher, 'HAS_CAPSTONE', False) or (
            hasattr(self.exe_patcher.__class__, 'HAS_CAPSTONE') or True
        )
        try:
            from capstone import Cs
            has_capstone = True
        except ImportError:
            has_capstone = False
        return {
            "success": len(instructions) > 0 and "error" not in instructions[0],
            "offset": offset,
            "count": count,
            "instructions": instructions,
            "has_capstone": has_capstone,
        }

    def api_disassemble_scan(self, scan_name: str, top_n: int = 5) -> dict:
        """对特征码扫描结果进行反汇编"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.exe_patcher.disassemble_scan_results(scan_name, top_n)

    def api_apply_nop_patch(self, offset: int, size: int) -> dict:
        """应用 NOP 补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if self.backup_mgr:
            self.backup_mgr.backup_exe()
        ok = self.exe_patcher.apply_nop_patch(offset, size)
        return {"success": ok, "message": f"NOP {size}字节 @ {hex(offset)}" if ok else "写入失败"}

    def api_apply_jmp_patch(self, offset: int, target_offset: int, is_short: bool = True) -> dict:
        """应用 JMP 补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if self.backup_mgr:
            self.backup_mgr.backup_exe()
        ok = self.exe_patcher.apply_jmp_patch(offset, target_offset, is_short)
        return {"success": ok, "message": f"JMP {hex(offset)} → {hex(target_offset)}" if ok else "JMP失败"}

    def api_apply_template_patch(self, template_name: str, offset: int, *args) -> dict:
        """应用预设补丁模板"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if self.backup_mgr:
            self.backup_mgr.backup_exe()
        return self.exe_patcher.apply_template_patch(template_name, offset, *args)

    def api_get_jmp_templates(self) -> dict:
        """获取 JMP 补丁模板列表"""
        return {"success": True, "templates": self.exe_patcher.get_jmp_templates()}

    def api_exe_community_patches(self) -> dict:
        """获取社区教程补丁列表"""
        patches = self.exe_patcher.get_community_patches()
        return {"success": True, "patches": patches, "count": len(patches),
                "message": f"共 {len(patches)} 个社区补丁"}

    def api_exe_apply_community_patch(self, patch_id: str, value: int) -> dict:
        """应用社区教程补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if self.backup_mgr:
            self.backup_mgr.backup_exe()
        return self.exe_patcher.apply_patch_auto(patch_id, value)

    # ============================================================
    # API: Sango7.ini 分辨率设置
    # ============================================================

    def api_get_sango7_config(self) -> dict:
        """读取 Sango7.ini 配置（分辨率、窗口模式等）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Sango7.ini")
        if not os.path.exists(path):
            return {"success": True, "config": {"width": 1024, "height": 768, "fullscreen": 1}}
        config = {"width": 1024, "height": 768, "fullscreen": 1}
        try:
            with open(path, "r", encoding="big5", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("m_lScreenWidth"):
                        config["width"] = int(line.split("=")[1].strip())
                    elif line.startswith("m_lScreenHeight"):
                        config["height"] = int(line.split("=")[1].strip())
                    elif line.startswith("m_bFullScreen"):
                        config["fullscreen"] = int(line.split("=")[1].strip())
        except Exception:
            logger.warning("读取Sango7.ini配置失败，使用默认值")
        return {"success": True, "config": config}

    def api_set_sango7_config(self, width: int = 0, height: int = 0, fullscreen: int = -1) -> dict:
        """修改 Sango7.ini 分辨率/窗口配置"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "Sango7.ini")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        # 读取现有内容
        lines = []
        if os.path.exists(path):
            with open(path, "r", encoding="big5", errors="replace") as f:
                lines = f.readlines()
        # 更新设置
        updated = {"width": False, "height": False, "fullscreen": False}
        new_lines = []
        for line in lines:
            s = line.strip()
            if width > 0 and s.startswith("m_lScreenWidth"):
                new_lines.append(f"m_lScreenWidth = {width}\n")
                updated["width"] = True
            elif height > 0 and s.startswith("m_lScreenHeight"):
                new_lines.append(f"m_lScreenHeight = {height}\n")
                updated["height"] = True
            elif fullscreen >= 0 and s.startswith("m_bFullScreen"):
                new_lines.append(f"m_bFullScreen = {fullscreen}\n")
                updated["fullscreen"] = True
            else:
                new_lines.append(line)
        # 追加缺失的配置项
        for key, val, flag in [("m_lScreenWidth", width, "width"),
                                ("m_lScreenHeight", height, "height"),
                                ("m_bFullScreen", fullscreen, "fullscreen")]:
            if not updated[flag]:
                if key == "m_bFullScreen" and fullscreen >= 0:
                    new_lines.append(f"{key} = {fullscreen}\n")
                elif key != "m_bFullScreen" and val > 0:
                    new_lines.append(f"{key} = {val}\n")
        with open(path, "w", encoding="big5", errors="replace") as f:
            f.writelines(new_lines)
        return {"success": True, "message": f"分辨率设置为 {width}x{height}" if width > 0 else "配置已保存"}

    # ============================================================
    # API: 批量修改工具
    # ============================================================

    # 文件字段映射（依据群7游戏实际INI字段）
    _BATCH_LABELS = {
        "General01.ini": "武将 (General01.ini)",
        "Soldier.ini": "兵种 (Soldier.ini)",
        "Thing.ini": "物品 (Thing.ini)",
        "Title.ini": "官职 (Title.ini)",
        "Nation.ini": "势力 (Nation.ini)",
        "City.ini": "城池连接 (City.ini)",
        "BFFront.ini": "冲阵兵器 (BFFront.ini)",
        "BFMagic.ini": "武将技 (BFMagic.ini)",
        "SFMagic.ini": "军师技 (SFMagic.ini)",
        "SuperAtk.ini": "必杀技 (SuperAtk.ini)",
        "GenSkill.ini": "个人特性 (GenSkill.ini)",
        "ArmySkill.ini": "主将特性 (ArmySkill.ini)",
        "ArmyGroupSkill.ini": "元帅特性 (ArmyGroupSkill.ini)",
        "DefSkill.ini": "初始特性 (DefSkill.ini)",
        "Variable.ini": "游戏变量 (Variable.ini)",
        "GenLV.ini": "等级经验 (GenLV.ini)",
        "ItemEnhance.ini": "物品合成 (ItemEnhance.ini)",
        "Format.ini": "阵型属性 (Format.ini)",
        "ChessFormat.ini": "自设阵法 (ChessFormat.ini)",
    }

    def api_get_batch_files(self) -> dict:
        """获取批量修改可用文件列表"""
        return {"success": True, "files": self._get_batch_schemas()}

    def _get_batch_schemas(self) -> dict:
        """从 Schema JSON 动态加载批量配置"""
        schema_dir = os.path.join(os.path.dirname(__file__), "data")
        dynamic = {}
        file_to_schema = {
            "General01.ini": "general_schema.json",
            "Soldier.ini": "soldier_schema.json",
            "Thing.ini": "thing_schema.json",
            "Title.ini": "title_schema.json",
            "Nation.ini": "nation_schema.json",
            "City.ini": "city_schema.json",
            "BFFront.ini": "bffront_schema.json",
            "BFMagic.ini": "bfmagic_schema.json",
            "SFMagic.ini": "sfmagic_schema.json",
            "SuperAtk.ini": "superatk_schema.json",
            "GenSkill.ini": "genskill_schema.json",
            "ArmySkill.ini": "armyskill_schema.json",
            "ArmyGroupSkill.ini": "armygroupskill_schema.json",
            "DefSkill.ini": "defskill_schema.json",
            "GenLV.ini": "genlv_schema.json",
            "Variable.ini": "variable_schema.json",
            "ItemEnhance.ini": "itemenhance_schema.json",
            "Format.ini": "format_schema.json",
            "ChessFormat.ini": "chessformat_schema.json",
        }
        for ini_file, schema_file in file_to_schema.items():
            schema_path = os.path.join(schema_dir, schema_file)
            if os.path.exists(schema_path):
                with open(schema_path, "r", encoding="utf-8") as f:
                    s = json.load(f)
                sections = s.get("sections", {})
                if sections:
                    first_section = list(sections.values())[0]
                    fields = list(first_section.get("fields", {}).keys())
                    section_name = list(sections.keys())[0]
                    label = self._BATCH_LABELS.get(ini_file, ini_file)
                    dynamic[ini_file] = {
                        "label": label,
                        "section": section_name,
                        "fields": fields,
                    }
        return dynamic

    def _load_ini_data(self, filename: str) -> List[Dict]:
        """加载指定INI文件的数据"""
        if not self.game_path:
            return []
        path = os.path.join(self.game_path, "Setting", filename)
        if not os.path.exists(path):
            return []
        parser = IniParser()
        parser.load(path)
        schemas = self._get_batch_schemas()
        schema = schemas.get(filename, {})
        section_name = schema.get("section", "")
        sections = parser.get_all_sections(section_name) if section_name else parser.sections
        return [dict(s.entries) for s in sections]

    def _save_ini_data(self, filename: str, data: List[Dict]) -> bool:
        """保存INI文件数据"""
        if not self.game_path:
            return False
        path = os.path.join(self.game_path, "Setting", filename)
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        schemas = self._get_batch_schemas()
        schema = schemas.get(filename, {})
        section_name = schema.get("section", "")
        parser = IniParser()
        parser.load(path)
        parser.replace_sections(section_name, data, "No")
        parser.save(path)
        return True

    def _apply_numeric_op(self, old_val: int, op: str, value: int) -> int:
        """应用数值操作"""
        if op == "add":
            return old_val + value
        elif op == "sub":
            return max(0, old_val - value)
        elif op == "mul":
            return int(old_val * value)
        elif op == "set":
            return value
        elif op == "cap":
            return min(old_val, value)
        return old_val

    def api_batch_preview(self, file: str, field: str, op: str, value: int,
                          filterField: str = None, filterValue: str = None) -> dict:
        """预览批量数值修改"""
        data = self._load_ini_data(file)
        if not data:
            return {"success": False, "message": f"无法加载 {file}"}

        preview = []
        for entry in data:
            if filterField and filterValue:
                if str(entry.get(filterField, "")) != str(filterValue):
                    continue
            old_val = int(entry.get(field, 0))
            new_val = self._apply_numeric_op(old_val, op, value)
            preview.append({
                "id": entry.get("No", ""),
                "name": entry.get("Name", ""),
                "oldVal": old_val,
                "newVal": new_val,
            })

        return {"success": True, "preview": preview, "count": len(preview)}

    def api_batch_execute(self, file: str, field: str, op: str, value: int,
                          filterField: str = None, filterValue: str = None) -> dict:
        """执行批量数值修改"""
        data = self._load_ini_data(file)
        if not data:
            return {"success": False, "message": f"无法加载 {file}"}

        modified = 0
        preview = []
        for entry in data:
            if filterField and filterValue:
                if str(entry.get(filterField, "")) != str(filterValue):
                    continue
            old_val = int(entry.get(field, 0))
            new_val = self._apply_numeric_op(old_val, op, value)
            if old_val != new_val:
                entry[field] = str(new_val)
                modified += 1
            preview.append({
                "id": entry.get("No", ""),
                "name": entry.get("Name", ""),
                "oldVal": old_val,
                "newVal": new_val,
            })

        if modified > 0:
            self._save_ini_data(file, data)

        # 刷新缓存
        if file == "General01.ini":
            self._general_cache = data

        return {"success": True, "message": f"修改了 {modified} 条记录", "preview": preview, "modified": modified}

    def api_batch_clone_preview(self, source: int, from_: int, to: int, type: str) -> dict:
        """预览批量复制技能"""
        if not self._general_cache:
            self._general_cache = self._load_ini_data("General01.ini")

        # 查找源武将
        source_general = None
        for g in self._general_cache:
            if int(g.get("No", 0)) == source:
                source_general = g
                break

        if not source_general:
            return {"success": False, "message": f"未找到武将 #{source}"}

        targets = []
        for g in self._general_cache:
            no = int(g.get("No", 0))
            if from_ <= no <= to and no != source:
                skill_count = 0
                for i in range(1, 9):
                    if g.get(f"Skill{i}"):
                        skill_count += 1
                targets.append({"id": no, "name": g.get("Name", ""), "skillCount": skill_count})

        return {"success": True, "targets": targets, "sourceName": source_general.get("Name", "")}

    def api_batch_clone_execute(self, source: int, from_: int, to: int, type: str) -> dict:
        """执行批量复制技能"""
        if not self._general_cache:
            self._general_cache = self._load_ini_data("General01.ini")

        source_general = None
        for g in self._general_cache:
            if int(g.get("No", 0)) == source:
                source_general = g
                break

        if not source_general:
            return {"success": False, "message": f"未找到武将 #{source}"}

        modified = 0
        for g in self._general_cache:
            no = int(g.get("No", 0))
            if from_ <= no <= to and no != source:
                if type in ("skills", "all"):
                    for i in range(1, 9):
                        g[f"Skill{i}"] = source_general.get(f"Skill{i}", "")
                if type in ("strategies", "all"):
                    for i in range(1, 5):
                        g[f"Strategy{i}"] = source_general.get(f"Strategy{i}", "")
                if type in ("traits", "all"):
                    for i in range(1, 4):
                        g[f"Feature{i}"] = source_general.get(f"Feature{i}", "")
                if type in ("soldiers", "all"):
                    for i in range(1, 4):
                        g[f"Soldier{i}"] = source_general.get(f"Soldier{i}", "")
                modified += 1

        if modified > 0:
            self._save_ini_data("General01.ini", self._general_cache)

        return {"success": True, "message": f"已复制到 {modified} 个武将", "modified": modified}

    def api_batch_search(self, find: str, replace: str = None, isRegex: bool = False,
                         caseSensitive: bool = False, scope: List[str] = None) -> dict:
        """全局查找"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        import re
        results = []
        total_matches = 0

        for filename in (scope or []):
            path = os.path.join(self.game_path, "Setting", filename)
            if not os.path.exists(path):
                continue

            matches = []
            try:
                with open(path, "r", encoding="big5", errors="replace") as f:
                    lines = f.readlines()

                for line_num, line in enumerate(lines, 1):
                    if isRegex:
                        flags = 0 if caseSensitive else re.IGNORECASE
                        try:
                            if re.search(find, line, flags):
                                matches.append(f"[行{line_num}] {line.strip()}")
                                total_matches += 1
                        except re.error:
                            return {"success": False, "message": f"正则表达式错误: {find}"}
                    else:
                        if caseSensitive:
                            if find in line:
                                matches.append(f"[行{line_num}] {line.strip()}")
                                total_matches += 1
                        else:
                            if find.lower() in line.lower():
                                matches.append(f"[行{line_num}] {line.strip()}")
                                total_matches += 1
            except Exception as e:
                logger.warning(f"批量搜索文件失败 {path}: {e}")
                continue

            if matches:
                results.append({"file": filename, "matches": matches})

        return {"success": True, "results": results, "totalMatches": total_matches}

    def api_batch_search_replace(self, find: str, replace: str, isRegex: bool = False,
                                  caseSensitive: bool = False, scope: List[str] = None) -> dict:
        """全局查找替换"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        import re
        results = []
        total_matches = 0
        total_replaced = 0

        for filename in (scope or []):
            path = os.path.join(self.game_path, "Setting", filename)
            if not os.path.exists(path):
                continue

            if self.backup_mgr:
                self.backup_mgr.backup_file(path)

            try:
                with open(path, "r", encoding="big5", errors="replace") as f:
                    content = f.read()

                if isRegex:
                    flags = 0 if caseSensitive else re.IGNORECASE
                    try:
                        new_content, count = re.subn(find, replace, content, flags=flags)
                        total_replaced += count
                    except re.error:
                        return {"success": False, "message": f"正则表达式错误: {find}"}
                else:
                    if caseSensitive:
                        count = content.count(find)
                        new_content = content.replace(find, replace)
                    else:
                        pattern = re.compile(re.escape(find), re.IGNORECASE)
                        new_content, count = pattern.subn(replace, content)
                    total_replaced += count

                if count > 0:
                    total_matches += count
                    with open(path, "w", encoding="big5") as f:
                        f.write(new_content)
                    results.append({"file": filename, "matches": [f"替换了 {count} 处"], "count": count})

            except Exception as e:
                results.append({"file": filename, "matches": [f"错误: {str(e)}"]})

        return {
            "success": True,
            "message": f"在 {len(results)} 个文件中替换了 {total_replaced} 处",
            "results": results,
            "totalMatches": total_matches,
            "totalReplaced": total_replaced,
        }

    # ============================================================
    # API: 差异对比
    # ============================================================

    def api_get_diff_backups(self, file: str) -> dict:
        """获取指定文件的备份列表"""
        if not self.backup_mgr:
            return {"success": True, "backups": []}

        backups = self.backup_mgr.get_backup_list(file)
        return {"success": True, "backups": backups}

    def api_diff_compare(self, file: str, backup_id: str) -> dict:
        """对比当前文件与备份"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        current_path = os.path.join(self.game_path, "Setting", file)
        if not os.path.exists(current_path):
            return {"success": False, "message": f"当前文件不存在: {file}"}

        if not self.backup_mgr:
            return {"success": False, "message": "备份管理器未初始化"}

        backup_path = self.backup_mgr.get_backup_path(file, backup_id)
        if not backup_path or not os.path.exists(backup_path):
            return {"success": False, "message": "备份文件不存在"}

        # 解析当前文件和备份文件
        parser_cur = IniParser()
        parser_cur.load(current_path)

        parser_old = IniParser()
        parser_old.load(backup_path)

        schema = self._get_batch_schemas().get(file, {})
        section_name = schema.get("section", "")

        cur_data = {}
        for s in parser_cur.get_all_sections(section_name):
            entries = dict(s.entries)
            no = entries.get("No", "")
            cur_data[no] = entries

        old_data = {}
        for s in parser_old.get_all_sections(section_name):
            entries = dict(s.entries)
            no = entries.get("No", "")
            old_data[no] = entries

        entries = []
        counts = {"added": 0, "modified": 0, "deleted": 0, "unchanged": 0}

        # 检查新增和修改
        for no, cur in cur_data.items():
            if no not in old_data:
                counts["added"] += 1
                entries.append({
                    "id": no,
                    "name": cur.get("Name", ""),
                    "type": "added",
                    "changes": [{"field": k, "oldVal": "(无)", "newVal": str(v)} for k, v in cur.items() if k != "No"],
                })
            else:
                old = old_data[no]
                changes = []
                for k, v in cur.items():
                    if k == "No":
                        continue
                    old_v = old.get(k, "")
                    if str(v) != str(old_v):
                        changes.append({"field": k, "oldVal": str(old_v), "newVal": str(v)})
                if changes:
                    counts["modified"] += 1
                    entries.append({
                        "id": no,
                        "name": cur.get("Name", ""),
                        "type": "modified",
                        "changes": changes,
                    })
                else:
                    counts["unchanged"] += 1

        # 检查删除
        for no, old in old_data.items():
            if no not in cur_data:
                counts["deleted"] += 1
                entries.append({
                    "id": no,
                    "name": old.get("Name", ""),
                    "type": "deleted",
                    "changes": [{"field": k, "oldVal": str(v), "newVal": "(已删除)"} for k, v in old.items() if k != "No"],
                })

        return {
            "success": True,
            "counts": counts,
            "entries": entries,
            "file": file,
            "backupId": backup_id,
        }

    def api_diff_export(self, diff_data: dict = None) -> dict:
        """导出差异报告"""
        if not diff_data:
            return {"success": False, "message": "无差异数据"}

        export_dir = os.path.join(PROJECT_ROOT, "exports", "diff_reports")
        os.makedirs(export_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"diff_{diff_data.get('file', 'unknown')}_{timestamp}.txt"
        path = os.path.join(export_dir, filename)

        with open(path, "w", encoding="utf-8") as f:
            f.write(f"差异报告: {diff_data.get('file', '')}\n")
            f.write(f"生成时间: {timestamp}\n")
            f.write("=" * 60 + "\n\n")
            counts = diff_data.get("counts", {})
            f.write(f"新增: {counts.get('added', 0)}  修改: {counts.get('modified', 0)}  删除: {counts.get('deleted', 0)}  未变更: {counts.get('unchanged', 0)}\n\n")
            for entry in diff_data.get("entries", []):
                type_label = {"added": "新增", "modified": "修改", "deleted": "删除", "unchanged": "未变更"}.get(entry.get("type", ""), "")
                f.write(f"[{type_label}] #{entry.get('id', '')} {entry.get('name', '')}\n")
                for change in entry.get("changes", []):
                    f.write(f"  {change['field']}: {change['oldVal']} → {change['newVal']}\n")
                f.write("\n")

        return {"success": True, "message": f"差异报告已导出到 {path}", "path": path}

    # ============================================================
    # API: MOD管理（增强版）
    # ============================================================

    def api_get_mod_list(self) -> dict:
        """获取MOD列表（含文件统计）"""
        mod_dir = os.path.join(PROJECT_ROOT, "mods")
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
        active_path = os.path.join(PROJECT_ROOT, "active_mod.txt")
        active = None
        if os.path.exists(active_path):
            with open(active_path, "r", encoding="utf-8") as f:
                active = f.read().strip()
        return {"success": True, "active": active}

    def api_set_active_mod(self, name: str) -> dict:
        """设置当前活跃MOD"""
        mod_dir = os.path.join(PROJECT_ROOT, "mods", name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{name}' 不存在"}

        active_path = os.path.join(PROJECT_ROOT, "active_mod.txt")
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

        mod_dir = os.path.join(PROJECT_ROOT, "mods", safe_name)
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
        mod_dir = os.path.join(PROJECT_ROOT, "mods", name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{name}' 不存在"}

        shutil.rmtree(mod_dir)

        # 如果删除的是活跃MOD，清除活跃状态
        active_path = os.path.join(PROJECT_ROOT, "active_mod.txt")
        if os.path.exists(active_path):
            with open(active_path, "r", encoding="utf-8") as f:
                active = f.read().strip()
            if active == name:
                os.remove(active_path)

        return {"success": True, "message": f"MOD工程 '{name}' 已删除"}

    def api_mod_snapshot(self, name: str) -> dict:
        """创建当前游戏数据快照（用于增量对比）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        mod_dir = os.path.join(PROJECT_ROOT, "mods", name)
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
            return {"success": False, "message": "请先设置游戏目录"}

        mod_dir = os.path.join(PROJECT_ROOT, "mods", mod_name)
        if not os.path.exists(mod_dir):
            return {"success": False, "message": f"MOD '{mod_name}' 不存在"}

        export_dir = os.path.join(PROJECT_ROOT, "exports", mod_name)
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
            "install_instructions": "将 Setting/ 复制到游戏目录，Shape/ 合并到游戏目录 Shape/，Script/ 复制到游戏目录，如有 EXE 替换原文件",
        }
        info_path = os.path.join(mod_dir, "mod_info.json")
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                mod_info.update({k: v for k, v in existing.items() if k in mod_info})
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
            except Exception:
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
                        except Exception:
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
        zip_path = os.path.join(PROJECT_ROOT, "exports", f"{mod_name}_v{mod_info['version']}.zip")
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
            return {"success": False, "message": "请先设置游戏目录"}
        # 1. 先检查是否有活跃MOD
        if not mod_name:
            return {"success": False, "message": "请先创建或选择一个MOD工程"}
        # 2. 自动创建快照
        snap_res = self.api_mod_snapshot(mod_name)
        if not snap_res.get("success"):
            return {"success": False, "message": f"快照创建失败: {snap_res.get('message', '')}"}
        # 3. 执行增量打包
        pack_res = self.api_pack_mod_incremental(mod_name)
        if pack_res.get("success"):
            pack_res["snapshot"] = snap_res.get("snapshot", "")
            pack_res["message"] = f"一键打包完成！共 {pack_res.get('changedCount', 0)} 个变更文件，{pack_res.get('zipSize', 0)}MB\nZIP: {pack_res.get('zipPath', '')}"
        return pack_res

    def api_import_mod(self, import_name: str = None, auto_remap: bool = True, backup_first: bool = True) -> dict:
        """导入MOD（从导出的MOD包导入）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

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
        mod_dir = os.path.join(PROJECT_ROOT, "mods", final_name)
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
            return {"success": False, "message": "请先设置游戏目录"}

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

                with open(file_path, "w", encoding="big5") as f:
                    f.write(content)
                remapped += 1
            except Exception as e:
                logger.warning(f"重映射写入失败 {file_path}: {e}")
                continue

        return {"success": True, "message": f"已重映射 {remapped} 个冲突", "remapped": remapped}

    # ============================================================
    # API: MOD 安装/卸载
    # ============================================================

    def api_install_mod(self, mod_name: str) -> dict:
        """安装MOD：将 exports/ 中的MOD文件复制到游戏目录，并记录安装状态"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        export_dir = os.path.join(PROJECT_ROOT, "exports", mod_name)
        if not os.path.exists(export_dir):
            return {"success": False, "message": f"MOD包 '{mod_name}' 不存在，请先打包"}

        # 读取MOD元数据
        info_path = os.path.join(export_dir, "mod_info.json")
        mod_info = {}
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    mod_info = json.load(f)
            except Exception:
                logger.warning("读取mod_info.json失败，将使用默认配置")
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
        install_log = os.path.join(PROJECT_ROOT, "mods", ".installed_mods.json")
        installed_mods = {}
        if os.path.exists(install_log):
            try:
                with open(install_log, "r", encoding="utf-8") as f:
                    installed_mods = json.load(f)
            except Exception:
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
            return {"success": False, "message": "请先设置游戏目录"}

        install_log = os.path.join(PROJECT_ROOT, "mods", ".installed_mods.json")
        if not os.path.exists(install_log):
            return {"success": False, "message": "没有已安装的MOD记录"}

        try:
            with open(install_log, "r", encoding="utf-8") as f:
                installed_mods = json.load(f)
        except Exception:
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
        install_log = os.path.join(PROJECT_ROOT, "mods", ".installed_mods.json")
        if not os.path.exists(install_log):
            return {"success": True, "mods": {}}
        try:
            with open(install_log, "r", encoding="utf-8") as f:
                mods = json.load(f)
            return {"success": True, "mods": mods}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_launch_game(self, mod_name: str = None) -> dict:
        """启动游戏（可指定MOD名称）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
                install_log = os.path.join(PROJECT_ROOT, "mods", ".installed_mods.json")
                if os.path.exists(install_log):
                    with open(install_log, "r", encoding="utf-8") as f:
                        installed = json.load(f)
                    if mod_name not in installed:
                        return {"success": False, "message": f"MOD '{mod_name}' 未安装，请先安装"}
            # 使用 subprocess 启动游戏（非阻塞）
            import subprocess
            if os.name == 'nt':
                subprocess.Popen([exe_path], cwd=cwd, shell=True)
            else:
                subprocess.Popen([exe_path], cwd=cwd)
            return {"success": True, "message": "游戏已启动" + (f" (MOD: {mod_name})" if mod_name else "")}
        except Exception as e:
            return {"success": False, "message": f"启动失败: {str(e)}"}


    # ============================================================
    # API: language.DAT 语言标识编辑
    # ============================================================
    def api_read_language_dat(self) -> dict:
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        path = os.path.join(self.game_path, "language.DAT")
        if not os.path.exists(path):
            return {"success": True, "current": "BIG5", "message": "language.DAT 不存在，默认为BIG5"}
        with open(path, "rb") as f:
            raw = f.read()
        val = raw.decode("ascii", errors="replace").strip()
        if val.startswith("LANG_"):
            val = val[5:]
        return {"success": True, "current": val, "raw": list(raw)}
    def api_write_language_dat(self, lang: str) -> dict:
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if lang not in ("BIG5", "GB", "SJIS", "KOR"):
            return {"success": False, "message": f"不支持的语言: {lang}，支持: BIG5/GB/SJIS/KOR"}
        path = os.path.join(self.game_path, "language.DAT")
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        with open(path, "wb") as f:
            f.write(f"LANG_{lang}".encode("ascii"))
        return {"success": True, "message": f"language.DAT 已切换为: LANG_{lang}", "current": lang}
    def api_switch_language_preset(self, lang: str) -> dict:
        """一键切换语言：同步 language.DAT + font.ini + 三个文本INI"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if lang not in ("BIG5", "GB", "SJIS", "KOR"):
            return {"success": False, "message": f"不支持的语言: {lang}"}
        lang_map = {"BIG5": "", "GB": "gb", "SJIS": "jp", "KOR": "ko"}
        suffix = lang_map.get(lang, "")
        switched = []
        try:
            # 1. language.DAT
            dat_path = os.path.join(self.game_path, "language.DAT")
            if self.backup_mgr:
                self.backup_mgr.backup_file(dat_path)
            with open(dat_path, "wb") as f:
                f.write(f"LANG_{lang}".encode("ascii"))
            switched.append("language.DAT")
            # 2. font.ini (从备份文件复制)
            font_src = os.path.join(self.game_path, "Setting", f"font.ini_{suffix}" if suffix else "font.ini")
            font_dst = os.path.join(self.game_path, "Setting", "font.ini")
            if os.path.exists(font_src):
                if self.backup_mgr:
                    self.backup_mgr.backup_file(font_dst)
                import shutil
                shutil.copy2(font_src, font_dst)
                switched.append("font.ini")
            # 3. TermText.ini
            for ini_name in ("TermText", "SystemText", "GossipText"):
                src = os.path.join(self.game_path, "Setting", f"{ini_name}.ini_{suffix}.txt" if suffix else f"{ini_name}.ini")
                dst = os.path.join(self.game_path, "Setting", f"{ini_name}.ini")
                if os.path.exists(src):
                    if self.backup_mgr:
                        self.backup_mgr.backup_file(dst)
                    import shutil
                    shutil.copy2(src, dst)
                    switched.append(f"{ini_name}.ini")
            # 刷新 TermText 缓存
            try:
                self.term_text = TermTextManager(self.game_path)
                self.term_text.load()
            except Exception as e:
                logger.warning(f"TermText刷新失败: {e}")
            return {"success": True, "message": f"语言已切换为 {lang}", "switched": switched}
        except Exception as e:
            return {"success": False, "message": f"切换失败: {str(e)}", "switched": switched}

    def api_export_language_pack(self, target_path: str = None) -> dict:
        """导出当前语言包为ZIP文件（含 language.DAT + font.ini + 三个文本INI）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        import zipfile, io
        # 读取当前语言
        lang = "BIG5"
        dat_path = os.path.join(self.game_path, "language.DAT")
        if os.path.exists(dat_path):
            with open(dat_path, "rb") as f:
                raw = f.read()
            val = raw.decode("ascii", errors="replace").strip()
            if val.startswith("LANG_"):
                lang = val[5:]

        if not target_path:
            target_path = os.path.join(self.game_path, f"lang_pack_{lang}.zip")

        files_to_pack = [
            ("language.DAT", dat_path),
            ("Setting/font.ini", os.path.join(self.game_path, "Setting", "font.ini")),
            ("Setting/TermText.ini", os.path.join(self.game_path, "Setting", "TermText.ini")),
            ("Setting/SystemText.ini", os.path.join(self.game_path, "Setting", "SystemText.ini")),
            ("Setting/GossipText.ini", os.path.join(self.game_path, "Setting", "GossipText.ini")),
        ]

        packed = []
        try:
            with zipfile.ZipFile(target_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # 添加元数据
                meta = {"language": lang, "exported_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"), "tool": "San7ModMaker V2.3"}
                zf.writestr("pack_meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
                for arcname, fpath in files_to_pack:
                    if os.path.exists(fpath):
                        zf.write(fpath, arcname)
                        packed.append(arcname)
            size_kb = round(os.path.getsize(target_path) / 1024, 1)
            return {"success": True, "message": f"语言包已导出: {os.path.basename(target_path)} ({size_kb} KB)", "path": target_path, "files": packed, "language": lang, "size_kb": size_kb}
        except Exception as e:
            return {"success": False, "message": f"导出失败: {str(e)}"}

    def api_import_language_pack(self, file_path: str) -> dict:
        """导入语言包ZIP文件"""
        import zipfile
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if not os.path.exists(file_path):
            return {"success": False, "message": "文件不存在"}
        if not file_path.lower().endswith(".zip"):
            return {"success": False, "message": "仅支持 .zip 格式的语言包"}

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()
                # 验证包结构
                if "language.DAT" not in names:
                    return {"success": False, "message": "无效的语言包: 缺少 language.DAT"}
                if "pack_meta.json" in names:
                    meta = json.loads(zf.read("pack_meta.json"))
                    lang = meta.get("language", "?")
                else:
                    lang = "?"

                imported = []
                for name in names:
                    if name == "pack_meta.json":
                        continue
                    target = os.path.join(self.game_path, name)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    if self.backup_mgr and os.path.exists(target):
                        self.backup_mgr.backup_file(target)
                    with open(target, "wb") as f:
                        f.write(zf.read(name))
                    imported.append(name)

            return {"success": True, "message": f"语言包已导入 ({lang}): {len(imported)} 个文件", "files": imported, "language": lang}
        except Exception as e:
            return {"success": False, "message": f"导入失败: {str(e)}"}

    def api_diff_language_texts(self, source_lang: str = "BIG5") -> dict:
        """对比当前语言与源语言的文本差异"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        # 获取当前语言
        current_lang = "BIG5"
        dat_path = os.path.join(self.game_path, "language.DAT")
        if os.path.exists(dat_path):
            with open(dat_path, "rb") as f:
                raw = f.read()
            val = raw.decode("ascii", errors="replace").strip()
            if val.startswith("LANG_"):
                current_lang = val[5:]

        if current_lang == source_lang:
            return {"success": True, "diff": {}, "message": "当前语言与源语言相同，无差异", "current": current_lang, "source": source_lang}

        # 尝试加载源语言文件
        suffix_map = {"BIG5": "", "GB": "gb", "SJIS": "jp", "KOR": "ko"}
        src_suffix = suffix_map.get(source_lang, "")
        cur_suffix = suffix_map.get(current_lang, "")

        results = {}
        for ini_name in ("TermText", "SystemText", "GossipText"):
            src_path = os.path.join(self.game_path, "Setting", f"{ini_name}.ini_{src_suffix}.txt" if src_suffix else f"{ini_name}.ini")
            cur_path = os.path.join(self.game_path, "Setting", f"{ini_name}.ini")

            if not os.path.exists(src_path):
                results[ini_name] = {"status": "source_missing", "message": f"源语言文件不存在: {src_path}"}
                continue

            parser = IniParser()
            parser.load(cur_path)
            cur_data = {}
            for s in parser.get_all_sections():
                e = dict(s.entries)
                no = e.get("No", "")
                if no:
                    cur_data[no] = e.get("Text", e.get("Name", ""))

            parser2 = IniParser()
            parser2.load(src_path)
            src_data = {}
            for s in parser2.get_all_sections():
                e = dict(s.entries)
                no = e.get("No", "")
                if no:
                    src_data[no] = e.get("Text", e.get("Name", ""))

            added = [k for k in cur_data if k not in src_data]
            removed = [k for k in src_data if k not in cur_data]
            changed = [(k, src_data[k], cur_data[k]) for k in cur_data if k in src_data and cur_data[k] != src_data[k]]

            results[ini_name] = {
                "total_current": len(cur_data),
                "total_source": len(src_data),
                "added": len(added),
                "removed": len(removed),
                "changed": len(changed),
                "changed_samples": [{"No": k, "source": s, "current": c} for k, s, c in changed[:20]],
                "added_samples": added[:10],
                "removed_samples": removed[:10],
            }

        return {
            "success": True,
            "diff": results,
            "current": current_lang,
            "source": source_lang,
            "total_changes": sum(r.get("changed", 0) + r.get("added", 0) + r.get("removed", 0) for r in results.values()),
        }

    def api_reload_termtext(self) -> dict:
        """语言切换后重新加载 TermTextManager 缓存"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            self.term_text = TermTextManager(self.game_path)
            self.term_text.load()
            return {"success": True, "message": "TermText 缓存已刷新", "count": len(self.term_text._data) if hasattr(self.term_text, '_data') else 0}
        except Exception as e:
            return {"success": False, "message": f"刷新失败: {str(e)}"}

    def api_language_status(self) -> dict:
        """获取语言系统完整状态（检测所有可用语言文件）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        # 当前语言
        current_lang = "BIG5"
        dat_path = os.path.join(self.game_path, "language.DAT")
        if os.path.exists(dat_path):
            with open(dat_path, "rb") as f:
                raw = f.read()
            val = raw.decode("ascii", errors="replace").strip()
            if val.startswith("LANG_"):
                current_lang = val[5:]

        # 检测可用语言
        available = []
        for lang, suffix in [("BIG5", ""), ("GB", "gb"), ("SJIS", "jp"), ("KOR", "ko")]:
            lang_files = {}
            for ini_name in ("TermText", "SystemText", "GossipText"):
                fpath = os.path.join(self.game_path, "Setting", f"{ini_name}.ini_{suffix}.txt" if suffix else f"{ini_name}.ini")
                lang_files[ini_name] = os.path.exists(fpath)
            font_path = os.path.join(self.game_path, "Setting", f"font.ini_{suffix}" if suffix else "font.ini")
            lang_files["font"] = os.path.exists(font_path)
            all_ok = all(lang_files.values())
            available.append({
                "lang": lang,
                "label": {"BIG5": "繁体中文", "GB": "简体中文", "SJIS": "日文", "KOR": "韩文"}.get(lang, lang),
                "is_current": lang == current_lang,
                "files": lang_files,
                "complete": all_ok,
                "missing": [k for k, v in lang_files.items() if not v],
            })

        return {
            "success": True,
            "current": current_lang,
            "available": available,
            "has_language_dat": os.path.exists(dat_path),
        }

    # ============================================================
    # API: 小地图 BMP→RAW 转换
    # ============================================================
    def api_bmp2raw(self, bmp_path: str) -> dict:
        """将382×270的BMP图片转换为游戏小地图RAW格式"""
        import struct
        if not os.path.exists(bmp_path):
            return {"success": False, "message": "BMP文件不存在"}
        try:
            with open(bmp_path, "rb") as f:
                # 读取BMP头
                header = f.read(54)
                if header[0:2] != b"BM":
                    return {"success": False, "message": "不是有效的BMP文件"}
                width = struct.unpack("<I", header[18:22])[0]
                height = struct.unpack("<I", header[22:26])[0]
                if width != 382 or height != 270:
                    return {"success": False, "message": f"BMP尺寸必须为382×270，当前为{width}×{height}"}
                # 读取BMP数据（BMP 24-bit）
                row_size = (width * 3 + 3) ^ ~3 + 1
                raw_data = bytearray()
                for y in range(height - 1, -1, -1):
                    f.seek(54 + y * row_size)
                    row = f.read(width * 3)
                    for x in range(width):
                        b = row[x * 3]
                        g = row[x * 3 + 1]
                        r = row[x * 3 + 2]
                        # 转RGB565
                        r5 = (r >> 3) & 0x1F
                        g6 = (g >> 2) & 0x3F
                        b5 = (b >> 3) & 0x1F
                        val = (r5 << 11) | (g6 << 5) | b5
                        raw_data.append(val & 0xFF)
                        raw_data.append((val >> 8) & 0xFF)
                # 写RAW
                raw_path = bmp_path.rsplit(".", 1)[0] + ".raw"
                with open(raw_path, "wb") as out:
                    out.write(bytes(raw_data))
                return {"success": True, "message": f"转换成功: {raw_path}", "raw_path": raw_path, "size": len(raw_data)}
        except Exception as e:
            return {"success": False, "message": f"转换失败: {str(e)}"}
    # ============================================================
    # API: 窗口模式分辨率预设
    # ============================================================
    def api_apply_resolution_preset(self, preset: str) -> dict:
        """应用分辨率预设: 1024x768/1280x720/1366x768/1440x900/1600x900/1920x1080/fullscreen"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": f"不支持的预设: {preset}，可用: {list(presets.keys())}"}
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
        return {"success": True, "message": f"分辨率已设置为 {label}", "width": w, "height": h, "fullscreen": fullscreen}

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
            return {"success": False, "message": f"坐标超出范围 (0~{self.MAP_WIDTH-1}, 0~{self.MAP_HEIGHT-1})"}
        gx = x // self.BLOCK_SIZE
        gy = y // self.BLOCK_SIZE
        block_no = gy * self.GRID_COLS + gx
        return {"success": True, "x": x, "y": y, "grid_x": gx, "grid_y": gy,
                "block_no": block_no, "block_size": self.BLOCK_SIZE,
                "grid_cols": self.GRID_COLS, "grid_rows": self.GRID_ROWS}

    def api_block_inverse(self, block_no: int) -> dict:
        """区块号→坐标范围转换"""
        if block_no < 0 or block_no >= self.GRID_COLS * self.GRID_ROWS:
            return {"success": False, "message": f"区块号超出范围 (0~{self.GRID_COLS * self.GRID_ROWS - 1})"}
        gy = block_no // self.GRID_COLS
        gx = block_no % self.GRID_COLS
        return {"success": True, "block_no": block_no, "grid_x": gx, "grid_y": gy,
                "x_min": gx * self.BLOCK_SIZE, "y_min": gy * self.BLOCK_SIZE,
                "x_max": (gx + 1) * self.BLOCK_SIZE - 1, "y_max": (gy + 1) * self.BLOCK_SIZE - 1,
                "block_size": self.BLOCK_SIZE, "grid_cols": self.GRID_COLS, "grid_rows": self.GRID_ROWS}

    def api_load_map_summary(self) -> dict:
        """加载地图摘要：城池坐标+建筑坐标+地形类型列表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": "请先设置游戏目录"}
        citypos_path = os.path.join(self.game_path, "Setting", "CityPos.ini")
        if not os.path.exists(citypos_path):
            return {"success": False, "message": "未找到 CityPos.ini"}
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
            return {"success": True, "message": f"已保存 {len(cities)} 个城池位置"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ============================================================
    # API: PCK 资源预览增强
    # ============================================================
    def api_pck_preview_shp(self, pck_name: str, internal_path: str) -> dict:
        """从PCK内直接预览SHP图片（返回base64 PNG）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        safe_pck = os.path.basename(pck_name)
        if safe_pck != pck_name or '..' in pck_name:
            return {"success": False, "message": "无效的PCK文件名"}
        pck_path = os.path.join(self.game_path, safe_pck)
        if not os.path.exists(pck_path):
            return {"success": False, "message": f"未找到 {pck_name}"}
        try:
            # 从PCK提取SHP二进制数据到内存
            with open(pck_path, "rb") as f:
                import struct
                magic = struct.unpack("<I", f.read(4))[0]
                if magic != 0x02000000:
                    return {"success": False, "message": "非标准PCK格式"}
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
                        return {"success": False, "message": "无法解码SHP图片"}
                return {"success": False, "message": f"PCK中未找到: {internal_path}"}
        except Exception as e:
            return {"success": False, "message": f"预览失败: {str(e)}"}

    # ============================================================
    # API: 运行时内存修改器
    # ============================================================
    def api_memory_attach(self) -> dict:
        """附加到游戏进程"""
        try:
            import pymem
            import pymem.process
            for proc in pymem.process.list_processes():
                try:
                    if proc.szExeFile and b'SG7' in proc.szExeFile:
                        pm = pymem.Pymem(proc.szExeFile.decode('gbk', errors='replace'))
                        self._memory_pm = pm
                        self._memory_process = proc.szExeFile.decode('gbk', errors='replace')
                        return {"success": True, "message": f"已附加到 {self._memory_process}",
                                "process": self._memory_process, "pid": proc.th32ProcessID}
                except (Exception,):
                    continue
            return {"success": False, "message": "未找到运行中的SG7.exe进程"}
        except ImportError:
            return {"success": False, "message": "pymem库未安装，请运行: pip install pymem"}

    def api_memory_read(self, address: int, size: int = 4) -> dict:
        """读取游戏内存"""
        if not hasattr(self, '_memory_pm') or not self._memory_pm:
            return {"success": False, "message": "请先附加到游戏进程 (memoryAttach)"}
        try:
            if size == 1:
                val = self._memory_pm.read_uchar(address)
            elif size == 2:
                val = self._memory_pm.read_ushort(address)
            elif size == 4:
                val = self._memory_pm.read_uint(address)
            else:
                val = self._memory_pm.read_bytes(address, size)
                return {"success": True, "address": address, "size": size, "value": list(val), "hex": val.hex()}
            return {"success": True, "address": address, "size": size, "value": val, "hex": hex(val)}
        except Exception as e:
            return {"success": False, "message": f"读取失败: {str(e)}"}

    def api_memory_write(self, address: int, value: int, size: int = 4) -> dict:
        """写入游戏内存"""
        if not hasattr(self, '_memory_pm') or not self._memory_pm:
            return {"success": False, "message": "请先附加到游戏进程 (memoryAttach)"}
        try:
            if size == 1:
                self._memory_pm.write_uchar(address, value)
            elif size == 2:
                self._memory_pm.write_ushort(address, value)
            elif size == 4:
                self._memory_pm.write_uint(address, value)
            else:
                return {"success": False, "message": "不支持的大小，仅支持 1/2/4 字节"}
            return {"success": True, "message": f"已写入 {hex(value)} 到 {hex(address)}"}
        except Exception as e:
            return {"success": False, "message": f"写入失败: {str(e)}"}

    def api_memory_search(self, value: int, size: int = 4) -> dict:
        """搜索内存值"""
        if not hasattr(self, '_memory_pm') or not self._memory_pm:
            return {"success": False, "message": "请先附加到游戏进程 (memoryAttach)"}
        try:
            import pymem.pattern
            if size == 4:
                pattern = value.to_bytes(4, 'little')
            elif size == 2:
                pattern = value.to_bytes(2, 'little')
            else:
                pattern = value.to_bytes(1, 'little')
            addrs = pymem.pattern.scan_pattern_page(self._memory_pm.process_handle, pattern, return_multiple=True)
            addrs = addrs[:20] if addrs else []
            return {"success": True, "count": len(addrs), "addresses": [hex(a) for a in addrs]}
        except Exception as e:
            return {"success": False, "message": f"搜索失败: {str(e)}"}

    # ============================================================
    # API: SANGO7.MPC 地形编辑器
    # ============================================================
    TERRAIN_NAMES = {0:"无",1:"草原",2:"乾草原",3:"荒地",4:"道路",5:"湿地",6:"森林",7:"丘陵",8:"高山",9:"沙漠",10:"河",11:"浅海",12:"深海",13:"残雪",14:"雪原",15:"雪丘",16:"雪山"}
    TERRAIN_COLORS = {0:"#2d5a27",1:"#4a8c3f",2:"#8b9a47",3:"#9e8b5e",4:"#c4a45a",5:"#5a7a3a",6:"#2d5a1e",7:"#7a8a5a",8:"#6a6a5a",9:"#d4c47a",10:"#3a6aaa",11:"#5a8aaa",12:"#2a4a7a",13:"#d4e4f4",14:"#e8f0f8",15:"#c8d8e8",16:"#f0f4f8"}

    def api_mpc_read(self, block_x: int = None, block_y: int = None, width: int = 546, height: int = 387) -> dict:
        """读取SANGO7.MPC地形数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        mpc_path = os.path.join(self.game_path, "map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            mpc_path = os.path.join(self.game_path, "Map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            return {"success": False, "message": "未找到 map/SANGO7.MPC"}
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
                return {"success": False, "message": "坐标超出范围"}
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
            return {"success": True, "data": sample, "summary": summary, "record_size": record_size,
                    "total_bytes": total, "grid_cols": self.GRID_COLS, "grid_rows": self.GRID_ROWS,
                    "expected_blocks": expected}
        except Exception as e:
            return {"success": False, "message": f"读取失败: {str(e)}"}

    def api_mpc_write(self, block_x: int, block_y: int, terrain: int) -> dict:
        """写入单个区块地形"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        mpc_path = os.path.join(self.game_path, "map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            mpc_path = os.path.join(self.game_path, "Map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            return {"success": False, "message": "未找到 map/SANGO7.MPC"}
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
                return {"success": True, "message": f"区块({block_x},{block_y})地形已设为{self.TERRAIN_NAMES.get(terrain,'?')}"}
            return {"success": False, "message": "坐标超出范围"}
        except Exception as e:
            return {"success": False, "message": f"写入失败: {str(e)}"}

    def api_mpc_batch_write(self, changes: list) -> dict:
        """批量写入地形: [{x,y,terrain},...]"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        mpc_path = os.path.join(self.game_path, "map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            mpc_path = os.path.join(self.game_path, "Map", "SANGO7.MPC")
        if not os.path.exists(mpc_path):
            return {"success": False, "message": "未找到 map/SANGO7.MPC"}
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
            return {"success": True, "message": f"已更新{count}个区块", "count": count}
        except Exception as e:
            return {"success": False, "message": f"批量写入失败: {str(e)}"}

    # ============================================================
    # API: Shape .info.ini 位移编辑器
    # ============================================================
    def api_shape_info_list(self, category: str = "all") -> dict:
        """列出所有 .info.ini 位移文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        shape_dir = os.path.join(self.game_path, "Shape")
        if not os.path.exists(shape_dir):
            return {"success": False, "message": "未找到Shape目录"}
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
            return {"success": False, "message": "请先设置游戏目录"}
        full = os.path.join(self.game_path, "Shape", rel_path)
        if not os.path.exists(full):
            return {"success": False, "message": "文件不存在"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(full)
        parser = IniParser()
        parser.load(full)
        parser.set("Offset", "X", str(x))
        parser.set("Offset", "Y", str(y))
        parser.save(full)
        return {"success": True, "message": f"已保存 {rel_path}: X={x}, Y={y}"}

    # ============================================================
    # API: CustomGen 自定义武将编辑
    # ============================================================
    def api_customgen_list(self) -> dict:
        """列出所有自定义武将"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        sav_path = os.path.join(self.game_path, "Save", "CustomGen.sav")
        if not os.path.exists(sav_path):
            return {"success": True, "generals": [], "count": 0, "message": "CustomGen.sav 不存在"}
        try:
            from core.save_editor import SaveEditor
            editor = SaveEditor(self.game_path)
            generals = editor.parse_customgen()
            return {"success": True, "generals": generals, "count": len(generals)}
        except Exception as e:
            return {"success": False, "message": f"解析失败: {str(e)}"}

    def api_customgen_get(self, index: int) -> dict:
        """获取单个自定义武将详情"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        sav_path = os.path.join(self.game_path, "Save", "CustomGen.sav")
        if not os.path.exists(sav_path):
            return {"success": False, "message": "CustomGen.sav 不存在"}
        try:
            from core.save_editor import SaveEditor
            editor = SaveEditor(self.game_path)
            general = editor.get_customgen_detail(index)
            if general:
                return {"success": True, "general": general}
            return {"success": False, "message": "索引超出范围"}
        except Exception as e:
            return {"success": False, "message": f"读取失败: {str(e)}"}

    def api_customgen_edit(self, index: int, field: str, value) -> dict:
        """编辑自定义武将字段"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        sav_path = os.path.join(self.game_path, "Save", "CustomGen.sav")
        if not os.path.exists(sav_path):
            return {"success": False, "message": "CustomGen.sav 不存在"}
        try:
            from core.save_editor import SaveEditor
            if self.backup_mgr:
                self.backup_mgr.backup_file(sav_path)
            editor = SaveEditor(self.game_path)
            result = editor.edit_customgen_field(index, field, value)
            return result
        except Exception as e:
            return {"success": False, "message": f"编辑失败: {str(e)}"}

    # ============================================================
    # API: 常用内存地址预设表
    # ============================================================
    MEMORY_PRESETS = {
        "金钱": {"address": 0x0095FDE0, "size": 4, "desc": "玩家金钱（4字节）"},
        "主角等级": {"address": 0x0095FD00, "size": 2, "desc": "主角当前等级"},
        "主角经验": {"address": 0x0095FD04, "size": 4, "desc": "主角当前经验值"},
        "队伍兵力": {"address": 0x0095FE00, "size": 2, "desc": "第一队兵力"},
        "时间-年": {"address": 0x0095F100, "size": 2, "desc": "游戏时间年份"},
        "时间-月": {"address": 0x0095F102, "size": 1, "desc": "游戏时间月份"},
        "时间-日": {"address": 0x0095F103, "size": 1, "desc": "游戏时间日期"},
        "国库-金": {"address": 0x0095FC00, "size": 4, "desc": "国库金币数量"},
        "国库-粮": {"address": 0x0095FC04, "size": 4, "desc": "国库粮草数量"},
        "人口": {"address": 0x0095FD10, "size": 2, "desc": "当前城池人口"},
        "民心": {"address": 0x0095FD14, "size": 2, "desc": "当前城池民心(0-1000)"},
        "防御": {"address": 0x0095FD18, "size": 2, "desc": "当前城池防御值"},
        "开发": {"address": 0x0095FD1C, "size": 2, "desc": "当前城池开发值"},
        "武将体力": {"address": 0x0095FE80, "size": 2, "desc": "主角当前体力HP"},
        "武将技力": {"address": 0x0095FE84, "size": 2, "desc": "主角当前技力MP"},
        "武将武力": {"address": 0x0095FE88, "size": 1, "desc": "主角基础武力"},
        "武将智力": {"address": 0x0095FE89, "size": 1, "desc": "主角基础智力"},
        "武将功勋": {"address": 0x0095FE90, "size": 4, "desc": "主角当前功勋值"},
        "战斗计时": {"address": 0x0095FF00, "size": 2, "desc": "千人战剩余时间"},
        "士气": {"address": 0x0095FF10, "size": 2, "desc": "当前队伍士气"},
    }

    # reserved: 预留给未来功能，暂无前端调用
    def api_memory_presets(self) -> dict:
        return {"success": True, "presets": self.MEMORY_PRESETS, "count": len(self.MEMORY_PRESETS)}

    def api_memory_read_preset(self, preset_name: str) -> dict:
        """使用预设名称读取内存"""
        if not hasattr(self, '_memory_pm') or not self._memory_pm:
            return {"success": False, "message": "请先附加到游戏进程 (memoryAttach)"}
        preset = self.MEMORY_PRESETS.get(preset_name)
        if not preset:
            return {"success": False, "message": f"未知预设: {preset_name}，可用: {list(self.MEMORY_PRESETS.keys())}"}
        return self.api_memory_read(preset["address"], preset["size"])

    # ============================================================
    # API: SHP 批量改名
    # ============================================================
    def api_shp_batch_rename(self, directory: str, prefix: str, start_id: int, digits: int = 4) -> dict:
        """批量重命名SHP文件: prefix_0001.shp, prefix_0002.shp..."""
        if not os.path.isdir(directory):
            return {"success": False, "message": "目录不存在"}
        shp_files = sorted([f for f in os.listdir(directory) if f.lower().endswith('.shp')])
        if not shp_files:
            return {"success": False, "message": "目录中没有SHP文件"}
        renamed = []
        for i, old_name in enumerate(shp_files):
            new_name = f"{prefix}_{start_id + i:0{digits}d}.shp"
            old_path = os.path.join(directory, old_name)
            new_path = os.path.join(directory, new_name)
            if old_path != new_path:
                if os.path.exists(new_path):
                    return {"success": False, "message": f"目标文件已存在: {new_name}"}
                os.rename(old_path, new_path)
                renamed.append({"from": old_name, "to": new_name})
        return {"success": True, "message": f"已重命名{len(renamed)}个文件", "renamed": renamed, "count": len(renamed)}

    # ============================================================
    # API: 城池连接关系
    # ============================================================
    def api_city_connections(self) -> dict:
        """获取所有城池连接关系（用于可视化）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        city_path = os.path.join(self.game_path, "Setting", "City.ini")
        citypos_path = os.path.join(self.game_path, "Setting", "CityPos.ini")
        if not os.path.exists(city_path):
            return {"success": False, "message": "未找到 City.ini"}
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
            return {"success": False, "message": "请先设置游戏目录"}
        city_path = os.path.join(self.game_path, "Setting", "City.ini")
        if not os.path.exists(city_path):
            return {"success": False, "message": "未找到 City.ini"}
        parser = IniParser()
        parser.load(city_path)
        data = []
        for s in parser.get_all_sections("CITY"):
            data.append(dict(s.entries))
        return {"success": True, "data": data, "count": len(data)}

    def api_save_city_connect(self, data: list) -> dict:
        """保存城池连接数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": True, "message": "城池连接已保存", "count": len(data)}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_load_idini(self) -> dict:
        """加载 WinTest/id.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        idini_path = os.path.join(self.game_path, "WinTest", "id.ini")
        if not os.path.exists(idini_path):
            return {"success": True, "data": [], "count": 0, "message": "id.ini 不存在"}
        try:
            parser = IniParser()
            parser.load(idini_path)
            data = []
            for s in parser.get_all_sections("ID"):
                e = dict(s.entries)
                data.append({"key": e.get("key", ""), "value": e.get("value", "")})
            return {"success": True, "data": data, "count": len(data)}
        except Exception as e:
            return {"success": False, "message": f"加载失败: {str(e)}"}

    def api_save_idini(self, data: list) -> dict:
        """保存 WinTest/id.ini"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        idini_path = os.path.join(self.game_path, "WinTest", "id.ini")
        os.makedirs(os.path.dirname(idini_path), exist_ok=True)
        if self.backup_mgr:
            self.backup_mgr.backup_file(idini_path)
        try:
            parser = IniParser()
            for item in data:
                parser.add_section("ID", {"key": item.get("key", ""), "value": item.get("value", "")})
            parser.save(idini_path)
            return {"success": True, "message": f"已保存 {len(data)} 条"}
        except Exception as e:
            return {"success": False, "message": f"保存失败: {str(e)}"}

    # ============================================================
    # API: 脚本编辑器
    # ============================================================

    def api_list_scripts(self) -> dict:
        """列出 Script/ 目录下的剧本脚本文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        script_dir = os.path.join(self.game_path, "Script")
        if not os.path.exists(script_dir):
            return {"success": True, "files": [], "message": "Script 目录不存在"}
        files = []
        for f in sorted(os.listdir(script_dir)):
            fpath = os.path.join(script_dir, f)
            if os.path.isfile(fpath):
                files.append({
                    "name": f,
                    "size": os.path.getsize(fpath),
                    "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                })
        return {"success": True, "files": files, "count": len(files)}

    def api_read_script(self, filename: str) -> dict:
        """读取脚本文件内容"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        safe_name = os.path.basename(filename)
        if safe_name != filename or '..' in filename:
            return {"success": False, "message": "无效的文件名"}
        script_path = os.path.join(self.game_path, "Script", safe_name)
        if not os.path.exists(script_path):
            return {"success": False, "message": f"脚本文件不存在: {safe_name}"}
        try:
            # 尝试多种编码
            content = ""
            for enc in ["gbk", "utf-8", "latin-1"]:
                try:
                    with open(script_path, "r", encoding=enc) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            return {
                "success": True,
                "filename": safe_name,
                "content": content,
                "lines": content.count('\n') + 1,
                "size_kb": round(os.path.getsize(script_path) / 1024, 1),
            }
        except Exception as e:
            return {"success": False, "message": f"读取失败: {e}"}

    def api_save_script(self, filename: str, content: str) -> dict:
        """保存脚本文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        safe_name = os.path.basename(filename)
        if safe_name != filename or '..' in filename:
            return {"success": False, "message": "无效的文件名"}
        script_path = os.path.join(self.game_path, "Script", safe_name)
        if not os.path.exists(script_path):
            return {"success": False, "message": f"脚本文件不存在: {safe_name}"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(script_path)
        try:
            with open(script_path, "w", encoding="gbk") as f:
                f.write(content)
            return {"success": True, "message": f"已保存: {safe_name}"}
        except Exception as e:
            return {"success": False, "message": f"保存失败: {e}"}

    def api_new_script(self, filename: str) -> dict:
        """新建脚本文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        safe_name = os.path.basename(filename)
        if safe_name != filename or '..' in filename:
            return {"success": False, "message": "无效的文件名"}
        script_dir = os.path.join(self.game_path, "Script")
        os.makedirs(script_dir, exist_ok=True)
        script_path = os.path.join(script_dir, safe_name)
        if os.path.exists(script_path):
            return {"success": False, "message": f"文件已存在: {safe_name}"}
        try:
            with open(script_path, "w", encoding="gbk") as f:
                f.write(f"; {safe_name}\n; 新建脚本\n")
            return {"success": True, "message": f"已创建: {safe_name}", "filename": safe_name}
        except Exception as e:
            return {"success": False, "message": f"创建失败: {e}"}

    def api_delete_script(self, filename: str) -> dict:
        """删除脚本文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        safe_name = os.path.basename(filename)
        if safe_name != filename or '..' in filename:
            return {"success": False, "message": "无效的文件名"}
        script_path = os.path.join(self.game_path, "Script", safe_name)
        if not os.path.exists(script_path):
            return {"success": False, "message": f"文件不存在: {safe_name}"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(script_path)
        try:
            os.remove(script_path)
            return {"success": True, "message": f"已删除: {safe_name}"}
        except Exception as e:
            return {"success": False, "message": f"删除失败: {e}"}

    def api_rename_script(self, old_name: str, new_name: str) -> dict:
        """重命名脚本文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        safe_old = os.path.basename(old_name)
        safe_new = os.path.basename(new_name)
        if safe_old != old_name or '..' in old_name or safe_new != new_name or '..' in new_name:
            return {"success": False, "message": "无效的文件名"}
        old_path = os.path.join(self.game_path, "Script", safe_old)
        new_path = os.path.join(self.game_path, "Script", safe_new)
        if not os.path.exists(old_path):
            return {"success": False, "message": f"文件不存在: {safe_old}"}
        if os.path.exists(new_path):
            return {"success": False, "message": f"目标文件已存在: {safe_new}"}
        if self.backup_mgr:
            self.backup_mgr.backup_file(old_path)
        try:
            os.rename(old_path, new_path)
            return {"success": True, "message": f"已重命名: {safe_old} → {safe_new}", "old_name": safe_old, "new_name": safe_new}
        except Exception as e:
            return {"success": False, "message": f"重命名失败: {e}"}

    def api_global_search(self, query: str, search_type: str = "id", tables: List[str] = None) -> dict:
        """全局数据搜索：跨所有表按ID或值搜索"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        if not query or not query.strip():
            return {"success": False, "message": "请输入搜索内容"}
        query = query.strip()
        results = []

        # 默认搜索范围
        all_tables = tables or [
            "General01.ini", "Soldier.ini", "Thing.ini", "DefSkill.ini",
            "BFMagic.ini", "SFMagic.ini", "Title.ini", "Nation.ini",
            "City.ini", "GenSkill.ini", "ArmySkill.ini", "ArmyGroupSkill.ini",
            "SuperAtk.ini", "Formation.ini", "Format.ini", "City01.ini",
            "City02.ini", "City03.ini", "City04.ini", "City05.ini",
            "City06.ini", "City07.ini", "City08.ini", "City09.ini", "City10.ini",
            "GenLV.ini", "ItemEnhance.ini", "Age.ini", "Color.ini",
        ]

        for filename in all_tables:
            path = os.path.join(self.game_path, "Setting", filename)
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="big5", errors="replace") as f:
                    content = f.read()
                # 解析 INI 条目
                entries = re.split(r'\n\s*\n', content)
                file_matches = []
                for entry in entries:
                    lines = entry.strip().split('\n')
                    if not lines:
                        continue
                    # 提取 No 和 Name
                    no_val = ""
                    name_val = ""
                    for line in lines:
                        m = re.match(r'No\s*=\s*(.+)', line)
                        if m:
                            no_val = m.group(1).strip()
                        m = re.match(r'Name\s*=\s*(.+)', line)
                        if m:
                            name_val = m.group(1).strip()
                    # 按 ID 搜索
                    if search_type == "id" and no_val == query:
                        file_matches.append({"no": no_val, "name": name_val, "entry": entry.strip()[:500]})
                    elif search_type == "name" and query.lower() in name_val.lower():
                        file_matches.append({"no": no_val, "name": name_val, "entry": entry.strip()[:500]})
                    elif search_type == "value" and query.lower() in entry.lower():
                        file_matches.append({"no": no_val, "name": name_val, "entry": entry.strip()[:500]})
                if file_matches:
                    results.append({"file": filename, "matches": file_matches, "count": len(file_matches)})
            except Exception as e:
                logger.warning(f"全局搜索文件失败 {filename}: {e}")
                continue

        total = sum(r["count"] for r in results)
        return {"success": True, "query": query, "type": search_type, "results": results, "totalMatches": total}

    def api_balance_analysis(self, scope: str = "all") -> dict:
        """游戏平衡分析：统计武将/兵种/物品属性分布"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        setting_dir = os.path.join(self.game_path, "Setting")
        analysis = {}

        # 武将分析
        if scope in ("all", "generals"):
            gen_path = os.path.join(setting_dir, "General01.ini")
            if os.path.exists(gen_path):
                stats = {"count": 0, "wstr": [], "intelligence": [], "hp": [], "mp": [], "morale": []}
                try:
                    entries = self.api_load_generals().get("data", [])
                    for g in entries:
                        stats["count"] += 1
                        for k in ["wstr", "intelligence", "hp", "mp", "morale"]:
                            v = int(g.get(k, 0))
                            stats[k].append(v)
                    analysis["generals"] = {
                        "count": stats["count"],
                        "wstr": {"min": min(stats["wstr"]) if stats["wstr"] else 0, "max": max(stats["wstr"]) if stats["wstr"] else 0, "avg": round(sum(stats["wstr"])/len(stats["wstr"]), 1) if stats["wstr"] else 0},
                        "intelligence": {"min": min(stats["intelligence"]) if stats["intelligence"] else 0, "max": max(stats["intelligence"]) if stats["intelligence"] else 0, "avg": round(sum(stats["intelligence"])/len(stats["intelligence"]), 1) if stats["intelligence"] else 0},
                        "hp": {"min": min(stats["hp"]) if stats["hp"] else 0, "max": max(stats["hp"]) if stats["hp"] else 0, "avg": round(sum(stats["hp"])/len(stats["hp"]), 1) if stats["hp"] else 0},
                        "mp": {"min": min(stats["mp"]) if stats["mp"] else 0, "max": max(stats["mp"]) if stats["mp"] else 0, "avg": round(sum(stats["mp"])/len(stats["mp"]), 1) if stats["mp"] else 0},
                    }
                except Exception as e:
                    analysis["generals"] = {"error": str(e)}

        # 兵种分析
        if scope in ("all", "soldiers"):
            sol_path = os.path.join(setting_dir, "Soldier.ini")
            if os.path.exists(sol_path):
                stats = {"count": 0, "hp": [], "atk": [], "def": [], "speed": []}
                try:
                    entries = self.api_load_soldiers().get("data", [])
                    for s in entries:
                        stats["count"] += 1
                        for k in ["hp", "atk", "def", "speed"]:
                            v = int(s.get(k, 0))
                            stats[k].append(v)
                    analysis["soldiers"] = {
                        "count": stats["count"],
                        "hp": {"min": min(stats["hp"]) if stats["hp"] else 0, "max": max(stats["hp"]) if stats["hp"] else 0, "avg": round(sum(stats["hp"])/len(stats["hp"]), 1) if stats["hp"] else 0},
                        "atk": {"min": min(stats["atk"]) if stats["atk"] else 0, "max": max(stats["atk"]) if stats["atk"] else 0, "avg": round(sum(stats["atk"])/len(stats["atk"]), 1) if stats["atk"] else 0},
                        "def": {"min": min(stats["def"]) if stats["def"] else 0, "max": max(stats["def"]) if stats["def"] else 0, "avg": round(sum(stats["def"])/len(stats["def"]), 1) if stats["def"] else 0},
                    }
                except Exception as e:
                    analysis["soldiers"] = {"error": str(e)}

        # 物品分析
        if scope in ("all", "things"):
            thing_path = os.path.join(setting_dir, "Thing.ini")
            if os.path.exists(thing_path):
                stats = {"count": 0, "str": [], "int": [], "hp": [], "mp": [], "price": [], "type_dist": {}}
                try:
                    entries = self.api_load_things().get("data", [])
                    for t in entries:
                        stats["count"] += 1
                        ttype = str(t.get("Type", "?"))
                        stats["type_dist"][ttype] = stats["type_dist"].get(ttype, 0) + 1
                        for k in ["str", "int", "hp", "mp", "price"]:
                            v = int(t.get(k, 0))
                            if v > 0:
                                stats[k].append(v)
                    analysis["things"] = {
                        "count": stats["count"],
                        "type_distribution": stats["type_dist"],
                        "str": {"min": min(stats["str"]) if stats["str"] else 0, "max": max(stats["str"]) if stats["str"] else 0, "avg": round(sum(stats["str"])/len(stats["str"]), 1) if stats["str"] else 0},
                        "int": {"min": min(stats["int"]) if stats["int"] else 0, "max": max(stats["int"]) if stats["int"] else 0, "avg": round(sum(stats["int"])/len(stats["int"]), 1) if stats["int"] else 0},
                        "hp": {"min": min(stats["hp"]) if stats["hp"] else 0, "max": max(stats["hp"]) if stats["hp"] else 0, "avg": round(sum(stats["hp"])/len(stats["hp"]), 1) if stats["hp"] else 0},
                        "price": {"min": min(stats["price"]) if stats["price"] else 0, "max": max(stats["price"]) if stats["price"] else 0, "avg": round(sum(stats["price"])/len(stats["price"]), 1) if stats["price"] else 0},
                    }
                except Exception as e:
                    analysis["things"] = {"error": str(e)}

        return {"success": True, "analysis": analysis}

    def api_mod_merge(self, mod_a: str, mod_b: str, output_name: str = None) -> dict:
        """合并两个MOD"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        mods_dir = os.path.join(PROJECT_ROOT, "mods")
        mod_a_path = os.path.join(mods_dir, mod_a)
        mod_b_path = os.path.join(mods_dir, mod_b)
        if not os.path.exists(mod_a_path):
            return {"success": False, "message": f"MOD A 不存在: {mod_a}"}
        if not os.path.exists(mod_b_path):
            return {"success": False, "message": f"MOD B 不存在: {mod_b}"}

        output = output_name or f"{mod_a}+{mod_b}"
        output_path = os.path.join(mods_dir, output)
        if os.path.exists(output_path):
            return {"success": False, "message": f"输出MOD已存在: {output}"}

        os.makedirs(output_path, exist_ok=True)
        os.makedirs(os.path.join(output_path, "data"), exist_ok=True)
        os.makedirs(os.path.join(output_path, "snapshots"), exist_ok=True)

        # 合并 data 目录
        conflicts = []
        for src_mod in [mod_a_path, mod_b_path]:
            src_data = os.path.join(src_mod, "data")
            if not os.path.exists(src_data):
                continue
            for fname in os.listdir(src_data):
                src_file = os.path.join(src_data, fname)
                dst_file = os.path.join(output_path, "data", fname)
                if os.path.exists(dst_file):
                    conflicts.append(fname)
                    # 重命名冲突文件
                    base, ext = os.path.splitext(fname)
                    conflict_name = f"{base}_from_{os.path.basename(src_mod)}{ext}"
                    shutil.copy2(src_file, os.path.join(output_path, "data", conflict_name))
                else:
                    shutil.copy2(src_file, dst_file)

        # 合并 snapshots
        for src_mod in [mod_a_path, mod_b_path]:
            src_snaps = os.path.join(src_mod, "snapshots")
            if not os.path.exists(src_snaps):
                continue
            for fname in os.listdir(src_snaps):
                src_file = os.path.join(src_snaps, fname)
                dst_file = os.path.join(output_path, "snapshots", fname)
                if not os.path.exists(dst_file):
                    shutil.copy2(src_file, dst_file)

        # 创建 info
        info = {
            "name": output,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "description": f"合并自 {mod_a} + {mod_b}",
            "merged_from": [mod_a, mod_b],
            "conflicts": conflicts,
        }
        with open(os.path.join(output_path, "mod_info.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": f"MOD合并完成: {output}",
            "output": output,
            "conflicts": conflicts,
            "conflictCount": len(conflicts),
        }

    def api_delete_history(self, index: int) -> dict:
        """原子删除历史事件条目"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            r = self.api_load_histories()
            if not r.get("success"):
                return r
            data = r.get("data", [])
            if index < 0 or index >= len(data):
                return {"success": False, "message": f"索引无效: {index}"}
            deleted = data.pop(index)
            self.history_parser = None  # 清除缓存
            save_r = self.api_save_histories(data)
            if save_r.get("success"):
                return {"success": True, "message": f"已删除: {deleted.get('Name', f'事件#{index}')}"}
            return save_r
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_batch_cross_file(self, target_field: str, operation: str, value: str,
                               file_types: List[str] = None, filter_field: str = None,
                               filter_value: str = None, preview: bool = True) -> dict:
        """跨文件批量操作：对多个文件类型的同一字段进行批量修改"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        # 支持的文件类型和字段映射
        file_configs = {
            "General01.ini": {"api": "api_load_generals", "save": "api_save_generals", "fields": ["Str", "Int", "HP", "MP", "Morale", "Loyal", "Race", "Sex", "Life", "IsFamous", "IsResurgable"]},
            "Thing.ini": {"api": "api_load_things", "save": "api_save_things", "fields": ["Str", "Int", "HP", "MP", "Speed", "Loyal", "Rate", "Price", "Level", "IsRare", "Count"]},
            "Soldier.ini": {"api": "api_load_soldiers", "save": "api_save_soldiers", "fields": ["HP", "Speed", "ATK", "DEF", "Life", "Range"]},
            "Title.ini": {"api": "api_load_titles", "save": "api_save_titles", "fields": ["Str", "Int", "HP", "MP", "Level"]},
        }

        targets = file_types or list(file_configs.keys())
        valid_targets = [t for t in targets if t in file_configs]
        if not valid_targets:
            return {"success": False, "message": "没有有效的文件类型"}

        total_affected = 0
        preview_data = []
        all_modified = {}

        for filename in valid_targets:
            config = file_configs[filename]
            if target_field not in config["fields"]:
                continue

            try:
                load_fn = getattr(self, config["api"])
                r = load_fn()
                if not r or not r.get("success"):
                    continue
                entries = r.get("data", [])
                affected = 0
                modified = []

                for entry in entries:
                    # 检查过滤条件
                    if filter_field and filter_value:
                        entry_val = str(entry.get(filter_field, ""))
                        if entry_val != filter_value:
                            continue

                    old_val = entry.get(target_field)
                    try:
                        new_val = self._apply_batch_op(old_val, operation, value)
                        if new_val != old_val:
                            entry[target_field] = new_val
                            affected += 1
                            modified.append({"no": entry.get("No", "?"), "name": entry.get("Name", ""), "old": old_val, "new": new_val})
                    except Exception:
                        continue

                if affected > 0:
                    total_affected += affected
                    preview_data.append({"file": filename, "count": affected, "changes": modified[:10]})
                    all_modified[filename] = entries

                    if not preview:
                        # 执行保存
                        save_fn = getattr(self, config["save"])
                        save_fn(entries)

            except Exception as e:
                logger.warning(f"跨文件批量操作失败 {filename}: {e}")

        if preview:
            return {"success": True, "preview": True, "totalAffected": total_affected, "results": preview_data}

        return {
            "success": True,
            "preview": False,
            "totalAffected": total_affected,
            "results": preview_data,
            "message": f"跨文件批量操作完成，共影响 {total_affected} 条记录",
        }

    def _apply_batch_op(self, old_val, operation: str, value: str):
        """应用批量操作的数值计算"""
        if old_val is None:
            return value
        try:
            old_num = float(old_val) if old_val != "" else 0
        except (ValueError, TypeError):
            return value
        try:
            val_num = float(value)
        except (ValueError, TypeError):
            return value

        if operation == "set":
            result = val_num
        elif operation == "add":
            result = old_num + val_num
        elif operation == "multiply":
            result = old_num * val_num
        elif operation == "min":
            result = min(old_num, val_num)
        elif operation == "max":
            result = max(old_num, val_num)
        else:
            return value

        return int(result) if isinstance(old_val, int) or old_val == "" else result

    def _load_schema(self, schema_name: str) -> dict:
        """内部方法：加载 data/ 目录下的 schema JSON 文件"""
        if not schema_name.endswith(".json"):
            schema_name = schema_name + ".json"
        schema_path = os.path.join(PROJECT_ROOT, "data", schema_name)
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Schema文件不存在: {schema_name}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Schema文件解析失败: {schema_name}: {e}")
            return {}

    def api_get_progress(self) -> dict:
        """获取开发进度"""
        return DEVELOPMENT_PROGRESS

    def api_get_schema(self, schema_type: str) -> dict:
        """获取Schema定义"""
        schema_map = {
            "general": "general_schema.json",
            "soldier": "soldier_schema.json",
            "thing": "thing_schema.json",
            "bfmagic": "bfmagic_schema.json",
            "sfmagic": "sfmagic_schema.json",
            "superatk": "superatk_schema.json",
            "defskill": "defskill_schema.json",
            "genskill": "genskill_schema.json",
            "formation": "formation_schema.json",
            "title": "title_schema.json",
            "nation": "nation_schema.json",
            "city": "city_schema.json",
            "genlv": "genlv_schema.json",
            "history": "history_schema.json",
            "armyskill": "armyskill_schema.json",
            "armygroupskill": "armygroupskill_schema.json",
            "age": "age_schema.json",
            "general02": "general02_schema.json",
            "scenario": "scenario_schema.json",
            "variable": "variable_schema.json",
            "itemenhance": "itemenhance_schema.json",
            "bffront": "bffront_schema.json",
            "dialogue": "dialogue_schema.json",
            "color": "color_schema.json",
            "citypos": "citypos_schema.json",
            "systemtext": "systemtext_schema.json",
            "gossiptext": "gossiptext_schema.json",
            "terrain": "terrain_schema.json",
            "extraterrain": "extraterrain_schema.json",
            "formatoffsetpos": "formatoffsetpos_schema.json",
            "buildingpos": "buildingpos_schema.json",
            "sfbridge": "sfbridge_schema.json",
            "sfroadblock": "sfroadblock_schema.json",
            "sfroadblockpos": "sfroadblockpos_schema.json",
            "var": "var_schema.json",
            "font": "font_schema.json",
            "systemini": "system_ini_schema.json",
            "termtext": "termtext_schema.json",
            "citysellitem": "citysellitem_schema.json",
            "gametext": "gametext_schema.json",
            "sango7": "sango7_schema.json",
            "format": "format_schema.json",
            "chessformat": "chessformat_schema.json",
        }
        filename = schema_map.get(schema_type)
        if not filename:
            return {"success": False, "message": "未知Schema类型"}

        schema_path = os.path.join(PROJECT_ROOT, "data", filename)
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                return {"success": True, "data": json.load(f)}
        except FileNotFoundError:
            return {"success": False, "message": f"Schema文件不存在: {filename}"}
        except json.JSONDecodeError as e:
            return {"success": False, "message": f"Schema文件解析失败: {e}"}

    # ============================================================
    # API: 存档编辑器（旧版 saveEditor 专用方法）
    # 注意: saveList/saveBackup/saveHexView 已由下方 saveMgr 统一提供
    # ============================================================

    def api_save_load(self, save_name: str) -> dict:
        """加载存档"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.load_save(save_name)

    def api_save_get_info(self) -> dict:
        """获取存档系统信息"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.get_save_info()

    def api_save_edit_customgen(self, save_name: str, generals: list) -> dict:
        """编辑CustomGen.sav中的自定义武将"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.edit_customgen(save_name, generals)

    def api_save_hex_search(self, save_name: str, pattern_hex: str, start_offset: int = 0) -> dict:
        """在存档中搜索十六进制模式"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.hex_search(save_name, pattern_hex, start_offset)

    def api_save_clone_general(self, save_name: str, source_index: int, clone_count: int = 1) -> dict:
        """克隆自定义武将"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.clone_custom_general(save_name, source_index, clone_count)

    # ============================================================
    # API: CustomLeaders.bytes 自建武将
    # ============================================================

    # reserved: 预留给未来功能，暂无前端调用
    def api_custom_leader_load(self) -> dict:
        """加载自建武将列表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.custom_leader.set_game_path(self.game_path)
        return self.custom_leader.load()

    def api_custom_leader_save(self, leaders: list) -> dict:
        """保存自建武将列表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.custom_leader.set_game_path(self.game_path)
        return self.custom_leader.save(leaders)

    # ============================================================
    # API: 存档管理
    # ============================================================

    def api_save_list(self) -> dict:
        """列出存档文件"""
        return self.save_manager.list_saves()

    def api_save_backup(self, save_name: str) -> dict:
        """备份存档"""
        return self.save_manager.backup_save(save_name)

    def api_save_restore(self, backup_path: str, save_name: str) -> dict:
        """还原存档"""
        return self.save_manager.restore_save(backup_path, save_name)

    def api_save_list_backups(self) -> dict:
        """列出备份"""
        return self.save_manager.list_backups()

    def api_save_delete_backup(self, backup_path: str) -> dict:
        """删除备份"""
        return self.save_manager.delete_backup(backup_path)

    def api_save_hex_view(self, save_name: str, offset: int = 0, length: int = 1024) -> dict:
        """十六进制查看"""
        return self.save_manager.hex_view(save_name, offset, length)

    def api_save_analyze(self, save_name: str) -> dict:
        """分析存档文件头"""
        return self.save_manager.analyze_save_header(save_name)

    # ============================================================
    # API: 存档解析器 (SaveParser) — 结构化编辑
    # ============================================================

    def api_save_parse_generals(self, save_name: str) -> dict:
        """解析存档中的武将数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        load_result = self.save_parser.load(save_path)
        if not load_result["success"]:
            return load_result
        generals = self.save_parser.find_generals()
        return {"success": True, "save_name": save_name, "generals": generals, "count": len(generals)}

    def api_save_edit_stat(self, save_name: str, offset: int, field: str, value: int) -> dict:
        """修改武将属性"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_general_stats(offset, field, value)
        if result["success"]:
            # 自动备份
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_edit_merit(self, save_name: str, offset: int, value: int) -> dict:
        """修改功勋值"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_merit(offset, value)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_edit_exp(self, save_name: str, offset: int, value: int) -> dict:
        """修改经验值"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_experience(offset, value)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_edit_soldier(self, save_name: str, offset: int, soldier_type: int, soldier_count: int) -> dict:
        """修改兵种和带兵数"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_soldier(offset, soldier_type, soldier_count)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_edit_weapon_exp(self, save_name: str, offset: int, weapon: str, value: int) -> dict:
        """修改武器熟练度"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_weapon_exp(offset, weapon, value)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_get_soldier_types(self) -> dict:
        """获取兵种代码表"""
        return {"success": True, "soldiers": [{"id": k, "name": v} for k, v in SaveParser.SOLDIER_TYPES.items()]}

    def api_save_get_structured_general(self, save_name: str, general_index: int) -> dict:
        """获取武将结构化数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        return self.save_parser.get_structured_general(general_index)

    def api_save_write_equipment(self, save_name: str, general_index: int, slot: str, item_id: int) -> dict:
        """修改武将装备"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_equipment(general_index, slot, item_id)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_write_skills(self, save_name: str, general_index: int, skill_type: str, slot: int, skill_id: int) -> dict:
        """修改武将技能"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_skills(general_index, skill_type, slot, skill_id)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    # reserved: 预留给未来功能，暂无前端调用
    def api_save_write_soldier_count(self, save_name: str, general_index: int, count: int) -> dict:
        """修改武将带兵数"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_soldier_count(general_index, count)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_write_formation(self, save_name: str, general_index: int, formation_id: int) -> dict:
        """修改武将阵型"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        save_path = os.path.join(self.game_path, "Save", save_name)
        if not os.path.exists(save_path):
            return {"success": False, "message": f"存档不存在: {save_name}"}
        self.save_parser.load(save_path)
        result = self.save_parser.write_formation(general_index, formation_id)
        if result["success"]:
            self.save_editor._make_backup(save_path)
            with open(save_path, "wb") as f:
                f.write(self.save_parser.get_raw_data())
        return result

    def api_save_get_weapon_names(self) -> dict:
        """获取武器名称字典"""
        return {"success": True, "weapons": [{"id": k, "name": v} for k, v in SaveParser.WEAPON_TYPES.items()]}

    def api_save_get_horse_names(self) -> dict:
        """获取坐骑名称字典"""
        return {"success": True, "horses": [{"id": k, "name": v} for k, v in SaveParser.HORSE_TYPES.items()]}

    def api_save_get_item_names(self) -> dict:
        """获取道具名称字典"""
        return {"success": True, "items": [{"id": k, "name": v} for k, v in SaveParser.ITEM_TYPES.items()]}

    def api_save_get_formation_names(self) -> dict:
        """获取阵型名称字典"""
        return {"success": True, "formations": [{"id": k, "name": v} for k, v in SaveParser.FORMATION_TYPES.items()]}

    # ============================================================
    # API: Script.so 分析器
    # ============================================================

    def api_scriptso_info(self) -> dict:
        """获取 Script.so 基本信息"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.get_script_so_info()

    def api_scriptso_strings(self) -> dict:
        """分析 Script.so 字符串"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.analyze_strings()

    def api_scriptso_hex_view(self, offset: int = 0, length: int = 512) -> dict:
        """十六进制查看 Script.so"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.hex_view(offset, length)

    def api_scriptso_hex_search(self, pattern_hex: str) -> dict:
        """在 Script.so 中搜索十六进制模式"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.hex_search(pattern_hex)

    def api_scriptso_list_files(self) -> dict:
        """列出 Script/ 目录文件"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        files = self.scriptso_analyzer.list_script_files()
        return {"success": True, "files": files, "count": len(files)}

    def api_scriptso_backup(self) -> dict:
        """备份 Script.so"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.backup_script_so()

    def api_scriptso_hex_write(self, offset: int, data_hex: str) -> dict:
        """十六进制写入 Script.so"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.hex_write(offset, data_hex)

    def api_scriptso_hex_patch(self, patches: list) -> dict:
        """批量十六进制补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.hex_patch(patches)

    def api_scriptso_sections(self) -> dict:
        """解析 Script.so ELF 段表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.parse_sections()

    def api_scriptso_symbols(self) -> dict:
        """解析 Script.so 符号表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.parse_symbols()

    def api_scriptso_string_replace(self, old_text: str, new_text: str) -> dict:
        """替换 Script.so 中的字符串"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.string_replace(old_text, new_text)

    def api_scriptso_get_patches(self) -> dict:
        """获取已知 Script.so 补丁列表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.get_known_patches()

    def api_scriptso_search_patch(self, patch_id: str) -> dict:
        """搜索已知补丁偏移"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.search_patch_offset(patch_id)

    def api_scriptso_apply_patch(self, patch_id: str, offset: int, new_value, value_type: str = None) -> dict:
        """应用已知补丁到指定偏移"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.apply_known_patch(patch_id, offset, new_value, value_type)

    def api_scriptso_community_patches(self) -> dict:
        """获取社区教程补丁列表"""
        return self.scriptso_analyzer.get_community_patches()

    def api_scriptso_apply_community_patch(self, patch_id: str) -> dict:
        """应用社区教程补丁（字符串替换）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.apply_community_patch(patch_id)

    def api_scriptso_disassemble(self, offset: int = None, length: int = 512) -> dict:
        """反汇编 Script.so"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.disassemble(offset, length)

    def api_scriptso_find_functions(self) -> dict:
        """检测 Script.so 函数边界"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.find_functions()

    def api_scriptso_disasm_func(self, address: int) -> dict:
        """反汇编单个函数"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.disassemble_function(address)

    def api_scriptso_find_xrefs(self, address: int) -> dict:
        """查找交叉引用"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.find_xrefs_to(address)

    def api_scriptso_instruction_patch(self, address: int, mnemonic: str, operands: str = "") -> dict:
        """指令级补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_analyzer.set_game_path(self.game_path)
        return self.scriptso_analyzer.instruction_patch(address, mnemonic, operands)

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
            return {"success": False, "message": "请先设置游戏目录"}

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
        一键创建兵种：自动联动 Soldier.ini + TermText.ini
        """
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}

        if no <= 0:
            return {"success": False, "message": "兵种编号必须大于0"}

        results = {}
        no_str = str(no)

        # 1. Soldier.ini
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
            section.set("Level", str(level))
            section.set("Upgrade", str(upgrade))
            section.set("HP", str(hp))
            section.set("Atk", str(atk))
            section.set("Def", str(def_val))
            section.set("Speed", str(speed))
            section.set("Range", str(range_val))
            section.set("Cost", str(cost))
            section.set("TroopCount", str(troop_count))
            if hit_sol1: section.set("HitSol1", str(hit_sol1))
            if hit_sol2: section.set("HitSol2", str(hit_sol2))
            if obj_id: section.set("ObjID", str(obj_id))
            section.set("IsUsed", str(is_used))
            parser.save(path)
            results["soldier"] = "OK"
        except Exception as e:
            results["soldier_error"] = str(e)

        # 2. TermText.ini (士兵名=13000+No, 说明=13500+No)
        try:
            if self.term_text.is_loaded():
                self.term_text.allocate_new_id(name)
                results["termtext"] = f"String={13000 + no}"
            else:
                results["termtext_skip"] = "TermText未加载"
        except Exception as e:
            results["termtext_error"] = str(e)

        results["success"] = results.get("soldier") == "OK"
        results["message"] = f"已为兵种 {name} (No.{no}) 创建 Soldier + TermText"
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
            return {"success": False, "message": "请先设置游戏目录"}
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
            except Exception:
                pass
        results["city_periods"] = "OK"

        # 5. TermText
        try:
            if self.term_text.is_loaded():
                self.term_text.allocate_new_id(name)
                results["termtext"] = "OK"
        except Exception:
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
            return {"success": False, "message": "请先设置游戏目录"}
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
        except Exception:
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
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            objects = self.obd_parser.load(obd_type)
            return {
                "success": True,
                "data": self.obd_parser.to_dict_list(),
                "count": len(objects),
                "sprite_types": self.obd_parser.get_sprite_types(),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_obd_save(self, obd_type: str, data: list) -> dict:
        """保存OBD模型数据"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            objects = [OBDObject.from_dict(d) for d in data]
            path = self.obd_parser.save(obd_type, objects)
            return {"success": True, "message": f"保存成功，共{len(objects)}个模型", "path": path}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_obd_new_object(self, obd_type: str = "bfsoldier") -> dict:
        """创建新OBD对象"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            self.obd_parser.load(obd_type)
            seq = self.obd_parser.find_free_sequence()
            obj = OBDObject()
            obj.sequence = seq
            obj.name = f"新模型_{seq}"
            return {"success": True, "data": obj.to_dict(), "sequence": seq}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_obd_delete(self, obd_type: str, sequence: int) -> dict:
        """删除指定OBD模型对象"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": str(e)}

    def api_obd_get_info(self) -> dict:
        """获取OBD格式信息"""
        return OBDParser.get_info()

    def api_obd_get_sprites(self, obd_type: str, sequence: int) -> dict:
        """获取指定OBD对象的Sprite帧列表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": str(e)}

    # reserved: 预留给未来功能，暂无前端调用
    def api_obd_update_sprites(self, obd_type: str, sequence: int, sprites: dict) -> dict:
        """更新OBD对象的Sprite帧"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            self.obd_parser.load(obd_type)
            obj = self.obd_parser.find_by_sequence(sequence)
            if not obj:
                return {"success": False, "message": f"未找到Sequence={sequence}的对象"}
            obj.sprites = OrderedDict(sprites)
            self.obd_parser.save(obd_type, self.obd_parser.objects)
            return {"success": True, "message": f"已更新 {len(sprites)} 个Sprite帧"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def api_obd_copy_to(self, source_type: str, target_type: str, sequence: int) -> dict:
        """跨文件复制OBD模型（如 NPC→武将）"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": str(e)}

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
            return {"success": False, "message": str(e)}

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
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": "请先设置游戏目录"}
        return self.pck_mgr.extract_shape_pck(pck_name)

    def api_shape_pck_extract_all(self) -> dict:
        """批量提取所有 Shape*.pck"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.pck_mgr.extract_all_shape_pcks()

    def api_shape_pck_repack(self, pck_name: str = "Shape00.pck") -> dict:
        """将 Shape/ 目录重新打包为 Shape*.pck"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
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
            return {"success": False, "message": str(e)}

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
            return {"success": False, "message": str(e)}

    def api_csv_confirm_import(self, data_type: str, file_path: str) -> dict:
        """确认导入 CSV 数据"""
        try:
            return self.csv_manager.import_csv(data_type, file_path)
        except Exception as e:
            return {"success": False, "message": str(e)}

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
        full_path = os.path.join(self.game_path, "Setting", file_path) if self.game_path else file_path
        return self.encoding_converter.preview_conversion(full_path, target_encoding)

    def api_encoding_convert_file(self, file_path: str, target_encoding: str = "gbk") -> dict:
        """转换单个文件编码"""
        full_path = os.path.join(self.game_path, "Setting", file_path) if self.game_path else file_path
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

        window = webview.create_window(
            title="San7ModMaker - 三国群英传7 MOD制作器 V2.1",
            url=html_path,
            js_api=api,
            width=1280,
            height=860,
            min_size=(1024, 700),
            resizable=True,
        )

        webview.start(debug=False)


class _JsApi:
    """JS API桥接类，暴露给前端调用的方法"""

    _API_MAP = {
        'applyExePatch': 'api_apply_exe_patch',
        'applyExePatchAuto': 'api_apply_exe_patch_auto',
        'applyJmpPatch': 'api_apply_jmp_patch',
        'applyNopPatch': 'api_apply_nop_patch',
        'applyResolutionPreset': 'api_apply_resolution_preset',
        'applyTemplatePatch': 'api_apply_template_patch',
        'backupAll': 'api_backup_all',
        'batchCloneExecute': 'api_batch_clone_execute',
        'batchClonePreview': 'api_batch_clone_preview',
        'batchExecute': 'api_batch_execute',
        'batchPreview': 'api_batch_preview',
        'batchSearch': 'api_batch_search',
        'batchSearchReplace': 'api_batch_search_replace',
        'blockCalc': 'api_block_calc',
        'blockInverse': 'api_block_inverse',
        'bmp2raw': 'api_bmp2raw',
        'browseShapeResources': 'api_browse_shape_resources',
        'checkReferences': 'api_check_references',
        'cityConnections': 'api_city_connections',
        'loadCityConnect': 'api_load_city_connect',
        'saveCityConnect': 'api_save_city_connect',
        'cloneGeneral': 'api_clone_general',
        'convertImageToBfobjShp': 'api_convert_image_to_bfobj_shp',
        'convertImageToShp': 'api_convert_image_to_shp',
        'convertImageToThingIcon': 'api_convert_image_to_thing_icon',
        'exportThingIconToPng': 'api_export_thing_icon_to_png',
        'thingIconBatchImport': 'api_thing_icon_batch_import',
        'thingIconBatchExport': 'api_thing_icon_batch_export',
        'createMod': 'api_create_mod',
        'createSHDir': 'api_create_sh_dir',
        'importSpriteFrame': 'api_import_sprite_frame',
        'csvConfirmImport': 'api_csv_confirm_import',
        'csvExport': 'api_csv_export',
        'csvGetFields': 'api_csv_get_fields',
        'csvImport': 'api_csv_import',
        'customLeaderLoad': 'api_custom_leader_load',
        'customLeaderSave': 'api_custom_leader_save',
        'customgenEdit': 'api_customgen_edit',
        'customgenGet': 'api_customgen_get',
        'customgenList': 'api_customgen_list',
        'deleteDefSkillEntry': 'api_delete_defskill_entry',
        'deleteGeneral': 'api_delete_general',
        'deleteIniItem': 'api_delete_ini_item',
        'deleteMod': 'api_delete_mod',
        'detectGameVersion': 'api_detect_game_version',
        'diffCompare': 'api_diff_compare',
        'diffExport': 'api_diff_export',
        'diffLanguageTexts': 'api_diff_language_texts',
        'disassembleExe': 'api_disassemble_exe',
        'disassembleScan': 'api_disassemble_scan',
        'effectAtkTypes': 'api_effect_atk_types',
        'effectBallTypes': 'api_effect_ball_types',
        'effectDamageTypes': 'api_effect_damage_types',
        'effectElementTypes': 'api_effect_element_types',
        'effectGetAll': 'api_effect_get_all',
        'effectItemScripts': 'api_effect_item_scripts',
        'effectWeaponGlow': 'api_effect_weapon_glow',
        'encodingBatchConvert': 'api_encoding_batch_convert',
        'encodingConvertFile': 'api_encoding_convert_file',
        'encodingPreview': 'api_encoding_preview',
        'encodingScan': 'api_encoding_scan',
        'eventGenerate': 'api_event_generate',
        'eventTemplates': 'api_event_templates',
        'exeApplyCommunityPatch': 'api_exe_apply_community_patch',
        'exeCommunityPatches': 'api_exe_community_patches',
        'exportLanguagePack': 'api_export_language_pack',
        'exportShpToPng': 'api_export_shp_to_png',
        'faceBatchExport': 'api_face_batch_export',
        'faceDelete': 'api_face_batch_delete',
        'facePreview': 'api_face_batch_preview',
        'faceStats': 'api_face_stats',
        'getActiveMod': 'api_get_active_mod',
        'getAllTermtext': 'api_get_all_termtext',
        'getBackupHistory': 'api_get_backup_history',
        'getBatchFiles': 'api_get_batch_files',
        'getDiffBackups': 'api_get_diff_backups',
        'getExeInfo': 'api_get_exe_info',
        'getFacePreview': 'api_get_face_preview',
        'getGameInfo': 'api_get_game_info',
        'getJmpTemplates': 'api_get_jmp_templates',
        'getModList': 'api_get_mod_list',
        'getProgress': 'api_get_progress',
        'getSango7Config': 'api_get_sango7_config',
        'getSchema': 'api_get_schema',
        'getThingTermText': 'api_get_thing_termtext',
        'importImageToGenhalf': 'api_import_image_to_genhalf',
        'importLanguagePack': 'api_import_language_pack',
        'importMod': 'api_import_mod',
        'installMod': 'api_install_mod',
        'languageStatus': 'api_language_status',
        'launchGame': 'api_launch_game',
        'listBfobjShps': 'api_list_bfobj_shps',
        'listGenhalfShps': 'api_list_genhalf_shps',
        'listInstalledMods': 'api_list_installed_mods',
        'listScripts': 'api_list_scripts',
        'newScript': 'api_new_script',
        'deleteScript': 'api_delete_script',
        'renameScript': 'api_rename_script',
        'globalSearch': 'api_global_search',
        'balanceAnalysis': 'api_balance_analysis',
        'modMerge': 'api_mod_merge',
        'deleteHistory': 'api_delete_history',
        'batchCrossFile': 'api_batch_cross_file',
        'loadAge': 'api_load_age',
        'loadBFFront': 'api_load_bffront',
        'loadBuildingPos': 'api_load_buildingpos',
        'loadButtonStyle': 'api_load_buttonstyle',
        'loadCDTable': 'api_load_cdtable',
        'loadChessFormat': 'api_load_chessformat',
        'loadCities': 'api_load_cities',
        'loadCityPeriod': 'api_load_city_period',
        'loadCityPos': 'api_load_citypos',
        'loadCitySellItems': 'api_load_city_sell_items',
        'loadCityText': 'api_load_citytext',
        'loadColor': 'api_load_color',
        'loadDefSkill': 'api_load_defskill',
        'loadDialogue': 'api_load_dialogue',
        'loadExtraTerrain': 'api_load_extraterrain',
        'loadFont': 'api_load_font',
        'loadFontMultiLang': 'api_load_fontmultilang',
        'loadFontSize': 'api_load_fontsize',
        'loadFormat': 'api_load_format',
        'loadFormatOffsetPos': 'api_load_formatoffsetpos',
        'loadFormations': 'api_load_formations',
        'loadFrameStyle': 'api_load_framestyle',
        'loadGameText': 'api_load_game_text',
        'loadGenLV': 'api_load_gen_lv',
        'loadGenSkills': 'api_load_gen_skills',
        'loadGeneral02': 'api_load_general02',
        'loadGenerals': 'api_load_generals',
        'loadGlobalParams': 'api_load_global_params',
        'loadGossipText': 'api_load_gossiptext',
        'loadHistories': 'api_load_histories',
        'loadIdini': 'api_load_idini',
        'loadItemEnhance': 'api_load_item_enhance',
        'loadListStyle': 'api_load_liststyle',
        'loadMapSummary': 'api_load_map_summary',
        'saveMapPositions': 'api_save_map_positions',
        'loadNations': 'api_load_nations',
        'loadPostPatch': 'api_load_postpatch',
        'loadSFBridge': 'api_load_sfbridge',
        'loadSFRoadBlock': 'api_load_sfroadblock',
        'loadSFRoadBlockPos': 'api_load_sfroadblockpos',
        'loadScenarios': 'api_load_scenarios',
        'loadShapeUI': 'api_load_shapeui',
        'loadSkills': 'api_load_skills',
        'loadSoldiers': 'api_load_soldiers',
        'loadStoreConfig': 'api_load_store_config',
        'loadSuperAtk': 'api_load_super_atk',
        'loadSystemIni': 'api_load_systemini',
        'loadSystemText': 'api_load_systemtext',
        'loadTermTextFull': 'api_load_term_text_full',
        'loadTerrain': 'api_load_terrain',
        'loadTextStyle': 'api_load_textstyle',
        'loadThingScriptNo': 'api_load_thingscriptno',
        'loadThings': 'api_load_things',
        'loadTitles': 'api_load_titles',
        'loadVar': 'api_load_var',
        'loadWinColor': 'api_load_wincolor',
        'loadWinMainMenu': 'api_load_winmainmenu',
        'matrixGet': 'api_matrix_get',
        'matrixGetSoldiers': 'api_matrix_get_soldiers',
        'matrixLoad': 'api_matrix_load',
        'matrixUpdate': 'api_matrix_update',
        'memoryAttach': 'api_memory_attach',
        'memoryPresets': 'api_memory_presets',
        'memoryRead': 'api_memory_read',
        'memoryReadPreset': 'api_memory_read_preset',
        'memorySearch': 'api_memory_search',
        'memoryWrite': 'api_memory_write',
        'modSnapshot': 'api_mod_snapshot',
        'mpcBatchWrite': 'api_mpc_batch_write',
        'mpcRead': 'api_mpc_read',
        'mpcWrite': 'api_mpc_write',
        'nationLinkageCheck': 'api_nation_linkage_check',
        'nationLinkageCreate': 'api_nation_linkage_create',
        'newBFFront': 'api_new_bffront',
        'newBuildingPos': 'api_new_buildingpos',
        'newButtonStyle': 'api_new_buttonstyle',
        'newCDTable': 'api_new_cdtable',
        'newChessFormat': 'api_new_chessformat',
        'newCity': 'api_new_city',
        'newCityPos': 'api_new_citypos',
        'newCityText': 'api_new_citytext',
        'newColor': 'api_new_color',
        'newDefSkillEntry': 'api_new_defskill_entry',
        'newDialogue': 'api_new_dialogue',
        'newExtraTerrain': 'api_new_extraterrain',
        'newFont': 'api_new_font',
        'newFontSize': 'api_new_fontsize',
        'newFormat': 'api_new_format',
        'newFormatOffsetPos': 'api_new_formatoffsetpos',
        'newFormation': 'api_new_formation',
        'newFrameStyle': 'api_new_framestyle',
        'newGeneral': 'api_new_general',
        'newGlobalParams': 'api_new_global_params',
        'newGossipText': 'api_new_gossiptext',
        'newHistory': 'api_new_history',
        'newListStyle': 'api_new_liststyle',
        'newNation': 'api_new_nation',
        'newPostPatch': 'api_new_postpatch',
        'newSFBridge': 'api_new_sfbridge',
        'newSFRoadBlock': 'api_new_sfroadblock',
        'newSFRoadBlockPos': 'api_new_sfroadblockpos',
        'newShapeUI': 'api_new_shapeui',
        'newSkill': 'api_new_skill',
        'newSoldier': 'api_new_soldier',
        'newSuperAtk': 'api_new_super_atk',
        'newSystemIni': 'api_new_systemini',
        'newSystemText': 'api_new_systemtext',
        'newTerrain': 'api_new_terrain',
        'newTextStyle': 'api_new_textstyle',
        'newThing': 'api_new_thing',
        'newThingScriptNo': 'api_new_thingscriptno',
        'newTitle': 'api_new_title',
        'newVar': 'api_new_var',
        'newWinColor': 'api_new_wincolor',
        'newWinMainMenu': 'api_new_winmainmenu',
        'obdCopyTo': 'api_obd_copy_to',
        'obdGetInfo': 'api_obd_get_info',
        'obdGetSprites': 'api_obd_get_sprites',
        'obdDelete': 'api_obd_delete',
        'obdListSpriteFrames': 'api_obd_list_sprite_frames',
        'obdLoad': 'api_obd_load',
        'obdNewObject': 'api_obd_new_object',
        'obdPreviewSpriteFrame': 'api_obd_preview_sprite_frame',
        'obdSave': 'api_obd_save',
        'obdUpdateSprites': 'api_obd_update_sprites',
        'packModIncremental': 'api_pack_mod_incremental',
        'packModOneClick': 'api_pack_mod_one_click',
        'pckDetect': 'api_pck_detect',
        'pckExtractAll': 'api_pck_extract_all',
        'pckExtractFile': 'api_pck_extract_file',
        'pckGetInfo': 'api_pck_get_info',
        'pckGetSettingStatus': 'api_pck_get_setting_status',
        'pckListFiles': 'api_pck_list_files',
        'pckPrepareSetting': 'api_pck_prepare_setting',
        'pckPreviewShp': 'api_pck_preview_shp',
        'pckRepack': 'api_pck_repack',
        'previewBfobjShp': 'api_preview_bfobj_shp',
        'previewGenhalfShp': 'api_preview_genhalf_shp',
        'readLanguageDat': 'api_read_language_dat',
        'readScript': 'api_read_script',
        'reloadTermtext': 'api_reload_termtext',
        'remapConflicts': 'api_remap_conflicts',
        'restoreAll': 'api_restore_all',
        'revertExePatches': 'api_revert_exe_patches',
        'saveAge': 'api_save_age',
        'saveAnalyze': 'api_save_analyze',
        'saveBFFront': 'api_save_bffront',
        'saveBackup': 'api_save_backup',
        'saveBuildingPos': 'api_save_buildingpos',
        'saveButtonStyle': 'api_save_buttonstyle',
        'saveCDTable': 'api_save_cdtable',
        'saveChessFormat': 'api_save_chessformat',
        'saveCities': 'api_save_cities',
        'saveCityPeriod': 'api_save_city_period',
        'saveCityPos': 'api_save_citypos',
        'saveCitySellItems': 'api_save_city_sell_items',
        'saveCityText': 'api_save_citytext',
        'saveCloneGeneral': 'api_save_clone_general',
        'saveColor': 'api_save_color',
        'saveDefSkill': 'api_save_defskill',
        'saveDeleteBackup': 'api_save_delete_backup',
        'saveDialogue': 'api_save_dialogue',
        'saveEditCustomGen': 'api_save_edit_customgen',
        'saveEditExp': 'api_save_edit_exp',
        'saveEditMerit': 'api_save_edit_merit',
        'saveEditSoldier': 'api_save_edit_soldier',
        'saveEditStat': 'api_save_edit_stat',
        'saveEditWeaponExp': 'api_save_edit_weapon_exp',
        'saveExtraTerrain': 'api_save_extraterrain',
        'saveFont': 'api_save_font',
        'saveFontMultiLang': 'api_save_fontmultilang',
        'saveFontSize': 'api_save_fontsize',
        'saveFormat': 'api_save_format',
        'saveFormatOffsetPos': 'api_save_formatoffsetpos',
        'saveFormations': 'api_save_formations',
        'saveFrameStyle': 'api_save_framestyle',
        'saveGameText': 'api_save_game_text',
        'saveGenLV': 'api_save_gen_lv',
        'saveGenSkills': 'api_save_gen_skills',
        'saveGeneral02': 'api_save_general02',
        'saveGenerals': 'api_save_generals',
        'saveGetFormationNames': 'api_save_get_formation_names',
        'saveGetHorseNames': 'api_save_get_horse_names',
        'saveGetInfo': 'api_save_get_info',
        'saveGetItemNames': 'api_save_get_item_names',
        'saveGetSoldierTypes': 'api_save_get_soldier_types',
        'saveGetStructuredGeneral': 'api_save_get_structured_general',
        'saveGetWeaponNames': 'api_save_get_weapon_names',
        'saveGlobalParams': 'api_save_global_params',
        'saveGossipText': 'api_save_gossiptext',
        'saveHexSearch': 'api_save_hex_search',
        'saveHexView': 'api_save_hex_view',
        'saveHistories': 'api_save_histories',
        'saveIdini': 'api_save_idini',
        'saveItemEnhance': 'api_save_item_enhance',
        'saveList': 'api_save_list',
        'saveListBackups': 'api_save_list_backups',
        'saveListStyle': 'api_save_liststyle',
        'saveLoad': 'api_save_load',
        'saveNations': 'api_save_nations',
        'saveParseGenerals': 'api_save_parse_generals',
        'savePngDialog': 'api_select_save_path',
        'savePostPatch': 'api_save_postpatch',
        'saveRestore': 'api_save_restore',
        'saveSFBridge': 'api_save_sfbridge',
        'saveSFRoadBlock': 'api_save_sfroadblock',
        'saveSFRoadBlockPos': 'api_save_sfroadblockpos',
        'saveScenarios': 'api_save_scenarios',
        'saveScript': 'api_save_script',
        'saveShapeUI': 'api_save_shapeui',
        'saveSkills': 'api_save_skills',
        'saveSoldiers': 'api_save_soldiers',
        'saveStoreConfig': 'api_save_store_config',
        'saveSuperAtk': 'api_save_super_atk',
        'saveSystemIni': 'api_save_systemini',
        'saveSystemText': 'api_save_systemtext',
        'saveTermText': 'api_save_term_text',
        'saveTerrain': 'api_save_terrain',
        'saveTextStyle': 'api_save_textstyle',
        'saveThingScriptNo': 'api_save_thingscriptno',
        'saveThings': 'api_save_things',
        'saveTitles': 'api_save_titles',
        'saveVar': 'api_save_var',
        'saveWinColor': 'api_save_wincolor',
        'saveWinMainMenu': 'api_save_winmainmenu',
        'saveWriteEquipment': 'api_save_write_equipment',
        'saveWriteFormation': 'api_save_write_formation',
        'saveWriteSkills': 'api_save_write_skills',
        'saveWriteSoldierCount': 'api_save_write_soldier_count',
        'scanExeSignatures': 'api_scan_exe_signatures',
        'scanExeValue': 'api_scan_exe_value',
        'scriptsoApplyCommunityPatch': 'api_scriptso_apply_community_patch',
        'scriptsoApplyPatch': 'api_scriptso_apply_patch',
        'scriptsoBackup': 'api_scriptso_backup',
        'scriptsoCommunityPatches': 'api_scriptso_community_patches',
        'scriptsoDisasmFunc': 'api_scriptso_disasm_func',
        'scriptsoDisassemble': 'api_scriptso_disassemble',
        'scriptsoFindFunctions': 'api_scriptso_find_functions',
        'scriptsoFindXrefs': 'api_scriptso_find_xrefs',
        'scriptsoGetPatches': 'api_scriptso_get_patches',
        'scriptsoHexPatch': 'api_scriptso_hex_patch',
        'scriptsoHexSearch': 'api_scriptso_hex_search',
        'scriptsoHexView': 'api_scriptso_hex_view',
        'scriptsoHexWrite': 'api_scriptso_hex_write',
        'scriptsoInfo': 'api_scriptso_info',
        'scriptsoInstructionPatch': 'api_scriptso_instruction_patch',
        'scriptsoListFiles': 'api_scriptso_list_files',
        'scriptsoSearchPatch': 'api_scriptso_search_patch',
        'scriptsoSections': 'api_scriptso_sections',
        'scriptsoStringReplace': 'api_scriptso_string_replace',
        'scriptsoStrings': 'api_scriptso_strings',
        'scriptsoSymbols': 'api_scriptso_symbols',
        'searchGlobalParams': 'api_search_global_params',
        'searchTermtext': 'api_search_termtext',
        'selectCsvFile': 'api_select_csv_file',
        'selectImageFile': 'api_select_image_file',
        'setActiveMod': 'api_set_active_mod',
        'setGamePath': 'api_set_game_path',
        'setSango7Config': 'api_set_sango7_config',
        'setThingTermText': 'api_set_thing_termtext',
        'shapeBatchDelete': 'api_shape_batch_delete',
        'shapeBatchExport': 'api_shape_batch_export',
        'shapeInfoList': 'api_shape_info_list',
        'shapeInfoSave': 'api_shape_info_save',
        'shapePckExtract': 'api_shape_pck_extract',
        'shapePckExtractAll': 'api_shape_pck_extract_all',
        'shapePckRepack': 'api_shape_pck_repack',
        'shapeResourceStats': 'api_shape_resource_stats',
        'shapeThumbnails': 'api_shape_thumbnails',
        'shpBatchRename': 'api_shp_batch_rename',
        'shpSelectDir': 'api_shp_select_dir',
        'switchLanguagePreset': 'api_switch_language_preset',
        'uninstallMod': 'api_uninstall_mod',
        'validateAll': 'api_validate_all',
        'wizardCreateGeneral': 'api_wizard_create_general',
        'wizardCreateSoldier': 'api_wizard_create_soldier',
        'wizardCreateNation': 'api_wizard_create_nation',
        'wizardCreateItem': 'api_wizard_create_item',
        'wizardDependencies': 'api_wizard_dependencies',
        'wizardGetSample': 'api_wizard_get_sample',
        'wizardProgress': 'api_wizard_progress',
        'wizardStart': 'api_wizard_start',
        'wizardStep': 'api_wizard_step',
        'wizardTemplates': 'api_wizard_templates',
        'writeLanguageDat': 'api_write_language_dat',
    }

    def __init__(self, app: "San7ModMaker"):
        self._app = app

    def _call(self, method_name: str, *args, **kwargs) -> dict:
        """通用调用包装"""
        try:
            func = getattr(self._app, method_name)
            return func(*args, **kwargs)
        except Exception as e:
            return {"success": False, "message": str(e)}

    def __getattr__(self, name: str):
        """动态转发：camelCase方法名 → api_snake_case"""
        if name in self._API_MAP:
            api_name = self._API_MAP[name]
            def wrapper(*args, **kwargs):
                return self._call(api_name, *args, **kwargs)
            return wrapper
        raise AttributeError(f"'_JsApi' object has no attribute '{name}'")

    def __dir__(self):
        """暴露所有可用方法给 pywebview 发现"""
        return list(self._API_MAP.keys()) + ['_call']

    def batchCloneExecute(self, params: dict):
        """params: {source, from, to, type}"""
        return self._call("api_batch_clone_execute",
            params.get("source", 0), params.get("from", 0),
            params.get("to", 0), params.get("type", ""))


    def batchClonePreview(self, params: dict):
        """params: {source, from, to, type}"""
        return self._call("api_batch_clone_preview",
            params.get("source", 0), params.get("from", 0),
            params.get("to", 0), params.get("type", ""))


    def batchExecute(self, params: dict):
        """params: {file, field, op, value, filterField, filterValue}"""
        return self._call("api_batch_execute",
            params.get("file", ""), params.get("field", ""),
            params.get("op", ""), params.get("value", 0),
            params.get("filterField", ""), params.get("filterValue", ""))


    def batchPreview(self, params: dict):
        """params: {file, field, op, value, filterField, filterValue}"""
        return self._call("api_batch_preview",
            params.get("file", ""), params.get("field", ""),
            params.get("op", ""), params.get("value", 0),
            params.get("filterField", ""), params.get("filterValue", ""))


    def batchSearch(self, params: dict):
        """params: {find, replace, isRegex, caseSensitive, scope}"""
        return self._call("api_batch_search",
            params.get("find", ""), params.get("replace", ""),
            params.get("isRegex", False), params.get("caseSensitive", False),
            params.get("scope", []))


    def batchSearchReplace(self, params: dict):
        """params: {find, replace, isRegex, caseSensitive, scope}"""
        return self._call("api_batch_search_replace",
            params.get("find", ""), params.get("replace", ""),
            params.get("isRegex", False), params.get("caseSensitive", False),
            params.get("scope", []))

    # 差异对比

    def nationLinkageCreate(self, nation_no: str, nation_name: str = "",
                            color_r: int = 255, color_g: int = 0, color_b: int = 0,
                            city_name: str = "", lord: int = 0):
        return self._call("api_nation_linkage_create", nation_no, nation_name,
                          color_r, color_g, color_b, city_name, lord)

    # 城池


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    app = San7ModMaker()
    app.run()