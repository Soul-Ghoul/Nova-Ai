import time
import json
from loguru import logger
from database.manager import DatabaseManager
from core.security import SecurityGuard
from ai.router import IntelligentRouter
from core.cache import cache_get, cache_set, record_tool_execution

_db: DatabaseManager | None = None

MAX_RESULTS = 2


def set_db(db: DatabaseManager):
    global _db
    _db = db


async def handle_lookup_extension(query: str, **kwargs) -> dict:
    start_time = time.perf_counter()
    cache_hit = False
    cache_level = "none"

    if SecurityGuard.is_injection(query):
        return {"output": SecurityGuard.get_safe_response()}

    route_res = IntelligentRouter.route(query)
    if route_res:
        return {"output": route_res["response"]}

    if not _db:
        return {"output": "Base de datos no disponible."}

    # ── L1: Buscar en Redis ──────────────────────────────────────────────
    cached = await cache_get("extension", query)
    if cached:
        cache_hit = True
        cache_level = "L1_redis"
        elapsed = (time.perf_counter() - start_time) * 1000
        logger.info(f"[CACHE] Extension '{query}' servida desde Redis en {elapsed:.1f}ms")
        await record_tool_execution("lookup_extension", query, elapsed, cache_hit=True, cache_level="L1")
        return {"output": cached}

    # ── L3: Consulta a la base de datos (Source of Truth) ────────────────
    results = await _db.search_extension(query)

    if not results:
        text = f"No se encontró ninguna extensión para '{query}'. Sugiere al usuario intentar con otro nombre o departamento."
        elapsed = (time.perf_counter() - start_time) * 1000
        await record_tool_execution("lookup_extension", query, elapsed)
        return {"output": text}

    top   = results[:MAX_RESULTS]
    total = len(results)

    items = []
    for r in top:
        status = "disponible" if r["available"] else "no disponible"
        items.append(f"{r['name']}, extensión {r['extension']}, departamento {r['department']}, {status}")

    text = f"Encontré {total} resultado(s): " + ". ".join(items) + "."

    if total > MAX_RESULTS:
        text += f" Hay más resultados; pide al usuario que sea más específico con el nombre o departamento."

    # ── Guardar en caché L1 (Redis) ──────────────────────────────────────
    await cache_set("extension", query, text)

    elapsed = (time.perf_counter() - start_time) * 1000
    logger.info(f"Extensión '{query}': {total} total, enviando {len(top)} ({elapsed:.1f}ms)")
    await record_tool_execution("lookup_extension", query, elapsed)
    return {"output": text}

