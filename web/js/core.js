/**
 * San7ModMaker - core
 * 从 app.js 拆分而来，保持原始顺序和功能不变
 */

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

/** 更新保存按钮状态（启用/禁用） */
function updateSaveBtnState(btnId, changed) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    if (changed) {
        btn.disabled = false;
        btn.classList.add('unsaved');
        btn.textContent = btn.textContent.replace('保存修改', '保存修改 *');
    } else {
        btn.disabled = true;
        btn.classList.remove('unsaved');
        btn.textContent = btn.textContent.replace(' *', '');
    }
}

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
    _timer: null,
    filter(query) {
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this._doFilter(query), 150);
    },
    _doFilter(query) {
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
        // SHP 像素编辑器
        shpPixelLoad: () => ({ success: false, message: '测试模式' }),
        shpPixelSave: () => ({ success: false, message: '测试模式' }),
        shpGetPalette: () => ({ success: true, palette: [], total: 0, message: '测试模式' }),
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
        getDataFile: () => ({}),
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
        autoBackupConfig: () => ({ success: true, config: { enabled: false, interval_minutes: 30 }, message: '测试模式' }),
        autoBackupStatus: () => ({ success: true, config: { enabled: false, interval_minutes: 30 }, backup_count: 0, last_backup: null }),
        previewBfobjAnimation: () => ({ success: false, message: '测试模式' }),
        listBfobjAnimDirs: () => ({ success: true, dirs: [], count: 0 }),
        checkModCompatibility: () => ({ success: true, compatible: true, game_version: 'unknown', warnings: [], issues: [] }),
        getNextFaceId: () => ({ success: true, next_id: 1, message: '测试模式' }),
        faceBrowse: () => ({ success: true, faces: [], total: 0 }),
        getThingIconPreview: () => ({ success: false, message: '测试模式' }),
        getNextThingIconId: () => ({ success: true, next_id: 1, message: '测试模式' }),
        convertImageToThingIcon: () => ({ success: false, message: '测试模式' }),
        previewModInstall: () => ({ success: true, total_files: 0, will_overwrite: [], will_create: [] }),
        getSoldierObdInfo: () => ({ success: true, obj_id: null, obd_linked: false, message: '测试模式' }),
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
        // MOD 依赖管理
        setModDependencies: () => ({ success: true, dependencies: [], message: '测试模式' }),
        getModDependencies: () => ({ success: true, dependencies: [], total: 0, satisfied: 0, all_satisfied: true, available_mods: [], message: '测试模式' }),
        checkModDependencies: () => ({ success: true, ok: true, missing: [], warnings: [], message: '测试模式' }),
        modConflictDetect: () => ({ success: true, conflicts: [], conflict_count: 0, has_conflicts: false, message: '测试模式' }),
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
        customgenAdd: () => ({ success: false, message: '测试模式' }),
        // 内存预设
        memoryPresets: () => ({ success: true, presets: {}, count: 0 }),
        memoryReadPreset: () => ({ success: false, message: '测试模式' }),
        // SHP改名
        shpBatchRename: () => ({ success: false, message: '测试模式' }),
        shpSelectDir: () => ({ success: true, path: '' }),
        // 城池连线
        cityConnections: () => ({ success: true, cities: {}, positions: {}, map_size: [17472, 12384] }),
        loadCityConnect: () => ({ success: true, data: [], count: 0 }),
        saveCityConnect: () => ({ success: true, message: '保存成功(演示模式)', count: 0 }),
        // id.ini
        loadIdini: () => ({ success: true, data: [], count: 0 }),
        saveIdini: () => ({ success: false, message: '测试模式' }),
        // V3.5.0: BGM/音效编辑器
        browseAudio: () => ({ success: true, dirs: { Music: { path: '', files: [], count: 0 }, Sound: { path: '', files: [], count: 0 } }, total_files: 0 }),
        previewAudio: () => ({ success: false, message: '测试模式' }),
        importAudio: () => ({ success: false, message: '测试模式' }),
        deleteAudio: () => ({ success: false, message: '测试模式' }),
        renameAudio: () => ({ success: false, message: '测试模式' }),
        // V3.5.0: 沙盒测试模式
        createSandbox: () => ({ success: false, message: '测试模式' }),
        installToSandbox: () => ({ success: false, message: '测试模式' }),
        launchSandbox: () => ({ success: false, message: '测试模式' }),
        cleanupSandbox: () => ({ success: false, message: '测试模式' }),
        getSandboxStatus: () => ({ success: true, exists: false }),
        // V3.5.0: 操作历史记录
        getOperationHistory: () => ({ success: true, history: [], total: 0, shown: 0 }),
        clearOperationHistory: () => ({ success: false, message: '测试模式' }),
        // V3.6.0: 批量自动化增强
        batchPreviewAdv: () => ({ success: true, preview: [], count: 0 }),
        batchExecuteAdv: () => ({ success: false, message: '测试模式' }),
        batchPresetList: () => ({ success: true, presets: [], count: 0 }),
        batchPresetSave: () => ({ success: false, message: '测试模式' }),
        batchPresetLoad: () => ({ success: false, message: '测试模式' }),
        batchPresetDelete: () => ({ success: false, message: '测试模式' }),
        batchUndo: () => ({ success: false, message: '测试模式' }),
        batchPipelineExecute: () => ({ success: false, message: '测试模式' }),
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
    'blockcalc':   { editorId: 'blockcalc',   obj: null },
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
    'refcheck': { editorId: 'refcheck', obj: null },
    'exepatch': { editorId: 'exepatch', obj: null },
    'pck': { editorId: 'pck', obj: null },
    'pcpreview': { editorId: 'pcpreview', obj: null },
    // V3.5.0: 新增面板
    'audioeditor': { editorId: 'audioeditor', obj: null },
    'sandbox': { editorId: 'sandbox', obj: null },
    'opshistory': { editorId: 'opshistory', obj: null },
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
    _editorTabMap['bmp2raw'].obj = (typeof bmp2rawTool !== 'undefined') ? bmp2rawTool : { changed: false };
    _editorTabMap['mpc'].obj = (typeof mpcEditor !== 'undefined') ? mpcEditor : { changed: false };
    _editorTabMap['shapeinfo'].obj = (typeof shapeInfoEditor !== 'undefined') ? shapeInfoEditor : { changed: false };
    _editorTabMap['shprename'].obj = (typeof shpRenameTool !== 'undefined') ? shpRenameTool : { changed: false };
    _editorTabMap['cityconnect'].obj = (typeof cityConnect !== 'undefined') ? cityConnect : { changed: false };
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
    _editorTabMap['refcheck'].obj = (typeof refChecker !== 'undefined') ? refChecker : { changed: false };
    _editorTabMap['exepatch'].obj = { changed: false };
    _editorTabMap['pck'].obj = (typeof pckEditor !== 'undefined') ? pckEditor : { changed: false };
    _editorTabMap['pcpreview'].obj = (typeof pckPreview !== 'undefined') ? pckPreview : { changed: false };
    _editorTabMap['blockcalc'].obj = (typeof blockCalc !== 'undefined') ? blockCalc : { changed: false };
    // V3.5.0: 新增面板
    _editorTabMap['audioeditor'].obj = (typeof audioEditor !== 'undefined') ? audioEditor : { changed: false };
    _editorTabMap['sandbox'].obj = (typeof sandboxManager !== 'undefined') ? sandboxManager : { changed: false };
    _editorTabMap['opshistory'].obj = (typeof operationHistory !== 'undefined') ? operationHistory : { changed: false };
}

document.addEventListener('panelsLoaded', () => {
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

    // 初始化 — 串行化避免启动时同时发起多个API请求导致卡顿
    (async () => {
        loadProgress();
        await dashboard.refresh();
        updateGameStatus();
        await backup.loadHistory();
        exepatch.loadInfo();
        mods.refreshList();
    })();

    // SHP像素编辑器初始化
    if (typeof shpPixelEditor !== 'undefined') {
        shpPixelEditor.init().then(() => shpPixelEditor._renderPalette());
    }

    // 标签切换时自动刷新
    document.querySelectorAll('[data-tab="home"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{loadProgress();dashboard.refresh();},100)));
    document.querySelectorAll('[data-tab="backup"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>backup.loadHistory(),100)));
    document.querySelectorAll('[data-tab="exepatch"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>exepatch.loadInfo(),100)));
    document.querySelectorAll('[data-tab="mods"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>mods.refreshList(),100)));
    document.querySelectorAll('[data-tab="generals"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(generals.data.length===0)generals.load();},100)));
    document.querySelectorAll('[data-tab="soldiers"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(soldiers.data.length===0)soldiers.load();},100)));
    document.querySelectorAll('[data-tab="things"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(things.data.length===0)things.load();},100)));
});

// ============================================================
// 首页 - 开发进度
// ============================================================

async function loadProgress() {
    const progress = await pyApi('getProgress');
    if (!progress || !progress.milestones) {
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
    if (!info) { return; }
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

