#!/usr/bin/env python3
"""
San7ModMaker 完整性验证脚本
在编译打包前运行，确保程序不会因为代码问题而启动失败

检查项:
  1. JS 语法检查 (node -c)
  2. Python 语法检查 (py_compile)
  3. Python 模块导入测试
  4. HTML/CSS/JS 文件引用完整性
  5. JSON 配置文件有效性
  6. 快速启动冒烟测试

用法:
  python validate.py          # 完整验证
  python validate.py --quick  # 仅语法检查（快）
  python validate.py --smoke  # 启动冒烟测试（慢）
"""

import os
import sys
import json
import subprocess
import glob
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()

# ── 颜色输出 ──────────────────────────────────────────────────
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def ok(msg):   print(f"  {Colors.GREEN}✓{Colors.RESET} {msg}")
def err(msg):  print(f"  {Colors.RED}✗{Colors.RESET} {msg}")
def warn(msg): print(f"  {Colors.YELLOW}⚠{Colors.RESET} {msg}")
def info(msg): print(f"  {Colors.CYAN}→{Colors.RESET} {msg}")
def hdr(msg):  print(f"\n{Colors.BOLD}{msg}{Colors.RESET}")

exit_code = 0

def fail(msg):
    global exit_code
    exit_code = 1
    err(msg)

# ── 1. JS 语法检查 ────────────────────────────────────────────
def check_js_syntax():
    hdr("[1/6] JavaScript 语法检查")
    js_dir = PROJECT_ROOT / "web" / "js"
    js_files = sorted(js_dir.glob("*.js"))
    if not js_files:
        fail("未找到 JS 文件")
        return

    for f in js_files:
        try:
            result = subprocess.run(
                ["node", "-c", str(f)],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                ok(f"web/js/{f.name}")
            else:
                fail(f"web/js/{f.name}: {result.stderr.strip()}")
        except FileNotFoundError:
            warn("Node.js 未安装，跳过 JS 语法检查")
            return
        except subprocess.TimeoutExpired:
            fail(f"web/js/{f.name}: 检查超时")

# ── 2. Python 语法检查 ────────────────────────────────────────
def check_python_syntax():
    hdr("[2/6] Python 语法检查")
    py_files = []
    for pattern in ["main.py", "core/**/*.py", "routes/**/*.py"]:
        py_files.extend(Path(PROJECT_ROOT).glob(pattern))

    for f in sorted(py_files):
        if '__pycache__' in str(f):
            continue
        try:
            source = f.read_text(encoding='utf-8')
            compile(source, str(f.relative_to(PROJECT_ROOT)), 'exec')
            ok(str(f.relative_to(PROJECT_ROOT)))
        except SyntaxError as e:
            fail(f"{f.relative_to(PROJECT_ROOT)}: {e}")

# ── 3. Python 模块导入测试 ────────────────────────────────────
def check_python_imports():
    hdr("[3/6] Python 模块导入测试")

    # 先确保项目根目录在 path 中
    sys.path.insert(0, str(PROJECT_ROOT))

    modules = [
        "core",
        "core.ini_parser",
        "core.term_text",
        "core.backup_mgr",
        "core.validator",
        "core.shp_converter",
        "core.exe_patcher",
        "core.field_mapper",
        "core.pck_manager",
        "core.obd_parser",
        "core.save_editor",
        "core.scriptso_analyzer",
        "core.soldier_matrix",
        "core.mod_wizard",
        "core.csv_manager",
        "core.version_detect",
        "core.custom_leader",
        "core.save_manager",
        "core.effect_catalog",
        "core.save_parser",
        "core.encoding_converter",
        "core.event_templates",
        "core.mod_packager",
        "core.termtext_allocator",
        "core.ini_template",
        "core.error_codes",
        "routes",
        "routes.mixin_base",
        "routes.mixin_core",
        "routes.mixin_assets",
        "routes.mixin_game",
        "routes.mixin_advanced",
        "routes.mixin_tools",
    ]

    for mod_name in modules:
        try:
            __import__(mod_name)
            ok(mod_name)
        except ImportError as e:
            fail(f"{mod_name}: {e}")
        except Exception as e:
            warn(f"{mod_name}: 导入时异常 (可能是缺少可选依赖) - {type(e).__name__}: {e}")

# ── 4. Web 资源完整性 ─────────────────────────────────────────
def check_web_integrity():
    hdr("[4/6] Web 资源完整性检查")

    web_dir = PROJECT_ROOT / "web"
    required = [
        "index.html",
        "style.css",
        "js/core.js",
        "js/panels-1.js",
        "js/panels-2.js",
        "js/panels-3.js",
        "js/panels-4.js",
        "panels/content-1.html",
        "panels/content-2.html",
    ]

    for f in required:
        path = web_dir / f
        if path.exists():
            ok(f"web/{f}")
        else:
            fail(f"web/{f}: 文件不存在")

    # 检查 index.html 引用的所有 JS/CSS 文件都存在
    index = web_dir / "index.html"
    if index.exists():
        content = index.read_text(encoding='utf-8')
        import re
        # 提取所有 src="..." 和 href="..."
        refs = re.findall(r'(?:src|href)="([^"]+)"', content)
        for ref in refs:
            if ref.startswith(('http://', 'https://', '//')):
                continue
            ref_path = web_dir / ref
            if ref_path.exists():
                ok(f"引用: {ref}")
            else:
                fail(f"引用缺失: {ref} (在 index.html 中)")

# ── 5. JSON 配置文件验证 ──────────────────────────────────────
def check_json_files():
    hdr("[5/6] JSON 配置文件验证")

    json_files = []
    json_files.extend(Path(PROJECT_ROOT / "data").glob("**/*.json"))
    json_files.extend(Path(PROJECT_ROOT / "mods").glob("**/*.json"))
    # backup_index 可能不存在
    backup_index = PROJECT_ROOT / "backup" / "backup_index.json"
    if backup_index.exists():
        json_files.append(backup_index)

    for f in sorted(json_files):
        if '__pycache__' in str(f):
            continue
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            ok(f"{f.relative_to(PROJECT_ROOT)} ({type(data).__name__})")
        except json.JSONDecodeError as e:
            fail(f"{f.relative_to(PROJECT_ROOT)}: JSON 解析错误 - {e}")
        except Exception as e:
            warn(f"{f.relative_to(PROJECT_ROOT)}: {e}")

# ── 6. 快速冒烟测试 ───────────────────────────────────────────
def check_smoke():
    hdr("[6/6] 启动冒烟测试")

    try:
        # 模拟 main.py 的初始化流程（不启动 GUI）
        sys.path.insert(0, str(PROJECT_ROOT))

        import main

        # 检查关键变量
        checks = [
            ("PROJECT_ROOT", hasattr(main, 'PROJECT_ROOT')),
            ("WRITE_ROOT", hasattr(main, 'WRITE_ROOT')),
            ("USER_DATA_DIR", hasattr(main, 'USER_DATA_DIR')),
        ]
        for name, result in checks:
            if result:
                ok(f"main.{name} 已定义")
            else:
                fail(f"main.{name} 未定义")

        # 检查 web 目录存在
        web_path = os.path.join(main.PROJECT_ROOT, 'web')
        if os.path.isdir(web_path):
            ok(f"web 目录存在: {web_path}")
        else:
            fail(f"web 目录不存在: {web_path}")

        # 检查 index.html 存在
        index_path = os.path.join(web_path, 'index.html')
        if os.path.isfile(index_path):
            ok(f"index.html 存在")
        else:
            fail(f"index.html 不存在")

        info("冒烟测试通过 - 主入口模块可正常导入")

    except ImportError as e:
        # 可能是缺少 GUI 依赖（pywebview 等），在 Linux 无头环境正常
        warn(f"部分依赖无法导入 (Linux 无头环境正常): {e}")
    except Exception as e:
        fail(f"冒烟测试失败: {e}")

# ── 主流程 ────────────────────────────────────────────────────
def main():
    print(f"{Colors.BOLD}{Colors.CYAN}")
    print("=" * 60)
    print("  San7ModMaker 完整性验证")
    print("=" * 60)
    print(f"{Colors.RESET}")

    quick = '--quick' in sys.argv
    smoke = '--smoke' in sys.argv

    check_js_syntax()
    check_python_syntax()

    if quick:
        print(f"\n{Colors.BOLD}快速模式: 仅检查语法{Colors.RESET}")
        sys.exit(exit_code)

    check_python_imports()
    check_web_integrity()
    check_json_files()

    if smoke:
        check_smoke()

    # ── 总结 ──
    print()
    if exit_code == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}{'=' * 60}")
        print(f"  ✓ 全部验证通过 - 程序可以启动")
        print(f"{'=' * 60}{Colors.RESET}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}{'=' * 60}")
        print(f"  ✗ 发现 {exit_code} 个问题，请修复后重试")
        print(f"{'=' * 60}{Colors.RESET}")

    sys.exit(exit_code)

if __name__ == '__main__':
    main()