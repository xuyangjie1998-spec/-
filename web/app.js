/**
 * San7ModMaker - 前端主脚本
 * 前后端交互逻辑，支持PyWebView JS-Python双向通信
 */

// ============================================================
// 通用工具
// ============================================================

// HTML转义函数
function escHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Toast 通知系统（替代 alert）
const ICON_MAP = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };

// ============================================================
// 主题切换
// ============================================================

function toggleTheme() {
    const html = document.documentElement;
    const btn = document.querySelector('.sidebar .btn-xs');
    const current = html.getAttribute('data-theme');
    if (current === 'light') {
        html.removeAttribute('data-theme');
        if (btn) btn.textContent = '☀';
        localStorage.setItem('san7_theme', 'dark');
    } else {
        html.setAttribute('data-theme', 'light');
        if (btn) btn.textContent = '☾';
        localStorage.setItem('san7_theme', 'light');
    }
}

// 初始化主题
(function initTheme() {
    const saved = localStorage.getItem('san7_theme');
    if (saved === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        const btn = document.querySelector('.sidebar .btn-xs');
        if (btn) btn.textContent = '☾';
    }
})();

// ============================================================
// 数据仪表盘
// ============================================================

const dashboard = {
    async refresh() {
        const res = await pyApi('dashboardStats');
        if (!res || !res.success) {
            showToast(res && res.message ? res.message : '加载统计失败', 'error');
            return;
        }
        const map = {
            dashGenerals: res.generals,
            dashSoldiers: res.soldiers,
            dashThings: res.things,
            dashSkills: res.skills,
            dashSuperAtk: res.superatk,
            dashFormations: res.formations,
            dashTitles: res.titles,
            dashNations: res.nations,
            dashCities: res.cities,
            dashHistories: res.histories,
            dashScenarios: res.scenarios,
            dashAges: res.ages,
            dashSettingFiles: res.setting_files,
            dashShapeDirs: res.shape_dirs,
            dashGenfaceFiles: res.genface_files,
            dashBackups: res.backup_files
        };
        for (const [id, val] of Object.entries(map)) {
            const el = document.getElementById(id);
            if (el) el.textContent = val != null ? val : '-';
        }
        showToast('统计数据已刷新', 'success');
    }
};
function showToast(msg, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    const text = String(msg);
    const displayText = text.length > 200 ? text.slice(0, 200) + '...' : text;
    el.innerHTML = `<span class="toast-icon">${ICON_MAP[type] || 'ℹ'}</span><span title="${escHtml(text)}">${escHtml(displayText)}</span>`;
    container.appendChild(el);
    setTimeout(() => { if (el.parentNode) el.remove(); }, 3500);
}

// 全局未捕获 Promise 拒绝处理器
window.addEventListener('unhandledrejection', (event) => {
    console.error('未捕获的Promise拒绝:', event.reason);
    showToast('操作异常: ' + (event.reason ? String(event.reason).slice(0, 80) : '未知错误'), 'error');
    event.preventDefault();
});

/** 全局标签切换（向导面板快捷入口） */
function switchTab(tabId) {
    const navItem = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
    if (navItem) navItem.click();
}

// ============================================================
// 导航分类折叠 & 全局搜索
// ============================================================
const NavCategory = {
    toggle(header) {
        const category = header.parentElement;
        category.classList.toggle('collapsed');
        const arrow = header.querySelector('.nav-category-arrow');
        const collapsed = category.classList.contains('collapsed');
        if (arrow) {
            arrow.textContent = collapsed ? '▶' : '▼';
        }
        header.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    }
};

const NavSearch = {
    filter(query) {
        const q = query.toLowerCase().trim();
        const categories = document.querySelectorAll('.nav-category');
        const topItems = document.querySelectorAll('.nav-menu > .nav-item');
        let anyVisible = false;

        // 过滤固定入口（首页、设置）
        topItems.forEach(item => {
            const text = (item.querySelector('.nav-text')?.textContent || '') + ' ' +
                         (item.querySelector('.nav-desc')?.textContent || '');
            if (!q || text.toLowerCase().includes(q)) {
                item.classList.remove('search-hidden');
                anyVisible = true;
            } else {
                item.classList.add('search-hidden');
            }
        });

        // 过滤分类中的项
        categories.forEach(cat => {
            const items = cat.querySelectorAll('.nav-item');
            let catHasVisible = false;
            items.forEach(item => {
                const text = (item.querySelector('.nav-text')?.textContent || '') + ' ' +
                             (item.querySelector('.nav-desc')?.textContent || '');
                if (!q || text.toLowerCase().includes(q)) {
                    item.classList.remove('search-hidden');
                    catHasVisible = true;
                } else {
                    item.classList.add('search-hidden');
                }
            });
            if (q && !catHasVisible) {
                cat.classList.add('search-hidden');
            } else {
                cat.classList.remove('search-hidden');
                if (catHasVisible && cat.classList.contains('collapsed') && q) {
                    // 搜索时自动展开匹配的分类
                    cat.classList.remove('collapsed');
                    const arrow = cat.querySelector('.nav-category-arrow');
                    if (arrow) arrow.textContent = '▼';
                }
            }
            if (catHasVisible) anyVisible = true;
        });
    }
};

// 全局API调用包装 - 兼容PyWebView和普通浏览器模式
// 全局加载状态
let _apiLoading = 0;
const _loadingTimer = {};

async function pyApi(method, ...args) {
    _apiLoading++;
    // 显示加载指示器（延迟300ms，避免闪烁）
    _loadingTimer[method] = setTimeout(() => {
        if (_apiLoading > 0) {
            let spinner = document.getElementById('globalSpinner');
            if (!spinner) {
                spinner = document.createElement('div');
                spinner.id = 'globalSpinner';
                spinner.innerHTML = '<div class="spinner"></div>';
                spinner.style.cssText = 'position:fixed;top:8px;right:8px;z-index:9999;width:20px;height:20px;border:3px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin 0.6s linear infinite;';
                document.body.appendChild(spinner);
            }
            spinner.style.display = 'block';
        }
    }, 300);
    try {
        if (typeof window.pywebview !== 'undefined' && window.pywebview.api) {
            const func = window.pywebview.api[method];
            if (typeof func === 'function') {
                return await func(...args);
            }
        }
        // 回退到测试模式
        console.warn('PyWebView API不可用，使用测试模式:', method);
        return mockApi(method, ...args);
    } catch (e) {
        console.error('API调用失败:', method, e);
        return { success: false, message: 'API调用失败: ' + e.message };
    } finally {
        _apiLoading--;
        clearTimeout(_loadingTimer[method]);
        if (_apiLoading <= 0) {
            _apiLoading = 0;
            const spinner = document.getElementById('globalSpinner');
            if (spinner) spinner.style.display = 'none';
        }
    }
}

// 预校验保存流程全局状态
let _validatePendingResolve = null;

// 弹窗确认按钮 — 由用户决定是否强制保存
function validateModalConfirmSave() {
    if (_validatePendingResolve) { _validatePendingResolve(true); _validatePendingResolve = null; }
    const overlay = document.getElementById('validateModalOverlay');
    const modal = document.getElementById('validateModal');
    if (overlay) overlay.style.display = 'none';
    if (modal) modal.style.display = 'none';
}

// 预校验所有数据，弹窗显示结果，由用户决定是否强制保存
async function validateBeforeSave() {
    const res = await pyApi('validateAll');
    if (!res) return true; // API 调用失败时允许保存
    const sum = res.summary || { total: 0, errors: 0, warnings: 0, infos: 0 };
    const container = document.getElementById('validateResultList');
    const results = res.results || [];
    document.getElementById('vsTotal').textContent = sum.total || 0;
    document.getElementById('vsErrors').textContent = sum.errors || 0;
    document.getElementById('vsWarnings').textContent = sum.warnings || 0;
    document.getElementById('vsInfos').textContent = sum.infos || 0;
    if (container) {
        container.innerHTML = '';
        if (results.length === 0) {
            container.innerHTML = '<div class="loading">没有检查出问题</div>';
        } else {
            results.forEach(r => {
                const item = document.createElement('div');
                item.className = `validate-item ${r.severity}`;
                const icon = r.severity === 'error' ? '✗' : r.severity === 'warning' ? '!' : 'ℹ';
                item.innerHTML = `<span class="v-icon">${icon}</span><div class="v-body"><div>${escHtml(r.message)}</div><div class="v-file">${escHtml(r.file_ref||'—')} ${escHtml(r.section_ref||'')} ${escHtml(r.field_ref||'')}</div></div>`;
                container.appendChild(item);
            });
        }
    }
    if (sum.errors === 0) return true;
    // 如果上一次的弹窗还在等待，先 resolve 它
    if (_validatePendingResolve) { _validatePendingResolve(false); _validatePendingResolve = null; }
    return new Promise((resolve) => {
        _validatePendingResolve = resolve;
        const overlay = document.getElementById('validateModalOverlay');
        const modal = document.getElementById('validateModal');
        if (overlay) overlay.style.display = 'block';
        if (modal) modal.style.display = 'block';
    });
}

// 工具提示渲染辅助 — 根据schema字段渲染带提示的label
function tooltipLabel(fieldName, description) {
    if (!description) return escHtml(fieldName);
    return escHtml(fieldName) + ' <span class="tooltip-icon" data-tip="' + escHtml(description) + '">?</span>';
}

// 为指定编辑器的表单字段添加工具提示
async function setupTooltips(schemaType, prefix) {
    // schemaType: "general" / "soldier" / "thing" / ... 
    // prefix: DOM id前缀, 如 "g_" / "s_" / "t_"
    try {
        const res = await pyApi('getSchema', schemaType);
        const schema = res.data || {};
        const sections = schema.sections || {};
        const sectionName = Object.keys(sections)[0];
        const fields = (sections[sectionName] || {}).fields || {};
        for (const [fieldName, fieldInfo] of Object.entries(fields)) {
            const desc = fieldInfo.description || '';
            if (!desc) continue;
            const inputEl = document.getElementById(prefix + fieldName);
            if (!inputEl) continue;
            const formGroup = inputEl.closest('.form-group');
            if (!formGroup) continue;
            const label = formGroup.querySelector('label');
            if (!label) continue;
            // 避免重复添加
            if (label.querySelector('.tooltip-icon')) continue;
            label.innerHTML = tooltipLabel(label.textContent.trim(), desc);
        }
    } catch(e) { /* 静默降级 */ }
}

// ============================================================
// 全局撤销/重做管理器
// ============================================================

const UndoManager = {
    _stacks: {},       // { editorId: { undo: [], redo: [] } }
    _maxSteps: 50,     // 每个编辑器最多保留50步

    /** 注册编辑器 */
    register(editorId) {
        if (!this._stacks[editorId]) {
            this._stacks[editorId] = { undo: [], redo: [] };
        }
    },

    /** 推送快照到撤销栈，同时清空重做栈 */
    pushState(editorId, snapshot) {
        if (!this._stacks[editorId]) this.register(editorId);
        const stack = this._stacks[editorId];
        // 调用方（snapshot()）已经做了 JSON 克隆，这里直接存储
        stack.undo.push(snapshot);
        if (stack.undo.length > this._maxSteps) stack.undo.shift();
        stack.redo = []; // 新操作清空重做栈
    },

    /** 撤销：返回上一个快照，或null */
    undo(editorId, currentSnapshot) {
        if (!this._stacks[editorId]) return null;
        const stack = this._stacks[editorId];
        if (stack.undo.length === 0) return null;
        // 当前状态推入重做栈
        stack.redo.push(JSON.parse(JSON.stringify(currentSnapshot)));
        // 弹出上一个状态
        return stack.undo.pop();
    },

    /** 重做：返回下一个快照，或null */
    redo(editorId, currentSnapshot) {
        if (!this._stacks[editorId]) return null;
        const stack = this._stacks[editorId];
        if (stack.redo.length === 0) return null;
        // 当前状态推入撤销栈
        stack.undo.push(JSON.parse(JSON.stringify(currentSnapshot)));
        // 弹出重做状态
        return stack.redo.pop();
    },

    /** 清空指定编辑器的历史 */
    clear(editorId) {
        if (this._stacks[editorId]) {
            this._stacks[editorId] = { undo: [], redo: [] };
        }
    },

    /** 获取撤销栈深度 */
    getUndoCount(editorId) {
        return this._stacks[editorId] ? this._stacks[editorId].undo.length : 0;
    },

    /** 获取重做栈深度 */
    getRedoCount(editorId) {
        return this._stacks[editorId] ? this._stacks[editorId].redo.length : 0;
    },
};

// 当前活跃的编辑器映射（tab -> editorId）
let _activeEditorId = null;

// 当前活跃编辑器的快照函数
let _activeSnapshotFn = null;

// 当前活跃编辑器的恢复函数
let _activeRestoreFn = null;

/** 设置当前活跃编辑器，让Ctrl+Z/Y知道操作哪个编辑器 */
function setActiveEditor(editorId, snapshotFn, restoreFn) {
    _activeEditorId = editorId;
    _activeSnapshotFn = snapshotFn;
    _activeRestoreFn = restoreFn;
    UndoManager.register(editorId);
}

/** 键盘快捷键：Ctrl+Z 撤销, Ctrl+Y 或 Ctrl+Shift+Z 重做 */
document.addEventListener('keydown', (e) => {
    if (!_activeEditorId || !_activeSnapshotFn || !_activeRestoreFn) return;
    // 忽略在input/textarea/select中的Ctrl+Z/Y（让浏览器默认行为处理文本输入）
    const tag = document.activeElement ? document.activeElement.tagName : '';
    const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
    if (isInput) return;

    if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        const current = _activeSnapshotFn();
        const prev = UndoManager.undo(_activeEditorId, current);
        if (prev !== null) {
            _activeRestoreFn(prev);
            showUndoToast(`撤销 (${UndoManager.getUndoCount(_activeEditorId)}步可撤销)`);
        }
    } else if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault();
        const current = _activeSnapshotFn();
        const next = UndoManager.redo(_activeEditorId, current);
        if (next !== null) {
            _activeRestoreFn(next);
            showUndoToast(`重做 (${UndoManager.getRedoCount(_activeEditorId)}步可重做)`);
        }
    } else if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        // Ctrl+S: 保存当前编辑器
        const activeTab = document.querySelector('.nav-item.active');
        if (activeTab) {
            const tabName = activeTab.getAttribute('data-tab');
            if (tabName && _activeEditorId) {
                e.preventDefault();
                const editor = _editorTabMap[tabName];
                if (editor && editor.obj && typeof editor.obj.save === 'function') {
                    editor.obj.save().then(() => showToast('已保存', 'success')).catch(e => showToast('保存失败: ' + e, 'error'));
                }
            }
        }
    } else if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        // Ctrl+F: 聚焦搜索框
        const searchInput = document.querySelector('[id$="Search"]');
        if (searchInput && document.activeElement !== searchInput) {
            e.preventDefault();
            searchInput.focus();
            searchInput.select();
        }
    }
});

/** 在底部显示简短的撤销/重做提示 */
let _undoToastTimer = null;
function showUndoToast(msg) {
    let toast = document.getElementById('undoToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'undoToast';
        toast.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.85);color:#fff;padding:8px 20px;border-radius:20px;font-size:12px;z-index:9999;pointer-events:none;transition:opacity 0.3s;';
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.opacity = '1';
    if (_undoToastTimer) clearTimeout(_undoToastTimer);
    _undoToastTimer = setTimeout(() => { toast.style.opacity = '0'; }, 2000);
}

// 测试模式mock
function mockApi(method, ...args) {
    const emptyData = { success: false, message: '请在PyWebView环境中运行', data: [], count: 0 };
    const mocks = {
        // 基础
        getProgress: () => ({
            milestones: [],
            version: '2.2',
            last_updated: '2026-07-13',
            known_issues: ['请在PyWebView环境中运行']
        }),
        getGameInfo: () => ({ game_path: '', configured: false, has_setting: false, has_face: false, has_exe: false, recent_paths: [] }),
        setGamePath: () => ({ success: false, message: '测试模式，请在实际环境中运行' }),
        // 武将
        loadGenerals: () => emptyData,
        saveGenerals: () => ({ success: false, message: '测试模式' }),
        newGeneral: () => emptyData,
        cloneGeneral: () => emptyData,
        deleteGeneral: () => ({ success: false, message: '测试模式' }),
        // 兵种
        loadSoldiers: () => emptyData,
        saveSoldiers: () => ({ success: false, message: '测试模式' }),
        // 物品
        loadThings: () => emptyData,
        saveThings: () => ({ success: false, message: '测试模式' }),
        loadStoreConfig: () => ({ success: true, data: {} }),
        saveStoreConfig: () => ({ success: false, message: '测试模式' }),
        loadItemEnhance: () => ({ success: true, data: [] }),
        saveItemEnhance: () => ({ success: false, message: '测试模式' }),
        // 技能
        loadDefSkill: () => emptyData,
        saveDefSkill: () => ({ success: false, message: '测试模式' }),
        loadSkills: () => ({ success: true, data: { magic: [], strategy: [] } }),
        saveSkills: () => ({ success: false, message: '测试模式' }),
        newSkill: () => emptyData,
        // 必杀技
        loadSuperAtk: () => ({ success: true, data: [] }),
        saveSuperAtk: () => ({ success: false, message: '测试模式' }),
        newSuperAtk: () => emptyData,
        // 特性
        loadGenSkills: () => ({ success: true, data: { gen: { sections: [] }, army: { sections: [] }, group: { sections: [] } } }),
        saveGenSkills: () => ({ success: false, message: '测试模式' }),
        // 阵型/官职
        loadFormations: () => ({ success: true, data: [], count: 0 }),
        saveFormations: () => ({ success: false, message: '测试模式' }),
        loadTitles: () => ({ success: true, data: [], count: 0 }),
        saveTitles: () => ({ success: false, message: '测试模式' }),
        newTitle: () => emptyData,
        // 剧本/参数
        loadScenarios: () => ({ success: true, data: [], count: 0 }),
        saveScenarios: () => ({ success: false, message: '测试模式' }),
        loadGlobalParams: () => ({ success: true, data: [], count: 0 }),
        saveGlobalParams: () => ({ success: false, message: '测试模式' }),
        // 势力/城池
        loadNations: () => ({ success: true, data: [], count: 0 }),
        saveNations: () => ({ success: false, message: '测试模式' }),
        loadCities: () => ({ success: true, data: [], count: 0 }),
        saveCities: () => ({ success: false, message: '测试模式' }),
        loadCityPeriod: () => ({ success: true, data: [], count: 0 }),
        saveCityPeriod: () => ({ success: false, message: '测试模式' }),
        loadHistories: () => ({ success: true, data: [], count: 0 }),
        saveHistories: () => ({ success: false, message: '测试模式' }),
        newHistory: () => ({ success: true, data: {} }),
        // 等级/年代/出生地
        loadGenLV: () => ({ success: true, data: [] }),
        saveGenLV: () => ({ success: false, message: '测试模式' }),
        loadAge: () => ({ success: true, data: [], count: 0 }),
        saveAge: () => ({ success: false, message: '测试模式' }),
        loadGeneral02: () => ({ success: true, data: [], count: 0 }),
        saveGeneral02: () => ({ success: false, message: '测试模式' }),
        // 文本
        loadTermTextFull: () => ({ success: true, data: {} }),
        saveTermText: () => ({ success: false, message: '测试模式' }),
        getThingTermText: () => ({ success: true, name: '', desc: '' }),
        setThingTermText: () => ({ success: false, message: '测试模式' }),
        searchTermtext: () => ({ success: true, results: [], count: 0 }),
        getAllTermtext: () => ({ success: true, data: {}, count: 0 }),
        // 备份/校验
        getBackupHistory: () => ({ success: true, history: [], count: 0 }),
        getExeInfo: () => ({ exists: false, size: 0, patches: [], applied: {} }),
        applyExePatch: () => ({ success: false, message: '测试模式' }),
        applyExePatchAuto: () => ({ success: false, message: '测试模式' }),
        disassembleExe: () => ({ success: false, instructions: [], has_capstone: false }),
        disassembleScan: () => ({ success: false, message: '测试模式' }),
        applyNopPatch: () => ({ success: false, message: '测试模式' }),
        applyJmpPatch: () => ({ success: false, message: '测试模式' }),
        applyTemplatePatch: () => ({ success: false, message: '测试模式' }),
        getJmpTemplates: () => ({ success: true, templates: {} }),
        scanExeSignatures: () => ({ success: false, message: '测试模式', signatures: {}, candidates: {} }),
        scanExeValue: () => ({ success: false, message: '测试模式', offsets: [], count: 0 }),
        revertExePatches: () => ({ success: false, message: '测试模式', count: 0 }),
        exeCommunityPatches: () => ({ success: true, patches: [], count: 0, message: '测试模式' }),
        exeApplyCommunityPatch: () => ({ success: false, message: '测试模式' }),
        // 分辨率/语言/转换
        applyResolutionPreset: () => ({ success: false, message: '测试模式' }),
        bmp2raw: () => ({ success: false, message: '测试模式' }),
        readLanguageDat: () => ({ success: true, current: 'BIG5' }),
        switchLanguagePreset: () => ({ success: false, message: '测试模式' }),
        exportLanguagePack: () => ({ success: false, message: '请在PyWebView环境中运行' }),
        importLanguagePack: () => ({ success: false, message: '请在PyWebView环境中运行' }),
        diffLanguageTexts: () => ({ success: true, diff: {}, message: '测试模式', current: 'BIG5', source: 'GB' }),
        reloadTermtext: () => ({ success: false, message: '测试模式' }),
        languageStatus: () => ({ success: true, current: 'BIG5', available: [], has_language_dat: false }),
        launchGame: () => ({ success: false, message: '测试模式' }),
        writeLanguageDat: () => ({ success: false, message: '测试模式' }),
        newGlobalParams: () => ({ success: true, data: {No:'',Name:'',Int00:'0',Int01:'0',Int02:'0',Int03:'0',Int04:'0',Int05:'0',Int06:'0',Int07:'0',Int08:'0',Int09:'0',Float00:'0',Float01:'0',Float02:'0',Float03:'0',Float04:'0',Float05:'0',Float06:'0',Float07:'0',Float08:'0',Float09:'0',String:''} }),
        // MOD
        getModList: () => ({ success: true, mods: [] }),
        getActiveMod: () => ({ success: true, mod_name: '' }),
        setActiveMod: () => ({ success: false, message: '测试模式' }),
        createMod: () => ({ success: false, message: '测试模式' }),
        deleteMod: () => ({ success: false, message: '测试模式' }),
        modSnapshot: () => ({ success: false, message: '测试模式' }),
        packModIncremental: () => ({ success: false, message: '测试模式' }),
        packModOneClick: () => ({ success: false, message: '测试模式' }),
        importMod: () => ({ success: false, message: '测试模式' }),
        remapConflicts: () => ({ success: false, message: '测试模式' }),
        // 批量/差异
        getBatchFiles: () => ({ success: true, files: [] }),
        batchPreview: () => ({ success: true, summary: {}, affected: 0 }),
        batchExecute: () => ({ success: false, message: '测试模式' }),
        batchClonePreview: () => ({ success: true, entries: [] }),
        batchCloneExecute: () => ({ success: false, message: '测试模式' }),
        batchSearch: () => ({ success: true, results: [] }),
        batchSearchReplace: () => ({ success: false, message: '测试模式' }),
        getDiffBackups: () => ({ success: true, backups: {} }),
        diffCompare: () => ({ success: true, diff: {}, stats: {} }),
        diffExport: () => ({ success: false, message: '测试模式' }),
        // 引用检查
        checkReferences: () => ({ success: true, total_issues: 0, issues: [], broken_refs: [], missing_entries: [], reference_summary: {}, general_count: 0 }),
        // 头像
        getFacePreview: () => ({ success: false, imgData: '' }),
        selectImageFile: () => ({ success: false, message: '测试模式' }),
        savePngDialog: () => ({ success: false, message: '测试模式' }),
        convertImageToShp: () => ({ success: false, message: '测试模式' }),
        convertImageToBfobjShp: () => ({ success: false, message: '测试模式' }),
        exportShpToPng: () => ({ success: false, message: '测试模式' }),
        faceStats: () => ({ success: true, stats: {} }),
        // 新增操作
        newSoldier: () => ({ success: false, message: '测试模式', data: null }),
        newThing: () => ({ success: false, message: '测试模式', data: null }),
        // PCK
        pckDetect: () => ({ success: true, state: 'empty', has_setting: false, ini_count: 0, pck_files: [], recommendations: [] }),
        pckGetSettingStatus: () => ({ success: true, exists: false, path: '', file_count: 0, files: [], subdirs: [] }),
        pckExtractAll: () => ({ success: false, message: '测试模式不支持提取' }),
        pckListFiles: () => ({ success: true, files: [] }),
        pckExtractFile: () => ({ success: false, message: '测试模式' }),
        pckPrepareSetting: () => ({ success: false, message: '测试模式' }),
        pckGetInfo: () => ({ success: true, magic: '', file_count: 0 }),
        // OBD
        obdLoad: () => ({ success: true, data: [], count: 0 }),
        obdSave: () => ({ success: false, message: '测试模式' }),
        obdNewObject: () => ({ success: false, message: '测试模式' }),
        obdGetInfo: () => ({ success: true, supported_types: ['bfsoldier', 'bfgen', 'bfevent', 'bfspec', 'bfweapon', 'bfhorse', 'bfweaponlight', 'bfsoldierweapon', 'bfgenweapon', 'bfmagic', 'bfskill', 'bfmagic2', 'bfskill2', 'bfmagic3', 'bfskill3', 'bfmagic4', 'bfskill4', 'bfmagic5', 'bfskill5', 'bfobject', 'bfbase', 'bftest', 'sfgen', 'sfevent', 'sfship', 'sfobject', 'sfbase', 'sftest'] }),
        obdPreviewSpriteFrame: () => ({ success: false, message: '测试模式' }),
        obdListSpriteFrames: () => ({ success: true, sequence: 0, name: '', actions: {} }),
        // Matrix
        matrixGet: () => ({ success: true, matrix: [], soldiers: [], size: 0 }),
        matrixUpdate: () => ({ success: false, message: '测试模式' }),
        matrixGetSoldiers: () => ({ success: true, data: [], count: 0 }),
        matrixLoad: () => ({ success: true, message: '测试模式' }),
        // Save
        saveList: () => ({ success: true, saves: [], count: 0 }),
        saveLoad: () => ({ success: false, message: '测试模式' }),
        saveBackup: () => ({ success: false, message: '测试模式' }),
        saveGetInfo: () => ({ success: true }),
        // Wizard
        wizardTemplates: () => ({ success: true, templates: [] }),
        wizardStart: () => ({ success: false, message: '测试模式' }),
        wizardStep: () => ({ success: true }),
        wizardProgress: () => ({ success: true, pct: '0%' }),
        wizardDependencies: () => ({ success: true, required: [], optional: [] }),
        // CitySell / GameText
        loadCitySellItems: () => ({ success: true, data: [], count: 0 }),
        saveCitySellItems: () => ({ success: false, message: '测试模式' }),
        loadGameText: () => ({ success: true, sections: [], count: 0 }),
        saveGameText: () => ({ success: false, message: '测试模式' }),
        listScripts: () => ({ success: true, files: [], count: 0 }),
        readScript: () => ({ success: false, message: '测试模式', content: '', lines: 0 }),
        saveScript: () => ({ success: false, message: '测试模式' }),
        getSchema: () => ({ success: true, data: {} }),
        obdGetSprites: () => ({ success: true, sprites: [] }),
        obdUpdateSprites: () => ({ success: false, message: '测试模式' }),
        shapePckExtract: () => ({ success: false, message: '测试模式' }),
        shapePckExtractAll: () => ({ success: false, message: '测试模式' }),
        shapePckRepack: () => ({ success: false, message: '测试模式' }),
        selectSavePath: () => ({ success: false, message: '测试模式' }),
        searchGlobalParams: () => ({ success: true, data: [] }),
        // 备份/校验
        backupAll: () => ({ success: false, message: '测试模式', backup_id: '', saved: 0 }),
        restoreAll: () => ({ success: false, message: '测试模式', restored: 0 }),
        validateAll: () => ({ success: true, total: 0, errors: 0, warnings: 0, infos: 0, results: [] }),
        // CSV
        csvExport: () => ({ success: false, message: '测试模式不支持导出' }),
        csvImport: () => ({ success: false, message: '请在PyWebView环境中运行' }),
        csvConfirmImport: () => ({ success: false, message: '测试模式' }),
        csvGetFields: () => ({ success: true, data: [] }),
        // 头像批量
        facePreview: () => ({ success: true, previews: [], total_found: 0 }),
        faceDelete: () => ({ success: false, message: '测试模式' }),
        faceBatchExport: () => ({ success: false, message: '测试模式' }),
        // Shape资源浏览
        listBfobjShps: () => ({ success: true, files: [] }),
        previewBfobjShp: () => ({ success: false, message: '测试模式' }),
        listGenhalfShps: () => ({ success: true, files: [] }),
        previewGenhalfShp: () => ({ success: false, message: '测试模式' }),
        importImageToGenhalf: () => ({ success: false, message: '测试模式' }),
        browseShapeResources: () => ({ success: true, categories: { Face: { exists: false, files: [], count: 0 }, BFObj: { exists: false, files: [], count: 0 }, genhalf: { exists: false, files: [], count: 0 } } }),
        shapeResourceStats: () => ({ success: true, total_files: 0, total_size_mb: 0, categories: {} }),
        shapeThumbnails: () => ({ success: true, thumbnails: {} }),
        shapeBatchDelete: () => ({ success: false, message: '测试模式' }),
        shapeBatchExport: () => ({ success: false, message: '测试模式' }),
        effectGetAll: () => ({
            success: true,
            ball_types: [{id:0,name:'默认',desc:'无弹道',visual:'●',color:'#888'}],
            damage_types: [{id:0,name:'物理',desc:'物理伤害',icon:'⚔'}],
            element_types: [{id:0,name:'无',desc:'无属性',visual:'○',color:'#888'}],
            item_scripts: [{id:0,name:'无',desc:'无特效',weapon_example:'—'}],
            weapon_glow: {desc:'测试模式',steps:[],note:''},
            atk_types: [{id:0,name:'单体',desc:'单体攻击',icon:'⚔'}],
        }),
        effectBallTypes: () => ({ success: true, data: [], count: 0 }),
        effectDamageTypes: () => ({ success: true, data: [], count: 0 }),
        effectElementTypes: () => ({ success: true, data: [], count: 0 }),
        effectItemScripts: () => ({ success: true, data: [], count: 0 }),
        effectWeaponGlow: () => ({ success: true, data: {desc:'',steps:[],note:''} }),
        effectAtkTypes: () => ({ success: true, data: [], count: 0 }),
        effectCrossRef: () => ({ success: true, refs: {ball:{},damage:{},atk:{},script_no:{},bfw_res_id:{}}, counts: {ball:{},damage:{},atk:{},script_no:{},bfw_res_id:{}} }),
        // 存档管理 (SaveManager)
        saveList: () => ({ success: true, saves: [], count: 0 }),
        saveBackup: () => ({ success: false, message: '测试模式' }),
        saveRestore: () => ({ success: false, message: '测试模式' }),
        saveListBackups: () => ({ success: true, backups: [], count: 0 }),
        saveDeleteBackup: () => ({ success: false, message: '测试模式' }),
        saveHexView: () => ({ success: true, hex_dump: '', file_size: 0 }),
        saveAnalyze: () => ({ success: true, format: '未知', file_size: 0 }),
        // PCK
        pckRepack: () => ({ success: false, message: '测试模式不支持打包' }),
        // 版本检测
        detectGameVersion: () => ({ success: false, message: '请在PyWebView环境中运行' }),
        // Wizard
        wizardGetSample: () => ({ success: true, data: { name: '', data: {}, notes: '' } }),
        wizardCreateGeneral: () => ({ success: false, message: '测试模式不支持创建' }),
        wizardCreateSoldier: () => ({ success: false, message: '测试模式不支持创建' }),
        customLeaderLoad: () => ({ success: true, leaders: [], count: 0 }),
        customLeaderSave: () => ({ success: false, message: '测试模式' }),
        // 存档编辑
        saveEditCustomGen: () => ({ success: false, message: '测试模式' }),
        saveHexView: () => ({ success: true, hex_lines: [], total_size: 0 }),
        saveHexSearch: () => ({ success: true, match_count: 0, positions: [] }),
        saveCloneGeneral: () => ({ success: false, message: '测试模式' }),
        // SG7 存档解析
        saveParseGenerals: () => ({ success: true, generals: [], count: 0 }),
        saveEditStat: () => ({ success: false, message: '测试模式不支持写入' }),
        saveEditMerit: () => ({ success: false, message: '测试模式不支持写入' }),
        saveEditExp: () => ({ success: false, message: '测试模式不支持写入' }),
        saveEditSoldier: () => ({ success: false, message: '测试模式不支持写入' }),
        saveEditWeaponExp: () => ({ success: false, message: '测试模式不支持写入' }),
        saveGetSoldierTypes: () => ({ success: true, soldiers: [] }),
        // SG7 结构化编辑
        saveGetStructuredGeneral: () => ({ success: false, message: '测试模式' }),
        saveWriteEquipment: () => ({ success: false, message: '测试模式不支持写入' }),
        saveWriteSkills: () => ({ success: false, message: '测试模式不支持写入' }),
        saveWriteSoldierCount: () => ({ success: false, message: '测试模式不支持写入' }),
        saveWriteFormation: () => ({ success: false, message: '测试模式不支持写入' }),
        saveGetWeaponNames: () => ({ success: true, weapons: [] }),
        saveGetHorseNames: () => ({ success: true, horses: [] }),
        saveGetItemNames: () => ({ success: true, items: [] }),
        saveGetFormationNames: () => ({ success: true, formations: [] }),
        // Script.so 分析
        scriptsoInfo: () => ({ success: true, exists: false, path: '' }),
        scriptsoStrings: () => ({ success: true, total_strings: 0, patterns: {} }),
        scriptsoHexView: () => ({ success: true, hex_lines: [], total_size: 0 }),
        scriptsoHexSearch: () => ({ success: true, match_count: 0, positions: [] }),
        scriptsoListFiles: () => ({ success: true, files: [], count: 0 }),
        scriptsoBackup: () => ({ success: false, message: '测试模式' }),
        scriptsoHexWrite: () => ({ success: false, message: '测试模式不支持写入' }),
        scriptsoHexPatch: () => ({ success: false, message: '测试模式不支持补丁' }),
        scriptsoStringReplace: () => ({ success: false, message: '测试模式不支持替换' }),
        scriptsoSections: () => ({ success: false, message: '请在PyWebView环境中运行' }),
        scriptsoSymbols: () => ({ success: false, message: '请在PyWebView环境中运行' }),
        scriptsoGetPatches: () => ({ success: true, patches: [], count: 0 }),
        scriptsoSearchPatch: () => ({ success: true, candidates: [] }),
        scriptsoApplyPatch: () => ({ success: false, message: '测试模式不支持应用补丁' }),
        scriptsoCommunityPatches: () => ({ success: true, categories: [], count: 0 }),
        scriptsoApplyCommunityPatch: () => ({ success: false, message: '测试模式' }),
        scriptsoDisassemble: () => ({ success: false, message: '请在PyWebView环境中运行' }),
        scriptsoFindFunctions: () => ({ success: false, message: '请在PyWebView环境中运行' }),
        scriptsoDisasmFunc: () => ({ success: false, message: '请在PyWebView环境中运行' }),
        scriptsoFindXrefs: () => ({ success: false, message: '请在PyWebView环境中运行' }),
        scriptsoInstructionPatch: () => ({ success: false, message: '请在PyWebView环境中运行' }),
        nationLinkageCheck: () => ({ success: true, data: { linked: false } }),
        nationLinkageCreate: () => ({ success: false, message: '测试模式不支持联动' }),
        loadFormat: () => ({ success: true, data: [], count: 0 }),
        saveFormat: () => ({ success: false, message: '测试模式' }),
        newFormat: () => ({ success: true, data: { No: 0, Name: '新阵型', Atk: 0, Def: 0, Speed: 0, Range: 0, IsUsed: 1 } }),
        loadChessFormat: () => ({ success: true, data: [], count: 0 }),
        saveChessFormat: () => ({ success: false, message: '测试模式' }),
        newChessFormat: () => ({ success: true, data: { No: 0, Name: '新阵法', Grid: '', Width: 5, Height: 5, IsUsed: 1 } }),
        // MOD 安装/卸载
        installMod: () => ({ success: false, message: '测试模式不支持安装' }),
        uninstallMod: () => ({ success: false, message: '测试模式不支持卸载' }),
        listInstalledMods: () => ({ success: true, mods: {} }),
        getSango7Config: () => ({ success: true, config: { width: 1024, height: 768, fullscreen: 1 } }),
        setSango7Config: () => ({ success: false, message: '测试模式不支持保存' }),
        // 编码转换
        encodingScan: () => ({ success: true, total: 0, gbk_count: 0, big5_count: 0, files: [] }),
        encodingPreview: () => ({ success: true, preview: [] }),
        encodingConvertFile: () => ({ success: false, message: '测试模式' }),
        encodingBatchConvert: () => ({ success: false, message: '测试模式' }),
        // 剧情事件
        eventTemplates: () => ({ success: true, templates: {} }),
        eventGenerate: () => ({ success: true, ini_text: '', message: '测试模式' }),
        // MPC地形
        mpcRead: () => ({ success: false, message: '请在PyWebView环境中运行' }),
        mpcWrite: () => ({ success: false, message: '测试模式' }),
        mpcBatchWrite: () => ({ success: false, message: '测试模式' }),
        // Shape位移
        shapeInfoList: () => ({ success: true, infos: [], count: 0, categories: [] }),
        shapeInfoSave: () => ({ success: false, message: '测试模式' }),
        // CustomGen
        customgenList: () => ({ success: true, generals: [], count: 0 }),
        customgenGet: () => ({ success: false, message: '测试模式' }),
        customgenEdit: () => ({ success: false, message: '测试模式' }),
        // 内存预设
        memoryPresets: () => ({ success: true, presets: {}, count: 0 }),
        memoryReadPreset: () => ({ success: false, message: '测试模式' }),
        // SHP改名
        shpBatchRename: () => ({ success: false, message: '测试模式' }),
        shpSelectDir: () => ({ success: true, path: '' }),
        // 城池连线
        cityConnections: () => ({ success: true, cities: {}, positions: {}, map_size: [17472, 12384] }),
        // id.ini
        loadIdini: () => ({ success: true, data: [], count: 0 }),
        saveIdini: () => ({ success: false, message: '测试模式' }),
    };
    return mocks[method] ? mocks[method](...args) : { success: false, message: `未知方法: ${method}` };
}

// ============================================================
// 导航切换
// ============================================================

// 编辑器与tab的映射：tab -> { editorId, editorObj }
// 全局未保存变更追踪
const _unsavedChanges = new Set();
let _currentTabId = null;

function markUnsaved(tabId) {
    if (tabId) _unsavedChanges.add(tabId);
}

function clearUnsaved(tabId) {
    if (tabId) _unsavedChanges.delete(tabId);
}

function hasUnsavedChanges() {
    return _unsavedChanges.size > 0;
}

/**
 * 自动追踪编辑器的 changed/_dirty 属性，关联到指定 tab 的未保存状态
 * 使用 Object.defineProperty 拦截 setter，无需修改每个编辑器内部代码
 */
function watchEditor(editor, tabId) {
    if (!editor || typeof editor !== 'object') return;
    const propName = '_dirty' in editor ? '_dirty' : 'changed';
    let _val = editor[propName];
    Object.defineProperty(editor, propName, {
        get() { return _val; },
        set(v) {
            _val = v;
            if (v) markUnsaved(tabId);
            else clearUnsaved(tabId);
        },
        configurable: true,
        enumerable: true
    });
    // 同时劫持 changed（如果不同），确保 setter 触发
    if (propName === '_dirty' && 'changed' in editor) {
        let _ch = editor.changed;
        Object.defineProperty(editor, 'changed', {
            get() { return _ch; },
            set(v) {
                _ch = v;
                if (v) markUnsaved(tabId);
                else clearUnsaved(tabId);
            },
            configurable: true,
            enumerable: true
        });
    }
    // 初始状态同步
    if (_val) markUnsaved(tabId);
}

// beforeunload 未保存修改警告
window.addEventListener('beforeunload', (e) => {
    if (hasUnsavedChanges()) {
        e.preventDefault();
        e.returnValue = '有未保存的修改，确定要离开吗？';
    }
});

const _editorTabMap = {
    'generals':    { editorId: 'generals',    obj: null },
    'soldiers':    { editorId: 'soldiers',    obj: null },
    'things':      { editorId: 'things',      obj: null },
    'skills':      { editorId: 'skills',      obj: null },
    'superatk':    { editorId: 'superatk',    obj: null },
    'effectEditor': { editorId: 'effectEditor', obj: null },
    'genSkills':   { editorId: 'genSkills',   obj: null },
    'formation':   { editorId: 'formation',   obj: null },
    'title':       { editorId: 'title',       obj: null },
    'scenario':    { editorId: 'scenario',    obj: null },
    'nation':      { editorId: 'nation',      obj: null },
    'city':        { editorId: 'city',        obj: null },
    'cityPeriod':  { editorId: 'cityPeriod',  obj: null },
    'defskill':    { editorId: 'defskill',    obj: null },
    'general02':   { editorId: 'general02',   obj: null },
    'genLv':       { editorId: 'genLv',       obj: null },
    'age':         { editorId: 'age',         obj: null },
    'termText':    { editorId: 'termText',    obj: null },
    'citySell':    { editorId: 'citySell',    obj: null },
    'gameText':    { editorId: 'gameText',    obj: null },
    // 通用INI编辑器
    'bffront':       { editorId: 'bffront',       obj: null },
    'dialogue':      { editorId: 'dialogue',      obj: null },
    'color':         { editorId: 'color',         obj: null },
    'citypos':       { editorId: 'citypos',       obj: null },
    'terrain':       { editorId: 'terrain',       obj: null },
    'systemtext':    { editorId: 'systemtext',    obj: null },
    'gossiptext':    { editorId: 'gossiptext',    obj: null },
    'extraterrain':  { editorId: 'extraterrain',  obj: null },
    'formatoffsetpos': { editorId: 'formatoffsetpos', obj: null },
    'buildingpos':   { editorId: 'buildingpos',   obj: null },
    'sfbridge':      { editorId: 'sfbridge',      obj: null },
    'mapvis':        { editorId: 'mapvis',        obj: null },
    'sfroadblock':   { editorId: 'sfroadblock',   obj: null },
    'sfroadblockpos': { editorId: 'sfroadblockpos', obj: null },
    'var':           { editorId: 'var',           obj: null },
    'font':          { editorId: 'font',          obj: null },
    'systemini':     { editorId: 'systemini',     obj: null },
    'format':        { editorId: 'format',        obj: null },
    'chessformat':   { editorId: 'chessformat',   obj: null },
    'variableEditor': { editorId: 'variableEditor', obj: null },
    'sango7Editor':   { editorId: 'sango7Editor',   obj: null },
    'shape':         { editorId: 'shape',         obj: null },
    // 存档管理
    'savemgr':       { editorId: 'savemgr',       obj: null },
    // 其他重要编辑器
    'history':       { editorId: 'history',       obj: null },
    'obd':           { editorId: 'obd',           obj: null },
    'matrix':        { editorId: 'matrix',        obj: null },
    'encoding':    { editorId: 'encoding',    obj: null },
    'eventEditor': { editorId: 'eventEditor', obj: null },
    'csvtools':    { editorId: 'csvtools',    obj: null },
    // 工具类（无独立编辑器对象，占位）
    // @deprecated: dead mappings, no HTML nav-item
    // 'storeConfig': { editorId: 'storeConfig', obj: null },
    // 'crafting': { editorId: 'crafting', obj: null },
    'uisubs': { editorId: 'uisubs', obj: null },
    'uisubsystem': { editorId: 'uisubsystem', obj: null },  // alias for uisubs (HTML tab name)
    'idini': { editorId: 'idini', obj: null },
    'configext': { editorId: 'configext', obj: null },
    'resolutionpresets': { editorId: 'resolutionpresets', obj: null },
    'bmp2raw': { editorId: 'bmp2raw', obj: null },
    'mpc': { editorId: 'mpc', obj: null },
    'shapeinfo': { editorId: 'shapeinfo', obj: null },
    'shprename': { editorId: 'shprename', obj: null },
    'cityconnect': { editorId: 'cityconnect', obj: null },
    'customgen': { editorId: 'customgen', obj: null },
    'script': { editorId: 'script', obj: null },
    // 编辑器映射（带独立编辑器对象）
    'mapeditor': { editorId: 'mapeditor', obj: null },
    'memoryeditor': { editorId: 'memoryeditor', obj: null },
    'saveEditor': { editorId: 'saveEditor', obj: null },
    'scriptso': { editorId: 'scriptso', obj: null },
};

/** 初始化编辑器引用（在编辑器对象定义后调用） */
function initEditorTabMap() {
    _editorTabMap['generals'].obj = generals;
    _editorTabMap['soldiers'].obj = soldiers;
    _editorTabMap['things'].obj = things;
    _editorTabMap['skills'].obj = skillEditor;
    _editorTabMap['superatk'].obj = superAtkEditor;
    _editorTabMap['effectEditor'].obj = (typeof effectEditor !== 'undefined') ? effectEditor : null;
    _editorTabMap['genSkills'].obj = genSkillEditor;
    _editorTabMap['formation'].obj = formationEditor;
    _editorTabMap['title'].obj = titleEditor;
    _editorTabMap['scenario'].obj = scenarioEditor;
    _editorTabMap['nation'].obj = nationEditor;
    _editorTabMap['city'].obj = (typeof cityEditor !== 'undefined') ? cityEditor : null;
    _editorTabMap['cityPeriod'].obj = (typeof cityPeriodEditor !== 'undefined') ? cityPeriodEditor : null;
    _editorTabMap['defskill'].obj = (typeof defskill !== 'undefined') ? defskill : null;
    _editorTabMap['general02'].obj = (typeof general02Editor !== 'undefined') ? general02Editor : null;
    _editorTabMap['genLv'].obj = (typeof genLvEditor !== 'undefined') ? genLvEditor : null;
    _editorTabMap['age'].obj = (typeof ageEditor !== 'undefined') ? ageEditor : null;
    _editorTabMap['termText'].obj = (typeof termTextEditor !== 'undefined') ? termTextEditor : null;
    _editorTabMap['citySell'].obj = (typeof citySellEditor !== 'undefined') ? citySellEditor : null;
    _editorTabMap['gameText'].obj = (typeof gameTextEditor !== 'undefined') ? gameTextEditor : null;
    // 通用INI编辑器
    _editorTabMap['bffront'].obj = (typeof bffrontEditor !== 'undefined') ? bffrontEditor : null;
    _editorTabMap['dialogue'].obj = (typeof dialogueEditor !== 'undefined') ? dialogueEditor : null;
    _editorTabMap['color'].obj = (typeof colorEditor !== 'undefined') ? colorEditor : null;
    _editorTabMap['citypos'].obj = (typeof cityposEditor !== 'undefined') ? cityposEditor : null;
    _editorTabMap['terrain'].obj = (typeof terrainEditor !== 'undefined') ? terrainEditor : null;
    _editorTabMap['systemtext'].obj = (typeof systemtextEditor !== 'undefined') ? systemtextEditor : null;
    _editorTabMap['gossiptext'].obj = (typeof gossiptextEditor !== 'undefined') ? gossiptextEditor : null;
    _editorTabMap['extraterrain'].obj = (typeof extraterrainEditor !== 'undefined') ? extraterrainEditor : null;
    _editorTabMap['formatoffsetpos'].obj = (typeof formatoffsetposEditor !== 'undefined') ? formatoffsetposEditor : null;
    _editorTabMap['buildingpos'].obj = (typeof buildingposEditor !== 'undefined') ? buildingposEditor : null;
    _editorTabMap['sfbridge'].obj = (typeof sfbridgeEditor !== 'undefined') ? sfbridgeEditor : null;
    _editorTabMap['mapvis'].obj = (typeof mapVisEditor !== 'undefined') ? mapVisEditor : null;
    _editorTabMap['sfroadblock'].obj = (typeof sfroadblockEditor !== 'undefined') ? sfroadblockEditor : null;
    _editorTabMap['sfroadblockpos'].obj = (typeof sfroadblockposEditor !== 'undefined') ? sfroadblockposEditor : null;
    _editorTabMap['var'].obj = (typeof varEditor !== 'undefined') ? varEditor : null;
    _editorTabMap['font'].obj = (typeof fontEditor !== 'undefined') ? fontEditor : null;
    _editorTabMap['systemini'].obj = (typeof systeminiEditor !== 'undefined') ? systeminiEditor : null;
    _editorTabMap['format'].obj = (typeof formatEditor !== 'undefined') ? formatEditor : null;
    _editorTabMap['chessformat'].obj = (typeof chessformatEditor !== 'undefined') ? chessformatEditor : null;
    _editorTabMap['variableEditor'].obj = (typeof variableEditor !== 'undefined') ? variableEditor : globalParams;
    _editorTabMap['sango7Editor'].obj = (typeof sango7Editor !== 'undefined') ? sango7Editor : null;
    // @deprecated: dead mappings, commented out
    // _editorTabMap['storeConfig'].obj = (typeof storeConfig !== 'undefined') ? storeConfig : null;
    // _editorTabMap['crafting'].obj = (typeof crafting !== 'undefined') ? crafting : null;
    _editorTabMap['shape'].obj = (typeof shapeBrowser !== 'undefined') ? shapeBrowser : null;
    // 存档管理
    _editorTabMap['savemgr'].obj = (typeof saveMgr !== 'undefined') ? saveMgr : null;
    // 其他重要编辑器
    _editorTabMap['history'].obj = (typeof historyEditor !== 'undefined') ? historyEditor : null;
    _editorTabMap['obd'].obj = (typeof obdEditor !== 'undefined') ? obdEditor : null;
    _editorTabMap['matrix'].obj = (typeof matrixEditor !== 'undefined') ? matrixEditor : null;
    _editorTabMap['encoding'].obj = (typeof encodingConverter !== 'undefined') ? encodingConverter : null;
    _editorTabMap['eventEditor'].obj = (typeof eventEditor !== 'undefined') ? eventEditor : null;
    _editorTabMap['uisubs'].obj = (typeof uisubsystemEditor !== 'undefined') ? uisubsystemEditor : { changed: false };
    _editorTabMap['uisubsystem'].obj = _editorTabMap['uisubs'].obj;  // alias
    _editorTabMap['idini'].obj = (typeof idiniEditor !== 'undefined') ? idiniEditor : { changed: false };
    _editorTabMap['configext'].obj = (typeof configextEditor !== 'undefined') ? configextEditor : { changed: false };
    _editorTabMap['resolutionpresets'].obj = (typeof resolutionPresets !== 'undefined') ? resolutionPresets : { changed: false };
    _editorTabMap['bmp2raw'].obj = (typeof bmp2rawEditor !== 'undefined') ? bmp2rawEditor : { changed: false };
    _editorTabMap['mpc'].obj = (typeof mpcEditor !== 'undefined') ? mpcEditor : { changed: false };
    _editorTabMap['shapeinfo'].obj = (typeof shapeInfoEditor !== 'undefined') ? shapeInfoEditor : { changed: false };
    _editorTabMap['shprename'].obj = (typeof shpRenameTool !== 'undefined') ? shpRenameTool : { changed: false };
    _editorTabMap['cityconnect'].obj = (typeof cityconnectEditor !== 'undefined') ? cityconnectEditor : { changed: false };
    _editorTabMap['csvtools'].obj = (typeof csvTools !== 'undefined') ? csvTools : { changed: false };
    _editorTabMap['surnameEditor'].obj = (typeof surnameEditor !== 'undefined') ? surnameEditor : { changed: false };
    _editorTabMap['customgen'].obj = (typeof customgenEditor !== 'undefined') ? customgenEditor : { changed: false };
    _editorTabMap['customleader'].obj = (typeof customLeaderEditor !== 'undefined') ? customLeaderEditor : { changed: false };
    _editorTabMap['script'].obj = (typeof scriptEditor !== 'undefined') ? scriptEditor : { changed: false };
    // 编辑器映射（带独立编辑器对象）
    _editorTabMap['mapeditor'].obj = (typeof mapEditor !== 'undefined') ? mapEditor : null;
    _editorTabMap['memoryeditor'].obj = (typeof memoryEditor !== 'undefined') ? memoryEditor : null;
    _editorTabMap['saveEditor'].obj = (typeof saveEditor !== 'undefined') ? saveEditor : null;
    _editorTabMap['scriptso'].obj = (typeof scriptsoEditor !== 'undefined') ? scriptsoEditor : null;
}

document.addEventListener('DOMContentLoaded', () => {
    // 初始化编辑器映射
    initEditorTabMap();

    // 自动追踪所有编辑器的 changed 属性，关联到对应 tab 的未保存状态
    for (const [tabId, mapping] of Object.entries(_editorTabMap)) {
        if (mapping.obj && mapping.obj.changed !== undefined) {
            watchEditor(mapping.obj, tabId);
        }
    }

    // 导航点击
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const tabId = item.dataset.tab;
            // 切换标签页时检查未保存变更
            if (_currentTabId && _currentTabId !== tabId && _unsavedChanges.has(_currentTabId)) {
                if (!confirm('当前页面有未保存的修改，确定要切换吗？')) {
                    return;
                }
                _unsavedChanges.delete(_currentTabId);
            }
            _currentTabId = tabId;
            document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            const target = document.getElementById(tabId);
            if (target) target.classList.add('active');

            // 自动展开该导航项所在的分类
            const cat = item.closest('.nav-category');
            if (cat && cat.classList.contains('collapsed')) {
                cat.classList.remove('collapsed');
                const arrow = cat.querySelector('.nav-category-arrow');
                if (arrow) arrow.textContent = '▼';
            }

            // 激活对应编辑器的撤销/重做支持
            const mapping = _editorTabMap[tabId];
            if (mapping && mapping.obj && typeof mapping.obj.snapshot === 'function') {
                setActiveEditor(mapping.editorId,
                    () => mapping.obj.snapshot(),
                    (data) => mapping.obj.restoreSnapshot(data)
                );
            } else {
                _activeEditorId = null;
            }

            // 显示/隐藏参考面板
            const thingTypePanel = document.getElementById('thingTypeRefPanel');
            const crossRefPanel = document.getElementById('crossRefPanel');
            const termSegPanel = document.getElementById('termTextSegPanel');
            if (thingTypePanel) thingTypePanel.style.display = (tabId === 'things') ? 'block' : 'none';
            if (crossRefPanel) crossRefPanel.style.display = (tabId === 'refcheck') ? 'block' : 'none';
            if (termSegPanel) termSegPanel.style.display = (tabId === 'gameText') ? 'block' : 'none';
        });
        // 键盘可访问性
        item.setAttribute('tabindex', '0');
        item.setAttribute('role', 'button');
        item.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                item.click();
            }
        });
    });

    // 初始化
    loadProgress();
    dashboard.refresh();
    updateGameStatus();
    backup.loadHistory();
    exepatch.loadInfo();
    mods.refreshList();

    // 标签切换时自动刷新
    document.querySelectorAll('[data-tab="home"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{loadProgress();dashboard.refresh();},100)));
    document.querySelectorAll('[data-tab="backup"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>backup.loadHistory(),100)));
    document.querySelectorAll('[data-tab="exepatch"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>exepatch.loadInfo(),100)));
    document.querySelectorAll('[data-tab="mods"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>mods.refreshList(),100)));
});

// ============================================================
// 首页 - 开发进度
// ============================================================

async function loadProgress() {
    const progress = await pyApi('getProgress');
    if (!progress || !progress.milestones) {
        console.warn('loadProgress: 获取进度数据失败');
        return;
    }
    let doneCount = 0;
    let totalProgress = 0;

    const container = document.getElementById('milestonesList');
    if (!container) return;
    container.innerHTML = '';

    const milestones = progress.milestones || [];
    milestones.forEach(m => {
        totalProgress += m.progress || 0;
        if (m.status === 'completed') doneCount++;

        const item = document.createElement('div');
        item.className = 'milestone-item';
        const statusLabel = m.status === 'completed' ? '已完成' : (m.status === 'in_progress' ? '开发中' : '待开发');
        const tasks = m.tasks || [];
        item.innerHTML = `
            <div class="milestone-header">
                <span class="milestone-name">${m.id}. ${m.name}</span>
                <span class="milestone-status ${m.status}">${statusLabel}</span>
            </div>
            <div class="milestone-progress">
                <div class="milestone-progress-fill" style="width: ${m.progress}%"></div>
            </div>
            <div class="milestone-tasks">
                ${tasks.map(t => `<div class="task-item ${t.done ? 'done' : 'not-done'}">${t.name}</div>`).join('')}
            </div>
        `;
        container.appendChild(item);
    });

    const overall = milestones.length > 0 ? Math.round(totalProgress / milestones.length) : 0;
    const elOverall = document.getElementById('overallProgress');
    const elOverallText = document.getElementById('overallProgressText');
    const elVersion = document.getElementById('versionNumber');
    const elDone = document.getElementById('doneMilestones');
    const elTotal = document.getElementById('totalMilestones');

    if (elOverall) elOverall.style.width = overall + '%';
    if (elOverallText) elOverallText.textContent = overall + '%';
    if (elVersion) elVersion.textContent = progress.version || '2.1';
    if (elDone) elDone.textContent = doneCount;
    if (elTotal) elTotal.textContent = milestones.length;

    const issues = document.getElementById('knownIssues');
    if (issues) {
        issues.innerHTML = (progress.known_issues || []).map(i => `<li>${i}</li>`).join('');
    }
}

// ============================================================
// 游戏目录配置
// ============================================================

async function selectGamePath() {
    const res = await pyApi('setGamePath');
    if (res.success) {
        await updateGameStatus();
        showToast(res.message, res && res.success ? 'success' : 'error');
    } else if (res.message) {
        showToast(res.message, res && res.success ? 'success' : 'error');
    }
}

async function updateGameStatus() {
    const info = await pyApi('getGameInfo');
    if (!info) { console.warn('updateGameStatus: 获取游戏信息失败'); return; }
    const elInput = document.getElementById('gamePathInput');
    const elDot = document.getElementById('statusDot');
    const elText = document.getElementById('statusText');

    if (elInput) elInput.value = info.game_path || '';

    if (info.configured && info.has_setting) {
        if (elDot) elDot.classList.add('ready');
        if (elText) elText.textContent = '就绪';
    } else {
        if (elDot) elDot.classList.remove('ready');
        if (elText) elText.textContent = '未配置游戏目录';
    }

    const checks = {
        checkSetting: info.has_setting ? '正常' : '未检测到',
        checkFace: info.has_face ? '正常' : '未检测到',
        checkExe: info.has_exe ? '正常' : '未检测到',
    };
    Object.entries(checks).forEach(([id, text]) => {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = (text === '正常' ? '✅ ' : '❌ ') + text;
        }
    });

    const recent = info.recent_paths || [];
    const list = document.getElementById('recentList');
    if (list) {
        if (recent.length === 0) {
            list.innerHTML = '<li class="empty">暂无</li>';
        } else {
            list.innerHTML = recent.map(p => {
                const escaped = p.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                return `<li onclick="document.getElementById('gamePathInput').value='${escaped}'">${p}</li>`;
            }).join('');
        }
    }
}

// ============================================================
// 武将编辑模块
// ============================================================

const generals = {
    data: [],
    currentIndex: -1,
    current: null,
    changed: false,
    _pageSize: 50,
    _currentPage: 0,
    _searchKeyword: '',

    async load() {
        const res = await pyApi('loadGenerals');
        if (!res.success) {
            showToast(res.message, res && res.success ? 'success' : 'error');
            return;
        }
        this.data = res.data || [];
        this.currentIndex = -1; this.current = null;
        this._currentPage = 0;
        this._searchKeyword = '';
        this.renderList();
        const el = document.getElementById('generalCount');
        if (el) el.textContent = this.data.length;
        setupTooltips('general', 'g_');
    },

    snapshot() { return JSON.parse(JSON.stringify(this.data)); },
    restoreSnapshot(data) { this.data = data; this.currentIndex = -1; this.current = null; this.renderList(); this.changed = false; },
    pushUndo() { UndoManager.pushState('generals', this.snapshot()); },

    async save() {
        if (!(await validateBeforeSave())) return;
        if (this.current && this.changed) {
            this.saveCurrent();
        }
        const res = await pyApi('saveGenerals', this.data);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) this.changed = false;
    },

    _getFilteredData() {
        if (!this._searchKeyword) return this.data;
        const kw = this._searchKeyword.toLowerCase();
        return this.data.filter((g, idx) => {
            const name = (g.Name || '').toLowerCase();
            const no = String(g.No || '');
            return name.includes(kw) || no.includes(kw);
        });
    },

    renderList() {
        const container = document.getElementById('generalList');
        if (!container) return;
        container.innerHTML = '';
        const filtered = this._getFilteredData();
        const totalPages = Math.max(1, Math.ceil(filtered.length / this._pageSize));
        if (this._currentPage >= totalPages) this._currentPage = totalPages - 1;
        const start = this._currentPage * this._pageSize;
        const page = filtered.slice(start, start + this._pageSize);
        page.forEach((g) => {
            const idx = this.data.indexOf(g);
            const card = document.createElement('div');
            card.className = 'item-card' + (idx === this.currentIndex ? ' selected' : '');
            card.innerHTML = `
                <div class="item-card-header">
                    <span class="item-name">${g.Name || '无名'}</span>
                    <span class="item-no">#${g.No || ''}</span>
                </div>
                <div class="item-desc">武力 ${g.WStr || '-'} 智力 ${g.Int || '-'} 体力 ${g.HP || '-'}</div>
            `;
            card.onclick = () => this.select(idx);
            container.appendChild(card);
        });
        this._renderPagination(filtered);
    },

    _renderPagination(filtered) {
        const pg = document.getElementById('generalPagination');
        if (!pg) return;
        const totalPages = Math.max(1, Math.ceil(filtered.length / this._pageSize));
        let html = `<button onclick="generals._goPage(0)" ${this._currentPage === 0 ? 'disabled' : ''}>首页</button>
            <button onclick="generals._goPage(${this._currentPage - 1})" ${this._currentPage === 0 ? 'disabled' : ''}>上一页</button>
            <span>${this._currentPage + 1} / ${totalPages} 页</span>
            <button onclick="generals._goPage(${this._currentPage + 1})" ${this._currentPage >= totalPages - 1 ? 'disabled' : ''}>下一页</button>
            <button onclick="generals._goPage(${totalPages - 1})" ${this._currentPage >= totalPages - 1 ? 'disabled' : ''}>末页</button>`;
        pg.innerHTML = html;
    },

    _goPage(n) {
        const filtered = this._getFilteredData();
        const totalPages = Math.max(1, Math.ceil(filtered.length / this._pageSize));
        if (n < 0) n = 0;
        if (n >= totalPages) n = totalPages - 1;
        this._currentPage = n;
        this.renderList();
    },

    select(idx) {
        if (idx < 0 || idx >= this.data.length) return;
        if (this.current && this.changed) this.saveCurrent();
        this.currentIndex = idx;
        this.current = this.data[idx];
        this.renderDetail();
        this.renderList();
        if (_previewPanelType === 'general') updatePreviewPanel('general');
        this.changed = false;
        // 加载原版参考数据对比
        const no = parseInt(this.current.No);
        if (no) ReferenceData.showGeneralRef(no);
    },

    renderDetail() {
        const emptyEl = document.getElementById('emptyGeneralDetail');
        const detailEl = document.getElementById('generalDetailContent');
        if (!this.current) {
            if (emptyEl) emptyEl.style.display = 'flex';
            if (detailEl) detailEl.style.display = 'none';
            return;
        }
        if (emptyEl) emptyEl.style.display = 'none';
        if (detailEl) detailEl.style.display = 'block';

        for (const key in this.current) {
            const el = document.getElementById('g_' + key);
            if (el) {
                if (el.tagName === 'SELECT') {
                    el.value = String(this.current[key] || '');
                } else {
                    el.value = this.current[key] || '';
                }
            }
        }

        const relation = this.current.Relation || 0;
        const slider = document.getElementById('g_Relation_slider');
        if (slider) slider.value = relation;

        this.refreshFacePreview();
    },

    currentChanged() {
        this.changed = true;
    },

    saveCurrent() {
        if (!this.current) return;
        const fields = [
            'No', 'Name', 'FaceID', 'WStr', 'Int', 'HP', 'MP',
            'Morale', 'Loyal', 'Relation', 'Sex', 'Race', 'Weapon', 'Horse',
            'Formation', 'BFSoldier', 'BFSoldier1', 'BFSoldier2',
            'HorseSkill', 'Sword', 'Spear', 'Bow', 'Blade', 'Fan',
            'SuperSkill', 'SuperSkillExp', 'FRelation',
            'Father', 'Spouse', 'Lord', 'Respawn', 'IsFamous', 'Life',
            'ResID', 'stringID_FullName', 'stringID_SecondName',
            'stringID_FirstName', 'stringID_CallMySelf', 'stringID_Appellation',
            'DefaultTitle', 'IsEvent', 'ExtraType', 'EventType', 'OffsetZ', 'IsUsed'
        ];
        fields.forEach(key => {
            const el = document.getElementById('g_' + key);
            if (el) this.current[key] = el.value;
        });
    },

    async addNew() {
        this.pushUndo();
        const res = await pyApi('newGeneral');
        if (res.success) {
            this.data.push(res.data);
            this.changed = true;
            this.renderList();
            this.select(this.data.length - 1);
            const el = document.getElementById('generalCount');
            if (el) el.textContent = this.data.length;
        } else {
            showToast(res.message, res && res.success ? 'success' : 'error');
        }
    },

    async cloneCurrent() {
        if (!this.current) { showToast('请先选择一个武将', 'warning'); return; }
        this.pushUndo();
        const no = parseInt(this.current.No);
        const res = await pyApi('cloneGeneral', no);
        if (res.success) {
            this.data.push(res.data);
            this.changed = true;
            this.renderList();
            this.select(this.data.length - 1);
            const el = document.getElementById('generalCount');
            if (el) el.textContent = this.data.length;
        } else {
            showToast(res.message, res && res.success ? 'success' : 'error');
        }
    },

    async deleteCurrent() {
        if (!this.current) return;
        if (!confirm(`确认删除武将 "${this.current.Name}" #${this.current.No}?`)) return;
        this.pushUndo();
        const no = parseInt(this.current.No);
        // 调用后端删除
        const res = await pyApi('deleteGeneral', no);
        this.data = this.data.filter(g => parseInt(g.No) !== no);
        this.current = null;
        this.currentIndex = -1;
        this.changed = true;
        this.renderList();
        const el = document.getElementById('generalCount');
        if (el) el.textContent = this.data.length;
        const emptyEl = document.getElementById('emptyGeneralDetail');
        const detailEl = document.getElementById('generalDetailContent');
        if (emptyEl) emptyEl.style.display = 'flex';
        if (detailEl) detailEl.style.display = 'none';
    },

    async importThingIcon() {
        if (!this.current) { showToast('请先选择一个物品', 'warning'); return; }
        const iconId = parseInt(this.current.IconID) || 0;
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/png,image/jpeg';
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = async () => {
                try {
                    const r = await pyApi('convertImageToThingIcon', reader.result, iconId);
                    if (r && r.success) {
                        showToast(`图标已转换为 ThingIcon #${iconId}`, 'success');
                    } else {
                        showToast('转换失败: ' + (r ? r.message : '未知错误'), 'error');
                    }
                } catch(e) { showToast('转换失败: ' + e, 'error'); }
            };
            reader.readAsDataURL(file);
        };
        input.click();
    },

    // ============================================================
    // 批量修改技能特效字段
    // ============================================================
    _batchPreviewData: null,

    _toggleBatchModify() {
        const panel = document.getElementById('effBatchModify');
        if (panel.style.display === 'none' || !panel.style.display) {
            panel.style.display = 'block';
            panel.scrollIntoView({behavior:'smooth'});
            this._batchFieldChanged();
        } else {
            panel.style.display = 'none';
        }
    },

    _closeBatchModify() {
        document.getElementById('effBatchModify').style.display = 'none';
        document.getElementById('effBatchResult').innerHTML = '';
        this._batchPreviewData = null;
    },

    _batchFieldChanged() {
        const field = document.getElementById('effBatchField').value;
        // 根据字段填充值下拉框
        let data = [];
        if (field === 'Ball') data = this._catalogs ? (this._catalogs.ball_types || []) : [];
        else if (field === 'DamageType') data = this._catalogs ? (this._catalogs.damage_types || []) : [];
        else if (field === 'Element') data = this._catalogs ? (this._catalogs.element_types || []) : [];
        else if (field === 'Atk') data = this._catalogs ? (this._catalogs.atk_types || []) : [];

        const oldOpts = data.map(d => `<option value="${d.id}">${d.id} - ${d.name}</option>`).join('');
        const newOpts = data.map(d => `<option value="${d.id}">${d.id} - ${d.name}</option>`).join('');

        document.getElementById('effBatchOldVal').innerHTML = oldOpts;
        document.getElementById('effBatchNewVal').innerHTML = newOpts;
        document.getElementById('effBatchResult').innerHTML = '';
        this._batchPreviewData = null;
    },

    async _batchPreview() {
        const field = document.getElementById('effBatchField').value;
        const oldVal = parseInt(document.getElementById('effBatchOldVal').value);
        if (isNaN(oldVal)) { this._showToast('请选择当前值', 'error'); return; }

        try {
            const r = await pyApi('effectBatchPreview', {field: field, old_value: oldVal});
            const result = document.getElementById('effBatchResult');
            if (r && r.success) {
                const affected = r.affected || [];
                this._batchPreviewData = affected;
                if (affected.length === 0) {
                    result.innerHTML = '<div style="color:var(--text-muted);padding:8px;">没有匹配的技能</div>';
                } else {
                    let html = `<div style="font-weight:600;margin-bottom:6px;color:var(--warning);">将影响 ${affected.length} 个技能：</div>`;
                    html += '<div style="display:flex;flex-wrap:wrap;gap:4px;">';
                    affected.forEach(s => {
                        html += `<span style="background:var(--bg-hover);padding:3px 8px;border-radius:4px;font-size:12px;border:1px solid var(--border);">${escHtml(s.name)} (No.${s.no})</span>`;
                    });
                    html += '</div>';
                    result.innerHTML = html;
                }
            } else {
                result.innerHTML = `<div style="color:var(--danger);">${r ? r.message : '预览失败'}</div>`;
            }
        } catch (e) {
            this._showToast('预览失败: ' + e.message, 'error');
        }
    },

    async _batchExecute() {
        const field = document.getElementById('effBatchField').value;
        const oldVal = parseInt(document.getElementById('effBatchOldVal').value);
        const newVal = parseInt(document.getElementById('effBatchNewVal').value);
        if (isNaN(oldVal) || isNaN(newVal)) { this._showToast('请选择当前值和目标值', 'error'); return; }
        if (oldVal === newVal) { this._showToast('当前值和目标值相同，无需修改', 'error'); return; }

        // 先预览确认
        if (!this._batchPreviewData) {
            await this._batchPreview();
            if (!this._batchPreviewData || this._batchPreviewData.length === 0) return;
        }

        const count = this._batchPreviewData.length;
        if (!confirm(`确定要将 ${count} 个技能的 ${field} 字段从 ${oldVal} 修改为 ${newVal} 吗？\n\n此操作会自动备份，但仍建议谨慎操作。`)) return;

        try {
            const r = await pyApi('effectBatchModify', {field: field, old_value: oldVal, new_value: newVal});
            const result = document.getElementById('effBatchResult');
            if (r && r.success) {
                result.innerHTML = `<div style="color:var(--success);font-weight:600;">✅ ${r.message}</div>`;
                this._showToast(r.message);
                this._batchPreviewData = null;
                // 刷新交叉引用
                await this._loadCrossRef();
            } else {
                result.innerHTML = `<div style="color:var(--danger);">${r ? r.message : '修改失败'}</div>`;
            }
        } catch (e) {
            this._showToast('批量修改失败: ' + e.message, 'error');
        }
    },

    async exportThingIcon() {
        if (!this.current) { showToast('请先选择一个物品', 'warning'); return; }
        const iconId = parseInt(this.current.IconID) || 0;
        if (!iconId) { showToast('该物品未设置图标ID', 'warning'); return; }
        try {
            const r = await pyApi('exportThingIconToPng', iconId);
            if (r && r.success && r.base64) {
                const a = document.createElement('a');
                a.href = r.base64;
                a.download = `ThingIcon_${String(iconId).padStart(4,'0')}.png`;
                a.click();
                showToast('图标已导出', 'success');
            } else {
                showToast('导出失败: ' + (r ? r.message : '未知错误'), 'error');
            }
        } catch(e) { showToast('导出失败: ' + e, 'error'); }
    },

    search(keyword) {
        this._searchKeyword = keyword;
        this._currentPage = 0;
        this.renderList();
    },

    async refreshFacePreview() {
        const el = document.getElementById('g_FaceID');
        if (!el) return;
        const fid = parseInt(el.value);
        if (isNaN(fid)) return;
        const res = await pyApi('getFacePreview', fid);
        const img = document.getElementById('facePreviewImg');
        if (img) {
            img.src = res.success ? res.imgData : '';
        }
    },

    async importCustomFace() {
        const el = document.getElementById('g_FaceID');
        if (!el) return;
        const fid = parseInt(el.value);
        const filePath = await pyApi('selectImageFile');
        if (!filePath.success || !filePath.path) return;
        const res = await pyApi('convertImageToShp', filePath.path, fid);
        if (res.success) {
            this.refreshFacePreview();
            const logBox = document.getElementById('faceConversionLog');
            if (logBox && res.log) {
                logBox.style.display = 'block';
                logBox.innerHTML = res.log.map(l => `<div>${l}</div>`).join('');
            }
            showToast('头像转换完成，已保存至Shape/Face目录', 'success');
        } else {
            showToast('转换失败: ' + res.message, 'error');
        }
    },

    async exportCurrentFace() {
        const el = document.getElementById('g_FaceID');
        if (!el) return;
        const fid = parseInt(el.value);
        const savePath = await pyApi('savePngDialog');
        if (!savePath.success || !savePath.path) return;
        const res = await pyApi('exportShpToPng', fid, savePath.path);
        showToast(res.success ? '头像导出成功' : '导出失败: ' + res.message, res.success ? 'success' : 'error');
    }
};

// ============================================================
// 批量头像管理
// ============================================================

let _faceBatchData = [];
let _faceBatchSelected = new Set();

async function faceBatchPreview() {
    const start = parseInt(document.getElementById('faceBatchStart').value) || 1;
    const count = parseInt(document.getElementById('faceBatchCount').value) || 50;
    const res = await pyApi('facePreview', start, count);
    if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
    _faceBatchData = res.previews || [];
    _faceBatchSelected.clear();
    document.getElementById('faceBatchStats').textContent =
        `共 ${res.total_found} 个 (${start}-${start + count - 1})`;
    renderFaceGrid();
}

function renderFaceGrid() {
    const grid = document.getElementById('faceBatchGrid');
    if (!_faceBatchData.length) {
        grid.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:20px;grid-column:1/-1;">无头像</div>';
        return;
    }
    grid.innerHTML = _faceBatchData.map(f => `
        <div class="face-thumb ${_faceBatchSelected.has(f.id) ? 'selected' : ''}"
             onclick="faceBatchToggle(${f.id})" title="#${f.id} (${(f.size/1024).toFixed(1)}KB)">
            <img src="${f.base64}" width="64" height="64" loading="lazy">
            <span class="face-id">${f.id}</span>
        </div>
    `).join('');
}

function faceBatchToggle(id) {
    if (_faceBatchSelected.has(id)) _faceBatchSelected.delete(id);
    else _faceBatchSelected.add(id);
    renderFaceGrid();
}

function faceBatchSelectAll() {
    _faceBatchData.forEach(f => _faceBatchSelected.add(f.id));
    renderFaceGrid();
}

async function faceBatchDelete() {
    if (_faceBatchSelected.size === 0) { showToast('请先选择头像', 'warning'); return; }
    if (!confirm(`确认删除 ${_faceBatchSelected.size} 个头像?`)) return;
    const ids = Array.from(_faceBatchSelected);
    const res = await pyApi('faceDelete', ids);
    if (res.success) {
        showToast(`已删除 ${res.count} 个头像`, 'info');
        _faceBatchSelected.clear();
        faceBatchPreview();
    } else {
        showToast('删除失败: ' + res.message, 'error');
    }
}

async function faceBatchExport() {
    if (_faceBatchSelected.size === 0) { showToast('请先选择头像', 'warning'); return; }
    const savePath = await pyApi('savePngDialog');
    if (!savePath.success || !savePath.path) return;
    const ids = Array.from(_faceBatchSelected);
    const res = await pyApi('faceBatchExport', ids, savePath.path);
    if (res.success) {
        showToast(`已导出 ${res.count} 个头像`, 'info');
    } else {
        showToast('导出失败: ' + res.message, 'error');
    }
}

// CSS for face grid
(function() {
    const style = document.createElement('style');
    style.textContent = `
        .face-thumb { position:relative; cursor:pointer; border:2px solid transparent; border-radius:4px; overflow:hidden; text-align:center; background:var(--bg-card); transition:border-color 0.15s; }
        .face-thumb:hover { border-color:var(--border-focus); }
        .face-thumb.selected { border-color:var(--accent); }
        .face-thumb img { display:block; margin:0 auto; }
        .face-thumb .face-id { display:block; font-size:10px; color:var(--text-muted); padding:1px 0; }
    `;
    document.head.appendChild(style);
})();

// ============================================================
// 兵种编辑
// ============================================================

const soldiers = {
    data: [],
    currentIndex: -1,
    current: null,
    changed: false,

    async load() {
        const res = await pyApi('loadSoldiers');
        if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
        this.data = res.data || [];
        this.currentIndex = -1; this.current = null;
        this.renderList();
        const el = document.getElementById('soldierCount');
        if (el) el.textContent = this.data.length;
        const warning = document.getElementById('soldierLimitWarning');
        if (warning) warning.style.display = res.over_limit ? 'inline' : 'none';
        // 初始化矩阵和升级树
        matrix.init(this.data);
        upgradeTree.render();
        setupTooltips('soldier', 's_');
    },

    snapshot() { return JSON.parse(JSON.stringify(this.data)); },
    restoreSnapshot(data) { this.data = data; this.currentIndex = -1; this.current = null; this.renderList(); this.changed = false; },
    pushUndo() { UndoManager.pushState('soldiers', this.snapshot()); },

    async save() {
        if (!(await validateBeforeSave())) return;
        if (this.current && this.changed) this.saveCurrent();
        const res = await pyApi('saveSoldiers', this.data);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) this.changed = false;
    },

    renderList() {
        const container = document.getElementById('soldierList');
        if (!container) return;
        container.innerHTML = '';
        this.data.forEach((s, idx) => {
            const card = document.createElement('div');
            card.className = 'item-card' + (idx === this.currentIndex ? ' selected' : '');
            card.innerHTML = `
                <div class="item-card-header">
                    <span class="item-name">${s.Name || '无名'}</span>
                    <span class="item-no">#${s.No || ''}</span>
                </div>
                <div class="item-desc">HP ${s.HP || '-'} 攻击 ${s.ATK || '-'} 防御 ${s.DEF || '-'}</div>
            `;
            card.onclick = () => this.select(idx);
            container.appendChild(card);
        });
    },

    select(idx) {
        if (idx < 0 || idx >= this.data.length) return;
        if (this.current && this.changed) this.saveCurrent();
        this.currentIndex = idx;
        this.current = this.data[idx];
        this.renderDetail();
        this.renderList();
        if (_previewPanelType === 'soldier') updatePreviewPanel('soldier');
        this.changed = false;
    },

    renderDetail() {
        const emptyEl = document.getElementById('emptySoldierDetail');
        const detailEl = document.getElementById('soldierDetailContent');
        if (!this.current) {
            if (emptyEl) emptyEl.style.display = 'flex';
            if (detailEl) detailEl.style.display = 'none';
            return;
        }
        if (emptyEl) emptyEl.style.display = 'none';
        if (detailEl) detailEl.style.display = 'block';
        const fields = ['No','Name','OrderNo','ObjID','Data01','Data02','Data03','SuperHit','Feature','Sex','DieMode','Rank','Upgrade','OffsetZ','SizeX','Str','Int','Life','Speed','Interval','DetectRangeMin','DetectRangeMax','Weapon','WeaponSpeed','BasePower','AddPower','Height','Horse','Type','Color','Special','IsUsed'];
        fields.forEach(k => {
            const el = document.getElementById('s_' + k);
            if (el) {
                if (el.tagName === 'SELECT') el.value = String(this.current[k] || '');
                else el.value = this.current[k] || '';
            }
        });
        // 升级目标提示
        const upgHint = document.getElementById('s_UpgradeHint');
        if (upgHint) {
            const upgTo = parseInt(this.current.Upgrade) || 0;
            if (upgTo > 0) {
                const target = this.data.find(s => parseInt(s.No) === upgTo);
                upgHint.textContent = target ? `→ ${target.Name}` : '→ (编号不存在)';
            } else {
                upgHint.textContent = '';
            }
        }
        // ObjID 提示
        const objHint = document.getElementById('s_ObjIDHint');
        if (objHint) {
            objHint.textContent = this.current.ObjID ? `(对应OBD Sequence尾数)` : '';
        }
    },

    currentChanged() { this.changed = true; },

    saveCurrent() {
        if (!this.current) return;
        const fields = ['No','Name','OrderNo','ObjID','Data01','Data02','Data03','SuperHit','Feature','Sex','DieMode','Rank','Upgrade','OffsetZ','SizeX','Str','Int','Life','Speed','Interval','DetectRangeMin','DetectRangeMax','Weapon','WeaponSpeed','BasePower','AddPower','Height','Horse','Type','Color','Special','IsUsed'];
        fields.forEach(k => {
            const el = document.getElementById('s_' + k);
            if (el) this.current[k] = el.value;
        });
    },

    async addNew() {
        this.pushUndo();
        const res = await pyApi('newSoldier');
        if (res.success) {
            this.data.push(res.data);
            this.changed = true;
            this.renderList();
            this.select(this.data.length - 1);
            const el = document.getElementById('soldierCount');
            if (el) el.textContent = this.data.length;
        } else { showToast(res.message, res && res.success ? 'success' : 'error'); }
    },

    async cloneCurrent() {
        if (!this.current) { showToast('请先选择一个兵种', 'warning'); return; }
        this.pushUndo();
        const no = parseInt(this.current.No);
        const clone = Object.assign({}, this.current);
        const usedIds = new Set(this.data.map(s => parseInt(s.No)));
        let newId = 0;
        for (let i = 1; i < 10000; i++) { if (!usedIds.has(i)) { newId = i; break; } }
        clone.No = newId;
        clone.Name = (clone.Name || '克隆兵种') + '_副本';
        this.data.push(clone);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        const el = document.getElementById('soldierCount');
        if (el) el.textContent = this.data.length;
    },

    deleteCurrent() {
        if (!this.current) return;
        if (!confirm(`确认删除兵种 "${this.current.Name}" #${this.current.No}?`)) return;
        this.pushUndo();
        const no = parseInt(this.current.No);
        pyApi('deleteIniItem', 'Setting/Soldier.ini', 'SOLDIER', 'No', String(no))
            .catch(e => showToast('删除失败: ' + e, 'error'));
        this.data = this.data.filter(s => parseInt(s.No) !== no);
        this.current = null;
        this.currentIndex = -1;
        this.changed = true;
        this.renderList();
        const el = document.getElementById('soldierCount');
        if (el) el.textContent = this.data.length;
        const emptyEl = document.getElementById('emptySoldierDetail');
        const detailEl = document.getElementById('soldierDetailContent');
        if (emptyEl) emptyEl.style.display = 'flex';
        if (detailEl) detailEl.style.display = 'none';
    },

    search(keyword) {
        const container = document.getElementById('soldierList');
        if (!container) return;
        container.innerHTML = '';
        const kw = keyword.toLowerCase();
        this.data.forEach((s, idx) => {
            const name = (s.Name || '').toLowerCase();
            const no = String(s.No || '');
            if (!kw || name.includes(kw) || no.includes(kw)) {
                const card = document.createElement('div');
                card.className = 'item-card';
                card.innerHTML = `
                    <div class="item-card-header">
                        <span class="item-name">${s.Name || '无名'}</span>
                        <span class="item-no">#${s.No || ''}</span>
                    </div>
                    <div class="item-desc">HP ${s.HP || '-'} 攻击 ${s.ATK || '-'} 防御 ${s.DEF || '-'}</div>
                `;
                card.onclick = () => this.select(idx);
                container.appendChild(card);
            }
        });
    }
};

// ============================================================
// 物品编辑
// ============================================================

const things = {
    data: [],
    currentIndex: -1,
    current: null,
    changed: false,
    // 类型名称映射
    typeNames: {1:'消耗品', 2:'武器', 3:'坐骑', 4:'道具', 5:'锻造书'},
    // 所有字段（与 thing_schema.json v3.0 对齐）
    allFields: ['No','Name','Type','Param1','Param2','Param3','Param4','Param5',
        'ScriptNo','ScriptHit','SFResID','BFResID','BFWResID','IconID',
        'IsRare','Count','Level','HP','MP','Str','Int','Speed','Loyal','Rate','ResponseTime','Price',
        'BFMagic01','BFMagic02','BFMagic03','BFMagic04','BFMagic05',
        'SFMagic01','SFMagic02','SuperAttack','SoldierType','Formation',
        'GenSkill01','GenSkill02','ArmySkill01','ArmySkill02','AGSkill01','AGSkill02',
        'Age01','Age02','Age03','Age04','Age05','Age06','Age07','Age08','IsUsed'],

    async load() {
        const res = await pyApi('loadThings');
        if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
        this.data = res.data || [];
        this.currentIndex = -1; this.current = null;
        this.renderList();
        const el = document.getElementById('thingCount');
        if (el) el.textContent = this.data.length;
        storeConfig.load();
        crafting.load();
        setupTooltips('thing', 't_');
    },

    snapshot() { return JSON.parse(JSON.stringify(this.data)); },
    restoreSnapshot(data) { this.data = data; this.currentIndex = -1; this.current = null; this.renderList(); this.changed = false; },
    pushUndo() { UndoManager.pushState('things', this.snapshot()); },

    async save() {
        if (!(await validateBeforeSave())) return;
        if (this.current && this.changed) this.saveCurrent();
        const res = await pyApi('saveThings', this.data);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) {
            this.changed = false;
            // 同步保存 TermText 名称和描述
            await this._saveTermText();
        }
    },

    renderList() {
        const container = document.getElementById('thingList');
        if (!container) return;
        container.innerHTML = '';
        this.data.forEach((t, idx) => {
            const card = document.createElement('div');
            card.className = 'item-card' + (idx === this.currentIndex ? ' selected' : '');
            const typeName = this.typeNames[String(t.Type)] || '未知';
            card.innerHTML = `
                <div class="item-card-header">
                    <span class="item-name">${t.Name || '无名'}</span>
                    <span class="item-no">#${t.No || ''}</span>
                </div>
                <div class="item-desc">${typeName} | 价格 ${t.Price || 0}</div>
            `;
            card.onclick = () => this.select(idx);
            container.appendChild(card);
        });
    },

    select(idx) {
        if (idx < 0 || idx >= this.data.length) return;
        if (this.current && this.changed) this.saveCurrent();
        this.currentIndex = idx;
        this.current = this.data[idx];
        this.renderDetail();
        this.renderList();
        if (_previewPanelType === 'thing') updatePreviewPanel('thing');
        this.changed = false;
        // 异步加载 TermText 名称和描述
        this._loadTermText();
        // 加载原版参考数据对比
        const no = parseInt(this.current.No);
        if (no) ReferenceData.showThingRef(no);
    },

    async _loadTermText() {
        if (!this.current) return;
        const no = parseInt(this.current.No);
        if (!no) return;
        try {
            const res = await pyApi('getThingTermText', no);
            const nameEl = document.getElementById('t_termName');
            const descEl = document.getElementById('t_termDesc');
            if (nameEl) nameEl.value = res.name || '';
            if (descEl) descEl.value = res.desc || '';
        } catch(e) { /* 静默降级 */ }
    },

    async _saveTermText() {
        if (!this.current) return;
        const no = parseInt(this.current.No);
        if (!no) return;
        const nameEl = document.getElementById('t_termName');
        const descEl = document.getElementById('t_termDesc');
        const name = nameEl ? nameEl.value : '';
        const desc = descEl ? descEl.value : '';
        if (!name && !desc) return;
        try {
            await pyApi('setThingTermText', no, name, desc);
        } catch(e) { /* 静默降级 */ }
    },

    renderDetail() {
        const emptyEl = document.getElementById('emptyThingDetail');
        const detailEl = document.getElementById('thingDetailContent');
        if (!this.current) {
            if (emptyEl) emptyEl.style.display = 'flex';
            if (detailEl) detailEl.style.display = 'none';
            return;
        }
        if (emptyEl) emptyEl.style.display = 'none';
        if (detailEl) detailEl.style.display = 'block';
        // 填充所有字段
        this.allFields.forEach(k => {
            const el = document.getElementById('t_' + k);
            if (el) {
                if (el.tagName === 'SELECT') el.value = String(this.current[k] != null ? this.current[k] : '');
                else el.value = this.current[k] != null ? this.current[k] : '';
            }
        });
        // 特殊处理：坐骑专属的 BFResID 和 Speed 共用同一字段
        const bfMount = document.getElementById('t_BFResID_mount');
        if (bfMount) bfMount.value = this.current.BFResID != null ? this.current.BFResID : '';
        const speedAttr = document.getElementById('t_Speed_attr');
        if (speedAttr) speedAttr.value = this.current.Speed != null ? this.current.Speed : '';
        // 根据类型显示/隐藏选项卡
        this.updateTabs();
    },

    currentChanged() { this.changed = true; },

    saveCurrent() {
        if (!this.current) return;
        this.allFields.forEach(k => {
            const el = document.getElementById('t_' + k);
            if (el) this.current[k] = el.value;
        });
        // 特殊处理：坐骑专属的 BFResID 和 Speed 共用
        const bfMount = document.getElementById('t_BFResID_mount');
        if (bfMount) this.current.BFResID = bfMount.value;
        const speedAttr = document.getElementById('t_Speed_attr');
        if (speedAttr) this.current.Speed = speedAttr.value;
    },

    onTypeChanged() {
        this.changed = true;
        this.updateTabs();
        // 自动设置 Param1 默认值
        const type = document.getElementById('t_Type')?.value;
        if (type === '2' && (this.current.Param1 == null || this.current.Param1 === '')) {
            document.getElementById('t_Param1').value = '0';
        }
    },

    updateTabs() {
        const type = this.current ? String(this.current.Type) : '';
        // 武器专属
        const weaponTab = document.getElementById('thingTabWeapon');
        const weaponPanel = document.getElementById('tab_thing_weapon');
        if (weaponTab) weaponTab.style.display = (type === '2') ? '' : 'none';
        // 坐骑专属
        const mountTab = document.getElementById('thingTabMount');
        const mountPanel = document.getElementById('tab_thing_mount');
        if (mountTab) mountTab.style.display = (type === '3') ? '' : 'none';
        // 切换到默认可见的选项卡
        this.switchTab('thing_basic', document.querySelector('.tab-btn[data-tab="thing_basic"]'));
    },

    switchTab(tabId, btn) {
        // 隐藏所有面板
        document.querySelectorAll('#thingDetailContent .tab-panel').forEach(p => p.classList.remove('active'));
        // 取消所有按钮激活
        document.querySelectorAll('#thingDetailContent .tab-btn').forEach(b => b.classList.remove('active'));
        // 显示目标面板
        const panel = document.getElementById('tab_' + tabId);
        if (panel) panel.classList.add('active');
        // 激活按钮
        if (btn) btn.classList.add('active');
    },

    async addNew() {
        this.pushUndo();
        const res = await pyApi('newThing');
        if (res.success) {
            this.data.push(res.data);
            this.changed = true;
            this.renderList();
            this.select(this.data.length - 1);
            const el = document.getElementById('thingCount');
            if (el) el.textContent = this.data.length;
        } else { showToast(res.message, res && res.success ? 'success' : 'error'); }
    },

    async cloneCurrent() {
        if (!this.current) { showToast('请先选择一个物品', 'warning'); return; }
        this.pushUndo();
        const clone = Object.assign({}, this.current);
        const usedIds = new Set(this.data.map(t => parseInt(t.No)));
        let newId = 0;
        for (let i = 1; i < 10000; i++) { if (!usedIds.has(i)) { newId = i; break; } }
        clone.No = newId;
        clone.Name = (clone.Name || '克隆物品') + '_副本';
        this.data.push(clone);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        const el = document.getElementById('thingCount');
        if (el) el.textContent = this.data.length;
    },

    deleteCurrent() {
        if (!this.current) return;
        if (!confirm(`确认删除物品 "${this.current.Name}" #${this.current.No}?`)) return;
        this.pushUndo();
        const no = parseInt(this.current.No);
        pyApi('deleteIniItem', 'Setting/Thing.ini', 'THING', 'No', String(no))
            .catch(e => showToast('删除失败: ' + e, 'error'));
        this.data = this.data.filter(t => parseInt(t.No) !== no);
        this.current = null;
        this.currentIndex = -1;
        this.changed = true;
        this.renderList();
        const el = document.getElementById('thingCount');
        if (el) el.textContent = this.data.length;
        const emptyEl = document.getElementById('emptyThingDetail');
        const detailEl = document.getElementById('thingDetailContent');
        if (emptyEl) emptyEl.style.display = 'flex';
        if (detailEl) detailEl.style.display = 'none';
    },

    search(keyword) {
        const container = document.getElementById('thingList');
        if (!container) return;
        container.innerHTML = '';
        const kw = keyword.toLowerCase();
        this.data.forEach((t, idx) => {
            const name = (t.Name || '').toLowerCase();
            const no = String(t.No || '');
            if (!kw || name.includes(kw) || no.includes(kw)) {
                const typeName = this.typeNames[String(t.Type)] || '未知';
                const card = document.createElement('div');
                card.className = 'item-card';
                card.innerHTML = `
                    <div class="item-card-header">
                        <span class="item-name">${t.Name || '无名'}</span>
                        <span class="item-no">#${t.No || ''}</span>
                    </div>
                    <div class="item-desc">${typeName} | 价格 ${t.Price || 0}</div>
                `;
                card.onclick = () => this.select(idx);
                container.appendChild(card);
            }
        });
    }
};

// ============================================================
// 兵种相克矩阵编辑器
// ============================================================

const matrix = {
    _data: {},       // {attackerNo: {defenderNo: value}}
    _soldiers: [],   // 兵种列表
    _changed: {},

    init(soldierData) {
        this._soldiers = soldierData;
        this._data = {};
        // 从兵种数据中提取相克字段 (Counter1~CounterN)
        soldierData.forEach(s => {
            const no = s.No;
            this._data[no] = {};
            for (const key in s) {
                if (key.startsWith('Counter')) {
                    const defNo = key.replace('Counter', '');
                    this._data[no][defNo] = parseFloat(s[key]) || 1.0;
                }
            }
        });
        this.render();
    },

    render() {
        const container = document.getElementById('matrixContainer');
        if (!container || this._soldiers.length === 0) {
            if (container) container.innerHTML = '<p class="hint" style="padding:20px;text-align:center;">请先加载兵种数据</p>';
            return;
        }

        const filter = document.getElementById('matrixFilter')?.value || 'all';
        const n = this._soldiers.length;
        document.getElementById('matrixSize').textContent = n;

        // 构建表格
        let html = '<table class="matrix-table"><thead><tr><th>#</th>';
        this._soldiers.forEach(s => {
            html += `<th title="${s.Name || ''}">${s.No}</th>`;
        });
        html += '</tr></thead><tbody>';

        this._soldiers.forEach(attacker => {
            const aNo = attacker.No;
            html += `<tr><th title="${attacker.Name || ''}">${aNo}</th>`;
            this._soldiers.forEach(defender => {
                const dNo = defender.No;
                const val = (this._data[aNo] && this._data[aNo][dNo] !== undefined) ? this._data[aNo][dNo] : 1.0;
                const fval = parseFloat(val);

                // 筛选
                let cls = 'equal';
                if (fval > 1.0) cls = 'over';
                else if (fval < 1.0) cls = 'under';

                let show = true;
                if (filter === 'gt1' && fval <= 1.0) show = false;
                if (filter === 'lt1' && fval >= 1.0) show = false;

                if (show) {
                    html += `<td class="matrix-cell ${cls}"><input type="number" value="${val}" step="0.1" min="0.1" max="5.0" onchange="matrix._setCell('${aNo}','${dNo}',this.value)" onfocus="matrix._onFocus(this)" title="${attacker.Name||aNo} → ${defender.Name||dNo}: ${val}"></td>`;
                } else {
                    html += `<td class="matrix-cell"><input type="number" value="${val}" step="0.1" min="0.1" max="5.0" onchange="matrix._setCell('${aNo}','${dNo}',this.value)" style="color:#555;"></td>`;
                }
            });
            html += '</tr>';
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    },

    _editMode: false,

    toggleEdit() {
        this._editMode = !this._editMode;
        const btn = document.getElementById('upgradeTreeEditBtn');
        btn.textContent = this._editMode ? '退出编辑' : '编辑模式';
        btn.classList.toggle('btn-accent', !this._editMode);
        btn.classList.toggle('btn-warning', this._editMode);
        this.render();
    },

    async _updateUpgrade(soldierNo, newUpgrade) {
        const soldier = soldiers.data.find(s => String(s.No) === String(soldierNo));
        if (!soldier) { showToast('兵种未找到', 'error'); return; }
        soldier.Upgrade = String(newUpgrade || 0);
        soldiers.changed = true;
        this.render();
        showToast(`兵种 #${soldierNo} 升级目标已更新为 #${newUpgrade || '无'}`, 'success');
    },

    _setCell(aNo, dNo, value) {
        if (!this._data[aNo]) this._data[aNo] = {};
        this._data[aNo][dNo] = parseFloat(value) || 1.0;
        if (!this._changed[aNo]) this._changed[aNo] = {};
        this._changed[aNo][dNo] = true;
    },

    _onFocus(el) {
        document.getElementById('matrixHint').textContent = `当前编辑: ${el.title}`;
    },

    resetDefaults() {
        if (!confirm('确认将所有相克系数重置为1.0（均势）？')) return;
        this._soldiers.forEach(a => {
            this._data[a.No] = {};
            this._soldiers.forEach(d => {
                this._data[a.No][d.No] = 1.0;
            });
        });
        this.render();
    },

    save() {
        // 将矩阵数据写入每个兵种的Counter字段
        this._soldiers.forEach(s => {
            const no = s.No;
            if (this._data[no]) {
                this._soldiers.forEach(d => {
                    const key = 'Counter' + d.No;
                    s[key] = String(this._data[no][d.No] || 1.0);
                });
            }
        });
        // 触发兵种保存
        soldiers.data = this._soldiers;
        soldiers.changed = true;
        soldiers.save();
    }
};

// ============================================================
// 兵种升级路线可视化
// ============================================================

const upgradeTree = {
    render() {
        const container = document.getElementById('upgradeTreeContainer');
        if (!container) return;

        const data = soldiers.data;
        if (data.length === 0) {
            container.innerHTML = '<p class="hint">请先加载兵种数据</p>';
            return;
        }

        // 构建升级映射: No -> {soldier, upgrades: [No, ...]}
        const t1 = []; // 1阶
        const t2 = []; // 2阶
        const t3 = []; // 3阶
        const map = {}; // No -> soldier

        data.forEach(s => {
            const lvl = parseInt(s.Level) || 1;
            map[s.No] = s;
            if (lvl === 1) t1.push(s);
            else if (lvl === 2) t2.push(s);
            else t3.push(s);
        });

        let html = '<div class="upgrade-tree">';

        data.forEach(s => {
            const upgradeTo = parseInt(s.Upgrade) || 0;
            const target = upgradeTo ? map[upgradeTo] : null;
            const targetName = target ? target.Name : '-';
            const lvl = parseInt(s.Level) || 1;
            const lvlLabel = lvl === 1 ? '1阶' : (lvl === 2 ? '2阶' : '3阶');

            html += `
                <div class="upgrade-node">
                    <div class="upgrade-node-name">[${lvlLabel}] ${s.Name || '无名'}</div>
                    <div class="upgrade-node-info">编号: ${s.No} | HP:${s.HP||'-'} ATK:${s.ATK||'-'}</div>
                    ${upgradeTo > 0 ? `<div class="upgrade-arrow">→ 升级至: ${targetName} (#${upgradeTo})</div>` : '<div class="upgrade-node-info">无升级路线</div>'}
                    ${this._editMode ? `<div style="margin-top:4px;font-size:11px;">
                        <span>升级至: </span>
                        <select onchange="upgradeTree._updateUpgrade(${s.No}, this.value)" style="font-size:11px;padding:1px 2px;">
                            <option value="0" ${upgradeTo===0?'selected':''}>无</option>
                            ${data.filter(x=>String(x.No)!==String(s.No)).map(x=>`<option value="${x.No}" ${upgradeTo===parseInt(x.No)?'selected':''}>#${x.No} ${x.Name||''}</option>`).join('')}
                        </select>
                    </div>` : ''}
                </div>
            `;
        });

        html += '</div>';

        // 统计信息
        html += `<div style="margin-top:12px;display:flex;gap:24px;font-size:12px;color:var(--text-secondary);">
            <span>1阶兵种: ${t1.length}个</span>
            <span>2阶兵种: ${t2.length}个</span>
            <span>3阶兵种: ${t3.length}个</span>
            <span>总计: ${data.length}个</span>
        </div>`;

        container.innerHTML = html;
    },

    async crossFilePreview() {
        const field = document.getElementById('batchCrossField').value;
        const op = document.getElementById('batchCrossOp').value;
        const val = document.getElementById('batchCrossValue').value;
        if (!val) { showToast('请输入值', 'warning'); return; }
        const files = Array.from(document.querySelectorAll('#batchCrossFiles input:checked')).map(cb => cb.value);
        if (!files.length) { showToast('请选择至少一个目标文件', 'warning'); return; }
        const res = await pyApi('batchCrossFile', field, op, val, files, null, null, true);
        this._renderCrossFileResults(res, 'batchCrossFileResults');
    },

    async crossFileExecute() {
        const field = document.getElementById('batchCrossField').value;
        const op = document.getElementById('batchCrossOp').value;
        const val = document.getElementById('batchCrossValue').value;
        if (!val) { showToast('请输入值', 'warning'); return; }
        const files = Array.from(document.querySelectorAll('#batchCrossFiles input:checked')).map(cb => cb.value);
        if (!files.length) { showToast('请选择至少一个目标文件', 'warning'); return; }
        if (!confirm(`确认对所有选中文件的 "${field}" 字段执行 "${op} ${val}" 操作？`)) return;
        const res = await pyApi('batchCrossFile', field, op, val, files, null, null, false);
        if (res.success) {
            showToast(res.message, 'success');
            this._renderCrossFileResults(res, 'batchCrossFileResults');
        } else {
            showToast(res.message || '操作失败', 'error');
        }
    },

    _renderCrossFileResults(res, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        if (!res || !res.results || !res.results.length) {
            container.innerHTML = '<div style="padding:8px;color:var(--text-muted);">无匹配结果</div>';
            return;
        }
        let html = `<div style="padding:8px;font-weight:bold;">总计 ${res.totalAffected} 条记录受影响</div>`;
        for (const r of res.results) {
            html += `<details style="margin:4px 0;background:var(--bg);border-radius:4px;padding:6px;">
                <summary>${r.file}: ${r.count}条</summary>`;
            for (const c of (r.changes || []).slice(0, 20)) {
                html += `<div style="font-size:11px;padding:2px 8px;">No=${c.no} ${c.name}: ${c.old} → <b>${c.new}</b></div>`;
            }
            if (r.changes && r.changes.length > 20) {
                html += `<div style="font-size:11px;padding:2px 8px;color:var(--text-muted);">...还有 ${r.changes.length - 20} 条</div>`;
            }
            html += '</details>';
        }
        container.innerHTML = html;
    },

    async doRename() {
        const type = document.getElementById('batchRenameType').value;
        const prefix = document.getElementById('batchRenamePrefix').value.trim();
        const startNo = parseInt(document.getElementById('batchRenameStart').value) || 1;
        const resultEl = document.getElementById('batchRenameResult');
        if (!prefix) { showToast('请输入名称前缀', 'warning'); return; }
        if (resultEl) resultEl.innerHTML = '<span style="color:var(--warning);">正在重命名...</span>';
        try {
            const res = await pyApi('batchRename', type, prefix, startNo);
            if (resultEl) {
                if (res && res.success) {
                    resultEl.innerHTML = `<span style="color:var(--success);">重命名完成: ${res.renamed || 0} 个条目</span>`;
                } else {
                    resultEl.innerHTML = `<span style="color:var(--danger);">重命名失败: ${res ? res.message : '未知错误'}</span>`;
                }
            }
            if (res && res.message) showToast(res.message, res.success ? 'success' : 'error');
        } catch(e) {
            if (resultEl) resultEl.innerHTML = `<span style="color:var(--danger);">重命名异常: ${e}</span>`;
            showToast('重命名异常: ' + e, 'error');
        }
    },
};

// ============================================================
// 城池时期编辑器 (City01~City10.ini)
// ============================================================

const cityPeriodEditor = {
    data: [],
    currentIndex: -1,
    current: null,
    changed: false,
    _period: '01',

    async load() {
        this._period = document.getElementById('cpPeriod')?.value || '01';
        try {
            const res = await pyApi('loadCityPeriod', { period: this._period });
            if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
            this.data = res.data || [];
            this.currentIndex = -1;
            this.current = null;
            this.changed = false;
            this.renderList();
            document.getElementById('cityPeriodCount').textContent = this.data.length;
            const emptyEl = document.getElementById('emptyCityPeriodDetail');
            const detailEl = document.getElementById('cityPeriodDetailContent');
            if (emptyEl) emptyEl.style.display = 'flex';
            if (detailEl) detailEl.style.display = 'none';
        } catch (e) {
            showToast('加载失败: ' + e.message, 'error');
        }
    },

    switchPeriod(period) {
        this._period = period;
        this.load();
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this.data));
    },

    restoreSnapshot(data) {
        this.data = data;
        this.currentIndex = -1;
        this.current = null;
        this.renderList();
        this.changed = false;
    },

    pushUndo() {
        UndoManager.pushState('cityPeriod', this.snapshot());
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        this.pushUndo();
        const res = await pyApi('saveCityPeriod', { period: this._period, data: this.data });
        if (res.success) showToast(res.message || `City${this._period}.ini 保存成功，共${this.data.length}条`, 'success');
        else showToast(res.message, res && res.success ? 'success' : 'error');
        this.changed = false;
    },

    renderList() {
        const container = document.getElementById('cityPeriodList');
        if (!container) return;
        container.innerHTML = '';
        this.data.forEach((c, idx) => {
            const card = document.createElement('div');
            card.className = 'item-card' + (idx === this.currentIndex ? ' selected' : '');
            card.innerHTML = `
                <div class="item-card-header">
                    <span class="item-name">${escHtml(c.Name || '无名')}</span>
                    <span class="item-no">#${escHtml(String(c.No || ''))}</span>
                </div>
                <div class="item-desc">君主 ${escHtml(String(c.Lord||0))} | 人口 ${escHtml(String(c.People||0))} | 金 ${escHtml(String(c.Money||0))}</div>
            `;
            card.onclick = () => this.select(idx);
            container.appendChild(card);
        });
    },

    select(idx) {
        if (idx < 0 || idx >= this.data.length) return;
        if (this.current && this.changed) this.saveCurrent();
        this.currentIndex = idx;
        this.current = this.data[idx];
        this.renderDetail();
        this.renderList();
        this.changed = false;
    },

    renderDetail() {
        const emptyEl = document.getElementById('emptyCityPeriodDetail');
        const detailEl = document.getElementById('cityPeriodDetailContent');
        if (!this.current) {
            if (emptyEl) emptyEl.style.display = 'flex';
            if (detailEl) detailEl.style.display = 'none';
            return;
        }
        if (emptyEl) emptyEl.style.display = 'none';
        if (detailEl) detailEl.style.display = 'block';
        const fields = ['No','Name','Lord','Chief','Adviser','People','PeopleHeart','Money','Defend','Economics','ReserveSoldierNumCur','DefaultTower','IsEvent','IsEventOpen','IsUsed'];
        fields.forEach(k => {
            const el = document.getElementById('cp_' + k);
            if (el) {
                if (el.tagName === 'SELECT') el.value = String(this.current[k] || '');
                else el.value = this.current[k] || '';
            }
        });
    },

    currentChanged() { this.changed = true; },

    saveCurrent() {
        if (!this.current) return;
        ['No','Name','Lord','Chief','Adviser','People','PeopleHeart','Money','Defend','Economics','ReserveSoldierNumCur','DefaultTower','IsEvent','IsEventOpen','IsUsed'].forEach(k => {
            const el = document.getElementById('cp_' + k);
            if (el) this.current[k] = el.value;
        });
    },

    addNew() {
        this.pushUndo();
        const usedIds = new Set(this.data.map(c => parseInt(c.No)));
        let newId = 0;
        for (let i = 1; i < 1000; i++) { if (!usedIds.has(i)) { newId = i; break; } }
        const entry = {No:newId, Name:'新城池_'+newId, Lord:0, Chief:0, Adviser:0, People:50000, PeopleHeart:600, Money:1000, Defend:150, Economics:150, ReserveSoldierNumCur:100, DefaultTower:0, IsEvent:0, IsEventOpen:0, IsUsed:1};
        this.data.push(entry);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        document.getElementById('cityPeriodCount').textContent = this.data.length;
    },

    cloneCurrent() {
        this.saveCurrent();
        if (!this.current) return;
        this.pushUndo();
        const clone = JSON.parse(JSON.stringify(this.current));
        const usedIds = new Set(this.data.map(c => parseInt(c.No)));
        let newId = 0;
        for (let i = 1; i < 1000; i++) { if (!usedIds.has(i)) { newId = i; break; } }
        clone.No = newId;
        this.data.push(clone);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        document.getElementById('cityPeriodCount').textContent = this.data.length;
    },

    deleteCurrent() {
        if (this.currentIndex < 0) return;
        if (!confirm(`确定删除 #${this.current.No} ${this.current.Name}？`)) return;
        this.pushUndo();
        this.data.splice(this.currentIndex, 1);
        this.currentIndex = -1;
        this.current = null;
        this.changed = true;
        this.renderList();
        document.getElementById('cityPeriodCount').textContent = this.data.length;
        const emptyEl = document.getElementById('emptyCityPeriodDetail');
        const detailEl = document.getElementById('cityPeriodDetailContent');
        if (emptyEl) emptyEl.style.display = 'flex';
        if (detailEl) detailEl.style.display = 'none';
    },
};

// ============================================================
// DefSkill 技能/特性编辑器
// ============================================================

const defskill = {
    _raw: null,          // 原始DefSkill.ini数据
    _modified: {},       // 修改追踪 {section: {key: newValue}}
    _generals: [],       // 武将名映射 {No: Name}
    _currentGenNo: null, // 当前选中的武将编号

    async load() {
        const res = await pyApi('loadDefSkill');
        if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
        this._raw = res.data;
        this._modified = {};
        // 加载武将名映射
        const genRes = await pyApi('loadGenerals');
        if (genRes.success && genRes.data) {
            this._generals = {};
            genRes.data.forEach(g => { this._generals[g.No] = g.Name; });
        }
        this._parseAndRender();
    },

    _parseAndRender() {
        // 解析DefSkill结构: GenSkillNN = 武将编号 -> 武将技组, GenFeatureNN = 武将编号 -> 特性组
        // 结构: { "GenSkill01": [{"1": "5,10,15,20,25,30,35,40,45,50"}, ...], ... }
        const data = this._raw || {};
        this._renderTable(data);
        document.getElementById('dsCount').textContent = Object.keys(this._generals || {}).length;
    },

    snapshot() {
        return {
            _raw: JSON.parse(JSON.stringify(this._raw)),
            _modified: JSON.parse(JSON.stringify(this._modified)),
        };
    },

    restoreSnapshot(data) {
        this._raw = data._raw ? JSON.parse(JSON.stringify(data._raw)) : {};
        this._modified = data._modified ? JSON.parse(JSON.stringify(data._modified)) : {};
        this._parseAndRender();
    },

    pushUndo() {
        UndoManager.pushState('defskill', this.snapshot());
    },

    _renderTable(data) {
        const tbody = document.getElementById('dsTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';

        // 收集所有武将编号
        const allGenNos = new Set();
        const skillSections = [];
        const featSections = [];

        for (const [secName, entries] of Object.entries(data)) {
            if (secName.startsWith('GenSkill') && /^\d+$/.test(secName.replace('GenSkill', ''))) {
                skillSections.push({ name: secName, index: parseInt(secName.replace('GenSkill', '')), entries });
            } else if (secName.startsWith('GenFeature') && /^\d+$/.test(secName.replace('GenFeature', ''))) {
                featSections.push({ name: secName, index: parseInt(secName.replace('GenFeature', '')), entries });
            }
        }

        // 从技能组中收集武将编号
        skillSections.forEach(sec => {
            (sec.entries || []).forEach(entry => {
                Object.keys(entry).forEach(k => allGenNos.add(k));
            });
        });
        featSections.forEach(sec => {
            (sec.entries || []).forEach(entry => {
                Object.keys(entry).forEach(k => allGenNos.add(k));
            });
        });

        const genNos = Array.from(allGenNos).sort((a, b) => parseInt(a) - parseInt(b));

        genNos.forEach(genNo => {
            const tr = document.createElement('tr');
            const name = (this._generals && this._generals[genNo]) || '未知';
            tr.innerHTML = this._buildRow(genNo, name, skillSections, featSections);
            tr.onclick = () => {
                // 切换选中状态
                const prev = document.querySelector('#dsTableBody tr.selected');
                if (prev) prev.classList.remove('selected');
                if (this._currentGenNo === genNo) {
                    this._currentGenNo = null;
                } else {
                    tr.classList.add('selected');
                    this._currentGenNo = genNo;
                }
            };
            tbody.appendChild(tr);
        });
    },

    _buildRow(genNo, name, skillSections, featSections) {
        // 武将技10列 + 军师技10列
        let skillCells = '';
        for (let i = 1; i <= 10; i++) {
            const sec = skillSections.find(s => s.index === i);
            let val = '';
            if (sec) {
                const entry = (sec.entries || []).find(e => e[genNo] !== undefined);
                if (entry) val = entry[genNo] || '';
            }
            skillCells += `<td><input type="number" value="${val}" onchange="defskill._markModified('GenSkill${i.toString().padStart(2,'0')}','${genNo}',this.value)" class="skill-input" style="width:50px;"></td>`;
        }

        // 军师技10列 (GenSkill 11-20 或 GenStrategy sections)
        let stratCells = '';
        for (let i = 1; i <= 10; i++) {
            const secIdx = 10 + i;
            const sec = skillSections.find(s => s.index === secIdx);
            let val = '';
            if (sec) {
                const entry = (sec.entries || []).find(e => e[genNo] !== undefined);
                if (entry) val = entry[genNo] || '';
            }
            stratCells += `<td><input type="number" value="${val}" onchange="defskill._markModified('GenSkill${secIdx.toString().padStart(2,'0')}','${genNo}',this.value)" class="skill-input" style="width:50px;"></td>`;
        }

        // 个人特性 GenFeature01
        let personal = '';
        const pSec = featSections.find(s => s.index === 1);
        if (pSec) {
            const entry = (pSec.entries || []).find(e => e[genNo] !== undefined);
            if (entry) personal = entry[genNo] || '';
        }

        // 主将特性 GenFeature02
        let leader = '';
        const lSec = featSections.find(s => s.index === 2);
        if (lSec) {
            const entry = (lSec.entries || []).find(e => e[genNo] !== undefined);
            if (entry) leader = entry[genNo] || '';
        }

        // 元帅特性 GenFeature03
        let marshal = '';
        const mSec = featSections.find(s => s.index === 3);
        if (mSec) {
            const entry = (mSec.entries || []).find(e => e[genNo] !== undefined);
            if (entry) marshal = entry[genNo] || '';
        }

        return `<td style="font-family:var(--font-mono);">${genNo}</td>
            <td style="font-weight:600;">${name}</td>
            ${skillCells}
            ${stratCells}
            <td><input type="text" value="${personal.replace(/"/g,'&quot;')}" onchange="defskill._markModified('GenFeature01','${genNo}',this.value)" style="width:80px;"></td>
            <td><input type="text" value="${leader.replace(/"/g,'&quot;')}" onchange="defskill._markModified('GenFeature02','${genNo}',this.value)" style="width:80px;"></td>
            <td><input type="text" value="${marshal.replace(/"/g,'&quot;')}" onchange="defskill._markModified('GenFeature03','${genNo}',this.value)" style="width:80px;"></td>`;
    },

    _markModified(section, genNo, value) {
        if (!this._modified[section]) this._modified[section] = {};
        this._modified[section][genNo] = value;
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        if (Object.keys(this._modified).length === 0) {
            showToast('没有需要保存的修改', 'success');
            return;
        }
        this.pushUndo();
        // 将修改合并到原始数据
        const data = JSON.parse(JSON.stringify(this._raw || {}));
        for (const [secName, changes] of Object.entries(this._modified)) {
            if (!data[secName]) data[secName] = [];
            for (const [genNo, val] of Object.entries(changes)) {
                let found = false;
                for (const entry of data[secName]) {
                    if (entry[genNo] !== undefined) {
                        entry[genNo] = val;
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    const newEntry = {};
                    newEntry[genNo] = val;
                    data[secName].push(newEntry);
                }
            }
        }
        const res = await pyApi('saveDefSkill', data);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) {
            this._modified = {};
            this._raw = data;
            this._parseAndRender();
        }
    },

    async addNew() {
        this.pushUndo();
        const genNo = prompt('请输入要添加的武将编号 (No):');
        if (!genNo || !/^\d+$/.test(genNo)) {
            showToast('请输入有效的武将编号', 'warning');
            return;
        }
        const res = await pyApi('newDefSkillEntry', genNo);
        if (res.success) {
            this._raw = res.data;
            this._modified = {};
            this._parseAndRender();
            showToast(res.message, 'success');
        } else {
            showToast(res.message, 'error');
        }
    },

    async deleteCurrent() {
        if (!this._currentGenNo) {
            showToast('请先选择要删除的武将行', 'warning');
            return;
        }
        if (!confirm(`确认删除武将 ${this._currentGenNo} 的 DefSkill 条目?`)) return;
        this.pushUndo();
        const res = await pyApi('deleteDefSkillEntry', this._currentGenNo);
        if (res.success) {
            this._raw = res.data;
            this._modified = {};
            this._currentGenNo = null;
            this._parseAndRender();
            showToast(res.message, 'success');
        } else {
            showToast(res.message, 'error');
        }
    },

    search(keyword) {
        const tbody = document.getElementById('dsTableBody');
        if (!tbody) return;
        const rows = tbody.querySelectorAll('tr');
        const kw = keyword.toLowerCase();
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length >= 2) {
                const no = cells[0].textContent.toLowerCase();
                const name = cells[1].textContent.toLowerCase();
                row.style.display = (!kw || no.includes(kw) || name.includes(kw)) ? '' : 'none';
            }
        });
    }
};

// ============================================================
// 备份还原
// ============================================================

const backup = {
    async backupAll() {
        if (!confirm('确认备份所有Setting目录下的INI文件吗？')) return;
        const res = await pyApi('backupAll');
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.loadHistory();
    },

    async restoreAll() {
        if (!confirm('确认要还原所有文件到备份状态吗？这会覆盖当前修改！')) return;
        const res = await pyApi('restoreAll');
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.loadHistory();
    },

    async loadHistory() {
        const res = await pyApi('getBackupHistory');
        const tbody = document.getElementById('backupHistory');
        if (!tbody) return;
        tbody.innerHTML = '';
        const history = res.history || [];
        if (history.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#999;">暂无备份</td></tr>';
            return;
        }
        history.forEach(r => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${r.timestamp || ''}</td>
                <td>${r.rel_path || ''}</td>
                <td>${Math.round((r.size || 0) / 1024)} KB</td>
            `;
            tbody.appendChild(tr);
        });
    },

    async cleanupOld() {
        if (!confirm('确定要清理旧备份吗？默认保留最近10个备份快照。')) return;
        const res = await pyApi('cleanupBackups');
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.loadHistory();
    }
};
// ============================================================
// 数据校验
// ============================================================

const validate = {
    async run() {
        const res = await pyApi('validateAll');
        const sum = res.summary || {};
        const elTotal = document.getElementById('vTotal');
        const elErrors = document.getElementById('vErrors');
        const elWarnings = document.getElementById('vWarnings');
        if (elTotal) elTotal.textContent = sum.total || 0;
        if (elErrors) elErrors.textContent = sum.errors || 0;
        if (elWarnings) elWarnings.textContent = sum.warnings || 0;

        const container = document.getElementById('validationList');
        if (!container) return;
        container.innerHTML = '';
        const results = res.results || [];
        if (results.length === 0) {
            container.innerHTML = '<div style="padding:20px;text-align:center;color:#666;">没有检查出任何问题</div>';
            return;
        }
        results.forEach(r => {
            const item = document.createElement('div');
            item.className = `validation-item ${r.severity}`;
            item.innerHTML = `
                <div class="v-header">
                    <span class="v-message">${r.message}</span>
                    <span class="v-category">${r.category}</span>
                </div>
                ${r.file_ref ? `<div class="v-location">文件: ${r.file_ref} → ${r.section_ref || ''} ${r.field_ref || ''}</div>` : ''}
            `;
            container.appendChild(item);
        });
    }
};

// ============================================================
// EXE补丁
// ============================================================

const exepatch = {
    async loadInfo() {
        const res = await pyApi('getExeInfo');
        const el = document.getElementById('exeStatus');
        if (el) {
            el.textContent = res.exists
                ? `已检测到 (${(res.size / 1024 / 1024).toFixed(2)} MB)`
                : '未检测到';
        }
        this.renderPatches(res.patches || []);
        this.loadTemplates();
        this.loadSango7Config();
        this.loadCommunityPatches();
    },

    renderPatches(patches) {
        const container = document.getElementById('patchList');
        if (!container) return;
        container.innerHTML = '';
        patches.forEach(p => {
            const item = document.createElement('div');
            item.className = 'patch-item';
            const offsetInfo = p.auto_detect
                ? '<span style="color:var(--warning);font-size:11px;">(需扫描定位)</span>'
                : p.multi_offset
                    ? `<span style="font-size:11px;color:var(--text-muted);">${p.offset_count}处偏移</span>`
                    : p.effective_offset
                        ? `<span style="font-size:11px;color:var(--text-muted);">偏移: ${'0x' + p.effective_offset.toString(16)}</span>`
                        : '';
            item.innerHTML = `
                <div>
                    <strong>${p.description}</strong> ${offsetInfo}
                    <p>当前值: ${p.current_value} (默认 ${p.default_value})</p>
                </div>
                <div>
                    <input type="number" id="patch_${p.name}_value" value="${p.current_value * 2}" style="width:80px;">
                    <button onclick="exepatch.applyAuto('${p.name}', document.getElementById('patch_${p.name}_value').value)" class="btn btn-primary">自动应用</button>
                </div>
            `;
            container.appendChild(item);
        });
    },

    async applyAuto(name, value) {
        value = parseInt(value);
        if (isNaN(value)) { showToast('请输入有效数值', 'warning'); return; }
        if (!confirm(`确认修改 ${name} 为 ${value}？`)) return;
        const res = await pyApi('applyExePatchAuto', name, value);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.loadInfo();
    },

    async apply(name, offset, value) {
        value = parseInt(value);
        if (isNaN(value)) { showToast('请输入有效数值', 'warning'); return; }
        if (!confirm(`确认修改 ${name} 为 ${value}？`)) return;
        const res = await pyApi('applyExePatch', name, offset, value);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.loadInfo();
    },

    async scanSignatures() {
        const el = document.getElementById('scanResult');
        if (el) el.textContent = '扫描中...';
        const res = await pyApi('scanExeSignatures');
        if (res.success) {
            const found = Object.entries(res.signatures)
                .filter(([_, count]) => count > 0)
                .map(([name, count]) => `${name}: ${count}处`)
                .join(', ');
            if (el) el.textContent = found ? `发现: ${found}` : '未找到匹配';
            } else {
            if (el) el.textContent = '扫描失败';
        }
        this.loadInfo();
    },

    async revertAll() {
        if (!confirm('确认撤销所有补丁，恢复原始EXE吗？')) return;
        const res = await pyApi('revertExePatches');
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.loadInfo();
    },

    // 反汇编
    async disassemble() {
        const offsetStr = document.getElementById('disasmOffset').value.trim();
        if (!offsetStr) return;
        const offset = parseInt(offsetStr, offsetStr.startsWith('0x') ? 16 : 10);
        if (isNaN(offset)) { showToast('无效偏移地址', 'warning'); return; }

        const out = document.getElementById('disasmOutput');
        out.textContent = '反汇编中...';
        const res = await pyApi('disassembleExe', offset, 8);
        if (res.success && res.instructions) {
            out.innerHTML = res.instructions.map(i => {
                if (i.error) return `<span style="color:var(--danger)">${i.error}</span>`;
                return `<span style="color:var(--text-muted)">${i.offset_hex}</span>  <span style="color:var(--accent)">${i.bytes}</span>  <span style="color:var(--success)">${i.mnemonic}</span> <span style="color:var(--text-primary)">${i.op_str}</span>`;
            }).join('\n');
        } else {
            out.textContent = res.instructions?.[0]?.error || '反汇编失败';
        }
    },

    async disassembleScan(scanName) {
        const out = document.getElementById('disasmOutput');
        out.textContent = `扫描特征码 "${scanName}" 并反汇编...`;
        const res = await pyApi('disassembleScan', scanName, 5);
        if (res.success && res.candidates) {
            let html = `<strong>${res.scan_name}</strong> 共 ${res.total_candidates} 处匹配，显示前 ${res.shown} 处:\n\n`;
            res.candidates.forEach((c, i) => {
                html += `<span style="color:var(--warning)">#${i+1} ${c.offset_hex} [${c.pattern_desc}]</span>\n`;
                html += `<span style="color:var(--text-muted)">  上下文: ${c.context_before} <b>${c.pattern_hex}</b> ${c.context_after}</span>\n`;
                if (c.instructions) {
                    c.instructions.forEach(insn => {
                        if (!insn.error) {
                            html += `  <span style="color:var(--text-muted)">${insn.offset_hex}</span>  <span style="color:var(--accent)">${insn.bytes}</span>  <span style="color:var(--success)">${insn.mnemonic}</span> <span style="color:var(--text-primary)">${insn.op_str}</span>\n`;
                        }
                    });
                }
                html += '\n';
            });
            out.innerHTML = html;
        } else {
            out.textContent = res.message || '反汇编失败';
        }
    },

    // NOP/JMP 模板
    async loadTemplates() {
        const res = await pyApi('getJmpTemplates');
        const container = document.getElementById('templateList');
        if (!container || !res.templates) return;
        container.innerHTML = Object.entries(res.templates).map(([name, t]) =>
            `<button onclick="exepatch.selectTemplate('${name}')" class="btn" style="font-size:11px;padding:4px 8px;" title="${t.usage}">${t.description}</button>`
        ).join('');
    },

    _selectedTemplate: null,

    selectTemplate(name) {
        this._selectedTemplate = name;
        const res = this._selectedTemplate;
        document.getElementById('templateOffset').placeholder = `偏移 (${res === 'nop_check' ? 'NOP位置' : res === 'jmp_skip' ? '跳转指令位置' : res === 'jmp_always_allow' ? '条件跳转位置' : 'cmp指令位置'})`;
        document.getElementById('templateArg').placeholder = res === 'nop_check' ? 'NOP字节数 (默认2)' : res === 'cmp_remove' ? 'cmp字节数 (默认3)' : '目标偏移地址';
        showToast(`已选择: ${res}\n\n用法: ${this._getTemplateUsage(res, 'info')}`, 'info');
    },

    _getTemplateUsage(name) {
        const map = {
            'nop_check': '填入要NOP掉的指令偏移 + 字节数。如偏移 0x10d099, 字节数 2',
            'jmp_skip': '填入条件跳转指令的偏移 + 目标偏移。如偏移 0x10d099, 目标 0x10d0a0',
            'jmp_always_allow': '填入条件跳转指令的偏移。自动识别跳转目标并改为无条件JMP',
            'cmp_remove': '填入cmp指令的偏移 + 字节数。如偏移 0x10d099, 字节数 3',
        };
        return map[name] || '';
    },

    async applyTemplate() {
        if (!this._selectedTemplate) { showToast('请先点击选择一个模板', 'warning'); return; }
        const offsetStr = document.getElementById('templateOffset').value.trim();
        const argStr = document.getElementById('templateArg').value.trim();
        if (!offsetStr) { showToast('请输入偏移地址', 'warning'); return; }
        const offset = parseInt(offsetStr, offsetStr.startsWith('0x') ? 16 : 10);
        if (isNaN(offset)) { showToast('无效偏移地址', 'warning'); return; }

        const args = [];
        if (argStr) {
            const arg = parseInt(argStr, argStr.startsWith('0x') ? 16 : 10);
            if (!isNaN(arg)) args.push(arg);
        }

        if (!confirm(`确认应用模板 "${this._selectedTemplate}" 到偏移 0x${offset.toString(16)}？修改前会自动备份EXE。`)) return;
        const res = await pyApi('applyTemplatePatch', this._selectedTemplate, offset, ...args);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.loadInfo();
    },

    // 一键突破全部属性999上限
    async applyAllStatBreak() {
        if (!confirm('确认将全部33处属性999上限修改为65535？\n\n修改前会自动备份EXE。\n适用于免认证版SG7.exe。')) return;
        const res = await pyApi('applyExePatchAuto', 'all_stat_999_break', 65535);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.loadInfo();
    },

    // Sango7.ini 分辨率配置
    async loadSango7Config() {
        const res = await pyApi('getSango7Config');
        const container = document.getElementById('sango7Config');
        if (!container || !res.success) return;
        const cfg = res.config;
        container.innerHTML = `
            <label>宽度: <input type="number" id="cfg_width" value="${cfg.width}" style="width:80px;"></label>
            <label>高度: <input type="number" id="cfg_height" value="${cfg.height}" style="width:80px;"></label>
            <label>全屏: <select id="cfg_fullscreen"><option value="1" ${cfg.fullscreen === 1 ? 'selected' : ''}>全屏</option><option value="0" ${cfg.fullscreen === 0 ? 'selected' : ''}>窗口</option></select></label>
            <span style="font-size:12px;color:var(--text-muted);">当前: ${cfg.width}x${cfg.height} ${cfg.fullscreen ? '全屏' : '窗口'}</span>
        `;
    },

    applyPreset(resolution) {
        const [w, h] = resolution.split('x').map(Number);
        document.getElementById('cfg_width').value = w;
        document.getElementById('cfg_height').value = h;
    },

    async saveSango7Config() {
        const w = parseInt(document.getElementById('cfg_width')?.value) || 0;
        const h = parseInt(document.getElementById('cfg_height')?.value) || 0;
        const fs = parseInt(document.getElementById('cfg_fullscreen')?.value);
        if (!w || !h) { showToast('请输入有效的分辨率', 'warning'); return; }
        const res = await pyApi('setSango7Config', w, h, fs);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.loadSango7Config();
    },

    async scanValue() {
        const val = prompt('输入要搜索的数值:', '999');
        if (!val) return;
        const v = parseInt(val);
        if (isNaN(v)) { showToast('请输入有效数值', 'warning'); return; }
        const type = prompt('数值类型: int32 / int16 / int8', 'int16');
        if (!type) return;
        try {
            const res = await pyApi('scanExeValue', v, type);
            if (res && res.success) {
                let msg = `搜索 ${v} (${type}) 结果: ${res.count} 处\n\n`;
                if (res.offsets && res.offsets.length > 0) {
                    res.offsets.forEach(o => {
                        msg += `  ${o.offset_hex || '0x'+o.toString(16)}: ${o.value || o}\n`;
                    });
                }
                showToast(msg, 'info');
            } else {
                showToast('搜索失败: ' + (res ? res.message : ''), 'error');
            }
        } catch(e) { showToast('搜索失败: '+e, 'error'); }
    },

    // 社区教程补丁
    async loadCommunityPatches() {
        const container = document.getElementById('communityPatchList');
        if (!container) return;
        try {
            const res = await pyApi('exeCommunityPatches');
            if (!res || !res.success) {
                container.innerHTML = '<span style="font-size:13px;color:var(--text-muted);">加载失败: ' + (res ? res.message : '') + '</span>';
                return;
            }
            const patches = res.patches || [];
            if (patches.length === 0) {
                container.innerHTML = '<span style="font-size:13px;color:var(--text-muted);">暂无社区补丁数据</span>';
                return;
            }
            container.innerHTML = patches.map(p => {
                const offsetInfo = p.offset_count
                    ? `<span style="font-size:11px;color:var(--text-muted);">${p.offset_count}处偏移 | ${p.all_offsets ? p.all_offsets.join(', ') : ''}</span>`
                    : (p.offsets && p.offsets.length > 0
                        ? `<span style="font-size:11px;color:var(--text-muted);">偏移: ${p.all_offsets ? p.all_offsets[0] : ''}</span>`
                        : '<span style="font-size:11px;color:var(--warning);">(需扫描定位)</span>');
                const noteHtml = p.note ? `<p style="font-size:11px;color:var(--text-muted);margin:2px 0;">${p.note}</p>` : '';
                const sourceHtml = p.source ? `<span style="font-size:10px;color:var(--text-muted);">来源: ${p.source}</span>` : '';
                return `
                <div class="patch-item" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                    <div>
                        <strong>${p.description}</strong> ${offsetInfo} ${sourceHtml}
                        <p>当前值: ${p.current_value} (默认 ${p.default_value})</p>
                        ${noteHtml}
                    </div>
                    <div>
                        <input type="number" id="community_patch_${p.name}_value" value="${p.current_value}" style="width:80px;">
                        <button onclick="exepatch.applyCommunityPatch('${p.name}', document.getElementById('community_patch_${p.name}_value').value)" class="btn btn-primary">应用</button>
                    </div>
                </div>
                `;
            }).join('');
        } catch(e) {
            container.innerHTML = '<span style="font-size:13px;color:var(--danger);">加载失败: ' + escHtml(String(e)) + '</span>';
        }
    },

    async applyCommunityPatch(patchId, value) {
        value = parseInt(value);
        if (isNaN(value)) { showToast('请输入有效数值', 'warning'); return; }
        if (!confirm(`确认应用社区补丁 "${patchId}"，值设为 ${value}？\n修改前会自动备份EXE。`)) return;
        const res = await pyApi('exeApplyCommunityPatch', patchId, value);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.loadInfo();
    },
};

// ============================================================
// Shape 资源浏览器 (Face/BFObj/genhalf)
// ============================================================
const shapeBrowser = {
    _currentCategory: 'Face',
    _currentPage: 0,
    _pageSize: 60,
    _allFiles: { Face: [], BFObj: [], genhalf: [] },
    _selectedFiles: new Set(),

    async init() {
        this._selectedFiles.clear();
        this._currentPage = 0;
        await this.loadCategory('Face');
    },

    async loadCategory(cat) {
        this._currentCategory = cat;
        this._currentPage = 0;
        this._selectedFiles.clear();
        document.querySelectorAll('.shape-cat-tab').forEach(t => t.classList.remove('active'));
        const tab = document.getElementById('shapeCatTab_' + cat);
        if (tab) tab.classList.add('active');
        await this._refresh();
    },

    async _refresh() {
        const grid = document.getElementById('shapeResGrid');
        const info = document.getElementById('shapeResInfo');
        if (!grid) return;
        grid.innerHTML = '<p class="loading">加载中...</p>';
        try {
            const r = await pyApi('browseShapeResources', this._currentCategory);
            if (r && r.success && r.categories) {
                const catData = r.categories[this._currentCategory];
                if (catData && catData.exists) {
                    this._allFiles[this._currentCategory] = catData.files || [];
                } else {
                    this._allFiles[this._currentCategory] = [];
                }
                this._renderStats();
                this._renderGrid();
            } else {
                grid.innerHTML = '<p class="hint">加载失败: ' + (r ? r.message : '') + '</p>';
            }
        } catch(e) {
            grid.innerHTML = '<p class="hint">加载失败: ' + escHtml(String(e)) + '</p>';
        }
    },

    _renderStats() {
        const info = document.getElementById('shapeResInfo');
        if (!info) return;
        const files = this._allFiles[this._currentCategory] || [];
        const totalKB = files.reduce((s, f) => s + (f.size_kb || 0), 0);
        const totalMB = (totalKB / 1024).toFixed(1);
        info.innerHTML = `<span>${this._currentCategory}: <b>${files.length}</b> 个文件</span>
            <span>总大小: <b>${totalMB} MB</b></span>
            <span>当前页: ${this._currentPage + 1}/${Math.max(1, Math.ceil(files.length / this._pageSize))}</span>`;
    },

    _renderGrid() {
        const grid = document.getElementById('shapeResGrid');
        if (!grid) return;
        const files = this._allFiles[this._currentCategory] || [];
        if (files.length === 0) {
            grid.innerHTML = '<p class="hint">该分类下暂无 SHP 文件（请先解包 Shape PCK）</p>';
            return;
        }
        const start = this._currentPage * this._pageSize;
        const page = files.slice(start, start + this._pageSize);
        let html = '';
        page.forEach((f, i) => {
            const idx = start + i;
            const sel = this._selectedFiles.has(f.path) ? ' selected' : '';
            const thumbId = 'shapeThumb_' + idx;
            html += `<div class="shape-thumb${sel}" data-path="${escHtml(f.path)}" data-idx="${idx}" onclick="shapeBrowser._toggleSelect(this, '${escHtml(f.path).replace(/'/g, "\\'")}')" ondblclick="shapeBrowser._preview('${escHtml(f.path).replace(/'/g, "\\'")}')" title="${escHtml(f.name)} (${f.size_kb}KB)">
                <div class="shape-thumb-img" id="${thumbId}"><div class="shape-thumb-placeholder">${escHtml(f.name)}</div></div>
                <div class="shape-thumb-name">${escHtml(f.name)}</div>
                <div class="shape-thumb-size">${f.size_kb}KB</div>
            </div>`;
        });
        grid.innerHTML = html;
        this._renderPagination();
        // 延迟加载缩略图
        setTimeout(() => this._loadThumbnails(page, start), 100);
    },

    async _loadThumbnails(page, startIdx) {
        const paths = page.map(f => f.path);
        try {
            const r = await pyApi('shapeThumbnails', this._currentCategory, paths);
            if (r && r.success && r.thumbnails) {
                page.forEach((f, i) => {
                    const thumbId = 'shapeThumb_' + (startIdx + i);
                    const el = document.getElementById(thumbId);
                    if (el && r.thumbnails[f.path]) {
                        el.innerHTML = `<img src="${r.thumbnails[f.path]}" style="width:48px;height:48px;object-fit:contain;image-rendering:pixelated;" />`;
                    }
                });
            }
        } catch(e) { /* 缩略图加载失败不影响使用 */ }
    },

    _renderPagination() {
        const pg = document.getElementById('shapeResPagination');
        if (!pg) return;
        const files = this._allFiles[this._currentCategory] || [];
        const totalPages = Math.max(1, Math.ceil(files.length / this._pageSize));
        let html = `<button onclick="shapeBrowser._goPage(0)" ${this._currentPage === 0 ? 'disabled' : ''}>首页</button>
            <button onclick="shapeBrowser._goPage(${this._currentPage - 1})" ${this._currentPage === 0 ? 'disabled' : ''}>上一页</button>
            <span>${this._currentPage + 1} / ${totalPages}</span>
            <button onclick="shapeBrowser._goPage(${this._currentPage + 1})" ${this._currentPage >= totalPages - 1 ? 'disabled' : ''}>下一页</button>
            <button onclick="shapeBrowser._goPage(${totalPages - 1})" ${this._currentPage >= totalPages - 1 ? 'disabled' : ''}>末页</button>`;
        pg.innerHTML = html;
    },

    _goPage(n) {
        const files = this._allFiles[this._currentCategory] || [];
        const totalPages = Math.max(1, Math.ceil(files.length / this._pageSize));
        if (n < 0) n = 0;
        if (n >= totalPages) n = totalPages - 1;
        this._currentPage = n;
        this._renderGrid();
    },

    _toggleSelect(el, path) {
        if (this._selectedFiles.has(path)) {
            this._selectedFiles.delete(path);
            el.classList.remove('selected');
        } else {
            this._selectedFiles.add(path);
            el.classList.add('selected');
        }
        this._updateSelectionInfo();
    },

    selectAll() {
        const files = this._allFiles[this._currentCategory] || [];
        const start = this._currentPage * this._pageSize;
        const page = files.slice(start, start + this._pageSize);
        const allSelected = page.every(f => this._selectedFiles.has(f.path));
        if (allSelected) {
            page.forEach(f => this._selectedFiles.delete(f.path));
        } else {
            page.forEach(f => this._selectedFiles.add(f.path));
        }
        this._renderGrid();
        this._updateSelectionInfo();
    },

    _updateSelectionInfo() {
        const info = document.getElementById('shapeSelInfo');
        if (info) info.textContent = this._selectedFiles.size > 0 ? `已选 ${this._selectedFiles.size} 个文件` : '';
    },

    async _preview(path) {
        const modal = document.getElementById('shapePreviewModal');
        const img = document.getElementById('shapePreviewImg');
        const info = document.getElementById('shapePreviewInfo');
        if (!modal || !img) return;
        modal.style.display = 'flex';
        img.src = '';
        info.textContent = '加载中...';
        try {
            let apiName = 'previewBfobjShp';
            if (this._currentCategory === 'Face') {
                // Face uses existing API
                const faceId = parseInt(path.replace(/\D/g, ''));
                const r = await pyApi('getFacePreview', faceId);
                if (r && r.success) {
                    img.src = 'data:image/png;base64,' + r.imgData;
                    info.textContent = path;
                } else {
                    info.textContent = '预览失败: ' + (r ? r.message : '');
                }
                return;
            } else if (this._currentCategory === 'genhalf') {
                apiName = 'previewGenhalfShp';
            }
            const r = await pyApi(apiName, path);
            if (r && r.success && r.image_base64) {
                img.src = 'data:image/png;base64,' + r.image_base64;
                info.textContent = path + ' (' + (r.size || '') + ')';
            } else {
                info.textContent = '预览失败: ' + (r ? r.message : '');
            }
        } catch(e) {
            info.textContent = '预览失败: ' + e;
        }
    },

    closePreview() {
        const modal = document.getElementById('shapePreviewModal');
        if (modal) modal.style.display = 'none';
    },

    async batchImport() {
        const src = prompt('输入源图片路径 (支持 BMP/PNG/JPG):');
        if (!src) return;
        try {
            let apiName = 'convertImageToBfobjShp';
            if (this._currentCategory === 'Face') {
                const faceId = prompt('输入目标头像编号 (如 1000):');
                if (!faceId) return;
                const r = await pyApi('convertImageToShp', src, parseInt(faceId));
                showToast(r && r.success ? r.message : '导入失败: ' + (r ? r.message : ''), 'info');
            } else if (this._currentCategory === 'genhalf') {
                apiName = 'importImageToGenhalf';
            }
            const r = await pyApi(apiName, src, '');
            if (r && r.success) {
                showToast(r.message, 'info');
                await this._refresh();
            } else {
                showToast('导入失败: ' + (r ? r.message : ''), 'error');
            }
        } catch(e) {
            showToast('导入失败: ' + e, 'error');
        }
    },

    async batchDelete() {
        if (this._selectedFiles.size === 0) {
            showToast('请先选择要删除的文件', 'warning');
            return;
        }
        if (!confirm(`确定要删除 ${this._selectedFiles.size} 个文件吗？此操作不可恢复！\n(会自动备份为 .modbak)`)) return;
        try {
            const paths = Array.from(this._selectedFiles);
            const r = await pyApi('shapeBatchDelete', this._currentCategory, paths);
            if (r && r.success) {
                showToast(`删除完成: ${r.count} 个成功${r.failed.length > 0 ? ', ' + r.failed.length + ' 个失败' : ''}`, 'info');
            } else {
                showToast('删除失败: ' + (r ? r.message : ''), 'error');
            }
            this._selectedFiles.clear();
            await this._refresh();
        } catch(e) {
            showToast('删除失败: ' + e, 'error');
        }
    },

    async batchExport() {
        if (this._selectedFiles.size === 0) {
            showToast('请先选择要导出的文件', 'warning');
            return;
        }
        try {
            const paths = Array.from(this._selectedFiles);
            const r = await pyApi('shapeBatchExport', this._currentCategory, paths);
            if (r && r.success) {
                showToast(`导出完成: ${r.count} 个成功 → ${r.output_dir}${r.failed.length > 0 ? '\n' + r.failed.length + ' 个失败' : ''}`, 'info');
            } else {
                showToast('导出失败: ' + (r ? r.message : ''), 'error');
            }
        } catch(e) {
            showToast('导出失败: ' + e, 'error');
        }
    },

    async batchShpConvert() {
        const category = document.getElementById('shpBatchCategory').value;
        const pngDir = document.getElementById('shpBatchPngDir').value.trim();
        const resultEl = document.getElementById('shpBatchResult');
        if (resultEl) resultEl.innerHTML = '<span style="color:var(--warning);">正在转换...</span>';
        try {
            const res = await pyApi('shpBatchConvert', category, pngDir || null);
            if (resultEl) {
                if (res && res.success) {
                    resultEl.innerHTML = `<span style="color:var(--success);">转换完成: ${res.converted || 0} 成功, ${res.failed || 0} 失败</span>`;
                } else {
                    resultEl.innerHTML = `<span style="color:var(--danger);">转换失败: ${res ? res.message : '未知错误'}</span>`;
                }
            }
            if (res && res.message) showToast(res.message, res.success ? 'success' : 'error');
        } catch(e) {
            if (resultEl) resultEl.innerHTML = `<span style="color:var(--danger);">转换异常: ${e}</span>`;
            showToast('转换异常: ' + e, 'error');
        }
    },
};

// ============================================================
// 历史事件编辑器 (History.ini)
// ============================================================

const historyEditor = {
    _data: [],
    _selectedIndex: -1,
    _dirty: false,

    async load() {
        const res = await pyApi('loadHistories');
        if (res.success) {
            this._data = res.data || [];
            this.renderList();
            document.getElementById('historyCount').textContent = `共 ${this._data.length} 个事件`;
        } else {
            showToast(res.message || '加载失败', 'warning');
        }
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        if (!this._dirty) { showToast('没有修改需要保存', 'success'); return; }
        this.pushUndo();
        const res = await pyApi('saveHistories', this._data);
        if (res.success) {
            this._dirty = false;
            showToast(res.message, res && res.success ? 'success' : 'error');
        } else {
            showToast(res.message || '保存失败', 'warning');
        }
    },

    async addNew() {
        const maxNo = this._data.reduce((max, h) => Math.max(max, parseInt(h.No) || 0), 0);
        const res = await pyApi('newHistory');
        if (!res.success) {
            showToast(res.message || '创建失败', 'error');
            return;
        }
        const entry = res.data || {};
        entry.No = String(maxNo + 1);
        this._data.push(entry);
        this._dirty = true;
        this._selectedIndex = this._data.length - 1;
        this.renderList();
        this.renderDetail();
        document.getElementById('historyCount').textContent = `共 ${this._data.length} 个事件`;
    },

    async clone() {
        if (this._selectedIndex < 0) { showToast('请先选择一个事件', 'warning'); return; }
        const maxNo = this._data.reduce((max, h) => Math.max(max, parseInt(h.No) || 0), 0);
        const clone = { ...this._data[this._selectedIndex] };
        clone.No = String(maxNo + 1);
        this._data.push(clone);
        this._dirty = true;
        this._selectedIndex = this._data.length - 1;
        this.renderList();
        this.renderDetail();
        document.getElementById('historyCount').textContent = `共 ${this._data.length} 个事件`;
    },

    delete() {
        if (this._selectedIndex < 0) { showToast('请先选择一个事件', 'warning'); return; }
        const h = this._data[this._selectedIndex];
        if (!confirm(`确认删除事件 #${h.No}？`)) return;
        this._data.splice(this._selectedIndex, 1);
        this._dirty = true;
        this._selectedIndex = Math.min(this._selectedIndex, this._data.length - 1);
        this.renderList();
        this.renderDetail();
        document.getElementById('historyCount').textContent = `共 ${this._data.length} 个事件`;
    },

    select(index) {
        this._selectedIndex = index;
        this.renderList();
        this.renderDetail();
    },

    renderList() {
        const container = document.getElementById('historyList');
        if (!container) return;
        container.innerHTML = this._data.map((h, i) => {
            const no = h.No || '?';
            const ctype = h.ClassType || '0';
            const typeName = this._getClassTypeName(parseInt(ctype));
            const isUsed = h.IsUsed === '1';
            const selected = i === this._selectedIndex;
            return `<div class="history-list-item ${selected ? 'selected' : ''}" onclick="historyEditor.select(${i})" style="padding:8px;cursor:pointer;border-bottom:1px solid var(--border);${selected ? 'background:var(--accent);color:white;' : ''}">
                <strong>#${no}</strong> <span style="font-size:11px;">${typeName}</span>
                ${isUsed ? '' : '<span style="color:var(--text-muted);font-size:10px;"> (禁用)</span>'}
            </div>`;
        }).join('');
    },

    renderDetail() {
        const container = document.getElementById('historyDetail');
        if (!container) return;
        if (this._selectedIndex < 0 || this._selectedIndex >= this._data.length) {
            container.innerHTML = '<p style="color:var(--text-muted);padding:20px;">请从左侧列表选择一个事件</p>';
            return;
        }
        const h = this._data[this._selectedIndex];
        const groups = [
            { name: '基本信息', fields: ['No', 'ClassType', 'Priority', 'Age', 'S_Year', 'S_Season', 'E_Year', 'E_Season', 'IsUsed', 'Version'] },
            { name: '事件链', fields: ['PreHistory', 'NedHistory01', 'NedHistory02', 'NedHistory03', 'Pic'] },
            { name: '参与君主', fields: ['LordA', 'LordALv', 'bCustomA', 'LordB', 'LordBLv', 'bCustomB', 'LordC', 'LorCLv', 'bCustomC', 'bDead'] },
            { name: '源方对话', fields: ['S_ProposeGeneral', 'S_ProposeString', 'S_AnsProposeString', 'S_DiplomaticGeneral', 'S_DiplomaticString'] },
            { name: '触发条件', fields: ['N_MinRelation', 'N_MinMoney', 'N_MaxMoney', 'N_MinGenNum', 'N_MinCityNum', 'N_MinPeopleHeart', 'N_SpecCity01', 'N_SpecCity02', 'N_SpecCity03', 'N_SpecCity04', 'N_SpecCity05', 'N_MinThingNum', 'N_OwnThing01', 'N_OwnThing02', 'N_OwnThing03', 'N_OwnThing04', 'N_OwnThing05'] },
            { name: '事件奖励', fields: ['Thing01', 'ThingNum01', 'Thing02', 'ThingNum02', 'Thing03', 'ThingNum03', 'Thing04', 'ThingNum04', 'Thing05', 'ThingNum05', 'Money', 'MoneyRatio', 'People', 'PeopleHeart', 'ReserveSoldier'] },
            { name: '属性/技能', fields: ['Str', 'Int', 'HP', 'MP', 'Title01', 'Title02', 'Title03', 'Title04', 'Title05', 'SFMagic', 'BFMagic', 'GenSkill', 'ArmySkill', 'ArmyGroupSkill'] },
            { name: '其他', fields: ['Relation', 'AllianceDay', 'BlockNo', 'BreakDays', 'BlockIndex', 'FreeDays', 'F_Relation'] },
        ];

        let html = '';
        groups.forEach(g => {
            html += `<div class="history-group" style="margin-bottom:12px;">
                <h4 style="font-size:13px;color:var(--text-secondary);margin:0 0 6px 0;border-bottom:1px solid var(--border);padding-bottom:4px;">${g.name}</h4>
                <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:6px;">`;
            g.fields.forEach(f => {
                const val = h[f] !== undefined ? h[f] : '';
                const label = this._getFieldLabel(f);
                html += `<div style="display:flex;align-items:center;gap:4px;">
                    <span style="font-size:11px;color:var(--text-muted);min-width:70px;text-align:right;">${label}</span>
                    <input type="text" value="${this._escapeHtml(String(val))}" onchange="historyEditor._updateField('${f}', this.value)" style="flex:1;font-size:12px;padding:2px 4px;min-width:0;">
                </div>`;
            });
            html += `</div></div>`;
        });

        // Source characters (1-10) compact
        html += `<div class="history-group" style="margin-bottom:12px;">
            <h4 style="font-size:13px;color:var(--text-secondary);margin:0 0 6px 0;border-bottom:1px solid var(--border);padding-bottom:4px;">源方武将 (S_)</h4>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:4px;">`;
        for (let i = 1; i <= 10; i++) {
            const si = String(i).padStart(2, '0');
            const g = h[`S_General${si}`] || '';
            const str = h[`S_StringA${si}`] || '';
            html += `<div style="font-size:11px;padding:2px 4px;background:var(--bg-card);border-radius:3px;">
                <span style="color:var(--text-muted);">#${i}</span>
                <input type="text" value="${this._escapeHtml(String(g))}" onchange="historyEditor._updateField('S_General${si}', this.value)" style="width:55px;font-size:11px;padding:1px 2px;" placeholder="武将">
                <input type="text" value="${this._escapeHtml(String(str))}" onchange="historyEditor._updateField('S_StringA${si}', this.value)" style="width:55px;font-size:11px;padding:1px 2px;" placeholder="台词">
                <input type="text" value="${this._escapeHtml(String(h['S_StringD'+si]||''))}" onchange="historyEditor._updateField('S_StringD${si}', this.value)" style="width:55px;font-size:10px;padding:1px;" placeholder="文本">
                <input type="text" value="${this._escapeHtml(String(h['S_MinGenLv'+si]||''))}" onchange="historyEditor._updateField('S_MinGenLv${si}', this.value)" style="width:35px;font-size:10px;padding:1px;" title="最低等级">
                <input type="text" value="${this._escapeHtml(String(h['S_MinLoyal'+si]||''))}" onchange="historyEditor._updateField('S_MinLoyal${si}', this.value)" style="width:35px;font-size:10px;padding:1px;" title="最低义理">
                <input type="text" value="${this._escapeHtml(String(h['S_City'+si]||''))}" onchange="historyEditor._updateField('S_City${si}', this.value)" style="width:35px;font-size:10px;padding:1px;" title="限定城池">
            </div>`;
        }
        html += `</div></div>`;

        // Destination characters (1-10) compact
        html += `<div class="history-group" style="margin-bottom:12px;">
            <h4 style="font-size:13px;color:var(--text-secondary);margin:0 0 6px 0;border-bottom:1px solid var(--border);padding-bottom:4px;">目标方武将 (D_)</h4>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:4px;">`;
        for (let i = 1; i <= 10; i++) {
            const si = String(i).padStart(2, '0');
            const g = h[`D_General${si}`] || '';
            const str = h[`D_StringA${si}`] || '';
            html += `<div style="font-size:11px;padding:2px 4px;background:var(--bg-card);border-radius:3px;">
                <span style="color:var(--text-muted);">#${i}</span>
                <input type="text" value="${this._escapeHtml(String(g))}" onchange="historyEditor._updateField('D_General${si}', this.value)" style="width:55px;font-size:11px;padding:1px 2px;" placeholder="武将">
                <input type="text" value="${this._escapeHtml(String(str))}" onchange="historyEditor._updateField('D_StringA${si}', this.value)" style="width:55px;font-size:11px;padding:1px 2px;" placeholder="台词">
                <input type="text" value="${this._escapeHtml(String(h['D_StringD'+si]||''))}" onchange="historyEditor._updateField('D_StringD${si}', this.value)" style="width:55px;font-size:10px;padding:1px;" placeholder="文本">
                <input type="text" value="${this._escapeHtml(String(h['D_MinGenLv'+si]||''))}" onchange="historyEditor._updateField('D_MinGenLv${si}', this.value)" style="width:35px;font-size:10px;padding:1px;" title="最低等级">
                <input type="text" value="${this._escapeHtml(String(h['D_MinLoyal'+si]||''))}" onchange="historyEditor._updateField('D_MinLoyal${si}', this.value)" style="width:35px;font-size:10px;padding:1px;" title="最低义理">
                <input type="text" value="${this._escapeHtml(String(h['D_City'+si]||''))}" onchange="historyEditor._updateField('D_City${si}', this.value)" style="width:35px;font-size:10px;padding:1px;" title="限定城池">
            </div>`;
        }
        html += `</div></div>`;

        container.innerHTML = html;
    },

    _updateField(field, value) {
        if (this._selectedIndex < 0) return;
        this._data[this._selectedIndex][field] = value;
        this._dirty = true;
    },

    _getClassTypeName(type) {
        const map = { 1: '武将表演', 5: '发现宝物', 6: '发现宝物(名将)', 10: '婚嫁', 15: '势力投靠', 20: '武将强化', 30: '通用事件' };
        return map[type] || `类型${type}`;
    },

    _getFieldLabel(field) {
        const labels = {
            'No': '编号', 'ClassType': '类型', 'Priority': '优先级', 'Age': '时代',
            'S_Year': '开始年', 'S_Season': '开始季', 'E_Year': '结束年', 'E_Season': '结束季',
            'PreHistory': '前置事件', 'NedHistory01': '需要事件1', 'NedHistory02': '需要事件2', 'NedHistory03': '需要事件3', 'Pic': 'CG图片',
            'LordA': '君主A', 'LordALv': 'A等级', 'bCustomA': 'A自定义',
            'LordB': '君主B', 'LordBLv': 'B等级', 'bCustomB': 'B自定义',
            'LordC': '君主C', 'LorCLv': 'C等级', 'bCustomC': 'C自定义', 'bDead': '死亡',
            'S_ProposeGeneral': '提议武将', 'S_ProposeString': '提议台词', 'S_AnsProposeString': '反对台词',
            'S_DiplomaticGeneral': '外交武将', 'S_DiplomaticString': '外交台词',
            'N_MinRelation': '最少友好', 'N_MinMoney': '最少金钱', 'N_MaxMoney': '最多金钱',
            'N_MinGenNum': '最少武将', 'N_MinCityNum': '最少城池', 'N_MinPeopleHeart': '最少民心',
            'N_SpecCity01': '指定城市1', 'N_SpecCity02': '指定城市2', 'N_SpecCity03': '指定城市3',
            'N_SpecCity04': '指定城市4', 'N_SpecCity05': '指定城市5',
            'N_MinThingNum': '最少物品', 'N_OwnThing01': '应有物品1', 'N_OwnThing02': '应有物品2',
            'N_OwnThing03': '应有物品3', 'N_OwnThing04': '应有物品4', 'N_OwnThing05': '应有物品5',
            'Thing01': '物品1', 'ThingNum01': '数量1', 'Thing02': '物品2', 'ThingNum02': '数量2',
            'Thing03': '物品3', 'ThingNum03': '数量3', 'Thing04': '物品4', 'ThingNum04': '数量4',
            'Thing05': '物品5', 'ThingNum05': '数量5', 'Money': '金钱', 'MoneyRatio': '金钱系数',
            'People': '人口', 'PeopleHeart': '民心', 'ReserveSoldier': '预备兵',
            'Str': '武力', 'Int': '智力', 'HP': '体力', 'MP': '技力',
            'Title01': '官职1', 'Title02': '官职2', 'Title03': '官职3', 'Title04': '官职4', 'Title05': '官职5',
            'SFMagic': '军师技', 'BFMagic': '武将技', 'GenSkill': '个人特性', 'ArmySkill': '主将特性', 'ArmyGroupSkill': '元帅特性',
            'Relation': '友好度', 'AllianceDay': '同盟天数', 'BlockNo': '封锁编号',
            'BreakDays': '中断天数', 'BlockIndex': '封锁索引', 'FreeDays': '空闲天数',
            'F_Relation': '最终友好', 'IsUsed': '启用', 'Version': '版本',
        };
        return labels[field] || field;
    },

    _escapeHtml(str) {
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    },

    _filterList(keyword) {
        const container = document.getElementById('historyList');
        if (!container) return;
        const items = container.querySelectorAll('.history-list-item');
        items.forEach(item => {
            if (!keyword) { item.style.display = ''; return; }
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(keyword.toLowerCase()) ? '' : 'none';
        });
    },

    snapshot() {
        return {
            _data: JSON.parse(JSON.stringify(this._data)),
            _selectedIndex: this._selectedIndex,
        };
    },

    restoreSnapshot(data) {
        this._data = data._data ? JSON.parse(JSON.stringify(data._data)) : [];
        this._selectedIndex = data._selectedIndex != null ? data._selectedIndex : -1;
        this._dirty = false;
        this.renderList();
        document.getElementById('historyCount').textContent = `共 ${this._data.length} 个事件`;
        if (this._selectedIndex >= 0) this.renderDetail();
    },

    pushUndo() {
        UndoManager.pushState('history', this.snapshot());
    },
};

// ============================================================
// 脚本编辑器 (Script/)
// ============================================================

const scriptEditor = {
    _files: [],
    _currentFile: null,
    _content: '',
    _originalContent: '',
    _dirty: false,

    async load() {
        const res = await pyApi('listScripts');
        if (res.success) {
            this._files = res.files || [];
            this.renderFileList();
            document.getElementById('scriptStatus').textContent = `共 ${this._files.length} 个脚本`;
        } else {
            showToast(res.message || '加载失败', 'warning');
        }
    },

    async openFile(filename) {
        const res = await pyApi('readScript', filename);
        if (res.success) {
            this._currentFile = filename;
            this._content = res.content;
            this._originalContent = res.content;
            this._dirty = false;
            document.getElementById('scriptFileName').textContent = filename;
            document.getElementById('scriptFileInfo').textContent = `${res.lines} 行 | ${res.size_kb} KB`;
            document.getElementById('scriptEditorArea').value = res.content;
            this.renderFileList(); // re-highlight
        } else {
            showToast(res.message || '读取失败', 'warning');
        }
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        if (!this._currentFile) { showToast('请先选择一个脚本文件', 'warning'); return; }
        const content = document.getElementById('scriptEditorArea').value;
        if (content === this._originalContent) { showToast('内容未修改', 'info'); return; }
        this.pushUndo();
        if (!confirm(`确认保存 ${this._currentFile}？这将覆盖原文件。`)) return;
        const res = await pyApi('saveScript', this._currentFile, content);
        if (res.success) {
            this._originalContent = content;
            this._dirty = false;
            showToast(res.message || '保存成功', 'success');
        } else {
            showToast(res.message || '保存失败', 'error');
        }
    },

    onEditorChange() {
        const content = document.getElementById('scriptEditorArea').value;
        this._content = content;
        this._dirty = content !== this._originalContent;
    },

    snapshot() {
        return {
            _currentFile: this._currentFile,
            _content: this._content,
            _originalContent: this._originalContent,
        };
    },

    restoreSnapshot(data) {
        this._currentFile = data._currentFile || null;
        this._content = data._content || '';
        this._originalContent = data._originalContent || '';
        this._dirty = false;
        document.getElementById('scriptEditorArea').value = this._content;
        document.getElementById('scriptFileName').textContent = this._currentFile || '';
    },

    pushUndo() {
        UndoManager.pushState('script', this.snapshot());
    },

    renderFileList() {
        const container = document.getElementById('scriptFileList');
        if (!container) return;
        container.innerHTML = this._files.map(f => {
            const selected = this._currentFile === f.name;
            return `<div class="script-file-item" onclick="scriptEditor.openFile('${escHtml(f.name)}')" style="padding:8px 12px;cursor:pointer;border-bottom:1px solid var(--border);${selected ? 'background:var(--accent);color:white;' : ''}">
                <div style="font-size:13px;">${escHtml(f.name)}</div>
                <div style="font-size:11px;color:${selected ? 'rgba(255,255,255,0.7)' : 'var(--text-muted)'};">${escHtml(String(f.size_kb))} KB</div>
            </div>`;
        }).join('');
    },

    async newFile() {
        const name = prompt('请输入新脚本文件名:');
        if (!name) return;
        const res = await pyApi('newScript', name);
        if (res.success) {
            showToast(res.message, 'success');
            await this.load();
        } else {
            showToast(res.message || '创建失败', 'error');
        }
    },

    async deleteFile() {
        if (!this._currentFile) { showToast('请先选择一个脚本文件', 'warning'); return; }
        if (!confirm(`确认删除 ${this._currentFile}？此操作不可撤销。`)) return;
        const res = await pyApi('deleteScript', this._currentFile);
        if (res.success) {
            this._currentFile = null;
            this._content = '';
            this._originalContent = '';
            document.getElementById('scriptEditorArea').value = '';
            document.getElementById('scriptFileName').textContent = '—';
            showToast(res.message, 'success');
            await this.load();
        } else {
            showToast(res.message || '删除失败', 'error');
        }
    },

    async renameFile() {
        if (!this._currentFile) { showToast('请先选择一个脚本文件', 'warning'); return; }
        const newName = prompt('请输入新文件名:', this._currentFile);
        if (!newName || newName === this._currentFile) return;
        const res = await pyApi('renameScript', this._currentFile, newName);
        if (res.success) {
            this._currentFile = newName;
            document.getElementById('scriptFileName').textContent = newName;
            showToast(res.message, 'success');
            await this.load();
        } else {
            showToast(res.message || '重命名失败', 'error');
        }
    }
};

// ============================================================
// Script.so 分析器
// ============================================================

const scriptsoEditor = {
    async load() {
        document.getElementById('scriptsoStatus').textContent = '分析中...';
        try {
            // 加载文件信息
            const info = await pyApi('scriptsoInfo');
            if (info && info.exists) {
                document.getElementById('scriptsoInfoPanel').style.display = 'block';
                const infoContent = document.getElementById('scriptsoInfoContent');
                const elf = info.elf_info || {};
                infoContent.innerHTML = `<div style="display:grid;grid-template-columns:auto 1fr;gap:4px 12px;">
                    <span style="color:var(--text-muted);">文件:</span><span>Script.so</span>
                    <span style="color:var(--text-muted);">大小:</span><span>${info.size_mb} MB (${info.size_kb} KB)</span>
                    <span style="color:var(--text-muted);">格式:</span><span>${info.is_elf ? 'ELF (' + (elf.class||'?') + ', ' + (elf.type||'?') + ')' : '未知二进制'}</span>
                    <span style="color:var(--text-muted);">架构:</span><span>${elf.machine || '—'}</span>
                    <span style="color:var(--text-muted);">字节序:</span><span>${elf.endian || '—'}</span>
                    <span style="color:var(--text-muted);">系统:</span><span>${elf.osabi || '—'}</span>
                </div>`;
                document.getElementById('scriptsoStatus').textContent = `已加载 (${info.size_mb} MB)`;
            } else {
                document.getElementById('scriptsoInfoPanel').style.display = 'none';
                document.getElementById('scriptsoStatus').textContent = 'Script.so 不存在';
            }

            // 加载字符串分析
            const strings = await pyApi('scriptsoStrings');
            if (strings && strings.success && strings.total_strings > 0) {
                document.getElementById('scriptsoStringListPanel').style.display = 'block';
                document.getElementById('scriptsoStringCount').textContent = `共 ${strings.total_strings} 个字符串`;
                const strList = document.getElementById('scriptsoStringList');
                const allStrings = strings.all_strings || [];
                strList.innerHTML = allStrings.slice(0, 200).map(s =>
                    `<span style="display:inline-block;margin:1px 2px;padding:1px 4px;background:var(--bg-input);border-radius:3px;font-size:10px;" title="0x${s.offset.toString(16)}">${escHtml(s.text)}</span>`
                ).join('');

                // 显示模式匹配
                if (strings.pattern_count > 0) {
                    document.getElementById('scriptsoPatternsPanel').style.display = 'block';
                    const patContent = document.getElementById('scriptsoPatternsContent');
                    patContent.innerHTML = Object.entries(strings.patterns).map(([name, p]) =>
                        `<div style="margin-bottom:6px;">
                            <div style="font-weight:600;font-size:11px;color:var(--accent);">${name} <span style="color:var(--text-muted);font-weight:400;">(${p.count}个)</span></div>
                            <div style="font-size:10px;color:var(--text-muted);">${(p.samples||[]).slice(0, 8).join(', ')}</div>
                        </div>`
                    ).join('');
                } else {
                    document.getElementById('scriptsoPatternsPanel').style.display = 'none';
                }
            } else {
                document.getElementById('scriptsoStringListPanel').style.display = 'none';
                document.getElementById('scriptsoPatternsPanel').style.display = 'none';
            }

            // 加载文件列表
            const files = await pyApi('scriptsoListFiles');
            if (files && files.success && files.files.length > 0) {
                document.getElementById('scriptsoFilesPanel').style.display = 'block';
                const filesContent = document.getElementById('scriptsoFilesContent');
                filesContent.innerHTML = files.files.map(f =>
                    `<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid var(--border);font-size:11px;">
                        <span>${escHtml(f.name)}</span>
                        <span style="color:var(--text-muted);">${f.size_kb} KB</span>
                    </div>`
                ).join('');
            }

            // 显示hex面板
            document.getElementById('scriptsoHexPanel').style.display = 'block';
            this.hexView(); // 默认显示前512字节

            // 加载编辑面板
            document.getElementById('scriptsoEditPanel').style.display = 'block';
            document.getElementById('scriptsoStrReplacePanel').style.display = 'block';
            this.loadPatches();
            this.loadCommunityPatches();
        } catch(e) {
            document.getElementById('scriptsoStatus').textContent = '加载失败';
        }
    },

    async hexView() {
        const offset = parseInt(document.getElementById('scriptsoHexOffset').value) || 0;
        const length = parseInt(document.getElementById('scriptsoHexLength').value) || 512;
        try {
            const r = await pyApi('scriptsoHexView', offset, length);
            if (r && r.success) {
                document.getElementById('scriptsoHexContent').textContent = r.hex_lines.join('\n') +
                    `\n\n--- 偏移: 0x${offset.toString(16)}, 长度: ${r.length} / ${r.total_size} 字节 ---`;
            }
        } catch(e) { showToast('十六进制查看失败: ' + e.message, 'error'); }
    },

    async hexSearch() {
        const pattern = document.getElementById('scriptsoHexSearch').value.trim();
        if (!pattern) { showToast('请输入搜索模式', 'warning'); return; }
        try {
            const r = await pyApi('scriptsoHexSearch', pattern);
            if (r && r.success) {
                showToast(`找到 ${r.match_count} 处匹配\n位置: ${(r.positions||[]).slice(0, 10).join(', ')}${r.match_count>10?'...':''}`, 'info');
            }
        } catch(e) { showToast('搜索失败: '+e, 'error'); }
    },

    async backup() {
        try {
            const r = await pyApi('scriptsoBackup');
            if (r) showToast(r.success ? r.message : '备份失败: '+r.message, 'info');
        } catch(e) { showToast('备份失败: '+e, 'error'); }
    },

    async hexWrite() {
        const offsetStr = document.getElementById('scriptsoEditOffset').value.trim();
        const dataHex = document.getElementById('scriptsoEditData').value.trim();
        if (!offsetStr || !dataHex) { showToast('请输入偏移和HEX数据', 'warning'); return; }
        let offset = parseInt(offsetStr, offsetStr.startsWith('0x')?16:10);
        if (isNaN(offset)) { showToast('无效的偏移值', 'warning'); return; }
        try {
            const r = await pyApi('scriptsoHexWrite', offset, dataHex);
            const el = document.getElementById('scriptsoEditResult');
            if (r && r.success) {
                el.textContent = `✓ 已写入 ${r.size} 字节 @ ${r.offset_hex}`;
                el.style.color = 'var(--success)';
            } else {
                el.textContent = '✗ ' + (r?r.message:'失败');
                el.style.color = 'var(--danger)';
            }
        } catch(e) {
            document.getElementById('scriptsoEditResult').textContent = '✗ '+e;
            document.getElementById('scriptsoEditResult').style.color = 'var(--danger)';
        }
    },

    async stringReplace() {
        const oldText = document.getElementById('scriptsoStrFind').value.trim();
        const newText = document.getElementById('scriptsoStrReplace').value.trim();
        if (!oldText || !newText) { showToast('请输入查找和替换字符串', 'warning'); return; }
        if (newText.length > oldText.length) { showToast('新字符串不能比旧字符串长', 'info'); return; }
        try {
            const r = await pyApi('scriptsoStringReplace', oldText, newText);
            const el = document.getElementById('scriptsoStrResult');
            if (r && r.success) {
                el.textContent = `✓ ${r.message}`;
                el.style.color = 'var(--success)';
            } else {
                el.textContent = '✗ ' + (r?r.message:'失败');
                el.style.color = 'var(--danger)';
            }
        } catch(e) {
            document.getElementById('scriptsoStrResult').textContent = '✗ '+e;
            document.getElementById('scriptsoStrResult').style.color = 'var(--danger)';
        }
    },

    async loadPatches() {
        try {
            const r = await pyApi('scriptsoGetPatches');
            if (r && r.success && r.patches) {
                document.getElementById('scriptsoPatchPanel').style.display = 'block';
                const list = document.getElementById('scriptsoPatchList');
                list.innerHTML = r.patches.map(p => `
                    <div style="padding:4px 6px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;">
                        <div style="flex:1;min-width:0;">
                            <span style="font-weight:600;">${escHtml(p.description)}</span>
                            <span style="color:var(--text-muted);margin-left:6px;">[${p.value_type}]</span>
                            <div style="font-size:10px;color:var(--text-muted);">${escHtml(p.note)}</div>
                        </div>
                        <div style="display:flex;gap:4px;flex-shrink:0;">
                            <button onclick="scriptsoEditor.searchPatch('${p.id}')" class="btn btn-sm">搜索偏移</button>
                            <button onclick="scriptsoEditor._showApplyDialog('${p.id}')" class="btn btn-sm btn-primary">应用</button>
                        </div>
                    </div>
                `).join('');
            }
        } catch(e) { showToast('加载补丁列表失败', 'error'); }
    },

    async searchPatch(patchId) {
        try {
            const r = await pyApi('scriptsoSearchPatch', patchId);
            if (r && r.success) {
                this._lastSearchResult = r;
                let msg = `补丁: ${r.description}\n搜索模式: ${r.pattern}\n类型: ${r.value_type}\n`;
                if (r.candidates && r.candidates.length > 0) {
                    msg += `\n找到 ${r.candidates.length} 个候选位置:\n`;
                    r.candidates.forEach(c => {
                        msg += `\n  ${c.string_offset}: "${c.string_text}"`;
                        if (c.nearby_values && c.nearby_values.length > 0) {
                            c.nearby_values.slice(0, 5).forEach(v => {
                                msg += `\n    ${v.offset} (Δ${v.delta}): int32=${v.int32}, float=${v.float}`;
                            });
                        }
                    });
                } else {
                    msg += `\n${r.message || '未找到匹配'}`;
                }
                if (r.note) msg += `\n\n提示: ${r.note}`;
                showToast(msg, 'info');
            } else {
                showToast('搜索失败: ' + (r?r.message:'未知错误'), 'error');
            }
        } catch(e) { showToast('搜索失败: '+e, 'error'); }
    },

    _showApplyDialog(patchId) {
        // 先搜索偏移
        pyApi('scriptsoSearchPatch', patchId).then(r => {
            if (!r || !r.success) { showToast('搜索失败: ' + (r?r.message:''), 'error'); return; }
            this._lastSearchResult = r;
            const candidates = r.candidates || [];
            let html = `<div style="padding:12px;min-width:400px;">
                <h3 style="margin:0 0 8px;">应用补丁: ${escHtml(r.description)}</h3>
                <p style="font-size:12px;color:var(--text-muted);">类型: ${r.value_type} | 模式: ${escHtml(r.pattern)}</p>`;
            if (candidates.length === 0) {
                html += `<p style="color:var(--danger);">未找到候选位置</p>`;
            } else {
                html += `<div style="margin:8px 0;">
                    <label style="font-size:12px;">选择候选位置:</label>
                    <select id="ssoPatchOffset" style="width:100%;margin:4px 0;font-family:monospace;font-size:11px;">`;
                candidates.forEach(c => {
                    if (c.nearby_values && c.nearby_values.length > 0) {
                        c.nearby_values.slice(0, 3).forEach(v => {
                            const valDisplay = r.value_type === 'float' ? v.float : v.int32;
                            html += `<option value="${v.offset}">${v.offset} (Δ${v.delta}) 当前值=${valDisplay} — "${c.string_text}"</option>`;
                        });
                    }
                });
                html += `</select></div>
                <div style="margin:8px 0;">
                    <label style="font-size:12px;">新值:</label>
                    <input type="text" id="ssoPatchNewVal" style="width:100%;margin:4px 0;font-family:monospace;font-size:13px;" placeholder="${r.value_type === 'float' ? '如 2.5' : '如 999'}">
                </div>`;
            }
            html += `<div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px;">
                <button onclick="document.getElementById('ssoPatchModal').style.display='none'" class="btn btn-outline btn-sm">取消</button>
                ${candidates.length > 0 ? '<button onclick="scriptsoEditor._applyPatch()" class="btn btn-primary btn-sm">确认应用</button>' : ''}
            </div></div>`;

            // 创建模态框
            let modal = document.getElementById('ssoPatchModal');
            if (!modal) {
                modal = document.createElement('div');
                modal.id = 'ssoPatchModal';
                modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:9999;';
                modal.onclick = function(e) { if (e.target === modal) modal.style.display = 'none'; };
                document.body.appendChild(modal);
            }
            modal.innerHTML = `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;box-shadow:0 4px 24px rgba(0,0,0,0.5);">${html}</div>`;
            modal.style.display = 'flex';
        }).catch(e => { showToast('搜索失败: '+e, 'error'); });
    },

    async _applyPatch() {
        const offsetStr = document.getElementById('ssoPatchOffset')?.value;
        const newValStr = document.getElementById('ssoPatchNewVal')?.value;
        if (!offsetStr || !newValStr) { showToast('请选择偏移并输入新值', 'info'); return; }
        const offset = parseInt(offsetStr, 16);
        if (isNaN(offset)) { showToast('无效的偏移', 'warning'); return; }
        const r = this._lastSearchResult;
        if (!r) { showToast('搜索结果已过期', 'info'); return; }
        const vt = r.value_type || 'int32';
        let newValue = vt === 'float' ? parseFloat(newValStr) : parseInt(newValStr);
        if (isNaN(newValue)) { showToast('无效的新值', 'warning'); return; }
        try {
            const result = await pyApi('scriptsoApplyPatch', r.patch_id, offset, newValue, vt);
            if (result && result.success) {
                showToast(`✓ 补丁应用成功!\n${result.description}\n偏移: ${result.offset_hex}\n旧值: ${result.old_value} → 新值: ${result.new_value}`, 'info');
                document.getElementById('ssoPatchModal').style.display = 'none';
            } else {
                showToast('应用失败: ' + (result?result.message:'未知错误'), 'error');
            }
        } catch(e) { showToast('应用失败: '+e, 'error'); }
    },

    async loadCommunityPatches() {
        try {
            const r = await pyApi('scriptsoCommunityPatches');
            if (r && r.success && r.categories) {
                document.getElementById('scriptsoCommunityPanel').style.display = 'block';
                this._renderCommunityPatches(r.categories);
            }
        } catch(e) { showToast('加载社区补丁失败', 'error'); }
    },

    async applyCommunityPatch(patchId) {
        if (!confirm('确定要应用此社区补丁吗？将自动备份 Script.so。')) return;
        try {
            const r = await pyApi('scriptsoApplyCommunityPatch', patchId);
            if (r && r.success) {
                showToast('补丁应用成功!\n' + r.desc + '\n' + (r.backup || ''), 'success');
            } else {
                showToast('应用失败: ' + (r ? r.message : '未知错误'), 'error');
            }
        } catch(e) { showToast('应用失败: ' + e, 'error'); }
    },

    _renderCommunityPatches(categories) {
        const list = document.getElementById('scriptsoCommunityList');
        let html = '';
        categories.forEach(cat => {
            html += `<div style="margin:6px 0;border:1px solid var(--border);border-radius:6px;overflow:hidden;">
                <div style="padding:6px 8px;background:var(--bg-input);font-weight:600;font-size:12px;color:var(--accent);">
                    ${escHtml(cat.category)} <span style="color:var(--text-muted);font-weight:400;">(${cat.count}个补丁)</span>
                </div>
                <div style="padding:4px 8px;font-size:10px;color:var(--text-muted);">${escHtml(cat.description)}</div>`;
            cat.patches.forEach(p => {
                html += `<div style="display:flex;align-items:center;justify-content:space-between;padding:4px 8px;border-top:1px solid var(--border);">
                    <div style="flex:1;min-width:0;">
                        <div style="font-size:11px;font-weight:500;">${escHtml(p.desc)}</div>
                        <div style="font-size:9px;color:var(--text-muted);">${escHtml(p.old)} → ${escHtml(p.new)}</div>
                        <div style="font-size:9px;color:var(--text-muted);">${escHtml(p.note || '')}</div>
                    </div>
                    <button onclick="scriptsoEditor.applyCommunityPatch('${p.id}')" class="btn btn-sm btn-primary" style="flex-shrink:0;margin-left:6px;font-size:10px;padding:2px 8px;">应用</button>
                </div>`;
            });
            html += `</div>`;
        });
        list.innerHTML = html || '<div style="padding:8px;color:var(--text-muted);">暂无社区补丁</div>';
    },

    async loadSections() {
        const res = await pyApi('scriptsoSections');
        if (!res.success) { showToast(res.message, 'error'); return; }
        const list = document.getElementById('scriptsoSections');
        if (!list) return;
        list.innerHTML = `<table style="width:100%;font-size:11px;border-collapse:collapse;">
            <thead><tr style="background:var(--bg-page);">
                <th style="padding:6px;text-align:left;">#</th>
                <th style="padding:6px;text-align:left;">名称</th>
                <th style="padding:6px;text-align:left;">类型</th>
                <th style="padding:6px;text-align:right;">大小</th>
                <th style="padding:6px;text-align:right;">偏移</th>
                <th style="padding:6px;text-align:left;">标志</th>
            </tr></thead>
            <tbody>${res.sections.map(s => `
                <tr style="border-bottom:1px solid var(--border);">
                    <td style="padding:6px;color:var(--text-muted);">${s.index}</td>
                    <td style="padding:6px;font-family:monospace;font-weight:600;">${s.name||'-'}</td>
                    <td style="padding:6px;color:${s.type_name==='PROGBITS'?'var(--accent)':s.type_name==='SYMTAB'?'#ff6644':'var(--text-muted)'};">${s.type_name}</td>
                    <td style="padding:6px;text-align:right;font-family:monospace;">${s.size_kb} KB</td>
                    <td style="padding:6px;text-align:right;font-family:monospace;font-size:10px;">${s.offset_hex}</td>
                    <td style="padding:6px;font-family:monospace;font-size:10px;">${s.flags_str||'-'}</td>
                </tr>`).join('')}</tbody></table>`;
    },

    async loadSymbols() {
        const res = await pyApi('scriptsoSymbols');
        if (!res.success) { showToast(res.message, 'error'); return; }
        const list = document.getElementById('scriptsoSymbols');
        if (!list) return;
        const funcs = res.symbols.filter(s => s.type === 'FUNC');
        const globals = res.symbols.filter(s => s.bind === 'GLOBAL');
        list.innerHTML = `<div style="display:flex;gap:16px;margin-bottom:8px;font-size:12px;color:var(--text-muted);">
            <span>总计: <b>${res.total}</b></span>
            <span>函数: <b>${res.func_count}</b></span>
            <span>全局对象: <b>${res.object_count}</b></span>
            <span>本地: <b>${res.local_count}</b></span>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <div class="panel-card" style="padding:8px;">
                <h4 style="margin:0 0 8px;font-size:13px;">函数列表 (${res.func_count})</h4>
                <div style="max-height:300px;overflow-y:auto;font-size:11px;font-family:monospace;">
                    ${funcs.slice(0,100).map(s => `<div style="padding:2px 0;border-bottom:1px solid var(--border);"><span style="color:var(--accent);">${s.name}</span> <span style="color:var(--text-muted);float:right;">${s.value_hex}</span></div>`).join('')}
                    ${funcs.length > 100 ? `<div style="color:var(--text-muted);padding:4px;">... 还有 ${funcs.length - 100} 个函数</div>` : ''}
                </div>
            </div>
            <div class="panel-card" style="padding:8px;">
                <h4 style="margin:0 0 8px;font-size:13px;">全局符号 (${res.object_count})</h4>
                <div style="max-height:300px;overflow-y:auto;font-size:11px;font-family:monospace;">
                    ${globals.filter(s=>s.type==='OBJECT').slice(0,100).map(s => `<div style="padding:2px 0;border-bottom:1px solid var(--border);"><span style="color:#ff6644;">${s.name}</span> <span style="color:var(--text-muted);float:right;">${s.value_hex}</span></div>`).join('')}
                </div>
            </div>
        </div>`;
    },

    async loadDisasm() {
        const offset = document.getElementById('scriptsoDisasmOffset').value.trim();
        const length = parseInt(document.getElementById('scriptsoDisasmLength').value) || 512;
        const res = await pyApi('scriptsoDisassemble', offset ? parseInt(offset) : null, length);
        if (!res.success) { showToast(res.message, 'error'); return; }
        const container = document.getElementById('scriptsoDisasmContent');
        if (!container) return;
        container.innerHTML = `<div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">
            架构: <b>${res.arch}</b> | 偏移: <b>${res.offset_hex}</b> | 指令数: <b>${res.instruction_count}</b>
            ${res.call_targets.length ? ` | 调用目标: <b>${res.call_targets.length}</b>` : ''}
        </div>
        <table style="width:100%;font-size:12px;font-family:monospace;border-collapse:collapse;">
            <tbody>${res.instructions.map(i => `
                <tr style="border-bottom:1px solid var(--border);${i.mnemonic==='call'?'background:rgba(100,180,255,0.1)':i.mnemonic.startsWith('j')||i.mnemonic==='ret'?'background:rgba(255,200,0,0.05)':''}">
                    <td style="padding:2px 6px;color:var(--accent);white-space:nowrap;">${i.address_hex}</td>
                    <td style="padding:2px 6px;color:var(--text-muted);font-size:10px;white-space:nowrap;">${i.bytes}</td>
                    <td style="padding:2px 6px;color:#ff6644;font-weight:600;">${i.mnemonic}</td>
                    <td style="padding:2px 6px;">${i.op_str}</td>
                </tr>`).join('')}</tbody></table>`;
    },

    async loadFunctions() {
        const res = await pyApi('scriptsoFindFunctions');
        if (!res.success) { showToast(res.message, 'error'); return; }
        const container = document.getElementById('scriptsoDisasmContent');
        if (!container) return;
        container.innerHTML = `<div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">
            段: ${res.section} | 架构: ${res.arch} | 检测到 <b>${res.count}</b> 个函数
        </div>
        <table style="width:100%;font-size:12px;font-family:monospace;border-collapse:collapse;">
            <thead><tr style="background:var(--bg-page);">
                <th style="padding:4px;text-align:left;">#</th>
                <th style="padding:4px;text-align:left;">地址</th>
                <th style="padding:4px;text-align:left;">名称</th>
                <th style="padding:4px;text-align:center;">操作</th>
            </tr></thead>
            <tbody>${res.functions.map((f, i) => `
                <tr style="border-bottom:1px solid var(--border);">
                    <td style="padding:4px;color:var(--text-muted);">${i+1}</td>
                    <td style="padding:4px;color:var(--accent);">${f.address_hex}</td>
                    <td style="padding:4px;${f.name?'color:#ff6644;font-weight:600;':'color:var(--text-muted);'}">${f.name||'(未命名)'}</td>
                    <td style="padding:4px;text-align:center;">
                        <button onclick="scriptsoEditor.disasmFunc(${f.address})" class="btn btn-sm">反汇编</button>
                        <button onclick="scriptsoEditor.xrefsTo(${f.address})" class="btn btn-sm">引用</button>
                    </td>
                </tr>`).join('')}</tbody></table>`;
    },

    async disasmFunc(address) {
        const res = await pyApi('scriptsoDisasmFunc', address);
        if (!res.success) { showToast(res.message, 'error'); return; }
        const container = document.getElementById('scriptsoDisasmContent');
        if (!container) return;
        container.innerHTML = `<div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">
            函数: <b style="color:#ff6644;">${res.function_name||'未命名'}</b> | 地址: <b>${res.function_address_hex}</b> | 指令: <b>${res.instruction_count}</b>
            ${res.branch_targets.length ? ` | 分支目标: <b>${res.branch_targets.length}</b>` : ''}
        </div>
        <table style="width:100%;font-size:12px;font-family:monospace;border-collapse:collapse;">
            <tbody>${res.instructions.map(i => `
                <tr style="border-bottom:1px solid var(--border);${i.mnemonic==='call'?'background:rgba(100,180,255,0.1)':i.mnemonic.startsWith('j')||i.mnemonic==='ret'?'background:rgba(255,200,0,0.05)':''}">
                    <td style="padding:2px 6px;color:var(--accent);white-space:nowrap;">${i.address_hex}</td>
                    <td style="padding:2px 6px;color:var(--text-muted);font-size:10px;white-space:nowrap;">${i.bytes}</td>
                    <td style="padding:2px 6px;color:#ff6644;font-weight:600;">${i.mnemonic}</td>
                    <td style="padding:2px 6px;">${i.op_str}</td>
                </tr>`).join('')}</tbody></table>`;
    },

    async xrefsTo(address) {
        const res = await pyApi('scriptsoFindXrefs', address);
        if (!res.success) { showToast(res.message, 'error'); return; }
        const container = document.getElementById('scriptsoDisasmContent');
        if (!container) return;
        container.innerHTML = `<div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">
            交叉引用到 <b style="color:var(--accent);">${res.target_hex}</b>: 共 <b>${res.count}</b> 处
        </div>
        ${res.count === 0 ? '<p style="color:var(--text-muted);">未找到引用</p>' : 
        `<table style="width:100%;font-size:12px;font-family:monospace;border-collapse:collapse;">
            <thead><tr style="background:var(--bg-page);">
                <th style="padding:4px;text-align:left;">来源地址</th>
                <th style="padding:4px;text-align:left;">类型</th>
                <th style="padding:4px;text-align:left;">段</th>
                <th style="padding:4px;text-align:left;">指令</th>
            </tr></thead>
            <tbody>${res.refs.map(r => `
                <tr style="border-bottom:1px solid var(--border);">
                    <td style="padding:4px;color:var(--accent);">${r.from_hex}</td>
                    <td style="padding:4px;color:${r.type==='call'?'#ff6644':'var(--accent)'};">${r.type}</td>
                    <td style="padding:4px;color:var(--text-muted);">${r.section}</td>
                    <td style="padding:4px;">${r.instruction}</td>
                </tr>`).join('')}</tbody></table>`}`;
    },

    async instructionPatch() {
        const addr = parseInt(document.getElementById('scriptsoPatchAddr').value.trim());
        const mnemonic = document.getElementById('scriptsoPatchMnemonic').value.trim().toLowerCase();
        const operands = document.getElementById('scriptsoPatchOperands').value.trim();
        if (isNaN(addr)) { showToast('请输入有效地址', 'warning'); return; }
        if (!mnemonic) { showToast('请输入指令', 'warning'); return; }
        if (!confirm(`确定在 ${'0x'+addr.toString(16).toUpperCase()} 处写入 "${mnemonic} ${operands}"？\n此操作会自动备份原文件。`)) return;
        const res = await pyApi('scriptsoInstructionPatch', addr, mnemonic, operands);
        if (res.success) {
            document.getElementById('scriptsoPatchResult').innerHTML = 
                `<div style="padding:8px;background:rgba(0,200,0,0.1);border-radius:4px;color:green;font-family:monospace;">
                ${res.message || res.instruction || '补丁已应用'}</div>`;
        } else {
            document.getElementById('scriptsoPatchResult').innerHTML = 
                `<div style="padding:8px;background:rgba(255,0,0,0.1);border-radius:4px;color:red;">${res.message}</div>`;
        }
    }
};

// ============================================================
// MOD管理
// ============================================================

const mods = {
    activeMod: null,
    conflictData: null,

    async refreshList() {
        const res = await pyApi('getModList');
        const container = document.getElementById('modList');
        if (!container) return;
        container.innerHTML = '';

        // 获取当前活跃MOD
        const activeRes = await pyApi('getActiveMod');
        this.activeMod = activeRes.active || null;
        this._updateActiveBar();

        const modList = res.mods || [];
        if (modList.length === 0) {
            container.innerHTML = '<div style="padding:20px;text-align:center;color:#999;">暂无MOD工程，请创建新工程</div>';
            return;
        }
        modList.forEach(m => {
            const isActive = this.activeMod === m.name;
            const card = document.createElement('div');
            card.className = 'mod-card' + (isActive ? ' active' : '');
            const info = m.info || {};
            const fileCount = m.files || 0;
            card.innerHTML = `
                <div class="mod-card-info">
                    <div class="mod-card-name">
                        ${m.name}
                        ${isActive ? '<span class="active-tag">当前</span>' : ''}
                    </div>
                    <div class="mod-card-meta">
                        <span>v${info.version || '1.0'}</span>
                        <span>${info.created || ''}</span>
                        <span>${fileCount} 个文件</span>
                        ${info.description ? `<span>${info.description}</span>` : ''}
                    </div>
                </div>
                <div class="mod-card-actions">
                    ${isActive
                        ? ''
                        : `<button onclick="mods.activate('${m.name}')" class="btn btn-primary">切换到此工程</button>`
                    }
                    <button onclick="mods.pack('${m.name}')" class="btn btn-success">打包</button>
                    <button onclick="mods.snapshot('${m.name}')" class="btn">快照</button>
                    <button onclick="mods.confirmDelete('${m.name}')" class="btn btn-danger">删除</button>
                </div>
            `;
            container.appendChild(card);
        });
    },

    _updateActiveBar() {
        document.getElementById('activeModName').textContent = this.activeMod || '未选择';
        if (this.activeMod) {
            document.getElementById('activeModDetail').textContent = '当前所有修改将记录到此工程';
        } else {
            document.getElementById('activeModDetail').textContent = '';
        }
    },

    async create() {
        const nameEl = document.getElementById('newModName');
        const descEl = document.getElementById('newModDesc');
        const name = nameEl.value.trim();
        if (!name) { showToast('请输入MOD名称', 'warning'); return; }
        const desc = descEl ? descEl.value.trim() : '';
        const res = await pyApi('createMod', name, desc);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) {
            nameEl.value = '';
            if (descEl) descEl.value = '';
            this.activate(name);
        }
        this.refreshList();
    },

    async activate(name) {
        const res = await pyApi('setActiveMod', name);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.refreshList();
    },

    async confirmDelete(name) {
        if (!confirm(`确认删除MOD工程 "${name}"？\n此操作不可撤销，但不会影响游戏数据文件。`)) return;
        const res = await pyApi('deleteMod', name);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.refreshList();
    },

    async pack(name) {
        if (!confirm(`确认打包MOD "${name}" 吗？\n系统将对比当前数据与快照，只打包变更文件。`)) return;
        const res = await pyApi('packModIncremental', name);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success && res.files) {
            this._showPackSummary(res);
        }
    },

    async oneClickPack() {
        if (!this.activeMod) { showToast('请先创建或选择一个MOD工程', 'success'); return; }
        if (!confirm(`一键打包 "${this.activeMod}"？\n会自动创建快照、对比变更、生成ZIP分发包。`)) return;
        const res = await pyApi('packModOneClick', this.activeMod);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success && res.files) {
            this._showPackSummary(res);
        }
    },

    _showPackSummary(res) {
        // 在MOD列表下方显示打包摘要
        let existing = document.getElementById('packSummary');
        if (existing) existing.remove();

        const summary = document.createElement('div');
        summary.id = 'packSummary';
        summary.className = 'pack-summary';
        let html = `<h4>打包完成 - ${res.exportPath || ''}</h4>`;
        html += `<p style="font-size:12px;color:var(--text-secondary);margin-bottom:8px;">共 ${res.fileCount || 0} 个文件，${res.changedCount || 0} 个变更</p>`;
        html += '<div class="pack-file-list">';
        (res.files || []).forEach(f => {
            html += `<span class="pack-file-tag ${res.changedFiles && res.changedFiles.includes(f.name) ? 'changed' : ''}">${f.name || f}</span>`;
        });
        html += '</div>';
        summary.innerHTML = html;
        const listEl = document.getElementById('modList');
        if (listEl) listEl.after(summary);
    },

    async snapshot(name) {
        if (!confirm(`为MOD "${name}" 创建状态快照？\n快照用于后续增量打包时对比变更。`)) return;
        const res = await pyApi('modSnapshot', name);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
    },

    // 导入MOD
    showImport() {
        document.getElementById('importModal').style.display = 'flex';
    },

    hideImport() {
        document.getElementById('importModal').style.display = 'none';
    },

    async doImport() {
        const autoRemap = document.getElementById('importAutoRemap').checked;
        const backupFirst = document.getElementById('importBackupFirst').checked;
        const importName = document.getElementById('importModName').value.trim();
        const res = await pyApi('importMod', importName || null, autoRemap, backupFirst);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.hideImport();
        if (res.success && res.conflicts && res.conflicts.length > 0) {
            this.conflictData = res;
            this._showConflicts(res);
        } else {
            this.refreshList();
        }
    },

    _showConflicts(res) {
        const panel = document.getElementById('conflictPanel');
        panel.style.display = 'block';
        document.getElementById('conflictSummary').textContent =
            `检测到 ${res.conflicts.length} 个ID冲突，建议重映射以避免覆盖现有数据`;

        const list = document.getElementById('conflictList');
        list.innerHTML = '';
        res.conflicts.forEach(c => {
            const entry = document.createElement('div');
            entry.className = 'conflict-entry';
            entry.innerHTML = `
                <span class="conflict-file">${c.file}</span>
                <span class="conflict-ids">
                    <span class="arrow">#${c.existingId}</span> ← 冲突 →
                    <span class="arrow">#${c.importId}</span>
                </span>
                <span class="conflict-suggestion">建议重映射到: #${c.suggestedId}</span>
            `;
            list.appendChild(entry);
        });
    },

    async remapAll() {
        if (!this.conflictData) return;
        const res = await pyApi('remapConflicts', this.conflictData);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.dismissConflicts();
        this.refreshList();
    },

    dismissConflicts() {
        document.getElementById('conflictPanel').style.display = 'none';
        this.conflictData = null;
    },

    async installMod() {
        if (!(await validateBeforeSave())) return;
        const name = prompt('输入要安装的MOD名称:');
        if (!name) return;
        try {
            const res = await pyApi('installMod', name);
            if (res && res.message) showToast(res.message, res && res.success ? 'success' : 'error');
            if (res && res.success) showToast('MOD安装成功! 请重启游戏生效。', 'success');
        } catch(e) { showToast('安装失败: '+e, 'error'); }
    },

    async listInstalled() {
        try {
            const res = await pyApi('listInstalledMods');
            if (res && res.success) {
                const mods = res.mods || [];
                if (mods.length === 0) {
                    showToast('当前没有已安装的MOD', 'warning');
                } else {
                    let msg = `已安装 ${mods.length} 个MOD:\n\n`;
                    mods.forEach(m => {
                        msg += `  ${m.name} (v${m.version || '1.0'})\n`;
                        if (m.path) msg += `    路径: ${m.path}\n`;
                    });
                    msg += '\n提示: 卸载MOD请使用 "卸载MOD" 功能';
                    showToast(msg, 'info');
                }
            } else {
                showToast('获取失败: ' + (res ? res.message : ''), 'error');
            }
        } catch(e) { showToast('获取失败: '+e, 'error'); }
    },

    async uninstallMod() {
        if (!confirm('确定要卸载当前MOD吗？\n\n此操作将：\n1. 恢复所有备份的原始文件\n2. 删除MOD修改的文件\n\n此操作不可撤销！')) return;
        const name = this.activeMod;
        if (!name) { showToast('请先选择一个MOD工程', 'warning'); return; }
        const el = document.getElementById('modUninstallResult');
        if (!el) return;
        el.textContent = '卸载中...';
        el.style.color = 'var(--text-muted)';
        try {
            const r = await pyApi('uninstallMod', name);
            if (r.success) {
                el.textContent = r.message;
                el.style.color = 'var(--success)';
                this.refreshList();
            } else {
                el.textContent = r.message;
                el.style.color = 'var(--danger)';
            }
        } catch(e) {
            el.textContent = '' + e;
            el.style.color = 'var(--danger)';
        }
    },

    async launchGame() {
        // 尝试获取已安装的MOD名称
        let modName = null;
        try {
            const r = await pyApi('listInstalledMods');
            if (r.success && r.mods) {
                const names = Object.keys(r.mods);
                if (names.length > 0) modName = names[0];
            }
        } catch(e) { /* 忽略 */ }
        if (!confirm(modName ?
            `启动游戏 (MOD: ${modName})?` :
            '启动游戏? (当前未安装MOD，将使用原始游戏数据)' )) return;
        try {
            const r = await pyApi('launchGame', modName);
            if (r.success) {
                showToast(r.message, 'success');
            } else {
                showToast(r.message, 'error');
            }
        } catch(e) {
            showToast('启动失败: ' + e, 'error');
        }
    },

    showMerge() {
        const modal = document.getElementById('mergeModal');
        modal.style.display = 'flex';
        this._populateMergeSelects();
    },

    hideMerge() {
        document.getElementById('mergeModal').style.display = 'none';
    },

    async _populateMergeSelects() {
        const res = await pyApi('listMods');
        const mods = res && res.mods ? res.mods : [];
        const selA = document.getElementById('mergeModA');
        const selB = document.getElementById('mergeModB');
        selA.innerHTML = selB.innerHTML = mods.map(m => `<option value="${m.name}">${m.name} (v${m.version || '1.0'})</option>`).join('');
    },

    async doMerge() {
        const modA = document.getElementById('mergeModA').value;
        const modB = document.getElementById('mergeModB').value;
        const output = document.getElementById('mergeOutputName').value.trim() || null;
        if (!modA || !modB) { showToast('请选择两个MOD', 'warning'); return; }
        if (modA === modB) { showToast('不能合并同一个MOD', 'warning'); return; }
        const res = await pyApi('modMerge', modA, modB, output);
        if (res.success) {
            let msg = res.message;
            if (res.conflicts && res.conflicts.length > 0) {
                msg += `\n冲突文件: ${res.conflicts.join(', ')}`;
                msg += '\n冲突文件已按来源重命名保留';
            }
            showToast(msg, 'success');
            this.hideMerge();
            this.refreshList();
        } else {
            showToast(res.message || '合并失败', 'error');
        }
    },
};

// ============================================================
// 武将技/军师技编辑器
// ============================================================

const skillEditor = {
    data: [],
    currentIndex: -1,
    current: null,
    changed: false,

    async load() {
        const res = await pyApi('loadSkills');
        if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
        this.data = res.data || [];
        this.currentIndex = -1; this.current = null;
        this.renderList();
        document.getElementById('skillCount').textContent = this.data.length;
        setupTooltips('bfmagic', 'sk_');
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this.data));
    },

    restoreSnapshot(data) {
        this.data = data;
        this.currentIndex = -1;
        this.current = null;
        this.renderList();
        this.changed = false;
    },

    pushUndo() {
        UndoManager.pushState('skills', this.snapshot());
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        if (this.current && this.changed) this.saveCurrent();
        const res = await pyApi('saveSkills', this.data);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) this.changed = false;
    },

    renderList() {
        const container = document.getElementById('skillList');
        if (!container) return;
        container.innerHTML = '';
        const filter = document.getElementById('skillTypeFilter')?.value || 'all';
        this.data.forEach((s, idx) => {
            const type = s.SkillType || s.Type || 'magic';
            if (filter !== 'all' && type !== filter) return;
            const typeLabel = type === 'magic' ? '武将技' : '军师技';
            const card = document.createElement('div');
            card.className = 'item-card' + (idx === this.currentIndex ? ' selected' : '');
            card.innerHTML = `
                <div class="item-card-header">
                    <span class="item-name">${escHtml(s.Name || '无名')}</span>
                    <span class="item-no">#${escHtml(String(s.No || ''))}</span>
                </div>
                <div class="item-desc">${escHtml(typeLabel)} | MP:${escHtml(String(s.MP||'-'))} ATK:${escHtml(String(s.ATK||'-'))}</div>
            `;
            card.onclick = () => this.select(idx);
            container.appendChild(card);
        });
    },

    select(idx) {
        if (idx < 0 || idx >= this.data.length) return;
        if (this.current && this.changed) this.saveCurrent();
        this.currentIndex = idx;
        this.current = this.data[idx];
        this.renderDetail();
        this.renderList();
        this.changed = false;
    },

    renderDetail() {
        const emptyEl = document.getElementById('emptySkillDetail');
        const detailEl = document.getElementById('skillDetailContent');
        if (!this.current) {
            if (emptyEl) emptyEl.style.display = 'flex';
            if (detailEl) detailEl.style.display = 'none';
            return;
        }
        if (emptyEl) emptyEl.style.display = 'none';
        if (detailEl) detailEl.style.display = 'block';
        const fields = ['No','Name','SkillType','MP','ATK','Level','Range','Target','Damage','Effect','Element','IsUsed','Desc','Ball','DamageType','Atk'];
        fields.forEach(k => {
            const el = document.getElementById('sk_' + k);
            if (el) {
                if (el.tagName === 'SELECT') el.value = String(this.current[k] || '');
                else el.value = this.current[k] || '';
            }
        });
        this._updateSkillPreview();
    },

    currentChanged() { this.changed = true; this._updateSkillPreview(); },

    saveCurrent() {
        if (!this.current) return;
        const fields = ['No','Name','SkillType','MP','ATK','Level','Range','Target','Damage','Effect','Element','IsUsed','Desc','Ball','DamageType','Atk'];
        fields.forEach(k => {
            const el = document.getElementById('sk_' + k);
            if (el) this.current[k] = el.value;
        });
    },

    async addNew() {
        this.pushUndo();
        const res = await pyApi('newSkill');
        if (res.success) {
            this.data.push(res.data);
            this.changed = true;
            this.renderList();
            this.select(this.data.length - 1);
            document.getElementById('skillCount').textContent = this.data.length;
        } else { showToast(res.message, res && res.success ? 'success' : 'error'); }
    },

    async cloneCurrent() {
        this.pushUndo();
        if (!this.current) { showToast('请先选择一个技能', 'warning'); return; }
        const clone = Object.assign({}, this.current);
        const usedIds = new Set(this.data.map(s => parseInt(s.No)));
        let newId = 0;
        for (let i = 1; i < 10000; i++) { if (!usedIds.has(i)) { newId = i; break; } }
        clone.No = newId;
        clone.Name = (clone.Name || '克隆技能') + '_副本';
        this.data.push(clone);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        document.getElementById('skillCount').textContent = this.data.length;
    },

    deleteCurrent() {
        this.pushUndo();
        if (!this.current) return;
        if (!confirm(`确认删除技能 "${this.current.Name}" #${this.current.No}?`)) return;
        const no = parseInt(this.current.No);
        const src = this.current._source || 'BFMagic.ini';
        pyApi('deleteIniItem', 'Setting/' + src, src.replace('.ini', '').toUpperCase(), 'No', String(no));
        this.data = this.data.filter(s => parseInt(s.No) !== no);
        this.current = null; this.currentIndex = -1; this.changed = true;
        this.renderList();
        document.getElementById('skillCount').textContent = this.data.length;
        document.getElementById('emptySkillDetail').style.display = 'flex';
        document.getElementById('skillDetailContent').style.display = 'none';
    },

    search(keyword) {
        const container = document.getElementById('skillList');
        if (!container) return;
        container.innerHTML = '';
        const kw = keyword.toLowerCase();
        const filter = document.getElementById('skillTypeFilter')?.value || 'all';
        this.data.forEach((s, idx) => {
            const name = (s.Name || '').toLowerCase();
            const no = String(s.No || '');
            const type = s.SkillType || s.Type || 'magic';
            if (filter !== 'all' && type !== filter) return;
            if (!kw || name.includes(kw) || no.includes(kw)) {
                const card = document.createElement('div');
                card.className = 'item-card';
                const typeLabel = type === 'magic' ? '武将技' : '军师技';
                card.innerHTML = `
                    <div class="item-card-header"><span class="item-name">${s.Name||'无名'}</span><span class="item-no">#${s.No||''}</span></div>
                    <div class="item-desc">${typeLabel} | MP:${s.MP||'-'} ATK:${s.ATK||'-'}</div>
                `;
                card.onclick = () => this.select(idx);
                container.appendChild(card);
            }
        });
    },

    // ============================================================
    // 特效模板应用 — 从特效模板一键创建技能
    // ============================================================
    applyTemplate(tpl) {
        this.pushUndo();
        // 找到未使用的编号
        const usedIds = new Set(this.data.map(s => parseInt(s.No)));
        let newId = 0;
        for (let i = 1; i < 10000; i++) { if (!usedIds.has(i)) { newId = i; break; } }
        // 基于模板参数创建新技能
        const p = tpl.params || {};
        const newSkill = {
            No: newId,
            Name: tpl.example || '新技能',
            SkillType: 'magic',
            MP: p.MP || 0,
            ATK: p.ATK || 0,
            Level: p.Level || 1,
            Range: p.Range || 1,
            Target: p.Target || 0,
            Damage: p.Damage || 1.0,
            Effect: p.Effect || 0,
            Element: p.Element || 0,
            IsUsed: 1,
            Desc: tpl.desc || '',
            Ball: p.Ball || 0,
            DamageType: p.DamageType || 0,
            Atk: p.Atk || 0,
        };
        this.data.push(newSkill);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        document.getElementById('skillCount').textContent = this.data.length;
        // 滚动到详情面板
        setTimeout(() => {
            const detail = document.getElementById('skillDetail');
            if (detail) detail.scrollIntoView({behavior:'smooth',block:'nearest'});
        }, 200);
    },

    // ============================================================
    // 特效预览 — 详情面板中实时显示参数可视化
    // ============================================================
    _updateSkillPreview() {
        const panel = document.getElementById('skEffectPreview');
        const content = document.getElementById('skEffectPreviewContent');
        const scoreEl = document.getElementById('skEffectScore');
        const warnEl = document.getElementById('skEffectWarning');
        if (!panel || !content) return;
        if (!this.current) { panel.style.display = 'none'; return; }
        panel.style.display = 'block';

        const getVal = (id, def) => { const el = document.getElementById('sk_' + id); return el ? (parseInt(el.value) || def) : def; };
        const ball = getVal('Ball', 0);
        const dmg = getVal('DamageType', 0);
        const elem = getVal('Element', 0);
        const atk = getVal('Atk', 0);
        const range = getVal('Range', 1);
        const target = getVal('Target', 0);
        const damage = parseFloat(document.getElementById('sk_Damage')?.value) || 1.0;
        const mp = getVal('MP', 0);
        const atkVal = getVal('ATK', 0);

        // 弹道可视化
        const ballVisuals = {
            0:{icon:'●',label:'默认',color:'#888'},1:{icon:'→',label:'直射',color:'#ff4444'},2:{icon:'⌒',label:'弧形',color:'#ff8800'},
            3:{icon:'⋘',label:'散射',color:'#44aaff'},4:{icon:'↷',label:'追踪',color:'#ff44ff'},5:{icon:'⚡',label:'落雷',color:'#ffff00'},
            6:{icon:'≈',label:'冲击',color:'#aa8844'},7:{icon:'◎',label:'旋转',color:'#ff6644'},8:{icon:'◆',label:'召唤',color:'#8844ff'},
            9:{icon:'━',label:'光束',color:'#44ffff'},10:{icon:'✱',label:'爆炸',color:'#ff0000'},11:{icon:'⇨',label:'穿透',color:'#ffaa00'},
            12:{icon:'❄',label:'冰锥',color:'#88ccff'},13:{icon:'🌀',label:'旋风',color:'#aaffaa'},14:{icon:'☠',label:'毒雾',color:'#88ff44'},
            15:{icon:'✚',label:'治疗',color:'#44ff44'},
        };
        const bv = ballVisuals[ball] || ballVisuals[0];
        const dmgColors = ['#ccc','#ff4444','#4488ff','#44ff44','#ffdd00','#aa44ff','#ff0000','#ff8800','#44ff88'];
        const dmgColor = dmgColors[dmg] || '#ccc';
        const dmgLabels = ['物理','火','水','风','雷','毒','真实','百分比','治疗'];
        const elemColors = ['#888','#ff4444','#4488ff','#44ff44','#ffdd00','#aa44ff'];
        const elemColor = elemColors[elem] || '#888';
        const elemLabels = ['无','火','水/冰','风','雷','毒'];
        const targetLabels = ['敌方单体','敌方全体','我方单体','我方全体'];
        const atkLabels = ['单体','群体','全军','持续','治疗','增益','减益','召唤','控制'];

        // 范围同心圆
        const rangeCircles = [];
        const maxRange = Math.min(range, 5);
        for (let i = 1; i <= maxRange; i++) {
            const size = 16 + i * 10;
            const opacity = 1 - (i - 1) * 0.15;
            rangeCircles.push(`<div style="position:absolute;width:${size}px;height:${size}px;border-radius:50%;border:1px solid var(--primary);opacity:${opacity};top:50%;left:50%;transform:translate(-50%,-50%);"></div>`);
        }

        content.innerHTML = `
            <div style="text-align:center;min-width:70px;">
                <div style="font-size:32px;color:${bv.color};line-height:1;">${bv.icon}</div>
                <div style="font-size:10px;color:var(--text-muted);margin-top:2px;">${bv.label}</div>
            </div>
            <div style="display:flex;flex-direction:column;gap:5px;font-size:11px;">
                <div style="display:flex;align-items:center;gap:5px;"><span style="width:8px;height:8px;border-radius:2px;background:${dmgColor};display:inline-block;"></span><span style="color:var(--text-muted);">伤害:</span><span style="font-weight:600;">${dmgLabels[dmg]||'?'}</span></div>
                <div style="display:flex;align-items:center;gap:5px;"><span style="width:8px;height:8px;border-radius:2px;background:${elemColor};display:inline-block;"></span><span style="color:var(--text-muted);">属性:</span><span style="font-weight:600;">${elemLabels[elem]||'?'}</span></div>
                <div style="display:flex;align-items:center;gap:5px;"><span style="color:var(--text-muted);">攻击:</span><span style="font-weight:600;">${atkLabels[atk]||'?'}</span></div>
                <div style="display:flex;align-items:center;gap:5px;"><span style="color:var(--text-muted);">目标:</span><span style="font-weight:600;">${targetLabels[target]||'?'}</span></div>
            </div>
            <div style="position:relative;width:70px;height:70px;min-width:70px;">
                <div style="position:absolute;width:8px;height:8px;border-radius:50%;background:var(--primary);top:50%;left:50%;transform:translate(-50%,-50%);z-index:2;"></div>
                ${rangeCircles.join('')}
            </div>
            <div style="font-size:11px;text-align:center;">
                <div style="color:var(--text-muted);">范围</div><div style="font-weight:600;font-size:15px;color:var(--primary);">${range}</div>
            </div>
            <div style="display:flex;flex-direction:column;gap:3px;font-size:11px;">
                <div><span style="color:var(--text-muted);">MP:</span><span style="font-weight:600;">${mp}</span></div>
                <div><span style="color:var(--text-muted);">ATK:</span><span style="font-weight:600;">${atkVal}</span></div>
                <div><span style="color:var(--text-muted);">倍率:</span><span style="font-weight:600;color:var(--warning);">x${damage}</span></div>
            </div>
        `;

        // 技能强度评分
        const score = this._calcSkillScore({ball, dmg, elem, atk, range, target, damage, mp, atkVal});
        let scoreColor = score >= 70 ? 'var(--success)' : score >= 40 ? 'var(--warning)' : 'var(--text-muted)';
        let scoreLabel = score >= 70 ? '高级' : score >= 40 ? '中级' : '入门';
        scoreEl.innerHTML = `强度: <span style="font-weight:600;color:${scoreColor};">${score}分</span> (${scoreLabel})`;

        // 参数校验警告
        const warnings = this._validateEffectParams({ball, dmg, elem, atk});
        if (warnings.length > 0) {
            warnEl.style.display = 'block';
            warnEl.innerHTML = `⚠️ ${warnings.join(' | ')}`;
            warnEl.style.color = 'var(--warning)';
        } else {
            warnEl.style.display = 'none';
        }
    },

    // ============================================================
    // 技能强度评分
    // ============================================================
    _calcSkillScore(p) {
        let score = 0;
        // 弹道加分
        const ballScore = {0:0,1:5,2:5,3:10,4:15,5:15,6:10,7:5,8:5,9:20,10:20,11:10,12:10,13:10,14:5,15:0};
        score += ballScore[p.ball] || 0;
        // 伤害类型
        const dmgScore = {0:0,1:10,2:8,3:8,4:12,5:6,6:15,7:15,8:0};
        score += dmgScore[p.dmg] || 0;
        // 攻击类型
        const atkScore = {0:0,1:10,2:20,3:8,4:0,5:0,6:0,7:5,8:8};
        score += atkScore[p.atk] || 0;
        // 范围
        score += Math.min(p.range, 10) * 2;
        // 伤害倍率
        score += Math.min(p.damage * 10, 30);
        // 消耗比
        if (p.atkVal > 0 && p.mp > 0) {
            const ratio = p.atkVal / p.mp;
            if (ratio > 3) score += 15;
            else if (ratio > 2) score += 10;
            else if (ratio > 1) score += 5;
        }
        return Math.min(Math.round(score), 100);
    },

    // ============================================================
    // 特效参数校验
    // ============================================================
    _validateEffectParams(p) {
        const warnings = [];
        // 弹道与伤害类型兼容性
        if (p.ball === 15 && p.dmg !== 8) warnings.push('治疗弹道建议搭配治疗伤害类型');
        if (p.ball === 14 && p.dmg !== 5) warnings.push('毒雾弹道建议搭配毒属性伤害');
        if (p.ball === 12 && p.dmg !== 2) warnings.push('冰锥弹道建议搭配水属性伤害');
        if (p.ball === 10 && p.dmg !== 1) warnings.push('爆炸弹道建议搭配火属性伤害');
        if (p.ball === 5 && p.dmg !== 4) warnings.push('落雷弹道建议搭配雷属性伤害');
        // 伤害类型与属性一致性
        if (p.dmg === 1 && p.elem !== 1) warnings.push('火属性伤害建议搭配火属性');
        if (p.dmg === 2 && p.elem !== 2) warnings.push('水属性伤害建议搭配水属性');
        if (p.dmg === 3 && p.elem !== 3) warnings.push('风属性伤害建议搭配风属性');
        if (p.dmg === 4 && p.elem !== 4) warnings.push('雷属性伤害建议搭配雷属性');
        if (p.dmg === 5 && p.elem !== 5) warnings.push('毒属性伤害建议搭配毒属性');
        // 攻击类型与目标一致性
        if (p.atk === 4 && p.target !== 3 && p.target !== 2) warnings.push('治疗攻击建议搭配我方目标');
        if (p.atk === 5 && p.target !== 3 && p.target !== 2) warnings.push('增益效果建议搭配我方目标');
        if (p.atk === 6 && p.target !== 1 && p.target !== 0) warnings.push('减益效果建议搭配敌方目标');
        // 弹道与攻击类型一致性
        if (p.ball === 8 && p.atk !== 7) warnings.push('召唤弹道建议搭配召唤攻击类型');
        if (p.ball === 5 && p.atk !== 2 && p.atk !== 1) warnings.push('落雷弹道建议搭配全军/群体攻击');
        // 范围合理性
        if (p.target === 0 && p.range > 3) warnings.push('敌方单体目标建议范围≤3');
        if (p.target === 1 && p.range < 2) warnings.push('敌方全体目标建议范围≥2');
        return warnings;
    },

    // ============================================================
    // 技能描述自动生成
    // ============================================================
    _generateDesc() {
        if (!this.current) return;
        const getVal = (id, def) => { const el = document.getElementById('sk_' + id); return el ? (parseInt(el.value) || def) : def; };
        const ball = getVal('Ball', 0);
        const dmg = getVal('DamageType', 0);
        const elem = getVal('Element', 0);
        const atk = getVal('Atk', 0);
        const range = getVal('Range', 1);
        const target = getVal('Target', 0);
        const damage = parseFloat(document.getElementById('sk_Damage')?.value) || 1.0;
        const level = getVal('Level', 1);

        const ballLabels = ['默认','直射','弧形','散射','追踪','落雷','冲击','旋转','召唤','光束','爆炸','穿透','冰锥','旋风','毒雾','治疗'];
        const dmgLabels = ['物理','火','水','风','雷','毒','真实','百分比','治疗'];
        const elemLabels = ['无','火','水/冰','风','雷','毒'];
        const atkLabels = ['单体','群体','全军','持续','治疗','增益','减益','召唤','控制'];
        const targetLabels = ['敌方单体','敌方全体','我方单体','我方全体'];

        let desc = '';
        const ballName = ballLabels[ball] || '默认';
        const dmgName = dmgLabels[dmg] || '物理';
        const elemName = elemLabels[elem] || '无';
        const atkName = atkLabels[atk] || '单体';
        const targetName = targetLabels[target] || '敌方';

        // 治疗类
        if (atk === 4 || dmg === 8 || ball === 15) {
            desc = `恢复${targetName === '我方全体' ? '全军' : targetName}生命值`;
            if (damage > 0) desc += `，恢复量倍率${damage}倍`;
            if (level > 1) desc += `。Lv${level}可学`;
        }
        // 辅助类
        else if (atk === 5 || atk === 6) {
            const action = atk === 5 ? '提升' : '降低';
            const scope = targetName === '敌方全体' ? '敌军全体' : targetName;
            desc = `${action}${scope}属性`;
            if (elem > 0) desc += `，附带${elemName}效果`;
            if (level > 1) desc += `。Lv${level}可学`;
        }
        // 召唤类
        else if (ball === 8 || atk === 7) {
            desc = `召唤士兵协助战斗`;
            if (level > 1) desc += `。Lv${level}可学`;
        }
        // 攻击类
        else {
            const rangeDesc = range >= 4 ? '大范围' : range >= 2 ? '中范围' : '近距';
            desc = `对${targetName}造成${rangeDesc}${dmgName}${atkName}${ballName}攻击`;
            if (damage >= 2.0) desc += '，伤害极高';
            else if (damage >= 1.5) desc += '，伤害较高';
            else if (damage >= 1.0) desc += '，伤害适中';
            else desc += '，轻度伤害';
            if (elem > 0 && dmgName !== elemName) desc += `，附带${elemName}属性`;
            if (level > 1) desc += `。Lv${level}可学`;
        }

        document.getElementById('sk_Desc').value = desc;
        this.current.Desc = desc;
        this.changed = true;
        this._showToast('技能描述已自动生成');
    },

    _showToast(msg) {
        let toast = document.getElementById('skToast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'skToast';
            toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--bg-card);color:#fff;padding:8px 20px;border-radius:6px;border:1px solid var(--border);font-size:13px;z-index:10000;pointer-events:none;transition:opacity 0.3s;';
            document.body.appendChild(toast);
        }
        toast.textContent = msg;
        toast.style.opacity = '1';
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => { toast.style.opacity = '0'; }, 2000);
    },
};

// ============================================================
// 阵型编辑器
// ============================================================

const formationEditor = {
    data: [],
    currentIndex: -1,
    current: null,
    changed: false,

    async load() {
        const res = await pyApi('loadFormations');
        if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
        this.data = res.data || [];
        this.currentIndex = -1; this.current = null;
        this.renderList();
        document.getElementById('formationCount').textContent = this.data.length;
        this.renderCounterTable();
        setupTooltips('formation', 'f_');
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this.data));
    },

    restoreSnapshot(data) {
        this.data = data;
        this.currentIndex = -1;
        this.current = null;
        this.renderList();
        this.changed = false;
    },

    pushUndo() {
        UndoManager.pushState('formation', this.snapshot());
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        if (this.current && this.changed) this.saveCurrent();
        const res = await pyApi('saveFormations', this.data);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) this.changed = false;
    },

    renderList() {
        const container = document.getElementById('formationList');
        if (!container) return;
        container.innerHTML = '';
        this.data.forEach((f, idx) => {
            const card = document.createElement('div');
            card.className = 'item-card' + (idx === this.currentIndex ? ' selected' : '');
            card.innerHTML = `
                <div class="item-card-header">
                    <span class="item-name">${f.Name || '无名'}</span>
                    <span class="item-no">#${f.No || ''}</span>
                </div>
                <div class="item-desc">ATK+${f.ATK||0}% DEF+${f.DEF||0}% SPD+${f.Speed||0}%</div>
            `;
            card.onclick = () => this.select(idx);
            container.appendChild(card);
        });
    },

    select(idx) {
        if (idx < 0 || idx >= this.data.length) return;
        if (this.current && this.changed) this.saveCurrent();
        this.currentIndex = idx;
        this.current = this.data[idx];
        this.renderDetail();
        this.renderList();
        this.changed = false;
    },

    renderDetail() {
        const emptyEl = document.getElementById('emptyFormationDetail');
        const detailEl = document.getElementById('formationDetailContent');
        if (!this.current) {
            if (emptyEl) emptyEl.style.display = 'flex';
            if (detailEl) detailEl.style.display = 'none';
            return;
        }
        if (emptyEl) emptyEl.style.display = 'none';
        if (detailEl) detailEl.style.display = 'block';
        const fields = ['No','Name','ATK','DEF','Speed','Counter1','Counter2','WeakTo','Desc'];
        fields.forEach(k => {
            const el = document.getElementById('f_' + k);
            if (el) el.value = this.current[k] || '';
        });
        // 提示克制目标名称
        ['Counter1','Counter2','WeakTo'].forEach(k => {
            const hint = document.getElementById('f_' + k + 'Hint');
            if (hint) {
                const targetId = parseInt(this.current[k]) || 0;
                const target = targetId ? this.data.find(f => parseInt(f.No) === targetId) : null;
                hint.textContent = target ? `→ ${target.Name}` : '';
            }
        });
    },

    currentChanged() { this.changed = true; },

    saveCurrent() {
        if (!this.current) return;
        ['No','Name','ATK','DEF','Speed','Counter1','Counter2','WeakTo','Desc'].forEach(k => {
            const el = document.getElementById('f_' + k);
            if (el) this.current[k] = el.value;
        });
    },

    async addNew() {
        this.pushUndo();
        const res = await pyApi('newFormation');
        if (!res.success) { showToast(res.message || '创建失败', 'error'); return; }
        const entry = res.data || {};
        if (!entry.No) {
            const maxNo = this.data.reduce((max, d) => Math.max(max, parseInt(d.No) || 0), 0);
            entry.No = String(maxNo + 1);
        }
        this.data.push(entry);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        document.getElementById('formationCount').textContent = this.data.length;
    },

    cloneCurrent() {
        this.pushUndo();
        if (!this.current) { showToast('请先选择一个阵型', 'warning'); return; }
        const clone = Object.assign({}, this.current);
        const usedIds = new Set(this.data.map(f => parseInt(f.No)));
        let newId = 0;
        for (let i = 1; i < 100; i++) { if (!usedIds.has(i)) { newId = i; break; } }
        clone.No = newId;
        clone.Name = (clone.Name || '克隆阵型') + '_副本';
        this.data.push(clone);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        document.getElementById('formationCount').textContent = this.data.length;
    },

    deleteCurrent() {
        this.pushUndo();
        if (!this.current) return;
        if (!confirm(`确认删除阵型 "${this.current.Name}"?`)) return;
        const no = parseInt(this.current.No);
        pyApi('deleteIniItem', 'Setting/Formation.ini', 'FORMATION', 'No', String(no));
        this.data = this.data.filter(f => parseInt(f.No) !== no);
        this.current = null; this.currentIndex = -1; this.changed = true;
        this.renderList();
        document.getElementById('formationCount').textContent = this.data.length;
        document.getElementById('emptyFormationDetail').style.display = 'flex';
        document.getElementById('formationDetailContent').style.display = 'none';
    },

    search(keyword) {
        const container = document.getElementById('formationList');
        if (!container) return;
        container.innerHTML = '';
        const kw = keyword.toLowerCase();
        this.data.forEach((f, idx) => {
            const name = (f.Name || '').toLowerCase();
            const no = String(f.No || '');
            if (!kw || name.includes(kw) || no.includes(kw)) {
                const card = document.createElement('div');
                card.className = 'item-card';
                card.innerHTML = `
                    <div class="item-card-header"><span class="item-name">${f.Name||'无名'}</span><span class="item-no">#${f.No||''}</span></div>
                    <div class="item-desc">ATK+${f.ATK||0}% DEF+${f.DEF||0}%</div>
                `;
                card.onclick = () => this.select(idx);
                container.appendChild(card);
            }
        });
    },

    renderCounterTable() {
        const container = document.getElementById('formationCounterTable');
        if (!container) return;
        let html = '<div class="formation-counter">';
        this.data.forEach(f => {
            const c1 = parseInt(f.Counter1) || 0;
            const c2 = parseInt(f.Counter2) || 0;
            const w = parseInt(f.WeakTo) || 0;
            const c1Name = c1 ? (this.data.find(x => parseInt(x.No) === c1) || {}).Name || c1 : '-';
            const c2Name = c2 ? (this.data.find(x => parseInt(x.No) === c2) || {}).Name || c2 : '-';
            const wName = w ? (this.data.find(x => parseInt(x.No) === w) || {}).Name || w : '-';
            html += `
                <div class="formation-counter-item">
                    <div class="fc-name">${f.Name || '#'+f.No}</div>
                    <div class="fc-info">ATK+${f.ATK||0}% DEF+${f.DEF||0}% SPD+${f.Speed||0}%</div>
                    <div class="fc-counter">克: ${c1Name}${c2 ? '、'+c2Name : ''}</div>
                    <div class="fc-weak">被克: ${wName}</div>
                </div>
            `;
        });
        html += '</div>';
        container.innerHTML = html;
    }
};

// ============================================================
// 官职系统编辑器
// ============================================================

const titleEditor = {
    data: [], currentIndex: -1, current: null, changed: false,
    _fields: ['No','Name','Type','Level','Hide','Cost','LimitGen','Race','LimitLevel','Gens',
        'Str0','Str1','Int0','Int1','HP','MP','Str','Int','Speed','IsUsed',
        'BFMagic1','BFMagic2','BFMagic3','BFMagic4','BFMagic5',
        'SFMagic1','SFMagic2','SFMagic3','SFMagic4','SFMagic5',
        'SolType1','SolType2','Formation',
        'GenSkill01','GenSkill02','ArmySkill01','ArmySkill02','AGSkill01','AGSkill02',
        'LimitCustomGeneral','LimitHistory'],

    async load() {
        const res = await pyApi('loadTitles');
        if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
        this.data = res.data || [];
        this.currentIndex = -1; this.current = null;
        this.renderList(); this.renderTree();
        document.getElementById('titleCount').textContent = this.data.length;
        setupTooltips('title', 'ti_');
    },
    snapshot() { return JSON.parse(JSON.stringify(this.data)); },
    restoreSnapshot(data) { this.data = data; this.currentIndex = -1; this.current = null; this.renderList(); this.changed = false; },
    pushUndo() { UndoManager.pushState('title', this.snapshot()); },
    async save() {
        if (!(await validateBeforeSave())) return;
        if (this.current && this.changed) this.saveCurrent();
        const res = await pyApi('saveTitles', this.data);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) this.changed = false;
    },

    renderList() {
        const container = document.getElementById('titleList');
        if (!container) return;
        const filter = document.getElementById('titleRankFilter')?.value || 'all';
        container.innerHTML = '';
        this.data.forEach((t, idx) => {
            const type = parseInt(t.Type) || 1;
            const typeLabel = type === 2 ? '文' : type === 3 ? '特' : '武';
            const cost = parseInt(t.Cost) || 0;
            if (filter !== 'all') {
                if (filter === 'w' && type !== 1) return;
                if (filter === 'e' && type !== 2) return;
                if (filter === 's' && type !== 3) return;
            }
            const card = document.createElement('div');
            card.className = 'item-card' + (idx === this.currentIndex ? ' selected' : '');
            card.innerHTML = '<div class="item-card-header"><span class="item-name">' + escHtml(t.Name||'无名') + '</span><span class="item-no">#' + (t.No||'') + '</span></div><div class="item-desc">' + typeLabel + '官 | 功勋' + cost + ' | Lv' + (t.Level||0) + '</div>';
            card.onclick = (function(idx) { return function() { titleEditor.select(idx); }; })(idx);
            container.appendChild(card);
        });
    },

    select(idx) {
        if (idx < 0 || idx >= this.data.length) return;
        if (this.current && this.changed) this.saveCurrent();
        this.currentIndex = idx;
        this.current = this.data[idx];
        this.renderDetail();
        this.renderList();
        this.changed = false;
    },

    renderDetail() {
        const emptyEl = document.getElementById('emptyTitleDetail');
        const detailEl = document.getElementById('titleDetailContent');
        if (!this.current) { if (emptyEl) emptyEl.style.display = 'flex'; if (detailEl) detailEl.style.display = 'none'; return; }
        if (emptyEl) emptyEl.style.display = 'none';
        if (detailEl) detailEl.style.display = 'block';
        var self = this;
        this._fields.forEach(function(k) {
            const el = document.getElementById('ti_' + k);
            if (el) {
                if (el.tagName === 'SELECT') el.value = String(self.current[k] || '');
                else el.value = self.current[k] || '';
            }
        });
    },

    currentChanged() { this.changed = true; },

    saveCurrent() {
        if (!this.current) return;
        var self = this;
        this._fields.forEach(function(k) {
            const el = document.getElementById('ti_' + k);
            if (el) self.current[k] = el.value;
        });
    },

    async addNew() {
        this.pushUndo();
        const res = await pyApi('newTitle');
        if (res.success) {
            this.data.push(res.data);
            this.changed = true;
            this.renderList();
            this.select(this.data.length - 1);
            document.getElementById('titleCount').textContent = this.data.length;
        } else { showToast(res.message, res && res.success ? 'success' : 'error'); }
    },

    cloneCurrent() {
        this.pushUndo();
        if (!this.current) { showToast('请先选择一个官职', 'warning'); return; }
        const clone = Object.assign({}, this.current);
        const usedIds = new Set(this.data.map(t => parseInt(t.No)));
        let newId = 0;
        for (let i = 1; i < 10000; i++) { if (!usedIds.has(i)) { newId = i; break; } }
        clone.No = newId;
        clone.Name = (clone.Name || '克隆官职') + '_副本';
        this.data.push(clone);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        document.getElementById('titleCount').textContent = this.data.length;
    },

    deleteCurrent() {
        this.pushUndo();
        if (!this.current) return;
        if (!confirm(`确认删除官职 "${this.current.Name}"?`)) return;
        const no = parseInt(this.current.No);
        pyApi('deleteIniItem', 'Setting/Title.ini', 'TITLE', 'No', String(no));
        this.data = this.data.filter(t => parseInt(t.No) !== no);
        this.current = null; this.currentIndex = -1; this.changed = true;
        this.renderList();
        document.getElementById('titleCount').textContent = this.data.length;
        document.getElementById('emptyTitleDetail').style.display = 'flex';
        document.getElementById('titleDetailContent').style.display = 'none';
    },

    search(keyword) {
        const container = document.getElementById('titleList');
        if (!container) return;
        const kw = (keyword || '').toLowerCase();
        const filter = document.getElementById('titleRankFilter')?.value || 'all';
        container.innerHTML = '';
        this.data.forEach(function(t, idx) {
            const name = (t.Name || '').toLowerCase();
            const no = String(t.No || '');
            const type = parseInt(t.Type) || 1;
            const typeLabel = type === 2 ? '文' : type === 3 ? '特' : '武';
            const cost = parseInt(t.Cost) || 0;
            if (filter !== 'all') {
                if (filter === 'w' && type !== 1) return;
                if (filter === 'e' && type !== 2) return;
                if (filter === 's' && type !== 3) return;
            }
            if (kw && !name.includes(kw) && !no.includes(kw)) return;
            const card = document.createElement('div');
            card.className = 'item-card';
            card.innerHTML = '<div class="item-card-header"><span class="item-name">' + escHtml(t.Name||'无名') + '</span><span class="item-no">#' + (t.No||'') + '</span></div><div class="item-desc">' + typeLabel + '官 | 功勋' + cost + ' | Lv' + (t.Level||0) + '</div>';
            card.onclick = (function(idx) { return function() { titleEditor.select(idx); }; })(idx);
            container.appendChild(card);
        });
    },

    renderTree() {
        const container = document.getElementById('titleTreeContainer');
        if (!container) return;
        if (this.data.length === 0) { container.innerHTML = '<p class="hint">请先加载官职数据</p>'; return; }
        const groups = {};
        for (let r = 1; r <= 9; r++) groups[r] = [];
        this.data.forEach(function(t) {
            const level = parseInt(t.Level) || 1;
            const rank = Math.min(9, Math.max(1, Math.ceil(level / 10) || 1));
            if (!groups[rank]) groups[rank] = [];
            groups[rank].push(t);
        });
        let html = '<div class="title-tree"><div class="hint" style="margin-bottom:8px;color:var(--accent);">AI封官规则: 每季选Cost最低且满足武力/智力/等级条件的官职封给武将</div>';
        for (let r = 9; r >= 1; r--) {
            if (!groups[r] || groups[r].length === 0) continue;
            html += '<div class="title-rank-group"><h4>Lv' + (r*10) + '级 (' + groups[r].length + '个)</h4><div class="title-rank-items">';
            groups[r].sort(function(a,b) { return (parseInt(a.Cost)||0) - (parseInt(b.Cost)||0); }).forEach(function(t) {
                const type = parseInt(t.Type) || 1;
                const typeLabel = type === 2 ? '文' : type === 3 ? '特' : '武';
                html += '<div class="title-chip" onclick="titleEditor.selectByNo(' + t.No + ')"><div class="tc-name">' + escHtml(t.Name || '#'+t.No) + ' <span style="color:var(--text-muted);font-size:10px;">' + typeLabel + '</span></div><div>功勋' + (t.Cost||0) + ' | 武' + (t.Str0||0) + '-' + (t.Str1||0) + ' | 智' + (t.Int0||0) + '-' + (t.Int1||0) + '</div></div>';
            });
            html += '</div></div>';
        }
        html += '</div>';
        container.innerHTML = html;
    },

    selectByNo(no) {
        const idx = this.data.findIndex(t => parseInt(t.No) === no);
        if (idx >= 0) this.select(idx);
    },

    simulateAI() {
        const str = parseInt(document.getElementById('aiSimStr').value) || 0;
        const int = parseInt(document.getElementById('aiSimInt').value) || 0;
        const lv = parseInt(document.getElementById('aiSimLv').value) || 0;
        const simType = parseInt(document.getElementById('aiSimType').value) || 1;
        const resultEl = document.getElementById('aiSimResult');
        const pathEl = document.getElementById('aiSimPath');
        if (!this.data || this.data.length === 0) {
            resultEl.textContent = '请先加载官职数据';
            resultEl.style.color = 'var(--danger)';
            return;
        }
        // 筛选符合条件的官职: 武力/智力/等级/类型匹配，且IsUsed启用
        const eligible = this.data.filter(function(t) {
            const tType = parseInt(t.Type) || 1;
            if (simType !== 3 && tType !== simType && tType !== 3) return false;
            if (parseInt(t.IsUsed) === 0) return false;
            const str0 = parseInt(t.Str0) || 0;
            const str1 = parseInt(t.Str1) || 255;
            const int0 = parseInt(t.Int0) || 0;
            const int1 = parseInt(t.Int1) || 255;
            const reqLv = parseInt(t.Level) || 0;
            if (str < str0 || str > str1) return false;
            if (int < int0 || int > int1) return false;
            if (lv < reqLv) return false;
            return true;
        });
        // 按Cost升序排序（AI的选择逻辑）
        eligible.sort(function(a, b) { return (parseInt(a.Cost) || 0) - (parseInt(b.Cost) || 0); });
        if (eligible.length === 0) {
            resultEl.textContent = '武力' + str + ' 智力' + int + ' 等级' + lv + ' → 无符合条件的官职';
            resultEl.style.color = 'var(--danger)';
            pathEl.innerHTML = '<p class="hint">该武将不满足任何官职的条件。尝试降低Str0/Int0门槛或提高武将属性。</p>';
            return;
        }
        resultEl.textContent = '武力' + str + ' 智力' + int + ' 等级' + lv + ' → 共 ' + eligible.length + ' 个可选官职，AI将按Cost从低到高依次封官';
        resultEl.style.color = 'var(--success)';
        let html = '<div style="margin-bottom:4px;color:var(--text-muted);">AI封官顺序（Cost升序）:</div>';
        html += '<div style="display:flex;flex-wrap:wrap;gap:4px;">';
        eligible.forEach(function(t, i) {
            const typeLabel = parseInt(t.Type) === 2 ? '文' : parseInt(t.Type) === 3 ? '特' : '武';
            const bg = i === 0 ? 'var(--accent)' : i < 5 ? 'var(--bg-card)' : 'rgba(255,255,255,0.03)';
            const color = i === 0 ? '#fff' : 'var(--ink)';
            html += '<div style="padding:4px 8px;background:' + bg + ';color:' + color + ';border-radius:4px;border:1px solid var(--border);cursor:pointer;font-size:11px;" onclick="titleEditor.selectByNo(' + t.No + ')" title="Cost:' + (t.Cost||0) + ' | 武' + (t.Str0||0) + '-' + (t.Str1||0) + ' | 智' + (t.Int0||0) + '-' + (t.Int1||0) + '">';
            html += '<b>' + (i+1) + '. ' + escHtml(t.Name || '#'+t.No) + '</b> <span style="font-size:10px;opacity:0.7;">' + typeLabel + ' Cost:' + (t.Cost||0) + '</span>';
            html += '<div style="font-size:10px;opacity:0.7;">+HP' + (t.HP||0) + ' +MP' + (t.MP||0) + ' +武' + (t.Str||0) + ' +智' + (t.Int||0) + '</div>';
            html += '</div>';
        });
        html += '</div>';
        html += '<div style="margin-top:8px;color:var(--text-muted);font-size:10px;">';
        html += '第1个(高亮) = AI当前立即封官 | 后续依次晋升 | 点击可查看官职详情';
        if (eligible.length > 1) {
            const totalCost = eligible.reduce(function(s, t) { return s + (parseInt(t.Cost) || 0); }, 0);
            html += '<br>全部封完需累计功勋: ' + totalCost.toLocaleString();
        }
        html += '</div>';
        pathEl.innerHTML = html;
    }
};

// ============================================================
// 物品商店售卖配置
// ============================================================

const storeConfig = {
    _cities: ['洛阳','长安','许昌','邺城','成都','建业','江陵','襄阳','汉中','下邳','北海','宛城','寿春','天水','会稽','吴郡'],
    _config: {},
    changed: false,

    async load() {
        const res = await pyApi('loadStoreConfig');
        if (res.success && res.data) {
            this._config = res.data;
        }
        this._cities.forEach(c => {
            if (!this._config[c]) this._config[c] = '';
        });
        this.render();
    },

    render() {
        const container = document.getElementById('storeConfigContainer');
        if (!container) return;
        container.innerHTML = this._cities.map(c => `
            <div class="form-group">
                <label>${c}</label>
                <input type="text" id="store_${c}" value="${escHtml(this._config[c] || '')}" placeholder="物品编号,用逗号分隔" onchange="storeConfig._set('${c}',this.value)">
            </div>
        `).join('');
    },

    _set(city, value) {
        this._config[city] = value;
        this.changed = true;
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        this.pushUndo();
        const data = [];
        this._cities.forEach((city, idx) => {
            data.push({ city: idx + 1, name: city, items: this._config[city] || '' });
        });
        const res = await pyApi('saveStoreConfig', data);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) this.changed = false;
    },

    snapshot() { return JSON.parse(JSON.stringify(this._config)); },
    restoreSnapshot(s) { this._config = JSON.parse(JSON.stringify(s)); this.render(); },
    pushUndo() { UndoManager.pushState('storeConfig', this.snapshot()); },
};

// ============================================================
// 合成配方编辑
// ============================================================

const crafting = {
    _recipes: [],
    changed: false,

    async load() {
        const res = await pyApi('loadItemEnhance');
        if (res.success && res.data) {
            this._recipes = res.data.map(r => ({
                No: r.No || '',
                Item: r.Item || '',
                Mat1: r.Mat1 || '',
                Num1: r.Num1 || '',
                Mat2: r.Mat2 || '',
                Num2: r.Num2 || '',
                Result: r.Result || '',
                Rate: r.Rate || '100',
            }));
        }
        if (this._recipes.length === 0) {
            this._recipes = [];
        }
        this.render();
    },

    addRecipe() {
        this._recipes.push({
            No: '',
            Item: '',
            Mat1: '',
            Num1: '',
            Mat2: '',
            Num2: '',
            Result: '',
            Rate: '100',
        });
        this.changed = true;
        this.render();
    },

    removeRecipe(index) {
        this._recipes.splice(index, 1);
        this.changed = true;
        this.render();
    },

    render() {
        const container = document.getElementById('craftingContainer');
        if (!container) return;
        if (this._recipes.length === 0) {
            container.innerHTML = '<p class="hint">暂无合成配方，点击「新增配方」添加</p>';
            return;
        }
        container.innerHTML = this._recipes.map((r, idx) => `
            <div class="panel-card" style="margin-bottom:8px;">
                <div style="padding:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                    <span style="font-size:11px;color:var(--text-muted);">#${idx+1}</span>
                    <div class="form-group" style="margin:0;width:60px;">
                        <label style="font-size:10px;">序号</label>
                        <input type="number" value="${r.No}" onchange="crafting._recipes[${idx}].No=this.value" style="font-size:11px;">
                    </div>
                    <div class="form-group" style="margin:0;flex:1;min-width:100px;">
                        <label style="font-size:10px;">源物品编号</label>
                        <input type="number" value="${r.Item}" onchange="crafting._recipes[${idx}].Item=this.value" style="font-size:11px;">
                    </div>
                    <div class="form-group" style="margin:0;flex:1;min-width:100px;">
                        <label style="font-size:10px;">材料1编号</label>
                        <input type="number" value="${r.Mat1}" onchange="crafting._recipes[${idx}].Mat1=this.value" style="font-size:11px;">
                    </div>
                    <div class="form-group" style="margin:0;width:60px;">
                        <label style="font-size:10px;">数量</label>
                        <input type="number" value="${r.Num1}" onchange="crafting._recipes[${idx}].Num1=this.value" style="font-size:11px;">
                    </div>
                    <div class="form-group" style="margin:0;flex:1;min-width:100px;">
                        <label style="font-size:10px;">材料2编号</label>
                        <input type="number" value="${r.Mat2}" onchange="crafting._recipes[${idx}].Mat2=this.value" style="font-size:11px;">
                    </div>
                    <div class="form-group" style="margin:0;width:60px;">
                        <label style="font-size:10px;">数量</label>
                        <input type="number" value="${r.Num2}" onchange="crafting._recipes[${idx}].Num2=this.value" style="font-size:11px;">
                    </div>
                    <div class="form-group" style="margin:0;flex:1;min-width:120px;">
                        <label style="font-size:10px;">成品编号</label>
                        <input type="number" value="${r.Result}" onchange="crafting._recipes[${idx}].Result=this.value" style="font-size:11px;">
                    </div>
                    <div class="form-group" style="margin:0;width:80px;">
                        <label style="font-size:10px;">成功率%</label>
                        <input type="number" value="${r.Rate}" onchange="crafting._recipes[${idx}].Rate=this.value" style="font-size:11px;">
                    </div>
                    <button onclick="crafting.removeRecipe(${idx})" class="btn btn-danger btn-sm" style="margin-top:14px;">删除</button>
                </div>
            </div>
        `).join('');
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        this.pushUndo();
        const res = await pyApi('saveItemEnhance', this._recipes);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) this.changed = false;
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this._recipes));
    },

    restoreSnapshot(data) {
        this._recipes = JSON.parse(JSON.stringify(data));
        this.render();
    },

    pushUndo() {
        UndoManager.pushState('crafting', this.snapshot());
    },
};

// ============================================================
// 剧本编辑器
// ============================================================

const scenarioEditor = {
    data: [],
    currentIndex: -1,
    current: null,
    changed: false,

    async load() {
        const res = await pyApi('loadScenarios');
        if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
        this.data = res.data || [];
        this.currentIndex = -1; this.current = null;
        this.renderList();
        document.getElementById('scenarioCount').textContent = this.data.length;
        globalParams._scenarios = this.data;
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this.data));
    },

    restoreSnapshot(data) {
        this.data = data;
        this.currentIndex = -1;
        this.current = null;
        this.renderList();
        this.changed = false;
    },

    pushUndo() {
        UndoManager.pushState('scenario', this.snapshot());
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        if (this.current && this.changed) this.saveCurrent();
        this.pushUndo();
        const res = await pyApi('saveScenarios', this.data);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) this.changed = false;
    },

    renderList() {
        const container = document.getElementById('scenarioList');
        if (!container) return;
        container.innerHTML = '';
        this.data.forEach((s, idx) => {
            const card = document.createElement('div');
            card.className = 'item-card' + (idx === this.currentIndex ? ' selected' : '');
            card.innerHTML = `
                <div class="item-card-header">
                    <span class="item-name">${s.Name || '无名'}</span>
                    <span class="item-no">#${s.No || ''}</span>
                </div>
                <div class="item-desc">${s.Year || '?'}年 | ${s.Desc || ''}</div>
            `;
            card.onclick = () => this.select(idx);
            container.appendChild(card);
        });
    },

    select(idx) {
        if (idx < 0 || idx >= this.data.length) return;
        if (this.current && this.changed) this.saveCurrent();
        this.currentIndex = idx;
        this.current = this.data[idx];
        this.renderDetail();
        this.renderList();
        this.changed = false;
    },

    renderDetail() {
        const emptyEl = document.getElementById('emptyScenarioDetail');
        const detailEl = document.getElementById('scenarioDetailContent');
        if (!this.current) {
            if (emptyEl) emptyEl.style.display = 'flex';
            if (detailEl) detailEl.style.display = 'none';
            return;
        }
        if (emptyEl) emptyEl.style.display = 'none';
        if (detailEl) detailEl.style.display = 'block';
        ['No','Name','Year','Desc','Nations'].forEach(k => {
            const el = document.getElementById('sc_' + k);
            if (el) el.value = this.current[k] || '';
        });
        // 提示势力名称
        const hint = document.getElementById('sc_NationsHint');
        if (hint) {
            const ids = (this.current.Nations || '').split(',').map(s => s.trim()).filter(Boolean);
            const names = ids.map(id => {
                const n = nationEditor.data.find(x => String(x.No) === id);
                return n ? n.Name : '#'+id;
            });
            hint.textContent = ids.length ? '→ ' + names.join(', ') : '';
        }
    },

    currentChanged() { this.changed = true; },

    saveCurrent() {
        if (!this.current) return;
        ['No','Name','Year','Desc','Nations'].forEach(k => {
            const el = document.getElementById('sc_' + k);
            if (el) this.current[k] = el.value;
        });
    },

    addNew() {
        this.pushUndo();
        const usedIds = new Set(this.data.map(s => parseInt(s.No)));
        let newId = 0;
        for (let i = 1; i < 100; i++) { if (!usedIds.has(i)) { newId = i; break; } }
        const entry = {No:newId, Name:'新剧本_'+newId, Year:200, Desc:'', Nations:''};
        this.data.push(entry);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        document.getElementById('scenarioCount').textContent = this.data.length;
    },

    cloneCurrent() {
        this.pushUndo();
        if (!this.current) { showToast('请先选择一个剧本', 'warning'); return; }
        const clone = Object.assign({}, this.current);
        const usedIds = new Set(this.data.map(s => parseInt(s.No)));
        let newId = 0;
        for (let i = 1; i < 100; i++) { if (!usedIds.has(i)) { newId = i; break; } }
        clone.No = newId;
        clone.Name = (clone.Name || '克隆剧本') + '_副本';
        this.data.push(clone);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        document.getElementById('scenarioCount').textContent = this.data.length;
    },

    deleteCurrent() {
        this.pushUndo();
        if (!this.current) return;
        if (!confirm(`确认删除剧本 "${this.current.Name}"?`)) return;
        const no = parseInt(this.current.No);
        pyApi('deleteIniItem', 'Setting/Scenario.ini', 'SCENARIO', 'No', String(no));
        this.data = this.data.filter(s => parseInt(s.No) !== no);
        this.current = null; this.currentIndex = -1; this.changed = true;
        this.renderList();
        document.getElementById('scenarioCount').textContent = this.data.length;
        document.getElementById('emptyScenarioDetail').style.display = 'flex';
        document.getElementById('scenarioDetailContent').style.display = 'none';
    },

    search(keyword) {
        const container = document.getElementById('scenarioList');
        if (!container) return;
        container.innerHTML = '';
        const kw = keyword.toLowerCase();
        this.data.forEach((s, idx) => {
            const name = (s.Name || '').toLowerCase();
            const no = String(s.No || '');
            if (!kw || name.includes(kw) || no.includes(kw)) {
                const card = document.createElement('div');
                card.className = 'item-card';
                card.innerHTML = `
                    <div class="item-card-header"><span class="item-name">${s.Name||'无名'}</span><span class="item-no">#${s.No||''}</span></div>
                    <div class="item-desc">${s.Year||'?'}年</div>
                `;
                card.onclick = () => this.select(idx);
                container.appendChild(card);
            }
        });
    }
};

// ============================================================
// 全局游戏参数 (Variable.ini - 完整覆盖)
// ============================================================

// 参数分类映射 (基于 No 范围)
const VAR_CATEGORIES = {
    '镜头与显示': [1, 14],
    '防御塔': [15, 20],
    '比武大会': [21, 30],
    '城市内政': [100, 131],
    '搜索人才': [132, 136],
    'AI与经验': [137, 150],
    '必杀熟练度': [151, 180],
    '外交系统': [138, 150],
    '事件部队': [230, 238],
    '聚宝洞府': [239, 244],
    '蓬莱百货': [245, 249],
    '其他': [0, 9999],
};

function getVarCategory(no) {
    for (const [name, [lo, hi]] of Object.entries(VAR_CATEGORIES)) {
        if (no >= lo && no <= hi) return name;
    }
    return '其他';
}

const globalParams = {
    _data: [],
    _filtered: [],
    _current: null,
    _categoryFilter: '',
    changed: false,

    async load() {
        const res = await pyApi('loadGlobalParams');
        if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
        this._data = res.data || [];
        this._filtered = [...this._data];
        this._categoryFilter = '';
        document.getElementById('varParamCount').textContent = this._data.length;
        document.getElementById('varParamSearch').value = '';
        this.renderCategoryStats();
        this.renderList();
        this.renderDetail();
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this._data));
    },

    restoreSnapshot(data) {
        this._data = data;
        this._filtered = [...this._data];
        this._current = null;
        this.renderList();
        this.renderDetail();
    },

    pushUndo() {
        UndoManager.pushState('globalParams', this.snapshot());
    },

    renderCategoryStats() {
        const cats = {};
        this._data.forEach(p => {
            const c = getVarCategory(p.No);
            cats[c] = (cats[c] || 0) + 1;
        });
        const container = document.getElementById('varCategoryStats');
        if (!container) return;
        container.innerHTML = Object.entries(cats).map(([name, count]) =>
            `<span class="var-cat-tag" data-cat="${name}" onclick="globalParams.filterByCategory('${name}')">${name} (${count})</span>`
        ).join('') + `<span class="var-cat-tag var-cat-all" onclick="globalParams.filterByCategory('')">全部 (${this._data.length})</span>`;
    },

    filterByCategory(cat) {
        this._categoryFilter = cat;
        this.applyFilters();
    },

    search(keyword) {
        this.applyFilters();
    },

    applyFilters() {
        const kw = (document.getElementById('varParamSearch')?.value || '').toLowerCase();
        let list = [...this._data];
        if (this._categoryFilter) {
            list = list.filter(p => getVarCategory(p.No) === this._categoryFilter);
        }
        if (kw) {
            list = list.filter(p =>
                (p.Name || '').toLowerCase().includes(kw) ||
                (p.EnumName || '').toLowerCase().includes(kw) ||
                String(p.No).includes(kw)
            );
        }
        this._filtered = list;
        this.renderList();
    },

    renderList() {
        const container = document.getElementById('varParamList');
        if (!container) return;
        if (this._filtered.length === 0) {
            container.innerHTML = '<div class="empty-detail">无匹配参数</div>';
            return;
        }
        const display = this._filtered.slice(0, 200); // 最多显示200条
        container.innerHTML = display.map((p, i) => {
            const cat = getVarCategory(p.No);
            const active = this._current && this._current.No === p.No ? ' active' : '';
            return `<div class="var-param-row${active}" onclick="globalParams.select(${i})" data-idx="${i}">
                <span class="var-param-no">#${p.No}</span>
                <span class="var-param-name">${escHtml(p.Name || '未命名')}</span>
                <span class="var-param-enum">${escHtml(p.EnumName || '')}</span>
                <span class="var-param-cat">${cat}</span>
            </div>`;
        }).join('');
        if (this._filtered.length > 200) {
            container.innerHTML += `<div class="hint" style="text-align:center;padding:8px;">仅显示前200条，共${this._filtered.length}条。请使用搜索或分类筛选</div>`;
        }
    },

    select(idx) {
        if (idx < 0 || idx >= this._filtered.length) return;
        this._current = this._filtered[idx];
        this.renderDetail();
        this.renderList(); // 刷新高亮
    },

    renderDetail() {
        const container = document.getElementById('varParamDetail');
        if (!container) return;
        if (!this._current) {
            container.innerHTML = '<div class="empty-detail">请从左侧列表选择一个参数</div>';
            return;
        }
        const p = this._current;
        const intFields = [];
        const floatFields = [];
        for (let i = 0; i < 10; i++) {
            const ik = `Int${String(i).padStart(2, '0')}`;
            if (p[ik] !== undefined && p[ik] !== '0') intFields.push({key: ik, value: p[ik]});
            const fk = `Float${String(i).padStart(2, '0')}`;
            if (p[fk] !== undefined && p[fk] !== '0' && p[fk] !== '0.0') floatFields.push({key: fk, value: p[fk]});
        }
        container.innerHTML = `
            <div class="var-detail-header">
                <div class="form-row">
                    <div class="form-group"><label>编号 No</label><input type="number" id="var_No" value="${p.No}" onchange="globalParams._setField('No',this.value)"></div>
                    <div class="form-group"><label>名称 Name</label><input type="text" id="var_Name" value="${escHtml(p.Name)}" onchange="globalParams._setField('Name',this.value)"></div>
                    <div class="form-group"><label>枚举名 EnumName</label><input type="text" id="var_EnumName" value="${escHtml(p.EnumName)}" onchange="globalParams._setField('EnumName',this.value)"></div>
                </div>
            </div>
            <div class="panel-card" style="margin-top:12px;">
                <div class="panel-card-header"><h4>整数参数 (Int00-Int09)</h4></div>
                <div style="padding:8px;display:grid;grid-template-columns:repeat(5,1fr);gap:6px;">
                    ${[0,1,2,3,4,5,6,7,8,9].map(i => {
                        const ik = `Int${String(i).padStart(2,'0')}`;
                        return `<div class="form-group"><label>${ik}</label><input type="number" id="var_${ik}" value="${p[ik] || '0'}" onchange="globalParams._setField('${ik}',this.value)"></div>`;
                    }).join('')}
                </div>
            </div>
            <div class="panel-card" style="margin-top:12px;">
                <div class="panel-card-header"><h4>浮点参数 (Float00-Float09)</h4></div>
                <div style="padding:8px;display:grid;grid-template-columns:repeat(5,1fr);gap:6px;">
                    ${[0,1,2,3,4,5,6,7,8,9].map(i => {
                        const fk = `Float${String(i).padStart(2,'0')}`;
                        return `<div class="form-group"><label>${fk}</label><input type="number" step="0.01" id="var_${fk}" value="${p[fk] || '0'}" onchange="globalParams._setField('${fk}',this.value)"></div>`;
                    }).join('')}
                </div>
            </div>`;
    },

    _setField(key, value) {
        if (!this._current) return;
        if (key === 'No') {
            this._current.No = parseInt(value) || 0;
        } else {
            this._current[key] = value;
        }
        this.changed = true;
    },

    addNew() {
        this.pushUndo();
        const maxNo = this._data.reduce((m, p) => Math.max(m, parseInt(p.No) || 0), 0);
        const newEntry = { No: String(maxNo + 1), Name: '新参数', Int00: '0' };
        // 复制第一个条目的字段结构
        if (this._data.length > 0) {
            const template = this._data[0];
            Object.keys(template).forEach(k => {
                if (!(k in newEntry)) newEntry[k] = template[k];
            });
            newEntry.No = String(maxNo + 1);
            newEntry.Name = '新参数';
        }
        this._data.push(newEntry);
        this._current = newEntry;
        this._currentIndex = this._data.length - 1;
        this.renderDetail();
        this.renderList();
    },

    cloneCurrent() {
        if (!this._current) return;
        this.pushUndo();
        const maxNo = this._data.reduce((m, p) => Math.max(m, parseInt(p.No) || 0), 0);
        const clone = Object.assign({}, this._current);
        clone.No = String(maxNo + 1);
        clone.Name = (clone.Name || '') + '(副本)';
        this._data.push(clone);
        this._current = clone;
        this._currentIndex = this._data.length - 1;
        this.renderDetail();
        this.renderList();
    },

    deleteCurrent() {
        if (!this._current) return;
        this.pushUndo();
        if (!confirm(`确认删除参数 No.${this._current.No} "${this._current.Name || ''}"?`)) return;
        this._data.splice(this._currentIndex, 1);
        this._current = null;
        this._currentIndex = -1;
        this.renderDetail();
        this.renderList();
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        this.pushUndo();
        const res = await pyApi('saveGlobalParams', this._data);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) this.changed = false;
    }
};

// ============================================================
// 势力编辑器
// ============================================================

const nationEditor = {
    data: [],
    currentIndex: -1,
    current: null,
    changed: false,
    _generals: [],
    _cities: [],

    async load() {
        const res = await pyApi('loadNations');
        if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
        this.data = res.data || [];
        this.currentIndex = -1; this.current = null;
        // 预加载武将和城池名
        const gRes = await pyApi('loadGenerals');
        if (gRes.success) this._generals = gRes.data || [];
        const cRes = await pyApi('loadCities');
        if (cRes.success) this._cities = cRes.data || [];
        this.renderList();
        document.getElementById('nationCount').textContent = this.data.length;
        this.renderOverview();
        setupTooltips('nation', 'n_');
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this.data));
    },

    restoreSnapshot(data) {
        this.data = data;
        this.currentIndex = -1;
        this.current = null;
        this.renderList();
        this.changed = false;
    },

    pushUndo() {
        UndoManager.pushState('nation', this.snapshot());
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        if (this.current && this.changed) this.saveCurrent();
        const res = await pyApi('saveNations', this.data);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) this.changed = false;
    },

    async createLinkage() {
        if (!this.current) { showToast('请先选择一个势力', 'warning'); return; }
        const no = this.current.No;
        const name = this.current.Name || '';
        if (!no) { showToast('势力编号不能为空', 'info'); return; }

        // 先检查联动状态
        const check = await pyApi('nationLinkageCheck', String(no));
        if (check && check.success && check.data) {
            const d = check.data;
            let status = '';
            if (d.color) status += 'Color: 已存在 ';
            else status += 'Color: 缺失 ';
            if (d.city) status += '| City: 已存在';
            else status += '| City: 缺失';
            if (d.linked) {
                if (!confirm(`势力 "${name}" (No.${no}) 联动状态:\n${status}\n\n是否重新创建联动数据？`)) return;
            }
        }

        // 获取君主编号
        const lord = parseInt(this.current.Lord) || 0;

        // 使用默认颜色（基于编号生成不同颜色）
        const colors = [
            [255,50,50], [50,150,255], [50,200,50], [255,200,50],
            [200,50,255], [50,255,200], [255,100,50], [100,200,255],
            [255,255,50], [150,255,50], [255,50,200], [50,255,100],
        ];
        const ci = (parseInt(no) || 0) % colors.length;
        const [cr, cg, cb] = colors[ci];

        const cityName = name ? name + '城' : '';

        try {
            const r = await pyApi('nationLinkageCreate', String(no), name, cr, cg, cb, cityName, lord);
            if (r && r.success) {
                showToast('✓ ' + (r.message || '联动创建成功'), 'info');
            } else {
                showToast('创建结果: ' + (r ? r.message : '未知错误'), 'info');
            }
        } catch(e) {
            showToast('联动创建失败: ' + e, 'error');
        }
    },

    renderList() {
        const container = document.getElementById('nationList');
        if (!container) return;
        container.innerHTML = '';
        this.data.forEach((n, idx) => {
            const card = document.createElement('div');
            card.className = 'item-card' + (idx === this.currentIndex ? ' selected' : '');
            const lord = this._getGeneralName(n.Lord);
            card.innerHTML = `
                <div class="item-card-header">
                    <span class="item-name">${n.Name || '无国号'}</span>
                    <span class="item-no">#${n.No || ''}</span>
                </div>
                <div class="item-desc">君主: ${lord} | 金钱: ${n.Money||0}</div>
            `;
            card.onclick = () => this.select(idx);
            container.appendChild(card);
        });
    },

    select(idx) {
        if (idx < 0 || idx >= this.data.length) return;
        if (this.current && this.changed) this.saveCurrent();
        this.currentIndex = idx;
        this.current = this.data[idx];
        this.renderDetail();
        this.renderList();
        this.changed = false;
    },

    renderDetail() {
        const emptyEl = document.getElementById('emptyNationDetail');
        const detailEl = document.getElementById('nationDetailContent');
        if (!this.current) {
            if (emptyEl) emptyEl.style.display = 'flex';
            if (detailEl) detailEl.style.display = 'none';
            return;
        }
        if (emptyEl) emptyEl.style.display = 'none';
        if (detailEl) detailEl.style.display = 'block';
        const fields = ['No','Name','Color','Lord','Advisor','Cities','Generals','Money','Food','Soldier'];
        fields.forEach(k => {
            const el = document.getElementById('na_' + k);
            if (el) {
                if (el.tagName === 'SELECT') el.value = String(this.current[k] || '');
                else el.value = this.current[k] || '';
            }
        });
        // 填充首都下拉
        const cap = document.getElementById('na_Capital');
        if (cap) {
            cap.innerHTML = '<option value="">无</option>' + this._cities.map(c => `<option value="${c.No}">${c.Name || '#'+c.No}</option>`).join('');
            cap.value = this.current.Capital || '';
        }
        // 提示
        this._showHint('na_LordHint', this.current.Lord, this._generals);
        this._showHint('na_AdvisorHint', this.current.Advisor, this._generals);
        this._showIdListHint('na_CitiesHint', this.current.Cities, this._cities);
        this._showIdListHint('na_GeneralsHint', this.current.Generals, this._generals);
    },

    _showHint(elId, rawId, source) {
        const hint = document.getElementById(elId);
        if (!hint) return;
        const id = parseInt(rawId) || 0;
        const target = id ? source.find(x => parseInt(x.No) === id) : null;
        hint.textContent = target ? `→ ${target.Name}` : '';
    },

    _showIdListHint(elId, raw, source) {
        const hint = document.getElementById(elId);
        if (!hint) return;
        if (!raw) { hint.textContent = ''; return; }
        const ids = String(raw).split(',').map(s => s.trim()).filter(Boolean);
        const names = ids.map(id => {
            const item = source.find(x => String(x.No) === id);
            return item ? item.Name : '#'+id;
        });
        hint.textContent = ids.length ? '→ ' + names.join(', ') : '';
    },

    _getGeneralName(no) {
        const id = parseInt(no) || 0;
        const g = this._generals.find(x => parseInt(x.No) === id);
        return g ? g.Name : (no || '无');
    },

    currentChanged() { this.changed = true; },

    saveCurrent() {
        if (!this.current) return;
        ['No','Name','Color','Lord','Advisor','Capital','Cities','Generals','Money','Food','Soldier'].forEach(k => {
            const el = document.getElementById('na_' + k);
            if (el) this.current[k] = el.value;
        });
    },

    async addNew() {
        this.pushUndo();
        const res = await pyApi('newNation');
        if (!res.success) { showToast(res.message || '创建失败', 'error'); return; }
        const entry = res.data || {};
        if (!entry.No) {
            const maxNo = this.data.reduce((max, d) => Math.max(max, parseInt(d.No) || 0), 0);
            entry.No = String(maxNo + 1);
        }
        this.data.push(entry);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        document.getElementById('nationCount').textContent = this.data.length;
    },

    cloneCurrent() {
        this.pushUndo();
        if (!this.current) { showToast('请先选择一个势力', 'warning'); return; }
        const clone = Object.assign({}, this.current);
        const usedIds = new Set(this.data.map(n => parseInt(n.No)));
        let newId = 0;
        for (let i = 1; i < 1000; i++) { if (!usedIds.has(i)) { newId = i; break; } }
        clone.No = newId;
        clone.Name = (clone.Name || '克隆势力') + '_副本';
        this.data.push(clone);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        document.getElementById('nationCount').textContent = this.data.length;
    },

    deleteCurrent() {
        this.pushUndo();
        if (!this.current) return;
        if (!confirm(`确认删除势力 "${this.current.Name}"?`)) return;
        const no = parseInt(this.current.No);
        pyApi('deleteIniItem', 'Setting/Nation.ini', 'NATION', 'No', String(no));
        this.data = this.data.filter(n => parseInt(n.No) !== no);
        this.current = null; this.currentIndex = -1; this.changed = true;
        this.renderList();
        document.getElementById('nationCount').textContent = this.data.length;
        document.getElementById('emptyNationDetail').style.display = 'flex';
        document.getElementById('nationDetailContent').style.display = 'none';
    },

    search(keyword) {
        const container = document.getElementById('nationList');
        if (!container) return;
        container.innerHTML = '';
        const kw = keyword.toLowerCase();
        this.data.forEach((n, idx) => {
            const name = (n.Name || '').toLowerCase();
            const no = String(n.No || '');
            if (!kw || name.includes(kw) || no.includes(kw)) {
                const card = document.createElement('div');
                card.className = 'item-card';
                card.innerHTML = `
                    <div class="item-card-header"><span class="item-name">${n.Name||'无国号'}</span><span class="item-no">#${n.No||''}</span></div>
                    <div class="item-desc">君主: ${this._getGeneralName(n.Lord)}</div>
                `;
                card.onclick = () => this.select(idx);
                container.appendChild(card);
            }
        });
    },

    renderOverview() {
        const container = document.getElementById('nationOverview');
        if (!container) return;
        if (this.data.length === 0) {
            container.innerHTML = '<p class="hint">请先加载势力数据</p>';
            return;
        }
        let html = '<div class="nation-overview">';
        this.data.forEach(n => {
            const lord = this._getGeneralName(n.Lord);
            const cities = (n.Cities || '').split(',').filter(Boolean).map(id => {
                const c = this._cities.find(x => String(x.No) === id.trim());
                return c ? c.Name : '#'+id;
            });
            html += `
                <div class="nation-card" style="border-color:${n.Color || '#555'};">
                    <div class="nation-card-header">
                        <span class="nation-card-name">${n.Name || '#'+n.No}</span>
                        <span class="nation-card-color" style="background:${n.Color || '#555'};"></span>
                    </div>
                    <div class="nation-card-info">
                        君主: ${lord}<br>
                        金钱: ${n.Money||0} | 粮草: ${n.Food||0}<br>
                        城池: ${cities.length ? cities.join(', ') : '无'}
                    </div>
                </div>
            `;
        });
        html += '</div>';
        container.innerHTML = html;
    }
};

// ============================================================
// 城池编辑器
// ============================================================

const cityEditor = {
    data: [],
    currentIndex: -1,
    current: null,
    changed: false,
    _nations: [],
    _generals: [],

    async load() {
        const res = await pyApi('loadCities');
        if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
        this.data = res.data || [];
        this.currentIndex = -1; this.current = null;
        const nRes = await pyApi('loadNations');
        if (nRes.success) this._nations = nRes.data || [];
        const gRes = await pyApi('loadGenerals');
        if (gRes.success) this._generals = gRes.data || [];
        this.renderList();
        document.getElementById('cityCount').textContent = this.data.length;
        this.renderOverview();
        setupTooltips('city', 'c_');
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this.data));
    },

    restoreSnapshot(data) {
        this.data = data;
        this.currentIndex = -1;
        this.current = null;
        this.renderList();
        this.changed = false;
    },

    pushUndo() {
        UndoManager.pushState('city', this.snapshot());
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        if (this.current && this.changed) this.saveCurrent();
        const res = await pyApi('saveCities', this.data);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) this.changed = false;
    },

    renderList() {
        const container = document.getElementById('cityList');
        if (!container) return;
        container.innerHTML = '';
        this.data.forEach((c, idx) => {
            const card = document.createElement('div');
            card.className = 'item-card' + (idx === this.currentIndex ? ' selected' : '');
            card.innerHTML = `
                <div class="item-card-header">
                    <span class="item-name">${c.Name || '无名'}</span>
                    <span class="item-no">#${c.No || ''}</span>
                </div>
                <div class="item-desc">类型 ${c.BuildingType||0} | 风格 ${c.BuildingStyle||0}</div>
            `;
            card.onclick = () => this.select(idx);
            container.appendChild(card);
        });
    },

    select(idx) {
        if (idx < 0 || idx >= this.data.length) return;
        if (this.current && this.changed) this.saveCurrent();
        this.currentIndex = idx;
        this.current = this.data[idx];
        this.renderDetail();
        this.renderList();
        this.changed = false;
    },

    renderDetail() {
        const emptyEl = document.getElementById('emptyCityDetail');
        const detailEl = document.getElementById('cityDetailContent');
        if (!this.current) {
            if (emptyEl) emptyEl.style.display = 'flex';
            if (detailEl) detailEl.style.display = 'none';
            return;
        }
        if (emptyEl) emptyEl.style.display = 'none';
        if (detailEl) detailEl.style.display = 'block';
        const fields = ['No','Name','BuildingType','BuildingStyle','Connect00','Connect01','Connect02','Connect03','Connect04','Connect05','Connect06','Connect07','Connect08','Connect09','IsUsed'];
        fields.forEach(k => {
            const el = document.getElementById('ci_' + k);
            if (el) {
                if (el.tagName === 'SELECT') el.value = String(this.current[k] || '');
                else el.value = this.current[k] || '';
            }
        });
    },

    currentChanged() { this.changed = true; },

    saveCurrent() {
        if (!this.current) return;
        ['No','Name','BuildingType','BuildingStyle','Connect00','Connect01','Connect02','Connect03','Connect04','Connect05','Connect06','Connect07','Connect08','Connect09','IsUsed'].forEach(k => {
            const el = document.getElementById('ci_' + k);
            if (el) this.current[k] = el.value;
        });
    },

    async addNew() {
        this.pushUndo();
        const res = await pyApi('newCity');
        if (!res.success) { showToast(res.message || '创建失败', 'error'); return; }
        const entry = res.data || {};
        if (!entry.No) {
            const maxNo = this.data.reduce((max, d) => Math.max(max, parseInt(d.No) || 0), 0);
            entry.No = String(maxNo + 1);
        }
        this.data.push(entry);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        document.getElementById('cityCount').textContent = this.data.length;
    },

    cloneCurrent() {
        this.pushUndo();
        if (!this.current) { showToast('请先选择一个城池', 'warning'); return; }
        const clone = Object.assign({}, this.current);
        const usedIds = new Set(this.data.map(c => parseInt(c.No)));
        let newId = 0;
        for (let i = 1; i < 1000; i++) { if (!usedIds.has(i)) { newId = i; break; } }
        clone.No = newId;
        clone.Name = (clone.Name || '克隆城池') + '_副本';
        this.data.push(clone);
        this.changed = true;
        this.renderList();
        this.select(this.data.length - 1);
        document.getElementById('cityCount').textContent = this.data.length;
    },

    deleteCurrent() {
        this.pushUndo();
        if (!this.current) return;
        if (!confirm(`确认删除城池 "${this.current.Name}"?`)) return;
        const no = parseInt(this.current.No);
        pyApi('deleteIniItem', 'Setting/City.ini', 'CITY', 'No', String(no));
        this.data = this.data.filter(c => parseInt(c.No) !== no);
        this.current = null; this.currentIndex = -1; this.changed = true;
        this.renderList();
        document.getElementById('cityCount').textContent = this.data.length;
        document.getElementById('emptyCityDetail').style.display = 'flex';
        document.getElementById('cityDetailContent').style.display = 'none';
    },

    search(keyword) {
        const container = document.getElementById('cityList');
        if (!container) return;
        container.innerHTML = '';
        const kw = keyword.toLowerCase();
        this.data.forEach((c, idx) => {
            const name = (c.Name || '').toLowerCase();
            const no = String(c.No || '');
            if (!kw || name.includes(kw) || no.includes(kw)) {
                const card = document.createElement('div');
                card.className = 'item-card';
                card.innerHTML = `
                    <div class="item-card-header"><span class="item-name">${c.Name||'无名'}</span><span class="item-no">#${c.No||''}</span></div>
                    <div class="item-desc">${this._getNationName(c.Nation)} | 人口 ${c.Population||0}</div>
                `;
                card.onclick = () => this.select(idx);
                container.appendChild(card);
            }
        });
    },

    renderOverview() {
        const container = document.getElementById('cityOverview');
        if (!container) return;
        if (this.data.length === 0) {
            container.innerHTML = '<p class="hint">请先加载城池数据</p>';
            return;
        }
        const regions = ['中原', '河北', '西凉', '巴蜀', '荆襄', '江东', '南中'];
        // 按区域分组
        const groups = {};
        regions.forEach((r, i) => groups[i] = []);
        this.data.forEach(c => {
            const region = parseInt(c.Region) || 0;
            if (!groups[region]) groups[region] = [];
            groups[region].push(c);
        });
        let html = '';
        regions.forEach((r, i) => {
            if (groups[i].length === 0) return;
            html += `<div style="margin-bottom:12px;"><strong style="color:var(--accent);font-size:13px;">${r}</strong></div><div class="city-overview">`;
            groups[i].forEach(c => {
                const nation = this._getNationName(c.Nation);
                html += `
                    <div class="city-card">
                        <div class="city-card-name">${c.Name || '#'+c.No}</div>
                        <div class="city-card-info">
                            势力: ${nation}<br>
                            人口: ${c.Population||0} | 防御: ${c.Defense||0}<br>
                            产出: 金${c.Gold||0} 粮${c.Food||0} 兵${c.Soldier||0}
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        });
        container.innerHTML = html;
    }
};

// ============================================================
// 批量修改工具
// ============================================================

const batch = {
    currentMode: 'numeric',
    fileSchemas: {},

    switchMode(mode) {
        this.currentMode = mode;
        document.querySelectorAll('.batch-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.batch-panel').forEach(p => { p.style.display = 'none'; });
        const btn = document.querySelector(`.batch-tab-btn[onclick*="${mode}"]`);
        if (btn) btn.classList.add('active');
        const panel = document.getElementById('batch' + mode.charAt(0).toUpperCase() + mode.slice(1));
        if (panel) panel.style.display = 'block';

        if (mode === 'search') this._initSearchScope();
    },

    async loadFiles() {
        const res = await pyApi('getBatchFiles');
        const select = document.getElementById('batchTargetFile');
        if (!select) return;
        select.innerHTML = '<option value="">-- 选择文件 --</option>';
        if (res.success && res.files) {
            this.fileSchemas = res.files;
            Object.keys(res.files).forEach(key => {
                select.innerHTML += `<option value="${key}">${res.files[key].label}</option>`;
            });
        }
    },

    onFileChange() {
        const fileKey = document.getElementById('batchTargetFile').value;
        const fieldSelect = document.getElementById('batchTargetField');
        const filterSelect = document.getElementById('batchFilterField');
        fieldSelect.innerHTML = '<option value="">-- 选择字段 --</option>';
        filterSelect.innerHTML = '<option value="">-- 全部 --</option>';
        if (fileKey && this.fileSchemas[fileKey]) {
            const fields = this.fileSchemas[fileKey].fields || [];
            fields.forEach(f => {
                fieldSelect.innerHTML += `<option value="${f}">${f}</option>`;
                filterSelect.innerHTML += `<option value="${f}">${f}</option>`;
            });
        }
    },

    async preview() {
        const params = this._getNumericParams();
        if (!params) return;
        const res = await pyApi('batchPreview', params);
        this._renderPreview(res, 'batchNumericPreview');
    },

    async execute() {
        const params = this._getNumericParams();
        if (!params) return;
        if (!confirm(`确认对 ${params.file} 的 ${params.field} 执行批量修改？`)) return;
        const res = await pyApi('batchExecute', params);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success && res.preview) this._renderPreview(res, 'batchNumericPreview');
    },

    _getNumericParams() {
        const file = document.getElementById('batchTargetFile').value;
        const field = document.getElementById('batchTargetField').value;
        const op = document.getElementById('batchOpType').value;
        const val = parseInt(document.getElementById('batchOpValue').value);
        const filterField = document.getElementById('batchFilterField').value;
        const filterValue = document.getElementById('batchFilterValue').value;
        if (!file) { showToast('请选择目标文件', 'info'); return null; }
        if (!field) { showToast('请选择目标字段', 'info'); return null; }
        if (isNaN(val)) { showToast('请输入有效数值', 'warning'); return null; }
        return { file, field, op, value: val, filterField: filterField || null, filterValue: filterValue || null };
    },

    _renderPreview(res, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        if (!res.success || !res.preview) {
            container.innerHTML = `<p style="color:var(--text-muted);padding:10px;">${res.message || '无预览数据'}</p>`;
            return;
        }
        const rows = res.preview;
        let html = `<table class="batch-preview-table"><tr><th>编号</th><th>名称</th><th>原值</th><th>新值</th></tr>`;
        rows.forEach(r => {
            const changed = r.oldVal !== r.newVal;
            html += `<tr class="${changed ? 'changed' : ''}">
                <td>${r.id}</td><td>${r.name || ''}</td>
                <td>${r.oldVal}</td>
                <td class="${changed ? 'new-val' : ''}">${r.newVal}</td>
            </tr>`;
        });
        html += '</table>';
        container.innerHTML = html;
    },

    async previewClone() {
        const params = this._getCloneParams();
        if (!params) return;
        const res = await pyApi('batchClonePreview', params);
        const container = document.getElementById('batchClonePreview');
        if (!container) return;
        if (!res.success) {
            container.innerHTML = `<p style="color:var(--danger);padding:10px;">${res.message}</p>`;
            return;
        }
        const list = res.targets || [];
        let html = `<p style="font-size:12px;color:var(--text-secondary);margin-bottom:8px;">将影响 ${list.length} 个武将：</p>`;
        html += `<table class="batch-preview-table"><tr><th>编号</th><th>名称</th><th>当前技能数</th></tr>`;
        list.forEach(t => {
            html += `<tr><td>${t.id}</td><td>${t.name}</td><td>${t.skillCount || 0}</td></tr>`;
        });
        html += '</table>';
        container.innerHTML = html;
    },

    async executeClone() {
        const params = this._getCloneParams();
        if (!params) return;
        if (!confirm(`确认将武将 #${params.source} 的技能复制到 ${params.from}-${params.to} 范围？`)) return;
        const res = await pyApi('batchCloneExecute', params);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
    },

    _getCloneParams() {
        const source = parseInt(document.getElementById('batchCloneSource').value);
        const from = parseInt(document.getElementById('batchCloneFrom').value);
        const to = parseInt(document.getElementById('batchCloneTo').value);
        const type = document.getElementById('batchCloneType').value;
        if (isNaN(source)) { showToast('请输入源武将编号', 'warning'); return null; }
        if (isNaN(from) || isNaN(to)) { showToast('请输入目标武将范围', 'warning'); return null; }
        if (from > to) { showToast('起始编号不能大于结束编号', 'info'); return null; }
        return { source, from, to, type };
    },

    _initSearchScope() {
        const container = document.getElementById('batchSearchScope');
        if (!container || container.children.length > 0) return;
        const files = ['General01.ini', 'Soldier.ini', 'Thing.ini', 'DefSkill.ini',
            'BFMagic.ini', 'SFMagic.ini', 'Formation.ini', 'Title.ini', 'Nation.ini', 'City.ini'];
        files.forEach(f => {
            container.innerHTML += `<label><input type="checkbox" value="${f}" checked> ${f}</label>`;
        });
    },

    async search() {
        const params = this._getSearchParams();
        if (!params) return;
        const res = await pyApi('batchSearch', params);
        this._renderSearchResults(res, 'batchSearchResults');
    },

    async searchReplace() {
        const params = this._getSearchParams();
        if (!params) return;
        if (!params.replace) {
            showToast('请输入替换值', 'warning');
            return;
        }
        if (!confirm(`确认在所有匹配处将 "${params.find}" 替换为 "${params.replace}"？`)) return;
        const res = await pyApi('batchSearchReplace', params);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this._renderSearchResults(res, 'batchSearchResults');
    },

    _getSearchParams() {
        const find = document.getElementById('batchSearchFind').value;
        const replace = document.getElementById('batchSearchReplace').value;
        const isRegex = document.getElementById('batchSearchRegex').checked;
        const caseSensitive = document.getElementById('batchSearchCase').checked;
        const scope = [];
        document.querySelectorAll('#batchSearchScope input:checked').forEach(cb => scope.push(cb.value));
        if (!find) { showToast('请输入查找内容', 'warning'); return null; }
        if (scope.length === 0) { showToast('请选择查找范围', 'info'); return null; }
        return { find, replace, isRegex, caseSensitive, scope };
    },

    _renderSearchResults(res, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        if (!res.success) {
            container.innerHTML = `<p style="color:var(--danger);padding:10px;">${res.message}</p>`;
            return;
        }
        const results = res.results || [];
        if (results.length === 0) {
            container.innerHTML = '<p style="color:var(--text-muted);padding:10px;">未找到匹配项</p>';
            return;
        }
        let html = `<p style="font-size:12px;color:var(--text-secondary);margin-bottom:8px;">找到 ${res.totalMatches || 0} 处匹配，涉及 ${results.length} 个文件</p>`;
        results.forEach(r => {
            html += `<div class="batch-search-result">
                <div class="file-name">${r.file} (${r.matches ? r.matches.length : 0} 处)</div>`;
            (r.matches || []).forEach(m => {
                html += `<div class="match-line">${m}</div>`;
            });
            html += '</div>';
        });
        container.innerHTML = html;
    }
};

// ============================================================
// 差异对比
// ============================================================

const diff = {
    currentData: null,
    diffResult: null,

    async loadBackups() {
        const el = document.getElementById('diffResults');
        if (el) el.innerHTML = '<p class="hint">请先选择对比文件，再选择基准版本进行对比</p>';
        // Try to auto-load file list
        const fileSelect = document.getElementById('diffFile');
        if (fileSelect && fileSelect.value) {
            await this.onFileChange();
        }
    },

    async onFileChange() {
        const file = document.getElementById('diffFile').value;
        const baseSelect = document.getElementById('diffBase');
        baseSelect.innerHTML = '<option value="">-- 选择备份 --</option>';
        if (!file) return;
        const res = await pyApi('getDiffBackups', file);
        if (res.success && res.backups) {
            res.backups.forEach(b => {
                baseSelect.innerHTML += `<option value="${b.id}">${b.time} - ${b.label}</option>`;
            });
        }
    },

    async compare() {
        const file = document.getElementById('diffFile').value;
        const baseId = document.getElementById('diffBase').value;
        if (!file) { showToast('请选择对比文件', 'info'); return; }
        if (!baseId) { showToast('请选择基准版本', 'info'); return; }
        const res = await pyApi('diffCompare', file, baseId);
        this.diffResult = res;
        this._renderStats(res);
        this._renderEntries(res);
    },

    _renderStats(res) {
        const statsEl = document.getElementById('diffStats');
        if (!statsEl) return;
        statsEl.style.display = 'flex';
        const counts = res.counts || { added: 0, modified: 0, deleted: 0, unchanged: 0 };
        document.getElementById('diffAddedCount').textContent = counts.added;
        document.getElementById('diffModifiedCount').textContent = counts.modified;
        document.getElementById('diffDeletedCount').textContent = counts.deleted;
        document.getElementById('diffUnchangedCount').textContent = counts.unchanged;
    },

    _renderEntries(res) {
        const container = document.getElementById('diffResults');
        if (!container) return;
        if (!res.success) {
            container.innerHTML = `<p style="color:var(--danger);padding:10px;">${res.message}</p>`;
            return;
        }
        const entries = res.entries || [];
        if (entries.length === 0) {
            container.innerHTML = '<p style="color:var(--text-muted);padding:10px;">无差异数据</p>';
            return;
        }
        let html = '';
        entries.forEach((e, idx) => {
            const typeLabel = e.type === 'added' ? '新增' : (e.type === 'modified' ? '修改' : (e.type === 'deleted' ? '删除' : '未变更'));
            html += `<div class="diff-entry ${e.type}">
                <div class="diff-entry-header" onclick="diff.toggleEntry(${idx})">
                    <span class="diff-badge ${e.type}">${typeLabel}</span>
                    <span class="diff-entry-name">${e.name || `#${e.id}`}</span>
                    <span style="font-size:11px;color:var(--text-muted);">${e.changes ? e.changes.length + ' 处变更' : ''}</span>
                </div>
                <div class="diff-entry-body" id="diffBody${idx}">`;
            if (e.changes) {
                e.changes.forEach(c => {
                    html += `<div class="diff-field-row">
                        <span class="diff-field-name">${c.field}</span>
                        <span><span class="diff-field-old">${c.oldVal}</span><span class="diff-field-arrow">→</span><span class="diff-field-new">${c.newVal}</span></span>
                    </div>`;
                });
            }
            html += '</div></div>';
        });
        container.innerHTML = html;
    },

    toggleEntry(idx) {
        const body = document.getElementById('diffBody' + idx);
        if (body) body.classList.toggle('open');
    },

    async exportDiff() {
        if (!this.diffResult) {
            showToast('请先执行对比', 'info');
            return;
        }
        const res = await pyApi('diffExport', this.diffResult);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
    }
};

// ============================================================
// 必杀技编辑器
// ============================================================

const superAtkEditor = {
    _data: [],
    _current: null,
    changed: false,
    _searchKeyword: '',

    async load() {
        const res = await pyApi('loadSuperAtk');
        this._data = res.data || [];
        document.getElementById('superAtkCount').textContent = `${this._data.length} 个必杀技`;
        this.renderList();
    },

    search(keyword) {
        this._searchKeyword = keyword || '';
        this.renderList();
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this._data));
    },

    restoreSnapshot(data) {
        this._data = data;
        this._current = null;
        this.renderList();
        this.renderDetail();
    },

    pushUndo() {
        UndoManager.pushState('superatk', this.snapshot());
    },

    renderList() {
        const container = document.getElementById('superAtkList');
        if (!container) return;
        const kw = (this._searchKeyword || '').toLowerCase();
        container.innerHTML = this._data.filter((s, idx) => {
            if (!kw) return true;
            const name = (s.Name || '').toLowerCase();
            const no = String(s.NO || s.No || '');
            return name.includes(kw) || no.includes(kw);
        }).map((s) => {
            const idx = this._data.indexOf(s);
            return `<div class="list-item${this._current === idx ? ' active' : ''}" onclick="superAtkEditor.select(${idx})">
                <span class="item-no">#${s.NO || s.No || ''}</span>
                <span class="item-name">${s.Name || ''}</span>
                <span class="item-sub">概率:${s.HitRatio || 0}%</span>
            </div>`;
        }).join('');
    },

    select(idx) {
        if (idx < 0 || idx >= this._data.length) return;
        this._current = idx;
        this.renderList();
        this.renderDetail();
    },

    renderDetail() {
        const container = document.getElementById('superAtkDetail');
        if (!container || this._current === null) return;
        const s = this._data[this._current];
        container.innerHTML = `
            <div class="detail-content">
                <div class="detail-row"><label>编号</label><input type="number" value="${s.NO || s.No || ''}" onchange="superAtkEditor._set('NO', this.value)"></div>
                <div class="detail-row"><label>名称</label><input type="text" value="${s.Name || ''}" onchange="superAtkEditor._set('Name', this.value)"></div>
                <div class="detail-row"><label>发动概率</label><input type="number" value="${s.HitRatio || 0}" onchange="superAtkEditor._set('HitRatio', this.value)"><span class="hint">单位：%</span></div>
                <h4 style="margin:12px 0 8px;color:var(--accent);">对武将伤害倍率</h4>
                <div class="detail-row"><label>初学</label><input type="number" step="0.01" value="${s.General01 || 0}" onchange="superAtkEditor._set('General01', this.value)"></div>
                <div class="detail-row"><label>进阶</label><input type="number" step="0.01" value="${s.General02 || 0}" onchange="superAtkEditor._set('General02', this.value)"></div>
                <div class="detail-row"><label>精通</label><input type="number" step="0.01" value="${s.General03 || 0}" onchange="superAtkEditor._set('General03', this.value)"></div>
                <h4 style="margin:12px 0 8px;color:var(--accent);">对士兵伤害倍率</h4>
                <div class="detail-row"><label>初学</label><input type="number" step="0.01" value="${s.Soldier01 || 0}" onchange="superAtkEditor._set('Soldier01', this.value)"></div>
                <div class="detail-row"><label>进阶</label><input type="number" step="0.01" value="${s.Soldier02 || 0}" onchange="superAtkEditor._set('Soldier02', this.value)"></div>
                <div class="detail-row"><label>精通</label><input type="number" step="0.01" value="${s.Soldier03 || 0}" onchange="superAtkEditor._set('Soldier03', this.value)"></div>
                <h4 style="margin:12px 0 8px;color:var(--accent);">对设施伤害倍率</h4>
                <div class="detail-row"><label>初学</label><input type="number" step="0.01" value="${s.Special01 || 0}" onchange="superAtkEditor._set('Special01', this.value)"></div>
                <div class="detail-row"><label>进阶</label><input type="number" step="0.01" value="${s.Special02 || 0}" onchange="superAtkEditor._set('Special02', this.value)"></div>
                <div class="detail-row"><label>精通</label><input type="number" step="0.01" value="${s.Special03 || 0}" onchange="superAtkEditor._set('Special03', this.value)"></div>
                <div class="detail-row"><label>启用</label><select onchange="superAtkEditor._set('IsUsed', this.value)"><option value="1" ${(s.IsUsed || 1) == 1 ? 'selected' : ''}>是</option><option value="0" ${(s.IsUsed || 1) == 0 ? 'selected' : ''}>否</option></select></div>
            </div>`;
    },

    _set(key, val) {
        if (this._current !== null) { this._data[this._current][key] = val; this.changed = true; }
    },

    search(q) {
        const filtered = this._data.filter(s => (s.Name || '').includes(q) || String(s.NO || s.No || '').includes(q));
        const container = document.getElementById('superAtkList');
        if (!container) return;
        container.innerHTML = filtered.map((s, idx) =>
            `<div class="list-item" onclick="superAtkEditor.select(${this._data.indexOf(s)})">
                <span class="item-no">#${s.NO || s.No || ''}</span>
                <span class="item-name">${s.Name || ''}</span>
            </div>`
        ).join('');
    },

    async addNew() {
        this.pushUndo();
        const res = await pyApi('newSuperAtk');
        if (res.success && res.data) {
            this._data.push(res.data);
        } else {
            const newEntry = { NO: this._data.length + 1, Name: '新必杀技', HitRatio: 25, General01: 1, General02: 1, IsUsed: 1 };
            this._data.push(newEntry);
        }
        this._current = this._data.length - 1;
        this.renderList();
        this.renderDetail();
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        this.pushUndo();
        const res = await pyApi('saveSuperAtk', this._data);
        if (res.success) this.changed = false;
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
    },

    async deleteCurrent() {
        this.pushUndo();
        if (this._current === null) return;
        const entry = this._data[this._current];
        if (!confirm(`确认删除必杀技 "${entry.Name}" #${entry.NO || entry.No}?`)) return;
        const no = entry.NO || entry.No;
        pyApi('deleteIniItem', 'Setting/SuperAtk.ini', 'SuperAtk', 'No', String(no));
        this._data.splice(this._current, 1);
        this._current = null;
        this.renderList();
        this.renderDetail();
    },

    async cloneCurrent() {
        this.pushUndo();
        if (this._current === null) return;
        const src = this._data[this._current];
        const clone = { ...src };
        clone.NO = this._data.length + 1;
        clone.Name = (src.Name || '克隆') + '_副本';
        this._data.push(clone);
        this._current = this._data.length - 1;
        this.renderList();
        this.renderDetail();
    }
};

// ============================================================
// 特效编辑器
// ============================================================
const effectEditor = {
    _catalogs: null,
    _xref: null,
    _currentTab: 'ball',

    async init() {
        try {
            const r = await pyApi('effectGetAll');
            if (r && r.success) {
                this._catalogs = r;
                this.switchTab(this._currentTab);
            }
        } catch(e) { showToast('加载特效知识库失败', 'error'); }
        // 异步加载交叉引用数据
        this._loadCrossRef();
    },

    async _loadCrossRef() {
        try {
            const r = await pyApi('effectCrossRef');
            if (r && r.success) {
                this._xref = r;
                // 重新渲染当前 tab 以显示引用数据
                if (this._catalogs) this._renderTab(this._currentTab);
            }
        } catch(e) { /* 交叉引用加载失败不影响主功能 */ }
    },

    _getRefCount(tab, id) {
        if (!this._xref || !this._xref.counts) return 0;
        const map = {
            'ball': this._xref.counts.ball,
            'damage': this._xref.counts.damage,
            'atk': this._xref.counts.atk,
            'items': this._xref.counts.script_no,
            'glow': this._xref.counts.bfw_res_id,
        };
        const countMap = map[tab] || {};
        return countMap[String(id)] || 0;
    },

    _getRefTooltip(tab, id) {
        if (!this._xref || !this._xref.refs) return '';
        const map = {
            'ball': this._xref.refs.ball,
            'damage': this._xref.refs.damage,
            'atk': this._xref.refs.atk,
            'items': this._xref.refs.script_no,
            'glow': this._xref.refs.bfw_res_id,
        };
        const refMap = map[tab] || {};
        const names = refMap[String(id)] || [];
        if (names.length === 0) return '暂无引用';
        const disp = names.slice(0, 8);
        let tip = '被以下技能/物品使用:\n' + disp.join('\n');
        if (names.length > 8) tip += `\n... 还有 ${names.length - 8} 个`;
        return tip;
    },

    switchTab(tab) {
        this._currentTab = tab;
        // 更新按钮状态
        document.querySelectorAll('#effTab_ball, #effTab_damage, #effTab_element, #effTab_items, #effTab_glow, #effTab_atk, #effTab_templates').forEach(b => b.classList.remove('active'));
        const btn = document.getElementById('effTab_' + tab);
        if (btn) btn.classList.add('active');
        // 切换面板
        document.querySelectorAll('.eff-panel').forEach(p => p.style.display = 'none');
        const panel = document.getElementById('effPanel_' + tab);
        if (panel) panel.style.display = 'block';
        // 渲染
        this._renderTab(tab);
    },

    _globalSearch() {
        if (!this._catalogs) return;
        this._renderTab(this._currentTab);
    },

    _renderTab(tab) {
        if (!this._catalogs) return;
        switch(tab) {
            case 'ball': this._renderBallTypes(); break;
            case 'damage': this._renderDamageTypes(); break;
            case 'element': this._renderElementTypes(); break;
            case 'items': this._renderItemScripts(); break;
            case 'glow': this._renderWeaponGlow(); break;
            case 'atk': this._renderAtkTypes(); break;
            case 'templates': this._renderTemplates(); break;
        }
    },

    _renderTable(tbodyId, data, columns, tabName) {
        const tbody = document.getElementById(tbodyId);
        if (!tbody) return;
        // 应用全局搜索过滤
        const q = document.getElementById('effGlobalSearch');
        if (q && q.value) {
            const kw = q.value.toLowerCase();
            data = data.filter(item => {
                return (item.name && item.name.toLowerCase().includes(kw)) ||
                       (item.desc && item.desc.toLowerCase().includes(kw)) ||
                       (item.weapon_example && item.weapon_example.toLowerCase().includes(kw));
            });
        }
        let html = '';
        const tab = tabName || this._currentTab;
        if (data.length === 0) {
            html = `<tr><td colspan="${columns.length}" style="text-align:center;padding:24px;color:var(--text-muted);">没有匹配的特效</td></tr>`;
            tbody.innerHTML = html;
            return;
        }
        data.forEach(item => {
            html += '<tr>';
            columns.forEach(col => {
                if (col === 'id') html += `<td style="font-family:monospace;font-weight:600;">${item.id}</td>`;
                else if (col === 'visual') html += `<td style="text-align:center;font-size:20px;color:${item.color||'#fff'};">${item.visual||item.icon||''}</td>`;
                else if (col === 'name') html += `<td><span style="font-weight:600;">${escHtml(item.name)}</span></td>`;
                else if (col === 'desc') html += `<td style="color:var(--text-muted);font-size:13px;">${escHtml(item.desc)}</td>`;
                else if (col === 'weapon') html += `<td style="font-size:12px;color:var(--text-muted);">${escHtml(item.weapon_example||'—')}</td>`;
                else if (col === 'ref') {
                    const cnt = this._getRefCount(tab, item.id);
                    const tip = this._getRefTooltip(tab, item.id);
                    const color = cnt > 0 ? (cnt >= 5 ? 'var(--success)' : 'var(--warning)') : 'var(--text-muted)';
                    const style = cnt > 0 ? 'cursor:pointer;text-decoration:underline;' : 'cursor:help;';
                    html += `<td style="text-align:center;" title="${escHtml(tip)}"><span style="font-weight:600;color:${color};${style}" onclick="effectEditor._showRefDetail('${tab}',${item.id},'${escHtml(item.name)}')">${cnt}</span></td>`;
                }
                else if (col === 'action') {
                    html += `<td style="text-align:center;white-space:nowrap;">`;
                    if (tab === 'ball') html += `<button onclick="effectEditor._copyValue(${item.id},'Ball')" class="btn btn-xs" title="复制弹道编号">📋</button>`;
                    else if (tab === 'damage') html += `<button onclick="effectEditor._copyValue(${item.id},'DamageType')" class="btn btn-xs" title="复制伤害类型编号">📋</button>`;
                    else if (tab === 'element') html += `<button onclick="effectEditor._copyValue(${item.id},'Element')" class="btn btn-xs" title="复制属性编号">📋</button>`;
                    else if (tab === 'items') html += `<button onclick="effectEditor._copyToItemScript('${item.id}')" class="btn btn-xs" title="复制到物品ScriptNo">📋</button>`;
                    else if (tab === 'atk') html += `<button onclick="effectEditor._copyValue(${item.id},'Atk')" class="btn btn-xs" title="复制攻击类型编号">📋</button>`;
                    html += ` <button onclick="effectEditor._openEditModal('${tab}',${item.id})" class="btn btn-xs" title="编辑">✏</button>`;
                    html += ` <button onclick="effectEditor._deleteItem('${tab}',${item.id},'${escHtml(item.name)}')" class="btn btn-xs" title="删除" style="color:var(--danger);">✕</button>`;
                    html += `</td>`;
                }
            });
            html += '</tr>';
        });
        tbody.innerHTML = html;
    },

    _renderBallTypes() {
        const data = this._catalogs.ball_types || [];
        this._renderTable('effBallTable', data, ['id', 'visual', 'name', 'desc', 'ref', 'action'], 'ball');
    },

    _renderDamageTypes() {
        const data = this._catalogs.damage_types || [];
        this._renderTable('effDamageTable', data, ['id', 'visual', 'name', 'desc', 'ref', 'action'], 'damage');
    },

    _renderElementTypes() {
        const data = this._catalogs.element_types || [];
        this._renderTable('effElementTable', data, ['id', 'visual', 'name', 'desc', 'ref', 'action'], 'element');
    },

    _renderItemScripts() {
        const data = this._catalogs.item_scripts || [];
        this._renderTable('effItemScriptsTable', data, ['id', 'name', 'desc', 'weapon', 'ref', 'action'], 'items');
    },

    _renderWeaponGlow() {
        const glow = this._catalogs.weapon_glow || {};
        document.getElementById('effGlowDesc').textContent = glow.desc || '';
        const steps = glow.steps || [];
        document.getElementById('effGlowSteps').innerHTML = steps.map(s => `<div style="padding:3px 0;font-size:13px;">${escHtml(s)}</div>`).join('');
        document.getElementById('effGlowNote').textContent = glow.note || '';
        // 渲染发光编号表格
        const glowIds = this._catalogs.weapon_glow_ids || [];
        this._renderGlowIdTable(glowIds);
    },

    _renderGlowIdTable(glowIds) {
        const tbody = document.getElementById('effGlowIdTable');
        if (!tbody) return;
        let html = '';
        glowIds.forEach(g => {
            const cnt = this._getRefCount('glow', g.id);
            const tip = this._getRefTooltip('glow', g.id);
            const refColor = cnt > 0 ? (cnt >= 5 ? 'var(--success)' : 'var(--warning)') : 'var(--text-muted)';
            const refStyle = cnt > 0 ? 'cursor:pointer;text-decoration:underline;' : 'cursor:help;';
            html += `<tr>
                <td style="font-family:monospace;font-weight:600;">${g.id}</td>
                <td><span style="display:inline-block;width:16px;height:16px;border-radius:50%;background:${g.color};border:1px solid var(--border);" title="${g.name}"></span></td>
                <td><span style="font-weight:600;">${escHtml(g.name)}</span></td>
                <td style="font-size:13px;color:var(--text-muted);">${escHtml(g.desc)}</td>
                <td style="font-size:12px;color:var(--text-muted);">${escHtml(g.example)}</td>
                <td style="text-align:center;" title="${escHtml(tip)}"><span style="font-weight:600;color:${refColor};${refStyle}" onclick="effectEditor._showRefDetail('glow',${g.id},'${escHtml(g.name)}')">${cnt}</span></td>
                <td><button onclick="effectEditor._copyGlowId(${g.id})" class="btn btn-xs" title="复制发光编号">📋 BFWResID=${g.id}</button>
                <button onclick="effectEditor._openEditModal('glow',${g.id})" class="btn btn-xs" title="编辑">✏</button>
                <button onclick="effectEditor._deleteItem('glow',${g.id},'${escHtml(g.name)}')" class="btn btn-xs" title="删除" style="color:var(--danger);">✕</button></td>
            </tr>`;
        });
        tbody.innerHTML = html;
    },

    _filterGlow() {
        const q = document.getElementById('effGlowSearch').value.toLowerCase();
        const glowIds = this._catalogs.weapon_glow_ids || [];
        const filtered = q ? glowIds.filter(g => g.name.toLowerCase().includes(q) || g.desc.toLowerCase().includes(q) || g.example.toLowerCase().includes(q)) : glowIds;
        this._renderGlowIdTable(filtered);
    },

    _copyGlowId(id) {
        navigator.clipboard.writeText(String(id)).then(() => {
            this._showToast(`BFWResID=${id} 已复制到剪贴板，可粘贴到物品编辑器的 BFWResID 字段`);
        }).catch(() => {});
    },

    _renderAtkTypes() {
        const data = this._catalogs.atk_types || [];
        this._renderTable('effAtkTable', data, ['id', 'visual', 'name', 'desc', 'ref', 'action'], 'atk');
    },

    _copyValue(value, fieldName) {
        navigator.clipboard.writeText(String(value)).then(() => {
            this._showToast(`${fieldName}=${value} 已复制到剪贴板`);
        }).catch(() => {
            this._showToast(`值: ${value} (${fieldName})`);
        });
    },

    _copyToItemScript(scriptNo) {
        navigator.clipboard.writeText(String(scriptNo)).then(() => {
            this._showToast(`ScriptNo=${scriptNo} 已复制，可粘贴到物品编辑器的 ScriptNo 字段`);
        }).catch(() => {});
    },

    _showRefDetail(tab, id, name) {
        if (!this._xref || !this._xref.refs) return;
        const map = {
            'ball': [this._xref.refs.ball, '弹道类型', '武将技'],
            'damage': [this._xref.refs.damage, '伤害类型', '武将技'],
            'atk': [this._xref.refs.atk, '攻击类型', '武将技'],
            'items': [this._xref.refs.script_no, '物品特效', '武器'],
            'glow': [this._xref.refs.bfw_res_id, '武器发光', '武器'],
        };
        const [refMap, catLabel, entityLabel] = map[tab] || [{}, '', ''];
        const names = refMap[String(id)] || [];
        const panel = document.getElementById('effRefDetail');
        document.getElementById('effRefDetailTitle').textContent = `${name} — 被 ${names.length} 个${entityLabel}引用`;
        let html = '';
        if (names.length === 0) {
            html = '<div style="text-align:center;padding:20px;color:var(--text-muted);">暂无引用</div>';
        } else {
            html = '<div style="display:flex;flex-wrap:wrap;gap:6px;">';
            names.forEach(n => {
                html += `<span style="background:var(--bg-hover);padding:4px 10px;border-radius:4px;font-size:13px;border:1px solid var(--border);">${escHtml(n)}</span>`;
            });
            html += '</div>';
            html += `<div style="margin-top:10px;font-size:12px;color:var(--text-muted);">提示：点击导航栏「技能编辑」或「物品编辑」可直接修改这些${entityLabel}的${catLabel}字段</div>`;
        }
        document.getElementById('effRefDetailList').innerHTML = html;
        panel.style.display = 'block';
        panel.scrollIntoView({behavior:'smooth'});
    },

    _closeRefDetail() {
        document.getElementById('effRefDetail').style.display = 'none';
    },

    // ============================================================
    // CRUD 操作 — 编辑/删除特效条目
    // ============================================================
    _editType: null,
    _editItemId: null,
    _editItem: null,

    _openEditModal(type, itemId) {
        this._editType = type;
        this._editItemId = itemId;
        this._editItem = null;

        if (itemId !== undefined && itemId !== null) {
            // 编辑模式：查找现有数据
            const data = this._getDataByType(type);
            const item = data.find(d => d.id === itemId);
            if (item) this._editItem = JSON.parse(JSON.stringify(item)); // 深拷贝
        }

        const title = document.getElementById('effEditModalTitle');
        const form = document.getElementById('effEditForm');
        const isNew = !this._editItem;

        title.textContent = isNew ? `添加${this._getTypeLabel(type)}` : `编辑${this._getTypeLabel(type)}`;

        let html = '';
        if (type === 'templates') {
            html = this._buildTemplateForm(isNew);
        } else {
            html = this._buildStandardForm(type, isNew);
        }

        form.innerHTML = html;
        document.getElementById('effEditModal').style.display = 'flex';
    },

    _getTypeLabel(type) {
        const labels = {ball:'弹道类型', damage:'伤害类型', element:'属性类型', items:'物品特效', glow:'发光编号', atk:'攻击类型', templates:'模板'};
        return labels[type] || type;
    },

    _getDataByType(type) {
        if (!this._catalogs) return [];
        const map = {ball:'ball_types', damage:'damage_types', element:'element_types', items:'item_scripts', glow:'weapon_glow_ids', atk:'atk_types', templates:'templates'};
        return this._catalogs[map[type]] || [];
    },

    _buildStandardForm(type, isNew) {
        const item = this._editItem || {};
        const isGlow = type === 'glow';
        const isItems = type === 'items';
        const hasVisual = type === 'ball' || type === 'element' || type === 'atk';
        const hasIcon = type === 'damage';
        let html = '';

        // ID 字段
        if (isNew) {
            if (type === 'templates') {
                html += `<div class="form-group"><label>模板 ID (英文)</label><input type="text" id="effEdit_id" value="" placeholder="如: fire_ultimate"></div>`;
            } else {
                // 自动建议下一个 ID
                const data = this._getDataByType(type);
                const maxId = data.reduce((max, d) => Math.max(max, d.id || 0), -1);
                html += `<div class="form-group"><label>编号</label><input type="number" id="effEdit_id" value="${maxId + 1}" min="0"></div>`;
            }
        } else {
            html += `<div class="form-group"><label>编号</label><input type="number" id="effEdit_id" value="${item.id || 0}" readonly style="opacity:0.6;"></div>`;
        }

        // 名称
        html += `<div class="form-group"><label>名称</label><input type="text" id="effEdit_name" value="${escHtml(item.name || '')}"></div>`;

        // 描述
        html += `<div class="form-group"><label>描述</label><input type="text" id="effEdit_desc" value="${escHtml(item.desc || '')}"></div>`;

        // 图标/视觉符号
        if (hasVisual) {
            html += `<div class="form-group"><label>视觉符号 (visual)</label><input type="text" id="effEdit_visual" value="${escHtml(item.visual || '')}" placeholder="如: ● → ⚡"></div>`;
        }
        if (hasIcon) {
            html += `<div class="form-group"><label>图标 (icon)</label><input type="text" id="effEdit_icon" value="${escHtml(item.icon || '')}" placeholder="如: 🔥 💧 ⚡"></div>`;
        }

        // 颜色
        if (hasVisual || hasIcon || isGlow) {
            html += `<div class="form-group"><label>颜色 (color)</label><div style="display:flex;gap:8px;align-items:center;"><input type="color" id="effEdit_color" value="${item.color || '#888888'}" style="width:40px;height:32px;padding:0;border:none;cursor:pointer;"><input type="text" id="effEdit_colorText" value="${escHtml(item.color || '#888')}" style="flex:1;" placeholder="#ff4444"></div></div>`;
        }

        // 示例武器 (items)
        if (isItems) {
            html += `<div class="form-group"><label>示例武器 (weapon_example)</label><input type="text" id="effEdit_weapon" value="${escHtml(item.weapon_example || '')}"></div>`;
        }

        // 示例武器 (glow)
        if (isGlow) {
            html += `<div class="form-group"><label>示例武器 (example)</label><input type="text" id="effEdit_example" value="${escHtml(item.example || '')}"></div>`;
        }

        return html;
    },

    _buildTemplateForm(isNew) {
        const item = this._editItem || {};
        const p = item.params || {};
        let html = '';

        if (isNew) {
            html += `<div class="form-group"><label>模板 ID (英文)</label><input type="text" id="effEdit_id" value="" placeholder="如: fire_ultimate"></div>`;
        } else {
            html += `<div class="form-group"><label>模板 ID</label><input type="text" id="effEdit_id" value="${escHtml(item.id || '')}" readonly style="opacity:0.6;"></div>`;
        }

        html += `<div class="form-group"><label>名称</label><input type="text" id="effEdit_name" value="${escHtml(item.name || '')}"></div>`;
        html += `<div class="form-group"><label>描述</label><input type="text" id="effEdit_desc" value="${escHtml(item.desc || '')}"></div>`;
        html += `<div class="form-group"><label>参考技能 (example)</label><input type="text" id="effEdit_example" value="${escHtml(item.example || '')}"></div>`;

        // 标签
        const tags = (item.tags || []).join(',');
        html += `<div class="form-group"><label>标签 (逗号分隔)</label><input type="text" id="effEdit_tags" value="${escHtml(tags)}" placeholder="火系,单体,入门"></div>`;

        // 参数
        html += `<div style="background:var(--bg-hover);padding:10px;border-radius:6px;margin-top:8px;"><span style="font-weight:600;font-size:13px;">参数组合</span>`;
        html += `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px;">`;
        html += `<div class="form-group"><label>Ball</label><input type="number" id="effEdit_pBall" value="${p.Ball || 0}" min="0"></div>`;
        html += `<div class="form-group"><label>DamageType</label><input type="number" id="effEdit_pDamageType" value="${p.DamageType || 0}" min="0"></div>`;
        html += `<div class="form-group"><label>Element</label><input type="number" id="effEdit_pElement" value="${p.Element || 0}" min="0"></div>`;
        html += `<div class="form-group"><label>Atk</label><input type="number" id="effEdit_pAtk" value="${p.Atk || 0}" min="0"></div>`;
        html += `<div class="form-group"><label>MP</label><input type="number" id="effEdit_pMP" value="${p.MP || 0}" min="0"></div>`;
        html += `<div class="form-group"><label>ATK</label><input type="number" id="effEdit_pATK" value="${p.ATK || 0}" min="0"></div>`;
        html += `<div class="form-group"><label>Level</label><input type="number" id="effEdit_pLevel" value="${p.Level || 1}" min="0"></div>`;
        html += `<div class="form-group"><label>Range</label><input type="number" id="effEdit_pRange" value="${p.Range || 1}" min="0"></div>`;
        html += `<div class="form-group"><label>Target</label><input type="number" id="effEdit_pTarget" value="${p.Target || 0}" min="0"></div>`;
        html += `<div class="form-group"><label>Damage</label><input type="number" id="effEdit_pDamage" value="${p.Damage || 1.0}" step="0.1" min="0"></div>`;
        html += `</div></div>`;

        return html;
    },

    _closeEditModal() {
        document.getElementById('effEditModal').style.display = 'none';
        this._editType = null;
        this._editItemId = null;
        this._editItem = null;
    },

    async _saveEditItem() {
        const type = this._editType;
        const isNew = !this._editItem;
        const isTemplate = type === 'templates';

        const getVal = (id, def) => { const el = document.getElementById(id); return el ? el.value : def; };

        let itemData = {};

        if (isTemplate) {
            itemData = {
                id: getVal('effEdit_id', ''),
                name: getVal('effEdit_name', ''),
                desc: getVal('effEdit_desc', ''),
                example: getVal('effEdit_example', ''),
                tags: getVal('effEdit_tags', '').split(',').map(t => t.trim()).filter(Boolean),
                params: {
                    Ball: parseInt(getVal('effEdit_pBall', '0')) || 0,
                    DamageType: parseInt(getVal('effEdit_pDamageType', '0')) || 0,
                    Element: parseInt(getVal('effEdit_pElement', '0')) || 0,
                    Atk: parseInt(getVal('effEdit_pAtk', '0')) || 0,
                    MP: parseInt(getVal('effEdit_pMP', '0')) || 0,
                    ATK: parseInt(getVal('effEdit_pATK', '0')) || 0,
                    Level: parseInt(getVal('effEdit_pLevel', '1')) || 1,
                    Range: parseInt(getVal('effEdit_pRange', '1')) || 1,
                    Target: parseInt(getVal('effEdit_pTarget', '0')) || 0,
                    Damage: parseFloat(getVal('effEdit_pDamage', '1.0')) || 1.0,
                },
            };
        } else {
            const isGlow = type === 'glow';
            const isItems = type === 'items';
            const hasVisual = type === 'ball' || type === 'element' || type === 'atk';
            const hasIcon = type === 'damage';

            itemData = {
                id: isNew ? parseInt(getVal('effEdit_id', '0')) : this._editItemId,
                name: getVal('effEdit_name', ''),
                desc: getVal('effEdit_desc', ''),
            };

            if (hasVisual) itemData.visual = getVal('effEdit_visual', '');
            if (hasIcon) itemData.icon = getVal('effEdit_icon', '');
            if (isGlow) itemData.example = getVal('effEdit_example', '');
            if (isItems) itemData.weapon_example = getVal('effEdit_weapon', '');

            // 颜色处理
            const colorEl = document.getElementById('effEdit_color');
            const colorText = document.getElementById('effEdit_colorText');
            if (colorEl) itemData.color = colorText ? colorText.value : colorEl.value;
        }

        try {
            const oldId = isNew ? null : this._editItemId;
            const r = await pyApi('effectSaveType', {catalog_type: type, item_data: itemData, item_id: oldId});
            if (r && r.success) {
                this._showToast(r.message);
                this._closeEditModal();
                // 重新加载
                await this.init();
            } else {
                this._showToast((r && r.message) || '保存失败', 'error');
            }
        } catch (e) {
            this._showToast('保存失败: ' + e.message, 'error');
        }
    },

    async _deleteItem(type, itemId, name) {
        if (!confirm(`确定要删除 "${name}" (id=${itemId}) 吗？\n\n此操作不可撤销，会直接从知识库中移除该条目。`)) return;
        try {
            const r = await pyApi('effectDeleteType', {catalog_type: type, item_id: itemId});
            if (r && r.success) {
                this._showToast(r.message);
                await this.init();
            } else {
                this._showToast((r && r.message) || '删除失败', 'error');
            }
        } catch (e) {
            this._showToast('删除失败: ' + e.message, 'error');
        }
    },

    // ============================================================
    // 导出/导入 JSON
    // ============================================================
    async _exportJson() {
        try {
            const r = await pyApi('effectExportJson');
            if (r && r.success && r.json) {
                // 触发下载
                const blob = new Blob([r.json], {type: 'application/json'});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                const now = new Date();
                const ts = now.getFullYear() + ('0'+(now.getMonth()+1)).slice(-2) + ('0'+now.getDate()).slice(-2) + '_' +
                           ('0'+now.getHours()).slice(-2) + ('0'+now.getMinutes()).slice(-2);
                a.download = `effect_catalog_${ts}.json`;
                a.click();
                URL.revokeObjectURL(url);
                this._showToast('特效知识库 JSON 已导出');
            } else {
                this._showToast('导出失败', 'error');
            }
        } catch (e) {
            this._showToast('导出失败: ' + e.message, 'error');
        }
    },

    _importJson() {
        // 创建隐藏的 file input
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            try {
                const text = await file.text();
                // 询问合并还是替换
                const mode = confirm('点击"确定"=合并模式（新数据覆盖同ID条目，保留其他数据）\n点击"取消"=替换模式（完全替换对应类型的数据）');
                const r = await pyApi('effectImportJson', {json_str: text, merge: mode});
                if (r && r.success) {
                    this._showToast(`导入成功: ${JSON.stringify(r.imported)}`);
                    await this.init();
                } else {
                    this._showToast((r && r.message) || '导入失败', 'error');
                }
            } catch (err) {
                this._showToast('导入失败: ' + err.message, 'error');
            }
        };
        input.click();
    },

    _showToast(msg, type) {
        let toast = document.getElementById('effToast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'effToast';
            toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--bg-card);color:#fff;padding:8px 20px;border-radius:6px;border:1px solid var(--border);font-size:13px;z-index:10000;pointer-events:none;transition:opacity 0.3s;';
            document.body.appendChild(toast);
        }
        if (type === 'error') {
            toast.style.background = '#ff444422';
            toast.style.borderColor = '#ff4444';
            toast.style.color = '#ff4444';
        } else {
            toast.style.background = 'var(--bg-card)';
            toast.style.borderColor = 'var(--border)';
            toast.style.color = '#fff';
        }
        toast.textContent = msg;
        toast.style.opacity = '1';
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => { toast.style.opacity = '0'; }, 2500);
    },

    _navigateTo(tab) {
        const navItem = document.querySelector(`[data-tab="${tab}"]`);
        if (navItem) navItem.click();
    },

    // ============================================================
    // 特效模板/预设
    // ============================================================
    _templateFilter: 'all',

    _renderTemplates() {
        const templates = (this._catalogs && this._catalogs.templates) ? this._catalogs.templates : [];
        const grid = document.getElementById('effTplGrid');
        if (!grid) return;
        if (templates.length === 0) {
            grid.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);grid-column:1/-1;">暂无模板数据</div>';
            return;
        }
        // 过滤
        let filtered = templates;
        if (this._templateFilter && this._templateFilter !== 'all') {
            filtered = templates.filter(t => t.tags && t.tags.includes(this._templateFilter));
        }
        if (filtered.length === 0) {
            grid.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);grid-column:1/-1;">没有匹配此标签的模板</div>';
            return;
        }
        let html = '';
        filtered.forEach(tpl => {
            const tagHtml = (tpl.tags || []).map(tag => {
                const colors = {
                    '火系': '#ff6644', '冰系': '#66aaff', '雷系': '#ffcc00', '风系': '#66cc66',
                    '毒系': '#aa66ff', '物理': '#ccaa66', '辅助': '#ff88aa',
                    '单体': '#88ccff', '群体': '#ffaa44', '全体': '#ff4444',
                    '持续': '#cc88ff', '贯穿': '#ffcc44', '追踪': '#44ddcc',
                    '召唤': '#aa88cc', '恢复': '#66dd66',
                    '入门': '#66cc66', '中级': '#ffaa22', '高级': '#ff4444',
                };
                const c = colors[tag] || '#888';
                return `<span style="display:inline-block;padding:1px 6px;border-radius:3px;font-size:11px;background:${c}22;color:${c};border:1px solid ${c}44;margin-right:3px;">${tag}</span>`;
            }).join('');
            // 参数摘要
            const p = tpl.params || {};
            const paramSummary = [];
            if (p.MP) paramSummary.push(`MP:${p.MP}`);
            if (p.ATK) paramSummary.push(`ATK:${p.ATK}`);
            if (p.Level) paramSummary.push(`Lv:${p.Level}`);
            if (p.Damage) paramSummary.push(`伤害:x${p.Damage}`);
            html += `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:14px;transition:border-color 0.2s;cursor:pointer;" onmouseenter="this.style.borderColor='var(--primary)'" onmouseleave="this.style.borderColor='var(--border)'">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
                    <div>
                        <span style="font-weight:600;font-size:15px;">${escHtml(tpl.name)}</span>
                        <span style="font-size:11px;color:var(--text-muted);margin-left:6px;">参考: ${escHtml(tpl.example)}</span>
                    </div>
                </div>
                <div style="font-size:13px;color:var(--text-muted);margin-bottom:8px;">${escHtml(tpl.desc)}</div>
                <div style="margin-bottom:8px;">${tagHtml}</div>
                <div style="font-size:12px;color:var(--text-muted);margin-bottom:10px;background:var(--bg-hover);padding:6px 8px;border-radius:4px;font-family:monospace;">${paramSummary.join(' | ') || '辅助类技能'}</div>
                <div style="display:flex;gap:8px;">
                    <button onclick="effectEditor._openQuickCreate('${tpl.id}')" class="btn btn-primary btn-sm" title="在当前页面调整参数并创建">📝 快速创建</button>
                    <button onclick="effectEditor._applyTemplateToSkill('${tpl.id}')" class="btn btn-outline btn-sm" title="跳转到技能编辑器">📋 跳转编辑</button>
                    <button onclick="effectEditor._openEditModal('templates','${tpl.id}')" class="btn btn-xs" title="编辑模板" style="margin-left:auto;">✏</button>
                    <button onclick="effectEditor._deleteItem('templates','${tpl.id}','${escHtml(tpl.name)}')" class="btn btn-xs" title="删除模板" style="color:var(--danger);">✕</button>
                </div>
            </div>`;
        });
        grid.innerHTML = html;
    },

    _filterTemplates(tag) {
        this._templateFilter = tag;
        // 更新标签按钮状态
        document.querySelectorAll('[id^="effTplTag_"]').forEach(b => b.classList.remove('active'));
        const btn = document.getElementById('effTplTag_' + tag);
        if (btn) btn.classList.add('active');
        this._renderTemplates();
    },

    _applyTemplateToSkill(tplId) {
        const templates = (this._catalogs && this._catalogs.templates) ? this._catalogs.templates : [];
        const tpl = templates.find(t => t.id === tplId);
        if (!tpl) return;
        this._showToast('正在跳转到技能编辑器...');
        // 跳转到技能编辑器
        const navItem = document.querySelector('[data-tab="skills"]');
        if (navItem) {
            navItem.click();
            // 延迟填入模板参数
            setTimeout(() => {
                if (typeof skillEditor !== 'undefined' && skillEditor.applyTemplate) {
                    skillEditor.applyTemplate(tpl);
                } else {
                    // 如果 skillEditor 没有 applyTemplate 方法，复制到剪贴板
                    this._copyTemplateToClipboard(tpl);
                }
            }, 600);
        } else {
            this._copyTemplateToClipboard(tpl);
        }
    },

    _copyTemplateParams(tplId) {
        const templates = (this._catalogs && this._catalogs.templates) ? this._catalogs.templates : [];
        const tpl = templates.find(t => t.id === tplId);
        if (!tpl) return;
        this._copyTemplateToClipboard(tpl);
    },

    _copyTemplateToClipboard(tpl) {
        const p = tpl.params || {};
        // 生成 INI 格式文本
        let text = `; ${tpl.name}\n; ${tpl.desc}\n`;
        text += `; 参考技能: ${tpl.example}\n`;
        text += `[SKILL]\n`;
        text += `Name = ${tpl.example}\n`;
        for (const [k, v] of Object.entries(p)) {
            text += `${k} = ${v}\n`;
        }
        text += `\n; 粘贴到 BFMagic.ini 或技能编辑器中即可`;
        navigator.clipboard.writeText(text).then(() => {
            this._showToast(`模板 "${tpl.name}" 参数已复制到剪贴板\n可在技能编辑器中粘贴使用`);
        }).catch(() => {
            this._showToast(`模板参数已生成，请手动复制`);
        });
    },

    // ============================================================
    // 快速创建技能 — 现场内特效制作
    // ============================================================
    _openQuickCreate(tplId) {
        const templates = (this._catalogs && this._catalogs.templates) ? this._catalogs.templates : [];
        const tpl = templates.find(t => t.id === tplId);
        if (!tpl) return;
        const p = tpl.params || {};
        // 填入表单
        document.getElementById('qc_Name').value = tpl.example || '';
        document.getElementById('qc_Ball').value = p.Ball || 0;
        document.getElementById('qc_DamageType').value = p.DamageType || 0;
        document.getElementById('qc_Element').value = p.Element || 0;
        document.getElementById('qc_Atk').value = p.Atk || 0;
        document.getElementById('qc_MP').value = p.MP || 0;
        document.getElementById('qc_ATK').value = p.ATK || 0;
        document.getElementById('qc_Level').value = p.Level || 1;
        document.getElementById('qc_Range').value = p.Range || 1;
        document.getElementById('qc_Target').value = p.Target || 0;
        document.getElementById('qc_Damage').value = p.Damage || 1.0;
        document.getElementById('qc_Effect').value = p.Effect || 0;
        // 显示面板
        const panel = document.getElementById('effQuickCreate');
        panel.style.display = 'block';
        panel.scrollIntoView({behavior:'smooth'});
        this._qcUpdateVisual();
        this._showToast(`模板 "${tpl.name}" 已加载，调整参数后点击保存`);
    },

    _qcUpdateVisual() {
        const visual = document.getElementById('effQcVisual');
        if (!visual) return;
        const ball = parseInt(document.getElementById('qc_Ball')?.value) || 0;
        const dmg = parseInt(document.getElementById('qc_DamageType')?.value) || 0;
        const elem = parseInt(document.getElementById('qc_Element')?.value) || 0;
        const atk = parseInt(document.getElementById('qc_Atk')?.value) || 0;
        const range = parseInt(document.getElementById('qc_Range')?.value) || 1;
        const target = parseInt(document.getElementById('qc_Target')?.value) || 0;
        const damage = parseFloat(document.getElementById('qc_Damage')?.value) || 1.0;

        // 弹道可视化
        const ballVisuals = {
            0: {icon: '●', label: '无弹道', color: '#888'},
            1: {icon: '→', label: '直射', color: '#ff4444'},
            2: {icon: '⌒', label: '弧形', color: '#ff8800'},
            3: {icon: '⋘', label: '散射', color: '#44aaff'},
            4: {icon: '↷', label: '追踪', color: '#ff44ff'},
            5: {icon: '⚡', label: '落雷', color: '#ffff00'},
            6: {icon: '≈', label: '冲击', color: '#aa8844'},
            7: {icon: '◎', label: '旋转', color: '#ff6644'},
            8: {icon: '◆', label: '召唤', color: '#8844ff'},
            9: {icon: '━', label: '光束', color: '#44ffff'},
            10: {icon: '✱', label: '爆炸', color: '#ff0000'},
            11: {icon: '⇨', label: '穿透', color: '#ffaa00'},
            12: {icon: '❄', label: '冰锥', color: '#88ccff'},
            13: {icon: '🌀', label: '旋风', color: '#aaffaa'},
            14: {icon: '☠', label: '毒雾', color: '#88ff44'},
            15: {icon: '✚', label: '治疗', color: '#44ff44'},
        };
        const bv = ballVisuals[ball] || ballVisuals[0];

        // 伤害类型颜色
        const dmgColors = ['#ccc','#ff4444','#4488ff','#44ff44','#ffdd00','#aa44ff','#ff0000','#ff8800','#44ff88'];
        const dmgColor = dmgColors[dmg] || '#ccc';

        // 属性颜色
        const elemColors = ['#888','#ff4444','#4488ff','#44ff44','#ffdd00','#aa44ff'];
        const elemColor = elemColors[elem] || '#888';

        // 目标类型
        const targetLabels = ['敌方单体', '敌方全体', '我方单体', '我方全体'];
        const targetLabel = targetLabels[target] || '敌方单体';

        // 攻击类型
        const atkLabels = ['单体', '群体', '全军', '持续', '治疗', '增益', '减益', '召唤', '控制'];
        const atkLabel = atkLabels[atk] || '单体';

        // 范围可视化 — 用同心圆表示
        const rangeCircles = [];
        const maxRange = Math.min(range, 5);
        for (let i = 1; i <= maxRange; i++) {
            const size = 16 + i * 10;
            const opacity = 1 - (i - 1) * 0.15;
            rangeCircles.push(`<div style="position:absolute;width:${size}px;height:${size}px;border-radius:50%;border:1px solid var(--primary);opacity:${opacity};top:50%;left:50%;transform:translate(-50%,-50%);"></div>`);
        }

        visual.innerHTML = `
            <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap;">
                <div style="text-align:center;min-width:80px;">
                    <div style="font-size:36px;color:${bv.color};line-height:1;">${bv.icon}</div>
                    <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">弹道: ${bv.label}</div>
                </div>
                <div style="display:flex;flex-direction:column;gap:6px;font-size:12px;">
                    <div style="display:flex;align-items:center;gap:6px;">
                        <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${dmgColor};"></span>
                        <span style="color:var(--text-muted);">伤害类型:</span><span style="font-weight:600;">${dmgColor}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:6px;">
                        <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${elemColor};"></span>
                        <span style="color:var(--text-muted);">属性:</span><span style="font-weight:600;">${elemColor}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:6px;">
                        <span style="color:var(--text-muted);">攻击类型:</span><span style="font-weight:600;">${atkLabel}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:6px;">
                        <span style="color:var(--text-muted);">目标:</span><span style="font-weight:600;">${targetLabel}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:6px;">
                        <span style="color:var(--text-muted);">伤害倍率:</span><span style="font-weight:600;color:var(--warning);">x${damage}</span>
                    </div>
                </div>
                <div style="position:relative;width:80px;height:80px;min-width:80px;">
                    <div style="position:absolute;width:8px;height:8px;border-radius:50%;background:var(--primary);top:50%;left:50%;transform:translate(-50%,-50%);z-index:2;"></div>
                    ${rangeCircles.join('')}
                </div>
                <div style="font-size:11px;color:var(--text-muted);text-align:center;">
                    <div>范围</div><div style="font-weight:600;font-size:16px;color:var(--primary);">${range}</div>
                </div>
            </div>
        `;
    },

    _quickCreateSave() {
        const name = document.getElementById('qc_Name').value.trim();
        if (!name) { this._showToast('请输入技能名称'); return; }
        const params = {
            Name: name,
            Ball: parseInt(document.getElementById('qc_Ball').value) || 0,
            DamageType: parseInt(document.getElementById('qc_DamageType').value) || 0,
            Element: parseInt(document.getElementById('qc_Element').value) || 0,
            Atk: parseInt(document.getElementById('qc_Atk').value) || 0,
            MP: parseInt(document.getElementById('qc_MP').value) || 0,
            ATK: parseInt(document.getElementById('qc_ATK').value) || 0,
            Level: parseInt(document.getElementById('qc_Level').value) || 1,
            Range: parseInt(document.getElementById('qc_Range').value) || 1,
            Target: parseInt(document.getElementById('qc_Target').value) || 0,
            Damage: parseFloat(document.getElementById('qc_Damage').value) || 1.0,
            Effect: parseInt(document.getElementById('qc_Effect').value) || 0,
        };
        // 构造模板对象传给 skillEditor
        const tpl = {
            id: 'qc_' + Date.now(),
            name: '自定义: ' + name,
            desc: '现场制作',
            example: name,
            params: params,
            tags: ['自定义'],
        };
        if (typeof skillEditor !== 'undefined' && skillEditor.applyTemplate) {
            skillEditor.applyTemplate(tpl);
            this._showToast(`技能 "${name}" 已创建并添加到技能列表`);
            // 切换到技能编辑器查看
            setTimeout(() => {
                const navItem = document.querySelector('[data-tab="skills"]');
                if (navItem) navItem.click();
            }, 300);
        } else {
            this._copyTemplateToClipboard(tpl);
            this._showToast('技能编辑器未加载，参数已复制到剪贴板');
        }
    },

    _quickCreateReset() {
        document.getElementById('qc_Name').value = '';
        ['qc_Ball','qc_DamageType','qc_Element','qc_Atk'].forEach(id => document.getElementById(id).value = '0');
        document.getElementById('qc_MP').value = '50';
        document.getElementById('qc_ATK').value = '120';
        document.getElementById('qc_Level').value = '5';
        document.getElementById('qc_Range').value = '1';
        document.getElementById('qc_Target').value = '0';
        document.getElementById('qc_Damage').value = '1.2';
        document.getElementById('qc_Effect').value = '0';
        this._qcUpdateVisual();
        this._showToast('已重置为默认值');
    },

    // ============================================================
    // 智能推荐 — 基于当前参数推荐最优 Ball+DamageType+Element+Atk 组合
    // ============================================================
    _RECOMMENDED_COMBOS: [
        {name:'🔥 火系单体爆发', ball:2, dmg:1, elem:1, atk:0, mp:45, atkVal:150, level:5, range:1, target:0, damage:1.5, desc:'高伤害火系单体，适合前期武将'},
        {name:'🔥 火系群体AOE', ball:10, dmg:1, elem:1, atk:1, mp:85, atkVal:220, level:15, range:3, target:1, damage:1.6, desc:'大范围爆炸，清兵利器'},
        {name:'❄ 冰系控制', ball:12, dmg:2, elem:2, atk:0, mp:50, atkVal:130, level:8, range:1, target:0, damage:1.3, desc:'冰锥减速，单体控制'},
        {name:'❄ 冰系范围冻结', ball:5, dmg:2, elem:2, atk:1, mp:90, atkVal:180, level:14, range:3, target:1, damage:1.4, desc:'天降冰锥，范围冻结'},
        {name:'⚡ 雷系全屏', ball:5, dmg:4, elem:4, atk:2, mp:100, atkVal:250, level:20, range:5, target:1, damage:1.8, desc:'全屏落雷，全军覆没'},
        {name:'⚡ 雷系激光', ball:9, dmg:4, elem:4, atk:0, mp:95, atkVal:300, level:25, range:1, target:0, damage:2.5, desc:'高能光束，单体秒杀'},
        {name:'🌀 风系范围', ball:13, dmg:3, elem:3, atk:1, mp:70, atkVal:160, level:12, range:2, target:1, damage:1.4, desc:'旋风席卷，范围打击'},
        {name:'☠ 毒系持续', ball:14, dmg:5, elem:5, atk:3, mp:60, atkVal:80, level:10, range:2, target:1, damage:0.8, desc:'毒雾持续伤害，多回合掉血'},
        {name:'⚔ 物理穿透', ball:11, dmg:0, elem:0, atk:0, mp:55, atkVal:150, level:10, range:1, target:0, damage:1.6, desc:'直线贯穿，穿透多人'},
        {name:'⚔ 物理冲击', ball:6, dmg:0, elem:0, atk:2, mp:110, atkVal:280, level:22, range:5, target:1, damage:1.7, desc:'大地狂啸，全屏物理'},
        {name:'💚 治疗恢复', ball:15, dmg:8, elem:0, atk:4, mp:70, atkVal:0, level:10, range:3, target:3, damage:0, desc:'全军恢复，续航必备'},
        {name:'💊 增益强化', ball:0, dmg:0, elem:0, atk:5, mp:60, atkVal:0, level:8, range:3, target:3, damage:0, desc:'提升属性，多回合持续'},
    ],

    _showRecommendations() {
        const panel = document.getElementById('effQuickCreate');
        if (panel.style.display === 'none') panel.style.display = 'block';
        // 在当前参数下方追加推荐面板
        let existing = document.getElementById('effRecommendPanel');
        if (existing) { existing.style.display = existing.style.display === 'none' ? 'block' : 'none'; this._renderRecommendations(); return; }

        const recPanel = document.createElement('div');
        recPanel.id = 'effRecommendPanel';
        recPanel.style.cssText = 'margin-top:12px;padding:12px;background:var(--bg-hover);border-radius:6px;border:1px solid var(--warning);';
        recPanel.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <span style="font-weight:600;font-size:14px;">🧠 智能推荐组合</span>
                <button onclick="document.getElementById('effRecommendPanel').style.display='none'" class="btn btn-xs">✕</button>
            </div>
            <div id="effRecommendList" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:8px;"></div>
        `;
        const visual = document.getElementById('effQcVisual');
        visual.parentNode.insertBefore(recPanel, visual.nextSibling);
        this._renderRecommendations();
    },

    _renderRecommendations() {
        const list = document.getElementById('effRecommendList');
        if (!list) return;
        let html = '';
        this._RECOMMENDED_COMBOS.forEach((r, i) => {
            const ballVisuals = {
                0:{icon:'●',color:'#888'},1:{icon:'→',color:'#ff4444'},2:{icon:'⌒',color:'#ff8800'},
                3:{icon:'⋘',color:'#44aaff'},4:{icon:'↷',color:'#ff44ff'},5:{icon:'⚡',color:'#ffff00'},
                6:{icon:'≈',color:'#aa8844'},7:{icon:'◎',color:'#ff6644'},8:{icon:'◆',color:'#8844ff'},
                9:{icon:'━',color:'#44ffff'},10:{icon:'✱',color:'#ff0000'},11:{icon:'⇨',color:'#ffaa00'},
                12:{icon:'❄',color:'#88ccff'},13:{icon:'🌀',color:'#aaffaa'},14:{icon:'☠',color:'#88ff44'},
                15:{icon:'✚',color:'#44ff44'},
            };
            const bv = ballVisuals[r.ball] || ballVisuals[0];
            const dmgColors = ['#ccc','#ff4444','#4488ff','#44ff44','#ffdd00','#aa44ff'];
            const dc = dmgColors[r.dmg] || '#ccc';
            const ec = dmgColors[r.elem] || '#888';
            html += `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:10px;cursor:pointer;transition:border-color 0.2s;" onmouseenter="this.style.borderColor='var(--warning)'" onmouseleave="this.style.borderColor='var(--border)'" onclick="effectEditor._applyRecommendation(${i})">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
                    <span style="font-weight:600;font-size:14px;">${r.name}</span>
                    <span style="font-size:24px;color:${bv.color};line-height:1;">${bv.icon}</span>
                </div>
                <div style="font-size:12px;color:var(--text-muted);margin-bottom:6px;">${r.desc}</div>
                <div style="display:flex;gap:4px;font-size:11px;">
                    <span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${dc};"></span>
                    <span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${ec};"></span>
                </div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:4px;font-family:monospace;">MP:${r.mp} ATK:${r.atkVal} Lv:${r.level} R:${r.range} x${r.damage}</div>
            </div>`;
        });
        list.innerHTML = html;
    },

    _applyRecommendation(idx) {
        const r = this._RECOMMENDED_COMBOS[idx];
        if (!r) return;
        document.getElementById('qc_Name').value = r.name;
        document.getElementById('qc_Ball').value = r.ball;
        document.getElementById('qc_DamageType').value = r.dmg;
        document.getElementById('qc_Element').value = r.elem;
        document.getElementById('qc_Atk').value = r.atk;
        document.getElementById('qc_MP').value = r.mp;
        document.getElementById('qc_ATK').value = r.atkVal;
        document.getElementById('qc_Level').value = r.level;
        document.getElementById('qc_Range').value = r.range;
        document.getElementById('qc_Target').value = r.target;
        document.getElementById('qc_Damage').value = r.damage;
        this._qcUpdateVisual();
        this._showToast(`推荐组合 "${r.name}" 已加载`);
        // 隐藏推荐面板
        const recPanel = document.getElementById('effRecommendPanel');
        if (recPanel) recPanel.style.display = 'none';
    },
};

// 全局函数：从特效编辑器跳转到 OBD 编辑器
window.openObdEditor = function(type) {
    const navItem = document.querySelector('[data-tab="obd"]');
    if (navItem) {
        navItem.click();
        setTimeout(() => {
            if (typeof obdEditor !== 'undefined' && obdEditor.select) {
                obdEditor.select(type);
            }
        }, 300);
    }
};

// ============================================================
// 特效目录查询器 — 技能编辑器的 Effect 字段联动
// ============================================================
const effectLookup = {
    _catalogs: null,
    _allItems: [],

    async open() {
        document.getElementById('effectLookupOverlay').style.display = 'block';
        document.getElementById('effectLookupModal').style.display = 'block';
        const inp = document.getElementById('effLookupSearch');
        inp.value = '';
        document.getElementById('effLookupCat').value = 'all';
        if (!this._catalogs) {
            try {
                const r = await pyApi('effectGetAll');
                if (r && r.success) {
                    this._catalogs = r;
                    this._buildIndex();
                }
            } catch(e) { showToast('加载特效知识库失败', 'error'); }
        }
        this._renderAll();
    },

    close() {
        document.getElementById('effectLookupOverlay').style.display = 'none';
        document.getElementById('effectLookupModal').style.display = 'none';
    },

    _buildIndex() {
        const c = this._catalogs;
        this._allItems = [];
        const add = (arr, cat, catLabel) => {
            if (!arr) return;
            arr.forEach(item => {
                this._allItems.push({
                    id: item.id,
                    name: item.name,
                    desc: item.desc || '',
                    visual: item.visual || item.icon || '',
                    color: item.color || '',
                    weapon: item.weapon_example || '',
                    cat: cat,
                    catLabel: catLabel,
                });
            });
        };
        add(c.ball_types, 'ball', '弹道类型');
        add(c.damage_types, 'damage', '伤害类型');
        add(c.element_types, 'element', '属性类型');
        add(c.item_scripts, 'items', '物品特效');
        add(c.atk_types, 'atk', '攻击类型');
    },

    _search() {
        const q = document.getElementById('effLookupSearch').value.toLowerCase();
        const cat = document.getElementById('effLookupCat').value;
        let items = this._allItems;
        if (cat !== 'all') items = items.filter(i => i.cat === cat);
        if (q) items = items.filter(i => i.name.toLowerCase().includes(q) || i.desc.toLowerCase().includes(q));
        this._renderItems(items);
    },

    _renderAll() {
        this._renderItems(this._allItems);
    },

    _renderItems(items) {
        const container = document.getElementById('effLookupResult');
        if (!items || items.length === 0) {
            container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);">没有匹配的特效</div>';
            return;
        }
        let html = '<table class="eff-table"><thead><tr><th style="width:50px;">编号</th><th style="width:60px;">图标</th><th style="width:90px;">分类</th><th>名称</th><th style="width:80px;">操作</th></tr></thead><tbody>';
        items.forEach(item => {
            html += `<tr>
                <td style="font-family:monospace;font-weight:600;">${item.id}</td>
                <td style="text-align:center;font-size:18px;color:${item.color||'#fff'};">${item.visual}</td>
                <td style="font-size:12px;color:var(--text-muted);">${item.catLabel}</td>
                <td><span style="font-weight:600;">${escHtml(item.name)}</span><br><span style="font-size:12px;color:var(--text-muted);">${escHtml(item.desc)}</span>${item.weapon ? '<br><span style="font-size:11px;color:var(--warning);">示例: ' + escHtml(item.weapon) + '</span>' : ''}</td>
                <td><button onclick="effectLookup._select(${item.id})" class="btn btn-xs btn-primary" title="填入特效编号">选择</button></td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    },

    _select(value) {
        const inp = document.getElementById('sk_Effect');
        if (inp) {
            inp.value = value;
            if (skillEditor && skillEditor.currentChanged) skillEditor.currentChanged();
            showToast('已填入特效编号: ' + value);
        }
        this.close();
    },
};

// ============================================================
// 特性定义编辑器
// ============================================================

const genSkillEditor = {
    _data: {},
    _currentTab: 'gen',
    changed: false,

    _fieldHints: {
        Data01: '效果类型: 0=加成武力, 1=加成智力, 2=加成体力, 3=加成技力, 4=致命一击, 5=加成速度, 6=冲锋, 7=加成防御, 8=移动速度, 9=闪避, 10=克制, 11=伤害加成%, 12=减伤%, 13=回复体力, 14=回复技力, 15=特殊效果',
        Data02: '效果强度/数值(如 Data01=10 克制时, Data02=被克制兵种编号)',
        Data03: '持续时间/回合数(0=永久/被动)',
        Data04: '触发概率(%)(0=必定触发)',
        Data05: '作用范围(0=自身, 1=全军, 2=全武将)',
        Data06: '扩展参数1(部分特性用于指定附加效果)',
        Data07: '扩展参数2(部分特性用于指定目标类型)',
        Data08: '扩展参数3(预留)',
        Data09: '扩展参数4(预留)',
        Data10: '扩展参数5(预留)',
    },

    _getHint(field) {
        return this._fieldHints[field] || '';
    },

    async load() {
        const res = await pyApi('loadGenSkills');
        this._data = res.data || {};
        this.renderCurrent();
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this._data));
    },

    restoreSnapshot(data) {
        this._data = data;
        this.renderCurrent();
    },

    pushUndo() {
        UndoManager.pushState('genSkills', this.snapshot());
    },

    switchTab(key) {
        this._currentTab = key;
        document.querySelectorAll('.gen-skill-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.gen-skill-panel').forEach(p => p.classList.remove('active'));
        const btn = document.querySelector(`.gen-skill-tab-btn[onclick*="${key}"]`);
        if (btn) btn.classList.add('active');
        document.getElementById('genSkill' + key.charAt(0).toUpperCase() + key.slice(1)).classList.add('active');
        this.renderCurrent();
    },

    renderCurrent() {
        const key = this._currentTab;
        const panel = document.getElementById('genSkill' + key.charAt(0).toUpperCase() + key.slice(1));
        if (!panel || !this._data[key]) return;
        const sections = this._data[key].sections || [];
        panel.innerHTML = sections.map((s, idx) => {
            const name = s.Name || '';
            const no = s.NO || s.No || '';
            const dataFields = Object.keys(s).filter(k => k.startsWith('Data') || k.startsWith('data'));
            const otherFields = Object.keys(s).filter(k => !k.startsWith('Data') && !k.startsWith('data') && k !== 'Name' && k !== 'NO' && k !== 'No' && k !== 'IsUsed');
            let fieldsHtml = '';
            dataFields.forEach(f => {
                const hint = this._getHint(f);
                fieldsHtml += `<div class="detail-row"><label title="${escHtml(hint)}">${f}${hint?' <span style="color:var(--accent);font-size:9px;cursor:help;" title="${escHtml(hint)}">?</span>':''}</label><input type="text" value="${s[f] || ''}" onchange="genSkillEditor._set('${key}', ${idx}, '${f}', this.value)" title="${escHtml(hint)}" placeholder="${hint ? escHtml(hint).substring(0,30)+'...' : ''}"></div>`;
            });
            otherFields.forEach(f => {
                fieldsHtml += `<div class="detail-row"><label>${f}</label><input type="text" value="${s[f] || ''}" onchange="genSkillEditor._set('${key}', ${idx}, '${f}', this.value)"></div>`;
            });
            return `<div class="card" style="margin-bottom:8px;">
                <h4>#${no} ${name}</h4>
                <div class="detail-content">${fieldsHtml}</div>
            </div>`;
        }).join('') || '<p style="color:var(--text-muted);padding:10px;">暂无数据</p>';
    },

    _set(key, idx, field, val) {
        if (this._data[key] && this._data[key].sections[idx]) {
            this._data[key].sections[idx][field] = val;
            this.changed = true;
        }
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        this.pushUndo();
        const res = await pyApi('saveGenSkills', this._data);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success) this.changed = false;
    },

    addNew() {
        this.pushUndo();
        if (!this._currentTab) return;
        const key = this._currentTab;
        const sections = this._data[key].sections;
        const newSection = {};
        // 检测第一个section的字段作为模板
        if (sections.length > 0) {
            Object.keys(sections[0]).forEach(k => { newSection[k] = ''; });
        } else {
            newSection.No = String(sections.length + 1);
            newSection.Name = '';
        }
        sections.push(newSection);
        this._currentSection = sections.length - 1;
        this.renderCurrent();
    },

    deleteCurrent() {
        this.pushUndo();
        if (!this._currentTab || this._currentSection === null) return;
        const sections = this._data[this._currentTab].sections;
        const entry = sections[this._currentSection];
        if (!confirm(`确认删除特性 "${entry.Name || '未命名'}"?`)) return;
        sections.splice(this._currentSection, 1);
        this._currentSection = null;
        this.renderCurrent();
    },

    cloneCurrent() {
        if (!this._currentTab || this._currentSection === null) return;
        this.pushUndo();
        const sections = this._data[this._currentTab].sections;
        const entry = sections[this._currentSection];
        const clone = Object.assign({}, entry);
        clone.No = String(sections.length + 1);
        sections.push(clone);
        this._currentSection = sections.length - 1;
        this.renderCurrent();
    }
};

// ============================================================
// 武将出生地编辑器
// ============================================================

const general02Editor = {
    _data: [],
    _current: null,
    changed: false,
    _searchKeyword: '',

    async load() {
        const res = await pyApi('loadGeneral02');
        this._data = res.data || [];
        document.getElementById('general02Count').textContent = `${this._data.length} 个武将`;
        this.renderList();
    },

    search(keyword) {
        this._searchKeyword = keyword || '';
        this.renderList();
    },

    renderList() {
        const container = document.getElementById('general02List');
        if (!container) return;
        const kw = (this._searchKeyword || '').toLowerCase();
        container.innerHTML = this._data.filter((g) => {
            if (!kw) return true;
            const name = (g.Name || '').toLowerCase();
            const no = String(g.No || '');
            return name.includes(kw) || no.includes(kw);
        }).map((g) => {
            const idx = this._data.indexOf(g);
            return `<div class="list-item${this._current === idx ? ' active' : ''}" onclick="general02Editor.select(${idx})">
                <span class="item-no">#${g.No || ''}</span>
                <span class="item-name">${g.Name || ''}</span>
            </div>`;
        }).join('');
    },

    select(idx) {
        if (idx < 0 || idx >= this._data.length) return;
        this._current = idx;
        this.renderList();
        this.renderDetail();
    },

    renderDetail() {
        const container = document.getElementById('general02Detail');
        if (!container || this._current === null) return;
        const g = this._data[this._current];
        let rows = '';
        for (let i = 1; i <= 10; i++) {
            const val = g[`City${i}`] || '';
            rows += `<div class="detail-row"><label>剧本${i}</label><input type="text" value="${val}" onchange="general02Editor._set('City${i}', this.value)" placeholder="城市编号, 状态 (0=在野 1=登场)"><span class="hint">例: 59, 0</span></div>`;
        }
        container.innerHTML = `<div class="detail-content">
            <div class="detail-row"><label>编号</label><span>${g.No || ''}</span></div>
            <div class="detail-row"><label>姓名</label><span>${g.Name || ''}</span></div>
            ${rows}
        </div>`;
    },

    _set(key, val) {
        if (this._current !== null) { this._data[this._current][key] = val; this.changed = true; }
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        const res = await pyApi('saveGeneral02', this._data);
        if (res.success) this.changed = false;
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this._data));
    },

    restoreSnapshot(data) {
        this._data = JSON.parse(JSON.stringify(data));
        this._current = null;
        this.renderList();
        this.renderDetail();
    },

    pushUndo() {
        UndoManager.pushState('general02', this.snapshot());
    },

    async addNew() {
        const newNo = this._data.length > 0 ? Math.max(...this._data.map(g => parseInt(g.No || 0))) + 1 : 1;
        const entry = { No: newNo, Name: `新武将_${newNo}` };
        for (let i = 1; i <= 10; i++) entry[`City${i}`] = '0, 0';
        this._data.push(entry);
        this._current = this._data.length - 1;
        this.renderList();
        this.renderDetail();
    },

    async deleteCurrent() {
        if (this._current === null) return;
        const entry = this._data[this._current];
        if (!confirm(`确认删除出生地 "${entry.Name}" #${entry.No}?`)) return;
        pyApi('deleteIniItem', 'Setting/General02.ini', 'GENERAL', 'No', String(entry.No));
        this._data.splice(this._current, 1);
        this._current = null;
        this.renderList();
        this.renderDetail();
    },

    async cloneCurrent() {
        if (this._current === null) return;
        const src = this._data[this._current];
        const clone = { ...src };
        clone.No = Math.max(...this._data.map(g => parseInt(g.No || 0))) + 1;
        clone.Name = (src.Name || '克隆') + '_副本';
        this._data.push(clone);
        this._current = this._data.length - 1;
        this.renderList();
        this.renderDetail();
    }
};

// ============================================================
// 剧本年代编辑器 (Age.ini)
// ============================================================

const ageEditor = {
    _data: [],
    _current: null,
    changed: false,
    _searchKeyword: '',

    async load() {
        const res = await pyApi('loadAge');
        if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
        this._data = res.data || [];
        this._current = null;
        this.renderList();
        document.getElementById('ageCount').textContent = this._data.length;
        this.renderDetail();
    },

    search(keyword) {
        this._searchKeyword = keyword || '';
        this.renderList();
    },

    renderList() {
        const container = document.getElementById('ageList');
        if (!container) return;
        const kw = (this._searchKeyword || '').toLowerCase();
        const filtered = kw ? this._data.filter((a) => {
            const name = (a.Name || '').toLowerCase();
            const no = String(a.No || a.NO || '');
            return name.includes(kw) || no.includes(kw);
        }) : this._data;
        if (filtered.length === 0) {
            container.innerHTML = '<div class="empty-detail">暂无年代数据</div>';
            return;
        }
        container.innerHTML = filtered.map((a) => {
            const idx = this._data.indexOf(a);
            const active = this._current === idx ? ' active' : '';
            return `<div class="list-item${active}" onclick="ageEditor.select(${idx})">
                <span class="item-no">#${a.No || a.NO || '-'}</span>
                <span class="item-name">${escHtml(a.Name || '未命名')}</span>
            </div>`;
        }).join('');
    },

    select(idx) {
        if (idx < 0 || idx >= this._data.length) return;
        this._current = idx;
        this.renderList();
        this.renderDetail();
    },

    renderDetail() {
        const emptyEl = document.getElementById('emptyAgeDetail');
        const detailEl = document.getElementById('ageDetailContent');
        if (!emptyEl || !detailEl) return;
        if (this._current === null) {
            emptyEl.style.display = 'flex';
            detailEl.style.display = 'none';
            return;
        }
        emptyEl.style.display = 'none';
        detailEl.style.display = 'block';
        const a = this._data[this._current];
        document.getElementById('age_No').value = a.No || a.NO || '';
        document.getElementById('age_Name').value = a.Name || '';

        // 渲染额外字段
        const extra = document.getElementById('ageExtraFields');
        if (!extra) return;
        const skipKeys = ['No', 'NO', 'Name', 'NAME'];
        const extraKeys = Object.keys(a).filter(k => !skipKeys.includes(k));
        if (extraKeys.length === 0) {
            extra.innerHTML = '';
            return;
        }
        extra.innerHTML = extraKeys.map(k => {
            return `<div class="form-group"><label>${k}</label><input type="text" id="age_${k}" value="${escHtml(a[k] || '')}" onchange="ageEditor._set('${k}',this.value)"></div>`;
        }).join('');
    },

    _set(key, value) {
        if (this._current === null) return;
        this._data[this._current][key] = value;
        this.changed = true;
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        const res = await pyApi('saveAge', this._data);
        if (res.success) this.changed = false;
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this._data));
    },

    restoreSnapshot(data) {
        this._data = JSON.parse(JSON.stringify(data));
        this._current = null;
        this.renderList();
        this.renderDetail();
    },

    pushUndo() {
        UndoManager.pushState('age', this.snapshot());
    },

    async addNew() {
        const newNo = this._data.length > 0 ? Math.max(...this._data.map(a => parseInt(a.No || 0))) + 1 : 1;
        this._data.push({ No: newNo, Name: `新年代_${newNo}` });
        this._current = this._data.length - 1;
        this.renderList();
        this.renderDetail();
    },

    async deleteCurrent() {
        if (this._current === null) return;
        const entry = this._data[this._current];
        if (!confirm(`确认删除年代 "${entry.Name}" #${entry.No}?`)) return;
        pyApi('deleteIniItem', 'Setting/Age.ini', 'AGE', 'No', String(entry.No));
        this._data.splice(this._current, 1);
        this._current = null;
        this.renderList();
        this.renderDetail();
    },

    async cloneCurrent() {
        if (this._current === null) return;
        const src = this._data[this._current];
        const clone = { ...src };
        clone.No = Math.max(...this._data.map(a => parseInt(a.No || 0))) + 1;
        clone.Name = (src.Name || '克隆') + '_副本';
        this._data.push(clone);
        this._current = this._data.length - 1;
        this.renderList();
        this.renderDetail();
    }
};

// ============================================================
// 等级经验编辑器
// ============================================================

const genLvEditor = {
    _data: [],
    changed: false,

    async load() {
        const res = await pyApi('loadGenLV');
        this._data = res.data || [];
        this.render();
    },

    render() {
        const tbody = document.getElementById('genLvBody');
        if (!tbody) return;
        tbody.innerHTML = this._data.map((lv, idx) =>
            `<tr>
                <td>${lv.No || ''}</td>
                <td><input type="number" value="${lv.Exp || 0}" onchange="genLvEditor._set(${idx}, 'Exp', this.value)" style="width:120px;"></td>
                <td><input type="number" value="${lv.SolNum || 0}" onchange="genLvEditor._set(${idx}, 'SolNum', this.value)" style="width:100px;"></td>
                <td><button onclick="genLvEditor.deleteEntry(${idx})" class="btn btn-danger btn-xs" title="删除">✕</button></td>
            </tr>`
        ).join('');
    },

    _set(idx, key, val) {
        if (this._data[idx]) { this._data[idx][key] = val; this.changed = true; }
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        this.pushUndo();
        const res = await pyApi('saveGenLV', this._data);
        if (res.success) this.changed = false;
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this._data));
    },

    restoreSnapshot(data) {
        this._data = JSON.parse(JSON.stringify(data));
        this.render();
    },

    pushUndo() {
        UndoManager.pushState('genLv', this.snapshot());
    },

    addNew() {
        const nextNo = this._data.length > 0 ? Math.max(...this._data.map(l => parseInt(l.No || 0))) + 1 : 1;
        this._data.push({ No: nextNo, Exp: 0, SolNum: 0 });
        this.render();
    },

    deleteEntry(idx) {
        if (!confirm(`确认删除等级 #${this._data[idx]?.No || idx + 1}?`)) return;
        pyApi('deleteIniItem', 'Setting/GenLV.ini', 'GENLV', 'No', String(this._data[idx]?.No || ''));
        this._data.splice(idx, 1);
        this.render();
    }
};

// ============================================================
// TermText 文本编辑器
// ============================================================

const termTextEditor = {
    _data: [],
    _filtered: [],
    changed: false,
    _currentCategory: 'all',

    // TermText 编号分类（基于社区文档）
    CATEGORIES: {
        'all':       { label: '全部',        min: 0,     max: 99999 },
        'building':  { label: '建物名',      min: 12000, max: 12311 },
        'soldier':   { label: '兵种名',      min: 13000, max: 13187 },
        'soldier_desc': { label: '兵种说明', min: 13500, max: 13687 },
        'item':      { label: '物品名',      min: 14000, max: 16716 },
        'item_desc': { label: '物品说明',    min: 15000, max: 16716 },
        'title':     { label: '官职',        min: 17000, max: 17209 },
        'sfmagic':   { label: '军师技',      min: 18000, max: 19203 },
        'bfmagic':   { label: '武将技',      min: 20000, max: 21646 },
        'superatk':  { label: '必杀技名',    min: 23000, max: 23646 },
        'superatk_desc': { label: '必杀说明', min: 23500, max: 23646 },
        'formation': { label: '阵法',        min: 24000, max: 25000 },
        'general':   { label: '武将名',      min: 25000, max: 26535 },
        'surname':   { label: '武将姓氏',    min: 27000, max: 27535 },
        'skill':     { label: '技能说明',    min: 35000, max: 37600 },
        'system':    { label: '系统文本',    min: 0,     max: 11999 },
    },

    async load() {
        const res = await pyApi('loadTermTextFull');
        this._data = res.data || [];
        this._filtered = this._data;
        document.getElementById('termTextCount').textContent = `${this._data.length} 条`;
        this._updateCategoryButtons();
        this.render();
    },

    search(q) {
        if (!q) { this._applyFilter(); return; }
        const lower = q.toLowerCase();
        this._filtered = this._data.filter(d => (d.value || '').toLowerCase().includes(lower) || (d.id || '').includes(q));
        this.render();
    },

    filterByCategory(catKey) {
        this._currentCategory = catKey;
        this._applyFilter();
        this._updateCategoryButtons();
        this.render();
    },

    _applyFilter() {
        const cat = this.CATEGORIES[this._currentCategory];
        const searchQ = document.getElementById('termTextSearch')?.value || '';
        let data = this._data;
        if (cat && this._currentCategory !== 'all') {
            data = data.filter(d => {
                const id = parseInt(d.id) || 0;
                return id >= cat.min && id <= cat.max;
            });
        }
        if (searchQ) {
            const lower = searchQ.toLowerCase();
            data = data.filter(d => (d.value || '').toLowerCase().includes(lower) || (d.id || '').includes(searchQ));
        }
        this._filtered = data;
    },

    _updateCategoryButtons() {
        const container = document.getElementById('termTextCategoryBtns');
        if (!container) return;
        const cats = Object.entries(this.CATEGORIES);
        container.innerHTML = cats.map(([key, cat]) => {
            const count = this._data.filter(d => {
                const id = parseInt(d.id) || 0;
                return id >= cat.min && id <= cat.max;
            }).length;
            const active = this._currentCategory === key ? 'btn-primary' : '';
            return `<button class="btn btn-sm ${active}" onclick="termTextEditor.filterByCategory('${key}')" style="margin:2px;font-size:11px;">${cat.label}(${count})</button>`;
        }).join('');
    },

    render() {
        const tbody = document.getElementById('termTextBody');
        if (!tbody) return;
        const show = this._filtered.slice(0, 200);
        tbody.innerHTML = show.map((d, idx) =>
            `<tr>
                <td>${d.id}</td>
                <td><input type="text" value="${d.value || ''}" onchange="termTextEditor._set(${this._data.indexOf(d)}, 'value', this.value)" style="width:100%;"></td>
                <td><button class="btn btn-sm btn-danger" onclick="termTextEditor._del(${this._data.indexOf(d)})">删除</button></td>
            </tr>`
        ).join('');
        if (this._filtered.length > 200) {
            tbody.innerHTML += `<tr><td colspan="3" style="text-align:center;color:var(--text-muted);">显示前200条，共${this._filtered.length}条匹配</td></tr>`;
        }
    },

    _set(realIdx, key, val) {
        if (this._data[realIdx]) { this._data[realIdx][key] = val; this.changed = true; }
    },

    _del(realIdx) {
        this._data.splice(realIdx, 1);
        this.search(document.querySelector('#termText input')?.value || '');
    },

    addNew() {
        const maxId = Math.max(...this._data.map(d => parseInt(d.id) || 0), 0);
        this._data.push({ id: String(maxId + 1), value: '新文本' });
        this._filtered = this._data;
        this.render();
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        const res = await pyApi('saveTermText', this._data);
        if (res.success) this.changed = false;
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this._data));
    },

    restoreSnapshot(data) {
        this._data = JSON.parse(JSON.stringify(data));
        this._filtered = this._data;
        this.render();
    },

    pushUndo() {
        UndoManager.pushState('termText', this.snapshot());
    },

    async serverSearch() {
        const q = prompt('输入关键词搜索 TermText:');
        if (!q) return;
        try {
            const res = await pyApi('searchTermtext', q);
            if (res && res.success && res.results) {
                let msg = `搜索 "${q}" 结果: ${res.count} 条\n\n`;
                res.results.slice(0, 30).forEach(r => {
                    msg += `#${r.id}: ${r.value}\n`;
                });
                if (res.count > 30) msg += `\n... 仅显示前30条，共${res.count}条`;
                showToast(msg, 'info');
            } else {
                showToast('搜索失败: ' + (res ? res.message : ''), 'error');
            }
        } catch(e) { showToast('搜索失败: '+e, 'error'); }
    },

    async showStats() {
        try {
            const [faceRes, textsRes] = await Promise.all([
                pyApi('faceStats'),
                pyApi('getAllTermtext'),
            ]);
            let msg = '=== 头像统计 ===\n';
            if (faceRes && faceRes.success && faceRes.stats) {
                const s = faceRes.stats;
                msg += `头像总数: ${s.total_faces || '?'}\n`;
                msg += `武将头像: ${s.general_faces || '?'}\n`;
                if (s.missing_faces) msg += `缺失头像: ${s.missing_faces}\n`;
            } else {
                msg += '暂无头像数据\n';
            }
            msg += '\n=== TermText 统计 ===\n';
            if (textsRes && textsRes.success) {
                msg += `文本总数: ${textsRes.count || 0}\n`;
                if (textsRes.data) {
                    const keys = Object.keys(textsRes.data);
                    msg += `文本分类: ${keys.length} 个\n`;
                    keys.slice(0, 10).forEach(k => {
                        msg += `  ${k}: ${textsRes.data[k]}条\n`;
                    });
                }
            }
            showToast(msg, 'info');
        } catch(e) { showToast('统计失败: '+e, 'error'); }
    },
};

// ============================================================
// 引用完整性检查器
// ============================================================

const refChecker = {
    async run() {
        try {
            const res = await pyApi('checkReferences');
            if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
            this.render(res);
        } catch (e) {
            showToast('检查失败: ' + e.message, 'error');
        }
    },

    render(result) {
        // 清理之前追加的错误元素
        const refcheckEl = document.getElementById('refcheck');
        if (refcheckEl) {
            refcheckEl.querySelectorAll('.panel-card.ref-err-card').forEach(el => el.remove());
        }

        // 统计卡片
        document.getElementById('rcGeneralCount').textContent = result.general_count || 0;
        const brokenCount = (result.broken_refs || []).length;
        const missingCount = (result.missing_entries || []).length;
        const totalRefs = Object.keys(result.reference_summary || {}).length;
        document.getElementById('rcBrokenCount').textContent = brokenCount;
        document.getElementById('rcMissingCount').textContent = missingCount;
        document.getElementById('rcTotalRefs').textContent = totalRefs;

        // 断裂引用
        const brokenList = document.getElementById('rcBrokenList');
        if (brokenCount === 0) {
            brokenList.innerHTML = '<p class="hint" style="color:var(--success);">所有引用均有效，未发现断裂引用</p>';
        } else {
            brokenList.innerHTML = result.broken_refs.map((r, i) =>
                `<div class="ref-issue ref-broken">
                    <span class="ref-issue-icon">⚠️</span>
                    <div class="ref-issue-body">
                        <strong>${r.file}</strong> — ${r.detail}
                        <span class="ref-issue-meta">${r.section || ''} ${r.field || ''} = ${r.value || ''}</span>
                    </div>
                </div>`
            ).join('');
        }

        // 缺失条目
        const missingList = document.getElementById('rcMissingList');
        if (missingCount === 0) {
            missingList.innerHTML = '<p class="hint" style="color:var(--success);">所有武将均有完整的关联条目</p>';
        } else {
            missingList.innerHTML = result.missing_entries.map((r, i) =>
                `<div class="ref-issue ref-missing">
                    <span class="ref-issue-icon">🔶</span>
                    <div class="ref-issue-body">
                        <strong>${r.file}</strong> — ${r.detail}
                    </div>
                </div>`
            ).join('');
        }

        // 引用关系总览
        const summary = document.getElementById('rcRefSummary');
        const refs = result.reference_summary || {};
        const keys = Object.keys(refs);
        if (keys.length === 0) {
            summary.innerHTML = '<p class="hint">暂无引用关系数据</p>';
        } else {
            // 按引用数量排序
            keys.sort((a, b) => refs[b].count - refs[a].count);
            summary.innerHTML = keys.map(key => {
                const info = refs[key];
                const type = key.startsWith('general_') ? '武将' : key.startsWith('city_') ? '城池' : '其他';
                const id = key.replace('general_', '').replace('city_', '');
                return `<div class="ref-issue ref-ok">
                    <span class="ref-issue-icon">✅</span>
                    <div class="ref-issue-body">
                        <strong>${type} #${id}</strong> — 被 ${info.count} 处引用
                        <span class="ref-issue-meta">${(info.sources || []).slice(0, 5).join(' | ')}</span>
                    </div>
                </div>`;
            }).join('');
        }

        // 其他问题
        const otherIssues = (result.issues || []).filter(i => i.type === 'error');
        if (otherIssues.length > 0) {
            const errDiv = document.createElement('div');
            errDiv.className = 'panel-card ref-err-card';
            errDiv.style.marginTop = '12px';
            errDiv.innerHTML = `<div class="panel-card-header"><h3>检查错误</h3></div>
                <div style="padding:12px;">${otherIssues.map(e => `<p class="hint" style="color:#e74c3c;">${e.file}: ${e.detail}</p>`).join('')}</div>`;
            document.getElementById('refcheck').appendChild(errDiv);
        }
    }
};

// ============================================================
// 全局函数暴露给HTML内联调用
// ============================================================
window.selectGamePath = selectGamePath;
window.refreshFacePreview = () => generals.refreshFacePreview();
window.importCustomFace = () => generals.importCustomFace();
window.exportCurrentFace = () => generals.exportCurrentFace();

// ============================================================
// PCK资源管理器
// ============================================================
const pckEditor = {
    async detect() {
        const el = document.getElementById('pckStateInfo');
        const fl = document.getElementById('pckFileList');
        const sd = document.getElementById('pckSettingDetail');
        el.innerHTML = '<p class="loading">检测中...</p>';
        try {
            let state = await pyApi('pckDetect');
            state = state || {};
            el.innerHTML = `<div class="info-row"><span class="info-label">状态:</span><span class="info-value ${state.state==='ready'?'text-success':'text-warning'}">${state.state||'未知'}</span></div>
                <div class="info-row"><span class="info-label">Setting文件夹:</span><span class="info-value">${state.has_setting?'存在':'不存在'}</span></div>
                <div class="info-row"><span class="info-label">INI文件数:</span><span class="info-value">${state.ini_count||0}</span></div>
                <div class="info-row"><span class="info-label">建议:</span><span class="info-value">${(state.recommendations||[]).join('<br>')}</span></div>`;
            if (state.pck_files && state.pck_files.length) {
                fl.innerHTML = state.pck_files.map(f=>`<div class="list-item"><span><b>${f.name}</b> (${f.size_mb}MB)</span><span class="tag">${f.type}</span></div>`).join('');
            } else { fl.innerHTML = '<p class="hint">未检测到PCK文件</p>'; }
            let status = await pyApi('pckGetSettingStatus');
            status = status || {};
            if (status.exists) {
                sd.innerHTML = `<div class="info-row"><span class="info-label">路径:</span><span class="info-value">${status.path||''}</span></div>
                    <div class="info-row"><span class="info-label">文件数:</span><span class="info-value">${status.file_count||0}</span></div>
                    <div class="info-row"><span class="info-label">子目录:</span><span class="info-value">${(status.subdirs||[]).map(d=>d.name+'('+d.file_count+'项)').join(', ')}</span></div>
                    <details><summary>文件列表</summary>${(status.files||[]).slice(0,50).map(f=>`<div class="list-item">${f.name} (${f.size_kb}KB)</div>`).join('')}${(status.files||[]).length>50?'<div class="hint">...还有'+(status.files.length-50)+'个文件</div>':''}</details>`;
            } else { sd.innerHTML = '<p class="hint">Setting文件夹不存在</p>'; }
        } catch(e) { el.innerHTML = '<p class="err">检测失败: '+escHtml(String(e))+'</p>'; }
    },
    async extractAll() {
        if (!confirm('将从Patch.pck提取所有文件到游戏目录，确认?')) return;
        try {
let r = await pyApi('pckExtractAll', 'Patch.pck');
            r = r || {};
            showToast(r.success ? '提取成功: '+r.extracted+'个文件' : '提取失败: '+r.message, r.success ? 'success' : 'error');
            if (r.success) this.detect();
        } catch(e) { showToast('提取失败: '+e, 'error'); }
    },
    async repack() {
        if (!confirm('将把 Setting/ 文件夹重新打包为 Patch.pck，原文件将备份为 .bak，确认?')) return;
        try {
            document.getElementById('pckStateInfo').innerHTML = '<p class="loading">打包中...</p>';
            let r = await pyApi('pckRepack');
            r = r || {};
            showToast(r.success ? r.message + ' (' + r.size_mb + 'MB, info)' : '打包失败: ' + r.message);
            if (r.success) this.detect();
        } catch(e) { showToast('打包失败: '+e, 'error'); }
    },

    async convertImage() {
        const src = prompt('输入源图片路径 (BMP/PNG):');
        if (!src) return;
        const dst = prompt('输出SHP路径 (如 data/GenHalf/0001.shp):');
        if (!dst) return;
        try {
            let r = await pyApi('convertImageToBfobjShp', src, dst);
            r = r || {};
            showToast(r.success ? '转换成功: ' + r.message : '转换失败: ' + r.message, r.success ? 'success' : 'error');
        } catch(e) { showToast('转换失败: '+e, 'error'); }
    },

    async browsePck() {
        const panel = document.getElementById('pckBrowsePanel');
        if (panel) { panel.style.display = 'block'; await this.browsePckFiles(); }
    },

    async browsePckFiles() {
        const sel = document.getElementById('pckBrowseSelect');
        const pckName = sel ? sel.value : 'Patch.pck';
        try {
            const r = await pyApi('pckListFiles', pckName);
            const list = document.getElementById('pckBrowseList');
            const count = document.getElementById('pckBrowseCount');
            if (r && r.success && r.files) {
                if (count) count.textContent = `共 ${r.count} 个文件`;
                if (list) {
                    const folders = {};
                    r.files.forEach(f => {
                        const parts = f.name.split('/');
                        const dir = parts.length > 1 ? parts.slice(0, -1).join('/') + '/' : '/';
                        if (!folders[dir]) folders[dir] = [];
                        folders[dir].push(f);
                    });

                    let html = '';
                    const sortedDirs = Object.keys(folders).sort();
                    sortedDirs.forEach(dir => {
                        const files = folders[dir];
                        html += `<div style="font-weight:600;color:var(--accent);margin:8px 0 4px;padding:2px 6px;background:var(--bg-card);border-radius:3px;">${dir}</div>`;
                        files.forEach(f => {
                            const name = f.name.split('/').pop();
                            const sizeKB = (f.size / 1024).toFixed(1);
                            html += `<div style="padding:2px 8px;font-family:monospace;display:flex;justify-content:space-between;border-bottom:1px solid var(--border);">
                                <span>${escHtml(name)}</span>
                                <span style="color:var(--text-muted);">${sizeKB} KB</span>
                            </div>`;
                        });
                    });
                    list.innerHTML = html || '<p class="hint">PCK为空</p>';
                }
            } else {
                if (count) count.textContent = '加载失败';
                if (list) list.innerHTML = '<p class="hint">加载失败: ' + (r ? r.message : '') + '</p>';
            }
        } catch(e) {
            const list = document.getElementById('pckBrowseList');
            if (list) list.innerHTML = '<p class="hint">浏览失败: ' + e + '</p>';
        }
    },
};

// ============================================================
// 通用INI编辑器工厂
// ============================================================
function createIniEditor(prefix, apiName, countId, listId, emptyId, detailId, fields, filePath, sectionName) {
    const _deleteFileMap = {
        'BFFront': 'Setting/BFFront.ini', 'Dialogue': 'Setting/Dialogue.ini',
        'Color': 'Setting/Color.ini', 'CityPos': 'Setting/CityPos.ini',
        'Terrain': 'Setting/Terrain.ini', 'SystemText': 'Setting/SystemText.ini',
        'GossipText': 'Setting/GossipText.ini', 'ExtraTerrain': 'Setting/ExtraTerrain.ini',
        'FormatOffsetPos': 'Setting/FormatOffsetPos.ini', 'BuildingPos': 'Setting/BuildingPos.ini',
        'SFBridge': 'Setting/SFBridge.ini', 'SFRoadBlock': 'Setting/SFRoadBlock.ini',
        'SFRoadBlockPos': 'Setting/SFRoadBlockPos.ini', 'Var': 'Setting/Var.ini',
        'Font': 'font.ini', 'SystemIni': 'system.ini', 'Format': 'Setting/Format.ini',
        'ChessFormat': 'Setting/ChessFormat.ini', 'GlobalParams': 'Setting/Variable.ini',
    };
    return {
        data: [],
        currentIndex: -1,
        current: null,
        changed: false,
        _pageSize: 50,
        _currentPage: 0,
        _searchKeyword: '',
        _prefix: prefix,
        _apiName: apiName,
        _countId: countId,
        _listId: listId,
        _emptyId: emptyId,
        _detailId: detailId,
        _fields: fields,
        _filePath: filePath || (_deleteFileMap[apiName] || ('Setting/' + apiName + '.ini')),
        _sectionName: sectionName || apiName.toUpperCase(),

        async load() {
            const res = await pyApi('load' + this._apiName);
            if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
            this.data = res.data || [];
            this._currentPage = 0;
            this._searchKeyword = '';
            this.renderList();
            const el = document.getElementById(this._countId);
            if (el) el.textContent = this.data.length;
        },

        async save() {
            if (this.changed) this.saveCurrent();
            if (!(await validateBeforeSave())) return;
            this.pushUndo();
            const res = await pyApi('save' + this._apiName, this.data);
            if (res.success) this.changed = false;
            if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        },

        async addNew() {
            this.pushUndo();
            const res = await pyApi('new' + this._apiName);
            if (res.success) {
                this.data.push(res.data);
                this.renderList();
                this.select(this.data.length - 1);
                const el = document.getElementById(this._countId);
                if (el) el.textContent = this.data.length;
            }
        },

        renderList() {
            const container = document.getElementById(this._listId);
            if (!container) return;
            container.innerHTML = '';
            const kw = (this._searchKeyword || '').toLowerCase();
            const filtered = kw ? this.data.filter(t => {
                return (t.Name || '').toLowerCase().includes(kw) || String(t.No || '').toLowerCase().includes(kw);
            }) : this.data;
            const total = filtered.length;
            const totalPages = Math.ceil(total / this._pageSize);
            if (this._currentPage >= totalPages) this._currentPage = Math.max(0, totalPages - 1);
            const start = this._currentPage * this._pageSize;
            const page = filtered.slice(start, start + this._pageSize);
            page.forEach((t) => {
                const idx = this.data.indexOf(t);
                const card = document.createElement('div');
                card.className = 'item-card' + (idx === this.currentIndex ? ' selected' : '');
                card.innerHTML = `<div class="item-card-header"><span class="item-name">${escHtml(t.Name || '#'+t.No)}</span><span class="item-no">#${escHtml(String(t.No || ''))}</span></div>`;
                card.onclick = () => this.select(idx);
                container.appendChild(card);
            });
            // Pagination controls
            if (totalPages > 1) {
                const pg = document.createElement('div');
                pg.className = 'pagination';
                pg.innerHTML = `<button class="pg-btn" onclick="window._pg_${this._prefix} && window._pg_${this._prefix}(0)" ${this._currentPage===0?'disabled':''}>«</button>
                    <button class="pg-btn" onclick="window._pg_${this._prefix} && window._pg_${this._prefix}(${this._currentPage-1})" ${this._currentPage===0?'disabled':''}>‹</button>
                    <span class="pg-info">${this._currentPage+1} / ${totalPages}</span>
                    <button class="pg-btn" onclick="window._pg_${this._prefix} && window._pg_${this._prefix}(${this._currentPage+1})" ${this._currentPage>=totalPages-1?'disabled':''}>›</button>
                    <button class="pg-btn" onclick="window._pg_${this._prefix} && window._pg_${this._prefix}(${totalPages-1})" ${this._currentPage>=totalPages-1?'disabled':''}>»</button>`;
                container.appendChild(pg);
            }
            // Register page control
            const self = this;
            window['_pg_' + this._prefix] = function(p) { self._currentPage = p; self.renderList(); };
        },

        select(idx) {
            if (idx < 0 || idx >= this.data.length) return;
            if (this.changed && this.currentIndex >= 0 && this.currentIndex !== idx) {
                this.saveCurrent();
            }
            this.currentIndex = idx;
            this.current = this.data[idx];
            this.changed = false;
            this.renderDetail();
            this.renderList();
        },

        renderDetail() {
            const emptyEl = document.getElementById(this._emptyId);
            const detailEl = document.getElementById(this._detailId);
            if (!this.current) {
                if (emptyEl) emptyEl.style.display = 'flex';
                if (detailEl) detailEl.style.display = 'none';
                return;
            }
            if (emptyEl) emptyEl.style.display = 'none';
            if (detailEl) detailEl.style.display = 'block';
            this._fields.forEach(k => {
                const el = document.getElementById(this._prefix + '_' + k);
                if (el) {
                    if (el.tagName === 'SELECT') el.value = String(this.current[k] != null ? this.current[k] : '');
                    else if (el.tagName === 'TEXTAREA') el.value = this.current[k] || '';
                    else el.value = this.current[k] != null ? this.current[k] : '';
                }
            });
        },

        saveCurrent() {
            if (!this.current) return;
            this._fields.forEach(k => {
                const el = document.getElementById(this._prefix + '_' + k);
                if (el) {
                    if (el.tagName === 'SELECT') this.current[k] = el.value;
                    else if (el.tagName === 'TEXTAREA') this.current[k] = el.value;
                    else this.current[k] = el.value != null ? el.value : '';
                }
            });
        },

        _set(key, val) {
            if (this.current) {
                this.current[key] = val;
                this.changed = true;
                if (key === 'No') this._validateId();
            }
        },

        _validateId() {
            // 清除所有ID校验提示
            const el = document.getElementById(this._prefix + '_No');
            if (!el) return;
            const oldClass = el.className;
            el.classList.remove('input-error', 'input-warn');
            const hintEl = document.getElementById(this._prefix + '_No_hint');
            if (hintEl) hintEl.remove();
            const no = String(this.current.No || '');
            if (!no) return;
            // 检查重复
            const dup = this.data.filter((d, i) => i !== this.currentIndex && String(d.No || '') === no);
            if (dup.length > 0) {
                el.classList.add('input-error');
                const hint = document.createElement('span');
                hint.id = this._prefix + '_No_hint';
                hint.style.cssText = 'color:var(--danger);font-size:11px;margin-left:8px;';
                hint.textContent = '⚠ ID重复';
                el.parentNode.appendChild(hint);
            }
        },

        deleteCurrent() {
            if (!this.current) return;
            if (!confirm('确认删除? #' + this.current.No)) return;
            this.pushUndo();
            const no = this.current.No;
            pyApi('deleteIniItem', this._filePath, this._sectionName, 'No', String(no));
            this.data.splice(this.currentIndex, 1);
            this.current = null;
            this.currentIndex = -1;
            this.renderList();
            const el = document.getElementById(this._countId);
            if (el) el.textContent = this.data.length;
            const emptyEl = document.getElementById(this._emptyId);
            const detailEl = document.getElementById(this._detailId);
            if (emptyEl) emptyEl.style.display = 'flex';
            if (detailEl) detailEl.style.display = 'none';
        },

        cloneCurrent() {
            if (!this.current) return;
            const clone = Object.assign({}, this.current);
            const usedIds = new Set(this.data.map(t => parseInt(t.No)));
            let newId = 0;
            for (let i = 1; i < 10000; i++) { if (!usedIds.has(i)) { newId = i; break; } }
            clone.No = newId;
            this.data.push(clone);
            this.renderList();
            this.select(this.data.length - 1);
            const el = document.getElementById(this._countId);
            if (el) el.textContent = this.data.length;
        },

        search(keyword) {
            this._searchKeyword = keyword || '';
            this._currentPage = 0;
            this.renderList();
        },

        snapshot() {
            return JSON.parse(JSON.stringify({
                data: this.data,
                currentIndex: this.currentIndex,
            }));
        },

        restoreSnapshot(data) {
            this.data = data.data ? JSON.parse(JSON.stringify(data.data)) : [];
            this.currentIndex = data.currentIndex != null ? data.currentIndex : -1;
            this.current = this.data[this.currentIndex] || null;
            this.renderList();
            const el = document.getElementById(this._countId);
            if (el) el.textContent = this.data.length;
            const emptyEl = document.getElementById(this._emptyId);
            const detailEl = document.getElementById(this._detailId);
            if (this.current) {
                if (emptyEl) emptyEl.style.display = 'none';
                if (detailEl) detailEl.style.display = 'block';
                this.renderDetail();
            } else {
                if (emptyEl) emptyEl.style.display = 'flex';
                if (detailEl) detailEl.style.display = 'none';
            }
        },

        pushUndo() {
            UndoManager.pushState(this._apiName.toLowerCase(), this.snapshot());
        },

        _selectByNo(no) {
        const idx = this.data.findIndex(function(t) { return parseInt(t.No) === parseInt(no); });
        if (idx >= 0) this.select(idx);
    },
    };
}

// ============================================================
// 攻城器械编辑器 (BFFront.ini)
// ============================================================
const bffrontEditor = createIniEditor('bf', 'BFFront', 'bffrontCount', 'bffrontList',
    'emptyBFFrontDetail', 'bffrontDetailContent',
    ['NO','Name','UnitNum','Icon','Format','UnitName','Explain','UnitPos','LVPos_0','LVPos_1','LVPos_2','LVPos_3','Hp','Speed','UseLv','UseInt','UseGen','UsePts']);

// ============================================================
// 特殊对话编辑器 (Dialogue.ini)
// ============================================================
const dialogueEditor = createIniEditor('dl', 'Dialogue', 'dialogueCount', 'dialogueList',
    'emptyDialogueDetail', 'dialogueDetailContent',
    ['No','Name','Speak01','Speak02','Nation1','Nation2','Scene','Relation','String01','String02','IsUsed']);

// ============================================================
// 势力颜色编辑器 (Color.ini)
// ============================================================
const colorEditor = createIniEditor('cl', 'Color', 'colorCount', 'colorList',
    'emptyColorDetail', 'colorDetailContent',
    ['No','Red','Green','Blue']);
colorEditor._preview = function() {
    const r = document.getElementById('cl_Red')?.value || 0;
    const g = document.getElementById('cl_Green')?.value || 0;
    const b = document.getElementById('cl_Blue')?.value || 0;
    const preview = document.getElementById('colorPreview');
    if (preview) preview.style.background = `rgb(${r},${g},${b})`;
};
// 覆盖 renderDetail 添加颜色预览
const _colorRenderDetail = colorEditor.renderDetail;
colorEditor.renderDetail = function() {
    _colorRenderDetail.call(this);
    this._preview();
};

// ============================================================
// 城池坐标编辑器 (CityPos.ini)
// ============================================================
const cityposEditor = createIniEditor('cpos', 'CityPos', 'cityposCount', 'cityposList',
    'emptyCityPosDetail', 'cityposDetailContent',
    ['No','X','Y']);

// ============================================================
// 地形编辑器 (Terrain.ini)
// ============================================================
const terrainEditor = createIniEditor('tr', 'Terrain', 'terrainCount', 'terrainList',
    'emptyTerrainDetail', 'terrainDetailContent',
    ['No','Name','Speed','Attack','Defense','Arrow','IsUsed']);

// ============================================================
// 系统文字编辑器 (SystemText.ini)
// ============================================================
const systemtextEditor = createIniEditor('st', 'SystemText', 'systemtextCount', 'systemtextList',
    'emptySystemTextDetail', 'systemtextDetailContent',
    ['No','Text']);

// ============================================================
// 游戏台词编辑器 (GossipText.ini)
// ============================================================
const gossiptextEditor = createIniEditor('gt', 'GossipText', 'gossiptextCount', 'gossiptextList',
    'emptyGossipTextDetail', 'gossiptextDetailContent',
    ['No','Text']);

// ============================================================
// 额外地形编辑器 (ExtraTerrain.ini)
// ============================================================
const extraterrainEditor = createIniEditor('et', 'ExtraTerrain', 'extraterrainCount', 'extraterrainList',
    'emptyExtraTerrainDetail', 'extraterrainDetailContent',
    ['No','Name','Speed','Attack','Defense']);

// ============================================================
// 阵型位置编辑器 (FormatOffsetPos.ini)
// ============================================================
const formatoffsetposEditor = createIniEditor('fo', 'FormatOffsetPos', 'formatoffsetposCount', 'formatoffsetposList',
    'emptyFormatOffsetPosDetail', 'formatoffsetposDetailContent',
    ['No','X','Y']);

// ============================================================
// 建筑位置编辑器 (BuildingPos.ini)
// ============================================================
const buildingposEditor = createIniEditor('bp', 'BuildingPos', 'buildingposCount', 'buildingposList',
    'emptyBuildingPosDetail', 'buildingposDetailContent',
    ['No','Name','Type','X','Y']);

// ============================================================
// 桥梁编辑器 (SFBridge.ini)
// ============================================================
const sfbridgeEditor = createIniEditor('sb', 'SFBridge', 'sfbridgeCount', 'sfbridgeList',
    'emptySFBridgeDetail', 'sfbridgeDetailContent',
    ['No','X','Y','Width','Height']);

// ============================================================
// 地图可视化坐标编辑器
// ============================================================
const mapVisEditor = {
    _cities: [],
    _buildings: [],
    _bridges: [],
    _roadblocks: [],
    _roadblockPos: [],
    _loaded: false,
    _hovered: null,
    _panX: 0,
    _panY: 0,
    _dragging: false,
    _dragStartX: 0,
    _dragStartY: 0,
    _dragStartPanX: 0,
    _dragStartPanY: 0,
    _searchTerm: '',

    async loadAll() {
        try {
            const [cr, br, sbr, rbr, rbp] = await Promise.all([
                pyApi('loadCityPos'),
                pyApi('loadBuildingPos'),
                pyApi('loadSFBridge'),
                pyApi('loadSFRoadBlock'),
                pyApi('loadSFRoadBlockPos'),
            ]);
            this._cities = (cr && cr.data) || [];
            this._buildings = (br && br.data) || [];
            this._bridges = (sbr && sbr.data) || [];
            this._roadblocks = (rbr && rbr.data) || [];
            this._roadblockPos = (rbp && rbp.data) || [];
            this._loaded = true;
            this._panX = 0; this._panY = 0;
            document.getElementById('mv_cityCount').textContent = this._cities.length;
            document.getElementById('mv_buildingCount').textContent = this._buildings.length;
            document.getElementById('mv_bridgeCount').textContent = this._bridges.length;
            document.getElementById('mv_roadblockCount').textContent = this._roadblocks.length;
            this.render();
        } catch (e) {
            this._loaded = true;
            this.render();
            showToast('地图数据加载失败: ' + e.message, 'error');
        }
    },

    _getCanvas() {
        return document.getElementById('mapCanvasBP');
    },

    _getZoom() {
        return parseFloat(document.getElementById('mv_zoom').value) || 1;
    },

    _getTransform() {
        const canvas = this._getCanvas();
        if (!canvas) return { scale: 1, offsetX: 0, offsetY: 0, toScreen: (wx, wy) => [wx, wy] };
        const w = canvas.clientWidth, h = canvas.clientHeight;
        const bounds = this._bounds();
        const zoom = this._getZoom();
        const worldW = bounds.maxX - bounds.minX;
        const worldH = bounds.maxY - bounds.minY;
        const scaleX = (w - 60) / worldW * zoom;
        const scaleY = (h - 60) / worldH * zoom;
        const scale = Math.min(scaleX, scaleY);
        const offsetX = (w - worldW * scale) / 2 - bounds.minX * scale + this._panX * zoom;
        const offsetY = (h - worldH * scale) / 2 - bounds.minY * scale + this._panY * zoom;
        const toScreen = (wx, wy) => [wx * scale + offsetX, wy * scale + offsetY];
        return { scale, offsetX, offsetY, toScreen, w, h, bounds, zoom, worldW, worldH };
    },

    _screenToWorld(sx, sy) {
        const t = this._getTransform();
        const wx = (sx - t.offsetX) / t.scale;
        const wy = (sy - t.offsetY) / t.scale;
        return [Math.round(wx), Math.round(wy)];
    },

    _bounds() {
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        const all = [...this._cities, ...this._buildings, ...this._bridges, ...this._roadblocks];
        for (const p of all) {
            const x = parseInt(p.X) || 0, y = parseInt(p.Y) || 0;
            if (x < minX) minX = x;
            if (y < minY) minY = y;
            if (x > maxX) maxX = x;
            if (y > maxY) maxY = y;
        }
        // 路障区域
        for (const rp of this._roadblockPos) {
            const x1 = parseInt(rp.X1) || 0, y1 = parseInt(rp.Y1) || 0;
            const x2 = parseInt(rp.X2) || 0, y2 = parseInt(rp.Y2) || 0;
            if (x1 < minX) minX = x1; if (y1 < minY) minY = y1;
            if (x2 > maxX) maxX = x2; if (y2 > maxY) maxY = y2;
        }
        if (!isFinite(minX)) { minX = 0; minY = 0; maxX = 1000; maxY = 1000; }
        const pad = Math.max((maxX - minX) * 0.05, (maxY - minY) * 0.05, 20);
        return { minX: minX - pad, minY: minY - pad, maxX: maxX + pad, maxY: maxY + pad };
    },

    fitAll() {
        document.getElementById('mv_zoom').value = 1;
        this._panX = 0;
        this._panY = 0;
        document.getElementById('mv_showCities').checked = true;
        document.getElementById('mv_showBuildings').checked = true;
        document.getElementById('mv_showBridges').checked = true;
        document.getElementById('mv_showRoadblock').checked = true;
        document.getElementById('mv_showGrid').checked = true;
        document.getElementById('mv_zoomLabel').textContent = '1.0x';
        this.render();
    },

    _onSearch(val) {
        this._searchTerm = (val || '').toLowerCase().trim();
        if (!this._searchTerm) { this.render(); return; }
        // 查找匹配的实体并居中
        let found = null;
        const all = [
            ...this._cities.map(d => ({ type: 'city', data: d })),
            ...this._buildings.map(d => ({ type: 'building', data: d })),
            ...this._bridges.map(d => ({ type: 'bridge', data: d })),
            ...this._roadblocks.map(d => ({ type: 'roadblock', data: d })),
        ];
        for (const item of all) {
            const no = String(item.data.No || '');
            const name = (item.data.Name || '').toLowerCase();
            if (no === this._searchTerm || name.includes(this._searchTerm)) {
                found = item;
                break;
            }
        }
        if (found) {
            const t = this._getTransform();
            const x = parseInt(found.data.X) || 0;
            const y = parseInt(found.data.Y) || 0;
            this._panX = 0; this._panY = 0;
            document.getElementById('mv_zoom').value = 2;
            document.getElementById('mv_zoomLabel').textContent = '2.0x';
            this._hovered = found;
        }
        this.render();
    },

    render() {
        const canvas = this._getCanvas();
        if (!canvas) return;
        const container = canvas.parentElement;
        const dpr = window.devicePixelRatio || 1;
        const w = container.clientWidth;
        const h = Math.max(500, container.clientHeight || 500);
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        canvas.style.width = w + 'px';
        canvas.style.height = h + 'px';
        const ctx = canvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        // 背景
        ctx.fillStyle = '#0d1117';
        ctx.fillRect(0, 0, w, h);

        const zoom = this._getZoom();
        document.getElementById('mv_zoomLabel').textContent = zoom.toFixed(1) + 'x';

        const t = this._getTransform();
        const toScreen = t.toScreen;

        // 网格
        if (document.getElementById('mv_showGrid').checked) {
            const gridStep = Math.max(50, Math.round(t.worldW / (w / 80) / 50) * 50);
            ctx.strokeStyle = 'rgba(255,255,255,0.04)';
            ctx.lineWidth = 0.5;
            const gx0 = Math.floor(t.bounds.minX / gridStep) * gridStep;
            const gy0 = Math.floor(t.bounds.minY / gridStep) * gridStep;
            for (let gx = gx0; gx <= t.bounds.maxX; gx += gridStep) {
                const [sx] = toScreen(gx, 0);
                ctx.beginPath(); ctx.moveTo(sx, 0); ctx.lineTo(sx, h); ctx.stroke();
            }
            for (let gy = gy0; gy <= t.bounds.maxY; gy += gridStep) {
                const [, sy] = toScreen(0, gy);
                ctx.beginPath(); ctx.moveTo(0, sy); ctx.lineTo(w, sy); ctx.stroke();
            }
            // 坐标轴标签
            ctx.fillStyle = 'rgba(255,255,255,0.2)';
            ctx.font = '10px monospace';
            for (let gx = gx0; gx <= t.bounds.maxX; gx += gridStep) {
                const [sx] = toScreen(gx, 0);
                ctx.fillText(gx, sx + 2, 12);
            }
            for (let gy = gy0; gy <= t.bounds.maxY; gy += gridStep) {
                const [, sy] = toScreen(0, gy);
                ctx.fillText(gy, 2, sy - 2);
            }
        }

        // 路障区域（最底层）
        if (document.getElementById('mv_showRoadblock').checked) {
            for (const rp of this._roadblockPos) {
                const x1 = parseInt(rp.X1) || 0, y1 = parseInt(rp.Y1) || 0;
                const x2 = parseInt(rp.X2) || 0, y2 = parseInt(rp.Y2) || 0;
                const [sx1, sy1] = toScreen(x1, y1);
                const [sx2, sy2] = toScreen(x2, y2);
                ctx.fillStyle = 'rgba(255,100,0,0.08)';
                ctx.fillRect(sx1, sy1, Math.max(3, sx2 - sx1), Math.max(3, sy2 - sy1));
                ctx.strokeStyle = 'rgba(255,100,0,0.3)';
                ctx.lineWidth = 1;
                ctx.setLineDash([4, 4]);
                ctx.strokeRect(sx1, sy1, Math.max(3, sx2 - sx1), Math.max(3, sy2 - sy1));
                ctx.setLineDash([]);
                if (zoom > 0.8) {
                    ctx.fillStyle = 'rgba(255,100,0,0.6)';
                    ctx.font = `${Math.max(7, 8 * zoom)}px sans-serif`;
                    ctx.fillText('区域#' + rp.No, sx1 + 2, sy1 - 2);
                }
            }
        }

        // 桥梁（底层）
        if (document.getElementById('mv_showBridges').checked) {
            for (const b of this._bridges) {
                const bx = parseInt(b.X) || 0, by = parseInt(b.Y) || 0;
                const bw = parseInt(b.Width) || 3, bh = parseInt(b.Height) || 1;
                const [sx, sy] = toScreen(bx, by);
                const [ex, ey] = toScreen(bx + bw, by + bh);
                const isHover = this._hovered && this._hovered.type === 'bridge' && this._hovered.data === b;
                ctx.fillStyle = isHover ? 'rgba(200,130,60,0.7)' : 'rgba(139,90,43,0.5)';
                ctx.fillRect(sx, sy, Math.max(3, ex - sx), Math.max(3, ey - sy));
                ctx.strokeStyle = isHover ? '#ffa500' : '#8b5a2b';
                ctx.lineWidth = isHover ? 2 : 1;
                ctx.strokeRect(sx, sy, Math.max(3, ex - sx), Math.max(3, ey - sy));
                if (zoom > 0.8) {
                    ctx.fillStyle = '#8b5a2b';
                    ctx.font = `${Math.max(7, 8 * zoom)}px sans-serif`;
                    ctx.fillText('桥#' + b.No, sx + 2, sy - 2);
                }
            }
        }

        // 建筑
        if (document.getElementById('mv_showBuildings').checked) {
            for (const b of this._buildings) {
                const bx = parseInt(b.X) || 0, by = parseInt(b.Y) || 0;
                const [sx, sy] = toScreen(bx, by);
                const r = Math.max(3, 4 * zoom);
                const isHover = this._hovered && this._hovered.type === 'building' && this._hovered.data === b;
                ctx.beginPath();
                ctx.arc(sx, sy, r, 0, Math.PI * 2);
                ctx.fillStyle = isHover ? '#ff6b6b' : 'rgba(100,200,100,0.7)';
                ctx.fill();
                ctx.strokeStyle = isHover ? '#fff' : '#2d8a2d';
                ctx.lineWidth = isHover ? 2 : 1;
                ctx.stroke();
                if (zoom > 0.8) {
                    ctx.fillStyle = '#fff';
                    ctx.font = `${Math.max(8, 9 * zoom)}px sans-serif`;
                    ctx.fillText(b.Name || ('#' + b.No), sx + r + 2, sy + r + 2);
                }
            }
        }

        // 城池
        if (document.getElementById('mv_showCities').checked) {
            for (const c of this._cities) {
                const cx = parseInt(c.X) || 0, cy = parseInt(c.Y) || 0;
                const [sx, sy] = toScreen(cx, cy);
                const r = Math.max(4, 5 * zoom);
                const isHover = this._hovered && this._hovered.type === 'city' && this._hovered.data === c;
                ctx.beginPath();
                ctx.arc(sx, sy, r, 0, Math.PI * 2);
                ctx.fillStyle = isHover ? '#ffd700' : 'rgba(255,200,50,0.8)';
                ctx.fill();
                ctx.strokeStyle = isHover ? '#fff' : '#b8960f';
                ctx.lineWidth = isHover ? 2.5 : 1.5;
                ctx.stroke();
                if (zoom > 0.7) {
                    ctx.fillStyle = '#fff';
                    ctx.font = `bold ${Math.max(8, 10 * zoom)}px sans-serif`;
                    ctx.fillText('#' + c.No, sx + r + 2, sy + r + 2);
                }
            }
        }

        // 路障点
        if (document.getElementById('mv_showRoadblock').checked) {
            for (const rb of this._roadblocks) {
                const rx = parseInt(rb.X) || 0, ry = parseInt(rb.Y) || 0;
                const [sx, sy] = toScreen(rx, ry);
                const r = Math.max(3, 3.5 * zoom);
                const isHover = this._hovered && this._hovered.type === 'roadblock' && this._hovered.data === rb;
                ctx.beginPath();
                ctx.arc(sx, sy, r, 0, Math.PI * 2);
                ctx.fillStyle = isHover ? '#ff6600' : 'rgba(255,100,0,0.7)';
                ctx.fill();
                ctx.strokeStyle = isHover ? '#fff' : '#cc5200';
                ctx.lineWidth = isHover ? 2 : 1;
                ctx.stroke();
                if (zoom > 0.9) {
                    ctx.fillStyle = '#ff6600';
                    ctx.font = `${Math.max(7, 8 * zoom)}px sans-serif`;
                    ctx.fillText('路#' + rb.No, sx + r + 2, sy + r + 2);
                }
            }
        }
    },

    _findHit(x, y) {
        const canvas = this._getCanvas();
        if (!canvas) return null;
        const t = this._getTransform();
        const toScreen = t.toScreen;
        const hitRadius = 12;

        if (document.getElementById('mv_showCities').checked) {
            for (const c of this._cities) {
                const [sx, sy] = toScreen(parseInt(c.X) || 0, parseInt(c.Y) || 0);
                if (Math.hypot(x - sx, y - sy) < hitRadius) return { type: 'city', data: c };
            }
        }
        if (document.getElementById('mv_showBuildings').checked) {
            for (const b of this._buildings) {
                const [sx, sy] = toScreen(parseInt(b.X) || 0, parseInt(b.Y) || 0);
                if (Math.hypot(x - sx, y - sy) < hitRadius) return { type: 'building', data: b };
            }
        }
        if (document.getElementById('mv_showBridges').checked) {
            for (const b of this._bridges) {
                const bx = parseInt(b.X) || 0, by = parseInt(b.Y) || 0;
                const bw = parseInt(b.Width) || 3, bh = parseInt(b.Height) || 1;
                const [sx, sy] = toScreen(bx, by);
                const [ex, ey] = toScreen(bx + bw, by + bh);
                if (x >= sx - 3 && x <= ex + 3 && y >= sy - 3 && y <= ey + 3) return { type: 'bridge', data: b };
            }
        }
        if (document.getElementById('mv_showRoadblock').checked) {
            for (const rb of this._roadblocks) {
                const [sx, sy] = toScreen(parseInt(rb.X) || 0, parseInt(rb.Y) || 0);
                if (Math.hypot(x - sx, y - sy) < hitRadius) return { type: 'roadblock', data: rb };
            }
        }
        return null;
    },

    _updateInfo() {
        const el = document.getElementById('mapVisInfo');
        if (!el) return;
        el.innerHTML = `点击地图查看坐标 — 已加载: ${this._cities.length} 城池 / ${this._buildings.length} 建筑 / ${this._bridges.length} 桥梁 / ${this._roadblocks.length} 路障`;
    },

    init() {
        if (!this._loaded) this.loadAll();
        const canvas = this._getCanvas();
        if (!canvas) return;
        const self = this;
        const tooltip = document.getElementById('mv_tooltip');
        const wrapper = document.getElementById('mv_canvasWrapper');

        canvas.onmousemove = function(e) {
            if (self._dragging) {
                const dx = e.clientX - self._dragStartX;
                const dy = e.clientY - self._dragStartY;
                self._panX = self._dragStartPanX + dx;
                self._panY = self._dragStartPanY + dy;
                self._hovered = null;
                self.render();
                return;
            }
            const rect = canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left, my = e.clientY - rect.top;
            const hit = self._findHit(mx, my);
            if (hit !== self._hovered) {
                self._hovered = hit;
                self.render();
            }
            if (hit) {
                tooltip.style.display = 'block';
                tooltip.style.left = (mx + 15) + 'px';
                tooltip.style.top = (my - 30) + 'px';
                const d = hit.data;
                if (hit.type === 'city') {
                    tooltip.innerHTML = `<b>城池 #${escHtml(String(d.No))}</b><br>坐标: (${escHtml(String(d.X))}, ${escHtml(String(d.Y))})`;
                } else if (hit.type === 'building') {
                    tooltip.innerHTML = `<b>建筑 #${escHtml(String(d.No))} ${escHtml(d.Name||'')}</b><br>坐标: (${escHtml(String(d.X))}, ${escHtml(String(d.Y))}) 类型:${escHtml(String(d.Type))}`;
                } else if (hit.type === 'bridge') {
                    tooltip.innerHTML = `<b>桥梁 #${escHtml(String(d.No))}</b><br>坐标: (${escHtml(String(d.X))}, ${escHtml(String(d.Y))}) ${escHtml(String(d.Width))}×${escHtml(String(d.Height))}`;
                } else if (hit.type === 'roadblock') {
                    tooltip.innerHTML = `<b>路障 #${escHtml(String(d.No))}</b><br>坐标: (${escHtml(String(d.X))}, ${escHtml(String(d.Y))}) 类型:${escHtml(String(d.Type))}`;
                }
                canvas.style.cursor = 'pointer';
            } else {
                tooltip.style.display = 'none';
                const [wx, wy] = self._screenToWorld(mx, my);
                self._updateInfo();
                document.getElementById('mapVisInfo').innerHTML =
                    `坐标: (${wx}, ${wy}) — 已加载: ${self._cities.length} 城池 / ${self._buildings.length} 建筑 / ${self._bridges.length} 桥梁 / ${self._roadblocks.length} 路障`;
                canvas.style.cursor = 'crosshair';
            }
        };

        canvas.onmousedown = function(e) {
            if (e.button === 2) {
                e.preventDefault();
                self._dragging = true;
                self._dragStartX = e.clientX;
                self._dragStartY = e.clientY;
                self._dragStartPanX = self._panX;
                self._dragStartPanY = self._panY;
                canvas.style.cursor = 'grabbing';
                return;
            }
        };

        canvas.onmouseup = function(e) {
            if (self._dragging) {
                self._dragging = false;
                canvas.style.cursor = 'crosshair';
                return;
            }
            if (e.button === 0) {
                const rect = canvas.getBoundingClientRect();
                const mx = e.clientX - rect.left, my = e.clientY - rect.top;
                const hit = self._findHit(mx, my);
                if (hit) {
                    const d = hit.data;
                    const tabMap = { city: 'citypos', building: 'buildingpos', bridge: 'sfbridge', roadblock: 'sfroadblock' };
                    const editorMap = { city: 'cityposEditor', building: 'buildingposEditor', bridge: 'sfbridgeEditor', roadblock: 'sfroadblockEditor' };
                    const tab = tabMap[hit.type];
                    const editorName = editorMap[hit.type];
                    if (tab && window[editorName]) {
                        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                        const navItem = document.querySelector(`[data-tab="${tab}"]`);
                        if (navItem) navItem.classList.add('active');
                        const tc = document.getElementById(tab);
                        if (tc) tc.classList.add('active');
                        const editor = window[editorName];
                        if (editor.load) {
                            editor.load().then(() => {
                                if (editor._selectByNo) editor._selectByNo(parseInt(d.No));
                            });
                        }
                    }
                } else {
                    const [wx, wy] = self._screenToWorld(mx, my);
                    document.getElementById('mapVisInfo').innerHTML =
                        `<b style="color:#ffd700;">点击坐标: (${wx}, ${wy})</b> — 已加载: ${self._cities.length} 城池 / ${self._buildings.length} 建筑 / ${self._bridges.length} 桥梁 / ${self._roadblocks.length} 路障`;
                    navigator.clipboard.writeText(`${wx}, ${wy}`).catch(() => {});
                }
            }
        };

        canvas.onmouseleave = function() {
            if (self._dragging) {
                self._dragging = false;
                canvas.style.cursor = 'crosshair';
            }
            self._hovered = null;
            tooltip.style.display = 'none';
            self.render();
            self._updateInfo();
        };

        // 滚轮缩放
        canvas.onwheel = function(e) {
            e.preventDefault();
            const zoomSlider = document.getElementById('mv_zoom');
            let zoom = parseFloat(zoomSlider.value) || 1;
            const delta = e.deltaY > 0 ? -0.1 : 0.1;
            zoom = Math.max(0.5, Math.min(3, zoom + delta));
            zoomSlider.value = zoom;
            document.getElementById('mv_zoomLabel').textContent = zoom.toFixed(1) + 'x';
            self.render();
        };

        // 全局右键菜单禁用
        canvas.oncontextmenu = function(e) { e.preventDefault(); };

        // 全局 mouseup 处理拖拽释放
        document.addEventListener('mouseup', function(e) {
            if (self._dragging) {
                self._dragging = false;
                canvas.style.cursor = 'crosshair';
            }
        });
    }
};

// ============================================================
// 路障属性编辑器 (SFRoadBlock.ini)
// ============================================================
const sfroadblockEditor = createIniEditor('sr', 'SFRoadBlock', 'sfroadblockCount', 'sfroadblockList',
    'emptySFRoadBlockDetail', 'sfroadblockDetailContent',
    ['No','X','Y','Type']);

// ============================================================
// 路障位置编辑器 (SFRoadBlockPos.ini)
// ============================================================
const sfroadblockposEditor = createIniEditor('sp', 'SFRoadBlockPos', 'sfroadblockposCount', 'sfroadblockposList',
    'emptySFRoadBlockPosDetail', 'sfroadblockposDetailContent',
    ['No','X1','Y1','X2','Y2','Count']);

// ============================================================
// 战场变量编辑器 (Var.ini)
// ============================================================
const varEditor = createIniEditor('vr', 'Var', 'varCount', 'varList',
    'emptyVarDetail', 'varDetailContent',
    ['No','Name','Value']);

// ============================================================
// 字体配置编辑器 (font.ini)
// ============================================================
const fontEditor = createIniEditor('fn', 'Font', 'fontCount', 'fontList',
    'emptyFontDetail', 'fontDetailContent',
    ['No','Name','Size','Bold']);

// ============================================================
// 系统配置编辑器 (system.ini)
// ============================================================
const systeminiEditor = createIniEditor('si', 'SystemIni', 'systeminiCount', 'systeminiList',
    'emptySystemIniDetail', 'systeminiDetailContent',
    ['No','Key','Value']);

const formatEditor = createIniEditor('fmt', 'Format', 'formatCount', 'formatList',
    'emptyFormatDetail', 'formatDetailContent',
    ['No','Name','1','2','3','4','5','P1','P2','P3','P4','P5','SoldierOffendAdjust','SoldierDefendAdjust','SoldierSpeedAdjust','Attrib','IsUsed']);

const chessformatEditor = createIniEditor('cf', 'ChessFormat', 'chessformatCount', 'chessformatList',
    'emptyChessformatDetail', 'chessformatDetailContent',
    ['NO','Name','Type','1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16','17','18','19','20','21','22','23','24','25','26','27','28','29','30','31','32','33','34','35','36','37','38','39','40','41','42','43','44','45','46','47','48','49','50','51','52','53','54','55','56','57','58','59','60','61','62','63','64','65','66','67','68','69','70','71','72','73','74','75','76','77','78','79','80']);

// ============================================================
// AI 行为整合面板
// ============================================================
const aiPanel = {
    _visible: false,
    _params: null,

    _presets: {
        aggressive: {
            label: '激进AI (频繁出兵, 武将快速升级)',
            values: {
                '121': { Int01: '80' },     // AI搜索速率大幅提升
                '133': { Float00: '3.0', Float01: '2.0', Float02: '1.5' }, // AI战斗经验倍率
                '134': { Int00: '100', Int01: '100', Int02: '0' },  // AI不撤退
                '137': { Int00: '80', Float00: '2.5', Float01: '2.0', Float02: '1.5' }, // 经验倍率
                '139': { Int07: '0', Int08: '10', Float05: '0.8', Float06: '-0.5' }, // 频繁出兵
                '140': { Int00: '1', Int01: '2' },  // 战后外交减少值降低
            },
        },
        balanced: {
            label: '平衡AI (默认行为)',
            values: {
                '121': { Int01: '40' },
                '133': { Float00: '1.5', Float01: '1.2', Float02: '0.9' },
                '134': { Int00: '400', Int01: '450', Int02: '20' },
                '137': { Int00: '50', Float00: '1.5', Float01: '1.2', Float02: '1.0' },
                '139': { Int07: '-100', Int08: '-5', Float05: '1.5', Float06: '0.75' },
                '140': { Int00: '3', Int01: '5' },
            },
        },
        passive: {
            label: '保守AI (减少出兵, 降低难度)',
            values: {
                '121': { Int01: '20' },
                '133': { Float00: '0.8', Float01: '0.6', Float02: '0.4' },
                '134': { Int00: '800', Int01: '900', Int02: '50' },
                '137': { Int00: '30', Float00: '0.8', Float01: '0.6', Float02: '0.5' },
                '139': { Int07: '-300', Int08: '-50', Float05: '3.0', Float06: '1.5' },
                '140': { Int00: '8', Int01: '12' },
            },
        },
    },

    _paramMeta: {
        '121': { name: '搜索人才/物品', icon: '🔍', desc: 'AI搜索成功率(Int01=AI)' },
        '133': { name: 'AI战斗经验倍率', icon: '⚔', desc: '各难度AI模拟战斗经验倍率' },
        '134': { name: 'AI撤退条件', icon: '🏃', desc: '战力比阈值(Int00-02, 全0=不退)' },
        '137': { name: '武将经验增长', icon: '📈', desc: '未出战武将自动经验增长' },
        '139': { name: 'AI出兵机率', icon: '⚡', desc: '外交度与出兵决策(Int07/08)' },
        '140': { name: '战后外交减少', icon: '🤝', desc: '开战后外交惩罚值' },
        '238': { name: 'NPC/事件部队', icon: '👻', desc: '大地图NPC数量(Int01)' },
    },

    toggle() {
        this._visible = !this._visible;
        document.getElementById('aiPanel').style.display = this._visible ? 'block' : 'none';
        const logicPanel = document.getElementById('aiLogicPanel');
        if (logicPanel) logicPanel.style.display = this._visible ? 'block' : 'none';
        if (this._visible) this.refresh();
    },

    refresh() {
        if (!variableEditor.data || !variableEditor.data.length) {
            document.getElementById('aiPanelContent').innerHTML = '<div class="hint" style="grid-column:1/-1;">请先加载 Variable.ini 数据</div>';
            return;
        }
        this._params = {};
        // 构建参数索引
        variableEditor.data.forEach(p => {
            const no = String(p.No || '');
            if (this._paramMeta[no]) this._params[no] = p;
        });
        this.render();
    },

    render() {
        const container = document.getElementById('aiPanelContent');
        if (!container) return;
        let html = '';
        const keys = ['121', '133', '134', '137', '139', '140', '238'];
        keys.forEach(no => {
            const meta = this._paramMeta[no];
            const p = this._params[no];
            const findById = (id) => { const el = variableEditor.data.find(d => String(d.No) === no); return el ? el[id] || '' : ''; };
            if (!p) {
                html += `<div class="card" style="padding:8px;opacity:0.5;">
                    <b>${meta.icon} ${meta.name} (No.${no})</b>
                    <div class="hint">未找到此参数，请新建 No=${no} 的条目</div>
                </div>`;
                return;
            }
            const fields = Object.keys(p).filter(k => k.match(/^(Int|Float)\d+/));
            html += `<div class="card" style="padding:8px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                    <b>${meta.icon} ${meta.name} (No.${no})</b>
                    <span style="font-size:10px;color:var(--text-muted);">${meta.desc}</span>
                </div>
                <div style="display:flex;flex-wrap:wrap;gap:4px;">
                    ${fields.map(f => `<div style="display:flex;align-items:center;gap:2px;font-size:11px;">
                        <span style="color:var(--text-muted);min-width:42px;">${f}</span>
                        <input type="text" value="${p[f]||''}" style="width:60px;padding:2px 4px;font-size:11px;border:1px solid var(--border);border-radius:3px;background:var(--bg-card);color:var(--ink);" onchange="aiPanel._setVal('${no}','${f}',this.value)">
                    </div>`).join('')}
                </div>
            </div>`;
        });
        container.innerHTML = html || '<div class="hint">无AI参数数据</div>';
    },

    _setVal(no, field, val) {
        const p = variableEditor.data.find(d => String(d.No) === no);
        if (p) {
            p[field] = val;
            this._params[no] = p;
        }
    },

    applyPreset(type) {
        if (!variableEditor.data || !variableEditor.data.length) { showToast('请先加载 Variable.ini', 'info'); return; }
        const preset = this._presets[type];
        if (!preset) return;
        if (!confirm(`确认应用预设: ${preset.label}?\n\n这将修改 Variable.ini 中 ${Object.keys(preset.values).length} 个AI参数的值。`)) return;
        Object.entries(preset.values).forEach(([no, fields]) => {
            const p = variableEditor.data.find(d => String(d.No) === no);
            if (p) {
                Object.entries(fields).forEach(([k, v]) => { p[k] = v; });
                this._params[no] = p;
            }
        });
        this.render();
        showToast(`已应用预设: ${preset.label}`, 'success');
    },

    async saveAll() {
        if (!variableEditor.save) { showToast('variableEditor 未初始化', 'error'); return; }
        await variableEditor.save();
        showToast('AI参数已保存', 'success');
    },
};

// ============================================================
// 全局游戏参数编辑器 (Variable.ini)
// ============================================================
const variableEditor = createIniEditor('ge', 'GlobalParams', 'variableCount', 'variableList',
    'emptyVariableDetail', 'variableDetailContent',
    ['No','Name','EnumName','Int00','Int01','Int02','Int03','Int04','Int05','Int06','Int07','Int08','Int09','Float00','Float01','Float02','Float03','Float04','Float05','Float06','Float07','Float08','Float09']);

// ============================================================
// Variable.ini 分类标签页
// ============================================================
const VariableCats = {
    _currentCat: 'all',
    _ref: null,
    _fullRef: null,
    _allData: [],

    async _loadRef() {
        if (this._ref) return this._ref;
        try {
            const res = await fetch('data/variable_ref.json');
            this._ref = await res.json();
            return this._ref;
        } catch(e) {
            console.warn('Variable ref not loaded:', e);
            this._ref = { categories: {} };
            return this._ref;
        }
    },

    async _loadFullRef() {
        if (this._fullRef) return this._fullRef;
        try {
            const res = await fetch('data/variable_full_ref.json');
            this._fullRef = await res.json();
            return this._fullRef;
        } catch(e) {
            console.warn('Variable full ref not loaded:', e);
            this._fullRef = { params: {} };
            return this._fullRef;
        }
    },

    filter(cat) {
        this._currentCat = cat;
        document.querySelectorAll('#varCatTabs .var-cat-tab').forEach(b => {
            b.classList.toggle('active', b.textContent === (cat === 'all' ? '全部' : b.textContent));
        });
        this._rebuildList();
    },

    async jumpTo(cat) {
        // Switch to variable editor tab and filter by category
        const navItem = document.querySelector('[data-tab="variableEditor"]');
        if (navItem) navItem.click();
        // Small delay to let the tab switch and load
        await new Promise(r => setTimeout(r, 150));
        await this._loadRef();
        this._currentCat = cat;
        this._rebuildList();
        // Update tab buttons
        document.querySelectorAll('#varCatTabs .var-cat-tab').forEach(b => {
            b.classList.toggle('active', b.textContent === cat || (cat === 'all' && b.textContent === '全部'));
        });
    },

    async _rebuildList() {
        await this._loadRef();
        const listEl = document.getElementById('variableList');
        if (!listEl) return;

        const ref = this._ref;
        const allKeys = variableEditor._data || [];
        this._allData = allKeys;

        let filtered = allKeys;
        if (this._currentCat !== 'all' && ref && ref.categories && ref.categories[this._currentCat]) {
            const catData = ref.categories[this._currentCat];
            if (catData.crossFile && catData.params && catData.params['Variable.ini'] && catData.params['Variable.ini'].refs) {
                // AI综合等跨文件分类：从 Variable.ini.refs 中提取编号
                const catNos = catData.params['Variable.ini'].refs.split(',');
                filtered = allKeys.filter(item => item && catNos.includes(String(item.No)));
            } else if (catData.params) {
                const catNos = Object.keys(catData.params);
                filtered = allKeys.filter(item => item && catNos.includes(String(item.No)));
            }
        }

        document.getElementById('variableCount').textContent = filtered.length;

        // Build HTML manually
        let html = '';
        filtered.forEach((item, idx) => {
            if (!item) return;
            const no = item.No || '';
            const name = item.Name || '';
            const catInfo = this._getCatInfo(item.No);
            const catLabel = catInfo ? `<span class="var-cat-label">${catInfo.cat}</span>` : '';
            html += `<div class="item-btn" data-idx="${idx}" data-no="${no}"
                onclick="VariableCats._selectItem(${idx},'${no}')">
                <span class="item-no">${no}</span>
                <span class="item-name">${name || '未命名'}</span>
                ${catLabel}
            </div>`;
        });
        listEl.innerHTML = html;
    },

    _getCatInfo(no) {
        const ref = this._ref;
        if (!ref || !ref.categories) return null;
        for (const [cat, catData] of Object.entries(ref.categories)) {
            if (catData.crossFile) {
                // AI综合等跨文件分类：检查 refs 列表
                const vini = catData.params && catData.params['Variable.ini'];
                if (vini && vini.refs && vini.refs.split(',').map(s => s.trim()).includes(String(no))) {
                    return { cat, ...catData };
                }
            }
            if (catData.params && catData.params[String(no)]) {
                return { cat, ...catData.params[String(no)] };
            }
        }
        return null;
    },

    _selectItem(idx, no) {
        variableEditor._select(idx);
        const catInfo = this._getCatInfo(no);
        const descBox = document.getElementById('varDescBox');
        if (descBox) {
            if (catInfo && (catInfo.desc || catInfo.detail)) {
                descBox.textContent = catInfo.desc || catInfo.detail;
                descBox.style.display = 'block';
            } else {
                descBox.style.display = 'none';
            }
        }
        // Show field-level hints from variable_ref.json categories
        if (catInfo && !catInfo.crossFile) {
            this._showFieldHints(catInfo);
        } else {
            document.querySelectorAll('.var-field-hint').forEach(el => el.textContent = '');
        }
        // Also show sub-field comments from variable_full_ref.json
        this._showFullRefHints(no);
    },

    async _showFullRefHints(no) {
        await this._loadFullRef();
        const fullRef = this._fullRef;
        if (!fullRef || !fullRef.params) return;
        const param = fullRef.params[String(no)];
        if (!param) return;

        const prefix = 'ge_';
        const allFields = { ...(param.ints || {}), ...(param.floats || {}) };
        for (const [fieldName, fieldData] of Object.entries(allFields)) {
            const el = document.getElementById(prefix + fieldName);
            if (!el) continue;
            const comment = fieldData.comment || '';
            const value = fieldData.value || '';
            // Find or create hint element
            let hintEl = el.parentElement.querySelector('.var-full-hint');
            if (!hintEl) {
                hintEl = document.createElement('div');
                hintEl.className = 'var-full-hint';
                hintEl.style.cssText = 'font-size:10px;color:var(--accent);margin-top:1px;line-height:1.3;';
                el.parentElement.appendChild(hintEl);
            }
            if (comment) {
                hintEl.textContent = comment;
                hintEl.style.display = 'block';
                // Also highlight the input with a subtle border
                el.style.borderColor = 'var(--accent)';
                el.style.borderWidth = '1px';
                el.title = `原版默认值: ${value}\n${comment}`;
            } else if (value) {
                hintEl.textContent = `原版默认: ${value}`;
                hintEl.style.display = 'block';
                el.title = `原版默认值: ${value}`;
            } else {
                hintEl.style.display = 'none';
                el.style.borderColor = '';
                el.title = '';
            }
        }
    },

    _showFieldHints(catInfo) {
        // Clear existing hints
        document.querySelectorAll('.var-field-hint').forEach(el => el.textContent = '');
        if (!catInfo || !catInfo.fields) return;

        const prefix = 'ge_';
        for (const [fieldName, hint] of Object.entries(catInfo.fields)) {
            const el = document.getElementById(prefix + fieldName);
            if (!el) continue;
            // Find or create hint element after the input
            let hintEl = el.parentElement.querySelector('.var-field-hint');
            if (!hintEl) {
                hintEl = document.createElement('div');
                hintEl.className = 'var-field-hint';
                el.parentElement.appendChild(hintEl);
            }
            hintEl.textContent = hint;
        }
    }
};

// ============================================================
// 参考数据服务 — 加载 xlsx 数据供各编辑器查询
// ============================================================
const ReferenceData = {
    _cache: {},
    _status: 'idle', // idle | loading | ready | error

    async _loadXlsx(name) {
        if (this._cache[name]) return this._cache[name];
        try {
            const res = await fetch(`data/xlsx_${name}.json`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            this._cache[name] = data;
            return data;
        } catch(e) {
            console.warn(`ReferenceData: ${name} not loaded:`, e.message);
            this._cache[name] = null;
            return null;
        }
    },

    async _loadChangfeng() {
        if (this._cache['_changfeng']) return this._cache['_changfeng'];
        try {
            const res = await fetch('data/changfeng_xls_ref.json');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            this._cache['_changfeng'] = data;
            return data;
        } catch(e) {
            this._cache['_changfeng'] = null;
            return null;
        }
    },

    /** 根据物品编号查找原版物品数据 */
    async lookupThing(no) {
        const data = await this._loadXlsx('Thing物品');
        if (!data) return null;
        for (const [sheetName, sheet] of Object.entries(data)) {
            const headers = sheet.headers || [];
            const noIdx = headers.findIndex(h => h.includes('No') || h === '编号');
            if (noIdx < 0) continue;
            for (const row of (sheet.sample_rows || [])) {
                if (String(row[noIdx]) === String(no)) {
                    const result = {};
                    headers.forEach((h, i) => { result[h] = row[i] || ''; });
                    return result;
                }
            }
        }
        return null;
    },

    /** 根据武将编号查找原版武将数据 */
    async lookupGeneral(no) {
        const data = await this._loadXlsx('General01全武将内容');
        if (!data) return null;
        for (const [sheetName, sheet] of Object.entries(data)) {
            const headers = sheet.headers || [];
            const noIdx = headers.findIndex(h => h.includes('No') || h === '编号');
            if (noIdx < 0) continue;
            for (const row of (sheet.sample_rows || [])) {
                if (String(row[noIdx]) === String(no)) {
                    const result = {};
                    headers.forEach((h, i) => { result[h] = row[i] || ''; });
                    return result;
                }
            }
        }
        return null;
    },

    /** 根据兵种编号查找原版兵种数据 */
    async lookupSoldier(no) {
        const data = await this._loadXlsx('Soldier兵种+召唤');
        if (!data) return null;
        for (const [sheetName, sheet] of Object.entries(data)) {
            const headers = sheet.headers || [];
            const noIdx = headers.findIndex(h => h.includes('No') || h === '编号');
            if (noIdx < 0) continue;
            for (const row of (sheet.sample_rows || [])) {
                if (String(row[noIdx]) === String(no)) {
                    const result = {};
                    headers.forEach((h, i) => { result[h] = row[i] || ''; });
                    return result;
                }
            }
        }
        return null;
    },

    /** 获取 changfeng.xls 中某个 Sheet 的数据 */
    async getChangfengSheet(sheetName) {
        const data = await this._loadChangfeng();
        if (!data) return null;
        return data[sheetName] || null;
    },

    /** 在物品编辑器中显示参考数据对比 */
    async showThingRef(thingNo) {
        if (!thingNo) return;
        const ref = await this.lookupThing(thingNo);
        const panel = document.getElementById('thingRefPanel');
        if (!panel) return;
        if (!ref) {
            panel.innerHTML = '<div style="padding:8px;font-size:12px;color:var(--text-muted);">未找到原版参考数据</div>';
            return;
        }
        let html = '<div style="padding:8px;"><h4 style="margin:0 0 6px;font-size:13px;">原版参考数据</h4><table style="width:100%;font-size:11px;border-collapse:collapse;">';
        const keyFields = ['Name', 'Type', 'Price', 'Level', 'IsRare', 'Count', 'ScriptNo', 'Str', 'Int', 'HP', 'MP', 'Speed', 'Loyal', 'Rate', 'IconID'];
        for (const key of keyFields) {
            if (ref[key] !== undefined && ref[key] !== '') {
                html += `<tr><td style="padding:2px 4px;color:var(--text-muted);">${key}</td><td style="padding:2px 4px;font-weight:bold;">${ref[key]}</td></tr>`;
            }
        }
        html += '</table></div>';
        panel.innerHTML = html;
    },

    /** 在武将编辑器中显示参考数据对比 */
    async showGeneralRef(generalNo) {
        if (!generalNo) return;
        const ref = await this.lookupGeneral(generalNo);
        const panel = document.getElementById('generalRefPanel');
        if (!panel) return;
        if (!ref) {
            panel.innerHTML = '<div style="padding:8px;font-size:12px;color:var(--text-muted);">未找到原版参考数据</div>';
            return;
        }
        let html = '<div style="padding:8px;"><h4 style="margin:0 0 6px;font-size:13px;">原版参考数据</h4><table style="width:100%;font-size:11px;border-collapse:collapse;">';
        const keyFields = ['Name', 'WStr', 'Int', 'HP', 'MP', 'Morale', 'Loyal', 'Sex', 'Race', 'Weapon', 'Horse', 'BFSoldier', 'Formation', 'AppearYear', 'City1', 'IsFamous'];
        for (const key of keyFields) {
            if (ref[key] !== undefined && ref[key] !== '') {
                html += `<tr><td style="padding:2px 4px;color:var(--text-muted);">${key}</td><td style="padding:2px 4px;font-weight:bold;">${ref[key]}</td></tr>`;
            }
        }
        html += '</table></div>';
        panel.innerHTML = html;
    },
};

// ============================================================
// 全局数据搜索
// ============================================================
const globalSearch = {
    async execute() {
        const query = document.getElementById('gsQuery').value.trim();
        const type = document.getElementById('gsSearchType').value;
        if (!query) { showToast('请输入搜索内容', 'warning'); return; }
        const resultsDiv = document.getElementById('gsResults');
        resultsDiv.innerHTML = '<div style="padding:20px;text-align:center;">搜索中...</div>';
        try {
            const res = await pyApi('globalSearch', query, type);
            if (!res || !res.success) {
                resultsDiv.innerHTML = `<div style="padding:20px;color:var(--text-muted);">${res ? res.message || '搜索失败' : '搜索失败'}</div>`;
                return;
            }
            if (!res.results || res.results.length === 0) {
                resultsDiv.innerHTML = `<div style="padding:20px;color:var(--text-muted);">未找到匹配 "${query}" 的结果</div>`;
                return;
            }
            let html = `<div style="padding:8px;color:var(--accent);">找到 ${res.totalMatches} 条匹配，分布在 ${res.results.length} 个文件中</div>`;
            for (const file of res.results) {
                html += `<details style="margin:4px 0;background:var(--bg-secondary);border-radius:6px;padding:8px;">
                    <summary style="cursor:pointer;font-weight:bold;">${file.file} (${file.count}条)</summary>`;
                for (const m of file.matches) {
                    html += `<div style="padding:4px 8px;margin:2px 0;background:var(--bg);border-radius:4px;font-size:12px;font-family:monospace;">
                        <b>No=${m.no}</b> ${m.name ? '| '+m.name : ''}
                        <pre style="margin:4px 0 0;font-size:11px;max-height:100px;overflow-y:auto;white-space:pre-wrap;">${m.entry}</pre>
                    </div>`;
                }
                html += '</details>';
            }
            resultsDiv.innerHTML = html;
        } catch(e) {
            resultsDiv.innerHTML = `<div style="padding:20px;color:var(--danger);">搜索出错: ${e}</div>`;
        }
    }
};

// ============================================================
// 游戏平衡分析
// ============================================================
const balanceAnalysis = {
    async run() {
        const resultsDiv = document.getElementById('balanceResults');
        resultsDiv.innerHTML = '<div style="padding:20px;text-align:center;">分析中...</div>';
        try {
            const res = await pyApi('balanceAnalysis', 'all');
            if (!res || !res.success) {
                resultsDiv.innerHTML = `<div style="padding:20px;color:var(--text-muted);">${res ? res.message || '分析失败' : '分析失败'}</div>`;
                return;
            }
            const a = res.analysis;
            let html = '';
            if (a.generals && !a.generals.error) {
                html += this._renderCard('武将属性', a.generals, [
                    {key:'wstr',label:'武力'},{key:'intelligence',label:'智力'},{key:'hp',label:'体力'},{key:'mp',label:'技力'}
                ]);
            }
            if (a.soldiers && !a.soldiers.error) {
                html += this._renderCard('兵种属性', a.soldiers, [
                    {key:'hp',label:'生命'},{key:'atk',label:'攻击'},{key:'def',label:'防御'}
                ]);
            }
            if (a.things && !a.things.error) {
                html += this._renderCard('物品属性', a.things, [
                    {key:'str',label:'武力加成'},{key:'int',label:'智力加成'},{key:'hp',label:'体力加成'},{key:'price',label:'价格'}
                ]);
                if (a.things.type_distribution) {
                    html += `<div class="stat-card"><h4>物品类型分布</h4><table style="font-size:12px;">`;
                    for (const [t,c] of Object.entries(a.things.type_distribution)) {
                        html += `<tr><td>Type ${t}</td><td style="text-align:right;">${c} 件</td></tr>`;
                    }
                    html += '</table></div>';
                }
            }
            resultsDiv.innerHTML = html || '<div style="padding:20px;">无分析数据</div>';
        } catch(e) {
            resultsDiv.innerHTML = `<div style="padding:20px;color:var(--danger);">分析出错: ${e}</div>`;
        }
    },
    _renderCard(title, data, fields) {
        let html = `<div class="stat-card" style="background:var(--bg-secondary);border-radius:8px;padding:12px;border:1px solid var(--border);">
            <h4 style="margin:0 0 8px;">${title} (${data.count}条)</h4><table style="width:100%;font-size:12px;border-collapse:collapse;">
            <tr style="color:var(--text-muted);"><td>属性</td><td style="text-align:right;">最低</td><td style="text-align:right;">最高</td><td style="text-align:right;">平均</td></tr>`;
        for (const f of fields) {
            const d = data[f.key];
            if (d) {
                html += `<tr><td>${f.label}</td><td style="text-align:right;">${d.min}</td><td style="text-align:right;color:var(--accent);">${d.max}</td><td style="text-align:right;">${d.avg}</td></tr>`;
            }
        }
        html += '</table></div>';
        return html;
    }
};

// ============================================================
// Hook into variableEditor's load and select to use categorized view
const _origVarLoad = variableEditor.load;
variableEditor.load = async function() {
    await _origVarLoad.call(this);
    VariableCats._allData = this._data || [];
    VariableCats._rebuildList();
};

const _origVarSelect = variableEditor._select;
variableEditor._select = function(idx) {
    _origVarSelect.call(this, idx);
    const item = this._data && this._data[idx];
    if (item) {
        VariableCats._selectItem(idx, item.No);
    }
};

// ============================================================
// 编辑器包装器 — 为缺少 JS 对象的编辑器提供 changed 追踪
// ============================================================

// UI 子系统编辑器
const uisubsystemEditor = {
    changed: false,
    _currentSub: 'ui_buttonstyle',
    _data: [],
    _selectedIdx: -1,

    // 字段说明映射
    _fieldRefs: {
        'ui_buttonstyle': {
            title: '按键样式 (ButtonStyle.ini)',
            desc: '控制游戏中所有按钮的正常/悬停/按下/禁用状态的样式。每行定义一种按钮风格。',
            fields: {
                'ID': '按钮样式ID',
                'Name': '样式名称',
                'Normal': '正常状态颜色/样式',
                'Hover': '鼠标悬停时颜色/样式',
                'Pressed': '按下时颜色/样式',
                'Disabled': '禁用时颜色/样式',
            }
        },
        'ui_fontsize': {
            title: '字体大小 (FontSize.ini)',
            desc: '控制游戏中各种界面文字的字体大小。每行定义一种字体规格。',
            fields: {
                'ID': '字体规格ID',
                'Name': '字体名称/用途',
                'Size': '字体大小(像素)',
            }
        },
        'ui_framestyle': {
            title: '菜单边框 (FrameStyle.ini)',
            desc: '控制游戏中菜单窗口的边框样式。包括四边和四角的尺寸/样式。',
            fields: {
                'ID': '边框样式ID',
                'Name': '边框名称',
                'Up': '上边框参数',
                'Down': '下边框参数',
                'Left': '左边框参数',
                'Right': '右边框参数',
                'UpLeft': '左上角参数',
                'UpRight': '右上角参数',
                'DownLeft': '左下角参数',
                'DownRight': '右下角参数',
            }
        },
        'ui_liststyle': {
            title: '列表样式 (ListStyle.ini)',
            desc: '控制游戏中列表控件的外观，包括滚动条和列表项高度。',
            fields: {
                'ID': '列表样式ID',
                'Name': '样式名称',
                'ScrollBar': '滚动条样式参数',
                'ItemHeight': '列表项高度(像素)',
            }
        },
        'ui_shapeui': {
            title: 'UI形状 (Shape.ini)',
            desc: '控制游戏中UI元素(按钮/窗口/图标)的Shape贴图映射。关联Shape/SHP文件。',
            fields: {
                'ID': 'Shape ID',
                'Name': 'UI元素名称',
                'X': 'X坐标/位置',
                'Y': 'Y坐标/位置',
                'Width': '宽度',
                'Height': '高度',
            }
        },
        'ui_textstyle': {
            title: '对齐方式 (TextStyle.ini)',
            desc: '控制游戏中文本的对齐方式、行间距、缩进等排版参数。',
            fields: {
                'ID': '文本样式ID',
                'Name': '样式名称',
                'Align': '对齐方式(左/中/右)',
                'LineHeight': '行间距',
                'Indent': '缩进量',
            }
        },
        'ui_wincolor': {
            title: '窗口颜色 (WinColor.ini)',
            desc: '控制游戏中各种窗口的背景颜色(RGBA格式)。每行定义一种窗口配色。',
            fields: {
                'ID': '配色ID',
                'Name': '配色名称/用途',
                'R': '红色分量(0-255)',
                'G': '绿色分量(0-255)',
                'B': '蓝色分量(0-255)',
                'Alpha': '透明度(0-255, 255=不透明)',
            }
        },
        'ui_winmainmenu': {
            title: '主菜单位置 (WinMainMenu.ini)',
            desc: '控制游戏主菜单各按钮的位置和大小。每行定义一个菜单项的区域。',
            fields: {
                'ID': '菜单项ID',
                'Name': '菜单项名称',
                'X': 'X坐标',
                'Y': 'Y坐标',
                'Width': '宽度',
                'Height': '高度',
                'FontX': '文字X偏移',
                'FontY': '文字Y偏移',
            }
        },
    },

    async load() {
        const sub = this._currentSub;
        const apiMap = {
            'ui_buttonstyle': 'ButtonStyle', 'ui_fontsize': 'FontSize',
            'ui_framestyle': 'FrameStyle', 'ui_liststyle': 'ListStyle',
            'ui_shapeui': 'ShapeUI', 'ui_textstyle': 'TextStyle',
            'ui_wincolor': 'WinColor', 'ui_winmainmenu': 'WinMainMenu'
        };
        const apiName = apiMap[sub] || 'ButtonStyle';
        const res = await pyApi('load' + apiName);
        if (res.success) {
            this._data = res.data || [];
            this._selectedIdx = -1;
            this._render();
            this._showDesc();
            this._hideDetail();
            document.getElementById('uisubsSummary').textContent = '共 ' + this._data.length + ' 条';
        }
        return res;
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        const sub = this._currentSub;
        const apiMap = {
            'ui_buttonstyle': 'ButtonStyle', 'ui_fontsize': 'FontSize',
            'ui_framestyle': 'FrameStyle', 'ui_liststyle': 'ListStyle',
            'ui_shapeui': 'ShapeUI', 'ui_textstyle': 'TextStyle',
            'ui_wincolor': 'WinColor', 'ui_winmainmenu': 'WinMainMenu'
        };
        const apiName = apiMap[sub] || 'ButtonStyle';
        const res = await pyApi('save' + apiName, this._data);
        if (res.success) { this.changed = false; updateSaveBtnState('uisubs_saveBtn', false); }
        if (res.message) showToast(res.message, res.success ? 'success' : 'error');
        return res;
    },

    search(keyword) {
        const items = document.querySelectorAll('#uisubs_list .item-card');
        items.forEach(el => {
            const text = el.textContent.toLowerCase();
            el.style.display = (!keyword || text.includes(keyword.toLowerCase())) ? '' : 'none';
        });
    },

    _showDesc() {
        const ref = this._fieldRefs[this._currentSub];
        const descBox = document.getElementById('uisubsDesc');
        if (descBox && ref) {
            descBox.innerHTML = `<strong>${escHtml(ref.title)}</strong>: ${escHtml(ref.desc)}`;
            descBox.style.display = 'block';
        }
    },

    _hideDetail() {
        const detail = document.getElementById('uisubs_detail');
        if (detail) detail.style.display = 'none';
        this._selectedIdx = -1;
    },

    _render() {
        const listEl = document.getElementById('uisubs_list');
        if (!listEl) return;
        const ref = this._fieldRefs[this._currentSub];
        listEl.innerHTML = '';
        this._data.forEach((item, idx) => {
            const card = document.createElement('div');
            card.className = 'item-card';
            const name = item.Name || item.name || ('#' + (item.ID || item.No || idx));
            // 窗口颜色特殊：显示颜色预览
            let colorPreview = '';
            if (this._currentSub === 'ui_wincolor' && item.R !== undefined) {
                const r = parseInt(item.R) || 0, g = parseInt(item.G) || 0, b = parseInt(item.B) || 0;
                const a = (parseInt(item.Alpha) || 255) / 255;
                colorPreview = `<span style="display:inline-block;width:16px;height:16px;border-radius:3px;background:rgba(${r},${g},${b},${a.toFixed(2)});border:1px solid var(--border);vertical-align:middle;margin-left:6px;"></span>`;
            }
            card.innerHTML = `<div class="item-card-header"><span class="item-name">${escHtml(name)}</span>${colorPreview}</div>`;
            card.onclick = () => this._select(idx);
            listEl.appendChild(card);
        });
    },

    select(idx) { this._select(idx); },

    _select(idx) {
        this._selectedIdx = idx;
        const item = this._data[idx];
        if (!item) return;
        const ref = this._fieldRefs[this._currentSub];
        const detail = document.getElementById('uisubs_detail');
        const fieldsEl = document.getElementById('uisubs_fields');
        if (!detail || !fieldsEl) return;
        detail.style.display = 'block';
        document.getElementById('uisubsDetailName').textContent = (item.Name || item.name || '#' + idx) + ' - 详情';
        let html = '';
        for (const [k, v] of Object.entries(item)) {
            const fieldLabel = (ref && ref.fields && ref.fields[k]) ? ref.fields[k] : k;
            const hintText = (ref && ref.fields && ref.fields[k]) ? ref.fields[k] : '';
            // 颜色相关字段添加颜色预览
            let extra = '';
            if (this._currentSub === 'ui_wincolor' && (k === 'R' || k === 'G' || k === 'B')) {
                const c = parseInt(v) || 0;
                const hex = c.toString(16).padStart(2, '0');
                extra = `<span style="display:inline-block;width:14px;height:14px;border-radius:2px;background:#${k === 'R' ? hex + '0000' : k === 'G' ? '00' + hex + '00' : '0000' + hex};border:1px solid var(--border);margin-left:6px;vertical-align:middle;"></span>`;
            }
            html += `<div class="form-row"><div class="form-group">
                <label title="${escHtml(hintText)}">${escHtml(fieldLabel)}</label>
                <input type="${k === 'R' || k === 'G' || k === 'B' || k === 'Alpha' ? 'number' : 'text'}" 
                    value="${escHtml(String(v != null ? v : ''))}" 
                    onchange="uisubsystemEditor._setField('${escHtml(k)}', this.value, ${idx})"
                    ${k === 'R' || k === 'G' || k === 'B' || k === 'Alpha' ? 'min="0" max="255"' : ''}>
                ${extra}
            </div></div>`;
        }
        fieldsEl.innerHTML = html;
    },

    _setField(key, val, idx) {
        if (this._data[idx]) {
            this._data[idx][key] = (key === 'R' || key === 'G' || key === 'B' || key === 'Alpha') ? parseInt(val) || 0 : val;
            this.changed = true;
            updateSaveBtnState('uisubs_saveBtn', true);
        }
    },
    _set(key, val) {
        if (this._selectedIdx >= 0 && this._data[this._selectedIdx]) {
            this._data[this._selectedIdx][key] = val;
            this.changed = true;
        }
    },

    addNew() {
        const newItem = {};
        const keys = this._data.length > 0 ? Object.keys(this._data[0]) : ['ID', 'Name'];
        keys.forEach(k => { newItem[k] = ''; });
        this._data.push(newItem);
        this._render();
        this._select(this._data.length - 1);
        this.changed = true;
        updateSaveBtnState('uisubs_saveBtn', true);
    }
};

// 配置扩展编辑器
const configextEditor = {
    changed: false,
    _currentSub: 'cfg_cdtable',
    _data: [],
    async load() {
        const sub = this._currentSub;
        const apiMap = {
            'cfg_cdtable': 'CDTable', 'cfg_citytext': 'CityText',
            'cfg_postpatch': 'PostPatch', 'cfg_thingscriptno': 'ThingScriptNo',
            'cfg_fontmultilang': 'FontMultiLang'
        };
        const apiName = apiMap[sub] || 'CDTable';
        const res = await pyApi('load' + apiName);
        if (res.success) { this._data = res.data || []; this._render(); }
        return res;
    },
    async save() {
        if (!(await validateBeforeSave())) return;
        const sub = this._currentSub;
        const apiMap = {
            'cfg_cdtable': 'CDTable', 'cfg_citytext': 'CityText',
            'cfg_postpatch': 'PostPatch', 'cfg_thingscriptno': 'ThingScriptNo',
            'cfg_fontmultilang': 'FontMultiLang'
        };
        const apiName = apiMap[sub] || 'CDTable';
        const res = await pyApi('save' + apiName, this._data);
        if (res.success) this.changed = false;
        if (res.message) showToast(res.message, res.success ? 'success' : 'error');
        return res;
    },
    search(keyword) {
        const items = document.querySelectorAll('#configext_list .item-card');
        items.forEach(el => {
            const text = el.textContent.toLowerCase();
            el.style.display = (!keyword || text.includes(keyword.toLowerCase())) ? '' : 'none';
        });
    },
    _render() {
        const listEl = document.getElementById('configext_list');
        if (!listEl) return;
        listEl.innerHTML = '';
        this._data.forEach((item, idx) => {
            const card = document.createElement('div');
            card.className = 'item-card';
            card.innerHTML = `<div class="item-card-header"><span class="item-name">${escHtml(item.Name || '#' + (item.No || idx))}</span></div>`;
            card.onclick = () => this._select(idx);
            listEl.appendChild(card);
        });
    },
    select(idx) { this._select(idx); },
    _select(idx) {
        const item = this._data[idx];
        document.getElementById('configext_empty').style.display = 'none';
        document.getElementById('configext_detail').style.display = 'block';
        const fieldsEl = document.getElementById('configext_fields');
        if (!fieldsEl || !item) return;
        let html = '';
        for (const [k, v] of Object.entries(item)) {
            html += `<div class="form-row"><div class="form-group"><label>${escHtml(k)}</label><input type="text" value="${escHtml(String(v != null ? v : ''))}" onchange="configextEditor._setField('${escHtml(k)}', this.value, ${idx})"></div></div>`;
        }
        fieldsEl.innerHTML = html;
    },
    _setField(key, val, idx) {
        if (this._data[idx]) this._data[idx][key] = val;
        this.changed = true;
    },
    addNew() {
        const newItem = {};
        const keys = this._data.length > 0 ? Object.keys(this._data[0]) : ['No', 'Name'];
        keys.forEach(k => { newItem[k] = ''; });
        this._data.push(newItem);
        this._render();
        this._select(this._data.length - 1);
        this.changed = true;
    }
};

// BMP→RAW 转换器
const bmp2rawEditor = {
    changed: false,
    async convert() {
        const path = document.getElementById('bmp2rawPath').value;
        if (!path) { showToast('请先选择BMP文件路径', 'error'); return; }
        const res = await pyApi('bmp2raw', path);
        document.getElementById('bmp2rawResult').textContent = res.message || '转换完成';
        if (res.message) showToast(res.message, res.success ? 'success' : 'error');
    }
};

// Shape 信息查看器
const shapeinfoEditor = {
    changed: false,
    async loadShape(path) {
        if (!path) return;
        const res = await pyApi('getShapeInfo', { path });
        if (res.success) {
            const info = res.data;
            const resultEl = document.getElementById('shapeInfoResult');
            if (resultEl) resultEl.innerHTML =
                `<pre style="font-size:11px;white-space:pre-wrap;">${escHtml(JSON.stringify(info, null, 2))}</pre>`;
        }
    }
};

// SHP 重命名工具
const shprenameEditor = {
    changed: false,
    async batchRename(pattern, mapping) {
        const res = await pyApi('shpBatchRename', pattern, mapping);
        if (res.message) showToast(res.message, res.success ? 'success' : 'error');
        return res;
    }
};

// 城池连接编辑器
const cityconnectEditor = {
    changed: false,
    _data: [],
    async load() {
        const res = await pyApi('loadCityConnect');
        if (res.success) { this._data = res.data || []; this._render(); }
        return res;
    },
    async save() {
        if (!(await validateBeforeSave())) return;
        const res = await pyApi('saveCityConnect', this._data);
        if (res.success) this.changed = false;
        if (res.message) showToast(res.message, res.success ? 'success' : 'error');
        return res;
    },
    _render() {
        const el = document.getElementById('cityconnect_list');
        if (!el) return;
        el.innerHTML = '';
        this._data.forEach((item, idx) => {
            const card = document.createElement('div');
            card.className = 'item-card';
            card.innerHTML = `<div class="item-card-header"><span class="item-name">${escHtml(item.Name || '#' + idx)}</span></div>`;
            card.onclick = () => this._select(idx);
            el.appendChild(card);
        });
    },
    _select(idx) {
        const item = this._data[idx];
        const fieldsEl = document.getElementById('cityconnect_fields');
        if (!fieldsEl || !item) return;
        let html = '';
        for (const [k, v] of Object.entries(item)) {
            html += `<div class="form-row"><div class="form-group"><label>${escHtml(k)}</label><input type="text" value="${escHtml(String(v != null ? v : ''))}" onchange="cityconnectEditor._setField('${escHtml(k)}', this.value, ${idx})"></div></div>`;
        }
        fieldsEl.innerHTML = html;
    },
    _setField(key, val, idx) {
        if (this._data[idx]) this._data[idx][key] = val;
        this.changed = true;
    }
};

// CSV 工具包装器
const csvtoolsEditor = (typeof csvTools !== 'undefined') ? csvTools : { changed: false };

// 自定义君主编辑器
const customLeaderEditor = {
    changed: false,
    _data: [],
    _selectedIdx: -1,
    async load() {
        const res = await pyApi('customLeaderLoad');
        if (res.success) {
            this._data = res.data || [];
            this._render();
            document.getElementById('customLeaderSummary').textContent = '共 ' + this._data.length + ' 个自定义君主';
        } else {
            showToast(res.message || '加载失败', 'error');
        }
        return res;
    },
    async save() {
        if (!(await validateBeforeSave())) return;
        const res = await pyApi('customLeaderSave', this._data);
        if (res.success) { this.changed = false; updateSaveBtnState('customLeaderSaveBtn', false); }
        if (res.message) showToast(res.message, res.success ? 'success' : 'error');
        return res;
    },
    addNew() {
        const newItem = { Name: '新君主', Str: 80, Int: 80, HP: 100, MP: 50 };
        this._data.push(newItem);
        this._render();
        this._select(this._data.length - 1);
        this.changed = true;
        updateSaveBtnState('customLeaderSaveBtn', true);
    },
    _render() {
        const listEl = document.getElementById('customLeaderList');
        if (!listEl) return;
        listEl.innerHTML = '';
        this._data.forEach((item, idx) => {
            const card = document.createElement('div');
            card.className = 'item-card';
            const name = item.Name || item.name || '未命名';
            card.innerHTML = `
                <div class="item-card-header">
                    <span class="item-name">${escHtml(name)}</span>
                    <span style="font-size:10px;color:var(--text-muted);">武${item.Str||'-'} 智${item.Int||'-'}</span>
                </div>`;
            card.onclick = () => this._select(idx);
            listEl.appendChild(card);
        });
    },
    _select(idx) {
        this._selectedIdx = idx;
        const item = this._data[idx];
        document.getElementById('customLeaderDetail').style.display = 'block';
        document.getElementById('customLeaderDetailName').textContent = (item.Name || item.name || '未命名') + ' - 详情';
        const fieldsEl = document.getElementById('customLeaderDetailFields');
        if (!fieldsEl) return;
        let html = '';
        for (const [k, v] of Object.entries(item)) {
            html += `<div class="form-group"><label>${escHtml(k)}</label><input type="text" value="${escHtml(String(v != null ? v : ''))}" onchange="customLeaderEditor._setField('${escHtml(k)}', this.value, ${idx})"></div>`;
        }
        fieldsEl.innerHTML = html;
    },
    saveDetail() {
        if (this._selectedIdx >= 0) {
            this.changed = true;
            updateSaveBtnState('customLeaderSaveBtn', true);
            showToast('请点击"保存修改"按钮保存全部更改', 'info');
        }
    },
    closeDetail() {
        document.getElementById('customLeaderDetail').style.display = 'none';
        this._selectedIdx = -1;
    },
    _setField(key, val, idx) {
        if (this._data[idx]) this._data[idx][key] = val;
        this.changed = true;
        updateSaveBtnState('customLeaderSaveBtn', true);
    }
};

// ============================================================
// 武将姓氏编辑器 (TermText 27000+系列)
// ============================================================
const surnameEditor = {
    changed: false,
    _data: [],
    _filtered: [],
    _selectedIdx: -1,
    _generalsMap: null, // 武将编号->武将名 映射

    async _loadGenerals() {
        if (this._generalsMap) return;
        try {
            const res = await pyApi('loadGenerals');
            if (res.success && res.data) {
                this._generalsMap = {};
                res.data.forEach(g => { this._generalsMap[g.No] = g.Name; });
            }
        } catch(e) { console.warn('load generals failed:', e); }
    },

    async load() {
        const res = await pyApi('loadTermTextFull');
        if (res.success) {
            this._data = res.data.filter(d => d.id >= 27000 && d.id < 28000);
            this._filtered = [...this._data];
            document.getElementById('surnameSummary').textContent = '共 ' + this._data.length + ' 个姓氏';
            this._render();
        } else {
            showToast(res.message || '加载失败', 'error');
        }
        return res;
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        // 通过 TermText 保存：只发送修改过的条目
        const res = await pyApi('saveTermText', this._data);
        if (res.success) { this.changed = false; updateSaveBtnState('surnameSaveBtn', false); }
        if (res.message) showToast(res.message, res.success ? 'success' : 'error');
        return res;
    },

    search(q) {
        if (!q) { this._filtered = [...this._data]; }
        else {
            const lower = q.toLowerCase();
            this._filtered = this._data.filter(d =>
                (d.value || '').toLowerCase().includes(lower) ||
                String(d.id).includes(q)
            );
        }
        this._render();
    },

    addNew() {
        const maxId = this._data.length > 0 ? Math.max(...this._data.map(d => d.id)) : 27000;
        const newItem = { id: maxId + 1, value: '新姓氏' };
        this._data.push(newItem);
        this._filtered = [...this._data];
        this._render();
        this._select(this._data.length - 1);
        this.changed = true;
        updateSaveBtnState('surnameSaveBtn', true);
    },

    _render() {
        const listEl = document.getElementById('surnameList');
        if (!listEl) return;
        listEl.innerHTML = '';
        this._filtered.forEach((item, idx) => {
            const card = document.createElement('div');
            card.className = 'item-card';
            const genNo = item.id - 27000;
            const genName = (this._generalsMap && this._generalsMap[genNo]) ? ' (' + this._generalsMap[genNo] + ')' : '';
            card.innerHTML = `
                <div class="item-card-header">
                    <span class="item-no">#${item.id}</span>
                    <span class="item-name">${escHtml(item.value || '')}</span>
                    <span style="font-size:10px;color:var(--text-muted);">武将No.${genNo}${escHtml(genName)}</span>
                </div>`;
            card.onclick = () => this._select(idx);
            listEl.appendChild(card);
        });
    },

    async _select(idx) {
        this._selectedIdx = idx;
        const item = this._filtered[idx];
        if (!item) return;
        await this._loadGenerals();
        document.getElementById('surnameDetail').style.display = 'block';
        const genNo = item.id - 27000;
        document.getElementById('surnameDetailName').textContent = '编辑姓氏: ' + (item.value || '');
        document.getElementById('surnameId').value = item.id;
        document.getElementById('surnameGenNo').value = genNo;
        const genName = (this._generalsMap && this._generalsMap[genNo]) ? this._generalsMap[genNo] : '未知武将';
        document.getElementById('surnameGenName').textContent = genName;
        document.getElementById('surnameValue').value = item.value || '';
        document.getElementById('surnameHint').textContent = '旗帜上显示的姓氏。27000+武将编号=' + genNo + ', 对应武将: ' + genName;
    },

    saveDetail() {
        if (this._selectedIdx >= 0) {
            const item = this._filtered[this._selectedIdx];
            const origIdx = this._data.indexOf(item);
            if (origIdx >= 0) {
                this._data[origIdx] = { ...item };
                this.changed = true;
                updateSaveBtnState('surnameSaveBtn', true);
            }
        }
        showToast('请点击"保存修改"按钮保存全部更改', 'info');
    },

    closeDetail() {
        document.getElementById('surnameDetail').style.display = 'none';
        this._selectedIdx = -1;
    },

    _setField(key, val) {
        if (this._selectedIdx >= 0) {
            const item = this._filtered[this._selectedIdx];
            if (key === 'id') item.id = parseInt(val) || 0;
            else item[key] = val;
            this.changed = true;
            updateSaveBtnState('surnameSaveBtn', true);
        }
    }
};

// ============================================================
// 子标签页事件绑定 (uisubsystem / configext)
// ============================================================
(function initSubTabEvents() {
    // 延迟执行，等待 DOM 加载
    function bindSubTabs() {
        // configext 子标签页
        const cfgTabs = document.querySelectorAll('#configext .sub-tab');
        cfgTabs.forEach(tab => {
            tab.addEventListener('click', function() {
                cfgTabs.forEach(t => t.classList.remove('active'));
                this.classList.add('active');
                const sub = this.dataset.sub;
                configextEditor._currentSub = sub;
                configextEditor.load();
            });
        });

        // uisubsystem 子标签页
        const uiTabs = document.querySelectorAll('#uisubsystem .sub-tab');
        uiTabs.forEach(tab => {
            tab.addEventListener('click', function() {
                uiTabs.forEach(t => t.classList.remove('active'));
                this.classList.add('active');
                const sub = this.dataset.sub;
                uisubsystemEditor._currentSub = sub;
                uisubsystemEditor.load();
            });
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindSubTabs);
    } else {
        bindSubTabs();
    }
})();

// ============================================================
// 游戏配置编辑器 (Sango7.ini)
// ============================================================
const sango7Editor = {
    async load() {
        try {
            const res = await pyApi('getSango7Config');
            if (res && res.success) {
                const c = res.config || {};
                const wEl = document.getElementById('sg7_width');
                const hEl = document.getElementById('sg7_height');
                const fEl = document.getElementById('sg7_fullscreen');
                if (wEl) wEl.value = c.width || 1024;
                if (hEl) hEl.value = c.height || 768;
                if (fEl) fEl.value = c.fullscreen !== undefined ? c.fullscreen : 1;
                const resultEl = document.getElementById('sango7Result');
                if (resultEl) { resultEl.textContent = '配置已加载'; resultEl.style.color = 'var(--success)'; }
            } else {
                const resultEl = document.getElementById('sango7Result');
                if (resultEl) { resultEl.textContent = '加载失败: ' + (res ? res.message : ''); resultEl.style.color = 'var(--danger)'; }
            }
        } catch(e) {
            const resultEl = document.getElementById('sango7Result');
            if (resultEl) { resultEl.textContent = '加载失败: ' + e; resultEl.style.color = 'var(--danger)'; }
        }
    },
    async save() {
        if (!(await validateBeforeSave())) return;
        this.pushUndo();
        const width = parseInt(document.getElementById('sg7_width').value) || 0;
        const height = parseInt(document.getElementById('sg7_height').value) || 0;
        const fullscreen = parseInt(document.getElementById('sg7_fullscreen').value);
        const resultEl = document.getElementById('sango7Result');
        try {
            const res = await pyApi('setSango7Config', width, height, fullscreen);
            if (res && res.success) {
                if (resultEl) { resultEl.textContent = res.message || '配置已保存'; resultEl.style.color = 'var(--success)'; }
            } else {
                if (resultEl) { resultEl.textContent = '保存失败: ' + (res ? res.message : ''); resultEl.style.color = 'var(--danger)'; }
            }
        } catch(e) {
            if (resultEl) { resultEl.textContent = '保存失败: ' + e; resultEl.style.color = 'var(--danger)'; }
        }
    },

    snapshot() {
        return {
            width: document.getElementById('sg7_width')?.value || '1024',
            height: document.getElementById('sg7_height')?.value || '768',
            fullscreen: document.getElementById('sg7_fullscreen')?.value || '1',
        };
    },

    restoreSnapshot(data) {
        if (document.getElementById('sg7_width')) document.getElementById('sg7_width').value = data.width || 1024;
        if (document.getElementById('sg7_height')) document.getElementById('sg7_height').value = data.height || 768;
        if (document.getElementById('sg7_fullscreen')) document.getElementById('sg7_fullscreen').value = data.fullscreen || 1;
    },

    pushUndo() {
        UndoManager.pushState('sango7', this.snapshot());
    },
};

// ============================================================
// 兵种动画帧导入向导
// ============================================================
const spriteImportWizard = {
    generateTemplate() {
        const obdType = document.getElementById('sprOBDType').value;
        const number = document.getElementById('sprNumber').value.trim() || '001';
        const types = ['Wait', 'Walk', 'Atk', 'Die', 'Hurt', 'Skill'];
        const animNames = { Wait: '待机', Walk: '行走', Atk: '攻击', Die: '死亡', Hurt: '受伤', Skill: '施法' };
        let html = '<div style="margin-bottom:8px;color:var(--accent);">OBD 参数模板: ' + obdType + ' #' + number + '</div>';
        html += '<div style="margin-bottom:4px;">复制以下内容到 OBD 编辑器的 Sprite 参数字段:</div>';
        types.forEach(function(type) {
            const frameCount = parseInt(document.getElementById('spr' + type).value) || 0;
            if (frameCount <= 0) return;
            html += '<div style="margin-bottom:4px;"><b>spr' + type + '1Com</b> = ' + zeroPad(number,3) + '\\\\' + type + '1.shp</div>';
            html += '<div style="margin-bottom:4px;"><b>spr' + type + '1</b> = ' + zeroPad(number,3) + '\\\\' + type + '1.shp</div>';
            for (let i = 2; i <= frameCount; i++) {
                html += '<div style="margin-bottom:2px;color:var(--text-muted);">spr' + type + '1Com' + zeroPad(i,2) + ' = ' + zeroPad(number,3) + '\\\\' + type + i + '.shp</div>';
            }
        });
        html += '<div style="margin-top:8px;color:var(--text-muted);font-size:10px;">SHP文件路径: Shape\\BFObj\\' + obdType + '\\' + zeroPad(number,3) + '\\</div>';
        html += '<div style="color:var(--text-muted);font-size:10px;">每帧图片尺寸: 建议 128x128 (BFSoldier/BFGen) 或 64x64 (BFWeapon)</div>';
        const templateEl = document.getElementById('spriteImportTemplate');
        templateEl.innerHTML = html;
        templateEl.style.display = 'block';
        showToast('已生成 OBD 参数模板', 'success');
    },

    async importFrames() {
        const obdType = document.getElementById('sprOBDType').value;
        const number = document.getElementById('sprNumber').value.trim() || '001';
        const types = ['Wait', 'Walk', 'Atk', 'Die', 'Hurt', 'Skill'];
        const resultEl = document.getElementById('spriteImportResult');
        resultEl.textContent = '正在创建目录...';
        resultEl.style.color = 'var(--text-muted)';
        try {
            // 创建目录结构
            await pyApi('createSHDir', obdType, number);
            let totalFrames = 0;
            let successFrames = 0;
            for (let t = 0; t < types.length; t++) {
                const type = types[t];
                const frameCount = parseInt(document.getElementById('spr' + type).value) || 0;
                if (frameCount <= 0) continue;
                for (let i = 1; i <= frameCount; i++) {
                    totalFrames++;
                    const r = await pyApi('importSpriteFrame', obdType, number, type, i);
                    if (r && r.success) successFrames++;
                    resultEl.textContent = '转换中... ' + type + ' ' + i + '/' + frameCount + ' (' + successFrames + '/' + totalFrames + ')';
                }
            }
            resultEl.textContent = '完成! ' + successFrames + '/' + totalFrames + ' 帧已生成';
            resultEl.style.color = 'var(--success)';
            showToast('帧导入完成: ' + successFrames + ' 帧\n\n路径: Shape/BFObj/' + obdType + '/' + zeroPad(number,3) + '/\n\n下一步: 用上方「生成 OBD 参数模板」按钮获取参数并填入 OBD 编辑器', 'success');
        } catch(e) {
            resultEl.textContent = '失败: ' + e;
            resultEl.style.color = 'var(--danger)';
            showToast('导入失败: ' + e, 'error');
        }
    }
};

function zeroPad(n, w) { n = String(n); while (n.length < w) n = '0' + n; return n; }

// ============================================================
// OBD模型编辑器
// ============================================================
const obdEditor = {
    data: [],
    async load() {
        const type = document.getElementById('obdType').value;
        document.getElementById('obdList').innerHTML = '<p class="loading">加载中...</p>';
        try {
let r = await pyApi('obdLoad', type);
            r = r || {};
            this.data = r.data || [];
            document.getElementById('obdCount').textContent = '('+this.data.length+'个)';
            this._renderList();
        } catch(e) { document.getElementById('obdList').innerHTML = '<p class="err">加载失败: '+escHtml(String(e))+'</p>'; }
    },
    _renderList() {
        const el = document.getElementById('obdList');
        if (!this.data.length) { el.innerHTML = '<p class="hint">无数据</p>'; return; }
        el.innerHTML = this.data.map((o,i)=>`<div class="list-item" onclick="obdEditor.select(${i})" style="cursor:pointer;">
            <span><b>#${o.sequence}</b> ${escHtml(o.name||'')} (ObjID:${o.obj_id})</span>
            <span>${Object.keys(o.sprites||{}).length}个动作</span></div>`).join('');
    },
    select(idx) {
        const o = this.data[idx];
        if (!o) return;
        this._selectedIdx = idx;
        this._selectedSeq = o.sequence;
        const card = document.getElementById('obdDetailCard');
        const el = document.getElementById('obdDetail');
        card.style.display = 'block';
        let html = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <span style="font-size:11px;color:var(--text-muted);">选中: #${o.sequence}</span>
            <button class="btn btn-danger btn-xs" onclick="obdEditor.deleteObj(${idx})" title="删除此模型">删除</button>
        </div>
        <div class="form-row"><label>Sequence</label><input type="number" value="${o.sequence}" onchange="obdEditor.data[${idx}].sequence=parseInt(this.value)||0"></div>
            <div class="form-row"><label>Name</label><input type="text" value="${escHtml(o.name||'')}" onchange="obdEditor.data[${idx}].name=this.value"></div>
            <div class="form-row"><label>Space (X,Y,Z)</label>
                <input type="number" value="${(o.space||[0,0,0])[0]}" style="width:60px" onchange="obdEditor.data[${idx}].space[0]=parseInt(this.value)||0">
                <input type="number" value="${(o.space||[0,0,0])[1]}" style="width:60px" onchange="obdEditor.data[${idx}].space[1]=parseInt(this.value)||0">
                <input type="number" value="${(o.space||[0,0,0])[2]}" style="width:60px" onchange="obdEditor.data[${idx}].space[2]=parseInt(this.value)||0">
            </div>
            <h4 style="margin-top:8px;">Sprites (${Object.keys(o.sprites||{}).length}个动作)</h4>`;
        for (const [k,v] of Object.entries(o.sprites||{})) {
            html += `<div class="form-row"><label>${escHtml(k)}</label><input type="text" value="${escHtml((v||[]).join(','))}" onchange="obdEditor.data[${idx}].sprites['${escHtml(k)}']=this.value.split(',').map(s=>s.trim())"></div>`;
        }
        el.innerHTML = html;
        // 添加 Sprite 帧预览
        const spritePreviewHTML = `
            <div style="margin-top:12px;border:1px solid var(--border);border-radius:6px;overflow:hidden;">
                <div style="padding:8px 12px;background:var(--bg-card);border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:13px;font-weight:600;">Sprite 帧预览</span>
                    <button class="btn btn-outline btn-sm" onclick="obdEditor.listSpriteFrames()">加载帧列表</button>
                </div>
                <div id="obdSpriteFramePanel" style="padding:8px;max-height:200px;overflow-y:auto;"></div>
                <div id="obdSpritePreviewBox" style="padding:8px;text-align:center;background:var(--bg-hover);min-height:80px;display:flex;align-items:center;justify-content:center;">
                    <img id="obdSpritePreviewImg" src="" style="max-width:200px;max-height:150px;object-fit:contain;display:none;" />
                    <span id="obdSpritePreviewInfo" style="color:var(--text-muted);font-size:12px;">点击帧按钮预览</span>
                </div>
            </div>`;
        document.getElementById('obdDetail').insertAdjacentHTML('beforeend', spritePreviewHTML);
    },
    async newObj() {
        const type = document.getElementById('obdType').value;
        try {
let r = await pyApi('obdNewObject', type);
            r = r || {};
            if (r.success) { this.data.push(r.data); this._renderList(); }
            else { showToast('创建失败: '+r.message, 'error'); }
        } catch(e) { showToast('创建失败: '+e, 'error'); }
    },
    async deleteObj(idx) {
        const o = this.data[idx];
        if (!o) return;
        if (!confirm(`确认删除模型 "${o.name || '#'+o.sequence}" (Sequence=${o.sequence})?`)) return;
        this.pushUndo();
        const type = document.getElementById('obdType').value;
        try {
            const r = await pyApi('obdDelete', type, o.sequence);
            if (r && r.success) {
                this.data.splice(idx, 1);
                this._selectedSeq = null;
                document.getElementById('obdDetailCard').style.display = 'none';
                this._renderList();
                document.getElementById('obdCount').textContent = '('+this.data.length+'个)';
                showToast(r.message, 'info');
            } else {
                showToast('删除失败: ' + (r ? r.message : ''), 'error');
            }
        } catch(e) { showToast('删除失败: '+e, 'error'); }
    },
    async save() {
        if (!(await validateBeforeSave())) return;
        const type = document.getElementById('obdType').value;
        try {
let r = await pyApi('obdSave', type, this.data);
            r = r || {};
            showToast(r.success ? r.message : '保存失败: '+r.message, 'info');
        } catch(e) { showToast('保存失败: '+e, 'error'); }
    },
    async copyTo() {
        const source = document.getElementById('obdCopySource')?.value || 'bfevent';
        const target = document.getElementById('obdCopyTarget')?.value || 'bfgen';
        const seq = parseInt(document.getElementById('obdCopySeq')?.value);
        if (!seq) { showToast('请输入要复制的 Sequence 编号', 'warning'); return; }
        if (source === target) { showToast('源和目标不能相同', 'info'); return; }
        if (!confirm(`确认从 ${source} 复制 Sequence=${seq} 到 ${target}？`)) return;
        try {
            const r = await pyApi('obdCopyTo', source, target, seq);
            if (r.success) {
                showToast(`复制成功！\n新Sequence=${r.new_sequence} (ObjID=${r.new_obj_id}, 'info')\n${r.message}`, 'info');
                this.load();
                // 联动提示
                if (source === 'bfevent' && target === 'bfgen') {
                    setTimeout(() => {
                        if (confirm('是否同时复制 SFEvent→SFGen 大地图造型？\n请在左侧下拉框中选择 SFEvent/SFGen 类型。')) {
                            document.getElementById('obdCopySource').value = 'sfevent';
                            document.getElementById('obdCopyTarget').value = 'sfgen';
                        }
                    }, 500);
                }
            } else {
                showToast('复制失败: ' + (r.message || '未知错误'), 'error');
            }
        } catch(e) { showToast('复制失败: '+e, 'error'); }
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this.data));
    },

    restoreSnapshot(data) {
        this.data = JSON.parse(JSON.stringify(data));
        this._renderList();
    },

    pushUndo() {
        UndoManager.pushState('obd', this.snapshot());
    },

    async previewSpriteFrame(action, frameIdx) {
        const type = document.getElementById('obdType').value;
        const seq = this._selectedSeq || 0;
        if (!seq) return;
        const img = document.getElementById('obdSpritePreviewImg');
        const info = document.getElementById('obdSpritePreviewInfo');
        if (!img || !info) return;
        try {
            const r = await pyApi('obdPreviewSpriteFrame', type, seq, action, frameIdx);
            if (r && r.success) {
                img.src = 'data:image/png;base64,' + r.image_base64;
                info.textContent = `${action} 第${frameIdx+1}帧 (${r.size}) - ${r.frame_name}`;
            } else {
                info.textContent = '预览失败: ' + (r ? r.message : '');
            }
        } catch(e) { info.textContent = '预览失败: ' + e; }
    },

    async listSpriteFrames() {
        const type = document.getElementById('obdType').value;
        const seq = this._selectedSeq || 0;
        if (!seq) return;
        const panel = document.getElementById('obdSpriteFramePanel');
        if (!panel) return;
        panel.innerHTML = '<p class="loading">加载帧列表...</p>';
        try {
            const r = await pyApi('obdListSpriteFrames', type, seq);
            if (!r || !r.success) { panel.innerHTML = '<p class="hint">加载失败</p>'; return; }
            let html = '';
            for (const [action, data] of Object.entries(r.actions || {})) {
                html += `<div class="sprite-action-group">
                    <div class="sprite-action-header" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
                        <b>${escHtml(action)}</b> <span style="color:var(--text-muted);font-size:11px;">${data.frame_count}帧</span>
                    </div>
                    <div class="sprite-action-frames" style="display:none;">`;
                data.frames.forEach((fn, fi) => {
                    html += `<span class="sprite-frame-btn" onclick="obdEditor.previewSpriteFrame('${escHtml(action)}',${fi})" title="${escHtml(fn)}">${fi+1}</span>`;
                });
                html += `</div></div>`;
            }
            panel.innerHTML = html || '<p class="hint">无动作数据</p>';
        } catch(e) { panel.innerHTML = '<p class="hint">加载失败: ' + escHtml(String(e)) + '</p>'; }
    },
};

// ============================================================
// 兵种相克矩阵编辑器
// ============================================================
const matrixEditor = {
    soldiers: [],
    async load() {
        try {
let r = await pyApi('loadSoldiers');
            r = r || {};
            if (!r.success) { showToast('请先加载兵种数据', 'info'); return; }
            this.soldiers = r.data || [];
let mr = await pyApi('matrixGet');
            mr = mr || {};
            const s = mr.summary || {};
            document.getElementById('mxSize').textContent = s.size||0;
            document.getElementById('mxStrong').textContent = s.strong_count||0;
            document.getElementById('mxWeak').textContent = s.weak_count||0;
            document.getElementById('mxNeutral').textContent = (s.size||0)*(s.size||0)-(s.strong_count||0)-(s.weak_count||0);
            this._renderGrid();
        } catch(e) { document.getElementById('matrixGrid').innerHTML = '<p class="err">加载失败: '+escHtml(String(e))+'</p>'; }
    },
    _renderGrid() {
        const el = document.getElementById('matrixGrid');
        if (!this.soldiers.length) { el.innerHTML = '<p class="hint">无兵种数据</p>'; return; }
        let html = '<table class="matrix-table"><thead><tr><th>兵种\\克制</th>';
        for (let i=0;i<this.soldiers.length;i++) {
            const n = this.soldiers[i].Name||('#'+i);
            html += `<th title="${escHtml(n)}">${escHtml(n.substring(0,2))}</th>`;
        }
        html += '</tr></thead><tbody>';
        for (let i=0;i<this.soldiers.length;i++) {
            html += `<tr><th>${escHtml((this.soldiers[i].Name||('#')+i).substring(0,4))}</th>`;
            for (let j=0;j<this.soldiers.length;j++) {
                const key = 'HitSol'+j;
                const val = parseInt(this.soldiers[i][key]) || 100;
                let cls = '';
                if (i===j) cls = 'style="background:var(--bg-card);font-weight:bold;"';
                else if (val>150) cls = 'style="background:#fde8e8;color:#e74c3c;"';
                else if (val<50) cls = 'style="background:#e8f0fe;color:#3498db;"';
                html += `<td ${cls} onclick="matrixEditor._editCell(${i},${j},${val})" title="${escHtml(this.soldiers[i].Name||'')} → ${escHtml(this.soldiers[j].Name||'')}: ${val}">${val}</td>`;
            }
            html += '</tr>';
        }
        html += '</tbody></table>';
        el.innerHTML = html;
    },
    _editCell(i, j, cur) {
        const v = prompt('克制值 (100=中性, >150=克制, <50=被克制):', cur);
        if (v===null) return;
        const val = parseInt(v)||100;
        this.soldiers[i]['HitSol'+j] = val;
        pyApi('matrixUpdate', i, j, val);
        this._renderGrid();
    },
    async save() {
        if (!(await validateBeforeSave())) return;
        this.pushUndo();
        try {
let r = await pyApi('saveSoldiers', this.soldiers);
            r = r || {};
            showToast(r.success ? r.message : '保存失败: '+r.message, 'info');
        } catch(e) { showToast('保存失败: '+e, 'error'); }
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this.soldiers));
    },

    restoreSnapshot(data) {
        this.soldiers = JSON.parse(JSON.stringify(data));
        this._renderGrid();
    },

    pushUndo() {
        UndoManager.pushState('matrix', this.snapshot());
    },
};

// ============================================================
// 存档管理器 (v2.0)
// ============================================================
const saveEditor = {
    _selectedSave: null,
    _customGenName: null,
    _customGenData: null,

    async refresh() {
        const el = document.getElementById('saveList');
        el.innerHTML = '<p class="loading">加载中...</p>';
        try {
            let r = await pyApi('saveList');
            r = r || {};
            const saves = r.saves || [];
            if (!saves.length) { el.innerHTML = '<p class="hint">未找到存档文件</p>'; return; }
            el.innerHTML = saves.map(s => {
                const typeLabel = {custom_general:'自定义武将',scenario:'剧本存档',unknown:'未知'}[s.type] || s.type;
                return `<div class="list-item" style="cursor:pointer;" onclick="saveEditor._load('${escHtml(s.name)}')">
                    <div>
                        <b>${escHtml(s.name)}</b>
                        <span class="tag" style="margin-left:8px;">${typeLabel}</span>
                    </div>
                    <div style="font-size:11px;color:var(--text-muted);">${s.size_kb}KB · ${s.modified}</div>
                    <div>
                        <button onclick="event.stopPropagation();saveEditor._backup('${escHtml(s.name)}');" class="btn btn-sm">备份</button>
                    </div>
                </div>`;
            }).join('');
        } catch(e) { el.innerHTML = '<p class="err">加载失败: '+escHtml(String(e))+'</p>'; }
    },

    async _backup(name) {
        try {
            let r = await pyApi('saveBackup', name);
            r = r || {};
            showToast(r.success ? r.message : '备份失败: '+r.message, 'info');
        } catch(e) { showToast('备份失败: '+e, 'error'); }
    },

    async _load(name) {
        this._selectedSave = name;
        try {
            let r = await pyApi('saveLoad', name);
            r = r || {};
            if (!r.success) { showToast('加载失败: '+r.message, 'error'); return; }

            const info = r.info || {};
            // 显示存档信息
            document.getElementById('saveInfoPanel').style.display = 'block';
            document.getElementById('saveInfoTitle').textContent = name;
            const infoContent = document.getElementById('saveInfoContent');
            infoContent.innerHTML = `<div style="display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:13px;">
                <span style="color:var(--text-muted);">大小:</span><span>${r.size} 字节</span>
                <span style="color:var(--text-muted);">类型:</span><span>${info.type||'未知'}</span>
                <span style="color:var(--text-muted);">描述:</span><span>${info.description||'—'}</span>
                <span style="color:var(--text-muted);">魔数:</span><span>${info.magic||'—'} ${info.magic_ascii||''}</span>
                ${info.format_version ? '<span style="color:var(--text-muted);">解析器:</span><span>'+info.format_version+'</span>' : ''}
                ${info.general_count !== undefined ? '<span style="color:var(--text-muted);">武将数:</span><span>'+info.general_count+'</span>' : ''}
            </div>`;

            // CustomGen面板
            if (name === 'CustomGen.sav' && info.generals) {
                this._customGenName = name;
                this._showCustomGen(info.generals);
                document.getElementById('customGenPanel').style.display = 'block';
                document.getElementById('scenarioPanel').style.display = 'none';
            } else {
                document.getElementById('customGenPanel').style.display = 'none';
                this._showScenarioInfo(info);
                // 尝试解析SG7存档武将
                this._parseSG7Generals();
            }

            // 隐藏hex面板
            document.getElementById('hexPanel').style.display = 'none';
        } catch(e) { showToast('加载失败: '+e, 'error'); }
    },

    _showCustomGen(generals) {
        document.getElementById('customGenCount').textContent =
            `共 ${generals.filter(g=>g.used).length} 个已用 / ${generals.length} 个槽位`;
        this._customGenData = generals;
        const list = document.getElementById('customGenList');
        list.innerHTML = generals.map(g => `
            <div class="list-item" style="${g.used ? '' : 'opacity:0.5;'}">
                <div style="min-width:60px;"><b>#${g.index+1}</b></div>
                <div style="flex:1;min-width:0;">
                    <div style="font-size:12px;">${escHtml(g.name || '(空)')}</div>
                    <div style="font-size:10px;color:var(--text-muted);">ID: ${escHtml(g.id)} | 偏移:0x${g.offset.toString(16)} | ${g.size}字节</div>
                </div>
                <input type="text" value="${escHtml(g.name || '')}" placeholder="武将名"
                       onchange="saveEditor._updateGenName(${g.index}, this.value)"
                       style="width:100px;font-size:12px;padding:2px 6px;">
                <button onclick="saveEditor._cloneGen(${g.index})" class="btn btn-sm" style="font-size:11px;">克隆</button>
            </div>
        `).join('');
    },

    _showScenarioInfo(info) {
        const panel = document.getElementById('scenarioPanel');
        panel.style.display = 'block';
        const content = document.getElementById('scenarioContent');
        let html = '';
        if (info.detected_structures && info.detected_structures.length) {
            html += '<h4 style="font-size:12px;margin:0 0 4px 0;">检测到的结构标记:</h4>';
            html += info.detected_structures.map(s =>
                `<div style="font-size:11px;padding:2px 0;">${s.type} @ ${s.offset_hex} (${s.marker})</div>`
            ).join('');
        }
        if (info.text_regions && info.text_regions.length) {
            html += '<h4 style="font-size:12px;margin:8px 0 4px 0;">文本区域:</h4>';
            html += info.text_regions.map(t =>
                `<div style="font-size:11px;padding:2px 0;">${t.offset_hex}: ${escHtml(t.preview)}</div>`
            ).join('');
        }
        if (info.value_regions && info.value_regions.length) {
            html += '<h4 style="font-size:12px;margin:8px 0 4px 0;">数值区域:</h4>';
            html += info.value_regions.map(v =>
                `<div style="font-size:11px;padding:2px 0;">${v.offset_hex}: ${v.count}个值, 样本: [${v.sample_values.join(', ')}]</div>`
            ).join('');
        }
        content.innerHTML = html || '<p style="font-size:12px;color:var(--text-muted);">无更多分析信息</p>';
    },

    _updateGenName(index, name) {
        if (this._customGenData) {
            const g = this._customGenData.find(x => x.index === index);
            if (g) g.name = name;
        }
    },

    async _cloneGen(index) {
        if (!this._customGenName) { showToast('请先分析CustomGen.sav', 'info'); return; }
        const count = parseInt(prompt('克隆数量:', '1')) || 1;
        if (count < 1) return;
        try {
            let r = await pyApi('saveCloneGeneral', this._customGenName, index, count);
            r = r || {};
            showToast(r.success ? r.message : '克隆失败: '+r.message, 'info');
            if (r.success) this._load(this._customGenName);
        } catch(e) { showToast('克隆失败: '+e, 'error'); }
    },

    async saveCustomGen() {
        if (!this._customGenName || !this._customGenData) { showToast('请先分析CustomGen.sav', 'info'); return; }
        try {
            let r = await pyApi('saveEditCustomGen', this._customGenName, this._customGenData);
            r = r || {};
            showToast(r.success ? r.message : '保存失败: ' + r.message, 'info');
        } catch(e) { showToast('保存失败: ' + e, 'error'); }
    },

    // ============================================================
    // SG7 存档武将结构化编辑
    // ============================================================
    _sg7GenData: null,
    _soldierTypes: null,

    async _parseSG7Generals() {
        if (!this._selectedSave || this._selectedSave === 'CustomGen.sav') return;
        const panel = document.getElementById('sg7GenPanel');
        const list = document.getElementById('sg7GenList');
        panel.style.display = 'block';
        list.innerHTML = '<p class="loading">正在解析武将数据...</p>';
        try {
            // 加载兵种类型
            if (!this._soldierTypes) {
                const sr = await pyApi('saveGetSoldierTypes');
                this._soldierTypes = (sr && sr.soldiers) || [];
            }
            const r = await pyApi('saveParseGenerals', this._selectedSave);
            if (!r || !r.success) {
                list.innerHTML = `<p class="hint">解析失败: ${escHtml(r?r.message:'未知错误')}</p>`;
                return;
            }
            this._sg7GenData = r.generals || [];
            document.getElementById('sg7GenCount').textContent = `找到 ${r.count} 个武将`;
            this._renderSG7Generals();
        } catch(e) {
            list.innerHTML = `<p class="err">解析失败: ${escHtml(String(e))}</p>`;
        }
    },

    _renderSG7Generals() {
        const list = document.getElementById('sg7GenList');
        const gens = this._sg7GenData || [];
        if (!gens.length) {
            list.innerHTML = '<p class="hint">未检测到武将数据（请确保存档来自游戏进行中，非初始存档）</p>';
            return;
        }
        list.innerHTML = gens.map((g, idx) => {
            const eq = g.equipment || {};
            const we = g.weapon_exp || {};
            return `<div class="list-item" style="flex-wrap:wrap;align-items:flex-start;gap:6px;">
                <div style="min-width:50px;font-weight:600;font-size:14px;">#${idx+1}</div>
                <div style="flex:1;min-width:200px;display:grid;grid-template-columns:repeat(3,1fr);gap:2px 8px;font-size:12px;">
                    <div>武力: <b>${g.wstr}</b></div>
                    <div>智力: <b>${g.intelligence}</b></div>
                    <div>体力: <b>${g.cur_hp}/${g.max_hp}</b></div>
                    <div>技力: <b>${g.cur_mp}/${g.max_mp}</b></div>
                    <div>士气: <b>${g.morale}</b></div>
                    <div>义理: <b>${g.loyal}</b></div>
                    ${g.merit !== undefined ? `<div>功勋: <b>${g.merit}</b></div>` : ''}
                    ${g.experience !== undefined ? `<div>经验: <b>${g.experience}</b></div>` : ''}
                    ${g.current_soldier_name ? `<div>兵种: <b>${g.current_soldier_name}</b> ×${g.current_soldier_count||0}</div>` : ''}
                </div>
                <div style="display:flex;gap:4px;flex-wrap:wrap;">
                    <button onclick="saveEditor._editSG7Gen(${idx})" class="btn btn-sm btn-primary">编辑</button>
                    <button onclick="saveEditor.loadStructuredGeneral(${idx})" class="btn btn-sm btn-primary" style="background:#5b21b6;">详细</button>
                    <button onclick="saveEditor._quickMax(${idx})" class="btn btn-sm" title="体力/技力回满">满血</button>
                    <button onclick="saveEditor._quickLevel(${idx})" class="btn btn-sm" title="经验设为99级">99级</button>
                </div>
            </div>`;
        }).join('');
    },

    async _quickMax(idx) {
        const g = this._sg7GenData[idx];
        if (!g) return;
        try {
            await pyApi('saveEditStat', this._selectedSave, g.offset, 'cur_hp', g.max_hp);
            await pyApi('saveEditStat', this._selectedSave, g.offset, 'cur_mp', g.max_mp);
            g.cur_hp = g.max_hp;
            g.cur_mp = g.max_mp;
            this._renderSG7Generals();
            this._showToast('体力/技力已回满');
        } catch(e) { showToast('修改失败: '+e, 'error'); }
    },

    async _quickLevel(idx) {
        const g = this._sg7GenData[idx];
        if (!g) return;
        try {
            // FF FF 98 00 = 99级经验值
            await pyApi('saveEditExp', this._selectedSave, g.offset, 0x0098FFFF);
            g.experience = 0x0098FFFF;
            this._renderSG7Generals();
            this._showToast('经验已设为99级');
        } catch(e) { showToast('修改失败: '+e, 'error'); }
    },

    _editSG7Gen(idx) {
        const g = this._sg7GenData[idx];
        if (!g) return;
        const we = g.weapon_exp || {};
        const soldierOpts = (this._soldierTypes || []).map(s =>
            `<option value="${s.id}" ${s.id === g.current_soldier_type ? 'selected' : ''}>${s.name}</option>`
        ).join('');

        let html = `<div style="padding:12px;min-width:500px;max-height:70vh;overflow-y:auto;">
            <h3 style="margin:0 0 12px;">编辑武将 #${idx+1} (偏移: 0x${g.offset.toString(16)})</h3>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px 12px;">

                <div><label style="font-size:11px;">武力</label>
                    <input type="number" id="eg_wstr" value="${g.wstr}" min="0" max="999" style="width:100%;padding:4px;font-size:13px;"></div>
                <div><label style="font-size:11px;">智力</label>
                    <input type="number" id="eg_intel" value="${g.intelligence}" min="0" max="999" style="width:100%;padding:4px;font-size:13px;"></div>

                <div><label style="font-size:11px;">最大体力</label>
                    <input type="number" id="eg_maxhp" value="${g.max_hp}" min="0" max="9999" style="width:100%;padding:4px;font-size:13px;"></div>
                <div><label style="font-size:11px;">当前体力</label>
                    <input type="number" id="eg_curhp" value="${g.cur_hp}" min="0" max="9999" style="width:100%;padding:4px;font-size:13px;"></div>

                <div><label style="font-size:11px;">最大技力</label>
                    <input type="number" id="eg_maxmp" value="${g.max_mp}" min="0" max="9999" style="width:100%;padding:4px;font-size:13px;"></div>
                <div><label style="font-size:11px;">当前技力</label>
                    <input type="number" id="eg_curmp" value="${g.cur_mp}" min="0" max="9999" style="width:100%;padding:4px;font-size:13px;"></div>

                <div><label style="font-size:11px;">义理</label>
                    <input type="number" id="eg_loyal" value="${g.loyal}" min="0" max="100" style="width:100%;padding:4px;font-size:13px;"></div>
                <div><label style="font-size:11px;">士气</label>
                    <input type="number" id="eg_morale" value="${g.morale}" min="0" max="100" style="width:100%;padding:4px;font-size:13px;"></div>

                <div><label style="font-size:11px;">相性</label>
                    <input type="number" id="eg_relation" value="${g.relation}" min="0" max="255" style="width:100%;padding:4px;font-size:13px;"></div>
                ${g.merit !== undefined ? `<div><label style="font-size:11px;">功勋</label>
                    <input type="number" id="eg_merit" value="${g.merit}" min="0" max="99999" style="width:100%;padding:4px;font-size:13px;"></div>` : ''}

            </div>

            <h4 style="margin:12px 0 6px;font-size:13px;">兵种</h4>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;">
                <div><label style="font-size:11px;">当前兵种</label>
                    <select id="eg_soldier_type" style="width:100%;padding:4px;font-size:13px;">${soldierOpts}</select></div>
                <div><label style="font-size:11px;">带兵数</label>
                    <input type="number" id="eg_soldier_count" value="${g.current_soldier_count||0}" min="0" max="9999" style="width:100%;padding:4px;font-size:13px;"></div>
            </div>

            <h4 style="margin:12px 0 6px;font-size:13px;">武器熟练度</h4>
            <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:4px 8px;">
                <div><label style="font-size:11px;">剑</label><input type="number" id="eg_sword" value="${we.sword||0}" min="0" max="255" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">枪</label><input type="number" id="eg_spear" value="${we.spear||0}" min="0" max="255" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">弓</label><input type="number" id="eg_bow" value="${we.bow||0}" min="0" max="255" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">刀</label><input type="number" id="eg_blade" value="${we.blade||0}" min="0" max="255" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">扇</label><input type="number" id="eg_fan" value="${we.fan||0}" min="0" max="255" style="width:100%;padding:3px;font-size:12px;"></div>
            </div>

            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;padding-top:12px;border-top:1px solid var(--border);">
                <button onclick="document.getElementById('sg7EditModal').style.display='none'" class="btn btn-outline btn-sm">取消</button>
                <button onclick="saveEditor._saveSG7Gen(${idx})" class="btn btn-primary">保存修改</button>
            </div>
        </div>`;

        let modal = document.getElementById('sg7EditModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'sg7EditModal';
            modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:9999;';
            modal.onclick = function(e) { if (e.target === modal) modal.style.display = 'none'; };
            document.body.appendChild(modal);
        }
        modal.innerHTML = `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;box-shadow:0 4px 24px rgba(0,0,0,0.5);">${html}</div>`;
        modal.style.display = 'flex';
    },

    async _saveSG7Gen(idx) {
        const g = this._sg7GenData[idx];
        if (!g) return;
        const saveName = this._selectedSave;
        const offset = g.offset;

        const fields = [
            ['wstr', 'eg_wstr'], ['intelligence', 'eg_intel'],
            ['max_hp', 'eg_maxhp'], ['cur_hp', 'eg_curhp'],
            ['max_mp', 'eg_maxmp'], ['cur_mp', 'eg_curmp'],
            ['loyal', 'eg_loyal'], ['morale', 'eg_morale'],
            ['relation', 'eg_relation'],
        ];

        let errors = [];
        for (const [field, elId] of fields) {
            const el = document.getElementById(elId);
            if (!el) continue;
            const val = parseInt(el.value);
            if (isNaN(val)) continue;
            try {
                const r = await pyApi('saveEditStat', saveName, offset, field, val);
                if (!r || !r.success) errors.push(`${field}: ${r?r.message:'失败'}`);
                else g[field] = r.new_value;
            } catch(e) { errors.push(`${field}: ${e}`); }
        }

        // 功勋
        const meritEl = document.getElementById('eg_merit');
        if (meritEl) {
            const val = parseInt(meritEl.value);
            if (!isNaN(val)) {
                try {
                    const r = await pyApi('saveEditMerit', saveName, offset, val);
                    if (r && r.success) g.merit = r.actual;
                    else errors.push('功勋: ' + (r?r.message:'失败'));
                } catch(e) { errors.push('功勋: '+e); }
            }
        }

        // 兵种
        const soldierTypeEl = document.getElementById('eg_soldier_type');
        const soldierCountEl = document.getElementById('eg_soldier_count');
        if (soldierTypeEl && soldierCountEl) {
            const st = parseInt(soldierTypeEl.value);
            const sc = parseInt(soldierCountEl.value);
            if (!isNaN(st) && !isNaN(sc)) {
                try {
                    const r = await pyApi('saveEditSoldier', saveName, offset, st, sc);
                    if (r && r.success) {
                        g.current_soldier_type = st;
                        g.current_soldier_count = sc;
                    } else errors.push('兵种: ' + (r?r.message:'失败'));
                } catch(e) { errors.push('兵种: '+e); }
            }
        }

        // 武器熟练度
        const weapons = ['sword', 'spear', 'bow', 'blade', 'fan'];
        for (const w of weapons) {
            const el = document.getElementById('eg_' + w);
            if (!el) continue;
            const val = parseInt(el.value);
            if (isNaN(val)) continue;
            try {
                const r = await pyApi('saveEditWeaponExp', saveName, offset, w, val);
                if (!r || !r.success) errors.push(`${w}: ${r?r.message:'失败'}`);
                else if (g.weapon_exp) g.weapon_exp[w] = val;
            } catch(e) { errors.push(`${w}: ${e}`); }
        }

        if (errors.length) {
            showToast('部分修改失败:\n' + errors.join('\n'), 'error');
        } else {
            this._showToast('武将数据已保存');
            document.getElementById('sg7EditModal').style.display = 'none';
            this._renderSG7Generals();
        }
    },

    // ============================================================
    // 结构化武将编辑
    // ============================================================
    _structuredData: null,
    _weaponNames: null,
    _horseNames: null,
    _itemNames: null,
    _formationNames: null,

    async loadStructuredGeneral(index) {
        const list = document.getElementById('sg7GenList');
        list.innerHTML = '<p class="loading">正在加载武将详细数据...</p>';
        try {
            // 并行加载名称字典
            if (!this._weaponNames) {
                const [wr, hr, ir, fr] = await Promise.all([
                    pyApi('saveGetWeaponNames'),
                    pyApi('saveGetHorseNames'),
                    pyApi('saveGetItemNames'),
                    pyApi('saveGetFormationNames'),
                ]);
                this._weaponNames = (wr && wr.weapons) || [];
                this._horseNames = (hr && hr.horses) || [];
                this._itemNames = (ir && ir.items) || [];
                this._formationNames = (fr && fr.formations) || [];
            }

            const r = await pyApi('saveGetStructuredGeneral', this._selectedSave, index);
            if (!r || !r.success) {
                list.innerHTML = `<p class="err">加载失败: ${escHtml(r?r.message:'未知错误')}</p>`;
                return;
            }
            this._structuredData = r;
            this._renderStructuredGeneral(r);
        } catch(e) {
            list.innerHTML = `<p class="err">加载失败: ${escHtml(String(e))}</p>`;
        }
    },

    _renderStructuredGeneral(data) {
        const list = document.getElementById('sg7GenList');
        const s = data.basic_stats || {};
        const eq = data.equipment || {};
        const mil = data.military || {};
        const sk = data.skills || {};
        const exp = data.experience || {};
        const meta = data.meta || {};

        const idx = meta.index || 0;
        const offset = meta.offset || 0;

        // 武器选项
        const weaponOpts = (this._weaponNames || []).map(w =>
            `<option value="${w.id}" ${w.id === eq.weapon.id ? 'selected' : ''}>${escHtml(w.name)}</option>`
        ).join('');

        // 坐骑选项
        const horseOpts = (this._horseNames || []).map(h =>
            `<option value="${h.id}" ${h.id === eq.horse.id ? 'selected' : ''}>${escHtml(h.name)}</option>`
        ).join('');

        // 道具选项
        const itemOpts = (this._itemNames || []).map(it =>
            `<option value="${it.id}" ${it.id === eq.item.id ? 'selected' : ''}>${escHtml(it.name)}</option>`
        ).join('');

        // 兵种选项
        const soldierOpts = (this._soldierTypes || []).map(s =>
            `<option value="${s.id}" ${s.id === mil.soldier_type ? 'selected' : ''}>${escHtml(s.name)}</option>`
        ).join('');

        // 阵型复选框
        const formationNames = this._formationNames || [];
        const enabledFormations = new Set((mil.formation_names || []).map(f => f.id));
        const formationChecks = formationNames.map(f =>
            `<label style="display:inline-flex;align-items:center;gap:2px;font-size:11px;margin:2px 4px;">
                <input type="checkbox" value="${f.id}" ${enabledFormations.has(f.id) ? 'checked' : ''}
                       onchange="saveEditor._toggleFormation(${f.id}, this.checked)">
                ${escHtml(f.name)}
            </label>`
        ).join('');

        let html = `<div style="padding:0;">
            <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);margin-bottom:8px;">
                <h3 style="margin:0;font-size:15px;">武将 #${idx+1} <span style="font-size:11px;color:var(--text-muted);">偏移: 0x${offset.toString(16)}</span></h3>
                <div style="display:flex;gap:4px;">
                    <button onclick="saveEditor._structuredQuickActions('max')" class="btn btn-sm">满血满蓝</button>
                    <button onclick="saveEditor._structuredQuickActions('level99')" class="btn btn-sm">等级99</button>
                    <button onclick="saveEditor._structuredQuickActions('clearEquip')" class="btn btn-sm">清空装备</button>
                    <button onclick="saveEditor._parseSG7Generals()" class="btn btn-sm btn-outline">返回列表</button>
                </div>
            </div>

            <!-- 基本属性 -->
            <h4 style="font-size:13px;margin:10px 0 6px;color:var(--accent);">基本属性</h4>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:4px 12px;font-size:12px;">
                <div><label style="font-size:11px;">武力</label>
                    <input type="number" id="s_wstr" value="${s.wstr}" min="0" max="999" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">智力</label>
                    <input type="number" id="s_intel" value="${s.intelligence}" min="0" max="999" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">体力</label>
                    <input type="number" id="s_hp" value="${s.hp}" min="0" max="9999" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">最大体力</label>
                    <input type="number" id="s_maxhp" value="${s.max_hp}" min="0" max="9999" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">技力</label>
                    <input type="number" id="s_mp" value="${s.mp}" min="0" max="9999" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">最大技力</label>
                    <input type="number" id="s_maxmp" value="${s.max_mp}" min="0" max="9999" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">义理</label>
                    <input type="number" id="s_justice" value="${s.justice}" min="0" max="100" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">相性</label>
                    <input type="number" id="s_personality" value="${s.personality}" min="0" max="255" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">士气</label>
                    <input type="number" id="s_morale" value="${s.morale}" min="0" max="100" style="width:100%;padding:3px;font-size:12px;"></div>
            </div>

            <!-- 装备 -->
            <h4 style="font-size:13px;margin:10px 0 6px;color:var(--accent);">装备</h4>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:4px 12px;font-size:12px;">
                <div><label style="font-size:11px;">武器</label>
                    <select id="s_weapon" style="width:100%;padding:3px;font-size:12px;">${weaponOpts}</select></div>
                <div><label style="font-size:11px;">坐骑</label>
                    <select id="s_horse" style="width:100%;padding:3px;font-size:12px;">${horseOpts}</select></div>
                <div><label style="font-size:11px;">道具</label>
                    <select id="s_item" style="width:100%;padding:3px;font-size:12px;">${itemOpts}</select></div>
            </div>
            <div style="margin-top:6px;">
                <button onclick="saveEditor._saveEquipment()" class="btn btn-sm btn-primary">保存装备</button>
            </div>

            <!-- 军事 -->
            <h4 style="font-size:13px;margin:10px 0 6px;color:var(--accent);">军事</h4>
            <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:4px 12px;font-size:12px;">
                <div><label style="font-size:11px;">兵种</label>
                    <select id="s_soldier_type" style="width:100%;padding:3px;font-size:12px;">${soldierOpts}</select></div>
                <div><label style="font-size:11px;">带兵数</label>
                    <input type="number" id="s_soldier_count" value="${mil.soldier_count||0}" min="0" max="9999" style="width:100%;padding:3px;font-size:12px;"></div>
            </div>
            <div style="margin-top:6px;"><label style="font-size:11px;">阵型</label>
                <div style="display:flex;flex-wrap:wrap;gap:2px;margin-top:2px;">${formationChecks}</div>
            </div>

            <!-- 技能 -->
            <h4 style="font-size:13px;margin:10px 0 6px;color:var(--accent);">技能位掩码</h4>
            <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:4px 8px;font-size:11px;">
                <div><label style="font-size:10px;">武将技</label>
                    <input type="text" id="s_bfmagic" value="${sk.bfmagic||''}" readonly style="width:100%;padding:2px;font-size:10px;background:var(--bg-input);"></div>
                <div><label style="font-size:10px;">军师技</label>
                    <input type="text" id="s_sfmagic" value="${sk.sfmagic||''}" readonly style="width:100%;padding:2px;font-size:10px;background:var(--bg-input);"></div>
                <div><label style="font-size:10px;">个人特性</label>
                    <input type="text" id="s_genskill" value="${sk.genskill||''}" readonly style="width:100%;padding:2px;font-size:10px;background:var(--bg-input);"></div>
                <div><label style="font-size:10px;">主将特性</label>
                    <input type="text" id="s_armyskill" value="${sk.armyskill||''}" readonly style="width:100%;padding:2px;font-size:10px;background:var(--bg-input);"></div>
                <div><label style="font-size:10px;">元帅特性</label>
                    <input type="text" id="s_armygroupskill" value="${sk.armygroupskill||''}" readonly style="width:100%;padding:2px;font-size:10px;background:var(--bg-input);"></div>
            </div>

            <!-- 经验 -->
            <h4 style="font-size:13px;margin:10px 0 6px;color:var(--accent);">经验与熟练度</h4>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:4px 12px;font-size:12px;">
                <div><label style="font-size:11px;">功勋</label>
                    <input type="number" id="s_merit" value="${exp.merit||0}" min="0" max="99999" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">经验</label>
                    <input type="number" id="s_exp" value="${exp.exp||0}" min="0" max="99999999" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">剑</label>
                    <input type="number" id="s_wexp_sword" value="${(exp.weapon_exp||[0])[0]}" min="0" max="255" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">枪</label>
                    <input type="number" id="s_wexp_spear" value="${(exp.weapon_exp||[0,0])[1]}" min="0" max="255" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">弓</label>
                    <input type="number" id="s_wexp_bow" value="${(exp.weapon_exp||[0,0,0])[2]}" min="0" max="255" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">刀</label>
                    <input type="number" id="s_wexp_blade" value="${(exp.weapon_exp||[0,0,0,0])[3]}" min="0" max="255" style="width:100%;padding:3px;font-size:12px;"></div>
                <div><label style="font-size:11px;">扇</label>
                    <input type="number" id="s_wexp_fan" value="${(exp.weapon_exp||[0,0,0,0,0])[4]}" min="0" max="255" style="width:100%;padding:3px;font-size:12px;"></div>
            </div>

            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;padding-top:12px;border-top:1px solid var(--border);">
                <button onclick="saveEditor._saveStructuredStats()" class="btn btn-primary">保存全部修改</button>
            </div>
        </div>`;

        list.innerHTML = html;
    },

    async _toggleFormation(formationId, enabled) {
        if (!this._structuredData) return;
        const index = this._structuredData.meta.index;
        try {
            const r = await pyApi('saveWriteFormation', this._selectedSave, index, formationId);
            if (r && r.success) {
                this._structuredData.military.formation_names = r.enabled_formations || [];
                this._showToast('阵型已更新');
            } else {
                showToast('阵型修改失败: ' + (r?r.message:'未知错误'), 'error');
            }
        } catch(e) { showToast('阵型修改失败: '+e, 'error'); }
    },

    async _saveEquipment() {
        if (!this._structuredData) return;
        const index = this._structuredData.meta.index;
        const saveName = this._selectedSave;
        const slots = [
            { slot: 'weapon', el: 's_weapon' },
            { slot: 'horse', el: 's_horse' },
            { slot: 'item', el: 's_item' },
        ];
        let errors = [];
        for (const {slot, el} of slots) {
            const sel = document.getElementById(el);
            if (!sel) continue;
            const itemId = parseInt(sel.value);
            if (isNaN(itemId)) continue;
            try {
                const r = await pyApi('saveWriteEquipment', saveName, index, slot, itemId);
                if (!r || !r.success) errors.push(`${slot}: ${r?r.message:'失败'}`);
                else if (this._structuredData.equipment) {
                    this._structuredData.equipment[slot] = { id: itemId, name: r.item_name };
                }
            } catch(e) { errors.push(`${slot}: ${e}`); }
        }
        if (errors.length) {
            showToast('装备保存失败:\n' + errors.join('\n'), 'error');
        } else {
            this._showToast('装备已保存');
        }
    },

    async _editSkill(skillType, slot) {
        if (!this._structuredData) return;
        const index = this._structuredData.meta.index;
        const currentMask = this._structuredData.skills[skillType] || '';
        const skillId = parseInt(prompt(`请输入技能ID (0=禁用, 1=启用): 当前掩码 ${currentMask.substring(0,16)}... 位${slot}`, '1'));
        if (isNaN(skillId)) return;
        try {
            const r = await pyApi('saveWriteSkills', this._selectedSave, index, skillType, slot, skillId);
            if (r && r.success) {
                this._showToast(`技能 ${skillType} 位${slot} 已${skillId?'启用':'禁用'}`);
                // 重新加载数据
                this.loadStructuredGeneral(index);
            } else {
                showToast('技能修改失败: ' + (r?r.message:'未知错误'), 'error');
            }
        } catch(e) { showToast('技能修改失败: '+e, 'error'); }
    },

    async _saveSkill() {
        // 已整合到 _editSkill 中
    },

    async _structuredQuickActions(action) {
        if (!this._structuredData) return;
        const index = this._structuredData.meta.index;
        const saveName = this._selectedSave;
        const s = this._structuredData.basic_stats;
        const offset = this._structuredData.meta.offset;

        try {
            if (action === 'max') {
                await pyApi('saveEditStat', saveName, offset, 'cur_hp', s.max_hp);
                await pyApi('saveEditStat', saveName, offset, 'cur_mp', s.max_mp);
                s.hp = s.max_hp;
                s.mp = s.max_mp;
                this._showToast('体力/技力已回满');
            } else if (action === 'level99') {
                await pyApi('saveEditExp', saveName, offset, 0x0098FFFF);
                this._structuredData.experience.exp = 0x0098FFFF;
                this._showToast('经验已设为99级');
            } else if (action === 'clearEquip') {
                for (const slot of ['weapon', 'horse', 'item']) {
                    await pyApi('saveWriteEquipment', saveName, index, slot, 0);
                }
                if (this._structuredData.equipment) {
                    this._structuredData.equipment.weapon = { id: 0, name: '无' };
                    this._structuredData.equipment.horse = { id: 0, name: '无' };
                    this._structuredData.equipment.item = { id: 0, name: '无' };
                }
                this._showToast('装备已清空');
            }
            this._renderStructuredGeneral(this._structuredData);
        } catch(e) { showToast('操作失败: '+e, 'error'); }
    },

    async _saveStructuredStats() {
        if (!this._structuredData) return;
        const index = this._structuredData.meta.index;
        const saveName = this._selectedSave;
        const offset = this._structuredData.meta.offset;

        const statFields = [
            { field: 'wstr', el: 's_wstr' },
            { field: 'intelligence', el: 's_intel' },
            { field: 'cur_hp', el: 's_hp' },
            { field: 'max_hp', el: 's_maxhp' },
            { field: 'cur_mp', el: 's_mp' },
            { field: 'max_mp', el: 's_maxmp' },
            { field: 'loyal', el: 's_justice' },
            { field: 'relation', el: 's_personality' },
            { field: 'morale', el: 's_morale' },
        ];

        let errors = [];
        // 保存基本属性
        for (const {field, el} of statFields) {
            const input = document.getElementById(el);
            if (!input) continue;
            const val = parseInt(input.value);
            if (isNaN(val)) continue;
            try {
                const r = await pyApi('saveEditStat', saveName, offset, field, val);
                if (!r || !r.success) errors.push(`${field}: ${r?r.message:'失败'}`);
            } catch(e) { errors.push(`${field}: ${e}`); }
        }

        // 保存功勋
        const meritEl = document.getElementById('s_merit');
        if (meritEl) {
            const val = parseInt(meritEl.value);
            if (!isNaN(val)) {
                try {
                    await pyApi('saveEditMerit', saveName, offset, val);
                } catch(e) { errors.push('功勋: '+e); }
            }
        }

        // 保存经验
        const expEl = document.getElementById('s_exp');
        if (expEl) {
            const val = parseInt(expEl.value);
            if (!isNaN(val)) {
                try {
                    await pyApi('saveEditExp', saveName, offset, val);
                } catch(e) { errors.push('经验: '+e); }
            }
        }

        // 保存兵种
        const soldierTypeEl = document.getElementById('s_soldier_type');
        const soldierCountEl = document.getElementById('s_soldier_count');
        if (soldierTypeEl && soldierCountEl) {
            const st = parseInt(soldierTypeEl.value);
            const sc = parseInt(soldierCountEl.value);
            if (!isNaN(st) && !isNaN(sc)) {
                try {
                    await pyApi('saveEditSoldier', saveName, offset, st, sc);
                } catch(e) { errors.push('兵种: '+e); }
            }
        }

        // 保存武器熟练度
        const weapons = ['sword', 'spear', 'bow', 'blade', 'fan'];
        for (const w of weapons) {
            const el = document.getElementById('s_wexp_' + w);
            if (!el) continue;
            const val = parseInt(el.value);
            if (isNaN(val)) continue;
            try {
                await pyApi('saveEditWeaponExp', saveName, offset, w, val);
            } catch(e) { errors.push(`${w}: ${e}`); }
        }

        // 保存装备
        await this._saveEquipment();

        if (errors.length) {
            showToast('部分修改失败:\n' + errors.join('\n'), 'error');
        } else {
            this._showToast('全部修改已保存');
        }
    },

    _showToast(msg) {
        let toast = document.getElementById('saveToast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'saveToast';
            toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--bg-card);color:#fff;padding:8px 20px;border-radius:6px;border:1px solid var(--border);font-size:13px;z-index:10000;pointer-events:none;transition:opacity 0.3s;';
            document.body.appendChild(toast);
        }
        toast.textContent = msg;
        toast.style.opacity = '1';
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => { toast.style.opacity = '0'; }, 2000);
    },

    async _loadHex() {
        if (!this._selectedSave) { showToast('请先选择一个存档', 'warning'); return; }
        const offset = parseInt(document.getElementById('hexOffset').value) || 0;
        const length = parseInt(document.getElementById('hexLength').value) || 512;
        try {
            let r = await pyApi('saveHexView', this._selectedSave, offset, length);
            r = r || {};
            if (r.success) {
                document.getElementById('hexPanel').style.display = 'block';
                document.getElementById('hexContent').textContent = r.hex_lines.join('\n') +
                    `\n\n--- 偏移: 0x${offset.toString(16)}, 长度: ${r.length} / ${r.total_size} 字节 ---`;
            } else {
                showToast('查看失败: '+r.message, 'error');
            }
        } catch(e) { showToast('查看失败: '+e, 'error'); }
    },

    async _searchHex() {
        if (!this._selectedSave) { showToast('请先选择一个存档', 'warning'); return; }
        const pattern = document.getElementById('hexSearch').value.trim();
        if (!pattern) { showToast('请输入搜索模式', 'warning'); return; }
        try {
            let r = await pyApi('saveHexSearch', this._selectedSave, pattern, 0);
            r = r || {};
            if (r.success) {
                showToast(`找到 ${r.match_count} 处匹配\n位置: ${r.positions.slice(0,10).join(', ')}${r.match_count>10?'...':''}`, 'info');
            } else {
                showToast('搜索失败: '+r.message, 'error');
            }
        } catch(e) { showToast('搜索失败: '+e, 'error'); }
    }
};

// ============================================================
// MOD制作向导
// ============================================================
const wizard = {
    activeId: null,
    async init() {
        const el = document.getElementById('wizardTemplates');
        if (!el) { console.warn('wizardTemplates not found, wizard init skipped'); return; }
        try {
let r = await pyApi('wizardTemplates');
            r = r || {};
            const templates = r.templates || [];
            el.innerHTML = templates.map(t=>`<div class="panel-card wizard-card" onclick="wizard.start('${t.id}')" style="cursor:pointer;">
                <div class="panel-card-header"><h3>${escHtml(t.name)}</h3></div>
                <div style="padding:12px;"><p style="font-size:13px;color:var(--text-muted);">${escHtml(t.description)}</p>
                <p style="font-size:12px;margin-top:8px;">${t.step_count}个步骤 · ${t.required_count}个必须</p></div>
            </div>`).join('');
        } catch(e) { el.innerHTML = '<p class="err">加载模板失败: '+escHtml(String(e))+'</p>'; }
    },
    async start(tid) {
        this.activeId = tid;
        const activeEl = document.getElementById('wizardActive');
        const stepsEl = document.getElementById('wizardSteps');
        const checklistEl = document.getElementById('wizardChecklist');
        if (!activeEl || !stepsEl || !checklistEl) {
            console.warn('wizard containers not found, using static forms');
            return;
        }
        try {
let r = await pyApi('wizardStart', tid);
            r = r || {};
            if (!r.success) { showToast('启动失败: '+r.message, 'error'); return; }
            document.getElementById('wizardActive').style.display = 'block';
            document.getElementById('wizardTitle').textContent = r.template;
            const steps = r.steps || [];
            const checklist = r.checklist || [];
            document.getElementById('wizardSteps').innerHTML = steps.map((s,i)=>`<div class="list-item">
                <input type="checkbox" id="ws${i}" ${r.progress&&r.progress[i]?'checked':''} onchange="wizard._step(${i})">
                <label for="ws${i}"><b>步骤${s.order}:</b> ${escHtml(s.action)} <span class="tag">${s.required?'必须':'可选'}</span></label>
                <span style="font-size:12px;color:var(--text-muted);">${escHtml(s.file)}</span>
            </div>`).join('');
            document.getElementById('wizardChecklist').innerHTML = checklist.map(c=>`<div class="list-item">☐ ${escHtml(c)}</div>`).join('');
        } catch(e) { showToast('启动失败: '+e, 'error'); }
    },
    async _step(idx) {
        if (!this.activeId) return;
        try {
            await pyApi('wizardStep', this.activeId, idx);
let r = await pyApi('wizardProgress', this.activeId);
            r = r || {};
            document.getElementById('wizardTitle').textContent = (r.template||'')+' ('+r.pct+'%)';
        } catch(e) { showToast('向导步骤执行失败', 'error'); }
    },
    async loadSample() {
        if (!this.activeId) { showToast('请先选择一个模板', 'warning'); return; }
        try {
            let r = await pyApi('wizardGetSample', this.activeId);
            r = r || {};
            if (!r.success || !r.data) { showToast('无示例数据', 'info'); return; }
            const sample = r.data;
            const note = document.getElementById('wizardSampleNote');
            if (note) note.textContent = sample.name + ' - ' + (sample.notes || '');

            // 根据模板类型将示例数据加载到对应编辑器
            const editorMap = {
                'new_general': { editor: generals, tab: 'generals' },
                'new_soldier': { editor: soldiers, tab: 'soldiers' },
                'new_item': { editor: things, tab: 'things' },
                'new_nation': { editor: nationEditor, tab: 'nation' },
            };
            const target = editorMap[this.activeId];
            if (!target || !target.editor) { showToast('编辑器未就绪', 'info'); return; }

            // 切换到目标tab
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            const navItem = document.querySelector(`[data-tab="${target.tab}"]`);
            if (navItem) navItem.classList.add('active');
            const tabContent = document.getElementById(target.tab);
            if (tabContent) tabContent.classList.add('active');

            // 推入撤销快照
            if (target.editor.pushUndo) target.editor.pushUndo();

            // 追加示例数据
            const ed = target.editor;
            const data = JSON.parse(JSON.stringify(sample.data));
            ed.data.push(data);
            ed.renderList();
            ed.changed = true;

            showToast(`示例数据 "${sample.name}" 已追加到编辑器`, 'info');
        } catch(e) { showToast('加载示例失败: ' + e.message, 'error'); }
    },

    showGeneralForm() {
        document.getElementById('wizardGeneralForm').style.display = 'block';
        document.getElementById('wizardSoldierForm').style.display = 'none';
    },

    showSoldierForm() {
        document.getElementById('wizardSoldierForm').style.display = 'block';
        document.getElementById('wizardGeneralForm').style.display = 'none';
    },

    async createGeneral() {
        if (!(await validateBeforeSave())) return;
        const no = parseInt(document.getElementById('wg_no').value);
        const name = document.getElementById('wg_name').value.trim();
        if (!no || !name) { showToast('编号和姓名不能为空', 'info'); return; }

        const getVal = (id, def) => { const v = document.getElementById(id).value; return v ? parseInt(v) : def; };
        const gs = document.getElementById('wg_genskill').value.trim();
        const genSkills = gs ? gs.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n)) : [];

        try {
            const r = await pyApi('wizardCreateGeneral', no, name, undefined, {
                str_val: getVal('wg_str',70), int_val: getVal('wg_int',50),
                hp: parseFloat(document.getElementById('wg_hp').value)||100,
                mp: getVal('wg_mp',30), justice: getVal('wg_justice',80),
                morale: getVal('wg_morale',70), weapon: getVal('wg_weapon',0),
                horse: getVal('wg_horse',0), formation: getVal('wg_formation',0),
                sol_type1: getVal('wg_sol1',1), sol_type2: getVal('wg_sol2',0),
                face_id: getVal('wg_face',0), sex: getVal('wg_sex',1),
                default_title: getVal('wg_title',1), gen_skills: genSkills,
                lord: getVal('wg_lord',0),
                city1: document.getElementById('wg_c1').value,
                city2: document.getElementById('wg_c2').value,
                city3: document.getElementById('wg_c3').value,
                city4: document.getElementById('wg_c4').value,
                city5: document.getElementById('wg_c5').value,
                city6: document.getElementById('wg_c6').value,
                city7: document.getElementById('wg_c7').value,
                city8: document.getElementById('wg_c8').value,
                city9: document.getElementById('wg_c9').value,
                city10: document.getElementById('wg_c10').value,
            });
            const el = document.getElementById('wizardResult');
            if (r && r.success) {
                el.textContent = '✓ ' + r.message;
                el.style.color = 'var(--success)';
                showToast('创建成功!\n\n已联动写入:\n✓ General01.ini\n✓ DefSkill.ini\n✓ General02.ini\n✓ TermText.ini\n\n请前往对应编辑器确认详情。', 'success');
            } else { el.textContent = '✗ '+(r?r.message:'失败'); el.style.color='var(--danger)'; }
        } catch(e) { document.getElementById('wizardResult').textContent='✗ '+e; document.getElementById('wizardResult').style.color='var(--danger)'; }
    },

    async createSoldier() {
        if (!(await validateBeforeSave())) return;
        const no = parseInt(document.getElementById('ws_no').value);
        const name = document.getElementById('ws_name').value.trim();
        if (!no || !name) { showToast('编号和名称不能为空', 'info'); return; }

        const getVal = (id, def) => { const v = document.getElementById(id).value; return v ? parseInt(v) : def; };

        try {
            const r = await pyApi('wizardCreateSoldier', no, name, undefined, {
                level: getVal('ws_level',1), upgrade: getVal('ws_upgrade',0),
                hp: getVal('ws_hp',50), atk: getVal('ws_atk',10),
                def_val: getVal('ws_def',5), speed: getVal('ws_speed',6),
                range_val: getVal('ws_range',1), cost: getVal('ws_cost',100),
                troop_count: getVal('ws_troop',1), obj_id: getVal('ws_objid',0),
            });
            const el = document.getElementById('wizardSoldierResult');
            if (r && r.success) {
                el.textContent = '✓ ' + r.message;
                el.style.color = 'var(--success)';
                showToast('创建成功!\n\n已联动写入:\n✓ Soldier.ini\n✓ TermText.ini\n\n提示: 记得在 OBD 编辑器中创建兵种模型。', 'success');
            } else { el.textContent = '✗ '+(r?r.message:'失败'); el.style.color='var(--danger)'; }
        } catch(e) { document.getElementById('wizardSoldierResult').textContent='✗ '+e; document.getElementById('wizardSoldierResult').style.color='var(--danger)'; }
    },

    fillSoldierTemplate(type) {
        const templates = {
            cav:   { no: '', name: '铁骑',   level: 3, hp: 60, atk: 12, def: 5, speed: 10, range: 1, cost: 300, troop: 3, objid: 0 },
            archer:{ no: '', name: '神射手', level: 2, hp: 35, atk: 10, def: 3, speed: 6,  range: 4, cost: 250, troop: 2, objid: 0 },
            infantry:{ no: '',name: '重甲兵', level: 2, hp: 100,atk: 6,  def: 9, speed: 4,  range: 1, cost: 200, troop: 2, objid: 0 },
            caster:{ no: '', name: '军师团', level: 3, hp: 25, atk: 5,  def: 2, speed: 5,  range: 3, cost: 350, troop: 1, objid: 0 },
        };
        const t = templates[type] || templates.cav;
        const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
        setVal('ws_no', t.no);
        setVal('ws_name', t.name);
        setVal('ws_level', t.level);
        setVal('ws_hp', t.hp);
        setVal('ws_atk', t.atk);
        setVal('ws_def', t.def);
        setVal('ws_speed', t.speed);
        setVal('ws_range', t.range);
        setVal('ws_cost', t.cost);
        setVal('ws_troop', t.troop);
        setVal('ws_objid', t.objid);
        showToast(`已加载模板: ${t.name}（请填写编号）`, 'info');
    },

    // ========== 势力创建向导 ==========
    showNationForm() {
        document.getElementById('wizardGeneralForm').style.display = 'none';
        document.getElementById('wizardSoldierForm').style.display = 'none';
        document.getElementById('wizardItemForm').style.display = 'none';
        document.getElementById('wizardNationForm').style.display = 'block';
    },

    async createNation() {
        if (!(await validateBeforeSave())) return;
        const no = parseInt(document.getElementById('wn_no').value);
        const name = document.getElementById('wn_name').value.trim();
        if (!no || !name) { showToast('编号和国号不能为空', 'info'); return; }

        const getVal = (id, def) => { const v = document.getElementById(id).value; return v ? parseInt(v) : def; };
        try {
            const r = await pyApi('wizardCreateNation', no, name,
                getVal('wn_color', 0), getVal('wn_lord', 0), getVal('wn_advisor', 0),
                getVal('wn_capital', 0),
                document.getElementById('wn_cities').value.trim(),
                document.getElementById('wn_generals').value.trim(),
                getVal('wn_money', 10000), getVal('wn_food', 50000),
                getVal('wn_soldier', 10000), getVal('wn_bgm', 8)
            );
            const el = document.getElementById('wizardNationResult');
            if (r && r.success) {
                el.textContent = '✓ ' + r.message;
                el.style.color = 'var(--success)';
                showToast('创建成功!\n\n已联动写入:\n✓ Nation.ini\n✓ Color.ini\n✓ City.ini\n✓ City01-10.ini (10个剧本)\n✓ General01.ini (Lord字段)\n✓ TermText.ini\n\n请前往势力编辑器确认详情。', 'success');
            } else { el.textContent = '✗ '+(r?r.message:'失败'); el.style.color='var(--danger)'; }
        } catch(e) { document.getElementById('wizardNationResult').textContent='✗ '+e; document.getElementById('wizardNationResult').style.color='var(--danger)'; }
    },

    // ========== 物品创建向导 ==========
    showItemForm() {
        document.getElementById('wizardGeneralForm').style.display = 'none';
        document.getElementById('wizardSoldierForm').style.display = 'none';
        document.getElementById('wizardNationForm').style.display = 'none';
        document.getElementById('wizardItemForm').style.display = 'block';
    },

    async createItem() {
        if (!(await validateBeforeSave())) return;
        const no = parseInt(document.getElementById('wi_no').value);
        const name = document.getElementById('wi_name').value.trim();
        if (!no || !name) { showToast('编号和名称不能为空', 'info'); return; }

        const getVal = (id, def) => { const v = document.getElementById(id).value; return v ? parseInt(v) : def; };
        const desc = document.getElementById('wi_desc').value.trim();
        try {
            const r = await pyApi('wizardCreateItem', no, name,
                getVal('wi_type', 2), getVal('wi_price', 100),
                getVal('wi_rare', 0), getVal('wi_icon', 0),
                getVal('wi_script', 0), getVal('wi_level', 1),
                getVal('wi_str', 0), getVal('wi_int', 0),
                getVal('wi_hp', 0), getVal('wi_mp', 0),
                desc
            );
            const el = document.getElementById('wizardItemResult');
            if (r && r.success) {
                el.textContent = '✓ ' + r.message;
                el.style.color = 'var(--success)';
                showToast('创建成功!\n\n已联动写入:\n✓ Thing.ini\n✓ TermText.ini (名称+描述)\n\n提示: 记得在物品编辑器中完善其他属性，并导入图标SHP到 Shape/ThingIcon/。', 'success');
            } else { el.textContent = '✗ '+(r?r.message:'失败'); el.style.color='var(--danger)'; }
        } catch(e) { document.getElementById('wizardItemResult').textContent='✗ '+e; document.getElementById('wizardItemResult').style.color='var(--danger)'; }
    },

    async showCustomLeaders() {
        try {
            const r = await pyApi('customLeaderLoad');
            if (r && r.success && r.leaders) {
                let msg = `自建武将: ${r.count} 个\n\n`;
                r.leaders.forEach(l => {
                    msg += `#${l.index}: ${l.name} (武${l.str_val}/智${l.int_val}/体${l.hp}/技${l.mp})\n`;
                });
                if (r.count === 0) msg += '暂无自建武将数据';
                showToast(msg, 'info');
            } else {
                showToast('读取失败: ' + (r ? r.message : ''), 'error');
            }
        } catch(e) { showToast('读取失败: '+e, 'error'); }
    },
};

// ============================================================
// 存档管理器
// ============================================================
const saveMgr = {
    async init() {
        await this.loadSaves();
        await this.loadBackups();
    },

    async loadSaves() {
        const el = document.getElementById('saveFileList');
        if (!el) return;
        el.innerHTML = '<p class="loading">加载中...</p>';
        try {
            const r = await pyApi('saveList');
            if (!r || !r.success) { el.innerHTML = '<p class="hint">' + (r ? r.message : '加载失败') + '</p>'; return; }
            document.getElementById('saveDirInfo').textContent = r.save_dir || '未知';
            if (!r.saves.length) { el.innerHTML = '<p class="hint">未找到存档文件</p>'; return; }
            el.innerHTML = r.saves.map(s => `<div class="list-item" onclick="saveMgr.selectSave('${escHtml(s.name)}')" style="cursor:pointer;">
                <span><b>${escHtml(s.name)}</b> <span class="tag">${s.type==='game_save'?'游戏存档':'自定义武将'}</span></span>
                <span style="color:var(--text-muted);font-size:11px;">${s.size_kb}KB | ${s.modified}</span></div>`).join('');
        } catch(e) { el.innerHTML = '<p class="hint">加载失败: ' + escHtml(String(e)) + '</p>'; }
    },

    async loadBackups() {
        const el = document.getElementById('saveBackupList');
        if (!el) return;
        el.innerHTML = '<p class="loading">加载中...</p>';
        try {
            const r = await pyApi('saveListBackups');
            if (!r || !r.success) { el.innerHTML = '<p class="hint">加载失败</p>'; return; }
            if (!r.backups.length) { el.innerHTML = '<p class="hint">暂无备份</p>'; return; }
            el.innerHTML = r.backups.map(b => `<div class="list-item" style="font-size:12px;">
                <span>${escHtml(b.name)}</span>
                <span style="color:var(--text-muted);font-size:10px;">${b.size_kb}KB | ${b.modified}</span>
                <div><button class="btn btn-outline btn-sm" onclick="saveMgr.restoreBackup('${escHtml(b.path).replace(/'/g,"\\'")}','${escHtml(b.orig_name)}')">还原</button>
                <button class="btn btn-sm btn-danger" onclick="saveMgr.deleteBackup('${escHtml(b.path).replace(/'/g,"\\'")}')">删除</button></div></div>`).join('');
        } catch(e) { el.innerHTML = '<p class="hint">加载失败: ' + escHtml(String(e)) + '</p>'; }
    },

    async selectSave(name) {
        document.getElementById('saveDetailName').textContent = name;
        document.getElementById('saveDetailCard').style.display = 'block';
        // 分析
        try {
            const r = await pyApi('saveAnalyze', name);
            if (r && r.success) {
                document.getElementById('saveAnalyzeInfo').innerHTML = 
                    `<b>格式:</b> ${escHtml(r.format||'未知')} | <b>大小:</b> ${(r.file_size/1024).toFixed(1)}KB | <b>Magic:</b> ${r.header_magic||'?'}`;
            }
        } catch(e) { showToast('存档分析失败: ' + e.message, 'error'); }
        // 查看十六进制
        this._viewHex(name, 0);
    },

    async _viewHex(name, offset) {
        const el = document.getElementById('saveHexView');
        if (!el) return;
        el.textContent = '加载中...';
        try {
            const r = await pyApi('saveHexView', name, offset, 1024);
            if (r && r.success) {
                el.textContent = r.hex_dump || '(空)';
                document.getElementById('saveHexInfo').textContent = 
                    `偏移: 0x${offset.toString(16).toUpperCase()} | 大小: ${(r.file_size/1024).toFixed(1)}KB`;
            }
        } catch(e) { el.textContent = '加载失败: ' + e; }
    },

    hexPrev() {
        const name = document.getElementById('saveDetailName').textContent;
        const info = document.getElementById('saveHexInfo').textContent;
        const m = info.match(/偏移: 0x([0-9A-Fa-f]+)/);
        let offset = m ? parseInt(m[1], 16) : 0;
        offset = Math.max(0, offset - 1024);
        this._viewHex(name, offset);
    },

    hexNext() {
        const name = document.getElementById('saveDetailName').textContent;
        const info = document.getElementById('saveHexInfo').textContent;
        const m = info.match(/偏移: 0x([0-9A-Fa-f]+)/);
        let offset = m ? parseInt(m[1], 16) : 0;
        offset += 1024;
        this._viewHex(name, offset);
    },

    async backupSave() {
        const name = prompt('输入要备份的存档文件名 (如 SG7-001.sav):');
        if (!name) return;
        try {
            const r = await pyApi('saveBackup', name);
            showToast(r && r.success ? r.message : '备份失败: ' + (r ? r.message : ''), 'info');
            if (r && r.success) await this.loadBackups();
        } catch(e) { showToast('备份失败: ' + e, 'error'); }
    },

    async restoreBackup(path, name) {
        if (!confirm(`确定要用备份还原 ${name}？当前存档将被覆盖。`)) return;
        try {
            const r = await pyApi('saveRestore', path, name);
            showToast(r && r.success ? r.message : '还原失败: ' + (r ? r.message : ''), 'info');
            if (r && r.success) await this.loadSaves();
        } catch(e) { showToast('还原失败: ' + e, 'error'); }
    },

    async deleteBackup(path) {
        if (!confirm('确定删除此备份？')) return;
        try {
            const r = await pyApi('saveDeleteBackup', path);
            showToast(r && r.success ? r.message : '删除失败', 'info');
            if (r && r.success) await this.loadBackups();
        } catch(e) { showToast('删除失败: ' + e, 'error'); }
    },

    snapshot() { return JSON.stringify({}); },
    restoreSnapshot() {},
};

// ============================================================
// 分辨率预设
// ============================================================
const resolutionPresets = {
    async apply(preset) {
        try {
            var r = await pyApi('applyResolutionPreset', preset);
            if (r.success) {
                showToast(r.message, 'success');
                document.getElementById('resolutionPresetResult').textContent = '已应用: ' + r.message;
            } else {
                showToast(r.message, 'error');
            }
        } catch(e) {
            showToast('应用失败: ' + e, 'error');
        }
    }
};

// ============================================================
// 小地图 BMP→RAW 转换
// ============================================================
const bmp2rawTool = {
    async convert() {
        var path = document.getElementById('bmp2rawPath').value.trim();
        if (!path) {
            showToast('请输入BMP文件路径', 'error');
            return;
        }
        try {
            var r = await pyApi('bmp2raw', path);
            var el = document.getElementById('bmp2rawResult');
            if (r.success) {
                el.innerHTML = '<span style="color:var(--success);">转换成功！</span> 输出: ' + escHtml(r.raw_path) + ' (' + r.size + ' bytes)';
                showToast(r.message, 'success');
            } else {
                el.innerHTML = '<span style="color:var(--danger);">错误: ' + escHtml(r.message) + '</span>';
                showToast(r.message, 'error');
            }
        } catch(e) {
            showToast('转换失败: ' + e, 'error');
        }
    }
};

// ============================================================
// CSV 批量导入/导出
// ============================================================
const csvTools = {
    async importCSV() {
        var type = document.getElementById('csvImportType').value;
        var path = document.getElementById('csvImportPath').value.trim();
        var el = document.getElementById('csvImportResult');
        if (!type) {
            el.innerHTML = '<span style="color:var(--danger);">请选择目标类型</span>';
            showToast('请选择目标类型', 'error');
            return;
        }
        if (!path) {
            el.innerHTML = '<span style="color:var(--danger);">请输入CSV文件路径</span>';
            showToast('请输入CSV文件路径', 'error');
            return;
        }
        try {
            el.innerHTML = '<span style="color:var(--text-muted);">导入中...</span>';
            var r = await pyApi('csvImport', type, path);
            if (r.success) {
                el.innerHTML = '<span style="color:var(--success);">导入成功！</span> ' + escHtml(r.message || '');
                showToast('CSV导入成功', 'success');
                this.showImportPreview();
            } else {
                el.innerHTML = '<span style="color:var(--danger);">错误: ' + escHtml(r.message) + '</span>';
                showToast(r.message || '导入失败', 'error');
            }
        } catch(e) {
            el.innerHTML = '<span style="color:var(--danger);">导入异常: ' + escHtml(String(e)) + '</span>';
            showToast('导入失败: ' + e, 'error');
        }
    },
    async exportCSV() {
        var type = document.getElementById('csvExportType').value;
        var path = document.getElementById('csvExportPath').value.trim();
        var el = document.getElementById('csvExportResult');
        if (!type) {
            el.innerHTML = '<span style="color:var(--danger);">请选择源类型</span>';
            showToast('请选择源类型', 'error');
            return;
        }
        try {
            el.innerHTML = '<span style="color:var(--text-muted);">导出中...</span>';
            var r = await pyApi('csvExport', type, path || null);
            if (r.success) {
                el.innerHTML = '<span style="color:var(--success);">导出成功！</span> ' + escHtml(r.message || '');
                showToast('CSV导出成功', 'success');
            } else {
                el.innerHTML = '<span style="color:var(--danger);">错误: ' + escHtml(r.message) + '</span>';
                showToast(r.message || '导出失败', 'error');
            }
        } catch(e) {
            el.innerHTML = '<span style="color:var(--danger);">导出异常: ' + escHtml(String(e)) + '</span>';
            showToast('导出失败: ' + e, 'error');
        }
    },
    async confirmImport() {
        const type = document.getElementById('csvImportType').value;
        if (!type) { showToast('请选择目标类型', 'warning'); return; }
        const filePath = _csvImportContext.csvPath;
        if (!filePath) { showToast('请先选择CSV文件', 'warning'); return; }
        const res = await pyApi('csvConfirmImport', type, filePath);
        if (res.success) {
            showToast(res.message, 'success');
            document.getElementById('csvImportResult').innerHTML = 
                `<span style="color:green;">&#10003; ${res.message}</span>`;
            document.getElementById('csvConfirmPanel').style.display = 'none';
        } else {
            showToast(res.message, 'error');
        }
    },

    cancelImport() {
        document.getElementById('csvConfirmPanel').style.display = 'none';
        document.getElementById('csvImportResult').textContent = '';
    },

    async showImportPreview() {
        const type = document.getElementById('csvImportType').value;
        if (!type) { showToast('请选择目标类型', 'warning'); return; }
        const res = await pyApi('csvGetFields', type);
        if (res.success && res.data) {
            const fields = Array.isArray(res.data) ? res.data : Object.keys(res.data);
            document.getElementById('csvConfirmFields').innerHTML = 
                `<p style="font-weight:600;">目标类型: ${type}</p>
                <p>字段列表: ${fields.slice(0,20).join(', ')}${fields.length > 20 ? '...' : ''}</p>`;
            document.getElementById('csvConfirmPanel').style.display = 'block';
        } else {
            showToast(res.message || '无法获取字段信息', 'error');
        }
    },
};

// ============================================================
// 区块定位计算器
// ============================================================
const blockCalc = {
    async calc() {
        var x = parseInt(document.getElementById('bcX').value) || 0;
        var y = parseInt(document.getElementById('bcY').value) || 0;
        try {
            var r = await pyApi('blockCalc', x, y);
            var el = document.getElementById('bcResult');
            if (r.success) {
                el.innerHTML = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;">' +
                    '<div><b>像素坐标:</b> (' + r.x + ', ' + r.y + ')</div>' +
                    '<div><b>网格坐标:</b> (' + r.grid_x + ', ' + r.grid_y + ')</div>' +
                    '<div><b>区块号:</b> <span style="color:var(--accent);font-size:16px;">' + r.block_no + '</span></div>' +
                    '<div><b>区块大小:</b> ' + r.block_size + '×' + r.block_size + ' px</div>' +
                    '<div style="grid-column:1/-1;font-size:11px;color:var(--text-muted);">网格: ' + r.grid_cols + '×' + r.grid_rows + ' 区块</div>' +
                    '</div>';
            } else {
                el.innerHTML = '<p style="color:var(--danger);">' + escHtml(r.message) + '</p>';
            }
        } catch(e) {
            document.getElementById('bcResult').innerHTML = '<p style="color:var(--danger);">计算失败: ' + e + '</p>';
        }
    },
    async inverse() {
        var block = parseInt(document.getElementById('bcBlock').value) || 0;
        try {
            var r = await pyApi('blockInverse', block);
            var el = document.getElementById('bcInvResult');
            if (r.success) {
                el.innerHTML = '<div><b>区块号:</b> <span style="color:var(--accent);font-size:16px;">' + r.block_no + '</span>' +
                    ' | <b>网格:</b> (' + r.grid_x + ', ' + r.grid_y + ')' +
                    ' | <b>X:</b> ' + r.x_min + '~' + r.x_max + ' | <b>Y:</b> ' + r.y_min + '~' + r.y_max + '</div>';
            } else {
                el.innerHTML = '<p style="color:var(--danger);">' + escHtml(r.message) + '</p>';
            }
        } catch(e) {
            document.getElementById('bcInvResult').innerHTML = '<p style="color:var(--danger);">计算失败: ' + e + '</p>';
        }
    },
    async loadCities() {
        try {
            var r = await pyApi('loadMapSummary');
            var el = document.getElementById('bcCityList');
            if (r.success && r.summary) {
                var s = r.summary;
                var html = '<div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">地图: ' + s.map_size[0] + '×' + s.map_size[1] + ' px, 网格: ' + s.grid[0] + '×' + s.grid[1] + '</div>';
                html += '<table style="width:100%;font-size:11px;border-collapse:collapse;"><thead><tr style="background:var(--bg-page);">' +
                    '<th>No</th><th>X</th><th>Y</th><th>GX</th><th>GY</th><th>区块</th></tr></thead><tbody>';
                for (var i = 0; i < s.cities.length; i++) {
                    var c = s.cities[i];
                    html += '<tr><td>' + escHtml(c.no) + '</td><td>' + c.x + '</td><td>' + c.y + '</td><td>' + c.grid_x + '</td><td>' + c.grid_y + '</td><td style="color:var(--accent);">' + c.block_no + '</td></tr>';
                }
                html += '</tbody></table>';
                el.innerHTML = html;
            } else {
                el.innerHTML = '<p style="color:var(--danger);">加载失败</p>';
            }
        } catch(e) {
            document.getElementById('bcCityList').innerHTML = '<p style="color:var(--danger);">加载失败: ' + e + '</p>';
        }
    }
};

// ============================================================
// PCK 资源预览增强
// ============================================================
const pckPreview = {
    _files: [],
    async loadPckList() {
        var pck = document.getElementById('pckPreviewSelect').value;
        if (!pck) { showToast('请选择PCK文件', 'error'); return; }
        try {
            var r = await pyApi('pckListFiles', pck);
            if (r.success && r.files) {
                this._files = r.files;
                this.renderFileList();
            } else {
                showToast(r.message || '加载失败', 'error');
            }
        } catch(e) {
            showToast('加载失败: ' + e, 'error');
        }
    },
    renderFileList() {
        var el = document.getElementById('pckPreviewFileList');
        var filter = (document.getElementById('pckFileFilter').value || '').toLowerCase();
        var html = '';
        for (var i = 0; i < this._files.length; i++) {
            var f = this._files[i];
            var name = f.name || f;
            if (filter && name.toLowerCase().indexOf(filter) === -1) continue;
            var isShp = name.toLowerCase().endsWith('.shp');
            var size = f.size ? (f.size > 1024 ? Math.round(f.size/1024) + 'KB' : f.size + 'B') : '';
            html += '<div style="padding:3px 6px;cursor:pointer;border-bottom:1px solid var(--border);" onmouseover="this.style.background=\'var(--bg-page)\'" onmouseout="this.style.background=\'\'" onclick="pckPreview.previewFile(\'' + escHtml(name).replace(/'/g, "\\'") + '\')"><span>' + (isShp ? '🖼 ' : '📄 ') + escHtml(name) + '</span><span style="color:var(--text-muted);float:right;">' + size + '</span></div>';
        }
        el.innerHTML = html || '<p style="color:var(--text-muted);padding:8px;">无匹配文件</p>';
    },
    filterFiles() { this.renderFileList(); },
    async previewFile(name) {
        var pck = document.getElementById('pckPreviewSelect').value;
        var area = document.getElementById('pckPreviewArea');
        if (!name.toLowerCase().endsWith('.shp')) {
            area.innerHTML = '<div style="text-align:center;color:var(--text-muted);"><p>非图片文件</p><p style="font-size:11px;">' + escHtml(name) + '</p></div>';
            return;
        }
        area.innerHTML = '<div style="text-align:center;color:var(--text-muted);"><div class="spinner" style="margin:20px auto;"></div><p>加载预览...</p></div>';
        try {
            var r = await pyApi('pckPreviewShp', pck, name);
            if (r.success) {
                area.innerHTML = '<div style="text-align:center;">' +
                    '<img src="' + r.base64 + '" style="max-width:100%;max-height:450px;image-rendering:pixelated;border:1px solid var(--border);">' +
                    '<p style="font-size:11px;color:var(--text-muted);margin-top:4px;">' + escHtml(name) + ' | ' + r.width + '×' + r.height + ' | ' + (r.size > 1024 ? Math.round(r.size/1024) + 'KB' : r.size + 'B') + '</p></div>';
            } else {
                area.innerHTML = '<p style="color:var(--danger);text-align:center;">' + escHtml(r.message) + '</p>';
            }
        } catch(e) {
            area.innerHTML = '<p style="color:var(--danger);text-align:center;">预览失败: ' + e + '</p>';
        }
    }
};

// ============================================================
// 大地图可视化编辑器
// ============================================================
const mapEditor = {
    _cities: [],
    _buildings: [],
    _showLabels: true,
    _editMode: false,
    _selectedCityIdx: -1,
    _scale: 0.0625,
    _offsetX: 0,
    _offsetY: 0,
    _dragging: false,
    _dragStartX: 0,
    _dragStartY: 0,
    _dragOffX: 0,
    _dragOffY: 0,
    _changed: false,

    async loadMap() {
        try {
            var r = await pyApi('loadMapSummary');
            if (r.success && r.summary) {
                this._cities = r.summary.cities || [];
                this._buildings = r.summary.buildings || [];
                this._scale = 1092 / r.summary.map_size[0];
                this._offsetX = 0;
                this._offsetY = 0;
                this._changed = false;
                this.render();
                showToast('加载完成: ' + this._cities.length + ' 城池, ' + this._buildings.length + ' 建筑', 'success');
            } else {
                showToast(r.message || '加载失败', 'error');
            }
        } catch(e) {
            showToast('加载失败: ' + e, 'error');
        }
    },

    toggleEdit() {
        this._editMode = !this._editMode;
        this._selectedCityIdx = -1;
        var btn = document.getElementById('mapEditBtn');
        if (btn) btn.textContent = this._editMode ? '退出编辑' : '编辑模式';
        if (btn) btn.style.background = this._editMode ? 'var(--accent)' : '';
        var canvas = document.getElementById('mapCanvas');
        if (canvas) canvas.style.cursor = this._editMode ? 'crosshair' : 'grab';
        this.render();
    },

    async saveChanges() {
        if (!this._changed) { showToast('没有修改', 'info'); return; }
        if (!confirm('确认保存城池位置修改? 将更新 City.ini 中的坐标数据')) return;
        try {
            var r = await pyApi('saveMapPositions', this._cities);
            if (r && r.success) {
                this._changed = false;
                showToast('保存成功: ' + r.message, 'success');
            } else {
                showToast('保存失败: ' + (r ? r.message : ''), 'error');
            }
        } catch(e) { showToast('保存失败: ' + e, 'error'); }
    },

    _findCityAt(mx, my) {
        for (var i = this._cities.length - 1; i >= 0; i--) {
            var c = this._cities[i];
            var cx = c.x * this._scale + this._offsetX;
            var cy = c.y * this._scale + this._offsetY;
            if (Math.abs(mx - cx) < 8 && Math.abs(my - cy) < 8) return i;
        }
        return -1;
    },

    render() {
        var canvas = document.getElementById('mapCanvas');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        var w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = '#1a2a1a';
        ctx.fillRect(0, 0, w, h);
        var gs = 32 * this._scale;
        ctx.strokeStyle = 'rgba(255,255,255,0.04)';
        ctx.lineWidth = 0.5;
        for (var gx = 0; gx < w; gx += gs) {
            ctx.beginPath(); ctx.moveTo(gx + this._offsetX % gs, 0); ctx.lineTo(gx + this._offsetX % gs, h); ctx.stroke();
        }
        for (var gy = 0; gy < h; gy += gs) {
            ctx.beginPath(); ctx.moveTo(0, gy + this._offsetY % gs); ctx.lineTo(w, gy + this._offsetY % gs); ctx.stroke();
        }
        for (var i = 0; i < this._buildings.length; i++) {
            var b = this._buildings[i];
            var bx = b.x * this._scale + this._offsetX;
            var by = b.y * this._scale + this._offsetY;
            ctx.fillStyle = 'rgba(100,100,255,0.6)';
            ctx.fillRect(bx - 2, by - 2, 4, 4);
        }
        for (var i = 0; i < this._cities.length; i++) {
            var c = this._cities[i];
            var cx = c.x * this._scale + this._offsetX;
            var cy = c.y * this._scale + this._offsetY;
            var isSelected = (i === this._selectedCityIdx);
            var radius = isSelected ? 7 : 4;
            ctx.fillStyle = isSelected ? '#ffaa00' : '#ff4444';
            ctx.beginPath();
            ctx.arc(cx, cy, radius, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = isSelected ? '#ffcc00' : '#ff8888';
            ctx.lineWidth = isSelected ? 2 : 1;
            ctx.stroke();
            if (this._showLabels && this._scale > 0.03) {
                ctx.fillStyle = '#fff';
                ctx.font = (isSelected ? 'bold ' : '') + '9px sans-serif';
                ctx.fillText(c.no + (c.name ? ' ' + c.name : ''), cx + 8, cy + 3);
            }
        }
        // Edit mode hint
        if (this._editMode) {
            ctx.fillStyle = 'rgba(255,170,0,0.15)';
            ctx.fillRect(0, 0, w, 20);
            ctx.fillStyle = '#ffaa00';
            ctx.font = '11px sans-serif';
            ctx.fillText('编辑模式: 点击城池选中, 拖拽移动位置', 8, 14);
            if (this._changed) {
                ctx.fillStyle = '#ff4444';
                ctx.fillText('● 已修改(未保存)', 230, 14);
            }
        }
        document.getElementById('mapZoom').textContent = Math.round(1 / this._scale) + ':1';
        document.getElementById('mapOffset').textContent = '(' + Math.round(-this._offsetX / this._scale) + ', ' + Math.round(-this._offsetY / this._scale) + ')';
    },

    toggleCities() { this._showLabels = !this._showLabels; this.render(); },
    zoomIn() { this._scale = Math.min(1, this._scale * 1.5); this.render(); },
    zoomOut() { this._scale = Math.max(0.01, this._scale / 1.5); this.render(); },
    resetView() { this._scale = 1092 / 17472; this._offsetX = 0; this._offsetY = 0; this.render(); },

    onMouseDown(e) {
        var rect = e.target.getBoundingClientRect();
        var scaleX = 1092 / rect.width;
        var scaleY = 774 / rect.height;
        var mx = (e.clientX - rect.left) * scaleX;
        var my = (e.clientY - rect.top) * scaleY;
        if (this._editMode) {
            var ci = this._findCityAt(mx, my);
            if (ci >= 0) {
                this._selectedCityIdx = ci;
                this._dragging = true;
                this._dragStartX = e.clientX;
                this._dragStartY = e.clientY;
                this._dragOffX = this._cities[ci].x;
                this._dragOffY = this._cities[ci].y;
                e.target.style.cursor = 'grabbing';
                this.render();
                return;
            }
            this._selectedCityIdx = -1;
            this.render();
            return;
        }
        this._dragging = true;
        this._dragStartX = e.clientX;
        this._dragStartY = e.clientY;
        this._dragOffX = this._offsetX;
        this._dragOffY = this._offsetY;
        e.target.style.cursor = 'grabbing';
    },

    onMouseMove(e) {
        var rect = e.target.getBoundingClientRect();
        var scaleX = 1092 / rect.width;
        var scaleY = 774 / rect.height;
        var mx = (e.clientX - rect.left) * scaleX;
        var my = (e.clientY - rect.top) * scaleY;
        var mapX = Math.round((mx - this._offsetX) / this._scale);
        var mapY = Math.round((my - this._offsetY) / this._scale);
        document.getElementById('mapMouse').textContent = (mapX >= 0 && mapY >= 0) ? '(' + mapX + ', ' + mapY + ')' : '超出范围';
        if (this._dragging) {
            if (this._editMode && this._selectedCityIdx >= 0) {
                var dx = (e.clientX - this._dragStartX) / this._scale;
                var dy = (e.clientY - this._dragStartY) / this._scale;
                this._cities[this._selectedCityIdx].x = Math.round(this._dragOffX + dx);
                this._cities[this._selectedCityIdx].y = Math.round(this._dragOffY + dy);
                this._changed = true;
                this.render();
            } else {
                this._offsetX = this._dragOffX + (e.clientX - this._dragStartX) * scaleX;
                this._offsetY = this._dragOffY + (e.clientY - this._dragStartY) * scaleY;
                this.render();
            }
        } else if (this._editMode) {
            var ci = this._findCityAt(mx, my);
            e.target.style.cursor = ci >= 0 ? 'pointer' : 'crosshair';
        }
    },

    onMouseUp(e) {
        this._dragging = false;
        e.target.style.cursor = this._editMode ? 'crosshair' : 'grab';
    },

    onWheel(e) {
        e.preventDefault();
        this._scale = Math.max(0.01, Math.min(1, this._scale * (e.deltaY < 0 ? 1.1 : 0.9)));
        this.render();
    }
};

// ============================================================
// 运行时内存修改器
// ============================================================
const memoryEditor = {
    async attach() {
        try {
            var r = await pyApi('memoryAttach');
            if (r.success) {
                document.getElementById('memStatus').innerHTML = '<span style="color:var(--success);">已连接: ' + escHtml(r.process) + ' (PID: ' + r.pid + ')</span>';
                document.getElementById('memAttachBtn').style.display = 'none';
                document.getElementById('memDetachBtn').style.display = '';
                showToast(r.message, 'success');
            } else {
                showToast(r.message, 'error');
            }
        } catch(e) {
            showToast('附加失败: ' + e, 'error');
        }
    },
    detach() {
        document.getElementById('memStatus').innerHTML = '<span style="color:var(--text-muted);">已断开</span>';
        document.getElementById('memAttachBtn').style.display = '';
        document.getElementById('memDetachBtn').style.display = 'none';
        showToast('已断开连接', 'success');
    },
    async read() {
        var addr = document.getElementById('memReadAddr').value.trim();
        var size = parseInt(document.getElementById('memReadSize').value);
        if (!addr) { showToast('请输入地址', 'error'); return; }
        if (addr.toLowerCase().startsWith('0x')) addr = parseInt(addr, 16);
        else addr = parseInt(addr);
        try {
            var r = await pyApi('memoryRead', addr, size);
            var el = document.getElementById('memReadResult');
            if (r.success) {
                el.innerHTML = '<div><b>地址:</b> ' + escHtml('0x' + r.address.toString(16).toUpperCase()) +
                    ' | <b>值:</b> <span style="color:var(--accent);font-size:16px;">' + r.value + '</span>' +
                    ' | <b>Hex:</b> ' + r.hex + ' | <b>大小:</b> ' + r.size + 'B</div>';
            } else {
                el.innerHTML = '<p style="color:var(--danger);">' + escHtml(r.message) + '</p>';
            }
        } catch(e) {
            document.getElementById('memReadResult').innerHTML = '<p style="color:var(--danger);">读取失败: ' + e + '</p>';
        }
    },
    async write() {
        var addr = document.getElementById('memWriteAddr').value.trim();
        var val = parseInt(document.getElementById('memWriteVal').value) || 0;
        var size = parseInt(document.getElementById('memWriteSize').value);
        if (!addr) { showToast('请输入地址', 'error'); return; }
        if (addr.toLowerCase().startsWith('0x')) addr = parseInt(addr, 16);
        else addr = parseInt(addr);
        try {
            var r = await pyApi('memoryWrite', addr, val, size);
            var el = document.getElementById('memWriteResult');
            if (r.success) {
                el.innerHTML = '<div style="color:var(--success);">' + escHtml(r.message) + '</div>';
            } else {
                el.innerHTML = '<p style="color:var(--danger);">' + escHtml(r.message) + '</p>';
            }
        } catch(e) {
            document.getElementById('memWriteResult').innerHTML = '<p style="color:var(--danger);">写入失败: ' + e + '</p>';
        }
    },
    async search() {
        var val = parseInt(document.getElementById('memSearchVal').value) || 0;
        var size = parseInt(document.getElementById('memSearchSize').value);
        try {
            var r = await pyApi('memorySearch', val, size);
            var el = document.getElementById('memSearchResult');
            if (r.success) {
                var html = '<div style="color:var(--success);">找到 ' + r.count + ' 个结果</div>';
                if (r.addresses && r.addresses.length > 0) {
                    html += '<div style="font-family:monospace;font-size:11px;">';
                    for (var i = 0; i < r.addresses.length; i++) {
                        html += '<span style="display:inline-block;width:120px;padding:2px;">' + r.addresses[i] + '</span>';
                    }
                    html += '</div>';
                }
                el.innerHTML = html;
            } else {
                el.innerHTML = '<p style="color:var(--danger);">' + escHtml(r.message) + '</p>';
            }
        } catch(e) {
            document.getElementById('memSearchResult').innerHTML = '<p style="color:var(--danger);">搜索失败: ' + e + '</p>';
        }
    },
    async readPreset(name) {
        const res = await pyApi('memoryReadPreset', name);
        if (res.success) {
            document.getElementById('memPresetResult').innerHTML = 
                `<span style="color:var(--accent);font-weight:600;">${name}</span> = <span style="color:#ff6644;font-size:16px;">${res.value}</span> (${res.hex})`;
        } else {
            document.getElementById('memPresetResult').innerHTML = 
                `<span style="color:red;">错误: ${res.message}</span>`;
        }
    },
};

// 初始化向导
setTimeout(() => { try { wizard.init(); } catch(e) { showToast('向导初始化失败', 'error'); } }, 500);

// ============================================================
// 城池商店编辑器
// ============================================================
const citySellEditor = {
    data: [],
    async load() {
        const el = document.getElementById('citySellList');
        el.innerHTML = '<p class="loading">加载中...</p>';
        try {
let r = await pyApi('loadCitySellItems');
            r = r || {};
            this.data = r.data || [];
            this._render();
        } catch(e) { el.innerHTML = '<p class="err">加载失败: '+escHtml(String(e))+'</p>'; }
    },
    _render() {
        const el = document.getElementById('citySellList');
        if (!this.data.length) { el.innerHTML = '<p class="hint">暂无城池商店数据</p>'; return; }
        el.innerHTML = this.data.map((c,i)=>`<div class="panel-card">
            <div class="panel-card-header"><h3>城池 #${escHtml(c.City||'')} - ${escHtml(c.Name||'')}</h3><button class="btn btn-danger btn-xs" onclick="citySellEditor.deleteEntry(${i})" title="删除">✕</button></div>
            <div style="padding:12px;">
                <div class="form-row"><label>城池编号</label><input type="number" value="${escHtml(c.City||'')}" onchange="citySellEditor.data[${i}].City=this.value"></div>
                ${(c.items||[]).map(it=>`<div class="form-row"><label>物品位${it.index}</label><input type="number" value="${escHtml(it.item_id||'')}" placeholder="物品编号" onchange="citySellEditor.data[${i}].items[${it.index-1}].item_id=this.value"></div>`).join('')}
            </div>
        </div>`).join('');
    },
    async save() {
        if (!(await validateBeforeSave())) return;
        if (!confirm('确认保存城池商店配置?')) return;
        this.pushUndo();
        try {
let r = await pyApi('saveCitySellItems', this.data);
            r = r || {};
            showToast(r.success ? '保存成功: '+r.message : '保存失败: '+r.message, r.success ? 'success' : 'error');
        } catch(e) { showToast('保存失败: '+e, 'error'); }
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this.data));
    },

    restoreSnapshot(data) {
        this.data = JSON.parse(JSON.stringify(data));
        this._render();
    },

    pushUndo() {
        UndoManager.pushState('citySell', this.snapshot());
    },

    addNew() {
        this.pushUndo();
        const newEntry = { City: '', Name: '', items: [{ index: 1, item_id: '' }, { index: 2, item_id: '' }, { index: 3, item_id: '' }] };
        this.data.push(newEntry);
        this._render();
    },

    deleteEntry(idx) {
        if (!confirm(`确认删除城池商店 #${this.data[idx]?.City || idx + 1}?`)) return;
        this.pushUndo();
        pyApi('deleteIniItem', 'Setting/CitySellItem.ini', 'CITYSELLITEM', 'City', String(this.data[idx]?.City || ''));
        this.data.splice(idx, 1);
        this._render();
    },
};

// ============================================================
// 游戏文本编辑器
// ============================================================
const gameTextEditor = {
    sections: [],
    filtered: [],
    async load() {
        const el = document.getElementById('gameTextSections');
        el.innerHTML = '<p class="loading">加载中...</p>';
        try {
let r = await pyApi('loadGameText');
            r = r || {};
            this.sections = r.sections || [];
            this.filtered = this.sections;
            document.getElementById('gameTextCount').textContent = this.sections.length+'个分类';
            this._render();
        } catch(e) { el.innerHTML = '<p class="err">加载失败: '+escHtml(String(e))+'</p>'; }
    },
    _filter() {
        const q = (document.getElementById('gameTextSearch').value||'').toLowerCase();
        if (!q) {
            this.filtered = this.sections;
        } else {
            this.filtered = this.sections.filter(s=>{
                if (s.name.toLowerCase().includes(q)) return true;
                for (const [k,v] of Object.entries(s.entries||{})) {
                    if (k.toLowerCase().includes(q) || String(v).toLowerCase().includes(q)) return true;
                }
                return false;
            });
        }
        document.getElementById('gameTextCount').textContent = this.filtered.length+'/'+this.sections.length+'个分类';
        this._render();
    },
    _render() {
        const el = document.getElementById('gameTextSections');
        if (!this.filtered.length) { el.innerHTML = '<p class="hint">无匹配结果</p>'; return; }
        el.innerHTML = this.filtered.map((s,fi)=>{
            const si = this.sections.indexOf(s);
            const entries = Object.entries(s.entries||{});
            return `<details class="panel-card" style="margin-bottom:8px;" ${entries.length<=5?'open':''}>
                <summary style="cursor:pointer;padding:8px;font-weight:600;background:var(--bg-card);border-radius:6px;display:flex;justify-content:space-between;align-items:center;">
                    <span>[${escHtml(s.name)}] <span style="color:var(--text-muted);font-weight:400;">(${entries.length}条)</span></span>
                    <button class="btn btn-danger btn-xs" onclick="event.stopPropagation();gameTextEditor.deleteSection(${si})" title="删除此分类" style="margin-left:8px;">✕</button>
                </summary>
                <div style="padding:12px;">
                    ${entries.map(([k,v])=>`<div class="form-row" style="display:flex;align-items:center;gap:4px;"><label style="flex:0 0 100px;">${escHtml(k)}</label><input type="text" value="${escHtml(v||'')}" onchange="gameTextEditor.sections[${si}].entries['${escHtml(k)}']=this.value" style="flex:1;"><button class="btn btn-danger btn-xs" onclick="gameTextEditor.deleteEntry(${si},'${escHtml(k)}')" title="删除此条目" style="flex:0 0 auto;">✕</button></div>`).join('')}
                    ${entries.length===0?'<p class="hint">此分类无条目</p>':''}
                </div>
            </details>`;
        }).join('');
    },
    async save() {
        if (!(await validateBeforeSave())) return;
        if (!confirm('确认保存游戏文本? 此操作会覆盖 GameText.ini')) return;
        this.pushUndo();
        try {
let r = await pyApi('saveGameText', this.sections);
            r = r || {};
            showToast(r.success ? '保存成功: '+r.message : '保存失败: '+r.message, r.success ? 'success' : 'error');
        } catch(e) { showToast('保存失败: '+e, 'error'); }
    },

    deleteEntry(sectionIdx, key) {
        if (!confirm(`确认删除条目 "${key}"?`)) return;
        this.pushUndo();
        delete this.sections[sectionIdx].entries[key];
        this._render();
    },

    deleteSection(sectionIdx) {
        const s = this.sections[sectionIdx];
        if (!s) return;
        if (!confirm(`确认删除分类 "[${s.name}]" (${Object.keys(s.entries||{}).length}条)?`)) return;
        this.pushUndo();
        this.sections.splice(sectionIdx, 1);
        this.filtered = this.sections;
        this._render();
        document.getElementById('gameTextCount').textContent = this.sections.length+'个分类';
    },

    snapshot() {
        return JSON.parse(JSON.stringify(this.sections));
    },

    restoreSnapshot(data) {
        this.sections = JSON.parse(JSON.stringify(data));
        this.filtered = this.sections;
        this._render();
    },

    pushUndo() {
        UndoManager.pushState('gameText', this.snapshot());
    },
};

// 注册所有新tab切换
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-tab="pck"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>pckEditor.detect(),100)));
    document.querySelectorAll('[data-tab="shape"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>shapeBrowser.init(),100)));
    document.querySelectorAll('[data-tab="sfbridge"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>sfbridgeEditor.load(),100)));
    document.querySelectorAll('[data-tab="mapvis"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>mapVisEditor.init(),100)));
    document.querySelectorAll('[data-tab="effectEditor"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>effectEditor.init(),100)));
    document.querySelectorAll('[data-tab="savemgr"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>saveMgr.init(),100)));
    document.querySelectorAll('[data-tab="saveEditor"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>saveEditor.refresh(),100)));
    document.querySelectorAll('[data-tab="wizard"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>wizard.init(),100)));
    document.querySelectorAll('[data-tab="obd"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>obdEditor.load(),100)));
    document.querySelectorAll('[data-tab="citySell"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>citySellEditor.load(),100)));
    document.querySelectorAll('[data-tab="history"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>historyEditor.load(),100)));
    document.querySelectorAll('[data-tab="script"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>scriptEditor.load(),100)));
    document.querySelectorAll('[data-tab="scriptso"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>scriptsoEditor.load(),100)));
    document.querySelectorAll('[data-tab="gameText"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>gameTextEditor.load(),100)));
    document.querySelectorAll('[data-tab="matrix"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>matrixEditor.load(),100)));
    document.querySelectorAll('[data-tab="refcheck"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>refChecker.run(),100)));
    document.querySelectorAll('[data-tab="batch"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>batch.loadFiles(),100)));
    document.querySelectorAll('[data-tab="diff"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>diff.loadBackups(),100)));
    document.querySelectorAll('[data-tab="validation"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>validate.run(),100)));
    document.querySelectorAll('[data-tab="defskill"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>defskill.load(),100)));
    document.querySelectorAll('[data-tab="variableEditor"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>variableEditor.load(),100)));
    document.querySelectorAll('[data-tab="sango7Editor"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>sango7Editor.load(),100)));
    document.querySelectorAll('[data-tab="eventEditor"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>eventEditor.init(),100)));
});

// ============================================================
// CSV 导入导出
// ============================================================

// 当前 CSV 导入上下文
let _csvImportContext = { dataType: '', data: [], editorObj: null, csvPath: '' };

/** 选择 CSV 文件并预览 */
async function importCsv(dataType, editorObj) {
    try {
        // 先选择CSV文件
        const fileRes = await pyApi('selectCsvFile');
        if (!fileRes || !fileRes.success || !fileRes.path) {
            if (fileRes && fileRes.path === '') return; // 用户取消
            showToast('请选择CSV文件', 'warning');
            return;
        }
        const csvPath = fileRes.path;
        const res = await pyApi('csvImport', dataType, csvPath);
        if (res && res.success && res.data) {
            _csvImportContext.csvPath = csvPath;
            showCsvPreview(dataType, res, editorObj);
        } else if (res && res.message) {
            showToast(res.message, res && res.success ? 'success' : 'error');
        }
    } catch(e) {
        showToast('导入失败: ' + e.message, 'error');
    }
}

/** 显示 CSV 预览弹窗 */
function showCsvPreview(dataType, result, editorObj) {
    _csvImportContext = { dataType, data: result.data || [], editorObj };

    const meta = document.getElementById('csvMeta');
    const errors = document.getElementById('csvErrors');
    const table = document.getElementById('csvPreviewTable');

    meta.innerHTML = `编码: <span>${escHtml(result.encoding || '未知')}</span> | 共 <span>${result.count || 0}</span> 条记录`;
    if (result.field_map) {
        const mapped = Object.keys(result.field_map).length;
        meta.innerHTML += ` | 已映射 <span>${mapped}</span> 个字段`;
    }

    if (result.errors && result.errors.length > 0) {
        errors.style.display = 'block';
        errors.innerHTML = result.errors.map(e => `<div>${escHtml(e)}</div>`).join('');
    } else {
        errors.style.display = 'none';
    }

    // 渲染预览表格
    const preview = result.preview || result.data || [];
    if (preview.length > 0) {
        const headers = Object.keys(preview[0]);
        table.innerHTML = `
            <thead><tr>${headers.map(h => `<th>${escHtml(h)}</th>`).join('')}</tr></thead>
            <tbody>${preview.slice(0, 20).map(row =>
                `<tr>${headers.map(h => `<td>${escHtml(String(row[h] || ''))}</td>`).join('')}</tr>`
            ).join('')}</tbody>
        `;
        if (preview.length > 20) {
            table.innerHTML += `<tfoot><tr><td colspan="${headers.length}" style="text-align:center;color:var(--text-muted);">仅显示前20条，共 ${preview.length} 条</td></tr></tfoot>`;
        }
    } else {
        table.innerHTML = '<tr><td style="text-align:center;color:var(--text-muted);padding:20px;">无数据</td></tr>';
    }

    document.getElementById('csvModalOverlay').style.display = 'block';
    document.getElementById('csvModal').style.display = 'block';
}

/** 关闭 CSV 弹窗 */
function closeCsvModal() {
    document.getElementById('csvModalOverlay').style.display = 'none';
    document.getElementById('csvModal').style.display = 'none';
    _csvImportContext = { dataType: '', data: [], editorObj: null };
}

/** 确认导入 CSV 数据 */
function confirmCsvImport() {
    const ctx = _csvImportContext;
    if (!ctx.editorObj || !ctx.data.length) {
        closeCsvModal();
        return;
    }

    // 推入撤销快照
    if (ctx.editorObj.pushUndo) ctx.editorObj.pushUndo();

    // 合并数据：按 No 匹配更新，无匹配则追加
    const existingMap = {};
    if (ctx.editorObj.data) {
        ctx.editorObj.data.forEach((item, idx) => {
            existingMap[String(item.No)] = idx;
        });
    }

    let added = 0, updated = 0;
    ctx.data.forEach(row => {
        const no = String(row.No);
        if (no in existingMap) {
            // 更新现有记录
            const target = ctx.editorObj.data[existingMap[no]];
            Object.assign(target, row);
            updated++;
        } else {
            // 追加新记录
            ctx.editorObj.data.push(row);
            added++;
        }
    });

    // 刷新UI
    if (ctx.editorObj.renderList) ctx.editorObj.renderList();
    if (ctx.editorObj.changed !== undefined) ctx.editorObj.changed = true;

    // 自动保存到磁盘
    if (ctx.editorObj.save) {
        ctx.editorObj.save().then(() => {
            showToast(`导入完成：新增 ${added} 条，更新 ${updated} 条（已保存）`, 'info');
        }).catch(() => {
            showToast(`导入完成：新增 ${added} 条，更新 ${updated} 条（保存失败，请手动保存）`, 'info');
        });
    } else {
        showToast(`导入完成：新增 ${added} 条，更新 ${updated} 条`, 'info');
    }

    closeCsvModal();
}

/** 导出当前编辑器数据为 CSV */
async function exportCsv(dataType, editorObj) {
    try {
        const res = await pyApi('csvExport', dataType);
        if (res && res.success) {
            showToast(res.message, res && res.success ? 'success' : 'error');
        } else if (res && res.message) {
            showToast(res.message, res && res.success ? 'success' : 'error');
        }
    } catch(e) {
        showToast('导出失败: ' + e.message, 'error');
    }
}

// ============================================================
// 实时预览面板
// ============================================================

let _previewPanelType = '';

function togglePreviewPanel(type) {
    const panel = document.getElementById('previewPanel');
    if (type && type !== _previewPanelType) {
        _previewPanelType = type;
        panel.style.display = 'block';
        updatePreviewPanel(type);
    } else if (panel.style.display === 'none' || !panel.style.display) {
        panel.style.display = 'block';
        if (type) { _previewPanelType = type; updatePreviewPanel(type); }
    } else {
        panel.style.display = 'none';
        _previewPanelType = '';
    }
}

function toggleHelpPanel() {
    const panel = document.getElementById('helpPanel');
    panel.style.display = (panel.style.display === 'none' || !panel.style.display) ? 'block' : 'none';
}

function updatePreviewPanel(type) {
    const panel = document.getElementById('previewPanel');
    if (panel.style.display === 'none') return; // 面板未打开，跳过
    const body = document.getElementById('previewBody');
    let obj = null;

    switch (type) {
        case 'general':
            obj = generals.current;
            if (!obj) { body.innerHTML = '<p class="hint">选择一个武将查看预览</p>'; return; }
            body.innerHTML = `
                <div class="preview-card">
                    <div class="preview-card-title">${escHtml(obj.Name || '未命名')}</div>
                    <div class="preview-card-subtitle">编号: ${obj.No || '-'} | 性别: ${obj.Sex === '1' ? '女' : '男'} | 登场: ${obj.AppearYear || '-'}年</div>
                    <div class="preview-card-row"><span class="label">武力</span><span class="value">${obj.WStr || 0}</span></div>
                    <div class="preview-stat-bar"><div class="preview-stat-fill str" style="width:${Math.min((obj.WStr||0)/255*100, 100)}%"></div></div>
                    <div class="preview-card-row"><span class="label">智力</span><span class="value">${obj.Int || 0}</span></div>
                    <div class="preview-stat-bar"><div class="preview-stat-fill int" style="width:${Math.min((obj.Int||0)/255*100, 100)}%"></div></div>
                    <div class="preview-card-row"><span class="label">体力</span><span class="value">${obj.HP || 0}</span></div>
                    <div class="preview-stat-bar"><div class="preview-stat-fill hp" style="width:${Math.min((obj.HP||0)/999*100, 100)}%"></div></div>
                    <div class="preview-card-row"><span class="label">技力</span><span class="value">${obj.MP || 0}</span></div>
                    <div class="preview-stat-bar"><div class="preview-stat-fill mp" style="width:${Math.min((obj.MP||0)/999*100, 100)}%"></div></div>
                    <div class="preview-card-row"><span class="label">士气</span><span class="value">${obj.Morale || 0}</span></div>
                    <div class="preview-card-row"><span class="label">忠诚</span><span class="value">${obj.Loyal || 0}</span></div>
                    <div class="preview-card-row"><span class="label">生命</span><span class="value">${obj.Life || 0}</span></div>
                    <div class="preview-card-row"><span class="label">兵种</span><span class="value">${obj.BFSoldier || '-'}</span></div>
                    <div class="preview-card-row"><span class="label">阵型</span><span class="value">${obj.Formation || '-'}</span></div>
                    <div class="preview-card-row"><span class="label">武器</span><span class="value">${obj.Weapon || '-'}</span></div>
                    <div class="preview-card-row"><span class="label">坐骑</span><span class="value">${obj.Horse || '-'}</span></div>
                    <div class="preview-card-row"><span class="label">必杀技</span><span class="value">${obj.SuperSkill || '-'}</span></div>
                    <div class="preview-card-row"><span class="label">君主</span><span class="value">${obj.Lord || '-'}</span></div>
                    <div class="preview-card-row"><span class="label">父亲</span><span class="value">${obj.Father || '-'}</span></div>
                    <div class="preview-card-row"><span class="label">配偶</span><span class="value">${obj.Spouse || '-'}</span></div>
                </div>
            `;
            break;
        case 'soldier':
            obj = soldiers.current;
            if (!obj) { body.innerHTML = '<p class="hint">选择一个兵种查看预览</p>'; return; }
            body.innerHTML = `
                <div class="preview-card">
                    <div class="preview-card-title">${escHtml(obj.Name || '未命名')}</div>
                    <div class="preview-card-subtitle">编号: ${obj.No || '-'} | 类型: ${obj.Type || '-'}</div>
                    <div class="preview-card-row"><span class="label">生命</span><span class="value">${obj.Life || 0}</span></div>
                    <div class="preview-card-row"><span class="label">攻击</span><span class="value">${obj.BasePower || 0}</span></div>
                    <div class="preview-card-row"><span class="label">防御</span><span class="value">${obj.AddPower || 0}</span></div>
                    <div class="preview-card-row"><span class="label">速度</span><span class="value">${obj.Speed || 0}</span></div>
                    <div class="preview-card-row"><span class="label">阶级</span><span class="value">${obj.Rank || 0}</span></div>
                    <div class="preview-card-row"><span class="label">特性</span><span class="value">${obj.Special || '-'}</span></div>
                    <div class="preview-card-row"><span class="label">射程</span><span class="value">${obj.DetectRangeMax || '-'}</span></div>
                </div>
            `;
            break;
        case 'thing':
            obj = things.current;
            if (!obj) { body.innerHTML = '<p class="hint">选择一个物品查看预览</p>'; return; }
            body.innerHTML = `
                <div class="preview-card">
                    <div class="preview-card-title">${escHtml(obj.Name || '未命名')}</div>
                    <div class="preview-card-subtitle">编号: ${obj.No || '-'} | 类型: ${obj.Type || '-'} | 价格: ${obj.Price || 0}</div>
                    <div class="preview-card-row"><span class="label">武力</span><span class="value">${obj.WStr || 0}</span></div>
                    <div class="preview-card-row"><span class="label">智力</span><span class="value">${obj.Int || 0}</span></div>
                    <div class="preview-card-row"><span class="label">体力</span><span class="value">${obj.HP || 0}</span></div>
                    <div class="preview-card-row"><span class="label">技力</span><span class="value">${obj.MP || 0}</span></div>
                    <div class="preview-card-row"><span class="label">速度</span><span class="value">${obj.Speed || 0}</span></div>
                    <div class="preview-card-row"><span class="label">等级</span><span class="value">${obj.Level || 0}</span></div>
                    <div class="preview-card-row"><span class="label">技能</span><span class="value">${obj.Skill || '-'}</span></div>
                </div>
            `;
            break;
        default:
            body.innerHTML = '<p class="hint">选择编辑器条目查看预览</p>';
    }
}// 版本检测
async function detectVersion() {
    const el = document.getElementById('versionDetail');
    el.innerHTML = '<p class="loading">检测中...</p>';
    try {
        let r = await pyApi('detectGameVersion');
        r = r || {};
        if (!r.success) { el.innerHTML = '<p class="err">' + (r.message || '检测失败') + '</p>'; return; }
        el.innerHTML = `
            <div class="info-row"><span class="info-label">EXE类型:</span><span class="info-value">${r.exe_type || '未知'}</span></div>
            <div class="info-row"><span class="info-label">EXE大小:</span><span class="info-value">${r.exe_size_mb || 0} MB</span></div>
            <div class="info-row"><span class="info-label">PE时间戳:</span><span class="info-value">${r.pe_timestamp || '-'}</span></div>
            <div class="info-row"><span class="info-label">镜像大小:</span><span class="info-value">${r.image_size_mb || 0} MB</span></div>
            <div class="info-row"><span class="info-label">区段数:</span><span class="info-value">${r.sections || '-'}</span></div>
            <div class="info-row"><span class="info-label">MD5:</span><span class="info-value" style="font-size:11px;word-break:break-all;">${r.md5 || '-'}</span></div>
            <div class="info-row"><span class="info-label">完整性:</span><span class="info-value ${r.integrity_score===100?'text-success':'text-warning'}">${r.integrity_score}% (${(r.missing_files||[]).length}个文件缺失)</span></div>
            ${(r.recommendations||[]).length ? '<div style="margin-top:4px">' + r.recommendations.map(rec => '<p class="hint">⚠ ' + escHtml(rec) + '</p>').join('') + '</div>' : ''}
        `;
    } catch(e) { el.innerHTML = '<p class="err">检测失败: ' + escHtml(String(e)) + '</p>'; }
}

// ============================================================
// 新手引导向导
// ============================================================

const OnboardingWizard = {
    _currentStep: 0,
    _steps: [
        { id: 'set_path', title: '第1步：设置游戏目录', desc: '点击左侧"游戏设置"，选择三国群英传7的安装目录。这是制作MOD的第一步。',
          target: () => document.querySelector('[data-tab="settings"]'),
          placement: 'right' },
        { id: 'core_data', title: '第2步：编辑核心数据', desc: '在"🎮 核心数据"区，你可以编辑武将、兵种、物品等核心游戏数据。点击"武将编辑"试试看！',
          target: () => document.querySelector('[data-tab="generals"]'),
          placement: 'right' },
        { id: 'systems', title: '第3步：调整游戏系统', desc: '在"🏰 游戏系统"区，可以修改阵型、官职、剧本、势力等游戏机制。',
          target: () => document.querySelector('.nav-category:nth-of-type(2) .nav-category-header'),
          placement: 'right' },
        { id: 'tools', title: '第4步：使用工具集', desc: '在"🔧 工具集"区，可以进行备份、批量修改、差异对比、打包发布等操作。',
          target: () => document.querySelector('.nav-category:nth-of-type(5) .nav-category-header'),
          placement: 'right' },
        { id: 'wizard', title: '第5步：MOD制作向导', desc: '在工具集中找到"MOD制作向导"，它会引导你一步步完成MOD制作全流程。',
          target: () => document.querySelector('[data-tab="wizard"]'),
          placement: 'right' },
        { id: 'search', title: '第6步：快速搜索功能', desc: '顶部的搜索框可以跨模块搜索任何功能，输入关键词即可快速定位。',
          target: () => document.getElementById('navSearchInput'),
          placement: 'bottom' },
        { id: 'done', title: '准备就绪！', desc: '你已经了解了主要功能。现在可以开始制作你的第一个MOD了！记得随时保存修改。',
          target: null, placement: 'center' },
    ],

    show() {
        const overlay = document.getElementById('onboardingOverlay');
        if (overlay) overlay.style.display = 'block';
        this._currentStep = 0;
        this.renderStep();
    },

    hide() {
        const overlay = document.getElementById('onboardingOverlay');
        if (overlay) overlay.style.display = 'none';
        document.getElementById('onboardingCard').style.display = 'none';
        localStorage.setItem('san7_onboarding_done', '1');
    },

    next() {
        if (this._currentStep < this._steps.length - 1) {
            this._currentStep++;
            this.renderStep();
        } else {
            this.hide();
        }
    },

    prev() {
        if (this._currentStep > 0) {
            this._currentStep--;
            this.renderStep();
        }
    },

    renderStep() {
        const step = this._steps[this._currentStep];
        const card = document.getElementById('onboardingCard');
        const spotlight = document.getElementById('onboardingSpotlight');
        const target = step.target ? step.target() : null;

        // 更新卡片内容
        document.getElementById('onboardingStepNum').textContent = `${this._currentStep + 1}/${this._steps.length}`;
        document.getElementById('onboardingStepTitle').textContent = step.title;
        document.getElementById('onboardingStepDesc').textContent = step.desc;
        document.getElementById('onboardingPrevBtn').style.display = this._currentStep > 0 ? '' : 'none';
        document.getElementById('onboardingNextBtn').textContent = this._currentStep < this._steps.length - 1 ? '下一步 →' : '完成 ✓';
        document.getElementById('onboardingSkipBtn').style.display = this._currentStep < this._steps.length - 1 ? '' : 'none';

        const dots = document.getElementById('onboardingDots');
        if (dots) {
            dots.innerHTML = this._steps.map((s, i) =>
                `<span class="onboarding-dot ${i === this._currentStep ? 'active' : i < this._currentStep ? 'done' : ''}"></span>`
            ).join('');
        }

        card.style.display = 'block';

        if (!target) {
            // 最后一步：居中显示
            card.style.top = '50%';
            card.style.left = '50%';
            card.style.transform = 'translate(-50%, -50%)';
            spotlight.style.background = 'rgba(0,0,0,0.65)';
            return;
        }

        // 获取目标元素位置
        const rect = target.getBoundingClientRect();
        const cardW = 360;
        const cardH = card.offsetHeight || 220;

        // 创建镂空效果（使用 box-shadow 技巧）
        const x = rect.left, y = rect.top, w = rect.width, h = rect.height;
        const pad = 6;
        spotlight.style.background = 'rgba(0,0,0,0.65)';
        spotlight.style.clipPath = `polygon(0% 0%, 0% 100%, ${x-pad}px 100%, ${x-pad}px ${y-pad}px, ${x+w+pad}px ${y-pad}px, ${x+w+pad}px ${y+h+pad}px, ${x-pad}px ${y+h+pad}px, ${x-pad}px 100%, 100% 100%, 100% 0%)`;

        // 定位卡片
        let cardTop, cardLeft;
        const gap = 16;

        switch (step.placement) {
            case 'right':
                cardLeft = Math.min(x + w + gap, window.innerWidth - cardW - 20);
                cardTop = Math.max(20, Math.min(y + h/2 - cardH/2, window.innerHeight - cardH - 20));
                break;
            case 'bottom':
                cardLeft = Math.max(20, Math.min(x + w/2 - cardW/2, window.innerWidth - cardW - 20));
                cardTop = Math.min(y + h + gap, window.innerHeight - cardH - 20);
                break;
            case 'left':
                cardLeft = Math.max(20, x - cardW - gap);
                cardTop = Math.max(20, Math.min(y + h/2 - cardH/2, window.innerHeight - cardH - 20));
                break;
            case 'top':
                cardLeft = Math.max(20, Math.min(x + w/2 - cardW/2, window.innerWidth - cardW - 20));
                cardTop = Math.max(20, y - cardH - gap);
                break;
            default:
                cardLeft = Math.max(20, Math.min(x + w + gap, window.innerWidth - cardW - 20));
                cardTop = Math.max(20, Math.min(y + h/2 - cardH/2, window.innerHeight - cardH - 20));
        }

        card.style.top = cardTop + 'px';
        card.style.left = cardLeft + 'px';
        card.style.transform = 'none';

        // 高亮脉冲动画
        if (target) {
            target.style.animation = 'onboardingPulse 1.5s ease-in-out infinite';
        }
    },

    init() {
        if (localStorage.getItem('san7_onboarding_done')) return;
        // 延迟显示，让页面先加载
        setTimeout(() => this.show(), 800);
    }
};

// 新手引导高亮脉冲动画样式注入
(function() {
    const style = document.createElement('style');
    style.textContent = '@keyframes onboardingPulse{0%,100%{box-shadow:0 0 0 0 rgba(233,69,96,0.5);}50%{box-shadow:0 0 0 8px rgba(233,69,96,0);}}';
    document.head.appendChild(style);
})();

// ============================================================
// 编码转换器
// ============================================================
const encodingConverter = {
    _scanResult: null,
    _previewFile: null,
    _previewTarget: null,

    init() {
        // 初始状态
    },

    async scan() {
        const result = await pyApi('encodingScan');
        if (!result.success) {
            showToast('扫描失败: ' + (result.message || '未知错误'));
            return;
        }

        this._scanResult = result;
        this.renderStats(result);
        this.renderFileList(result);
    },

    renderStats(result) {
        document.getElementById('encodingStats').style.display = 'flex';
        document.getElementById('encTotal').textContent = result.total || 0;
        document.getElementById('encGbkCnt').textContent = result.gbk_count || 0;
        document.getElementById('encBig5Cnt').textContent = result.big5_count || 0;
        document.getElementById('encUtf8Cnt').textContent = result.utf8_count || 0;
        document.getElementById('encUnkCnt').textContent = result.unknown_count || 0;
    },

    renderFileList(result) {
        const tbody = document.getElementById('encodingFileList');
        if (!result.files || result.files.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="hint">未找到INI文件</td></tr>';
            return;
        }

        let html = '';
        const encColors = { gbk: '#27ae60', big5: '#e94560', 'utf-8': '#3498db', unknown: '#f39c12' };

        for (const f of result.files) {
            const color = encColors[f.encoding] || '#888';
            html += '<tr>';
            html += '<td style="font-family:var(--font-mono);font-size:12px;">' + escHtml(f.file) + '</td>';
            html += '<td><span style="color:' + color + ';font-weight:700;">' + f.encoding.toUpperCase() + '</span></td>';
            html += '<td>' + (f.confidence || 0) + '%</td>';
            html += '<td>' + (f.size_kb || 0) + '</td>';
            html += '<td>';
            html += '<button class="btn btn-xs" onclick="encodingConverter.preview(\'' + escHtml(f.file).replace(/'/g, "\\'") + '\', \'gbk\')" title="预览转GBK">预览GBK</button> ';
            html += '<button class="btn btn-xs" onclick="encodingConverter.preview(\'' + escHtml(f.file).replace(/'/g, "\\'") + '\', \'big5\')" title="预览转Big5">预览Big5</button> ';
            html += '<button class="btn btn-xs btn-primary" onclick="encodingConverter.convertFile(\'' + escHtml(f.file).replace(/'/g, "\\'") + '\', \'gbk\')">转GBK</button> ';
            html += '<button class="btn btn-xs btn-info" onclick="encodingConverter.convertFile(\'' + escHtml(f.file).replace(/'/g, "\\'") + '\', \'big5\')">转Big5</button>';
            html += '</td>';
            html += '</tr>';
        }
        tbody.innerHTML = html;
    },

    async preview(filePath, targetEncoding) {
        this._previewFile = filePath;
        this._previewTarget = targetEncoding;

        const result = await pyApi('encodingPreview', filePath, targetEncoding);
        if (!result.success) {
            showToast('预览失败: ' + (result.message || '未知错误'));
            return;
        }

        if (result.same_encoding) {
            showToast(result.message);
            return;
        }

        document.getElementById('encodingPreviewInfo').innerHTML = 
            '<strong>文件:</strong> ' + escHtml(result.file) + ' | ' +
            '<strong>源编码:</strong> ' + result.source_encoding.toUpperCase() + ' → ' +
            '<strong>目标编码:</strong> ' + result.target_encoding.toUpperCase() + ' | ' +
            '<strong>总行数:</strong> ' + result.total_lines;

        let previewHtml = '<table class="eff-table" style="width:100%;">';
        previewHtml += '<thead><tr><th style="width:8%;">行号</th><th style="width:46%;">原始内容</th><th style="width:46%;">转换后</th></tr></thead><tbody>';

        for (const line of (result.preview || [])) {
            const rowStyle = line.changed ? 'background:rgba(233,69,96,0.1);' : '';
            previewHtml += '<tr style="' + rowStyle + '">';
            previewHtml += '<td>' + line.line + '</td>';
            previewHtml += '<td style="font-family:var(--font-mono);font-size:11px;word-break:break-all;">' + escHtml(line.original) + '</td>';
            previewHtml += '<td style="font-family:var(--font-mono);font-size:11px;word-break:break-all;">' + escHtml(line.converted) + '</td>';
            previewHtml += '</tr>';
        }
        previewHtml += '</tbody></table>';

        document.getElementById('encodingPreviewContent').innerHTML = previewHtml;
        document.getElementById('encodingPreviewConvertBtn').textContent = '确认转换为 ' + targetEncoding.toUpperCase();
        document.getElementById('encodingPreviewOverlay').style.display = 'block';
        document.getElementById('encodingPreviewModal').style.display = 'block';
    },

    closePreview() {
        document.getElementById('encodingPreviewOverlay').style.display = 'none';
        document.getElementById('encodingPreviewModal').style.display = 'none';
        this._previewFile = null;
        this._previewTarget = null;
    },

    async confirmPreviewConvert() {
        if (!this._previewFile || !this._previewTarget) {
            showToast('预览数据已过期，请重新预览');
            this.closePreview();
            return;
        }
        await this.convertFile(this._previewFile, this._previewTarget);
        this.closePreview();
    },

    async convertFile(filePath, targetEncoding) {
        const encName = targetEncoding.toUpperCase();
        if (!confirm('确认将 ' + escHtml(filePath) + ' 转换为 ' + encName + ' 编码？\n转换前会自动备份原文件。')) {
            return;
        }

        const result = await pyApi('encodingConvertFile', filePath, targetEncoding);
        if (result.success) {
            if (result.skipped) {
                showToast(result.message);
            } else {
                showToast('转换成功: ' + escHtml(filePath) + ' → ' + encName);
                // 刷新扫描结果
                this.scan();
            }
        } else {
            showToast('转换失败: ' + (result.message || '未知错误'));
        }
    },

    async batchConvert(targetEncoding) {
        const encName = targetEncoding.toUpperCase();
        if (!confirm('确认批量转换 Setting/ 目录下所有 INI 文件为 ' + encName + ' 编码？\n转换前会自动备份原文件。\n建议先"扫描编码"查看当前状态。')) {
            return;
        }

        const resultMsg = document.getElementById('encodingResultMsg');
        resultMsg.style.display = 'block';
        resultMsg.style.background = 'rgba(52,152,219,0.15)';
        resultMsg.style.color = '#3498db';
        resultMsg.textContent = '正在批量转换中，请稍候...';

        const result = await pyApi('encodingBatchConvert', targetEncoding);

        if (result.success) {
            resultMsg.style.background = 'rgba(39,174,96,0.15)';
            resultMsg.style.color = '#27ae60';
            resultMsg.textContent = result.message + ' | 转换: ' + result.converted + ' | 跳过: ' + result.skipped + ' | 错误: ' + result.errors;
            showToast(result.message);
            // 刷新扫描
            this.scan();
        } else {
            resultMsg.style.background = 'rgba(192,57,43,0.15)';
            resultMsg.style.color = '#c0392b';
            resultMsg.textContent = '转换失败: ' + (result.message || '未知错误');
            showToast('批量转换失败: ' + (result.message || '未知错误'));
        }
    },
};

// ============================================================
// 剧情事件编辑器
// ============================================================
const eventEditor = {
    _templates: null,
    _currentType: '',
    _generatedText: '',

    async init() {
        if (!this._templates) {
            const r = await pyApi('eventTemplates');
            if (r.success && r.templates) {
                this._templates = r.templates;
                this._populateTypeSelect();
            }
        }
    },

    _populateTypeSelect() {
        const sel = document.getElementById('eventClassType');
        if (!sel || !this._templates) return;
        sel.innerHTML = '<option value="">-- 请选择模板 --</option>';
        for (const [key, tpl] of Object.entries(this._templates)) {
            sel.innerHTML += '<option value="' + key + '">ClassType ' + key + ': ' + escHtml(tpl.name) + '</option>';
        }
    },

    switchTemplate(type) {
        this._currentType = type;
        const infoEl = document.getElementById('eventTemplateInfo');
        const nameEl = document.getElementById('eventTemplateName');
        const descEl = document.getElementById('eventTemplateDesc');
        const formEl = document.getElementById('eventParamForm');
        const previewEl = document.getElementById('eventPreview');
        const copyBtn = document.getElementById('eventCopyBtn');

        if (!type || !this._templates || !this._templates[type]) {
            infoEl.style.display = 'none';
            formEl.innerHTML = '';
            previewEl.textContent = '; 请选择模板并填写参数后点击"生成"';
            copyBtn.disabled = true;
            return;
        }

        const tpl = this._templates[type];
        infoEl.style.display = 'block';
        nameEl.textContent = tpl.name;
        descEl.textContent = tpl.description;

        // 通用字段
        let html = '<div class="event-form-section"><h4>通用字段</h4>';
        const commonFields = { No: '事件编号', Priority: '优先级', Age: '剧本编号(1-10)', S_Year: '起始年份(-1=无限制)', S_Season: '起始季节(-1=无限制)', E_Year: '结束年份(-1=无限制)', E_Season: '结束季节(-1=无限制)', PreHistory: '前置事件编号', NedHistory01: '后续事件1', NedHistory02: '后续事件2', NedHistory03: '后续事件3', Pic: 'CG图片编号', IsUsed: '是否启用(1=是)', Version: '版本' };
        for (const [fname, flabel] of Object.entries(commonFields)) {
            html += '<div class="form-row"><label>' + flabel + '</label><input type="text" id="ef_' + fname + '" placeholder="' + flabel + '" class="event-param"></div>';
        }
        html += '</div>';

        // 模板专用字段
        html += '<div class="event-form-section"><h4>模板字段 (' + tpl.name + ')</h4>';
        for (const [fname, flabel] of Object.entries(tpl.fields)) {
            html += '<div class="form-row"><label>' + flabel + '</label><input type="text" id="ef_' + fname + '" placeholder="' + flabel + '" class="event-param"></div>';
        }
        html += '</div>';

        formEl.innerHTML = html;
        previewEl.textContent = '; 请选择模板并填写参数后点击"生成"';
        copyBtn.disabled = true;
    },

    async generate() {
        const type = this._currentType;
        if (!type || !this._templates) return;

        const params = {};
        const inputs = document.querySelectorAll('#eventParamForm input.event-param');
        inputs.forEach(inp => {
            const fname = inp.id.replace('ef_', '');
            params[fname] = inp.value || '0';
        });

        const r = await pyApi('eventGenerate', type, params);
        const previewEl = document.getElementById('eventPreview');
        const copyBtn = document.getElementById('eventCopyBtn');

        if (r.success) {
            this._generatedText = r.ini_text || '';
            previewEl.textContent = this._generatedText;
            copyBtn.disabled = false;
            showToast('生成成功！');
        } else {
            previewEl.textContent = '; 生成失败: ' + (r.message || '未知错误');
            copyBtn.disabled = true;
        }
    },

    copyToClipboard() {
        if (!this._generatedText) return;
        navigator.clipboard.writeText(this._generatedText).then(() => {
            showToast('已复制到剪贴板！');
        }).catch(() => {
            showToast('复制失败，请手动选择文本复制');
        });
    },

    clear() {
        document.getElementById('eventClassType').value = '';
        this._currentType = '';
        this._generatedText = '';
        document.getElementById('eventTemplateInfo').style.display = 'none';
        document.getElementById('eventParamForm').innerHTML = '';
        document.getElementById('eventPreview').textContent = '; 请选择模板并填写参数后点击"生成"';
        document.getElementById('eventCopyBtn').disabled = true;
    },

    // === 直接编辑模式 ===
    _directMode: true,
    _directData: [],
    _directIdx: -1,
    _directDirty: false,

    switchMode(mode) {
        this._directMode = (mode === 'direct');
        document.getElementById('eventModeDirect').classList.toggle('active', mode === 'direct');
        document.getElementById('eventModeTemplate').classList.toggle('active', mode === 'template');
        document.getElementById('eventDirectPanel').style.display = (mode === 'direct') ? 'block' : 'none';
        document.getElementById('eventTemplatePanel').style.display = (mode === 'template') ? 'block' : 'none';
        if (mode === 'template') this.init();
    },

    async _loadDirect() {
        const res = await pyApi('loadHistories');
        if (res && res.success) {
            this._directData = res.data || [];
            this._directIdx = -1;
            this._directDirty = false;
            this._renderDirectList();
            document.getElementById('eventDirectCount').textContent = `共 ${this._directData.length} 个事件`;
        }
    },

    _renderDirectList(filter) {
        const container = document.getElementById('eventDirectList');
        let data = this._directData;
        if (filter) {
            const q = filter.toLowerCase();
            data = data.filter(h => String(h.No || '').toLowerCase().includes(q) || String(h.ClassType || '').includes(q));
        }
        container.innerHTML = data.map((h, i) => {
            const selected = i === this._directIdx;
            return `<div class="list-item ${selected ? 'selected' : ''}" onclick="eventEditor._selectDirect(${i})" style="padding:8px;cursor:pointer;border-bottom:1px solid var(--border);${selected?'background:var(--accent);color:#fff;':''}">
                <div style="font-weight:bold;">#${h.No || '?'} | 类型${h.ClassType || '?'}</div>
                <div style="font-size:11px;color:${selected?'rgba(255,255,255,0.7)':'var(--text-muted)'};">${h.Name || '未命名'} | 时代${h.Age || '?'}</div>
            </div>`;
        }).join('');
    },

    _selectDirect(idx) {
        if (this._directDirty && this._directIdx >= 0) {
            this._saveDirectCurrent();
        }
        this._directIdx = idx;
        this._renderDirectList();
        this._renderDirectDetail();
    },

    _renderDirectDetail() {
        const container = document.getElementById('eventDirectDetail');
        if (this._directIdx < 0 || this._directIdx >= this._directData.length) {
            container.innerHTML = '<p style="color:var(--text-muted);padding:20px;">请从左侧列表选择一个事件</p>';
            return;
        }
        const h = this._directData[this._directIdx];
        const groups = [
            { name: '基本信息', fields: ['No','ClassType','Priority','Age','S_Year','S_Season','E_Year','E_Season','IsUsed','Version'] },
            { name: '事件链', fields: ['PreHistory','NedHistory01','NedHistory02','NedHistory03','Pic'] },
            { name: '参与君主', fields: ['LordA','LordALv','bCustomA','LordB','LordBLv','bCustomB','LordC','LorCLv','bCustomC','bDead'] },
            { name: '源方对话', fields: ['S_ProposeGeneral','S_ProposeString','S_AnsProposeString','S_DiplomaticGeneral','S_DiplomaticString'] },
            { name: '触发条件', fields: ['N_MinRelation','N_MinMoney','N_MaxMoney','N_MinGenNum','N_MinCityNum','N_MinPeopleHeart','N_SpecCity01','N_SpecCity02','N_SpecCity03','N_SpecCity04','N_SpecCity05'] },
            { name: '事件奖励', fields: ['Thing01','ThingNum01','Thing02','ThingNum02','Thing03','ThingNum03','Thing04','ThingNum04','Thing05','ThingNum05','Money','People','PeopleHeart','ReserveSoldier'] },
            { name: '属性/技能', fields: ['Str','Int','HP','MP','Title01','Title02','Title03','Title04','Title05','SFMagic','BFMagic','GenSkill','ArmySkill','ArmyGroupSkill'] },
        ];
        let html = '';
        groups.forEach(g => {
            html += `<div style="margin-bottom:8px;"><h4 style="font-size:12px;color:var(--text-secondary);margin:0 0 4px;border-bottom:1px solid var(--border);padding-bottom:2px;">${g.name}</h4>
                <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:4px;">`;
            g.fields.forEach(f => {
                const val = h[f] !== undefined ? h[f] : '';
                html += `<div style="display:flex;align-items:center;gap:2px;font-size:11px;">
                    <span style="color:var(--text-muted);min-width:60px;text-align:right;">${f}</span>
                    <input type="text" value="${this._escStr(String(val))}" onchange="eventEditor._updateDirectField('${f}', this.value)" style="flex:1;font-size:11px;padding:1px 3px;min-width:50px;">
                </div>`;
            });
            html += '</div></div>';
        });
        // S_Gen 武将 (1-10) with extra fields
        html += '<div style="margin-bottom:8px;"><h4 style="font-size:12px;color:var(--text-secondary);margin:0 0 4px;border-bottom:1px solid var(--border);">源方武将 (S_Gen)</h4>';
        for (let i = 1; i <= 10; i++) {
            const si = String(i).padStart(2,'0');
            html += `<div style="display:flex;gap:4px;margin:2px 0;font-size:11px;align-items:center;">
                <span style="min-width:20px;">#${i}</span>
                <input type="text" value="${this._escStr(String(h['S_General'+si]||''))}" onchange="eventEditor._updateDirectField('S_General${si}', this.value)" style="width:60px;font-size:11px;padding:1px 2px;" placeholder="武将">
                <input type="text" value="${this._escStr(String(h['S_StringA'+si]||''))}" onchange="eventEditor._updateDirectField('S_StringA${si}', this.value)" style="width:60px;font-size:11px;padding:1px 2px;" placeholder="台词">
                <input type="text" value="${this._escStr(String(h['S_StringD'+si]||''))}" onchange="eventEditor._updateDirectField('S_StringD${si}', this.value)" style="width:60px;font-size:11px;padding:1px 2px;" placeholder="显示文本">
                <input type="text" value="${this._escStr(String(h['S_MinGenLv'+si]||''))}" onchange="eventEditor._updateDirectField('S_MinGenLv${si}', this.value)" style="width:40px;font-size:10px;padding:1px;" placeholder="等级">
                <input type="text" value="${this._escStr(String(h['S_MinLoyal'+si]||''))}" onchange="eventEditor._updateDirectField('S_MinLoyal${si}', this.value)" style="width:40px;font-size:10px;padding:1px;" placeholder="义理">
                <input type="text" value="${this._escStr(String(h['S_City'+si]||''))}" onchange="eventEditor._updateDirectField('S_City${si}', this.value)" style="width:40px;font-size:10px;padding:1px;" placeholder="城池">
            </div>`;
        }
        html += '</div>';
        // D_Gen 武将 (1-10) with extra fields
        html += '<div style="margin-bottom:8px;"><h4 style="font-size:12px;color:var(--text-secondary);margin:0 0 4px;border-bottom:1px solid var(--border);">目标方武将 (D_Gen)</h4>';
        for (let i = 1; i <= 10; i++) {
            const si = String(i).padStart(2,'0');
            html += `<div style="display:flex;gap:4px;margin:2px 0;font-size:11px;align-items:center;">
                <span style="min-width:20px;">#${i}</span>
                <input type="text" value="${this._escStr(String(h['D_General'+si]||''))}" onchange="eventEditor._updateDirectField('D_General${si}', this.value)" style="width:60px;font-size:11px;padding:1px 2px;" placeholder="武将">
                <input type="text" value="${this._escStr(String(h['D_StringA'+si]||''))}" onchange="eventEditor._updateDirectField('D_StringA${si}', this.value)" style="width:60px;font-size:11px;padding:1px 2px;" placeholder="台词">
                <input type="text" value="${this._escStr(String(h['D_StringD'+si]||''))}" onchange="eventEditor._updateDirectField('D_StringD${si}', this.value)" style="width:60px;font-size:11px;padding:1px 2px;" placeholder="显示文本">
                <input type="text" value="${this._escStr(String(h['D_MinGenLv'+si]||''))}" onchange="eventEditor._updateDirectField('D_MinGenLv${si}', this.value)" style="width:40px;font-size:10px;padding:1px;" placeholder="等级">
                <input type="text" value="${this._escStr(String(h['D_MinLoyal'+si]||''))}" onchange="eventEditor._updateDirectField('D_MinLoyal${si}', this.value)" style="width:40px;font-size:10px;padding:1px;" placeholder="义理">
                <input type="text" value="${this._escStr(String(h['D_City'+si]||''))}" onchange="eventEditor._updateDirectField('D_City${si}', this.value)" style="width:40px;font-size:10px;padding:1px;" placeholder="城池">
            </div>`;
        }
        html += '</div>';
        container.innerHTML = html;
    },

    _updateDirectField(field, value) {
        if (this._directIdx < 0) return;
        this._directData[this._directIdx][field] = value;
        this._directDirty = true;
    },

    _saveDirectCurrent() {
        // Save current DOM input values back to _directData before switching selection
        // (onchange may not have fired if user is still focused on an input)
        if (this._directIdx < 0 || this._directIdx >= this._directData.length) return;
        const container = document.getElementById('eventDirectDetail');
        if (!container) return;
        const h = this._directData[this._directIdx];
        const inputs = container.querySelectorAll('input[type="text"]');
        inputs.forEach(inp => {
            const match = inp.getAttribute('onchange');
            if (match) {
                const m = match.match(/_updateDirectField\('([^']+)'/);
                if (m && m[1]) h[m[1]] = inp.value;
            }
        });
    },

    // snapshot/restore for undo support (delegates to _directData)
    get changed() { return this._directDirty; },
    set changed(v) { this._directDirty = v; },

    snapshot() {
        return JSON.parse(JSON.stringify({
            data: this._directData,
            index: this._directIdx,
        }));
    },

    restoreSnapshot(data) {
        this._directData = data.data ? JSON.parse(JSON.stringify(data.data)) : [];
        this._directIdx = data.index != null ? data.index : -1;
        this._directDirty = false;
        this._renderDirectList();
        if (this._directIdx >= 0 && this._directIdx < this._directData.length) {
            this._renderDirectDetail();
        } else {
            document.getElementById('eventDirectDetail').innerHTML = '<p style="color:var(--text-muted);padding:20px;">请从左侧列表选择一个事件</p>';
        }
        document.getElementById('eventDirectCount').textContent = `共 ${this._directData.length} 个事件`;
    },

    pushUndo() {
        UndoManager.pushState('eventEditor', this.snapshot());
    },

    async _saveDirect() {
        if (!this._directDirty) { showToast('没有修改', 'info'); return; }
        if (!confirm('确认保存历史事件修改？')) return;
        const res = await pyApi('saveHistories', this._directData);
        if (res && res.success) {
            this._directDirty = false;
            showToast(res.message || '保存成功', 'success');
        } else {
            showToast(res ? res.message || '保存失败' : '保存失败', 'error');
        }
    },

    async _addDirect() {
        const res = await pyApi('newHistory');
        if (res && res.success) {
            this._directData.push(res.data);
            this._directIdx = this._directData.length - 1;
            this._directDirty = true;
            this._renderDirectList();
            this._renderDirectDetail();
            document.getElementById('eventDirectCount').textContent = `共 ${this._directData.length} 个事件`;
        }
    },

    async _cloneDirect() {
        if (this._directIdx < 0) { showToast('请先选择一个事件', 'warning'); return; }
        const clone = JSON.parse(JSON.stringify(this._directData[this._directIdx]));
        clone.No = '0';
        this._directData.push(clone);
        this._directIdx = this._directData.length - 1;
        this._directDirty = true;
        this._renderDirectList();
        this._renderDirectDetail();
        document.getElementById('eventDirectCount').textContent = `共 ${this._directData.length} 个事件`;
    },

    async _deleteDirect() {
        if (this._directIdx < 0) { showToast('请先选择一个事件', 'warning'); return; }
        const h = this._directData[this._directIdx];
        if (!confirm(`确认删除事件 #${h.No || '?'}？此操作不可撤销。`)) return;
        const res = await pyApi('deleteHistory', this._directIdx);
        if (res && res.success) {
            this._directData.splice(this._directIdx, 1);
            if (this._directIdx >= this._directData.length) this._directIdx = this._directData.length - 1;
            this._directDirty = true;
            this._renderDirectList();
            this._renderDirectDetail();
            document.getElementById('eventDirectCount').textContent = `共 ${this._directData.length} 个事件`;
            showToast(res.message, 'success');
        } else {
            showToast(res ? res.message || '删除失败' : '删除失败', 'error');
        }
    },

    _filterDirectList(query) {
        this._renderDirectList(query);
    },

    _escStr(str) {
        return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    },
};

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    OnboardingWizard.init();
    initSubTabGroups();
});

// ============================================================
// 子标签组管理器 — UI子系统 + 配置扩展
// ============================================================
function initSubTabGroups() {
    // ---- UI子系统 ----
    const uiEditors = {};
    const uiConfigs = [
        { sub: 'ui_buttonstyle', api: 'ButtonStyle', fields: ['ID','Name','Normal','Hover','Pressed','Disabled'] },
        { sub: 'ui_fontsize', api: 'FontSize', fields: ['ID','Name','Size'] },
        { sub: 'ui_framestyle', api: 'FrameStyle', fields: ['ID','Name','Up','Down','Left','Right','UpLeft','UpRight','DownLeft','DownRight'] },
        { sub: 'ui_liststyle', api: 'ListStyle', fields: ['ID','Name','ScrollBar','ItemHeight'] },
        { sub: 'ui_shapeui', api: 'ShapeUI', fields: ['ID','Name','X','Y','Width','Height'] },
        { sub: 'ui_textstyle', api: 'TextStyle', fields: ['ID','Name','Align','Color'] },
        { sub: 'ui_wincolor', api: 'WinColor', fields: ['ID','Name','R','G','B','Alpha'] },
        { sub: 'ui_winmainmenu', api: 'WinMainMenu', fields: ['ID','Name','X','Y','Width','Height','FontX','FontY'] },
    ];
    uiConfigs.forEach(cfg => {
        uiEditors[cfg.sub] = createIniEditor(
            'uisubs', cfg.api, null, 'uisubs_list',
            'uisubs_empty', 'uisubs_detail', cfg.fields
        );
        uiEditors[cfg.sub].changed = false;
        var _oSet = uiEditors[cfg.sub]._set;
        uiEditors[cfg.sub]._set = function(key, val) {
            _oSet.call(this, key, val);
            this.changed = true;
        };
        var _oSave = uiEditors[cfg.sub].save;
        uiEditors[cfg.sub].save = async function() {
            var r = await _oSave.call(this);
            if (r && r.success) this.changed = false;
            return r;
        };
        uiEditors[cfg.sub].renderDetail = function() {
            var emptyEl = document.getElementById('uisubs_empty');
            var detailEl = document.getElementById('uisubs_detail');
            var fieldsEl = document.getElementById('uisubs_fields');
            if (!this.current) {
                if (emptyEl) emptyEl.style.display = 'flex';
                if (detailEl) detailEl.style.display = 'none';
                ;
            }
            if (emptyEl) emptyEl.style.display = 'none';
            if (detailEl) detailEl.style.display = 'block';
            if (fieldsEl) {
                fieldsEl.innerHTML = this._fields.map(k => {
                    var val = this.current[k] != null ? this.current[k] : '';
                    return '<div class="form-group"><label>' + escHtml(k) + '</label><input type="text" id="uisubs_' + k + '" value="' + escHtml(String(val)) + '" onchange="uisubs_currentEditor._set(\'' + k + '\', this.value)" class="form-input"></div>';
                }).join('');
            }
        };
        uiEditors[cfg.sub]._apiName = cfg.api;
    });

    let uiCurrent = uiEditors['ui_buttonstyle'];
    window.uisubs_currentEditor = uiCurrent;

    function switchUISub(sub) {
        uiCurrent = uiEditors[sub];
        window.uisubs_currentEditor = uiCurrent;
        document.querySelectorAll('#uisubs .sub-tab').forEach(b => b.classList.toggle('active', b.dataset.sub === sub));
        uiCurrent.renderList();
        const emptyEl = document.getElementById('uisubs_empty');
        const detailEl = document.getElementById('uisubs_detail');
        if (emptyEl) emptyEl.style.display = 'flex';
        if (detailEl) detailEl.style.display = 'none';
    }

    document.querySelectorAll('#uisubsystem .sub-tab').forEach(btn => {
        btn.addEventListener('click', () => switchUISub(btn.dataset.sub));
    });

    document.getElementById('uisubs_loadBtn').onclick = () => uiCurrent.load();
    document.getElementById('uisubs_addBtn').onclick = () => uiCurrent.addNew();
    document.getElementById('uisubs_saveBtn').onclick = () => uiCurrent.save();

    // ---- 配置扩展 ----
    const cfgEditors = {};
    const cfgConfigs = [
        { sub: 'cfg_cdtable', api: 'CDTable', fields: ['No','Name','CDTrack'] },
        { sub: 'cfg_citytext', api: 'CityText', fields: ['No','Name','Text'] },
        { sub: 'cfg_postpatch', api: 'PostPatch', fields: ['No','Name','PosX','PosY','IsUsed'] },
        { sub: 'cfg_thingscriptno', api: 'ThingScriptNo', fields: ['No','ScriptNo','Name'] },
    ];
    cfgConfigs.forEach(cfg => {
        cfgEditors[cfg.sub] = createIniEditor(
            'configext', cfg.api, null, 'configext_list',
            'configext_empty', 'configext_detail', cfg.fields
        );
        cfgEditors[cfg.sub].changed = false;
        var _oSet2 = cfgEditors[cfg.sub]._set;
        cfgEditors[cfg.sub]._set = function(key, val) {
            _oSet2.call(this, key, val);
            this.changed = true;
        };
        var _oSave2 = cfgEditors[cfg.sub].save;
        cfgEditors[cfg.sub].save = async function() {
            var r = await _oSave2.call(this);
            if (r && r.success) this.changed = false;
            return r;
        };
        cfgEditors[cfg.sub].renderDetail = function() {
            const emptyEl = document.getElementById('configext_empty');
            const detailEl = document.getElementById('configext_detail');
            const fieldsEl = document.getElementById('configext_fields');
            if (!this.current) {
                if (emptyEl) emptyEl.style.display = 'flex';
                if (detailEl) detailEl.style.display = 'none';
                return;
            }
            if (emptyEl) emptyEl.style.display = 'none';
            if (detailEl) detailEl.style.display = 'block';
            if (fieldsEl) {
                fieldsEl.innerHTML = this._fields.map(k => {
                    var val = this.current[k] != null ? this.current[k] : '';
                    return '<div class="form-group"><label>' + escHtml(k) + '</label><input type="text" id="configext_' + k + '" value="' + escHtml(String(val)) + '" onchange="configext_currentEditor._set(\'' + k + '\', this.value)" class="form-input"></div>';
                }).join('');
            }
        };
        cfgEditors[cfg.sub]._apiName = cfg.api;
    });

    let cfgCurrent = cfgEditors['cfg_cdtable'];
    window.configext_currentEditor = cfgCurrent;

    function switchCfgSub(sub) {
        cfgCurrent = cfgEditors[sub];
        window.configext_currentEditor = cfgCurrent;
        document.querySelectorAll('#configext .sub-tab').forEach(b => b.classList.toggle('active', b.dataset.sub === sub));
        cfgCurrent.renderList();
        const emptyEl = document.getElementById('configext_empty');
        const detailEl = document.getElementById('configext_detail');
        if (emptyEl) emptyEl.style.display = 'flex';
        if (detailEl) detailEl.style.display = 'none';
    }

    document.querySelectorAll('#configext .sub-tab').forEach(btn => {
        btn.addEventListener('click', () => switchCfgSub(btn.dataset.sub));
    });

    document.getElementById('configext_loadBtn').onclick = () => cfgCurrent.load();
    document.getElementById('configext_addBtn').onclick = () => cfgCurrent.addNew();
    }

// ============================================================
// MPC地形编辑器
// ============================================================
const mpcEditor = {
    data: null,
    grid: [],
    changes: {},
    brush: 0,
    loaded: false,
    _dragging: false,
    _scale: 2,
    _offsetX: 0,
    _offsetY: 0,

    async load() {
        const res = await pyApi('mpcRead');
        if (!res.success) { showToast(res.message, 'error'); return; }
        this.data = res.data;
        this.grid = res.data;
        this.loaded = true;
        this.render();
        // 渲染摘要
        const summary = document.getElementById('mpcSummary');
        summary.innerHTML = res.summary.map(s => 
            `<span style="background:${TERRAIN_COLORS[s.id]||'#333'};color:#fff;padding:2px 6px;border-radius:3px;">${s.name}:${s.count}(${s.pct}%)</span>`
        ).join('');
        document.getElementById('mpcChanged').textContent = '0';
    },

    selectTerrain(v) {
        this.brush = parseInt(v);
        const names = ['无','草原','乾草原','荒地','道路','湿地','森林','丘陵','高山','沙漠','河','浅海','深海','残雪','雪原','雪丘','雪山'];
        document.getElementById('mpcBrushLabel').textContent = names[this.brush] || '?';
    },

    render() {
        const canvas = document.getElementById('mpcCanvas');
        if (!canvas || !this.grid.length) return;
        const ctx = canvas.getContext('2d');
        const w = this.grid[0].length, h = this.grid.length;
        const cw = canvas.width, ch = canvas.height;
        ctx.clearRect(0, 0, cw, ch);
        const scale = this._scale;
        for (let gy = 0; gy < h; gy++) {
            for (let gx = 0; gx < w; gx++) {
                const v = this.grid[gy][gx];
                const key = `${gx},${gy}`;
                const cv = key in this.changes ? this.changes[key] : v;
                ctx.fillStyle = TERRAIN_COLORS[cv] || '#333';
                ctx.fillRect(this._offsetX + gx * scale, this._offsetY + gy * scale, scale, scale);
            }
        }
    },

    getBlock(e) {
        const canvas = document.getElementById('mpcCanvas');
        const rect = canvas.getBoundingClientRect();
        const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
        const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
        const gx = Math.floor((sx - this._offsetX) / this._scale);
        const gy = Math.floor((sy - this._offsetY) / this._scale);
        if (gx >= 0 && gy >= 0 && this.grid.length && gx < this.grid[0].length && gy < this.grid.length) {
            return { gx, gy, val: this.grid[gy][gx] };
        }
        return null;
    },

    onMouseDown(e) { this._dragging = true; this.paint(e); },
    onMouseUp(e) { this._dragging = false; },
    onMouseMove(e) {
        const block = this.getBlock(e);
        const tip = document.getElementById('mpcTooltip');
        const info = document.getElementById('mpcMouse');
        if (block) {
            const names = ['无','草原','乾草原','荒地','道路','湿地','森林','丘陵','高山','沙漠','河','浅海','深海','残雪','雪原','雪丘','雪山'];
            tip.style.display = 'block';
            tip.style.left = (e.clientX + 15) + 'px';
            tip.style.top = (e.clientY - 30) + 'px';
            tip.textContent = `(${block.gx},${block.gy}) ${names[block.val]||'?'}`;
            info.textContent = `(${block.gx}, ${block.gy}) ${names[block.val]||'?'}`;
            if (this._dragging) this.paint(e);
        } else {
            tip.style.display = 'none';
            info.textContent = '-';
        }
    },

    paint(e) {
        const block = this.getBlock(e);
        if (!block) return;
        const key = `${block.gx},${block.gy}`;
        if (this.grid[block.gy][block.gx] === this.brush) {
            delete this.changes[key];
        } else {
            this.changes[key] = this.brush;
        }
        this.render();
        document.getElementById('mpcChanged').textContent = Object.keys(this.changes).length;
    },

    async saveBatch() {
        const changes = Object.entries(this.changes).map(([k, v]) => {
            const [x, y] = k.split(',').map(Number);
            return { x, y, terrain: v };
        });
        if (!changes.length) { showToast('没有待保存的修改', 'info'); return; }
        const res = await pyApi('mpcBatchWrite', changes);
        if (res.success) {
            showToast(res.message, 'success');
            this.changes = {};
            document.getElementById('mpcChanged').textContent = '0';
            this.load();
        } else {
            showToast(res.message, 'error');
        }
    }
};

const TERRAIN_COLORS = {"0":"#2d5a27","1":"#4a8c3f","2":"#8b9a47","3":"#9e8b5e","4":"#c4a45a","5":"#5a7a3a","6":"#2d5a1e","7":"#7a8a5a","8":"#6a6a5a","9":"#d4c47a","10":"#3a6aaa","11":"#5a8aaa","12":"#2a4a7a","13":"#d4e4f4","14":"#e8f0f8","15":"#c8d8e8","16":"#f0f4f8"};

// ============================================================
// Shape位移编辑器
// ============================================================
const shapeInfoEditor = {
    infos: [],
    _dirty: {},

    async load() {
        const cat = document.getElementById('shapeInfoCategory').value;
        const res = await pyApi('shapeInfoList', cat);
        if (!res.success) { showToast(res.message, 'error'); return; }
        this.infos = res.infos;
        this._dirty = {};
        // 更新类别下拉
        const sel = document.getElementById('shapeInfoCategory');
        const curVal = sel.value;
        sel.innerHTML = '<option value="all">全部类别</option>' + 
            res.categories.map(c => `<option value="${c}">${c}</option>`).join('');
        sel.value = curVal;
        this.render();
        document.getElementById('shapeInfoStatus').textContent = `共 ${res.count} 个 .info.ini 文件`;
    },

    render() {
        const list = document.getElementById('shapeInfoList');
        if (!this.infos.length) {
            list.innerHTML = '<p style="padding:16px;color:var(--text-muted);text-align:center;">无数据</p>';
            return;
        }
        list.innerHTML = `<table style="width:100%;font-size:12px;border-collapse:collapse;">
            <thead><tr style="background:var(--bg-page);">
                <th style="padding:8px;text-align:left;">类别</th>
                <th style="padding:8px;text-align:left;">文件</th>
                <th style="padding:8px;text-align:left;">路径</th>
                <th style="padding:8px;text-align:center;width:80px;">X偏移</th>
                <th style="padding:8px;text-align:center;width:80px;">Y偏移</th>
                <th style="padding:8px;text-align:center;width:60px;">操作</th>
            </tr></thead>
            <tbody>${this.infos.map((info, i) => {
                const key = info.path;
                const x = key in this._dirty ? this._dirty[key].x : info.x;
                const y = key in this._dirty ? this._dirty[key].y : info.y;
                const dirty = key in this._dirty;
                return `<tr style="border-bottom:1px solid var(--border);${dirty?'background:rgba(255,200,0,0.1);':''}">
                    <td style="padding:8px;">${info.category}</td>
                    <td style="padding:8px;font-family:monospace;">${info.file}</td>
                    <td style="padding:8px;font-size:11px;color:var(--text-muted);">${info.path}</td>
                    <td style="padding:4px;text-align:center;"><input type="number" value="${x}" style="width:60px;font-size:12px;" onchange="shapeInfoEditor.setDirty('${key}','x',this.value)" data-idx="${i}" data-field="x"></td>
                    <td style="padding:4px;text-align:center;"><input type="number" value="${y}" style="width:60px;font-size:12px;" onchange="shapeInfoEditor.setDirty('${key}','y',this.value)" data-idx="${i}" data-field="y"></td>
                    <td style="padding:4px;text-align:center;"><button onclick="shapeInfoEditor.saveOne('${key}')" class="btn btn-sm btn-primary" ${dirty?'':'disabled'}>保存</button></td>
                </tr>`;
            }).join('')}</tbody></table>`;
    },

    setDirty(key, field, val) {
        if (!this._dirty[key]) this._dirty[key] = { x: this.infos.find(i => i.path === key).x, y: this.infos.find(i => i.path === key).y };
        this._dirty[key][field] = parseInt(val) || 0;
    },

    async saveOne(key) {
        if (!this._dirty[key]) return;
        const d = this._dirty[key];
        const res = await pyApi('shapeInfoSave', key, d.x, d.y);
        if (res.success) {
            delete this._dirty[key];
            showToast(res.message, 'success');
            this.load();
        } else {
            showToast(res.message, 'error');
        }
    },

    async saveAll() {
        const keys = Object.keys(this._dirty);
        if (!keys.length) { showToast('没有待保存的修改', 'info'); return; }
        let saved = 0;
        for (const key of keys) {
            const d = this._dirty[key];
            const res = await pyApi('shapeInfoSave', key, d.x, d.y);
            if (res.success) saved++;
        }
        this._dirty = {};
        showToast(`已保存 ${saved}/${keys.length} 个文件`, 'success');
        this.load();
    }
};

// ============================================================
// SHP批量改名
// ============================================================
const shpRenameTool = {
    async selectDir() {
        const res = await pyApi('shpSelectDir');
        if (res.success && res.path) {
            document.getElementById('shpRenameDir').value = res.path;
        }
    },

    async preview() {
        const dir = document.getElementById('shpRenameDir').value.trim();
        const prefix = document.getElementById('shpRenamePrefix').value.trim();
        const startId = parseInt(document.getElementById('shpRenameStartId').value) || 1;
        const digits = parseInt(document.getElementById('shpRenameDigits').value) || 4;
        if (!dir) { showToast('请先设置目标目录', 'warning'); return; }
        // 模拟预览：列出目录中的shp文件
        const previewDiv = document.getElementById('shpRenamePreview');
        previewDiv.innerHTML = `<p style="color:var(--text-muted);">预览模式：将重命名 <b>${dir}</b> 中的SHP文件为 <b>${prefix}_0001.shp</b> 格式，起始编号 <b>${startId}</b></p>
            <p style="color:var(--accent);margin-top:8px;">确认无误请点击"执行改名"</p>`;
    },

    async execute() {
        const dir = document.getElementById('shpRenameDir').value.trim();
        const prefix = document.getElementById('shpRenamePrefix').value.trim();
        const startId = parseInt(document.getElementById('shpRenameStartId').value) || 1;
        const digits = parseInt(document.getElementById('shpRenameDigits').value) || 4;
        if (!dir) { showToast('请先设置目标目录', 'warning'); return; }
        if (!prefix) { showToast('请设置文件名前缀', 'warning'); return; }
        if (!confirm(`确定要将 ${dir} 中的SHP文件重命名为 ${prefix}_XXXX.shp 格式？\n起始编号: ${startId}\n此操作不可撤销！`)) return;
        const res = await pyApi('shpBatchRename', dir, prefix, startId, digits);
        if (res.success) {
            const previewDiv = document.getElementById('shpRenamePreview');
            previewDiv.innerHTML = `<p style="color:green;font-weight:600;">${res.message}</p>` +
                res.renamed.map(r => `<div style="font-family:monospace;font-size:11px;">${r.from} → ${r.to}</div>`).join('');
        } else {
            showToast(res.message, 'error');
        }
    }
};

// ============================================================
// 城池连线可视化
// ============================================================
const cityConnect = {
    cities: {},
    positions: {},
    mapSize: [17472, 12384],
    _showLabels: true,
    _scale: 16,
    _offsetX: 0,
    _offsetY: 0,
    _dragging: false,
    _dragStartX: 0,
    _dragStartY: 0,
    _dragOX: 0,
    _dragOY: 0,

    async load() {
        const res = await pyApi('cityConnections');
        if (!res.success) { showToast(res.message, 'error'); return; }
        this.cities = res.cities;
        this.positions = res.positions;
        this.mapSize = res.map_size;
        document.getElementById('cityConnectCount').textContent = Object.keys(this.cities).length;
        let lineCount = 0;
        for (const c of Object.values(this.cities)) lineCount += (c.connections || []).length;
        document.getElementById('cityConnectLineCount').textContent = lineCount;
        this.render();
    },

    toggleLabels() { this._showLabels = !this._showLabels; this.render(); },
    zoomIn() { this._scale = Math.min(this._scale * 1.5, 64); this.render(); },
    zoomOut() { this._scale = Math.max(this._scale / 1.5, 2); this.render(); },
    resetView() { this._offsetX = 0; this._offsetY = 0; this._scale = 16; this.render(); },

    render() {
        const canvas = document.getElementById('cityConnectCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const cw = canvas.width, ch = canvas.height;
        ctx.clearRect(0, 0, cw, ch);
        const scale = this._scale;
        const ox = this._offsetX, oy = this._offsetY;
        // 绘制连线
        ctx.strokeStyle = 'rgba(100,160,255,0.4)';
        ctx.lineWidth = 1;
        for (const c of Object.values(this.cities)) {
            const pos = this.positions[c.no];
            if (!pos) continue;
            const x1 = ox + pos.x / scale, y1 = oy + pos.y / scale;
            for (const conn of (c.connections || [])) {
                const tpos = this.positions[conn.target];
                if (!tpos) continue;
                const x2 = ox + tpos.x / scale, y2 = oy + tpos.y / scale;
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.stroke();
            }
        }
        // 绘制城池点
        for (const c of Object.values(this.cities)) {
            const pos = this.positions[c.no];
            if (!pos) continue;
            const cx = ox + pos.x / scale, cy = oy + pos.y / scale;
            ctx.fillStyle = '#ff6644';
            ctx.beginPath();
            ctx.arc(cx, cy, 4, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1;
            ctx.stroke();
            if (this._showLabels) {
                ctx.fillStyle = '#fff';
                ctx.font = '10px sans-serif';
                ctx.fillText(c.name || c.no, cx + 6, cy - 4);
            }
        }
        document.getElementById('cityConnectZoom').textContent = `${this._scale}:1`;
    },

    onMouseDown(e) {
        this._dragging = true;
        this._dragStartX = e.clientX;
        this._dragStartY = e.clientY;
        this._dragOX = this._offsetX;
        this._dragOY = this._offsetY;
    },
    onMouseMove(e) {
        if (this._dragging) {
            this._offsetX = this._dragOX + (e.clientX - this._dragStartX);
            this._offsetY = this._dragOY + (e.clientY - this._dragStartY);
            this.render();
        }
    },
    onMouseUp(e) { this._dragging = false; },
    onWheel(e) {
        e.preventDefault();
        if (e.deltaY < 0) this.zoomIn();
        else this.zoomOut();
    }
};

// ============================================================
// id.ini 编辑器
// ============================================================
const idiniEditor = {
    data: [],
    _dirty: false,

    async load() {
        const res = await pyApi('loadIdini');
        if (!res.success) { showToast(res.message, 'error'); return; }
        this.data = res.data || [];
        this._dirty = false;
        this.render();
        document.getElementById('idiniCount').textContent = `共 ${this.data.length} 条`;
    },

    render() {
        const list = document.getElementById('idiniList');
        if (!this.data.length) {
            list.innerHTML = '<p style="padding:16px;color:var(--text-muted);text-align:center;">id.ini 为空或不存在</p>';
            return;
        }
        list.innerHTML = `<table style="width:100%;font-size:12px;border-collapse:collapse;">
            <thead><tr style="background:var(--bg-page);">
                <th style="padding:8px;text-align:left;width:80px;">#</th>
                <th style="padding:8px;text-align:left;">键 (Key)</th>
                <th style="padding:8px;text-align:left;">值 (Value)</th>
                <th style="padding:8px;text-align:center;width:60px;">操作</th>
            </tr></thead>
            <tbody>${this.data.map((item, i) => `
                <tr style="border-bottom:1px solid var(--border);">
                    <td style="padding:8px;color:var(--text-muted);">${i+1}</td>
                    <td style="padding:4px;"><input type="text" value="${this._esc(item.key||'')}" style="width:100%;font-size:12px;" onchange="idiniEditor.update(${i},'key',this.value)"></td>
                    <td style="padding:4px;"><input type="text" value="${this._esc(item.value||'')}" style="width:100%;font-size:12px;" onchange="idiniEditor.update(${i},'value',this.value)"></td>
                    <td style="padding:4px;text-align:center;"><button onclick="idiniEditor.remove(${i})" class="btn btn-sm btn-danger">删除</button></td>
                </tr>`).join('')}</tbody></table>`;
    },

    _esc(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); },

    update(i, field, val) {
        this.data[i][field] = val;
        this._dirty = true;
    },

    remove(i) {
        if (!confirm('确定删除此条目？')) return;
        this.data.splice(i, 1);
        this._dirty = true;
        this.render();
        document.getElementById('idiniCount').textContent = `共 ${this.data.length} 条`;
    },

    newEntry() {
        this.data.push({ key: '', value: '' });
        this._dirty = true;
        this.render();
        document.getElementById('idiniCount').textContent = `共 ${this.data.length} 条`;
    },

    async save() {
        const res = await pyApi('saveIdini', this.data);
        if (res.success) {
            this._dirty = false;
            showToast(res.message, 'success');
        } else {
            showToast(res.message, 'error');
        }
    }
};

// ============================================================
// 语言切换器
// ============================================================
const languageSwitcher = {
    async read() {
        const res = await pyApi('readLanguageDat');
        if (res.success) {
            document.getElementById('langCurrent').textContent = res.current;
            const sel = document.getElementById('langSelect');
            if (sel && res.current) {
                for (const opt of sel.options) {
                    if (opt.value === res.current) { sel.value = res.current; break; }
                }
            }
        } else {
            showToast(res.message, 'error');
        }
    },

    async switch() {
        const lang = document.getElementById('langSelect').value;
        if (!confirm(`确定切换语言为 ${lang}？\n\n这将同步修改:\n- language.DAT\n- font.ini\n- TermText.ini\n- SystemText.ini\n- GossipText.ini\n\n操作前会自动备份原文件。`)) return;
        const res = await pyApi('switchLanguagePreset', lang);
        if (res.success) {
            document.getElementById('langCurrent').textContent = lang;
            showToast(`语言已切换为 ${lang}`, 'success');
        } else {
            showToast(res.message, 'error');
        }
    },

    async exportPack() {
        const res = await pyApi('exportLanguagePack');
        if (res.success) {
            showToast(`语言包已导出: ${res.path}`, 'success');
        } else {
            showToast(res.message, 'error');
        }
    },

    async importPack() {
        const path = prompt('请输入语言包 .zip 文件路径:');
        if (!path) return;
        if (!confirm(`确定导入语言包 ${path}？\n\n此操作将覆盖当前的语言文件，操作前会自动备份。`)) return;
        const res = await pyApi('importLanguagePack', path);
        if (res.success) {
            showToast(`语言包已导入 (${res.language})`, 'success');
            this.read();
        } else {
            showToast(res.message, 'error');
        }
    },

    async diffTexts() {
        const source = prompt('对比源语言 (BIG5/GB/SJIS/KOR):', 'BIG5');
        if (!source) return;
        const res = await pyApi('diffLanguageTexts', source);
        if (!res.success) { showToast(res.message, 'error'); return; }
        if (res.current === res.source) { showToast('当前语言与源语言相同，无差异。', 'info'); return; }
        let msg = `语言对比: ${res.source} → ${res.current}\n总变更: ${res.total_changes} 处\n\n`;
        for (const [ini, d] of Object.entries(res.diff)) {
            if (d.status === 'source_missing') { msg += `${ini}: 源文件不存在\n`; continue; }
            msg += `${ini}: 新增${d.added} 删除${d.removed} 修改${d.changed}\n`;
            if (d.changed_samples && d.changed_samples.length) {
                msg += '  修改示例:\n';
                d.changed_samples.slice(0, 5).forEach(c => msg += `    #${c.No}: "${c.source}" → "${c.current}"\n`);
            }
        }
        showToast(msg, 'info');
    },

    async showStatus() {
        const res = await pyApi('languageStatus');
        if (!res.success) { showToast(res.message, 'error'); return; }
        let msg = `当前语言: ${res.current}\n\n可用语言:\n`;
        res.available.forEach(a => {
            const icon = a.is_current ? '★ ' : '  ';
            const status = a.complete ? '✓ 完整' : '✗ 缺少: ' + a.missing.join(', ');
            msg += `${icon}${a.label} (${a.lang}) - ${status}\n`;
        });
        showToast(msg, 'info');
    },

    async reload() {
        const res = await pyApi('reloadTermtext');
        if (res.success) {
            showToast(`TermText缓存已刷新 (${res.count} 条)`, 'success');
        } else {
            showToast(res.message, 'error');
        }
    },
};

// 页面加载时自动读取当前语言
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        if (document.getElementById('langCurrent')) languageSwitcher.read();
    }, 500);
});

// ============================================================
// CustomGen 自定义武将编辑器
// ============================================================
const customgenEditor = {
    _generals: [],
    _dirty: {},  // {index: {field: value}}
    _selectedIndex: -1,

    async load() {
        const res = await pyApi('customgenList');
        if (!res.success) { showToast(res.message, 'error'); return; }
        this._generals = res.generals || [];
        this._dirty = {};
        this._selectedIndex = -1;
        document.getElementById('customgenSummary').textContent = `共 ${this._generals.length} 个自定义武将`;
        this.renderList();
        document.getElementById('customgenDetail').style.display = 'none';
    },

    renderList() {
        const list = document.getElementById('customgenList');
        if (!this._generals.length) {
            list.innerHTML = '<p style="padding:16px;color:var(--text-muted);text-align:center;">CustomGen.sav 为空或不存在</p>';
            return;
        }
        list.innerHTML = `<table style="width:100%;font-size:12px;border-collapse:collapse;">
            <thead><tr style="background:var(--bg-page);">
                <th style="padding:6px;text-align:left;">#</th>
                <th style="padding:6px;text-align:left;">名称</th>
                <th style="padding:6px;text-align:left;">等级</th>
                <th style="padding:6px;text-align:left;">武力/智力</th>
                <th style="padding:6px;text-align:left;">体力/技力</th>
                <th style="padding:6px;text-align:center;">操作</th>
            </tr></thead>
            <tbody>${this._generals.map((g, i) => {
                const dirty = this._dirty[i] ? 'background:rgba(255,200,0,0.1);' : '';
                const name = (this._dirty[i] && this._dirty[i].Name) ? this._dirty[i].Name : (g.Name || g.name || '?');
                const level = (this._dirty[i] && this._dirty[i].Level !== undefined) ? this._dirty[i].Level : (g.Level || g.level || '?');
                const str = (this._dirty[i] && this._dirty[i].Str !== undefined) ? this._dirty[i].Str : (g.Str || g.str || '?');
                const intel = (this._dirty[i] && this._dirty[i].Int !== undefined) ? this._dirty[i].Int : (g.Int || g.int || '?');
                const hp = (this._dirty[i] && this._dirty[i].HP !== undefined) ? this._dirty[i].HP : (g.HP || g.hp || '?');
                const mp = (this._dirty[i] && this._dirty[i].MP !== undefined) ? this._dirty[i].MP : (g.MP || g.mp || '?');
                return `<tr style="border-bottom:1px solid var(--border);${dirty}">
                    <td style="padding:6px;color:var(--text-muted);">${i+1}</td>
                    <td style="padding:6px;font-weight:600;">${this._esc(name)}</td>
                    <td style="padding:6px;">${level}</td>
                    <td style="padding:6px;">${str}/${intel}</td>
                    <td style="padding:6px;">${hp}/${mp}</td>
                    <td style="padding:6px;text-align:center;">
                        <button onclick="customgenEditor.showDetail(${i})" class="btn btn-sm btn-primary">详情</button>
                        <button onclick="customgenEditor.deleteOne(${i})" class="btn btn-sm btn-danger">删除</button>
                    </td>
                </tr>`;
            }).join('')}</tbody></table>`;
        document.getElementById('customgenSaveBtn').disabled = Object.keys(this._dirty).length === 0;
    },

    _esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); },

    async showDetail(index) {
        this._selectedIndex = index;
        const res = await pyApi('customgenGet', index);
        if (!res.success) { showToast(res.message, 'error'); return; }
        const g = res.general || {};
        const dirty = this._dirty[index] || {};
        const fields = {};
        for (const [k, v] of Object.entries(g)) {
            fields[k] = k in dirty ? dirty[k] : v;
        }
        // Also include dirty-only fields
        for (const [k, v] of Object.entries(dirty)) {
            if (!(k in fields)) fields[k] = v;
        }

        document.getElementById('customgenDetailName').textContent = fields.Name || fields.name || `武将 #${index+1}`;
        const fieldsDiv = document.getElementById('customgenDetailFields');
        const fieldOrder = ['Name', 'Level', 'Str', 'Int', 'HP', 'MP', 'Weapon', 'Mount', 'Title', 'Nation', 'City', 'Formation', 'Soldier', 'Skill1', 'Skill2', 'Skill3', 'SuperSkill', 'ArmySkill', 'ArmyGroupSkill'];
        const allKeys = [...new Set([...fieldOrder, ...Object.keys(fields)])];
        fieldsDiv.innerHTML = allKeys.map(k => {
            const v = fields[k];
            const label = {Name:'名称',Level:'等级',Str:'武力',Int:'智力',HP:'体力',MP:'技力',Weapon:'武器',Mount:'坐骑',Title:'官职',Nation:'势力',City:'城池',Formation:'阵型',Soldier:'兵种',Skill1:'武将技1',Skill2:'武将技2',Skill3:'武将技3',SuperSkill:'必杀技',ArmySkill:'主将特性',ArmyGroupSkill:'元帅特性'}[k] || k;
            return `<div>
                <label style="font-size:11px;color:var(--text-muted);">${label}</label>
                <input type="text" value="${this._esc(v)}" data-field="${k}" onchange="customgenEditor.onFieldChange('${k}', this.value)" class="form-input" style="width:100%;font-size:12px;">
            </div>`;
        }).join('');
        document.getElementById('customgenDetail').style.display = 'block';
    },

    onFieldChange(field, value) {
        if (this._selectedIndex < 0) return;
        if (!this._dirty[this._selectedIndex]) this._dirty[this._selectedIndex] = {};
        // Try to convert to number
        const num = Number(value);
        this._dirty[this._selectedIndex][field] = isNaN(num) ? value : num;
        document.getElementById('customgenSaveBtn').disabled = false;
    },

    closeDetail() {
        this._selectedIndex = -1;
        document.getElementById('customgenDetail').style.display = 'none';
    },

    async saveDetail() {
        if (this._selectedIndex < 0) return;
        const dirty = this._dirty[this._selectedIndex];
        if (!dirty) return;
        let saved = 0, failed = 0;
        for (const [field, value] of Object.entries(dirty)) {
            const res = await pyApi('customgenEdit', this._selectedIndex, field, value);
            if (res.success) saved++;
            else failed++;
        }
        if (failed === 0) {
            delete this._dirty[this._selectedIndex];
        }
        showToast(`保存完成: ${saved} 成功, ${failed} 失败`, saved > 0 ? 'success' : 'error');
        this.load();
    },

    async saveChanges() {
        const keys = Object.keys(this._dirty);
        if (!keys.length) { showToast('没有待保存的修改', 'info'); return; }
        let totalSaved = 0, totalFailed = 0;
        for (const idx of keys) {
            const dirty = this._dirty[idx];
            for (const [field, value] of Object.entries(dirty)) {
                const res = await pyApi('customgenEdit', parseInt(idx), field, value);
                if (res.success) totalSaved++;
                else totalFailed++;
            }
        }
        this._dirty = {};
        showToast(`批量保存完成: ${totalSaved} 成功, ${totalFailed} 失败`, totalSaved > 0 ? 'success' : 'error');
        this.load();
    },

    async deleteOne(index) {
        if (!confirm(`确定删除自定义武将 #${index+1}？\n此操作不可撤销！`)) return;
        // 通过将所有字段设为空来"删除"（CustomGen.sav 格式不支持真删除）
        const res = await pyApi('customgenEdit', index, 'Name', '');
        if (res.success) {
            showToast('已标记删除', 'success');
            this.load();
        } else {
            showToast(res.message, 'error');
        }
    }
};
