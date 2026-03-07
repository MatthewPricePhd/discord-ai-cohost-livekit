"""
Voice channel management for Discord AI Co-Host Bot
"""
import asyncio
from typing import Optional, Dict, Any

import discord
from discord.ext import commands

from .audio_handler import AudioHandler
from ..config import get_logger, settings

logger = get_logger(__name__)


class VoiceManager:
    """Manages Discord voice channel connections and audio streaming"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.audio_handler = AudioHandler()
        self.voice_client: Optional[discord.VoiceClient] = None
        self.current_channel: Optional[discord.VoiceChannel] = None
        self.is_listening = False
        self.is_speaking = False
        self._connection_lock = asyncio.Lock()
        
    async def join_voice_channel(self, channel: discord.VoiceChannel) -> bool:
        """Join a Discord voice channel"""
        async with self._connection_lock:
            try:
                if self.voice_client and self.voice_client.is_connected():
                    if self.voice_client.channel.id == channel.id:
                        logger.info("Already connected to voice channel", 
                                   channel_id=channel.id, 
                                   channel_name=channel.name)
                        return True
                    else:
                        await self.leave_voice_channel()
                
                logger.info("Joining voice channel", 
                           channel_id=channel.id, 
                           channel_name=channel.name,
                           guild_name=channel.guild.name)
                
                self.voice_client = await channel.connect()
                self.current_channel = channel

                # Initialize VAD if not already loaded
                if self.audio_handler.vad is None:
                    self.audio_handler.initialize_vad()

                # Set up audio capture
                sink = self.audio_handler.create_audio_sink()
                self.voice_client.listen(sink)
                
                logger.info("Successfully joined voice channel",
                           channel_id=channel.id,
                           channel_name=channel.name)
                
                return True
                
            except Exception as e:
                logger.error("Failed to join voice channel",
                           error=str(e),
                           channel_id=channel.id,
                           channel_name=channel.name)
                return False
    
    async def leave_voice_channel(self) -> None:
        """Leave the current voice channel"""
        async with self._connection_lock:
            if self.voice_client:
                try:
                    logger.info("Leaving voice channel",
                               channel_id=self.current_channel.id if self.current_channel else None)
                    
                    await self.stop_listening()
                    await self.stop_speaking()
                    
                    await self.voice_client.disconnect()
                    self.voice_client = None
                    self.current_channel = None
                    
                    logger.info("Successfully left voice channel")
                    
                except Exception as e:
                    logger.error("Error leaving voice channel", error=str(e))
    
    async def start_listening(self) -> None:
        """Start listening to voice channel audio"""
        if not self.voice_client or not self.voice_client.is_connected():
            logger.warning("Cannot start listening: not connected to voice channel")
            return
        
        if self.is_listening:
            logger.debug("Already listening")
            return
        
        try:
            await self.audio_handler.start_recording()
            self.is_listening = True
            
            logger.info("Started listening to voice channel",
                       channel_id=self.current_channel.id if self.current_channel else None)
            
        except Exception as e:
            logger.error("Failed to start listening", error=str(e))
    
    async def stop_listening(self) -> None:
        """Stop listening to voice channel audio"""
        if not self.is_listening:
            return
        
        try:
            await self.audio_handler.stop_recording()
            self.is_listening = False
            
            logger.info("Stopped listening to voice channel")
            
        except Exception as e:
            logger.error("Failed to stop listening", error=str(e))
    
    async def start_speaking(self) -> None:
        """Start speaking in voice channel"""
        if not self.voice_client or not self.voice_client.is_connected():
            logger.warning("Cannot start speaking: not connected to voice channel")
            return
        
        if self.is_speaking:
            logger.debug("Already speaking")
            return
        
        try:
            # Create audio source and start playing
            audio_source = self.audio_handler.create_audio_source()
            
            # Start playing the audio source
            if not self.voice_client.is_playing():
                self.voice_client.play(audio_source)
            
            await self.audio_handler.start_playback()
            self.is_speaking = True
            
            logger.info("Started speaking in voice channel",
                       channel_id=self.current_channel.id if self.current_channel else None)
            
        except Exception as e:
            logger.error("Failed to start speaking", error=str(e))
    
    async def stop_speaking(self) -> None:
        """Stop speaking in voice channel"""
        if not self.is_speaking:
            return
        
        try:
            await self.audio_handler.stop_playback()
            
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.stop()
            
            self.is_speaking = False
            
            logger.info("Stopped speaking in voice channel")
            
        except Exception as e:
            logger.error("Failed to stop speaking", error=str(e))
    
    async def send_audio(self, audio_data: bytes) -> None:
        """Send AI-generated audio to the voice channel"""
        if not self.is_speaking:
            logger.warning("Cannot send audio: not currently speaking")
            return
        
        try:
            await self.audio_handler.send_audio(audio_data)
        except Exception as e:
            logger.error("Failed to send audio", error=str(e))
    
    async def get_audio_stream(self):
        """Get stream of incoming audio from voice channel"""
        if not self.is_listening:
            logger.warning("Cannot get audio stream: not currently listening")
            return
        
        async for audio_data in self.audio_handler.get_audio_stream():
            yield audio_data
    
    def set_audio_callback(self, callback) -> None:
        """Set callback function for incoming audio"""
        self.audio_handler.set_audio_callback(callback)
    
    @property
    def connection_status(self) -> Dict[str, Any]:
        """Get current connection status"""
        return {
            "connected": self.voice_client is not None and self.voice_client.is_connected(),
            "channel_id": self.current_channel.id if self.current_channel else None,
            "channel_name": self.current_channel.name if self.current_channel else None,
            "guild_name": self.current_channel.guild.name if self.current_channel else None,
            "is_listening": self.is_listening,
            "is_speaking": self.is_speaking,
            "latency": self.voice_client.latency if self.voice_client else None
        }
    
    async def cleanup(self) -> None:
        """Clean up resources"""
        await self.leave_voice_channel()
        logger.info("Voice manager cleanup completed")