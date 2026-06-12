from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

from django_project.state import init_resources, close_resources
from realtime.voice_ws import router as voice_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ASGI Lifespan: Inicializando recursos globales...")
    await init_resources()
    logger.info("ASGI Lifespan: Inicialización completada exitosamente.")
    yield
    logger.info("ASGI Lifespan: Liberando recursos globales...")
    await close_resources()
    logger.info("ASGI Lifespan: Recursos liberados.")


fastapi_app = FastAPI(
    title="Nova Real-Time Engine",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

fastapi_app.include_router(voice_router)
