import json
import asyncio
from loguru import logger
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from django_project import state
from core.audio_processor import AudioProcessor
from core.vad import VoiceActivityDetector

router = APIRouter()


@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()

    agent = websocket.query_params.get("agent", "nova_default")
    user_id_raw = websocket.query_params.get("user_id")
    user_id = None
    if user_id_raw:
        try:
            user_id = int(user_id_raw)
        except ValueError:
            pass

    session = await state.session_manager.create_session(source="web", user_id=user_id)
    logger.info(f"WebSocket de voz conectado: {session.session_id} [user_id={user_id}]")

    vad = VoiceActivityDetector()

    gemini_task = asyncio.create_task(
        state.gemini_client.start_session(session, prompt_name=agent, user_id=user_id)
    )

    async def send_audio_to_browser():
        try:
            while session.active:
                try:
                    audio_data = await asyncio.wait_for(
                        session.audio_queue_out.get(), timeout=0.5
                    )
                    if audio_data is None:
                        break
                    pcm_16khz = AudioProcessor.gemini_to_browser(audio_data)
                    await websocket.send_bytes(pcm_16khz)
                except asyncio.TimeoutError:
                    continue
        except Exception as e:
            if session.active:
                logger.debug(f"Send audio to browser cerrado: {e}")

    send_task = asyncio.create_task(send_audio_to_browser())

    try:
        while True:
            message = await websocket.receive()
            msg_type = message.get("type", "")

            if msg_type == "websocket.disconnect":
                break

            if "bytes" in message and message["bytes"] is not None:
                if not session.active:
                    continue
                pcm_16khz = AudioProcessor.browser_to_gemini(message["bytes"])
                vad.is_speech(pcm_16khz)
                try:
                    session.audio_queue_in.put_nowait(pcm_16khz)
                except asyncio.QueueFull:
                    try:
                        session.audio_queue_in.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    session.audio_queue_in.put_nowait(pcm_16khz)

            elif "text" in message and message["text"] is not None:
                if not session.active:
                    continue
                try:
                    msg = json.loads(message["text"])
                    if msg.get("type") == "end":
                        break
                except Exception as e:
                    logger.error(f"Error procesando mensaje de texto en ws: {e}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WebSocket cerrado inesperadamente: {e}")
    finally:
        logger.info(f"WebSocket desconectado: {session.session_id}")
        session.active = False
        await session.audio_queue_in.put(None)

        if not gemini_task.done():
            gemini_task.cancel()
            try:
                await gemini_task
            except (asyncio.CancelledError, Exception):
                pass

        if not send_task.done():
            send_task.cancel()
            try:
                await send_task
            except (asyncio.CancelledError, Exception):
                pass

        ended = await state.session_manager.end_session(session.session_id, "websocket_disconnect")
        if ended:
            try:
                await state.db.log_call(
                    session_id=ended.session_id,
                    caller_id=ended.caller_id or "web",
                    source=ended.source,
                    duration=round(ended.duration, 2),
                    actions=str(ended.metadata.get("actions", [])),
                    transcript="",
                    tokens_input=ended.tokens_input,
                    tokens_output=ended.tokens_output,
                )
            except Exception as _log_err:
                logger.warning(f"No se pudo registrar log de llamada: {_log_err}")

        logger.info(f"Sesión WebSocket limpia: {session.session_id}")
