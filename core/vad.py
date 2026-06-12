import math
import struct
from loguru import logger

class VoiceActivityDetector:
    def __init__(self, sample_rate: int = 16000, frame_duration_ms: int = 20, threshold_ratio: float = 2.0, hangover_ms: int = 250):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.threshold_ratio = threshold_ratio
        
        # Histéresis
        self.hangover_frames = int(hangover_ms / frame_duration_ms)
        self.hangover_counter = 0
        
        # Autocalibración dinámica
        self.noise_floor = -1.0
        self.calibrated_frames = 0
        self.min_calibration_frames = 15  # primeros 300ms

    def calculate_rms(self, pcm_data: bytes) -> float:
        count = len(pcm_data) // 2
        if count == 0:
            return 0.0
        samples = struct.unpack(f"<{count}h", pcm_data)
        sum_squares = sum(s * s for s in samples)
        return math.sqrt(sum_squares / count)

    def is_speech(self, pcm_data: bytes) -> bool:
        rms = self.calculate_rms(pcm_data)
        
        if self.noise_floor < 0:
            self.noise_floor = rms if rms > 1.0 else 5.0
            return False

        if self.calibrated_frames < self.min_calibration_frames:
            self.noise_floor = self.noise_floor * 0.8 + rms * 0.2
            self.calibrated_frames += 1
            return False

        threshold = max(self.noise_floor * self.threshold_ratio, 45.0)

        if rms > threshold:
            self.hangover_counter = self.hangover_frames
            # Si el RMS es moderadamente mayor al ruido floor, adaptamos despacio
            if rms < self.noise_floor * 5.0:
                self.noise_floor = self.noise_floor * 0.999 + rms * 0.001
            return True
        else:
            # Es silencio, adaptamos el ruido floor de forma dinámica
            self.noise_floor = self.noise_floor * 0.98 + rms * 0.02
            
            if self.hangover_counter > 0:
                self.hangover_counter -= 1
                return True
            return False
