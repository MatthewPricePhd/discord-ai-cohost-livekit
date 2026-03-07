"""
Configuration management for Discord AI Co-Host Bot
"""
import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Discord Configuration
    discord_bot_token: str = Field(..., description="Discord bot token")

    # OpenAI Configuration
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_admin_key: Optional[str] = Field(default=None, description="OpenAI Admin key for Usage API")
    openai_model: str = Field(default="gpt-realtime", description="OpenAI Realtime model")
    openai_realtime_model: str = Field(default="gpt-realtime", description="Realtime voice model (gpt-realtime or gpt-realtime-mini)")
    openai_reasoning_model: str = Field(default="gpt-5.4", description="Text reasoning model (gpt-5.4 or gpt-5.3-instant)")

    # ElevenLabs Configuration
    elevenlabs_api_key: Optional[str] = Field(default=None, description="ElevenLabs API key")
    elevenlabs_voice_id: Optional[str] = Field(default=None, description="ElevenLabs voice ID")
    elevenlabs_model: str = Field(default="eleven_flash_v2_5", description="ElevenLabs model (eleven_flash_v2_5 or eleven_multilingual_v2)")

    # Provider Selection
    tts_provider: str = Field(default="openai", description="TTS provider (openai or elevenlabs)")
    stt_provider: str = Field(default="openai", description="STT provider (openai or elevenlabs)")
    
    # Web Application Configuration
    secret_key: str = Field(..., description="Secret key for web application")
    web_port: int = Field(default=8000, description="Web server port")
    web_host: str = Field(default="0.0.0.0", description="Web server host")
    
    # File Upload Configuration
    upload_dir: Path = Field(default=Path("./uploads"), description="Directory for uploaded files")
    max_file_size: int = Field(default=52428800, description="Maximum file size in bytes (50MB)")
    supported_formats: List[str] = Field(
        default=["pdf", "docx", "txt", "md"], 
        description="Supported file formats"
    )
    
    # Vector Storage Configuration
    chroma_db_path: Path = Field(default=Path("./data/chroma"), description="ChromaDB storage path")
    pinecone_api_key: Optional[str] = Field(default=None, description="Pinecone API key (optional)")
    pinecone_environment: Optional[str] = Field(default=None, description="Pinecone environment (optional)")
    
    # Context Management Configuration
    max_context_tokens: int = Field(default=256000, description="Maximum context tokens for GPT-5.4 (supports up to 1M)")
    context_window_strategy: str = Field(default="sliding", description="Context window management strategy")
    session_timeout: int = Field(default=3600, description="Session timeout in seconds")
    
    # Audio Configuration
    audio_sample_rate: int = Field(default=24000, description="Audio sample rate in Hz")
    audio_channels: int = Field(default=1, description="Number of audio channels (mono)")
    audio_format: str = Field(default="pcm16", description="Audio format")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")
    
    # Redis Configuration (optional)
    redis_url: Optional[str] = Field(default=None, description="Redis URL for caching/scaling")
    
    # Environment Configuration
    env: str = Field(default="development", description="Environment (development/production)")
    debug: bool = Field(default=True, description="Debug mode")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_db_path.mkdir(parents=True, exist_ok=True)
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.env.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.env.lower() == "production"
    
    @property
    def openai_realtime_url(self) -> str:
        """Get OpenAI Realtime API WebSocket URL"""
        return f"wss://api.openai.com/v1/realtime?model={self.openai_realtime_model}"

    @property
    def openai_realtime_headers(self) -> dict:
        """Get headers for OpenAI Realtime API"""
        return {
            "Authorization": f"Bearer {self.openai_api_key}",
            "OpenAI-Beta": "realtime=v1"
        }

    @property
    def elevenlabs_available(self) -> bool:
        """Check if ElevenLabs is configured"""
        return self.elevenlabs_api_key is not None


# Global settings instance
settings = Settings()