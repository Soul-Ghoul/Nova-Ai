import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
django.setup()

from django.core.asgi import get_asgi_application
from realtime.app import fastapi_app

django_asgi_app = get_asgi_application()


async def application(scope, receive, send):
    if scope["type"] == "lifespan":
        await fastapi_app(scope, receive, send)
    elif scope["type"] == "websocket":
        await fastapi_app(scope, receive, send)
    elif scope["type"] == "http":
        await django_asgi_app(scope, receive, send)
