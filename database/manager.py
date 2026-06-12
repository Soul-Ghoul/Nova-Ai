import aiosqlite
import os
import re
import json
import unicodedata
from loguru import logger
from config.settings import get_settings
from database.models import SCHEMA_SQL, SCHEMA_POSTGRES_SQL


def _normalize(text: str) -> str:
    nfd = unicodedata.normalize('NFD', text)
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn').lower()


def _get_counterpart_word(word: str) -> str:
    original = word.lower()
    if original.endswith('ora') and len(original) >= 5:
        return original[:-1]
    if original.endswith('or') and len(original) >= 4:
        return original + 'a'
    if len(original) >= 4 and original.endswith('s'):
        if original.endswith('ces'):
            return original[:-3] + 'z'
        if original.endswith('ches'):
            return original[:-2]
        if original.endswith('res'):
            return original[:-2]
        if original.endswith('les'):
            return original[:-2]
        if original.endswith('nes'):
            return original[:-2]
        if original.endswith('des'):
            return original[:-2]
        return original[:-1]
    if len(original) >= 2:
        if original.endswith('z'):
            return original[:-1] + 'ces'
        if original.endswith(('a', 'e', 'i', 'o', 'u')):
            return original + 's'
        if original.endswith(('r', 'l', 'n', 'd', 't', 'ch')):
            if original.endswith('ch'):
                return original + 'es'
            return original + 'es'
    return word


def _get_counterpart_query(query: str) -> str:
    words = query.split()
    counterparts = []
    for w in words:
        clean_w = re.sub(r'[^\w]', '', w)
        if not clean_w:
            counterparts.append(w)
            continue
        cp = _get_counterpart_word(clean_w)
        if w[0].isupper():
            cp = cp.capitalize()
        counterparts.append(cp)
    return " ".join(counterparts)


_STOPWORDS = {
    "de", "la", "el", "en", "un", "los", "las", "del", "al", "por",
    "con", "sin", "se", "le", "su", "es", "que", "para", "como", "una",
    "and", "the", "for", "with", "from", "of", "in", "on", "at", "to",
}

def _tokenize_query(query: str) -> list[str]:
    norm = _normalize(query)
    terms = {norm}
    words = [w for w in norm.split() if len(w) >= 2]
    terms.update(words)
    for w in words:
        if len(w) >= 5:
            terms.add(w[:4])
    return list(terms)


def _sanitize_fts_query(query: str) -> str:
    cleaned = re.sub(r'[^\w\s]', ' ', query)
    forbidden = {"or", "and", "not"}
    tokens = [t for t in cleaned.split() if t.lower() not in forbidden]
    return ' OR '.join(f'"{t}"*' for t in tokens if t)


class DatabaseManager:
    def __init__(self):
        self.config_path = "./data/db_config.json"
        self.db_type = "postgres"
        self.sqlite_path = get_settings().db_path
        self.postgres_url = get_settings().database_url
        self._db = None
        self.load_config()

    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.db_type = cfg.get("db_type", "postgres")
                    self.sqlite_path = cfg.get("sqlite_path", "./data/nova.db")
                    self.postgres_url = cfg.get("postgres_url", get_settings().database_url)
            else:
                settings = get_settings()
                if settings.database_url:
                    self.db_type = "postgres"
                    self.postgres_url = settings.database_url
                else:
                    self.db_type = "sqlite"
                    self.sqlite_path = settings.db_path
        except Exception as e:
            logger.error(f"Error cargando db_config.json: {e}")

    @staticmethod
    def _normalize_text(text: str) -> str:
        return _normalize(text)

    def _convert_query(self, sql: str) -> str:
        if self.db_type == "postgres":
            count = 1
            def repl(match):
                nonlocal count
                res = f"${count}"
                count += 1
                return res
            return re.sub(r'\?', repl, sql)
        return sql

    async def connect(self):
        self.load_config()
        if self.db_type == "postgres":
            import asyncpg
            logger.info("Conectando a PostgreSQL (Railway) con pool de conexiones...")
            try:
                self._db = await asyncpg.create_pool(
                    self.postgres_url,
                    min_size=2,
                    max_size=20,
                    command_timeout=30,
                )
                async with self._db.acquire() as conn:
                    await conn.execute(SCHEMA_POSTGRES_SQL)
                    try:
                        await conn.execute("ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user'")
                    except Exception as _mig_err:
                        logger.debug(f"Migración PostgreSQL role: {_mig_err}")
                    try:
                        await conn.execute("ALTER TABLE inventory ADD COLUMN IF NOT EXISTS tags TEXT DEFAULT ''")
                    except Exception as _mig_err:
                        logger.debug(f"Migración PostgreSQL tags: {_mig_err}")
                    try:
                        await conn.execute("ALTER TABLE admin_agents ADD COLUMN IF NOT EXISTS builder_config TEXT DEFAULT '{}'")
                    except Exception as _mig_err:
                        logger.debug(f"Migración PostgreSQL builder_config: {_mig_err}")
                    try:
                        await conn.execute("CREATE TABLE IF NOT EXISTS prompt_config (user_id INTEGER NOT NULL PRIMARY KEY, mode TEXT NOT NULL DEFAULT 'builder', use_custom BOOLEAN DEFAULT false, voice TEXT DEFAULT 'Nova', builder TEXT DEFAULT '{}', raw_content TEXT DEFAULT '', agent_id TEXT DEFAULT '', agent_source TEXT DEFAULT 'preset', agent_builder TEXT DEFAULT '{}', updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES admin_users(id) ON DELETE CASCADE)")
                    except Exception as _mig_err:
                        logger.debug(f"Migración PostgreSQL prompt_config: {_mig_err}")
                    try:
                        await conn.execute("CREATE INDEX IF NOT EXISTS idx_call_logs_cost ON call_logs (cost_usd DESC)")
                    except Exception as _mig_err:
                        logger.debug(f"Migración PostgreSQL index cost: {_mig_err}")
                logger.info("✅ Base de datos PostgreSQL conectada (pool activo)")
                return
            except Exception as e:
                logger.error(f"❌ CRÍTICO: Fallo al conectar a PostgreSQL (Railway): {e}")
                logger.error("❌ No se puede iniciar sin Postgres en producción. Verifica DATABASE_URL.")
                raise RuntimeError(f"PostgreSQL connection failed: {e}")

        # SQLite solo permitido en desarrollo
        if self.db_type == "sqlite":
            logger.warning("⚠️  SQLite detectado - solo válido para DESARROLLO local")
            os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)
            self._db = await aiosqlite.connect(self.sqlite_path)
            self._db.row_factory = aiosqlite.Row
            await self._db.executescript(SCHEMA_SQL)
            await self._db.commit()
            try:
                await self._db.execute("ALTER TABLE inventory ADD COLUMN tags TEXT DEFAULT ''")
                await self._db.commit()
            except Exception:
                pass
            try:
                await self._db.execute("ALTER TABLE admin_users ADD COLUMN role TEXT DEFAULT 'user'")
                await self._db.commit()
            except Exception:
                pass
            try:
                await self._db.execute("ALTER TABLE admin_agents ADD COLUMN builder_config TEXT DEFAULT '{}'")
                await self._db.commit()
            except Exception:
                pass
            try:
                await self._db.execute("CREATE TABLE IF NOT EXISTS prompt_config (user_id INTEGER NOT NULL PRIMARY KEY, mode TEXT NOT NULL DEFAULT 'builder', use_custom BOOLEAN DEFAULT 0, voice TEXT DEFAULT 'Nova', builder TEXT DEFAULT '{}', raw_content TEXT DEFAULT '', agent_id TEXT DEFAULT '', agent_source TEXT DEFAULT 'preset', agent_builder TEXT DEFAULT '{}', updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES admin_users(id) ON DELETE CASCADE)")
                await self._db.commit()
            except Exception:
                pass
            try:
                await self._db.execute("CREATE INDEX IF NOT EXISTS idx_call_logs_cost ON call_logs (cost_usd DESC)")
                await self._db.commit()
            except Exception:
                pass
            await self._rebuild_fts_index()
            logger.info(f"✅ Base de datos SQLite conectada (desarrollo): {self.sqlite_path}")

    async def reconnect(self, db_type: str, sqlite_path: str, postgres_url: str):
        await self.disconnect()
        config_data = {
            "db_type": db_type,
            "sqlite_path": sqlite_path,
            "postgres_url": postgres_url
        }
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        self.db_type = db_type
        self.sqlite_path = sqlite_path
        self.postgres_url = postgres_url
        await self.connect()

    async def test_connection(self, db_type: str, sqlite_path: str, postgres_url: str):
        if db_type == "postgres":
            import asyncpg
            conn = await asyncpg.connect(postgres_url)
            await conn.close()
        else:
            conn = await aiosqlite.connect(sqlite_path)
            await conn.close()

    async def _rebuild_fts_index(self):
        if self.db_type == "postgres":
            return
        try:
            await self._db.execute("INSERT INTO inventory_fts(inventory_fts) VALUES('rebuild')")
            await self._db.execute("INSERT INTO extensions_fts(extensions_fts) VALUES('rebuild')")
            await self._db.commit()
            logger.info("Índices FTS5 reconstruidos")
        except Exception as e:
            logger.debug(f"FTS rebuild (normal en BD nueva): {e}")

    async def disconnect(self):
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("Base de datos desconectada")

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        sql = self._convert_query(sql)
        if self.db_type == "postgres":
            async with self._db.acquire() as conn:
                rows = await conn.fetch(sql, *params)
            return [dict(r) for r in rows]
        else:
            async with self._db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict:
        sql = self._convert_query(sql)
        if self.db_type == "postgres":
            async with self._db.acquire() as conn:
                row = await conn.fetchrow(sql, *params)
            return dict(row) if row else {}
        else:
            async with self._db.execute(sql, params) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else {}

    async def execute(self, sql: str, params: tuple = ()):
        sql = self._convert_query(sql)
        if self.db_type == "postgres":
            async with self._db.acquire() as conn:
                await conn.execute(sql, *params)
        else:
            await self._db.execute(sql, params)
            await self._db.commit()

    # ── BÚSQUEDA EXTENSIONES ───────────────────────────────────────────────────

    async def search_extension(self, query: str) -> list[dict]:
        norm_query = _normalize(query)
        logger.info(f"[SEARCH] extension='{query}'")
        if self.db_type == "postgres":
            results = await self._ilike_search_extensions(query)
            if not results:
                results = await self._token_search_extensions(norm_query)
        else:
            results = await self._fts_search_extensions(norm_query)
            if not results:
                results = await self._token_search_extensions(norm_query)
        logger.info(f"[SEARCH] extension results: {len(results)}")
        return results

    async def _ilike_search_extensions(self, query: str) -> list[dict]:
        try:
            raw_terms  = [t for t in query.split() if len(t) >= 3 and t.lower() not in _STOPWORDS]
            norm_terms = [t for t in _normalize(query).split() if len(t) >= 3 and t not in _STOPWORDS]
            all_terms  = list(dict.fromkeys(raw_terms + norm_terms)) or [_normalize(query)]

            conditions = []
            params = []
            for term in all_terms[:6]:
                pattern = f"%{term}%"
                base = len(params)
                conditions.append(
                    f"(name ILIKE ${base+1} OR department ILIKE ${base+2} OR extension ILIKE ${base+3})"
                )
                params.extend([pattern, pattern, pattern])

            where = " OR ".join(conditions)
            sql = f"SELECT * FROM extensions WHERE {where} LIMIT 20"

            async with self._db.acquire() as conn:
                rows = await conn.fetch(sql, *params)
            return [{
                "name": r["name"], "extension": r["extension"],
                "department": r["department"], "email": r["email"],
                "available": r["available"]
            } for r in rows]
        except Exception as e:
            logger.warning(f"ILIKE extensions search error: {e}")
            return []

    async def _fts_search_extensions(self, query: str) -> list[dict]:
        try:
            fts_query = _sanitize_fts_query(query)
            if not fts_query:
                return []
            sql = """
                SELECT e.* FROM extensions e
                JOIN extensions_fts f ON e.id = f.rowid
                WHERE extensions_fts MATCH ?
                ORDER BY rank LIMIT 20
            """
            rows = await self.fetch_all(sql, (fts_query,))
            return [{
                "name": r["name"], "extension": r["extension"],
                "department": r["department"], "email": r["email"],
                "available": r["available"]
            } for r in rows]
        except Exception as e:
            logger.debug(f"FTS5 extension error (usando fallback): {e}")
            return []

    async def _token_search_extensions(self, norm_query: str) -> list[dict]:
        terms = _tokenize_query(norm_query)
        all_rows = await self.fetch_all("SELECT * FROM extensions")
        seen, results = set(), []
        for row in all_rows:
            n = _normalize(row["name"])
            d = _normalize(row["department"])
            e = _normalize(row["extension"])
            for t in terms:
                if t in n or t in d or t in e:
                    if row["id"] not in seen:
                        seen.add(row["id"])
                        results.append({
                            "name": row["name"], "extension": row["extension"],
                            "department": row["department"], "email": row["email"],
                            "available": row["available"]
                        })
                    break
        return results

    # ── BÚSQUEDA INVENTARIO ────────────────────────────────────────────────────

    async def _execute_search_pipeline(self, query: str, norm_query: str) -> list[dict]:
        if self.db_type == "postgres":
            results = await self._ilike_search_inventory_exact(query)
            if not results:
                results = await self._ilike_search_inventory(query, include_description=False, use_and=True)
            if not results:
                results = await self._ilike_search_inventory(query, include_description=False, use_and=False)
            if not results:
                results = await self._ilike_search_inventory(query, include_description=True, use_and=True)
            if not results:
                results = await self._token_search_inventory(norm_query)
        else:
            results = await self._fts_search_inventory(norm_query)
            if not results:
                results = await self._token_search_inventory(norm_query)
        return results

    async def search_inventory(self, query: str) -> list[dict]:
        norm_query = _normalize(query)
        logger.info(f"[SEARCH] inventory='{query}'")
        results = await self._execute_search_pipeline(query, norm_query)
        if not results:
            counterpart = _get_counterpart_query(query)
            if counterpart != query:
                logger.info(f"[SEARCH FALLBACK] Probando contraparte: '{counterpart}'")
                norm_counterpart = _normalize(counterpart)
                results = await self._execute_search_pipeline(counterpart, norm_counterpart)
        logger.info(f"[SEARCH] inventory results: {len(results)}")
        return results

    async def _ilike_search_inventory_exact(self, query: str) -> list[dict]:
        """Fase 1: frase exacta completa en nombre, marca, categoría o tags."""
        try:
            pattern = f"%{_normalize(query)}%"
            sql = (
                "SELECT * FROM inventory "
                "WHERE product_name ILIKE $1 OR brand ILIKE $2 OR category ILIKE $3 OR tags ILIKE $4 "
                "LIMIT 50"
            )
            async with self._db.acquire() as conn:
                rows = await conn.fetch(sql, pattern, pattern, pattern, pattern)
            return [{
                "product_name": r["product_name"], "description": r["description"],
                "price": r["price"], "stock": r["stock"],
                "category": r["category"], "brand": r["brand"],
                "color": r["color"], "weight": r["weight"],
                "tags": r["tags"] or ""
            } for r in rows]
        except Exception as e:
            logger.warning(f"ILIKE exact search error: {e}")
            return []

    async def _ilike_search_inventory(self, query: str, include_description: bool = False, use_and: bool = False) -> list[dict]:
        """Fase 2/3: tokens significativos con AND (todos deben coincidir) o OR (fallback)."""
        try:
            raw_terms  = [t for t in query.split() if len(t) >= 3 and t.lower() not in _STOPWORDS]
            norm_terms = [t for t in _normalize(query).split() if len(t) >= 3 and t not in _STOPWORDS]
            all_terms  = list(dict.fromkeys(raw_terms + norm_terms)) or [_normalize(query)]
            all_terms  = all_terms[:6]

            conditions = []
            params = []
            for term in all_terms:
                pattern = f"%{term}%"
                base = len(params)
                if include_description:
                    conditions.append(
                        f"(product_name ILIKE ${base+1} OR description ILIKE ${base+2} "
                        f"OR category ILIKE ${base+3} OR brand ILIKE ${base+4} OR tags ILIKE ${base+5})"
                    )
                    params.extend([pattern, pattern, pattern, pattern, pattern])
                else:
                    conditions.append(
                        f"(product_name ILIKE ${base+1} OR category ILIKE ${base+2} OR brand ILIKE ${base+3} OR tags ILIKE ${base+4})"
                    )
                    params.extend([pattern, pattern, pattern, pattern])

            joiner = " AND " if use_and else " OR "
            where = joiner.join(conditions)
            sql = f"SELECT * FROM inventory WHERE {where} LIMIT 50"

            async with self._db.acquire() as conn:
                rows = await conn.fetch(sql, *params)
            return [{
                "product_name": r["product_name"], "description": r["description"],
                "price": r["price"], "stock": r["stock"],
                "category": r["category"], "brand": r["brand"],
                "color": r["color"], "weight": r["weight"],
                "tags": r["tags"] or ""
            } for r in rows]
        except Exception as e:
            logger.warning(f"ILIKE search error: {e}")
            return []

    async def _fts_search_inventory(self, query: str) -> list[dict]:
        try:
            fts_query = _sanitize_fts_query(query)
            if not fts_query:
                return []
            sql = """
                SELECT i.* FROM inventory i
                JOIN inventory_fts f ON i.id = f.rowid
                WHERE inventory_fts MATCH ?
                ORDER BY rank LIMIT 20
            """
            rows = await self.fetch_all(sql, (fts_query,))
            return [{
                "product_name": r["product_name"], "description": r["description"],
                "price": r["price"], "stock": r["stock"],
                "category": r["category"], "brand": r["brand"],
                "color": r["color"], "weight": r["weight"],
                "tags": r.get("tags") or ""
            } for r in rows]
        except Exception as e:
            logger.debug(f"FTS5 inventory error (usando fallback): {e}")
            return []

    async def _token_search_inventory(self, norm_query: str) -> list[dict]:
        sig_terms = [t for t in norm_query.split() if len(t) >= 3 and t not in _STOPWORDS]
        all_terms = _tokenize_query(norm_query)
        all_rows = await self.fetch_all("SELECT * FROM inventory")
        seen, results = set(), []
        for row in all_rows:
            n = _normalize(row["product_name"])
            c = _normalize(row["category"])
            b = _normalize(row["brand"])
            d = _normalize(row["description"])
            tg = _normalize(row.get("tags") or "")

            if sig_terms and all(t in n or t in c or t in b or t in tg for t in sig_terms):
                if row["id"] not in seen:
                    seen.add(row["id"])
                    results.append({
                        "product_name": row["product_name"], "description": row["description"],
                        "price": row["price"], "stock": row["stock"],
                        "category": row["category"], "brand": row["brand"],
                        "color": row["color"], "weight": row["weight"],
                        "tags": row.get("tags") or ""
                    })
                continue

            for t in all_terms:
                if t in n or t in c or t in b or t in tg or t in d:
                    if row["id"] not in seen:
                        seen.add(row["id"])
                        results.append({
                            "product_name": row["product_name"], "description": row["description"],
                            "price": row["price"], "stock": row["stock"],
                            "category": row["category"], "brand": row["brand"],
                            "color": row["color"], "weight": row["weight"],
                            "tags": row.get("tags") or ""
                        })
                    break
        return results

    # ── LOGS ───────────────────────────────────────────────────────────────────

    async def log_call(self, session_id: str, caller_id: str, source: str,
                       duration: float, actions: str, transcript: str,
                       tokens_input: int = 0, tokens_output: int = 0):
        from datetime import datetime
        created_at = datetime.now()
        tokens_total = tokens_input + tokens_output
        cost_usd = (tokens_input * 0.000001) + (tokens_output * 0.000002)
        sql = """
            INSERT INTO call_logs
                (session_id, caller_id, source, duration, actions_taken, transcript,
                 tokens_input, tokens_output, tokens_total, cost_usd, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await self.execute(sql, (
            session_id, caller_id, source, duration, actions, transcript,
            tokens_input, tokens_output, tokens_total, cost_usd, created_at
        ))
        await self._upsert_daily_usage(tokens_input, tokens_output, tokens_total, cost_usd)

    async def _upsert_daily_usage(self, tin: int, tout: int, ttotal: int, cost: float):
        from datetime import date, datetime
        today = date.today().isoformat()
        now = datetime.now()
        sql = """
            INSERT INTO token_usage_daily (date, total_calls, tokens_input, tokens_output, tokens_total, cost_usd, updated_at)
            VALUES (?, 1, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_calls   = token_usage_daily.total_calls + 1,
                tokens_input  = token_usage_daily.tokens_input + excluded.tokens_input,
                tokens_output = token_usage_daily.tokens_output + excluded.tokens_output,
                tokens_total  = token_usage_daily.tokens_total + excluded.tokens_total,
                cost_usd      = token_usage_daily.cost_usd + excluded.cost_usd,
                updated_at    = excluded.updated_at
        """
        await self.execute(sql, (today, tin, tout, ttotal, cost, now))

    # ── EXTENSIONES CRUD ───────────────────────────────────────────────────────

    async def get_all_extensions(self) -> list[dict]:
        return await self.fetch_all("SELECT * FROM extensions ORDER BY name")

    async def add_extension(self, name: str, extension: str, department: str = "", email: str = ""):
        sql = "INSERT INTO extensions (name, extension, department, email) VALUES (?, ?, ?, ?)"
        await self.execute(sql, (name, extension, department, email))

    async def delete_extension(self, ext_id: int):
        await self.execute("DELETE FROM extensions WHERE id = ?", (ext_id,))

    # ── INVENTARIO CRUD ────────────────────────────────────────────────────────

    async def get_all_inventory(self) -> list[dict]:
        return await self.fetch_all("SELECT * FROM inventory ORDER BY product_name")

    async def add_inventory_item(self, product_name: str, description: str,
                                 price: float, stock: int, category: str,
                                 brand: str = "", color: str = "", weight: str = "",
                                 tags: str = ""):
        sql = """INSERT INTO inventory (product_name, description, price, stock, category, brand, color, weight, tags)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        await self.execute(sql, (product_name, description, price, stock, category, brand, color, weight, tags))

    async def delete_inventory_item(self, item_id: int):
        await self.execute("DELETE FROM inventory WHERE id = ?", (item_id,))

    # ── CALL LOGS ──────────────────────────────────────────────────────────────

    async def get_call_logs(self, limit: int = 50) -> list[dict]:
        sql = "SELECT * FROM call_logs ORDER BY created_at DESC LIMIT ?"
        return await self.fetch_all(sql, (limit,))

    async def get_token_stats_summary(self) -> dict:
        sql = """
            SELECT
                COALESCE(SUM(total_calls),0)   as total_calls,
                COALESCE(SUM(tokens_input),0)  as tokens_input,
                COALESCE(SUM(tokens_output),0) as tokens_output,
                COALESCE(SUM(tokens_total),0)  as tokens_total,
                COALESCE(SUM(cost_usd),0)      as cost_usd,
                CASE 
                    WHEN COALESCE(SUM(total_calls),0) > 0 THEN COALESCE(SUM(tokens_total),0) * 1.0 / COALESCE(SUM(total_calls),0)
                    ELSE 0
                END as avg_tokens_per_call
            FROM token_usage_daily
        """
        return await self.fetch_one(sql)

    async def get_token_usage_daily(self, days: int = 30) -> list[dict]:
        sql = """
            SELECT date, total_calls, tokens_input, tokens_output, tokens_total, cost_usd
            FROM token_usage_daily
            ORDER BY date DESC
            LIMIT ?
        """
        return await self.fetch_all(sql, (days,))

    async def get_top_calls_by_cost(self, limit: int = 10) -> list[dict]:
        sql = """
            SELECT session_id, caller_id, source, duration,
                   tokens_input, tokens_output, tokens_total, cost_usd, created_at
            FROM call_logs
            ORDER BY cost_usd DESC
            LIMIT ?
        """
        return await self.fetch_all(sql, (limit,))

    # ── MÉTODOS DE AUTENTICACIÓN Y SEGURIDAD ─────────────────────────────────

    async def get_user_by_username(self, username: str) -> dict:
        sql = "SELECT * FROM admin_users WHERE username = ?"
        return await self.fetch_one(sql, (username,))

    async def get_user_by_email(self, email: str) -> dict:
        sql = "SELECT * FROM admin_users WHERE email = ?"
        return await self.fetch_one(sql, (email,))

    async def create_admin_user(self, username: str, password_plain: str, email: str = "", role: str = "user"):
        from auth.utils import hash_password
        password_hash = hash_password(password_plain)
        sql = "INSERT INTO admin_users (username, password_hash, email, role) VALUES (?, ?, ?, ?)"
        await self.execute(sql, (username, password_hash, email, role))

    async def create_session_token(self, user_id: int, duration_seconds: int = 24 * 3600) -> str:
        from auth.utils import generate_session_token
        from datetime import datetime, timedelta
        token = generate_session_token()
        expires_at = datetime.now() + timedelta(seconds=duration_seconds)
        sql = "INSERT INTO admin_sessions (session_token, user_id, expires_at) VALUES (?, ?, ?)"
        await self.execute(sql, (token, user_id, expires_at))
        return token

    async def validate_session_token(self, session_token: str) -> dict | None:
        from datetime import datetime
        sql = """
            SELECT s.expires_at, u.id as user_id, u.username, u.email, u.role
            FROM admin_sessions s
            JOIN admin_users u ON s.user_id = u.id
            WHERE s.session_token = ?
        """
        row = await self.fetch_one(sql, (session_token,))
        if not row:
            return None
        
        expires_at_str = row["expires_at"]
        try:
            if isinstance(expires_at_str, datetime):
                expires_at = expires_at_str
            else:
                expires_at = datetime.strptime(str(expires_at_str).split('.')[0], '%Y-%m-%d %H:%M:%S')
        except Exception:
            try:
                expires_at = datetime.fromisoformat(str(expires_at_str).replace('Z', ''))
            except Exception:
                expires_at = datetime.now()
        
        if expires_at < datetime.now():
            await self.delete_session_token(session_token)
            return None
            
        return {
            "id": row["user_id"],
            "username": row["username"],
            "email": row["email"],
            "role": row.get("role", "user")
        }

    async def delete_session_token(self, session_token: str):
        sql = "DELETE FROM admin_sessions WHERE session_token = ?"
        await self.execute(sql, (session_token,))

    # ── MÉTODOS DE PROMPTS Y AGENTES AISLADOS ───────────────────────────────

    async def get_admin_agent(self, user_id: int, agent_id: str) -> dict:
        sql = "SELECT * FROM admin_agents WHERE user_id = ? AND agent_id = ?"
        return await self.fetch_one(sql, (user_id, agent_id))

    async def save_admin_agent(self, user_id: int, agent_id: str, name: str, system_prompt: str, builder_config: dict = None):
        config_json = json.dumps(builder_config or {}, ensure_ascii=False)
        sql = """
            INSERT INTO admin_agents (user_id, agent_id, name, system_prompt, builder_config)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, agent_id) DO UPDATE SET
                name = excluded.name,
                system_prompt = excluded.system_prompt,
                builder_config = excluded.builder_config
        """
        await self.execute(sql, (user_id, agent_id, name, system_prompt, config_json))

    async def get_all_admin_agents(self, user_id: int) -> list[dict]:
        sql = "SELECT agent_id, name, system_prompt, builder_config FROM admin_agents WHERE user_id = ? ORDER BY agent_id"
        rows = await self.fetch_all(sql, (user_id,))
        result = []
        for r in rows:
            try:
                builder = json.loads(r.get("builder_config") or "{}")
            except Exception:
                builder = {}
            result.append({
                "id": r["agent_id"],
                "agent_id": r["agent_id"],
                "name": r["name"],
                "system_prompt": r["system_prompt"],
                "profile_name": builder.get("profile_name", r["name"]),
                "builder": builder.get("builder", {}),
                "traits": builder.get("traits", []),
            })
        return result

    # ── AGENT DATA SOURCE ──────────────────────────────────────────────────

    async def get_agent_data_source(self, user_id: int) -> dict | None:
        sql = "SELECT * FROM agent_data_source WHERE user_id = ?"
        row = await self.fetch_one(sql, (user_id,))
        return row if row else None

    async def save_agent_data_source(self, user_id: int, source_type: str,
                                      pg_connection_string: str = "",
                                      odoo_url: str = "", odoo_db: str = "",
                                      odoo_api_key: str = "", odoo_user: str = ""):
        from datetime import datetime
        now = datetime.now()
        if self.db_type == "postgres":
            sql = """
                INSERT INTO agent_data_source
                    (user_id, source_type, pg_connection_string, odoo_url, odoo_db, odoo_api_key, odoo_user, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT(user_id) DO UPDATE SET
                    source_type = EXCLUDED.source_type,
                    pg_connection_string = EXCLUDED.pg_connection_string,
                    odoo_url = EXCLUDED.odoo_url,
                    odoo_db = EXCLUDED.odoo_db,
                    odoo_api_key = EXCLUDED.odoo_api_key,
                    odoo_user = EXCLUDED.odoo_user,
                    updated_at = EXCLUDED.updated_at
            """
            async with self._db.acquire() as conn:
                await conn.execute(sql, user_id, source_type, pg_connection_string,
                                   odoo_url, odoo_db, odoo_api_key, odoo_user, now)
        else:
            sql = """
                INSERT INTO agent_data_source
                    (user_id, source_type, pg_connection_string, odoo_url, odoo_db, odoo_api_key, odoo_user, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    source_type = excluded.source_type,
                    pg_connection_string = excluded.pg_connection_string,
                    odoo_url = excluded.odoo_url,
                    odoo_db = excluded.odoo_db,
                    odoo_api_key = excluded.odoo_api_key,
                    odoo_user = excluded.odoo_user,
                    updated_at = excluded.updated_at
            """
            await self._db.execute(sql, (user_id, source_type, pg_connection_string,
                                          odoo_url, odoo_db, odoo_api_key, odoo_user, now))
            await self._db.commit()
        logger.info(f"Agent data source guardada para user_id={user_id}, tipo={source_type}")

    async def delete_agent_data_source(self, user_id: int):
        await self.execute("DELETE FROM agent_data_source WHERE user_id = ?", (user_id,))

    # ── PROMPT CONFIG (persistencia en BD) ──────────────────────────────────────────────────

    async def save_prompt_config(self, user_id: int, config: dict):
        """Guarda la configuración de prompts del usuario en BD (no en JSON local)"""
        from datetime import datetime
        mode = config.get("mode", "builder")
        use_custom = config.get("use_custom", False)
        voice = config.get("voice", "Nova")
        
        builder_data = config.get("builder")
        if builder_data is None:
            builder_data = {}
        builder = json.dumps(builder_data, ensure_ascii=False)
        
        raw_content = config.get("raw_content", "")
        agent_id = config.get("agent_id", "")
        agent_source = config.get("agent_source", "preset")
        
        agent_builder_data = config.get("agent_builder")
        if agent_builder_data is None:
            agent_builder_data = {}
        agent_builder = json.dumps(agent_builder_data, ensure_ascii=False)
        
        now = datetime.now()

        if self.db_type == "postgres":
            sql = """
                INSERT INTO prompt_config 
                    (user_id, mode, use_custom, voice, builder, raw_content, agent_id, agent_source, agent_builder, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT(user_id) DO UPDATE SET
                    mode = EXCLUDED.mode,
                    use_custom = EXCLUDED.use_custom,
                    voice = EXCLUDED.voice,
                    builder = EXCLUDED.builder,
                    raw_content = EXCLUDED.raw_content,
                    agent_id = EXCLUDED.agent_id,
                    agent_source = EXCLUDED.agent_source,
                    agent_builder = EXCLUDED.agent_builder,
                    updated_at = EXCLUDED.updated_at
            """
            async with self._db.acquire() as conn:
                await conn.execute(sql, user_id, mode, use_custom, voice, builder, raw_content, 
                                 agent_id, agent_source, agent_builder, now)
        else:
            sql = """
                INSERT INTO prompt_config 
                    (user_id, mode, use_custom, voice, builder, raw_content, agent_id, agent_source, agent_builder, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    mode = excluded.mode,
                    use_custom = excluded.use_custom,
                    voice = excluded.voice,
                    builder = excluded.builder,
                    raw_content = excluded.raw_content,
                    agent_id = excluded.agent_id,
                    agent_source = excluded.agent_source,
                    agent_builder = excluded.agent_builder,
                    updated_at = excluded.updated_at
            """
            await self._db.execute(sql, (user_id, mode, int(use_custom), voice, builder, raw_content, 
                                       agent_id, agent_source, agent_builder, now))
            await self._db.commit()
        logger.info(f"✅ Prompt config guardada en BD para user_id={user_id} (modo={mode})")

    async def load_prompt_config(self, user_id: int) -> dict | None:
        """Carga la configuración de prompts del usuario desde BD"""
        sql = """
            SELECT mode, use_custom, voice, builder, raw_content, agent_id, agent_source, agent_builder
            FROM prompt_config WHERE user_id = ?
        """
        row = await self.fetch_one(sql, (user_id,))
        if not row:
            return None
        
        try:
            b_val = row.get("builder")
            builder = json.loads(b_val) if b_val and b_val != "null" else {}
        except Exception:
            builder = {}
            
        try:
            ab_val = row.get("agent_builder")
            agent_builder = json.loads(ab_val) if ab_val and ab_val != "null" else {}
        except Exception:
            agent_builder = {}
            
        profile_name = "Preconfigurado"
        try:
            agent_row = await self.fetch_one("SELECT name FROM admin_agents WHERE user_id = ? AND agent_id = ?", (user_id, "active_agent"))
            if agent_row and agent_row.get("name"):
                profile_name = agent_row["name"]
        except Exception:
            pass
        
        return {
            "mode": row.get("mode", "builder"),
            "use_custom": bool(row.get("use_custom", False)),
            "voice": row.get("voice", "Nova"),
            "builder": builder,
            "raw_content": row.get("raw_content", ""),
            "agent_id": row.get("agent_id", ""),
            "agent_source": row.get("agent_source", "preset"),
            "agent_builder": agent_builder,
            "profile_name": profile_name,
        }

    async def delete_prompt_config(self, user_id: int):
        """Elimina la configuración de prompts del usuario de BD"""
        await self.execute("DELETE FROM prompt_config WHERE user_id = ?", (user_id,))
        logger.info(f"Prompt config eliminada para user_id={user_id}")


