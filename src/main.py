"""Main application entry point for AI Podcast Co-Host Studio."""
import asyncio
import signal
import sys

from .config import setup_logging, get_logger, settings
from .rooms import RoomManager

logger = get_logger(__name__)


class StudioApp:
    """Main application — serves the web UI and manages LiveKit rooms."""

    def __init__(self):
        self.room_manager = RoomManager(
            livekit_url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
        self.web_server = None
        self.running = False
        self.current_mode = "passive"
        self.session_start_time = None
        # Placeholders for features that reference the old app structure
        self.openai_client = None
        self.observer_agent = None
        self.discord_client = None

    async def set_mode(self, mode: str) -> str:
        """Set the AI operating mode."""
        if mode in ("passive", "speech-to-speech", "ask-chatgpt"):
            self.current_mode = mode
            logger.info("Mode changed", mode=mode)
        return self.current_mode

    async def toggle_mode(self) -> str:
        """Toggle between passive and speech-to-speech mode."""
        new_mode = "speech-to-speech" if self.current_mode == "passive" else "passive"
        return await self.set_mode(new_mode)

    async def force_ai_response(self):
        """Force the AI to generate a response (placeholder)."""
        logger.info("Force AI response triggered")

    async def start_transcription(self) -> bool:
        """Start transcription (placeholder)."""
        logger.info("Transcription start requested")
        return True

    async def stop_transcription(self) -> bool:
        """Stop transcription (placeholder)."""
        logger.info("Transcription stop requested")
        return True

    async def generate_tts(self, text: str) -> bytes:
        """Generate TTS audio (placeholder)."""
        logger.info("TTS generation requested", text_length=len(text))
        return b""

    async def start(self):
        """Start the web server."""
        try:
            logger.info("Starting AI Podcast Studio", version="2.0.0", env=settings.env)

            # Initialize web application
            from .web import WebApp
            web_app_instance = WebApp(self)
            web_app = web_app_instance.app

            # Start web server
            import uvicorn
            from uvicorn.config import Config

            config = Config(
                app=web_app,
                host=settings.web_host,
                port=settings.web_port,
                log_level=settings.log_level.lower(),
                access_log=settings.is_development,
            )
            self.web_server = uvicorn.Server(config)
            self.running = True

            logger.info("Web server starting", host=settings.web_host, port=settings.web_port)
            await self.web_server.serve()

        except Exception as e:
            logger.error("Failed to start Studio", error=str(e))
            raise

    async def shutdown(self):
        """Shutdown gracefully."""
        if not self.running:
            return
        logger.info("Shutting down Studio")
        self.running = False
        if self.room_manager:
            await self.room_manager.close()
        if self.web_server:
            self.web_server.should_exit = True
        logger.info("Shutdown complete")

    def get_status(self) -> dict:
        return {
            "running": self.running,
            "mode": self.current_mode,
            "livekit_url": settings.livekit_url,
        }


async def main():
    setup_logging()
    app = StudioApp()

    def signal_handler():
        asyncio.create_task(app.shutdown())

    signal.signal(signal.SIGINT, lambda s, f: signal_handler())
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler())

    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error("Unexpected error", error=str(e))
        sys.exit(1)
    finally:
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
