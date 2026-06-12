import datetime
import json
import httpx
from typing import Any
from loguru import logger
from ai.odoo_worker import OdooInventoryWorker

class OdooVendorWorker(OdooInventoryWorker):
    """Worker para operaciones de soporte interno a vendedores en Odoo 19 Enterprise."""

    def __init__(self, base_url: str, api_key: str, db_name: str = "", odoo_user: str = ""):
        super().__init__(base_url, api_key, db_name, odoo_user)
        logger.info(f"OdooVendorWorker: Gemini AI de vendedores inicializado ({self.ai_model})")

    async def _create_multi(self, model: str, vals_list: list[dict]) -> Any:
        url = f"{self.base_url}/json/2/{model}/create"
        payload = {
            "vals_list": vals_list
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self._headers, json=payload)
                if resp.status_code in (401, 403):
                    logger.error(f"Odoo: {resp.status_code} para {url}")
                    return None
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict):
                    if data.get("error"):
                        logger.error(f"Odoo API Error en create_multi para {model}: {data['error']}")
                        return None
                    if "result" in data:
                        return data["result"]
                return data
        except Exception as e:
            logger.error(f"Odoo create_multi error para {model}: {e}")
            return None

    async def _resolve_mailing_model_id(self, model_name="res.partner") -> int:
        models = await self._search_read("ir.model", [["model", "=", model_name]], ["id"], limit=1)
        if models and isinstance(models, list):
            return models[0]["id"]
        return None

    async def _create_mailing_list(self, name: str, partners: list[dict]) -> int:
        res = await self._create("mailing.list", {"name": name})
        if not res:
            return None
        
        list_id = None
        if isinstance(res, list) and len(res) > 0:
            list_id = res[0]
        elif isinstance(res, int):
            list_id = res
            
        if not list_id:
            return None

        contact_vals = []
        for p in partners:
            email = p.get("email")
            if email:
                contact_vals.append({
                    "name": p.get("name") or email,
                    "email": email,
                    "list_ids": [(4, list_id)]
                })

        if contact_vals:
            await self._create_multi("mailing.contact", contact_vals)
        return list_id

    async def search_customers_by_product(
        self, product_query=None, days_back=30,
        state_filter=None, city_filter=None,
        category_filter=None, min_amount=None,
        source="sales"
    ) -> dict:
        try:
            partner_ids = None

            if product_query or category_filter:
                p_domain = []
                if product_query:
                    search_terms = await self._extract_intelligent_terms(product_query)
                    logger.info(f"OdooVendorWorker: Buscando variantes inteligentes para '{product_query}': {search_terms}")
                    if search_terms:
                        sub_domains = [["name", "ilike", term] for term in search_terms]
                        if len(sub_domains) == 1:
                            p_domain.append(sub_domains[0])
                        else:
                            prod_name_domain = []
                            for _ in range(len(sub_domains) - 1):
                                prod_name_domain.append("|")
                            for sd in sub_domains:
                                prod_name_domain.append(sd)
                            p_domain.extend(prod_name_domain)
                    else:
                        p_domain.append(["name", "ilike", product_query])
                if category_filter:
                    p_domain.append(["categ_id.name", "ilike", category_filter])

                products = await self._search_read("product.product", p_domain, ["id", "name"], limit=100)
                if not products:
                    return {"success": True, "partners": [], "message": "No se encontraron productos con esos criterios."}
                product_ids = [p["id"] for p in products]

                line_model = "sale.order.line" if source == "sales" else "purchase.order.line"
                l_domain = [["product_id", "in", product_ids]]

                if days_back:
                    date_cutoff = (datetime.date.today() - datetime.timedelta(days=int(days_back))).isoformat()
                    l_domain.append(["create_date", ">=", date_cutoff])

                lines = await self._search_read(line_model, l_domain, ["order_id"], limit=500)
                if not lines:
                    return {"success": True, "partners": [], "message": "No se registraron transacciones recientes para esos productos."}

                order_ids = []
                for l in lines:
                    oid = l.get("order_id")
                    if isinstance(oid, (list, tuple)) and len(oid) > 0:
                        order_ids.append(oid[0])
                    elif isinstance(oid, int):
                        order_ids.append(oid)
                order_ids = list(set(order_ids))

                if not order_ids:
                    return {"success": True, "partners": [], "message": "No se encontraron órdenes asociadas."}

                order_model = "sale.order" if source == "sales" else "purchase.order"
                o_domain = [["id", "in", order_ids]]
                if min_amount:
                    o_domain.append(["amount_total", ">=", float(min_amount)])

                orders = await self._search_read(order_model, o_domain, ["partner_id"], limit=500)

                partner_ids = []
                for o in orders:
                    pid = o.get("partner_id")
                    if isinstance(pid, (list, tuple)) and len(pid) > 0:
                        partner_ids.append(pid[0])
                    elif isinstance(pid, int):
                        partner_ids.append(pid)
                partner_ids = list(set(partner_ids))

                if not partner_ids:
                    return {"success": True, "partners": [], "message": "No se encontraron clientes asociados a las órdenes."}

            elif min_amount or days_back:
                order_model = "sale.order" if source == "sales" else "purchase.order"
                o_domain = []
                if days_back:
                    date_cutoff = (datetime.date.today() - datetime.timedelta(days=int(days_back))).isoformat()
                    o_domain.append(["create_date", ">=", date_cutoff])
                if min_amount:
                    o_domain.append(["amount_total", ">=", float(min_amount)])

                orders = await self._search_read(order_model, o_domain, ["partner_id"], limit=500)
                partner_ids = []
                for o in orders:
                    pid = o.get("partner_id")
                    if isinstance(pid, (list, tuple)) and len(pid) > 0:
                        partner_ids.append(pid[0])
                    elif isinstance(pid, int):
                        partner_ids.append(pid)
                partner_ids = list(set(partner_ids))

                if not partner_ids:
                    return {"success": True, "partners": [], "message": "No se encontraron clientes con órdenes que coincidan."}

            p_domain = []
            if partner_ids is not None:
                p_domain.append(["id", "in", partner_ids])

            if state_filter:
                p_domain.append(["state_id.name", "ilike", state_filter])
            if city_filter:
                p_domain.append(["city", "ilike", city_filter])

            p_domain.append(["email", "!=", False])

            partners = await self._search_read("res.partner", p_domain, ["id", "name", "email", "phone", "city", "state_id"], limit=100)
            return {
                "success": True,
                "partners": partners,
                "message": f"Se encontraron {len(partners)} clientes."
            }
        except Exception as e:
            logger.error(f"Error en search_customers_by_product: {e}")
            return {"success": False, "partners": [], "message": f"Error al buscar clientes: {str(e)}"}

    async def create_mailing_draft(
        self, subject: str, partners: list[dict],
        use_list=False, list_name=None
    ) -> dict:
        try:
            if not partners:
                return {"success": False, "message": "No hay destinatarios seleccionados."}

            partner_ids = [p["id"] for p in partners if "id" in p]
            if not partner_ids:
                return {"success": False, "message": "Los destinatarios no tienen IDs válidos."}

            is_mode_b = use_list or len(partner_ids) > 50

            if is_mode_b:
                lname = list_name or f"Lista - {subject[:30]}"
                list_id = await self._create_mailing_list(lname, partners)
                if not list_id:
                    return {"success": False, "message": "Error al crear la lista de contactos en Odoo."}

                model_id = await self._resolve_mailing_model_id("mailing.contact")
                if not model_id:
                    return {"success": False, "message": "No se pudo resolver el modelo mailing.contact en ir.model."}

                vals = {
                    "subject": subject,
                    "mailing_model_id": model_id,
                    "contact_list_ids": [(6, 0, [list_id])],
                    "body_html": "",
                    "state": "draft"
                }
            else:
                model_id = await self._resolve_mailing_model_id("res.partner")
                if not model_id:
                    return {"success": False, "message": "No se pudo resolver el modelo res.partner en ir.model."}

                domain_str = json.dumps([["id", "in", partner_ids]])
                vals = {
                    "subject": subject,
                    "mailing_model_id": model_id,
                    "mailing_domain": domain_str,
                    "body_html": "",
                    "state": "draft"
                }

            res = await self._create("mailing.mailing", vals)
            if not res:
                return {"success": False, "message": "Error al crear el borrador de mailing en Odoo."}

            mailing_id = None
            if isinstance(res, list) and len(res) > 0:
                mailing_id = res[0]
            elif isinstance(res, int):
                mailing_id = res

            if not mailing_id:
                return {"success": False, "message": "No se pudo obtener el ID del mailing creado."}

            return {
                "success": True,
                "mailing_id": mailing_id,
                "mode": "list" if is_mode_b else "domain",
                "message": f"Borrador de mailing MASS/{mailing_id} creado con éxito."
            }
        except Exception as e:
            logger.error(f"Error en create_mailing_draft: {e}")
            return {"success": False, "message": f"Error al crear el mailing: {str(e)}"}
