"""
Audio processing and streaming handler for Discord AI Co-Host Bot
"""
import asyncio
import io
import wave
from typing import AsyncGenerator, Optional, Callable

import numpy as np
import soundfile as sf
from discord import AudioSource, PCMVolumeTransformer

from ..config import get_logger, settings

logger = get_logger(__name__)


class AudioBuffer:
    """Thread-safe audio buffer for streaming audio data"""
    
    def __init__(self, sample_rate: int = 24000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self._buffer = io.BytesIO()
        self._lock = asyncio.Lock()
    
    async def write(self, audio_data: bytes) -> None:
        """Write audio data to buffer"""
        async with self._lock:
            self._buffer.write(audio_data)
    
    async def read(self, size: int = -1) -> bytes:
        """Read audio data from buffer"""
        async with self._lock:
            current_pos = self._buffer.tell()
            self._buffer.seek(0)
            data = self._buffer.read(size)
            
            # Keep remaining data and reset position
            remaining = self._buffer.read()
            self._buffer.seek(0)
            self._buffer.truncate(0)
            self._buffer.write(remaining)
            
            return data
    
    async def clear(self) -> None:
        """Clear the buffer"""
        async with self._lock:
            self._buffer.seek(0)
            self._buffer.truncate(0)


class DiscordAudioSink:
    """Custom audio sink to capture audio from Discord voice channel"""
    
    def __init__(self, audio_callback: Optional[Callable[[bytes, int], None]] = None):
        self.audio_callback = audio_callback
        self.buffer = AudioBuffer()
        self._recording = False
        
    def cleanup(self) -> None:
        """Clean up resources"""
        pass
    
    def write(self, data, user) -> None:
        """Called when audio data is received from Discord"""
        if not self._recording:
            return
            
        if data and len(data) > 0:
            # Convert Discord's audio format to our target format
            try:
                # Discord sends PCM 48kHz stereo, convert to 24kHz mono
                audio_array = np.frombuffer(data, dtype=np.int16)
                
                # If stereo, convert to mono by averaging channels
                if len(audio_array) % 2 == 0:
                    stereo_array = audio_array.reshape(-1, 2)
                    mono_array = np.mean(stereo_array, axis=1, dtype=np.int16)
                else:
                    mono_array = audio_array
                
                # Resample from 48kHz to 24kHz (simple downsampling by 2)
                downsampled = mono_array[::2]
                
                # Convert back to bytes
                processed_data = downsampled.tobytes()
                
                # Add to buffer
                asyncio.create_task(self.buffer.write(processed_data))
                
                # Call callback if provided
                if self.audio_callback:
                    self.audio_callback(processed_data, user.id if user else 0)
                    
            except Exception as e:
                logger.error("Error processing audio data", error=str(e), user_id=user.id if user else None)
    
    def start_recording(self) -> None:
        """Start recording audio"""
        self._recording = True
        logger.info("Started audio recording")
    
    def stop_recording(self) -> None:
        """Stop recording audio"""
        self._recording = False
        logger.info("Stopped audio recording")
    
    async def get_audio_stream(self) -> AsyncGenerator[bytes, None]:
        """Get continuous stream of audio data"""
        while self._recording:
            data = await self.buffer.read(4800)  # ~100ms of 24kHz mono audio
            if data:
                yield data
            else:
                await asyncio.sleep(0.01)  # Small delay if no data


class DiscordAudioSource(AudioSource):
    """Custom audio source to send AI-generated audio to Discord"""
    
    def __init__(self):
        self.buffer = AudioBuffer()
        self._playing = False
        
    def read(self) -> bytes:
        """Read audio data for Discord (blocking call)"""
        if not self._playing:
            return b'\x00' * 3840  # Silence for 20ms at 48kHz stereo
        
        try:
            # This is a blocking call, but Discord expects it
            # In real implementation, we'd need a sync wrapper
            loop = asyncio.get_event_loop()
            data = loop.run_until_complete(self.buffer.read(3840))
            
            if data:
                # Convert from 24kHz mono to 48kHz stereo for Discord
                audio_array = np.frombuffer(data, dtype=np.int16)
                
                # Upsample by duplicating samples
                upsampled = np.repeat(audio_array, 2)
                
                # Convert mono to stereo by duplicating channel
                stereo = np.column_stack((upsampled, upsampled)).flatten()
                
                # Ensure we have exactly the right amount of data
                if len(stereo) < 3840 // 2:  # 3840 bytes = 1920 samples
                    padding = np.zeros(3840 // 2 - len(stereo), dtype=np.int16)
                    stereo = np.concatenate([stereo, padding])
                elif len(stereo) > 3840 // 2:
                    stereo = stereo[:3840 // 2]
                
                return stereo.tobytes()
            else:
                return b'\x00' * 3840  # Silence if no data
                
        except Exception as e:
            logger.error("Error reading audio data", error=str(e))
            return b'\x00' * 3840
    
    def is_opus(self) -> bool:
        """Return False as we're providing raw PCM data"""
        return False
    
    async def add_audio(self, audio_data: bytes) -> None:
        """Add audio data to be played"""
        await self.buffer.write(audio_data)
    
    def start_playing(self) -> None:
        """Start audio playback"""
        self._playing = True
        logger.info("Started audio playback")
    
    def stop_playing(self) -> None:
        """Stop audio playback"""
        self._playing = False
        asyncio.create_task(self.buffer.clear())
        logger.info("Stopped audio playback")


class AudioHandler:
    """Main audio handler for Discord AI Co-Host Bot"""
    
    def __init__(self):
        self.sink: Optional[DiscordAudioSink] = None
        self.source: Optional[DiscordAudioSource] = None
        self.audio_callback: Optional[Callable[[bytes, int], None]] = None
        
    def set_audio_callback(self, callback: Callable[[bytes, int], None]) -> None:
        """Set callback for incoming audio data"""
        self.audio_callback = callback
        if self.sink:
            self.sink.audio_callback = callback
    
    def create_audio_sink(self) -> DiscordAudioSink:
        """Create audio sink for capturing Discord audio"""
        self.sink = DiscordAudioSink(self.audio_callback)
        logger.info("Created Discord audio sink")
        return self.sink
    
    def create_audio_source(self) -> PCMVolumeTransformer:
        """Create audio source for sending AI audio to Discord"""
        self.source = DiscordAudioSource()
        # Wrap with volume transformer for better control
        volume_source = PCMVolumeTransformer(self.source, volume=1.0)
        logger.info("Created Discord audio source")
        return volume_source
    
    async def start_recording(self) -> None:
        """Start recording audio from Discord"""
        if self.sink:
            self.sink.start_recording()
    
    async def stop_recording(self) -> None:
        """Stop recording audio from Discord"""
        if self.sink:
            self.sink.stop_recording()
    
    async def start_playback(self) -> None:
        """Start playing AI-generated audio"""
        if self.source:
            self.source.start_playing()
    
    async def stop_playback(self) -> None:
        """Stop playing AI-generated audio"""
        if self.source:
            self.source.stop_playing()
    
    async def send_audio(self, audio_data: bytes) -> None:
        """Send AI-generated audio to Discord"""
        if self.source:
            await self.source.add_audio(audio_data)
    
    async def get_audio_stream(self) -> AsyncGenerator[bytes, None]:
        """Get stream of incoming audio data"""
        if self.sink:
            async for data in self.sink.get_audio_stream():
                yield data
        else:
            # Return empty generator if no sink
            return
            yield  # Make this a generator