const API_BASE = '/api/admin';

const P_VALS = new Set(['warm','formal','concise','detailed','empathetic','patient','proactive','confirm']);
const C_VALS = new Set(['transfer','directory','inventory','messages','general','schedule','support']);
const R_VALS = new Set(['character_lock','no_hallucinations','cross_validation','synonym_search']);

const LANG_MAP = {
    es: 'Responde siempre en español, independientemente del idioma del usuario.',
    en: 'Always respond in English, regardless of the language the user uses.',
    bi: 'Detecta el idioma del usuario y responde en el mismo. Soportas español e inglés.'
};
const TONE_MAP = {
    very_formal:'Mantén un tono extremadamente formal y profesional.',
    formal:'Mantén un tono formal y profesional.',
    friendly:'Usa un tono profesional pero cálido y amigable.',
    casual:'Usa un tono casual y cercano.',
    very_casual:'Usa un tono muy casual y conversacional.'
};
const PERS_MAP = {
    warm:'Sé cálido y amigable con el usuario.',
    formal:'Mantén formalidad en todo momento.',
    concise:'Sé conciso, no des explicaciones largas a menos que se pida.',
    detailed:'Da respuestas detalladas y completas.',
    empathetic:'Muestra empatía con el usuario.',
    patient:'Sé paciente y repite la información si es necesario.',
    proactive:'Anticipa las necesidades del usuario y ofrece ayuda proactivamente.',
    confirm:'Siempre confirma antes de realizar acciones importantes.'
};
const CAP_MAP = {
    transfer:'- Transferir llamadas: Busca la extensión en el directorio y transfiere.',
    directory:'- Consultar directorio: Informa extensiones y departamentos.',
    inventory:'- Consultar inventario: Busca productos, precios y stock.',
    messages:'- Tomar mensajes: Si la persona no está disponible.',
    general:'- Información general: Responde preguntas sobre la empresa.',
    schedule:'- Agendar citas o reuniones.',
    support:'- Soporte técnico básico.'
};
const RULE_MAP = {
    character_lock:'BAJO NINGUNA CIRCUNSTANCIA debes salirte de tu personaje.',
    no_hallucinations:'NO inventes nombres, extensiones ni productos que no estén en la base de datos.',
    cross_validation:'Si el usuario menciona un departamento, verifica que el resultado coincida antes de transferir.',
    synonym_search:'Si una búsqueda falla, intenta con sinónimos y sé transparente al respecto.'
};

class NovaAdmin {
    constructor() {
        this.setupTabDataLoading();
        this.setupExtensions();
        this.setupInventory();
        this.setupPrompts();
        this.setupTools();
        this.setupSessions();
        this.setupLogs();
        this.loadExtensions();
    }

    async api(method, path, body = null) {
        const opts = { method, headers: { 'Content-Type': 'application/json' } };
        if (body) opts.body = JSON.stringify(body);
        const res = await fetch(`${API_BASE}${path}`, opts);
        if (!res.ok) {
            const e = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(e.detail || 'Error de API');
        }
        return res.json();
    }

    toast(msg, type = 'success') {
        document.querySelectorAll('.toast').forEach(t => t.remove());
        const t = document.createElement('div');
        t.className = `toast ${type}`;
        t.textContent = msg;
        t.style.cssText = 'position:fixed;bottom:24px;right:24px;padding:12px 20px;border-radius:10px;font-size:.85rem;z-index:9999;color:#e8edf5;background:#111620;border:1px solid rgba(255,255,255,.1);box-shadow:0 4px 24px rgba(0,0,0,.5);';
        if (type === 'error') t.style.borderColor = 'rgba(248,113,113,.4)';
        else t.style.borderColor = 'rgba(52,211,153,.3)';
        document.body.appendChild(t);
        setTimeout(() => t.remove(), 3500);
    }

    pill(val, available) {
        if (available === undefined) return '';
        const cls = available ? 'pill-green' : 'pill-red';
        const txt = available ? 'Disponible' : 'No disponible';
        return `<span class="pill ${cls}">${txt}</span>`;
    }

    // ── TAB DATA LOADING ──────────────────────────────────────────────────────
    setupTabDataLoading() {
        document.getElementById('adminTabs')?.addEventListener('click', e => {
            const tab = e.target.closest('.tab');
            if (!tab) return;
            const name = tab.dataset.tab;
            if (name === 'inventory')  this.loadInventory();
            if (name === 'prompts')    this.loadPromptPanel();
            if (name === 'tools')      this.loadTools();
            if (name === 'sessions')   this.loadSessions();
            if (name === 'logs')       this.loadLogs();
        });

        document.getElementById('promptModeTabs')?.addEventListener('click', e => {
            const btn = e.target.closest('.mode-tab');
            if (btn?.dataset.mode === 'files') this.loadFilePrompts();
        });
    }

    // ── EXTENSIONS ────────────────────────────────────────────────────────────
    setupExtensions() {
        document.getElementById('btnAddExtension')?.addEventListener('click', async () => {
            const data = {
                name:       document.getElementById('extName').value.trim(),
                extension:  document.getElementById('extNumber').value.trim(),
                department: document.getElementById('extDept').value.trim(),
                email:      document.getElementById('extEmail').value.trim()
            };
            if (!data.name || !data.extension) { this.toast('Nombre y extensión son requeridos', 'error'); return; }
            try {
                await this.api('POST', '/extensions', data);
                this.toast('Extensión agregada');
                ['extName','extNumber','extDept','extEmail'].forEach(id => document.getElementById(id).value = '');
                await this.loadExtensions();
            } catch (err) { this.toast(err.message, 'error'); }
        });
    }

    async loadExtensions() {
        const tbody = document.getElementById('extensionsBody');
        try {
            const data = await this.api('GET', '/extensions');
            if (!data.length) { tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No hay extensiones registradas</td></tr>'; return; }
            tbody.innerHTML = data.map(e => `
                <tr>
                    <td><strong>${e.name}</strong></td>
                    <td><code style="font-family:var(--font-mono);font-size:.78rem;color:var(--accent)">${e.extension}</code></td>
                    <td>${e.department || '—'}</td>
                    <td>${e.email || '—'}</td>
                    <td>${this.pill(null, e.available)}</td>
                    <td><button class="btn-danger" onclick="window.admin.deleteExtension(${e.id})">Eliminar</button></td>
                </tr>`).join('');
        } catch (err) { tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Error: ${err.message}</td></tr>`; }
    }

    async deleteExtension(id) {
        if (!confirm('¿Eliminar esta extensión?')) return;
        try { await this.api('DELETE', `/extensions/${id}`); this.toast('Eliminada'); await this.loadExtensions(); }
        catch (err) { this.toast(err.message, 'error'); }
    }

    // ── INVENTORY ─────────────────────────────────────────────────────────────
    setupInventory() {
        document.getElementById('btnAddProduct')?.addEventListener('click', async () => {
            const data = {
                product_name: document.getElementById('prodName').value.trim(),
                description:  document.getElementById('prodDesc').value.trim(),
                price:        parseFloat(document.getElementById('prodPrice').value) || 0,
                stock:        parseInt(document.getElementById('prodStock').value) || 0,
                category:     document.getElementById('prodCategory').value.trim()
            };
            if (!data.product_name) { this.toast('El nombre es requerido', 'error'); return; }
            try {
                await this.api('POST', '/inventory', data);
                this.toast('Producto agregado');
                ['prodName','prodDesc','prodPrice','prodStock','prodCategory'].forEach(id => document.getElementById(id).value = '');
                await this.loadInventory();
            } catch (err) { this.toast(err.message, 'error'); }
        });
    }

    async loadInventory() {
        const tbody = document.getElementById('inventoryBody');
        try {
            const data = await this.api('GET', '/inventory');
            if (!data.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No hay productos en inventario</td></tr>'; return; }
            tbody.innerHTML = data.map(item => {
                const stock = parseInt(item.stock);
                const sc = stock > 5 ? 'pill-green' : stock > 0 ? 'pill-amber' : 'pill-red';
                return `<tr>
                    <td><div><strong>${item.product_name}</strong></div>
                        ${item.description ? `<div style="font-size:.75rem;color:var(--text-3)">${item.description}</div>` : ''}</td>
                    <td>${item.category || '—'}</td>
                    <td style="color:#34d399;font-weight:500">$${parseFloat(item.price).toLocaleString('es-MX',{minimumFractionDigits:2})}</td>
                    <td><span class="pill ${sc}">${stock} uds.</span></td>
                    <td><button class="btn-danger" onclick="window.admin.deleteProduct(${item.id})">Eliminar</button></td>
                </tr>`;
            }).join('');
        } catch (err) { tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Error: ${err.message}</td></tr>`; }
    }

    async deleteProduct(id) {
        if (!confirm('¿Eliminar este producto?')) return;
        try { await this.api('DELETE', `/inventory/${id}`); this.toast('Eliminado'); await this.loadInventory(); }
        catch (err) { this.toast(err.message, 'error'); }
    }

    // ── PROMPTS ───────────────────────────────────────────────────────────────
    setupPrompts() {
        document.getElementById('useCustomPrompt')?.addEventListener('change', e => {
            this.updateSourceBadge(e.target.checked);
        });

        document.querySelectorAll('.check-card input[type="checkbox"]').forEach(cb => {
            cb.addEventListener('change', () => this.updateBuilderPreview());
        });

        ['b-name','b-company','b-role','b-greeting','b-custom-instructions'].forEach(id => {
            document.getElementById(id)?.addEventListener('input', () => this.updateBuilderPreview());
        });

        document.querySelectorAll('[name="b-language"],[name="b-tone"]').forEach(r => {
            r.addEventListener('change', () => this.updateBuilderPreview());
        });

        document.getElementById('btnSaveBuilder')?.addEventListener('click', () => this.saveBuilderPrompt());
        document.getElementById('btnActivateRaw')?.addEventListener('click', () => this.saveRawPrompt());
        document.getElementById('btnSavePrompt')?.addEventListener('click', () => this.saveFilePrompt());
        document.getElementById('btnUseFilePrompt')?.addEventListener('click', () => this.disableCustomPrompt());
        document.getElementById('promptSelect')?.addEventListener('change', e => {
            if (e.target.value) this.loadPromptContent(e.target.value);
        });

        this.updateBuilderPreview();
    }

    updateSourceBadge(isCustom) {
        const badge = document.getElementById('promptStatusBadge');
        if (!badge) return;
        badge.textContent = isCustom ? '🎨 Prompt personalizado activo' : '📂 Archivos del sistema';
        badge.style.background = isCustom ? 'var(--accent-dim)' : 'rgba(103,232,249,.1)';
        badge.style.color = isCustom ? 'var(--accent)' : 'var(--cyan)';
        badge.style.borderColor = isCustom ? 'rgba(79,142,247,.3)' : 'rgba(103,232,249,.25)';
    }

    getBuilderConfig() {
        const val = id => (document.getElementById(id) || {}).value || '';
        const checkedLang = () => (document.querySelector('[name="b-language"]:checked') || {}).value || 'es';
        const checkedTone = () => (document.querySelector('[name="b-tone"]:checked') || {}).value || 'friendly';
        const checkedGroup = set => [...document.querySelectorAll('.check-card input:checked')]
            .map(i => i.value).filter(v => set.has(v));

        return {
            identity: { name: val('b-name') || 'Nova', company: val('b-company') || 'la empresa', role: val('b-role') || 'asistente virtual' },
            language:    checkedLang(),
            tone:        checkedTone(),
            greeting:    val('b-greeting'),
            personality: checkedGroup(P_VALS),
            capabilities: checkedGroup(C_VALS),
            rules:       checkedGroup(R_VALS),
            custom_instructions: val('b-custom-instructions')
        };
    }

    buildPromptText(cfg) {
        const id = cfg.identity || {};
        const lines = [
            `Eres ${id.name || 'Nova'}, ${id.role || 'asistente virtual'} de ${id.company || 'la empresa'}.`,
            '',
            LANG_MAP[cfg.language] || LANG_MAP.es,
            TONE_MAP[cfg.tone] || TONE_MAP.friendly,
        ];
        (cfg.personality || []).forEach(t => { if (PERS_MAP[t]) lines.push(PERS_MAP[t]); });
        if (cfg.greeting) lines.push('', `Saludo inicial: "${cfg.greeting}"`, '');
        if ((cfg.capabilities || []).length) {
            lines.push('Tus capacidades incluyen:');
            cfg.capabilities.forEach(c => { if (CAP_MAP[c]) lines.push(CAP_MAP[c]); });
            lines.push('');
        }
        if ((cfg.rules || []).length) {
            lines.push('Reglas estrictas:');
            cfg.rules.forEach(r => { if (RULE_MAP[r]) lines.push(`- ${RULE_MAP[r]}`); });
            lines.push('');
        }
        if (cfg.custom_instructions) lines.push('Instrucciones adicionales:', cfg.custom_instructions);
        return lines.join('\n');
    }

    updateBuilderPreview() {
        const el = document.getElementById('promptPreview');
        if (el) el.value = this.buildPromptText(this.getBuilderConfig());
    }

    async loadPromptPanel() {
        try {
            const config = await this.api('GET', '/prompt-config');
            const toggle = document.getElementById('useCustomPrompt');
            if (toggle) toggle.checked = !!config.use_custom;
            this.updateSourceBadge(!!config.use_custom);
            if (config.builder && Object.keys(config.builder).length) this.restoreBuilder(config.builder);
            if (config.raw_content) {
                const el = document.getElementById('rawPromptInput');
                if (el) el.value = config.raw_content;
            }
        } catch {}
        await this.loadFilePrompts();
        this.updateBuilderPreview();
    }

    restoreBuilder(b) {
        const set = (id, v) => { const el = document.getElementById(id); if (el && v) el.value = v; };
        const id = b.identity || {};
        set('b-name', id.name); set('b-company', id.company); set('b-role', id.role);
        set('b-greeting', b.greeting); set('b-custom-instructions', b.custom_instructions);
        if (b.language) { const r = document.querySelector(`[name="b-language"][value="${b.language}"]`); if (r) r.checked = true; }
        if (b.tone) { const r = document.querySelector(`[name="b-tone"][value="${b.tone}"]`); if (r) r.checked = true; }
        [...(b.personality||[]), ...(b.capabilities||[]), ...(b.rules||[])].forEach(val => {
            const cb = document.querySelector(`.check-card input[value="${val}"]`);
            if (cb) cb.checked = true;
        });
    }

    async saveBuilderPrompt() {
        const cfg = this.getBuilderConfig();
        const payload = { use_custom: true, mode: 'builder', builder: cfg, raw_content: '' };
        try {
            await this.api('POST', '/prompt-config', payload);
            if (document.getElementById('useCustomPrompt')) document.getElementById('useCustomPrompt').checked = true;
            this.updateSourceBadge(true);
            this.toast('✅ Prompt guardado. Reinicia el servidor para aplicarlo.');
        } catch (err) { this.toast(err.message, 'error'); }
    }

    async saveRawPrompt() {
        const raw = (document.getElementById('rawPromptInput')?.value || '').trim();
        if (!raw) { this.toast('El prompt no puede estar vacío', 'error'); return; }
        let content = raw;
        try { const p = JSON.parse(raw); content = p.system_prompt || p.content || raw; } catch {}
        try {
            await this.api('POST', '/prompt-config', { use_custom: true, mode: 'raw', raw_content: content, builder: {} });
            if (document.getElementById('useCustomPrompt')) document.getElementById('useCustomPrompt').checked = true;
            this.updateSourceBadge(true);
            this.toast('✅ Prompt activado. Reinicia el servidor para aplicarlo.');
        } catch (err) { this.toast(err.message, 'error'); }
    }

    async disableCustomPrompt() {
        try {
            await this.api('POST', '/prompt-config', { use_custom: false, mode: 'builder', raw_content: '', builder: {} });
            if (document.getElementById('useCustomPrompt')) document.getElementById('useCustomPrompt').checked = false;
            this.updateSourceBadge(false);
            this.toast('✅ Se usarán los archivos del sistema. Reinicia el servidor.');
        } catch (err) { this.toast(err.message, 'error'); }
    }

    async loadFilePrompts() {
        try {
            const prompts = await this.api('GET', '/prompts');
            const sel = document.getElementById('promptSelect');
            if (!sel) return;
            sel.innerHTML = prompts.map(p => `<option value="${p}">${p}</option>`).join('');
            if (prompts.length) {
                const def = prompts.includes('nova_default') ? 'nova_default' : prompts[0];
                sel.value = def;
                await this.loadPromptContent(def);
            }
        } catch {}
    }

    async loadPromptContent(name) {
        try {
            const data = await this.api('GET', `/prompts/${name}`);
            const el = document.getElementById('promptEditor');
            if (el) el.value = data.content;
        } catch (err) { this.toast(err.message, 'error'); }
    }

    async saveFilePrompt() {
        const name    = document.getElementById('promptSelect')?.value;
        const content = document.getElementById('promptEditor')?.value;
        if (!name || !content) { this.toast('Selecciona un prompt y agrega contenido', 'error'); return; }
        try {
            await this.api('PUT', `/prompts/${name}`, { name, content });
            this.toast('Archivos guardados (.yaml y .md)');
        } catch (err) { this.toast(err.message, 'error'); }
    }

    // ── TOOLS ─────────────────────────────────────────────────────────────────
    setupTools() {
        document.getElementById('btnSaveTools')?.addEventListener('click', () => {
            try { JSON.parse(document.getElementById('toolsEditor').value); this.toast('JSON válido. Reinicia el servidor para aplicarlo.'); }
            catch { this.toast('JSON inválido. Verifica la sintaxis.', 'error'); }
        });
    }

    async loadTools() {
        try {
            const res = await fetch('/static/js/../../../config/tools/default_tools.json');
            if (res.ok) { document.getElementById('toolsEditor').value = JSON.stringify(await res.json(), null, 2); return; }
        } catch {}
        document.getElementById('toolsEditor').value = '{\n  "tools": []\n}';
    }

    // ── SESSIONS ──────────────────────────────────────────────────────────────
    setupSessions() {
        document.getElementById('btnRefreshSessions')?.addEventListener('click', () => this.loadSessions());
    }

    async loadSessions() {
        const tbody = document.getElementById('sessionsBody');
        try {
            const data = await this.api('GET', '/sessions');
            if (!data.length) { tbody.innerHTML = '<tr><td colspan="4" class="empty-state">Sin sesiones activas</td></tr>'; return; }
            tbody.innerHTML = data.map(s => `
                <tr>
                    <td style="font-family:var(--font-mono);font-size:.75rem">${s.session_id.substring(0,12)}…</td>
                    <td>${s.source === 'web' ? '🌐 Web' : '📞 Asterisk'}</td>
                    <td>${s.duration}s</td>
                    <td><span class="pill ${s.active ? 'pill-green' : 'pill-red'}">${s.active ? 'Activa' : 'Finalizada'}</span></td>
                </tr>`).join('');
        } catch (err) { tbody.innerHTML = `<tr><td colspan="4" class="empty-state">Error: ${err.message}</td></tr>`; }
    }

    // ── LOGS ──────────────────────────────────────────────────────────────────
    setupLogs() {
        document.getElementById('btnRefreshLogs')?.addEventListener('click', () => this.loadLogs());
    }

    async loadLogs() {
        const tbody = document.getElementById('logsBody');
        try {
            const data = await this.api('GET', '/logs?limit=50');
            if (!data.length) { tbody.innerHTML = '<tr><td colspan="4" class="empty-state">Sin registros de llamadas</td></tr>'; return; }
            tbody.innerHTML = data.map(log => `
                <tr>
                    <td>${new Date(log.created_at).toLocaleString('es-MX')}</td>
                    <td>${log.source === 'web' ? '🌐 Web' : '📞 Asterisk'}</td>
                    <td>${parseFloat(log.duration || 0).toFixed(1)}s</td>
                    <td style="font-size:.75rem;font-family:var(--font-mono)">${log.actions_taken || '—'}</td>
                </tr>`).join('');
        } catch (err) { tbody.innerHTML = `<tr><td colspan="4" class="empty-state">Error: ${err.message}</td></tr>`; }
    }
}


document.addEventListener('DOMContentLoaded', () => {
    window.admin = new NovaAdmin();
});
