const API_BASE = '/api/admin';

const P_VALS = new Set(['human_sales','warm','formal','concise','detailed','empathetic','patient','proactive','confirm','repeat_before_transfer','list_options']);
const C_VALS = new Set(['transfer','directory','inventory','messages','general','schedule','support','faq','order_status']);
const R_VALS = new Set(['character_lock','no_hallucinations','cross_validation','synonym_search','no_personal_data','abuse_protection']);

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
    human_sales:'Actúa como un vendedor sumamente empático, paciente y muy humano. Prohíbe terminantemente el uso de términos robóticos, técnicos o clínicos como "abrumar", "saturar", "parámetros", "limitar" o "saturación". En su lugar, exprésate de manera muy cálida y amigable, guiando al usuario con naturalidad y facilitándole la elección con un tono conversacional fluido, cercano y servicial.',
    warm:'Sé cálido y amigable con el usuario.',
    formal:'Mantén formalidad en todo momento.',
    concise:'Sé conciso, no des explicaciones largas a menos que se pida.',
    detailed:'Da respuestas detalladas y completas.',
    empathetic:'Muestra empatía con el usuario.',
    patient:'Sé paciente y repite la información si es necesario.',
    proactive:'Anticipa las necesidades del usuario y ofrece ayuda proactivamente.',
    confirm:'Siempre confirma antes de realizar acciones importantes.',
    repeat_before_transfer:'Repite nombre y extensión antes de transferir.',
    list_options:'Lista múltiples opciones si hay ambigüedad.'
};
const CAP_MAP = {
    transfer:'- Transferir llamadas: Busca la extensión en el directorio y transfiere.',
    directory:'- Consultar directorio: Informa extensiones y departamentos.',
    inventory:'- Consultar inventario: Busca productos, precios y stock.',
    messages:'- Tomar mensajes: Si la persona no está disponible.',
    general:'- Información general: Responde preguntas sobre la empresa.',
    schedule:'- Agendar citas o reuniones.',
    support:'- Soporte técnico básico.',
    faq:'- Responder preguntas frecuentes (FAQs).',
    order_status:'- Informar estatus de pedidos o solicitudes.'
};
const RULE_MAP = {
    character_lock:'BAJO NINGUNA CIRCUNSTANCIA debes salirte de tu personaje.',
    no_hallucinations:'NO inventes nombres, extensiones ni productos que no estén en la base de datos.',
    cross_validation:'Si el usuario menciona un departamento, verifica que el resultado coincida antes de transferir.',
    synonym_search:'Si una búsqueda falla, intenta con sinónimos y sé transparente al respecto.',
    no_personal_data:'NUNCA compartas datos personales de empleados (emails personales, teléfonos).',
    abuse_protection:'Finaliza la llamada si detectas abuso o lenguaje inapropiado.'
};

const AGENT_PRESETS = [
    {
        id: 'blank', icon: '⬜', name: 'En Blanco', badge: '',
        desc: 'Agente sin personalidad predefinida. Configúralo desde cero.',
        traits: [
            { key: 'amabilidad',    label: '😊 Amabilidad',     value: 5 },
            { key: 'formalidad',    label: '🎩 Formalidad',     value: 5 },
            { key: 'paciencia',     label: '🧘 Paciencia',      value: 5 },
            { key: 'proactividad',  label: '🚀 Proactividad',   value: 5 },
            { key: 'detalle',       label: '🔍 Detalle',        value: 5 },
            { key: 'empatia',       label: '💛 Empatía',        value: 5 },
            { key: 'persuasion',    label: '🎯 Persuasión',     value: 5 },
            { key: 'concision',     label: '✂️ Concisión',      value: 5 },
        ],
        builder: {
            identity: { name: 'Nova', company: 'la empresa', role: 'asistente virtual' },
            language: 'es', tone: 'friendly', greeting: 'Hola, ¿en qué puedo ayudarle?',
            personality: [], capabilities: ['general'], rules: ['character_lock', 'no_hallucinations'],
            custom_instructions: ''
        }
    },
    {
        id: 'ventas', icon: '💰', name: 'Ventas', badge: '★ Popular',
        desc: 'Vendedor persuasivo, empático y cálido. Cierra tratos con naturalidad.',
        traits: [
            { key: 'amabilidad',    label: '😊 Amabilidad',     value: 9 },
            { key: 'formalidad',    label: '🎩 Formalidad',     value: 4 },
            { key: 'paciencia',     label: '🧘 Paciencia',      value: 8 },
            { key: 'proactividad',  label: '🚀 Proactividad',   value: 9 },
            { key: 'detalle',       label: '🔍 Detalle',        value: 7 },
            { key: 'empatia',       label: '💛 Empatía',        value: 10 },
            { key: 'persuasion',    label: '🎯 Persuasión',     value: 9 },
            { key: 'concision',     label: '✂️ Concisión',      value: 4 },
        ],
        builder: {
            identity: { name: 'Nova', company: 'la empresa', role: 'asistente de ventas' },
            language: 'es', tone: 'friendly', greeting: '¡Hola! Bienvenido, ¿en qué le puedo ayudar el día de hoy?',
            personality: ['human_sales', 'warm', 'proactive', 'empathetic'],
            capabilities: ['inventory', 'transfer', 'general', 'faq'],
            rules: ['character_lock', 'no_hallucinations', 'synonym_search'],
            custom_instructions: ''
        }
    },
    {
        id: 'soporte', icon: '🛠️', name: 'Soporte', badge: '',
        desc: 'Agente técnico paciente. Resuelve problemas paso a paso.',
        traits: [
            { key: 'amabilidad',    label: '😊 Amabilidad',     value: 7 },
            { key: 'formalidad',    label: '🎩 Formalidad',     value: 6 },
            { key: 'paciencia',     label: '🧘 Paciencia',      value: 10 },
            { key: 'proactividad',  label: '🚀 Proactividad',   value: 7 },
            { key: 'detalle',       label: '🔍 Detalle',        value: 9 },
            { key: 'empatia',       label: '💛 Empatía',        value: 8 },
            { key: 'persuasion',    label: '🎯 Persuasión',     value: 2 },
            { key: 'concision',     label: '✂️ Concisión',      value: 5 },
        ],
        builder: {
            identity: { name: 'Nova', company: 'la empresa', role: 'agente de soporte técnico' },
            language: 'es', tone: 'friendly', greeting: 'Hola, soy Nova de soporte técnico. Cuénteme, ¿cómo le puedo ayudar?',
            personality: ['patient', 'detailed', 'empathetic', 'confirm'],
            capabilities: ['support', 'faq', 'transfer', 'general', 'messages'],
            rules: ['character_lock', 'no_hallucinations', 'cross_validation'],
            custom_instructions: 'Guía al usuario paso a paso para resolver su problema. Si no puedes resolverlo, ofrece transferir con un especialista.'
        }
    },
    {
        id: 'finanzas', icon: '📊', name: 'Finanzas', badge: '',
        desc: 'Agente formal y preciso. Maneja datos financieros con cuidado.',
        traits: [
            { key: 'amabilidad',    label: '😊 Amabilidad',     value: 6 },
            { key: 'formalidad',    label: '🎩 Formalidad',     value: 9 },
            { key: 'paciencia',     label: '🧘 Paciencia',      value: 7 },
            { key: 'proactividad',  label: '🚀 Proactividad',   value: 5 },
            { key: 'detalle',       label: '🔍 Detalle',        value: 10 },
            { key: 'empatia',       label: '💛 Empatía',        value: 5 },
            { key: 'persuasion',    label: '🎯 Persuasión',     value: 3 },
            { key: 'concision',     label: '✂️ Concisión',      value: 7 },
        ],
        builder: {
            identity: { name: 'Nova', company: 'la empresa', role: 'asistente del departamento de finanzas' },
            language: 'es', tone: 'formal', greeting: 'Buenos días, soy Nova del departamento de finanzas. ¿En qué puedo asistirle?',
            personality: ['formal', 'detailed', 'confirm'],
            capabilities: ['general', 'transfer', 'messages', 'order_status'],
            rules: ['character_lock', 'no_hallucinations', 'no_personal_data', 'cross_validation'],
            custom_instructions: 'Maneja toda información financiera con extrema precisión. Siempre confirma montos y datos antes de proceder.'
        }
    },
    {
        id: 'atencion', icon: '📞', name: 'Atención', badge: '',
        desc: 'Recepcionista virtual. Canaliza llamadas al departamento correcto.',
        traits: [
            { key: 'amabilidad',    label: '😊 Amabilidad',     value: 8 },
            { key: 'formalidad',    label: '🎩 Formalidad',     value: 7 },
            { key: 'paciencia',     label: '🧘 Paciencia',      value: 8 },
            { key: 'proactividad',  label: '🚀 Proactividad',   value: 8 },
            { key: 'detalle',       label: '🔍 Detalle',        value: 5 },
            { key: 'empatia',       label: '💛 Empatía',        value: 7 },
            { key: 'persuasion',    label: '🎯 Persuasión',     value: 3 },
            { key: 'concision',     label: '✂️ Concisión',      value: 8 },
        ],
        builder: {
            identity: { name: 'Nova', company: 'la empresa', role: 'recepcionista virtual de atención telefónica' },
            language: 'es', tone: 'friendly', greeting: 'Hola, gracias por comunicarse. ¿Con quién desea hablar o en qué le puedo ayudar?',
            personality: ['warm', 'concise', 'proactive', 'confirm', 'repeat_before_transfer'],
            capabilities: ['transfer', 'directory', 'messages', 'general', 'faq'],
            rules: ['character_lock', 'no_hallucinations', 'cross_validation'],
            custom_instructions: 'Tu prioridad es identificar rápidamente con quién o con qué departamento necesita hablar el usuario y transferirlo eficientemente.'
        }
    },
    {
        id: 'tecnico', icon: '⚙️', name: 'Técnico', badge: '',
        desc: 'Ingeniero de soporte avanzado. Diagnóstico detallado y técnico.',
        traits: [
            { key: 'amabilidad',    label: '😊 Amabilidad',     value: 5 },
            { key: 'formalidad',    label: '🎩 Formalidad',     value: 7 },
            { key: 'paciencia',     label: '🧘 Paciencia',      value: 9 },
            { key: 'proactividad',  label: '🚀 Proactividad',   value: 6 },
            { key: 'detalle',       label: '🔍 Detalle',        value: 10 },
            { key: 'empatia',       label: '💛 Empatía',        value: 4 },
            { key: 'persuasion',    label: '🎯 Persuasión',     value: 2 },
            { key: 'concision',     label: '✂️ Concisión',      value: 3 },
        ],
        builder: {
            identity: { name: 'Nova', company: 'la empresa', role: 'ingeniero de soporte técnico avanzado' },
            language: 'es', tone: 'formal', greeting: 'Hola, soy Nova del equipo técnico. Describa su situación con el mayor detalle posible.',
            personality: ['patient', 'detailed', 'formal', 'confirm'],
            capabilities: ['support', 'faq', 'transfer', 'general'],
            rules: ['character_lock', 'no_hallucinations', 'cross_validation', 'synonym_search'],
            custom_instructions: 'Realiza diagnósticos técnicos paso a paso. Pide información específica del sistema, versiones y logs. Si el problema excede tu capacidad, transfiere al equipo de ingeniería.'
        }
    }
];

class NovaAdmin {
    constructor() {
        this.setupTabDataLoading();
        this.setupExtensions();
        this.setupInventory();
        this.setupPrompts();
        this.setupAgents();
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
            if (btn?.dataset.mode === 'agents') this.renderAgentCards();
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

        this.updateBuilderPreview();
    }

    updateSourceBadge(mode) {
        const badge = document.getElementById('promptStatusBadge');
        if (!badge) return;
        const modes = {
            builder: { text: '🎨 Constructor Visual', bg: 'var(--accent-dim)', color: 'var(--accent)', border: 'rgba(79,142,247,.3)' },
            raw:     { text: '📝 Texto / JSON', bg: 'rgba(52,211,153,.1)', color: '#34d399', border: 'rgba(52,211,153,.3)' },
            agent:   { text: '🤖 Agente Preconfigurado', bg: 'rgba(251,191,36,.1)', color: '#fbbf24', border: 'rgba(251,191,36,.3)' },
        };
        const m = modes[mode] || { text: '📂 Archivos del sistema', bg: 'rgba(103,232,249,.1)', color: 'var(--cyan)', border: 'rgba(103,232,249,.25)' };
        badge.textContent = m.text;
        badge.style.background = m.bg;
        badge.style.color = m.color;
        badge.style.borderColor = m.border;
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
            const mode = config.mode || 'none';
            this.updateSourceBadge(mode);

            // Cambiar la pestaña de modo activa en la UI de forma programática
            const tabName = mode === 'agent' ? 'agents' : (mode === 'raw' ? 'raw' : 'builder');
            document.querySelectorAll('.mode-tab').forEach(t => {
                if (t.dataset.mode === tabName) t.classList.add('active');
                else t.classList.remove('active');
            });
            document.querySelectorAll('.mode-panel').forEach(p => {
                if (p.id === `mode-${tabName}`) p.classList.add('active');
                else p.classList.remove('active');
            });

            if (mode === 'agent') {
                this._selectedAgentId = config.agent_id;
                this._selectedAgentSource = config.agent_source;
            }

            if (config.builder && Object.keys(config.builder).length) this.restoreBuilder(config.builder);
            if (config.raw_content) {
                const el = document.getElementById('rawPromptInput');
                if (el) el.value = config.raw_content;
            }

            await this.renderAgentCards();

            if (mode === 'agent' && this._selectedAgentId && this._selectedAgentSource) {
                this.selectAgent(this._selectedAgentId, this._selectedAgentSource);
                const ab = config.agent_builder || config.builder;
                if (ab && Object.keys(ab).length) {
                    const id = ab.identity || {};
                    if (id.name) document.getElementById('ag-name').value = id.name;
                    if (id.company) document.getElementById('ag-company').value = id.company;
                    if (id.role) document.getElementById('ag-role').value = id.role;
                    if (ab.greeting) document.getElementById('ag-greeting').value = ab.greeting;
                }
            }
        } catch (err) {
            this.updateSourceBadge('none');
            await this.renderAgentCards();
        }
        this.updateBuilderPreview();
    }

    restoreBuilder(b) {
        const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ''; };
        const id = b.identity || {};
        set('b-name', id.name); set('b-company', id.company); set('b-role', id.role);
        set('b-greeting', b.greeting); set('b-custom-instructions', b.custom_instructions);
        
        if (b.language) { const r = document.querySelector(`[name="b-language"][value="${b.language}"]`); if (r) r.checked = true; }
        if (b.tone) { const r = document.querySelector(`[name="b-tone"][value="${b.tone}"]`); if (r) r.checked = true; }
        
        // Limpiar todos los checkboxes primero
        document.querySelectorAll('.check-card input[type="checkbox"]').forEach(cb => cb.checked = false);
        
        // Marcar los que vienen en la config
        [...(b.personality||[]), ...(b.capabilities||[]), ...(b.rules||[])].forEach(val => {
            const cb = document.querySelector(`.check-card input[value="${val}"]`);
            if (cb) cb.checked = true;
        });
    }

    async saveBuilderPrompt() {
        const cfg = this.getBuilderConfig();
        const payload = { mode: 'builder', builder: cfg, raw_content: '' };
        try {
            await this.api('POST', '/prompt-config', payload);
            this.updateSourceBadge('builder');
            this.toast('✅ Prompt del Constructor guardado y activado.');
        } catch (err) { this.toast(err.message, 'error'); }
    }

    async saveRawPrompt() {
        const raw = (document.getElementById('rawPromptInput')?.value || '').trim();
        if (!raw) { this.toast('El prompt no puede estar vacío', 'error'); return; }
        let content = raw;
        try { const p = JSON.parse(raw); content = p.system_prompt || p.content || raw; } catch {}
        try {
            await this.api('POST', '/prompt-config', { mode: 'raw', raw_content: content, builder: {} });
            this.updateSourceBadge('raw');
            this.toast('✅ Prompt de texto activado.');
        } catch (err) { this.toast(err.message, 'error'); }
    }

    // ── AGENT PRESETS ─────────────────────────────────────────────────────────
    setupAgents() {
        this._selectedAgentId = null;
        this._selectedAgentSource = null;
        this._agentTraitValues = {};
        this._customAgents = [];
        document.getElementById('btnApplyAgent')?.addEventListener('click', () => this.applyAgent());
        document.getElementById('btnSaveAgent')?.addEventListener('click', () => this.saveCustomAgent());
    }

    _getIntensityClass(val) {
        if (val <= 3) return 'intensity-low';
        if (val <= 6) return 'intensity-mid';
        if (val <= 8) return 'intensity-high';
        return 'intensity-max';
    }

    _intensityLabel(val) {
        if (val <= 2) return 'Mínimo';
        if (val <= 4) return 'Bajo';
        if (val <= 6) return 'Medio';
        if (val <= 8) return 'Alto';
        return 'Intenso';
    }

    async renderAgentCards() {
        const grid = document.getElementById('agentGrid');
        if (!grid) return;

        try { this._customAgents = await this.api('GET', '/custom-agents'); } catch { this._customAgents = []; }

        let html = AGENT_PRESETS.map(a => `
            <div class="agent-card${this._selectedAgentId === a.id && this._selectedAgentSource === 'preset' ? ' selected' : ''}" data-agent="${a.id}" data-source="preset">
                ${a.badge ? `<span class="agent-card-badge">${a.badge}</span>` : ''}
                <span class="agent-card-icon">${a.icon}</span>
                <span class="agent-card-name">${a.name}</span>
                <span class="agent-card-desc">${a.desc}</span>
            </div>
        `).join('');

        html += this._customAgents.map(a => `
            <div class="agent-card custom${this._selectedAgentId === a.id && this._selectedAgentSource === 'custom' ? ' selected' : ''}" data-agent="${a.id}" data-source="custom">
                <button class="agent-card-delete" data-delete="${a.id}" title="Eliminar">✕</button>
                <span class="agent-card-badge">Guardado</span>
                <span class="agent-card-icon">🧩</span>
                <span class="agent-card-name">${a.profile_name || 'Sin nombre'}</span>
                <span class="agent-card-desc">${a.builder?.identity?.role || 'Agente personalizado'}</span>
            </div>
        `).join('');

        grid.innerHTML = html;

        grid.querySelectorAll('.agent-card').forEach(card => {
            card.addEventListener('click', e => {
                if (e.target.closest('.agent-card-delete')) return;
                this.selectAgent(card.dataset.agent, card.dataset.source);
            });
        });
        grid.querySelectorAll('.agent-card-delete').forEach(btn => {
            btn.addEventListener('click', e => {
                e.stopPropagation();
                this.deleteCustomAgent(btn.dataset.delete);
            });
        });
    }

    selectAgent(agentId, source = 'preset') {
        this._selectedAgentId = agentId;
        this._selectedAgentSource = source;

        let preset, profileName = '';
        if (source === 'custom') {
            const custom = this._customAgents.find(a => a.id === agentId);
            if (!custom) return;
            profileName = custom.profile_name || '';
            preset = {
                id: custom.id, icon: '🧩', name: custom.profile_name || 'Personalizado',
                desc: custom.builder?.identity?.role || 'Agente personalizado',
                traits: custom.traits || AGENT_PRESETS[0].traits,
                builder: custom.builder || AGENT_PRESETS[0].builder
            };
        } else {
            preset = AGENT_PRESETS.find(a => a.id === agentId);
            if (!preset) return;
            profileName = preset.name;
        }

        this._agentTraitValues = {};
        preset.traits.forEach(t => { this._agentTraitValues[t.key] = t.value; });

        document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('selected'));
        const sel = document.querySelector(`.agent-card[data-agent="${agentId}"][data-source="${source}"]`);
        if (sel) sel.classList.add('selected');

        document.getElementById('agentCfgIcon').textContent = preset.icon;
        document.getElementById('agentCfgTitle').textContent = `Configurar: ${preset.name}`;
        document.getElementById('agentCfgSub').textContent = preset.desc;

        const identity = preset.builder?.identity || {};
        document.getElementById('agentProfileName').value = profileName;
        document.getElementById('ag-name').value = identity.name || 'Nova';
        document.getElementById('ag-company').value = identity.company || 'la empresa';
        document.getElementById('ag-role').value = identity.role || 'asistente virtual';
        document.getElementById('ag-greeting').value = preset.builder?.greeting || 'Hola, ¿en qué puedo ayudarle?';

        const traitGrid = document.getElementById('traitGrid');
        traitGrid.innerHTML = preset.traits.map(t => {
            const ic = this._getIntensityClass(t.value);
            const il = this._intensityLabel(t.value);
            return `
            <div class="trait-row">
                <span class="trait-label">${t.label} <span class="trait-level ${ic}">${il}</span></span>
                <input type="range" class="trait-slider ${ic}" min="1" max="10" value="${t.value}" data-trait="${t.key}">
                <span class="trait-value ${ic}" data-trait-value="${t.key}">${t.value}</span>
            </div>`;
        }).join('');

        traitGrid.querySelectorAll('.trait-slider').forEach(slider => {
            slider.addEventListener('input', () => {
                const key = slider.dataset.trait;
                const val = parseInt(slider.value, 10);
                this._agentTraitValues[key] = val;
                const ic = this._getIntensityClass(val);
                const il = this._intensityLabel(val);
                const display = traitGrid.querySelector(`[data-trait-value="${key}"]`);
                if (display) {
                    display.textContent = val;
                    display.className = `trait-value ${ic}`;
                }
                slider.className = `trait-slider ${ic}`;
                const label = slider.closest('.trait-row')?.querySelector('.trait-level');
                if (label) { label.textContent = il; label.className = `trait-level ${ic}`; }
            });
        });

        document.getElementById('agentConfigPanel').classList.add('active');
    }

    _getAgentBuilderFromForm() {
        const preset = this._selectedAgentSource === 'custom'
            ? (this._customAgents.find(a => a.id === this._selectedAgentId) || {}).builder || AGENT_PRESETS[0].builder
            : (AGENT_PRESETS.find(a => a.id === this._selectedAgentId) || AGENT_PRESETS[0]).builder;

        const baseBuilder = JSON.parse(JSON.stringify(preset));
        baseBuilder.identity = {
            name: document.getElementById('ag-name')?.value || 'Nova',
            company: document.getElementById('ag-company')?.value || 'la empresa',
            role: document.getElementById('ag-role')?.value || 'asistente virtual',
        };
        baseBuilder.greeting = document.getElementById('ag-greeting')?.value || 'Hola, ¿en qué puedo ayudarle?';

        const traitInstructions = this._traitsToCustomInstructions(this._agentTraitValues);
        const baseInstr = preset.custom_instructions || '';
        baseBuilder.custom_instructions = [baseInstr, traitInstructions].filter(Boolean).join('\n\n');

        return baseBuilder;
    }

    _traitsToCustomInstructions(traits) {
        const lines = [];
        const T = (key) => traits[key] || 5;

        if (T('amabilidad') >= 8)
            lines.push('Sé extremadamente amable y cálido en cada interacción. Usa un tono cercano y servicial.');
        else if (T('amabilidad') >= 6)
            lines.push('Mantén un trato amable y cordial con el usuario.');
        else if (T('amabilidad') <= 3)
            lines.push('Sé directo y profesional, sin adornos innecesarios.');

        if (T('formalidad') >= 8)
            lines.push('Utiliza un lenguaje muy formal y profesional. Trata al usuario de usted.');
        else if (T('formalidad') <= 3)
            lines.push('Usa un lenguaje casual y cercano. Tutea al usuario si es apropiado.');

        if (T('paciencia') >= 8)
            lines.push('Ten mucha paciencia. Repite información cuantas veces sea necesario sin mostrar frustración.');
        else if (T('paciencia') <= 3)
            lines.push('Sé eficiente con el tiempo. Si el usuario se desvía, redirige la conversación.');

        if (T('proactividad') >= 8)
            lines.push('Anticípate a las necesidades del usuario. Ofrece opciones y sugerencias sin que te las pidan.');
        else if (T('proactividad') <= 3)
            lines.push('Responde solo lo que te pregunten. No ofrezcas información adicional no solicitada.');

        if (T('detalle') >= 8)
            lines.push('Da respuestas detalladas y completas. Incluye toda la información relevante.');
        else if (T('detalle') <= 3)
            lines.push('Sé breve y conciso. Responde con lo mínimo necesario.');

        if (T('empatia') >= 8)
            lines.push('Muestra empatía genuina. Reconoce las emociones del usuario y responde con sensibilidad.');
        else if (T('empatia') <= 3)
            lines.push('Mantente objetivo y enfocado en los hechos.');

        if (T('persuasion') >= 8)
            lines.push('Sé persuasivo y convincente. Destaca beneficios y crea sentido de urgencia cuando sea apropiado.');
        else if (T('persuasion') <= 3)
            lines.push('Presenta la información de forma neutral sin intentar persuadir.');

        if (T('concision') >= 8)
            lines.push('Sé extremadamente conciso. Responde en la menor cantidad de palabras posible.');
        else if (T('concision') <= 3)
            lines.push('Puedes extenderte en tus explicaciones para asegurar claridad total.');

        return lines.join('\n');
    }

    async applyAgent() {
        if (!this._selectedAgentId) { this.toast('Selecciona un agente primero', 'error'); return; }
        const builder = this._getAgentBuilderFromForm();
        const name = document.getElementById('agentProfileName')?.value || 'Agente';
        const payload = {
            mode: 'agent',
            agent_id: this._selectedAgentId,
            agent_source: this._selectedAgentSource,
            profile_name: name,
            agent_builder: builder,
            raw_content: ''
        };
        try {
            await this.api('POST', '/prompt-config', payload);
            this.updateSourceBadge('agent');
            this.updateBuilderPreview();
            this.toast(`✅ Agente "${name}" aplicado y activado.`);
        } catch (err) { this.toast(err.message, 'error'); }
    }

    async saveCustomAgent() {
        if (!this._selectedAgentId) { this.toast('Selecciona un agente primero', 'error'); return; }
        const profileName = (document.getElementById('agentProfileName')?.value || '').trim();
        if (!profileName) { this.toast('Escribe un nombre para el perfil', 'error'); return; }

        const builder = this._getAgentBuilderFromForm();
        const traits = AGENT_PRESETS[0].traits.map(t => ({
            ...t, value: this._agentTraitValues[t.key] || t.value
        }));

        const data = { profile_name: profileName, builder, traits };
        try {
            await this.api('POST', '/custom-agents', data);
            this.toast(`💾 Perfil "${profileName}" guardado.`);
            await this.renderAgentCards();
        } catch (err) { this.toast(err.message, 'error'); }
    }

    async deleteCustomAgent(agentId) {
        if (!confirm('¿Eliminar este perfil de agente?')) return;
        try {
            await this.api('DELETE', `/custom-agents/${agentId}`);
            if (this._selectedAgentId === agentId) {
                this._selectedAgentId = null;
                document.getElementById('agentConfigPanel').classList.remove('active');
            }
            this.toast('Perfil eliminado.');
            await this.renderAgentCards();
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
                    <td>${log.created_at ? log.created_at.replace('T', ' ').substring(0, 19) : '—'}</td>
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
