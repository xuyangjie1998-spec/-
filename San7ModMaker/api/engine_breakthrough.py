"""
引擎突破模块 API Mixin
包含 V3.12.0 ~ V3.18.0 新增的引擎逆向/注入/分析相关 API 方法
从 main.py 拆分出来以减小主文件体积
"""

import base64
import json


# ============================================================
# 引擎突破模块 API 映射表（camelCase → snake_case）
# ============================================================
ENGINE_BREAKTHROUGH_API_MAP = {
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
    # V3.13.0: 引擎突破 — PE 结构解析器
    'parsePeDosHeader': 'api_parse_pe_dos_header',
    'parsePeNtHeaders': 'api_parse_pe_nt_headers',
    'parsePeImportTable': 'api_parse_pe_import_table',
    'parsePeExportTable': 'api_parse_pe_export_table',
    'parsePeRelocations': 'api_parse_pe_relocations',
    'buildIatHook': 'api_build_iat_hook',
    'getPeFullAnalysis': 'api_get_pe_full_analysis',
    # V3.13.0: 引擎突破 — Script.so PLT/GOT 深度分析
    'parseScriptsoDynamic': 'api_parse_scriptso_dynamic',
    'parseScriptsoPlt': 'api_parse_scriptso_plt',
    'parseScriptsoGot': 'api_parse_scriptso_got',
    'getScriptsoImportedFunctions': 'api_get_scriptso_imported_functions',
    'buildGotOverwrite': 'api_build_got_overwrite',
    'listHookableFunctions': 'api_list_hookable_functions',
    # V3.13.0: 引擎突破 — 内存扫描引擎
    'memoryAttachProcess': 'api_memory_attach_process',
    'memoryDetach': 'api_memory_detach',
    'memoryScanExact': 'api_memory_scan_exact',
    'memoryScanPattern': 'api_memory_scan_pattern',
    'memoryNewScan': 'api_memory_new_scan',
    'memoryNextScan': 'api_memory_next_scan',
    'memoryRead': 'api_memory_read',
    'memoryWrite': 'api_memory_write',
    'memoryFindCodeCave': 'api_memory_find_code_cave',
    'memoryInjectCode': 'api_memory_inject_code',
    'memoryInstallHook': 'api_memory_install_hook',
    'memoryRemoveHook': 'api_memory_remove_hook',
    'memoryTakeSnapshot': 'api_memory_take_snapshot',
    'memoryCompareSnapshots': 'api_memory_compare_snapshots',

    # V3.14.0: 引擎突破 — 汇编级代码分析器
    'asmLoadFile': 'api_asm_load_file',
    'asmLoadBytes': 'api_asm_load_bytes',
    'asmDisassemble': 'api_asm_disassemble',
    'asmFindPattern': 'api_asm_find_pattern',
    'asmDetectFunctions': 'api_asm_detect_functions',
    'asmBuildCfg': 'api_asm_build_cfg',
    'asmAnalyzeStackFrame': 'api_asm_analyze_stack_frame',
    'asmGenerateHook': 'api_asm_generate_hook',
    'asmGetStatistics': 'api_asm_get_statistics',
    'asmGetFullAnalysis': 'api_asm_get_full_analysis',
    'asmGetCrossReferences': 'api_asm_get_cross_references',

    # V3.14.0: 引擎突破 — 资源格式深度逆向
    'resourceAnalyzeFile': 'api_resource_analyze_file',
    'resourceAnalyzeDirectory': 'api_resource_analyze_directory',
    'resourceDetectFormat': 'api_resource_detect_format',
    'resourceVerifyFile': 'api_resource_verify_file',
    'resourceGetSpec': 'api_resource_get_spec',
    'resourceGenerateTemplate': 'api_resource_generate_template',
    'resourceListFormats': 'api_resource_list_formats',
    'resourceParseShpHeader': 'api_resource_parse_shp_header',
    'resourceParsePckHeader': 'api_resource_parse_pck_header',
    'resourceParseObd': 'api_resource_parse_obd',

    # V3.14.0: 引擎突破 — 游戏进程调试器
    'debuggerAttach': 'api_debugger_attach',
    'debuggerDetach': 'api_debugger_detach',
    'debuggerGetState': 'api_debugger_get_state',
    'debuggerGetProcessInfo': 'api_debugger_get_process_info',
    'debuggerSetBreakpoint': 'api_debugger_set_breakpoint',
    'debuggerRemoveBreakpoint': 'api_debugger_remove_breakpoint',
    'debuggerListBreakpoints': 'api_debugger_list_breakpoints',
    'debuggerGetRegisters': 'api_debugger_get_registers',
    'debuggerReadMemory': 'api_debugger_read_memory',
    'debuggerWriteMemory': 'api_debugger_write_memory',
    'debuggerReadInt32': 'api_debugger_read_int32',
    'debuggerReadFloat': 'api_debugger_read_float',
    'debuggerStepInto': 'api_debugger_step_into',
    'debuggerStepOver': 'api_debugger_step_over',
    'debuggerContinue': 'api_debugger_continue',
    'debuggerGetCallStack': 'api_debugger_get_call_stack',
    'debuggerGetModules': 'api_debugger_get_modules',
    'debuggerSetWatchpoint': 'api_debugger_set_watchpoint',
    'debuggerGetDisassembly': 'api_debugger_get_disassembly',
    'debuggerGetFullStatus': 'api_debugger_get_full_status',
    # V3.15.0: 引擎突破 — 游戏AI行为分析器
    'aiCreateDecisionTree': 'api_ai_create_decision_tree',
    'aiAddConditionNode': 'api_ai_add_condition_node',
    'aiAddActionNode': 'api_ai_add_action_node',
    'aiExportDecisionTree': 'api_ai_export_decision_tree',
    'aiImportDecisionTree': 'api_ai_import_decision_tree',
    'aiListDecisionTrees': 'api_ai_list_decision_trees',
    'aiMatchBehaviors': 'api_ai_match_behaviors',
    'aiListBehaviorPatterns': 'api_ai_list_behavior_patterns',
    'aiCreateAiProfile': 'api_ai_create_ai_profile',
    'aiGetAiProfile': 'api_ai_get_ai_profile',
    'aiListAiProfiles': 'api_ai_list_ai_profiles',
    'aiCompareAiProfiles': 'api_ai_compare_ai_profiles',
    'aiRankDecisions': 'api_ai_rank_decisions',
    'aiSimulateAi': 'api_ai_simulate_ai',
    'aiBatchSimulateAi': 'api_ai_batch_simulate_ai',
    'aiSaveAiData': 'api_ai_save_ai_data',
    'aiLoadAiData': 'api_ai_load_ai_data',
    'aiListDecisionTypes': 'api_ai_list_decision_types',
    'aiListEventTypes': 'api_ai_list_event_types',
    'aiGetContextAnalysis': 'api_ai_get_context_analysis',
    # V3.15.0: 引擎突破 — 存档加密/解密引擎
    'savecryptoAnalyze': 'api_savecrypto_analyze',
    'savecryptoAnalyzeBytes': 'api_savecrypto_analyze_bytes',
    'savecryptoDecryptXor': 'api_savecrypto_decrypt_xor',
    'savecryptoEncryptXor': 'api_savecrypto_encrypt_xor',
    'savecryptoBruteForceKey': 'api_savecrypto_brute_force_key',
    'savecryptoPatchSave': 'api_savecrypto_patch_save',
    'savecryptoExtractSections': 'api_savecrypto_extract_sections',
    'savecryptoHexDump': 'api_savecrypto_hex_dump',
    'savecryptoCompareSaves': 'api_savecrypto_compare_saves',
    'savecryptoRegisterFormat': 'api_savecrypto_register_format',
    'savecryptoGetInfo': 'api_savecrypto_get_info',
    # V3.15.0: 引擎突破 — 调用追踪与API拦截器
    'tracerEnable': 'api_tracer_enable',
    'tracerDisable': 'api_tracer_disable',
    'tracerIsEnabled': 'api_tracer_is_enabled',
    'tracerTraceCall': 'api_tracer_trace_call',
    'tracerTraceReturn': 'api_tracer_trace_return',
    'tracerAddFilter': 'api_tracer_add_filter',
    'tracerGetEvents': 'api_tracer_get_events',
    'tracerGetStatistics': 'api_tracer_get_statistics',
    'tracerGetCallTree': 'api_tracer_get_call_tree',
    'tracerClear': 'api_tracer_clear',
    'tracerAddHook': 'api_tracer_add_hook',
    'tracerRemoveHook': 'api_tracer_remove_hook',
    'tracerListHooks': 'api_tracer_list_hooks',
    'tracerGetPerformanceSummary': 'api_tracer_get_performance_summary',
    'tracerExportTrace': 'api_tracer_export_trace',
    'tracerGenerateCallGraphDot': 'api_tracer_generate_call_graph_dot',
    'tracerGenerateCallGraphMermaid': 'api_tracer_generate_call_graph_mermaid',
    'tracerGetInfo': 'api_tracer_get_info',
    # V3.16.0: 引擎突破 — 二进制差异化与补丁引擎
    'diffGenerateDelta': 'api_diff_generate_delta',
    'diffApplyDelta': 'api_diff_apply_delta',
    'diffDiffBytes': 'api_diff_diff_bytes',
    'diffScanSignature': 'api_diff_scan_signature',
    'diffGenerateSignature': 'api_diff_generate_signature',
    'diffCreatePatch': 'api_diff_create_patch',
    'diffApplyPatch': 'api_diff_apply_patch',
    'diffGetInfo': 'api_diff_get_info',
    # V3.16.0: 引擎突破 — 脚本虚拟机逆向引擎
    'vmDetectType': 'api_vm_detect_type',
    'vmDetectTypeFile': 'api_vm_detect_type_file',
    'vmDisassemble': 'api_vm_disassemble',
    'vmAnalyze': 'api_vm_analyze',
    'vmBuildCfg': 'api_vm_build_cfg',
    'vmGeneratePseudoCode': 'api_vm_generate_pseudo_code',
    'vmSimulate': 'api_vm_simulate',
    'vmGetInfo': 'api_vm_get_info',
    # V3.16.0: 引擎突破 — 代码注入与DLL劫持引擎
    'injectAnalyzeProcess': 'api_inject_analyze_process',
    'injectEnumerateModules': 'api_inject_enumerate_modules',
    'injectPlanInjection': 'api_inject_plan_injection',
    'injectFindCodeCaves': 'api_inject_find_code_caves',
    'injectGenerateInlineHook': 'api_inject_generate_inline_hook',
    'injectGenerateIatHook': 'api_inject_generate_iat_hook',
    'injectGenerateNopPatch': 'api_inject_generate_nop_patch',
    'injectAnalyzeDll': 'api_inject_analyze_dll',
    'injectFindHijackOpportunities': 'api_inject_find_hijack_opportunities',
    'injectGenerateProxyDll': 'api_inject_generate_proxy_dll',
    'injectAnalyzeSecurity': 'api_inject_analyze_security',
    'injectScanAntiTamper': 'api_inject_scan_anti_tamper',
    'injectComprehensiveAnalysis': 'api_inject_comprehensive_analysis',
    'injectGetInfo': 'api_inject_get_info',
    # V3.18.0: 反调试/反反调试引擎
    'antiDebugAnalyze': 'api_anti_debug_analyze',
    'antiDebugScan': 'api_anti_debug_scan',
    'antiDebugBypass': 'api_anti_debug_bypass',
    'antiDebugIntegrity': 'api_anti_debug_integrity',
    'antiDebugBypassCode': 'api_anti_debug_bypass_code',
    'antiDebugSignatures': 'api_anti_debug_signatures',
    'antiDebugStats': 'api_anti_debug_stats',
    # V3.18.0: 代码混淆分析/去混淆引擎
    'deobfuscatorAnalyze': 'api_deobfuscator_analyze',
    'deobfuscatorScan': 'api_deobfuscator_scan',
    'deobfuscatorStrings': 'api_deobfuscator_strings',
    'deobfuscatorPredicates': 'api_deobfuscator_predicates',
    'deobfuscatorCff': 'api_deobfuscator_cff',
    'deobfuscatorEntropy': 'api_deobfuscator_entropy',
    'deobfuscatorStats': 'api_deobfuscator_stats',
    # V3.18.0: 反编译/反汇编引擎
    'decompile': 'api_decompile',
    'decompileFile': 'api_decompile_file',
    'buildCfg': 'api_build_cfg',
    'symbolicExecute': 'api_symbolic_execute',
    'solveConstraints': 'api_solve_constraints',
    'simplifyExpr': 'api_simplify_expr',
    'decompilerStats': 'api_decompiler_stats',
}


class EngineBreakthroughMixin:
    """引擎突破模块 API Mixin
    包含 V3.12.0 ~ V3.18.0 新增的引擎逆向/注入/分析相关 API 方法
    作为 San7ModMaker 的 Mixin 类使用
    """

    # ============================================================
    # V3.12.0: 引擎突破 — Script.so 深层逆向
    # ============================================================

    def api_build_scriptso_cfg(self, start_address: int = None, max_blocks: int = 500) -> dict:
        """构建 Script.so 控制流图"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.scriptso_analyzer.build_cfg(start_address, max_blocks)

    def api_find_scriptso_vtables(self) -> dict:
        """识别 Script.so 虚函数表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        return self.scriptso_analyzer.find_vtables()

    def api_inject_scriptso_code_cave(self, cave_address: int, machine_code_hex: str, hook_address: int = None) -> dict:
        """向 Script.so Code Cave 注入代码"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            machine_code = bytes.fromhex(machine_code_hex.replace(" ", ""))
        except ValueError:
            return {"success": False, "message": "无效的十六进制机器码"}
        return self.scriptso_analyzer.inject_code_cave(cave_address, machine_code, hook_address)

    # ============================================================
    # V3.12.0: 引擎突破 — SG7-XX.sav 深度格式逆向
    # ============================================================

    def api_deep_parse_sg7_save(self, save_name: str = None) -> dict:
        """深度解析 SG7-XX.sav 场景存档"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.deep_parse_sg7_save(save_name)

    def api_edit_save_general(self, save_name: str, general_index: int, field_updates: dict) -> dict:
        """编辑场景存档中指定武将的属性"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.save_editor.set_game_path(self.game_path)
        return self.save_editor.edit_save_general(save_name, general_index, field_updates)

    # ============================================================
    # V3.12.0: 引擎突破 — EXE Code Cave 注入
    # ============================================================

    def api_find_exe_code_cave(self, min_size: int = 64, section_end: bool = True) -> dict:
        """搜索 EXE Code Cave"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.exe_patcher.set_game_path(self.game_path)
        return self.exe_patcher.find_code_cave(min_size, section_end)

    def api_inject_exe_code_cave(self, cave_offset: int, machine_code_hex: str, hook_offset: int = None, backup: bool = True) -> dict:
        """向 EXE Code Cave 注入代码"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        try:
            machine_code = bytes.fromhex(machine_code_hex.replace(" ", ""))
        except ValueError:
            return {"success": False, "message": "无效的十六进制机器码"}
        self.exe_patcher.set_game_path(self.game_path)
        return self.exe_patcher.inject_code_cave(cave_offset, machine_code, hook_offset, backup)

    def api_build_jump_stub(self, from_offset: int, to_offset: int, stub_type: str = "jmp") -> dict:
        """构建跳转桩代码"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.exe_patcher.set_game_path(self.game_path)
        return self.exe_patcher.build_jump_stub(from_offset, to_offset, stub_type)

    # ============================================================
    # V3.13.0: 引擎突破 — PE 结构解析器
    # ============================================================

    def api_parse_pe_dos_header(self) -> dict:
        """解析 PE DOS Header"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.pe_analyzer.set_exe_path(self.exe_patcher.exe_path)
        return self.pe_analyzer.parse_dos_header()

    def api_parse_pe_nt_headers(self) -> dict:
        """解析 PE NT Headers"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.pe_analyzer.set_exe_path(self.exe_patcher.exe_path)
        return self.pe_analyzer.parse_nt_headers()

    def api_parse_pe_import_table(self) -> dict:
        """解析 PE 导入表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.pe_analyzer.set_exe_path(self.exe_patcher.exe_path)
        return self.pe_analyzer.parse_import_table()

    def api_parse_pe_export_table(self) -> dict:
        """解析 PE 导出表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.pe_analyzer.set_exe_path(self.exe_patcher.exe_path)
        return self.pe_analyzer.parse_export_table()

    def api_parse_pe_relocations(self) -> dict:
        """解析 PE 重定位表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.pe_analyzer.set_exe_path(self.exe_patcher.exe_path)
        return self.pe_analyzer.parse_relocations()

    def api_build_iat_hook(self, dll_name: str, func_name: str, hook_address: int) -> dict:
        """构建 IAT Hook"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.pe_analyzer.set_exe_path(self.exe_patcher.exe_path)
        return self.pe_analyzer.build_iat_hook(dll_name, func_name, hook_address)

    def api_get_pe_full_analysis(self) -> dict:
        """获取 PE 完整分析"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.pe_analyzer.set_exe_path(self.exe_patcher.exe_path)
        return self.pe_analyzer.get_full_analysis()

    # ============================================================
    # V3.13.0: 引擎突破 — Script.so PLT/GOT 深度分析
    # ============================================================

    def api_parse_scriptso_dynamic(self) -> dict:
        """解析 Script.so 动态段"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_dynamic.set_game_path(self.game_path)
        return self.scriptso_dynamic.parse_dynamic_section()

    def api_parse_scriptso_plt(self) -> dict:
        """解析 Script.so PLT"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_dynamic.set_game_path(self.game_path)
        return self.scriptso_dynamic.parse_plt()

    def api_parse_scriptso_got(self) -> dict:
        """解析 Script.so GOT"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_dynamic.set_game_path(self.game_path)
        return self.scriptso_dynamic.parse_got()

    def api_get_scriptso_imported_functions(self) -> dict:
        """获取 Script.so 导入函数列表"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_dynamic.set_game_path(self.game_path)
        return self.scriptso_dynamic.get_imported_functions()

    def api_build_got_overwrite(self, func_name: str, new_address: int) -> dict:
        """构建 GOT 覆写补丁"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_dynamic.set_game_path(self.game_path)
        return self.scriptso_dynamic.build_got_overwrite(func_name, new_address)

    def api_list_hookable_functions(self) -> dict:
        """列出可 Hook 的导入函数"""
        if not self.game_path:
            return {"success": False, "message": "请先设置游戏目录"}
        self.scriptso_dynamic.set_game_path(self.game_path)
        return self.scriptso_dynamic.list_hookable_functions()

    # ============================================================
    # V3.13.0: 引擎突破 — 内存扫描引擎
    # ============================================================

    def api_memory_attach_process(self, process_name: str = "Sango7.exe") -> dict:
        """附加到游戏进程"""
        return self.memory_scanner.attach(process_name)

    def api_memory_detach(self) -> dict:
        """断开进程连接"""
        return self.memory_scanner.detach()

    def api_memory_scan_exact(self, value: int, value_type: str = "int32") -> dict:
        """精确值内存扫描"""
        if not self.memory_scanner.is_attached():
            return {"success": False, "message": "请先附加到游戏进程"}
        return self.memory_scanner.scan_exact_value(value, value_type)

    def api_memory_scan_pattern(self, pattern: str, mask: str = None) -> dict:
        """AOB 模式扫描"""
        if not self.memory_scanner.is_attached():
            return {"success": False, "message": "请先附加到游戏进程"}
        try:
            pattern_bytes = bytes.fromhex(pattern.replace(" ", ""))
        except ValueError:
            return {"success": False, "message": "无效的十六进制模式"}
        return self.memory_scanner.scan_pattern(pattern_bytes, mask)

    def api_memory_new_scan(self) -> dict:
        """开始新一轮模糊扫描"""
        if not self.memory_scanner.is_attached():
            return {"success": False, "message": "请先附加到游戏进程"}
        return self.memory_scanner.new_scan()

    def api_memory_next_scan(self, filter_type: str, **kwargs) -> dict:
        """下一轮模糊扫描过滤"""
        if not self.memory_scanner.is_attached():
            return {"success": False, "message": "请先附加到游戏进程"}
        return self.memory_scanner.next_scan(filter_type, **kwargs)

    def api_memory_read(self, address: int, size: int) -> dict:
        """读取进程内存"""
        if not self.memory_scanner.is_attached():
            return {"success": False, "message": "请先附加到游戏进程"}
        return self.memory_scanner.read_memory(address, size)

    def api_memory_write(self, address: int, data_hex: str) -> dict:
        """写入进程内存"""
        if not self.memory_scanner.is_attached():
            return {"success": False, "message": "请先附加到游戏进程"}
        try:
            data = bytes.fromhex(data_hex.replace(" ", ""))
        except ValueError:
            return {"success": False, "message": "无效的十六进制数据"}
        return self.memory_scanner.write_memory(address, data)

    def api_memory_find_code_cave(self, min_size: int = 256) -> dict:
        """搜索内存 Code Cave"""
        if not self.memory_scanner.is_attached():
            return {"success": False, "message": "请先附加到游戏进程"}
        return self.memory_scanner.find_code_cave(min_size)

    def api_memory_inject_code(self, address: int, machine_code_hex: str) -> dict:
        """向进程注入机器码"""
        if not self.memory_scanner.is_attached():
            return {"success": False, "message": "请先附加到游戏进程"}
        try:
            machine_code = bytes.fromhex(machine_code_hex.replace(" ", ""))
        except ValueError:
            return {"success": False, "message": "无效的十六进制机器码"}
        return self.memory_scanner.inject_code(address, machine_code)

    def api_memory_install_hook(self, address: int, hook_code_hex: str, hook_type: str = "detour") -> dict:
        """安装内存 Hook"""
        if not self.memory_scanner.is_attached():
            return {"success": False, "message": "请先附加到游戏进程"}
        try:
            hook_code = bytes.fromhex(hook_code_hex.replace(" ", ""))
        except ValueError:
            return {"success": False, "message": "无效的十六进制代码"}
        return self.memory_scanner.install_hook(address, hook_code, hook_type)

    def api_memory_remove_hook(self, address: int) -> dict:
        """移除内存 Hook"""
        if not self.memory_scanner.is_attached():
            return {"success": False, "message": "请先附加到游戏进程"}
        return self.memory_scanner.remove_hook(address)

    def api_memory_take_snapshot(self, name: str = None) -> dict:
        """创建内存快照"""
        if not self.memory_scanner.is_attached():
            return {"success": False, "message": "请先附加到游戏进程"}
        return self.memory_scanner.take_snapshot(name)

    def api_memory_compare_snapshots(self, snapshot1: str, snapshot2: str) -> dict:
        """对比内存快照"""
        return self.memory_scanner.compare_snapshots(snapshot1, snapshot2)

    # ============================================================
    # V3.14.0: 引擎突破 — 汇编级代码分析器 (asm_analyzer)
    # ============================================================

    def api_asm_load_file(self, file_path: str, base_address: int = 0, arch: str = "x86") -> dict:
        """加载二进制文件进行汇编分析"""
        return self.asm_analyzer.load_file(file_path, base_address, arch)

    def api_asm_load_bytes(self, data_hex: str, base_address: int = 0, arch: str = "x86") -> dict:
        """从十六进制数据加载"""
        try:
            data = bytes.fromhex(data_hex)
        except ValueError:
            return {"success": False, "message": "无效的十六进制数据"}
        self.asm_analyzer.load_bytes(data, base_address, arch)
        return {"success": True, "message": f"已加载 {len(data)} 字节"}

    def api_asm_disassemble(self, start: int = 0, end: int = None, count: int = None) -> dict:
        """反汇编"""
        return self.asm_analyzer.disassemble(start, end, count)

    def api_asm_find_pattern(self, pattern: str, mask: str = None, start: int = 0, end: int = None) -> dict:
        """搜索字节模式"""
        pattern_bytes = bytes.fromhex(pattern)
        mask_bytes = mask.encode() if mask else None
        return self.asm_analyzer.find_pattern(pattern_bytes, mask_bytes, start, end)

    def api_asm_detect_functions(self) -> dict:
        """检测函数边界"""
        return self.asm_analyzer.detect_functions()

    def api_asm_build_cfg(self, function_address: int = None) -> dict:
        """构建控制流图"""
        return self.asm_analyzer.build_cfg(function_address)

    def api_asm_analyze_stack_frame(self, function_address: int) -> dict:
        """分析栈帧"""
        return self.asm_analyzer.analyze_stack_frame(function_address)

    def api_asm_generate_hook(self, target_address: int, hook_address: int, hook_type: str = "detour", arch: str = "x86") -> dict:
        """生成Hook代码"""
        if hook_type == "detour":
            return self.asm_analyzer.generate_detour_hook(target_address, hook_address, arch)
        elif hook_type == "trampoline":
            return self.asm_analyzer.generate_trampoline(target_address, hook_address, 5, arch)
        elif hook_type == "inline":
            return self.asm_analyzer.generate_inline_hook(target_address, hook_address, hook_address + 0x1000, 5, arch)
        elif hook_type == "vtable":
            return self.asm_analyzer.generate_vtable_hook(target_address, 0, hook_address, arch)
        return {"success": False, "message": f"未知Hook类型: {hook_type}"}

    def api_asm_get_statistics(self) -> dict:
        """获取指令统计"""
        return self.asm_analyzer.get_instruction_statistics()

    def api_asm_get_full_analysis(self) -> dict:
        """获取完整分析报告"""
        return self.asm_analyzer.get_full_analysis()

    def api_asm_get_cross_references(self) -> dict:
        """获取交叉引用"""
        return self.asm_analyzer.get_cross_references()

    # ============================================================
    # V3.14.0: 引擎突破 — 资源格式深度逆向 (resource_reverse)
    # ============================================================

    def api_resource_analyze_file(self, file_path: str) -> dict:
        """综合分析资源文件"""
        return self.resource_reverse.analyze_file(file_path)

    def api_resource_analyze_directory(self, directory: str) -> dict:
        """综合分析资源目录"""
        return self.resource_reverse.analyze_directory(directory)

    def api_resource_detect_format(self, file_path: str) -> dict:
        """检测文件格式"""
        from core.resource_reverse import FormatDetector
        fmt = FormatDetector.detect(file_path)
        return {"success": True, "format": fmt or "unknown"}

    def api_resource_verify_file(self, file_path: str) -> dict:
        """校验文件完整性"""
        from core.resource_reverse import IntegrityChecker
        result = IntegrityChecker.verify_file(file_path)
        return {
            "success": True,
            "valid": result.is_valid,
            "format": result.format_type,
            "errors": result.errors,
            "warnings": result.warnings,
            "info": result.info
        }

    def api_resource_get_spec(self, format_type: str) -> dict:
        """获取格式规范"""
        return self.resource_reverse.get_format_specification(format_type)

    def api_resource_generate_template(self, format_type: str) -> dict:
        """生成二进制模板"""
        return self.resource_reverse.generate_binary_template(format_type)

    def api_resource_list_formats(self) -> dict:
        """列出所有已知格式"""
        return self.resource_reverse.get_all_formats()

    def api_resource_parse_shp_header(self, file_path: str) -> dict:
        """解析SHP头部"""
        self.resource_reverse.shp_reverser.load(file_path)
        return self.resource_reverse.shp_reverser.parse_header()

    def api_resource_parse_pck_header(self, file_path: str) -> dict:
        """解析PCK头部"""
        self.resource_reverse.pck_reverser.load(file_path)
        return self.resource_reverse.pck_reverser.parse_header()

    def api_resource_parse_obd(self, file_path: str) -> dict:
        """解析OBD文件"""
        self.resource_reverse.obd_reverser.load(file_path)
        return self.resource_reverse.obd_reverser.parse()

    # ============================================================
    # V3.14.0: 引擎突破 — 游戏进程调试器 (game_debugger)
    # ============================================================

    def api_debugger_attach(self, pid: int) -> dict:
        """附加到进程"""
        return self.game_debugger.attach(pid)

    def api_debugger_detach(self) -> dict:
        """从进程分离"""
        return self.game_debugger.detach()

    def api_debugger_get_state(self) -> dict:
        """获取调试器状态"""
        return self.game_debugger.get_state()

    def api_debugger_get_process_info(self) -> dict:
        """获取进程信息"""
        return self.game_debugger.get_process_info()

    def api_debugger_set_breakpoint(self, address: int, condition: str = "", one_shot: bool = False) -> dict:
        """设置断点"""
        return self.game_debugger.set_breakpoint(address, condition, one_shot)

    def api_debugger_remove_breakpoint(self, bp_id: int) -> dict:
        """移除断点"""
        return self.game_debugger.remove_breakpoint(bp_id)

    def api_debugger_list_breakpoints(self) -> dict:
        """列出断点"""
        return self.game_debugger.list_breakpoints()

    def api_debugger_get_registers(self) -> dict:
        """获取寄存器"""
        return self.game_debugger.get_registers()

    def api_debugger_read_memory(self, address: int, size: int) -> dict:
        """读取内存"""
        return self.game_debugger.read_memory(address, size)

    def api_debugger_write_memory(self, address: int, data_hex: str) -> dict:
        """写入内存"""
        try:
            data = bytes.fromhex(data_hex)
        except ValueError:
            return {"success": False, "message": "无效的十六进制数据"}
        return self.game_debugger.write_memory(address, data)

    def api_debugger_read_int32(self, address: int) -> dict:
        """读取int32"""
        return self.game_debugger.read_int32(address)

    def api_debugger_read_float(self, address: int) -> dict:
        """读取float"""
        return self.game_debugger.read_float(address)

    def api_debugger_step_into(self) -> dict:
        """单步步入"""
        return self.game_debugger.step_into()

    def api_debugger_step_over(self) -> dict:
        """单步步过"""
        return self.game_debugger.step_over()

    def api_debugger_continue(self) -> dict:
        """继续执行"""
        return self.game_debugger.continue_execution()

    def api_debugger_get_call_stack(self) -> dict:
        """获取调用栈"""
        return self.game_debugger.get_call_stack()

    def api_debugger_get_modules(self) -> dict:
        """获取模块列表"""
        return self.game_debugger.get_modules()

    def api_debugger_set_watchpoint(self, address: int, size: int, watch_type: str = "write") -> dict:
        """设置监视点"""
        return self.game_debugger.set_watchpoint(address, size, watch_type)

    def api_debugger_get_disassembly(self, address: int, count: int = 10) -> dict:
        """获取反汇编"""
        return self.game_debugger.get_disassembly(address, count)

    def api_debugger_get_full_status(self) -> dict:
        """获取完整调试状态"""
        return self.game_debugger.get_full_status()

    # ============================================================
    # V3.15.0: 引擎突破 — 游戏AI行为分析器
    # ============================================================

    def api_ai_create_decision_tree(self, tree_id: str, name: str, description: str = "") -> dict:
        """创建AI决策树"""
        return self.ai_analyzer.create_decision_tree(tree_id, name, description)

    def api_ai_add_condition_node(self, tree_id: str, parent_id: str, condition: dict, weight: float = 1.0) -> dict:
        """添加AI条件节点"""
        return self.ai_analyzer.add_condition_node(tree_id, parent_id, condition, weight)

    def api_ai_add_action_node(self, tree_id: str, parent_id: str, action: dict, weight: float = 1.0) -> dict:
        """添加AI动作节点"""
        return self.ai_analyzer.add_action_node(tree_id, parent_id, action, weight)

    def api_ai_export_decision_tree(self, tree_id: str) -> dict:
        """导出AI决策树"""
        return self.ai_analyzer.export_decision_tree(tree_id)

    def api_ai_import_decision_tree(self, data: dict) -> dict:
        """导入AI决策树"""
        return self.ai_analyzer.import_decision_tree(data)

    def api_ai_list_decision_trees(self) -> list:
        """列出AI决策树"""
        return self.ai_analyzer.list_decision_trees()

    def api_ai_match_behaviors(self, state: dict, event: str) -> dict:
        """匹配AI行为模式"""
        return self.ai_analyzer.match_behaviors(state, event)

    def api_ai_list_behavior_patterns(self) -> list:
        """列出AI行为模式"""
        return self.ai_analyzer.list_behavior_patterns()

    def api_ai_create_ai_profile(self, profile_id: str, name: str, **kwargs) -> dict:
        """创建AI角色"""
        return self.ai_analyzer.create_ai_profile(profile_id, name, **kwargs)

    def api_ai_get_ai_profile(self, profile_id: str) -> dict:
        """获取AI角色"""
        return self.ai_analyzer.get_ai_profile(profile_id)

    def api_ai_list_ai_profiles(self) -> list:
        """列出AI角色"""
        return self.ai_analyzer.list_ai_profiles()

    def api_ai_compare_ai_profiles(self, profile_id1: str, profile_id2: str) -> dict:
        """比较AI角色"""
        return self.ai_analyzer.compare_ai_profiles(profile_id1, profile_id2)

    def api_ai_rank_decisions(self, profile_id: str = None, context: str = "peace", state: dict = None, limit: int = 10) -> list:
        """排序AI决策"""
        return self.ai_analyzer.rank_decisions(profile_id, context, state, limit)

    def api_ai_simulate_ai(self, profile_id: str, initial_state: dict, num_turns: int = 10, events: list = None) -> dict:
        """模拟AI行为"""
        return self.ai_analyzer.simulate_ai(profile_id, initial_state, num_turns, events)

    def api_ai_batch_simulate_ai(self, profile_ids: list, initial_state: dict, num_turns: int = 10, runs: int = 3) -> dict:
        """批量模拟AI"""
        return self.ai_analyzer.batch_simulate_ai(profile_ids, initial_state, num_turns, runs)

    def api_ai_save_ai_data(self, file_path: str) -> dict:
        """保存AI数据"""
        return self.ai_analyzer.save_ai_data(file_path)

    def api_ai_load_ai_data(self, file_path: str) -> dict:
        """加载AI数据"""
        return self.ai_analyzer.load_ai_data(file_path)

    def api_ai_list_decision_types(self) -> list:
        """列出AI决策类型"""
        return self.ai_analyzer.list_decision_types()

    def api_ai_list_event_types(self) -> list:
        """列出AI事件类型"""
        return self.ai_analyzer.list_event_types()

    def api_ai_get_context_analysis(self, context: str) -> dict:
        """获取AI情境分析"""
        return self.ai_analyzer.get_context_analysis(context)

    # ============================================================
    # V3.15.0: 引擎突破 — 存档加密/解密引擎
    # ============================================================

    def api_savecrypto_analyze(self, file_path: str) -> dict:
        """分析存档文件"""
        return self.save_crypto.analyze(file_path)

    def api_savecrypto_analyze_bytes(self, data: bytes) -> dict:
        """分析原始字节"""
        return self.save_crypto.analyze_bytes(data)

    def api_savecrypto_decrypt_xor(self, file_path: str, key: bytes, output_path: str = None) -> dict:
        """XOR解密文件"""
        return self.save_crypto.decrypt_xor(file_path, key, output_path)

    def api_savecrypto_encrypt_xor(self, file_path: str, key: bytes, output_path: str = None) -> dict:
        """XOR加密文件"""
        return self.save_crypto.encrypt_xor(file_path, key, output_path)

    def api_savecrypto_brute_force_key(self, file_path: str, max_key_len: int = 8) -> dict:
        """暴力恢复XOR密钥"""
        return self.save_crypto.brute_force_xor_key(file_path, max_key_len)

    def api_savecrypto_patch_save(self, file_path: str, offset: int, new_data: bytes, fix_checksum: bool = True, checksum_type: str = "crc32", output_path: str = None) -> dict:
        """修补存档"""
        return self.save_crypto.patch_save(file_path, offset, new_data, fix_checksum, checksum_type, output_path)

    def api_savecrypto_extract_sections(self, file_path: str, sections: list) -> dict:
        """提取存档区域"""
        return self.save_crypto.extract_sections(file_path, sections)

    def api_savecrypto_hex_dump(self, file_path: str, offset: int = 0, size: int = 256) -> dict:
        """存档十六进制转储"""
        return self.save_crypto.hex_dump(file_path, offset, size)

    def api_savecrypto_compare_saves(self, file1: str, file2: str) -> dict:
        """比较两个存档"""
        return self.save_crypto.compare_saves(file1, file2)

    def api_savecrypto_register_format(self, format_id: str, name: str, **kwargs) -> dict:
        """注册存档格式"""
        return self.save_crypto.format_parser.register_format(format_id, name, **kwargs)

    def api_savecrypto_get_info(self) -> dict:
        """获取存档加密引擎信息"""
        return self.save_crypto.get_info()

    # ============================================================
    # V3.15.0: 引擎突破 — 调用追踪与API拦截器
    # ============================================================

    def api_tracer_enable(self) -> dict:
        """启用追踪"""
        return self.call_tracer.enable_tracing()

    def api_tracer_disable(self) -> dict:
        """禁用追踪"""
        return self.call_tracer.disable_tracing()

    def api_tracer_is_enabled(self) -> bool:
        """检查追踪状态"""
        return self.call_tracer.is_tracing()

    def api_tracer_trace_call(self, function_name: str, module: str = "", params: list = None, address: int = 0) -> dict:
        """追踪一次调用"""
        return self.call_tracer.trace_call(function_name, module, params, address)

    def api_tracer_trace_return(self, call_id: int, return_value: any = None) -> dict:
        """追踪一次返回"""
        return self.call_tracer.trace_return(call_id, return_value)

    def api_tracer_add_filter(self, name: str = "", module: str = "", filter_type: str = "include") -> dict:
        """添加追踪过滤器"""
        return self.call_tracer.add_filter(name, module, filter_type)

    def api_tracer_get_events(self, limit: int = 100, event_type: str = None) -> list:
        """获取追踪事件"""
        return self.call_tracer.get_trace_events(limit, event_type)

    def api_tracer_get_statistics(self) -> dict:
        """获取追踪统计"""
        return self.call_tracer.get_trace_statistics()

    def api_tracer_get_call_tree(self) -> dict:
        """获取调用树"""
        return self.call_tracer.get_call_tree()

    def api_tracer_clear(self) -> dict:
        """清除追踪数据"""
        return self.call_tracer.clear_trace()

    def api_tracer_add_hook(self, function_name: str, hook_type: str, module: str = "", condition: str = "") -> dict:
        """添加Hook"""
        return self.call_tracer.add_hook(function_name, hook_type, module=module, condition=condition)

    def api_tracer_remove_hook(self, hook_id: str) -> dict:
        """移除Hook"""
        return self.call_tracer.remove_hook(hook_id)

    def api_tracer_list_hooks(self) -> list:
        """列出所有Hook"""
        return self.call_tracer.list_hooks()

    def api_tracer_get_performance_summary(self) -> dict:
        """获取性能摘要"""
        return self.call_tracer.get_performance_summary()

    def api_tracer_export_trace(self, file_path: str, format: str = "json") -> dict:
        """导出追踪数据"""
        return self.call_tracer.export_trace(file_path, format)

    def api_tracer_generate_call_graph_dot(self) -> str:
        """生成DOT调用图"""
        return self.call_tracer.generate_call_graph_dot()

    def api_tracer_generate_call_graph_mermaid(self) -> str:
        """生成Mermaid调用图"""
        return self.call_tracer.generate_call_graph_mermaid()

    def api_tracer_get_info(self) -> dict:
        """获取追踪引擎信息"""
        return self.call_tracer.get_info()

    # ============================================================
    # V3.16.0: 引擎突破 — 二进制差异化与补丁引擎
    # ============================================================

    def api_diff_generate_delta(self, old_data_b64: str, new_data_b64: str) -> dict:
        """生成 Delta 补丁"""
        old_data = base64.b64decode(old_data_b64)
        new_data = base64.b64decode(new_data_b64)
        return self.binary_diff.generate_delta(old_data, new_data)

    def api_diff_apply_delta(self, old_data_b64: str, delta_b64: str) -> dict:
        """应用 Delta 补丁"""
        old_data = base64.b64decode(old_data_b64)
        delta = base64.b64decode(delta_b64)
        return self.binary_diff.apply_delta(old_data, delta)

    def api_diff_diff_bytes(self, old_data_b64: str, new_data_b64: str) -> dict:
        """字节级差异"""
        old_data = base64.b64decode(old_data_b64)
        new_data = base64.b64decode(new_data_b64)
        return self.binary_diff.diff_bytes(old_data, new_data)

    def api_diff_scan_signature(self, data_b64: str, pattern: str, fmt: str = "ida") -> dict:
        """扫描签名"""
        data = base64.b64decode(data_b64)
        return self.binary_diff.scan_signature(data, pattern, fmt)

    def api_diff_generate_signature(self, data_b64: str, offset: int, length: int, fmt: str = "ida") -> dict:
        """生成签名"""
        data = base64.b64decode(data_b64)
        return self.binary_diff.generate_signature(data, offset, length, fmt)

    def api_diff_create_patch(self, source_hash: str, target_hash: str, entries_json: str, fmt: str = "delta") -> dict:
        """创建补丁"""
        entries = json.loads(entries_json)
        return self.binary_diff.create_patch(source_hash, target_hash, entries, fmt)

    def api_diff_apply_patch(self, data_b64: str, patch_json: str) -> dict:
        """应用补丁"""
        data = base64.b64decode(data_b64)
        patch = json.loads(patch_json)
        return self.binary_diff.apply_patch(data, patch)

    def api_diff_get_info(self) -> dict:
        """获取引擎信息"""
        return self.binary_diff.get_info()

    # ============================================================
    # V3.16.0: 引擎突破 — 脚本虚拟机逆向引擎
    # ============================================================

    def api_vm_detect_type(self, data_b64: str) -> dict:
        """检测 VM 类型"""
        data = base64.b64decode(data_b64)
        return self.script_vm.detect_vm_type(data)

    def api_vm_detect_type_file(self, file_path: str) -> dict:
        """从文件检测 VM 类型"""
        return self.script_vm.detect_vm_type_file(file_path)

    def api_vm_disassemble(self, data_b64: str, vm_type: str) -> dict:
        """反汇编字节码"""
        data = base64.b64decode(data_b64)
        return self.script_vm.disassemble(data, vm_type)

    def api_vm_analyze(self, file_path: str, vm_type: str = "") -> dict:
        """综合分析脚本文件"""
        return self.script_vm.analyze(file_path, vm_type)

    def api_vm_build_cfg(self, instructions_json: str) -> dict:
        """构建控制流图"""
        instructions = json.loads(instructions_json)
        return self.script_vm.build_cfg(instructions)

    def api_vm_generate_pseudo_code(self, instructions_json: str) -> dict:
        """生成伪代码"""
        instructions = json.loads(instructions_json)
        return self.script_vm.generate_pseudo_code(instructions)

    def api_vm_simulate(self, instructions_json: str) -> dict:
        """模拟执行"""
        instructions = json.loads(instructions_json)
        return self.script_vm.simulate(instructions)

    def api_vm_get_info(self) -> dict:
        """获取引擎信息"""
        return self.script_vm.get_info()

    # ============================================================
    # V3.16.0: 引擎突破 — 代码注入与DLL劫持引擎
    # ============================================================

    def api_inject_analyze_process(self, process_name: str) -> dict:
        """分析进程"""
        return self.code_inject.analyze_process(process_name)

    def api_inject_enumerate_modules(self, process_name: str) -> dict:
        """枚举模块"""
        return self.code_inject.enumerate_modules(process_name)

    def api_inject_plan_injection(self, target_process: str, dll_path: str = "", prefer_stealth: bool = True) -> dict:
        """规划注入策略"""
        return self.code_inject.plan_injection(target_process, dll_path, prefer_stealth)

    def api_inject_find_code_caves(self, data_b64: str, base_address: int = 0, required_size: int = 0) -> dict:
        """寻找代码洞穴"""
        data = base64.b64decode(data_b64)
        return self.code_inject.find_code_caves(data, base_address, required_size)

    def api_inject_generate_inline_hook(self, target_addr: int, hook_addr: int, original_bytes_b64: str = "", is_64bit: bool = True) -> dict:
        """生成内联 Hook"""
        original_bytes = base64.b64decode(original_bytes_b64) if original_bytes_b64 else b""
        return self.code_inject.generate_inline_hook(target_addr, hook_addr, original_bytes, is_64bit)

    def api_inject_generate_iat_hook(self, module_name: str, function_name: str, hook_addr: int) -> dict:
        """生成 IAT Hook"""
        return self.code_inject.generate_iat_hook(module_name, function_name, hook_addr)

    def api_inject_generate_nop_patch(self, address: int, size: int) -> dict:
        """生成 NOP 补丁"""
        return self.code_inject.generate_nop_patch(address, size)

    def api_inject_analyze_dll(self, dll_name: str) -> dict:
        """分析 DLL"""
        return self.code_inject.analyze_dll(dll_name)

    def api_inject_find_hijack_opportunities(self, target_exe: str) -> dict:
        """寻找 DLL 劫持机会"""
        return self.code_inject.find_hijack_opportunities(target_exe)

    def api_inject_generate_proxy_dll(self, target_dll: str, payload_code: str = "", architecture: str = "x64") -> dict:
        """生成代理 DLL"""
        return self.code_inject.generate_proxy_dll(target_dll, payload_code, architecture)

    def api_inject_analyze_security(self, process_name: str, code_data_b64: str = "") -> dict:
        """分析安全措施"""
        code_data = base64.b64decode(code_data_b64) if code_data_b64 else b""
        return self.code_inject.analyze_security(process_name, code_data)

    def api_inject_scan_anti_tamper(self, data_b64: str) -> dict:
        """扫描反篡改措施"""
        data = base64.b64decode(data_b64)
        return self.code_inject.scan_anti_tamper(data)

    def api_inject_comprehensive_analysis(self, process_name: str, exe_data_b64: str = "", is_64bit: bool = True) -> dict:
        """综合分析"""
        exe_data = base64.b64decode(exe_data_b64) if exe_data_b64 else b""
        return self.code_inject.comprehensive_analysis(process_name, exe_data, is_64bit)

    def api_inject_get_info(self) -> dict:
        """获取引擎信息"""
        return {"success": True, "engine": "CodeInjectEngine", "version": "1.0.0"}

    # ============================================================
    # V3.18.0: 引擎突破 — 反调试/反反调试引擎
    # ============================================================

    def api_anti_debug_analyze(self, file_path: str) -> dict:
        """分析文件的反调试措施"""
        return self.anti_debug.analyze(file_path)

    def api_anti_debug_scan(self, file_path: str, category: str = "") -> dict:
        """扫描反调试代码"""
        return self.anti_debug.scan_anti_debug(file_path, category)

    def api_anti_debug_bypass(self, file_path: str) -> dict:
        """生成反调试绕过"""
        return self.anti_debug.generate_bypass(file_path)

    def api_anti_debug_integrity(self, file_path: str) -> dict:
        """扫描完整性检查"""
        return self.anti_debug.scan_integrity(file_path)

    def api_anti_debug_bypass_code(self, name: str) -> dict:
        """获取绕过代码"""
        return self.anti_debug.get_bypass_code(name)

    def api_anti_debug_signatures(self, category: str = "") -> dict:
        """列出反调试签名"""
        return self.anti_debug.list_signatures(category)

    def api_anti_debug_stats(self) -> dict:
        """获取反调试统计"""
        return self.anti_debug.get_statistics()

    # ============================================================
    # V3.18.0: 引擎突破 — 代码混淆分析/去混淆引擎
    # ============================================================

    def api_deobfuscator_analyze(self, file_path: str) -> dict:
        """分析文件混淆情况"""
        return self.deobfuscator.analyze(file_path)

    def api_deobfuscator_scan(self, file_path: str) -> dict:
        """扫描混淆代码"""
        return self.deobfuscator.scan_obfuscation(file_path)

    def api_deobfuscator_strings(self, file_path: str) -> dict:
        """解密字符串"""
        return self.deobfuscator.decrypt_strings(file_path)

    def api_deobfuscator_predicates(self, file_path: str) -> dict:
        """检测不透明谓词"""
        return self.deobfuscator.detect_opaque_predicates(file_path)

    def api_deobfuscator_cff(self, file_path: str) -> dict:
        """检测控制流平坦化"""
        return self.deobfuscator.detect_cff(file_path)

    def api_deobfuscator_entropy(self, file_path: str) -> dict:
        """获取熵分析"""
        return self.deobfuscator.get_entropy_analysis(file_path)

    def api_deobfuscator_stats(self) -> dict:
        """获取去混淆统计"""
        return self.deobfuscator.get_statistics()

    # ============================================================
    # V3.18.0: 引擎突破 — 反编译/反汇编引擎
    # ============================================================

    def api_decompile(self, asm_text: str, func_name: str = "") -> dict:
        """反编译汇编代码"""
        return self.decompiler.decompile(asm_text, func_name)

    def api_decompile_file(self, file_path: str) -> dict:
        """反编译文件"""
        return self.decompiler.decompile_file(file_path)

    def api_build_cfg(self, asm_text: str) -> dict:
        """构建控制流图"""
        return self.decompiler.build_cfg(asm_text)

    def api_symbolic_execute(self, asm_text: str, max_depth: int = 50) -> dict:
        """符号执行"""
        return self.decompiler.symbolic_execute(asm_text, max_depth)

    def api_solve_constraints(self, constraints: list) -> dict:
        """求解约束"""
        return self.decompiler.solve_constraints(constraints)

    def api_simplify_expr(self, expr_data: dict) -> dict:
        """简化表达式"""
        return self.decompiler.simplify_expression(expr_data)

    def api_decompiler_stats(self) -> dict:
        """获取反编译统计"""
        return self.decompiler.get_statistics()