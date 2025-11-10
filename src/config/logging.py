"""
Logging configuration for Discord AI Co-Host Bot
"""
import sys
import json
import logging
from pathlib import Path
from typing import Any, Dict

import structlog
from loguru import logger

from .settings import settings


class StructlogRenderer:
    """Custom renderer for structlog to work with loguru"""
    
    def __call__(self, _, __, event_dict: Dict[str, Any]) -> str:
        return json.dumps(event_dict, default=str) if settings.log_format == "json" else str(event_dict)


def setup_logging():
    """Configure logging for the application"""
    
    # Remove default loguru handler
    logger.remove()
    
    # Configure loguru
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    if settings.log_format == "json":
        # JSON format for production - use serialize=True for JSON
        logger.add(
            sys.stderr,
            level=settings.log_level,
            serialize=True,
            colorize=False
        )
    else:
        # Human-readable format for development
        logger.add(
            sys.stderr,
            level=settings.log_level,
            format=log_format,
            colorize=True
        )
    
    # Add file logging
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logger.add(
        log_dir / "discord_ai_cohost.log",
        level=settings.log_level,
        format=log_format,
        serialize=settings.log_format == "json",
        rotation="1 day",
        retention="30 days",
        compression="gz"
    )
    
    # Configure structlog to work with loguru
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer() if settings.is_development else StructlogRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        logger_factory=structlog.WriteLoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )
    
    # Log startup message
    logger.info("Logging configured", 
                level=settings.log_level, 
                format=settings.log_format,
                environment=settings.env)


def get_logger(name: str = None):
    """Get a configured logger instance"""
    return logger.bind(logger_name=name) if name else logger