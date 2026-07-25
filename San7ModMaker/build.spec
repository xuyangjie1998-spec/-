# -*- mode: python ; coding: utf-8 -*-
import os
import glob

# 项目根目录
PROJECT_ROOT = SPECPATH

# 自动发现 core/ 下所有模块（避免手动维护 hiddenimports 遗漏）
def _discover_core_modules():
    """自动发现 core/ 目录下所有 .py 模块"""
    core_dir = os.path.join(PROJECT_ROOT, 'core')
    modules = ['core']
    if os.path.isdir(core_dir):
        for f in sorted(os.listdir(core_dir)):
            if f.endswith('.py') and not f.startswith('_'):
                mod_name = f[:-3]  # 去掉 .py
                modules.append(f'core.{mod_name}')
    return modules

CORE_MODULES = _discover_core_modules()

# 收集 mods 目录下的所有文件
mods_files = []
for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, 'mods')):
    for f in files:
        src = os.path.join(root, f)
        rel = os.path.relpath(os.path.join(root, f), os.path.join(PROJECT_ROOT, 'mods'))
        mods_files.append((src, os.path.join('mods', rel)))

# 收集 exports 目录下的所有文件
exports_files = []
for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, 'exports')):
    for f in files:
        src = os.path.join(root, f)
        rel = os.path.relpath(os.path.join(root, f), os.path.join(PROJECT_ROOT, 'exports'))
        exports_files.append((src, os.path.join('exports', rel)))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('web', 'web'),
        ('data', 'data'),
        ('core', 'core'),
        (os.path.join(PROJECT_ROOT, 'active_mod.txt'), '.'),
        *mods_files,
        *exports_files,
    ],
    hiddenimports=[
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'webview',
        'webview.platforms.cef',
        'webview.platforms.gtk',
        'chardet',
        'json',
        'struct',
        'base64',
        'io',
        'logging',
        'csv',
        'tempfile',
        'tkinter',
        'tkinter.filedialog',
        *CORE_MODULES,  # 自动发现所有 core/*.py 模块
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter.test',
        'unittest',
        'email',
        'http',
        'xml',
        'pydoc',
        'test',
        'tests',
        'setuptools',
        'pip',
        'pkg_resources',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='San7ModMaker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)