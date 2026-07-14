from loguru import logger
from database.manager import DatabaseManager


async def seed_database(db: DatabaseManager):
    # Sembrar usuario administrador por defecto si no existe ninguno
    try:
        admins_count = await db.fetch_one("SELECT COUNT(*) as count FROM admin_users")
        if not admins_count or admins_count.get("count", 0) == 0:
            logger.info("No se encontraron usuarios administradores. Sembrando administradores por defecto...")
            # Sembrar admin general (id=1)
            await db.execute(
                "INSERT INTO admin_users (id, username, password_hash, email, role) VALUES (?, ?, ?, ?, ?)",
                (1, "admin", "pbkdf2:sha256:600000$xxxx$hash", "admin@nova-ia.app", "admin")
            )
            # Sembrar usuario telefónico (id=2)
            await db.execute(
                "INSERT INTO admin_users (id, username, password_hash, email, role) VALUES (?, ?, ?, ?, ?)",
                (2, "telephony_user", "pbkdf2:sha256:600000$yyyy$hash", "telephony@nova-ia.app", "user")
            )
            
            # Sembrar config del agente PMS para el usuario de telefonía (id=2)
            await db.execute(
                "INSERT INTO prompt_config (user_id, mode, agent_id, agent_source) VALUES (?, ?, ?, ?)",
                (2, "agent", "pms_receptionist", "preset")
            )
            
            # Sembrar fuente de datos PMS para el usuario de telefonía (id=2)
            await db.execute(
                """INSERT INTO agent_data_source 
                   (user_id, source_type, pms_url, pms_username, pms_password) 
                   VALUES (?, ?, ?, ?, ?)""",
                (2, "pms", "http://127.0.0.1:8000", "admin", "admin")
            )
            logger.info("Usuarios y configuraciones de agentes por defecto sembrados con éxito.")
        else:
            # Asegurar que el usuario admin principal tenga el rol 'admin'
            await db.execute("UPDATE admin_users SET role = 'admin' WHERE username = 'admin'")
            
            # Asegurar que exista el registro de telefonía en id=2
            has_telephony = await db.fetch_one("SELECT 1 FROM admin_users WHERE id = 2")
            if not has_telephony:
                await db.execute(
                    "INSERT INTO admin_users (id, username, password_hash, email, role) VALUES (?, ?, ?, ?, ?)",
                    (2, "telephony_user", "pbkdf2:sha256:600000$yyyy$hash", "telephony@nova-ia.app", "user")
                )
                await db.execute(
                    "INSERT INTO prompt_config (user_id, mode, agent_id, agent_source) VALUES (?, ?, ?, ?)",
                    (2, "agent", "pms_receptionist", "preset")
                )
                await db.execute(
                    """INSERT INTO agent_data_source 
                       (user_id, source_type, pms_url, pms_username, pms_password) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (2, "pms", "http://127.0.0.1:8000", "admin", "admin")
                )
                logger.info("Configuraciones por defecto de telefonía (ID 2) restablecidas.")
    except Exception as e:
        logger.error(f"Error sembrando configuraciones de base de datos: {e}")

    # Sembrar extensiones e inventario si no hay extensiones
    existing = await db.get_all_extensions()
    if existing:
        logger.info(f"Base de datos ya tiene {len(existing)} extensiones, omitiendo seed de negocio")
        return

    logger.info("Insertando datos iniciales de ejemplo...")

    extensions = [
        ("Luis Alfonso García", "104", "Ventas", "luis.garcia@techsolutions.com"),
        ("María Fernanda López", "105", "Soporte Técnico", "maria.lopez@techsolutions.com"),
        ("Carlos Rodríguez", "106", "Desarrollo", "carlos.rodriguez@techsolutions.com"),
        ("Ana Patricia Méndez", "107", "Recursos Humanos", "ana.mendez@techsolutions.com"),
        ("Roberto Sánchez", "108", "Dirección General", "roberto.sanchez@techsolutions.com"),
        ("Gabriela Torres", "109", "Contabilidad", "gabriela.torres@techsolutions.com"),
        ("Soporte Técnico", "200", "Soporte Técnico", "soporte@techsolutions.com"),
        ("Ventas", "201", "Ventas", "ventas@techsolutions.com"),
        ("Recepción", "100", "Administración", "recepcion@techsolutions.com"),
    ]

    for name, ext, dept, email in extensions:
        await db.add_extension(name, ext, dept, email)

    products = [
        ("Laptop ProBook 450", "Laptop empresarial 15.6 pulgadas, i7, 16GB RAM", 18500.00, 15, "Computadoras", "HP", "Plata", "1.7 kg"),
        ("Monitor UltraWide 34", "Monitor curvo 34 pulgadas WQHD", 8900.00, 8, "Monitores", "LG", "Negro", "6.2 kg"),
        ("Monitor Básico 24", "Monitor LED 24 pulgadas Full HD", 3500.00, 20, "Monitores", "Dell", "Negro", "3.5 kg"),
        ("Teléfono IP GXP2170", "Teléfono IP empresarial Grandstream 6 líneas", 3200.00, 25, "Telefonía", "Grandstream", "Negro", "0.9 kg"),
        ("Celular Empresarial A54", "Smartphone corporativo 128GB", 6500.00, 10, "Telefonía", "Samsung", "Gris", "0.2 kg"),
        ("Switch PoE 24 puertos", "Switch gestionable PoE+ 24 puertos Gigabit", 12500.00, 5, "Redes", "Cisco", "Metálico", "2.1 kg"),
        ("Licencia Office 365", "Licencia anual Microsoft 365 Business", 2800.00, 100, "Software", "Microsoft", "N/A", "0 kg"),
        ("Cable UTP Cat6 (305m)", "Bobina cable red categoría 6 certificado", 1850.00, 30, "Cableado", "Belden", "Azul", "12 kg"),
        ("Access Point WiFi 6", "Punto de acceso WiFi 6 para interiores", 4500.00, 12, "Redes", "Ubiquiti", "Blanco", "0.5 kg"),
        ("Teclado Inalámbrico", "Teclado ergonómico bluetooth silencioso", 1200.00, 45, "Periféricos", "Logitech", "Gris Oscuro", "0.8 kg"),
        ("Ratón Óptico Inalámbrico", "Mouse bluetooth de precisión", 800.00, 50, "Periféricos", "Logitech", "Negro", "0.1 kg"),
        ("Servidor Rack 1U", "Servidor de montaje en rack, Xeon 32GB RAM", 45000.00, 3, "Servidores", "Dell", "Metálico", "18 kg"),
    ]

    for name, desc, price, stock, cat, brand, color, weight in products:
        await db.add_inventory_item(name, desc, price, stock, cat, brand, color, weight)

    logger.info("Datos iniciales insertados correctamente")
