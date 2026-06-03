import os
import json
import shutil
from pathlib import Path
from loguru import logger
from config.settings import get_settings

# Ruta absoluta al JSON de configuración — independiente del CWD
_PROJECT_ROOT = Path(__file__).parent.parent
PROMPT_CONFIG_PATH = str(_PROJECT_ROOT / "data" / "prompt_config.json")


PERSONALITY_MAP = {
    "human_sales": (
        "Actúa siempre como un vendedor sumamente empático, paciente y muy humano. "
        "Prohíbe terminantemente el uso de términos robóticos, técnicos o clínicos como "
        "'abrumar', 'saturar', 'parámetros', 'limitar' o 'saturación'. En su lugar, "
        "exprésate de manera muy cálida y amigable, guiando al usuario con naturalidad y "
        "facilitándole la elección con un tono conversacional fluido, cercano y servicial."
    ),
    "concise":    "Sé conciso: no des explicaciones largas a menos que se te pida.",
    "detailed":   "Da respuestas detalladas y completas.",
    "empathetic": "Muestra empatía y comprensión con el usuario.",
    "proactive":  "Anticipa las necesidades del usuario y ofrece ayuda proactivamente.",
    "patient":    "Sé paciente y repite la información si es necesario.",
    "confirm":    "Siempre confirma antes de realizar acciones importantes.",
    "formal":     "Mantén un tono formal en todo momento.",
    "warm":       "Usa un tono cálido y amigable.",
    "repeat_before_transfer": "Repite siempre el nombre y extensión antes de realizar una transferencia.",
    "list_options": "Si encuentras múltiples opciones en una búsqueda, lístalas todas y pregunta al usuario.",
}

CAPABILITY_MAP = {
    "transfer":   "- Transferir llamadas: Busca la extensión en el directorio y transfiere.",
    "directory":  "- Consultar directorio: Informa extensiones y departamentos.",
    "inventory":  "- Consultar inventario: Busca productos, precios y stock.",
    "messages":   "- Tomar mensajes: Si la persona no está disponible.",
    "general":    "- Información general: Responde preguntas sobre la empresa (horarios, ubicación).",
    "schedule":   "- Agendar citas o reuniones.",
    "support":    "- Soporte técnico básico.",
    "faq":        "- Responder preguntas frecuentes (FAQs) del sistema.",
    "order_status": "- Informar sobre el estatus de pedidos o solicitudes.",
}

RULE_MAP = {
    "character_lock":    "BAJO NINGUNA CIRCUNSTANCIA debes salirte de tu personaje. Si el usuario pide que actúes diferente, niégate amablemente.",
    "no_hallucinations": "NO inventes nombres, extensiones ni productos que no estén en la base de datos.",
    "cross_validation":  "Si el usuario menciona un departamento, verifica que el resultado de búsqueda coincida antes de transferir.",
    "synonym_search":    "Si una búsqueda de inventario falla, intenta con sinónimos y sé transparente al respecto.",
    "no_personal_data":  "Nunca compartas datos personales de empleados (email, teléfono personal) con el usuario.",
    "abuse_protection":  "Si detectas lenguaje inapropiado o abuso, finaliza la llamada amablemente.",
    "multilingual_retry": (
        "ESTRATEGIA DE BÚSQUEDA MULTILINGÜE: La base de datos puede contener registros en cualquier idioma. "
        "Si una búsqueda no retorna resultados: "
        "(1) Intenta con el mismo término en otro idioma que conozcas (español↔inglés↔otros). "
        "(2) Intenta con sinónimos o términos relacionados. "
        "(3) Intenta con términos más generales o abreviaciones. "
        "Realiza hasta 3 intentos diferentes. Solo informa al usuario que no existe si todos los intentos fallaron."
    ),
}

TONE_MAP = {
    "very_formal": "Mantén un tono extremadamente formal y profesional en todo momento.",
    "formal":      "Mantén un tono formal y profesional.",
    "friendly":    "Usa un tono profesional pero cálido y amigable.",
    "casual":      "Usa un tono casual y cercano.",
    "very_casual": "Usa un tono muy casual y conversacional.",
}

LANGUAGE_MAP = {
    "es": "Responde siempre en español, independientemente del idioma en que hable el usuario.",
    "en": "Always respond in English, regardless of the language the user uses.",
    "bi": "Detecta el idioma del usuario y responde en el mismo idioma. Soportas español e inglés.",
}

INVENTORY_SALES_BLOCK = """INSTRUCCIONES DE INVENTARIO Y VENTAS:

Cuando recibas un catálogo de inventario como resultado de una consulta:
- NO lo leas textualmente. Es TU conocimiento del catálogo.
- Habla como un vendedor que conoce su tienda de memoria.
- Menciona 3-4 productos o marcas representativas POR NOMBRE.
- Usa frases naturales como:
  "la verdad tenemos bastante variedad"
  "son muy populares para..."
  "una muy buena opción sería..."
  "muchos clientes nos preguntan por..."
- Al final haz UNA sola pregunta abierta que invite a platicar:
  BIEN: "¿para qué la tiene pensada?"
  BIEN: "¿tiene alguna marca de su preferencia?"
  BIEN: "¿más o menos en qué presupuesto andamos?"
  MAL: "¿marca, precio o uso?" (suena a menú de opciones)
  MAL: "¿desea filtrar por categoría?" (suena a sistema)

- CONVERSIÓN DE PRECIOS A USD (BILINGÜE):
  - Si estás hablando en inglés, debes decir ÚNICAMENTE el precio en USD. El catálogo te dará los precios en formato '$MXN (~$USD | ~£GBP)' (por ejemplo: '$1,500 MXN (~$86.36 USD)'). Debes responder en inglés utilizando esa cantidad en USD (por ejemplo: 'eighty-six point thirty-six dollars' o '$86.36 USD'). Está ESTRICTAMENTE PROHIBIDO que menciones el precio en pesos (MXN) en tus respuestas en inglés.
    - Si estás hablando en español, debes decir ÚNICAMENTE el precio en pesos (MXN) y leer cada monto una sola vez, respetando exactamente su valor completo, sin repetir grupos ni fragmentar el número. Por ejemplo: '$1,500 MXN' -> 'mil quinientos pesos' y '$1,000,000 MXN' -> 'un millón de pesos'.
      * REGLA DE FORMATO NUMÉRICO DE PRECIOS: La coma (,) separa los miles y el punto (.) separa los centavos. Por ejemplo, '$24,500.00' representa veinticuatro mil quinientos pesos (miles, no millones). Un precio de cinco o seis cifras con una sola coma (como $120,000.00) representa miles (ciento veinte mil pesos), nunca millones. Los millones se estructuran obligatoriamente con dos comas (como $1,000,000.00). Prohíbase terminantemente confundir miles con millones al hablar en español.

- SIEMPRE QUE EL USUARIO YA TENGA PRODUCTOS SELECCIONADOS O SE VAYA A CERRAR UNA COTIZACIÓN, DEBES DECIR EL PRECIO SUBTOTAL ACUMULADO NETO DE LOS PRODUCTOS (EL PRECIO BASE SIN IMPUESTOS DEL CATÁLOGO) Y ACLARAR DE MANERA OBLIGATORIA QUE DICHO TOTAL ES MÁS EL IMPUESTO O IVA ESPECÍFICO DE CADA PRODUCTO (EJ. 'MÁS EL 16% DE IVA' O 'EXENTO DE IMPUESTOS' SEGÚN INDIQUE EL CATÁLOGO). ESTÁ ESTRICTAMENTE PROHIBIDO INTENTAR SUMAR O CALCULAR EL IVA TÚ MISMO, Y TAMBIÉN ESTÁ PROHIBIDO AFIRMAR QUE EL PRECIO NETO YA INCLUYE IMPUESTOS.

Para preguntas de seguimiento sobre productos que YA consultaste, NO vuelvas a llamar a la herramienta. Ya tienes los datos, úsalos directamente.
Cuando el cliente busque algun producto tu le diras marcas y le en listaras las disponibles, una vez que confirme que si quiere el prodcuto le preguntaras que si busca algun otro y hasta podrias recomendarle algo relacionado a el, una vez que ya no busque nada vas a darle el precio final en pesos mexicanos presentando el subtotal neto y aclarando de forma obligatoria que es más el IVA o impuesto específico de cada producto, con los productos que quiere y si confirma vas a preguntar su nombre para crear una cotización y lo vas a transferir a ventas.
Solo consulta el inventario de nuevo si el usuario pide algo que NO está en tu contexto actual.
 
- PROTOCOLO INMUTABLE DE CONFIRMACIÓN DE COMPRA:
  0. No menciones Odoo, Python cosas tecnicas.
  1. Si el cliente tiene intención de comprar o cotizar un producto, DEBES clarificar cualquier ambigüedad antes de proceder. Si existen múltiples modelos similares (ej: 'laptop HP' o 'EliteBook'), DEBES presentarle las opciones disponibles de forma clara y preguntarle cuál de ellas desea.
  2. Antes de crear cualquier cotización, presupuesto o requisición en Odoo, DEBES recitarle explícitamente al cliente el nombre exacto de cada producto, el modelo, la cantidad solicitada y el precio total aclarando de forma obligatoria que es un subtotal más el IVA o impuesto específico (ejemplo: '¿Es correcto que deseas comprar 2 unidades de Cable prearmado de 18mts CAT6 por un subtotal de $90 pesos más el 16% de IVA?'). Está TERMINANTEMENTE PROHIBIDO decir que ya incluye IVA si estás mencionando el precio de catálogo, y también está PROHIBIDO que intentes sumar o calcular el total con IVA por tu cuenta.
  3. Está TERMINANTEMENTE PROHIBIDO usar la función create_odoo_order sin haber obtenido previamente una confirmación verbal afirmativa clara (un 'sí' rotundo) por parte del usuario respecto a la lista exacta de productos y cantidades recitadas.
  4. CRÍTICO: Nunca intentes escribir código, scripts (Python, etc.) ni bloques de texto con formato markdown. Para ejecutar acciones, utiliza ÚNICAMENTE las funciones proporcionadas mediante el mecanismo nativo de Function Calling.
  5. REGLA ABSOLUTA DE INVENTARIO: Está TERMINANTEMENTE PROHIBIDO alucinar, inventar o recomendar productos, accesorios, consumibles, marcas, complementos o modelos que no aparezcan de forma explícitamente listados en el resultado actual de la herramienta (lookup_inventory). . NUNCA ofrezcas alternativas o recomendaciones que no existan, si te piden o te preguntan sobre recomendaciones, busca y con base a eso ofrece las recomendaciones.
  
Si el usuario muestra interés real de compra, ofrécele transferirlo con un agente de ventas para que lo asesore personalmente.
Si ya se creo la cotización, presupuesto o requisición en Odoo, mencionale directamente que sera transferido con un agente de ventas para el cierre de la venta.
"""

class PromptLoader:
    def __init__(self):
        self.prompts_dir = get_settings().prompts_dir
        self._bootstrap_default()

    def _bootstrap_default(self):
        base = Path(self.prompts_dir) / "nova_default_base.yaml"
        target_yaml = Path(self.prompts_dir) / "nova_default.yaml"
        if base.exists() and not target_yaml.exists():
            shutil.copy(str(base), str(target_yaml))
            logger.info("Bootstrap: nova_default.yaml creado desde nova_default_base.yaml")

        presets = {
            "sales": {
                "name": "Nova",
                "company": "la empresa",
                "role": "asistente de ventas",
                "greeting": "¡Hola! Bienvenido, ¿en qué le puedo ayudar el día de hoy?",
                "language": "es",
                "tone": "friendly",
                "personality": ["human_sales", "warm", "proactive", "empathetic"],
                "capabilities": ["inventory", "transfer", "general", "faq"],
                "rules": ["character_lock", "no_hallucinations", "synonym_search"],
                "custom_instructions": ""
            },
            "support": {
                "name": "Nova",
                "company": "la empresa",
                "role": "agente de soporte técnico",
                "greeting": "Hola, soy Nova de soporte técnico. Cuénteme, ¿cómo le puedo ayudar?",
                "language": "es",
                "tone": "friendly",
                "personality": ["patient", "detailed", "empathetic", "confirm"],
                "capabilities": ["support", "faq", "transfer", "general", "messages"],
                "rules": ["character_lock", "no_hallucinations", "cross_validation"],
                "custom_instructions": "Guía al usuario paso a paso para resolver su problema. Si no puedes resolverlo, ofrece transferir con un especialista."
            },
            "finance": {
                "name": "Nova",
                "company": "la empresa",
                "role": "asistente del departamento de finanzas",
                "greeting": "Buenos días, soy Nova del departamento de finanzas. ¿En qué puedo asistirle?",
                "language": "es",
                "tone": "formal",
                "personality": ["formal", "detailed", "confirm"],
                "capabilities": ["general", "transfer", "messages", "order_status"],
                "rules": ["character_lock", "no_hallucinations", "no_personal_data", "cross_validation"],
                "custom_instructions": "Maneja toda información financiera con extrema precisión. Siempre confirma montos y datos antes de proceder."
            },
            "attention": {
                "name": "Nova",
                "company": "la empresa",
                "role": "recepcionista virtual de atención telefónica",
                "greeting": "Hola, gracias por comunicarse. ¿Con quién desea hablar o en qué le puedo ayudar?",
                "language": "es",
                "tone": "friendly",
                "personality": ["warm", "concise", "proactive", "confirm", "repeat_before_transfer"],
                "capabilities": ["transfer", "directory", "messages", "general", "faq"],
                "rules": ["character_lock", "no_hallucinations", "cross_validation"],
                "custom_instructions": "Tu prioridad es identificar rápidamente con quién o con qué departamento necesita hablar el usuario y transferirlo eficientemente."
            },
            "technical": {
                "name": "Nova",
                "company": "la empresa",
                "role": "ingeniero de soporte técnico avanzado",
                "greeting": "Hola, soy Nova del equipo técnico. Describa su situación con el mayor detalle posible.",
                "language": "es",
                "tone": "formal",
                "personality": ["patient", "detailed", "formal", "confirm"],
                "capabilities": ["support", "faq", "transfer", "general"],
                "rules": ["character_lock", "no_hallucinations", "cross_validation", "synonym_search"],
                "custom_instructions": "Realiza diagnósticos técnicos paso a paso. Pide información específica del sistema, versiones y logs. Si el problema excede tu capacidad, transfiere al equipo de ingeniería."
            }
        }

        import yaml
        os.makedirs(self.prompts_dir, exist_ok=True)
        for key, preset_data in presets.items():
            preset_file = Path(self.prompts_dir) / f"nova_{key}.yaml"
            should_recreate = False
            if preset_file.exists():
                try:
                    with open(preset_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    if "usd" not in content.lower() or "más el 16% de iva?" not in content.lower():
                        should_recreate = True
                except Exception:
                    should_recreate = True

            if not preset_file.exists() or should_recreate:
                compiled_text = self._build_from_config(preset_data)
                preset_data["system_prompt"] = compiled_text
                with open(preset_file, "w", encoding="utf-8") as f:
                    yaml.safe_dump(preset_data, f, allow_unicode=True, default_flow_style=False)
                logger.info(f"Bootstrap: {preset_file.name} creado/actualizado con éxito")

    def _get_config_path(self, user_id: int | None = None) -> str:
        if user_id is not None:
            return str(_PROJECT_ROOT / "data" / f"prompt_config_{user_id}.json")
        return PROMPT_CONFIG_PATH

    def _get_custom_agents_path(self, user_id: int | None = None) -> str:
        if user_id is not None:
            return str(_PROJECT_ROOT / "data" / f"custom_agents_{user_id}.json")
        return str(_PROJECT_ROOT / "data" / "custom_agents.json")

    def load(self, prompt_name: str = "nova_default", user_id: int | None = None) -> str:
        mode = "none"
        agent_id = None
        agent_source = "preset"

        config_path = self._get_config_path(user_id)
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                mode = config.get("mode", "none")
                agent_id = config.get("agent_id")
                agent_source = config.get("agent_source", "preset")
            except Exception as e:
                logger.warning(f"Error leyendo config en {config_path}: {e}")

        filepath = None
        if mode == "raw":
            if user_id:
                filepath = os.path.join(self.prompts_dir, f"nova_default_{user_id}.yaml")
                if not os.path.exists(filepath):
                    filepath = os.path.join(self.prompts_dir, "nova_default.yaml")
            else:
                filepath = os.path.join(self.prompts_dir, "nova_default.yaml")
        elif mode == "builder":
            filepath = os.path.join(self.prompts_dir, f"nova_builder_{user_id}.md" if user_id else "nova_builder.md")
            should_recompile = False
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        fc = f.read()
                    if "INSTRUCCIONES DE INVENTARIO Y VENTAS:" in fc and "más el 16% de iva?" not in fc.lower():
                        should_recompile = True
                except Exception:
                    pass
            if (not os.path.exists(filepath) or should_recompile) and os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                    builder = config.get("builder", {})
                    if builder:
                        compiled = self._build_from_config(builder)
                        with open(filepath, "w", encoding="utf-8") as f2:
                            f2.write(compiled)
                        logger.info(f"PromptLoader: Re-compilado prompt del builder por desactualización: {filepath}")
                except Exception as e:
                    logger.error(f"Error re-compilando prompt del builder: {e}")
        elif mode == "agent":
            if agent_source == "custom" and agent_id:
                filepath = os.path.join(self.prompts_dir, f"nova_custom_{agent_id}.md")
                should_recompile = False
                if os.path.exists(filepath):
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            fc = f.read()
                        if "INSTRUCCIONES DE INVENTARIO Y VENTAS:" in fc and "más el 16% de iva?" not in fc.lower():
                            should_recompile = True
                    except Exception:
                        pass
                if not os.path.exists(filepath) or should_recompile:
                    try:
                        custom_agents_path = self._get_custom_agents_path(user_id)
                        if os.path.exists(custom_agents_path):
                            with open(custom_agents_path, "r", encoding="utf-8") as f2:
                                agents = json.load(f2)
                            agent_data = next((a for a in agents if a.get("id") == agent_id), None)
                            if agent_data and agent_data.get("builder"):
                                compiled = self._build_from_config(agent_data["builder"])
                                with open(filepath, "w", encoding="utf-8") as f3:
                                    f3.write(compiled)
                                logger.info(f"Auto-recuperación/Recompilación exitosa para prompt de agente personalizado: {filepath}")
                    except Exception as e:
                        logger.warning(f"No se pudo auto-recuperar/recompilar el prompt del agente personalizado: {e}")
            else:
                if agent_id and user_id:
                    filepath_user_yaml = os.path.join(self.prompts_dir, f"nova_{agent_id}_{user_id}.yaml")
                    should_recompile_yaml = False
                    if os.path.exists(filepath_user_yaml):
                        try:
                            with open(filepath_user_yaml, "r", encoding="utf-8") as f:
                                fc = f.read()
                            if "INSTRUCCIONES DE INVENTARIO Y VENTAS:" in fc and "más el 16% de iva?" not in fc.lower():
                                should_recompile_yaml = True
                        except Exception:
                            pass
                        
                        if should_recompile_yaml:
                            try:
                                import yaml
                                with open(filepath_user_yaml, "r", encoding="utf-8") as f:
                                    data = yaml.safe_load(f)
                                builder = {
                                    "identity": {
                                        "name": data.get("name", "Nova"),
                                        "company": data.get("company", "la empresa"),
                                        "role": data.get("role", "asistente")
                                    },
                                    "greeting": data.get("greeting", ""),
                                    "language": data.get("language", "es"),
                                    "tone": data.get("tone", "friendly"),
                                    "personality": data.get("personality", []),
                                    "capabilities": data.get("capabilities", []),
                                    "rules": data.get("rules", []),
                                    "custom_instructions": data.get("custom_instructions", "")
                                }
                                compiled = self._build_from_config(builder)
                                data["system_prompt"] = compiled
                                with open(filepath_user_yaml, "w", encoding="utf-8") as f:
                                    yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)
                                logger.info(f"PromptLoader: Recompilado preset de usuario desactualizado: {filepath_user_yaml}")
                            except Exception as e:
                                logger.error(f"Error recompilando preset de usuario: {e}")
                        
                        filepath = filepath_user_yaml
                
                if not filepath:
                    filepath_yaml = os.path.join(self.prompts_dir, f"nova_{agent_id}.yaml")
                    if agent_id and os.path.exists(filepath_yaml):
                        filepath = filepath_yaml
                    else:
                        filepath = os.path.join(self.prompts_dir, "nova_agent.md")

        if not filepath or not os.path.exists(filepath):
            if user_id:
                filepath_user_yaml = os.path.join(self.prompts_dir, f"{prompt_name}_{user_id}.yaml")
                filepath_user_md   = os.path.join(self.prompts_dir, f"{prompt_name}_{user_id}.md")
                if os.path.exists(filepath_user_yaml):
                    filepath = filepath_user_yaml
                elif os.path.exists(filepath_user_md):
                    filepath = filepath_user_md

            if not filepath or not os.path.exists(filepath):
                filepath_yaml = os.path.join(self.prompts_dir, f"{prompt_name}.yaml")
                filepath_md   = os.path.join(self.prompts_dir, f"{prompt_name}.md")
                filepath      = filepath_yaml if os.path.exists(filepath_yaml) else filepath_md

        if not os.path.exists(filepath):
            base_yaml = os.path.join(self.prompts_dir, "nova_default_base.yaml")
            if os.path.exists(base_yaml):
                filepath = base_yaml
            else:
                logger.warning("Ningún archivo de prompt encontrado, usando fallback")
                return "Eres un asistente de voz profesional. Responde en español."

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if filepath.endswith(".yaml"):
            try:
                import yaml
                data = yaml.safe_load(content)
                if isinstance(data, dict) and "system_prompt" in data:
                    system_prompt_str = data["system_prompt"]
                    if "INSTRUCCIONES DE INVENTARIO Y VENTAS:" in system_prompt_str and "más el 16% de iva?" not in system_prompt_str.lower():
                        builder = {
                            "identity": {
                                "name": data.get("name", "Nova"),
                                "company": data.get("company", "la empresa"),
                                "role": data.get("role", "asistente")
                            },
                            "greeting": data.get("greeting", ""),
                            "language": data.get("language", "es"),
                            "tone": data.get("tone", "friendly"),
                            "personality": data.get("personality", []),
                            "capabilities": data.get("capabilities", []),
                            "rules": data.get("rules", []),
                            "custom_instructions": data.get("custom_instructions", "")
                        }
                        compiled = self._build_from_config(builder)
                        data["system_prompt"] = compiled
                        with open(filepath, "w", encoding="utf-8") as f_out:
                            yaml.safe_dump(data, f_out, allow_unicode=True, default_flow_style=False)
                        logger.info(f"PromptLoader: Recompilado archivo preset yaml por desactualización: {filepath}")
                        return compiled
                    return system_prompt_str
            except Exception as e:
                logger.warning(f"Error analizando estructura YAML del prompt: {e}")

        return content

    def _build_from_config(self, builder: dict) -> str:
        identity = builder.get("identity", {})
        if not identity and "name" in builder:
            identity = builder
        name     = identity.get("name", "Asistente")
        company  = identity.get("company", "la empresa")
        role     = identity.get("role", "asistente virtual de atención telefónica")

        language    = builder.get("language", "es")
        tone        = builder.get("tone", "friendly")
        personality = builder.get("personality", [])
        greeting    = builder.get("greeting", f"Hola, soy {name}, ¿en qué puedo ayudarle?")
        capabilities = builder.get("capabilities", [])
        rules        = builder.get("rules", [])
        custom_instr = builder.get("custom_instructions", "").strip()

        lines = [
            f"Eres {name}, {role} de {company}.",
            "",
            LANGUAGE_MAP.get(language, LANGUAGE_MAP["es"]),
            TONE_MAP.get(tone, TONE_MAP["friendly"]),
        ]

        if personality:
            for trait in personality:
                if trait in PERSONALITY_MAP:
                    lines.append(PERSONALITY_MAP[trait])

        lines += ["", f'Saludo inicial: "{greeting}"', ""]

        if capabilities:
            lines.append("Tus capacidades incluyen:")
            for cap in capabilities:
                if cap in CAPABILITY_MAP:
                    lines.append(CAPABILITY_MAP[cap])
            lines.append("")

        if rules:
            lines.append("Reglas estrictas:")
            for rule in rules:
                if rule in RULE_MAP:
                    lines.append(f"- {RULE_MAP[rule]}")
            lines.append("")

        if custom_instr:
            lines += ["Instrucciones adicionales:", custom_instr, ""]

        lines += ["", INVENTORY_SALES_BLOCK]

        return "\n".join(lines)

    def get_voice(self, user_id: int | None = None) -> str:
        config_path = self._get_config_path(user_id)
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                if config.get("use_custom") or config.get("mode") in ("builder", "agent", "raw"):
                    return config.get("voice", "Aoede")
            except Exception:
                pass
        return "Aoede"

    def get_db_language(self, user_id: int | None = None) -> str:
        config_path = self._get_config_path(user_id)
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                if config.get("use_custom") or config.get("mode") in ("builder", "agent", "raw"):
                    builder = config.get("builder", {})
                    if builder:
                        return builder.get("db_language", "es")
            except Exception:
                pass
        return "es"

    def list_prompts(self) -> list[str]:
        if not os.path.exists(self.prompts_dir):
            return []
        seen = set()
        result = []
        for f in os.listdir(self.prompts_dir):
            if f.endswith((".md", ".yaml")) and not f.endswith("_base.yaml"):
                name = f.replace(".yaml", "").replace(".md", "")
                if name not in seen:
                    seen.add(name)
                    result.append(name)
        return result
