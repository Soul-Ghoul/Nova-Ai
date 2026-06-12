from loguru import logger
import json


async def handle_create_odoo_order(products_names: str, quantities: str, customer_name: str = None, session=None, **kwargs) -> dict:
    """
    Crea una requisición de compra (presupuesto borrador) en Odoo.
    Asocia los productos seleccionados y el cliente en llamada.
    """
    from django_project.state import db
    user_id = getattr(session, "user_id", None) if session else None
    if not user_id:
        user_id = 1

    try:
        # Procesar los nombres y cantidades separados por comas
        names_list = [n.strip() for n in products_names.split(",") if n.strip()]
        
        qty_list = []
        if quantities:
            for q in quantities.split(","):
                try:
                    qty_list.append(int(q.strip()))
                except ValueError:
                    qty_list.append(1)
        else:
            qty_list = [1] * len(names_list)

        # Si hay desfase de longitud, rellenar con 1s
        if len(qty_list) < len(names_list):
            qty_list.extend([1] * (len(names_list) - len(qty_list)))
            
        products_list = []
        for i, name in enumerate(names_list):
            products_list.append({
                "product_name": name,
                "quantity": qty_list[i]
            })

        config = await db.get_agent_data_source(user_id)
        if not config:
            return {"output": "El sistema de compras en Odoo no está configurado."}

        source_type = config.get("source_type", "internal")
        if source_type != "odoo":
            return {"output": "Odoo no está configurado como la fuente de datos activa de inventario."}

        odoo_url = config.get("odoo_url", "")
        odoo_api_key = config.get("odoo_api_key", "")
        if not odoo_url or not odoo_api_key:
            return {"output": "Faltan credenciales para conectar con Odoo."}

        from ai.odoo_worker import get_odoo_worker
        worker = get_odoo_worker(
            base_url=odoo_url,
            api_key=odoo_api_key,
            db_name=config.get("odoo_db", ""),
            odoo_user=config.get("odoo_user", ""),
            user_id=user_id
        )

        partner_name = customer_name.strip() if customer_name else "Cliente Llamada Nova"
        logger.info(f"Odoo Order: Buscando cliente '{partner_name}'...")
        
        partners = await worker._search_read("res.partner", [["name", "=", partner_name]], ["id"], limit=1)
        
        if partners and len(partners) > 0:
            partner_id = partners[0]["id"]
            logger.info(f"Odoo Order: Cliente encontrado con ID {partner_id}")
        else:
            logger.info(f"Odoo Order: Creando nuevo cliente '{partner_name}'...")
            partner_res = await worker._create("res.partner", {"name": partner_name})
            if partner_res:
                partner_id = partner_res[0] if isinstance(partner_res, list) else partner_res
                logger.info(f"Odoo Order: Cliente creado con ID {partner_id}")
            else:
                logger.warning("Odoo Order: Falló la creación de res.partner. Buscando contacto existente como fallback...")
                existing_partners = await worker._search_read("res.partner", [], ["id", "name"], limit=3)
                if existing_partners and len(existing_partners) > 0:
                    partner_id = existing_partners[0]["id"]
                    logger.info(f"Odoo Order: Fallback exitoso. Asociado a contacto existente '{existing_partners[0]['name']}' con ID {partner_id}")
                else:
                    return {"output": "No se pudo crear ni asociar ningún cliente en Odoo."}

        order_lines = []
        missing_products = []

        for item in products_list:
            p_name = item.get("product_name", "").strip()
            qty = item.get("quantity", 1)
            
            if not p_name:
                continue

            logger.info(f"Odoo Order: Buscando ID para el producto '{p_name}'...")
            
            prods = await worker._search_read(
                "product.product", 
                ["|", ["name", "ilike", p_name], ["default_code", "=", p_name]], 
                ["id", "name", "list_price"], 
                limit=1
            )
            
            if prods and len(prods) > 0:
                p_id = prods[0]["id"]
                p_price = prods[0].get("list_price", 0.0)
                order_lines.append((0, 0, {
                    "product_id": p_id,
                    "product_uom_qty": qty,
                    "price_unit": p_price
                }))
                logger.info(f"Odoo Order: Producto '{prods[0]['name']}' enlazado con ID {p_id} y precio {p_price}")
            else:
                missing_products.append(p_name)

        if not order_lines:
            return {"output": f"No se pudo enlazar ningún producto en Odoo. No coinciden con el inventario: {', '.join(missing_products)}"}

        order_values = {
            "partner_id": partner_id,
            "order_line": order_lines,
            "note": "Presupuesto borrador generado automáticamente desde el canal de voz inteligente Nova. Confirmar con el cliente antes de procesar."
        }

        logger.info("Odoo Order: Creando presupuesto 'sale.order'...")
        order_res = await worker._create("sale.order", order_values)

        if not order_res:
            return {"output": "Odoo rechazó la creación de la cotización. Revisa si el módulo de Ventas está instalado y configurado."}

        order_id = order_res[0] if isinstance(order_res, list) else order_res
        logger.info(f"Odoo Order: Presupuesto creado exitosamente en Odoo con ID {order_id}")

        order_data = await worker._search_read("sale.order", [["id", "=", order_id]], ["name"], limit=1)
        order_folio = order_data[0]["name"] if order_data and len(order_data) > 0 else f"ID: {order_id}"

        response_msg = f"¡Excelente noticia! He registrado exitosamente tu requisición de compra en Odoo con la cotización folio {order_folio}."
        if missing_products:
            response_msg += f" (Nota: Los siguientes productos no se pudieron enlazar en el sistema: {', '.join(missing_products)})."
        
        return {"output": response_msg}

    except Exception as e:
        logger.error(f"Error procesando requisición en Odoo: {e}")
        return {"output": f"Fallo al intentar registrar la compra en Odoo. Error: {str(e)}"}
