import os, json, re, time, logging
from io import BytesIO
from typing import Any, Dict, List, Optional

logger = logging.getLogger('San7ModMaker')

from core.config import USER_DATA_DIR, WRITE_ROOT, PROJECT_ROOT, HAS_TK

from core.backup_mgr import BackupManager
from core.error_codes import ErrorCode, error_response, safe_error_message

__all__ = ['San7ModMakerBase']

class San7ModMakerBase:
    """MOD制作器 - 基础类 (初始化 + 游戏目录管理)"""

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
        self.ini_template = IniTemplateEngine()
        self.mod_packager = ModPackager()
        self.termtext_allocator = TermTextAllocator()

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
        config_path = os.path.join(USER_DATA_DIR, self.CONFIG_FILE)
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"配置文件读取失败: {e}")
        return {"game_path": "", "recent_paths": [], "language": "zh_CN"}

    def _save_config(self):
        config_path = os.path.join(USER_DATA_DIR, self.CONFIG_FILE)
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
            self.validator.set_game_path(self.game_path)
            self.save_editor.set_game_path(self.game_path)
            self.custom_leader.set_game_path(self.game_path)
            self.scriptso_analyzer.set_game_path(self.game_path)

    # ============================================================
    # API: 游戏目录管理
    # ============================================================

    def api_set_game_path(self, path: str = None) -> dict:
        """设置游戏目录"""
        if path is None:
            if not HAS_TK:
                return {"success": False, "message": "当前环境不支持文件对话框，请手动输入路径"}
            import tkinter as tk
            from tkinter import filedialog
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
        self.ini_template.game_path = self.game_path

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
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        return self.version_detector.detect(self.game_path)

    # ============================================================
    # 通用 INI 辅助方法 (消除子类重复代码)
    # ============================================================

    def _load_ini_sections(self, filename: str, section: str):
        """加载 INI 文件指定 section 的条目列表。
        返回 (entries, error_dict) 元组。
        - entries: 条目字典列表，文件不存在时返回 []
        - error_dict: 错误时返回 error_response，成功时返回 None
        """
        if not self.game_path:
            return None, error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", filename)
        if not os.path.exists(path):
            return [], None
        parser = IniParser()
        parser.load(path)
        sections = parser.get_all_sections(section)
        return [dict(s.entries) for s in sections], None

    def _save_ini_sections(self, filename: str, entries: list, section: str, key_field: str = "No"):
        """保存 INI 文件指定 section。返回 error_dict 或 None。
        自动备份 + 原子写入。
        """
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", filename)
        if self.backup_mgr:
            self.backup_mgr.backup_file(path)
        parser = IniParser()
        if os.path.exists(path):
            parser.load(path)
        parser.replace_sections(section, entries, key_field)
        parser.save(path)
        return None

    def _check_id_not_exists(self, filename: str, section: str, no: int, label: str) -> Optional[dict]:
        """检查 INI 文件中指定编号是否已存在。
        返回 None 表示不存在（可继续），否则返回错误 dict。
        """
        if not self.game_path:
            return error_response(ErrorCode.GAME_PATH_NOT_SET)
        path = os.path.join(self.game_path, "Setting", filename)
        if not os.path.exists(path):
            return None
        parser = IniParser()
        parser.load(path)
        no_str = str(no)
        for s in parser.get_all_sections(section):
            if str(s.entries.get("No", "")) == no_str:
                return {"success": False, "message": f"{label}编号 {no} 已存在于 {filename}"}
        return None

    def _sync_term_text_names(self, data: list) -> None:
        """将 data 中的 Name 字段同步到 TermText（需 term_text 已加载）"""
        if self.term_text.is_loaded():
            for entry in data:
                name = entry.get("Name", "")
                if name:
                    self.term_text.allocate_new_id(name)
            self.term_text.save()

