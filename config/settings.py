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
    telephony_user_id: int = Field(default=1, description="User ID del agente que contesta llamadas telefónicas")

    nova_host: str = Field(default="0.0.0.0")
    nova_port: int = Field(default=8000)
    nova_debug: bool = Field(default=True)

    db_path: str = Field(default="./data/nova.db")
    redis_url: str = Field(default="redis://localhost:6379", description="URL de conexión a Redis para caché L1")

    prompts_dir: str = Field(default="./config/prompts")
    tools_dir: str = Field(default="./config/tools")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
