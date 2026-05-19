import aiosqlite
import os
import unicodedata
from loguru import logger
from config.settings import get_settings
from database.models import SCHEMA_SQL


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
            fts_query = ' OR '.join(f'"{t}"*' for t in query.split() if t)
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
            fts_query = ' OR '.join(f'"{t}"*' for t in query.split() if t)
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
                       duration: float, actions: str, transcript: str):
        sql = """
            INSERT INTO call_logs (session_id, caller_id, source, duration, actions_taken, transcript)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        await self._db.execute(sql, (session_id, caller_id, source, duration, actions, transcript))
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

    async def delete_extension(self, ext_id: int):
        await self._db.execute("DELETE FROM extensions WHERE id = ?", (ext_id,))
        await self._db.commit()

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

    async def delete_inventory_item(self, item_id: int):
        await self._db.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
        await self._db.commit()

    # ── CALL LOGS ──────────────────────────────────────────────────────────────

    async def get_call_logs(self, limit: int = 50) -> list[dict]:
        sql = "SELECT * FROM call_logs ORDER BY created_at DESC LIMIT ?"
        async with self._db.execute(sql, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
