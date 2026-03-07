"""
ElevenLabs TTS and STT client for AI Co-Host Bot
"""
import io
from typing import AsyncIterator, List, Optional

from elevenlabs import AsyncElevenLabs

from ..config import get_logger
from .provider import TTSProvider, STTProvider

logger = get_logger(__name__)


class ElevenLabsTTS(TTSProvider):
    """ElevenLabs text-to-speech provider with streaming support."""

    def __init__(self, settings):
        self.client = AsyncElevenLabs(api_key=settings.elevenlabs_api_key)
        self.voice_id = settings.elevenlabs_voice_id
        self.model = settings.elevenlabs_model

    async def generate_speech(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        """Generate streaming speech audio as PCM 24kHz 16-bit mono bytes."""
        if not text.strip():
            return

        voice_id = voice or self.voice_id
        if not voice_id:
            raise ValueError("No voice_id configured for ElevenLabs TTS")

        try:
            response = await self.client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id=self.model,
                output_format="pcm_24000",
            )

            async for chunk in response:
                yield chunk

        except Exception as e:
            logger.error("ElevenLabs TTS streaming error", error=str(e))
            raise

    async def generate_speech_full(self, text: str, voice: str | None = None) -> bytes:
        """Generate speech audio as a single bytes object."""
        chunks: list[bytes] = []
        async for chunk in self.generate_speech(text, voice):
            chunks.append(chunk)
        return b"".join(chunks)


class ElevenLabsSTT(STTProvider):
    """ElevenLabs speech-to-text provider using Scribe v2."""

    def __init__(self, settings, keyterms: Optional[List[str]] = None):
        self.client = AsyncElevenLabs(api_key=settings.elevenlabs_api_key)
        self.keyterms = keyterms or []

    async def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio bytes to text using ElevenLabs Scribe v2."""
        if not audio_data:
            return ""

        try:
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.wav"

            kwargs = {
                "file": audio_file,
                "model_id": "scribe_v1",
            }

            if self.keyterms:
                kwargs["keyterms"] = self.keyterms

            response = await self.client.speech_to_text.convert(**kwargs)

            transcript = response.text.strip()

            logger.debug(
                "ElevenLabs STT transcription complete",
                transcript_length=len(transcript),
            )

            return transcript

        except Exception as e:
            logger.error("ElevenLabs STT error", error=str(e))
            return ""
