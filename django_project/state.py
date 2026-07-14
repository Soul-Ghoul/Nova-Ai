import asyncio
import os
from loguru import logger
import redis.asyncio as aioredis

from config.settings import get_settings
from core.session import SessionManager
from ai.gemini_live import GeminiLiveClient
from ai.function_registry import FunctionRegistry
from ai.prompt_loader import PromptLoader
from database.manager import DatabaseManager
from database.seed import seed_database
from telephony.audiosocket_server import AudioSocketServer
from telephony.ami_client import AMIClient

from actions.lookup_extension import (
    handle_lookup_extension,
    set_db as set_lookup_ext_db,
)
from actions.lookup_inventory import (
    handle_lookup_inventory,
    set_worker as set_lookup_inv_worker,
    set_db as set_lookup_inv_db,
)
from ai.inventory_worker import InventoryWorker
from actions.transfer_call import (
    handle_transfer_call,
    set_dependencies as set_transfer_deps,
)
from actions.end_call import handle_end_call
from actions.create_odoo_order import handle_create_odoo_order
from actions.search_odoo_contacts import handle_search_odoo_contacts
from actions.create_odoo_mailing import handle_create_odoo_mailing
from actions.pms_hotel import (
    handle_pms_check_rooms,
    handle_pms_room_status,
    handle_pms_get_reservations,
    handle_pms_create_reservation,
    handle_pms_query,
)
from api.admin import set_dependencies as set_admin_deps

from core.exchange_updater import ExchangeRateUpdater

# Instancias globales
settings = get_settings()
db = DatabaseManager()
session_manager = SessionManager()
prompt_loader = PromptLoader()
function_registry = FunctionRegistry()
ami_client = AMIClient()
gemini_client: GeminiLiveClient | None = None
audiosocket_server: AudioSocketServer | None = None
exchange_updater: ExchangeRateUpdater | None = None
redis_client: aioredis.Redis | None = None

async def _restore_prompt_configs():
    try:
        import os
        import json
        
        logger.info("Iniciando restauración de configuraciones de prompts desde la base de datos...")
        prompts_dir = prompt_loader.prompts_dir
        os.makedirs(prompts_dir, exist_ok=True)
        os.makedirs("data", exist_ok=True)
        
        configs_by_user = {}
        
        # 1. Cargar y restaurar desde prompt_config
        try:
            sql_configs = "SELECT user_id, mode, use_custom, voice, builder, raw_content, agent_id, agent_source, agent_builder FROM prompt_config"
            configs_rows = await db.fetch_all(sql_configs)
            logger.info(f"Cargando {len(configs_rows)} registros de prompt_config para restauración...")
            for r in configs_rows:
                u_id = r["user_id"]
                try:
                    b_val = r["builder"]
                    builder = json.loads(b_val) if b_val and b_val != "null" else {}
                    ab_val = r["agent_builder"]
                    agent_builder = json.loads(ab_val) if ab_val and ab_val != "null" else {}
                except Exception:
                    builder = {}
                    agent_builder = {}
                
                configs_by_user[u_id] = {
                    "mode": r["mode"],
                    "use_custom": bool(r["use_custom"]),
                    "voice": r["voice"] or "Nova",
                    "builder": builder,
                    "raw_content": r["raw_content"] or "",
                    "agent_id": r["agent_id"] or "",
                    "agent_source": r["agent_source"] or "preset",
                    "agent_builder": agent_builder,
                }
        except Exception as err:
            logger.error(f"Error restaurando desde tabla prompt_config: {err}")

        # 2. Cargar y restaurar archivos físicos desde admin_agents (active_agent)
        try:
            sql = "SELECT user_id, name, system_prompt, builder_config FROM admin_agents WHERE agent_id = ?"
            rows = await db.fetch_all(sql, ("active_agent",))
            logger.info(f"Cargados {len(rows)} agentes activos desde admin_agents para restauración...")
            
            for r in rows:
                u_id = r["user_id"]
                system_prompt = r["system_prompt"]
                builder_config_str = r.get("builder_config") or "{}"
                
                try:
                    agent_config = json.loads(builder_config_str)
                except Exception:
                    agent_config = {}
                
                if not agent_config:
                    continue
                
                # Si el usuario no estaba en configs_by_user, inicializarlo
                if u_id not in configs_by_user:
                    configs_by_user[u_id] = agent_config
                else:
                    for key, val in agent_config.items():
                        if key not in configs_by_user[u_id] or (key in ("pms_agent_type", "odoo_agent_type", "agent_id", "agent_source", "mode") and val):
                            configs_by_user[u_id][key] = val
                
                agent_name = r.get("name") or ""
                if agent_name:
                    configs_by_user[u_id]["profile_name"] = agent_name
                
                # Escribir los archivos físicos correspondientes al agente activo
                mode = agent_config.get("mode", "none")
                if mode == "builder":
                    filepath = os.path.join(prompts_dir, f"nova_builder_{u_id}.md")
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(system_prompt)
                elif mode == "raw":
                    filepath = os.path.join(prompts_dir, f"nova_default_{u_id}.yaml")
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(system_prompt)
                elif mode == "agent":
                    agent_id = agent_config.get("agent_id")
                    agent_source = agent_config.get("agent_source", "preset")
                    
                    if agent_source == "custom" and agent_id:
                        filepath = os.path.join(prompts_dir, f"nova_custom_{agent_id}.md")
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(system_prompt)
        except Exception as err:
            logger.error(f"Error procesando agentes activos de admin_agents: {err}")

        # 3. Guardar todas las configs enriquecidas localmente y cachearlas
        for u_id, config_data in configs_by_user.items():
            try:
                # Reparar en la BD si no existe registro en prompt_config
                try:
                    sql_check = "SELECT 1 FROM prompt_config WHERE user_id = ?"
                    has_pc = await db.fetch_one(sql_check, (u_id,))
                    if not has_pc:
                        logger.warning(f"Usuario {u_id} tenía agente activo pero no registro en prompt_config. Reparando en BD...")
                        await db.save_prompt_config(u_id, config_data)
                except Exception as dberr:
                    logger.error(f"Error reparando prompt_config en BD: {dberr}")

                config_path = prompt_loader._get_config_path(u_id)
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
                prompt_loader.set_prompt_config_cache(u_id, config_data)
            except Exception as w_err:
                logger.error(f"Error guardando JSON local para user_id {u_id}: {w_err}")
                
        logger.info("Restauración de agentes activos completada exitosamente.")
    except Exception as e:
        logger.error(f"Error general en restauración de agentes activos: {e}")


async def init_resources():
    global gemini_client, audiosocket_server, exchange_updater, redis_client

    run_mode = os.environ.get("SERVICE_TYPE", settings.run_mode).lower()
    logger.info("=" * 60)
    logger.info(f"  Nova Voice Agent — Iniciando en modo: {run_mode.upper()}...")
    logger.info("=" * 60)

    # Conectar base de datos primero (compartida en todos los modos)
    await db.connect()

    # Inicializar Redis (compartido en todos los modos, con fallback silencioso)
    if settings.redis_url:
        try:
            redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
            await asyncio.wait_for(redis_client.ping(), timeout=2.0)
            logger.info("✅ Conectado exitosamente a Redis")
            from core.events import event_bus
            event_bus.start_listener()
        except Exception as re:
            redis_client = None
            logger.warning(f"⚠️ No se pudo conectar a Redis: {re}. Continuando sin caché de Redis.")

    if run_mode in ("hybrid", "django"):
        await seed_database(db)
        await _restore_prompt_configs()

    # Configurar dependencias
    set_lookup_ext_db(db)
    set_lookup_inv_db(db)
    worker = InventoryWorker(db)
    set_lookup_inv_worker(worker)
    set_transfer_deps(db, ami_client)
    set_admin_deps(db, session_manager, prompt_loader)

    # Registrar funciones comunes
    function_registry.register("transfer_call", handle_transfer_call)
    function_registry.register("lookup_extension", handle_lookup_extension)
    function_registry.register("lookup_inventory", handle_lookup_inventory)
    function_registry.register("end_call", handle_end_call)
    function_registry.register("create_odoo_order", handle_create_odoo_order)
    function_registry.register("search_odoo_contacts", handle_search_odoo_contacts)
    function_registry.register("create_odoo_mailing", handle_create_odoo_mailing)
    function_registry.register("pms_check_rooms", handle_pms_check_rooms)
    function_registry.register("pms_room_status", handle_pms_room_status)
    function_registry.register("pms_get_reservations", handle_pms_get_reservations)
    function_registry.register("pms_create_reservation", handle_pms_create_reservation)
    function_registry.register("pms_query", handle_pms_query)

    # Solo levantar servicios de voz en modo realtime u híbrido
    if run_mode in ("hybrid", "realtime"):
        exchange_updater = ExchangeRateUpdater()
        exchange_updater.start()

        logger.info(f"Funciones registradas: {function_registry.registered_functions}")
        await ami_client.connect()
        gemini_client = GeminiLiveClient(function_registry, prompt_loader)

        audiosocket_server = AudioSocketServer(session_manager, gemini_client)
        await audiosocket_server.start()

    logger.info("=" * 60)
    if run_mode in ("hybrid", "django"):
        logger.info(f"  Nova Admin listo en http://{settings.nova_host}:{settings.nova_port}")
        logger.info(f"  Panel Admin: http://{settings.nova_host}:{settings.nova_port}/admin")
    if run_mode in ("hybrid", "realtime"):
        logger.info(f"  AudioSocket escuchando en {settings.audiosocket_host}:{settings.audiosocket_port}")
        logger.info(f"  FastAPI WebSocket listo en ws://{settings.nova_host}:{settings.nova_port}/ws/voice")
    logger.info("=" * 60)

async def close_resources():
    global audiosocket_server, exchange_updater, redis_client
    logger.info("Nova Voice Agent — Cerrando...")
    if exchange_updater:
        try:
            exchange_updater.stop()
        except Exception as e:
            logger.error(f"Error deteniendo actualizador de divisas: {e}")
    if audiosocket_server:
        try:
            await audiosocket_server.stop()
        except Exception as e:
            logger.error(f"Error apagando AudioSocket: {e}")
    try:
        await ami_client.disconnect()
    except Exception as e:
        logger.error(f"Error desconectando AMI Client: {e}")
    if redis_client:
        try:
            from core.events import event_bus
            await event_bus.stop_listener()
        except Exception as e:
            logger.error(f"Error deteniendo listener de eventos: {e}")
        try:
            await redis_client.close()
        except Exception as e:
            logger.error(f"Error cerrando cliente Redis: {e}")
    try:
        await db.disconnect()
    except Exception as e:
        logger.error(f"Error desconectando Base de Datos: {e}")
    logger.info("Nova Voice Agent — Cerrado.")
