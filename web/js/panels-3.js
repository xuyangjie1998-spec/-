/**
 * San7ModMaker - panels-3
 * 从 app.js 拆分而来，保持原始顺序和功能不变
 */

const pckEditor = {
    async detect() {
        const el = document.getElementById('pckStateInfo');
        const fl = document.getElementById('pckFileList');
        const sd = document.getElementById('pckSettingDetail');
        el.innerHTML = '<p class="loading">检测中...</p>';
        try {
            let state = await pyApi('pckDetect');
            state = state || {};
            el.innerHTML = `<div class="info-row"><span class="info-label">状态:</span><span class="info-value ${state.state==='ready'?'text-success':'text-warning'}">${escHtml(state.state||'未知')}</span></div>
                <div class="info-row"><span class="info-label">Setting文件夹:</span><span class="info-value">${state.has_setting?'存在':'不存在'}</span></div>
                <div class="info-row"><span class="info-label">INI文件数:</span><span class="info-value">${state.ini_count||0}</span></div>
                <div class="info-row"><span class="info-label">建议:</span><span class="info-value">${(state.recommendations||[]).map(r => escHtml(r)).join('<br>')}</span></div>`;
            if (state.pck_files && state.pck_files.length) {
                fl.innerHTML = state.pck_files.map(f=>`<div class="list-item"><span><b>${escHtml(f.name)}</b> (${f.size_mb}MB)</span><span class="tag">${escHtml(f.type)}</span></div>`).join('');
            } else { fl.innerHTML = '<p class="hint">未检测到PCK文件</p>'; }
            let status = await pyApi('pckGetSettingStatus');
            status = status || {};
            if (status.exists) {
                sd.innerHTML = `<div class="info-row"><span class="info-label">路径:</span><span class="info-value">${escHtml(status.path||'')}</span></div>
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
                if (list) list.innerHTML = '<p class="hint">加载失败: ' + escHtml(r ? r.message : '') + '</p>';
            }
        } catch(e) {
            const list = document.getElementById('pckBrowseList');
            if (list) list.innerHTML = '<p class="hint">浏览失败: ' + escHtml(String(e)) + '</p>';
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
            window['_pg_' + this._prefix] = (p) => { this._currentPage = p; this.renderList(); };
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
                hide(detailEl);
                return;
            }
            hide(emptyEl);
            show(detailEl);
            this._fields.forEach(k => {
                const el = document.getElementById(this._prefix + '_' + k);
                if (el) {
                    if (el.tagName === 'SELECT') el.value = String(this.current[k] != null ? this.current[k] : '');
                    else if (el.tagName === 'TEXTAREA') el.value = this.current[k] || '';
                    else el.value = this.current[k] != null ? this.current[k] : '';
                    // 自动脏标记 — 任何字段变更自动标记 changed=true
                    if (!el._autoDirtyBound) {
                        el._autoDirtyBound = true;
                        const field = k;
                        el.addEventListener('change', () => {
                            let val;
                            if (el.tagName === 'SELECT') val = el.value;
                            else if (el.tagName === 'TEXTAREA') val = el.value;
                            else val = el.value;
                            this._set(field, val);
                        });
                        el.addEventListener('input', () => {
                            this.changed = true;
                        });
                    }
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
                hint.className = 'hint-text-danger';
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
            hide(detailEl);
        },

        cloneCurrent() {
            if (!this.current) return;
            const clone = Object.assign({}, this.current);
            const usedIds = new Set(this.data.map(t => toInt(t.No)));
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
                hide(emptyEl);
                show(detailEl);
                this.renderDetail();
            } else {
                if (emptyEl) emptyEl.style.display = 'flex';
                hide(detailEl);
            }
        },

        pushUndo() {
            UndoManager.pushState(this._apiName.toLowerCase(), this.snapshot());
        },

        _selectByNo(no) {
            const idx = this.data.findIndex(t => toInt(t.No) === toInt(no));
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
            const x = toInt(p.X), y = toInt(p.Y);
            if (x < minX) minX = x;
            if (y < minY) minY = y;
            if (x > maxX) maxX = x;
            if (y > maxY) maxY = y;
        }
        // 路障区域
        for (const rp of this._roadblockPos) {
            const x1 = toInt(rp.X1), y1 = toInt(rp.Y1);
            const x2 = toInt(rp.X2), y2 = toInt(rp.Y2);
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
            const x = toInt(found.data.X);
            const y = toInt(found.data.Y);
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
                const x1 = toInt(rp.X1), y1 = toInt(rp.Y1);
                const x2 = toInt(rp.X2), y2 = toInt(rp.Y2);
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
                const bx = toInt(b.X), by = toInt(b.Y);
                const bw = toInt(b.Width) || 3, bh = toInt(b.Height) || 1;
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
                const bx = toInt(b.X), by = toInt(b.Y);
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
                const cx = toInt(c.X), cy = toInt(c.Y);
                const [sx, sy] = toScreen(cx, cy);
                const r = Math.max(4, 5 * zoom);
                const isHover = this._hovered && this._hovered.type === 'city' && this._hovered.data === c;
                ctx.beginPath();
                ctx.arc(sx, sy, r, 0, Math.PI * 2);
                ctx.fillStyle = isHover ? C.gold : 'rgba(255,200,50,0.8)';
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
                const rx = toInt(rb.X), ry = toInt(rb.Y);
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
                const [sx, sy] = toScreen(toInt(c.X), toInt(c.Y));
                if (Math.hypot(x - sx, y - sy) < hitRadius) return { type: 'city', data: c };
            }
        }
        if (document.getElementById('mv_showBuildings').checked) {
            for (const b of this._buildings) {
                const [sx, sy] = toScreen(toInt(b.X), toInt(b.Y));
                if (Math.hypot(x - sx, y - sy) < hitRadius) return { type: 'building', data: b };
            }
        }
        if (document.getElementById('mv_showBridges').checked) {
            for (const b of this._bridges) {
                const bx = toInt(b.X), by = toInt(b.Y);
                const bw = toInt(b.Width) || 3, bh = toInt(b.Height) || 1;
                const [sx, sy] = toScreen(bx, by);
                const [ex, ey] = toScreen(bx + bw, by + bh);
                if (x >= sx - 3 && x <= ex + 3 && y >= sy - 3 && y <= ey + 3) return { type: 'bridge', data: b };
            }
        }
        if (document.getElementById('mv_showRoadblock').checked) {
            for (const rb of this._roadblocks) {
                const [sx, sy] = toScreen(toInt(rb.X), toInt(rb.Y));
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
        const tooltip = document.getElementById('mv_tooltip');
        const wrapper = document.getElementById('mv_canvasWrapper');

        canvas.onmousemove = (e) => {
            if (this._dragging) {
                const dx = e.clientX - this._dragStartX;
                const dy = e.clientY - this._dragStartY;
                this._panX = this._dragStartPanX + dx;
                this._panY = this._dragStartPanY + dy;
                this._hovered = null;
                this.render();
                return;
            }
            const rect = canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left, my = e.clientY - rect.top;
            const hit = this._findHit(mx, my);
            if (hit !== this._hovered) {
                this._hovered = hit;
                this.render();
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
                const [wx, wy] = this._screenToWorld(mx, my);
                this._updateInfo();
                document.getElementById('mapVisInfo').innerHTML =
                    `坐标: (${wx}, ${wy}) — 已加载: ${this._cities.length} 城池 / ${this._buildings.length} 建筑 / ${this._bridges.length} 桥梁 / ${this._roadblocks.length} 路障`;
                canvas.style.cursor = 'crosshair';
            }
        };

        canvas.onmousedown = (e) => {
            if (e.button === 2) {
                e.preventDefault();
                this._dragging = true;
                this._dragStartX = e.clientX;
                this._dragStartY = e.clientY;
                this._dragStartPanX = this._panX;
                this._dragStartPanY = this._panY;
                canvas.style.cursor = 'grabbing';
                return;
            }
        };

        canvas.onmouseup = (e) => {
            if (this._dragging) {
                this._dragging = false;
                canvas.style.cursor = 'crosshair';
                return;
            }
            if (e.button === 0) {
                const rect = canvas.getBoundingClientRect();
                const mx = e.clientX - rect.left, my = e.clientY - rect.top;
                const hit = this._findHit(mx, my);
                if (hit) {
                    const d = hit.data;
                    const tabMap = { city: 'citypos', building: 'buildingpos', bridge: 'sfbridge', roadblock: 'sfroadblock' };
                    const editorMap = { city: 'cityposEditor', building: 'buildingposEditor', bridge: 'sfbridgeEditor', roadblock: 'sfroadblockEditor' };
                    const tab = tabMap[hit.type];
                    const editorName = editorMap[hit.type];
                    if (tab && window[editorName]) {
                        $$('.nav-item').removeClass('active');
                        $$('.tab-content').removeClass('active');
                        const navItem = document.querySelector(`[data-tab="${tab}"]`);
                        if (navItem) navItem.classList.add('active');
                        const tc = document.getElementById(tab);
                        if (tc) tc.classList.add('active');
                        const editor = window[editorName];
                        if (editor.load) {
                            editor.load().then(() => {
                                if (editor._selectByNo) editor._selectByNo(toInt(d.No));
                            });
                        }
                    }
                } else {
                    const [wx, wy] = this._screenToWorld(mx, my);
                    document.getElementById('mapVisInfo').innerHTML =
                        `<b style="color:${C.gold};">点击坐标: (${wx}, ${wy})</b> — 已加载: ${this._cities.length} 城池 / ${this._buildings.length} 建筑 / ${this._bridges.length} 桥梁 / ${this._roadblocks.length} 路障`;
                    navigator.clipboard.writeText(`${wx}, ${wy}`).catch(() => {});
                }
            }
        };

        canvas.onmouseleave = () => {
            if (this._dragging) {
                this._dragging = false;
                canvas.style.cursor = 'crosshair';
            }
            this._hovered = null;
            tooltip.style.display = 'none';
            this.render();
            this._updateInfo();
        };

        // 滚轮缩放
        canvas.onwheel = (e) => {
            e.preventDefault();
            const zoomSlider = document.getElementById('mv_zoom');
            let zoom = parseFloat(zoomSlider.value) || 1;
            const delta = e.deltaY > 0 ? -0.1 : 0.1;
            zoom = Math.max(0.5, Math.min(3, zoom + delta));
            zoomSlider.value = zoom;
            document.getElementById('mv_zoomLabel').textContent = zoom.toFixed(1) + 'x';
            this.render();
        };

        // 全局右键菜单禁用
        canvas.oncontextmenu = (e) => { e.preventDefault(); };

        // 全局 mouseup 处理拖拽释放
        document.addEventListener('mouseup', (e) => {
            if (this._dragging) {
                this._dragging = false;
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
            this._ref = await pyApi('getDataFile', 'variable_ref.json');
            if (!this._ref || Object.keys(this._ref).length === 0) {
                this._ref = { categories: {} };
            }
            return this._ref;
        } catch(e) {
            console.error('Variable ref not loaded:', e);
            this._ref = { categories: {} };
            return this._ref;
        }
    },

    async _loadFullRef() {
        if (this._fullRef) return this._fullRef;
        try {
            this._fullRef = await pyApi('getDataFile', 'variable_full_ref.json');
            if (!this._fullRef || Object.keys(this._fullRef).length === 0) {
                this._fullRef = { params: {} };
            }
            return this._fullRef;
        } catch(e) {
            console.error('Variable full ref not loaded:', e);
            this._fullRef = { params: {} };
            return this._fullRef;
        }
    },

    filter(cat) {
        this._currentCat = cat;
        $$('#varCatTabs .let-cat-tab').toggleClass('active', false);
        $$('#varCatTabs .let-cat-tab').forEach(b => {
            if (b.textContent === (cat === 'all' ? '全部' : b.textContent)) b.classList.add('active');
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
        document.querySelectorAll('#varCatTabs .let-cat-tab').forEach(b => {
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
            const catLabel = catInfo ? `<span class="let-cat-label">${catInfo.cat}</span>` : '';
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
            document.querySelectorAll('.let-field-hint').forEach(el => el.textContent = '');
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
            let hintEl = el.parentElement.querySelector('.let-full-hint');
            if (!hintEl) {
                hintEl = document.createElement('div');
                hintEl.className = 'let-full-hint hint-text-accent';
                el.parentElement.appendChild(hintEl);
            }
            if (comment) {
                hintEl.textContent = comment;
                hintEl.style.display = 'block';
                // Also highlight the input with a subtle border
                el.style.borderColor = C.accent;
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
        document.querySelectorAll('.let-field-hint').forEach(el => el.textContent = '');
        if (!catInfo || !catInfo.fields) return;

        const prefix = 'ge_';
        for (const [fieldName, hint] of Object.entries(catInfo.fields)) {
            const el = document.getElementById(prefix + fieldName);
            if (!el) continue;
            // Find or create hint element after the input
            let hintEl = el.parentElement.querySelector('.let-field-hint');
            if (!hintEl) {
                hintEl = document.createElement('div');
                hintEl.className = 'let-field-hint';
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
            const data = await pyApi('getDataFile', `xlsx_${name}.json`);
            if (!data || Object.keys(data).length === 0) throw new Error('Empty data');
            this._cache[name] = data;
            return data;
        } catch(e) {
            console.error(`ReferenceData: ${name} not loaded:`, e.message);
            this._cache[name] = null;
            return null;
        }
    },

    async _loadChangfeng() {
        if (this._cache['_changfeng']) return this._cache['_changfeng'];
        try {
            const data = await pyApi('getDataFile', 'changfeng_xls_ref.json');
            if (!data || Object.keys(data).length === 0) throw new Error('Empty data');
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
                resultsDiv.innerHTML = `<div style="padding:20px;color:var(--text-muted);">${escHtml(res ? res.message || '搜索失败' : '搜索失败')}</div>`;
                return;
            }
            if (!res.results || res.results.length === 0) {
                resultsDiv.innerHTML = `<div style="padding:20px;color:var(--text-muted);">未找到匹配 "${escHtml(query)}" 的结果</div>`;
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
            resultsDiv.innerHTML = `<div style="padding:20px;color:var(--danger);">搜索出错: ${escHtml(String(e))}</div>`;
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
                resultsDiv.innerHTML = `<div style="padding:20px;color:var(--text-muted);">${escHtml(res ? res.message || '分析失败' : '分析失败')}</div>`;
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
            resultsDiv.innerHTML = `<div style="padding:20px;color:var(--danger);">分析出错: ${escHtml(String(e))}</div>`;
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
        hide(detail);
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
                const r = toInt(item.R), g = toInt(item.G), b = toInt(item.B);
                const a = (toInt(item.Alpha) || 255) / 255;
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
                const c = toInt(v);
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
            this._data[idx][key] = (key === 'R' || key === 'G' || key === 'B' || key === 'Alpha') ? toInt(val) : val;
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
    },

    saveCurrent() {
        if (this._selectedIdx < 0) return;
        this.changed = true;
        updateSaveBtnState('uisubs_saveBtn', true);
        showToast('当前条目已修改，请点击"保存"提交', 'info');
    },

    deleteCurrent() {
        if (this._selectedIdx < 0) { showToast('请先选择一个条目', 'warning'); return; }
        const item = this._data[this._selectedIdx];
        if (!confirm(`确认删除 "${item.Name || item.name || '#' + this._selectedIdx}"?`)) return;
        this._data.splice(this._selectedIdx, 1);
        this._selectedIdx = -1;
        this.changed = true;
        updateSaveBtnState('uisubs_saveBtn', true);
        this._render();
        this._hideDetail();
        document.getElementById('uisubsSummary').textContent = '共 ' + this._data.length + ' 条';
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
    },

    saveCurrent() {
        if (this._selectedIdx < 0) return;
        this.changed = true;
        showToast('当前条目已修改，请点击"保存"提交', 'info');
    },

    deleteCurrent() {
        if (this._selectedIdx < 0) { showToast('请先选择一个条目', 'warning'); return; }
        const item = this._data[this._selectedIdx];
        if (!confirm(`确认删除 "${item.Name || '#' + this._selectedIdx}"?`)) return;
        this._data.splice(this._selectedIdx, 1);
        this._selectedIdx = -1;
        this.changed = true;
        this._render();
        document.getElementById('configext_detail').style.display = 'none';
        document.getElementById('configext_empty').style.display = 'flex';
    }
};

// ============================================================
// BMP→RAW 转换器（增强版）
// ============================================================
const bmp2rawTool = {
    changed: false,

    async convert() {
        const path = document.getElementById('bmp2rawPath').value.trim();
        if (!path) { showToast('请输入BMP文件路径', 'error'); return; }
        try {
            const r = await pyApi('bmp2raw', path);
            const el = document.getElementById('bmp2rawResult');
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
    },

    async reverse() {
        const path = document.getElementById('bmp2rawPath').value.trim();
        if (!path) { showToast('请输入RAW文件路径', 'error'); return; }
        try {
            const r = await pyApi('raw2bmp', path);
            const el = document.getElementById('bmp2rawResult');
            if (r.success) {
                el.innerHTML = '<span style="color:var(--success);">反向转换成功！</span> 输出: ' + escHtml(r.bmp_path) + ' (' + r.size + ' bytes)';
                showToast(r.message, 'success');
            } else {
                el.innerHTML = '<span style="color:var(--danger);">错误: ' + escHtml(r.message) + '</span>';
                showToast(r.message, 'error');
            }
        } catch(e) {
            showToast('反向转换失败: ' + e, 'error');
        }
    },

    async batchConvert() {
        const dirPath = prompt('请输入包含BMP文件的目录路径（将转换目录下所有382×270的BMP文件）:');
        if (!dirPath) return;
        try {
            const r = await pyApi('bmp2rawBatch', dirPath);
            const el = document.getElementById('bmp2rawResult');
            if (r.success) {
                el.innerHTML = '<span style="color:var(--success);">批量转换完成！</span> 成功: ' + r.converted + ' 个, 失败: ' + (r.failed || 0) + ' 个';
                showToast(r.message, 'success');
            } else {
                el.innerHTML = '<span style="color:var(--danger);">错误: ' + escHtml(r.message) + '</span>';
                showToast(r.message, 'error');
            }
        } catch(e) {
            showToast('批量转换失败: ' + e, 'error');
        }
    },

    async preview() {
        const path = document.getElementById('bmp2rawPath').value.trim();
        if (!path) { showToast('请输入BMP文件路径', 'error'); return; }
        const previewEl = document.getElementById('bmp2rawPreview');
        if (!previewEl) return;
        try {
            const r = await pyApi('bmpPreview', path);
            if (r.success && r.base64) {
                previewEl.innerHTML = '<img src="data:image/bmp;base64,' + r.base64 + '" style="max-width:382px;max-height:270px;border:1px solid var(--border);border-radius:4px;" alt="BMP预览" />';
            } else {
                previewEl.innerHTML = '<span style="color:var(--danger);">预览失败: ' + escHtml(r.message || '未知错误') + '</span>';
            }
        } catch(e) {
            previewEl.innerHTML = '<span style="color:var(--danger);">预览失败: ' + escHtml(String(e)) + '</span>';
        }
    }
};

// ============================================================
// SHP 像素编辑器
// ============================================================
const shpPixelEditor = {
    changed: false,
    _pixels: null,
    _width: 0,
    _height: 0,
    _palette: [],
    _currentPath: '',
    _zoom: 4,
    _tool: 'pencil',
    _color: 0,
    _undoStack: [],
    _redoStack: [],
    _isDrawing: false,

    async open(shpPath) {
        document.getElementById('shpPixelModal').style.display = 'flex';
        document.getElementById('shpPixelPath').textContent = shpPath;
        this._currentPath = shpPath;
        this._undoStack = [];
        this._redoStack = [];
        await this._load(shpPath);
    },

    close() {
        document.getElementById('shpPixelModal').style.display = 'none';
    },

    async _load(path) {
        const statusEl = document.getElementById('shpPixelStatus');
        statusEl.textContent = '加载中...';
        try {
            const r = await pyApi('shpPixelLoad', path);
            if (r && r.success) {
                this._pixels = r.pixels;
                this._width = r.width;
                this._height = r.height;
                this._palette = r.palette || [];
                this._zoom = Math.max(1, Math.min(16, Math.floor(512 / Math.max(r.width, r.height))));
                document.getElementById('shpPixelZoom').value = this._zoom;
                document.getElementById('shpPixelInfo').textContent = `${r.width}x${r.height} · ${r.total_colors}色`;
                statusEl.textContent = '已加载';
                statusEl.style.color = C.success;
                this._render();
            } else {
                statusEl.textContent = r ? r.message : '加载失败';
                statusEl.style.color = C.danger;
            }
        } catch(e) {
            statusEl.textContent = '加载失败: ' + e;
            statusEl.style.color = C.danger;
        }
    },

    async save() {
        if (!this._pixels) return;
        const statusEl = document.getElementById('shpPixelStatus');
        statusEl.textContent = '保存中...';
        try {
            const r = await pyApi('shpPixelSave', this._currentPath, this._pixels, this._width, this._height);
            if (r && r.success) {
                this.changed = false;
                statusEl.textContent = '已保存';
                statusEl.style.color = C.success;
                showToast('像素数据已保存', 'success');
            } else {
                statusEl.textContent = r ? r.message : '保存失败';
                statusEl.style.color = C.danger;
            }
        } catch(e) {
            statusEl.textContent = '保存失败: ' + e;
            statusEl.style.color = C.danger;
        }
    },

    _pushUndo() {
        this._undoStack.push([...this._pixels]);
        this._redoStack = [];
        if (this._undoStack.length > 50) this._undoStack.shift();
    },

    undo() {
        if (this._undoStack.length === 0) return;
        this._redoStack.push([...this._pixels]);
        this._pixels = this._undoStack.pop();
        this.changed = true;
        this._render();
    },

    redo() {
        if (this._redoStack.length === 0) return;
        this._undoStack.push([...this._pixels]);
        this._pixels = this._redoStack.pop();
        this.changed = true;
        this._render();
    },

    _render() {
        const canvas = document.getElementById('shpPixelCanvas');
        if (!canvas || !this._pixels) return;
        const ctx = canvas.getContext('2d');
        const z = this._zoom;
        canvas.width = this._width * z;
        canvas.height = this._height * z;
        ctx.imageSmoothingEnabled = false;

        // 绘制像素
        const imgData = ctx.createImageData(canvas.width, canvas.height);
        for (let y = 0; y < this._height; y++) {
            for (let x = 0; x < this._width; x++) {
                const idx = y * this._width + x;
                const palIdx = this._pixels[idx] || 0;
                const rgb = this._palette[palIdx] || [0, 0, 0];
                // 填充缩放后的像素块
                for (let dy = 0; dy < z; dy++) {
                    for (let dx = 0; dx < z; dx++) {
                        const pi = ((y * z + dy) * canvas.width + (x * z + dx)) * 4;
                        imgData.data[pi] = rgb[0];
                        imgData.data[pi + 1] = rgb[1];
                        imgData.data[pi + 2] = rgb[2];
                        imgData.data[pi + 3] = 255;
                    }
                }
            }
        }
        ctx.putImageData(imgData, 0, 0);

        // 绘制网格线
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.lineWidth = 0.5;
        for (let x = 0; x <= this._width; x++) {
            ctx.beginPath();
            ctx.moveTo(x * z, 0);
            ctx.lineTo(x * z, this._height * z);
            ctx.stroke();
        }
        for (let y = 0; y <= this._height; y++) {
            ctx.beginPath();
            ctx.moveTo(0, y * z);
            ctx.lineTo(this._width * z, y * z);
            ctx.stroke();
        }
    },

    _renderPalette() {
        const container = document.getElementById('shpPixelPalette');
        if (!container) return;
        container.innerHTML = '';
        this._palette.forEach((rgb, i) => {
            const swatch = document.createElement('div');
            swatch.className = 'palette-swatch' + (i === this._color ? ' selected' : '');
            swatch.style.backgroundColor = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
            swatch.title = `#${i} RGB(${rgb[0]},${rgb[1]},${rgb[2]})`;
            swatch.onclick = () => {
                this._color = i;
                this._renderPalette();
                document.getElementById('shpPixelColorInfo').textContent = `#${i} RGB(${rgb[0]},${rgb[1]},${rgb[2]})`;
            };
            container.appendChild(swatch);
        });
    },

    _getPixel(x, y) {
        if (x < 0 || y < 0 || x >= this._width || y >= this._height) return -1;
        return this._pixels[y * this._width + x];
    },

    _setPixel(x, y, color) {
        if (x < 0 || y < 0 || x >= this._width || y >= this._height) return;
        this._pixels[y * this._width + x] = color;
    },

    _canvasToPixel(clientX, clientY) {
        const canvas = document.getElementById('shpPixelCanvas');
        const rect = canvas.getBoundingClientRect();
        const cx = clientX - rect.left;
        const cy = clientY - rect.top;
        return {
            x: Math.floor(cx / this._zoom),
            y: Math.floor(cy / this._zoom),
        };
    },

    _onMouseDown(e) {
        if (e.button !== 0) return;
        this._isDrawing = true;
        this._pushUndo();
        const pos = this._canvasToPixel(e.clientX, e.clientY);
        this._applyTool(pos.x, pos.y);
    },

    _onMouseMove(e) {
        // 节流：每 30ms 最多更新一次坐标显示
        const now = Date.now();
        if (!this._isDrawing && (!this._lastMoveTime || now - this._lastMoveTime > 30)) {
            this._lastMoveTime = now;
            const pos = this._canvasToPixel(e.clientX, e.clientY);
            const colorIdx = this._getPixel(pos.x, pos.y);
            const rgb = this._palette[colorIdx] || [0, 0, 0];
            const el = document.getElementById('shpPixelCursor');
            if (el) el.textContent = `(${pos.x},${pos.y}) 索引#${colorIdx} RGB(${rgb[0]},${rgb[1]},${rgb[2]})`;
            return;
        }
        if (!this._isDrawing) return;
        const pos = this._canvasToPixel(e.clientX, e.clientY);
        this._applyTool(pos.x, pos.y);
    },

    _onMouseUp() {
        this._isDrawing = false;
    },

    _applyTool(x, y) {
        switch (this._tool) {
            case 'pencil':
                this._setPixel(x, y, this._color);
                break;
            case 'eraser':
                this._setPixel(x, y, 0);
                break;
            case 'fill':
                this._floodFill(x, y, this._color);
                break;
            case 'picker':
                const c = this._getPixel(x, y);
                if (c >= 0) {
                    this._color = c;
                    this._renderPalette();
                    const rgb = this._palette[c] || [0, 0, 0];
                    document.getElementById('shpPixelColorInfo').textContent = `#${c} RGB(${rgb[0]},${rgb[1]},${rgb[2]})`;
                }
                break;
        }
        this.changed = true;
        this._render();
    },

    _floodFill(sx, sy, fillColor) {
        const targetColor = this._getPixel(sx, sy);
        if (targetColor < 0 || targetColor === fillColor) return;
        const w = this._width, h = this._height;
        const stack = [[sx, sy]];
        const visited = new Set();
        while (stack.length > 0) {
            const [x, y] = stack.pop();
            const key = y * w + x;
            if (visited.has(key)) continue;
            if (x < 0 || y < 0 || x >= w || y >= h) continue;
            if (this._pixels[key] !== targetColor) continue;
            visited.add(key);
            this._pixels[key] = fillColor;
            stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
        }
    },

    setTool(tool) {
        this._tool = tool;
        document.querySelectorAll('.shp-tool-btn').forEach(b => b.classList.remove('active'));
        const btn = document.getElementById('shpTool_' + tool);
        if (btn) btn.classList.add('active');
    },

    setZoom(z) {
        this._zoom = Math.max(1, Math.min(16, toInt(z) || 4));
        this._render();
    },

    // 初始化
    async init() {
        // 加载调色板
        try {
            const r = await pyApi('shpGetPalette');
            if (r && r.success && r.palette) {
                this._palette = r.palette;
            }
        } catch(e) { console.warn('SHP调色板加载失败:', e); }

        // 绑定Canvas事件
        const canvas = document.getElementById('shpPixelCanvas');
        if (canvas) {
            canvas.addEventListener('mousedown', (e) => this._onMouseDown(e));
            canvas.addEventListener('mousemove', (e) => this._onMouseMove(e));
            canvas.addEventListener('mouseup', () => this._onMouseUp());
            canvas.addEventListener('mouseleave', () => this._onMouseUp());
            // 右键吸色
            canvas.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                const pos = this._canvasToPixel(e.clientX, e.clientY);
                const c = this._getPixel(pos.x, pos.y);
                if (c >= 0) {
                    this._color = c;
                    this._renderPalette();
                    this.setTool('pencil');
                    const rgb = this._palette[c] || [0, 0, 0];
                    document.getElementById('shpPixelColorInfo').textContent = `#${c} RGB(${rgb[0]},${rgb[1]},${rgb[2]})`;
                }
            });
        }
    },

    // 导出为PNG
    exportPNG() {
        const canvas = document.getElementById('shpPixelCanvas');
        if (!canvas) return;
        // 创建无网格的canvas
        const exportCanvas = document.createElement('canvas');
        exportCanvas.width = this._width;
        exportCanvas.height = this._height;
        const ctx = exportCanvas.getContext('2d');
        ctx.imageSmoothingEnabled = false;
        const imgData = ctx.createImageData(this._width, this._height);
        for (let i = 0; i < this._pixels.length; i++) {
            const rgb = this._palette[this._pixels[i]] || [0, 0, 0];
            const pi = i * 4;
            imgData.data[pi] = rgb[0];
            imgData.data[pi + 1] = rgb[1];
            imgData.data[pi + 2] = rgb[2];
            imgData.data[pi + 3] = 255;
        }
        ctx.putImageData(imgData, 0, 0);
        const link = document.createElement('a');
        link.download = 'shp_export.png';
        link.href = exportCanvas.toDataURL('image/png');
        link.click();
    },
};

// 城池连接编辑器
// CSV 工具包装器
const csvtoolsEditor = (typeof csvTools !== 'undefined') ? csvTools : { changed: false };

// 自定义君主编辑器
const customLeaderEditor = {
    changed: false,
    _data: [],
    _selectedIdx: -1,
    async load() {
        const res = await pyApi('customLeaderLoad');
        if (res && res.success) {
            // 后端返回 leaders 数组，字段为 name/str_val/int_val/hp/mp
            this._data = (res.leaders || res.data || []).map(l => ({
                name: l.name || l.Name || '',
                str_val: l.str_val || l.Str || 80,
                int_val: l.int_val || l.Int || 80,
                hp: l.hp || l.HP || 100,
                mp: l.mp || l.MP || 50,
            }));
            this._render();
            document.getElementById('customLeaderSummary').textContent = '共 ' + this._data.length + ' 个自定义君主';
        } else {
            showToast((res && res.message) || '加载失败', 'error');
        }
        return res;
    },
    async save() {
        if (!(await validateBeforeSave())) return;
        const res = await pyApi('customLeaderSave', this._data);
        if (res && res.success) { this.changed = false; updateSaveBtnState('customLeaderSaveBtn', false); }
        if (res && res.message) showToast(res.message, res.success ? 'success' : 'error');
        return res;
    },
    addNew() {
        const newItem = { name: '新君主', str_val: 80, int_val: 80, hp: 100, mp: 50 };
        this._data.push(newItem);
        this._render();
        this._select(this._data.length - 1);
        this.changed = true;
        updateSaveBtnState('customLeaderSaveBtn', true);
    },
    deleteCurrent() {
        if (this._selectedIdx < 0) { showToast('请先选择一个君主', 'warning'); return; }
        const item = this._data[this._selectedIdx];
        if (!confirm(`确认删除自定义君主 "${item.name || '未命名'}"?`)) return;
        this._data.splice(this._selectedIdx, 1);
        this._selectedIdx = -1;
        this.changed = true;
        updateSaveBtnState('customLeaderSaveBtn', true);
        this._render();
        document.getElementById('customLeaderDetail').style.display = 'none';
        document.getElementById('customLeaderSummary').textContent = '共 ' + this._data.length + ' 个自定义君主';
    },
    _render() {
        const listEl = document.getElementById('customLeaderList');
        if (!listEl) return;
        listEl.innerHTML = '';
        this._data.forEach((item, idx) => {
            const card = document.createElement('div');
            card.className = 'item-card' + ((this._selectedIdx === idx) ? ' card-selected' : '');
            const name = item.name || '未命名';
            card.innerHTML = `
                <div class="item-card-header">
                    <span class="item-name">${escHtml(name)}</span>
                    <span style="font-size:10px;color:var(--text-muted);">武${item.str_val||'-'} 智${item.int_val||'-'}</span>
                </div>`;
            card.onclick = () => this._select(idx);
            listEl.appendChild(card);
        });
    },
    _select(idx) {
        this._selectedIdx = idx;
        const item = this._data[idx];
        if (!item) return;
        document.getElementById('customLeaderDetail').style.display = 'block';
        document.getElementById('customLeaderDetailName').textContent = (item.name || '未命名') + ' - 详情';
        const fieldsEl = document.getElementById('customLeaderDetailFields');
        if (!fieldsEl) return;
        const labelMap = { name: '名称', str_val: '武力', int_val: '智力', hp: '体力', mp: '技力' };
        let html = '';
        for (const [k, v] of [['name',item.name],['str_val',item.str_val],['int_val',item.int_val],['hp',item.hp],['mp',item.mp]]) {
            html += `<div class="form-group"><label>${labelMap[k]||k}</label><input type="${k==='name'?'text':'number'}" value="${escHtml(String(v != null ? v : ''))}" onchange="customLeaderEditor._setField('${k}', this.value, ${idx})"></div>`;
        }
        fieldsEl.innerHTML = html;
        this._render();
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
        this._render();
    },
    _setField(key, val, idx) {
        if (this._data[idx]) {
            this._data[idx][key] = (key === 'name') ? val : (toInt(val));
        }
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
        } catch(e) { console.error('load generals failed:', e); }
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

    _setField(field, val) {
        if (this._selectedIdx < 0) return;
        const item = this._filtered[this._selectedIdx];
        if (field === 'id') {
            item.id = toInt(val) || item.id;
            // 更新详情面板中的武将编号
            const genNo = item.id - 27000;
            document.getElementById('surnameGenNo').value = genNo;
            const genName = (this._generalsMap && this._generalsMap[genNo]) ? this._generalsMap[genNo] : '未知武将';
            document.getElementById('surnameGenName').textContent = genName;
            document.getElementById('surnameHint').textContent = '旗帜上显示的姓氏。27000+武将编号=' + genNo + ', 对应武将: ' + genName;
        } else if (field === 'value') {
            item.value = val;
            document.getElementById('surnameDetailName').textContent = '编辑姓氏: ' + (val || '');
        }
        this.changed = true;
        updateSaveBtnState('surnameSaveBtn', true);
    },

    saveDetail() {
        if (this._selectedIdx < 0) return;
        // 先从 DOM 读取最新值确保同步
        const item = this._filtered[this._selectedIdx];
        item.id = toInt(document.getElementById('surnameId').value) || item.id;
        item.value = document.getElementById('surnameValue').value;
        const origIdx = this._data.indexOf(item);
        if (origIdx >= 0) {
            this._data[origIdx] = { ...item };
            this.changed = true;
            updateSaveBtnState('surnameSaveBtn', true);
        }
        showToast('请点击"保存"按钮提交更改', 'info');
    },

    saveCurrent() {
        if (this._selectedIdx < 0) return;
        // 从 DOM 读取最新值
        const item = this._filtered[this._selectedIdx];
        item.id = toInt(document.getElementById('surnameId').value) || item.id;
        item.value = document.getElementById('surnameValue').value;
        this.changed = true;
        updateSaveBtnState('surnameSaveBtn', true);
    },

    deleteCurrent() {
        if (this._selectedIdx < 0) { showToast('请先选择一个姓氏', 'warning'); return; }
        const item = this._filtered[this._selectedIdx];
        if (!confirm(`确认删除姓氏 "${item.value || ''}" (ID: ${item.id})?`)) return;
        const origIdx = this._data.indexOf(item);
        if (origIdx >= 0) {
            this._data.splice(origIdx, 1);
            this._filtered = [...this._data];
            this.changed = true;
            updateSaveBtnState('surnameSaveBtn', true);
        }
        this._selectedIdx = -1;
        document.getElementById('surnameDetail').style.display = 'none';
        this._render();
        document.getElementById('surnameSummary').textContent = '共 ' + this._data.length + ' 个姓氏';
    },

    closeDetail() {
        document.getElementById('surnameDetail').style.display = 'none';
        this._selectedIdx = -1;
    },

    _setField(key, val) {
        if (this._selectedIdx >= 0) {
            const item = this._filtered[this._selectedIdx];
            if (key === 'id') item.id = toInt(val);
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
    const bindSubTabs = () => {
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
                if (resultEl) { resultEl.textContent = '配置已加载'; resultEl.style.color = C.success; }
            } else {
                const resultEl = document.getElementById('sango7Result');
                if (resultEl) { resultEl.textContent = '加载失败: ' + (res ? res.message : ''); resultEl.style.color = C.danger; }
            }
        } catch(e) {
            const resultEl = document.getElementById('sango7Result');
            if (resultEl) { resultEl.textContent = '加载失败: ' + e; resultEl.style.color = C.danger; }
        }
    },
    async save() {
        if (!(await validateBeforeSave())) return;
        this.pushUndo();
        const width = toInt(document.getElementById('sg7_width').value);
        const height = toInt(document.getElementById('sg7_height').value);
        const fullscreen = toInt(document.getElementById('sg7_fullscreen').value);
        const resultEl = document.getElementById('sango7Result');
        try {
            const res = await pyApi('setSango7Config', width, height, fullscreen);
            if (res && res.success) {
                if (resultEl) { resultEl.textContent = res.message || '配置已保存'; resultEl.style.color = C.success; }
            } else {
                if (resultEl) { resultEl.textContent = '保存失败: ' + (res ? res.message : ''); resultEl.style.color = C.danger; }
            }
        } catch(e) {
            if (resultEl) { resultEl.textContent = '保存失败: ' + e; resultEl.style.color = C.danger; }
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

    saveCurrent() {
        showToast('配置已修改，请点击"保存"提交', 'info');
    }
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
        types.forEach((type) => {
            const frameCount = toInt(document.getElementById('spr' + type).value);
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
        resultEl.style.color = C.muted;
        try {
            // 创建目录结构
            await pyApi('createSHDir', obdType, number);
            let totalFrames = 0;
            let successFrames = 0;
            for (let t = 0; t < types.length; t++) {
                const type = types[t];
                const frameCount = toInt(document.getElementById('spr' + type).value);
                if (frameCount <= 0) continue;
                for (let i = 1; i <= frameCount; i++) {
                    totalFrames++;
                    const r = await pyApi('importSpriteFrame', obdType, number, type, i);
                    if (r && r.success) successFrames++;
                    resultEl.textContent = '转换中... ' + type + ' ' + i + '/' + frameCount + ' (' + successFrames + '/' + totalFrames + ')';
                }
            }
            resultEl.textContent = '完成! ' + successFrames + '/' + totalFrames + ' 帧已生成';
            resultEl.style.color = C.success;
            showToast('帧导入完成: ' + successFrames + ' 帧\n\n路径: Shape/BFObj/' + obdType + '/' + zeroPad(number,3) + '/\n\n下一步: 用上方「生成 OBD 参数模板」按钮获取参数并填入 OBD 编辑器', 'success');
        } catch(e) {
            resultEl.textContent = '失败: ' + e;
            resultEl.style.color = C.danger;
            showToast('导入失败: ' + escHtml(String(e)), 'error');
        }
    }
};

const zeroPad = (n, w) => { n = String(n); while (n.length < w) n = '0' + n; return n; }

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
            <span><b>#${escHtml(String(o.sequence))}</b> ${escHtml(o.name||'')} (ObjID:${escHtml(String(o.obj_id))})</span>
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
        <div class="form-row"><label>Sequence</label><input type="number" value="${o.sequence}" onchange="obdEditor.data[${idx}].sequence=toInt(this.value)"></div>
            <div class="form-row"><label>Name</label><input type="text" value="${escHtml(o.name||'')}" onchange="obdEditor.data[${idx}].name=this.value"></div>
            <div class="form-row"><label>Space (X,Y,Z)</label>
                <input type="number" value="${(o.space||[0,0,0])[0]}" style="width:60px" onchange="obdEditor.data[${idx}].space[0]=toInt(this.value)">
                <input type="number" value="${(o.space||[0,0,0])[1]}" style="width:60px" onchange="obdEditor.data[${idx}].space[1]=toInt(this.value)">
                <input type="number" value="${(o.space||[0,0,0])[2]}" style="width:60px" onchange="obdEditor.data[${idx}].space[2]=toInt(this.value)">
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
                    <img id="obdSpritePreviewImg" src="" alt="Sprite预览" style="max-width:200px;max-height:150px;object-fit:contain;display:none;" />
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
    saveCurrent() {
        showToast('当前模型已修改，请点击"保存"提交', 'info');
    },
    addNew() {
        this.newObj();
    },
    deleteCurrent() {
        if (this._selectedIdx >= 0) {
            this.deleteObj(this._selectedIdx);
            this._selectedIdx = -1;
        } else {
            showToast('请先从列表中选择一个模型', 'warning');
        }
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
        const seq = toInt(document.getElementById('obdCopySeq')?.value);
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
                const val = toInt(this.soldiers[i][key]) || 100;
                let cls = '';
                if (i===j) cls = 'style="background:var(--bg-card);font-weight:bold;"';
                else if (val>150) cls = `style="background:#fde8e8;color:${C.danger};"`;
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
        const val = toInt(v)||100;
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
        const count = toInt(prompt('克隆数量:', '1')) || 1;
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
            showToast('体力/技力已回满');
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
            showToast('经验已设为99级');
        } catch(e) { showToast('修改失败: '+e, 'error'); }
    },

    _editSG7Gen(idx) {
        const g = this._sg7GenData[idx];
        if (!g) return;
        const we = g.weapon_exp || {};
        const soldierOpts = (this._soldierTypes || []).map(s =>
            `<option value="${s.id}" ${s.id === g.current_soldier_type ? 'selected' : ''}>${escHtml(s.name)}</option>`
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
            modal.className = 'modal-overlay modal-overlay-top';
            modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };
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
            const val = toInt(el.value);
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
            const val = toInt(meritEl.value);
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
            const st = toInt(soldierTypeEl.value);
            const sc = toInt(soldierCountEl.value);
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
            const val = toInt(el.value);
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
            showToast('武将数据已保存');
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
                showToast('阵型已更新');
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
            const itemId = toInt(sel.value);
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
            showToast('装备已保存');
        }
    },

    async _editSkill(skillType, slot) {
        if (!this._structuredData) return;
        const index = this._structuredData.meta.index;
        const currentMask = this._structuredData.skills[skillType] || '';
        const skillId = toInt(prompt(`请输入技能ID (0=禁用, 1=启用): 当前掩码 ${currentMask.substring(0,16)}... 位${slot}`, '1'));
        if (isNaN(skillId)) return;
        try {
            const r = await pyApi('saveWriteSkills', this._selectedSave, index, skillType, slot, skillId);
            if (r && r.success) {
                showToast(`技能 ${skillType} 位${slot} 已${skillId?'启用':'禁用'}`);
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
                showToast('体力/技力已回满');
            } else if (action === 'level99') {
                await pyApi('saveEditExp', saveName, offset, 0x0098FFFF);
                this._structuredData.experience.exp = 0x0098FFFF;
                showToast('经验已设为99级');
            } else if (action === 'clearEquip') {
                for (const slot of ['weapon', 'horse', 'item']) {
                    await pyApi('saveWriteEquipment', saveName, index, slot, 0);
                }
                if (this._structuredData.equipment) {
                    this._structuredData.equipment.weapon = { id: 0, name: '无' };
                    this._structuredData.equipment.horse = { id: 0, name: '无' };
                    this._structuredData.equipment.item = { id: 0, name: '无' };
                }
                showToast('装备已清空');
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
            const val = toInt(input.value);
            if (isNaN(val)) continue;
            try {
                const r = await pyApi('saveEditStat', saveName, offset, field, val);
                if (!r || !r.success) errors.push(`${field}: ${r?r.message:'失败'}`);
            } catch(e) { errors.push(`${field}: ${e}`); }
        }

        // 保存功勋
        const meritEl = document.getElementById('s_merit');
        if (meritEl) {
            const val = toInt(meritEl.value);
            if (!isNaN(val)) {
                try {
                    await pyApi('saveEditMerit', saveName, offset, val);
                } catch(e) { errors.push('功勋: '+e); }
            }
        }

        // 保存经验
        const expEl = document.getElementById('s_exp');
        if (expEl) {
            const val = toInt(expEl.value);
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
            const st = toInt(soldierTypeEl.value);
            const sc = toInt(soldierCountEl.value);
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
            const val = toInt(el.value);
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
            showToast('全部修改已保存');
        }
    },

    async _loadHex() {
        if (!this._selectedSave) { showToast('请先选择一个存档', 'warning'); return; }
        const offset = toInt(document.getElementById('hexOffset').value);
        const length = toInt(document.getElementById('hexLength').value) || 512;
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
        if (!el) { return; }
        try {
let r = await pyApi('wizardTemplates');
            r = r || {};
            const templates = r.templates || [];
            el.innerHTML = templates.map(t=>`<div class="panel-card wizard-card" onclick="wizard.start('${escHtml(String(t.id))}')" style="cursor:pointer;">
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
        const no = toInt(document.getElementById('wg_no').value);
        const name = document.getElementById('wg_name').value.trim();
        if (!no || !name) { showToast('编号和姓名不能为空', 'info'); return; }

        const getVal = (id, def) => { const v = document.getElementById(id).value; return v ? toInt(v) : def; };
        const gs = document.getElementById('wg_genskill').value.trim();
        const genSkills = gs ? gs.split(',').map(s => toInt(s.trim())).filter(n => !isNaN(n)) : [];

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
                el.style.color = C.success;
                this._refreshFacePreview(face_id);
                showToast('创建成功!\n\n已联动写入:\n✓ General01.ini\n✓ DefSkill.ini\n✓ General02.ini\n✓ TermText.ini\n\n请前往对应编辑器确认详情。', 'success');
            } else { el.textContent = '✗ '+(r?r.message:'失败'); el.style.color=C.danger; }
        } catch(e) { document.getElementById('wizardResult').textContent='✗ '+e; document.getElementById('wizardResult').style.color=C.danger; }
    },

    async autoAssignFace() {
        try {
            const r = await pyApi('getNextFaceId');
            if (r && r.success) {
                document.getElementById('wg_face').value = r.next_id;
                showToast(r.message, 'success');
                this._refreshFacePreview(r.next_id);
            } else {
                showToast(r ? r.message : '获取失败', 'error');
            }
        } catch(e) { showToast('自动分配失败: ' + e, 'error'); }
    },

    async _refreshFacePreview(faceId) {
        const previewEl = document.getElementById('wg_face_preview');
        const imgEl = document.getElementById('wg_face_img');
        if (!previewEl || !imgEl) return;
        if (!faceId || faceId <= 0) {
            previewEl.style.display = 'none';
            return;
        }
        try {
            const r = await pyApi('getFacePreview', faceId);
            if (r && r.success && r.imgData) {
                imgEl.src = r.imgData;
                previewEl.style.display = 'block';
            } else {
                previewEl.style.display = 'none';
            }
        } catch(e) { previewEl.style.display = 'none'; }
    },

    async browseFaces() {
        document.getElementById('faceBrowserModal').style.display = 'flex';
        this._faceBrowserSelected = null;
        document.getElementById('faceBrowserStart').value = document.getElementById('wg_face').value || 1;
        await this.refreshFaceBrowser();
    },

    async refreshFaceBrowser() {
        const grid = document.getElementById('faceBrowserGrid');
        const info = document.getElementById('faceBrowserInfo');
        const start = toInt(document.getElementById('faceBrowserStart').value) || 1;
        grid.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:20px;grid-column:1/-1;">加载中...</div>';
        try {
            const r = await pyApi('faceBrowse', start, 30);
            if (r && r.success && r.faces) {
                info.textContent = '共 ' + r.total + ' 个头像 (ID ' + start + '-' + (start + 29) + ')';
                if (r.faces.length === 0) {
                    grid.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:20px;grid-column:1/-1;">该范围内无头像</div>';
                    return;
                }
                grid.innerHTML = r.faces.map(f => {
                    const sel = this._faceBrowserSelected === f.id ? 'border:3px solid var(--accent);' : '';
                    return `<div onclick="wizard._onFaceClick(${f.id})" style="cursor:pointer;text-align:center;padding:4px;border-radius:6px;${sel}" title="#${f.id}">
                        ${f.base64 ? '<img src="'+f.base64+'" alt="头像#'+f.id+'" style="width:64px;height:64px;object-fit:contain;border:1px solid var(--border);border-radius:4px;">' : '<div style="width:64px;height:64px;background:var(--bg2);border:1px solid var(--border);border-radius:4px;display:flex;align-items:center;justify-content:center;color:var(--text-muted);">无</div>'}
                        <div style="font-size:10px;color:var(--text-muted);margin-top:2px;">#${f.id}</div>
                    </div>`;
                }).join('');
            } else {
                grid.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:20px;grid-column:1/-1;">加载失败</div>';
            }
        } catch(e) {
            grid.innerHTML = '<div style="text-align:center;color:var(--danger);padding:20px;grid-column:1/-1;">加载失败: ' + escHtml(String(e)) + '</div>';
        }
    },

    _onFaceClick(id) {
        this._faceBrowserSelected = id;
        this.refreshFaceBrowser();
    },

    selectFaceFromBrowser() {
        if (!this._faceBrowserSelected) {
            showToast('请先点击选择一个头像', 'info');
            return;
        }
        document.getElementById('wg_face').value = this._faceBrowserSelected;
        this._refreshFacePreview(this._faceBrowserSelected);
        document.getElementById('faceBrowserModal').style.display = 'none';
    },

    async autoAssignIcon() {
        try {
            const r = await pyApi('getNextThingIconId');
            if (r && r.success) {
                document.getElementById('wi_icon').value = r.next_id;
                showToast(r.message, 'success');
                this.refreshIconPreview();
            } else {
                showToast(r ? r.message : '获取失败', 'error');
            }
        } catch(e) { showToast('自动分配失败: ' + e, 'error'); }
    },

    async refreshIconPreview() {
        const iconId = toInt(document.getElementById('wi_icon').value);
        const previewEl = document.getElementById('wi_icon_preview');
        const imgEl = document.getElementById('wi_icon_img');
        if (!previewEl || !imgEl) return;
        if (!iconId || iconId <= 0) {
            previewEl.style.display = 'none';
            return;
        }
        try {
            const r = await pyApi('getThingIconPreview', iconId);
            if (r && r.success && r.base64) {
                imgEl.src = r.base64;
                previewEl.style.display = 'block';
            } else {
                previewEl.style.display = 'none';
            }
        } catch(e) { previewEl.style.display = 'none'; }
    },

    async uploadItemIcon() {
        const iconId = toInt(document.getElementById('wi_icon').value);
        if (!iconId || iconId <= 0) {
            showToast('请先设置图标ID', 'info');
            return;
        }
        try {
            const fileRes = await pyApi('selectImageFile');
            if (!fileRes || !fileRes.success || !fileRes.path) {
                showToast('未选择文件', 'info');
                return;
            }
            const res = await pyApi('convertImageToThingIcon', fileRes.path, iconId);
            if (res && res.success) {
                showToast('图标上传成功!', 'success');
                this.refreshIconPreview();
            } else {
                showToast('上传失败: ' + (res ? res.message : '未知错误'), 'error');
            }
        } catch(e) { showToast('上传失败: ' + e, 'error'); }
    },

    async createSoldier() {
        if (!(await validateBeforeSave())) return;
        const no = toInt(document.getElementById('ws_no').value);
        const name = document.getElementById('ws_name').value.trim();
        if (!no || !name) { showToast('编号和名称不能为空', 'info'); return; }

        const getVal = (id, def) => { const v = document.getElementById(id).value; return v ? toInt(v) : def; };

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
                el.style.color = C.success;
                showToast('创建成功!\n\n已联动写入:\n✓ Soldier.ini\n✓ TermText.ini\n✓ OBD模型(自动创建)\n\nObjID已自动分配并回写Soldier.ini。', 'success');
            } else { el.textContent = '✗ '+(r?r.message:'失败'); el.style.color=C.danger; }
        } catch(e) { document.getElementById('wizardSoldierResult').textContent='✗ '+e; document.getElementById('wizardSoldierResult').style.color=C.danger; }
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
        const no = toInt(document.getElementById('wn_no').value);
        const name = document.getElementById('wn_name').value.trim();
        if (!no || !name) { showToast('编号和国号不能为空', 'info'); return; }

        const getVal = (id, def) => { const v = document.getElementById(id).value; return v ? toInt(v) : def; };
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
                el.style.color = C.success;
                showToast('创建成功!\n\n已联动写入:\n✓ Nation.ini\n✓ Color.ini\n✓ City.ini\n✓ City01-10.ini (10个剧本)\n✓ General01.ini (Lord字段)\n✓ TermText.ini\n\n请前往势力编辑器确认详情。', 'success');
            } else { el.textContent = '✗ '+(r?r.message:'失败'); el.style.color=C.danger; }
        } catch(e) { document.getElementById('wizardNationResult').textContent='✗ '+e; document.getElementById('wizardNationResult').style.color=C.danger; }
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
        const no = toInt(document.getElementById('wi_no').value);
        const name = document.getElementById('wi_name').value.trim();
        if (!no || !name) { showToast('编号和名称不能为空', 'info'); return; }

        const getVal = (id, def) => { const v = document.getElementById(id).value; return v ? toInt(v) : def; };
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
                el.style.color = C.success;
                showToast('创建成功!\n\n已联动写入:\n✓ Thing.ini\n✓ TermText.ini (名称+描述)\n\n提示: 记得在物品编辑器中完善其他属性，并导入图标SHP到 Shape/ThingIcon/。', 'success');
            } else { el.textContent = '✗ '+(r?r.message:'失败'); el.style.color=C.danger; }
        } catch(e) { document.getElementById('wizardItemResult').textContent='✗ '+e; document.getElementById('wizardItemResult').style.color=C.danger; }
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
            if (!r || !r.success) { el.innerHTML = '<p class="hint">' + escHtml(r ? r.message : '加载失败') + '</p>'; return; }
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
        let offset = m ? toInt(m[1], 16) : 0;
        offset = Math.max(0, offset - 1024);
        this._viewHex(name, offset);
    },

    hexNext() {
        const name = document.getElementById('saveDetailName').textContent;
        const info = document.getElementById('saveHexInfo').textContent;
        const m = info.match(/偏移: 0x([0-9A-Fa-f]+)/);
        let offset = m ? toInt(m[1], 16) : 0;
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
            let r = await pyApi('applyResolutionPreset', preset);
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
// ============================================================
// CSV 批量导入/导出
// ============================================================
const csvTools = {
    async importCSV() {
        let type = document.getElementById('csvImportType').value;
        let path = document.getElementById('csvImportPath').value.trim();
        let el = document.getElementById('csvImportResult');
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
            let r = await pyApi('csvImport', type, path);
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
        let type = document.getElementById('csvExportType').value;
        let path = document.getElementById('csvExportPath').value.trim();
        let el = document.getElementById('csvExportResult');
        if (!type) {
            el.innerHTML = '<span style="color:var(--danger);">请选择源类型</span>';
            showToast('请选择源类型', 'error');
            return;
        }
        try {
            el.innerHTML = '<span style="color:var(--text-muted);">导出中...</span>';
            let r = await pyApi('csvExport', type, path || null);
            if (r.success) {
                el.innerHTML = '<span style="color:var(--success);">导出成功！</span> ' + escHtml(r.message || '');
                showToast('CSV导出成功', 'success');
            } else {
                el.innerHTML = '<span style="color:var(--danger);">错误: ' + escHtml(r.message) + '</span>';
                showToast(r.message || '导出失败', 'error');
            }
        } catch(e) {
            el.innerHTML = '<span style="color:var(--danger);">导出异常: ' + escHtml(String(e)) + '</span>';
            showToast('导出失败: ' + escHtml(String(e)), 'error');
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
        let x = toInt(document.getElementById('bcX').value);
        let y = toInt(document.getElementById('bcY').value);
        try {
            let r = await pyApi('blockCalc', x, y);
            let el = document.getElementById('bcResult');
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
            document.getElementById('bcResult').innerHTML = '<p style="color:var(--danger);">计算失败: ' + escHtml(String(e)) + '</p>';
        }
    },
    async inverse() {
        let block = toInt(document.getElementById('bcBlock').value);
        try {
            let r = await pyApi('blockInverse', block);
            let el = document.getElementById('bcInvResult');
            if (r.success) {
                el.innerHTML = '<div><b>区块号:</b> <span style="color:var(--accent);font-size:16px;">' + r.block_no + '</span>' +
                    ' | <b>网格:</b> (' + r.grid_x + ', ' + r.grid_y + ')' +
                    ' | <b>X:</b> ' + r.x_min + '~' + r.x_max + ' | <b>Y:</b> ' + r.y_min + '~' + r.y_max + '</div>';
            } else {
                el.innerHTML = '<p style="color:var(--danger);">' + escHtml(r.message) + '</p>';
            }
        } catch(e) {
            document.getElementById('bcInvResult').innerHTML = '<p style="color:var(--danger);">计算失败: ' + escHtml(String(e)) + '</p>';
        }
    },
    async loadCities() {
        try {
            let r = await pyApi('loadMapSummary');
            let el = document.getElementById('bcCityList');
            if (r.success && r.summary) {
                let s = r.summary;
                let html = '<div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">地图: ' + s.map_size[0] + '×' + s.map_size[1] + ' px, 网格: ' + s.grid[0] + '×' + s.grid[1] + '</div>';
                html += '<table style="width:100%;font-size:11px;border-collapse:collapse;"><thead><tr style="background:var(--bg-page);">' +
                    '<th>No</th><th>X</th><th>Y</th><th>GX</th><th>GY</th><th>区块</th></tr></thead><tbody>';
                for (let i = 0; i < s.cities.length; i++) {
                    let c = s.cities[i];
                    html += '<tr><td>' + escHtml(c.no) + '</td><td>' + c.x + '</td><td>' + c.y + '</td><td>' + c.grid_x + '</td><td>' + c.grid_y + '</td><td style="color:var(--accent);">' + c.block_no + '</td></tr>';
                }
                html += '</tbody></table>';
                el.innerHTML = html;
            } else {
                el.innerHTML = '<p style="color:var(--danger);">加载失败</p>';
            }
        } catch(e) {
            document.getElementById('bcCityList').innerHTML = '<p style="color:var(--danger);">加载失败: ' + escHtml(String(e)) + '</p>';
        }
    }
};

// ============================================================
// PCK 资源预览增强
// ============================================================
const pckPreview = {
    _files: [],
    async loadPckList() {
        let pck = document.getElementById('pckPreviewSelect').value;
        if (!pck) { showToast('请选择PCK文件', 'error'); return; }
        try {
            let r = await pyApi('pckListFiles', pck);
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
        let el = document.getElementById('pckPreviewFileList');
        let filter = (document.getElementById('pckFileFilter').value || '').toLowerCase();
        let html = '';
        for (let i = 0; i < this._files.length; i++) {
            let f = this._files[i];
            let name = f.name || f;
            if (filter && name.toLowerCase().indexOf(filter) === -1) continue;
            let isShp = name.toLowerCase().endsWith('.shp');
            let size = f.size ? (f.size > 1024 ? Math.round(f.size/1024) + 'KB' : f.size + 'B') : '';
            html += '<div style="padding:3px 6px;cursor:pointer;border-bottom:1px solid var(--border);" onmouseover="this.style.background=\'var(--bg-page)\'" onmouseout="this.style.background=\'\'" onclick="pckPreview.previewFile(\'' + escHtml(name).replace(/'/g, "\\'") + '\')"><span>' + (isShp ? '🖼 ' : '📄 ') + escHtml(name) + '</span><span style="color:var(--text-muted);float:right;">' + size + '</span></div>';
        }
        el.innerHTML = html || '<p style="color:var(--text-muted);padding:8px;">无匹配文件</p>';
    },
    filterFiles() { this.renderFileList(); },
    async previewFile(name) {
        let pck = document.getElementById('pckPreviewSelect').value;
        let area = document.getElementById('pckPreviewArea');
        if (!name.toLowerCase().endsWith('.shp')) {
            area.innerHTML = '<div style="text-align:center;color:var(--text-muted);"><p>非图片文件</p><p style="font-size:11px;">' + escHtml(name) + '</p></div>';
            return;
        }
        area.innerHTML = '<div style="text-align:center;color:var(--text-muted);"><div class="spinner" style="margin:20px auto;"></div><p>加载预览...</p></div>';
        try {
            let r = await pyApi('pckPreviewShp', pck, name);
            if (r.success) {
                area.innerHTML = '<div style="text-align:center;">' +
                    '<img src="' + r.base64 + '" alt="' + escHtml(name) + '" style="max-width:100%;max-height:450px;image-rendering:pixelated;border:1px solid var(--border);">' +
                    '<p style="font-size:11px;color:var(--text-muted);margin-top:4px;">' + escHtml(name) + ' | ' + r.width + '×' + r.height + ' | ' + (r.size > 1024 ? Math.round(r.size/1024) + 'KB' : r.size + 'B') + '</p></div>';
            } else {
                area.innerHTML = '<p style="color:var(--danger);text-align:center;">' + escHtml(r.message) + '</p>';
            }
        } catch(e) {
            area.innerHTML = '<p style="color:var(--danger);text-align:center;">预览失败: ' + escHtml(String(e)) + '</p>';
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
            let r = await pyApi('loadMapSummary');
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
        let btn = document.getElementById('mapEditBtn');
        if (btn) btn.textContent = this._editMode ? '退出编辑' : '编辑模式';
        if (btn) btn.style.background = this._editMode ? C.accent : '';
        let canvas = document.getElementById('mapCanvas');
        if (canvas) canvas.style.cursor = this._editMode ? 'crosshair' : 'grab';
        this.render();
    },

    async saveChanges() {
        if (!this._changed) { showToast('没有修改', 'info'); return; }
        if (!confirm('确认保存城池位置修改? 将更新 City.ini 中的坐标数据')) return;
        try {
            let r = await pyApi('saveMapPositions', this._cities);
            if (r && r.success) {
                this._changed = false;
                showToast('保存成功: ' + r.message, 'success');
            } else {
                showToast('保存失败: ' + (r ? r.message : ''), 'error');
            }
        } catch(e) { showToast('保存失败: ' + e, 'error'); }
    },

    saveCurrent() {
        this._changed = true;
        showToast('城池位置已修改，请点击"保存"提交', 'info');
    },

    addNew() {
        if (!this._editMode) { showToast('请先开启编辑模式', 'warning'); return; }
        const maxNo = this._cities.reduce((m, c) => Math.max(m, c.no || 0), 0);
        const newCity = {
            no: maxNo + 1,
            name: '新城池',
            x: Math.round(8736 / this._scale / 2),
            y: Math.round(6192 / this._scale / 2),
        };
        this._cities.push(newCity);
        this._selectedCityIdx = this._cities.length - 1;
        this._changed = true;
        this.render();
        showToast(`已添加城池 #${newCity.no}，请拖拽调整位置`, 'success');
    },

    deleteCurrent() {
        if (!this._editMode) { showToast('请先开启编辑模式', 'warning'); return; }
        if (this._selectedCityIdx < 0 || this._selectedCityIdx >= this._cities.length) {
            showToast('请先选中一个城池', 'warning');
            return;
        }
        const city = this._cities[this._selectedCityIdx];
        if (!confirm(`确认删除城池 "${city.name || '#' + city.no}"?`)) return;
        this._cities.splice(this._selectedCityIdx, 1);
        this._selectedCityIdx = -1;
        this._changed = true;
        this.render();
        showToast('城池已删除，请点击保存提交', 'info');
    },

    _findCityAt(mx, my) {
        for (let i = this._cities.length - 1; i >= 0; i--) {
            let c = this._cities[i];
            let cx = c.x * this._scale + this._offsetX;
            let cy = c.y * this._scale + this._offsetY;
            if (Math.abs(mx - cx) < 8 && Math.abs(my - cy) < 8) return i;
        }
        return -1;
    },

    render() {
        let canvas = document.getElementById('mapCanvas');
        if (!canvas) return;
        let ctx = canvas.getContext('2d');
        let w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = '#1a2a1a';
        ctx.fillRect(0, 0, w, h);
        let gs = 32 * this._scale;
        ctx.strokeStyle = 'rgba(255,255,255,0.04)';
        ctx.lineWidth = 0.5;
        for (let gx = 0; gx < w; gx += gs) {
            ctx.beginPath(); ctx.moveTo(gx + this._offsetX % gs, 0); ctx.lineTo(gx + this._offsetX % gs, h); ctx.stroke();
        }
        for (let gy = 0; gy < h; gy += gs) {
            ctx.beginPath(); ctx.moveTo(0, gy + this._offsetY % gs); ctx.lineTo(w, gy + this._offsetY % gs); ctx.stroke();
        }
        for (let i = 0; i < this._buildings.length; i++) {
            let b = this._buildings[i];
            let bx = b.x * this._scale + this._offsetX;
            let by = b.y * this._scale + this._offsetY;
            ctx.fillStyle = 'rgba(100,100,255,0.6)';
            ctx.fillRect(bx - 2, by - 2, 4, 4);
        }
        for (let i = 0; i < this._cities.length; i++) {
            let c = this._cities[i];
            let cx = c.x * this._scale + this._offsetX;
            let cy = c.y * this._scale + this._offsetY;
            let isSelected = (i === this._selectedCityIdx);
            let radius = isSelected ? 7 : 4;
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
        let rect = e.target.getBoundingClientRect();
        let scaleX = 1092 / rect.width;
        let scaleY = 774 / rect.height;
        let mx = (e.clientX - rect.left) * scaleX;
        let my = (e.clientY - rect.top) * scaleY;
        if (this._editMode) {
            let ci = this._findCityAt(mx, my);
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
        let rect = e.target.getBoundingClientRect();
        let scaleX = 1092 / rect.width;
        let scaleY = 774 / rect.height;
        let mx = (e.clientX - rect.left) * scaleX;
        let my = (e.clientY - rect.top) * scaleY;
        let mapX = Math.round((mx - this._offsetX) / this._scale);
        let mapY = Math.round((my - this._offsetY) / this._scale);
        document.getElementById('mapMouse').textContent = (mapX >= 0 && mapY >= 0) ? '(' + mapX + ', ' + mapY + ')' : '超出范围';
        if (this._dragging) {
            if (this._editMode && this._selectedCityIdx >= 0) {
                let dx = (e.clientX - this._dragStartX) / this._scale;
                let dy = (e.clientY - this._dragStartY) / this._scale;
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
            let ci = this._findCityAt(mx, my);
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
