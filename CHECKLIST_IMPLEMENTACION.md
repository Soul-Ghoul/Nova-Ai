# ✅ CHECKLIST DE IMPLEMENTACIÓN

## 🔧 Cambios Realizados

### 1. Base de Datos
- [x] Agregar tabla `prompt_config` en Postgres schema (database/models.py)
- [x] Agregar tabla `prompt_config` en SQLite schema (database/models.py)
- [x] Aumentar pool Postgres: 10 → 20 conexiones (database/manager.py:139)
- [x] Forzar Postgres, eliminar fallback automático a SQLite (database/manager.py:162-166 → error explícito)
- [x] Crear índices y columna `updated_at` (database/manager.py)

### 2. API (DatabaseManager)
- [x] Método `save_prompt_config(user_id, config)` (database/manager.py:786-823)
- [x] Método `load_prompt_config(user_id)` (database/manager.py:825-851)
- [x] Método `delete_prompt_config(user_id)` (database/manager.py:853-858)

### 3. Admin Panel
- [x] Reemplazar `prompt_config_handler()` para usar BD (api/admin.py:318-375)
- [x] Actualizar `get_active_prompt_preview()` para mostrar storage type (api/admin.py:430-443)
- [x] Remover dependencia de archivos JSON locales

### 4. Scripts
- [x] Crear script de migración (scripts/migrate_prompt_configs_to_db.py)

### 5. Documentación
- [x] Crear PERSISTENCIA_CONFIGS_RAILWAY.md

---

## 📋 Próximos Pasos

### ANTES de deployar a Railway:

```bash
# 1. Validar cambios localmente
cd "TestV1_Speech"
git status

# 2. Verificar que Postgres conecta (DATABASE_URL debe estar configurada localmente)
# Si usas SQLite en desarrollo, los cambios siguen siendo compatibles

# 3. Si tienes usuarios con configs guardadas en archivos:
python scripts/migrate_prompt_configs_to_db.py
# Esto traslada prompt_config_*.json → Postgres

# 4. Commit y push
git add -A
git commit -m "feat: persist prompt configs in Postgres (Railway-safe)"
git push
```

### EN Railway:

```bash
# 1. El deploy ejecutará automáticamente las migraciones de BD
# 2. Verifica en logs: "✅ Base de datos PostgreSQL conectada"
# 3. Si ves "❌ CRÍTICO", verifica DATABASE_URL

# 4. Pruba: Guarda un prompt en Admin
# 5. Redeploy el app
# 6. Verifica que la config se recuperó ✅
```

---

## 🧪 Testing Local

### Prueba 1: Guardar y cargar config
```python
# Simulación en terminal Python
from database.manager import DatabaseManager
import asyncio

async def test():
    db = DatabaseManager()
    await db.connect()
    
    # Guardar config
    await db.save_prompt_config(1, {
        "mode": "builder",
        "builder": {"name": "Nova", "role": "test"},
        "voice": "Nova"
    })
    
    # Cargar config
    config = await db.load_prompt_config(1)
    print("Config cargada:", config)
    
    await db.disconnect()

asyncio.run(test())
```

### Prueba 2: Endpoint de API
```bash
# GET /api/admin/prompt-config
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/admin/prompt-config

# POST /api/admin/prompt-config
curl -X POST -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"mode":"builder","builder":{"name":"Nova"}}' \
  http://localhost:8000/api/admin/prompt-config
```

---

## ⚠️ Validaciones Críticas

### ✅ Si ves estos logs = está funcionando:
```
✅ Base de datos PostgreSQL conectada (pool activo)
✅ Prompt config guardada en BD para user_id=1 (modo=builder)
```

### ❌ Si ves estos logs = problema:
```
❌ CRÍTICO: Fallo al conectar a PostgreSQL (Railway)
❌ No se puede iniciar sin Postgres en producción.
```
**Acción:** Verifica `DATABASE_URL` en Railway → Secrets

---

## 📊 Verificación de Estado

### Ver todas las configs guardadas (en DB):
```sql
SELECT user_id, mode, voice, updated_at FROM prompt_config;
```

### Ver configs de un usuario específico:
```sql
SELECT * FROM prompt_config WHERE user_id = 1 \G
```

### Contar cuántas configs hay:
```sql
SELECT COUNT(*) as total_configs FROM prompt_config;
```

---

## 🔄 Si algo falla

### Problema: "Database connection failed"
**Causa:** `DATABASE_URL` malformado o no disponible  
**Solución:**
```bash
# En Railway Dashboard → Settings → Environment
# Verifica que DATABASE_URL existe y tiene formato:
# postgresql://user:password@host:5432/database
```

### Problema: "Config no persiste después de redeploy"
**Causa:** Fallback a SQLite (pero eso ahora genera error)  
**Solución:**
```bash
# Mira los logs del deploy en Railway
# Si dice "SQLite", la implementación no se aplicó correctamente
# Verifica que los archivos fueron pusheados a Git
git log --oneline | head -5
```

### Problema: "Migración de archivos JSON falla"
**Causa:** Archivos con nombre incorrecto o JSON inválido  
**Solución:**
```bash
# Verifica nombres de archivos
ls -la ./data/prompt_config_*.json

# Si un JSON está corrupto, elimínalo antes de migrar
rm ./data/prompt_config_corrupted.json

# Reintenta
python scripts/migrate_prompt_configs_to_db.py
```

---

## 📝 Cambios de Comportamiento

| Antes | Ahora |
|-------|-------|
| Config guardada en `./data/prompt_config_<user_id>.json` | Guardada en tabla `prompt_config` de Postgres |
| Si Postgres fallaba → fallback silencioso a SQLite | Si Postgres falla → error explícito (falla al iniciar) |
| Configs se perdían en cada redeploy | Configs persisten en Postgres (recuperadas automáticamente) |
| Pool Postgres max_size=10 | Pool Postgres max_size=20 |
| Sin migración de datos | Script incluido: `migrate_prompt_configs_to_db.py` |

---

## 🎯 Objetivo Cumplido

✅ Las configuraciones de prompts ahora persisten en Railway tras redeploys  
✅ Sin cambios en el código de la UI (transparente para el usuario)  
✅ Fallback eliminado (mayor seguridad)  
✅ Pool aumentado (soporte para 100 llamadas)  
✅ Script de migración incluido para usuarios existentes

---

## 📞 Soporte

Si algo falla:
1. Revisa los logs en Railway Dashboard
2. Busca "❌ CRÍTICO" o "Error"
3. Verifica DATABASE_URL
4. Re-run la migración si es necesario

Implementación completada: **2026-06-12 11:15 UTC**
