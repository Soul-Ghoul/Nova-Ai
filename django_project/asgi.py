import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
django.setup()

from django.core.asgi import get_asgi_application
from config.settings import get_settings
from realtime.app import fastapi_app

django_asgi_app = get_asgi_application()
settings = get_settings()

run_mode = os.environ.get("SERVICE_TYPE", getattr(settings, "run_mode", "hybrid")).lower()

_initialized = False
_init_lock = None


async def init_django_only():
    global _initialized, _init_lock
    if not _initialized:
        if _init_lock is None:
            import asyncio
            _init_lock = asyncio.Lock()
        async with _init_lock:
            if not _initialized:
                from django_project.state import init_resources
                await init_resources()
                _initialized = True


async def application(scope, receive, send):
    if run_mode == "hybrid":
        if scope["type"] in ("lifespan", "websocket"):
            await fastapi_app(scope, receive, send)
        else:
            await django_asgi_app(scope, receive, send)
    elif run_mode == "realtime":
        await fastapi_app(scope, receive, send)
    else:
        await init_django_only()
        await django_asgi_app(scope, receive, send)

