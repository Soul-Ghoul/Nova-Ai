"""
Test de conexión con Odoo usando JSON-2 API.
Valida: autenticación, búsqueda atómica (search_read) y lectura de catálogo.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.odoo_client import OdooJson2Client, OdooAPIError

ODOO_BASE_URL = "https://tilyngo.odoo.com"
ODOO_DB = "tilyngo"
ODOO_API_KEY = "3de59600d375286d00b1814383fb8566c3b123cf"


async def test_odoo_connection():
    print("=" * 60)
    print("  TEST DE CONEXION ODOO -- JSON-2 API")
    print("=" * 60)

    print(f"\n> URL:  {ODOO_BASE_URL}")
    print(f"> DB:  ***{ODOO_DB[-4:]}")
    print(f"> Auth: Bearer ****{ODOO_API_KEY[-8:]}")

    client = OdooJson2Client.__new__(OdooJson2Client)
    client.base_url = ODOO_BASE_URL.rstrip("/")
    client.api_key = ODOO_API_KEY
    client.timeout = 15.0
    client._headers = {
        "Authorization": f"bearer {ODOO_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        print("\n1. Probando search_read en product.product...")

        products = await client.search_read(
            model="product.product",
            domain=[["sale_ok", "=", True]],
            fields=["id", "name", "default_code", "barcode", "list_price", "qty_available"],
            limit=5,
            order="name asc",
        )

        if not products:
            print("[INFO] No se encontraron productos para venta. La conexión funciona, pero el catálogo está vacío.")
            return True

        print(f"\n[ÉXITO] {len(products)} productos obtenidos:\n")
        print(f"{'Nombre':<30} {'SKU':<15} {'Precio':>10} {'Stock':>8}")  # noqa: E501
        print("-" * 67)

        for p in products:
            name = (p.get("name") or "Sin nombre")[:29]
            sku = (p.get("default_code") or "—")[:14]
            price = p.get("list_price", 0.0)
            stock = p.get("qty_available", 0.0)
            print(f"{name:<30} {sku:<15} ${price:>8.2f} {stock:>7.1f}")

        print("-" * 67)

        print("\n2. Probando search_count...")
        total = await client.search_count(
            model="product.product",
            domain=[["sale_ok", "=", True]],
        )
        print(f"[ÉXITO] Total productos vendibles: {total}")

        print("\n" + "=" * 60)
        print("  [OK] TODAS LAS PRUEBAS PASARON")
        print("  > JSON-2 API funciona correctamente")
        print("  > Autenticacion Bearer OK")
        print("  > search_read atomico OK")
        print("=" * 60)
        return True

    except OdooAPIError as e:
        print(f"\n[ERROR ODOO] {e.detail}")
        if e.status_code == 401:
            print("  > Revisa que ODOO_API_KEY sea valida y no este expirada")
        elif e.status_code == 404:
            print("  > Tu version de Odoo podria no soportar JSON-2 API")
            print("  > JSON-2 esta disponible desde Odoo 17+")
        return False

    except Exception as e:
        print(f"\n[ERROR] Fallo inesperado: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_odoo_connection())
    sys.exit(0 if success else 1)
