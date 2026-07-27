/**
 * San7ModMaker - panels-4
 * 从 app.js 拆分而来，保持原始顺序和功能不变
 */

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
                        html += '<span style="display:inline-block;width:120px;padding:2px;">' + escHtml(r.addresses[i]) + '</span>';
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

    saveCurrent() {
        showToast('当前城池商店已修改，请点击"保存"提交', 'info');
    }
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

    saveCurrent() {
        showToast('当前文本已修改，请点击"保存"提交', 'info');
    },

    addNew() {
        const name = prompt('请输入新分类名称:');
        if (!name) return;
        this.pushUndo();
        this.sections.push({ name: name, entries: {} });
        this.filtered = this.sections;
        this._render();
        document.getElementById('gameTextCount').textContent = this.sections.length + '个分类';
        showToast('已添加分类: ' + name, 'success');
    },

    deleteCurrent() {
        showToast('请点击分类旁的 ✕ 按钮删除分类，或点击条目旁的 ✕ 按钮删除条目', 'info');
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
document.addEventListener('panelsLoaded', () => {
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
    // V3.13.0: 引擎突破与MOD工具面板懒加载
    document.querySelectorAll('[data-tab="modPackager"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>modPackagerPanel.init(),100)));
    document.querySelectorAll('[data-tab="termtextAlloc"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>termtextAllocPanel.init(),100)));
    document.querySelectorAll('[data-tab="iniTemplateGen"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>iniTemplatePanel.init(),100)));
    document.querySelectorAll('[data-tab="engineBreakthrough"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>enginePanel.init(),100)));
    // ============================================================
    // 数据编辑器自动加载（V3.13.1：修复大量编辑器点开无数据的问题）
    // ============================================================
    // -- 技能/必杀/武将技/阵型/官职 --
    document.querySelectorAll('[data-tab="skills"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(skillEditor.data.length===0)skillEditor.load();},100)));
    document.querySelectorAll('[data-tab="superatk"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(superAtkEditor._data.length===0)superAtkEditor.load();},100)));
    document.querySelectorAll('[data-tab="genSkills"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(Object.keys(genSkillEditor._data).length===0)genSkillEditor.load();},100)));
    document.querySelectorAll('[data-tab="formation"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(formationEditor.data.length===0)formationEditor.load();},100)));
    document.querySelectorAll('[data-tab="title"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(titleEditor.data.length===0)titleEditor.load();},100)));
    // -- 剧本/时代/势力 --
    document.querySelectorAll('[data-tab="scenario"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(scenarioEditor.data.length===0)scenarioEditor.load();},100)));
    document.querySelectorAll('[data-tab="age"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(ageEditor._data.length===0)ageEditor.load();},100)));
    document.querySelectorAll('[data-tab="nation"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(nationEditor.data.length===0)nationEditor.load();},100)));
    // -- 城池/城池时期/武将扩展/等级 --
    document.querySelectorAll('[data-tab="city"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(cityEditor.data.length===0)cityEditor.load();},100)));
    document.querySelectorAll('[data-tab="cityPeriod"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(cityPeriodEditor.data.length===0)cityPeriodEditor.load();},100)));
    document.querySelectorAll('[data-tab="general02"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(general02Editor._data.length===0)general02Editor.load();},100)));
    document.querySelectorAll('[data-tab="genLv"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(genLvEditor._data.length===0)genLvEditor.load();},100)));
    // -- TermText/自定义武将/自设君主/姓氏 --
    document.querySelectorAll('[data-tab="termText"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(termTextEditor._data.length===0)termTextEditor.load();},100)));
    document.querySelectorAll('[data-tab="customgen"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(customgenEditor._generals.length===0)customgenEditor.load();},100)));
    document.querySelectorAll('[data-tab="customleader"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(customLeaderEditor._data.length===0)customLeaderEditor.load();},100)));
    document.querySelectorAll('[data-tab="surnameEditor"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(surnameEditor._data.length===0)surnameEditor.load();},100)));
    // -- 通用INI编辑器（BFFront/Dialogue/Color/CityPos/Terrain/SystemText/GossipText/ExtraTerrain等） --
    document.querySelectorAll('[data-tab="bffront"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(bffrontEditor.data.length===0)bffrontEditor.load();},100)));
    document.querySelectorAll('[data-tab="dialogue"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(dialogueEditor.data.length===0)dialogueEditor.load();},100)));
    document.querySelectorAll('[data-tab="color"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(colorEditor.data.length===0)colorEditor.load();},100)));
    document.querySelectorAll('[data-tab="citypos"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(cityposEditor.data.length===0)cityposEditor.load();},100)));
    document.querySelectorAll('[data-tab="terrain"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(terrainEditor.data.length===0)terrainEditor.load();},100)));
    document.querySelectorAll('[data-tab="systemtext"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(systemtextEditor.data.length===0)systemtextEditor.load();},100)));
    document.querySelectorAll('[data-tab="gossiptext"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(gossiptextEditor.data.length===0)gossiptextEditor.load();},100)));
    document.querySelectorAll('[data-tab="extraterrain"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(extraterrainEditor.data.length===0)extraterrainEditor.load();},100)));
    document.querySelectorAll('[data-tab="formatoffsetpos"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(formatoffsetposEditor.data.length===0)formatoffsetposEditor.load();},100)));
    document.querySelectorAll('[data-tab="buildingpos"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(buildingposEditor.data.length===0)buildingposEditor.load();},100)));
    document.querySelectorAll('[data-tab="sfroadblock"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(sfroadblockEditor.data.length===0)sfroadblockEditor.load();},100)));
    document.querySelectorAll('[data-tab="sfroadblockpos"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(sfroadblockposEditor.data.length===0)sfroadblockposEditor.load();},100)));
    document.querySelectorAll('[data-tab="var"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(varEditor.data.length===0)varEditor.load();},100)));
    document.querySelectorAll('[data-tab="font"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(fontEditor.data.length===0)fontEditor.load();},100)));
    document.querySelectorAll('[data-tab="systemini"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(systeminiEditor.data.length===0)systeminiEditor.load();},100)));
    document.querySelectorAll('[data-tab="format"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(formatEditor.data.length===0)formatEditor.load();},100)));
    document.querySelectorAll('[data-tab="chessformat"]').forEach(el=>el.addEventListener('click',()=>setTimeout(()=>{if(chessformatEditor.data.length===0)chessformatEditor.load();},100)));
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
    el.innerHTML = '<p class="loading">正在检测游戏版本，请稍候...</p>';
    try {
        let r = await pyApi('detectGameVersion');
        r = r || {};
        if (!r.success) { el.innerHTML = '<p class="err">' + (r.message || '检测失败') + '</p>'; return; }
        const missingFileCount = (r.missing_files||[]).length;
        const missingDirCount = (r.missing_dirs||[]).length;
        const totalMissing = missingFileCount + missingDirCount;
        const missingSettingCount = (r.missing_setting_files||[]).length;
        const se = r.setting_encoding || {};
        const langLabel = r.language === 'zh-TW' ? '繁体中文 (Big5)' : r.language === 'zh-CN' ? '简体中文 (GBK/UTF-8)' : (r.language_name || '未知');
        const langColor = r.language === 'zh-TW' ? '#e9a645' : r.language === 'zh-CN' ? '#4ec9b0' : 'var(--text-secondary)';
        const confLabel = r.version_confidence === 'exact' ? '精确匹配' : r.version_confidence === 'timestamp' ? 'PE时间戳推断' : r.version_confidence === 'size' ? '文件大小推断' : '未知';
        el.innerHTML = `
            <div style="margin-bottom:10px;padding:8px 12px;background:var(--bg-page);border-radius:6px;border-left:3px solid ${langColor};">
                <span style="font-weight:600;">语言/区域：</span><span style="color:${langColor};">${langLabel}</span>
                ${se.encoding ? '<span style="margin-left:8px;font-size:12px;color:var(--text-secondary);">(' + se.encoding + ' 编码)</span>' : ''}
            </div>
            <div class="info-row"><span class="info-label">EXE类型:</span><span class="info-value">${r.exe_type || '未知'}</span></div>
            <div class="info-row"><span class="info-label">EXE大小:</span><span class="info-value">${r.exe_size_mb || 0} MB</span></div>
            <div class="info-row"><span class="info-label">PE时间戳:</span><span class="info-value">${r.pe_timestamp ? new Date(r.pe_timestamp * 1000).toISOString().split('T')[0] : '-'}</span></div>
            <div class="info-row"><span class="info-label">镜像大小:</span><span class="info-value">${r.image_size_mb || 0} MB</span></div>
            <div class="info-row"><span class="info-label">区段数:</span><span class="info-value">${r.sections || '-'}</span></div>
            <div class="info-row"><span class="info-label">文件修改时间:</span><span class="info-value">${r.file_timestamp || '-'}</span></div>
            ${r.version_hint ? '<div class="info-row"><span class="info-label">推断版本:</span><span class="info-value" style="color:var(--info);">' + escHtml(r.version_hint) + '</span><span style="font-size:11px;color:var(--text-secondary);margin-left:4px;">(' + confLabel + ')</span></div>' : ''}
            ${r.has_script_so !== undefined ? '<div class="info-row"><span class="info-label">Script.so:</span><span class="info-value ' + (r.has_script_so ? 'text-success' : 'text-warning') + '">' + (r.has_script_so ? '已找到' : '未找到') + '</span></div>' : ''}
            <div class="info-row"><span class="info-label">MD5:</span><span class="info-value" style="font-size:11px;word-break:break-all;">${r.md5 || '-'}</span></div>
            <div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border);">
                <div class="info-row"><span class="info-label">游戏目录完整性:</span><span class="info-value ${r.integrity_score===100?'text-success':'text-warning'}">${r.integrity_score}% (${totalMissing}项缺失)</span></div>
                ${r.setting_integrity !== undefined ? '<div class="info-row"><span class="info-label">Setting 完整性:</span><span class="info-value ' + (r.setting_integrity===100?'text-success':'text-warning') + '">' + r.setting_integrity + '% (' + missingSettingCount + '个文件缺失)</span></div>' : ''}
            </div>
            ${(r.missing_files||[]).length ? '<div class="info-row" style="margin-top:4px;"><span class="info-label">缺失文件:</span><span class="info-value" style="color:var(--warning);">' + r.missing_files.join(', ') + '</span></div>' : ''}
            ${(r.missing_dirs||[]).length ? '<div class="info-row"><span class="info-label">缺失目录:</span><span class="info-value" style="color:var(--warning);">' + r.missing_dirs.join(', ') + '</span></div>' : ''}
            ${(r.missing_setting_files||[]).length ? '<div class="info-row"><span class="info-label">缺失Setting文件:</span><span class="info-value" style="color:var(--warning);">' + r.missing_setting_files.join(', ') + '</span></div>' : ''}
            ${(r.recommendations||[]).length ? '<div style="margin-top:8px">' + r.recommendations.map(rec => '<p class="hint">⚠ ' + escHtml(rec) + '</p>').join('') + '</div>' : ''}
        `;
    } catch(e) { el.innerHTML = '<p class="err">检测失败: ' + escHtml(String(e)) + '</p>'; }
}

// ============================================================
// 新手引导向导（含术语解释）
// ============================================================

const OnboardingWizard = {
    _currentStep: 0,
    _steps: [
        { 
            id: 'set_path', 
            title: '第1步：设置游戏目录', 
            desc: '点击左侧导航栏的"游戏设置"，选择你电脑上三国群英传7的安装目录。软件会自动检测版本、语言、完整性。',
            glossary: '<b>游戏目录：</b>即 Sango7.exe 所在的文件夹，里面包含 Shape、Script、Setting、Save 等子目录。<br><b>解包：</b>游戏资源打包在 .pck 文件中，需要用 RPGViewer 等工具解压到 Setting 目录才能编辑。',
            target: () => document.querySelector('[data-tab="settings"]'),
            placement: 'right' 
        },
        { 
            id: 'unpack_guide', 
            title: '第2步：解包游戏资源（重要）', 
            desc: '游戏数据打包在 Patch.pck 中，必须先解包才能编辑。点击"游戏设置"→ 版本检测，如果 Setting 完整性不是100%，说明还没解包。',
            glossary: '<b>PCK：</b>游戏的资源包文件，类似压缩包。内含 Setting、Shape 等目录。<br><b>RPGViewer：</b>第三方解包工具，百度搜索"RPGViewer 三国群英传7"下载。<br><b>解包后：</b>Setting 目录下会出现 General01.ini、Thing.ini 等可编辑文件。',
            target: () => document.querySelector('[data-tab="settings"]'),
            placement: 'right' 
        },
        { 
            id: 'core_data', 
            title: '第3步：编辑核心数据', 
            desc: '在"核心数据"区点击"武将编辑"进入编辑器。左侧列表选择武将，右侧修改属性。修改后点击"保存"按钮。',
            glossary: '<b>武将编辑：</b>修改武将姓名、武力、智力、兵种、必杀技等属性。<br><b>兵种编辑：</b>修改士兵的生命、攻击、防御、速度等战斗参数。<br><b>物品编辑：</b>修改武器、道具、坐骑的属性值和效果。',
            target: () => document.querySelector('[data-tab="generals"]'),
            placement: 'right' 
        },
        { 
            id: 'systems', 
            title: '第4步：调整游戏系统', 
            desc: '在"游戏系统"区可以修改阵型、官职、剧本、势力、城市等游戏机制。每个编辑器都遵循"选择→修改→保存"的流程。',
            glossary: '<b>阵型：</b>战斗中的布阵方式，影响攻防加成。<br><b>官职：</b>武将封官后的属性加成和带兵数量。<br><b>剧本：</b>不同历史时期的初始势力分布。<br><b>势力：</b>各诸侯的初始城市、武将、资源。',
            target: () => document.querySelector('.nav-category:nth-of-type(2) .nav-category-header'),
            placement: 'right' 
        },
        { 
            id: 'tools', 
            title: '第5步：使用工具集', 
            desc: '在"工具集"区可以进行备份恢复、批量修改、差异对比、编码转换、MOD打包等操作。打包好的MOD可以分享给其他人。',
            glossary: '<b>备份：</b>修改前先备份原文件，出问题可以一键恢复。<br><b>差异对比：</b>查看修改前后的具体变化。<br><b>编码转换：</b>繁体(Big5)和简体(GBK)之间的批量转换。<br><b>MOD打包：</b>将修改打包成 .zip 分发给其他玩家。',
            target: () => document.querySelector('.nav-category:nth-of-type(5) .nav-category-header'),
            placement: 'right' 
        },
        { 
            id: 'search_help', 
            title: '第6步：搜索和帮助', 
            desc: '顶部搜索框可跨模块搜索功能。右侧边缘的"?"按钮打开帮助面板，包含完整的术语词典和常见问题解答。',
            glossary: '<b>快捷键：</b>Ctrl+S 保存当前编辑内容。<br><b>帮助面板：</b>点击页面右侧边缘的"?"按钮，可搜索术语解释。<br><b>术语词典：</b>TermText、OBD、INI、PCK 等专业术语的通俗解释。',
            target: () => document.getElementById('navSearchInput'),
            placement: 'bottom' 
        },
        { 
            id: 'done', 
            title: '准备就绪！', 
            desc: '你已了解主要功能。建议先从简单的武将属性修改开始，熟悉后再尝试兵种、物品、剧本等高级编辑。修改前记得先备份！',
            glossary: '<b>新手建议：</b>①先改武将武力智力练手 → ②再改兵种攻防速度 → ③尝试修改物品属性 → ④最后编辑剧本和势力。<br><b>遇到问题：</b>点击"?"帮助面板，或查看"工具集→备份恢复"还原原始文件。',
            target: null, placement: 'center' 
        },
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
        
        // 术语解释
        const glossaryEl = document.getElementById('onboardingGlossary');
        if (step.glossary) {
            glossaryEl.style.display = 'block';
            glossaryEl.innerHTML = '<span style="color:var(--accent);font-weight:600;">📖 术语解释：</span><br>' + step.glossary;
        } else {
            glossaryEl.style.display = 'none';
        }

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
            spotlight.style.clipPath = '';
            return;
        }

        // 获取目标元素位置
        const rect = target.getBoundingClientRect();
        const cardW = 400;
        const cardH = card.offsetHeight || 280;

        // 创建镂空效果
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
    changed: false,

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

    /** 保存历史事件修改（兼容 Ctrl+S 全局保存） */
    async save() {
        if (this._directMode && this._directDirty) {
            return await this._saveDirect();
        }
        return { success: true, message: '无需保存' };
    },
};

// 初始化
document.addEventListener('panelsLoaded', () => {
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
                return;
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
    },

    saveCurrent() {
        showToast('地形已修改，请点击"保存"提交', 'info');
    }
};

const TERRAIN_COLORS = {"0":"#2d5a27","1":"#4a8c3f","2":"#8b9a47","3":"#9e8b5e","4":"#c4a45a","5":"#5a7a3a","6":"#2d5a1e","7":"#7a8a5a","8":"#6a6a5a","9":"#d4c47a","10":"#3a6aaa","11":"#5a8aaa","12":"#2a4a7a","13":"#d4e4f4","14":"#e8f0f8","15":"#c8d8e8","16":"#f0f4f8"};

// ============================================================
// Shape位移编辑器
// ============================================================
const shapeInfoEditor = {
    infos: [],
    _dirty: {},
    _selectedIdx: -1,

    async load() {
        const cat = document.getElementById('shapeInfoCategory').value;
        const res = await pyApi('shapeInfoList', cat);
        if (!res.success) { showToast(res.message, 'error'); return; }
        this.infos = res.infos;
        this._dirty = {};
        this._selectedIdx = -1;
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
                const selected = i === this._selectedIdx;
                return `<tr style="border-bottom:1px solid var(--border);${dirty?'background:rgba(255,200,0,0.1);':''}${selected?'background:var(--accent);color:white;':''}cursor:pointer;" onclick="shapeInfoEditor._selectedIdx=${i};shapeInfoEditor.render();">
                    <td style="padding:8px;color:${selected?'white':'inherit'};">${info.category}</td>
                    <td style="padding:8px;font-family:monospace;color:${selected?'white':'inherit'};">${info.file}</td>
                    <td style="padding:8px;font-size:11px;color:${selected?'rgba(255,255,255,0.7)':'var(--text-muted)'};">${info.path}</td>
                    <td style="padding:4px;text-align:center;"><input type="number" value="${x}" style="width:60px;font-size:12px;" onchange="shapeInfoEditor.setDirty('${key}','x',this.value)" onclick="event.stopPropagation();"></td>
                    <td style="padding:4px;text-align:center;"><input type="number" value="${y}" style="width:60px;font-size:12px;" onchange="shapeInfoEditor.setDirty('${key}','y',this.value)" onclick="event.stopPropagation();"></td>
                    <td style="padding:4px;text-align:center;"><button onclick="event.stopPropagation();shapeInfoEditor.saveOne('${key}')" class="btn btn-sm btn-primary" ${dirty?'':'disabled'}>保存</button></td>
                </tr>`;
            }).join('')}</tbody></table>`;
    },

    setDirty(key, field, val) {
        if (!this._dirty[key]) this._dirty[key] = { x: this.infos.find(i => i.path === key).x, y: this.infos.find(i => i.path === key).y };
        this._dirty[key][field] = parseInt(val) || 0;
    },

    saveCurrent() {
        if (this._selectedIdx >= 0 && this._selectedIdx < this.infos.length) {
            showToast('当前条目已修改，请点击"保存"提交', 'info');
        } else {
            showToast('请先选中一行', 'warning');
        }
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
    },

    async deleteCurrent() {
        if (this._selectedIdx < 0 || this._selectedIdx >= this.infos.length) {
            showToast('请先选中一行', 'warning');
            return;
        }
        const info = this.infos[this._selectedIdx];
        if (!confirm(`确认删除文件 "${info.file}"?\n路径: ${info.path}\n此操作不可撤销。`)) return;
        const res = await pyApi('shapeInfoDelete', info.path);
        if (res.success) {
            showToast(res.message, 'success');
            this._selectedIdx = -1;
            this.load();
        } else {
            showToast(res.message, 'error');
        }
    },

    async cloneCurrent() {
        if (this._selectedIdx < 0 || this._selectedIdx >= this.infos.length) {
            showToast('请先选中一行', 'warning');
            return;
        }
        const info = this.infos[this._selectedIdx];
        const newName = prompt('请输入新文件名（含 .info.ini 后缀）:', info.file.replace('.info.ini', '_copy.info.ini'));
        if (!newName) return;
        const res = await pyApi('shapeInfoClone', info.path, newName);
        if (res.success) {
            showToast(res.message, 'success');
            this.load();
        } else {
            showToast(res.message, 'error');
        }
    },

    async addNew() {
        const newName = prompt('请输入新文件名（含 .info.ini 后缀，如 "MyShape.info.ini"）:');
        if (!newName) return;
        const cat = document.getElementById('shapeInfoCategory').value;
        const res = await pyApi('shapeInfoNew', newName, cat);
        if (res.success) {
            showToast(res.message, 'success');
            this.load();
        } else {
            showToast(res.message, 'error');
        }
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
    // Canvas visualization
    cities: {},
    positions: {},
    mapSize: [17472, 12384],
    _showLabels: true,
    _scale: 16,
    _offsetX: 0, _offsetY: 0,
    _dragging: false,
    _dragStartX: 0, _dragStartY: 0,
    _dragOX: 0, _dragOY: 0,

    // Data editor (merged from cityconnectEditor)
    changed: false,
    _data: [],
    _selectedIdx: -1,

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
        // 同时加载可编辑数据
        const editRes = await pyApi('loadCityConnect');
        if (editRes.success) {
            this._data = editRes.data || [];
            this._renderList();
        }
    },

    async save() {
        if (!(await validateBeforeSave())) return;
        const res = await pyApi('saveCityConnect', this._data);
        if (res.success) { this.changed = false; updateSaveBtnState('cityConnectSaveBtn', false); }
        if (res.message) showToast(res.message, res.success ? 'success' : 'error');
        return res;
    },

    _renderList() {
        const el = document.getElementById('cityconnect_list');
        if (!el) return;
        el.innerHTML = '';
        this._data.forEach((item, idx) => {
            const card = document.createElement('div');
            card.className = 'item-card' + (idx === this._selectedIdx ? ' selected' : '');
            card.style.cssText = 'padding:8px 12px;cursor:pointer;border-bottom:1px solid var(--border);';
            card.innerHTML = `<span class="item-name">${escHtml(item.Name || '#' + idx)}</span> <span style="color:var(--text-muted);font-size:11px;">No=${escHtml(String(item.No || ''))}</span>`;
            card.onclick = () => this._select(idx);
            el.appendChild(card);
        });
    },

    _select(idx) {
        this._selectedIdx = idx;
        this._renderList();
        const item = this._data[idx];
        const fieldsEl = document.getElementById('cityconnect_fields');
        if (!fieldsEl || !item) return;
        let html = '';
        for (const [k, v] of Object.entries(item)) {
            html += `<div class="form-row"><div class="form-group"><label>${escHtml(k)}</label><input type="text" value="${escHtml(String(v != null ? v : ''))}" onchange="cityConnect._setField('${escHtml(k)}', this.value, ${idx})"></div></div>`;
        }
        fieldsEl.innerHTML = html;
    },

    _setField(key, val, idx) {
        if (this._data[idx]) this._data[idx][key] = val;
        this.changed = true;
        updateSaveBtnState('cityConnectSaveBtn', true);
    },

    // Canvas methods
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
    _selectedIdx: -1,

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
                <tr style="border-bottom:1px solid var(--border);${this._selectedIdx===i?'background:var(--accent);color:white;':''}cursor:pointer;" onclick="idiniEditor._selectedIdx=${i};idiniEditor.render();">
                    <td style="padding:8px;color:${this._selectedIdx===i?'white':'var(--text-muted)'};">${i+1}</td>
                    <td style="padding:4px;"><input type="text" value="${this._esc(item.key||'')}" style="width:100%;font-size:12px;" onchange="idiniEditor.update(${i},'key',this.value)" onclick="event.stopPropagation();"></td>
                    <td style="padding:4px;"><input type="text" value="${this._esc(item.value||'')}" style="width:100%;font-size:12px;" onchange="idiniEditor.update(${i},'value',this.value)" onclick="event.stopPropagation();"></td>
                    <td style="padding:4px;text-align:center;"><button onclick="event.stopPropagation();idiniEditor.remove(${i})" class="btn btn-sm btn-danger">删除</button></td>
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

    addNew() {
        this.newEntry();
    },

    saveCurrent() {
        this._dirty = true;
        showToast('当前条目已修改，请点击"保存"提交', 'info');
    },

    deleteCurrent() {
        if (this._selectedIdx >= 0 && this._selectedIdx < this.data.length) {
            this.remove(this._selectedIdx);
            this._selectedIdx = -1;
        } else {
            showToast('请先点击选中一个条目', 'warning');
        }
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
document.addEventListener('panelsLoaded', () => {
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

    async addNew() {
        const name = prompt('请输入新武将名称:', '新武将');
        if (!name || !name.trim()) return;
        const res = await pyApi('customgenAdd', name.trim());
        if (res.success) {
            showToast(res.message, 'success');
            this.load();
        } else {
            showToast(res.message, 'error');
        }
    },

    saveCurrent() {
        if (this._selectedIndex < 0) return;
        this.changed = true;
        showToast('当前武将已修改，请点击"保存此武将"或"保存修改"提交', 'info');
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

// ============================================================
// V3.5.0: BGM/音效编辑器
// ============================================================
const audioEditor = {
    _dirs: {},
    _currentDir: 'Music',
    _currentFile: null,
    _audioPlayer: null,
    changed: false,

    async init() {
        document.getElementById('audioDirSelect').innerHTML = '<option value="">加载中...</option>';
        document.getElementById('audioFileList').innerHTML = '<div class="empty-state">加载中...</div>';
        const r = await pyApi('browseAudio');
        if (r.success) {
            this._dirs = r.dirs;
            this._renderDirSelect();
            if (this._dirs.Music && this._dirs.Music.count > 0) {
                this._currentDir = 'Music';
            } else if (this._dirs.Sound && this._dirs.Sound.count > 0) {
                this._currentDir = 'Sound';
            }
            this._renderFileList();
            document.getElementById('audioStats').textContent = `共 ${r.total_files} 个音频文件`;
            showToast(r.message, 'success');
        } else {
            showToast(r.message, 'error');
        }
    },

    _renderDirSelect() {
        const sel = document.getElementById('audioDirSelect');
        sel.innerHTML = '';
        for (const name of ['Music', 'Sound', 'Audio']) {
            if (this._dirs[name] && this._dirs[name].count > 0) {
                const opt = document.createElement('option');
                opt.value = name;
                opt.textContent = `${name} (${this._dirs[name].count} 个文件)`;
                if (name === this._currentDir) opt.selected = true;
                sel.appendChild(opt);
            }
        }
    },

    switchDir(dir) {
        this._currentDir = dir || document.getElementById('audioDirSelect').value;
        this._renderFileList();
    },

    _renderFileList() {
        const list = document.getElementById('audioFileList');
        const dir = this._dirs[this._currentDir];
        if (!dir || dir.count === 0) {
            list.innerHTML = '<div class="empty-state">此目录下没有音频文件</div>';
            return;
        }
        let html = '';
        dir.files.forEach((f, i) => {
            const icon = this._getFileIcon(f.ext);
            html += `<div class="audio-file-item ${this._currentFile === f.name ? 'selected' : ''}" 
                onclick="audioEditor.selectFile('${this._escapeHtml(f.name)}', ${i})" 
                ondblclick="audioEditor.preview('${this._escapeHtml(f.name)}')">
                <span class="audio-file-icon">${icon}</span>
                <span class="audio-file-name">${this._escapeHtml(f.name)}</span>
                <span class="audio-file-size">${f.size_kb} KB</span>
                <span class="audio-file-actions">
                    <button class="btn btn-sm" onclick="event.stopPropagation();audioEditor.preview('${this._escapeHtml(f.name)}')" title="预览">▶</button>
                    <button class="btn btn-sm" onclick="event.stopPropagation();audioEditor.promptRename('${this._escapeHtml(f.name)}')" title="重命名">✏</button>
                    <button class="btn btn-sm btn-danger" onclick="event.stopPropagation();audioEditor.deleteFile('${this._escapeHtml(f.name)}')" title="删除">✕</button>
                </span>
            </div>`;
        });
        list.innerHTML = html;
    },

    selectFile(name, idx) {
        this._currentFile = name;
        this._renderFileList();
    },

    async preview(name) {
        const fname = name || this._currentFile;
        if (!fname) return;
        showToast('加载音频预览...', 'info');
        const r = await pyApi('previewAudio', this._currentDir, fname);
        if (r.success) {
            const container = document.getElementById('audioPreviewContainer');
            const ext = (fname || '').split('.').pop().toLowerCase();
            if (ext === 'mid' || ext === 'midi') {
                container.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-muted);">
                    <p>MIDI 文件不支持浏览器预览</p><p style="font-size:12px;">请使用本地播放器播放: ${this._escapeHtml(fname)}</p></div>`;
            } else {
                container.innerHTML = `<audio controls autoplay style="width:100%;max-width:500px;" onerror="this.parentElement.innerHTML='<p style=color:var(--danger)>播放失败</p>'">
                    <source src="${r.base64}" type="${r.mime}"></audio>
                    <p style="margin-top:8px;font-size:12px;color:var(--text-muted);">${this._escapeHtml(fname)} (${r.size_kb} KB)</p>`;
            }
            showToast('预览加载成功', 'success');
        } else {
            showToast(r.message, 'error');
        }
    },

    async importFile() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.wav,.mp3,.ogg,.wma,.mid,.midi,.flac';
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            // 在 PyWebView 环境中，需要通过后端处理文件上传
            const r = await pyApi('importAudio', file.name, this._currentDir, file.name);
            if (r.success) {
                showToast(r.message, 'success');
                this.init();
            } else {
                showToast(r.message, 'error');
            }
        };
        input.click();
    },

    async promptRename(name) {
        const fname = name || this._currentFile;
        if (!fname) return;
        const newName = prompt('输入新文件名:', fname);
        if (!newName || newName.trim() === '' || newName === fname) return;
        const r = await pyApi('renameAudio', this._currentDir, fname, newName.trim());
        if (r.success) {
            showToast(r.message, 'success');
            this._currentFile = newName.trim();
            this.init();
        } else {
            showToast(r.message, 'error');
        }
    },

    async deleteFile(name) {
        const fname = name || this._currentFile;
        if (!fname) return;
        if (!confirm(`确定删除音频文件 "${fname}"？\n此操作不可撤销！`)) return;
        const r = await pyApi('deleteAudio', this._currentDir, fname);
        if (r.success) {
            showToast(r.message, 'success');
            if (this._currentFile === fname) this._currentFile = null;
            this.init();
        } else {
            showToast(r.message, 'error');
        }
    },

    saveCurrent() { this.changed = true; },

    _getFileIcon(ext) {
        const map = { '.wav': '🔊', '.mp3': '🎵', '.ogg': '🎶', '.wma': '🎼', '.mid': '🎹', '.midi': '🎹', '.flac': '🎧' };
        return map[ext] || '🎵';
    },

    _escapeHtml(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }
};

// ============================================================
// V3.5.0: 沙盒测试模式
// ============================================================
const sandboxManager = {
    _status: null,
    changed: false,

    async init() {
        await this.refreshStatus();
    },

    async refreshStatus() {
        const r = await pyApi('getSandboxStatus');
        this._status = r;
        this._render();
    },

    _render() {
        const container = document.getElementById('sandboxContent');
        const s = this._status;

        if (!s || !s.exists) {
            container.innerHTML = `
                <div class="empty-state" style="padding:40px;">
                    <p style="font-size:48px;margin-bottom:16px;">🧪</p>
                    <h3>沙盒未创建</h3>
                    <p style="color:var(--text-muted);margin-bottom:20px;">沙盒是一个独立的测试环境，在其中安装MOD不会影响原始游戏文件</p>
                    <button class="btn btn-primary btn-lg" onclick="sandboxManager.create()">创建沙盒</button>
                </div>`;
            return;
        }

        const modsHtml = (s.mods_installed && s.mods_installed.length > 0)
            ? s.mods_installed.map(m => `<span class="badge" style="background:var(--success-bg);color:var(--success);margin:2px;">${m}</span>`).join('')
            : '<span style="color:var(--text-muted);">无</span>';

        container.innerHTML = `
            <div class="sandbox-info-card">
                <div class="sandbox-status-row">
                    <span class="sandbox-status-dot active"></span>
                    <span style="font-weight:700;">沙盒运行中</span>
                </div>
                <div class="sandbox-details">
                    <div class="sandbox-detail-item"><span class="label">创建时间</span><span>${s.created || '-'}</span></div>
                    <div class="sandbox-detail-item"><span class="label">文件数</span><span>${s.file_count || 0}</span></div>
                    <div class="sandbox-detail-item"><span class="label">大小</span><span>${s.total_size_mb || 0} MB</span></div>
                    <div class="sandbox-detail-item"><span class="label">已安装MOD</span><span>${modsHtml}</span></div>
                    <div class="sandbox-detail-item"><span class="label">最后安装</span><span>${s.last_install || '-'}</span></div>
                </div>
                <div class="sandbox-actions">
                    <button class="btn btn-success" onclick="sandboxManager.launch()">🚀 启动游戏</button>
                    <button class="btn" onclick="sandboxManager.installMod()">📦 安装MOD</button>
                    <button class="btn btn-danger" onclick="sandboxManager.cleanup()">🗑 清理沙盒</button>
                </div>
            </div>`;
    },

    async create() {
        if (!confirm('创建沙盒将复制必要的游戏文件到临时目录。继续？')) return;
        showToast('正在创建沙盒...', 'info');
        const r = await pyApi('createSandbox');
        if (r.success) {
            showToast(r.message, 'success');
            await this.refreshStatus();
        } else {
            showToast(r.message, 'error');
        }
    },

    async launch() {
        if (!confirm('确定从沙盒启动游戏？')) return;
        const r = await pyApi('launchSandbox');
        if (r.success) {
            showToast('游戏已启动！', 'success');
        } else {
            showToast(r.message, 'error');
        }
    },

    async installMod() {
        const modName = prompt('输入要安装到沙盒的MOD名称（需先打包）:');
        if (!modName || !modName.trim()) return;
        showToast('正在安装...', 'info');
        const r = await pyApi('installToSandbox', modName.trim());
        if (r.success) {
            showToast(r.message, 'success');
            await this.refreshStatus();
        } else {
            showToast(r.message, 'error');
        }
    },

    async cleanup() {
        if (!confirm('确定清理沙盒？所有沙盒中的修改将丢失！')) return;
        const r = await pyApi('cleanupSandbox');
        if (r.success) {
            showToast(r.message, 'success');
            await this.refreshStatus();
        } else {
            showToast(r.message, 'error');
        }
    },

    saveCurrent() { this.changed = true; }
};

// ============================================================
// V3.5.0: 修改历史记录
// ============================================================
const operationHistory = {
    _history: [],
    _total: 0,
    _filter: '',
    changed: false,

    async init() {
        await this.load();
    },

    async load(filter) {
        this._filter = filter || '';
        const r = await pyApi('getOperationHistory', 100, this._filter || undefined);
        if (r.success) {
            this._history = r.history;
            this._total = r.total;
            this._render();
        } else {
            showToast(r.message, 'error');
        }
    },

    _render() {
        const container = document.getElementById('opshistoryContent');
        if (!this._history || this._history.length === 0) {
            container.innerHTML = '<div class="empty-state">暂无操作记录</div>';
            return;
        }

        let html = `<div class="opshistory-toolbar">
            <span style="color:var(--text-muted);">共 ${this._total} 条记录，显示最近 ${this._history.length} 条</span>
            <div style="display:flex;gap:8px;">
                <input type="text" id="opshistoryFilter" placeholder="筛选操作类型..." value="${this._escapeHtml(this._filter)}" 
                    onkeydown="if(event.key==='Enter')operationHistory.load(document.getElementById('opshistoryFilter').value)"
                    style="padding:4px 8px;border:1px solid var(--border);border-radius:4px;background:var(--bg-input);color:var(--text-primary);font-size:12px;width:160px;">
                <button class="btn btn-sm" onclick="operationHistory.load(document.getElementById('opshistoryFilter').value)">筛选</button>
                <button class="btn btn-sm btn-danger" onclick="operationHistory.clearAll()">清空记录</button>
            </div>
        </div>`;

        html += '<div class="opshistory-list">';
        this._history.forEach((h, i) => {
            const actionIcon = this._getActionIcon(h.action);
            html += `<div class="opshistory-item">
                <span class="opshistory-icon">${actionIcon}</span>
                <div class="opshistory-body">
                    <div class="opshistory-action">${this._escapeHtml(h.action)}</div>
                    <div class="opshistory-target">${this._escapeHtml(h.target)}</div>
                    ${h.detail ? `<div class="opshistory-detail">${this._escapeHtml(h.detail)}</div>` : ''}
                </div>
                <span class="opshistory-time">${h.timestamp}</span>
            </div>`;
        });
        html += '</div>';

        container.innerHTML = html;
    },

    async clearAll() {
        if (!confirm('确定清空所有操作历史记录？此操作不可撤销！')) return;
        const r = await pyApi('clearOperationHistory');
        if (r.success) {
            showToast(r.message, 'success');
            this._history = [];
            this._total = 0;
            this._render();
        } else {
            showToast(r.message, 'error');
        }
    },

    saveCurrent() { this.changed = true; },

    _getActionIcon(action) {
        const a = (action || '').toLowerCase();
        if (a.includes('save') || a.includes('保存')) return '💾';
        if (a.includes('delete') || a.includes('删除')) return '🗑';
        if (a.includes('create') || a.includes('新建') || a.includes('创建')) return '➕';
        if (a.includes('import') || a.includes('导入')) return '📥';
        if (a.includes('export') || a.includes('导出')) return '📤';
        if (a.includes('backup') || a.includes('备份')) return '📋';
        if (a.includes('pack') || a.includes('打包')) return '📦';
        if (a.includes('install') || a.includes('安装')) return '⚡';
        if (a.includes('edit') || a.includes('修改') || a.includes('编辑')) return '✏';
        return '📌';
    },

    _escapeHtml(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }
};

// ============================================================
// V3.13.0: MOD 打包分发系统面板
// ============================================================
const modPackagerPanel = {
    changed: false,
    _mods: [],
    _selectedMod: '',

    async init() { await this.loadModList(); },

    async loadModList() {
        const r = await pyApi('listMods');
        if (r.success && r.mods) {
            this._mods = r.mods;
            this._renderModList();
        } else {
            showToast(r.message || '加载MOD列表失败', 'error');
        }
    },

    _renderModList() {
        const c = document.getElementById('modPackagerModList');
        if (!this._mods.length) { c.innerHTML = '<div class="empty-state">暂无MOD</div>'; return; }
        c.innerHTML = this._mods.map(m => 
            `<div class="audio-file-item" onclick="modPackagerPanel._selectMod('${m.name}')" 
                 style="cursor:pointer;padding:8px;border:1px solid var(--border);border-radius:4px;margin-bottom:4px;${this._selectedMod===m.name?'border-color:var(--accent);background:var(--bg-hover);':''}">
                <strong>${m.name}</strong><br><span style="font-size:0.8em;color:var(--text-muted);">${m.size_kb||0}KB · ${m.version||'v?'}</span>
            </div>`
        ).join('');
    },

    _selectMod(name) { this._selectedMod = name; this._renderModList(); this._showResult(`已选择: ${name}`); },

    _showResult(html) {
        const c = document.getElementById('modPackagerResult');
        if (c) c.innerHTML = `<div style="background:var(--bg-input);border-radius:8px;padding:12px;">${html}</div>`;
    },

    async analyzeMod() {
        if (!this._selectedMod) { showToast('请先选择MOD', 'warning'); return; }
        const r = await pyApi('analyzeModStructure', this._selectedMod);
        if (r.success) {
            const s = r.summary || r;
            this._showResult(`
                <h4>分析结果: ${r.mod_name||this._selectedMod}</h4>
                <p>文件总数: ${s.total_files||r.file_count||0}</p>
                <p>Setting文件: ${s.setting_files||0} | Shape: ${s.shape_files||0} | Script: ${s.script_files||0}</p>
                <p>总大小: ${((s.total_size||r.total_size||0)/1024).toFixed(1)}KB</p>
            `);
        } else { showToast(r.message, 'error'); }
    },

    async packOneClick() {
        if (!this._selectedMod) { showToast('请先选择MOD', 'warning'); return; }
        showToast('正在打包...', 'info');
        const r = await pyApi('packModOneClick', this._selectedMod);
        if (r.success) { showToast('打包成功!', 'success'); this._showResult(`<p>✅ 打包成功</p><p>路径: ${r.zip_path||r.output||'已生成'}</p><p>文件数: ${r.file_count||0}</p>`); }
        else { showToast(r.message, 'error'); }
    },

    async packFull() {
        if (!this._selectedMod) { showToast('请先选择MOD', 'warning'); return; }
        const r = await pyApi('packModFull', this._selectedMod);
        if (r.success) { showToast('完整打包成功!', 'success'); this._showResult(`<p>✅ 完整打包成功</p><p>路径: ${r.zip_path||r.output||'已生成'}</p>`); }
        else { showToast(r.message, 'error'); }
    },

    async packIncremental() {
        if (!this._selectedMod) { showToast('请先选择MOD', 'warning'); return; }
        const r = await pyApi('packModIncremental', this._selectedMod);
        if (r.success) { showToast('增量打包成功!', 'success'); this._showResult(`<p>✅ 增量打包成功</p><p>新增: ${r.added||0} | 修改: ${r.modified||0} | 删除: ${r.deleted||0}</p>`); }
        else { showToast(r.message, 'error'); }
    },

    async generateInstaller() {
        if (!this._selectedMod) { showToast('请先选择MOD', 'warning'); return; }
        const r = await pyApi('generateModInstaller', this._selectedMod);
        if (r.success) { showToast('安装器已生成!', 'success'); this._showResult(`<p>✅ 安装器已生成</p><p>路径: ${r.installer_path||r.output||'已生成'}</p>`); }
        else { showToast(r.message, 'error'); }
    },

    async generateReadme() {
        if (!this._selectedMod) { showToast('请先选择MOD', 'warning'); return; }
        const r = await pyApi('generateModReadme', this._selectedMod);
        if (r.success) { showToast('README已生成!', 'success'); this._showResult(`<p>✅ README已生成</p><pre style="white-space:pre-wrap;margin-top:8px;">${(r.content||r.readme||'').substring(0, 500)}</pre>`); }
        else { showToast(r.message, 'error'); }
    },

    async createSnapshot() {
        if (!this._selectedMod) { showToast('请先选择MOD', 'warning'); return; }
        const r = await pyApi('createModSnapshotV2', this._selectedMod);
        if (r.success) { showToast('快照已创建!', 'success'); this._showResult(`<p>✅ 快照已创建</p><p>文件数: ${r.file_count||0}</p>`); }
        else { showToast(r.message, 'error'); }
    },

    async validatePackage() {
        if (!this._selectedMod) { showToast('请先选择MOD', 'warning'); return; }
        const r = await pyApi('modValidatePack', this._selectedMod);
        if (r.success) { showToast('校验通过!', 'success'); this._showResult(`<p>✅ 校验通过</p>`); }
        else { showToast(r.message||'校验失败', 'error'); }
    },

    async versionBump(level) {
        if (!this._selectedMod) { showToast('请先选择MOD', 'warning'); return; }
        const r = await pyApi('versionBumpMod', this._selectedMod, level);
        if (r.success) { showToast(`版本已升级: ${r.new_version||level}`, 'success'); }
        else { showToast(r.message, 'error'); }
    },

    async detectConflicts() {
        if (this._mods.length < 2) { showToast('至少需要2个MOD才能检测冲突', 'warning'); return; }
        const r = await pyApi('detectModConflictsV2', this._mods[0].name, this._mods[1].name);
        if (r.success) {
            const conflicts = r.conflicts || [];
            this._showResult(`<p>冲突检测完成: ${conflicts.length} 个冲突</p>${conflicts.map(c=>`<div style="color:var(--warning);">⚠ ${c.file||c.path||'未知'} (${c.type||'overlap'})</div>`).join('')}`);
        } else { showToast(r.message, 'error'); }
    },

    saveCurrent() { this.changed = true; }
};

// ============================================================
// V3.13.0: TermText 智能编号分配面板
// ============================================================
const termtextAllocPanel = {
    changed: false,

    async init() { await this.loadSegments(); },

    async loadSegments() {
        const r = await pyApi('getTermtextAllSegments');
        if (r.success && r.segments) {
            this._renderSegments(r.segments);
        } else {
            // 尝试不依赖游戏路径的静态信息
            const info = await pyApi('getTermtextSegmentInfo', 'item_name');
            if (info.success) { this._renderSegments([info]); }
            else { showToast(r.message || '请先设置游戏目录', 'error'); }
        }
    },

    _renderSegments(segments) {
        const c = document.getElementById('termtextSegmentsGrid');
        if (!c) return;
        if (!segments || !segments.length) { c.innerHTML = '<div class="empty-state">无段数据</div>'; return; }
        c.innerHTML = segments.map(s => {
            const pct = s.usage_rate || s.usage_percent || 0;
            const color = pct > 90 ? 'var(--danger)' : pct > 70 ? 'var(--warning)' : 'var(--success)';
            return `<div style="background:var(--bg-input);border-radius:6px;padding:10px;">
                <div style="font-weight:bold;font-size:0.85em;">${s.content_type||s.name||'?'}</div>
                <div style="font-size:0.75em;color:var(--text-muted);">${s.start_id||'?'}-${s.end_id||'?'}</div>
                <div style="margin-top:4px;height:4px;background:var(--border);border-radius:2px;overflow:hidden;">
                    <div style="width:${pct}%;height:100%;background:${color};"></div>
                </div>
                <div style="font-size:0.72em;margin-top:2px;">${s.used||0}/${s.capacity||0} (${pct.toFixed(0)}%)</div>
            </div>`;
        }).join('');
    },

    async allocateSingle() {
        const ct = document.getElementById('termtextContentType').value;
        const r = await pyApi('allocateTermtextId', ct);
        if (r.success) {
            const c = document.getElementById('termtextAllocResult');
            c.innerHTML = `<div style="background:var(--bg-input);border-radius:8px;padding:12px;">
                <p>✅ 分配成功</p><p>内容类型: ${ct}</p><p>分配ID: <strong style="color:var(--accent);">${r.allocated_id||r.id}</strong></p><p>段: ${r.segment_info||''}</p>
            </div>`;
            showToast(`已分配 ID: ${r.allocated_id||r.id}`, 'success');
        } else { showToast(r.message, 'error'); }
    },

    async allocateSmart() {
        const ct = document.getElementById('termtextContentType').value;
        const count = parseInt(document.getElementById('termtextAllocCount').value) || 1;
        const r = await pyApi('smartAllocateTermtext', ct, count, false);
        if (r.success) {
            const ids = r.allocated_ids || r.ids || [];
            const c = document.getElementById('termtextAllocResult');
            c.innerHTML = `<div style="background:var(--bg-input);border-radius:8px;padding:12px;">
                <p>✅ 智能分配 ${ids.length} 个ID</p><p>类型: ${ct}</p><p>ID列表: ${ids.join(', ')}</p>
            </div>`;
            showToast(`已分配 ${ids.length} 个ID`, 'success');
        } else { showToast(r.message, 'error'); }
    },

    async allocateBatch() {
        const ct = document.getElementById('termtextContentType').value;
        const count = parseInt(document.getElementById('termtextAllocCount').value) || 1;
        const requests = [{ content_type: ct, count: count }];
        const r = await pyApi('allocateTermtextBatch', requests);
        if (r.success) {
            const c = document.getElementById('termtextAllocResult');
            c.innerHTML = `<div style="background:var(--bg-input);border-radius:8px;padding:12px;">
                <p>✅ 批量分配完成</p><p>总分配数: ${r.total_allocated||count}</p>
            </div>`;
            showToast('批量分配完成', 'success');
        } else { showToast(r.message, 'error'); }
    },

    async detectConflicts() {
        const r = await pyApi('detectTermtextConflicts');
        if (r.success) {
            const conflicts = r.conflicts || r.duplicates || [];
            const c = document.getElementById('termtextAllocResult');
            c.innerHTML = `<div style="background:var(--bg-input);border-radius:8px;padding:12px;">
                <p>冲突检测完成</p><p>重复ID: ${r.duplicate_count||0}</p><p>跨段冲突: ${r.cross_segment_count||0}</p><p>越界ID: ${r.out_of_range_count||0}</p>
                ${conflicts.length ? `<div style="margin-top:8px;color:var(--warning);">${conflicts.slice(0,10).map(c=>`⚠ ID ${c.id||c.text_id}: ${c.issue||c.type||''}`).join('<br>')}</div>` : '<p style="color:var(--success);">✅ 无冲突</p>'}
            </div>`;
        } else { showToast(r.message, 'error'); }
    },

    async autoRemediate() {
        if (!confirm('确定要自动修复所有冲突吗？')) return;
        const r = await pyApi('autoRemediateTermtext');
        if (r.success) { showToast(`已修复 ${r.fixed_count||0} 个问题`, 'success'); this.detectConflicts(); }
        else { showToast(r.message, 'error'); }
    },

    async generateReport() {
        const r = await pyApi('generateTermtextReport');
        if (r.success) {
            const c = document.getElementById('termtextAllocResult');
            c.innerHTML = `<div style="background:var(--bg-input);border-radius:8px;padding:12px;">
                <h4>分配报告</h4><p>总段数: ${r.total_segments||0}</p><p>总已用: ${r.total_used||0}</p><p>总可用: ${r.total_available||0}</p>
            </div>`;
        } else { showToast(r.message, 'error'); }
    },

    saveCurrent() { this.changed = true; }
};

// ============================================================
// V3.13.0: INI 模板生成器面板
// ============================================================
const iniTemplatePanel = {
    changed: false,
    _presets: [],
    _templates: [],

    async init() { await this.loadPresets(); },

    async loadPresets() {
        const r = await pyApi('getPresetTemplates');
        if (r.success && r.presets) {
            this._presets = r.presets;
            this._renderPresets();
        } else { showToast(r.message || '加载预设失败', 'error'); }
    },

    _renderPresets() {
        const c = document.getElementById('iniTemplatePresets');
        if (!c) return;
        if (!this._presets.length) { c.innerHTML = '<div class="empty-state">无预设</div>'; return; }
        c.innerHTML = this._presets.map(p => 
            `<button onclick="iniTemplatePanel._selectPreset('${p.name}')" class="btn" style="text-align:left;padding:10px;">
                <strong>${p.name}</strong><br><span style="font-size:0.78em;color:var(--text-muted);">${p.description||''}</span>
            </button>`
        ).join('');
    },

    _selectPreset(name) {
        document.getElementById('templateName').value = name;
        showToast(`已选择模板: ${name}`, 'info');
    },

    async loadTemplates() {
        const r = await pyApi('listTemplates');
        if (r.success) {
            this._templates = r.templates || [];
            const c = document.getElementById('iniTemplatePresets');
            c.innerHTML = this._templates.map(t =>
                `<button onclick="iniTemplatePanel._selectPreset('${t.name}')" class="btn" style="text-align:left;padding:10px;">
                    <strong>${t.name}</strong><br><span style="font-size:0.78em;color:var(--text-muted);">${t.data_type||''}</span>
                </button>`
            ).join('') || '<div class="empty-state">无自定义模板</div>';
        } else { showToast(r.message, 'error'); }
    },

    async generate() {
        const name = document.getElementById('templateName').value;
        const count = parseInt(document.getElementById('templateGenCount').value) || 1;
        if (!name) { showToast('请输入或选择模板名称', 'warning'); return; }
        const r = await pyApi('generateFromTemplate', name, count);
        if (r.success) {
            const data = r.generated_data || r.data || [];
            const c = document.getElementById('iniTemplateResult');
            c.innerHTML = `<div style="background:var(--bg-input);border-radius:8px;padding:12px;">
                <p>✅ 已生成 ${data.length} 条数据</p>
                <pre style="white-space:pre-wrap;font-size:0.8em;max-height:300px;overflow-y:auto;margin-top:8px;">${JSON.stringify(data.slice(0, 3), null, 2)}${data.length>3?'\n... (共'+data.length+'条)':''}</pre>
            </div>`;
            showToast(`已生成 ${data.length} 条数据`, 'success');
        } else { showToast(r.message, 'error'); }
    },

    async generateCrossFile() {
        const name = document.getElementById('templateName').value;
        if (!name) { showToast('请输入模板名称', 'warning'); return; }
        const templates = [{ name: name, count: 1 }];
        const relationships = [{ from: name, to: name, type: 'one_to_one' }];
        const r = await pyApi('generateCrossFile', templates, relationships);
        if (r.success) {
            const c = document.getElementById('iniTemplateResult');
            c.innerHTML = `<div style="background:var(--bg-input);border-radius:8px;padding:12px;">
                <p>✅ 跨文件生成完成</p><pre style="white-space:pre-wrap;font-size:0.8em;max-height:300px;overflow-y:auto;">${JSON.stringify(r, null, 2).substring(0, 800)}</pre>
            </div>`;
            showToast('跨文件生成完成', 'success');
        } else { showToast(r.message, 'error'); }
    },

    async validate() {
        const name = document.getElementById('templateName').value;
        const r = await pyApi('generateFromTemplate', name, 1);
        if (r.success && r.generated_data) {
            const v = await pyApi('validateCrossFileData', { [name]: r.generated_data });
            if (v.success) {
                const c = document.getElementById('iniTemplateResult');
                c.innerHTML = `<div style="background:var(--bg-input);border-radius:8px;padding:12px;">
                    <p>✅ 验证完成</p><p>错误: ${v.error_count||0} | 警告: ${v.warning_count||0}</p>
                </div>`;
                showToast('验证完成', 'success');
            } else { showToast(v.message, 'error'); }
        } else { showToast(r.message, 'error'); }
    },

    saveCurrent() { this.changed = true; }
};

// ============================================================
// V3.13.0: 引擎逆向工具面板
// ============================================================
const enginePanel = {
    changed: false,

    async init() {},

    _showResult(html) {
        const c = document.getElementById('engineResult');
        if (c) c.innerHTML = `<div style="font-size:0.85em;">${html}</div>`;
    },

    async buildCfg() {
        showToast('正在构建控制流图...', 'info');
        const r = await pyApi('buildScriptsoCfg');
        if (r.success) {
            this._showResult(`<h4>控制流图 (CFG)</h4>
                <p>基本块: ${r.total_blocks||0}</p><p>边: ${r.total_edges||0}</p>
                <p>函数: ${r.total_functions||0}</p><p>架构: ${r.arch||'?'}</p>
                ${r.functions ? `<details><summary>函数列表 (${r.functions.length})</summary><pre style="font-size:0.75em;">${JSON.stringify(r.functions.slice(0,10), null, 2)}</pre></details>` : ''}`);
            showToast(`CFG: ${r.total_blocks||0} 块, ${r.total_functions||0} 函数`, 'success');
        } else { showToast(r.message, 'error'); }
    },

    async findVtables() {
        showToast('正在识别虚函数表...', 'info');
        const r = await pyApi('findScriptsoVtables');
        if (r.success) {
            this._showResult(`<h4>虚函数表 (vtable)</h4>
                <p>识别到 ${r.vtable_count||0} 个虚函数表</p>
                ${r.vtables ? `<details><summary>详情</summary><pre style="font-size:0.75em;">${JSON.stringify(r.vtables.slice(0,10), null, 2)}</pre></details>` : ''}`);
            showToast(`识别到 ${r.vtable_count||0} 个虚函数表`, 'success');
        } else { showToast(r.message, 'error'); }
    },

    async injectScriptsoCave() {
        const addr = document.getElementById('scriptsoCaveAddr').value;
        const code = document.getElementById('scriptsoMachineCode').value;
        if (!addr || !code) { showToast('请填写地址和机器码', 'warning'); return; }
        if (!confirm(`确定要注入 Script.so Code Cave (地址: ${addr})？`)) return;
        const r = await pyApi('injectScriptsoCodeCave', parseInt(addr, 16), code);
        if (r.success) { showToast('注入成功!', 'success'); this._showResult(`<p>✅ 注入成功</p><p>${r.message||''}</p>`); }
        else { showToast(r.message, 'error'); }
    },

    async findExeCave() {
        showToast('正在搜索 EXE Code Cave...', 'info');
        const r = await pyApi('findExeCodeCave');
        if (r.success) {
            this._showResult(`<h4>EXE Code Cave</h4>
                <p>找到 ${r.cave_count||0} 个空闲区域</p><p>总可用空间: ${r.total_available||0} 字节</p>
                ${r.caves ? `<details><summary>详情 (前${Math.min(r.caves.length,10)}个)</summary><pre style="font-size:0.75em;">${JSON.stringify(r.caves.slice(0,10), null, 2)}</pre></details>` : ''}`);
            showToast(`找到 ${r.cave_count||0} 个 Code Cave`, 'success');
        } else { showToast(r.message, 'error'); }
    },

    async buildJumpStub() {
        const from = document.getElementById('jumpFromOffset').value;
        const to = document.getElementById('jumpToOffset').value;
        const type = document.getElementById('jumpStubType').value;
        if (!from || !to) { showToast('请填写跳转源和目标地址', 'warning'); return; }
        const r = await pyApi('buildJumpStub', parseInt(from, 16), parseInt(to, 16), type);
        if (r.success) {
            this._showResult(`<h4>跳转桩代码</h4>
                <p>类型: ${r.type||type}</p><p>大小: ${r.size||0} 字节</p>
                <p>机器码: <code style="color:var(--accent);">${r.code||''}</code></p>
                <p>汇编: <code>${r.assembly||''}</code></p>`);
            showToast(`已生成 ${r.size||0}B 跳转桩`, 'success');
        } else { showToast(r.message, 'error'); }
    },

    async deepParseSave() {
        const saveName = document.getElementById('sg7SaveSelect').value;
        if (!saveName) { showToast('请选择存档', 'warning'); return; }
        showToast('正在深度解析存档...', 'info');
        const r = await pyApi('deepParseSg7Save', saveName);
        if (r.success) {
            const c = document.getElementById('sg7ParseResult');
            c.innerHTML = `<p>武将: ${r.general_count||0}</p><p>势力: ${(r.factions||[]).length}</p><p>城池: ${(r.cities||[]).length}</p>`;
            this._showResult(`<h4>存档深度解析: ${saveName}</h4>
                <p>文件大小: ${r.file_size||0} 字节</p><p>武将数: ${r.general_count||0}</p>
                <p>势力数: ${(r.factions||[]).length}</p><p>城池数: ${(r.cities||[]).length}</p>
                ${r.generals ? `<details><summary>武将列表 (前5)</summary><pre style="font-size:0.75em;">${JSON.stringify(r.generals.slice(0,5), null, 2)}</pre></details>` : ''}`);
            showToast(`解析完成: ${r.general_count||0} 武将`, 'success');
        } else { showToast(r.message, 'error'); }
    },

    saveCurrent() { this.changed = true; }
};
