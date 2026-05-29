from __future__ import annotations

import httpx
from loguru import logger
from typing import Any
from config.settings import get_settings


class OdooAPIError(Exception):
    """Error de comunicación con la API JSON-2 de Odoo."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Odoo API {status_code}: {detail}")


class OdooJson2Client:
    """
    Cliente async para la External JSON-2 API de Odoo.
    Sigue la arquitectura recomendada:
    - Autenticación con API Key en header Bearer
    - Operaciones atómicas (search_read)
    - Timeouts configurables
    - Logging estructurado
    """

    def __init__(self, timeout: float = 15.0):
        settings = get_settings()
        self.base_url = settings.odoo_base_url.rstrip("/")
        self.api_key = settings.odoo_api_key
        self.timeout = timeout
        self._headers = {
            "Authorization": f"bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def call(
        self,
        model: str,
        method: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/json/2/{model}/{method}"
        payload = payload or {}

        logger.debug("Odoo JSON-2 → {method} en {model}", method=method, model=model)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=self._headers, json=payload)

            if resp.status_code == 401:
                raise OdooAPIError(401, "API Key inválida o expirada. Revisa ODOO_API_KEY.")
            if resp.status_code == 403:
                raise OdooAPIError(403, "Sin permisos para este modelo/método. Revisa los ACL del usuario bot.")
            if resp.status_code == 404:
                raise OdooAPIError(404, f"Endpoint no encontrado: {url}. ¿Tu Odoo soporta JSON-2 API?")

            resp.raise_for_status()

            data = resp.json()

            if isinstance(data, dict) and data.get("error"):
                error_info = data["error"]
                raise OdooAPIError(
                    500,
                    error_info.get("message", str(error_info)),
                )

            if isinstance(data, dict) and "result" in data:
                return data["result"]
            return data

    async def search_read(
        self,
        model: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        limit: int = 80,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "domain": domain or [],
            "fields": fields or [],
            "limit": limit,
            "offset": offset,
        }
        if order:
            payload["order"] = order

        return await self.call(model, "search_read", payload)

    async def search_count(
        self,
        model: str,
        domain: list | None = None,
    ) -> int:
        return await self.call(model, "search_count", {"domain": domain or []})


_client: OdooJson2Client | None = None


def get_odoo_client() -> OdooJson2Client:
    global _client
    if _client is None:
        _client = OdooJson2Client()
    return _client
