import json
from django.http import JsonResponse, HttpResponse
from django_project.state import db
from auth.utils import verify_password

async def login_handler(request):
    """
    Controlador para inicio de sesión de administradores.
    Valida credenciales, genera un session_token seguro y establece una cookie HttpOnly.
    """
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
        identifier = body.get("username", "").strip()
        password = body.get("password", "").strip()

        if not identifier or not password:
            return JsonResponse({"detail": "Usuario y contraseña son requeridos."}, status=400)

        if "@" in identifier:
            user = await db.get_user_by_email(identifier)
        else:
            user = await db.get_user_by_username(identifier)

        if not user:
            return JsonResponse({"detail": "Credenciales inválidas."}, status=401)

        # Verificar contraseña con PBKDF2
        if not verify_password(password, user["password_hash"]):
            return JsonResponse({"detail": "Credenciales inválidas."}, status=401)

        # Crear token de sesión de 24 horas
        token = await db.create_session_token(user["id"])

        response = JsonResponse({
            "success": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"]
            }
        })

        # Configurar cookie segura de sesión HttpOnly
        response.set_cookie(
            "session_token",
            token,
            max_age=24 * 3600,
            httponly=True,
            samesite="Lax",
            secure=request.is_secure(),
            path="/"
        )
        return response

    except Exception as e:
        return JsonResponse({"detail": f"Error interno en login: {str(e)}"}, status=500)

async def logout_handler(request):
    """
    Cierra la sesión del administrador borrando el token de la DB y del cliente.
    """
    token = request.COOKIES.get("session_token")
    if token:
        try:
            await db.delete_session_token(token)
        except Exception:
            pass

    response = JsonResponse({"success": True, "message": "Sesión cerrada exitosamente."})
    response.delete_cookie("session_token", path="/")
    return response

async def check_session_handler(request):
    """
    Verifica si hay una sesión activa y devuelve los datos del administrador.
    """
    if request.method != "GET":
        return HttpResponse(status=405)

    token = request.COOKIES.get("session_token")
    if not token:
        return JsonResponse({"authenticated": False})

    try:
        user = await db.validate_session_token(token)
    except Exception as e:
        return JsonResponse({
            "authenticated": False,
            "error": f"Error de base de datos: {str(e)}"
        }, status=500)

    if not user:
        response = JsonResponse({"authenticated": False})
        response.delete_cookie("session_token", path="/")
        return response

    return JsonResponse({
        "authenticated": True,
        "user": user
    })
