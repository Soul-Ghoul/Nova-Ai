import aiosqlite
import os
import re
import unicodedata
from loguru import logger
from config.settings import get_settings
from database.models import SCHEMA_SQL
from core.cache import cache_invalidate, semantic_cache_invalidate


def _normalize(text: str) -> str:
    nfd = unicodedata.normalize('NFD', text)
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn').lower()


def _tokenize_query(query: str) -> list[str]:
    """
    Tokeniza el query de forma genérica y escalable.
    Retorna el query completo + tokens individuales + prefijos.
    Sin diccionarios: el AI maneja la traducción via prompt.
    """
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
        self.db_path = get_settings().db_path
        self._db: aiosqlite.Connection | None = None

    @staticmethod
    def _normalize_text(text: str) -> str:
        return _normalize(text)

    async def connect(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()
        await self._rebuild_fts_index()
        logger.info(f"Base de datos conectada: {self.db_path}")

    async def _rebuild_fts_index(self):
        """Reconstruye índices FTS5 para incluir registros previos a la creación del índice."""
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
            logger.info("Base de datos desconectada")

    # ── HELPERS SQL GENÉRICOS ──────────────────────────────────────────────────

    async def execute(self, sql: str, params: tuple = ()):
        """Ejecuta una consulta SQL genérica que no retorna filas."""
        await self._db.execute(sql, params)
        await self._db.commit()

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        """Retorna una sola fila como diccionario o None."""
        async with self._db.execute(sql, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """Retorna todas las filas resultantes como una lista de diccionarios."""
        async with self._db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_agent_data_source(self, user_id: int) -> dict | None:
        """Obtiene la configuración de datos (PMS u Odoo) asignada a un usuario."""
        sql = "SELECT * FROM agent_data_source WHERE user_id = ?"
        return await self.fetch_one(sql, (user_id,))

    # ── BÚSQUEDA EXTENSIONES ───────────────────────────────────────────────────

    async def search_extension(self, query: str) -> list[dict]:
        """Búsqueda multilingüe: FTS5 primero, token-search como fallback."""
        norm_query = _normalize(query)
        logger.info(f"[SEARCH] extension='{query}'")
        results = await self._fts_search_extensions(norm_query)
        if not results:
            results = await self._token_search_extensions(norm_query)
        logger.info(f"[SEARCH] extension results: {len(results)}")
        return results

    async def _fts_search_extensions(self, query: str) -> list[dict]:
        """FTS5: busca en name y department simultáneamente."""
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
            async with self._db.execute(sql, (fts_query,)) as cursor:
                rows = await cursor.fetchall()
            return [{
                "name": r["name"], "extension": r["extension"],
                "department": r["department"], "email": r["email"],
                "available": r["available"]
            } for r in rows]
        except Exception as e:
            logger.debug(f"FTS5 extension error (usando fallback): {e}")
            return []

    async def _token_search_extensions(self, norm_query: str) -> list[dict]:
        """Token-search: fallback para búsquedas numéricas o BD sin FTS5."""
        terms = _tokenize_query(norm_query)
        async with self._db.execute("SELECT * FROM extensions") as cursor:
            all_rows = await cursor.fetchall()
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

    async def search_inventory(self, query: str) -> list[dict]:
        """Búsqueda multilingüe: FTS5 primero, token-search como fallback."""
        norm_query = _normalize(query)
        logger.info(f"[SEARCH] inventory='{query}'")
        results = await self._fts_search_inventory(norm_query)
        if not results:
            results = await self._token_search_inventory(norm_query)
        logger.info(f"[SEARCH] inventory results: {len(results)}")
        return results

    async def _fts_search_inventory(self, query: str) -> list[dict]:
        """FTS5: busca en name, description, category, brand, color simultáneamente."""
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
            async with self._db.execute(sql, (fts_query,)) as cursor:
                rows = await cursor.fetchall()
            return [{
                "product_name": r["product_name"], "description": r["description"],
                "price": r["price"], "stock": r["stock"],
                "category": r["category"], "brand": r["brand"],
                "color": r["color"], "weight": r["weight"]
            } for r in rows]
        except Exception as e:
            logger.debug(f"FTS5 inventory error (usando fallback): {e}")
            return []

    async def _token_search_inventory(self, norm_query: str) -> list[dict]:
        """Token-search: fallback para BD sin FTS5."""
        terms = _tokenize_query(norm_query)
        async with self._db.execute("SELECT * FROM inventory") as cursor:
            all_rows = await cursor.fetchall()
        seen, results = set(), []
        for row in all_rows:
            n = _normalize(row["product_name"])
            c = _normalize(row["category"])
            d = _normalize(row["description"])
            b = _normalize(row["brand"])
            for t in terms:
                if t in n or t in c or t in d or t in b:
                    if row["id"] not in seen:
                        seen.add(row["id"])
                        results.append({
                            "product_name": row["product_name"], "description": row["description"],
                            "price": row["price"], "stock": row["stock"],
                            "category": row["category"], "brand": row["brand"],
                            "color": row["color"], "weight": row["weight"]
                        })
                    break
        return results

    # ── LOGS ───────────────────────────────────────────────────────────────────

    async def log_call(self, session_id: str, caller_id: str, source: str,
                       duration: float, actions: str, transcript: str,
                       tokens_input: int = 0, tokens_output: int = 0):
        from datetime import datetime
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tokens_total = tokens_input + tokens_output
        cost_usd = (tokens_input * 0.000001) + (tokens_output * 0.000002)
        sql = """
            INSERT INTO call_logs
                (session_id, caller_id, source, duration, actions_taken, transcript,
                 tokens_input, tokens_output, tokens_total, cost_usd, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await self._db.execute(sql, (
            session_id, caller_id, source, duration, actions, transcript,
            tokens_input, tokens_output, tokens_total, cost_usd, created_at
        ))
        await self._db.commit()
        await self._upsert_daily_usage(tokens_input, tokens_output, tokens_total, cost_usd)

    async def _upsert_daily_usage(self, tin: int, tout: int, ttotal: int, cost: float):
        from datetime import date, datetime
        today = date.today().isoformat()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sql = """
            INSERT INTO token_usage_daily (date, total_calls, tokens_input, tokens_output, tokens_total, cost_usd, updated_at)
            VALUES (?, 1, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_calls   = total_calls + 1,
                tokens_input  = tokens_input + excluded.tokens_input,
                tokens_output = tokens_output + excluded.tokens_output,
                tokens_total  = tokens_total + excluded.tokens_total,
                cost_usd      = cost_usd + excluded.cost_usd,
                updated_at    = excluded.updated_at
        """
        await self._db.execute(sql, (today, tin, tout, ttotal, cost, now))
        await self._db.commit()

    # ── EXTENSIONES CRUD ───────────────────────────────────────────────────────

    async def get_all_extensions(self) -> list[dict]:
        async with self._db.execute("SELECT * FROM extensions ORDER BY name") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def add_extension(self, name: str, extension: str, department: str = "", email: str = ""):
        sql = "INSERT INTO extensions (name, extension, department, email) VALUES (?, ?, ?, ?)"
        await self._db.execute(sql, (name, extension, department, email))
        await self._db.commit()
        # Invalidar caché de extensiones
        await cache_invalidate("extension")
        logger.debug("Caché de extensiones invalidada tras agregar")

    async def delete_extension(self, ext_id: int):
        await self._db.execute("DELETE FROM extensions WHERE id = ?", (ext_id,))
        await self._db.commit()
        # Invalidar caché de extensiones
        await cache_invalidate("extension")
        logger.debug("Caché de extensiones invalidada tras eliminar")

    # ── INVENTARIO CRUD ────────────────────────────────────────────────────────

    async def get_all_inventory(self) -> list[dict]:
        async with self._db.execute("SELECT * FROM inventory ORDER BY product_name") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def add_inventory_item(self, product_name: str, description: str,
                                 price: float, stock: int, category: str,
                                 brand: str = "", color: str = "", weight: str = ""):
        sql = """INSERT INTO inventory (product_name, description, price, stock, category, brand, color, weight)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
        await self._db.execute(sql, (product_name, description, price, stock, category, brand, color, weight))
        await self._db.commit()
        # Invalidar caché de inventario (L1 + L2)
        await cache_invalidate("inventory")
        await semantic_cache_invalidate("inventory")
        logger.debug("Caché de inventario invalidada tras agregar")

    async def delete_inventory_item(self, item_id: int):
        await self._db.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
        await self._db.commit()
        # Invalidar caché de inventario (L1 + L2)
        await cache_invalidate("inventory")
        await semantic_cache_invalidate("inventory")
        logger.debug("Caché de inventario invalidada tras eliminar")

    # ── CALL LOGS ──────────────────────────────────────────────────────────────

    async def get_call_logs(self, limit: int = 50) -> list[dict]:
        sql = "SELECT * FROM call_logs ORDER BY created_at DESC LIMIT ?"
        async with self._db.execute(sql, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_token_stats_summary(self) -> dict:
        sql = """
            SELECT
                COUNT(*) as total_calls,
                COALESCE(SUM(tokens_input),0)  as tokens_input,
                COALESCE(SUM(tokens_output),0) as tokens_output,
                COALESCE(SUM(tokens_total),0)  as tokens_total,
                COALESCE(SUM(cost_usd),0)      as cost_usd,
                COALESCE(AVG(tokens_total),0)  as avg_tokens_per_call
            FROM call_logs
        """
        async with self._db.execute(sql) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {}

    async def get_token_usage_daily(self, days: int = 30) -> list[dict]:
        sql = """
            SELECT date, total_calls, tokens_input, tokens_output, tokens_total, cost_usd
            FROM token_usage_daily
            ORDER BY date DESC
            LIMIT ?
        """
        async with self._db.execute(sql, (days,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_top_calls_by_cost(self, limit: int = 10) -> list[dict]:
        sql = """
            SELECT session_id, caller_id, source, duration,
                   tokens_input, tokens_output, tokens_total, cost_usd, created_at
            FROM call_logs
            ORDER BY cost_usd DESC
            LIMIT ?
        """
        async with self._db.execute(sql, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ── PROMPTS CONFIG CRUD ────────────────────────────────────────────────────

    async def load_prompt_config(self, user_id: int) -> dict | None:
        """Carga la configuración del prompt para un usuario desde la base de datos."""
        import json
        sql = "SELECT * FROM prompt_config WHERE user_id = ?"
        row = await self.fetch_one(sql, (user_id,))
        if not row:
            return None
        res = dict(row)
        for key in ("builder", "agent_builder"):
            if res.get(key) and isinstance(res[key], str):
                try:
                    res[key] = json.loads(res[key])
                except Exception:
                    res[key] = {}
        return res

    async def save_prompt_config(self, user_id: int, config: dict):
        """Guarda o actualiza la configuración del prompt de un usuario."""
        import json
        builder_str = json.dumps(config.get("builder", {}) or {})
        agent_builder_str = json.dumps(config.get("agent_builder", {}) or {})
        
        sql = """
            INSERT INTO prompt_config (user_id, mode, use_custom, voice, builder, raw_content, agent_id, agent_source, agent_builder)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                mode = excluded.mode,
                use_custom = excluded.use_custom,
                voice = excluded.voice,
                builder = excluded.builder,
                raw_content = excluded.raw_content,
                agent_id = excluded.agent_id,
                agent_source = excluded.agent_source,
                agent_builder = excluded.agent_builder,
                updated_at = CURRENT_TIMESTAMP
        """
        await self.execute(sql, (
            user_id, config.get("mode", "builder"), config.get("use_custom", 0),
            config.get("voice", "Nova"), builder_str, config.get("raw_content", ""),
            config.get("agent_id", ""), config.get("agent_source", "preset"),
            agent_builder_str
        ))
