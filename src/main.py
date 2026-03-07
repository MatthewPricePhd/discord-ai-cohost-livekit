"""
Main application entry point for Discord AI Co-Host Bot
"""
import asyncio
import signal
import sys
from typing import Optional

import discord
from .bot import DiscordClient
from .api import OpenAIClient
from .web import create_web_app
from .config import setup_logging, get_logger, settings
from .context.observer import ObserverAgent

logger = get_logger(__name__)


class AICoHostApp:
    """Main application class that coordinates all components"""
    
    def __init__(self):
        self.discord_client: Optional[DiscordClient] = None
        self.openai_client: Optional[OpenAIClient] = None
        self.observer_agent: Optional[ObserverAgent] = None
        self.web_app = None
        self.web_server = None
        self.is_passive_mode = True  # Start in passive mode
        self.current_mode = "passive"  # Split-stack mode tracking
        self.running = False
        
    async def start(self):
        """Start the AI Co-Host application"""
        try:
            logger.info("Starting AI Co-Host Bot", version="1.0.0", env=settings.env)

            # Initialize components
            await self._initialize_components()

            # Start web server first so dashboard is always available
            await self._start_web_server()

            # Setup audio pipeline (OpenAI Realtime connection)
            try:
                await self._setup_audio_pipeline()
            except Exception as e:
                logger.error("Audio pipeline setup failed — will retry on voice join", error=str(e))

            # Start Discord bot (non-fatal if it fails)
            await self._start_discord_bot()

            self.running = True
            logger.info("AI Co-Host Bot started successfully")

        except Exception as e:
            logger.error("Failed to start AI Co-Host Bot", error=str(e))
            await self.shutdown()
            raise
    
    async def _initialize_components(self):
        """Initialize all application components"""
        logger.info("Initializing components")
        
        # Initialize Discord client
        self.discord_client = DiscordClient()
        
        # Initialize OpenAI client
        self.openai_client = OpenAIClient()
        
        # Initialize Observer Agent
        self.observer_agent = ObserverAgent()
        await self.observer_agent.start()

        # Initialize web application
        from .web import WebApp
        web_app_instance = WebApp(self)
        self.web_app = web_app_instance.app

        logger.info("Components initialized")
    
    async def _setup_audio_pipeline(self):
        """Setup the audio processing pipeline between Discord and OpenAI"""
        logger.info("Setting up audio pipeline")
        
        # Connect OpenAI Realtime API
        success = await self.openai_client.connect_realtime()
        if not success:
            raise RuntimeError("Failed to connect to OpenAI Realtime API")
        
        # Setup callbacks for audio flow
        # Discord audio -> OpenAI
        async def on_discord_audio(audio_data: bytes, user_id: int):
            if not self.is_passive_mode:  # Only send audio when not in passive mode
                await self.openai_client.send_audio_to_realtime(audio_data)
        
        # OpenAI audio -> Discord
        async def on_openai_audio(audio_data: bytes):
            if self.discord_client:
                await self.discord_client.send_audio(audio_data)
        
        # Setup transcription handling
        async def on_transcription(text: str, is_final: bool):
            if is_final:
                logger.debug("Transcription received", text=text)
                self.openai_client.add_conversation_turn("User", text)
                if self.observer_agent:
                    self.observer_agent.add_turn("User", text)
        
        # Setup status updates
        async def on_status_update(status_data: dict):
            logger.debug("Status update", data=status_data)
            # TODO: Broadcast to web clients
        
        # Setup error handling
        async def on_error(error_type: str, exception: Exception):
            logger.error("Pipeline error", error_type=error_type, error=str(exception))
        
        # Connect callbacks
        self.discord_client.set_audio_callback(on_discord_audio)
        self.openai_client.set_audio_callback(on_openai_audio)
        self.openai_client.set_transcript_callback(on_transcription)
        self.openai_client.set_status_callback(on_status_update)
        self.openai_client.set_error_callback(on_error)
        
        logger.info("Audio pipeline setup completed")
    
    async def _start_web_server(self):
        """Start the web server"""
        try:
            import uvicorn
            from uvicorn.config import Config
            
            config = Config(
                app=self.web_app,
                host=settings.web_host,
                port=settings.web_port,
                log_level=settings.log_level.lower(),
                access_log=settings.is_development
            )
            
            self.web_server = uvicorn.Server(config)
            
            # Start server in background task
            asyncio.create_task(self.web_server.serve())
            
            logger.info("Web server started", 
                       host=settings.web_host,
                       port=settings.web_port)
            
        except Exception as e:
            logger.error("Failed to start web server", error=str(e))
            raise
    
    async def _start_discord_bot(self):
        """Start the Discord bot"""
        try:
            # Start bot in background task
            bot_task = asyncio.create_task(self.discord_client.start(settings.discord_bot_token))

            # Add error handler so unhandled exceptions get logged
            def _on_bot_done(task):
                if task.cancelled():
                    logger.warning("Discord bot task was cancelled")
                elif task.exception():
                    logger.error("Discord bot task failed", error=str(task.exception()))
            bot_task.add_done_callback(_on_bot_done)

            # Wait for bot to be ready with timeout
            timeout = 30  # seconds
            elapsed = 0
            while not self.discord_client._ready and elapsed < timeout:
                await asyncio.sleep(0.5)
                elapsed += 0.5
                # Check if bot task already failed
                if bot_task.done() and bot_task.exception():
                    raise bot_task.exception()

            if not self.discord_client._ready:
                logger.warning("Discord bot did not become ready within timeout — web server will continue running")
            else:
                logger.info("Discord bot started successfully")

        except discord.LoginFailure as e:
            logger.error("Discord login failed — check your DISCORD_BOT_TOKEN", error=str(e))
            logger.info("Web server will continue running. Fix the token and restart.")
        except Exception as e:
            logger.error("Failed to start Discord bot", error=str(e))
            logger.info("Web server will continue running without Discord.")
    
    async def shutdown(self):
        """Shutdown the application gracefully"""
        if not self.running:
            return
        
        logger.info("Shutting down AI Co-Host Bot")
        self.running = False
        
        try:
            # Stop Observer Agent
            if self.observer_agent:
                await self.observer_agent.stop()

            # Stop Discord bot
            if self.discord_client:
                await self.discord_client.cleanup()

            # Disconnect OpenAI
            if self.openai_client:
                await self.openai_client.disconnect_realtime()
            
            # Stop web server
            if self.web_server:
                self.web_server.should_exit = True
                await self.web_server.shutdown()
            
            logger.info("AI Co-Host Bot shutdown completed")
            
        except Exception as e:
            logger.error("Error during shutdown", error=str(e))
    
    # Control methods for web interface
    async def join_voice_channel(self, channel_id: int) -> bool:
        """Join a Discord voice channel"""
        if not self.discord_client:
            return False
        
        success = await self.discord_client.join_voice_channel(channel_id)
        if success:
            await self.discord_client.start_listening()
        return success
    
    async def leave_voice_channel(self):
        """Leave current voice channel"""
        if self.discord_client:
            await self.discord_client.leave_voice_channel()
    
    async def toggle_mode(self) -> str:
        """Toggle between passive and active mode"""
        self.is_passive_mode = not self.is_passive_mode
        mode = "passive" if self.is_passive_mode else "active"
        
        logger.info("Mode switched", mode=mode)
        
        if not self.is_passive_mode:
            # Activate AI response generation
            if self.openai_client:
                await self.openai_client.activate_ai_response()
            
            # Start speaking in Discord
            if self.discord_client:
                await self.discord_client.start_speaking()
        else:
            # Stop speaking in Discord
            if self.discord_client:
                await self.discord_client.stop_speaking()
        
        return mode
    
    # Split-stack architecture methods
    async def set_mode(self, mode: str) -> bool:
        """Set split-stack operational mode"""
        valid_modes = ["passive", "speech-to-speech", "ask-chatgpt"]
        if mode not in valid_modes:
            logger.error("Invalid mode requested", mode=mode, valid_modes=valid_modes)
            return False
        
        try:
            if self.openai_client:
                success = await self.openai_client.set_mode(mode)
                if success:
                    # Update application state
                    if mode == "passive":
                        self.is_passive_mode = True
                    else:
                        self.is_passive_mode = False
                    
                    # Update current mode tracking
                    self.current_mode = mode
                    
                    logger.info("Application mode switched", mode=mode)
                    return True
            
            return False
            
        except Exception as e:
            logger.error("Error setting application mode", mode=mode, error=str(e))
            return False
    
    async def start_transcription(self) -> bool:
        """Start STT transcription"""
        if self.openai_client:
            return await self.openai_client.start_transcription()
        return False
    
    async def stop_transcription(self) -> bool:
        """Stop STT transcription"""
        if self.openai_client:
            return await self.openai_client.stop_transcription()
        return False
    
    async def generate_tts(self, text: str) -> bytes:
        """Generate TTS audio"""
        if self.openai_client:
            return await self.openai_client.generate_tts(text)
        return b""
    
    async def force_ai_response(self):
        """Force AI to generate a response (for testing/manual control)"""
        if self.openai_client:
            await self.openai_client.activate_ai_response()
    
    def get_status(self) -> dict:
        """Get application status"""
        return {
            "running": self.running,
            "mode": "passive" if self.is_passive_mode else "active",
            "discord_status": self.discord_client.get_status() if self.discord_client else None,
            "openai_status": self.openai_client.status if self.openai_client else None,
            "web_server_running": self.web_server is not None
        }


async def main():
    """Main application entry point"""
    # Setup logging
    setup_logging()
    
    # Create application instance
    app = AICoHostApp()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(app.shutdown())
    
    # Register signal handlers
    signal.signal(signal.SIGINT, lambda s, f: signal_handler())
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler())
    
    try:
        # Start the application
        await app.start()
        
        # Keep running until shutdown
        while app.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error("Unexpected error", error=str(e))
        sys.exit(1)
    finally:
        await app.shutdown()


if __name__ == "__main__":
    # Check for required environment variables
    if not settings.discord_bot_token:
        logger.error("DISCORD_BOT_TOKEN environment variable is required")
        sys.exit(1)
    
    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY environment variable is required")
        sys.exit(1)
    
    # Run the application
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Failed to start application", error=str(e))
        sys.exit(1)