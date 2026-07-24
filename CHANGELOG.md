# Changelog

## [3.2.6] - 2026-07-24

### 项目稳定性增强 — 版本号统一 + 编辑器脏标记 + 测试 + 代码清理 + 地图编辑器统一

- **版本号统一**：main.py 窗口标题 V2.1→V3.2.5，语言包导出元数据 V2.3→V3.2.5，DEVELOPMENT_PROGRESS 同步到 3.2.5
- **createIniEditor 自动脏标记**：renderDetail 中所有字段自动绑定 change/input 事件，任意字段变更立即标记 changed=true，防止静默数据丢失
- **死代码清理**：删除 shapeinfoEditor/shprenameEditor 旧版存根（已有 shapeInfoEditor/shpRenameTool 完整实现）
- **地图编辑器统一**：cityConnect(canvas可视化)与cityconnectEditor(数据编辑)合并为单一cityConnect对象，Canvas下方新增城池列表+详情编辑面板，保存按钮联动脏标记
- **effect_catalog 单元测试**：新增 23 个测试用例，覆盖加载(10)+CRUD(10)+持久化(3)，测试总数 29→52
- **DEVELOPMENT_PROGRESS 已知问题更新**：标注已修复项，新增待处理项

### 修复

- `_selectByNo` 缩进不一致修复
- 地图编辑器cityConnect与cityconnectEditor拆分统一

## [3.2.5] - 2026-07-24

### 特效数据可编辑化 — CRUD + 导出导入 + 批量修改

- **特效数据可编辑**：弹道类型/伤害类型/属性类型/物品特效/攻击类型/发光编号 全部支持增删改
- **编辑弹窗**：点击 ✏ 按钮弹出编辑表单，自动识别字段类型（名称/描述/图标/颜色/示例武器）
- **删除确认**：点击 ✕ 按钮弹出确认对话框，防止误删
- **添加条目**：每个面板底部「+ 添加」按钮，自动分配编号
- **用户自定义模板**：模板卡片新增 ✏/✕ 按钮，支持编辑参数组合和标签
- **特效 JSON 导出/导入**：📥 导出全部知识库为 JSON 文件下载，📤 导入支持合并/替换两种模式
- **批量修改技能特效**：🔄 面板批量修改 BFMagic.ini 中的 Ball/DamageType/Element/Atk 字段，支持预览影响范围后执行
- **原子写入保存**：JSON 文件使用 tempfile + os.replace 原子写入，防止写入中断损坏

### 新增 API

- `effectSaveType` / `effectDeleteType`：特效类型 CRUD
- `effectExportJson` / `effectImportJson`：JSON 导出/导入
- `effectBatchPreview` / `effectBatchModify`：批量修改预览/执行

## [3.2.4] - 2026-07-24

### 技能编辑器深度增强 — Desc 自动生成 + 特效预览 + 参数校验 + 智能推荐

- **Desc 自动生成**：🤖 按钮一键生成中文技能描述，根据 Ball/DamageType/Element/Atk/Range/Target/Damage 自动组合（治疗/辅助/召唤/攻击四类）
- **技能编辑器特效预览**：详情面板底部实时显示弹道图标、伤害/属性色条、范围同心圆、MP/ATK/倍率数据
- **技能强度评分**：基于弹道、伤害类型、攻击类型、范围、倍率、消耗比计算 0-100 分，标注入门/中级/高级
- **特效参数校验**：20+ 条规则，实时警告不合理的参数组合（弹道-伤害不匹配、伤害-属性不一致、攻击-目标冲突等）
- **Ball/DamageType/Atk 字段**：技能编辑器详情面板新增三个下拉选择框，完整覆盖 BFMagic 特效字段
- **智能推荐组合**：12 个预设最优组合卡片，弹道图标+颜色色条+参数摘要，一键填充到快速创建面板

### 修复

- 技能编辑器 `renderDetail`/`saveCurrent` 字段列表补齐 Ball/DamageType/Atk

## [3.2.3] - 2026-07-24

### 现场内特效制作 — 快速创建技能面板

- **快速创建技能面板**：特效编辑器内嵌完整的技能参数配置表单，无需离开页面即可创建技能
- **参数可视化**：实时显示弹道类型图标、伤害/属性颜色色条、目标类型标签、范围同心圆图示
- **模板加载**：点击模板卡片「快速创建」直接加载参数到表单，调整后保存
- **skillEditor.applyTemplate**：新增方法，从模板一键创建技能并自动分配编号
- **导航修复**：`data-tab="skilleditor"` → `data-tab="skills"`，模板跳转技能编辑器不再失效

### 表单字段

12 个可配置参数：技能名称、Ball 弹道类型、DamageType 伤害类型、Element 属性、Atk 攻击类型、MP 消耗技力、ATK 攻击力、Level 学习等级、Range 攻击范围、Target 目标类型、Damage 伤害倍率、Effect 特效编号

## [3.2.2] - 2026-07-24

### 特效模板/预设系统

- **16 个特效模板**：火系、冰系、雷系、风系、毒系、物理、辅助等分类，每个模板包含完整的推荐参数（Ball、DamageType、Element、Atk、MP、ATK、Level、Range、Target、Damage）
- **标签筛选**：按元素类型（🔥火/❄冰/⚡雷/🌀风/☠毒/⚔物理/💊辅助）快速过滤模板
- **一键创建技能**：点击「创建技能」跳转技能编辑器并填入参数，或「复制参数」生成 INI 格式文本到剪贴板
- **模板卡片**：网格布局展示名称、描述、标签、参数摘要、参考技能名

### 特效交叉引用

- **反向追溯**：每个特效编号旁显示引用计数，点击可查看被哪些技能/物品使用
- **引用详情面板**：展开显示完整引用列表，绿色=高频引用，橙色=低频引用
- **武器发光引用**：发光编号表格也支持引用追溯

### 修复

- 武器发光面板中 `_showRefDetail` → `_showRefDetail` 已统一为正确命名

## [3.2.1] - 2026-07-24

### 特效编辑器全面增强

- **技能 Effect 字段联动**：特效编号旁新增 🔍 按钮，打开特效目录查询弹窗，支持分类筛选+关键词搜索，点击即可填入编号
- **武器发光专用编辑器**：新增 38 种发光编号明细表 (BFWResID)，支持颜色预览、搜索过滤、一键复制编号、跳转 OBD/物品编辑器
- **特效知识库 JSON 化**：数据从硬编码迁移到 `data/effect_catalog.json`，`EffectCatalog` 优先 JSON 加载，硬编码回退
- **特效编辑器搜索增强**：工具栏新增全局搜索框，实时过滤当前标签页数据

### 安全加固

- 路径遍历漏洞修复（3 处 `realpath` 校验）
- 边界检查补全（16 个 `select()` 方法）
- 引用重置（9 个 `load()` 方法 `currentIndex`/`current` 重置）
- 未处理 Promise rejection 全局捕获
- 裸 `except Exception` 替换为具体异常类型

### CI 改进

- Release 标签从固定 `latest` 改为版本号驱动（`v3.2.1`），从 `index.html` 自动提取版本号
- 构建时间与提交时间语义对齐，不再混淆

---

## [3.2] - 2026-07-21

### 主题切换 — 深色/浅色双模式

- 新增 `[data-theme="light"]` CSS 变量，完整覆盖浅色主题配色
- 侧边栏主题切换按钮（☀/☾），支持 localStorage 记忆
- 所有编辑器、面板、表格均适配浅色主题

### 数据仪表盘 — 首页实时统计

- 首页新增 16 个实时统计卡片：武将/兵种/物品/技能/必杀技/阵型/官职/势力/城池/历史事件/剧本/年代/Setting文件/素材目录/GenFace文件/备份数量
- 点击「刷新统计」按钮或切换到首页时自动加载
- 后端 `api_dashboard_stats` 遍历所有数据源

### SHP 批量转换 — PNG 目录 → SHP

- 素材预览面板新增 SHP 批量转换区域
- 支持 GenFace (128×128)、ThingIcon (64×64)、genhalf 三种类别
- 自定义 PNG 源目录，自动按文件名数字匹配编号
- 后端 `api_shp_batch_convert` 批量调用 SHP 编码器

### 批量重命名 — 统一前缀+编号

- 批量修改面板新增「批量重命名」标签页
- 支持武将/兵种/物品/技能/必杀技/官职/势力/城池 8 种类型
- 自定义名称前缀和起始编号，自动递增
- 后端 `api_batch_rename` 调用各 INI 管理器

### 自动化增强

- **MOD 打包前自动校验**：`api_pack_mod_one_click` 打包前自动调用 `validateAll`
- **自动备份清理**：备份面板新增「清理旧备份」按钮，默认保留最近 10 个快照
- 后端 `api_cleanup_backups` 调用 `backup_mgr.cleanup_old_backups()`

### 代码清理

- 删除重复的 `pad()` 函数，统一使用 `zeroPad()`（6 处调用迁移）

### 版本号

- `index.html`：V3.1 → V3.2
- `README.md`：V3.1 → V3.2，新增 V3.2 版本历史
- `CHANGELOG.md`：新增 V3.2 条目

---

## [3.1] - 2026-07-21

### Event 编辑器升级 — 从模板生成器到双模式编辑器

- **「直接编辑」模式**：完整的 History.ini 直接编辑功能，支持增删改查+克隆+搜索
- **「模板生成」模式**：保留原有 8 种 ClassType 模板参数化生成
- 详情面板展示全部字段，包括 S_Gen/D_Gen 的 6 个子字段（武将/台词/文本/等级/义理/城池）
- 独立于 History 编辑器的完整 API 调用（`loadHistories`/`saveHistories`/`newHistory`/`deleteHistory`）

### History 详情面板补全

- **S_Gen 武将面板**：新增 StringD(显示文本)、MinGenLv(最低等级)、MinLoyal(最低义理)、City(限定城池) 4 个字段
- **D_Gen 武将面板**：同上，新增 4 个附加字段
- 每个武将面板从 2 个字段扩展到 6 个字段，覆盖 History.ini 完整结构

### UpgradeTree 升级树可编辑化

- **编辑模式**：点击「编辑模式」按钮，每个兵种节点显示下拉框，可修改升级目标
- 下拉框列出所有其他兵种（含编号和名称），支持选择「无」取消升级
- 修改后自动标记 `soldiers.changed = true`，提示保存

### 版本号

- `index.html`：V3.0 → V3.1
- `README.md`：V3.0 → V3.1，新增历史事件功能行、V3.1 版本历史
- `CHANGELOG.md`：新增 V3.1 条目

---

## [3.0] - 2026-07-21

### 新增功能 - 补齐最后的功能缺口

- **全局数据搜索**：跨所有29个INI文件按ID/名称/值搜索，快速定位引用关系，`api_global_search` + 前端搜索面板
- **游戏平衡分析**：武将/兵种/物品属性统计(min/max/avg) + 物品类型分布，一键诊断MOD平衡性，`api_balance_analysis` + 前端分析面板
- **跨文件批量操作**：对多个文件类型(武将/物品/兵种/官职)的同一字段执行统一操作(设为/加上/乘以/不超过/不低于)，`api_batch_cross_file` + 前端批量面板
- **MOD 合并**：将两个独立MOD合并为一个，自动处理文件冲突(按来源重命名)，`api_mod_merge` + 前端合并弹窗
- **Script 编辑器增强**：新增新建文件/删除文件/重命名文件功能，`api_new_script` / `api_delete_script` / `api_rename_script`
- **History 删除 API**：原子删除历史事件条目，`api_delete_history`

### 后端新增
- 9个新 API：`api_new_script`, `api_delete_script`, `api_rename_script`, `api_global_search`, `api_balance_analysis`, `api_mod_merge`, `api_delete_history`, `api_batch_cross_file`, `_apply_batch_op`
- 9个新 dispatch 条目

### 前端新增
- 全局搜索 section：搜索类型选择 + 输入框 + 结果展示(按文件分组)
- 平衡分析 section：武将/兵种/物品属性统计卡片 + 类型分布表
- 跨文件批量面板：目标字段/操作/值/目标文件选择 + 预览/执行
- MOD 合并弹窗：MOD A/B 选择 + 输出名称 + 冲突提示
- Script 编辑器：新建/删除/重命名按钮
- 导航栏：新增「全局搜索」「平衡分析」两个入口

### 修复
- 批量修改面板切换：`classList.add/remove('active')` → `style.display` 切换，修复跨文件批量面板显示问题

---

## [2.9.1] - 2026-07-21

### 文档更新
- **README 已知限制移除**：PCK 打包和存档编辑功能均已完整实现，原"已知限制"章节改为"MOD分发"章节
- **PCK 打包**：`pck_manager.py` 已实现 `repack_patch()` / `repack_shape_pck()`，前端「重新打包Patch.pck」按钮
- **存档编辑器**：`save_parser.py` 完整实现 SG7 剧本存档武将编辑(属性/装备/兵种/阵型/技能/经验)，`save_editor.py` 提供 15 个编辑 API
- **功能模块表**：新增「存档编辑」行，资源管理描述更新为"PCK解包/打包"

---

## [2.9] - 2026-07-20

### 新增功能
- **参考数据接入项目**：提取的文档数据全部接入编辑器，实现实时查询
- **ReferenceData 服务**：加载21个xlsx原版数据表，提供 `lookupThing()` / `lookupGeneral()` / `lookupSoldier()` 查询
- **Variable.ini 子字段注释实时显示**：选中参数时，每个 Int/Float 输入框下方显示原版注释，输入框高亮+tooltip
- **编辑器参考面板**：物品编辑器/武将编辑器自动显示原版属性对比面板
- **长风吹云.xls 接入**：`getChangfengSheet()` 可查询任意38个Sheet

### 修复
- **Sex 下拉框**：修正为 1=男/0=女（与SG7Setting文档一致，之前完全相反）
- **Race 下拉框**：输入框→下拉框，显示汉/匈奴/南蛮/倭国/妖魔枚举值
- **IsRare 下拉框**：加入 0 值（搜索出现）
- **thingTypeRefPanel**：更新 Param1-4 参数说明、IsRare 分级修正

---

## [2.8] - 2026-07-20

### 新增功能
- **variable_full_ref.json**：Variable.ini 141个参数 × 22子字段的独立注释，逐字段提取
- **21个 xlsx 数据表结构化提取**：Thing(853行)/General01(1684行)/Soldier(188行)/CITY(2824行)等
- **changfeng_xls_ref.json**：长风吹云.xls 全部38个Sheet完整提取

### 修复
- **thing_schema.json（7处）**：Param1(系别+坐骑高度+配方书)、Param2(武器特效/弓类射程)、Param3(手握姿势)、Param4(武器特性:吸血/破城/妖灵)、IsRare(0=搜索)、Rate(卖价/出现几率)、ResponseTime(攻击间隔)
- **general_schema.json（15处）**：Sex(1=男/0=女)、Race(0汉1匈奴2南蛮3倭国4妖魔)、Loyal(义理值越大越不易叛变)、Relation(相性差越小越忠诚)、FRelation(土匪/山寨友好度)、Respawn(复活+霸王剧本+第9剧本君主)、stringID_*(5个均标注同步编号)、Weapon/Horse(对应Thing.ini)、Sword/Spear/Bow/Blade/Fan(修正系别映射)、IsFamous(空白=否)、OffsetZ(高度位差)
- **new_entry_template**：Sex 默认值从 0 修正为 1

---

## [2.7] - 2026-07-20

### 新增功能
- **新势力教程**：nation_schema.json 补全13个完整字段，`api_wizard_create_nation` 一键联动 Nation+Color+City+City01-10(10个剧本)+General01(Lord)+TermText
- **新武将+CG教程**：武将编辑表单补全19个缺失字段(Race/BFSoldier2/HorseSkill/SuperSkill/SuperSkillExp/FRelation/Lord/Respawn/ResID/5个stringID/DefaultTitle/IsEvent/ExtraType/EventType/OffsetZ)
- **新物品+图标教程**：ThingIcon 物品图标完整支持(shp_converter + 4个API)、`api_wizard_create_item` 一键联动 Thing+TermText
- **shp_converter**：FACE_DIR 修正 Shape/Face→Shape/GenFace，新增 THING_ICON_SIZE=64/THING_ICON_DIR
- **向导表单**：wizardNationForm + wizardItemForm，MW向导页一键创建
- **物品图标导入/导出**：物品编辑器新增导入PNG/导出PNG按钮，支持 base64 直传

### 修复
- **nation_linkage_create**：扩展为同时更新 City01-10.ini(10个剧本) + General01.ini Lord 字段
- **api_new_thing**：自动创建 TermText 描述(15000+No)
- **api_convert_image_to_thing_icon**：支持 base64 data URL 输入
- **api_export_thing_icon_to_png**：返回 base64 数据供前端下载

---

## [2.6] - 2026-07-20

### 新增功能
- **OBD 11种新类型**：BFSoldierWeapon/BFGenWeapon/BFSkill/BFMagic2-5/BFSkill2-5，累计28种OBD文件类型
- **Variable.ini 全252参数覆盖**：variable_ref.json 从50个扩展到182+参数，涵盖 AI行为/比武大会/蓬莱阁/聚宝洞府/必杀技/红点事件/战斗参数/防御塔/经济内政/等级经验/武将属性/物品装备/特殊事件/剧本年代/军师技/武将技/阵型/士兵/外交/其他杂项

---

## [2.5] - 2026-07-20

### 新增功能
- **SG7Setting说明文档全面应用**：基于解压的225个文档文件，全面对照项目Schema
- **2个新Schema**：cdtable_schema.json(战斗音乐)、postpatch_schema.json(高唐港/朱雀塔坐标)
- **3个参考面板**：thingTypeRefPanel(物品类型/ScriptNo特效/IsRare分级)、TermText编号段、跨文件引用对照表
- **thing_type_ref.json**：物品Type枚举、ScriptNo 16种特效、IsRare 0-6分级
- **termtext_segments.json**：18个TermText编号段映射
- **cross_ref_table.json**：15种跨文件编号引用关系

### 修复
- **buildingpos/citypos schema**：X/Y 字段修正为 PosX/PosY
- **bfmagic schema**：确认 ComboGen/ComboGenAttr1 存在
- **general schema**：确认 IsFamous 字段存在

---

## [2.4] - 2026-07-19

### 新增功能
- **AI行为逻辑面板**：可视化展示AI搜索/出战/撤退/外交参数
- **兵种动画帧导入向导**：SHP精灵帧批量导入，支持动画预览
- **封官模拟器**：官职升级路径模拟，实时预览属性变化

### 修复
- 13个BUG修复（详情见commit记录）

---

## [2.3] - 2026-07-16

### 新增功能
- **Script.so 深度分析**：ELF段表解析、符号表解析、Capstone反汇编引擎、函数识别、交叉引用搜索、指令级补丁
- **语言包管理**：一键切换语言（BIG5/GB/SJIS/KOR）、语言包导出/导入、文本差异对比、缓存刷新
- **自定义武将编辑器**：CustomGen.sav 二进制读写、列表浏览、详情编辑
- **全局导航搜索**：导航栏顶部搜索框，跨模块快速定位功能
- **交互式新手引导**：聚光灯镂空遮罩+高亮标注+浮动卡片，7步引导指向实际UI元素
- **导航分类重构**：75项平铺→6个可折叠分类（核心数据、游戏系统、文本与配置、地图与场景、工具集、高级功能）
- **内存修改器**：20个预设内存地址，一键读写
- **CSV确认导入面板**：预览、确认/取消导入流程
- **MPC地形/Shape位移/SHP改名/城池连线/id.ini** 等编辑器
- **字段描述全覆盖**：history_schema(57项)、var_schema(302项)、idini_schema(新建)

### 修复
- **运行时缺陷**：修复10+处 `return` 关键字缺失导致的静默失败（语言切换、BMP转换、分辨率预设）
- **编码系统**：编码检测优先级从GBK→BIG5改为BIG5→GBK（游戏原生编码），8处硬编码gbk改为big5
- **异常处理**：6个辅助保存API添加try/except保护，6处裸except改为具体异常类型
- **前端一致性**：修复showToast类型错误（warning→success/error）、historyEditor空值检查、5个save()中多余pushUndo删除、3个addNew()统一调用后端
- **日志系统**：15处print()替换为logging模块，4个core模块同步添加
- **原子写入**：IniParser.save()改为tempfile+os.replace原子写入，防止写入中断导致文件损坏
- **依赖锁定**：requirements.txt 中 `>=` 改为 `==` 防止未来不兼容

### 改进
- 版本号从2.2升级到2.3
- 术语通俗化：76个导航项添加中文描述，技术黑话替换为通俗用语
- 所有51个alert()替换为非阻塞showToast()
- 编码方案统一为BIG5优先，确保与原版游戏文件兼容

---

## [2.2] - 2026-07-14

### 新增功能
- **PCK资源管理**：PCK格式解析、文件列表、按需提取、Setting目录自动准备
- **OBD模型编辑器**：支持BFSoldier/BFGen/BFEvent/BFSpec四种OBD文件的解析和编辑
- **兵种相克矩阵**：67×67可视化矩阵编辑器，支持批量设置和分析
- **存档管理器**：存档列表浏览、备份/还原、基础分析
- **MOD制作向导**：5套模板（新增武将/势力/兵种/物品/完整MOD），步骤引导+checklist
- **城池商店编辑器**：CitySellItem.ini 编辑，各城池10个物品槽位
- **游戏文本编辑器**：GameText.ini 分类编辑，支持全文搜索
- **物品强化编辑器**：ItemEnhance.ini 合成配方编辑
- **全局参数编辑器**：Variable.ini 全字段编辑和搜索
- **引用完整性检查**：跨文件引用检查（武将→兵种/物品/特性/出生地/势力/城池）
- **Schema体系**：新增8个Schema文件（SFMagic/ArmySkill/ArmyGroupSkill/Age/General02/ItemEnhance/Scenario/Variable），累计20个

### 修复
- **SHP转换器**：完全重写，支持正确的8字节头部格式和3种格式变体检测
- **INI解析器**：保存时保留注释和原始行格式，添加Big5编码自动检测
- **TermText**：修复键格式，添加release_by_name方法
- **字段映射**：新增Schema→游戏字段名映射层，支持双向转换
- **备份系统**：备份目录移至项目工作区，添加级联删除支持
- **数据校验器**：从3类规则扩展到9类，新增5种跨文件一致性检查
- **前端**：修复19处const重复赋值Bug、补齐5个标签的自动加载、统一API调用方式

### 改进
- 版本号从2.1升级到2.2
- API从约60个扩展到89个
- JsApi桥接从约150个扩展到227个
- 核心模块从6个扩展到11个
- 编辑器页面从约20个扩展到32个
- Schema文件从12个扩展到20个

---

## [2.1] - 2026-07-12

### 初始版本
- PyWebView桌面框架、前后端双向通信
- INI解析器（GBK编码）、TermText文本管理
- 武将/兵种/物品/技能/阵型/官职/剧本/势力/城池/等级/年代/出生地编辑器
- 备份还原系统、EXE补丁工具
- 批量修改/搜索替换、差异对比
- MOD隔离管理、增量打包/导入
- 基础数据校验器（3类规则）