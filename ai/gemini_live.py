import asyncio
import json
from google import genai
from google.genai import types
from loguru import logger
from config.settings import get_settings
from ai.prompt_loader import PromptLoader
from ai.function_registry import FunctionRegistry
from core.session import CallSession


class GeminiLiveClient:
    def __init__(self, function_registry: FunctionRegistry, prompt_loader: PromptLoader):
        settings = get_settings()
        self._model = settings.gemini_model
        self._registry = function_registry
        self._prompt_loader = prompt_loader
        self._client = None

        if settings.gemini_api_key:
            self._client = genai.Client(api_key=settings.gemini_api_key)
            logger.info(f"Gemini Live Client inicializado con modelo: {self._model}")
        else:
            logger.warning("GEMINI_API_KEY no configurada. Configúrala en .env para habilitar la IA.")

    def _build_config(self, prompt_name: str = "nova_default", user_id: int | None = None) -> types.LiveConnectConfig:
        system_prompt = self._prompt_loader.load(prompt_name, user_id=user_id)

        if not isinstance(system_prompt, str):
            logger.error(
                f"[_build_config] system_prompt no es string "
                f"(type={type(system_prompt).__name__}, user_id={user_id}). "
                f"Usando prompt base."
            )
            system_prompt = self._prompt_loader.load("nova_default")
            if not isinstance(system_prompt, str):
                system_prompt = "Eres un asistente de voz profesional. Responde en español."

        tools      = self._registry.load_schemas()
        voice_name = self._prompt_loader.get_voice(user_id=user_id)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(
                parts=[types.Part(text=system_prompt)]
            ),
            tools=tools,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            ),
        )

    @staticmethod
    def _drain_queue(q: asyncio.Queue):
        while not q.empty():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def start_session(self, session: CallSession, prompt_name: str = "nova_default", user_id: int | None = None):
        if not self._client:
            logger.error("No se puede iniciar sesión: GEMINI_API_KEY no configurada")
            return

        config = self._build_config(prompt_name, user_id=user_id)
        max_retries = 3

        for attempt in range(max_retries):
            if not session.active:
                break
            try:
                self._drain_queue(session.audio_queue_in)
                logger.info(f"Conectando sesión {session.session_id} a Gemini Live (intento {attempt + 1}/{max_retries})...")
                async with self._client.aio.live.connect(
                    model=self._model,
                    config=config
                ) as gemini_session:
                    session.gemini_session = gemini_session
                    logger.info(f"Sesión {session.session_id} conectada a Gemini Live")

                    send_task = asyncio.create_task(
                        self._send_audio_loop(session, gemini_session)
                    )
                    receive_task = asyncio.create_task(
                        self._receive_loop(session, gemini_session)
                    )

                    await asyncio.sleep(0.1)

                    await gemini_session.send(
                        input="Hola",
                        end_of_turn=True
                    )

                    await asyncio.gather(send_task, receive_task)
                    break

            except asyncio.CancelledError:
                logger.info(f"Sesión Gemini {session.session_id} cancelada")
                break
            except Exception as e:
                logger.error(f"Error en sesión Gemini {session.session_id} (intento {attempt + 1}): {e}")
                self._drain_queue(session.audio_queue_in)
                if attempt < max_retries - 1 and session.active:
                    wait = 1.5 * (attempt + 1)
                    logger.info(f"Reintentando en {wait:.1f}s...")
                    await asyncio.sleep(wait)
                else:
                    session.active = False
                    break
            finally:
                session.gemini_session = None

    async def _send_audio_loop(self, session: CallSession, gemini_session):
        try:
            while session.active:
                try:
                    audio_chunk = await asyncio.wait_for(
                        session.audio_queue_in.get(), timeout=0.5
                    )
                    if audio_chunk is None:
                        break

                    if session.metadata.get("tool_running", False):
                        # Descartar el audio o ignorarlo mientras procesamos tools
                        continue

                    await gemini_session.send(
                        input={"data": audio_chunk, "mime_type": "audio/pcm;rate=16000"}
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error enviando audio a Gemini: {e}")
        finally:
            self._drain_queue(session.audio_queue_in)

    async def _receive_loop(self, session: CallSession, gemini_session):
        try:
            while session.active:
                try:
                    async for response in gemini_session.receive():
                        if not session.active:
                            break

                        usage = getattr(response, "usage_metadata", None)
                        if usage:
                            tin  = getattr(usage, "prompt_token_count", 0) or 0
                            tout = getattr(usage, "candidates_token_count", 0) or 0
                            session.tokens_input  = tin
                            session.tokens_output = tout
                            session.metadata["last_usage"] = {
                                "tokens_input":  session.tokens_input,
                                "tokens_output": session.tokens_output,
                                "tokens_total":  session.tokens_total,
                            }
                            if session.token_limit_reached:
                                logger.warning(
                                    f"[{session.session_id}] CIRCUIT BREAKER: "
                                    f"límite de {session.tokens_total} tokens alcanzado. "
                                    f"Cerrando sesión."
                                )
                                session.active = False
                                break

                        server_content = response.server_content
                        if server_content:
                            if server_content.interrupted:
                                logger.debug(f"[{session.session_id}] IA interrumpida por usuario")
                                while not session.audio_queue_out.empty():
                                    try:
                                        session.audio_queue_out.get_nowait()
                                    except asyncio.QueueEmpty:
                                        break
                                continue

                            model_turn = server_content.model_turn
                            if model_turn:
                                for part in model_turn.parts:
                                    if part.text:
                                        logger.info(f"[{session.session_id}] IA: {part.text}")
                                        if not hasattr(session, "_ai_transcript_accumulator"):
                                            session._ai_transcript_accumulator = []
                                        session._ai_transcript_accumulator.append(part.text)
                                    if part.inline_data:
                                        try:
                                            session.audio_queue_out.put_nowait(part.inline_data.data)
                                        except asyncio.QueueFull:
                                            try:
                                                session.audio_queue_out.get_nowait()
                                            except asyncio.QueueEmpty:
                                                pass
                                            session.audio_queue_out.put_nowait(part.inline_data.data)

                            if server_content.turn_complete:
                                logger.debug(f"[{session.session_id}] Turno de IA completado")

                        tool_call = response.tool_call
                        if tool_call:
                            session.metadata["tool_running"] = True
                            try:
                                await self._handle_tool_call(session, gemini_session, tool_call)
                            finally:
                                session.metadata["tool_running"] = False

                except Exception as e:
                    if session.active:
                        logger.error(f"Error recibiendo de Gemini: {e}")
                        session.active = False
                        self._drain_queue(session.audio_queue_in)
                    break
        except asyncio.CancelledError:
            pass

    async def _handle_tool_call(self, session: CallSession, gemini_session, tool_call):
        function_responses = []

        for fc in tool_call.function_calls:
            logger.info(f"[{session.session_id}] Function Call: {fc.name}({fc.args})")

            args = dict(fc.args) if fc.args else {}

            if fc.name in ("transfer_call", "end_call", "lookup_inventory"):
                args["session"] = session

            result = await self._registry.execute(fc.name, args)

            if not isinstance(result, dict):
                result = {"result": str(result)}

            if isinstance(result.get("output"), str):
                flat_response = result
            else:
                flat_response = {"output": json.dumps(result, ensure_ascii=False)}

            fc_id = fc.id or f"{fc.name}_response"

            function_responses.append(
                types.FunctionResponse(
                    id=fc_id,
                    name=fc.name,
                    response=flat_response,
                )
            )
            logger.debug(f"[{session.session_id}] FunctionResponse id={fc_id} payload={len(flat_response['output'])}chars")

        await gemini_session.send(
            input=types.LiveClientToolResponse(
                function_responses=function_responses
            )
        )
        logger.info(f"[{session.session_id}] Tool response enviada para {len(function_responses)} funciones")
