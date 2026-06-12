import sys
import os
import asyncio
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.manager import DatabaseManager

async def main():
    db = DatabaseManager()
    await db.connect()
    
    print("\n--- AUDITORÍA DE BASE DE DATOS ---")
    print(f"Tipo de BD activa: {db.db_type}")
    
    # 1. Consultar tabla prompt_config
    try:
        rows_config = await db.fetch_all("SELECT * FROM prompt_config")
        print(f"\n[prompt_config] Total de registros: {len(rows_config)}")
        for r in rows_config:
            print(f"  - User ID: {r.get('user_id')}")
            print(f"    Mode: {r.get('mode')}")
            print(f"    Voice: {r.get('voice')}")
            print(f"    Agent ID: {r.get('agent_id')}")
            print(f"    Builder: {r.get('builder')[:100]}...")
            print(f"    Agent Builder: {r.get('agent_builder')[:100]}...")
    except Exception as e:
        print(f"Error consultando prompt_config: {e}")
        
    # 2. Consultar tabla admin_agents
    try:
        rows_agents = await db.fetch_all("SELECT user_id, agent_id, name, builder_config FROM admin_agents")
        print(f"\n[admin_agents] Total de registros: {len(rows_agents)}")
        for r in rows_agents:
            print(f"  - User ID: {r.get('user_id')} | Agent ID: {r.get('agent_id')}")
            print(f"    Name: {r.get('name')}")
            print(f"    Builder Config: {r.get('builder_config')[:120]}...")
    except Exception as e:
        print(f"Error consultando admin_agents: {e}")
        
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
