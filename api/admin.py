import os
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import uuid
from loguru import logger
from django.http import JsonResponse, HttpResponse
from pydantic import BaseModel
from typing import Optional

_db = None
_session_manager = None
_prompt_loader = None


def _get_prompt_loader():
    global _prompt_loader
    if _prompt_loader is None:
        from ai.prompt_loader import PromptLoader
        _prompt_loader = PromptLoader()
    return _prompt_loader


def set_dependencies(db, session_manager, prompt_loader):
    global _db, _session_manager, _prompt_loader
    _db = db
    _session_manager = session_manager
    _prompt_loader = prompt_loader


class ExtensionCreate(BaseModel):
    name: str
    extension: str
    department: str = ""
    email: str = ""


class InventoryCreate(BaseModel):
    product_name: str
    description: str = ""
    price: float = 0.0
    stock: int = 0
    category: str = ""
    brand: str = ""
    color: str = ""
    weight: str = ""
    tags: str = ""


class PromptUpdate(BaseModel):
    name: str
    content: str


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _is_valid_email(value: str) -> bool:
    return bool(value and EMAIL_RE.match(value.strip()))


def _validate_postgres_connection_string(value: str) -> str | None:
    connection_string = (value or "").strip()
    if not connection_string:
        return "La URL de conexión PostgreSQL es requerida."

    try:
        parsed = urlparse(connection_string)
    except Exception:
        return "La URL de conexión PostgreSQL tiene un formato inválido."

    if parsed.scheme not in ("postgres", "postgresql"):
        return "La URL de conexión PostgreSQL debe iniciar con postgres:// o postgresql://."

    if not parsed.hostname:
        return "La URL de conexión PostgreSQL debe incluir un host válido."

    try:
        port = parsed.port
    except ValueError:
        return "El puerto de PostgreSQL debe ser numérico."

    if port is not None and not (1 <= port <= 65535):
        return "El puerto de PostgreSQL debe estar entre 1 y 65535."

    return None


# --- Extensiones ---
async def extensions_list_create(request):
    if request.method == "GET":
        data = await _db.get_all_extensions()
        return JsonResponse(data, safe=False)
    elif request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
            data = ExtensionCreate(**body)
            await _db.add_extension(data.name, data.extension, data.department, data.email)
            return JsonResponse({"success": True, "message": f"Extensión {data.extension} creada"})
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=400)
    return HttpResponse(status=405)


async def delete_extension(request, ext_id: int):
    if request.method == "DELETE":
        await _db.delete_extension(ext_id)
        return JsonResponse({"success": True})
    return HttpResponse(status=405)


# --- Inventario ---
async def inventory_list_create(request):
    from loguru import logger
    if request.method == "GET":
        try:
            source_type = "internal"
            config = None
            if _db:
                config = await _db.get_agent_data_source(1)
                if config:
                    source_type = config.get("source_type", "internal")

            if source_type == "odoo" and config:
                odoo_url = config.get("odoo_url", "")
                odoo_api_key = config.get("odoo_api_key", "")
                odoo_db = config.get("odoo_db", "")
                odoo_user = config.get("odoo_user", "")

                if odoo_url and odoo_api_key:
                    from ai.odoo_worker import OdooInventoryWorker
                    worker = OdooInventoryWorker(
                        base_url=odoo_url,
                        api_key=odoo_api_key,
                        db_name=odoo_db,
                        odoo_user=odoo_user
                    )
                    
                    fields = [
                        "name", "default_code", "barcode",
                        "list_price", "qty_available",
                        "categ_id"
                    ]
                    
                    odoo_products = await worker._search_read(
                        model="product.product",
                        domain=[["sale_ok", "=", True]],
                        fields=fields,
                        limit=100
                    )
                    
                    formatted = []
                    for idx, p in enumerate(odoo_products):
                        categ_name = "General"
                        categ = p.get("categ_id")
                        if isinstance(categ, (list, tuple)) and len(categ) >= 2:
                            categ_name = categ[1]
                        elif isinstance(categ, str):
                            categ_name = categ

                        formatted.append({
                            "id": p.get("id", idx + 1),
                            "product_name": p.get("name", "Producto Odoo"),
                            "description": f"SKU: {p.get('default_code') or '—'}" + (f" | Código de barras: {p.get('barcode')}" if p.get('barcode') else ""),
                            "price": float(p.get("list_price", 0.0) or 0.0),
                            "stock": int(p.get("qty_available", 0.0) or 0.0),
                            "category": categ_name,
                            "brand": "Odoo API",
                            "color": "",
                            "weight": "",
                            "tags": "Odoo"
                        })
                    return JsonResponse(formatted, safe=False)
        except Exception as e:
            logger.error(f"Error cargando inventario Odoo para admin: {e}")

        data = await _db.get_all_inventory()
        return JsonResponse(data, safe=False)
    elif request.method == "POST":
        try:
            source_type = "internal"
            if _db:
                config = await _db.get_agent_data_source(1)
                if config:
                    source_type = config.get("source_type", "internal")

            if source_type == "odoo":
                return JsonResponse({"detail": "El inventario de Odoo es de sólo lectura. Modifícalo directamente en Odoo."}, status=400)

            body = json.loads(request.body.decode("utf-8"))
            data = InventoryCreate(**body)
            await _db.add_inventory_item(
                data.product_name, data.description,
                data.price, data.stock, data.category,
                data.brand, data.color, data.weight, data.tags
            )
            return JsonResponse({"success": True, "message": f"Producto '{data.product_name}' creado"})
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=400)
    return HttpResponse(status=405)


async def delete_inventory_item(request, item_id: int):
    if request.method == "DELETE":
        source_type = "internal"
        if _db:
            config = await _db.get_agent_data_source(1)
            if config:
                source_type = config.get("source_type", "internal")

        if source_type == "odoo":
            return JsonResponse({"detail": "El inventario de Odoo es de sólo lectura."}, status=400)

        await _db.delete_inventory_item(item_id)
        return JsonResponse({"success": True})
    return HttpResponse(status=405)


# --- Logs ---
async def list_call_logs(request):
    if request.method == "GET":
        limit = int(request.GET.get("limit", 50))
        data = await _db.get_call_logs(limit)
        return JsonResponse(data, safe=False)
    return HttpResponse(status=405)


# --- Sesiones activas ---
async def list_active_sessions(request):
    if request.method == "GET":
        from core.session import TOKEN_LIMIT_PER_SESSION
        sessions = _session_manager.active_sessions
        data = [
            {
                "session_id": s.session_id,
                "source": s.source,
                "caller_id": s.caller_id,
                "duration": round(s.duration, 1),
                "active": s.active,
                "tokens_input": s.tokens_input,
                "tokens_output": s.tokens_output,
                "tokens_total": s.tokens_total,
                "token_limit": TOKEN_LIMIT_PER_SESSION,
                "token_pct": round(s.tokens_total / TOKEN_LIMIT_PER_SESSION * 100, 1),
            }
            for s in sessions.values()
        ]
        return JsonResponse(data, safe=False)
    return HttpResponse(status=405)


# --- Estadísticas de tokens ---
async def get_token_stats(request):
    if request.method == "GET":
        data = await _db.get_token_stats_summary()
        return JsonResponse(data)
    return HttpResponse(status=405)


async def get_token_stats_daily(request):
    if request.method == "GET":
        days = int(request.GET.get("days", 30))
        data = await _db.get_token_usage_daily(days)
        return JsonResponse(data, safe=False)
    return HttpResponse(status=405)


async def get_top_calls_by_cost(request):
    if request.method == "GET":
        limit = int(request.GET.get("limit", 10))
        data = await _db.get_top_calls_by_cost(limit)
        return JsonResponse(data, safe=False)
    return HttpResponse(status=405)


# --- System Prompts ---
async def list_prompts(request):
    if request.method == "GET":
        data = _get_prompt_loader().list_prompts()
        return JsonResponse(data, safe=False)
    return HttpResponse(status=405)


async def prompt_detail(request, name: str):
    if request.method == "GET":
        content = _get_prompt_loader().load(name)
        return JsonResponse({"name": name, "content": content})
    elif request.method == "PUT":
        try:
            body = json.loads(request.body.decode("utf-8"))
            data = PromptUpdate(**body)
            loader = _get_prompt_loader()
            os.makedirs(loader.prompts_dir, exist_ok=True)
            
            filepath_md = os.path.join(loader.prompts_dir, f"{name}.md")
            with open(filepath_md, "w", encoding="utf-8") as f:
                f.write(data.content)
            
            filepath_yaml = os.path.join(loader.prompts_dir, f"{name}.yaml")
            try:
                import yaml
                yaml.safe_load(data.content)
                with open(filepath_yaml, "w", encoding="utf-8") as f:
                    f.write(data.content)
            except Exception:
                pass
            
            return JsonResponse({"success": True, "message": f"Prompt '{name}' guardado en archivos"})
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=400)
    return HttpResponse(status=405)


_PROJECT_ROOT = Path(__file__).parent.parent
PROMPT_CONFIG_PATH = str(_PROJECT_ROOT / "data" / "prompt_config.json")


async def prompt_config_handler(request):
    user_id = request.admin_user["id"]
    loader = _get_prompt_loader()

    if request.method == "GET":
        # Cargar desde BD
        config = await _db.load_prompt_config(user_id)
        if config:
            return JsonResponse(config)
        return JsonResponse({"use_custom": False, "mode": "builder", "raw_content": "", "builder": {}})
    
    elif request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            
            mode = data.get("mode", "builder")
            compiled = ""
            agent_name = "Nova"

            if mode == "builder":
                builder = data.get("builder", {})
                if builder:
                    compiled = loader._build_from_config(builder)
                    agent_name = builder.get("identity", {}).get("name", "Nova")
                        
            elif mode == "raw":
                raw_content = data.get("raw_content", "").strip()
                compiled = raw_content
                agent_name = "Raw Agent"
                        
            elif mode == "agent":
                agent_builder = data.get("agent_builder") or data.get("builder", {})
                if agent_builder:
                    compiled = loader._build_from_config(agent_builder)
                    agent_name = agent_builder.get("identity", {}).get("name", "Nova")

            # Guardar en BD
            config_to_save = {
                "mode": mode,
                "use_custom": data.get("use_custom", False),
                "voice": data.get("voice", "Nova"),
                "builder": data.get("builder", {}),
                "raw_content": data.get("raw_content", ""),
                "agent_id": data.get("agent_id", ""),
                "agent_source": data.get("agent_source", "preset"),
                "agent_builder": data.get("agent_builder", {}),
            }
            
            await _db.save_prompt_config(user_id, config_to_save)
            loader.set_prompt_config_cache(user_id, config_to_save)

            # Guardar también en archivo JSON local como respaldo
            os.makedirs(str(_PROJECT_ROOT / "data"), exist_ok=True)
            config_path = loader._get_config_path(user_id)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_to_save, f, ensure_ascii=False, indent=2)

            # También guardar agent en admin_agents para compatibilidad
            if compiled:
                await _db.save_admin_agent(user_id, "active_agent", agent_name, compiled, config_to_save)
                
            logger.info(f"✅ Config guardada: BD + JSON local (user_id={user_id}, modo={mode})")
            return JsonResponse({"success": True, "message": "✅ Configuración guardada (BD + local)"})
        except Exception as e:
            logger.error(f"Error en prompt_config_handler: {e}")
            return JsonResponse({"detail": str(e)}, status=400)
            
    return HttpResponse(status=405)


async def get_active_prompt_preview(request):
    if request.method == "GET":
        user_id = request.admin_user["id"]
        from ai.prompt_loader import PromptLoader
        loader = PromptLoader()
        
        # Cargar texto del prompt
        text = loader.load(user_id=user_id)
        
        # Cargar config desde BD
        config_data = await _db.load_prompt_config(user_id)
        
        return JsonResponse({
            "prompt_preview": text[:500] + "..." if len(text) > 500 else text,
            "total_chars": len(text),
            "config_stored": bool(config_data),
            "config_exists": bool(config_data),
            "storage_type": "PostgreSQL (persistente en Railway)" if _db.db_type == "postgres" else "SQLite (local)",
            "mode": config_data.get("mode", "builder") if config_data else "builder"
        })
    return HttpResponse(status=405)


async def _load_custom_agents(user_id: int) -> list:
    try:
        return await _db.get_all_admin_agents(user_id)
    except Exception:
        return []


async def _save_agent_to_db(user_id: int, agent_id: str, data: dict, compiled: str = ""):
    profile_name = data.get("profile_name", "Agente Personalizado")
    builder_config = {
        "profile_name": profile_name,
        "builder": data.get("builder", {}),
        "traits": data.get("traits", []),
    }
    await _db.save_admin_agent(user_id, agent_id, profile_name, compiled or "", builder_config)


async def custom_agents_handler(request):
    user_id = request.admin_user["id"]
    if request.method == "GET":
        return JsonResponse(await _load_custom_agents(user_id), safe=False)

    elif request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            agent_id = str(uuid.uuid4())[:8]
            data["id"] = agent_id

            builder = data.get("builder", {})
            compiled = ""
            if builder:
                loader = _get_prompt_loader()
                compiled = loader._build_from_config(builder)

            await _save_agent_to_db(user_id, agent_id, data, compiled)

            return JsonResponse({"success": True, "id": agent_id, "message": f"Agente '{data.get('profile_name', '')}' guardado en la base de datos"})
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=400)

    return HttpResponse(status=405)


async def delete_custom_agent(request, agent_id: str):
    user_id = request.admin_user["id"]
    if request.method == "DELETE":
        try:
            await _db.execute("DELETE FROM admin_agents WHERE user_id = ? AND agent_id = ?", (user_id, agent_id))
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=400)
        return JsonResponse({"success": True})
    return HttpResponse(status=405)


class DbConfigUpdate(BaseModel):
    db_type: str
    sqlite_path: Optional[str] = "./data/nova.db"
    postgres_url: Optional[str] = ""


async def get_db_config(request):
    if request.method == "GET":
        connected = _db._db is not None
        masked_url = _db.postgres_url
        if masked_url and "@" in masked_url:
            masked_url = re.sub(r'(:[^:@]+)@', ':****@', masked_url)
        return JsonResponse({
            "db_type": _db.db_type,
            "sqlite_path": _db.sqlite_path,
            "postgres_url": masked_url,
            "connected": connected,
            "error": None if connected else "Base de datos desconectada"
        })
    return HttpResponse(status=405)


async def update_db_config(request):
    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
            data = DbConfigUpdate(**body)
            if data.db_type in ("postgres_local", "postgres_railway"):
                validation_error = _validate_postgres_connection_string(data.postgres_url or "")
                if validation_error:
                    return JsonResponse({"success": False, "message": validation_error}, status=400)
            await _db.reconnect(data.db_type, data.sqlite_path, data.postgres_url)
            return JsonResponse({"success": True, "message": "Base de datos reconectada exitosamente"})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=400)
    return HttpResponse(status=405)


async def test_db_config(request):
    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
            data = DbConfigUpdate(**body)
            if data.db_type in ("postgres_local", "postgres_railway"):
                validation_error = _validate_postgres_connection_string(data.postgres_url or "")
                if validation_error:
                    return JsonResponse({"success": False, "message": validation_error})
            await _db.test_connection(data.db_type, data.sqlite_path, data.postgres_url)
            return JsonResponse({"success": True, "message": "Prueba de conexión exitosa"})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
    return HttpResponse(status=405)


class UserCreate(BaseModel):
    username: str
    password: str
    email: str = ""
    role: str = "user"


# --- Gestión de Usuarios (CRUD) ---
async def users_list_create(request):
    if request.admin_user.get("role") != "admin":
        return JsonResponse({"detail": "Permisos insuficientes."}, status=403)

    if request.method == "GET":
        try:
            users = await _db.fetch_all("SELECT id, username, email, role, created_at FROM admin_users ORDER BY username")
            return JsonResponse(users, safe=False)
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=500)

    elif request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
            data = UserCreate(**body)
            
            username = data.username.strip()
            if not username:
                return JsonResponse({"detail": "El nombre de usuario es obligatorio."}, status=400)
                
            existing = await _db.get_user_by_username(username)
            if existing:
                return JsonResponse({"detail": f"El usuario '{username}' ya existe."}, status=400)
                
            role = data.role if data.role in ["admin", "user"] else "user"
            await _db.create_admin_user(username, data.password, data.email, role)
            return JsonResponse({"success": True, "message": f"Usuario '{username}' creado exitosamente"})
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=400)

    return HttpResponse(status=405)


async def delete_user(request, user_id: int):
    if request.admin_user.get("role") != "admin":
        return JsonResponse({"detail": "Permisos insuficientes."}, status=403)

    if request.method == "DELETE":
        try:
            if int(user_id) == int(request.admin_user["id"]):
                return JsonResponse({"detail": "No puedes eliminar tu propia cuenta de usuario."}, status=400)
                
            await _db.execute("DELETE FROM admin_users WHERE id = ?", (user_id,))
            return JsonResponse({"success": True, "message": "Usuario eliminado exitosamente"})
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=400)

    return HttpResponse(status=405)


# --- Agent Data Source ---
class DataSourceConfig(BaseModel):
    source_type: str
    pg_connection_string: Optional[str] = ""
    odoo_url: Optional[str] = ""
    odoo_db: Optional[str] = ""
    odoo_api_key: Optional[str] = ""
    odoo_user: Optional[str] = ""


def _mask_sensitive(value: str, visible_chars: int = 4) -> str:
    if not value or len(value) <= visible_chars:
        return "****"
    return value[:visible_chars] + "****" + value[-2:]


async def get_agent_data_source(request):
    if request.method == "GET":
        user_id = request.admin_user["id"]
        config = await _db.get_agent_data_source(user_id)
        if not config:
            return JsonResponse({
                "source_type": "internal",
                "pg_connection_string": "",
                "odoo_url": "",
                "odoo_db": "",
                "odoo_api_key": "",
                "odoo_user": "",
            })
        return JsonResponse({
            "source_type": config.get("source_type", "internal"),
            "pg_connection_string": _mask_sensitive(config.get("pg_connection_string", "")) if config.get("pg_connection_string") else "",
            "odoo_url": config.get("odoo_url", ""),
            "odoo_db": config.get("odoo_db", ""),
            "odoo_api_key": _mask_sensitive(config.get("odoo_api_key", "")) if config.get("odoo_api_key") else "",
            "odoo_user": config.get("odoo_user", ""),
        })
    return HttpResponse(status=405)


async def save_agent_data_source(request):
    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
            data = DataSourceConfig(**body)
            user_id = request.admin_user["id"]

            existing = await _db.get_agent_data_source(user_id)
            pg_conn = data.pg_connection_string or ""
            odoo_key = data.odoo_api_key or ""
            if pg_conn and "****" in pg_conn and existing:
                pg_conn = existing.get("pg_connection_string", "")
            if odoo_key and "****" in odoo_key and existing:
                odoo_key = existing.get("odoo_api_key", "")

            if data.source_type in ("postgres_local", "postgres_railway"):
                validation_error = _validate_postgres_connection_string(pg_conn)
                if validation_error:
                    return JsonResponse({"detail": validation_error}, status=400)

            if data.source_type == "odoo" and data.odoo_user and not _is_valid_email(data.odoo_user):
                return JsonResponse({"detail": "El campo Usuario / Email de Odoo debe tener un formato de correo válido."}, status=400)

            await _db.save_agent_data_source(
                user_id=user_id,
                source_type=data.source_type,
                pg_connection_string=pg_conn,
                odoo_url=data.odoo_url or "",
                odoo_db=data.odoo_db or "",
                odoo_api_key=odoo_key,
                odoo_user=data.odoo_user or "",
            )
            return JsonResponse({"success": True, "message": f"Fuente de datos '{data.source_type}' configurada exitosamente"})
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=400)
    return HttpResponse(status=405)


async def test_agent_data_source(request):
    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
            source_type = body.get("source_type", "internal")
            user_id = request.admin_user["id"]

            if source_type == "internal":
                connected = _db._db is not None
                if connected:
                    return JsonResponse({"success": True, "message": "Base de datos interna conectada correctamente"})
                return JsonResponse({"success": False, "message": "Base de datos interna desconectada"})

            if source_type in ("postgres_local", "postgres_railway"):
                pg_conn = body.get("pg_connection_string", "")
                if pg_conn and "****" in pg_conn:
                    existing = await _db.get_agent_data_source(user_id)
                    if existing:
                        pg_conn = existing.get("pg_connection_string", "")
                validation_error = _validate_postgres_connection_string(pg_conn)
                if validation_error:
                    return JsonResponse({"success": False, "message": validation_error})
                if not pg_conn:
                    return JsonResponse({"success": False, "message": "URL de conexión PostgreSQL requerida"})
                try:
                    import asyncpg
                    conn = await asyncpg.connect(pg_conn, timeout=10)
                    version = await conn.fetchval("SELECT version()")
                    await conn.close()
                    return JsonResponse({"success": True, "message": f"Conexión PostgreSQL exitosa. {version[:50]}"})
                except Exception as e:
                    return JsonResponse({"success": False, "message": f"Error PostgreSQL: {str(e)[:200]}"})

            if source_type == "odoo":
                odoo_url = body.get("odoo_url", "")
                odoo_api_key = body.get("odoo_api_key", "")
                odoo_user = body.get("odoo_user", "")
                if odoo_api_key and "****" in odoo_api_key:
                    existing = await _db.get_agent_data_source(user_id)
                    if existing:
                        odoo_api_key = existing.get("odoo_api_key", "")
                if odoo_user and not _is_valid_email(odoo_user):
                    return JsonResponse({"success": False, "message": "El campo Usuario / Email de Odoo debe tener un formato de correo válido."})
                if not odoo_url or not odoo_api_key:
                    return JsonResponse({"success": False, "message": "URL de Odoo y API Key son requeridos"})
                from ai.odoo_worker import OdooInventoryWorker
                worker = OdooInventoryWorker(
                    base_url=odoo_url,
                    api_key=odoo_api_key,
                    db_name=body.get("odoo_db", ""),
                    odoo_user=odoo_user,
                )
                result = await worker.test_connection()
                return JsonResponse(result)

            return JsonResponse({"success": False, "message": f"Tipo de fuente '{source_type}' no soportado"})
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Error: {str(e)}"})
    return HttpResponse(status=405)


async def odoo_agents_handler(request):
    user_id = request.admin_user["id"]
    loader = _get_prompt_loader()
    config_path = loader._get_config_path(user_id)

    if request.method == "GET":
        config = await _db.get_agent_data_source(user_id)
        if not config or config.get("source_type") != "odoo":
            return JsonResponse({"available": False, "presets": [], "custom": []})

        presets = [
            {
                "id": "odoo_sales",
                "name": "Soporte en Ventas",
                "icon": "🛒",
                "description": "Atiende clientes, consulta inventario Odoo, crea cotizaciones y transfiere a ventas",
                "type": "customer_facing",
                "tools_config": "odoo_sales_tools",
                "capabilities": ["inventory", "transfer", "general"]
            },
            {
                "id": "odoo_vendor_support",
                "name": "Soporte a Vendedores",
                "icon": "📧",
                "description": "Ayuda a vendedores internos: buscar clientes por compras, consultar historial y crear borradores de mailing",
                "type": "internal",
                "tools_config": "odoo_vendor_tools",
                "capabilities": ["odoo_contacts", "odoo_mailing", "odoo_sales_history", "inventory"]
            }
        ]
        
        custom_agents = await _db.get_all_admin_agents(user_id)
        odoo_custom = []
        for a in custom_agents:
            builder = a.get("builder") or {}
            caps = builder.get("capabilities") or []
            if builder.get("odoo_agent_type") or any(c in caps for c in ["odoo_contacts", "odoo_mailing"]):
                odoo_custom.append(a)

        return JsonResponse({"available": True, "presets": presets, "custom": odoo_custom})

    elif request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            agent_id = data.get("agent_id")
            
            existing_config = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        existing_config = json.load(f)
                except Exception:
                    pass

            existing_config["mode"] = "agent"
            existing_config["agent_id"] = agent_id
            existing_config["agent_source"] = "preset"
            existing_config["odoo_agent_type"] = agent_id

            preset_prompt = loader.load(f"nova_{agent_id}")
            agent_name = "Soporte en Ventas (Odoo)" if agent_id == "odoo_sales" else "Soporte a Vendedores (Odoo)"
            
            await _db.save_admin_agent(user_id, "active_agent", agent_name, preset_prompt, existing_config)
            await _db.save_prompt_config(user_id, existing_config)
            loader.set_prompt_config_cache(user_id, existing_config)

            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(existing_config, f, ensure_ascii=False, indent=2)

            return JsonResponse({"success": True, "message": f"Agente Odoo '{agent_name}' activado con éxito"})
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=400)

    return HttpResponse(status=405)
