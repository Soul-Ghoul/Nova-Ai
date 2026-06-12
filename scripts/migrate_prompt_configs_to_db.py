#!/usr/bin/env python
"""
Script de migración: Traslada las configs de prompts de archivos JSON locales a la BD Postgres.
Útil para restaurar las configuraciones después de deploys en Railway.

Uso: python scripts/migrate_prompt_configs_to_db.py
"""
import asyncio
import json
import os
from pathlib import Path
from loguru import logger

async def main():
    from config.settings import get_settings
    from database.manager import DatabaseManager

    logger.info("=" * 80)
    logger.info("🔄 Migrando configuraciones de prompts a la base de datos...")
    logger.info("=" * 80)

    db = DatabaseManager()
    await db.connect()

    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"

    if not data_dir.exists():
        logger.warning(f"⚠️  Directorio {data_dir} no existe. No hay archivos para migrar.")
        return

    # Buscar archivos prompt_config_*.json
    config_files = list(data_dir.glob("prompt_config_*.json"))
    
    if not config_files:
        logger.info("✅ No hay archivos prompt_config_*.json para migrar.")
        await db.disconnect()
        return

    migrated_count = 0
    for config_file in config_files:
        try:
            # Extraer user_id del nombre del archivo
            filename = config_file.name
            user_id_str = filename.replace("prompt_config_", "").replace(".json", "")
            
            if not user_id_str.isdigit():
                logger.warning(f"⚠️  Saltando {filename}: nombre inválido")
                continue
            
            user_id = int(user_id_str)
            
            # Leer JSON
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            
            # Guardar en BD
            await db.save_prompt_config(user_id, config_data)
            migrated_count += 1
            logger.info(f"✅ Migrado: user_id={user_id} desde {filename}")
            
        except Exception as e:
            logger.error(f"❌ Error migrando {config_file.name}: {e}")

    await db.disconnect()
    
    logger.info("=" * 80)
    logger.info(f"✅ Migración completada: {migrated_count} configuraciones trasladadas a BD")
    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
