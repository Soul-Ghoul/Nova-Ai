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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
"""
