"""
Nova Cache Manager — Sistema Inteligente de Caché de 3 Niveles
L1: Redis (caché de alta velocidad para consultas exactas)
L2: Caché Semántica (embeddings + similitud coseno en SQLite)
L3: Source of Truth (base de datos / API externa)
"""
import json
import time
import hashlib
import struct
import math
from datetime import datetime
from typing import Optional

from loguru import logger

# ── L1: Redis (Opcional — fallback silencioso si no está disponible) ───────────

_redis_client = None
_redis_available = False


async def init_redis(url: str = "redis://localhost:6379"):
    """Inicializa la conexión a Redis. Si falla, continúa sin caché L1."""
    global _redis_client, _redis_available
    try:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(url, decode_responses=True)
        await _redis_client.ping()
        _redis_available = True
        logger.info("✅ Redis conectado — Caché L1 activa")
    except Exception as e:
        _redis_available = False
        _redis_client = None
        logger.warning(f"⚠️ Redis no disponible ({e}). Continuando sin caché L1.")


async def close_redis():
    """Cierra la conexión a Redis."""
    global _redis_client, _redis_available
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        _redis_available = False
        logger.info("Redis desconectado")


# ── L1: Operaciones de Caché Redis ─────────────────────────────────────────────

# TTLs configurables por tipo de dato (en segundos)
CACHE_TTLS = {
    "extension":  3600,    # 1 hora — extensiones casi nunca cambian
    "inventory":  60,      # 1 minuto — inventario/habitaciones cambian frecuentemente
    "static":     21600,   # 6 horas — datos estáticos (WiFi, horarios, políticas)
}


def _make_cache_key(namespace: str, query: str) -> str:
    """Genera una clave de caché normalizada: 'nova:extension:recepcion'"""
    normalized = query.strip().lower()
    return f"nova:{namespace}:{normalized}"


async def cache_get(namespace: str, query: str) -> Optional[str]:
    """Busca un valor en la caché L1 (Redis). Retorna None si no existe o Redis no está disponible."""
    if not _redis_available or not _redis_client:
        return None
    try:
        key = _make_cache_key(namespace, query)
        value = await _redis_client.get(key)
        if value:
            logger.debug(f"[CACHE L1 HIT] {key}")
            await _record_stat("cache_l1_hit", namespace, query)
        return value
    except Exception as e:
        logger.debug(f"[CACHE L1] Error de lectura: {e}")
        return None


async def cache_set(namespace: str, query: str, value: str, ttl: Optional[int] = None):
    """Guarda un valor en la caché L1 (Redis) con TTL automático por tipo."""
    if not _redis_available or not _redis_client:
        return
    try:
        key = _make_cache_key(namespace, query)
        if ttl is None:
            ttl = CACHE_TTLS.get(namespace, 300)
        await _redis_client.setex(key, ttl, value)
        logger.debug(f"[CACHE L1 SET] {key} (TTL: {ttl}s)")
    except Exception as e:
        logger.debug(f"[CACHE L1] Error de escritura: {e}")


async def cache_invalidate(namespace: str, query: Optional[str] = None):
    """
    Invalida entradas de caché.
    Si se pasa query, invalida solo esa clave.
    Si no, invalida todas las claves del namespace.
    """
    if not _redis_available or not _redis_client:
        return
    try:
        if query:
            key = _make_cache_key(namespace, query)
            await _redis_client.delete(key)
            logger.info(f"[CACHE L1 INVALIDATE] {key}")
        else:
            pattern = f"nova:{namespace}:*"
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await _redis_client.scan(cursor, match=pattern, count=100)
                if keys:
                    await _redis_client.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            if deleted:
                logger.info(f"[CACHE L1 INVALIDATE] {deleted} claves de '{namespace}' eliminadas")
    except Exception as e:
        logger.debug(f"[CACHE L1] Error de invalidación: {e}")


# ── L2: Caché Semántica (Embeddings en SQLite) ────────────────────────────────

_db_connection = None
_genai_client = None

SEMANTIC_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS semantic_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    namespace TEXT NOT NULL,
    query_text TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    embedding BLOB NOT NULL,
    result_data TEXT NOT NULL,
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(namespace, query_hash)
);

CREATE INDEX IF NOT EXISTS idx_semantic_ns ON semantic_cache(namespace);
"""

STATS_SCHEMA = """
CREATE TABLE IF NOT EXISTS nova_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    namespace TEXT DEFAULT '',
    query_text TEXT DEFAULT '',
    tool_name TEXT DEFAULT '',
    response_time_ms REAL DEFAULT 0.0,
    cache_hit INTEGER DEFAULT 0,
    cache_level TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stats_event ON nova_stats(event_type);
CREATE INDEX IF NOT EXISTS idx_stats_date ON nova_stats(created_at);
"""


async def init_semantic_cache(db_connection, genai_client=None):
    """Inicializa la caché semántica creando las tablas necesarias."""
    global _db_connection, _genai_client
    _db_connection = db_connection
    _genai_client = genai_client

    try:
        await _db_connection.executescript(SEMANTIC_CACHE_SCHEMA)
        await _db_connection.executescript(STATS_SCHEMA)
        await _db_connection.commit()
        logger.info("✅ Caché semántica (L2) y estadísticas inicializadas en SQLite")
    except Exception as e:
        logger.error(f"Error inicializando caché semántica: {e}")


def _hash_query(query: str) -> str:
    """Genera un hash MD5 del texto normalizado para búsquedas exactas rápidas."""
    normalized = query.strip().lower()
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def _embed_to_bytes(embedding: list[float]) -> bytes:
    """Convierte una lista de floats a bytes para almacenar en SQLite."""
    return struct.pack(f"{len(embedding)}f", *embedding)


def _bytes_to_embed(data: bytes) -> list[float]:
    """Convierte bytes almacenados a lista de floats."""
    count = len(data) // 4
    return list(struct.unpack(f"{count}f", data))


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Calcula la similitud coseno entre dos vectores."""
    if len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _get_embedding(text: str) -> Optional[list[float]]:
    """Obtiene el embedding de un texto usando la API de Gemini."""
    if not _genai_client:
        return None
    try:
        response = await _genai_client.aio.models.embed_content(
            model="text-embedding-004",
            contents=text,
        )
        return response.embeddings[0].values
    except Exception as e:
        logger.debug(f"[SEMANTIC L2] Error obteniendo embedding: {e}")
        return None


async def semantic_cache_get(
    namespace: str, query: str, similarity_threshold: float = 0.95
) -> Optional[str]:
    """
    Busca en la caché semántica (L2).
    1. Primero busca por hash exacto (ultra rápido).
    2. Si no hay coincidencia exacta, calcula similitud coseno.
    3. Si la similitud supera el umbral (95%), retorna los datos cacheados.
    """
    if not _db_connection:
        return None

    query_hash = _hash_query(query)

    # Paso 1: Búsqueda exacta por hash
    try:
        async with _db_connection.execute(
            "SELECT result_data FROM semantic_cache WHERE namespace = ? AND query_hash = ?",
            (namespace, query_hash),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                await _db_connection.execute(
                    "UPDATE semantic_cache SET hit_count = hit_count + 1 WHERE namespace = ? AND query_hash = ?",
                    (namespace, query_hash),
                )
                await _db_connection.commit()
                logger.debug(f"[SEMANTIC L2 EXACT HIT] {namespace}:{query[:50]}")
                await _record_stat("cache_l2_exact_hit", namespace, query)
                return row[0]
    except Exception as e:
        logger.debug(f"[SEMANTIC L2] Error búsqueda exacta: {e}")

    # Paso 2: Búsqueda semántica por similitud coseno
    query_embedding = await _get_embedding(query)
    if not query_embedding:
        return None

    try:
        async with _db_connection.execute(
            "SELECT query_text, query_hash, embedding, result_data FROM semantic_cache WHERE namespace = ?",
            (namespace,),
        ) as cursor:
            rows = await cursor.fetchall()

        best_match = None
        best_similarity = 0.0

        for row in rows:
            cached_embedding = _bytes_to_embed(row[2])
            similarity = _cosine_similarity(query_embedding, cached_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = row

        if best_match and best_similarity >= similarity_threshold:
            await _db_connection.execute(
                "UPDATE semantic_cache SET hit_count = hit_count + 1 WHERE namespace = ? AND query_hash = ?",
                (namespace, best_match[1]),
            )
            await _db_connection.commit()
            logger.info(
                f"[SEMANTIC L2 HIT] {namespace}: '{query[:40]}' ≈ '{best_match[0][:40]}' "
                f"(similitud: {best_similarity:.2%})"
            )
            await _record_stat("cache_l2_semantic_hit", namespace, query)
            return best_match[3]

    except Exception as e:
        logger.debug(f"[SEMANTIC L2] Error búsqueda semántica: {e}")

    return None


async def semantic_cache_set(namespace: str, query: str, result_data: str):
    """Guarda un resultado en la caché semántica (L2) con su embedding."""
    if not _db_connection:
        return

    query_hash = _hash_query(query)
    embedding = await _get_embedding(query)
    if not embedding:
        return

    try:
        embedding_bytes = _embed_to_bytes(embedding)
        await _db_connection.execute(
            """INSERT OR REPLACE INTO semantic_cache
               (namespace, query_text, query_hash, embedding, result_data)
               VALUES (?, ?, ?, ?, ?)""",
            (namespace, query, query_hash, embedding_bytes, result_data),
        )
        await _db_connection.commit()
        logger.debug(f"[SEMANTIC L2 SET] {namespace}:{query[:50]}")
    except Exception as e:
        logger.debug(f"[SEMANTIC L2] Error guardando: {e}")


async def semantic_cache_invalidate(namespace: str):
    """Invalida toda la caché semántica de un namespace."""
    if not _db_connection:
        return
    try:
        await _db_connection.execute(
            "DELETE FROM semantic_cache WHERE namespace = ?", (namespace,)
        )
        await _db_connection.commit()
        logger.info(f"[SEMANTIC L2 INVALIDATE] Namespace '{namespace}' limpiado")
    except Exception as e:
        logger.debug(f"[SEMANTIC L2] Error invalidando: {e}")


# ── Estadísticas ──────────────────────────────────────────────────────────────

async def _record_stat(
    event_type: str,
    namespace: str = "",
    query: str = "",
    tool_name: str = "",
    response_time_ms: float = 0.0,
    cache_hit: bool = False,
    cache_level: str = "",
):
    """Registra un evento de estadísticas en la tabla nova_stats."""
    if not _db_connection:
        return
    try:
        await _db_connection.execute(
            """INSERT INTO nova_stats
               (event_type, namespace, query_text, tool_name, response_time_ms, cache_hit, cache_level)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event_type, namespace, query[:200], tool_name, response_time_ms, int(cache_hit), cache_level),
        )
        await _db_connection.commit()
    except Exception:
        pass


async def record_tool_execution(
    tool_name: str,
    query: str,
    response_time_ms: float,
    cache_hit: bool = False,
    cache_level: str = "none",
):
    """Registra la ejecución de una herramienta con métricas de rendimiento."""
    await _record_stat(
        event_type="tool_execution",
        namespace=tool_name,
        query=query,
        tool_name=tool_name,
        response_time_ms=response_time_ms,
        cache_hit=cache_hit,
        cache_level=cache_level,
    )


async def get_cache_stats() -> dict:
    """Obtiene un resumen de estadísticas de caché para el panel de administración."""
    if not _db_connection:
        return {}
    try:
        stats = {}

        async with _db_connection.execute(
            "SELECT COUNT(*) FROM nova_stats WHERE event_type = 'tool_execution'"
        ) as cursor:
            row = await cursor.fetchone()
            stats["total_tool_calls"] = row[0] if row else 0

        for level in ["cache_l1_hit", "cache_l2_exact_hit", "cache_l2_semantic_hit"]:
            async with _db_connection.execute(
                "SELECT COUNT(*) FROM nova_stats WHERE event_type = ?", (level,)
            ) as cursor:
                row = await cursor.fetchone()
                stats[level] = row[0] if row else 0

        async with _db_connection.execute(
            "SELECT AVG(response_time_ms) FROM nova_stats WHERE event_type = 'tool_execution'"
        ) as cursor:
            row = await cursor.fetchone()
            stats["avg_response_time_ms"] = round(row[0], 2) if row and row[0] else 0.0

        async with _db_connection.execute(
            """SELECT tool_name, COUNT(*) as cnt
               FROM nova_stats WHERE event_type = 'tool_execution' AND tool_name != ''
               GROUP BY tool_name ORDER BY cnt DESC LIMIT 10"""
        ) as cursor:
            rows = await cursor.fetchall()
            stats["top_tools"] = [{"name": r[0], "count": r[1]} for r in rows]

        async with _db_connection.execute(
            """SELECT namespace, query_text, hit_count
               FROM semantic_cache ORDER BY hit_count DESC LIMIT 10"""
        ) as cursor:
            rows = await cursor.fetchall()
            stats["top_cached_queries"] = [
                {"namespace": r[0], "query": r[1], "hits": r[2]} for r in rows
            ]

        return stats
    except Exception as e:
        logger.debug(f"Error obteniendo estadísticas de caché: {e}")
        return {}
