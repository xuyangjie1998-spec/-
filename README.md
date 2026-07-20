# San7ModMaker - 三国群英传7 MOD制作器 V2.3

## 简介

San7ModMaker 是一款纯MOD制作工具（非存档修改器），提供可视化编辑界面来管理三国群英传7的全部游戏配置文件。

核心特色：
- 支持全类型内容新增（武将/兵种/物品/官职/技能/剧本）
- 完整INI结构化编辑，保留原始格式和注释
- 内置武将头像实时预览，支持SHP专用图片格式双向转换
- PCK资源包解包/提取，无需依赖外部工具
- 兵种相克矩阵可视化编辑器（67×67）
- EXE引擎限制突破（兵种67上限、属性255上限等）
- 多MOD独立隔离管理、一键打包分发
- MOD制作向导（5套模板，覆盖武将/势力/兵种/物品/完整MOD）

## 系统要求

- Windows 7/8/10/11
- Python 3.8+（源码运行）
- 三国群英传7游戏本体

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行程序

```bash
python main.py
```

### 3. 打包为EXE（可选）

```bash
pip install pyinstaller
pyinstaller build.spec
```

## 使用前的准备

1. 启动 San7ModMaker，选择游戏根目录
2. 程序会自动检测PCK文件状态，引导提取Setting文件
3. 也可使用 RPGViewer 或 SangoExplorer 手动解包 Sango7.pck
4. 确保存在以下目录：
   - `游戏目录/Setting/` - 存放所有INI配置文件
   - `游戏目录/Shape/Face/` - 存放武将头像SHP文件

## 功能模块

| 模块 | 状态 | 说明 |
|------|------|------|
| 底层核心引擎 | ✓ 已完成 | INI读写(GBK/Big5)、备份还原、字段映射 |
| 武将编辑 | ✓ 已完成 | 全字段编辑、DefSkill联动、SHP头像预览/转换 |
| 兵种编辑 | ✓ 已完成 | 全字段编辑、相克矩阵(67×67)、升级树 |
| 物品编辑 | ✓ 已完成 | 分类管理、商店配置、强化合成配方 |
| 技能/特性 | ✓ 已完成 | 武将技/军师技/必杀技/特性/主将特性/元帅特性 |
| 阵型/官职/等级 | ✓ 已完成 | 阵型/官职/等级/年代编辑器 |
| 剧本世界 | ✓ 已完成 | 剧本城池数据、势力编辑、全局参数 |
| 高级工具 | ✓ 已完成 | EXE突破、批量修改、差异对比、数据校验 |
| MOD管理 | ✓ 已完成 | 多MOD隔离、增量打包、导入/冲突重映射 |
| 资源管理 | ✓ 已完成 | PCK解包/提取、OBD模型编辑 |
| 存档管理 | ✓ 已完成 | 存档列表、备份/还原 |
| MOD向导 | ✓ 已完成 | 5套制作模板，步骤引导+checklist |

## 项目结构

```
San7ModMaker/
├── main.py                 # 程序主入口 (89个API, 227个JsApi桥接)
├── requirements.txt        # Python依赖
├── build.spec              # PyInstaller打包配置
├── core/                   # 底层核心引擎 (11个模块)
│   ├── ini_parser.py       # INI读写解析器(GBK/Big5/注释保留)
│   ├── term_text.py        # TermText文本管理器
│   ├── backup_mgr.py       # 备份还原系统
│   ├── validator.py        # 全局数据校验器(9类规则)
│   ├── field_mapper.py     # Schema↔游戏字段名映射
│   ├── shp_converter.py    # SHP头像解码/转换核心
│   ├── pck_manager.py      # PCK资源包管理
│   ├── obd_parser.py       # OBD模型文件解析
│   ├── save_editor.py      # 存档文件管理
│   ├── soldier_matrix.py   # 兵种相克矩阵编辑器
│   └── mod_wizard.py       # MOD制作向导
├── data/                   # 配置Schema、规则库 (20个Schema)
│   ├── general_schema.json
│   ├── soldier_schema.json
│   ├── thing_schema.json
│   ├── bfmagic_schema.json
│   ├── sfmagic_schema.json
│   ├── superatk_schema.json
│   ├── defskill_schema.json
│   ├── genskill_schema.json
│   ├── armyskill_schema.json
│   ├── armygroupskill_schema.json
│   ├── formation_schema.json
│   ├── title_schema.json
│   ├── nation_schema.json
│   ├── city_schema.json
│   ├── genlv_schema.json
│   ├── age_schema.json
│   ├── general02_schema.json
│   ├── scenario_schema.json
│   ├── variable_schema.json
│   ├── itemenhance_schema.json
│   └── field_mapping.json  # 字段映射表
├── web/                    # 前端页面 (32个编辑器页面)
│   ├── index.html          # 主界面
│   ├── style.css           # 全局样式
│   └── app.js              # 前端交互逻辑
├── mods/                   # MOD工程目录
├── backup/                 # 备份文件目录
├── exports/                # MOD导出目录
└── README.md
```

## 头像格式说明

- 资源路径：`游戏目录/Shape/Face/`
- 命名规则：`0001.shp` ~ `9999.shp`
- 尺寸：128×128 像素
- 色彩：256 色索引调色板
- 格式：SHP 二进制封装

支持功能：
- 实时预览武将头像
- PNG/JPG/BMP → SHP 转换（自动缩放、调色板适配）
- SHP → PNG 导出

## 已知限制

- PCK打包(repack)功能尚未实现，MOD分发需手动打包
- 存档编辑器仅支持基础分析，完整存档修改需进一步逆向

## 注意事项

- 所有修改操作前会自动备份原文件
- 建议定期清理备份目录以释放空间
- EXE修改前务必确认备份已生成

## 许可

本项目仅供MOD制作学习交流使用。