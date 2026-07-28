"""
San7ModMaker - API 路由模块
将 main.py 的 ~500 个 API 方法拆分为独立 Mixin 类
"""

from .mixin_base import San7ModMakerBase
from .mixin_core import San7ModMakerCore
from .mixin_game import San7ModMakerGame
from .mixin_assets import San7ModMakerAssets
from .mixin_tools import San7ModMakerTools
from .mixin_advanced import San7ModMakerAdvanced
from .mixin_save_edit import San7ModMakerSaveEdit
from .mixin_scriptso import San7ModMakerScriptSO
from .mixin_wizard import San7ModMakerWizard
from .mixin_mod import San7ModMakerMod

__all__ = [
    'San7ModMakerBase',
    'San7ModMakerCore',
    'San7ModMakerGame',
    'San7ModMakerAssets',
    'San7ModMakerTools',
    'San7ModMakerAdvanced',
    'San7ModMakerSaveEdit',
    'San7ModMakerScriptSO',
    'San7ModMakerWizard',
    'San7ModMakerMod',
]
