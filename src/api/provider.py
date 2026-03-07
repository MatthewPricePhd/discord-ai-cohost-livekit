"""
Provider abstraction for TTS and STT services
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator


class TTSProvider(ABC):
    """Abstract base class for text-to-speech providers."""

    @abstractmethod
    async def generate_speech(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        """Generate speech audio as streaming PCM 24kHz 16-bit mono bytes."""
        ...

    @abstractmethod
    async def generate_speech_full(self, text: str, voice: str | None = None) -> bytes:
        """Generate speech audio as a single bytes object (PCM 24kHz 16-bit mono)."""
        ...


class STTProvider(ABC):
    """Abstract base class for speech-to-text providers."""

    @abstractmethod
    async def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio bytes to text."""
        ...


def get_tts_provider(settings) -> TTSProvider:
    """Factory function to create the configured TTS provider."""
    provider = settings.tts_provider.lower()

    if provider == "elevenlabs":
        from .elevenlabs_client import ElevenLabsTTS
        return ElevenLabsTTS(settings)
    elif provider == "openai":
        from .openai_provider import OpenAITTS
        return OpenAITTS(settings)
    else:
        raise ValueError(f"Unknown TTS provider: {provider}")


def get_stt_provider(settings) -> STTProvider:
    """Factory function to create the configured STT provider."""
    provider = settings.stt_provider.lower()

    if provider == "elevenlabs":
        from .elevenlabs_client import ElevenLabsSTT
        return ElevenLabsSTT(settings)
    elif provider == "openai":
        from .openai_provider import OpenAISTT
        return OpenAISTT(settings)
    else:
        raise ValueError(f"Unknown STT provider: {provider}")
