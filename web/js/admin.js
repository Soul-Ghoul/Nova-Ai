const API_BASE = '/api/admin';

const HEADER_MAP = {
    extensions: {
        title: 'Directorio de Extensiones',
        sub: 'Registra y administra las extensiones telefónicas de los departamentos y empleados.'
    },
    inventory: {
        title: 'Catálogo de Inventario',
        sub: 'Administra los productos de tecnología, precios, stock y etiquetas de búsqueda.'
    },
    prompts: {
        title: 'System Prompt del Agente',
        sub: 'Diseña la identidad, tono, personalidad y capacidades operativas de la IA.'
    },
    tokens: {
        title: 'Panel de Consumo de Tokens',
        sub: 'Controla el consumo de tokens de entrada/salida y analiza los costos acumulados.'
    },
    users: {
        title: 'Gestión de Usuarios',
        sub: 'Administra las cuentas de usuario y los privilegios de acceso al panel.'
    },
    profile: {
        title: 'Mi Perfil y Ajustes',
        sub: 'Gestiona tus datos de acceso a la cuenta y configura la conexión de la base de datos externa.'
    }
};

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

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

class NovaAdmin {
    constructor() {
        this.adminUser = null;
        this.adminUserId = null;
        this.inventoryData = [];
        this.inventoryPage = 1;
        this.inventoryLimit = 10;
        
        this.setupTabDataLoading();
        this.setupExtensions();
        this.setupInventory();
        this.setupDataSource();
        this.setupPrompts();
        this.setupAgents();
        this.setupUsers();
        this.setupAuth();
        this.setupOdooAgents();
        this.init();
    }

    async init() {
        try {
            const res = await fetch('/api/auth/session');
            if (res.ok) {
                const d = await res.json();
                if (d.authenticated && d.user) {
                    this.adminUser = d.user;
                    this.adminUserId = d.user.id;
                    
                    if (this.adminUser && this.adminUser.role === 'admin') {
                        const tabBtn = document.getElementById('tabUsersBtn');
                        if (tabBtn) tabBtn.style.display = 'inline-block';
                    }
                }
            }
        } catch (e) {
            console.error('Error verificando sesión', e);
        }
        await this.loadExtensions();
        await this.checkOdooVisibility();
        this.updatePageHeader('extensions');
    }

    async api(method, path, body = null) {
        const headers = { 'Content-Type': 'application/json' };
        if (['POST', 'PUT', 'DELETE'].includes(method.toUpperCase())) {
            const csrf = getCookie('csrftoken');
            if (csrf) headers['X-CSRFToken'] = csrf;
        }
        const opts = { method, headers };
        if (body) opts.body = JSON.stringify(body);
        const res = await fetch(`${API_BASE}${path}`, opts);
        
        if (res.status === 401) {
            window.location.reload();
            throw new Error('Sesión expirada o no autorizada.');
        }
        
        if (!res.ok) {
            const e = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(e.detail || 'Error de API');
        }
        return res.json();
    }

    setupAuth() {
        const btnLogout = document.getElementById('btnLogout');
        btnLogout?.addEventListener('click', async () => {
            if (!confirm('¿Deseas cerrar sesión?')) return;
            try {
                await fetch('/api/auth/logout', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCookie('csrftoken') || '' }
                });
            } catch (err) {
                console.error('Error al cerrar sesión', err);
            }
            window.location.reload();
        });
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
            this.updatePageHeader(name);
            if (name === 'inventory')  this.loadInventory();
            if (name === 'prompts')    this.loadPromptPanel();
            if (name === 'database')   this.loadDatabaseConfig();
            if (name === 'users')      this.loadUsers();
        });

        document.getElementById('promptModeTabs')?.addEventListener('click', e => {
            const btn = e.target.closest('.mode-tab');
            if (btn?.dataset.mode === 'agents') this.renderAgentCards();
            if (btn?.dataset.mode === 'odoo-agents') this.loadOdooAgents();
        });

        document.getElementById('btnProfile')?.addEventListener('click', () => {
            const sidebar = document.getElementById('profileSidebar');
            const overlay = document.getElementById('sidebarOverlay');
            sidebar?.classList.add('open');
            overlay?.classList.add('open');
            
            this.loadDataSource();
            
            if (this.adminUser) {
                const usernameEl = document.getElementById('profUsername');
                if (usernameEl) usernameEl.value = this.adminUser.username || '';
                const roleEl = document.getElementById('profRole');
                if (roleEl) roleEl.value = this.adminUser.role === 'admin' ? 'Administrador' : 'Usuario Normal';
                
                const name = this.adminUser.username || 'Admin';
                const avatarEl = document.querySelector('.profile-admin-avatar');
                if (avatarEl) avatarEl.textContent = name.charAt(0).toUpperCase();
                const nameEl = document.getElementById('sidebarAdminName');
                if (nameEl) nameEl.textContent = name;
                const sidebarRoleEl = document.querySelector('.profile-admin-role');
                if (sidebarRoleEl) sidebarRoleEl.textContent = this.adminUser.role === 'admin' ? 'Super User' : 'Standard User';
            }
        });

        const closeSidebar = () => {
            document.getElementById('profileSidebar')?.classList.remove('open');
            document.getElementById('sidebarOverlay')?.classList.remove('open');
        };
        document.getElementById('btnCloseProfileSidebar')?.addEventListener('click', closeSidebar);
        document.getElementById('sidebarOverlay')?.addEventListener('click', closeSidebar);
    }

    updatePageHeader(tabName) {
        const titleEl = document.getElementById('mainPageTitle');
        const subEl = document.getElementById('mainPageSub');
        const info = HEADER_MAP[tabName] || {
            title: 'Configuración del Agente',
            sub: 'Administra extensiones, inventario, prompts del sistema y monitorea la actividad'
        };
        if (titleEl) titleEl.textContent = info.title;
        if (subEl) subEl.textContent = info.sub;
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
                category:     document.getElementById('prodCategory').value.trim(),
                brand:        document.getElementById('prodBrand').value.trim(),
                tags:         document.getElementById('prodTags').value.trim()
            };
            if (!data.product_name) { this.toast('El nombre es requerido', 'error'); return; }
            try {
                await this.api('POST', '/inventory', data);
                this.toast('Producto agregado');
                ['prodName','prodDesc','prodPrice','prodStock','prodCategory','prodBrand','prodTags'].forEach(id => document.getElementById(id).value = '');
                await this.loadInventory();
            } catch (err) { this.toast(err.message, 'error'); }
        });
    }

    async loadInventory() {
        try {
            if (this.activeSourceType === undefined) {
                try {
                    const config = await this.api('GET', '/agent-data-source');
                    this.activeSourceType = config.source_type || 'internal';
                } catch (e) {
                    this.activeSourceType = 'internal';
                }
            }
            
            const isOdoo = this.activeSourceType === 'odoo';
            const addCard = document.getElementById('cardAddProduct');
            if (addCard) addCard.style.display = isOdoo ? 'none' : 'block';

            const data = await this.api('GET', '/inventory');
            this.inventoryData = data || [];
            this.inventoryPage = 1;
            this.renderInventory();
        } catch (err) {
            const tbody = document.getElementById('inventoryBody');
            if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Error: ${err.message}</td></tr>`;
        }
    }

    renderInventory() {
        const tbody = document.getElementById('inventoryBody');
        const pagEl = document.getElementById('inventoryPagination');
        if (!tbody) return;

        const isOdoo = this.activeSourceType === 'odoo';
        const total = this.inventoryData.length;

        if (!total) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No hay productos en inventario</td></tr>';
            if (pagEl) pagEl.innerHTML = '';
            return;
        }

        const maxPage = Math.ceil(total / this.inventoryLimit);
        if (this.inventoryPage > maxPage) this.inventoryPage = maxPage;
        if (this.inventoryPage < 1) this.inventoryPage = 1;

        const start = (this.inventoryPage - 1) * this.inventoryLimit;
        const end = Math.min(start + this.inventoryLimit, total);
        const pageData = this.inventoryData.slice(start, end);

        tbody.innerHTML = pageData.map(item => {
            const stock = parseInt(item.stock);
            const sc = stock > 5 ? 'pill-green' : stock > 0 ? 'pill-amber' : 'pill-red';
            const tagsHtml = item.tags
                ? item.tags.split(',').map(t => t.trim()).filter(Boolean)
                    .map(t => `<span style="display:inline-block;background:rgba(79,142,247,.15);color:var(--accent);border:1px solid rgba(79,142,247,.3);border-radius:4px;padding:1px 6px;font-size:.68rem;margin:1px">${t}</span>`).join('')
                : '';
            return `<tr>
                <td><div><strong>${item.product_name}</strong></div>
                    ${item.description ? `<div style="font-size:.75rem;color:var(--text-3)">${item.description}</div>` : ''}
                    ${tagsHtml ? `<div style="margin-top:3px">${tagsHtml}</div>` : ''}</td>
                <td>${item.brand || '—'}</td>
                <td>${item.category || '—'}</td>
                <td style="color:#34d399;font-weight:500">$${parseFloat(item.price).toLocaleString('es-MX',{minimumFractionDigits:2})}</td>
                <td><span class="pill ${sc}">${stock} uds.</span></td>
                <td>${isOdoo 
                    ? `<span style="font-size:.72rem;color:var(--text-3);border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.02);padding:2px 8px;border-radius:4px;">Solo Lectura</span>`
                    : `<button class="btn-danger" onclick="window.admin.deleteProduct(${item.id})">Eliminar</button>`
                }</td>
            </tr>`;
        }).join('');

        if (pagEl) {
            pagEl.innerHTML = `
                <span style="font-size:0.8rem;color:var(--text-2)">Mostrando ${start + 1}-${end} de ${total}</span>
                <div style="display:flex;gap:4px">
                    <button class="btn-ghost" id="btnPrevInv" ${this.inventoryPage === 1 ? 'disabled style="opacity:0.4;cursor:default;"' : ''} style="padding:4px 10px;font-size:0.8rem">&lt;</button>
                    <span style="display:flex;align-items:center;padding:0 8px;font-size:0.8rem;font-weight:500">${this.inventoryPage} / ${maxPage}</span>
                    <button class="btn-ghost" id="btnNextInv" ${this.inventoryPage === maxPage ? 'disabled style="opacity:0.4;cursor:default;"' : ''} style="padding:4px 10px;font-size:0.8rem">&gt;</button>
                </div>
            `;

            document.getElementById('btnPrevInv')?.addEventListener('click', () => {
                if (this.inventoryPage > 1) {
                    this.inventoryPage--;
                    this.renderInventory();
                }
            });

            document.getElementById('btnNextInv')?.addEventListener('click', () => {
                if (this.inventoryPage < maxPage) {
                    this.inventoryPage++;
                    this.renderInventory();
                }
            });
        }
    }

    async deleteProduct(id) {
        if (!confirm('¿Eliminar este producto?')) return;
        try { await this.api('DELETE', `/inventory/${id}`); this.toast('Eliminado'); await this.loadInventory(); }
        catch (err) { this.toast(err.message, 'error'); }
    }

    // ── DATA SOURCE ──────────────────────────────────────────────────────────
    setupDataSource() {
        const select = document.getElementById('dsSourceType');
        select?.addEventListener('change', () => this._toggleDsFields());

        document.getElementById('btnSaveDataSource')?.addEventListener('click', () => this.saveDataSource());
        document.getElementById('btnTestDataSource')?.addEventListener('click', () => this.testDataSource());
    }

    _isValidEmail(value) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test((value || '').trim());
    }

    _validatePostgresConnectionString(value) {
        const connectionString = (value || '').trim();
        if (!connectionString) return 'La URL de conexión PostgreSQL es requerida.';

        let parsed;
        try {
            parsed = new URL(connectionString);
        } catch (_) {
            return 'La URL de conexión PostgreSQL tiene un formato inválido.';
        }

        if (!['postgres:', 'postgresql:'].includes(parsed.protocol)) {
            return 'La URL de conexión PostgreSQL debe iniciar con postgres:// o postgresql://.';
        }

        if (!parsed.hostname) {
            return 'La URL de conexión PostgreSQL debe incluir un host válido.';
        }

        if (parsed.port && !/^\d+$/.test(parsed.port)) {
            return 'El puerto de PostgreSQL debe ser numérico.';
        }

        return '';
    }

    _validateDataSourceForm(sourceType, payload) {
        if (sourceType === 'postgres_local' || sourceType === 'postgres_railway') {
            return this._validatePostgresConnectionString(payload.pg_connection_string);
        }

        if (sourceType === 'odoo' && payload.odoo_user && !this._isValidEmail(payload.odoo_user)) {
            return 'El campo Usuario / Email de Odoo debe tener un formato de correo válido.';
        }

        return '';
    }

    _toggleDsFields() {
        const type = document.getElementById('dsSourceType')?.value || 'internal';
        const pgFields = document.getElementById('dsPgFields');
        const odooFields = document.getElementById('dsOdooFields');
        if (pgFields) pgFields.style.display = (type === 'postgres_local' || type === 'postgres_railway') ? 'block' : 'none';
        if (odooFields) odooFields.style.display = type === 'odoo' ? 'block' : 'none';
        document.getElementById('dsTestResult').style.display = 'none';
    }

    _updateDsBadge(sourceType) {
        const badge = document.getElementById('dsActiveBadge');
        if (!badge) return;
        const map = {
            internal:        { text: '🗃️ BD Interna', bg: 'var(--accent-dim)', color: 'var(--accent)', border: 'rgba(79,142,247,.3)' },
            postgres_local:  { text: '🐘 PostgreSQL Local', bg: 'rgba(52,211,153,.1)', color: '#34d399', border: 'rgba(52,211,153,.3)' },
            postgres_railway: { text: '🚂 PostgreSQL Railway', bg: 'rgba(251,191,36,.1)', color: '#fbbf24', border: 'rgba(251,191,36,.3)' },
            odoo:            { text: '🟣 Odoo JSON-2', bg: 'rgba(124,94,245,.12)', color: '#7c5ef5', border: 'rgba(124,94,245,.3)' },
        };
        const m = map[sourceType] || map.internal;
        badge.textContent = m.text;
        badge.style.background = m.bg;
        badge.style.color = m.color;
        badge.style.borderColor = m.border;
    }

    async loadDataSource() {
        try {
            const config = await this.api('GET', '/agent-data-source');
            const select = document.getElementById('dsSourceType');
            if (select) select.value = config.source_type || 'internal';

            document.getElementById('dsPgConnString').value = config.pg_connection_string || '';
            document.getElementById('dsOdooUrl').value = config.odoo_url || '';
            document.getElementById('dsOdooDb').value = config.odoo_db || '';
            document.getElementById('dsOdooApiKey').value = config.odoo_api_key || '';
            document.getElementById('dsOdooUser').value = config.odoo_user || '';

            this.activeSourceType = config.source_type || 'internal';
            this._toggleDsFields();
            this._updateDsBadge(config.source_type || 'internal');
        } catch (err) {
            this.activeSourceType = 'internal';
            this._updateDsBadge('internal');
        }
    }

    async saveDataSource() {
        const sourceType = document.getElementById('dsSourceType')?.value || 'internal';
        const payload = {
            source_type: sourceType,
            pg_connection_string: document.getElementById('dsPgConnString')?.value || '',
            odoo_url: document.getElementById('dsOdooUrl')?.value || '',
            odoo_db: document.getElementById('dsOdooDb')?.value || '',
            odoo_api_key: document.getElementById('dsOdooApiKey')?.value || '',
            odoo_user: document.getElementById('dsOdooUser')?.value || '',
        };

        const validationError = this._validateDataSourceForm(sourceType, payload);
        if (validationError) {
            this.toast(validationError, 'error');
            return;
        }

        try {
            const res = await this.api('POST', '/agent-data-source/save', payload);
            this.activeSourceType = sourceType;
            this._updateDsBadge(sourceType);
            await this.checkOdooVisibility();
            this.toast(res.message || 'Configuración guardada');
        } catch (err) {
            this.toast(err.message, 'error');
        }
    }

    async testDataSource() {
        const sourceType = document.getElementById('dsSourceType')?.value || 'internal';
        const resultEl = document.getElementById('dsTestResult');
        const innerEl = resultEl?.querySelector('div');
        resultEl.style.display = 'block';
        innerEl.textContent = '⏳ Probando conexión...';
        innerEl.style.background = 'var(--bg-input)';
        innerEl.style.color = 'var(--text-2)';
        innerEl.style.border = '1px solid var(--border)';

        const payload = {
            source_type: sourceType,
            pg_connection_string: document.getElementById('dsPgConnString')?.value || '',
            odoo_url: document.getElementById('dsOdooUrl')?.value || '',
            odoo_db: document.getElementById('dsOdooDb')?.value || '',
            odoo_api_key: document.getElementById('dsOdooApiKey')?.value || '',
            odoo_user: document.getElementById('dsOdooUser')?.value || '',
        };

        const validationError = this._validateDataSourceForm(sourceType, payload);
        if (validationError) {
            innerEl.textContent = `❌ ${validationError}`;
            innerEl.style.background = 'rgba(248,113,113,.08)';
            innerEl.style.color = '#f87171';
            innerEl.style.border = '1px solid rgba(248,113,113,.3)';
            return;
        }

        try {
            const res = await this.api('POST', '/agent-data-source/test', payload);
            const cleanMsg = (msg) => {
                if (typeof msg === 'string') {
                    const lowerMsg = msg.toLowerCase();
                    if (lowerMsg.includes('<html') || lowerMsg.includes('<body') || lowerMsg.includes('<script') || lowerMsg.includes('</html')) {
                        return 'El servidor de Odoo respondió con una página web (HTML). Verifica que la URL de Odoo y el subdominio sean correctos.';
                    }
                }
                return msg;
            };
            if (res.success) {
                innerEl.textContent = `✅ ${cleanMsg(res.message)}`;
                innerEl.style.background = 'rgba(52,211,153,.08)';
                innerEl.style.color = '#34d399';
                innerEl.style.border = '1px solid rgba(52,211,153,.3)';
            } else {
                innerEl.textContent = `❌ ${cleanMsg(res.message)}`;
                innerEl.style.background = 'rgba(248,113,113,.08)';
                innerEl.style.color = '#f87171';
                innerEl.style.border = '1px solid rgba(248,113,113,.3)';
            }
        } catch (err) {
            const msg = err.message || '';
            const lowerMsg = msg.toLowerCase();
            const cleanMsg = (lowerMsg.includes('<html') || lowerMsg.includes('<body') || lowerMsg.includes('<script') || lowerMsg.includes('</html'))
                ? 'El servidor respondió con código HTML en lugar de JSON. Verifica la configuración.'
                : msg;
            innerEl.textContent = `❌ Error: ${cleanMsg}`;
            innerEl.style.background = 'rgba(248,113,113,.08)';
            innerEl.style.color = '#f87171';
            innerEl.style.border = '1px solid rgba(248,113,113,.3)';
        }
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

        document.getElementById('btnActivateBuilder')?.addEventListener('click', () => this.saveBuilderPrompt());
        document.getElementById('btnSaveBuilderAgent')?.addEventListener('click', () => this.saveBuilderAgent());
        document.getElementById('btnActivateRaw')?.addEventListener('click', () => this.saveRawPrompt());

        this.updateBuilderPreview();
        this.renderBuilderAgentCards();
    }

    updateSourceBadge(mode, agentId = null) {
        const badge = document.getElementById('promptStatusBadge');
        if (!badge) return;
        
        let m;
        if (mode === 'builder') {
            m = { text: '🎨 Constructor Visual', bg: 'var(--accent-dim)', color: 'var(--accent)', border: 'rgba(79,142,247,.3)' };
        } else if (mode === 'raw') {
            m = { text: '📝 Texto / JSON', bg: 'rgba(52,211,153,.1)', color: '#34d399', border: 'rgba(52,211,153,.3)' };
        } else if (mode === 'agent') {
            if (agentId === 'odoo_sales' || agentId === 'odoo_vendor_support' || (agentId && agentId.startsWith('odoo_'))) {
                m = { text: '🟣 Agente Odoo', bg: 'rgba(168,85,247,.1)', color: '#a855f7', border: 'rgba(168,85,247,.3)' };
            } else {
                m = { text: '🤖 Agente Preconfigurado', bg: 'rgba(251,191,36,.1)', color: '#fbbf24', border: 'rgba(251,191,36,.3)' };
            }
        } else {
            m = { text: '📂 Archivos del sistema', bg: 'rgba(103,232,249,.1)', color: 'var(--cyan)', border: 'rgba(103,232,249,.25)' };
        }
        
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
            await this.checkOdooVisibility();
            const config = await this.api('GET', '/prompt-config');
            const mode = config.mode || 'none';
            const agentId = config.agent_id || null;
            this.updateSourceBadge(mode, agentId);

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

            if (config.builder && typeof config.builder === 'object' && Object.keys(config.builder).length) this.restoreBuilder(config.builder);
            if (config.raw_content) {
                const el = document.getElementById('rawPromptInput');
                if (el) el.value = config.raw_content;
            }

            await this.renderAgentCards();
            await this.renderBuilderAgentCards();

            if (mode === 'agent' && this._selectedAgentId && this._selectedAgentSource) {
                const isOdoo = this._selectedAgentId.startsWith('odoo_');
                if (isOdoo) {
                    const odooTab = document.querySelector('[data-mode="odoo-agents"]');
                    if (odooTab) odooTab.click();
                    await this.loadOdooAgents();
                    this.selectOdooAgent(this._selectedAgentId);
                } else {
                    this.selectAgent(this._selectedAgentId, this._selectedAgentSource);
                    const ab = config.agent_builder || config.builder;
                    if (ab && typeof ab === 'object' && Object.keys(ab).length) {
                        const id = ab.identity || {};
                        if (id.name) document.getElementById('ag-name').value = id.name;
                        if (id.company) document.getElementById('ag-company').value = id.company;
                        if (id.role) document.getElementById('ag-role').value = id.role;
                        if (ab.greeting) document.getElementById('ag-greeting').value = ab.greeting;
                    }
                }
            }
            
            try {
                const activeRes = await this.api('GET', '/prompt-config/active');
                const previewEl = document.getElementById('promptPreview');
                if (previewEl && activeRes.prompt_preview) {
                    previewEl.value = activeRes.prompt_preview;
                }
            } catch (e) {
                console.error("Error al cargar preview activo:", e);
            }
        } catch (err) {
            this.updateSourceBadge('none');
            await this.renderAgentCards();
        }
        
        const activeTab = document.querySelector('.mode-tab.active');
        if (activeTab && activeTab.dataset.mode === 'builder') {
            this.updateBuilderPreview();
        }
    }

    restoreBuilder(b) {
        if (!b || typeof b !== 'object') return;
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
            this.toast('✅ Prompt activado.');
        } catch (err) { this.toast(err.message, 'error'); }
    }

    async saveBuilderAgent() {
        const nameInput = document.getElementById('b-agent-name');
        const profileName = (nameInput?.value || '').trim();
        if (!profileName) {
            nameInput?.focus();
            nameInput?.style && (nameInput.style.borderColor = 'rgba(248,113,113,.6)');
            this.toast('Escribe un nombre para el agente antes de guardar', 'error');
            return;
        }
        const cfg = this.getBuilderConfig();
        const traits = [
            { key: 'amabilidad', label: 'Amabilidad', value: 7 },
            { key: 'formalidad', label: 'Formalidad', value: 5 },
            { key: 'paciencia', label: 'Paciencia', value: 7 },
            { key: 'proactividad', label: 'Proactividad', value: 7 },
            { key: 'detalle', label: 'Detalle', value: 5 },
            { key: 'empatia', label: 'Empatía', value: 7 },
            { key: 'persuasion', label: 'Persuasión', value: 6 },
            { key: 'concision', label: 'Concisión', value: 6 },
        ];
        try {
            await this.api('POST', '/custom-agents', { profile_name: profileName, builder: cfg, traits, _source: 'builder' });
            this.toast(`💾 Agente "${profileName}" guardado en la base de datos.`);
            if (nameInput) { nameInput.value = ''; nameInput.style.borderColor = ''; }
            await this.renderBuilderAgentCards();
        } catch (err) { this.toast(err.message, 'error'); }
    }

    async renderBuilderAgentCards() {
        const container = document.getElementById('builderSavedAgents');
        if (!container) return;
        let agents = [];
        try { agents = await this.api('GET', '/custom-agents'); } catch { agents = []; }
        if (!agents.length) {
            container.innerHTML = '<div style="color:var(--text-2);font-size:.8rem;padding:8px 0;">Aún no has guardado ningún agente.</div>';
            return;
        }
        container.innerHTML = agents.map(a => `
            <div class="agent-card custom${this._selectedBuilderAgent === a.id ? ' selected' : ''}" data-bid="${a.id}" style="cursor:pointer;position:relative;min-width:120px;max-width:160px;">
                <button class="agent-card-delete" data-bdel="${a.id}" title="Eliminar" style="position:absolute;top:6px;right:6px;z-index:2;">✕</button>
                <span class="agent-card-badge">Guardado</span>
                <span class="agent-card-icon">🧩</span>
                <span class="agent-card-name">${a.profile_name || 'Sin nombre'}</span>
                <span class="agent-card-desc">${a.builder?.identity?.role || 'Constructor Visual'}</span>
            </div>
        `).join('');
        container.querySelectorAll('[data-bid]').forEach(card => {
            card.addEventListener('click', e => {
                if (e.target.closest('[data-bdel]')) return;
                const agent = agents.find(a => a.id === card.dataset.bid);
                if (agent?.builder) {
                    this.restoreBuilder(agent.builder);
                    this._selectedBuilderAgent = agent.id;
                    const nameInput = document.getElementById('b-agent-name');
                    if (nameInput) nameInput.value = agent.profile_name || '';
                    this.toast(`📂 Agente "${agent.profile_name}" cargado.`);
                    this.renderBuilderAgentCards();
                }
            });
        });
        container.querySelectorAll('[data-bdel]').forEach(btn => {
            btn.addEventListener('click', async e => {
                e.stopPropagation();
                if (!confirm('¿Eliminar este agente guardado?')) return;
                try {
                    await this.api('DELETE', `/custom-agents/${btn.dataset.bdel}`);
                    if (this._selectedBuilderAgent === btn.dataset.bdel) this._selectedBuilderAgent = null;
                    this.toast('Agente eliminado.');
                    await this.renderBuilderAgentCards();
                } catch (err) { this.toast(err.message, 'error'); }
            });
        });
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
            this.updateSourceBadge('agent', this._selectedAgentId);
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



    // ── USERS MANAGEMENT ──────────────────────────────────────────────────────

    setupUsers() {
        document.getElementById('btnCreateUser')?.addEventListener('click', () => this.createUser());
    }

    async loadUsers() {
        const tbody = document.getElementById('usersBody');
        try {
            const data = await this.api('GET', '/users');
            if (!data.length) {
                tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No hay usuarios registrados</td></tr>';
                return;
            }
            tbody.innerHTML = data.map(u => {
                const isSelf = this.adminUserId && parseInt(u.id) === parseInt(this.adminUserId);
                const roleClass = u.role === 'admin' ? 'pill-green' : 'pill-cyan';
                const roleLabel = u.role === 'admin' ? 'Administrador' : 'Usuario Normal';
                const deleteBtn = isSelf 
                    ? `<span style="font-size: .8rem; color: var(--text-3); font-style: italic;">Actual (Tú)</span>` 
                    : `<button class="btn-danger" onclick="window.admin.deleteUser(${u.id})">Eliminar</button>`;
                
                return `
                <tr>
                    <td><strong>${u.username}</strong></td>
                    <td>${u.email || '—'}</td>
                    <td><span class="pill ${roleClass}">${roleLabel}</span></td>
                    <td>${u.created_at ? u.created_at.replace('T', ' ').substring(0, 19) : '—'}</td>
                    <td>${deleteBtn}</td>
                </tr>`;
            }).join('');
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Error: ${err.message}</td></tr>`;
        }
    }

    async createUser() {
        const username = document.getElementById('usrUsername')?.value.trim();
        const password = document.getElementById('usrPassword')?.value;
        const email = document.getElementById('usrEmail')?.value.trim();
        const role = document.getElementById('usrRole')?.value || 'user';

        if (!username || !password) {
            this.toast('Nombre de usuario y contraseña son obligatorios', 'error');
            return;
        }

        const btn = document.getElementById('btnCreateUser');
        const origText = btn ? btn.textContent : '';
        if (btn) {
            btn.disabled = true;
            btn.textContent = '⏳ Creando...';
        }

        try {
            await this.api('POST', '/users', { username, password, email, role });
            this.toast(`Usuario "${username}" creado correctamente.`);
            
            // Limpiar formulario
            ['usrUsername', 'usrPassword', 'usrEmail'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
            const roleEl = document.getElementById('usrRole');
            if (roleEl) roleEl.value = 'user';

            await this.loadUsers();
        } catch (err) {
            this.toast(err.message, 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = origText;
            }
        }
    }

    async deleteUser(id) {
        if (!confirm('¿Estás seguro de que deseas eliminar este usuario?')) return;
        try {
            await this.api('DELETE', `/users/${id}`);
            this.toast('Usuario eliminado exitosamente.');
            await this.loadUsers();
        } catch (err) {
            this.toast(err.message, 'error');
        }
    }

    setupOdooAgents() {
        this._selectedOdooAgentId = null;
        this._odooPresets = [];
        document.getElementById('btnApplyOdooAgent')?.addEventListener('click', () => {
            if (this._selectedOdooAgentId) {
                this.applyOdooAgent(this._selectedOdooAgentId);
            } else {
                this.toast('Selecciona un agente de Odoo primero', 'error');
            }
        });
    }

    async checkOdooVisibility() {
        try {
            const config = await this.api('GET', '/agent-data-source');
            console.log("CheckOdooVisibility: active source_type is", config.source_type, config);
            const tab = document.getElementById('odooAgentsTab');
            if (tab) {
                if (config.source_type === 'odoo') {
                    tab.style.display = 'inline-block';
                } else {
                    tab.style.display = 'none';
                    if (tab.classList.contains('active')) {
                        document.querySelector('[data-mode="builder"]')?.click();
                    }
                }
            }
        } catch (e) {
            console.error('Error al verificar visibilidad de Odoo:', e);
        }
    }

    async loadOdooAgents() {
        const grid = document.getElementById('odooAgentGrid');
        if (!grid) return;

        try {
            const res = await this.api('GET', '/odoo-agents');
            if (!res.available) {
                grid.innerHTML = '<div style="color:var(--text-2);font-size:.8rem;padding:8px 0;">La integración de Odoo no está disponible o activa.</div>';
                return;
            }

            this._odooPresets = res.presets || [];
            
            let html = this._odooPresets.map(a => `
                <div class="agent-card${this._selectedOdooAgentId === a.id ? ' selected' : ''}" data-odoo-agent="${a.id}">
                    <span class="agent-card-icon">${a.icon}</span>
                    <span class="agent-card-name">${a.name}</span>
                    <span class="agent-card-desc">${a.description}</span>
                </div>
            `).join('');

            grid.innerHTML = html;

            grid.querySelectorAll('[data-odoo-agent]').forEach(card => {
                card.addEventListener('click', () => {
                    this.selectOdooAgent(card.dataset.odooAgent);
                });
            });

            const config = await this.api('GET', '/prompt-config');
            if (config.mode === 'agent' && (config.agent_id === 'odoo_sales' || config.agent_id === 'odoo_vendor_support')) {
                this.selectOdooAgent(config.agent_id);
            }
        } catch (err) {
            grid.innerHTML = `<div style="color:var(--text-2);font-size:.8rem;padding:8px 0;">Error al cargar agentes de Odoo: ${err.message}</div>`;
        }
    }

    selectOdooAgent(agentId) {
        this._selectedOdooAgentId = agentId;
        const preset = this._odooPresets.find(a => a.id === agentId);
        if (!preset) return;

        document.querySelectorAll('[data-odoo-agent]').forEach(c => c.classList.remove('selected'));
        const sel = document.querySelector(`[data-odoo-agent="${agentId}"]`);
        if (sel) sel.classList.add('selected');

        const configPanel = document.getElementById('odooAgentConfigPanel');
        if (configPanel) {
            configPanel.style.display = 'block';
            configPanel.classList.add('active');
        }

        document.getElementById('odooAgentCfgIcon').textContent = preset.icon;
        document.getElementById('odooAgentCfgTitle').textContent = `Configurar: ${preset.name}`;
        document.getElementById('odooAgentCfgSub').textContent = preset.description;
        document.getElementById('odooAgentProfileName').value = preset.name;

        const capGrid = document.getElementById('odooCapabilitiesGrid');
        if (capGrid) {
            capGrid.innerHTML = preset.capabilities.map(c => {
                const label = CAP_MAP[c] || c;
                return `
                <label class="check-card" style="cursor: default; pointer-events: none; opacity: 0.9;">
                    <input type="checkbox" checked disabled>
                    <span class="check-box" style="border-color: var(--accent); background: var(--accent-dim);"></span>
                    <span>${label.replace(/^- /, '')}</span>
                </label>`;
            }).join('');
        }
    }

    async applyOdooAgent(agentId) {
        try {
            const res = await this.api('POST', '/odoo-agents', { agent_id: agentId });
            this.updateSourceBadge('agent', agentId);
            this.toast(`✅ Agente Odoo activado con éxito: ${res.message || ''}`);
        } catch (err) {
            this.toast(err.message, 'error');
        }
    }
}


document.addEventListener('DOMContentLoaded', () => {
    window.admin = new NovaAdmin();
});
