# San7ModMaker 架构文档

## 项目概述

San7ModMaker 是一款基于 PyWebView 的**三国群英传7 MOD制作器**桌面应用。采用 Python 后端 + HTML/CSS/JS 前端架构，通过 PyWebView 的 JS-Python 双向通信实现前后端交互。

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 桌面框架 | PyWebView | 嵌入式 WebView 窗口 |
| 前端 | HTML5 + CSS3 + Vanilla JS | 无框架依赖 |
| 后端 | Python 3.10+ | 核心业务逻辑 |
| 打包 | PyInstaller | Windows 单文件分发 |
| 测试 | pytest + unittest | 前后端测试 |

## 项目结构

```
San7ModMaker/
├── main.py                  # 应用入口, San7ModMaker 主类, JsApi 桥接
├── build.spec               # PyInstaller 打包配置
├── pytest.ini               # pytest 配置
│
├── core/                    # 核心引擎模块 (纯 Python 库)
│   ├── ini_parser.py        # 群7特殊 INI 解析器
│   ├── backup_mgr.py        # 自动备份/还原管理器
│   ├── validator.py         # 数据校验器
│   ├── shp_converter.py     # SHP 图片格式转换
│   ├── field_mapper.py      # 字段名映射 (Schema↔Game)
│   ├── term_text.py         # TermText 文本管理
│   ├── exe_patcher.py       # EXE 引擎限制突破
│   ├── pck_manager.py       # PCK 资源解包
│   ├── obd_parser.py        # OBD 模型解析
│   ├── save_editor.py       # 存档编辑器
│   ├── save_manager.py      # 存档管理器
│   ├── save_parser.py       # 存档解析器
│   ├── scriptso_analyzer.py # Script.so 分析器
│   ├── soldier_matrix.py    # 兵种相克矩阵
│   ├── mod_wizard.py        # MOD 制作向导
│   ├── mod_packager.py      # MOD 打包器
│   ├── csv_manager.py       # CSV 导入导出
│   ├── version_detect.py    # 游戏版本检测
│   ├── custom_leader.py     # 自建武将解析
│   ├── effect_catalog.py    # 特效目录
│   ├── encoding_converter.py# 编码转换 (GBK/Big5)
│   ├── event_templates.py   # 事件模板
│   ├── ini_template.py      # INI 模板引擎
│   └── termtext_allocator.py# TermText ID 分配器
│
├── routes/                  # API 路由 (Mixin 模块化架构)
│   ├── __init__.py          # 统一导出
│   ├── mixin_base.py        # 基础类: 初始化 + 游戏目录管理
│   ├── mixin_core.py        # 核心数据: 武将/兵种/物品/技能/特性
│   ├── mixin_game.py        # 游戏系统: 剧本/势力/城池/官职
│   ├── mixin_assets.py      # 资源管理: SHP/头像/图标/模型/特效
│   ├── mixin_tools.py       # 工具集: 备份/校验/EXE/批量/差异/MOD
│   └── mixin_advanced.py    # 高级功能: 存档/脚本/PCK/模板/引擎
│
├── data/                    # 数据文件
│   ├── schema/              # 20个 INI Schema 定义
│   └── field_mapping.json   # 字段映射配置
│
├── web/                     # 前端资源
│   ├── index.html           # 主页面 (模板加载器)
│   ├── style.css            # 样式表
│   ├── js/                  # JavaScript 模块
│   │   ├── core.js          # 核心工具函数 + 仪表盘
│   │   ├── panels-1.js      # 面板1: 武将/兵种/物品编辑
│   │   ├── panels-2.js      # 面板2: 技能/阵型/官职/剧本
│   │   ├── panels-3.js      # 面板3: 资源/头像/模型/特效
│   │   └── panels-4.js      # 面板4: 工具/EXE/存档/编码
│   ├── panels/              # HTML 模板
│   │   ├── nav.html         # 左侧导航
│   │   ├── content-1.html   # 内容面板1
│   │   └── content-2.html   # 内容面板2
│   └── tests/               # 前端测试
│       ├── index.html       # 测试运行页面
│       ├── test-runner.js   # 轻量测试运行器
│       └── test-core.js     # core.js 单元测试
│
├── tests/                   # 后端测试
│   ├── conftest.py          # 测试 Fixtures
│   ├── test_smoke.py        # 核心模块冒烟测试
│   ├── test_api_routes.py   # API 路由测试 (43个)
│   └── test_*.py            # 各模块专项测试
│
├── mods/                    # MOD 工程目录
├── exports/                 # MOD 导出目录
└── backup/                  # 自动备份目录
```

## 架构设计

### Mixin 模块化架构

main.py 的 `San7ModMaker` 类通过多重继承组合 6 个 Mixin 类:

```python
class San7ModMaker(
    San7ModMakerBase,      # 初始化 + 游戏目录管理
    San7ModMakerCore,      # 核心数据 CRUD
    San7ModMakerGame,      # 游戏系统编辑
    San7ModMakerAssets,    # 资源管理
    San7ModMakerTools,     # 工具集
    San7ModMakerAdvanced   # 高级功能
):
    pass
```

### 前后端通信

前端通过 `pyApi(method, ...args)` 调用后端 API:

```javascript
// 前端调用
const result = await pyApi('loadGenerals');

// 映射到后端方法
// _JsApi._API_MAP: {'loadGenerals': 'api_load_generals'}
// → San7ModMaker.api_load_generals()
```

### 数据流

```
用户操作 → JS 事件 → pyApi() → PyWebView Bridge
    → _JsApi._call() → San7ModMaker.api_xxx()
    → core 引擎处理 → INI 文件读写
    → 返回结果 → JS 更新 DOM
```

### 编码处理

- 游戏文件使用 Big5 编码（繁体中文）
- 前端使用 UTF-8
- 后端自动检测编码并转换
- `core/encoding_converter.py` 提供批量转换

## 开发指南

### 环境准备

```bash
# 安装依赖
pip install pywebview pillow --break-system-packages

# 安装测试依赖
pip install pytest --break-system-packages
```

### 运行测试

```bash
# 运行全部测试
python3 -m pytest tests/ -v

# 运行 API 路由测试
python3 -m pytest tests/test_api_routes.py -v

# 运行特定模块测试
python3 -m pytest tests/test_smoke.py -v

# 前端测试: 在浏览器中打开 web/tests/index.html
```

### 添加新 API

1. 在对应的 `routes/mixin_*.py` 中添加 `api_xxx()` 方法
2. 在 `main.py` 的 `_JsApi._API_MAP` 中注册映射
3. 在 `tests/test_api_routes.py` 中添加测试

### 添加新前端面板

1. 在 `web/panels/` 中创建 HTML 模板
2. 在 `web/js/panels-N.js` 中添加交互逻辑
3. 在 `web/index.html` 中注册模板加载

### 打包发布

```bash
pyinstaller build.spec
```

## 版本历史

当前版本: **3.13.0** (2026-07-24)

### 技术债务修复 (2026-07-27)

| 项目 | 状态 | 说明 |
|------|------|------|
| 拆分 app.js | ✅ | 18K行 → 5个模块 (core + panels-1~4) |
| 拆分 index.html | ✅ | 5.8K行 → 模板化加载 |
| 拆分 main.py | ✅ | 12K行 → 6个 Mixin 类 |
| 测试框架 | ✅ | 43个 API 测试 + JS 测试框架 |
| 类型注解 | ✅ | `__all__` + 类型注解补充 |
| 开发者文档 | ✅ | 本文档 |