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

    def _resample_24k_to_16k(self, audio_24k: np.ndarray) -> np.ndarray:
        """Resample from 24kHz to 16kHz using linear interpolation"""
        num_samples_16k = int(len(audio_24k) * 16000 / 24000)
        indices = np.linspace(0, len(audio_24k) - 1, num_samples_16k)
        return np.interp(indices, np.arange(len(audio_24k)), audio_24k).astype(np.float32)

    def process_audio(self, audio_chunk: bytes) -> VADResult:
        """Process a chunk of 24kHz mono PCM16 audio through Silero VAD.

        Returns a VADResult with speech probability and is_speech flag.
        Also triggers on_speech_start/on_speech_end callbacks based on
        min duration thresholds.
        """
        if self._model is None:
            raise RuntimeError("VAD model not loaded. Use VADProcessor.load() to create an instance.")

        # Decode PCM16 to float32
        audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
        audio_f32 = audio_int16.astype(np.float32) / 32768.0

        # Resample 24kHz -> 16kHz
        audio_16k = self._resample_24k_to_16k(audio_f32)

        # Run Silero VAD (expects float32 tensor, 16kHz)
        tensor = torch.from_numpy(audio_16k)
        probability = float(self._model(tensor, 16000))

        is_speech = probability >= self.threshold

        # Track duration of audio processed (based on input at 24kHz)
        chunk_duration_ms = len(audio_int16) * 1000 / 24000
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
        if self._model is not None:
            self._model.reset_states()

    @property
    def is_speaking(self) -> bool:
        """Whether speech is currently detected (after min duration threshold)"""
        return self._is_speaking
