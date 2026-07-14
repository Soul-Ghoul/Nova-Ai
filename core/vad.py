import struct
from loguru import logger

try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False
    import math

class VoiceActivityDetector:
    def __init__(self, sample_rate: int = 16000, frame_duration_ms: int = 20, threshold_ratio: float = 2.5, hangover_ms: int = 250):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.threshold_ratio = threshold_ratio
        
        # Histéresis
        self.hangover_frames = int(hangover_ms / frame_duration_ms)
        self.hangover_counter = 0
        self.is_speech_state = False
        
        self.use_webrtc = WEBRTCVAD_AVAILABLE
        if self.use_webrtc:
            try:
                self.vad = webrtcvad.Vad(2)  # Agresividad moderada
                logger.debug("VAD de WebRTC inicializado de forma nativa en C.")
            except Exception as e:
                logger.warning(f"Error inicializando webrtcvad, cayendo a VAD matemático: {e}")
                self.use_webrtc = False
                
        if not self.use_webrtc:
            # Inicialización fallback matemático basado en energía RMS
            self.noise_floor = -1.0
            self.calibrated_frames = 0
            self.min_calibration_frames = 15  # Primeros 300ms

    def calculate_rms(self, pcm_data: bytes) -> float:
        count = len(pcm_data) // 2
        if count == 0:
            return 0.0
        samples = struct.unpack(f"<{count}h", pcm_data)
        sum_squares = sum(s * s for s in samples)
        import math
        return math.sqrt(sum_squares / count)

    def is_speech(self, pcm_data: bytes) -> bool:
        result = self._is_speech_internal(pcm_data)
        if result and not self.is_speech_state:
            self.is_speech_state = True
            logger.info("VAD: Voz detectada (Inicio)")
        elif not result and self.is_speech_state:
            self.is_speech_state = False
            logger.info("VAD: Silencio detectado (Fin)")
        return result

    def _is_speech_internal(self, pcm_data: bytes) -> bool:
        if self.use_webrtc:
            # webrtcvad requiere tramas de audio exactas de 10, 20 o 30 ms.
            # Para 16000Hz y 20ms = 640 bytes (320 muestras de 16 bits).
            frame_size = int(self.sample_rate * (self.frame_duration_ms / 1000.0) * 2)
            
            # Completar con ceros si el frame recibido es menor al tamaño esperado
            if len(pcm_data) < frame_size:
                pcm_data = pcm_data + b'\x00' * (frame_size - len(pcm_data))
            
            speech_detected = False
            # Procesar el buffer de audio en bloques exactos compatibles con webrtcvad
            for offset in range(0, len(pcm_data), frame_size):
                chunk = pcm_data[offset:offset + frame_size]
                if len(chunk) < frame_size:
                    break
                try:
                    if self.vad.is_speech(chunk, self.sample_rate):
                        speech_detected = True
                        break
                except Exception as e:
                    logger.warning(f"Error en webrtcvad.is_speech: {e}")
                    rms = self.calculate_rms(chunk)
                    if rms > 45.0:
                        speech_detected = True
                        break
            
            if speech_detected:
                self.hangover_counter = self.hangover_frames
                return True
            else:
                if self.hangover_counter > 0:
                    self.hangover_counter -= 1
                    return True
                return False
        else:
            # Fallback matemático basado en RMS
            rms = self.calculate_rms(pcm_data)
            
            if self.noise_floor < 0:
                self.noise_floor = rms if rms > 1.0 else 5.0
                return False

            if self.calibrated_frames < self.min_calibration_frames:
                self.noise_floor = self.noise_floor * 0.8 + rms * 0.2
                self.calibrated_frames += 1
                return False

            threshold = max(self.noise_floor * self.threshold_ratio, 15.0)

            if rms > threshold:
                self.hangover_counter = self.hangover_frames
                if rms < self.noise_floor * 5.0:
                    self.noise_floor = self.noise_floor * 0.999 + rms * 0.001
                return True
            else:
                self.noise_floor = self.noise_floor * 0.98 + rms * 0.02
                
                if self.hangover_counter > 0:
                    self.hangover_counter -= 1
                    return True
                return False
