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
# PyInstaller 打包后:
#   PROJECT_ROOT = sys._MEIPASS (只读，存放打包的资源文件：data/ web/ core/)
#   WRITE_ROOT   = exe所在目录 (可写，存放用户数据：mods/ exports/ sandbox/ backup/)
# 开发模式: 两者相同
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = sys._MEIPASS
    WRITE_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    WRITE_ROOT = PROJECT_ROOT
sys.path.insert(0, PROJECT_ROOT)

# 用户配置目录（打包后写入 %APPDATA%/San7ModMaker，确保配置持久化）
def _get_user_data_dir():
    """获取用户配置目录"""
    if getattr(sys, 'frozen', False):
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        data_dir = os.path.join(base, 'San7ModMaker')
    else:
        data_dir = PROJECT_ROOT
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

USER_DATA_DIR = _get_user_data_dir()

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
from core.ini_template import IniTemplateEngine
from core.mod_packager import ModPackager
from core.termtext_allocator import TermTextAllocator

from routes import (
    San7ModMakerBase, San7ModMakerCore, San7ModMakerGame,
    San7ModMakerAssets, San7ModMakerTools, San7ModMakerAdvanced
)

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
    "version": "3.13.0",
    "last_updated": "2026-07-24",
    "known_issues": []
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
class San7ModMaker(
    San7ModMakerBase,
    San7ModMakerCore,
    San7ModMakerGame,
    San7ModMakerAssets,
    San7ModMakerTools,
    San7ModMakerAdvanced
):
    """MOD制作器主应用 — API 方法已拆分为 routes/ 下的 Mixin 类"""
    pass

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
        'cleanupBackups': 'api_cleanup_backups',
        'autoBackupConfig': 'api_auto_backup_config',
        'autoBackupStatus': 'api_auto_backup_status',
        'shpBatchConvert': 'api_shp_batch_convert',
        'batchRename': 'api_batch_rename',
        'dashboardStats': 'api_dashboard_stats',
        'batchCloneExecute': 'api_batch_clone_execute',
        'batchClonePreview': 'api_batch_clone_preview',
        'batchExecute': 'api_batch_execute',
        'batchPreview': 'api_batch_preview',
        'batchSearch': 'api_batch_search',
        'batchSearchReplace': 'api_batch_search_replace',
        'blockCalc': 'api_block_calc',
        'blockInverse': 'api_block_inverse',
        'bmp2raw': 'api_bmp2raw',
        'raw2bmp': 'api_raw2bmp',
        'bmp2rawBatch': 'api_bmp2raw_batch',
        'bmpPreview': 'api_bmp_preview',
        'shpPixelLoad': 'api_shp_pixel_load',
        'shpPixelSave': 'api_shp_pixel_save',
        'shpGetPalette': 'api_shp_get_palette',
        'browseShapeResources': 'api_browse_shape_resources',
        'checkReferences': 'api_check_references',
        'checkModCompatibility': 'api_check_mod_compatibility',
        'checkModDependencies': 'api_check_mod_dependencies',
        'getModDependencies': 'api_get_mod_dependencies',
        'setModDependencies': 'api_set_mod_dependencies',
        'modConflictDetect': 'api_mod_conflict_detect',
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
        'customgenAdd': 'api_customgen_add',
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
        'effectBatchModify': 'api_effect_batch_modify',
        'effectBatchPreview': 'api_effect_batch_preview',
        'effectCrossRef': 'api_effect_cross_ref',
        'effectDamageTypes': 'api_effect_damage_types',
        'effectDeleteType': 'api_effect_delete_type',
        'effectElementTypes': 'api_effect_element_types',
        'effectExportJson': 'api_effect_export_json',
        'effectGetAll': 'api_effect_get_all',
        'effectImportJson': 'api_effect_import_json',
        'effectItemScripts': 'api_effect_item_scripts',
        'effectSaveType': 'api_effect_save_type',
        'effectTemplates': 'api_effect_templates',
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
        'getNextFaceId': 'api_get_next_face_id',
        'faceBrowse': 'api_face_browse',
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
        'listMods': 'api_get_mod_list',
        'getProgress': 'api_get_progress',
        'getDataFile': 'api_get_data_file',
        'getSango7Config': 'api_get_sango7_config',
        'getSchema': 'api_get_schema',
        'getSoldierObdInfo': 'api_get_soldier_obd_info',
        'getThingTermText': 'api_get_thing_termtext',
        'getThingIconPreview': 'api_get_thing_icon_preview',
        'getNextThingIconId': 'api_get_next_thing_icon_id',
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
        'listOBDModels': 'api_list_obd_models',
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
        'previewModInstall': 'api_preview_mod_install',
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
        'previewBfobjAnimation': 'api_preview_bfobj_animation',
        'listBfobjAnimDirs': 'api_list_bfobj_anim_dirs',
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
        'shapeInfoDelete': 'api_shape_info_delete',
        'shapeInfoClone': 'api_shape_info_clone',
        'shapeInfoNew': 'api_shape_info_new',
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
        'deleteSoldier': 'api_delete_soldier',
        'wizardCreateNation': 'api_wizard_create_nation',
        'wizardCreateItem': 'api_wizard_create_item',
        'wizardDependencies': 'api_wizard_dependencies',
        'wizardGetSample': 'api_wizard_get_sample',
        'wizardProgress': 'api_wizard_progress',
        'wizardStart': 'api_wizard_start',
        'wizardStep': 'api_wizard_step',
        'wizardTemplates': 'api_wizard_templates',
        'writeLanguageDat': 'api_write_language_dat',
        # V3.5.0: BGM/音效编辑器
        'browseAudio': 'api_browse_audio',
        'previewAudio': 'api_preview_audio',
        'importAudio': 'api_import_audio',
        'deleteAudio': 'api_delete_audio',
        'renameAudio': 'api_rename_audio',
        # V3.5.0: 沙盒测试模式
        'createSandbox': 'api_create_sandbox',
        'installToSandbox': 'api_install_to_sandbox',
        'launchSandbox': 'api_launch_sandbox',
        'cleanupSandbox': 'api_cleanup_sandbox',
        'getSandboxStatus': 'api_get_sandbox_status',
        # V3.5.0: 操作历史记录
        'getOperationHistory': 'api_get_operation_history',
        'clearOperationHistory': 'api_clear_operation_history',
        # V3.6.0: 批量自动化增强
        'batchPreviewAdv': 'api_batch_preview_adv',
        'batchExecuteAdv': 'api_batch_execute_adv',
        'batchPresetList': 'api_batch_preset_list',
        'batchPresetSave': 'api_batch_preset_save',
        'batchPresetLoad': 'api_batch_preset_load',
        'batchPresetDelete': 'api_batch_preset_delete',
        'batchUndo': 'api_batch_undo',
        'batchPipelineExecute': 'api_batch_pipeline_execute',
        # V3.7.0: MOD 安装回滚 / 重新安装 / 打包校验
        'modRollback': 'api_mod_rollback',
        'modReinstall': 'api_mod_reinstall',
        'modValidatePack': 'api_mod_validate_pack',
        # V3.8.0: 素材资源管理增强 — 批量导入/搜索/分类
        'resourceSearch': 'api_resource_search',
        'resourceBatchImport': 'api_resource_batch_import',
        'resourceCategorize': 'api_resource_categorize',
        # V3.8.0: 差异对比增强 — 跨MOD对比/摘要报告
        'diffCrossMod': 'api_diff_cross_mod',
        'diffSummary': 'api_diff_summary',
        # V3.8.0: MOD打包增强 — 完整打包/分发包/预设
        'packModFull': 'api_pack_mod_full',
        'packModDistribution': 'api_pack_mod_distribution',
        'packModPreset': 'api_pack_mod_preset',
        # V3.12.0: MOD 打包分发系统 (mod_packager)
        'analyzeModStructure': 'api_analyze_mod_structure',
        'resolveModDeps': 'api_resolve_mod_deps',
        'generateModInstaller': 'api_generate_mod_installer',
        'detectModConflictsV2': 'api_detect_mod_conflicts_v2',
        'resolveModConflictsV2': 'api_resolve_mod_conflicts_v2',
        'generateModReadme': 'api_generate_mod_readme',
        'versionBumpMod': 'api_version_bump_mod',
        'createModSnapshotV2': 'api_create_mod_snapshot_v2',
        'compareModSnapshots': 'api_compare_mod_snapshots',
        # V3.12.0: TermText 智能编号分配器 (termtext_allocator)
        'allocateTermtextId': 'api_allocate_termtext_id',
        'allocateTermtextBatch': 'api_allocate_termtext_batch',
        'detectTermtextConflicts': 'api_detect_termtext_conflicts',
        'resolveTermtextConflicts': 'api_resolve_termtext_conflicts',
        'migrateTermtextIds': 'api_migrate_termtext_ids',
        'getTermtextSegmentInfo': 'api_get_termtext_segment_info',
        'getTermtextAllSegments': 'api_get_termtext_all_segments',
        'smartAllocateTermtext': 'api_smart_allocate_termtext',
        'crossFileTermtextDetect': 'api_cross_file_termtext_detect',
        'generateTermtextReport': 'api_generate_termtext_report',
        'autoRemediateTermtext': 'api_auto_remediate_termtext',
        # V3.12.0: INI 模板化数据生成引擎 (ini_template)
        'createDataTemplate': 'api_create_data_template',
        'saveTemplate': 'api_save_template',
        'loadTemplate': 'api_load_template',
        'listTemplates': 'api_list_templates',
        'deleteTemplate': 'api_delete_template',
        'generateFromTemplate': 'api_generate_from_template',
        'generateCrossFile': 'api_generate_cross_file',
        'batchGenerateTemplates': 'api_batch_generate_templates',
        'validateCrossFileData': 'api_validate_cross_file_data',
        'getPresetTemplates': 'api_get_preset_templates',
        'mergeTemplates': 'api_merge_templates',
        'applyTemplateOverrides': 'api_apply_template_overrides',
        'transformTemplateData': 'api_transform_template_data',
        # V3.12.0: 引擎突破 — Script.so 深层逆向
        'buildScriptsoCfg': 'api_build_scriptso_cfg',
        'findScriptsoVtables': 'api_find_scriptso_vtables',
        'injectScriptsoCodeCave': 'api_inject_scriptso_code_cave',
        # V3.12.0: 引擎突破 — SG7-XX.sav 深度逆向
        'deepParseSg7Save': 'api_deep_parse_sg7_save',
        'editSaveGeneral': 'api_edit_save_general',
        # V3.12.0: 引擎突破 — EXE Code Cave 注入
        'findExeCodeCave': 'api_find_exe_code_cave',
        'injectExeCodeCave': 'api_inject_exe_code_cave',
        'buildJumpStub': 'api_build_jump_stub',
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
    try:
        app = San7ModMaker()
        app.run()
    except Exception as e:
        logger.critical(f"程序启动失败: {e}", exc_info=True)
        try:
            import tkinter.messagebox as mb
            mb.showerror("启动失败", f"程序启动时发生异常:\n\n{str(e)[:300]}")
        except Exception:
            pass
        sys.exit(1)