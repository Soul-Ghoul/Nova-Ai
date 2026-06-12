import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.manager import DatabaseManager
from ai.prompt_loader import PromptLoader

async def main():
    db = DatabaseManager()
    await db.connect()
    
    loader = PromptLoader()
    
    # Obtener todos los usuarios de prompt_config
    rows = await db.fetch_all("SELECT user_id, mode, agent_id FROM prompt_config")
    print(f"\n--- TEST DE CARGA DE PROMPTS ({len(rows)} usuarios) ---")
    
    for r in rows:
        u_id = r["user_id"]
        mode = r["mode"]
        agent_id = r["agent_id"]
        
        # Cargar config a la caché manualmente para simular el ciclo de vida
        config = await db.load_prompt_config(u_id)
        loader.set_prompt_config_cache(u_id, config)
        
        prompt = loader.load(user_id=u_id)
        print(f"\nUser ID: {u_id} | Mode: {mode} | Agent ID: {agent_id}")
        print(f"Longitud del prompt cargado: {len(prompt)} caracteres")
        print("Inicio del prompt:")
        print(prompt[:300] + "...")
        
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
