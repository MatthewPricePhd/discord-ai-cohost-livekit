"""
OpenAI Realtime API event handler
"""
import asyncio
import base64
import json
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime

from .websocket_manager import WebSocketManager, ConnectionState
from ..config import get_logger, settings

logger = get_logger(__name__)


class RealtimeHandler:
    """Handles OpenAI Realtime API events and audio streaming"""
    
    def __init__(self):
        self.ws_manager = WebSocketManager()
        self.session_id: Optional[str] = None
        self.conversation_id: Optional[str] = None
        
        # Audio settings
        self.audio_format = "pcm16"  # PCM 16-bit
        self.sample_rate = 24000     # 24kHz
        
        # State tracking
        self.is_speaking = False
        self.is_listening = False
        self.response_in_progress = False
        
        # Event callbacks
        self.audio_callback: Optional[Callable[[bytes], None]] = None
        self.transcript_callback: Optional[Callable[[str, bool], None]] = None  # (text, is_final)
        self.response_callback: Optional[Callable[[str], None]] = None
        self.error_callback: Optional[Callable[[str, Exception], None]] = None
        self.status_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # Setup event handlers
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup WebSocket event handlers"""
        # Connection state changes
        self.ws_manager.add_connection_handler(self._on_connection_change)
        
        # API event handlers
        self.ws_manager.add_message_handler("session.created", self._on_session_created)
        self.ws_manager.add_message_handler("session.updated", self._on_session_updated)
        self.ws_manager.add_message_handler("conversation.created", self._on_conversation_created)
        self.ws_manager.add_message_handler("input_audio_buffer.speech_started", self._on_speech_started)
        self.ws_manager.add_message_handler("input_audio_buffer.speech_stopped", self._on_speech_stopped)
        self.ws_manager.add_message_handler("conversation.item.input_audio_transcription.completed", self._on_transcription_completed)
        self.ws_manager.add_message_handler("response.created", self._on_response_created)
        self.ws_manager.add_message_handler("response.output_item.added", self._on_response_item_added)
        self.ws_manager.add_message_handler("response.audio.delta", self._on_audio_delta)
        self.ws_manager.add_message_handler("response.audio_transcript.delta", self._on_transcript_delta)
        self.ws_manager.add_message_handler("response.done", self._on_response_done)
        self.ws_manager.add_message_handler("error", self._on_error)
        
        # Error handling
        self.ws_manager.add_error_handler(self._on_websocket_error)
    
    async def connect(self) -> bool:
        """Connect to OpenAI Realtime API and initialize session"""
        success = await self.ws_manager.connect()
        if success:
            await self._initialize_session()
        return success
    
    async def connect_transcription_mode(self) -> bool:
        """Connect to OpenAI Realtime API in transcription-only mode for split-stack"""
        success = await self.ws_manager.connect()
        if success:
            await self._initialize_transcription_session()
        return success
    
    async def disconnect(self):
        """Disconnect from OpenAI Realtime API"""
        await self.ws_manager.disconnect()
        self.session_id = None
        self.conversation_id = None
    
    async def _initialize_session(self):
        """Initialize a new session with OpenAI Realtime API"""
        session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": self._get_system_instructions(),
                "voice": "alloy",
                "input_audio_format": self.audio_format,
                "output_audio_format": self.audio_format,
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                },
                "tools": [],  # Can add function calling tools later
                "tool_choice": "none"
            }
        }
        
        await self.ws_manager.send_message(session_config)
        logger.info("Sent session initialization")
    
    async def _initialize_transcription_session(self):
        """Initialize a transcription-only session for split-stack architecture"""
        session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["audio"],  # Audio input only for transcription
                "instructions": "Transcribe audio input accurately. Do not generate responses.",
                "input_audio_format": self.audio_format,
                "input_audio_transcription": {
                    "model": "whisper-1"  # Use Whisper for cost-efficient transcription
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 800  # Longer silence for passive mode
                },
                "tools": [],
                "tool_choice": "none"
            }
        }
        
        await self.ws_manager.send_message(session_config)
        logger.info("Sent transcription-only session initialization")
    
    def _get_system_instructions(self) -> str:
        """Get system instructions for the AI co-host"""
        return """You are an intelligent AI co-host for podcast recordings. Your role is to:

1. Listen passively to conversations and build context
2. When activated, provide contextual insights, ask thoughtful questions, or add relevant information
3. Keep responses concise and natural for audio format (aim for 10-30 seconds)
4. Stay in character as a knowledgeable but not overwhelming co-host
5. Reference previous conversation points when relevant
6. Help maintain engaging conversation flow

Communication style:
- Natural, conversational tone
- Appropriate humor when fitting
- Professional but personable
- Clear pronunciation for voice synthesis

You have access to pre-loaded research documents that can inform your responses. Use this information to provide valuable insights when relevant to the current discussion topic."""
    
    async def send_audio(self, audio_data: bytes):
        """Send audio data to the API"""
        if not self.ws_manager.is_connected:
            logger.warning("Cannot send audio: not connected")
            return
        
        # Convert to base64 for transmission
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        
        message = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64
        }
        
        await self.ws_manager.send_message(message)
    
    async def commit_audio_buffer(self):
        """Commit the audio buffer to create a conversation item"""
        if not self.ws_manager.is_connected:
            logger.warning("Cannot commit audio: not connected")
            return
        
        message = {
            "type": "input_audio_buffer.commit"
        }
        
        await self.ws_manager.send_message(message)
    
    async def clear_audio_buffer(self):
        """Clear the audio buffer"""
        if not self.ws_manager.is_connected:
            logger.warning("Cannot clear audio: not connected")
            return
        
        message = {
            "type": "input_audio_buffer.clear"
        }
        
        await self.ws_manager.send_message(message)
    
    async def create_response(self):
        """Request the AI to generate a response"""
        if not self.ws_manager.is_connected:
            logger.warning("Cannot create response: not connected")
            return
        
        if self.response_in_progress:
            logger.debug("Response already in progress")
            return
        
        message = {
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"],
                "instructions": "Respond as the AI co-host. Keep it natural and conversational."
            }
        }
        
        await self.ws_manager.send_message(message)
        logger.debug("Requested AI response")
    
    async def cancel_response(self):
        """Cancel the current response generation"""
        if not self.ws_manager.is_connected or not self.response_in_progress:
            return
        
        message = {
            "type": "response.cancel"
        }
        
        await self.ws_manager.send_message(message)
        logger.debug("Cancelled AI response")
    
    # Event handlers
    async def _on_connection_change(self, state: ConnectionState):
        """Handle connection state changes"""
        logger.info("Connection state changed", state=state.value)
        
        if self.status_callback:
            await self.status_callback({
                "connection_state": state.value,
                "session_id": self.session_id,
                "is_connected": state == ConnectionState.CONNECTED
            })
    
    async def _on_session_created(self, message: Dict[str, Any]):
        """Handle session created event"""
        session = message.get("session", {})
        self.session_id = session.get("id")
        
        logger.info("Session created", session_id=self.session_id)
    
    async def _on_session_updated(self, message: Dict[str, Any]):
        """Handle session updated event"""
        logger.debug("Session updated")
    
    async def _on_conversation_created(self, message: Dict[str, Any]):
        """Handle conversation created event"""
        conversation = message.get("conversation", {})
        self.conversation_id = conversation.get("id")
        
        logger.info("Conversation created", conversation_id=self.conversation_id)
    
    async def _on_speech_started(self, message: Dict[str, Any]):
        """Handle speech started event"""
        logger.debug("Speech started detected")
        self.is_speaking = True
        
        if self.status_callback:
            await self.status_callback({"user_speaking": True})
    
    async def _on_speech_stopped(self, message: Dict[str, Any]):
        """Handle speech stopped event"""
        logger.debug("Speech stopped detected")
        self.is_speaking = False
        
        # Automatically commit audio buffer when speech stops
        await self.commit_audio_buffer()
        
        if self.status_callback:
            await self.status_callback({"user_speaking": False})
    
    async def _on_transcription_completed(self, message: Dict[str, Any]):
        """Handle transcription completed event"""
        transcript = message.get("transcript", "")
        
        logger.debug("Transcription completed", transcript=transcript)
        
        if self.transcript_callback and transcript:
            await self.transcript_callback(transcript, True)
    
    async def _on_response_created(self, message: Dict[str, Any]):
        """Handle response created event"""
        response = message.get("response", {})
        response_id = response.get("id")
        
        logger.debug("Response created", response_id=response_id)
        self.response_in_progress = True
    
    async def _on_response_item_added(self, message: Dict[str, Any]):
        """Handle response item added event"""
        item = message.get("item", {})
        logger.debug("Response item added", item_type=item.get("type"))
    
    async def _on_audio_delta(self, message: Dict[str, Any]):
        """Handle audio delta event (streaming AI audio)"""
        audio_b64 = message.get("delta")
        if audio_b64 and self.audio_callback:
            try:
                audio_data = base64.b64decode(audio_b64)
                await self.audio_callback(audio_data)
            except Exception as e:
                logger.error("Error processing audio delta", error=str(e))
    
    async def _on_transcript_delta(self, message: Dict[str, Any]):
        """Handle transcript delta event (streaming AI transcript)"""
        delta = message.get("delta", "")
        if delta and self.transcript_callback:
            await self.transcript_callback(delta, False)
    
    async def _on_response_done(self, message: Dict[str, Any]):
        """Handle response done event"""
        response = message.get("response", {})
        response_id = response.get("id")
        status = response.get("status")
        
        logger.debug("Response done", response_id=response_id, status=status)
        self.response_in_progress = False
        
        if self.status_callback:
            await self.status_callback({
                "response_completed": True,
                "response_status": status
            })
    
    async def _on_error(self, message: Dict[str, Any]):
        """Handle API error event"""
        error = message.get("error", {})
        error_type = error.get("type", "unknown")
        error_message = error.get("message", "Unknown error")
        
        logger.error("API error", error_type=error_type, message=error_message)
        
        if self.error_callback:
            await self.error_callback(error_type, Exception(error_message))
    
    async def _on_websocket_error(self, error: Exception):
        """Handle WebSocket errors"""
        logger.error("WebSocket error", error=str(error))
        
        if self.error_callback:
            await self.error_callback("websocket", error)
    
    # Callback setters
    def set_audio_callback(self, callback: Callable[[bytes], None]):
        """Set callback for AI-generated audio"""
        self.audio_callback = callback
    
    def set_transcript_callback(self, callback: Callable[[str, bool], None]):
        """Set callback for transcription updates (text, is_final)"""
        self.transcript_callback = callback
    
    def set_response_callback(self, callback: Callable[[str], None]):
        """Set callback for completed responses"""
        self.response_callback = callback
    
    def set_error_callback(self, callback: Callable[[str, Exception], None]):
        """Set callback for errors (error_type, exception)"""
        self.error_callback = callback
    
    def set_status_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback for status updates"""
        self.status_callback = callback
    
    @property
    def status(self) -> Dict[str, Any]:
        """Get current handler status"""
        return {
            "connected": self.ws_manager.is_connected,
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "is_speaking": self.is_speaking,
            "is_listening": self.is_listening,
            "response_in_progress": self.response_in_progress,
            "connection_info": self.ws_manager.connection_info
        }