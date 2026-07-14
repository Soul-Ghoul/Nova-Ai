from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.views.decorators.csrf import csrf_exempt
from django_project.views import serve_index, serve_admin
from api.health import health_check
from django_project.api_admin import (
    extensions_list_create,
    delete_extension,
    inventory_list_create,
    delete_inventory_item,
    list_call_logs,
    list_active_sessions,
    get_token_stats,
    get_token_stats_daily,
    get_top_calls_by_cost,
    list_prompts,
    prompt_detail,
    prompt_config_handler,
    get_active_prompt_preview,
    custom_agents_handler,
    delete_custom_agent,
    get_db_config,
    update_db_config,
    test_db_config,
    users_list_create,
    delete_user,
    get_agent_data_source,
    save_agent_data_source,
    test_agent_data_source,
    odoo_agents_handler,
    pms_agents_handler,
)
from api.auth import login_handler, logout_handler, check_session_handler

urlpatterns = [
    # Páginas principales del frontend
    path('', serve_index),
    path('admin', serve_admin),
    path('admin/', serve_admin),
    
    # Endpoint de salud
    path('health', health_check),
    path('health/', health_check),
    
    # Endpoints de Autenticación
    path('api/auth/login', csrf_exempt(login_handler)),
    path('api/auth/logout', csrf_exempt(logout_handler)),
    path('api/auth/session', check_session_handler),
    
    # Endpoints de API de Administración
    path('api/admin/extensions', csrf_exempt(extensions_list_create)),
    path('api/admin/extensions/<int:ext_id>', csrf_exempt(delete_extension)),
    path('api/admin/inventory', csrf_exempt(inventory_list_create)),
    path('api/admin/inventory/<int:item_id>', csrf_exempt(delete_inventory_item)),
    path('api/admin/logs', list_call_logs),
    path('api/admin/sessions', list_active_sessions),
    path('api/admin/token-stats', get_token_stats),
    path('api/admin/token-stats/daily', get_token_stats_daily),
    path('api/admin/token-stats/top', get_top_calls_by_cost),
    path('api/admin/prompts', list_prompts),
    path('api/admin/prompts/<str:name>', prompt_detail),
    path('api/admin/prompt-config', csrf_exempt(prompt_config_handler)),
    path('api/admin/prompt-config/active', get_active_prompt_preview),
    path('api/admin/custom-agents', csrf_exempt(custom_agents_handler)),
    path('api/admin/custom-agents/<str:agent_id>', csrf_exempt(delete_custom_agent)),
    path('api/admin/db/config', get_db_config),
    path('api/admin/db/config/update', csrf_exempt(update_db_config)),
    path('api/admin/db/test', csrf_exempt(test_db_config)),
    path('api/admin/users', csrf_exempt(users_list_create)),
    path('api/admin/users/<int:user_id>', csrf_exempt(delete_user)),
    path('api/admin/agent-data-source', csrf_exempt(get_agent_data_source)),
    path('api/admin/agent-data-source/save', csrf_exempt(save_agent_data_source)),
    path('api/admin/agent-data-source/test', csrf_exempt(test_agent_data_source)),
    path('api/admin/odoo-agents', csrf_exempt(odoo_agents_handler)),
    path('api/admin/pms-agents', csrf_exempt(pms_agents_handler)),
] + static('/static/', document_root=settings.STATICFILES_DIRS[0])
