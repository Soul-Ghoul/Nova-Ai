SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS extensions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    extension TEXT NOT NULL UNIQUE,
    department TEXT DEFAULT '',
    email TEXT DEFAULT '',
    available INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    description TEXT DEFAULT '',
    price REAL DEFAULT 0.0,
    stock INTEGER DEFAULT 0,
    category TEXT DEFAULT '',
    brand TEXT DEFAULT '',
    color TEXT DEFAULT '',
    weight TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    caller_id TEXT DEFAULT '',
    source TEXT DEFAULT 'unknown',
    duration REAL DEFAULT 0.0,
    actions_taken TEXT DEFAULT '[]',
    transcript TEXT DEFAULT '',
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    tokens_total INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_call_logs_cost ON call_logs (cost_usd DESC);
CREATE INDEX IF NOT EXISTS idx_call_logs_created ON call_logs (created_at DESC);

CREATE TABLE IF NOT EXISTS token_usage_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    total_calls INTEGER DEFAULT 0,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    tokens_total INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date)
);

-- FTS5: Full-Text Search sobre inventario (multilingüe, sin configuración de idioma)
-- Indexa: nombre, descripción, categoría, marca — busca tokens en cualquier idioma
CREATE VIRTUAL TABLE IF NOT EXISTS inventory_fts USING fts5(
    product_name, description, category, brand, color,
    content=inventory, content_rowid=id
);

-- FTS5: Full-Text Search sobre extensiones
CREATE VIRTUAL TABLE IF NOT EXISTS extensions_fts USING fts5(
    name, department,
    content=extensions, content_rowid=id
);

-- Triggers para mantener FTS sincronizado con inventory
CREATE TRIGGER IF NOT EXISTS inventory_fts_insert
    AFTER INSERT ON inventory BEGIN
    INSERT INTO inventory_fts(rowid, product_name, description, category, brand, color)
    VALUES (new.id, new.product_name, new.description, new.category, new.brand, new.color);
END;

CREATE TRIGGER IF NOT EXISTS inventory_fts_delete
    AFTER DELETE ON inventory BEGIN
    INSERT INTO inventory_fts(inventory_fts, rowid, product_name, description, category, brand, color)
    VALUES ('delete', old.id, old.product_name, old.description, old.category, old.brand, old.color);
END;

CREATE TRIGGER IF NOT EXISTS inventory_fts_update
    AFTER UPDATE ON inventory BEGIN
    INSERT INTO inventory_fts(inventory_fts, rowid, product_name, description, category, brand, color)
    VALUES ('delete', old.id, old.product_name, old.description, old.category, old.brand, old.color);
    INSERT INTO inventory_fts(rowid, product_name, description, category, brand, color)
    VALUES (new.id, new.product_name, new.description, new.category, new.brand, new.color);
END;

-- Triggers para mantener FTS sincronizado con extensions
CREATE TRIGGER IF NOT EXISTS extensions_fts_insert
    AFTER INSERT ON extensions BEGIN
    INSERT INTO extensions_fts(rowid, name, department)
    VALUES (new.id, new.name, new.department);
END;

CREATE TRIGGER IF NOT EXISTS extensions_fts_delete
    AFTER DELETE ON extensions BEGIN
    INSERT INTO extensions_fts(extensions_fts, rowid, name, department)
    VALUES ('delete', old.id, old.name, old.department);
END;

CREATE TRIGGER IF NOT EXISTS extensions_fts_update
    AFTER UPDATE ON extensions BEGIN
    INSERT INTO extensions_fts(extensions_fts, rowid, name, department)
    VALUES ('delete', old.id, old.name, old.department);
    INSERT INTO extensions_fts(rowid, name, department)
    VALUES (new.id, new.name, new.department);
END;
-- Tablas para autenticación de administradores y aislamiento de prompts
CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT DEFAULT '',
    role TEXT DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_sessions (
    session_token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES admin_users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin_agents (
    user_id INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    name TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    builder_config TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, agent_id),
    FOREIGN KEY(user_id) REFERENCES admin_users(id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS agent_data_source (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    source_type TEXT NOT NULL DEFAULT 'internal',
    pg_connection_string TEXT DEFAULT '',
    odoo_url TEXT DEFAULT '',
    odoo_db TEXT DEFAULT '',
    odoo_api_key TEXT DEFAULT '',
    odoo_user TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES admin_users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prompt_config (
    user_id INTEGER NOT NULL PRIMARY KEY,
    mode TEXT NOT NULL DEFAULT 'builder',
    use_custom BOOLEAN DEFAULT 0,
    voice TEXT DEFAULT 'Nova',
    builder TEXT DEFAULT '{}',
    raw_content TEXT DEFAULT '',
    agent_id TEXT DEFAULT '',
    agent_source TEXT DEFAULT 'preset',
    agent_builder TEXT DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES admin_users(id) ON DELETE CASCADE
);
"""


SCHEMA_POSTGRES_SQL = """
CREATE TABLE IF NOT EXISTS extensions (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    extension TEXT NOT NULL UNIQUE,
    department TEXT DEFAULT '',
    email TEXT DEFAULT '',
    available INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory (
    id SERIAL PRIMARY KEY,
    product_name TEXT NOT NULL,
    description TEXT DEFAULT '',
    price DOUBLE PRECISION DEFAULT 0.0,
    stock INTEGER DEFAULT 0,
    category TEXT DEFAULT '',
    brand TEXT DEFAULT '',
    color TEXT DEFAULT '',
    weight TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS call_logs (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    caller_id TEXT DEFAULT '',
    source TEXT DEFAULT 'unknown',
    duration DOUBLE PRECISION DEFAULT 0.0,
    actions_taken TEXT DEFAULT '[]',
    transcript TEXT DEFAULT '',
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    tokens_total INTEGER DEFAULT 0,
    cost_usd DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_call_logs_cost ON call_logs (cost_usd DESC);
CREATE INDEX IF NOT EXISTS idx_call_logs_created ON call_logs (created_at DESC);

CREATE TABLE IF NOT EXISTS token_usage_daily (
    id SERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    total_calls INTEGER DEFAULT 0,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    tokens_total INTEGER DEFAULT 0,
    cost_usd DOUBLE PRECISION DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date)
);

-- Tablas para autenticación de administradores y aislamiento de prompts en PostgreSQL
CREATE TABLE IF NOT EXISTS admin_users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT DEFAULT '',
    role TEXT DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_sessions (
    session_token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES admin_users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin_agents (
    user_id INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    name TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    builder_config TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, agent_id),
    FOREIGN KEY(user_id) REFERENCES admin_users(id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS agent_data_source (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    source_type TEXT NOT NULL DEFAULT 'internal',
    pg_connection_string TEXT DEFAULT '',
    odoo_url TEXT DEFAULT '',
    odoo_db TEXT DEFAULT '',
    odoo_api_key TEXT DEFAULT '',
    odoo_user TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES admin_users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prompt_config (
    user_id INTEGER NOT NULL PRIMARY KEY,
    mode TEXT NOT NULL DEFAULT 'builder',
    use_custom BOOLEAN DEFAULT false,
    voice TEXT DEFAULT 'Nova',
    builder TEXT DEFAULT '{}',
    raw_content TEXT DEFAULT '',
    agent_id TEXT DEFAULT '',
    agent_source TEXT DEFAULT 'preset',
    agent_builder TEXT DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES admin_users(id) ON DELETE CASCADE
);
"""

