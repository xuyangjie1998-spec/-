# Changelog

## [3.13.1] - 2026-07-28

### 代码质量全面提升 — XSS 安全修复 + 代码现代化 + 样式系统化 + 自动验证

**P1 安全修复 (15+ 处)**

- **XSS 漏洞修复**: panels-4.js `_showResult()` 所有调用方添加 `escHtml()` 转义，覆盖 MOD 名称、文件路径、README 内容、冲突文件、汇编代码、机器码
- panels-3.js: 修复 `s.name` 缺失 `escHtml()`（与同文件 L3583 对齐）
- panels-1.js: 修复 `c.string_text`、`_currentCategory`、缩略图 URL 等未转义注入点

**P2 代码现代化 (40+ 处)**

- **function → 箭头函数**: core.js 16 处、panels-1/2/3/4.js 各 3-8 处，共 40 处转换
- **style.cssText → CSS 类**: 5 处内联样式提取为 `.rec-panel-warning`、`.hint-text-danger`、`.hint-text-accent`、`.card-selected`、`.card-hoverable`
- **toInt bug 修复**: `toInt(v,10)` 递归调用修正为 `parseInt(v,10)`

**P3 样式系统化 (32+ 处)**

- 新增 CSS 变量: `--text-on-accent`、`--code-highlight`、`--gold`
- 新增 JS 常量: `C.textOnAccent`、`C.codeHighlight`、`C.gold`
- style.css: 18 处 `color: #fff` → `var(--text-on-accent)`
- JS 文件: 14 处硬编码颜色 → `C.*` 常量
- 删除重复 `.btn-warning` 定义

**Bug 修复**

- 2 处单引号内 `${C.xxx}` 模板插值不生效（panels-3.js:3076, panels-1.js:3528）
- 4 组 CSS 重复选择器合并（`.matrix-table`、`.form-row`、`.panel-card`、`.modal-overlay`）

**自动化验证**

- 新增 `validate.py` — 6 项完整性检查（JS 语法/Python 语法/模块导入/Web 资源/JSON 配置/冒烟测试）
- `build.bat` 编译前自动运行验证，不通过则拒绝编译

## [3.13.0] - 2026-07-26

### 前端面板集成 — 四大可视化操作面板 + 全模块主应用集成

**MOD 打包分发面板 (modPackager)**

- **MOD 列表**: 加载/选择/显示 MOD 信息（名称/大小/版本）
- **打包操作**: 一键打包 / 完整打包 / 增量打包 / 安装器生成 / README 生成
- **版本管理**: 创建快照 / 校验包 / 版本号递增 (patch)
- **冲突检测**: 双 MOD 冲突分析，按文件和类型分类显示

**TermText 智能编号分配面板 (termtextAlloc)**

- **段状态网格**: 24 段使用率可视化（颜色编码：绿/黄/红）
- **ID 分配**: 8 种内容类型下拉选择（物品/兵种/武将/技能/必杀/势力/城市/阵型）
- **分配模式**: 单个分配 / 智能分配 / 批量分配
- **冲突管理**: 冲突检测 / 自动修复 / 报告生成

**INI 模板生成器面板 (iniTemplateGen)**

- **预设模板**: 7 个内置预设（new_general / new_soldier / new_item / new_skill / new_nation / new_city / new_superatk）
- **数据生成**: 模板化批量生成，支持自定义数量
- **跨文件生成**: 联合生成关联文件数据
- **一致性验证**: 生成后自动验证跨文件引用完整性

**引擎逆向工具面板 (engineBreakthrough)**

- **Script.so 逆向**: CFG 控制流图构建 / 虚函数表识别 / Code Cave 注入
- **EXE Code Cave**: 空闲区域搜索 / 4 种跳转桩生成 (JMP/CALL/SHORT/PUSH-RET)
- **SG7 存档深度解析**: 存档选择 / 武将-势力-城池数据提取

**前端基础设施**

- 新增导航分类「🚀 引擎突破与MOD工具」，含 4 个导航项
- 懒加载注册：4 个面板切换时自动初始化
- 版本号同步：侧边栏 V3.13.0 / 首页动态版本号 3.13.0
- 全部按钮和表单均绑定到后端 500 个 _API_MAP 接口

## [3.12.0] - 2026-07-25

### 引擎突破 + 完整大型 MOD 支持 — 三大引擎突破 + 三大 MOD 基础设施

**引擎突破 1: Script.so 深层逆向 (scriptso_analyzer.py)**

- **控制流图 (CFG)**: `build_cfg()` 构建函数级控制流图，支持 x86/ARM 双架构，输出基本块/边/函数入口点
- **虚函数表识别**: `find_vtables()` 扫描 .rodata/.data/.data.rel.ro 段，自动识别 C++ 虚函数表指针并猜测类名
- **Code Cave 注入框架**: `inject_code_cave()` 向 Script.so 空闲代码段注入自定义机器码，支持可选 Hook 跳转

**引擎突破 2: SG7-XX.sav 完整格式逆向 (save_editor.py)**

- **深度解析**: `deep_parse_sg7_save()` 启发式扫描场景存档，提取武将(属性/装备/技能/兵种/阵型)、势力(君主/友好度/城池数)、城池(太守/人口/防御/金钱)数据
- **武将字段布局**: 40+ 字段的 `GENERAL_FIELD_LAYOUT` 定义，覆盖 No/Name/Force/WStr/Int/HP/MP/Level/Exp/Title/Skill/Equip/Formation 等
- **存档编辑**: `edit_save_general()` 编辑指定武将属性 / `batch_edit_save_generals()` 批量编辑 / `export_save_to_csv()` 导出为 CSV
- **修复**: `_make_backup()` / `backup_save()` 返回值处理修复

**引擎突破 3: EXE Code Cave 注入 (exe_patcher.py)**

- **Code Cave 搜索**: `find_code_cave()` 在 EXE 代码段中搜索空闲字节区域，按大小排序，返回可用洞穴列表
- **跳转桩生成**: `build_jump_stub()` 生成 4 种跳转指令 — JMP (5字节) / CALL (5字节) / JMP SHORT (2字节) / PUSH+RET (6字节)
- **多补丁原子操作**: `apply_patch_chain()` 原子化应用多个补丁，任一步骤失败则自动回滚
- **补丁分析**: `analyze_patch_impact()` 分析补丁对 EXE 的影响范围
- **Jump Table 检测**: `find_jump_tables()` 检测 EXE 中的跳转表结构

**大型 MOD 1: MOD 打包分发系统 (mod_packager.py)**

- **一键打包**: `pack_one_click()` 自动分析→校验→打包→生成 ZIP
- **完整打包**: `pack_full()` 全量打包 Setting/Shape/Script/EXE + mod_info.json 元数据
- **增量打包**: `pack_incremental()` 对比快照仅打包变更文件
- **安装器生成**: `generate_installer()` 生成 install.py + install.bat + uninstall.bat，支持安装/卸载/回滚
- **冲突检测**: `detect_conflicts()` 检测两个 MOD 文件冲突，按类型分级 / `resolve_conflicts()` 4 种冲突解决策略
- **依赖解析**: `resolve_dependencies()` 解析跨文件 INI 引用依赖，返回缺失/内部/外部依赖
- **版本管理**: `version_bump()` 语义化版本递增 / `validate_package()` 包完整性校验
- **快照系统**: `create_snapshot()` / `compare_snapshots()` 目录快照与差异对比
- **README 生成**: `generate_readme()` 自动生成安装说明和文件清单

**大型 MOD 2: TermText 智能编号分配器 (termtext_allocator.py)**

- **段感知分配**: `allocate_id()` / `smart_allocate()` 根据内容类型自动选择 24 个编号段
- **批量分配**: `allocate_batch()` 批量分配 ID，支持连续块分配
- **冲突检测**: `detect_conflicts()` 全面检测重复 ID/跨段冲突/越界 ID/段内空缺
- **冲突解决**: `resolve_conflicts()` 4 种策略 / `auto_remediate()` 自动修复常见问题
- **跨文件检测**: `cross_file_detect()` 扫描多个 INI 文件的 TermText ID 引用冲突
- **ID 迁移**: `migrate_ids()` 批量迁移旧 ID 到新 ID
- **预留机制**: `reserve_segment()` 为未来扩展预留连续 ID 段
- **分配报告**: `generate_allocation_report()` 完整的状态报告与使用趋势

**大型 MOD 3: INI 模板化数据生成引擎 (ini_template.py)**

- **模板系统**: `create_template()` / `save_template()` / `load_template()` 完整的模板 CRUD 操作
- **12 种表达式**: auto_increment / random / random_float / pick / ref / calc / sequence / uuid / counter / if / pad / concat
- **批量生成**: `generate_from_template()` 模板批量生成 / `generate_cross_file()` 跨文件联合生成，支持 one_to_one/one_to_many/many_to_one 关系
- **跨文件验证**: `validate_cross_file()` 8 项检查 / `check_references()` 引用完整性 / `consistency_report()` 结构化报告
- **模板合并**: `merge_templates()` 多模板合并 / `apply_overrides()` 点号路径深层覆盖
- **数据转换**: `transform_data()` 6 种转换 — type_cast / value_map / condition / rename / remove / format
- **7 个预设模板**: new_general / new_soldier / new_item / new_skill / new_nation / new_city / new_superatk

**测试覆盖**

- 新增 191 个测试用例: mod_packager (46) / termtext_allocator (57) / ini_template (88)
- 测试用例总数: 566 → 757 (+191)
- 核心模块测试覆盖: 24/24 (100%)
- 修复 test_save_editor 中 `_make_backup()` 返回 None 导致的测试失败

## [3.11.0] - 2026-07-25

### 深度开发 — Script.so 运行时修改框架 + PCK 增量打包 + SHP 批量处理流水线

**Script.so 运行时行为修改框架 (scriptso_analyzer.py)**

- **Hook 模板系统**: 5 种 Hook 类型 — jmp_redirect (无条件跳转重定向) / call_redirect (调用重定向) / nop_patch (NOP 填充禁用) / push_ret (栈上构造返回地址) / int3_break (INT3 断点注入)
- **补丁预设包**: 6 个预设 — double_exp (双倍经验) / triple_drop (三倍掉落) / instant_battle (快速战斗) / no_enemy_skill (无敌人技能) / fast_loading (快速加载) / god_mode (无敌模式)
- **方法**: `generate_hook_template()` 生成 Hook 机器码 / `find_jump_tables()` 检测跳转表 / `verify_patch_offsets()` 验证补丁偏移 / `get_patch_presets()` 获取补丁预设 / `apply_patch_preset()` 应用补丁预设 / `get_hook_templates()` 获取 Hook 模板列表

**PCK 增量打包系统 (pck_manager.py)**

- **差异对比**: `diff_setting_vs_pck()` 对比 Setting/ 文件夹与原始 Patch.pck，输出新增/修改/删除/未变化文件统计
- **增量打包**: `pack_incremental()` 仅打包变更文件生成更小的 Patch_incremental.pck，便于 MOD 分发
- **MOD 合并**: `merge_mod_pcks()` 合并多个 MOD 的 PCK 文件，后者覆盖前者
- **跨 MOD 对比**: `get_pck_diff_detail()` 对比两个 PCK 文件的详细差异，含重叠率统计
- **get_info()**: 静态方法返回 PCK 格式元信息

**SHP 批量处理流水线 (shp_converter.py)**

- **目录分析**: `analyze_shp_directory()` 分析目录中所有 SHP 文件的尺寸分布和格式信息
- **尺寸标准化**: `batch_standardize_size()` 等比缩放 + 居中裁剪批量统一到目标尺寸
- **调色板重映射**: `remap_palette()` 单个 SHP 调色板重映射 / `batch_remap_palette()` 批量统一调色板
- **序列帧导入**: `import_sequence_frames()` 从序列帧图片目录批量导入为编号 SHP，支持文件模式过滤
- **批量缩放**: `batch_resize_shp()` 直接拉伸缩放（不保持比例）

**测试覆盖**

- SHP 批量处理流水线测试: 24 个新测试用例 (analyze_shp_directory 5 / batch_standardize_size 3 / remap_palette 4 / batch_remap_palette 3 / import_sequence_frames 5 / batch_resize_shp 4)
- PCK: 修复 `get_info()` 静态方法缺失导致的测试失败

**基础设施**

- 测试用例总数: 542 → 566 (+24)
- 核心模块测试覆盖: 21/21 (100%)

## [3.10.0] - 2026-07-25

### 存档管理 + 自建武将测试覆盖 — 核心模块测试 100% 深度覆盖

**存档管理模块测试覆盖 (新增 47 个测试用例)**

- **save_manager 测试套件**: 47 个测试用例，覆盖初始化(无路径/带路径)/set_game_path/find_save_dir(存在/缺失/无路径)/list_saves(空/游戏存档/CustomGen/混合/忽略非存档/无存档目录/slot解析/无效slot/修改时间戳)/backup_save(成功/自动创建目录/文件不存在/无存档目录/时间戳)/restore_save(成功/无存档目录/备份不存在/自动备份当前)/list_backups(空/有备份/无存档目录)/delete_backup(成功/不存在)/hex_view(成功/偏移量/超出/截断/无目录/文件不存在/格式)/analyze_save_header(成功/GZip/ZIP/全零/未知/可读文本/无目录/文件不存在/文件大小/magic十六进制)/SAVE_PATHS 常量

**自建武将模块测试覆盖 + save/load 格式一致性修复 (新增 28 个测试用例)**

- **custom_leader 测试套件**: 28 个测试用例，覆盖 CustomLeader 数据对象初始化与属性设置；CustomLeaderParser 初始化(无路径/带路径)/set_game_path/exists(存在/不存在/无路径)/load(无文件/空文件/单武将/多武将/索引顺序/ASCII名称/截断数据/total_size)/save(无路径/单武将/多武将/回环一致性/自动创建目录/覆盖已有/默认值/长名截断/空名)/RECORD_SIZE 常量/无效字节名/纯二进制数据
- **BUG 修复**: `custom_leader.py` 的 `save()` 方法曾使用 `while len(result) % 64 != 0` 全局填充，导致多武将记录的 save/load 回环不一致（第二条记录起被错误解析）。修复为按记录单独填充 `name_padded + 64` 字节，与 `load()` 的 `pos = value_start + 64` 跳转逻辑保持一致

**基础设施**

- 测试用例总数: 467 → 542 (+75)
- 核心模块测试覆盖: 21/21 (100%)，全部 21 个模块现在均有深度专属测试套件
- save_manager 和 custom_leader 从 `仅导入` 提升至 `已覆盖`

## [3.9.0] - 2026-07-25

### 核心模块测试全覆盖 — 深度测试 + 报告修正

**核心模块深度测试覆盖 (新增 106 个测试用例)**

- **scriptso_analyzer 测试套件**: 40 个测试用例，覆盖初始化/路径管理/ELF头解析(32bit/64bit/损坏)/段表解析(32bit/64bit/错误路径)/符号表解析/反汇编(兼容Capstone未安装)/架构检测/字符串提取/十六进制查看/十六进制搜索/已知模式匹配/脚本文件列表/常量
- **validator 测试套件**: 35 个测试用例，覆盖 ValidationResult 创建与序列化/编号重复/编号缺失/数值范围(正常/溢出/非数值)/跨文件引用(兵种/武器/坐骑)/技能引用(缺失/孤立)/出生地引用/物品完整性(武器ATK/空名称)/兵种相克矩阵/兵种上限/TermText控制字符/势力城池一致性/全面校验/汇总统计
- **csv_manager 测试套件**: 31 个测试用例，覆盖编码检测(UTF-8-BOM/UTF-8/GBK/Big5/回退)/CSV导出(空数据/有数据/无效类型/字符串)/CSV预览(空/有效/无效类型)/CSV导入(有效/空/重复ID/缺失No/非数值/无效类型)/字段映射(精确匹配/别名/ID→No/中文名称)/数值字段集合

**完成度报告修正**

- 修正 4 个模块测试覆盖 badge 错误：exe_patcher、save_parser、mod_wizard、obd_parser 从 `gap - 无` 更正为 `ok - 已覆盖`（这些模块在 V3.7.0 已添加测试，但报告未同步更新）
- 测试覆盖统计更新：从 "18/21 (86%)" 更正为 "21/21 (100%)"

**基础设施**

- 测试用例总数: 361 → 467 (+106)
- 核心模块测试覆盖: 21/21 (100%)，其中 15 个有深度专属测试
- 模块测试覆盖分布更新：scriptso_analyzer 从 `仅导入` 提升至 `已覆盖`，validator 和 csv_manager 从基础覆盖提升至 `已覆盖`

## [3.8.0] - 2026-07-25

### 素材资源管理增强 + 差异对比增强 + MOD打包增强 + 核心模块测试全覆盖

**素材资源管理增强**

- **全局素材搜索**: 新增 `api_resource_search` API，支持按关键词/分类(shape/audio)/文件类型/排序方式(name/size/date)搜索 Shape 和 Music 目录下的所有资源，返回文件路径、大小、修改时间等详细信息
- **批量导入素材**: 新增 `api_resource_batch_import` API，支持从外部目录批量导入图片/音频资源到游戏目录，支持 SHP→PNG 自动转换、自动重命名（keep/sequential/prefix_date）、冲突处理
- **素材分类管理**: 新增 `api_resource_categorize` API，支持按自定义分类对素材进行分组管理，提供 list/add/remove/reassign 操作

**差异对比增强**

- **跨MOD对比**: 新增 `api_diff_cross_mod` API，对比两个已打包MOD之间的文件差异，列出仅在A/B中存在的文件、共同文件的差异，计算重叠率
- **差异摘要报告**: 新增 `api_diff_summary` API，生成文件的差异摘要，包含新增/修改/删除条目统计、变更详情

**MOD打包增强**

- **完整打包**: 新增 `api_pack_mod_full` API，一键打包MOD的全部内容（Setting/Shape/Script/EXE），自动压缩为ZIP，包含详细统计信息
- **分发包生成**: 新增 `api_pack_mod_distribution` API，生成完整MOD分发包（含README安装说明、screenshots目录、版本/作者/描述元数据）
- **打包预设**: 新增 `api_pack_mod_preset` API，支持保存/加载/列表/删除打包预设配置，快速复用打包参数

**核心模块测试覆盖 (新增 109 个测试用例)**

- **pck_manager 测试套件**: 52 个测试用例，覆盖初始化/路径设置/游戏状态检测(empty/ready/partial/need_extract)/PCK文件列表/PCK头解析(合法/无效/空/缓存)/文件提取(单文件/批量)/Setting管理/Setting状态/工具集成/PCK打包/Patch.pck重打包/Shape PCK提取与重打包/常量和静态方法
- **shp_converter 测试套件**: 27 个测试用例，覆盖初始化/格式检测(8字节头/4字节头/无头/小数据)/SHP解码(无头/带头)/文件存在判断/按ID加载/调色板/列表/统计/日志/批量操作(删除/导出)/BFObj管理/常量(含PIL环境自动跳过)
- **save_editor 测试套件**: 30 个测试用例，覆盖初始化/常量/list_saves(空/多文件/类型识别)/load_save(CustomGen/场景存档)/hex_view/hex_search/parse_customgen/add_customgen(新建/追加)/clone/存档操作(save/backup/restore)/内部方法(_find_all/_find_next_nwj/_parse_customgen_v2)

**基础设施**

- `_API_MAP`: 注册 8 个新 API 映射 (resourceSearch/resourceBatchImport/resourceCategorize/diffCrossMod/diffSummary/packModFull/packModDistribution/packModPreset)
- 测试用例总数: 252 → 361 (+109)
- 核心模块测试覆盖: 21个模块中 18个已有测试覆盖 (86%)

## [3.7.0] - 2026-07-25

### MOD 安装回滚与重装 + 打包校验 + 核心模块测试覆盖

**P0 MOD 管理增强**

- **MOD 安装回滚**: 新增 `api_mod_rollback` API，基于安装时记录的备份文件精确还原 MOD 安装时替换的所有文件，保留安装记录不删除（与卸载区分），支持回退到 backup_mgr 最新备份，记录回滚次数和时间戳
- **MOD 重新安装**: 新增 `api_mod_reinstall` API，组合回滚+安装两步操作，适用于 MOD 包更新后的一键重装，返回回滚和安装的详细结果
- **MOD 打包校验**: 新增 `api_mod_validate_pack` API，检查 MOD 包完整性：必要文件 (mod_info.json/pack_meta.json)、目录结构、文件统计（Setting/Shape 分别计数）、大文件检测 (>50MB 警告)、元数据字段验证

**P0 核心模块测试覆盖 (新增 109 个测试用例)**

- **exe_patcher 测试套件**: 28 个测试用例，覆盖初始化/路径设置/EXE 存在性检查/大小获取/读写 int32/int16/int8/原始字节/写后读验证/不存在 EXE 的读写保护/补丁定义完整性/一键突破补丁偏移量/社区补丁/补丁应用/超出范围保护/特征码扫描规则/空文件/缓存重载/无路径初始化
- **save_parser 测试套件**: 21 个测试用例，覆盖初始化/从字节加载/从文件加载/不存在的文件/按属性精确搜索武将/扫描模式搜索/空数据/无匹配/基本属性解析/偏移量/无效范围过滤/截断数据/大数据量/兵种/武器/坐骑/道具/阵型/功勋系数/装备标记等常量表完整性
- **mod_wizard 测试套件**: 26 个测试用例，覆盖初始化/模板获取/模板结构/启动模板/未知模板/步骤标记/全部完成/超出范围/未开始模板/进度查询/默认进度/无活动进度/依赖检查（武将/兵种/物品/势力/未知）/示例数据（武将/兵种/骑兵/弓兵）/检查清单/步骤顺序/必要步骤/多模板切换
- **obd_parser 测试套件**: 34 个测试用例，覆盖 OBDObject 初始化/ObjID 提取/Sprite 获取设置/序列化反序列化/Sprite 类型常量；OBDParser 初始化/路径设置/文件注册表/解析（简单/多对象/Directory/空文件/不存在/未知类型/注释）/保存重载一致性/按 Sequence 查询/按 ObjID 查询/不存在的 ObjID/Sprite 类型汇总/所有 Sequence/空闲 Sequence 查找/按 Sequence 查找/字典列表导出/获取信息/额外参数/异常行容错

**基础设施**

- `_API_MAP`: 注册 3 个新 API 映射 (modRollback/modReinstall/modValidatePack)
- 测试用例总数: 143 → 252 (+109)

## [3.6.0] - 2026-07-25

### 批量自动化增强 — 复合筛选 + 预设模板 + 撤销回滚 + 操作流水线

**P1 批量/自动化维度提升 (75% → 90%)**

- **复合筛选条件**: 新增 `_match_filters()` 辅助方法，支持 8 种运算符 (eq/ne/gt/lt/gte/lte/contains/in)、AND/OR 逻辑组合；新增 `api_batch_preview_adv` / `api_batch_execute_adv` API，执行前自动备份；前端新增多条件筛选 UI（动态添加/删除筛选行、AND/OR 模式切换）
- **批量操作预设/模板**: 新增 `api_batch_preset_save` / `api_batch_preset_load` / `api_batch_preset_list` / `api_batch_preset_delete` API，预设存储为 JSON 文件；前端预设管理栏（下拉选择 + 一键应用/保存/删除），自动填充表单和筛选条件
- **批量修改撤销/回滚**: 新增 `api_batch_undo` API，通过 `backup_mgr.restore_all()` 恢复所有已备份文件；前端预设栏新增「撤销」按钮，一键恢复最近一次批量修改
- **操作链/流水线**: 新增 `api_batch_pipeline_execute` API，顺序执行多个批量操作步骤；前端新增「操作流水线」标签页，支持动态添加/删除步骤（文件/字段/操作/数值），一键执行全链路并展示结果摘要

**基础设施**

- `_API_MAP`: 注册 8 个新 API 映射（batchPreviewAdv/batchExecuteAdv/batchPresetList/batchPresetSave/batchPresetLoad/batchPresetDelete/batchUndo/batchPipelineExecute）
- 前端 mock API stubs: 新增 8 个
- 前端 CSS: 新增预设栏/筛选行/流水线步骤 3 组样式规则（~70 行）
- 前端 batch 对象: 新增 ~250 行方法（复合筛选/预设管理/撤销/流水线）

## [3.5.0] - 2026-07-25

### BGM/音效编辑器 + 沙盒测试模式 + 操作历史记录

**P2 体验型缺口修复**

- **BGM/音效编辑器**: 新增 `api_browse_audio` / `api_preview_audio` / `api_import_audio` / `api_delete_audio` / `api_rename_audio` API，支持浏览 Music/Sound/Audio 目录、在线预览音频（WAV/MP3/OGG/FLAC）、导入外部音频文件、删除/重命名音频文件；前端双面板布局：左侧文件列表（含格式图标、文件大小、悬停操作按钮）、右侧音频播放器预览
- **沙盒测试模式**: 新增 `api_create_sandbox` / `api_install_to_sandbox` / `api_launch_sandbox` / `api_cleanup_sandbox` / `api_get_sandbox_status` API，支持创建独立测试环境（符号链接 Shape/Music/Sound 目录、复制 Setting/Script/EXE）、将MOD安装到沙盒、从沙盒启动游戏、清理沙盒；前端状态卡片面板：显示创建时间、文件数、大小、已安装MOD列表，一键启动/安装/清理
- **操作历史记录**: 新增 `api_get_operation_history` / `api_clear_operation_history` API，支持自动记录操作日志（时间戳/操作类型/目标/详情）、按操作类型筛选、保留最近 500 条记录；前端时间线列表面板：按操作类型显示图标（保存/删除/创建/导入/导出/备份/打包/安装/编辑）、支持筛选和清空

**基础设施**

- `_API_MAP`: 注册 13 个新 API 映射（browseAudio/previewAudio/importAudio/deleteAudio/renameAudio/createSandbox/installToSandbox/launchSandbox/cleanupSandbox/getSandboxStatus/getOperationHistory/clearOperationHistory）
- `_editorTabMap`: 新增 3 个面板注册（audioeditor/sandbox/opshistory）
- 前端 mock API stubs: 新增 13 个
- 前端 CSS: 新增音频编辑器/沙盒/操作历史 3 组样式规则（~170 行）

## [3.4.0] - 2026-07-25

### MOD 依赖管理 + SHP 像素编辑器 + 合并冲突检测

**P1 体验型缺口修复**

- **MOD 依赖管理**: 新增 `api_set_mod_dependencies` / `api_get_mod_dependencies` / `api_check_mod_dependencies` API，支持声明 MOD 依赖关系、检查依赖满足状态、版本匹配检测；前端新增依赖管理弹窗（添加/移除依赖、实时状态显示），MOD 卡片显示依赖徽章（绿色=满足，黄色=部分缺失）
- **MOD 合并冲突检测**: 新增 `api_mod_conflict_detect` API，合并前检测两个 MOD 之间的文件冲突；`doMerge()` 增强，合并前弹出冲突预览确认对话框；合并时自动合并依赖信息
- **SHP 像素编辑器**: 新增 `api_shp_pixel_load` / `api_shp_pixel_save` / `api_shp_get_palette` API；`shp_converter` 新增 `get_pixel_data()` / `save_pixel_data()` / `get_palette_rgb()` 方法；前端 Canvas 像素编辑器完整实现：铅笔/橡皮/填充/吸色四种工具、256 色调色板（ACT）、缩放 1x-16x、撤销/重做（最多 50 步）、右键吸色、导出 PNG、自动备份原文件

**基础设施**

- `api_pack_mod_incremental`: 打包时保留 MOD 依赖信息
- `api_install_mod`: 安装前自动检查依赖
- `api_mod_merge`: 合并时自动合并依赖列表
- 前端 mock API stubs: 新增 7 个（setModDependencies / getModDependencies / checkModDependencies / modConflictDetect / shpPixelLoad / shpPixelSave / shpGetPalette）

## [3.3.0] - 2026-07-25

### 端到端工作流打通 — 头像自动分配 + 兵种OBD绑定 + 物品图标关联 + MOD安装预览

**P0 阻断型缺口修复**

- **武将头像自动分配**: 新增 `api_get_next_face_id` / `api_face_browse` API，支持自动扫描 Face 目录获取下一个可用 ID；向导表单新增「自动分配」和「浏览」按钮，头像浏览器弹窗支持可视化选择（含缩略图预览），创建成功后自动回显头像预览
- **兵种→OBD模型绑定修正**: 修复 `createSoldier()` 提示文案（原提示"记得在OBD编辑器中创建兵种模型"与实际不符——后端已自动创建OBD模型并回写ObjID）；新增 `api_get_soldier_obd_info` 用于查询兵种OBD绑定状态
- **物品图标关联**: 新增 `api_get_thing_icon_preview` / `api_get_next_thing_icon_id` API；向导物品表单新增「自动分配」图标ID、「上传图标」按钮（调用 `api_convert_image_to_thing_icon`）、图标预览缩略图

**P1 体验型缺口修复**

- **MOD 安装预览**: 新增 `api_preview_mod_install` API，安装前展示将覆盖/新增的文件列表（含文件大小），用户确认后才执行安装；`mods.installMod()` 前端增加预览确认流程

**基础设施**

- `shp_converter`: 新增 `load_shp_file_base64()` 方法，支持从任意路径读取SHP文件并返回base64预览
- 测试桩: 新增 7 个 API stub（getNextFaceId / faceBrowse / getThingIconPreview / getNextThingIconId / convertImageToThingIcon / previewModInstall / getSoldierObdInfo）

## [3.2.15] - 2026-07-24

### 代码清理 + 测试覆盖 — blockcalc 注册 + 废弃映射移除 + event_templates 测试

- **_editorTabMap 一致性**: `blockcalc` 正式加入 `_editorTabMap` 定义（此前仅在 `initEditorTabMap()` 中动态赋值，编码模式不一致）
- **废弃代码清理**: 移除 `storeConfig`/`crafting` 两个已废弃的映射注释（HTML 中无对应 tab，保留死代码无意义）
- **测试覆盖**: 新增 `tests/test_event_templates.py`（16 个用例），覆盖 `EVENT_TEMPLATES` 8 种模板结构验证 + `generate_event_section()` 函数（默认值/自定义值/未知类型/全类型生成），测试总数从 127 → 143

## [3.2.14] - 2026-07-24

### API 映射修复 + 编辑器 Tab 注册 + saveCurrent 补全 + 调试日志规范化

- **API 映射修复**: `pyApi('listMods')` → `api_get_mod_list` 添加映射条目（`_JsApi._API_MAP` 中缺失导致 mods 合并功能运行时静默失败）
- **编辑器 Tab 注册**: 补全 `_editorTabMap` 中 4 个缺失条目：
  - `refcheck` → `refChecker`（引用完整性检查工具）
  - `exepatch` → `{ changed: false }`（EXE引擎突破，无独立编辑器对象）
  - `pck` → `pckEditor`（PCK资源管理）
  - `pcpreview` → `pckPreview`（PCK资源浏览器）
- **saveCurrent() 补全**: `superAtkEditor` 和 `scriptEditor` 新增 `saveCurrent()` 方法，与其他编辑器行为统一
- **调试日志规范化**: 4 处正常条件静默跳过（移除 `console.warn`），4 处异常条件升级为 `console.error`（Variable ref/ReferenceData/generals 加载失败）

## [3.2.13] - 2026-07-24

### saveCurrent() 行为统一 — 撤销栈污染修复 + 调试残留清理

- **citySellEditor/gameTextEditor/obdEditor**: saveCurrent() 移除不必要的 `pushUndo()`（撤销快照应在 save() 中创建），防止每次切换条目时污染撤销栈
- **shapeInfoEditor.saveCurrent()**: 改为仅标记 dirty + toast，不再直接调用 `saveOne()`（与其他编辑器行为统一）
- **customgenEditor.saveCurrent()**: 移除无效的 `_dirty` 空对象赋值，改为正确的 `this.changed = true` 标记
- **调试残留清理**: 移除 `app.js` 中 `console.warn('PyWebView API不可用...')` 调试日志

## [3.2.12] - 2026-07-24

### BUG 修复: surnameEditor 数据丢失 + 编辑器标准化

- **surnameEditor 数据丢失修复**: 新增 `_setField()` 方法（HTML 中 `onchange` 已绑定但方法缺失），修复 `saveCurrent()` 和 `saveDetail()` 从 DOM 回读数据逻辑，防止切换选中条目时修改静默丢失
- **shapeInfoEditor 补全 addNew()**: 新增 `addNew()` 方法 + 后端 `api_shape_info_new` API，支持创建新 .info.ini 文件
- **obdEditor 标准化**: HTML 中 `newObj()` → `addNew()`，统一方法名
- **scriptEditor 标准化**: 新增 `addNew()`/`deleteCurrent()` 标准包装方法（调用 `newFile()`/`deleteFile()`）

## [3.2.11] - 2026-07-24

### BUG 修复 + 编辑器 CRUD 补全 — shapeInfo/map/mpc/sango7 标准化

- **BUG 修复**: `uisubsystemEditor.renderDetail` 缺少 `return` 导致空指针崩溃（`;` → `return;`）
- **BUG 修复**: `_editorTabMap['bmp2raw']` 引用已删除的 `bmp2rawEditor` 对象，改为 `bmp2rawTool`
- **Shape位移编辑器 (shapeInfoEditor)**: 补全 `saveCurrent()`/`deleteCurrent()`/`cloneCurrent()`，新增 `_selectedIdx` 行选中高亮
- **地图编辑器 (mapEditor)**: 补全 `saveCurrent()`/`addNew()` 新建城池/`deleteCurrent()` 删除城池，更新 HTML 按钮
- **MPC地形编辑器 (mpcEditor)**: 补全 `saveCurrent()` 标记修改
- **Sango7配置编辑器 (sango7Editor)**: 补全 `saveCurrent()` 标记修改
- **blockcalc**: 注册到 `_editorTabMap`，修复 tab 切换 dirty-check 缺口
- **后端新增 API**: `api_shape_info_delete`（删除 .info.ini 文件）、`api_shape_info_clone`（克隆 .info.ini 文件）

## [3.2.10] - 2026-07-24

### 编辑器 CRUD 补全 — BMP↔RAW 双向转换 + gameText/obd/idini 标准化

- **BMP↔RAW 双向转换器增强**：删除重复的 `bmp2rawEditor` 死代码，统一为增强版 `bmp2rawTool`，新增 `reverse()` RAW→BMP 反向转换、`batchConvert()` 批量目录转换、`preview()` BMP 图片预览
- **游戏文本编辑器 (gameText)**：补全 `addNew()` 新建分类、`deleteCurrent()` 删除入口，更新 HTML 面板按钮
- **OBD 模型编辑器 (obdEditor)**：补全标准化 `addNew()`/`deleteCurrent()` 方法，包装现有 `newObj()`/`deleteObj()` 逻辑
- **id.ini 编辑器 (idiniEditor)**：补全标准化 `addNew()` 方法（包装 `newEntry()`），`deleteCurrent()` 新增 `_selectedIdx` 行选中跟踪，修复未定义引用问题
- **后端新增 API**：`api_raw2bmp`（RAW→BMP 反向转换）、`api_bmp2raw_batch`（批量目录转换）、`api_bmp_preview`（BMP base64 预览）

### 修复

- 删除重复的 `bmp2rawEditor` 死代码（HTML 从未引用，与 `bmp2rawTool` 功能重复）
- `idiniEditor.deleteCurrent()` 引用未定义的 `this._selectedIdx` 导致运行时错误

## [3.2.9] - 2026-07-24

### 编辑器 CRUD 补全 — 自定义武将 + 城池商店 + 个人特性 + saveCurrent 标准化

- **自定义武将编辑器 (CustomGen)**：补全 CRUD 操作，新增 `addNew` 新建武将（克隆首个现有武将为模板），添加 `parse_customgen`/`get_customgen_detail`/`edit_customgen_field`/`add_customgen` 四个后端方法
- **个人特性编辑器 (genSkills)**：确认 CRUD 完整（已有 `addNew`/`deleteCurrent`/`cloneCurrent`/`saveCurrent`/`save`），支持 GenSkill/ArmySkill/ArmyGroupSkill 三类特性
- **城池商店编辑器 (citySell)**：确认 CRUD 完整（已有 `addNew`/`deleteEntry`/`save`），支持多城池多物品位编辑
- **saveCurrent 标准化**：为 `historyEditor`/`defskill`/`ageEditor`/`general02Editor` 四个编辑器补全 `saveCurrent()` 方法，统一保存前确认流程
- **前端 mock API**：补全 `customgenAdd` 测试模式入口

### 修复

- `save_editor.py` 缺失 `parse_customgen`/`get_customgen_detail`/`edit_customgen_field` 三个方法导致前端调用报错

## [3.2.8] - 2026-07-24

### 兵种制作板块完善 — 模型选择器 + 技能配置 + CSV对齐 + 运行时BUG修复

- **ObjID 模型下拉选择器**：兵种编辑器中 ObjID 字段从纯数字输入框改为下拉选择，自动列出 BFSoldier.obd 所有模型（Sequence/名称/动作数），选择后自动同步 ObjID 值
- **OBD 编辑器一键跳转**：ObjID 旁新增 🔧 按钮，点击自动切换到 OBD 编辑器面板，筛选 BFSoldier 类型并高亮对应模型
- **兵种模型预览**：详情面板底部新增模型预览区，点击"加载模型预览"显示 Wait 动作第一帧
- **兵种技能配置**：新增 BFMagic（必杀技）、SFMagic（普通技）、SuperAttack（超级攻击）三个字段，自动显示技能名称提示
- **向导创建兵种加强**：`api_wizard_create_soldier` 使用正确的 Soldier.ini 字段名（Life/BasePower/AddPower），自动联动创建 OBD 模型条目
- **CSV 字段全面对齐**：soldier FIELD_MAPS 从 14 个旧字段扩展为 36 个 Schema 对齐字段，新增 FIELD_ALIASES 别名映射（HP→Life, ATK→BasePower, Level→Rank 等），向后兼容旧 CSV
- **新增 API**：`api_list_obd_models` 列出 OBD 模型简要信息
- **测试覆盖**：新增 36→38 个 soldier 测试用例，含 CSV 字段对齐和别名验证

### 修复

- **运行时 BUG**：兵种列表卡片始终显示 HP/ATK/DEF 为 `-`（字段名错误，已修复为 Life/BasePower/AddPower）
- **升级树 BUG**：相同字段名错误导致升级树节点显示 `-`
- **soldier_matrix get_summary**：返回结构新增 `analysis` 嵌套键（strong_count/weak_count/neutral_count）

## [3.2.7] - 2026-07-24

### 物品编辑器特效增强 — 武器特效预览 + 模板参数校验 + 发光OBD跳转

- **物品编辑器特效预览面板**：在武器专属选项卡中新增可视化预览面板，实时显示 ScriptNo 物品特效（图标+名称+描述+示例武器+发动概率）和 BFWResID 武器发光（颜色圆球+名称+描述+示例武器）
- **模板编辑参数校验**：保存模板时自动校验参数组合合理性（弹道-伤害类型兼容性、伤害类型-属性一致性、攻击类型-目标一致性、弹道-攻击类型一致性、范围合理性），不合理的组合弹出警告对话框
- **发光编号 OBD 跳转**：在物品编辑器武器专属选项卡中，BFWResID 字段旁新增 🎯 OBD 按钮，点击自动跳转到 OBD 编辑器并筛选 BFWeapon 类型+搜索对应编号
- **批量修改扩展**：effectBatchModify API 新增 `file` 参数支持（bfmagic/thing），可批量修改 Thing.ini 中的 ScriptNo/BFWResID 字段
- **交叉引用缓存**：effect_catalog 新增 `_cross_ref_cache` 持久化缓存，避免重复扫描，支持强制刷新
- **版本号统一至 V3.2.7**

### 修复

- 物品编辑器武器选项卡只在 Type=2(武器) 时显示
- OBD 编辑器导航兼容性修复

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