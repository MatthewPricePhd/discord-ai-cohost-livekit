"""
OpenAI TTS and STT provider wrappers for AI Co-Host Bot
"""
from typing import AsyncIterator

from openai import AsyncOpenAI

from ..config import get_logger
from .provider import TTSProvider, STTProvider

logger = get_logger(__name__)


class OpenAITTS(TTSProvider):
    """OpenAI text-to-speech provider."""

    def __init__(self, settings):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.default_voice = "alloy"

    async def generate_speech(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        """Generate streaming speech audio as PCM bytes."""
        if not text.strip():
            return

        try:
            response = await self.client.audio.speech.create(
                model="tts-1",
                voice=voice or self.default_voice,
                input=text,
                response_format="pcm",
            )

            yield response.content

        except Exception as e:
            logger.error("OpenAI TTS error", error=str(e))
            raise

    async def generate_speech_full(self, text: str, voice: str | None = None) -> bytes:
        """Generate speech audio as a single bytes object."""
        if not text.strip():
            return b""

        try:
            response = await self.client.audio.speech.create(
                model="tts-1",
                voice=voice or self.default_voice,
                input=text,
                response_format="pcm",
            )

            return response.content

        except Exception as e:
            logger.error("OpenAI TTS error", error=str(e))
            return b""


class OpenAISTT(STTProvider):
    """OpenAI speech-to-text provider using Whisper."""

    def __init__(self, settings):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio bytes to text using Whisper."""
        if not audio_data:
            return ""

        try:
            response = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.wav", audio_data, "audio/wav"),
                response_format="text",
            )

            transcript = response.strip()

            logger.debug(
                "OpenAI STT transcription complete",
                transcript_length=len(transcript),
            )

            return transcript

        except Exception as e:
            logger.error("OpenAI STT error", error=str(e))
            return ""
