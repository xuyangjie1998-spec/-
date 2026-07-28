# San7ModMaker - 三国群英传7 MOD制作器 V3.13.1

## 简介

San7ModMaker 是一款纯MOD制作工具（非存档修改器），提供可视化编辑界面来管理三国群英传7的全部游戏配置文件。

核心特色：
- 支持全类型内容新增（武将/兵种/物品/官职/技能/剧本/势力）
- 完整INI结构化编辑，保留原始格式和注释，Big5/GBK双编码
- 内置武将头像实时预览，支持SHP专用图片格式双向转换（含GenFace头像+ThingIcon物品图标）
- PCK资源包解包/提取，无需依赖外部工具
- 兵种相克矩阵可视化编辑器（67×67）
- EXE引擎限制突破（兵种67上限、属性255上限等）
- 多MOD独立隔离管理、一键打包分发（含自动校验）
- MOD制作向导（武将/势力/兵种/物品，一键联动创建）
- 数据仪表盘：首页实时统计武将/兵种/物品/技能等数据量
- 深色/浅色主题切换，支持本地记忆
- SHP批量转换工具（PNG目录→SHP，支持GenFace/ThingIcon/genhalf）
- 批量重命名功能（支持武将/兵种/物品/技能/官职等）
- 自动备份清理（保留最近10个快照）
- SG7Setting文档全面应用：47个Schema + 4个参考数据文件 + 21个xlsx数据表
- 三大MOD制作流程：新势力/新武将+头像CG/新物品+图标 完整向导
- 参考数据服务：编辑器内自动显示原版属性对比
- **V3.2.2+** 特效制作全流程：16个模板/标签筛选/一键创建技能/交叉引用追溯
- **V3.2.3+** 现场内特效制作：快速创建技能面板/参数可视化/模板加载
- **V3.2.4+** 技能编辑器深度增强：Desc自动生成/特效预览/参数校验/智能推荐/强度评分
- **V3.2.5+** 特效数据CRUD/JSON导出导入/批量修改技能特效
- **V3.2.6+** 版本号统一/编辑器脏标记/死代码清理/地图编辑器统一/52个测试用例
- **V3.2.7+** 物品编辑器特效预览/模板参数校验/发光OBD跳转/批量修改扩展/交叉引用缓存/60个测试用例
- **V3.2.8+** 兵种制作板块完善：ObjID模型选择器/OBD跳转/模型预览/技能配置/CSV字段对齐(36字段)
- **V3.2.9+** 编辑器CRUD补全：自定义武将+城池商店+个人特性+saveCurrent标准化(10个编辑器)
- **V3.2.10+** BMP↔RAW双向转换(reverse/batch/preview)、gameText/obd/idini编辑器CRUD标准化
- **V3.2.11+** BUG修复(uisubsystem空指针+bmp2raw引用)、shapeInfo/map/mpc/sango7编辑器CRUD标准化
- **V3.2.12+** surnameEditor数据丢失修复、shapeInfoEditor补全addNew、obd/scriptEditor标准化
- **V3.2.13+** saveCurrent()行为统一(撤销栈污染修复)、调试残留清理
- **V3.2.14+** 修复4个API映射缺失 + 4个编辑器Tab未注册 + superAtkEditor/scriptEditor补全saveCurrent + 调试日志规范化
- **V3.2.15+** blockcalc注册到_editorTabMap定义 + 清理废弃storeConfig/crafting映射 + 新增event_templates测试(16用例)
- **V3.3.0+** 端到端工作流打通：头像自动分配+兵种OBD绑定+物品图标关联+MOD安装预览
- **V3.4.0+** MOD依赖管理+SHP像素编辑器+合并冲突检测
- **V3.5.0+** BGM/音效编辑器+沙盒测试模式+操作历史记录
- **V3.6.0+** 批量自动化：复合筛选+预设模板+撤销回滚+操作流水线
- **V3.7.0+** MOD安装回滚/重装+打包校验+核心模块测试覆盖(109→361用例)
- **V3.8.0+** 素材资源管理增强+差异对比增强+MOD打包增强+测试覆盖(361→467用例)
- **V3.9.0+** 核心模块测试全覆盖(467→542用例)+scriptso/validator/csv_manager深度测试
- **V3.10.0+** 存档管理+自建武将测试覆盖(542→566用例)+save/load格式一致性修复
- **V3.11.0+** Script.so运行时修改框架+PCK增量打包+SHP批量处理流水线(566→757用例)
- **V3.12.0+** 引擎突破(EXE/存档/Script.so三大逆向)+大型MOD基础设施(打包/编号/模板)
- **V3.13.0+** 四大可视化操作面板(打包/编号/模板/引擎)+全模块主应用集成+757用例
- **V3.13.1+** 代码质量全面提升：XSS安全修复(15+处)+箭头函数现代化(40+处)+CSS变量系统化(32+处)+自动验证脚本

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

### 3. 下载预编译EXE（推荐）

从 [Release 页面](https://github.com/xuyangjie1998-spec/-/releases) 下载 `San7ModMaker.exe`，直接运行。

### 4. 打包为EXE（可选）

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
   - `游戏目录/Shape/GenFace/` - 存放武将头像SHP文件
   - `游戏目录/Shape/ThingIcon/` - 存放物品图标SHP文件

## 功能模块

| 模块 | 状态 | 说明 |
|------|------|------|
| 底层核心引擎 | ✓ 已完成 | INI读写(Big5/GBK)、备份还原、字段映射、原子写入 |
| 武将编辑 | ✓ 已完成 | 45字段全编辑、头像预览/转换、原版参考数据对比 |
| 兵种编辑 | ✓ 已完成 | 99字段全编辑、相克矩阵(67×67)、升级树、动画帧导入 |
| 物品编辑 | ✓ 已完成 | 52字段全编辑、商店配置、强化合成、图标导入/导出 |
| 技能/特性 | ✓ 已完成 | 武将技/军师技/必杀技/个人特性/主将特性/元帅特性 |
| 阵型/官职/等级 | ✓ 已完成 | 阵型/官职/等级/年代编辑器 |
| 势力编辑 | ✓ 已完成 | 13字段全编辑、一键联动创建(Nation+Color+City+City01-10+TermText) |
| 历史事件 | ✓ 已完成 | 全字段CRUD(含S_Gen/D_Gen 6子字段)、搜索过滤、克隆、事件模板生成 |
| 剧本世界 | ✓ 已完成 | 剧本城池数据、全局参数(252参数×22子字段注释) |
| 高级工具 | ✓ 已完成 | EXE突破、批量修改、差异对比、数据校验、引用检查、全局搜索、跨文件批量 |
| MOD管理 | ✓ 已完成 | 多MOD隔离、增量打包、导入/冲突重映射、**MOD合并** |
| 资源管理 | ✓ 已完成 | PCK解包/打包(patch+shape)、OBD模型编辑(28种类型)、SHP双向转换 |
| 存档编辑 | ✓ 已完成 | SG7剧本存档武将全属性编辑、装备/兵种/技能/阵型修改、CustomGen管理 |
| MOD向导 | ✓ 已完成 | 武将/势力/兵种/物品 一键创建，全联动自动写入 |
| 平衡分析 | ✓ 已完成 | 武将/兵种/物品属性统计(min/max/avg)、类型分布、平衡性诊断 |
| 文档参考 | ✓ 已完成 | 47个Schema、4个参考数据文件、21个xlsx原版数据表、Variable.ini子字段注释 |
| 参考数据 | ✓ 已完成 | 编辑器内原版数据对比面板、Variable.ini子字段实时注释 |

## 项目结构

```
San7ModMaker/
├── main.py                 # 程序主入口 (500+ API, 500+ JsApi 桥接)
├── requirements.txt        # Python依赖
├── build.spec              # PyInstaller打包配置
├── core/                   # 底层核心引擎 (24个模块)
│   ├── ini_parser.py       # INI读写解析器(Big5/GBK/注释保留)
│   ├── term_text.py        # TermText文本管理器(18个段映射)
│   ├── backup_mgr.py       # 备份还原系统
│   ├── validator.py        # 全局数据校验器(9类规则)
│   ├── field_mapper.py     # Schema↔游戏字段名映射
│   ├── shp_converter.py    # SHP头像/图标解码转换核心
│   ├── pck_manager.py      # PCK资源包管理
│   ├── obd_parser.py       # OBD模型文件解析(28种类型)
│   ├── save_editor.py      # 存档文件管理
│   ├── soldier_matrix.py   # 兵种相克矩阵编辑器
│   └── mod_wizard.py       # MOD制作向导
├── data/                   # 配置Schema、规则库、参考数据
│   ├── *_schema.json       # 47个Schema文件(全INI类型覆盖)
│   ├── *_ref.json          # 4个参考数据文件
│   │   ├── variable_ref.json       # Variable.ini 18大类高层摘要
│   │   ├── variable_full_ref.json  # Variable.ini 141参数子字段注释
│   │   ├── thing_type_ref.json     # 物品类型/稀有度/ScriptNo参考
│   │   └── cross_ref_table.json    # 跨文件编号引用对照表
│   ├── xlsx_*.json         # 21个原版数据表(Thing/Soldier/General01等)
│   ├── changfeng_xls_ref.json      # 长风吹云.xls(38个Sheet)
│   ├── termtext_segments.json      # TermText编号段映射
│   ├── color_palette.act           # 256色调色板
│   └── field_mapping.json          # 字段映射表
├── web/                    # 前端页面 (100+编辑器对象)
│   ├── index.html          # 主界面
│   ├── style.css           # 全局样式 (CSS变量驱动)
│   ├── js/                 # JavaScript 模块 (5文件拆分)
│   │   ├── core.js         # 核心工具函数 (DOM/颜色常量/主题/Toast/撤销)
│   │   ├── panels-1.js     # 面板1: 武将/兵种/物品/资源浏览
│   │   ├── panels-2.js     # 面板2: 技能/阵型/官职/事件/剧本
│   │   ├── panels-3.js     # 面板3: 资源/头像/模型/特效/存档
│   │   └── panels-4.js     # 面板4: 工具/EXE/打包/引擎/模板
│   └── panels/             # HTML 模板
│       ├── nav.html        # 左侧导航
│       ├── content-1.html  # 内容面板1
│       └── content-2.html  # 内容面板2
├── docs/                   # 文档资料
│   └── SG7Setting说明/     # SG7Setting完整文档(225个文件)
├── validate.py             # 6项完整性自动验证脚本
├── .github/workflows/      # CI/CD自动构建
│   └── build-exe.yml       # Windows EXE自动编译+发布Release
├── mods/                   # MOD工程目录
├── backup/                 # 备份文件目录
├── exports/                # MOD导出目录
└── README.md
```

## 头像/图标格式说明

### 武将头像 (GenFace)
- 资源路径：`游戏目录/Shape/GenFace/`
- 命名规则：`0001.shp` ~ `9999.shp`
- 尺寸：128×128 像素
- 色彩：256 色索引调色板
- 格式：SHP 二进制封装(8字节文件头 + 像素数据)

### 物品图标 (ThingIcon)
- 资源路径：`游戏目录/Shape/ThingIcon/`
- 命名规则：`0001.shp` ~ `9999.shp`
- 尺寸：64×64 像素
- 格式：同武将头像SHP格式

支持功能：
- 实时预览武将头像和物品图标
- PNG/JPG/BMP → SHP 转换（自动缩放、调色板适配）
- SHP → PNG 导出
- 批量导入/导出

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| V3.13.1 | 2026-07-28 | 代码质量提升：XSS安全修复(15+)+箭头函数(40+)+CSS变量(32+)+自动验证脚本 |
| V3.13.0 | 2026-07-26 | 四大可视化操作面板(MOD打包/TermText编号/INI模板/引擎逆向)+全模块集成 |
| V3.12.0 | 2026-07-25 | 引擎突破(EXE/存档/Script.so)+MOD基础设施(打包/编号/模板)+757用例 |
| V3.11.0 | 2026-07-25 | Script.so运行时修改框架+PCK增量打包+SHP批量处理 |
| V3.10.0 | 2026-07-25 | 存档管理+自建武将测试覆盖+save/load格式一致性修复 |
| V3.9.0 | 2026-07-25 | 核心模块测试全覆盖(467→542)+深度测试(scriptso/validator/csv) |
| V3.8.0 | 2026-07-25 | 素材资源管理+差异对比+MOD打包增强+测试覆盖(361→467) |
| V3.7.0 | 2026-07-25 | MOD安装回滚/重装+打包校验+核心模块测试(109→361) |
| V3.6.0 | 2026-07-25 | 批量自动化：复合筛选+预设模板+撤销回滚+操作流水线 |
| V3.5.0 | 2026-07-25 | BGM/音效编辑器+沙盒测试模式+操作历史记录 |
| V3.4.0 | 2026-07-25 | MOD依赖管理+SHP像素编辑器+合并冲突检测 |
| V3.3.0 | 2026-07-25 | 端到端工作流：头像分配+OBD绑定+物品图标+MOD安装预览 |
| V3.2.15 | 2026-07-24 | blockcalc注册到_editorTabMap + 清理storeConfig/crafting废弃映射 + 新增event_templates测试(16用例、143→143全通过) |
| V3.2.14 | 2026-07-24 | 修复4个API映射缺失(listMods)、4个编辑器Tab未注册(refcheck/exepatch/pck/pcpreview)、superAtkEditor/scriptEditor补全saveCurrent、调试日志规范化(8处) |
| V3.2.13 | 2026-07-24 | saveCurrent()行为统一(移除3个pushUndo污染+shapeInfo直接保存修复)、customgenEditor dirty标记修复、调试残留清理 |
| V3.2.12 | 2026-07-24 | surnameEditor数据丢失修复(_setField缺失)、shapeInfoEditor补全addNew()、obd/scriptEditor标准化 |
| V3.2.11 | 2026-07-24 | 2个BUG修复(uisubsystem空指针+bmp2raw引用错误)、shapeInfo/map/mpc/sango7编辑器CRUD标准化、blockcalc注册 |
| V3.2.10 | 2026-07-24 | BMP↔RAW双向转换(reverse/batch/preview)、gameText/obd/idini编辑器CRUD标准化、新增3个后端API |
| V3.2.9 | 2026-07-24 | 编辑器CRUD补全：自定义武将+城池商店+个人特性+saveCurrent标准化(10个编辑器) |
| V3.2.8 | 2026-07-24 | 兵种制作板块完善：ObjID模型选择器/OBD跳转/模型预览/技能配置/CSV字段对齐(36字段)/38个测试 |
| V3.2.7 | 2026-07-24 | 物品编辑器特效预览/模板参数校验/发光OBD跳转/批量修改扩展/交叉引用缓存/60个测试用例 |
| V3.2.6 | 2026-07-24 | 地图编辑器统一(cityConnect+cityconnectEditor合并)、编辑器脏标记、死代码清理、effect_catalog测试(52个) |
| V3.2.5 | 2026-07-24 | 特效数据CRUD(弹道/伤害/属性/物品特效/攻击类型/发光)、JSON导出导入、批量修改技能特效 |
| V3.2.4 | 2026-07-24 | Desc自动生成、特效预览、参数校验(20+规则)、智能推荐(12预设)、技能强度评分(0-100) |
| V3.2.3 | 2026-07-24 | 快速创建技能面板、参数可视化、模板加载(applyTemplate) |
| V3.2.2 | 2026-07-24 | 16个特效模板/标签筛选/一键创建技能/特效交叉引用追溯 |
| V3.2.1 | 2026-07-24 | 特效编辑器增强(技能Effect联动/武器发光编辑器/特效知识库JSON化)、CI版本号驱动、安全加固 |
| V3.2 | 2026-07-21 | 主题切换(深色/浅色)、数据仪表盘、SHP批量转换、批量重命名、备份清理、MOD打包校验 |
| V3.1 | 2026-07-21 | Event编辑器升级(双模式)、History面板补全(S_Gen附加字段)、UpgradeTree可编辑 |
| V3.0 | 2026-07-21 | 全局搜索/平衡分析/跨文件批量/MOD合并/Script增强/History删除API |
| V2.9 | 2026-07-20 | 参考数据接入项目：编辑器原版对比面板、Variable子字段注释实时显示 |
| V2.8 | 2026-07-20 | Schema描述22处修正 + 文档数据提取(21个xlsx/长风吹云38Sheet) |
| V2.7 | 2026-07-20 | 三大MOD制作流程完善(新势力/新武将+CG/新物品+图标) |
| V2.6 | 2026-07-20 | OBD 11种新类型 + Variable.ini 全252参数覆盖 |
| V2.5 | 2026-07-20 | SG7Setting说明文档全面应用 |
| V2.4 | 2026-07-19 | AI行为逻辑、兵种动画导入、13个BUG修复 |
| V2.3 | 2026-07-16 | 代码质量全面修复(编码/异常/原子写入/日志) |

详见 [CHANGELOG.md](CHANGELOG.md)

## MOD分发

### PCK 打包工具
San7ModMaker 内置 PCK 打包/解包引擎，无需外部工具：
- **解包**：从 Patch.pck / Shape00-06.pck 提取资源文件
- **打包**：将修改后的 Setting/ 文件夹重新打包为 Patch.pck
- **Shape 打包**：将 Shape/ 目录打包为 Shape00.pck
- 前端 PCK 面板提供一键「重新打包Patch.pck」按钮

### 存档编辑器
完整的存档修改功能，支持：
- **SG7 剧本存档**：武将属性(武力/智力/体力/技力/士气/义理)、装备(武器/坐骑/道具)、兵种、阵型、技能位掩码、经验/熟练度，一键满血/满级
- **CustomGen.sav**：自定义武将名称编辑、克隆、槽位管理
- **十六进制查看器**：原始字节查看和搜索
- 基于社区逆向资料（游侠论坛 sdlt 2006 + 3DM qweytr_1 2025）的结构化解析

### MOD 管理器
多 MOD 隔离管理，支持：
- 增量打包、导入/导出
- 冲突检测与重映射
- 一键打包分发

## 注意事项

- 所有修改操作前会自动备份原文件
- 建议定期清理备份目录以释放空间
- EXE修改前务必确认备份已生成

## 许可

本项目采用 **GPL v3** 开源协议。你可以自由使用、修改和分发，但修改后的版本也必须以 GPL v3 开源。详见 [LICENSE](LICENSE) 文件。