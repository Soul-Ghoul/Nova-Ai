from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import async_to_sync
from django_project.state import db

class AdminAuthMiddleware:
    """
    Middleware de Django para validar la sesión de administradores.
    Protege todos los endpoints bajo /api/admin/ validando la cookie 'session_token'.
    Inyecta el diccionario del usuario autenticado en request.admin_user.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if path.startswith("/api/"):
            request._dont_enforce_csrf_checks = True

        if path in ["/api/auth/login", "/api/auth/logout"]:
            return self.get_response(request)

        if path.startswith("/api/admin"):
            token = request.COOKIES.get("session_token")
            if not token:
                return JsonResponse({"detail": "No autorizado. Sesión no iniciada."}, status=401)

            try:
                user = async_to_sync(db.validate_session_token)(token)
            except Exception as e:
                response = JsonResponse({
                    "detail": "Error de base de datos al validar sesión.",
                    "error": str(e)
                }, status=500)
                return response

            if not user:
                response = JsonResponse({"detail": "Sesión inválida o expirada."}, status=401)
                response.delete_cookie("session_token", path="/")
                return response

            request.admin_user = user

            if path.startswith("/api/admin/users") and user.get("role") != "admin":
                return JsonResponse({"detail": "No autorizado. Permisos insuficientes."}, status=403)

        return self.get_response(request)

