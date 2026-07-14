import time
from loguru import logger
from core.security import SecurityGuard
from ai.router import IntelligentRouter
from ai.inventory_worker import InventoryWorker
from core.cache import (
    cache_get, cache_set,
    semantic_cache_get, semantic_cache_set,
    record_tool_execution,
)

_worker: InventoryWorker | None = None


def set_worker(worker: InventoryWorker):
    global _worker
    _worker = worker


async def handle_lookup_inventory(product_query: str, session=None, **kwargs) -> dict:
    start_time = time.perf_counter()

    if SecurityGuard.is_injection(product_query):
        return {"output": SecurityGuard.get_safe_response()}

    route_res = IntelligentRouter.route(product_query)
    if route_res:
        return {"output": route_res["response"]}

    if not _worker:
        return {"output": "Sistema de inventario no disponible."}

    # ── L1: Buscar en Redis (consulta exacta) ────────────────────────────
    cached = await cache_get("inventory", product_query)
    if cached:
        elapsed = (time.perf_counter() - start_time) * 1000
        logger.info(f"[CACHE] Inventario '{product_query}' servido desde Redis en {elapsed:.1f}ms")
        await record_tool_execution("lookup_inventory", product_query, elapsed, cache_hit=True, cache_level="L1")
        return {"output": cached}

    # ── L2: Buscar en caché semántica (consulta similar) ─────────────────
    semantic_result = await semantic_cache_get("inventory", product_query)
    if semantic_result:
        elapsed = (time.perf_counter() - start_time) * 1000
        logger.info(f"[CACHE] Inventario '{product_query}' servido desde caché semántica en {elapsed:.1f}ms")
        await record_tool_execution("lookup_inventory", product_query, elapsed, cache_hit=True, cache_level="L2")
        return {"output": semantic_result}

    # ── L3: Source of Truth (base de datos / API externa) ────────────────
    result = await _worker.process(product_query, session)

    # Guardar en L1 (Redis) y L2 (Semántica) para futuras consultas
    await cache_set("inventory", product_query, result)
    await semantic_cache_set("inventory", product_query, result)

    elapsed = (time.perf_counter() - start_time) * 1000
    logger.info(f"Inventario '{product_query}': Worker retornó {len(result)} chars ({elapsed:.1f}ms)")
    await record_tool_execution("lookup_inventory", product_query, elapsed)
    return {"output": result}

