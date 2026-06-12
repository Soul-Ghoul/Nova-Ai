import asyncio
import os
import sys

# Añadir el directorio raíz al path de Python para poder importar los módulos locales
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from auth.utils import hash_password

async def main():
    db = DatabaseManager()
    await db.connect()
    
    username = "admin"
    password = "nova1234"
    email = "tylingo.oficial@gmail.com"
    role = "admin"
    
    password_hash = hash_password(password)
    
    # Verificar si existe
    user = await db.get_user_by_username(username)
    if user:
        print(f"El usuario '{username}' ya existe. Actualizando contraseña a '{password}'...")
        await db.execute(
            "UPDATE admin_users SET password_hash = ?, email = ?, role = ? WHERE username = ?",
            (password_hash, email, role, username)
        )
        print("¡Usuario actualizado con éxito!")
    else:
        print(f"El usuario '{username}' no existe. Creándolo con contraseña '{password}'...")
        await db.create_admin_user(username, password, email, role)
        print("¡Usuario creado con éxito!")
        
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
