import sys
import os
import json
import traceback

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar y configurar la app
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# JSON de prueba idéntico al enviado por la UI en constructor visual
payload = {
    "mode": "builder",
    "builder": {
        "identity": {
            "name": "Nova",
            "company": "la empresa",
            "role": "asistente virtual"
        },
        "language": "es",
        "tone": "friendly",
        "greeting": "Hola, ¿en qué puedo ayudarle?",
        "personality": [],
        "capabilities": ["general"],
        "rules": ["character_lock", "no_hallucinations"],
        "custom_instructions": ""
    },
    "raw_content": ""
}

try:
    print("Enviando POST a /api/admin/prompt-config...")
    response = client.post("/api/admin/prompt-config", json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON: {response.json()}")
except Exception as e:
    print("EXCEPCIÓN DETECTADA:")
    traceback.print_exc()
