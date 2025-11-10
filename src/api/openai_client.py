"""
OpenAI client for AI Co-Host Bot
"""
import asyncio
from typing import Optional, Dict, Any, List

from openai import AsyncOpenAI

from .realtime_handler import RealtimeHandler
from ..config import get_logger, settings

logger = get_logger(__name__)


class OpenAIClient:
    """Main OpenAI client that manages split-stack architecture with mode switching"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.realtime_handler = RealtimeHandler()
        self.context_summary: str = ""
        self.conversation_history: List[Dict[str, str]] = []
        
        # Split-stack architecture modes
        self.current_mode = "passive"  # passive, speech-to-speech, ask-chatgpt
        self.transcription_active = False
        
        # Cost tracking for split-stack
        self.session_costs = {
            "stt_minutes": 0.0,
            "tts_minutes": 0.0,
            "tokens_in": 0,
            "tokens_out": 0,
            "requests": 0
        }
        
    async def connect_realtime(self) -> bool:
        """Connect to OpenAI Realtime API"""
        try:
            success = await self.realtime_handler.connect()
            if success:
                logger.info("Connected to OpenAI Realtime API")
            else:
                logger.error("Failed to connect to OpenAI Realtime API")
            return success
        except Exception as e:
            logger.error("Error connecting to Realtime API", error=str(e))
            return False
    
    async def disconnect_realtime(self):
        """Disconnect from OpenAI Realtime API"""
        await self.realtime_handler.disconnect()
        logger.info("Disconnected from OpenAI Realtime API")
    
    async def send_audio_to_realtime(self, audio_data: bytes):
        """Send audio data to Realtime API"""
        await self.realtime_handler.send_audio(audio_data)
    
    async def activate_ai_response(self):
        """Activate AI to generate a response"""
        await self.realtime_handler.create_response()
    
    async def cancel_ai_response(self):
        """Cancel ongoing AI response"""
        await self.realtime_handler.cancel_response()
    
    # Split-stack architecture methods
    async def set_mode(self, mode: str) -> bool:
        """Set operational mode for split-stack architecture"""
        valid_modes = ["passive", "speech-to-speech", "ask-chatgpt"]
        if mode not in valid_modes:
            logger.error("Invalid mode requested", mode=mode, valid_modes=valid_modes)
            return False
        
        previous_mode = self.current_mode
        self.current_mode = mode
        
        logger.info("Mode switched", 
                   previous_mode=previous_mode, 
                   new_mode=mode)
        
        # Handle mode-specific setup
        if mode == "passive":
            # Start transcription-only mode
            await self.start_transcription()
        elif mode == "speech-to-speech":
            # Ensure both STT and TTS capabilities are ready
            await self.start_transcription()
        elif mode == "ask-chatgpt":
            # Text-only mode, no audio processing needed
            pass
        
        return True
    
    async def start_transcription(self) -> bool:
        """Start STT transcription using gpt-4o-mini-transcribe"""
        try:
            if self.transcription_active:
                logger.debug("Transcription already active")
                return True
            
            # Connect to realtime API with transcription intent
            # Use the efficient realtime transcription endpoint
            success = await self.realtime_handler.connect_transcription_mode()
            
            if success:
                self.transcription_active = True
                logger.info("STT transcription started", model="gpt-4o-mini-transcribe")
            else:
                logger.error("Failed to start STT transcription")
            
            return success
            
        except Exception as e:
            logger.error("Error starting transcription", error=str(e))
            return False
    
    async def stop_transcription(self) -> bool:
        """Stop STT transcription"""
        try:
            if not self.transcription_active:
                logger.debug("Transcription not active")
                return True
            
            await self.realtime_handler.disconnect()
            self.transcription_active = False
            
            logger.info("STT transcription stopped")
            return True
            
        except Exception as e:
            logger.error("Error stopping transcription", error=str(e))
            return False
    
    async def transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio using STT in split-stack mode"""
        try:
            # Track STT usage for cost calculation
            audio_duration_minutes = len(audio_data) / (16000 * 2 * 60)  # Assume 16kHz mono 16-bit
            self.session_costs["stt_minutes"] += audio_duration_minutes
            
            # Use Whisper API for transcription (cost-efficient)
            response = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.wav", audio_data, "audio/wav"),
                response_format="text"
            )
            
            transcript = response.strip()
            
            logger.debug("Audio transcribed", 
                        duration_minutes=round(audio_duration_minutes, 3),
                        transcript_length=len(transcript))
            
            return transcript
            
        except Exception as e:
            logger.error("Error transcribing audio", error=str(e))
            return ""
    
    async def generate_tts(self, text: str, voice: str = "alloy") -> bytes:
        """Generate TTS audio using cost-efficient model"""
        try:
            if not text.strip():
                return b""
            
            # Estimate TTS duration for cost tracking (rough estimate: 150 words per minute)
            word_count = len(text.split())
            estimated_minutes = word_count / 150
            self.session_costs["tts_minutes"] += estimated_minutes
            
            # Generate TTS using OpenAI TTS API
            response = await self.client.audio.speech.create(
                model="tts-1",  # Cost-efficient TTS model
                voice=voice,
                input=text,
                response_format="wav"
            )
            
            audio_data = response.content
            
            logger.debug("TTS audio generated", 
                        text_length=len(text),
                        word_count=word_count,
                        estimated_minutes=round(estimated_minutes, 3),
                        audio_size=len(audio_data))
            
            return audio_data
            
        except Exception as e:
            logger.error("Error generating TTS", error=str(e))
            return b""
    
    async def speech_to_speech_interaction(self, audio_data: bytes) -> bytes:
        """Handle complete speech-to-speech interaction"""
        try:
            if self.current_mode != "speech-to-speech":
                logger.warning("Speech-to-speech called but not in correct mode", 
                              current_mode=self.current_mode)
                return b""
            
            # Step 1: Transcribe the input audio (STT)
            transcript = await self.transcribe_audio(audio_data)
            if not transcript:
                logger.warning("No transcript generated from audio")
                return b""
            
            # Step 2: Generate text response using reasoning model
            response_text = await self.get_text_completion(transcript)
            if not response_text:
                logger.warning("No text response generated")
                return b""
            
            # Step 3: Convert response to speech (TTS)
            response_audio = await self.generate_tts(response_text)
            
            # Add to conversation history
            self.add_conversation_turn("User", transcript)
            self.add_conversation_turn("AI", response_text)
            
            logger.info("Speech-to-speech interaction completed",
                       transcript_length=len(transcript),
                       response_length=len(response_text))
            
            return response_audio
            
        except Exception as e:
            logger.error("Error in speech-to-speech interaction", error=str(e))
            return b""
    
    def get_session_costs(self) -> Dict[str, float]:
        """Get current session cost breakdown"""
        # Cost rates (USD)
        stt_rate = 0.006  # per minute
        tts_rate = 0.015  # per minute  
        token_rate_in = 0.30 / 1000  # gpt-5-mini input per token
        token_rate_out = 0.60 / 1000  # gpt-5-mini output per token
        
        costs = {
            "stt_cost": self.session_costs["stt_minutes"] * stt_rate,
            "tts_cost": self.session_costs["tts_minutes"] * tts_rate,
            "token_cost": (self.session_costs["tokens_in"] * token_rate_in + 
                          self.session_costs["tokens_out"] * token_rate_out),
            "total_cost": 0.0
        }
        
        costs["total_cost"] = costs["stt_cost"] + costs["tts_cost"] + costs["token_cost"]
        
        return costs
    
    def reset_session_costs(self):
        """Reset session cost tracking"""
        self.session_costs = {
            "stt_minutes": 0.0,
            "tts_minutes": 0.0,
            "tokens_in": 0,
            "tokens_out": 0,
            "requests": 0
        }
        logger.debug("Session costs reset")

    async def generate_context_summary(self, conversation_text: str, max_tokens: int = 1000) -> str:
        """Generate a summary of conversation context using standard API"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-5-mini",  # Using GPT-5-mini for cost-efficient context summarization
                messages=[
                    {
                        "role": "system",
                        "content": "You are helping create a concise summary of a podcast conversation for an AI co-host. Extract key topics, main points, and important context that would help the AI co-host contribute meaningfully to the ongoing discussion. Focus on actionable insights and discussion topics."
                    },
                    {
                        "role": "user",
                        "content": f"Please summarize this conversation segment:\n\n{conversation_text}"
                    }
                ],
                max_completion_tokens=max_tokens,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content
            self.context_summary = summary
            
            logger.debug("Generated context summary", 
                        length=len(summary),
                        tokens=response.usage.total_tokens)
            
            return summary
            
        except Exception as e:
            logger.error("Error generating context summary", error=str(e))
            return "Error generating summary"
    
    async def extract_key_topics(self, text: str) -> List[str]:
        """Extract key topics from text for document retrieval"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract 3-5 key topics or concepts from the given text. Return them as a simple list, one topic per line. Focus on concrete topics that could be used for document retrieval."
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                max_completion_tokens=200,
                temperature=0.1
            )
            
            topics_text = response.choices[0].message.content
            topics = [topic.strip("- ").strip() for topic in topics_text.split('\n') if topic.strip()]
            
            logger.debug("Extracted key topics", topics=topics)
            return topics
            
        except Exception as e:
            logger.error("Error extracting topics", error=str(e))
            return []
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts using OpenAI embedding model"""
        try:
            response = await self.client.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            
            embeddings = [item.embedding for item in response.data]
            
            logger.debug("Generated embeddings", 
                        count=len(embeddings),
                        tokens=response.usage.total_tokens)
            
            return embeddings
            
        except Exception as e:
            logger.error("Error generating embeddings", error=str(e))
            return []
    
    async def enhance_context_with_documents(self, current_context: str, relevant_docs: List[str]) -> str:
        """Enhance conversation context with relevant document excerpts"""
        if not relevant_docs:
            return current_context
        
        try:
            doc_context = "\n\n".join(relevant_docs)
            
            response = await self.client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are helping prepare context for an AI podcast co-host. You have the current conversation context and some relevant document excerpts. Create an enhanced context summary that weaves together the conversation and document information in a way that would help the AI co-host provide informed, relevant contributions."
                    },
                    {
                        "role": "user",
                        "content": f"Current conversation context:\n{current_context}\n\nRelevant document excerpts:\n{doc_context}\n\nPlease create an enhanced context summary."
                    }
                ],
                max_completion_tokens=2000,
                temperature=0.3
            )
            
            enhanced_context = response.choices[0].message.content
            
            logger.debug("Enhanced context with documents",
                        original_length=len(current_context),
                        enhanced_length=len(enhanced_context))
            
            return enhanced_context
            
        except Exception as e:
            logger.error("Error enhancing context", error=str(e))
            return current_context
    
    def add_conversation_turn(self, speaker: str, text: str):
        """Add a conversation turn to history"""
        self.conversation_history.append({
            "speaker": speaker,
            "text": text,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        # Keep only last 50 turns to manage memory
        if len(self.conversation_history) > 50:
            self.conversation_history = self.conversation_history[-50:]
        
        logger.debug("Added conversation turn", 
                    speaker=speaker,
                    text_length=len(text),
                    total_turns=len(self.conversation_history))
    
    def get_recent_conversation_text(self, minutes: int = 15) -> str:
        """Get recent conversation as text"""
        current_time = asyncio.get_event_loop().time()
        cutoff_time = current_time - (minutes * 60)
        
        recent_turns = [
            turn for turn in self.conversation_history 
            if turn["timestamp"] > cutoff_time
        ]
        
        conversation_text = "\n".join([
            f"{turn['speaker']}: {turn['text']}"
            for turn in recent_turns
        ])
        
        return conversation_text
    
    async def get_text_completion(self, prompt: str) -> str:
        """Get text completion from ChatGPT with cost tracking"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are ChatGPT, a helpful AI assistant. Provide clear, concise, and accurate responses to user questions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_completion_tokens=1000,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            
            # Track token usage for cost calculation
            if response.usage:
                self.session_costs["tokens_in"] += response.usage.prompt_tokens
                self.session_costs["tokens_out"] += response.usage.completion_tokens
                self.session_costs["requests"] += 1
            
            logger.debug("Generated text completion", 
                        prompt_length=len(prompt),
                        response_length=len(content),
                        tokens_in=response.usage.prompt_tokens if response.usage else 0,
                        tokens_out=response.usage.completion_tokens if response.usage else 0,
                        total_tokens=response.usage.total_tokens if response.usage else 0)
            
            return content
            
        except Exception as e:
            logger.error("Error getting text completion", error=str(e), prompt=prompt[:100])
            raise e
    
    # Callback setters for realtime handler
    def set_audio_callback(self, callback):
        """Set callback for AI-generated audio"""
        self.realtime_handler.set_audio_callback(callback)
    
    def set_transcript_callback(self, callback):
        """Set callback for transcription updates"""
        self.realtime_handler.set_transcript_callback(callback)
    
    def set_response_callback(self, callback):
        """Set callback for completed responses"""
        self.realtime_handler.set_response_callback(callback)
    
    def set_error_callback(self, callback):
        """Set callback for errors"""
        self.realtime_handler.set_error_callback(callback)
    
    def set_status_callback(self, callback):
        """Set callback for status updates"""
        self.realtime_handler.set_status_callback(callback)
    
    @property
    def status(self) -> Dict[str, Any]:
        """Get current client status with split-stack information"""
        return {
            "realtime_status": self.realtime_handler.status,
            "context_summary_length": len(self.context_summary),
            "conversation_turns": len(self.conversation_history),
            "recent_conversation_length": len(self.get_recent_conversation_text()),
            
            # Split-stack architecture status
            "current_mode": self.current_mode,
            "transcription_active": self.transcription_active,
            "session_costs": self.get_session_costs(),
            "cost_summary": self.session_costs
        }