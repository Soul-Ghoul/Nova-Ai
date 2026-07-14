import asyncio
import struct
import uuid
from loguru import logger
from core.session import SessionManager, CallSession
from core.audio_processor import AudioProcessor
from core.vad import VoiceActivityDetector
from core.events import event_bus
from config.settings import get_settings

# AudioSocket Protocol:
# Header: 1 byte type + 2 bytes length (big-endian) + N bytes payload
# Types: 0x01 = UUID, 0x10 = Audio (slin16), 0x00 = Hangup/Error
MSG_TYPE_UUID = 0x01
MSG_TYPE_AUDIO = 0x10
MSG_TYPE_HANGUP = 0x00
MSG_TYPE_ERROR = 0xFF


class AudioSocketServer:
    def __init__(self, session_manager: SessionManager, gemini_client=None):
        self._session_manager = session_manager
        self._gemini_client = gemini_client
        self._server: asyncio.AbstractServer | None = None
        settings = get_settings()
        self.host = settings.audiosocket_host
        self.port = settings.audiosocket_port
        self.telephony_user_id = settings.telephony_user_id

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle_connection, self.host, self.port
        )
        logger.info(f"AudioSocket Server escuchando en {self.host}:{self.port}")

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("AudioSocket Server detenido")

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        logger.info(f"AudioSocket: nueva conexión desde {peer}")
        session: CallSession | None = None
        gemini_task: asyncio.Task | None = None

        try:
            session = await self._session_manager.create_session(
                source="asterisk",
                call_id=str(uuid.uuid4()),
                user_id=self.telephony_user_id
            )

            vad = VoiceActivityDetector()

            send_task = asyncio.create_task(
                self._send_audio_to_asterisk(session, writer)
            )

            await event_bus.emit("asterisk_call_started", session=session)

            # Arrancar Gemini para esta llamada
            if self._gemini_client:
                gemini_task = asyncio.create_task(
                    self._gemini_client.start_session(session, user_id=self.telephony_user_id)
                )
                logger.info(
                    f"Gemini iniciado para llamada telefónica {session.session_id} "
                    f"(user_id={self.telephony_user_id})"
                )
            else:
                logger.error("AudioSocket sin gemini_client: la llamada no tendrá IA.")

            while session.active:
                header = await reader.readexactly(3)
                msg_type = header[0]
                msg_len = struct.unpack(">H", header[1:3])[0]

                if msg_len > 0:
                    payload = await reader.readexactly(msg_len)
                else:
                    payload = b""

                if msg_type == MSG_TYPE_UUID:
                    call_uuid = payload.decode("utf-8", errors="ignore").strip()
                    session.call_id = call_uuid
                    logger.info(f"AudioSocket UUID recibido: {call_uuid}")

                elif msg_type == MSG_TYPE_AUDIO:
                    # Fijar la frecuencia de muestreo de Asterisk al recibir el primer paquete de audio (el códec de llamada no cambia a mitad de llamada)
                    if "asterisk_rate" not in session.metadata:
                        if len(payload) >= 640:
                            session.metadata["asterisk_rate"] = 16000
                            logger.info(f"[{session.session_id}] Tasa de llamada fijada a 16kHz (slin16) - primer payload de {len(payload)} bytes")
                        else:
                            session.metadata["asterisk_rate"] = 8000
                            logger.info(f"[{session.session_id}] Tasa de llamada fijada a 8kHz (slin8) - primer payload de {len(payload)} bytes")

                    # Procesar el audio según la tasa fijada
                    rate = session.metadata["asterisk_rate"]
                    if rate == 16000:
                        pcm_16khz = payload
                    else:
                        pcm_16khz = AudioProcessor.asterisk_to_gemini(payload)
                    
                    # Ejecutar VAD para logs de diagnóstico en consola
                    vad.is_speech(pcm_16khz)
                    
                    # Enviar el audio de forma continua para que Gemini escuche la frase completa sin cortes
                    try:
                        session.audio_queue_in.put_nowait(pcm_16khz)
                    except asyncio.QueueFull:
                        try:
                            session.audio_queue_in.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        session.audio_queue_in.put_nowait(pcm_16khz)

                elif msg_type == MSG_TYPE_HANGUP:
                    logger.info(f"AudioSocket: colgado recibido para {session.session_id}")
                    break

                elif msg_type == MSG_TYPE_ERROR:
                    logger.error(f"AudioSocket: error recibido para {session.session_id}")
                    break

        except asyncio.IncompleteReadError:
            logger.info(f"AudioSocket: conexión cerrada por Asterisk")
        except Exception as e:
            logger.error(f"AudioSocket error: {e}")
        finally:
            if session:
                session.active = False
                await session.audio_queue_in.put(None)
                if gemini_task and not gemini_task.done():
                    gemini_task.cancel()
                    try:
                        await gemini_task
                    except (asyncio.CancelledError, Exception):
                        pass
                await self._session_manager.end_session(session.session_id, "asterisk_disconnect")
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            logger.info(f"AudioSocket: conexión cerrada para {peer}")

    async def _send_audio_to_asterisk(self, session: CallSession, writer: asyncio.StreamWriter):
        try:
            start_time = None
            sent_samples = 0

            while session.active:
                try:
                    audio_data = await asyncio.wait_for(
                        session.audio_queue_out.get(), timeout=0.5
                    )
                    if audio_data is None:
                        break

                    session.metadata["ia_speaking"] = True
                    rate = session.metadata.get("asterisk_rate", 8000)
                    if rate == 16000:
                        resampled = AudioProcessor.gemini_to_browser(audio_data)  # 24kHz -> 16kHz
                        chunk_size = 640  # 20ms a 16kHz
                        samples_per_chunk = 320
                    else:
                        resampled = AudioProcessor.gemini_to_asterisk(audio_data)  # 24kHz -> 8kHz
                        chunk_size = 320  # 20ms a 8kHz
                        samples_per_chunk = 160

                    if start_time is None:
                        start_time = asyncio.get_event_loop().time()

                    for i in range(0, len(resampled), chunk_size):
                        chunk = resampled[i:i + chunk_size]
                        if len(chunk) == 0:
                            break
                        header = struct.pack(">BH", MSG_TYPE_AUDIO, len(chunk))
                        writer.write(header + chunk)
                        await writer.drain()
                        
                        sent_samples += samples_per_chunk
                        
                        # Compensación de deriva de tiempo real con límite de velocidad de ráfaga
                        expected_time = sent_samples / rate
                        actual_time = asyncio.get_event_loop().time() - start_time
                        sleep_time = expected_time - actual_time
                        
                        # Limitar la velocidad máxima de vaciado: no dormir menos de 16ms por bloque de 20ms
                        if sleep_time < 0.016:
                            sleep_time = 0.016
                            # Corregir la referencia de tiempo (deriva) para que los siguientes bloques mantengan el ritmo constante
                            start_time = asyncio.get_event_loop().time() - expected_time + 0.016
                            
                        await asyncio.sleep(sleep_time)

                except asyncio.TimeoutError:
                    session.metadata["ia_speaking"] = False
                    start_time = None  # Resetear el cronómetro al haber silencio
                    sent_samples = 0
                    
                    # Enviar silencio para mantener viva la conexión con Asterisk
                    rate = session.metadata.get("asterisk_rate", 8000)
                    chunk_size = 640 if rate == 16000 else 320
                    silence = b'\x00' * chunk_size
                    header = struct.pack(">BH", MSG_TYPE_AUDIO, len(silence))
                    try:
                        writer.write(header + silence)
                        await writer.drain()
                    except Exception:
                        break
                    continue
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if session.active:
                logger.error(f"Error enviando audio a Asterisk: {e}")
