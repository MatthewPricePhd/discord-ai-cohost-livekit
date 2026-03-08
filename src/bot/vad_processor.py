"""
Silero VAD processor for voice activity detection
"""
import asyncio
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import torch

from ..config import get_logger

logger = get_logger(__name__)


@dataclass
class VADResult:
    """Result from VAD processing"""
    speech_probability: float
    is_speech: bool


class VADProcessor:
    """Wraps Silero VAD for speech detection on 24kHz mono PCM16 audio"""

    def __init__(
        self,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 300,
    ):
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms

        self._model: Optional[torch.jit.ScriptModule] = None
        self._is_speaking = False
        self._speech_start_ms = 0
        self._silence_start_ms = 0
        self._elapsed_ms = 0

        self.on_speech_start: Optional[Callable[[], None]] = None
        self.on_speech_end: Optional[Callable[[], None]] = None

    @classmethod
    def load(cls, **kwargs) -> "VADProcessor":
        """Create and initialize a VADProcessor with the Silero model loaded"""
        from silero_vad import load_silero_vad

        processor = cls(**kwargs)
        processor._model = load_silero_vad()
        logger.info("Silero VAD model loaded")
        return processor

    def _resample(self, audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
        """Resample audio using linear interpolation"""
        if from_rate == to_rate:
            return audio
        num_samples = int(len(audio) * to_rate / from_rate)
        indices = np.linspace(0, len(audio) - 1, num_samples)
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

    def _stereo_to_mono(self, audio_int16: np.ndarray) -> np.ndarray:
        """Convert interleaved stereo int16 to mono float32"""
        # Reshape to (N, 2) and average channels
        stereo = audio_int16.reshape(-1, 2).astype(np.float32)
        return (stereo[:, 0] + stereo[:, 1]) / (2.0 * 32768.0)

    def process_audio(self, audio_chunk: bytes, sample_rate: int = 24000, channels: int = 1) -> VADResult:
        """Process a chunk of PCM16 audio through Silero VAD.

        Accepts any sample rate and channel count. Converts to 16kHz mono
        and chunks into 512-sample segments for Silero.

        Returns a VADResult with speech probability and is_speech flag.
        """
        if self._model is None:
            raise RuntimeError("VAD model not loaded. Use VADProcessor.load() to create an instance.")

        # Decode PCM16 to float32 mono
        audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)

        if channels == 2:
            audio_f32 = self._stereo_to_mono(audio_int16)
        else:
            audio_f32 = audio_int16.astype(np.float32) / 32768.0

        # Resample to 16kHz
        audio_16k = self._resample(audio_f32, sample_rate, 16000)

        # Silero VAD requires exactly 512 samples at 16kHz.
        # Buffer and process in 512-sample chunks, return result from last chunk.
        if not hasattr(self, '_vad_buffer'):
            self._vad_buffer = np.array([], dtype=np.float32)

        self._vad_buffer = np.concatenate([self._vad_buffer, audio_16k])

        probability = 0.0
        is_speech = False
        processed_any = False

        while len(self._vad_buffer) >= 512:
            chunk = self._vad_buffer[:512]
            self._vad_buffer = self._vad_buffer[512:]
            tensor = torch.from_numpy(chunk)
            probability = float(self._model(tensor, 16000))
            is_speech = probability >= self.threshold
            processed_any = True

        if not processed_any:
            return VADResult(speech_probability=0.0, is_speech=False)

        # Track duration of audio processed
        chunk_duration_ms = (len(audio_int16) / channels) * 1000 / sample_rate
        self._elapsed_ms += chunk_duration_ms

        # State machine for speech start/end with duration thresholds
        if is_speech:
            self._silence_start_ms = 0
            if not self._is_speaking:
                if self._speech_start_ms == 0:
                    self._speech_start_ms = self._elapsed_ms
                elif (self._elapsed_ms - self._speech_start_ms) >= self.min_speech_duration_ms:
                    self._is_speaking = True
                    if self.on_speech_start:
                        self.on_speech_start()
        else:
            self._speech_start_ms = 0
            if self._is_speaking:
                if self._silence_start_ms == 0:
                    self._silence_start_ms = self._elapsed_ms
                elif (self._elapsed_ms - self._silence_start_ms) >= self.min_silence_duration_ms:
                    self._is_speaking = False
                    if self.on_speech_end:
                        self.on_speech_end()

        return VADResult(speech_probability=probability, is_speech=is_speech)

    def reset(self) -> None:
        """Reset the VAD state"""
        self._is_speaking = False
        self._speech_start_ms = 0
        self._silence_start_ms = 0
        self._elapsed_ms = 0
        self._vad_buffer = np.array([], dtype=np.float32)
        if self._model is not None:
            self._model.reset_states()

    @property
    def is_speaking(self) -> bool:
        """Whether speech is currently detected (after min duration threshold)"""
        return self._is_speaking
