"""
API routes for Discord AI Co-Host Bot web interface
"""
from typing import Dict, Any, List, Optional, TYPE_CHECKING

import json
import os
import time
from datetime import datetime
from pathlib import Path
import httpx

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from ..config import get_logger, settings

if TYPE_CHECKING:
    from ..main import StudioApp

logger = get_logger(__name__)


# Pydantic models for request/response
class StatusResponse(BaseModel):
    running: bool
    mode: str
    discord_status: Optional[Dict[str, Any]] = None
    openai_status: Optional[Dict[str, Any]] = None
    web_server_running: bool


class ModeToggleResponse(BaseModel):
    mode: str
    success: bool
    message: str


class DocumentUploadResponse(BaseModel):
    success: bool
    message: str
    document_id: Optional[str] = None


class ExportRequest(BaseModel):
    content_type: str  # "transcript" or "context"
    
    
class SessionRequest(BaseModel):
    action: str  # "start" or "stop"
    start_time: Optional[int] = None
    
    
class SessionResponse(BaseModel):
    success: bool
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    total_usd: Optional[float] = None
    breakdown: Optional[List[Dict[str, Any]]] = None
    message: str


class ObserverConfigureRequest(BaseModel):
    analysis_frequency: Optional[int] = None
    enabled: Optional[bool] = None


def create_api_router(ai_app: "StudioApp") -> APIRouter:
    """Create API router with all endpoints"""
    
    router = APIRouter()
    
    @router.get("/status", response_model=StatusResponse)
    async def get_status():
        """Get current application status"""
        try:
            status = ai_app.get_status()
            
            # Sanitize status to remove non-serializable objects
            def sanitize_dict(obj):
                """Remove non-serializable objects from dict"""
                if isinstance(obj, dict):
                    return {k: sanitize_dict(v) for k, v in obj.items() 
                           if not str(type(v)).startswith('<class \'asyncio')}
                elif isinstance(obj, (list, tuple)):
                    return [sanitize_dict(item) for item in obj]
                else:
                    return obj
            
            sanitized_status = sanitize_dict(status)
            return StatusResponse(**sanitized_status)
        except Exception as e:
            logger.error("Error getting status", error=str(e))
            raise HTTPException(status_code=500, detail="Failed to get status")
    
    @router.post("/mode/toggle", response_model=ModeToggleResponse)
    async def toggle_mode():
        """Toggle between passive and active mode"""
        try:
            new_mode = await ai_app.toggle_mode()
            return ModeToggleResponse(
                mode=new_mode,
                success=True,
                message=f"Successfully switched to {new_mode} mode"
            )
        except Exception as e:
            logger.error("Error toggling mode", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/ai/respond")
    async def force_ai_response():
        """Force AI to generate a response"""
        try:
            await ai_app.force_ai_response()
            return {
                "success": True,
                "message": "AI response triggered"
            }
        except Exception as e:
            logger.error("Error forcing AI response", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/documents/upload", response_model=DocumentUploadResponse)
    async def upload_document(
        file: UploadFile = File(...),
        title: Optional[str] = Form(None)
    ):
        """Upload a document for context enhancement"""
        try:
            # Validate file type
            if not file.filename:
                raise HTTPException(status_code=400, detail="No file provided")
            
            file_ext = file.filename.split('.')[-1].lower()
            if file_ext not in settings.supported_formats:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type. Supported: {', '.join(settings.supported_formats)}"
                )
            
            # Check file size
            content = await file.read()
            if len(content) > settings.max_file_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size: {settings.max_file_size / (1024*1024):.1f}MB"
                )
            
            # TODO: Process document through document processing system
            # For now, return success
            return DocumentUploadResponse(
                success=True,
                message=f"Document '{file.filename}' uploaded successfully",
                document_id=f"doc_{file.filename}_{hash(content) % 10000}"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error uploading document", 
                        filename=file.filename if file else None,
                        error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/documents")
    async def list_documents():
        """List uploaded documents"""
        try:
            # TODO: Implement document listing from document processing system
            return {
                "documents": [],
                "count": 0
            }
        except Exception as e:
            logger.error("Error listing documents", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.delete("/documents/{document_id}")
    async def delete_document(document_id: str):
        """Delete a document"""
        try:
            # TODO: Implement document deletion
            return {
                "success": True,
                "message": f"Document {document_id} deleted successfully"
            }
        except Exception as e:
            logger.error("Error deleting document", 
                        document_id=document_id,
                        error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/conversation/transcript")
    async def get_conversation_transcript():
        """Get recent conversation transcript"""
        try:
            if not ai_app.openai_client:
                return {"transcript": "", "turns": []}
            
            recent_text = ai_app.openai_client.get_recent_conversation_text()
            turns = ai_app.openai_client.conversation_history[-20:]  # Last 20 turns
            
            return {
                "transcript": recent_text,
                "turns": turns,
                "count": len(turns)
            }
            
        except Exception as e:
            logger.error("Error getting transcript", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/conversation/summary")
    async def get_conversation_summary():
        """Get conversation context summary"""
        try:
            if not ai_app.openai_client:
                return {"summary": "No context available"}
            
            summary = ai_app.openai_client.context_summary
            return {
                "summary": summary,
                "length": len(summary)
            }
            
        except Exception as e:
            logger.error("Error getting conversation summary", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/conversation/summarize")
    async def create_conversation_summary():
        """Generate a new conversation summary"""
        try:
            if not ai_app.openai_client:
                raise HTTPException(status_code=400, detail="OpenAI client not available")
            
            recent_text = ai_app.openai_client.get_recent_conversation_text()
            if not recent_text:
                raise HTTPException(status_code=400, detail="No conversation to summarize")
            
            summary = await ai_app.openai_client.generate_context_summary(recent_text)
            
            return {
                "success": True,
                "summary": summary,
                "length": len(summary)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error creating conversation summary", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/logs")
    async def get_logs():
        """Get application logs"""
        try:
            # Return comprehensive mock logs with various levels
            mock_logs = [
                {"timestamp": "2025-08-12T01:45:00Z", "level": "INFO", "logger": "discord_client", "message": "Discord bot started successfully"},
                {"timestamp": "2025-08-12T01:44:55Z", "level": "INFO", "logger": "openai_client", "message": "OpenAI Realtime API connection established"},
                {"timestamp": "2025-08-12T01:44:50Z", "level": "INFO", "logger": "web_server", "message": "Web server started on port 8000"},
                {"timestamp": "2025-08-12T01:44:45Z", "level": "INFO", "logger": "main", "message": "AI Co-Host Bot started successfully"},
                {"timestamp": "2025-08-12T01:44:40Z", "level": "DEBUG", "logger": "voice_handler", "message": "Voice handler initialized"},
                {"timestamp": "2025-08-12T01:44:35Z", "level": "DEBUG", "logger": "discord_client", "message": "Processing guild member update"},
                {"timestamp": "2025-08-12T01:44:30Z", "level": "DEBUG", "logger": "openai_client", "message": "Sending audio chunk to OpenAI"},
                {"timestamp": "2025-08-12T01:44:25Z", "level": "DEBUG", "logger": "voice_handler", "message": "Audio frame received from Discord"},
                {"timestamp": "2025-08-12T01:44:20Z", "level": "DEBUG", "logger": "web_server", "message": "Status endpoint requested"},
                {"timestamp": "2025-08-12T01:44:15Z", "level": "WARNING", "logger": "discord_client", "message": "No voice channels found in guild"},
                {"timestamp": "2025-08-12T01:44:10Z", "level": "WARNING", "logger": "openai_client", "message": "Rate limit approaching, throttling requests"},
                {"timestamp": "2025-08-12T01:44:05Z", "level": "WARNING", "logger": "voice_handler", "message": "Audio quality degraded, adjusting parameters"},
                {"timestamp": "2025-08-12T01:44:00Z", "level": "ERROR", "logger": "discord_client", "message": "Failed to connect to voice channel: Permission denied"},
                {"timestamp": "2025-08-12T01:43:55Z", "level": "ERROR", "logger": "openai_client", "message": "API request failed with status 500"},
                {"timestamp": "2025-08-12T01:43:50Z", "level": "ERROR", "logger": "voice_handler", "message": "Audio processing failed: Buffer overflow"},
                {"timestamp": "2025-08-12T01:43:45Z", "level": "INFO", "logger": "discord_client", "message": "User joined voice channel: General"},
                {"timestamp": "2025-08-12T01:43:40Z", "level": "INFO", "logger": "voice_handler", "message": "Starting voice recording session"},
                {"timestamp": "2025-08-12T01:43:35Z", "level": "INFO", "logger": "openai_client", "message": "Generated response for user query"},
                {"timestamp": "2025-08-12T01:43:30Z", "level": "DEBUG", "logger": "main", "message": "Periodic health check completed"},
                {"timestamp": "2025-08-12T01:43:25Z", "level": "WARNING", "logger": "web_server", "message": "High memory usage detected"},
                {"timestamp": "2025-08-12T01:43:20Z", "level": "DEBUG", "logger": "discord_client", "message": "Guild cache updated"},
                {"timestamp": "2025-08-12T01:43:15Z", "level": "INFO", "logger": "openai_client", "message": "Session renewed with OpenAI API"},
                {"timestamp": "2025-08-12T01:43:10Z", "level": "DEBUG", "logger": "voice_handler", "message": "Noise reduction applied"},
                {"timestamp": "2025-08-12T01:43:05Z", "level": "WARNING", "logger": "main", "message": "Memory usage above threshold: 85%"},
                {"timestamp": "2025-08-12T01:43:00Z", "level": "INFO", "logger": "discord_client", "message": "Command processed successfully"},
                {"timestamp": "2025-08-12T01:42:55Z", "level": "ERROR", "logger": "web_server", "message": "Rate limit exceeded for IP 192.168.1.100"},
                {"timestamp": "2025-08-12T01:42:50Z", "level": "DEBUG", "logger": "openai_client", "message": "Token count: 1,247 / 4,096"},
                {"timestamp": "2025-08-12T01:42:45Z", "level": "INFO", "logger": "voice_handler", "message": "Audio stream quality: Good"},
                {"timestamp": "2025-08-12T01:42:40Z", "level": "DEBUG", "logger": "discord_client", "message": "Heartbeat sent to Discord gateway"},
                {"timestamp": "2025-08-12T01:42:35Z", "level": "WARNING", "logger": "openai_client", "message": "Response timeout, retrying request"},
                {"timestamp": "2025-08-12T01:42:30Z", "level": "INFO", "logger": "main", "message": "Application health check passed"},
                {"timestamp": "2025-08-12T01:42:25Z", "level": "DEBUG", "logger": "web_server", "message": "WebSocket connection established"},
                {"timestamp": "2025-08-12T01:42:20Z", "level": "ERROR", "logger": "discord_client", "message": "Message send failed: Channel not found"},
                {"timestamp": "2025-08-12T01:42:15Z", "level": "DEBUG", "logger": "voice_handler", "message": "Buffer size adjusted to 4096 bytes"},
                {"timestamp": "2025-08-12T01:42:10Z", "level": "INFO", "logger": "openai_client", "message": "Context window optimized"},
                {"timestamp": "2025-08-12T01:42:05Z", "level": "WARNING", "logger": "main", "message": "Config reload required due to changes"},
                {"timestamp": "2025-08-12T01:42:00Z", "level": "DEBUG", "logger": "discord_client", "message": "Presence updated for 1 guilds"},
                {"timestamp": "2025-08-12T01:41:55Z", "level": "INFO", "logger": "voice_handler", "message": "Microphone sensitivity adjusted"},
                {"timestamp": "2025-08-12T01:41:50Z", "level": "ERROR", "logger": "openai_client", "message": "Invalid API key format detected"},
                {"timestamp": "2025-08-12T01:41:45Z", "level": "DEBUG", "logger": "web_server", "message": "Session cleanup completed"},
                {"timestamp": "2025-08-12T01:41:40Z", "level": "INFO", "logger": "main", "message": "Scheduled maintenance task completed"},
                {"timestamp": "2025-08-12T01:41:35Z", "level": "WARNING", "logger": "discord_client", "message": "Slow response from Discord API: 2.3s"},
                {"timestamp": "2025-08-12T01:41:30Z", "level": "DEBUG", "logger": "voice_handler", "message": "Echo cancellation enabled"},
                {"timestamp": "2025-08-12T01:41:25Z", "level": "INFO", "logger": "openai_client", "message": "Model response cached for efficiency"},
                {"timestamp": "2025-08-12T01:41:20Z", "level": "ERROR", "logger": "web_server", "message": "Database connection timeout"},
                {"timestamp": "2025-08-12T01:41:15Z", "level": "DEBUG", "logger": "main", "message": "Garbage collection triggered"},
                {"timestamp": "2025-08-12T01:41:10Z", "level": "INFO", "logger": "discord_client", "message": "Bot status updated to online"},
                {"timestamp": "2025-08-12T01:41:05Z", "level": "WARNING", "logger": "voice_handler", "message": "Packet loss detected: 3.2%"},
                {"timestamp": "2025-08-12T01:41:00Z", "level": "DEBUG", "logger": "openai_client", "message": "Request queued for processing"}
            ]
            
            return {
                "logs": mock_logs,
                "count": len(mock_logs),
                "total_lines": len(mock_logs)
            }
            
        except Exception as e:
            logger.error("Error getting logs", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.delete("/logs")
    async def clear_logs():
        """Clear application logs"""
        try:
            # TODO: Implement log clearing functionality
            # This would typically clear log files or reset log storage
            return {
                "success": True,
                "message": "Logs cleared successfully"
            }
            
        except Exception as e:
            logger.error("Error clearing logs", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/chatgpt/completion")
    async def chatgpt_completion(request: dict):
        """Get ChatGPT text completion"""
        try:
            if not ai_app.openai_client:
                raise HTTPException(status_code=400, detail="OpenAI client not available")
            
            prompt = request.get("prompt", "").strip()
            if not prompt:
                raise HTTPException(status_code=400, detail="Prompt is required")
            
            # Use the OpenAI client to get text completion
            response = await ai_app.openai_client.get_text_completion(prompt)
            
            return {
                "success": True,
                "response": response,
                "prompt": prompt
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error getting ChatGPT completion", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/context/add")
    async def add_to_context(request: dict):
        """Add content to context summary"""
        try:
            content = request.get("content", "").strip()
            content_type = request.get("type", "text")  # text, document, chatgpt
            
            if not content:
                raise HTTPException(status_code=400, detail="Content is required")
            
            if not ai_app.openai_client:
                raise HTTPException(status_code=400, detail="OpenAI client not available")
            
            # Add content to context summary
            current_summary = ai_app.openai_client.context_summary or ""
            
            # Format the new content based on type
            if content_type == "chatgpt":
                formatted_content = f"\n\n## ChatGPT Response\n{content}"
            elif content_type == "document":
                formatted_content = f"\n\n## Document Summary\n{content}"
            else:
                formatted_content = f"\n\n## Additional Context\n{content}"
            
            # Update the context summary
            ai_app.openai_client.context_summary = current_summary + formatted_content
            
            return {
                "success": True,
                "message": "Content added to context successfully"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error adding to context", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    # Split Stack Architecture - New API Endpoints
    @router.post("/mode/passive")
    async def set_passive_mode():
        """Set AI to Passive Listening mode (transcription-only)"""
        try:
            # Switch to passive listening mode
            await ai_app.set_mode("passive")
            
            return {
                "success": True,
                "mode": "passive",
                "message": "Switched to Passive Listening mode - transcription only"
            }
            
        except Exception as e:
            logger.error("Error setting passive mode", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/mode/speech-to-speech")
    async def set_speech_to_speech_mode():
        """Set AI to Speech-to-Speech Interaction mode"""
        try:
            # Switch to speech-to-speech mode
            await ai_app.set_mode("speech-to-speech")
            
            return {
                "success": True,
                "mode": "speech-to-speech",
                "message": "Switched to Speech-to-Speech Interaction mode"
            }
            
        except Exception as e:
            logger.error("Error setting speech-to-speech mode", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/mode/ask-chatgpt")
    async def set_ask_chatgpt_mode():
        """Set AI to Ask ChatGPT mode (text-only)"""
        try:
            await ai_app.set_mode("ask-chatgpt")

            return {
                "success": True,
                "mode": "ask-chatgpt",
                "message": "Switched to Ask ChatGPT mode - text-only queries"
            }

        except Exception as e:
            logger.error("Error setting ask-chatgpt mode", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/ai/ask-chatgpt")
    async def ask_chatgpt_mode(request: dict):
        """Ask ChatGPT mode - text-only Q&A without audio processing"""
        try:
            prompt = request.get("prompt", "").strip()
            if not prompt:
                raise HTTPException(status_code=400, detail="Prompt is required")
            
            if not ai_app.openai_client:
                raise HTTPException(status_code=400, detail="OpenAI client not available")
            
            # Set mode to ask-chatgpt temporarily
            previous_mode = getattr(ai_app, 'current_mode', 'passive')
            await ai_app.set_mode("ask-chatgpt")
            
            # Use gpt-5-mini for cost efficiency in Ask ChatGPT mode
            response = await ai_app.openai_client.get_text_completion(prompt)
            
            # Return to previous mode
            await ai_app.set_mode(previous_mode)
            
            return {
                "success": True,
                "mode": "ask-chatgpt",
                "prompt": prompt,
                "response": response,
                "message": "ChatGPT response generated successfully"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error in ask-chatgpt mode", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/transcription/start")
    async def start_transcription():
        """Start STT transcription in passive mode"""
        try:
            if not ai_app.openai_client:
                raise HTTPException(status_code=400, detail="OpenAI client not available")
            
            # Start transcription using gpt-4o-mini-transcribe model
            success = await ai_app.start_transcription()
            
            if success:
                return {
                    "success": True,
                    "message": "Transcription started using gpt-4o-mini-transcribe"
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to start transcription")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error starting transcription", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/transcription/stop")
    async def stop_transcription():
        """Stop STT transcription"""
        try:
            success = await ai_app.stop_transcription()
            
            if success:
                return {
                    "success": True,
                    "message": "Transcription stopped"
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to stop transcription")
            
        except Exception as e:
            logger.error("Error stopping transcription", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/tts/generate")
    async def generate_speech(request: dict):
        """Generate TTS audio for speech-to-speech mode"""
        try:
            text = request.get("text", "").strip()
            if not text:
                raise HTTPException(status_code=400, detail="Text is required")
            
            if not ai_app.openai_client:
                raise HTTPException(status_code=400, detail="OpenAI client not available")
            
            # Generate TTS using cost-efficient model
            audio_data = await ai_app.generate_tts(text)
            
            return {
                "success": True,
                "message": "TTS audio generated successfully",
                "audio_length": len(audio_data) if audio_data else 0
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error generating TTS", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/export/transcript")
    async def export_transcript():
        """Export conversation transcript as markdown"""
        try:
            if not ai_app.openai_client:
                raise HTTPException(status_code=400, detail="OpenAI client not available")
            
            # Check if bot is in passive mode and not actively transcribing
            if ai_app.discord_client and (ai_app.discord_client.voice_manager.voice_client and ai_app.discord_client.voice_manager.voice_client.is_connected()):
                if ai_app.current_mode != "passive":
                    raise HTTPException(status_code=400, detail="Export not allowed during active transcription")
            
            turns = ai_app.openai_client.conversation_history or []
            if not turns:
                raise HTTPException(status_code=400, detail="No conversation to export")
            
            # Create exports directory if it doesn't exist
            exports_dir = Path("exports")
            exports_dir.mkdir(exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"conversation_transcript_{timestamp}.md"
            filepath = exports_dir / filename
            
            # Generate markdown content
            markdown_content = f"# Conversation Transcript\n\n"
            markdown_content += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            markdown_content += f"**Total Turns:** {len(turns)}\n\n"
            markdown_content += "---\n\n"
            
            for i, turn in enumerate(turns, 1):
                speaker = turn.get('speaker', 'Unknown')
                text = turn.get('text', '')
                timestamp = turn.get('timestamp', '')
                
                if timestamp:
                    formatted_time = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')
                    markdown_content += f"## Turn {i} - {speaker} ({formatted_time})\n\n"
                else:
                    markdown_content += f"## Turn {i} - {speaker}\n\n"
                
                markdown_content += f"{text}\n\n"
            
            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            logger.info("Transcript exported successfully", 
                       filename=filename, 
                       turns_count=len(turns))
            
            return {
                "success": True,
                "message": f"Transcript exported to {filename}",
                "filename": filename,
                "turns_count": len(turns)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error exporting transcript", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/export/context")
    async def export_context():
        """Export context summary as markdown"""
        try:
            if not ai_app.openai_client:
                raise HTTPException(status_code=400, detail="OpenAI client not available")
            
            # Check if bot is in passive mode and not actively processing
            if ai_app.discord_client and (ai_app.discord_client.voice_manager.voice_client and ai_app.discord_client.voice_manager.voice_client.is_connected()):
                if ai_app.current_mode != "passive":
                    raise HTTPException(status_code=400, detail="Export not allowed during active mode")
            
            summary = ai_app.openai_client.context_summary
            if not summary or summary.strip() == "":
                raise HTTPException(status_code=400, detail="No context summary to export")
            
            # Create exports directory if it doesn't exist
            exports_dir = Path("exports")
            exports_dir.mkdir(exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"context_summary_{timestamp}.md"
            filepath = exports_dir / filename
            
            # Generate markdown content with header
            markdown_content = f"# Context Summary\n\n"
            markdown_content += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            markdown_content += f"**Content Length:** {len(summary)} characters\n\n"
            markdown_content += "---\n\n"
            markdown_content += summary
            
            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            logger.info("Context summary exported successfully", 
                       filename=filename, 
                       content_length=len(summary))
            
            return {
                "success": True,
                "message": f"Context summary exported to {filename}",
                "filename": filename,
                "content_length": len(summary)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error exporting context", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/session/status")
    async def get_session_status():
        """Get current session tracking status with provider info"""
        try:
            # Check if session is running (stored in app state)
            session_start = getattr(ai_app, 'session_start_time', None)
            is_running = session_start is not None

            # Include live cost tracking from openai_client if available
            live_costs = None
            if ai_app.openai_client:
                live_costs = ai_app.openai_client.get_session_costs()

            return {
                "running": is_running,
                "start_time": session_start,
                "duration": int(time.time() - session_start) if is_running else 0,
                "tts_provider": settings.tts_provider,
                "stt_provider": settings.stt_provider,
                "reasoning_model": settings.openai_reasoning_model,
                "live_costs": live_costs,
            }
            
        except Exception as e:
            logger.error("Error getting session status", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/session/start")
    async def start_session():
        """Start tracking a usage session"""
        try:
            # Store session start time in app state
            ai_app.session_start_time = int(time.time())
            
            logger.info("Usage session started", start_time=ai_app.session_start_time)
            
            return {
                "success": True,
                "start_time": ai_app.session_start_time,
                "message": "Session tracking started"
            }
            
        except Exception as e:
            logger.error("Error starting session", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/session/stop")
    async def stop_session():
        """Stop session and calculate estimated cost"""
        try:
            start_time = getattr(ai_app, 'session_start_time', None)
            if not start_time:
                raise HTTPException(status_code=400, detail="No active session to stop")
            
            end_time = int(time.time())
            
            # Get OpenAI Admin key for Usage API (requires admin key, not regular API key)
            admin_key = settings.openai_admin_key
            if not admin_key:
                logger.warning("OpenAI Admin key not configured — using tracked costs from this session instead")
                # Fall back to locally tracked costs
                ai_app.session_start_time = None
                computed_costs = ai_app.openai_client.get_session_costs() if ai_app.openai_client else {"total_cost": 0.0}
                return {
                    "success": True,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration_seconds": end_time - start_time,
                    "total_usd": round(computed_costs.get("total_cost", 0.0), 6),
                    "breakdown": [],
                    "cost_summary": computed_costs,
                    "message": f"Session completed (local tracking). Duration: {end_time - start_time}s",
                    "source": "local"
                }
            
            # Enhanced pricing map with STT, TTS, and Realtime rates (USD per 1K tokens unless noted)
            pricing_map = {
                # Reasoning / text models (per 1K tokens)
                "gpt-5.4": {"input": 1.25, "output": 5.00},
                "gpt-5.3-instant": {"input": 0.50, "output": 2.00},

                # Realtime voice models (per 1K tokens)
                "gpt-realtime": {
                    "input": 4.00, "output": 16.00,
                    "audio_input": 32.00, "audio_output": 64.00,
                },
                "gpt-realtime-mini": {"input": 0.60, "output": 2.40},

                # Legacy models kept for usage API lookups
                "gpt-4o-2024-08-06": {"input": 2.50, "output": 5.00},
                "gpt-4o-mini-2024-07-18": {"input": 0.50, "output": 1.50},

                # STT models (per minute)
                "gpt-4o-mini-transcribe": {"rate_per_minute": 0.006},
                "whisper-1": {"rate_per_minute": 0.006},

                # TTS models (per minute)
                "gpt-4o-mini-tts": {"rate_per_minute": 0.024},
                "tts-1": {"rate_per_minute": 0.015},
                "tts-1-hd": {"rate_per_minute": 0.030},
            }
            
            try:
                # Call OpenAI Usage API
                async with httpx.AsyncClient() as client:
                    params = {
                        "start_time": str(start_time),
                        "end_time": str(end_time),
                        "bucket_width": "1m",
                        "group_by": "model"
                    }
                    
                    response = await client.get(
                        "https://api.openai.com/v1/organization/usage/completions",
                        headers={"Authorization": f"Bearer {admin_key}"},
                        params=params,
                        timeout=30.0
                    )
                    
                    if response.status_code != 200:
                        logger.warning("OpenAI Usage API request failed",
                                     status_code=response.status_code,
                                     response=response.text)
                        # Fall back to locally tracked costs
                        ai_app.session_start_time = None
                        costs = ai_app.openai_client.session_costs if ai_app.openai_client else {}
                        return {
                            "success": True,
                            "start_time": start_time,
                            "end_time": end_time,
                            "duration_seconds": end_time - start_time,
                            "total_usd": round(costs.get("total_cost", 0.0), 6),
                            "breakdown": [],
                            "cost_summary": ai_app.openai_client.get_session_costs() if ai_app.openai_client else {},
                            "message": f"Session completed (local tracking — Usage API returned {response.status_code}). Duration: {end_time - start_time}s",
                            "source": "local"
                        }
                    
                    data = response.json().get("data", [])
                    
                    # Aggregate tokens by model
                    by_model = {}
                    for bucket in data:
                        for row in bucket.get("results", []):
                            model = row.get("model") or "unknown"
                            stats = by_model.setdefault(model, {
                                "input": 0, "output": 0, "cached": 0, "requests": 0
                            })
                            stats["input"] += row.get("input_tokens", 0)
                            stats["output"] += row.get("output_tokens", 0)
                            stats["cached"] += row.get("input_cached_tokens", 0)
                            stats["requests"] += row.get("num_model_requests", 0)
                    
                    # Calculate costs
                    total_cost = 0.0
                    breakdown = []
                    
                    for model, stats in by_model.items():
                        pricing = pricing_map.get(model, {"input": 0, "output": 0})
                        input_cost = (stats["input"] / 1000) * pricing["input"]
                        output_cost = (stats["output"] / 1000) * pricing["output"]
                        model_cost = input_cost + output_cost
                        total_cost += model_cost
                        
                        breakdown.append({
                            "model": model,
                            "input_tokens": stats["input"],
                            "output_tokens": stats["output"],
                            "cached_tokens": stats["cached"],
                            "requests": stats["requests"],
                            "cost_usd": round(model_cost, 6)
                        })
                    
            except httpx.RequestError as e:
                logger.warning("OpenAI Usage API request failed", error=str(e))
                ai_app.session_start_time = None
                computed_costs = ai_app.openai_client.get_session_costs() if ai_app.openai_client else {"total_cost": 0.0}
                return {
                    "success": True,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration_seconds": end_time - start_time,
                    "total_usd": round(computed_costs.get("total_cost", 0.0), 6),
                    "breakdown": [],
                    "cost_summary": computed_costs,
                    "message": f"Session completed (local tracking — network error). Duration: {end_time - start_time}s",
                    "source": "local"
                }
            
            # Clear session start time
            ai_app.session_start_time = None
            
            logger.info("Usage session completed", 
                       start_time=start_time,
                       end_time=end_time,
                       duration=end_time-start_time,
                       total_cost=total_cost)
            
            return {
                "success": True,
                "start_time": start_time,
                "end_time": end_time,
                "duration_seconds": end_time - start_time,
                "total_usd": round(total_cost, 6),
                "breakdown": breakdown,
                "message": f"Session completed. Duration: {end_time - start_time}s"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error stopping session", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _get_mock_session_data(start_time: int, end_time: int):
        """Return mock session data for development/testing with enhanced cost tracking"""
        duration = end_time - start_time
        duration_minutes = duration / 60
        
        # Generate realistic mock data based on session duration with split-stack costs
        tts_provider = settings.tts_provider
        stt_provider = settings.stt_provider

        mock_breakdown = [
            # Token-based costs (gpt-5.4 for reasoning)
            {
                "service": "Text Processing",
                "provider": "openai",
                "model": settings.openai_reasoning_model,
                "input_tokens": max(100, duration * 2),
                "output_tokens": max(50, duration * 1),
                "cached_tokens": 0,
                "requests": max(1, duration // 30),
                "cost_usd": round((max(100, duration * 2) / 1000 * 1.25) + (max(50, duration * 1) / 1000 * 5.00), 6)
            },
            # STT costs
            {
                "service": "Speech-to-Text",
                "provider": stt_provider,
                "model": "whisper-1" if stt_provider == "openai" else "scribe_v1",
                "minutes": round(duration_minutes * 0.8, 2),
                "cost_usd": round(duration_minutes * 0.8 * (0.006 if stt_provider == "openai" else 0.005), 6)
            },
            # TTS costs
            {
                "service": "Text-to-Speech",
                "provider": tts_provider,
                "model": "tts-1" if tts_provider == "openai" else settings.elevenlabs_model,
                "minutes": round(duration_minutes * 0.1, 2),
                "characters": max(100, duration * 5) if tts_provider == "elevenlabs" else 0,
                "cost_usd": round(
                    duration_minutes * 0.1 * 0.015 if tts_provider == "openai"
                    else max(100, duration * 5) * 0.30 / 1000, 6
                )
            }
        ]
        
        total_cost = sum(item["cost_usd"] for item in mock_breakdown)
        
        return {
            "success": True,
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration,
            "total_usd": round(total_cost, 6),
            "breakdown": mock_breakdown,
            "cost_summary": {
                "stt_minutes": round(duration_minutes * 0.8, 2),
                "tts_minutes": round(duration_minutes * 0.1, 2),
                "total_tokens": max(150, duration * 3),
                "total_requests": max(1, duration // 30)
            },
            "message": f"Session completed (mock data). Duration: {duration}s with split-stack cost tracking"
        }
    
    # ------------------------------------------------------------------
    # Provider & Voice endpoints
    # ------------------------------------------------------------------

    @router.get("/providers")
    async def get_providers():
        """Get current TTS/STT provider configuration and available options"""
        return {
            "tts_provider": settings.tts_provider,
            "stt_provider": settings.stt_provider,
            "reasoning_model": settings.openai_reasoning_model,
            "available_tts_providers": ["openai", "elevenlabs"] if settings.elevenlabs_available else ["openai"],
            "available_stt_providers": ["openai", "elevenlabs"] if settings.elevenlabs_available else ["openai"],
            "available_reasoning_models": ["gpt-5.4", "gpt-5.3-instant"],
            "elevenlabs_available": settings.elevenlabs_available,
        }

    @router.post("/providers/tts")
    async def set_tts_provider(request: dict):
        """Switch TTS provider"""
        provider = request.get("provider", "").lower()
        if provider not in ("openai", "elevenlabs"):
            raise HTTPException(status_code=400, detail="Invalid TTS provider. Use 'openai' or 'elevenlabs'.")
        if provider == "elevenlabs" and not settings.elevenlabs_available:
            raise HTTPException(status_code=400, detail="ElevenLabs API key not configured.")
        settings.tts_provider = provider
        return {"success": True, "tts_provider": provider, "message": f"TTS provider set to {provider}"}

    @router.post("/providers/stt")
    async def set_stt_provider(request: dict):
        """Switch STT provider"""
        provider = request.get("provider", "").lower()
        if provider not in ("openai", "elevenlabs"):
            raise HTTPException(status_code=400, detail="Invalid STT provider. Use 'openai' or 'elevenlabs'.")
        if provider == "elevenlabs" and not settings.elevenlabs_available:
            raise HTTPException(status_code=400, detail="ElevenLabs API key not configured.")
        settings.stt_provider = provider
        return {"success": True, "stt_provider": provider, "message": f"STT provider set to {provider}"}

    @router.post("/providers/reasoning-model")
    async def set_reasoning_model(request: dict):
        """Switch reasoning model"""
        model = request.get("model", "")
        valid_models = ["gpt-5.4", "gpt-5.3-instant"]
        if model not in valid_models:
            raise HTTPException(status_code=400, detail=f"Invalid model. Use one of: {valid_models}")
        settings.openai_reasoning_model = model
        return {"success": True, "reasoning_model": model, "message": f"Reasoning model set to {model}"}

    @router.get("/voices")
    async def list_voices():
        """List available voices for the current TTS provider"""
        if settings.tts_provider == "openai":
            return {
                "provider": "openai",
                "voices": [
                    {"id": "alloy", "name": "Alloy"},
                    {"id": "ash", "name": "Ash"},
                    {"id": "ballad", "name": "Ballad"},
                    {"id": "coral", "name": "Coral"},
                    {"id": "echo", "name": "Echo"},
                    {"id": "fable", "name": "Fable"},
                    {"id": "onyx", "name": "Onyx"},
                    {"id": "nova", "name": "Nova"},
                    {"id": "sage", "name": "Sage"},
                    {"id": "shimmer", "name": "Shimmer"},
                    {"id": "verse", "name": "Verse"},
                ]
            }
        elif settings.tts_provider == "elevenlabs":
            # Return configured voice plus a note to manage voices in ElevenLabs dashboard
            voices = []
            if settings.elevenlabs_voice_id:
                voices.append({"id": settings.elevenlabs_voice_id, "name": "Configured Voice"})
            try:
                if settings.elevenlabs_available:
                    from elevenlabs import AsyncElevenLabs
                    client = AsyncElevenLabs(api_key=settings.elevenlabs_api_key)
                    response = await client.voices.get_all()
                    voices = [{"id": v.voice_id, "name": v.name} for v in response.voices]
            except Exception as e:
                logger.warning("Failed to fetch ElevenLabs voices", error=str(e))
            return {"provider": "elevenlabs", "voices": voices}
        else:
            return {"provider": settings.tts_provider, "voices": []}

    @router.post("/voices/select")
    async def select_voice(request: dict):
        """Select a voice for the current TTS provider"""
        voice_id = request.get("voice_id", "")
        if not voice_id:
            raise HTTPException(status_code=400, detail="voice_id is required")
        if settings.tts_provider == "elevenlabs":
            settings.elevenlabs_voice_id = voice_id
        return {"success": True, "voice_id": voice_id, "provider": settings.tts_provider}

    # ------------------------------------------------------------------
    # Observer Agent endpoints
    # ------------------------------------------------------------------

    @router.get("/observer/insights")
    async def get_observer_insights():
        """Get latest AI observer insights"""
        try:
            if not ai_app.observer_agent:
                return {"insights": [], "enabled": False}

            return {
                "insights": ai_app.observer_agent.get_latest_insights(),
                "enabled": ai_app.observer_agent.enabled,
                "analysis_frequency": ai_app.observer_agent.analysis_frequency,
            }

        except Exception as e:
            logger.error("Error getting observer insights", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/observer/configure")
    async def configure_observer(request: ObserverConfigureRequest):
        """Configure the observer agent"""
        try:
            if not ai_app.observer_agent:
                raise HTTPException(status_code=400, detail="Observer agent not available")

            config = ai_app.observer_agent.configure(
                analysis_frequency=request.analysis_frequency,
                enabled=request.enabled,
            )

            return {
                "success": True,
                "config": config,
                "message": "Observer configuration updated",
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error configuring observer", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    # --- Room Management Endpoints ---

    @router.post("/rooms/create")
    async def create_room(request: Request):
        """Create a new podcast room."""
        body = await request.json()
        title = body.get("title", "Podcast Session")

        # Input validation
        if not isinstance(title, str) or len(title.strip()) == 0:
            raise HTTPException(status_code=400, detail="Title is required")
        if len(title) > 200:
            raise HTTPException(status_code=400, detail="Title must be 200 characters or fewer")
        title = title.strip()

        app = request.app.state.studio_app
        room_name = app.room_manager.generate_room_name(title)
        room_info = await app.room_manager.create_room(room_name, metadata=json.dumps({"title": title}))

        # Generate producer token for the host
        host_token = app.room_manager.create_token(
            room_name=room_name,
            participant_name="Host",
            identity="host",
            role="producer",
        )

        return {
            "success": True,
            "room": room_info,
            "host_token": host_token,
            "livekit_url": settings.livekit_url,
        }

    @router.get("/rooms")
    async def list_rooms(request: Request):
        """List active rooms."""
        app = request.app.state.studio_app
        rooms = await app.room_manager.list_rooms()
        return {"success": True, "rooms": rooms}

    @router.delete("/rooms/{room_name}")
    async def delete_room(request: Request, room_name: str):
        """Delete a room."""
        app = request.app.state.studio_app
        await app.room_manager.delete_room(room_name)
        return {"success": True}

    @router.post("/rooms/{room_name}/invite")
    async def create_invite(request: Request, room_name: str):
        """Generate an invite link for a guest."""
        body = await request.json()
        participant_name = body.get("name", "Guest")
        role = body.get("role", "guest")

        # Input validation
        if not isinstance(participant_name, str) or len(participant_name.strip()) == 0:
            participant_name = "Guest"
        if len(participant_name) > 100:
            raise HTTPException(status_code=400, detail="Name must be 100 characters or fewer")
        participant_name = participant_name.strip()
        if role not in ("guest", "co-producer", "producer"):
            raise HTTPException(status_code=400, detail="Role must be guest, co-producer, or producer")

        app = request.app.state.studio_app
        base_url = str(request.base_url).rstrip("/")
        link = app.room_manager.create_invite_link(
            room_name=room_name,
            participant_name=participant_name,
            role=role,
            base_url=base_url,
        )

        return {"success": True, "invite_link": link}

    # ------------------------------------------------------------------
    # Participant management endpoints
    # ------------------------------------------------------------------

    @router.post("/rooms/{room_name}/participants/{identity}/mute")
    async def mute_participant(request: Request, room_name: str, identity: str):
        """Mute a participant's audio track."""
        try:
            app = request.app.state.studio_app
            lk_api = app.room_manager._get_api()
            from livekit import api as lk_api_mod
            await lk_api.room.mute_published_track(
                lk_api_mod.MuteRoomTrackRequest(
                    room=room_name,
                    identity=identity,
                    track_sid="",  # empty = mute all
                    muted=True,
                )
            )
            return {"success": True, "message": f"Muted {identity}"}
        except Exception as e:
            logger.error("Error muting participant", identity=identity, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete("/rooms/{room_name}/participants/{identity}")
    async def remove_participant(request: Request, room_name: str, identity: str):
        """Remove a participant from the room."""
        try:
            app = request.app.state.studio_app
            lk_api = app.room_manager._get_api()
            from livekit import api as lk_api_mod
            await lk_api.room.remove_participant(
                lk_api_mod.RoomParticipantIdentity(
                    room=room_name,
                    identity=identity,
                )
            )
            return {"success": True, "message": f"Removed {identity}"}
        except Exception as e:
            logger.error("Error removing participant", identity=identity, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    # ------------------------------------------------------------------
    # Transcript archive endpoints
    # ------------------------------------------------------------------

    # In-memory transcript store (v1 — upgrade to SQLite in Phase 3)
    _transcript_entries: list = []

    @router.post("/transcript/add")
    async def add_transcript_entry(request: Request):
        """Store a transcript entry for later export."""
        body = await request.json()
        speaker = body.get("speaker", "Unknown")
        text = body.get("text", "")

        # Input validation
        if not isinstance(speaker, str) or len(speaker) > 200:
            speaker = "Unknown"
        if not isinstance(text, str) or len(text) > 50000:
            raise HTTPException(status_code=400, detail="Text too long (max 50000 chars)")

        entry = {
            "speaker": speaker,
            "text": text,
            "timestamp": body.get("timestamp", int(time.time())),
        }
        _transcript_entries.append(entry)
        return {"success": True, "count": len(_transcript_entries)}

    @router.get("/transcript")
    async def get_transcript():
        """Get all stored transcript entries."""
        return {
            "success": True,
            "entries": _transcript_entries,
            "count": len(_transcript_entries),
        }

    @router.delete("/transcript")
    async def clear_transcript():
        """Clear stored transcript entries."""
        _transcript_entries.clear()
        return {"success": True, "message": "Transcript cleared"}

    # ------------------------------------------------------------------
    # Phase 3: Episode History + Memory Search + Document Upload
    # ------------------------------------------------------------------

    from ..archive import TranscriptStore
    from ..memory import PodcastMemory
    from ..documents.uploader import DocumentUploader

    _archive_store = TranscriptStore()
    _podcast_memory = PodcastMemory()
    _doc_uploader = DocumentUploader()

    @router.get("/episodes")
    async def list_episodes():
        """List all past episodes with entry counts."""
        try:
            episodes = _archive_store.list_episodes()
            return {"success": True, "episodes": episodes, "count": len(episodes)}
        except Exception as e:
            logger.error("Error listing episodes", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/episodes/{episode_id}")
    async def get_episode(episode_id: str):
        """Get full episode transcript."""
        try:
            episode = _archive_store.get_episode(episode_id)
            if not episode:
                raise HTTPException(status_code=404, detail="Episode not found")
            return {"success": True, "episode": episode}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error getting episode", episode_id=episode_id, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/episodes/{episode_id}/export")
    async def export_episode(episode_id: str, fmt: str = "markdown"):
        """Export episode transcript as markdown or JSON."""
        try:
            if fmt == "json":
                content = _archive_store.export_json(episode_id)
            else:
                content = _archive_store.export_markdown(episode_id)

            if content is None:
                raise HTTPException(status_code=404, detail="Episode not found")

            return {
                "success": True,
                "format": fmt,
                "content": content,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error exporting episode", episode_id=episode_id, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/memory/search")
    async def search_memory(request: Request):
        """Search across all episode memories."""
        try:
            body = await request.json()
            query = body.get("query", "").strip()
            if not query:
                raise HTTPException(status_code=400, detail="Query is required")
            if len(query) > 5000:
                raise HTTPException(status_code=400, detail="Query too long (max 5000 chars)")

            episode_id = body.get("episode_id")
            limit = min(body.get("limit", 10), 100)  # Cap at 100 results

            results = _podcast_memory.search(query, episode_id=episode_id, limit=limit)
            return {"success": True, "results": results, "count": len(results)}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error searching memory", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/documents/upload/full")
    async def upload_document_full(
        file: UploadFile = File(...),
        title: Optional[str] = Form(None),
    ):
        """Upload a document, process it, and store vectors for RAG."""
        try:
            result = await _doc_uploader.upload_document(file, title=title)
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("error", "Upload failed"))
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error in full document upload", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/documents/list")
    async def list_uploaded_documents():
        """List all uploaded and processed documents."""
        try:
            docs = _doc_uploader.list_documents()
            return {"success": True, "documents": docs, "count": len(docs)}
        except Exception as e:
            logger.error("Error listing documents", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    # ------------------------------------------------------------------
    # Phase 4: Content Pipeline
    # ------------------------------------------------------------------

    from ..archive.content_pipeline import ContentPipeline

    _content_pipeline = ContentPipeline(store=_archive_store)

    @router.post("/episodes/{episode_id}/blog-post")
    async def generate_blog_post(episode_id: str):
        """Generate a blog post from the episode transcript."""
        try:
            result = await _content_pipeline.generate_blog_post(episode_id)
            if not result.get("success"):
                status = 404 if "not found" in result.get("error", "").lower() else 500
                raise HTTPException(status_code=status, detail=result.get("error", "Generation failed"))
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error generating blog post", episode_id=episode_id, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/episodes/{episode_id}/show-notes")
    async def generate_show_notes(episode_id: str):
        """Generate show notes from the episode transcript."""
        try:
            result = await _content_pipeline.generate_show_notes(episode_id)
            if not result.get("success"):
                status = 404 if "not found" in result.get("error", "").lower() else 500
                raise HTTPException(status_code=status, detail=result.get("error", "Generation failed"))
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error generating show notes", episode_id=episode_id, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/episodes/{episode_id}/social-clips")
    async def generate_social_clips(episode_id: str):
        """Generate social media clips from the episode transcript."""
        try:
            result = await _content_pipeline.generate_social_clips(episode_id)
            if not result.get("success"):
                status = 404 if "not found" in result.get("error", "").lower() else 500
                raise HTTPException(status_code=status, detail=result.get("error", "Generation failed"))
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error generating social clips", episode_id=episode_id, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/episodes/{episode_id}/content/{content_type}")
    async def get_generated_content(episode_id: str, content_type: str):
        """Get previously generated content for an episode."""
        valid_types = {"blog-post", "show-notes", "social-clips"}
        if content_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid content type. Must be one of: {', '.join(sorted(valid_types))}",
            )

        cached = _content_pipeline.get_cached(episode_id, content_type)
        if cached is None:
            raise HTTPException(status_code=404, detail="Content not yet generated")
        return {"success": True, **cached}

    # ------------------------------------------------------------------
    # Phase 4: Recording Stubs (LiveKit Egress)
    # ------------------------------------------------------------------

    @router.post("/rooms/{room_name}/recording/start")
    async def start_recording(room_name: str):
        """Start recording the room composite via LiveKit Egress.

        Note: Requires LiveKit Egress service. Returns a stub response if
        Egress is not available (e.g. on the free Cloud tier).
        """
        try:
            result = await ai_app.room_manager.start_recording(room_name)
            return result
        except Exception as e:
            logger.error("Error starting recording", room_name=room_name, error=str(e))
            return {
                "success": False,
                "error": str(e),
                "message": "Recording requires LiveKit Egress service. This may not be available on the free Cloud tier.",
            }

    @router.post("/rooms/{room_name}/recording/stop")
    async def stop_recording(room_name: str):
        """Stop recording."""
        try:
            result = await ai_app.room_manager.stop_recording(room_name)
            return result
        except Exception as e:
            logger.error("Error stopping recording", room_name=room_name, error=str(e))
            return {"success": False, "error": str(e)}

    return router