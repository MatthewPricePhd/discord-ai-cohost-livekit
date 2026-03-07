"""
Discord bot client for AI Co-Host Bot
"""
import asyncio
from typing import Optional, Callable, Dict, Any

import sys
import platform

import disnake
from disnake.ext import commands

from .voice_manager import VoiceManager
from ..config import get_logger, settings

logger = get_logger(__name__)

# Load opus library for voice support
if not disnake.opus.is_loaded():
    if platform.system() == "Darwin":
        _opus_paths = ["/opt/homebrew/lib/libopus.dylib", "/usr/local/lib/libopus.dylib"]
    elif platform.system() == "Linux":
        _opus_paths = ["libopus.so.0", "libopus.so"]
    else:
        _opus_paths = ["opus"]
    for _path in _opus_paths:
        try:
            disnake.opus.load_opus(_path)
            logger.info("Loaded opus library", path=_path)
            break
        except OSError:
            continue
    if not disnake.opus.is_loaded():
        logger.warning("Could not load opus library — voice will not work")


class DiscordClient(commands.Bot):
    """Main Discord bot client for AI Co-Host functionality"""
    
    def __init__(self):
        intents = disnake.Intents.default()
        intents.voice_states = True
        intents.guilds = True
        # intents.message_content = True  # Commented out to avoid privileged intent requirement
        
        super().__init__(
            command_prefix='!ai',
            intents=intents,
            description='AI Co-Host Bot for Podcast Recording'
        )
        
        self.voice_manager = VoiceManager(self)
        self.audio_callback: Optional[Callable[[bytes, int], None]] = None
        self.status_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._bot_ready = False
        
    async def setup_hook(self) -> None:
        """Setup hook called when bot is starting"""
        logger.info("Discord bot setup hook called")
        await self.add_cog(CoHostCommands(self))
    
    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info("Discord bot ready",
                   bot_user=str(self.user),
                   guild_count=len(self.guilds))
        
        # Set bot status
        await self.change_presence(
            activity=disnake.Activity(
                type=disnake.ActivityType.listening,
                name="for podcast hosts"
            ),
            status=disnake.Status.online
        )
        
        self._bot_ready = True
    
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates"""
        # Detect when the bot itself gets disconnected
        if member == self.user and before.channel and not after.channel:
            # Only treat as real disconnect if:
            # 1. voice_manager thinks it's connected
            # 2. connection lock isn't held (not mid-handshake)
            # 3. at least 10s have passed since connection (DAVE handshake grace period)
            import time
            seconds_since_connect = time.monotonic() - self.voice_manager._connected_at
            is_handshaking = self.voice_manager._connection_lock.locked()
            is_grace_period = seconds_since_connect < 10

            if self.voice_manager.current_channel and not is_handshaking and not is_grace_period:
                logger.warning("Bot was disconnected from voice channel",
                              channel=before.channel.name,
                              seconds_since_connect=round(seconds_since_connect, 1))
                self.voice_manager.is_listening = False
                self.voice_manager.is_speaking = False
                self.voice_manager.voice_client = None
                self.voice_manager.current_channel = None
            else:
                logger.debug("Ignoring voice state transition during handshake/grace period",
                            channel=before.channel.name,
                            is_handshaking=is_handshaking,
                            is_grace_period=is_grace_period)

        # Log voice channel changes for debugging
        if before.channel != after.channel:
            logger.debug("Voice state update",
                        member=str(member),
                        before_channel=before.channel.name if before.channel else None,
                        after_channel=after.channel.name if after.channel else None)
    
    async def on_error(self, event_method: str, *args, **kwargs):
        """Handle bot errors"""
        logger.error("Discord bot error",
                    event=event_method,
                    args=str(args),
                    kwargs=str(kwargs))
    
    def set_audio_callback(self, callback: Callable[[bytes, int], None]) -> None:
        """Set callback for incoming audio data"""
        self.audio_callback = callback
        self.voice_manager.set_audio_callback(callback)
    
    def set_status_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set callback for status updates"""
        self.status_callback = callback
    
    async def join_voice_channel(self, channel_id: int) -> bool:
        """Join a voice channel by ID"""
        try:
            channel = self.get_channel(channel_id)
            if not channel:
                # Channel not in cache, try fetching from API
                try:
                    channel = await self.fetch_channel(channel_id)
                except disnake.NotFound:
                    logger.error("Voice channel not found", channel_id=channel_id)
                    return False
            if not isinstance(channel, (disnake.VoiceChannel, disnake.StageChannel)):
                logger.error("Invalid voice channel", channel_id=channel_id)
                return False
            
            success = await self.voice_manager.join_voice_channel(channel)
            
            if self.status_callback:
                await self.status_callback(self.get_status())
            
            return success
            
        except Exception as e:
            logger.error("Error joining voice channel", error=str(e), channel_id=channel_id)
            return False
    
    async def leave_voice_channel(self) -> None:
        """Leave current voice channel"""
        await self.voice_manager.leave_voice_channel()
        
        if self.status_callback:
            await self.status_callback(self.get_status())
    
    async def start_listening(self) -> None:
        """Start listening to voice channel"""
        await self.voice_manager.start_listening()
        
        if self.status_callback:
            await self.status_callback(self.get_status())
    
    async def stop_listening(self) -> None:
        """Stop listening to voice channel"""
        await self.voice_manager.stop_listening()
        
        if self.status_callback:
            await self.status_callback(self.get_status())
    
    async def start_speaking(self) -> None:
        """Start speaking in voice channel"""
        await self.voice_manager.start_speaking()
        
        if self.status_callback:
            await self.status_callback(self.get_status())
    
    async def stop_speaking(self) -> None:
        """Stop speaking in voice channel"""
        await self.voice_manager.stop_speaking()
        
        if self.status_callback:
            await self.status_callback(self.get_status())
    
    async def send_audio(self, audio_data: bytes) -> None:
        """Send AI-generated audio to voice channel"""
        await self.voice_manager.send_audio(audio_data)
    
    async def get_audio_stream(self):
        """Get stream of incoming audio"""
        async for audio_data in self.voice_manager.get_audio_stream():
            yield audio_data
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        voice_status = self.voice_manager.connection_status
        
        return {
            "bot_ready": self._bot_ready,
            "bot_user": str(self.user) if self.user else None,
            "guild_count": len(self.guilds),
            "voice_connection": voice_status,
            "latency": round(self.latency * 1000, 2)  # Convert to ms
        }
    
    async def cleanup(self) -> None:
        """Clean up bot resources"""
        logger.info("Cleaning up Discord bot")
        await self.voice_manager.cleanup()
        await self.close()


class CoHostCommands(commands.Cog):
    """Command cog for AI Co-Host bot"""
    
    def __init__(self, bot: DiscordClient):
        self.bot = bot
    
    @commands.command(name='join')
    async def join_channel(self, ctx):
        """Join the user's voice channel"""
        if not ctx.author.voice:
            await ctx.send("You need to be in a voice channel for me to join!")
            return
        
        channel = ctx.author.voice.channel
        success = await self.bot.join_voice_channel(channel.id)
        
        if success:
            await ctx.send(f"Joined {channel.name}! I'm now listening in passive mode.")
            await self.bot.start_listening()
        else:
            await ctx.send("Failed to join the voice channel. Please try again.")
    
    @commands.command(name='leave')
    async def leave_channel(self, ctx):
        """Leave the current voice channel"""
        await self.bot.leave_voice_channel()
        await ctx.send("Left the voice channel. See you next time!")
    
    @commands.command(name='status')
    async def status(self, ctx):
        """Get bot status information"""
        status = self.bot.get_status()
        
        embed = disnake.Embed(
            title="AI Co-Host Status",
            color=disnake.Color.blue()
        )
        
        embed.add_field(
            name="Bot Status",
            value=f"Ready: {status['bot_ready']}\nLatency: {status['latency']}ms",
            inline=True
        )
        
        voice_conn = status['voice_connection']
        embed.add_field(
            name="Voice Connection",
            value=f"Connected: {voice_conn['connected']}\nChannel: {voice_conn['channel_name'] or 'None'}\nListening: {voice_conn['is_listening']}\nSpeaking: {voice_conn['is_speaking']}",
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='commands')
    async def help_command(self, ctx):
        """Show available commands"""
        embed = disnake.Embed(
            title="AI Co-Host Commands",
            description="Available commands for the AI Co-Host bot",
            color=disnake.Color.green()
        )
        
        embed.add_field(
            name="!ai join",
            value="Join your current voice channel",
            inline=False
        )
        
        embed.add_field(
            name="!ai leave",
            value="Leave the current voice channel",
            inline=False
        )
        
        embed.add_field(
            name="!ai status",
            value="Show bot status and connection info",
            inline=False
        )
        
        embed.add_field(
            name="!ai commands",
            value="Show this help message",
            inline=False
        )
        
        embed.add_field(
            name="Web Interface",
            value="Use the web dashboard for advanced controls like passive/active mode switching and document upload.",
            inline=False
        )
        
        await ctx.send(embed=embed)