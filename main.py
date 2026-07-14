import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger

from config.settings import get_settings
from core.session import SessionManager
from core.audio_processor import AudioProcessor
from core.vad import VoiceActivityDetector
from ai.gemini_live import GeminiLiveClient
from ai.function_registry import FunctionRegistry
from ai.prompt_loader import PromptLoader
from database.manager import DatabaseManager
from database.seed import seed_database
from telephony.audiosocket_server import AudioSocketServer
from telephony.ami_client import AMIClient
from api.admin import router as admin_router, set_dependencies as set_admin_deps
from api.health import router as health_router
from core.cache import init_redis, close_redis, init_semantic_cache
from actions.lookup_extension import (
    handle_lookup_extension,
    set_db as set_lookup_ext_db,
)
from actions.lookup_inventory import (
    handle_lookup_inventory,
    set_worker as set_lookup_inv_worker,
)
from ai.inventory_worker import InventoryWorker
from actions.transfer_call import (
    handle_transfer_call,
    set_dependencies as set_transfer_deps,
)
from actions.end_call import handle_end_call
from actions.pms_hotel import (
    handle_pms_check_rooms,
    handle_pms_room_status,
    handle_pms_get_reservations,
    handle_pms_create_reservation,
    handle_pms_query,
)

settings = get_settings()
PROJECT_ROOT = Path(__file__).resolve().parent
FRONT_DIST_DIR = PROJECT_ROOT / "front" / "dist"
FRONT_ASSETS_DIR = FRONT_DIST_DIR / "assets"
db = DatabaseManager()
session_manager = SessionManager()
prompt_loader = PromptLoader()
function_registry = FunctionRegistry()
ami_client = AMIClient()
gemini_client: GeminiLiveClient | None = None
audiosocket_server: AudioSocketServer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global gemini_client, audiosocket_server

    logger.info("=" * 60)
    logger.info("  Nova Voice Agent — Iniciando...")
    logger.info("=" * 60)

    await db.connect()
    
    # Sincronizar instancias globales con django_project.state para módulos dependientes
    import django_project.state
    django_project.state.db = db
    django_project.state.ami_client = ami_client

    await seed_database(db)

    # Inicializar sistema de caché
    await init_redis(settings.redis_url)
    genai_client = None
    if settings.gemini_api_key:
        from google import genai as _genai
        genai_client = _genai.Client(api_key=settings.gemini_api_key)
    await init_semantic_cache(db._db, genai_client)

    set_lookup_ext_db(db)
    worker = InventoryWorker(db)
    set_lookup_inv_worker(worker)
    set_transfer_deps(db, ami_client)
    set_admin_deps(db, session_manager, prompt_loader)

    function_registry.register("transfer_call", handle_transfer_call)
    function_registry.register("lookup_extension", handle_lookup_extension)
    function_registry.register("lookup_inventory", handle_lookup_inventory)
    function_registry.register("end_call", handle_end_call)
    function_registry.register("pms_check_rooms", handle_pms_check_rooms)
    function_registry.register("pms_room_status", handle_pms_room_status)
    function_registry.register("pms_get_reservations", handle_pms_get_reservations)
    function_registry.register("pms_create_reservation", handle_pms_create_reservation)
    function_registry.register("pms_query", handle_pms_query)
    logger.info(f"Funciones registradas: {function_registry.registered_functions}")

    await ami_client.connect()

    gemini_client = GeminiLiveClient(function_registry, prompt_loader)

    audiosocket_server = AudioSocketServer(session_manager, gemini_client)
    await audiosocket_server.start()

    logger.info("=" * 60)
    logger.info(f"  Nova lista en http://{settings.nova_host}:{settings.nova_port}")
    logger.info(f"  AudioSocket en {settings.audiosocket_host}:{settings.audiosocket_port}")
    logger.info(f"  Panel Admin: http://{settings.nova_host}:{settings.nova_port}/admin")
    logger.info("=" * 60)

    yield

    logger.info("Nova Voice Agent — Cerrando...")
    if audiosocket_server:
        await audiosocket_server.stop()
    await ami_client.disconnect()
    await close_redis()
    await db.disconnect()
    logger.info("Nova Voice Agent — Cerrado.")


app = FastAPI(
    title="Nova Voice Agent",
    description="Microservicio de asistente de voz IA en tiempo real",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(admin_router)

if FRONT_DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONT_ASSETS_DIR)), name="assets")


@app.get("/")
async def serve_index():
    return FileResponse(FRONT_DIST_DIR / "index.html")


@app.get("/admin")
async def serve_admin():
    return FileResponse(FRONT_DIST_DIR / "index.html")


@app.get("/favicon.svg")
async def serve_favicon():
    return FileResponse(FRONT_DIST_DIR / "favicon.svg")


@app.get("/icons.svg")
async def serve_icons():
    return FileResponse(FRONT_DIST_DIR / "icons.svg")


@app.websocket("/ws/voice")
async def websocket_voice(websocket: WebSocket):
    await websocket.accept()
    session = await session_manager.create_session(source="web")
    logger.info(f"WebSocket de voz conectado: {session.session_id}")

    vad = VoiceActivityDetector()

    try:
        gemini_task = asyncio.create_task(
            gemini_client.start_session(session)
        )

        send_task = asyncio.create_task(
            _send_audio_to_browser(session, websocket)
        )

        while session.active:
            data = await websocket.receive()

            if "bytes" in data:
                audio_bytes = data["bytes"]
                pcm_16khz = AudioProcessor.browser_to_gemini(audio_bytes)
                if vad.is_speech(pcm_16khz):
                    try:
                        session.audio_queue_in.put_nowait(pcm_16khz)
                    except asyncio.QueueFull:
                        try:
                            session.audio_queue_in.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        session.audio_queue_in.put_nowait(pcm_16khz)
                        logger.debug(f"[{session.session_id}] Cola de audio llena: se descarta frame antiguo.")

            elif "text" in data:
                msg = json.loads(data["text"])
                if msg.get("type") == "end":
                    break

    except WebSocketDisconnect:
        logger.info(f"WebSocket desconectado: {session.session_id}")
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}")
    finally:
        session.active = False
        await session.audio_queue_in.put(None)

        if gemini_task and not gemini_task.done():
            gemini_task.cancel()
            try:
                await gemini_task
            except (asyncio.CancelledError, Exception):
                pass

        ended = await session_manager.end_session(session.session_id, "websocket_disconnect")
        if ended:
            try:
                await db.log_call(
                    session_id=ended.session_id,
                    caller_id=ended.caller_id or "web",
                    source=ended.source,
                    duration=round(ended.duration, 2),
                    actions=str(ended.metadata.get("actions", [])),
                    transcript="",
                    tokens_input=ended.tokens_input,
                    tokens_output=ended.tokens_output,
                )
            except Exception as _log_err:
                logger.warning(f"No se pudo registrar log de llamada: {_log_err}")
        logger.info(f"Sesión WebSocket limpiada: {session.session_id}")


async def _send_audio_to_browser(session, websocket: WebSocket):
    try:
        while session.active:
            try:
                audio_data = await asyncio.wait_for(
                    session.audio_queue_out.get(), timeout=0.5
                )
                if audio_data is None:
                    break

                pcm_16khz = AudioProcessor.gemini_to_browser(audio_data)
                await websocket.send_bytes(pcm_16khz)

            except asyncio.TimeoutError:
                continue
    except Exception as e:
        if session.active:
            logger.debug(f"Send audio to browser cerrado: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.nova_host,
        port=settings.nova_port,
        reload=settings.nova_debug,
        log_level="info",
    )
