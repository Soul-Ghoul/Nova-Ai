from loguru import logger
from core.security import SecurityGuard
from ai.router import IntelligentRouter
from ai.inventory_worker import InventoryWorker
from database.manager import DatabaseManager

_worker: InventoryWorker | None = None
_db: DatabaseManager | None = None


def set_worker(worker: InventoryWorker):
    global _worker
    _worker = worker


def set_db(db: DatabaseManager):
    global _db
    _db = db


async def _get_worker_for_session(session=None) -> InventoryWorker | None:
    if not _db:
        return _worker

    user_id = getattr(session, "user_id", None) if session else None
    if not user_id:
        user_id = 1

    try:
        config = await _db.get_agent_data_source(user_id)
        if not config:
            return _worker

        source_type = config.get("source_type", "internal")

        if source_type == "internal":
            return _worker

        if source_type == "odoo":
            odoo_url = config.get("odoo_url", "")
            odoo_api_key = config.get("odoo_api_key", "")
            if not odoo_url or not odoo_api_key:
                logger.warning(f"[user_id={user_id}] Odoo configurado pero faltan credenciales, usando interno")
                return _worker
            from ai.odoo_worker import get_odoo_worker
            return get_odoo_worker(
                base_url=odoo_url,
                api_key=odoo_api_key,
                db_name=config.get("odoo_db", ""),
                odoo_user=config.get("odoo_user", ""),
                user_id=user_id
            )

        if source_type in ("postgres_local", "postgres_railway"):
            return _worker

    except Exception as e:
        logger.error(f"Error resolviendo data source para user_id={user_id}: {e}")

    return _worker


async def handle_lookup_inventory(product_query: str, session=None, **kwargs) -> dict:
    if SecurityGuard.is_injection(product_query):
        return {"output": SecurityGuard.get_safe_response()}

    route_res = IntelligentRouter.route(product_query)
    if route_res:
        return {"output": route_res["response"]}

    worker = await _get_worker_for_session(session)
    if not worker:
        return {"output": "Sistema de inventario no disponible."}

    result = await worker.process(product_query, session)
    logger.info(f"Inventario '{product_query}': Worker retornó {len(result)} chars")
    return {"output": result}
