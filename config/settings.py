from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    gemini_api_key: str = Field(default="", description="Google Gemini API Key")
    gemini_model: str = Field(default="gemini-2.0-flash-live-001", description="Modelo Gemini Live")
    gemini_worker_model: str = Field(default="gemini-2.0-flash", description="Modelo Gemini para Worker de inventario")

    ami_host: str = Field(default="127.0.0.1")
    ami_port: int = Field(default=5038)
    ami_username: str = Field(default="nova_agent")
    ami_secret: str = Field(default="supersecret")

    audiosocket_host: str = Field(default="0.0.0.0")
    audiosocket_port: int = Field(default=9092)

    nova_host: str = Field(default="0.0.0.0")
    nova_port: int = Field(default=8000)
    nova_debug: bool = Field(default=False)

    db_path: str = Field(default="./data/nova.db")
    database_url: str = Field(default="postgresql://postgres:UfukxyHgiawVrdxrBwbDdEgvldvsDYaO@postgres.railway.internal:5432/railway")


    prompts_dir: str = Field(default="./config/prompts")
    tools_dir: str = Field(default="./config/tools")
    usd_exchange_rate: float = Field(default=17.37, description="Tipo de cambio de pesos a dólares (ej: 17.37 MXN = 1 USD)")

    odoo_base_url: str = Field(default="", description="URL base de Odoo (ej: https://mi-empresa.odoo.com)")
    odoo_db: str = Field(default="", description="Base de datos de Odoo")
    odoo_api_key: str = Field(default="", description="API Key de Odoo para JSON-2 API")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
