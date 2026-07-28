/**
 * San7ModMaker - panels-1
 * 从 app.js 拆分而来，保持原始顺序和功能不变
 */

const generals = {
    data: [],
    currentIndex: -1,
    current: null,
    changed: false,
    _pageSize: 50,
    _currentPage: 0,
    _searchKeyword: '',
    // EditorBase 配置
    _undoId: 'generals',
    _fields: ['No', 'Name', 'FaceID', 'WStr', 'Int', 'HP', 'MP',
        'Morale', 'Loyal', 'Relation', 'Sex', 'Race', 'Weapon', 'Horse',
        'Formation', 'BFSoldier', 'BFSoldier1', 'BFSoldier2',
        'HorseSkill', 'Sword', 'Spear', 'Bow', 'Blade', 'Fan',
        'SuperSkill', 'SuperSkillExp', 'FRelation',
        'Father', 'Spouse', 'Lord', 'Respawn', 'IsFamous', 'Life',
        'ResID', 'stringID_FullName', 'stringID_SecondName',
        'stringID_FirstName', 'stringID_CallMySelf', 'stringID_Appellation',
        'DefaultTitle', 'IsEvent', 'ExtraType', 'EventType', 'OffsetZ', 'IsUsed'],
    _fieldPrefix: 'g_',
    _emptyId: 'emptyGeneralDetail',
    _detailId: 'generalDetailContent',
    _countId: 'generalCount',
    _listId: 'generalList',
    _selfRef: 'generals',
    // 复用 EditorBase 方法
    snapshot: EditorBase.snapshot,
    restoreSnapshot: EditorBase.restoreSnapshot,
    pushUndo: EditorBase.pushUndo,
    saveCurrent: EditorBase.saveCurrent,
    _goPage: EditorBase._goPage,
    _renderPagination: EditorBase._renderPagination,

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
        this._renderPagination(filtered, 'generalPagination');
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
        const no = toInt(this.current.No);
        if (no) ReferenceData.showGeneralRef(no);
    },

    renderDetail() {
        const emptyEl = document.getElementById('emptyGeneralDetail');
        const detailEl = document.getElementById('generalDetailContent');
        if (!this.current) {
            if (emptyEl) emptyEl.style.display = 'flex';
            hide(detailEl);
            return;
        }
        hide(emptyEl);
        show(detailEl);

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
        return this.cloneCurrentServer('cloneGeneral', '武将');
    },

    async deleteCurrent() {
        if (!this.current) return;
        if (!confirm(`确认删除武将 "${this.current.Name}" #${this.current.No}?`)) return;
        this.pushUndo();
        const no = toInt(this.current.No);
        // 调用后端删除
        const res = await pyApi('deleteGeneral', no);
        this.data = this.data.filter(g => toInt(g.No) !== no);
        this.current = null;
        this.currentIndex = -1;
        this.changed = true;
        this.renderList();
        const el = document.getElementById('generalCount');
        if (el) el.textContent = this.data.length;
        const emptyEl = document.getElementById('emptyGeneralDetail');
        const detailEl = document.getElementById('generalDetailContent');
        if (emptyEl) emptyEl.style.display = 'flex';
        hide(detailEl);
    },

    async importThingIcon() {
        if (!this.current) { showToast('请先选择一个物品', 'warning'); return; }
        const iconId = toInt(this.current.IconID);
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

    _batchFileChanged() {
        const file = document.getElementById('effBatchFile').value;
        const fieldSelect = document.getElementById('effBatchField');
        const desc = document.getElementById('effBatchDesc');

        if (file === 'thing') {
            fieldSelect.innerHTML = `
                <option value="ScriptNo">ScriptNo (物品特效)</option>
                <option value="BFWResID">BFWResID (武器发光)</option>
            `;
            desc.textContent = '将 Thing.ini 中符合条件的物品特效字段批量替换为新值';
            // 更新级联数据
            let data = this._catalogs ? (this._catalogs.item_scripts || []) : [];
            const oldOpts = data.map(d => `<option value="${d.id}">${d.id} - ${d.name}</option>`).join('');
            const newOpts = data.map(d => `<option value="${d.id}">${d.id} - ${d.name}</option>`).join('');
            document.getElementById('effBatchOldVal').innerHTML = oldOpts;
            document.getElementById('effBatchNewVal').innerHTML = newOpts;
        } else {
            fieldSelect.innerHTML = `
                <option value="Ball">Ball (弹道类型)</option>
                <option value="DamageType">DamageType (伤害类型)</option>
                <option value="Element">Element (属性类型)</option>
                <option value="Atk">Atk (攻击类型)</option>
            `;
            desc.textContent = '将 BFMagic.ini 中符合条件的技能特效字段批量替换为新值';
            this._batchFieldChanged();
        }
        document.getElementById('effBatchResult').innerHTML = '';
        this._batchPreviewData = null;
    },

    _batchFieldChanged() {
        const file = document.getElementById('effBatchFile').value;
        const field = document.getElementById('effBatchField').value;
        let data = [];
        if (file === 'thing') {
            if (field === 'ScriptNo') data = this._catalogs ? (this._catalogs.item_scripts || []) : [];
            else if (field === 'BFWResID') data = this._catalogs ? (this._catalogs.weapon_glow_ids || []) : [];
        } else {
            if (field === 'Ball') data = this._catalogs ? (this._catalogs.ball_types || []) : [];
            else if (field === 'DamageType') data = this._catalogs ? (this._catalogs.damage_types || []) : [];
            else if (field === 'Element') data = this._catalogs ? (this._catalogs.element_types || []) : [];
            else if (field === 'Atk') data = this._catalogs ? (this._catalogs.atk_types || []) : [];
        }
        const oldOpts = data.map(d => `<option value="${d.id}">${d.id} - ${d.name}</option>`).join('');
        const newOpts = data.map(d => `<option value="${d.id}">${d.id} - ${d.name}</option>`).join('');
        document.getElementById('effBatchOldVal').innerHTML = oldOpts;
        document.getElementById('effBatchNewVal').innerHTML = newOpts;
        document.getElementById('effBatchResult').innerHTML = '';
        this._batchPreviewData = null;
    },

    async _batchPreview() {
        const file = document.getElementById('effBatchFile').value;
        const field = document.getElementById('effBatchField').value;
        const oldVal = toInt(document.getElementById('effBatchOldVal').value);
        if (isNaN(oldVal)) { showToast('请选择当前值', 'error'); return; }

        try {
            const r = await pyApi('effectBatchPreview', {field: field, old_value: oldVal, file: file});
            const result = document.getElementById('effBatchResult');
            if (r && r.success) {
                const affected = r.affected || [];
                this._batchPreviewData = affected;
                const typeLabel = file === 'thing' ? '物品' : '技能';
                if (affected.length === 0) {
                    result.innerHTML = `<div style="color:var(--text-muted);padding:8px;">没有匹配的${typeLabel}</div>`;
                } else {
                    let html = `<div style="font-weight:600;margin-bottom:6px;color:var(--warning);">将影响 ${affected.length} 个${typeLabel}：</div>`;
                    html += '<div style="display:flex;flex-wrap:wrap;gap:4px;">';
                    affected.forEach(s => {
                        html += `<span style="background:var(--bg-hover);padding:3px 8px;border-radius:4px;font-size:12px;border:1px solid var(--border);">${escHtml(s.name)} (No.${s.no})</span>`;
                    });
                    html += '</div>';
                    result.innerHTML = html;
                }
            } else {
                result.innerHTML = `<div style="color:var(--danger);">${escHtml(r ? r.message : '预览失败')}</div>`;
            }
        } catch (e) {
            showToast('预览失败: ' + e.message, 'error');
        }
    },

    async _batchExecute() {
        const file = document.getElementById('effBatchFile').value;
        const field = document.getElementById('effBatchField').value;
        const oldVal = toInt(document.getElementById('effBatchOldVal').value);
        const newVal = toInt(document.getElementById('effBatchNewVal').value);
        if (isNaN(oldVal) || isNaN(newVal)) { showToast('请选择当前值和目标值', 'error'); return; }
        if (oldVal === newVal) { showToast('当前值和目标值相同，无需修改', 'error'); return; }

        // 先预览确认
        if (!this._batchPreviewData) {
            await this._batchPreview();
            if (!this._batchPreviewData || this._batchPreviewData.length === 0) return;
        }

        const count = this._batchPreviewData.length;
        const typeLabel = file === 'thing' ? '物品' : '技能';
        if (!confirm(`确定要将 ${count} 个${typeLabel}的 ${field} 字段从 ${oldVal} 修改为 ${newVal} 吗？\n\n此操作会自动备份，但仍建议谨慎操作。`)) return;

        try {
            const r = await pyApi('effectBatchModify', {field: field, old_value: oldVal, new_value: newVal, file: file});
            const result = document.getElementById('effBatchResult');
            if (r && r.success) {
                result.innerHTML = `<div style="color:var(--success);font-weight:600;">✅ ${escHtml(r.message)}</div>`;
                showToast(r.message);
                this._batchPreviewData = null;
                // 刷新交叉引用
                await this._loadCrossRef();
            } else {
                result.innerHTML = `<div style="color:var(--danger);">${escHtml(r ? r.message : '修改失败')}</div>`;
            }
        } catch (e) {
            showToast('批量修改失败: ' + e.message, 'error');
        }
    },

    async exportThingIcon() {
        if (!this.current) { showToast('请先选择一个物品', 'warning'); return; }
        const iconId = toInt(this.current.IconID);
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
        const fid = toInt(el.value);
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
        const fid = toInt(el.value);
        const filePath = await pyApi('selectImageFile');
        if (!filePath.success || !filePath.path) return;
        const res = await pyApi('convertImageToShp', filePath.path, fid);
        if (res.success) {
            this.refreshFacePreview();
            const logBox = document.getElementById('faceConversionLog');
            if (logBox && res.log) {
                logBox.style.display = 'block';
                logBox.innerHTML = res.log.map(l => `<div>${escHtml(l)}</div>`).join('');
            }
            showToast('头像转换完成，已保存至Shape/Face目录', 'success');
        } else {
            showToast('转换失败: ' + res.message, 'error');
        }
    },

    async exportCurrentFace() {
        const el = document.getElementById('g_FaceID');
        if (!el) return;
        const fid = toInt(el.value);
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
    const start = toInt(document.getElementById('faceBatchStart').value) || 1;
    const count = toInt(document.getElementById('faceBatchCount').value) || 50;
    const res = await pyApi('facePreview', start, count);
    if (!res.success) { showToast(res.message, res && res.success ? 'success' : 'error'); return; }
    _faceBatchData = res.previews || [];
    _faceBatchSelected.clear();
    document.getElementById('faceBatchStats').textContent =
        `共 ${res.total_found} 个 (${start}-${start + count - 1})`;
    renderFaceGrid();
}

const renderFaceGrid = () => {
    const grid = document.getElementById('faceBatchGrid');
    if (!_faceBatchData.length) {
        grid.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:20px;grid-column:1/-1;">无头像</div>';
        return;
    }
    grid.innerHTML = _faceBatchData.map(f => `
        <div class="face-thumb ${_faceBatchSelected.has(f.id) ? 'selected' : ''}"
             onclick="faceBatchToggle(${f.id})" title="#${f.id} (${(f.size/1024).toFixed(1)}KB)">
            <img src="${f.base64}" width="64" height="64" loading="lazy" alt="头像#${f.id}">
            <span class="face-id">${f.id}</span>
        </div>
    `).join('');
}

const faceBatchToggle = (id) => {
    if (_faceBatchSelected.has(id)) _faceBatchSelected.delete(id);
    else _faceBatchSelected.add(id);
    renderFaceGrid();
}

const faceBatchSelectAll = () => {
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
    // EditorBase 配置
    _undoId: 'soldiers',
    _fields: ['No','Name','OrderNo','ObjID','Data01','Data02','Data03','SuperHit','Feature','Sex','DieMode','Rank','Upgrade','OffsetZ','SizeX','Str','Int','Life','Speed','Interval','DetectRangeMin','DetectRangeMax','Weapon','WeaponSpeed','BasePower','AddPower','Height','Horse','Type','Color','Special','IsUsed','BFMagic','SFMagic','SuperAttack'],
    _fieldPrefix: 's_',
    _emptyId: 'emptySoldierDetail',
    _detailId: 'soldierDetailContent',
    _countId: 'soldierCount',
    _listId: 'soldierList',
    _selfRef: 'soldiers',
    // 复用 EditorBase 方法
    snapshot: EditorBase.snapshot,
    restoreSnapshot: EditorBase.restoreSnapshot,
    pushUndo: EditorBase.pushUndo,
    saveCurrent: EditorBase.saveCurrent,

    async load() {
        const res = await pyApi('loadSoldiers');
        if (!res.success) { showToast(res.message, 'error'); return; }
        this.data = res.data || [];
        this.currentIndex = -1; this.current = null;
        this.renderList();
        const el = $(this._countId); if (el) el.textContent = this.data.length;
        const warning = document.getElementById('soldierLimitWarning');
        if (warning) warning.style.display = res.over_limit ? 'inline' : 'none';
        // 初始化矩阵和升级树
        matrix.init(this.data);
        upgradeTree.render();
        setupTooltips('soldier', 's_');
    },

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
                <div class="item-desc">生命 ${s.Life || '-'} 攻击 ${s.BasePower || '-'} 防御 ${s.AddPower || '-'}</div>
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
            hide(detailEl);
            return;
        }
        hide(emptyEl);
        show(detailEl);
        const fields = ['No','Name','OrderNo','ObjID','Data01','Data02','Data03','SuperHit','Feature','Sex','DieMode','Rank','Upgrade','OffsetZ','SizeX','Str','Int','Life','Speed','Interval','DetectRangeMin','DetectRangeMax','Weapon','WeaponSpeed','BasePower','AddPower','Height','Horse','Type','Color','Special','IsUsed','BFMagic','SFMagic','SuperAttack'];
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
            const upgTo = toInt(this.current.Upgrade);
            if (upgTo > 0) {
                const target = this.data.find(s => toInt(s.No) === upgTo);
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
        // BFMagic/SFMagic 技能名称提示
        const bfHint = document.getElementById('s_BFMagicHint');
        if (bfHint) {
            const bfVal = toInt(this.current.BFMagic);
            bfHint.textContent = bfVal > 0 ? this._getSkillName(bfVal) : '';
        }
        const sfHint = document.getElementById('s_SFMagicHint');
        if (sfHint) {
            const sfVal = toInt(this.current.SFMagic);
            sfHint.textContent = sfVal > 0 ? this._getSkillName(sfVal) : '';
        }
        // 加载 OBD 模型列表到下拉框
        this._loadOBDModelList();
        // 显示模型预览面板
        const previewPanel = document.getElementById('soldierModelPreview');
        if (previewPanel) {
            previewPanel.style.display = this.current.ObjID ? 'block' : 'none';
        }
        const modelInfo = document.getElementById('soldierModelInfo');
        if (modelInfo) {
            modelInfo.textContent = this.current.ObjID ? `ObjID=${this.current.ObjID}` : '';
        }
    },

    async _loadOBDModelList() {
        const select = document.getElementById('s_ObjIDSelect');
        if (!select) return;
        // 如果已加载过，跳过
        if (select._loaded) {
            this._syncObjIDSelect();
            return;
        }
        try {
            const res = await pyApi('listOBDModels', 'bfsoldier');
            if (res && res.success && res.data) {
                this._obdModels = res.data;
                select.innerHTML = '<option value="">-- 选择模型 --</option>';
                res.data.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m.obj_id;
                    opt.textContent = `#${m.sequence} ${m.name} (ObjID=${m.obj_id}, ${m.action_count}动作)`;
                    opt.dataset.seq = m.sequence;
                    select.appendChild(opt);
                });
                select._loaded = true;
                this._syncObjIDSelect();
            }
        } catch(e) { console.warn('OBD模型列表加载失败:', e); }
    },

    _syncObjIDSelect() {
        const select = document.getElementById('s_ObjIDSelect');
        if (!select || !this.current) return;
        const curObjId = String(this.current.ObjID || '');
        // 尝试匹配
        for (let i = 0; i < select.options.length; i++) {
            if (select.options[i].value === curObjId) {
                select.selectedIndex = i;
                return;
            }
        }
        select.selectedIndex = 0; // 未匹配
    },

    onObjIDSelect() {
        const select = document.getElementById('s_ObjIDSelect');
        if (!select || !this.current) return;
        const val = select.value;
        if (val !== '') {
            document.getElementById('s_ObjID').value = val;
            this.current.ObjID = val;
            this.changed = true;
            // 显示模型预览
            const previewPanel = document.getElementById('soldierModelPreview');
            show(previewPanel);
            const modelInfo = document.getElementById('soldierModelInfo');
            if (modelInfo) modelInfo.textContent = `ObjID=${val}`;
            // 更新提示
            const objHint = document.getElementById('s_ObjIDHint');
            if (objHint) {
                const selectedOpt = select.options[select.selectedIndex];
                const seq = selectedOpt ? selectedOpt.dataset.seq : '';
                objHint.textContent = seq ? `(Sequence=${seq})` : '(对应OBD Sequence尾数)';
            }
        }
    },

    _getSkillName(no) {
        // 从技能缓存中查找技能名称
        if (typeof skillsData !== 'undefined' && skillsData.length) {
            const skill = skillsData.find(s => toInt(s.No) === no);
            if (skill) return `→ ${skill.Name}`;
        }
        return '';
    },

    jumpToOBD() {
        if (!this.current) return;
        const objId = this.current.ObjID;
        if (!objId) { showToast('请先设置 ObjID', 'warning'); return; }
        // 切换到 OBD 编辑器面板
        const tabBtns = document.querySelectorAll('.tab-btn');
        tabBtns.forEach(b => {
            if (b.dataset.tab === 'obd') b.click();
        });
        // 选择 bfsoldier 类型并高亮对应模型
        setTimeout(() => {
            const typeSel = document.getElementById('obdType');
            if (typeSel) typeSel.value = 'bfsoldier';
            if (typeof obdEditor !== 'undefined' && obdEditor.load) {
                obdEditor.load().then(() => {
                    // 查找匹配的模型
                    const match = obdEditor.data.find(o => (o.sequence % 100) === toInt(objId));
                    if (match !== undefined) {
                        const idx = obdEditor.data.indexOf(match);
                        if (idx >= 0) obdEditor.select(idx);
                    }
                    showToast(`已跳转到 OBD 编辑器 (ObjID=${objId})`, 'info');
                });
            }
        }, 200);
    },

    async loadModelPreview() {
        if (!this.current || !this.current.ObjID) return;
        const objId = toInt(this.current.ObjID);
        const previewImg = document.getElementById('soldierModelPreviewImg');
        if (!previewImg) return;
        previewImg.innerHTML = '<span style="color:var(--text-muted);">加载中...</span>';

        // 从缓存的 OBD 模型列表中查找 Sequence
        let sequence = null;
        if (this._obdModels) {
            const match = this._obdModels.find(m => m.obj_id === objId);
            if (match) sequence = match.sequence;
        }
        if (!sequence) {
            previewImg.innerHTML = '<span style="color:var(--error);font-size:12px;">未找到对应 OBD 模型</span>';
            return;
        }

        try {
            const res = await pyApi('obdPreviewSpriteFrame', 'bfsoldier', sequence, 'Wait', 0);
            if (res && res.success && res.image_base64) {
                previewImg.innerHTML = `<img src="data:image/png;base64,${res.image_base64}" style="max-width:200px;max-height:200px;image-rendering:pixelated;border:1px solid var(--border);border-radius:4px;" alt="模型预览">`;
            } else {
                previewImg.innerHTML = `<span style="color:var(--text-muted);font-size:12px;">${escHtml(res.message || '无法加载预览')}</span>`;
            }
        } catch(e) {
            previewImg.innerHTML = `<span style="color:var(--error);font-size:12px;">加载失败: ${escHtml(String(e))}</span>`;
        }
    },

    currentChanged() {
        this.changed = true;
        this._updateThingEffectPreview();
    },

    saveCurrent() {
        if (!this.current) return;
        const fields = ['No','Name','OrderNo','ObjID','Data01','Data02','Data03','SuperHit','Feature','Sex','DieMode','Rank','Upgrade','OffsetZ','SizeX','Str','Int','Life','Speed','Interval','DetectRangeMin','DetectRangeMax','Weapon','WeaponSpeed','BasePower','AddPower','Height','Horse','Type','Color','Special','IsUsed','BFMagic','SFMagic','SuperAttack'];
        fields.forEach(k => {
            const el = document.getElementById('s_' + k);
            if (el) this.current[k] = el.value;
        });
    },

    async addNew() {
        return this.addNewServer('newSoldier');
    },

    async cloneCurrent() {
        return this.cloneCurrentLocal('兵种');
    },

    deleteCurrent() {
        if (!this.current) return;
        if (!confirm(`确认删除兵种 "${this.current.Name}" #${this.current.No}?\n\n此操作将同时清理:\n- Soldier.ini 条目\n- OBD 模型 (BFSoldier.obd)\n- TermText 名称\n- 兵符物品 (Thing.ini)`)) return;
        this.pushUndo();
        const no = toInt(this.current.No);
        pyApi('deleteSoldier', no)
            .then(res => {
                if (res && res.success) {
                    showToast(res.message, 'success');
                    if (res.linkage && res.linkage.length) {
                        showToast('联动清理: ' + res.linkage.join('; '), 'info');
                    }
                } else {
                    showToast((res && res.message) || '删除失败', 'error');
                }
            })
            .catch(e => showToast('删除失败: ' + e, 'error'));
        this.data = this.data.filter(s => toInt(s.No) !== no);
        this.current = null;
        this.currentIndex = -1;
        this.changed = true;
        this.renderList();
        const el = document.getElementById('soldierCount');
        if (el) el.textContent = this.data.length;
        const emptyEl = document.getElementById('emptySoldierDetail');
        const detailEl = document.getElementById('soldierDetailContent');
        if (emptyEl) emptyEl.style.display = 'flex';
        hide(detailEl);
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
                    <div class="item-desc">生命 ${s.Life || '-'} 攻击 ${s.BasePower || '-'} 防御 ${s.AddPower || '-'}</div>
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
    _countId: 'thingCount',
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
        const no = toInt(this.current.No);
        if (no) ReferenceData.showThingRef(no);
    },

    async _loadTermText() {
        if (!this.current) return;
        const no = toInt(this.current.No);
        if (!no) return;
        try {
            const res = await pyApi('getThingTermText', no);
            const nameEl = document.getElementById('t_termName');
            const descEl = document.getElementById('t_termDesc');
            if (nameEl) nameEl.value = res.name || '';
            if (descEl) descEl.value = res.desc || '';
        } catch(e) { console.warn('TermText加载失败:', e); }
    },

    async _saveTermText() {
        if (!this.current) return;
        const no = toInt(this.current.No);
        if (!no) return;
        const nameEl = document.getElementById('t_termName');
        const descEl = document.getElementById('t_termDesc');
        const name = nameEl ? nameEl.value : '';
        const desc = descEl ? descEl.value : '';
        if (!name && !desc) return;
        try {
            await pyApi('setThingTermText', no, name, desc);
        } catch(e) { console.warn('TermText保存失败:', e); }
    },

    renderDetail() {
        const emptyEl = document.getElementById('emptyThingDetail');
        const detailEl = document.getElementById('thingDetailContent');
        if (!this.current) {
            if (emptyEl) emptyEl.style.display = 'flex';
            hide(detailEl);
            return;
        }
        hide(emptyEl);
        show(detailEl);
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
        // 更新特效预览
        this._updateThingEffectPreview();
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
        // 切换到武器选项卡时刷新特效预览
        if (tabId === 'thing_weapon') this._updateThingEffectPreview();
    },

    // ============================================================
    // 武器特效预览 — 在武器专属选项卡中可视化 ScriptNo 和 BFWResID
    // ============================================================
    _updateThingEffectPreview() {
        const panel = document.getElementById('thingEffectPreview');
        const content = document.getElementById('thingEffectPreviewContent');
        if (!panel || !content) return;
        if (!this.current || String(this.current.Type) !== '2') {
            panel.style.display = 'none';
            return;
        }
        panel.style.display = 'block';

        const scriptNo = toInt(this.current.ScriptNo);
        const bfwResId = toInt(this.current.BFWResID);
        const scriptHit = toInt(this.current.ScriptHit);

        // 从 effectEditor 获取知识库数据（如果未加载则尝试加载）
        const catalogs = (typeof effectEditor !== 'undefined' && effectEditor._catalogs) ? effectEditor._catalogs : null;
        const itemScripts = catalogs ? (catalogs.item_scripts || []) : [];
        const weaponGlowIds = catalogs ? (catalogs.weapon_glow_ids || []) : [];

        // 查找匹配的特效数据
        const scriptInfo = itemScripts.find(s => s.id === scriptNo);
        const glowInfo = weaponGlowIds.find(g => g.id === bfwResId);

        // 特效名称和图标映射
        const scriptIcons = {
            0:'○',1:'⚔',2:'🗡',3:'↗',4:'↔',5:'⚡',6:'🩸',7:'💨',8:'💫',9:'☠',10:'❄',
            11:'🔥',12:'⚡',13:'✂',14:'💥',15:'🛡',16:'💚',17:'✨',18:'↗',19:'↔',20:'◆'
        };
        const scriptColors = [
            C.muted,'#ff4444','#ff8800','#44aaff','#ffaa00','#ffdd00','#ff0000','#8844ff',
            C.codeHighlight,'#88ff44','#88ccff','#ff6600','#ffdd00','#aa44ff','#ff8800','#aa8844',
            '#44ff44','#ff44ff','#ffaa00','#ff8800','#8844ff'
        ];

        let html = '';

        // ScriptNo 特效预览
        if (scriptInfo) {
            const icon = scriptIcons[scriptNo] || '✦';
            const color = scriptColors[scriptNo % scriptColors.length] || '#ffaa00';
            html += `
                <div style="text-align:center;min-width:70px;">
                    <div style="font-size:32px;color:${color};line-height:1;">${icon}</div>
                    <div style="font-size:10px;color:var(--text-muted);margin-top:2px;">ScriptNo=${scriptNo}</div>
                </div>
                <div style="display:flex;flex-direction:column;gap:5px;font-size:11px;">
                    <div style="font-weight:600;color:var(--primary);">${scriptInfo.name}</div>
                    <div style="color:var(--text-muted);max-width:180px;">${scriptInfo.desc}</div>
                    ${scriptInfo.weapon_example ? `<div style="color:var(--text-muted);">示例: <span style="color:var(--accent);">${scriptInfo.weapon_example}</span></div>` : ''}
                    <div style="margin-top:2px;"><span style="color:var(--text-muted);">发动概率:</span><span style="font-weight:600;color:var(--warning);">${scriptHit}%</span></div>
                </div>`;
        } else {
            html += `
                <div style="text-align:center;min-width:70px;">
                    <div style="font-size:32px;color:${C.muted};line-height:1;">○</div>
                    <div style="font-size:10px;color:var(--text-muted);margin-top:2px;">ScriptNo=${scriptNo}</div>
                </div>
                <div style="display:flex;flex-direction:column;gap:5px;font-size:11px;">
                    <div style="color:var(--text-muted);">${scriptNo === 0 ? '无特效' : '未知特效编号'}</div>
                    <div style="color:var(--text-muted);">请在特效参考面板中查看详情</div>
                </div>`;
        }

        // BFWResID 发光预览
        if (glowInfo) {
            html += `
                <div style="width:1px;height:60px;background:var(--border);"></div>
                <div style="text-align:center;min-width:70px;">
                    <div style="width:36px;height:36px;border-radius:50%;background:${glowInfo.color};margin:0 auto;box-shadow:0 0 12px ${glowInfo.color}80;"></div>
                    <div style="font-size:10px;color:var(--text-muted);margin-top:4px;">BFWResID=${bfwResId}</div>
                </div>
                <div style="display:flex;flex-direction:column;gap:5px;font-size:11px;">
                    <div style="font-weight:600;color:var(--primary);">${glowInfo.name}</div>
                    <div style="color:var(--text-muted);max-width:180px;">${glowInfo.desc}</div>
                    ${glowInfo.example ? `<div style="color:var(--text-muted);">示例: <span style="color:var(--accent);">${glowInfo.example}</span></div>` : ''}
                </div>`;
        } else if (bfwResId > 0) {
            html += `
                <div style="width:1px;height:60px;background:var(--border);"></div>
                <div style="text-align:center;min-width:70px;">
                    <div style="width:36px;height:36px;border-radius:50%;background:#888;margin:0 auto;"></div>
                    <div style="font-size:10px;color:var(--text-muted);margin-top:4px;">BFWResID=${bfwResId}</div>
                </div>
                <div style="display:flex;flex-direction:column;gap:5px;font-size:11px;">
                    <div style="color:var(--text-muted);">未知发光编号</div>
                    <div style="color:var(--text-muted);">点击 🎯 OBD 按钮查看</div>
                </div>`;
        }

        content.innerHTML = html;
    },

    // 跳转到 OBD 编辑器查看发光模型
    _navigateToOBD() {
        if (!this.current) return;
        const bfwResId = toInt(this.current.BFWResID);
        const navItem = document.querySelector('[data-tab="obdeditor"]');
        if (navItem) {
            navItem.click();
            setTimeout(() => {
                if (typeof obdEditor !== 'undefined' && obdEditor.selectCategory) {
                    obdEditor.selectCategory('BFWeapon');
                }
                const catSelect = document.getElementById('obdCategory');
                if (catSelect) {
                    catSelect.value = 'BFWeapon';
                    catSelect.dispatchEvent(new Event('change'));
                }
                const searchInput = document.getElementById('obdSearch');
                if (searchInput) {
                    searchInput.value = String(bfwResId).padStart(4, '0');
                    searchInput.dispatchEvent(new Event('input'));
                }
                showToast(`已跳转到 OBD 编辑器，筛选 BFWeapon 类型，搜索编号 ${bfwResId}`);
            }, 300);
        } else {
            showToast('OBD 编辑器导航项不存在', 'error');
        }
    },

    async addNew() {
        return this.addNewServer('newThing');
    },

    async cloneCurrent() {
        return this.cloneCurrentLocal('物品');
    },

    deleteCurrent() {
        if (!this.current) return;
        if (!confirm(`确认删除物品 "${this.current.Name}" #${this.current.No}?`)) return;
        this.pushUndo();
        const no = toInt(this.current.No);
        pyApi('deleteIniItem', 'Setting/Thing.ini', 'THING', 'No', String(no))
            .catch(e => showToast('删除失败: ' + e, 'error'));
        this.data = this.data.filter(t => toInt(t.No) !== no);
        this.current = null;
        this.currentIndex = -1;
        this.changed = true;
        this.renderList();
        const el = document.getElementById('thingCount');
        if (el) el.textContent = this.data.length;
        const emptyEl = document.getElementById('emptyThingDetail');
        const detailEl = document.getElementById('thingDetailContent');
        if (emptyEl) emptyEl.style.display = 'flex';
        hide(detailEl);
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

        // 使用数组批量构建，避免 O(n²) 字符串拼接
        const parts = [];
        parts.push('<table class="matrix-table"><thead><tr><th>#</th>');
        this._soldiers.forEach(s => {
            parts.push(`<th title="${s.Name || ''}">${s.No}</th>`);
        });
        parts.push('</tr></thead><tbody>');

        this._soldiers.forEach(attacker => {
            const aNo = attacker.No;
            parts.push(`<tr><th title="${attacker.Name || ''}">${aNo}</th>`);
            this._soldiers.forEach(defender => {
                const dNo = defender.No;
                const val = (this._data[aNo] && this._data[aNo][dNo] !== undefined) ? this._data[aNo][dNo] : 1.0;
                const fval = parseFloat(val);

                let cls = 'equal';
                if (fval > 1.0) cls = 'over';
                else if (fval < 1.0) cls = 'under';

                let show = true;
                if (filter === 'gt1' && fval <= 1.0) show = false;
                if (filter === 'lt1' && fval >= 1.0) show = false;

                if (show) {
                    parts.push(`<td class="matrix-cell ${cls}"><input type="number" value="${val}" step="0.1" min="0.1" max="5.0" onchange="matrix._setCell('${aNo}','${dNo}',this.value)" onfocus="matrix._onFocus(this)" title="${attacker.Name||aNo} → ${defender.Name||dNo}: ${val}"></td>`);
                } else {
                    parts.push(`<td class="matrix-cell"><input type="number" value="${val}" step="0.1" min="0.1" max="5.0" onchange="matrix._setCell('${aNo}','${dNo}',this.value)" style="color:#555;"></td>`);
                }
            });
            parts.push('</tr>');
        });
        parts.push('</tbody></table>');
        container.innerHTML = parts.join('');
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
            const lvl = toInt(s.Level) || 1;
            map[s.No] = s;
            if (lvl === 1) t1.push(s);
            else if (lvl === 2) t2.push(s);
            else t3.push(s);
        });

        let html = '<div class="upgrade-tree">';

        data.forEach(s => {
            const upgradeTo = toInt(s.Upgrade);
            const target = upgradeTo ? map[upgradeTo] : null;
            const targetName = target ? target.Name : '-';
            const lvl = toInt(s.Level) || 1;
            const lvlLabel = lvl === 1 ? '1阶' : (lvl === 2 ? '2阶' : '3阶');

            html += `
                <div class="upgrade-node">
                    <div class="upgrade-node-name">[${lvlLabel}] ${s.Name || '无名'}</div>
                    <div class="upgrade-node-info">编号: ${s.No} | 生命:${s.Life||'-'} 攻击:${s.BasePower||'-'}</div>
                    ${upgradeTo > 0 ? `<div class="upgrade-arrow">→ 升级至: ${targetName} (#${upgradeTo})</div>` : '<div class="upgrade-node-info">无升级路线</div>'}
                    ${this._editMode ? `<div style="margin-top:4px;font-size:11px;">
                        <span>升级至: </span>
                        <select onchange="upgradeTree._updateUpgrade(${s.No}, this.value)" style="font-size:11px;padding:1px 2px;">
                            <option value="0" ${upgradeTo===0?'selected':''}>无</option>
                            ${data.filter(x=>String(x.No)!==String(s.No)).map(x=>`<option value="${x.No}" ${upgradeTo===toInt(x.No)?'selected':''}>#${x.No} ${x.Name||''}</option>`).join('')}
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
        const startNo = toInt(document.getElementById('batchRenameStart').value) || 1;
        const resultEl = document.getElementById('batchRenameResult');
        if (!prefix) { showToast('请输入名称前缀', 'warning'); return; }
        if (resultEl) resultEl.innerHTML = '<span style="color:var(--warning);">正在重命名...</span>';
        try {
            const res = await pyApi('batchRename', type, prefix, startNo);
            if (resultEl) {
                if (res && res.success) {
                    resultEl.innerHTML = `<span style="color:var(--success);">重命名完成: ${res.renamed || 0} 个条目</span>`;
                } else {
                    resultEl.innerHTML = `<span style="color:var(--danger);">重命名失败: ${escHtml(res ? res.message : '未知错误')}</span>`;
                }
            }
            if (res && res.message) showToast(res.message, res.success ? 'success' : 'error');
        } catch(e) {
            if (resultEl) resultEl.innerHTML = `<span style="color:var(--danger);">重命名异常: ${escHtml(String(e))}</span>`;
            showToast('重命名异常: ' + escHtml(String(e)), 'error');
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
            hide(detailEl);
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
            hide(detailEl);
            return;
        }
        hide(emptyEl);
        show(detailEl);
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
        const usedIds = new Set(this.data.map(c => toInt(c.No)));
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
        const usedIds = new Set(this.data.map(c => toInt(c.No)));
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
        hide(detailEl);
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
        const table = tbody.closest('table');

        // 收集所有武将编号
        const allGenNos = new Set();
        const skillSections = [];
        const featSections = [];

        for (const [secName, entries] of Object.entries(data)) {
            if (secName.startsWith('GenSkill') && /^\d+$/.test(secName.replace('GenSkill', ''))) {
                skillSections.push({ name: secName, index: toInt(secName.replace('GenSkill', '')), entries });
            } else if (secName.startsWith('GenFeature') && /^\d+$/.test(secName.replace('GenFeature', ''))) {
                featSections.push({ name: secName, index: toInt(secName.replace('GenFeature', '')), entries });
            }
        }

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

        const genNos = Array.from(allGenNos).sort((a, b) => toInt(a) - toInt(b));

        // 使用数组批量构建HTML，一次性innerHTML，避免多次重排
        const parts = [];
        genNos.forEach(genNo => {
            const name = (this._generals && this._generals[genNo]) || '未知';
            parts.push(`<tr data-gen="${genNo}">${this._buildRow(genNo, name, skillSections, featSections)}</tr>`);
        });
        tbody.innerHTML = parts.join('');

        // 事件委托：在table上统一处理行点击
        if (table && !table._dsClickBound) {
            table._dsClickBound = true;
            table.addEventListener('click', (e) => {
                const tr = e.target.closest('tr[data-gen]');
                if (!tr) return;
                const genNo = tr.getAttribute('data-gen');
                const prev = tbody.querySelector('tr.selected');
                if (prev) prev.classList.remove('selected');
                if (this._currentGenNo === genNo) {
                    this._currentGenNo = null;
                } else {
                    tr.classList.add('selected');
                    this._currentGenNo = genNo;
                }
            });
        }
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

    saveCurrent() {
        if (Object.keys(this._modified).length === 0) {
            showToast('没有需要保存的修改', 'info');
            return;
        }
        showToast('当前必杀技修改已记录，请点击"保存"提交', 'info');
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
        if (!res || !res.history) {
            tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;color:${C.muted};">暂无备份</td></tr>`;
            return;
        }
        const history = res.history || [];
        if (history.length === 0) {
            tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;color:${C.muted};">暂无备份</td></tr>`;
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
            container.innerHTML = `<div style="padding:20px;text-align:center;color:${C.muted};">没有检查出任何问题</div>`;
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
        value = toInt(value);
        if (isNaN(value)) { showToast('请输入有效数值', 'warning'); return; }
        if (!confirm(`确认修改 ${name} 为 ${value}？`)) return;
        const res = await pyApi('applyExePatchAuto', name, value);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.loadInfo();
    },

    async apply(name, offset, value) {
        value = toInt(value);
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
        const offset = toInt(offsetStr, offsetStr.startsWith('0x') ? 16 : 10);
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
        const offset = toInt(offsetStr, offsetStr.startsWith('0x') ? 16 : 10);
        if (isNaN(offset)) { showToast('无效偏移地址', 'warning'); return; }

        const args = [];
        if (argStr) {
            const arg = toInt(argStr, argStr.startsWith('0x') ? 16 : 10);
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
        const w = toInt(document.getElementById('cfg_width')?.value);
        const h = toInt(document.getElementById('cfg_height')?.value);
        const fs = toInt(document.getElementById('cfg_fullscreen')?.value);
        if (!w || !h) { showToast('请输入有效的分辨率', 'warning'); return; }
        const res = await pyApi('setSango7Config', w, h, fs);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        this.loadSango7Config();
    },

    async scanValue() {
        const val = prompt('输入要搜索的数值:', '999');
        if (!val) return;
        const v = toInt(val);
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
                container.innerHTML = '<span style="font-size:13px;color:var(--text-muted);">加载失败: ' + escHtml(res ? res.message : '') + '</span>';
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
        value = toInt(value);
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
                grid.innerHTML = '<p class="hint">加载失败: ' + escHtml(r ? r.message : '') + '</p>';
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
        info.innerHTML = `<span>${escHtml(this._currentCategory)}: <b>${files.length}</b> 个文件</span>
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
                        el.innerHTML = `<img src="${escHtml(r.thumbnails[f.path])}" alt="缩略图" style="width:48px;height:48px;object-fit:contain;image-rendering:pixelated;" />`;
                    }
                });
            }
        } catch(e) { console.warn('缩略图加载失败:', e); }
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
                const faceId = toInt(path.replace(/\D/g, ''));
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
        hide(modal);
    },

    async batchImport() {
        const src = prompt('输入源图片路径 (支持 BMP/PNG/JPG):');
        if (!src) return;
        try {
            let apiName = 'convertImageToBfobjShp';
            if (this._currentCategory === 'Face') {
                const faceId = prompt('输入目标头像编号 (如 1000):');
                if (!faceId) return;
                const r = await pyApi('convertImageToShp', src, toInt(faceId));
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
                    resultEl.innerHTML = `<span style="color:var(--danger);">转换失败: ${escHtml(res ? res.message : '未知错误')}</span>`;
                }
            }
            if (res && res.message) showToast(res.message, res.success ? 'success' : 'error');
        } catch(e) {
            if (resultEl) resultEl.innerHTML = `<span style="color:var(--danger);">转换异常: ${escHtml(String(e))}</span>`;
            showToast('转换异常: ' + escHtml(String(e)), 'error');
        }
    },

    async previewAnimation() {
        const obdType = document.getElementById('bfobjAnimType')?.value || 'BFSoldier';
        const number = document.getElementById('bfobjAnimNumber')?.value || '';
        const animType = document.getElementById('bfobjAnimName')?.value || 'Wait';
        if (!number) { showToast('请输入模型编号', 'info'); return; }
        const preview = document.getElementById('bfobjAnimPreview');
        if (preview) preview.innerHTML = '<p style="text-align:center;color:var(--text-muted);">加载动画中...</p>';
        try {
            const r = await pyApi('previewBfobjAnimation', obdType, number, animType);
            if (r && r.success && r.base64) {
                if (preview) preview.innerHTML = '<img src="' + r.base64 + '" alt="动画预览" style="max-width:100%;image-rendering:pixelated;" title="' + escHtml(r.message) + '"><p style="text-align:center;font-size:11px;color:var(--text-muted);margin-top:4px;">' + escHtml(r.message) + '</p>';
            } else {
                if (preview) preview.innerHTML = '<p style="text-align:center;color:var(--text-muted);">' + escHtml(r ? r.message : '预览失败') + '</p>';
            }
        } catch(e) {
            if (preview) preview.innerHTML = '<p style="text-align:center;color:var(--danger);">预览失败: ' + escHtml(String(e)) + '</p>';
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
        const maxNo = this._data.reduce((max, h) => Math.max(max, toInt(h.No)), 0);
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
        const maxNo = this._data.reduce((max, h) => Math.max(max, toInt(h.No)), 0);
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
            const typeName = this._getClassTypeName(toInt(ctype));
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

    saveCurrent() {
        if (this._selectedIndex < 0) return;
        this._dirty = true;
        showToast('当前事件已修改，请点击"保存"提交', 'info');
    },

    async delete() {
        if (this._selectedIndex < 0) { showToast('请先选择一个事件', 'warning'); return; }
        const entry = this._data[this._selectedIndex];
        if (!confirm(`确认删除事件 #${entry.No || ''}?`)) return;
        this.pushUndo();
        const res = await pyApi('deleteHistory', entry.No);
        if (res.success) {
            this._data.splice(this._selectedIndex, 1);
            this._selectedIndex = -1;
            this._dirty = true;
            this.renderList();
            document.getElementById('historyCount').textContent = `共 ${this._data.length} 个事件`;
            document.getElementById('historyDetail').innerHTML = '<p style="color:var(--text-muted);padding:20px;">请从左侧列表选择一个事件</p>';
        }
        showToast(res.message || '删除完成', res.success ? 'success' : 'error');
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

    saveCurrent() {
        const content = document.getElementById('scriptEditorArea').value;
        if (content !== this._originalContent) {
            this._dirty = true;
            showToast('当前脚本已修改，请点击"保存"提交', 'info');
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
                <div style="font-size:11px;color:${selected ? 'rgba(255,255,255,0.7)' : C.muted};">${escHtml(String(f.size_kb))} KB</div>
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

    addNew() {
        this.newFile();
    },

    deleteCurrent() {
        this.deleteFile();
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
        const offset = toInt(document.getElementById('scriptsoHexOffset').value);
        const length = toInt(document.getElementById('scriptsoHexLength').value) || 512;
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
        let offset = toInt(offsetStr, offsetStr.startsWith('0x')?16:10);
        if (isNaN(offset)) { showToast('无效的偏移值', 'warning'); return; }
        try {
            const r = await pyApi('scriptsoHexWrite', offset, dataHex);
            const el = document.getElementById('scriptsoEditResult');
            if (r && r.success) {
                el.textContent = `✓ 已写入 ${r.size} 字节 @ ${r.offset_hex}`;
                el.style.color = C.success;
            } else {
                el.textContent = '✗ ' + (r?r.message:'失败');
                el.style.color = C.danger;
            }
        } catch(e) {
            document.getElementById('scriptsoEditResult').textContent = '✗ '+e;
            document.getElementById('scriptsoEditResult').style.color = C.danger;
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
                el.style.color = C.success;
            } else {
                el.textContent = '✗ ' + (r?r.message:'失败');
                el.style.color = C.danger;
            }
        } catch(e) {
            document.getElementById('scriptsoStrResult').textContent = '✗ '+e;
            document.getElementById('scriptsoStrResult').style.color = C.danger;
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
                            html += `<option value="${v.offset}">${v.offset} (Δ${v.delta}) 当前值=${valDisplay} — "${escHtml(c.string_text)}"</option>`;
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
                modal.className = 'modal-overlay modal-overlay-top';
                modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };
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
        const offset = toInt(offsetStr, 16);
        if (isNaN(offset)) { showToast('无效的偏移', 'warning'); return; }
        const r = this._lastSearchResult;
        if (!r) { showToast('搜索结果已过期', 'info'); return; }
        const vt = r.value_type || 'int32';
        let newValue = vt === 'float' ? parseFloat(newValStr) : toInt(newValStr);
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
                    <td style="padding:6px;color:${s.type_name==='PROGBITS'?C.accent:s.type_name==='SYMTAB'?C.codeHighlight:C.muted};">${s.type_name}</td>
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
                    ${globals.filter(s=>s.type==='OBJECT').slice(0,100).map(s => `<div style="padding:2px 0;border-bottom:1px solid var(--border);"><span style="color:${C.codeHighlight};">${s.name}</span> <span style="color:var(--text-muted);float:right;">${s.value_hex}</span></div>`).join('')}
                </div>
            </div>
        </div>`;
    },

    async loadDisasm() {
        const offset = document.getElementById('scriptsoDisasmOffset').value.trim();
        const length = toInt(document.getElementById('scriptsoDisasmLength').value) || 512;
        const res = await pyApi('scriptsoDisassemble', offset ? toInt(offset) : null, length);
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
                    <td style="padding:2px 6px;color:${C.codeHighlight};font-weight:600;">${i.mnemonic}</td>
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
                    <td style="padding:4px;${f.name?`color:${C.codeHighlight};font-weight:600;`:'color:var(--text-muted);'}">${f.name||'(未命名)'}</td>
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
            函数: <b style="color:${C.codeHighlight};">${res.function_name||'未命名'}</b> | 地址: <b>${res.function_address_hex}</b> | 指令: <b>${res.instruction_count}</b>
            ${res.branch_targets.length ? ` | 分支目标: <b>${res.branch_targets.length}</b>` : ''}
        </div>
        <table style="width:100%;font-size:12px;font-family:monospace;border-collapse:collapse;">
            <tbody>${res.instructions.map(i => `
                <tr style="border-bottom:1px solid var(--border);${i.mnemonic==='call'?'background:rgba(100,180,255,0.1)':i.mnemonic.startsWith('j')||i.mnemonic==='ret'?'background:rgba(255,200,0,0.05)':''}">
                    <td style="padding:2px 6px;color:var(--accent);white-space:nowrap;">${i.address_hex}</td>
                    <td style="padding:2px 6px;color:var(--text-muted);font-size:10px;white-space:nowrap;">${i.bytes}</td>
                    <td style="padding:2px 6px;color:${C.codeHighlight};font-weight:600;">${i.mnemonic}</td>
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
                    <td style="padding:4px;color:${r.type==='call'?C.codeHighlight:C.accent};">${r.type}</td>
                    <td style="padding:4px;color:var(--text-muted);">${r.section}</td>
                    <td style="padding:4px;">${r.instruction}</td>
                </tr>`).join('')}</tbody></table>`}`;
    },

    async instructionPatch() {
        const addr = toInt(document.getElementById('scriptsoPatchAddr').value.trim());
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
            container.innerHTML = `<div style="padding:20px;text-align:center;color:${C.muted};">暂无MOD工程，请创建新工程</div>`;
            return;
        }
        modList.forEach(async m => {
            const isActive = this.activeMod === m.name;
            const card = document.createElement('div');
            card.className = 'mod-card' + (isActive ? ' active' : '');
            const info = m.info || {};
            const fileCount = m.files || 0;
            const deps = info.dependencies || [];
            const depCount = deps.length;
            const depBadge = depCount > 0
                ? `<span class="dep-badge" title="${depCount}个依赖" onclick="event.stopPropagation();mods.showDependencyEditor('${m.name}')" style="cursor:pointer;font-size:10px;padding:1px 6px;border-radius:4px;background:var(--accent);color:var(--bg);margin-left:6px;">🔗${depCount}</span>`
                : '';
            card.innerHTML = `
                <div class="mod-card-info">
                    <div class="mod-card-name">
                        ${m.name}${depBadge}
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
                    <button onclick="mods.showDependencyEditor('${m.name}')" class="btn" title="管理MOD依赖">依赖</button>
                    <button onclick="mods.pack('${m.name}')" class="btn btn-success">打包</button>
                    <button onclick="mods.snapshot('${m.name}')" class="btn">快照</button>
                    <button onclick="mods.confirmDelete('${m.name}')" class="btn btn-danger">删除</button>
                </div>
            `;
            container.appendChild(card);

            // 异步加载依赖状态
            if (depCount > 0) {
                this._loadDepStatus(m.name).then(depStatus => {
                    if (depStatus && !depStatus.allOk) {
                        const badge = card.querySelector('.dep-badge');
                        if (badge) {
                            badge.style.background = 'var(--warn)';
                            badge.style.color = 'var(--bg)';
                            badge.title = `${depStatus.satisfied}/${depStatus.total} 依赖已满足`;
                        }
                    }
                });
            }
        });
        this._autoBackupRefresh();
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
        // 兼容性检查
        try {
            const compat = await pyApi('checkModCompatibility', name);
            if (compat && compat.success && !compat.compatible) {
                let msg = '兼容性警告:\n';
                if (compat.issues) compat.issues.forEach(i => msg += '⚠ ' + i + '\n');
                if (compat.warnings) compat.warnings.forEach(w => msg += '⚡ ' + w + '\n');
                if (!confirm(msg + '\n仍要继续安装？')) return;
            } else if (compat && compat.success && compat.warnings && compat.warnings.length > 0) {
                let msg = '兼容性提示:\n';
                compat.warnings.forEach(w => msg += '⚡ ' + w + '\n');
                if (!confirm(msg + '\n确认安装？')) return;
            }
        } catch(e) { console.warn('兼容性检查失败:', e); }
        // 先预览
        try {
            const preview = await pyApi('previewModInstall', name);
            if (preview && preview.success && preview.total_files > 0) {
                let msg = `MOD「${name}」安装预览:\n\n`;
                if (preview.will_overwrite && preview.will_overwrite.length > 0) {
                    msg += `📝 将覆盖 ${preview.will_overwrite.length} 个文件:\n`;
                    msg += preview.will_overwrite.slice(0, 10).map(f => '  • ' + f.file).join('\n');
                    if (preview.will_overwrite.length > 10) msg += '\n  ... 等共' + preview.will_overwrite.length + '个';
                    msg += '\n\n';
                }
                if (preview.will_create && preview.will_create.length > 0) {
                    msg += `✨ 将新增 ${preview.will_create.length} 个文件:\n`;
                    msg += preview.will_create.slice(0, 10).map(f => '  • ' + f.file).join('\n');
                    if (preview.will_create.length > 10) msg += '\n  ... 等共' + preview.will_create.length + '个';
                }
                if (!confirm(msg + '\n\n确认安装？')) return;
            }
        } catch(e) { console.warn('安装预览失败:', e); }
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
        el.style.color = C.muted;
        try {
            const r = await pyApi('uninstallMod', name);
            if (r.success) {
                el.textContent = r.message;
                el.style.color = C.success;
                this.refreshList();
            } else {
                el.textContent = r.message;
                el.style.color = C.danger;
            }
        } catch(e) {
            el.textContent = '' + e;
            el.style.color = C.danger;
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
        } catch(e) { console.warn('MOD信息获取失败:', e); }
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

    async autoBackupConfig(enabled) {
        try {
            const r = await pyApi('autoBackupConfig', enabled, undefined);
            if (r && r.success) showToast(r.message, 'success');
            this._autoBackupRefresh();
        } catch(e) { showToast('配置失败: ' + e, 'error'); }
    },

    async autoBackupStatus() {
        try {
            const r = await pyApi('autoBackupStatus');
            if (r && r.success) {
                const el = document.getElementById('autoBackupStatus');
                if (el) {
                    const cfg = r.config;
                    el.innerHTML = (cfg.enabled
                        ? '<span style="color:var(--success);">● 自动备份已启用</span> (每' + cfg.interval_minutes + '分钟)'
                        : '<span style="color:var(--text-muted);">○ 自动备份已禁用</span>') +
                        ' | 备份数: ' + r.backup_count +
                        (r.last_backup ? ' | 最近: ' + r.last_backup : '');
                }
            }
        } catch(e) { console.warn('自动备份状态检查失败:', e); }
    },

    _autoBackupTimer: null,
    _autoBackupRefresh() {
        this.autoBackupStatus();
        // 启动定时器
        if (this._autoBackupTimer) clearInterval(this._autoBackupTimer);
        this._autoBackupTimer = setInterval(async () => {
            try {
                const r = await pyApi('autoBackupStatus');
                if (r && r.success && r.config && r.config.enabled) {
                    // 检查是否需要执行备份
                    const now = Date.now();
                    if (r.last_backup) {
                        const lastTime = new Date(
                            toInt(r.last_backup.substring(0,4)),
                            toInt(r.last_backup.substring(4,6)) - 1,
                            toInt(r.last_backup.substring(6,8)),
                            toInt(r.last_backup.substring(9,11)),
                            toInt(r.last_backup.substring(11,13)),
                            toInt(r.last_backup.substring(13,15))
                        ).getTime();
                        const intervalMs = r.config.interval_minutes * 60 * 1000;
                        if (now - lastTime >= intervalMs) {
                            await pyApi('backupAll');
                            this.autoBackupStatus();
                        }
                    }
                }
            } catch(e) { console.warn('自动备份计时器失败:', e); }
        }, 60000); // 每分钟检查一次
    },

    // ==================== MOD 依赖管理 ====================

    async showDependencyEditor(modName) {
        const modal = document.getElementById('depModal');
        document.getElementById('depModName').textContent = modName;
        document.getElementById('depModNameData').value = modName;
        modal.style.display = 'flex';

        // 加载当前依赖
        const res = await pyApi('getModDependencies', modName);
        const deps = (res && res.dependencies) ? res.dependencies : [];
        const available = (res && res.available_mods) ? res.available_mods.filter(m => m !== modName) : [];

        document.getElementById('depAvailableCount').textContent = available.length;
        document.getElementById('depTotalCount').textContent = '(' + deps.length + '个依赖)';

        const list = document.getElementById('depList');
        list.innerHTML = '';
        if (deps.length === 0) {
            list.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:16px;">暂无依赖声明</div>';
        } else {
            deps.forEach(dep => {
                const depName = dep.name || dep;
                const depVer = dep.version || '*';
                const satisfied = dep.satisfied;
                const row = document.createElement('div');
                row.className = 'dep-item';
                row.innerHTML = `
                    <span style="flex:1;font-weight:600;">${escHtml(depName)}</span>
                    <span style="color:var(--text-muted);font-size:12px;margin:0 8px;">v${escHtml(depVer)}</span>
                    <span style="font-size:11px;color:${satisfied ? C.success : C.danger};margin-right:12px;">${satisfied ? '✓ 满足' : '✗ 缺失'}</span>
                    <button onclick="mods._removeDep('${escHtml(depName)}')" class="btn btn-sm" style="font-size:11px;padding:2px 6px;">移除</button>
                `;
                list.appendChild(row);
            });
        }

        // 填充可用MOD下拉
        const sel = document.getElementById('depAddSelect');
        sel.innerHTML = '<option value="">-- 选择MOD --</option>' +
            available.map(m => `<option value="${escHtml(m)}">${escHtml(m)}</option>`).join('');

        this._depCurrentMod = modName;
    },

    hideDependencyEditor() {
        document.getElementById('depModal').style.display = 'none';
    },

    async addDependency() {
        const sel = document.getElementById('depAddSelect');
        const ver = document.getElementById('depAddVersion').value.trim() || '*';
        const depName = sel.value;
        if (!depName) { showToast('请选择依赖MOD', 'info'); return; }

        const res = await pyApi('getModDependencies', this._depCurrentMod);
        let deps = (res && res.dependencies) ? res.dependencies.map(d => (typeof d === 'string' ? {name: d, version: '*'} : d)) : [];
        if (deps.find(d => d.name === depName)) {
            showToast('该依赖已存在', 'info');
            return;
        }
        deps.push({ name: depName, version: ver, required: true });
        await pyApi('setModDependencies', this._depCurrentMod, deps);
        showToast('依赖已添加', 'success');
        this.showDependencyEditor(this._depCurrentMod);
    },

    async _removeDep(depName) {
        const res = await pyApi('getModDependencies', this._depCurrentMod);
        let deps = (res && res.dependencies) ? res.dependencies.map(d => (typeof d === 'string' ? {name: d, version: '*'} : d)) : [];
        deps = deps.filter(d => d.name !== depName);
        await pyApi('setModDependencies', this._depCurrentMod, deps);
        showToast('依赖已移除', 'success');
        this.showDependencyEditor(this._depCurrentMod);
    },

    async checkDependencies(modName) {
        const res = await pyApi('checkModDependencies', modName || this.activeMod);
        if (!res || !res.success) {
            showToast(res ? res.message : '检查失败', 'error');
            return;
        }
        if (res.ok) {
            showToast('所有依赖已满足 ✓', 'success');
        } else {
            let msg = '依赖检查发现问题:\n';
            if (res.missing) res.missing.forEach(m => msg += '✗ ' + m + '\n');
            if (res.warnings) res.warnings.forEach(w => msg += '⚠ ' + w + '\n');
            alert(msg);
        }
        return res;
    },

    async _loadDepStatus(modName) {
        try {
            const res = await pyApi('getModDependencies', modName);
            if (res && res.success && res.dependencies && res.dependencies.length > 0) {
                const satisfied = res.satisfied || 0;
                const total = res.total || res.dependencies.length;
                const allOk = res.all_satisfied;
                return { total, satisfied, allOk, deps: res.dependencies };
            }
        } catch(e) { console.warn('依赖检查失败:', e); }
        return null;
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
        selA.innerHTML = selB.innerHTML = mods.map(m => `<option value="${escHtml(m.name)}">${escHtml(m.name)} (v${escHtml(m.version || '1.0')})</option>`).join('');
    },

    async doMerge() {
        const modA = document.getElementById('mergeModA').value;
        const modB = document.getElementById('mergeModB').value;
        const output = document.getElementById('mergeOutputName').value.trim() || null;
        if (!modA || !modB) { showToast('请选择两个MOD', 'warning'); return; }
        if (modA === modB) { showToast('不能合并同一个MOD', 'warning'); return; }

        // 合并前检测冲突
        try {
            const conflictRes = await pyApi('modConflictDetect', modA, modB);
            if (conflictRes && conflictRes.success && conflictRes.has_conflicts) {
                let conflictMsg = `检测到 ${conflictRes.conflict_count} 个文件冲突:\n`;
                conflictRes.conflicts.slice(0, 10).forEach(c => conflictMsg += '• ' + c + '\n');
                if (conflictRes.conflicts.length > 10) conflictMsg += `... 还有 ${conflictRes.conflicts.length - 10} 个\n`;
                conflictMsg += '\n合并时冲突文件将按来源重命名保留。\n\n确认继续合并？';
                if (!confirm(conflictMsg)) return;
            }
        } catch(e) { console.warn('冲突检测失败:', e); }

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

