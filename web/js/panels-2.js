/**
 * San7ModMaker - panels-2
 * 从 app.js 拆分而来，保持原始顺序和功能不变
 */

// ============================================================
// 共享颜色常量（消除 3 处重复定义）
// ============================================================
const BALL_VISUALS = {
    0:{icon:'●',label:'默认',color:'#888'},1:{icon:'→',label:'直射',color:'#ff4444'},2:{icon:'⌒',label:'弧形',color:'#ff8800'},
    3:{icon:'⋘',label:'散射',color:'#44aaff'},4:{icon:'↷',label:'追踪',color:'#ff44ff'},5:{icon:'⚡',label:'落雷',color:'#ffff00'},
    6:{icon:'≈',label:'冲击',color:'#aa8844'},7:{icon:'◎',label:'旋转',color:'#ff6644'},8:{icon:'◆',label:'召唤',color:'#8844ff'},
    9:{icon:'━',label:'光束',color:'#44ffff'},10:{icon:'✱',label:'爆炸',color:'#ff0000'},11:{icon:'⇨',label:'穿透',color:'#ffaa00'},
    12:{icon:'❄',label:'冰锥',color:'#88ccff'},13:{icon:'🌀',label:'旋风',color:'#aaffaa'},14:{icon:'☠',label:'毒雾',color:'#88ff44'},
    15:{icon:'✚',label:'治疗',color:'#44ff44'},
};
const DMG_COLORS = ['#ccc','#ff4444','#4488ff','#44ff44','#ffdd00','#aa44ff','#ff0000','#ff8800','#44ff88'];
const DMG_LABELS = ['物理','火','水','风','雷','毒','真实','百分比','治疗'];
const ELEM_COLORS = ['#888','#ff4444','#4488ff','#44ff44','#ffdd00','#aa44ff'];
const ELEM_LABELS = ['无','火','水/冰','风','雷','毒'];

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
            hide(detailEl);
            return;
        }
        hide(emptyEl);
        show(detailEl);
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
        const usedIds = new Set(this.data.map(s => toInt(s.No)));
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
        const no = toInt(this.current.No);
        const src = this.current._source || 'BFMagic.ini';
        pyApi('deleteIniItem', 'Setting/' + src, src.replace('.ini', '').toUpperCase(), 'No', String(no));
        this.data = this.data.filter(s => toInt(s.No) !== no);
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
        const usedIds = new Set(this.data.map(s => toInt(s.No)));
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

        const getVal = (id, def) => { const el = document.getElementById('sk_' + id); return el ? (toInt(el.value) || def) : def; };
        const ball = getVal('Ball', 0);
        const dmg = getVal('DamageType', 0);
        const elem = getVal('Element', 0);
        const atk = getVal('Atk', 0);
        const range = getVal('Range', 1);
        const target = getVal('Target', 0);
        const damage = parseFloat(document.getElementById('sk_Damage')?.value) || 1.0;
        const mp = getVal('MP', 0);
        const atkVal = getVal('ATK', 0);

        // 弹道可视化（使用共享常量）
        const bv = BALL_VISUALS[ball] || BALL_VISUALS[0];
        const dmgColor = DMG_COLORS[dmg] || '#ccc';
        const elemColor = ELEM_COLORS[elem] || '#888';
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
                <div style="display:flex;align-items:center;gap:5px;"><span style="width:8px;height:8px;border-radius:2px;background:${dmgColor};display:inline-block;"></span><span style="color:var(--text-muted);">伤害:</span><span style="font-weight:600;">${DMG_LABELS[dmg]||'?'}</span></div>
                <div style="display:flex;align-items:center;gap:5px;"><span style="width:8px;height:8px;border-radius:2px;background:${elemColor};display:inline-block;"></span><span style="color:var(--text-muted);">属性:</span><span style="font-weight:600;">${ELEM_LABELS[elem]||'?'}</span></div>
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
        let scoreColor = score >= 70 ? C.success : score >= 40 ? C.warning : C.muted;
        let scoreLabel = score >= 70 ? '高级' : score >= 40 ? '中级' : '入门';
        scoreEl.innerHTML = `强度: <span style="font-weight:600;color:${scoreColor};">${score}分</span> (${escHtml(scoreLabel)})`;

        // 参数校验警告
        const warnings = this._validateEffectParams({ball, dmg, elem, atk});
        if (warnings.length > 0) {
            warnEl.style.display = 'block';
            warnEl.innerHTML = `⚠️ ${escHtml(warnings.join(' | '))}`;
            warnEl.style.color = C.warning;
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
        const getVal = (id, def) => { const el = document.getElementById('sk_' + id); return el ? (toInt(el.value) || def) : def; };
        const ball = getVal('Ball', 0);
        const dmg = getVal('DamageType', 0);
        const elem = getVal('Element', 0);
        const atk = getVal('Atk', 0);
        const range = getVal('Range', 1);
        const target = getVal('Target', 0);
        const damage = parseFloat(document.getElementById('sk_Damage')?.value) || 1.0;
        const level = getVal('Level', 1);

        const ballLabels = ['默认','直射','弧形','散射','追踪','落雷','冲击','旋转','召唤','光束','爆炸','穿透','冰锥','旋风','毒雾','治疗'];
        const dmgLabels = DMG_LABELS;
        const elemLabels = ELEM_LABELS;
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
        showToast('技能描述已自动生成');
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
            hide(detailEl);
            return;
        }
        hide(emptyEl);
        show(detailEl);
        const fields = ['No','Name','ATK','DEF','Speed','Counter1','Counter2','WeakTo','Desc'];
        fields.forEach(k => {
            const el = document.getElementById('f_' + k);
            if (el) el.value = this.current[k] || '';
        });
        // 提示克制目标名称
        ['Counter1','Counter2','WeakTo'].forEach(k => {
            const hint = document.getElementById('f_' + k + 'Hint');
            if (hint) {
                const targetId = toInt(this.current[k]);
                const target = targetId ? this.data.find(f => toInt(f.No) === targetId) : null;
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
            const maxNo = this.data.reduce((max, d) => Math.max(max, toInt(d.No)), 0);
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
        const usedIds = new Set(this.data.map(f => toInt(f.No)));
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
        const no = toInt(this.current.No);
        pyApi('deleteIniItem', 'Setting/Formation.ini', 'FORMATION', 'No', String(no));
        this.data = this.data.filter(f => toInt(f.No) !== no);
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
            const c1 = toInt(f.Counter1);
            const c2 = toInt(f.Counter2);
            const w = toInt(f.WeakTo);
            const c1Name = c1 ? (this.data.find(x => toInt(x.No) === c1) || {}).Name || c1 : '-';
            const c2Name = c2 ? (this.data.find(x => toInt(x.No) === c2) || {}).Name || c2 : '-';
            const wName = w ? (this.data.find(x => toInt(x.No) === w) || {}).Name || w : '-';
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
    },

    // ============================================================
    // V3.6.0: 复合筛选增强
    // ============================================================
    _filters: [],       // 当前复合筛选条件
    _filterMode: 'AND', // AND / OR

    addFilter() {
        const fileKey = document.getElementById('batchTargetFile').value;
        const fields = fileKey && this.fileSchemas[fileKey] ? this.fileSchemas[fileKey].fields : [];
        this._filters.push({ field: fields[0] || '', op: 'eq', value: '' });
        this._renderFilters();
    },

    removeFilter(idx) {
        this._filters.splice(idx, 1);
        this._renderFilters();
    },

    setFilterMode(mode) {
        this._filterMode = mode;
        $$('.filter-mode-btn').removeClass('active');
        const btn = document.querySelector(`.filter-mode-btn[onclick*="${mode}"]`);
        if (btn) btn.classList.add('active');
    },

    _renderFilters() {
        const container = document.getElementById('batchAdvFilters');
        if (!container) return;
        const fileKey = document.getElementById('batchTargetFile').value;
        const fields = fileKey && this.fileSchemas[fileKey] ? this.fileSchemas[fileKey].fields : [];
        let html = '';
        this._filters.forEach((f, i) => {
            html += `<div class="adv-filter-row">
                <select onchange="batch._filters[${i}].field=this.value">
                    ${fields.map(fn => `<option value="${fn}" ${fn === f.field ? 'selected' : ''}>${fn}</option>`).join('')}
                </select>
                <select onchange="batch._filters[${i}].op=this.value">
                    <option value="eq" ${f.op === 'eq' ? 'selected' : ''}>=</option>
                    <option value="ne" ${f.op === 'ne' ? 'selected' : ''}>≠</option>
                    <option value="gt" ${f.op === 'gt' ? 'selected' : ''}>&gt;</option>
                    <option value="lt" ${f.op === 'lt' ? 'selected' : ''}>&lt;</option>
                    <option value="gte" ${f.op === 'gte' ? 'selected' : ''}>≥</option>
                    <option value="lte" ${f.op === 'lte' ? 'selected' : ''}>≤</option>
                    <option value="contains" ${f.op === 'contains' ? 'selected' : ''}>包含</option>
                    <option value="in" ${f.op === 'in' ? 'selected' : ''}>属于</option>
                </select>
                <input type="text" value="${this._escapeHtml(String(f.value))}" placeholder="值" 
                    onchange="batch._filters[${i}].value=this.value">
                <button class="btn btn-sm btn-danger" onclick="batch.removeFilter(${i})">✕</button>
            </div>`;
        });
        if (this._filters.length === 0) {
            html = '<span style="color:var(--text-muted);font-size:12px;">无筛选条件（匹配全部条目）</span>';
        }
        container.innerHTML = html;
    },

    async previewAdv() {
        const params = this._getAdvParams();
        if (!params) return;
        const res = await pyApi('batchPreviewAdv', params);
        this._renderPreview(res, 'batchNumericPreview');
    },

    async executeAdv() {
        const params = this._getAdvParams();
        if (!params) return;
        if (!confirm(`确认对 ${params.file} 的 ${params.field} 执行批量修改？`)) return;
        const res = await pyApi('batchExecuteAdv', params);
        if (res.message) showToast(res.message, res && res.success ? 'success' : 'error');
        if (res.success && res.preview) this._renderPreview(res, 'batchNumericPreview');
    },

    _getAdvParams() {
        const file = document.getElementById('batchTargetFile').value;
        const field = document.getElementById('batchTargetField').value;
        const op = document.getElementById('batchOpType').value;
        const val = toInt(document.getElementById('batchOpValue').value);
        if (!file) { showToast('请选择目标文件', 'info'); return null; }
        if (!field) { showToast('请选择目标字段', 'info'); return null; }
        if (isNaN(val)) { showToast('请输入有效数值', 'warning'); return null; }
        const filters = this._filters.length > 0 ? this._filters.map(f => ({
            field: f.field, op: f.op, value: f.op === 'in' ? f.value : f.value
        })) : null;
        return { file, field, op, value: val, filters, filterMode: this._filterMode };
    },

    // ============================================================
    // V3.6.0: 预设管理
    // ============================================================
    async loadPresets() {
        const r = await pyApi('batchPresetList');
        const select = document.getElementById('batchPresetSelect');
        if (!select) return;
        select.innerHTML = '<option value="">-- 选择预设 --</option>';
        if (r.success && r.presets) {
            r.presets.forEach(p => {
                select.innerHTML += `<option value="${escHtml(p.id)}">${escHtml(p.name)} [${escHtml(p.mode)}]</option>`;
            });
        }
    },

    async applyPreset() {
        const presetId = document.getElementById('batchPresetSelect').value;
        if (!presetId) return;
        const r = await pyApi('batchPresetLoad', presetId);
        if (!r.success) { showToast(r.message, 'error'); return; }
        const p = r.preset;
        const params = p.params || {};
        // 填充表单
        if (params.file) {
            document.getElementById('batchTargetFile').value = params.file;
            this.onFileChange();
        }
        if (params.field) {
            setTimeout(() => { document.getElementById('batchTargetField').value = params.field; }, 100);
        }
        if (params.op) document.getElementById('batchOpType').value = params.op;
        if (params.value !== undefined) document.getElementById('batchOpValue').value = params.value;
        if (params.filters) {
            this._filters = params.filters;
            this._renderFilters();
        }
        if (params.filterMode) this.setFilterMode(params.filterMode);
        showToast(`已加载预设: ${p.name}`, 'success');
    },

    async savePreset() {
        const params = this._getAdvParams();
        if (!params) return;
        const name = prompt('输入预设名称:', `批量_${params.file}_${params.field}_${params.op}`);
        if (!name || !name.trim()) return;
        const desc = prompt('输入预设描述（可选）:', '') || '';
        params.filters = this._filters.length > 0 ? this._filters.map(f => ({
            field: f.field, op: f.op, value: f.value
        })) : null;
        params.filterMode = this._filterMode;
        const r = await pyApi('batchPresetSave', name.trim(), 'numeric', params, desc);
        if (r.success) {
            showToast(r.message, 'success');
            this.loadPresets();
        } else {
            showToast(r.message, 'error');
        }
    },

    async deletePreset() {
        const presetId = document.getElementById('batchPresetSelect').value;
        if (!presetId) return;
        if (!confirm(`确定删除预设 "${presetId}"？`)) return;
        const r = await pyApi('batchPresetDelete', presetId);
        if (r.success) {
            showToast(r.message, 'success');
            this.loadPresets();
        } else {
            showToast(r.message, 'error');
        }
    },

    // ============================================================
    // V3.6.0: 撤销批量修改
    // ============================================================
    async undo() {
        if (!confirm('确定撤销最近一次批量修改？将恢复所有已备份的文件。')) return;
        const r = await pyApi('batchUndo');
        if (r.success) {
            showToast(r.message, 'success');
        } else {
            showToast(r.message, 'error');
        }
    },

    // ============================================================
    // V3.6.0: 操作链/流水线
    // ============================================================
    _pipelineSteps: [],

    addPipelineStep() {
        this._pipelineSteps.push({ file: '', field: '', op: 'set', value: 0, filters: [], filterMode: 'AND' });
        this._renderPipeline();
    },

    removePipelineStep(idx) {
        this._pipelineSteps.splice(idx, 1);
        this._renderPipeline();
    },

    _renderPipeline() {
        const container = document.getElementById('batchPipelineSteps');
        if (!container) return;
        if (this._pipelineSteps.length === 0) {
            container.innerHTML = '<div class="empty-state">暂无操作步骤，请点击"添加步骤"</div>';
            return;
        }
        let html = '';
        this._pipelineSteps.forEach((step, i) => {
            const fileKeys = Object.keys(this.fileSchemas);
            const fields = step.file && this.fileSchemas[step.file] ? this.fileSchemas[step.file].fields : [];
            html += `<div class="pipeline-step">
                <span class="pipeline-step-num">#${i + 1}</span>
                <select onchange="batch._pipelineSteps[${i}].file=this.value;batch._renderPipeline()" style="min-width:140px;">
                    <option value="">-- 文件 --</option>
                    ${fileKeys.map(k => `<option value="${k}" ${k === step.file ? 'selected' : ''}>${this.fileSchemas[k] ? this.fileSchemas[k].label : k}</option>`).join('')}
                </select>
                <select onchange="batch._pipelineSteps[${i}].field=this.value" style="min-width:100px;">
                    <option value="">-- 字段 --</option>
                    ${fields.map(fn => `<option value="${fn}" ${fn === step.field ? 'selected' : ''}>${fn}</option>`).join('')}
                </select>
                <select onchange="batch._pipelineSteps[${i}].op=this.value">
                    <option value="add" ${step.op === 'add' ? 'selected' : ''}>+</option>
                    <option value="sub" ${step.op === 'sub' ? 'selected' : ''}>−</option>
                    <option value="mul" ${step.op === 'mul' ? 'selected' : ''}>×</option>
                    <option value="set" ${step.op === 'set' ? 'selected' : ''}>=</option>
                    <option value="cap" ${step.op === 'cap' ? 'selected' : ''}>上限</option>
                </select>
                <input type="number" value="${step.value}" onchange="batch._pipelineSteps[${i}].value=toInt(this.value)" style="width:80px;">
                <button class="btn btn-sm btn-danger" onclick="batch.removePipelineStep(${i})">✕</button>
            </div>`;
        });
        container.innerHTML = html;
    },

    async executePipeline() {
        if (this._pipelineSteps.length === 0) {
            showToast('请先添加操作步骤', 'info');
            return;
        }
        if (!confirm(`确认执行 ${this._pipelineSteps.length} 步批量操作流水线？\n此操作将修改多个文件。`)) return;
        showToast('执行流水线中...', 'info');
        const r = await pyApi('batchPipelineExecute', this._pipelineSteps);
        if (r.success) {
            let summary = r.message + '\n\n';
            (r.steps || []).forEach(s => {
                summary += `  步骤 ${s.step}: ${s.file}.${s.field} ${s.op} → ${s.message}\n`;
            });
            showToast(r.message, 'success');
            const container = document.getElementById('batchPipelineResult');
            if (container) {
                container.innerHTML = `<pre style="font-size:12px;color:var(--text-primary);">${this._escapeHtml(summary)}</pre>`;
            }
        } else {
            showToast(r.message, 'error');
        }
    },

    _escapeHtml(s) {
        const d = document.createElement('div');
        d.textContent = String(s);
        return d.innerHTML;
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
            const type = toInt(t.Type) || 1;
            const typeLabel = type === 2 ? '文' : type === 3 ? '特' : '武';
            const cost = toInt(t.Cost);
            if (filter !== 'all') {
                if (filter === 'w' && type !== 1) return;
                if (filter === 'e' && type !== 2) return;
                if (filter === 's' && type !== 3) return;
            }
            const card = document.createElement('div');
            card.className = 'item-card' + (idx === this.currentIndex ? ' selected' : '');
            card.innerHTML = '<div class="item-card-header"><span class="item-name">' + escHtml(t.Name||'无名') + '</span><span class="item-no">#' + (t.No||'') + '</span></div><div class="item-desc">' + typeLabel + '官 | 功勋' + cost + ' | Lv' + (t.Level||0) + '</div>';
            card.onclick = () => titleEditor.select(idx);
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
        if (!this.current) { if (emptyEl) emptyEl.style.display = 'flex'; hide(detailEl); return; }
        hide(emptyEl);
        show(detailEl);
        this._fields.forEach(k => {
            const el = document.getElementById('ti_' + k);
            if (el) {
                if (el.tagName === 'SELECT') el.value = String(this.current[k] || '');
                else el.value = this.current[k] || '';
            }
        });
    },

    currentChanged() { this.changed = true; },

    saveCurrent() {
        if (!this.current) return;
        this._fields.forEach(k => {
            const el = document.getElementById('ti_' + k);
            if (el) this.current[k] = el.value;
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
        const usedIds = new Set(this.data.map(t => toInt(t.No)));
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
        const no = toInt(this.current.No);
        pyApi('deleteIniItem', 'Setting/Title.ini', 'TITLE', 'No', String(no));
        this.data = this.data.filter(t => toInt(t.No) !== no);
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
        this.data.forEach((t, idx) => {
            const name = (t.Name || '').toLowerCase();
            const no = String(t.No || '');
            const type = toInt(t.Type) || 1;
            const typeLabel = type === 2 ? '文' : type === 3 ? '特' : '武';
            const cost = toInt(t.Cost);
            if (filter !== 'all') {
                if (filter === 'w' && type !== 1) return;
                if (filter === 'e' && type !== 2) return;
                if (filter === 's' && type !== 3) return;
            }
            if (kw && !name.includes(kw) && !no.includes(kw)) return;
            const card = document.createElement('div');
            card.className = 'item-card';
            card.innerHTML = '<div class="item-card-header"><span class="item-name">' + escHtml(t.Name||'无名') + '</span><span class="item-no">#' + (t.No||'') + '</span></div><div class="item-desc">' + typeLabel + '官 | 功勋' + cost + ' | Lv' + (t.Level||0) + '</div>';
            card.onclick = () => titleEditor.select(idx);
            container.appendChild(card);
        });
    },

    renderTree() {
        const container = document.getElementById('titleTreeContainer');
        if (!container) return;
        if (this.data.length === 0) { container.innerHTML = '<p class="hint">请先加载官职数据</p>'; return; }
        const groups = {};
        for (let r = 1; r <= 9; r++) groups[r] = [];
        this.data.forEach((t) => {
            const level = toInt(t.Level) || 1;
            const rank = Math.min(9, Math.max(1, Math.ceil(level / 10) || 1));
            if (!groups[rank]) groups[rank] = [];
            groups[rank].push(t);
        });
        let html = '<div class="title-tree"><div class="hint" style="margin-bottom:8px;color:var(--accent);">AI封官规则: 每季选Cost最低且满足武力/智力/等级条件的官职封给武将</div>';
        for (let r = 9; r >= 1; r--) {
            if (!groups[r] || groups[r].length === 0) continue;
            html += '<div class="title-rank-group"><h4>Lv' + (r*10) + '级 (' + groups[r].length + '个)</h4><div class="title-rank-items">';
            groups[r].sort((a,b) => (toInt(a.Cost)) - (toInt(b.Cost))).forEach((t) => {
                const type = toInt(t.Type) || 1;
                const typeLabel = type === 2 ? '文' : type === 3 ? '特' : '武';
                html += '<div class="title-chip" onclick="titleEditor.selectByNo(' + t.No + ')"><div class="tc-name">' + escHtml(t.Name || '#'+t.No) + ' <span style="color:var(--text-muted);font-size:10px;">' + typeLabel + '</span></div><div>功勋' + (t.Cost||0) + ' | 武' + (t.Str0||0) + '-' + (t.Str1||0) + ' | 智' + (t.Int0||0) + '-' + (t.Int1||0) + '</div></div>';
            });
            html += '</div></div>';
        }
        html += '</div>';
        container.innerHTML = html;
    },

    selectByNo(no) {
        const idx = this.data.findIndex(t => toInt(t.No) === no);
        if (idx >= 0) this.select(idx);
    },

    simulateAI() {
        const str = toInt(document.getElementById('aiSimStr').value);
        const int = toInt(document.getElementById('aiSimInt').value);
        const lv = toInt(document.getElementById('aiSimLv').value);
        const simType = toInt(document.getElementById('aiSimType').value) || 1;
        const resultEl = document.getElementById('aiSimResult');
        const pathEl = document.getElementById('aiSimPath');
        if (!this.data || this.data.length === 0) {
            resultEl.textContent = '请先加载官职数据';
            resultEl.style.color = C.danger;
            return;
        }
        // 筛选符合条件的官职: 武力/智力/等级/类型匹配，且IsUsed启用
        const eligible = this.data.filter((t) => {
            const tType = toInt(t.Type) || 1;
            if (simType !== 3 && tType !== simType && tType !== 3) return false;
            if (toInt(t.IsUsed) === 0) return false;
            const str0 = toInt(t.Str0);
            const str1 = toInt(t.Str1) || 255;
            const int0 = toInt(t.Int0);
            const int1 = toInt(t.Int1) || 255;
            const reqLv = toInt(t.Level);
            if (str < str0 || str > str1) return false;
            if (int < int0 || int > int1) return false;
            if (lv < reqLv) return false;
            return true;
        });
        // 按Cost升序排序（AI的选择逻辑）
        eligible.sort((a, b) => (toInt(a.Cost)) - (toInt(b.Cost)));
        if (eligible.length === 0) {
            resultEl.textContent = '武力' + str + ' 智力' + int + ' 等级' + lv + ' → 无符合条件的官职';
            resultEl.style.color = C.danger;
            pathEl.innerHTML = '<p class="hint">该武将不满足任何官职的条件。尝试降低Str0/Int0门槛或提高武将属性。</p>';
            return;
        }
        resultEl.textContent = '武力' + str + ' 智力' + int + ' 等级' + lv + ' → 共 ' + eligible.length + ' 个可选官职，AI将按Cost从低到高依次封官';
        resultEl.style.color = C.success;
        let html = '<div style="margin-bottom:4px;color:var(--text-muted);">AI封官顺序（Cost升序）:</div>';
        html += '<div style="display:flex;flex-wrap:wrap;gap:4px;">';
        eligible.forEach((t, i) => {
            const typeLabel = toInt(t.Type) === 2 ? '文' : toInt(t.Type) === 3 ? '特' : '武';
            const bg = i === 0 ? C.accent : i < 5 ? 'var(--bg-card)' : 'rgba(255,255,255,0.03)';
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
            const totalCost = eligible.reduce((s, t) => s + (toInt(t.Cost)), 0);
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
            hide(detailEl);
            return;
        }
        hide(emptyEl);
        show(detailEl);
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
        const usedIds = new Set(this.data.map(s => toInt(s.No)));
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
        const usedIds = new Set(this.data.map(s => toInt(s.No)));
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
        const no = toInt(this.current.No);
        pyApi('deleteIniItem', 'Setting/Scenario.ini', 'SCENARIO', 'No', String(no));
        this.data = this.data.filter(s => toInt(s.No) !== no);
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

const getVarCategory = (no) => {
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
            this._current.No = toInt(value);
        } else {
            this._current[key] = value;
        }
        this.changed = true;
    },

    addNew() {
        this.pushUndo();
        const maxNo = this._data.reduce((m, p) => Math.max(m, toInt(p.No)), 0);
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
        const maxNo = this._data.reduce((m, p) => Math.max(m, toInt(p.No)), 0);
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
        const lord = toInt(this.current.Lord);

        // 使用默认颜色（基于编号生成不同颜色）
        const colors = [
            [255,50,50], [50,150,255], [50,200,50], [255,200,50],
            [200,50,255], [50,255,200], [255,100,50], [100,200,255],
            [255,255,50], [150,255,50], [255,50,200], [50,255,100],
        ];
        const ci = (toInt(no)) % colors.length;
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
            hide(detailEl);
            return;
        }
        hide(emptyEl);
        show(detailEl);
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
            cap.innerHTML = '<option value="">无</option>' + this._cities.map(c => `<option value="${escHtml(String(c.No))}">${escHtml(c.Name || '#'+c.No)}</option>`).join('');
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
        const id = toInt(rawId);
        const target = id ? source.find(x => toInt(x.No) === id) : null;
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
        const id = toInt(no);
        const g = this._generals.find(x => toInt(x.No) === id);
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
            const maxNo = this.data.reduce((max, d) => Math.max(max, toInt(d.No)), 0);
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
        const usedIds = new Set(this.data.map(n => toInt(n.No)));
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
        const no = toInt(this.current.No);
        pyApi('deleteIniItem', 'Setting/Nation.ini', 'NATION', 'No', String(no));
        this.data = this.data.filter(n => toInt(n.No) !== no);
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
            hide(detailEl);
            return;
        }
        hide(emptyEl);
        show(detailEl);
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
            const maxNo = this.data.reduce((max, d) => Math.max(max, toInt(d.No)), 0);
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
        const usedIds = new Set(this.data.map(c => toInt(c.No)));
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
        const no = toInt(this.current.No);
        pyApi('deleteIniItem', 'Setting/City.ini', 'CITY', 'No', String(no));
        this.data = this.data.filter(c => toInt(c.No) !== no);
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
            const region = toInt(c.Region);
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
        $$('.batch-tab-btn').removeClass('active');
        $$('.batch-panel').hide();
        const btn = document.querySelector(`.batch-tab-btn[onclick*="${mode}"]`);
        if (btn) btn.classList.add('active');
        const panel = document.getElementById('batch' + mode.charAt(0).toUpperCase() + mode.slice(1));
        show(panel);

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
                select.innerHTML += `<option value="${escHtml(key)}">${escHtml(res.files[key].label)}</option>`;
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
                fieldSelect.innerHTML += `<option value="${escHtml(f)}">${escHtml(f)}</option>`;
                filterSelect.innerHTML += `<option value="${escHtml(f)}">${escHtml(f)}</option>`;
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
        const val = toInt(document.getElementById('batchOpValue').value);
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
            container.innerHTML = `<p style="color:var(--text-muted);padding:10px;">${escHtml(res.message || '无预览数据')}</p>`;
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
            container.innerHTML = `<p style="color:var(--danger);padding:10px;">${escHtml(res.message)}</p>`;
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
        const source = toInt(document.getElementById('batchCloneSource').value);
        const from = toInt(document.getElementById('batchCloneFrom').value);
        const to = toInt(document.getElementById('batchCloneTo').value);
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
            container.innerHTML += `<label><input type="checkbox" value="${escHtml(f)}" checked> ${escHtml(f)}</label>`;
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
            container.innerHTML = `<p style="color:var(--danger);padding:10px;">${escHtml(res.message)}</p>`;
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
                baseSelect.innerHTML += `<option value="${escHtml(b.id)}">${escHtml(b.time)} - ${escHtml(b.label)}</option>`;
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
            container.innerHTML = `<p style="color:var(--danger);padding:10px;">${escHtml(res.message)}</p>`;
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
                <div class="detail-row"><label>启用</label><select onchange="superAtkEditor._set('IsUsed', this.value)"><option value="1" ${(s.IsUsed || 1) === 1 ? 'selected' : ''}>是</option><option value="0" ${(s.IsUsed || 1) === 0 ? 'selected' : ''}>否</option></select></div>
            </div>`;
    },

    _set(key, val) {
        if (this._current !== null) { this._data[this._current][key] = val; this.changed = true; }
    },

    saveCurrent() {
        if (this._current !== null) {
            showToast('当前必杀技已修改，请点击"保存"提交', 'info');
        } else {
            showToast('请先选中一个必杀技', 'warning');
        }
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
    changed: false,

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
                // 显示缓存状态
                if (r.from_cache) {
                    showToast(`交叉引用数据已从缓存加载 (${r.cached_at || ''})`, 'info');
                } else if (r.cached_at) {
                    showToast(`交叉引用数据已扫描并缓存 (${r.cached_at})`, 'success');
                }
                // 重新渲染当前 tab 以显示引用数据
                if (this._catalogs) this._renderTab(this._currentTab);
            }
        } catch(e) { console.warn('交叉引用加载失败:', e); }
    },

    async _refreshCrossRef() {
        // 强制刷新交叉引用：清除缓存后重新扫描
        this._xref = null;
        showToast('正在重新扫描交叉引用...', 'info');
        try {
            const r = await pyApi('effectCrossRef', { force: true });
            if (r && r.success) {
                this._xref = r;
                showToast(`交叉引用已重新扫描 (${r.cached_at || ''})`, 'success');
                if (this._catalogs) this._renderTab(this._currentTab);
            }
        } catch(e) { console.warn('交叉引用刷新失败:', e); }
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
        $$('#effTab_ball, #effTab_damage, #effTab_element, #effTab_items, #effTab_glow, #effTab_atk, #effTab_templates').removeClass('active');
        const btn = document.getElementById('effTab_' + tab);
        if (btn) btn.classList.add('active');
        // 切换面板
        $$('.eff-panel').hide();
        const panel = document.getElementById('effPanel_' + tab);
        show(panel);
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
                    const color = cnt > 0 ? (cnt >= 5 ? C.success : C.warning) : C.muted;
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
            const refColor = cnt > 0 ? (cnt >= 5 ? C.success : C.warning) : C.muted;
            const refStyle = cnt > 0 ? 'cursor:pointer;text-decoration:underline;' : 'cursor:help;';
            html += `<tr>
                <td style="font-family:monospace;font-weight:600;">${g.id}</td>
                <td><span style="display:inline-block;width:16px;height:16px;border-radius:50%;background:${g.color};border:1px solid var(--border);" title="${g.name}"></span></td>
                <td><span style="font-weight:600;">${escHtml(g.name)}</span></td>
                <td style="font-size:13px;color:var(--text-muted);">${escHtml(g.desc)}</td>
                <td style="font-size:12px;color:var(--text-muted);">${escHtml(g.example)}</td>
                <td style="text-align:center;" title="${escHtml(tip)}"><span style="font-weight:600;color:${refColor};${refStyle}" onclick="effectEditor._showRefDetail('glow',${g.id},'${escHtml(g.name)}')">${cnt}</span></td>
                <td><button onclick="effectEditor._copyGlowId(${g.id})" class="btn btn-xs" title="复制发光编号">📋 BFWResID=${g.id}</button>
                <button onclick="effectEditor._navigateToOBD(${g.id})" class="btn btn-xs" title="在OBD编辑器中查看模型" style="color:var(--accent);">🎯 OBD</button>
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
            showToast(`BFWResID=${id} 已复制到剪贴板，可粘贴到物品编辑器的 BFWResID 字段`);
        }).catch(() => {});
    },

    _renderAtkTypes() {
        const data = this._catalogs.atk_types || [];
        this._renderTable('effAtkTable', data, ['id', 'visual', 'name', 'desc', 'ref', 'action'], 'atk');
    },

    _copyValue(value, fieldName) {
        navigator.clipboard.writeText(String(value)).then(() => {
            showToast(`${fieldName}=${value} 已复制到剪贴板`);
        }).catch(() => {
            showToast(`值: ${value} (${fieldName})`);
        });
    },

    _copyToItemScript(scriptNo) {
        navigator.clipboard.writeText(String(scriptNo)).then(() => {
            showToast(`ScriptNo=${scriptNo} 已复制，可粘贴到物品编辑器的 ScriptNo 字段`);
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
                    Ball: toInt(getVal('effEdit_pBall', '0')),
                    DamageType: toInt(getVal('effEdit_pDamageType', '0')),
                    Element: toInt(getVal('effEdit_pElement', '0')),
                    Atk: toInt(getVal('effEdit_pAtk', '0')),
                    MP: toInt(getVal('effEdit_pMP', '0')),
                    ATK: toInt(getVal('effEdit_pATK', '0')),
                    Level: toInt(getVal('effEdit_pLevel', '1')) || 1,
                    Range: toInt(getVal('effEdit_pRange', '1')) || 1,
                    Target: toInt(getVal('effEdit_pTarget', '0')),
                    Damage: parseFloat(getVal('effEdit_pDamage', '1.0')) || 1.0,
                },
            };
            // 模板参数校验
            const warnings = this._validateTemplateParams(itemData.params);
            if (warnings.length > 0) {
                const msg = '⚠ 参数组合存在以下问题，是否继续保存？\n\n' + warnings.join('\n');
                if (!confirm(msg)) return;
            }
        } else {
            const isGlow = type === 'glow';
            const isItems = type === 'items';
            const hasVisual = type === 'ball' || type === 'element' || type === 'atk';
            const hasIcon = type === 'damage';

            itemData = {
                id: isNew ? toInt(getVal('effEdit_id', '0')) : this._editItemId,
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
                showToast(r.message);
                this._closeEditModal();
                // 重新加载
                await this.init();
            } else {
                showToast((r && r.message) || '保存失败', 'error');
            }
        } catch (e) {
            showToast('保存失败: ' + e.message, 'error');
        }
    },

    async _deleteItem(type, itemId, name) {
        if (!confirm(`确定要删除 "${name}" (id=${itemId}) 吗？\n\n此操作不可撤销，会直接从知识库中移除该条目。`)) return;
        try {
            const r = await pyApi('effectDeleteType', {catalog_type: type, item_id: itemId});
            if (r && r.success) {
                showToast(r.message);
                await this.init();
            } else {
                showToast((r && r.message) || '删除失败', 'error');
            }
        } catch (e) {
            showToast('删除失败: ' + e.message, 'error');
        }
    },

    // ============================================================
    // 模板参数校验 — 校验模板参数组合合理性
    // ============================================================
    _validateTemplateParams(params) {
        const warnings = [];
        const ball = params.Ball || 0;
        const dmg = params.DamageType || 0;
        const elem = params.Element || 0;
        const atk = params.Atk || 0;
        const range = params.Range || 1;
        const target = params.Target || 0;
        const damage = params.Damage || 1.0;
        const mp = params.MP || 0;
        const atkVal = params.ATK || 0;

        // Ball-DamageType 兼容性
        if (ball === 0 && dmg !== 0) warnings.push("- 弹道为 0 (无弹道) 时，伤害类型应设为 0");
        if (ball === 15 && dmg !== 8) warnings.push("- 治疗弹道建议搭配治疗伤害类型(8)");
        if (ball === 14 && dmg !== 5) warnings.push("- 毒雾弹道建议搭配毒属性伤害(5)");
        if (ball === 12 && dmg !== 2) warnings.push("- 冰锥弹道建议搭配水属性伤害(2)");
        if (ball === 10 && dmg !== 1) warnings.push("- 爆炸弹道建议搭配火属性伤害(1)");
        if (ball === 5 && dmg !== 4) warnings.push("- 落雷弹道建议搭配雷属性伤害(4)");

        // DamageType-Element 一致性
        if (dmg === 0 && elem !== 0) warnings.push("- 伤害类型为 0 (无伤害) 时，属性应设为 0");
        if (dmg === 1 && elem !== 1) warnings.push("- 火属性伤害建议搭配火属性(1)");
        if (dmg === 2 && elem !== 2) warnings.push("- 水属性伤害建议搭配水/冰属性(2)");
        if (dmg === 3 && elem !== 3) warnings.push("- 风属性伤害建议搭配风属性(3)");
        if (dmg === 4 && elem !== 4) warnings.push("- 雷属性伤害建议搭配雷属性(4)");
        if (dmg === 5 && elem !== 5) warnings.push("- 毒属性伤害建议搭配毒属性(5)");

        // Attack-Target 一致性
        if ((atk >= 10 && atk <= 14) && target !== 1) warnings.push("- 范围攻击类型建议目标设为群体(1)");
        if (atk === 4 && target !== 3 && target !== 2) warnings.push("- 治疗攻击建议搭配我方目标(2或3)");
        if (atk === 5 && target !== 3 && target !== 2) warnings.push("- 增益效果建议搭配我方目标(2或3)");
        if (atk === 6 && target !== 1 && target !== 0) warnings.push("- 减益效果建议搭配敌方目标(0或1)");

        // Ball-Attack 一致性
        if ((ball >= 1 && ball <= 15) && atk === 0) warnings.push("- 有弹道时建议搭配非 0 攻击类型");
        if (ball === 8 && atk !== 7) warnings.push("- 召唤弹道建议搭配召唤攻击类型(7)");
        if (ball === 5 && atk !== 2 && atk !== 1) warnings.push("- 落雷弹道建议搭配全军/群体攻击(1或2)");

        // Range 合理性
        if (range < 1) warnings.push("- 范围值过小，建议至少为 1");
        if (target === 0 && range > 3) warnings.push("- 敌方单体目标建议范围 ≤ 3");
        if (target === 1 && range < 2) warnings.push("- 敌方全体目标建议范围 ≥ 2");

        // 消耗比合理性
        if (atkVal > 0 && mp === 0) warnings.push("- 有攻击力但无 MP 消耗，建议设置合理 MP 值");
        if (atkVal === 0 && mp > 0) warnings.push("- 有 MP 消耗但无攻击力，建议检查是否为辅助技能");

        // 伤害倍率合理性
        if (damage > 3.0) warnings.push("- 伤害倍率过高(>3.0)，可能导致游戏不平衡");
        if (damage <= 0 && atk > 0) warnings.push("- 攻击类技能伤害倍率不应为 0");

        return warnings;
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
                showToast('特效知识库 JSON 已导出');
            } else {
                showToast('导出失败', 'error');
            }
        } catch (e) {
            showToast('导出失败: ' + e.message, 'error');
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
                    showToast(`导入成功: ${JSON.stringify(r.imported)}`);
                    await this.init();
                } else {
                    showToast((r && r.message) || '导入失败', 'error');
                }
            } catch (err) {
                showToast('导入失败: ' + err.message, 'error');
            }
        };
        input.click();
    },

    _navigateTo(tab) {
        const navItem = document.querySelector(`[data-tab="${tab}"]`);
        if (navItem) navItem.click();
    },

    _navigateToOBD(glowId) {
        // 跳转到 OBD 编辑器，筛选 BFWeapon 类型并高亮对应编号
        // BFWResID 对应 OBDFile_BFWeapon_XXXX.obd
        const navItem = document.querySelector('[data-tab="obdeditor"]');
        if (navItem) {
            navItem.click();
            // 切换到 OBD 编辑器后，选择 BFWeapon 类型
            setTimeout(() => {
                if (typeof obdEditor !== 'undefined' && obdEditor.selectCategory) {
                    obdEditor.selectCategory('BFWeapon');
                }
                const catSelect = document.getElementById('obdCategory');
                if (catSelect) {
                    catSelect.value = 'BFWeapon';
                    catSelect.dispatchEvent(new Event('change'));
                }
                // 搜索对应编号
                const searchInput = document.getElementById('obdSearch');
                if (searchInput) {
                    searchInput.value = String(glowId).padStart(4, '0');
                    searchInput.dispatchEvent(new Event('input'));
                }
                showToast(`已跳转到 OBD 编辑器，筛选 BFWeapon 类型，搜索编号 ${glowId}`);
            }, 300);
        } else {
            showToast('OBD 编辑器导航项不存在', 'error');
        }
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
        $$('[id^="effTplTag_"]').removeClass('active');
        const btn = document.getElementById('effTplTag_' + tag);
        if (btn) btn.classList.add('active');
        this._renderTemplates();
    },

    _applyTemplateToSkill(tplId) {
        const templates = (this._catalogs && this._catalogs.templates) ? this._catalogs.templates : [];
        const tpl = templates.find(t => t.id === tplId);
        if (!tpl) return;
        showToast('正在跳转到技能编辑器...');
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
            showToast(`模板 "${tpl.name}" 参数已复制到剪贴板\n可在技能编辑器中粘贴使用`);
        }).catch(() => {
            showToast(`模板参数已生成，请手动复制`);
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
        showToast(`模板 "${tpl.name}" 已加载，调整参数后点击保存`);
    },

    _qcUpdateVisual() {
        const visual = document.getElementById('effQcVisual');
        if (!visual) return;
        const ball = toInt(document.getElementById('qc_Ball')?.value);
        const dmg = toInt(document.getElementById('qc_DamageType')?.value);
        const elem = toInt(document.getElementById('qc_Element')?.value);
        const atk = toInt(document.getElementById('qc_Atk')?.value);
        const range = toInt(document.getElementById('qc_Range')?.value) || 1;
        const target = toInt(document.getElementById('qc_Target')?.value);
        const damage = parseFloat(document.getElementById('qc_Damage')?.value) || 1.0;

        // 弹道可视化（使用共享常量）
        const bv = BALL_VISUALS[ball] || BALL_VISUALS[0];

        // 伤害类型颜色
        const dmgColor = DMG_COLORS[dmg] || '#ccc';

        // 属性颜色
        const elemColor = ELEM_COLORS[elem] || '#888';

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
        if (!name) { showToast('请输入技能名称'); return; }
        const params = {
            Name: name,
            Ball: toInt(document.getElementById('qc_Ball').value),
            DamageType: toInt(document.getElementById('qc_DamageType').value),
            Element: toInt(document.getElementById('qc_Element').value),
            Atk: toInt(document.getElementById('qc_Atk').value),
            MP: toInt(document.getElementById('qc_MP').value),
            ATK: toInt(document.getElementById('qc_ATK').value),
            Level: toInt(document.getElementById('qc_Level').value) || 1,
            Range: toInt(document.getElementById('qc_Range').value) || 1,
            Target: toInt(document.getElementById('qc_Target').value),
            Damage: parseFloat(document.getElementById('qc_Damage').value) || 1.0,
            Effect: toInt(document.getElementById('qc_Effect').value),
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
            showToast(`技能 "${name}" 已创建并添加到技能列表`);
            // 切换到技能编辑器查看
            setTimeout(() => {
                const navItem = document.querySelector('[data-tab="skills"]');
                if (navItem) navItem.click();
            }, 300);
        } else {
            this._copyTemplateToClipboard(tpl);
            showToast('技能编辑器未加载，参数已复制到剪贴板');
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
        showToast('已重置为默认值');
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
        recPanel.className = 'rec-panel-warning';
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
            const bv = BALL_VISUALS[r.ball] || BALL_VISUALS[0];
            const dc = DMG_COLORS[r.dmg] || '#ccc';
            const ec = DMG_COLORS[r.elem] || '#888';
            html += `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:10px;cursor:pointer;transition:border-color 0.2s;" onmouseenter="this.style.borderColor=C.warning" onmouseleave="this.style.borderColor='var(--border)'" onclick="effectEditor._applyRecommendation(${i})">
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
        showToast(`推荐组合 "${r.name}" 已加载`);
        // 隐藏推荐面板
        const recPanel = document.getElementById('effRecommendPanel');
        hide(recPanel);
    },
};

// 全局函数：从特效编辑器跳转到 OBD 编辑器
window.openObdEditor = (type) => {
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

    /** 特效编辑器是知识库工具，无需保存数据文件 */
    async save() { return { success: true }; },
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
        $$('.gen-skill-tab-btn').removeClass('active');
        $$('.gen-skill-panel').removeClass('active');
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
            const isSelected = this._currentSection === idx;
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
            return `<div class="card" style="margin-bottom:8px;cursor:pointer;${isSelected ? 'border:2px solid var(--accent);background:var(--bg-card-hover);' : ''}" onclick="genSkillEditor.selectSection(${idx})">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <h4 style="margin:0;">#${no} ${name}</h4>
                    ${isSelected ? '<span style="font-size:10px;color:var(--accent);">已选中</span>' : ''}
                </div>
                <div class="detail-content">${fieldsHtml}</div>
            </div>`;
        }).join('') || '<p style="color:var(--text-muted);padding:10px;">暂无数据</p>';
    },

    selectSection(idx) {
        this._currentSection = idx;
        this.renderCurrent();
    },

    saveCurrent() {
        if (this._currentSection === null || this._currentSection === undefined) return;
        // 数据已通过 _set 实时更新到 this._data，无需额外操作
        this.changed = true;
        showToast('当前特性已修改，请点击"保存全部"提交', 'info');
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

    saveCurrent() {
        if (this._current === null) return;
        this.changed = true;
        showToast('当前武将出生地已修改，请点击"保存"提交', 'info');
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
        const newNo = this._data.length > 0 ? Math.max(...this._data.map(g => toInt(g.No || 0))) + 1 : 1;
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
        clone.No = Math.max(...this._data.map(g => toInt(g.No || 0))) + 1;
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

    saveCurrent() {
        if (this._current === null) return;
        this.changed = true;
        showToast('当前年代已修改，请点击"保存"提交', 'info');
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
        const newNo = this._data.length > 0 ? Math.max(...this._data.map(a => toInt(a.No || 0))) + 1 : 1;
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
        clone.No = Math.max(...this._data.map(a => toInt(a.No || 0))) + 1;
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
    _selectedIdx: -1,

    async load() {
        const res = await pyApi('loadGenLV');
        this._data = res.data || [];
        this._selectedIdx = -1;
        this.render();
    },

    render() {
        const tbody = document.getElementById('genLvBody');
        if (!tbody) return;
        tbody.innerHTML = this._data.map((lv, idx) =>
            `<tr onclick="genLvEditor._select(${idx})" style="cursor:pointer;${this._selectedIdx === idx ? 'background:var(--accent);color:white;' : ''}">
                <td>${lv.No || ''}</td>
                <td><input type="number" value="${lv.Exp || 0}" onchange="genLvEditor._set(${idx}, 'Exp', this.value)" onclick="event.stopPropagation()" style="width:120px;"></td>
                <td><input type="number" value="${lv.SolNum || 0}" onchange="genLvEditor._set(${idx}, 'SolNum', this.value)" onclick="event.stopPropagation()" style="width:100px;"></td>
                <td><button onclick="event.stopPropagation();genLvEditor.deleteEntry(${idx})" class="btn btn-danger btn-xs" title="删除">✕</button></td>
            </tr>`
        ).join('');
    },

    _select(idx) {
        this._selectedIdx = idx;
        this.render();
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
        const nextNo = this._data.length > 0 ? Math.max(...this._data.map(l => toInt(l.No || 0))) + 1 : 1;
        this._data.push({ No: nextNo, Exp: 0, SolNum: 0 });
        this.render();
    },

    deleteEntry(idx) {
        if (!confirm(`确认删除等级 #${this._data[idx]?.No || idx + 1}?`)) return;
        pyApi('deleteIniItem', 'Setting/GenLV.ini', 'GENLV', 'No', String(this._data[idx]?.No || ''));
        this._data.splice(idx, 1);
        this.render();
    },

    saveCurrent() {
        this.changed = true;
        showToast('当前等级已修改，请点击"保存"提交', 'info');
    },

    deleteCurrent() {
        if (this._selectedIdx < 0) { showToast('请先选择一行', 'warning'); return; }
        this.deleteEntry(this._selectedIdx);
        this._selectedIdx = -1;
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
                const id = toInt(d.id);
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
                const id = toInt(d.id);
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
        const maxId = Math.max(...this._data.map(d => toInt(d.id)), 0);
        this._data.push({ id: String(maxId + 1), value: '新文本' });
        this._filtered = this._data;
        this.render();
    },

    saveCurrent() {
        this.changed = true;
        showToast('当前文本已修改，请点击"保存"提交', 'info');
    },

    deleteCurrent() {
        if (this._selectedIdx < 0) { showToast('请先选择一条文本', 'warning'); return; }
        this._del(this._selectedIdx);
        this._selectedIdx = -1;
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
                <div style="padding:12px;">${otherIssues.map(e => `<p class="hint" style="color:${C.danger};">${e.file}: ${e.detail}</p>`).join('')}</div>`;
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
