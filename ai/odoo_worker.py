import httpx
import asyncio
import json
from typing import Any
from loguru import logger
from collections import defaultdict


class OdooInventoryWorker:
    def __init__(self, base_url: str, api_key: str, db_name: str = "", odoo_user: str = ""):
        url = base_url.rstrip("/")
        for suffix in ["/odoo", "/web", "/api"]:
            if url.lower().endswith(suffix):
                url = url[:-len(suffix)]
        self.base_url = url
        self.api_key = api_key
        self.db_name = db_name
        self.odoo_user = odoo_user
        self._headers = {
            "Authorization": f"bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            from config.settings import get_settings
            from google import genai
            settings = get_settings()
            if settings.gemini_api_key:
                self.ai_client = genai.Client(api_key=settings.gemini_api_key)
                self.ai_model = settings.gemini_worker_model or "gemini-2.0-flash"
                logger.info(f"OdooInventoryWorker: Gemini AI de soporte inicializado ({self.ai_model})")
            else:
                self.ai_client = None
        except Exception as e:
            logger.warning(f"OdooInventoryWorker: No se pudo inicializar GeminiClient: {e}")
            self.ai_client = None

    async def _search_read(self, model: str, domain: list, fields: list,
                            limit: int = 30, order: str = "name asc") -> list[dict]:
        url = f"{self.base_url}/json/2/{model}/search_read"
        payload = {
            "domain": domain,
            "fields": fields,
            "limit": limit,
            "order": order,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=self._headers, json=payload)
                if resp.status_code == 401:
                    logger.error(f"Odoo: 401 Unauthorized para {url}")
                    return []
                if resp.status_code == 403:
                    logger.error(f"Odoo: 403 Forbidden para {url}")
                    return []
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict):
                    if data.get("error"):
                        logger.error(f"Odoo API Error en search_read: {data['error']}")
                        return []
                    if "result" in data:
                        return data["result"]
                if isinstance(data, list):
                    return data
                return []
        except httpx.TimeoutException:
            logger.error("Odoo: Timeout al consultar inventario")
            return []
        except Exception as e:
            logger.error(f"Odoo search_read error: {e}")
            return []

    async def _create(self, model: str, values: dict) -> Any:
        url = f"{self.base_url}/json/2/{model}/create"
        payload = {
            "vals_list": [values]
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=self._headers, json=payload)
                if resp.status_code == 401:
                    logger.error(f"Odoo: 401 Unauthorized para {url}")
                    return None
                if resp.status_code == 403:
                    logger.error(f"Odoo: 403 Forbidden para {url}")
                    return None
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict):
                    if data.get("error"):
                        logger.error(f"Odoo API Error en create para {model}: {data['error']}")
                        return None
                    if "result" in data:
                        return data["result"]
                return data
        except Exception as e:
            logger.error(f"Odoo create error para {model}: {e}")
            return None

    def _get_stem_variants(self, word: str) -> list[str]:
        w = word.strip().lower()
        if len(w) < 2:
            return [w]
        for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ü", "u")]:
            w = w.replace(a, b)
        variants = {w}
        if w.endswith("aciones"):
            variants.add(w[:-7])
        elif w.endswith("acion"):
            variants.add(w[:-5])
        elif w.endswith("iones"):
            variants.add(w[:-5])
        elif w.endswith("ion"):
            variants.add(w[:-3])
        if w.endswith("adoras") or w.endswith("adores"):
            variants.add(w[:-6])
            variants.add(w[:-5])
        elif w.endswith("adora") or w.endswith("adore") or w.endswith("ador"):
            variants.add(w[:-5])
            variants.add(w[:-4])
            variants.add(w[:-3])
        if w.endswith("es"):
            variants.add(w[:-2])
            if w.endswith("ones"):
                variants.add(w[:-4])
        elif w.endswith("s"):
            variants.add(w[:-1])
        w_singular = w[:-1] if w.endswith("s") else w
        if len(w_singular) >= 4:
            if w_singular.endswith("o") or w_singular.endswith("a"):
                variants.add(w_singular[:-1])
            elif w_singular.endswith("os") or w_singular.endswith("as"):
                variants.add(w_singular[:-2])
        if len(w) >= 6:
            variants.add(w[:5])
            variants.add(w[:6])
        elif len(w) >= 5:
            variants.add(w[:4])
        return sorted(list(variants), key=len)

    async def _extract_intelligent_terms(self, query: str) -> list[str]:
        q_norm = query.strip()
        if not q_norm:
            return []
        q_clean = q_norm.lower()
        for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")]:
            q_clean = q_clean.replace(a, b)
        stopwords = {"de", "la", "el", "en", "un", "los", "las", "del", "al", "por", "con", "sin", "para", "como", "una", "y", "para", "que", "busco", "quiero", "necesito", "encontrar", "ver"}
        words = [w for w in q_clean.split() if w not in stopwords and len(w) >= 2]
        basic_variants = []
        if words:
            for w in words:
                basic_variants.extend(self._get_stem_variants(w))
            if len(words) >= 2:
                basic_variants.append(" ".join(words))
                basic_variants.append(" ".join(words[1:]))
                basic_variants.append(" ".join(words[:-1]))
        tech_variants = []
        for v in list(basic_variants):
            if "access" in v:
                tech_variants.append(v.replace("access", "acces"))
            elif "acces" in v:
                tech_variants.append(v.replace("acces", "access"))
            if "swich" in v:
                tech_variants.append(v.replace("swich", "switch"))
            elif "switch" in v:
                tech_variants.append(v.replace("switch", "swich"))
        basic_variants.extend(tech_variants)
        seen = set()
        basic_variants = [v for v in basic_variants if not (v.lower() in seen or seen.add(v.lower()))]
        if not self.ai_client:
            return basic_variants
        prompt = f"""Eres un motor de traducción semántica y corrección ortográfica para un buscador de inventario en Odoo.
Tu tarea es analizar la consulta del usuario en lenguaje natural y extraer los términos de búsqueda óptivos que se usarán en una consulta de base de datos relacional (usando operador ILIKE).

Sigue estas reglas estrictas:
1. Identifica el núcleo esencial del producto. Ignora palabras de relleno, conectores o explicaciones (ej: en "busco unidad de almacenamiento para computadora hp tipo ssd", lo esencial es "ssd", opcionalmente "hp").
2. Corrige errores ortográficos y simplifica términos técnicos (ej: "acxes point" -> "access point", "acces point").
3. Incluye sinónimos o variaciones comunes de marcas/modelos en español e inglés relevantes para tecnología (ej: si busca "laptops" o "computadoras", incluye ["laptop", "pc", "computadora", "portatil", "notebook"]).
4. Devuelve el resultado ESTRICTAMENTE en un formato JSON plano que contenga una lista de cadenas de búsqueda principales optimizadas.

Consulta del usuario: "{q_norm}"
Devuelve ÚNICAMENTE el JSON plano estructurado con la clave "search_terms". Sin formato markdown ni texto explicativo adicional."""
        try:
            def run_api():
                return self.ai_client.models.generate_content(
                    model=self.ai_model,
                    contents=prompt
                )
            resp = await asyncio.to_thread(run_api)
            text = resp.text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```json"):
                    text = "\n".join(lines[1:-1])
                elif lines[0].startswith("```"):
                    text = "\n".join(lines[1:-1])
            data = json.loads(text)
            terms = data.get("search_terms", [])
            if isinstance(terms, list) and len(terms) > 0:
                expanded_terms = []
                for term in terms:
                    expanded_terms.append(term)
                    for part in term.split():
                        if part not in stopwords and len(part) >= 2:
                            expanded_terms.extend(self._get_stem_variants(part))
                seen_exp = set()
                expanded_terms = [t for t in expanded_terms if not (t.lower() in seen_exp or seen_exp.add(t.lower()))]
                logger.info(f"Odoo Worker AI extrajo términos semánticos y expandió: {expanded_terms}")
                return expanded_terms
        except Exception as e:
            logger.error(f"Error extrayendo términos semánticos de Gemini: {e}")
        return basic_variants

    async def process(self, query: str, session=None) -> str:
        q = query.strip()
        if not q:
            return "No se especificó qué buscar en Odoo."

        q_norm = q.lower()
        for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")]:
            q_norm = q_norm.replace(a, b)

        is_additional = any(
            kw in q_norm for kw in [
                "adicional", "restante", "faltante", "los otros", "los demas",
                "los dema", "mas", "siguientes", "continuar",
                "listame todos", "todos los demas", "todos los restantes",
                "dame los demas", "dame todos", "todo", "todos", "todas",
                "toda", "completo", "completa", "entero", "todo lo que tengas",
                "dame todo"
            ]
        )

        if is_additional and session and "last_inventory_results" in session.metadata:
            return self._paginate_cached(session)

        search_terms = await self._extract_intelligent_terms(q)
        logger.info(f"OdooWorker: Buscando variantes inteligentes para '{q}': {search_terms}")

        sub_domains = []
        for term in search_terms:
            sub_domains.append(["|", "|", "|",
                ["name", "ilike", term],
                ["default_code", "ilike", term],
                ["barcode", "ilike", term],
                ["categ_id.name", "ilike", term],
            ])

        if len(sub_domains) == 1:
            domain = sub_domains[0]
        else:
            domain = []
            for _ in range(len(sub_domains) - 1):
                domain.append("|")
            for sd in sub_domains:
                domain.extend(sd)

        fields = [
            "name", "default_code", "barcode",
            "list_price", "qty_available",
            "categ_id", "type", "taxes_id",
        ]

        results = await self._search_read("product.product", domain, fields, limit=80)

        if not results:
            return f"No se encontraron productos en Odoo para '{q}'."

        results = await self._attach_taxes(results)

        total = len(results)

        if session:
            session.metadata["last_inventory_results"] = {
                "query": q,
                "results": results,
                "current_index": min(total, 15),
            }

        if total <= 15:
            catalog = self._build_catalog(results, q)
        else:
            catalog = self._build_catalog(results[:15], q)
            all_categories = sorted(set(
                p.get("categ_id")[1] if isinstance(p.get("categ_id"), (list, tuple)) and len(p.get("categ_id")) >= 2 else "General"
                for p in results
            ))
            catalog += f"\n\nMostrando 15 de {total} productos."
            catalog += f"\nCategorías disponibles: {', '.join(all_categories)}."
            catalog += f"\n\nSi deseas ver los demás productos, por favor di 'siguiente' o 'ver más'."

        return catalog

    def _paginate_cached(self, session) -> str:
        cached = session.metadata["last_inventory_results"]
        results = cached.get("results", [])
        original_query = cached.get("query", "")
        start_idx = cached.get("current_index", 0)

        remaining = results[start_idx:]
        if not remaining:
            return "Ya se han mostrado todos los productos de esa búsqueda en Odoo."

        page = remaining[:15]
        next_index = start_idx + len(page)
        cached["current_index"] = next_index

        catalog = self._build_catalog(page, original_query, continuation=True)

        has_more = len(results) > next_index
        if has_more:
            left = len(results) - next_index
            catalog += f"\n\nQuedan {left} productos adicionales en Odoo. Di 'ver más' o 'siguientes' para continuar."
        else:
            catalog += "\n\nEstos son todos los productos restantes en Odoo."

        logger.info(f"OdooWorker paginación: enviando {len(page)} productos (idx {start_idx}-{next_index})")
        return catalog

    async def _attach_taxes(self, products: list[dict]) -> list[dict]:
        all_tax_ids = set()
        for p in products:
            for tid in (p.get("taxes_id") or []):
                all_tax_ids.add(int(tid))

        if not all_tax_ids:
            return products

        domain = [["id", "in", list(all_tax_ids)]]
        fields = ["id", "name", "amount", "amount_type"]
        tax_records = await self._search_read("account.tax", domain, fields, limit=len(all_tax_ids))

        tax_map = {}
        for t in tax_records:
            tid = t.get("id")
            amount_type = t.get("amount_type", "percent")
            amount = t.get("amount", 0)
            name = t.get("name", "")
            if amount_type == "percent":
                label = f"{name} ({amount:.4g}%)"
            elif amount_type == "fixed":
                label = f"{name} (fijo ${amount:,.2f})"
            else:
                label = name
            tax_map[tid] = label

        for p in products:
            tax_ids = p.get("taxes_id") or []
            p["_taxes_resolved"] = [tax_map[int(i)] for i in tax_ids if int(i) in tax_map]

        return products

    def _build_catalog(self, products: list[dict], query: str, continuation: bool = False) -> str:
        grouped = defaultdict(list)
        for p in products:
            cat = "General"
            categ = p.get("categ_id")
            if isinstance(categ, (list, tuple)) and len(categ) >= 2:
                cat = categ[1]
            elif isinstance(categ, str):
                cat = categ
            grouped[cat].append(p)

        lines = []
        if not continuation:
            lines.append("=== INVENTARIO ODOO ===")
            lines.append("")

        for category in sorted(grouped.keys()):
            lines.append(category.upper())
            for p in grouped[category]:
                name = p.get("name", "Producto")
                code = p.get("default_code") or ""
                price = p.get("list_price", 0) or 0
                qty = p.get("qty_available", 0) or 0
                barcode = p.get("barcode") or ""
                taxes = p.get("_taxes_resolved") or []

                stock_str = f"stock: {int(qty)}" if qty > 0 else "agotado"
                code_str = f" [{code}]" if code else ""
                barcode_str = f" | cod.barras: {barcode}" if barcode else ""
                tax_str = f" | IVA: {', '.join(taxes)}" if taxes else ""
                line = f"    - {name}{code_str} — ${price:,.2f} ({stock_str}){barcode_str}{tax_str}"
                lines.append(line)
            lines.append("")

        total_p = len(products)
        if not continuation:
            lines.append(f"Encontrados en esta categoría: {total_p} productos")

        return "\n".join(lines)


    async def test_connection(self) -> dict:
        url = f"{self.base_url}/json/2/res.users/search_read"
        payload = {"domain": [["id", "=", 1]], "fields": ["name", "login"], "limit": 1}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=self._headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    result = data.get("result", data) if isinstance(data, dict) else data
                    if isinstance(result, list) and len(result) > 0:
                        return {"success": True, "message": f"Conexión exitosa a Odoo. Usuario: {result[0].get('name', '?')}"}
                    return {"success": True, "message": "Conexión a Odoo exitosa (sin datos de usuario)"}
                if resp.status_code == 401:
                    return {"success": False, "message": "API Key inválida o expirada"}
                if resp.status_code == 403:
                    return {"success": False, "message": "Sin permisos. Revisa los ACL del usuario"}
                
                content_type = resp.headers.get("Content-Type", "").lower()
                text = resp.text or ""
                if "html" in content_type or text.strip().startswith(("<html", "<!doctype", "<body", "<script")):
                    return {"success": False, "message": f"Error HTTP {resp.status_code}: El servidor de Odoo respondió con una página web (HTML). Verifica si la URL o el subdominio de Odoo son correctos."}
                
                return {"success": False, "message": f"Error HTTP {resp.status_code}: {text[:200]}"}
        except httpx.TimeoutException:
            return {"success": False, "message": "Timeout al conectar con Odoo (>10s)"}
        except Exception as e:
            return {"success": False, "message": f"Error de conexión: {str(e)}"}


def get_odoo_worker(base_url: str, api_key: str, db_name: str = "", odoo_user: str = "", user_id: int | None = None) -> OdooInventoryWorker:
    is_vendor = False
    if user_id is not None:
        try:
            from ai.prompt_loader import PromptLoader
            loader = PromptLoader()
            p_config = loader.get_prompt_config_cache(user_id)
            if p_config is None:
                import os
                config_path = loader._get_config_path(user_id)
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        p_config = json.load(f)
            
            if isinstance(p_config, dict) and p_config.get("odoo_agent_type") == "odoo_vendor_support":
                is_vendor = True
        except Exception as e:
            logger.error(f"Error resolviendo tipo de odoo worker: {e}")

    if is_vendor:
        from ai.odoo_vendor_worker import OdooVendorWorker
        return OdooVendorWorker(base_url, api_key, db_name, odoo_user)
    else:
        return OdooInventoryWorker(base_url, api_key, db_name, odoo_user)
