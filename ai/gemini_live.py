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

    def _build_config(self, prompt_name: str = "nova_default") -> types.LiveConnectConfig:
        system_prompt = self._prompt_loader.load(prompt_name)
        tools         = self._registry.load_schemas()

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(
                parts=[types.Part(text=system_prompt)]
            ),
            tools=tools,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
        )

    async def start_session(self, session: CallSession, prompt_name: str = "nova_default"):
        if not self._client:
            logger.error("No se puede iniciar sesión: GEMINI_API_KEY no configurada")
            return

        config = self._build_config(prompt_name)
        logger.info(f"Conectando sesión {session.session_id} a Gemini Live...")

        try:
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

                await asyncio.gather(send_task, receive_task)

        except asyncio.CancelledError:
            logger.info(f"Sesión Gemini {session.session_id} cancelada")
        except Exception as e:
            logger.error(f"Error en sesión Gemini {session.session_id}: {e}")
            raise
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

    async def _receive_loop(self, session: CallSession, gemini_session):
        try:
            while session.active:
                try:
                    async for response in gemini_session.receive():
                        if not session.active:
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
                                    if part.inline_data:
                                        await session.audio_queue_out.put(part.inline_data.data)

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
                    break
        except asyncio.CancelledError:
            pass

    async def _handle_tool_call(self, session: CallSession, gemini_session, tool_call):
        function_responses = []

        for fc in tool_call.function_calls:
            logger.info(f"[{session.session_id}] Function Call: {fc.name}({fc.args})")

            args = dict(fc.args) if fc.args else {}

            if fc.name in ("transfer_call", "end_call"):
                args["session"] = session

            result = await self._registry.execute(fc.name, args)

            if not isinstance(result, dict):
                result = {"result": str(result)}

            function_responses.append(
                types.FunctionResponse(
                    id=fc.id,
                    name=fc.name,
                    response=result
                )
            )

        await gemini_session.send(
            input=types.LiveClientToolResponse(
                function_responses=function_responses
            )
        )
        logger.info(f"[{session.session_id}] Tool response enviada para {len(function_responses)} funciones")
