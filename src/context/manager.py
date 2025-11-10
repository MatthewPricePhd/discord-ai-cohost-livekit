"""
Main context management system for AI Co-Host Bot
"""
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import deque

from .summarizer import ConversationSummarizer
from .retrieval import DocumentRetriever
from .notes import NoteTaker
from ..config import get_logger, settings

logger = get_logger(__name__)


class ContextManager:
    """
    Intelligent context management system that handles:
    - Conversation history and summarization
    - Document retrieval based on current topics
    - Context window optimization for GPT-5
    - Note-taking and key point extraction
    """
    
    def __init__(self):
        self.summarizer = ConversationSummarizer()
        self.retriever = DocumentRetriever()
        self.note_taker = NoteTaker()
        
        # Context storage
        self.conversation_history: deque = deque(maxlen=100)  # Last 100 turns
        self.current_context: str = ""
        self.document_context: str = ""
        self.key_notes: List[Dict[str, Any]] = []
        
        # Context management settings
        self.max_context_tokens = settings.max_context_tokens
        self.context_refresh_interval = 30  # seconds
        self.summary_trigger_turns = 10  # Create summary after X new turns
        
        # Tracking variables
        self.last_context_refresh = datetime.utcnow()
        self.turns_since_summary = 0
        self.current_topics: List[str] = []
        
        # Start background context management
        asyncio.create_task(self._background_context_refresh())
    
    async def add_conversation_turn(self, speaker: str, text: str, timestamp: Optional[datetime] = None) -> None:
        """
        Add a new conversation turn and trigger context updates
        
        Args:
            speaker: Who is speaking (User, AI, etc.)
            text: The spoken text
            timestamp: When this was said (defaults to now)
        """
        try:
            if not timestamp:
                timestamp = datetime.utcnow()
            
            turn = {
                "speaker": speaker,
                "text": text,
                "timestamp": timestamp,
                "id": len(self.conversation_history)
            }
            
            self.conversation_history.append(turn)
            self.turns_since_summary += 1
            
            logger.debug("Added conversation turn",
                        speaker=speaker,
                        text_length=len(text),
                        total_turns=len(self.conversation_history))
            
            # Extract key points if significant content
            if len(text) > 50:  # Only process substantial content
                await self._extract_key_points(turn)
            
            # Trigger context refresh if needed
            if self._should_refresh_context():
                await self.refresh_context()
            
        except Exception as e:
            logger.error("Error adding conversation turn", 
                        speaker=speaker,
                        error=str(e))
    
    async def refresh_context(self) -> Dict[str, Any]:
        """
        Refresh the current context by:
        1. Summarizing recent conversation
        2. Extracting current topics
        3. Retrieving relevant documents
        4. Building optimized context window
        """
        try:
            logger.debug("Refreshing context")
            
            # Get recent conversation text
            recent_conversation = self._get_recent_conversation(minutes=15)
            
            if not recent_conversation:
                return self._get_current_context_info()
            
            # Generate summary of recent conversation
            summary = await self.summarizer.summarize_conversation(recent_conversation)
            
            # Extract current topics
            topics = await self.summarizer.extract_topics(recent_conversation)
            self.current_topics = topics
            
            # Retrieve relevant documents
            relevant_docs = await self.retriever.get_relevant_documents(
                topics=topics,
                conversation_context=recent_conversation[:2000]  # Limit for efficiency
            )
            
            # Build document context
            self.document_context = self._build_document_context(relevant_docs)
            
            # Create comprehensive context
            self.current_context = self._build_comprehensive_context(
                conversation_summary=summary,
                recent_conversation=recent_conversation[-3000:],  # Last ~3000 chars
                document_context=self.document_context
            )
            
            # Update tracking
            self.last_context_refresh = datetime.utcnow()
            self.turns_since_summary = 0
            
            context_info = self._get_current_context_info()
            
            logger.info("Context refreshed successfully",
                       context_tokens=self._estimate_tokens(self.current_context),
                       topics=len(topics),
                       relevant_docs=len(relevant_docs),
                       key_notes=len(self.key_notes))
            
            return context_info
            
        except Exception as e:
            logger.error("Error refreshing context", error=str(e))
            return self._get_current_context_info()
    
    async def get_context_for_ai(self) -> str:
        """
        Get the current context optimized for AI consumption
        
        Returns:
            Formatted context string for GPT-5 Realtime API
        """
        try:
            # Ensure we have fresh context
            if self._should_refresh_context():
                await self.refresh_context()
            
            # Build AI-optimized context
            context_parts = []
            
            # System context and personality
            context_parts.append(self._get_system_context())
            
            # Pre-loaded document summaries
            if self.document_context:
                context_parts.append(f"## Reference Materials:\n{self.document_context}")
            
            # Key conversation notes
            if self.key_notes:
                notes_text = self._format_key_notes()
                context_parts.append(f"## Key Discussion Points:\n{notes_text}")
            
            # Current conversation context
            if self.current_context:
                context_parts.append(f"## Current Context:\n{self.current_context}")
            
            full_context = "\n\n".join(context_parts)
            
            # Ensure we don't exceed token limit
            if self._estimate_tokens(full_context) > self.max_context_tokens * 0.9:
                full_context = self._truncate_context(full_context)
            
            return full_context
            
        except Exception as e:
            logger.error("Error building AI context", error=str(e))
            return self._get_system_context()  # Fallback to basic context
    
    async def get_context_summary_for_web(self) -> Dict[str, Any]:
        """Get context summary for web dashboard display"""
        try:
            return {
                "current_topics": self.current_topics,
                "conversation_turns": len(self.conversation_history),
                "key_notes_count": len(self.key_notes),
                "last_refresh": self.last_context_refresh.isoformat(),
                "context_length": len(self.current_context),
                "estimated_tokens": self._estimate_tokens(self.current_context),
                "recent_summary": await self._get_recent_summary()
            }
            
        except Exception as e:
            logger.error("Error getting context summary for web", error=str(e))
            return {}
    
    def _should_refresh_context(self) -> bool:
        """Determine if context should be refreshed"""
        time_since_refresh = datetime.utcnow() - self.last_context_refresh
        
        return (
            time_since_refresh.total_seconds() > self.context_refresh_interval or
            self.turns_since_summary >= self.summary_trigger_turns
        )
    
    def _get_recent_conversation(self, minutes: int = 15) -> str:
        """Get recent conversation as formatted text"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        recent_turns = [
            turn for turn in self.conversation_history
            if turn["timestamp"] > cutoff_time
        ]
        
        if not recent_turns:
            return ""
        
        formatted_turns = []
        for turn in recent_turns:
            timestamp_str = turn["timestamp"].strftime("%H:%M")
            formatted_turns.append(f"[{timestamp_str}] {turn['speaker']}: {turn['text']}")
        
        return "\n".join(formatted_turns)
    
    def _build_document_context(self, relevant_docs: List[Dict[str, Any]]) -> str:
        """Build context from relevant document chunks"""
        if not relevant_docs:
            return ""
        
        doc_parts = []
        for doc in relevant_docs[:5]:  # Limit to top 5 most relevant
            title = doc.get("metadata", {}).get("document_title", "Document")
            text = doc.get("text", "")
            similarity = doc.get("similarity", 0)
            
            if text:
                doc_parts.append(f"**{title}** (relevance: {similarity:.2f}):\n{text[:500]}...")
        
        return "\n\n".join(doc_parts)
    
    def _build_comprehensive_context(self, 
                                   conversation_summary: str,
                                   recent_conversation: str,
                                   document_context: str) -> str:
        """Build comprehensive context from all sources"""
        context_parts = []
        
        if conversation_summary:
            context_parts.append(f"**Conversation Summary:**\n{conversation_summary}")
        
        if recent_conversation:
            context_parts.append(f"**Recent Conversation:**\n{recent_conversation}")
        
        if document_context:
            context_parts.append(f"**Relevant Documents:**\n{document_context}")
        
        return "\n\n".join(context_parts)
    
    def _get_system_context(self) -> str:
        """Get system context and AI personality"""
        return """You are an intelligent AI co-host for a podcast recording session. Your role is to:

1. Listen carefully to the ongoing conversation and understand the context
2. When activated, provide thoughtful insights, ask engaging questions, or contribute relevant information
3. Reference the conversation history and any uploaded research materials when appropriate
4. Keep responses natural, conversational, and appropriately timed for audio format
5. Help maintain an engaging flow of conversation

Communication Guidelines:
- Speak naturally as you would in a real conversation
- Keep responses concise (typically 15-45 seconds when spoken)
- Reference previous points when relevant to show you're following along
- Ask thoughtful follow-up questions to deepen the discussion
- Share relevant insights from the research materials when appropriate

Remember: You are a co-host, not a host. Your job is to enhance the conversation, not dominate it."""
    
    async def _extract_key_points(self, turn: Dict[str, Any]) -> None:
        """Extract key points from a conversation turn"""
        try:
            key_points = await self.note_taker.extract_key_points(turn["text"])
            
            for point in key_points:
                note = {
                    "text": point,
                    "speaker": turn["speaker"],
                    "timestamp": turn["timestamp"],
                    "turn_id": turn["id"]
                }
                
                self.key_notes.append(note)
            
            # Keep only recent key notes (last 50)
            if len(self.key_notes) > 50:
                self.key_notes = self.key_notes[-50:]
                
        except Exception as e:
            logger.debug("Error extracting key points", error=str(e))
    
    def _format_key_notes(self) -> str:
        """Format key notes for context"""
        if not self.key_notes:
            return ""
        
        # Group by speaker and time
        recent_notes = self.key_notes[-10:]  # Last 10 key points
        formatted_notes = []
        
        for note in recent_notes:
            time_str = note["timestamp"].strftime("%H:%M")
            formatted_notes.append(f"- [{time_str}] {note['speaker']}: {note['text']}")
        
        return "\n".join(formatted_notes)
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 characters for English)"""
        return len(text) // 4
    
    def _truncate_context(self, context: str) -> str:
        """Truncate context to fit within token limits"""
        max_chars = self.max_context_tokens * 4 * 0.9  # 90% of limit
        
        if len(context) <= max_chars:
            return context
        
        # Try to truncate at section boundaries
        sections = context.split("\n\n")
        truncated_sections = []
        current_length = 0
        
        for section in sections:
            if current_length + len(section) <= max_chars:
                truncated_sections.append(section)
                current_length += len(section) + 2  # +2 for \n\n
            else:
                break
        
        result = "\n\n".join(truncated_sections)
        
        # If still too long, do hard truncation
        if len(result) > max_chars:
            result = result[:int(max_chars)]
        
        return result
    
    def _get_current_context_info(self) -> Dict[str, Any]:
        """Get current context information"""
        return {
            "conversation_turns": len(self.conversation_history),
            "current_topics": self.current_topics,
            "context_length": len(self.current_context),
            "estimated_tokens": self._estimate_tokens(self.current_context),
            "key_notes": len(self.key_notes),
            "last_refresh": self.last_context_refresh.isoformat(),
            "turns_since_summary": self.turns_since_summary
        }
    
    async def _get_recent_summary(self) -> str:
        """Get a brief summary of recent activity"""
        if not self.conversation_history:
            return "No conversation yet"
        
        recent_text = self._get_recent_conversation(minutes=5)
        if not recent_text:
            return "No recent activity"
        
        try:
            return await self.summarizer.create_brief_summary(recent_text)
        except:
            return "Recent conversation ongoing"
    
    async def _background_context_refresh(self):
        """Background task for periodic context refresh"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                if self._should_refresh_context():
                    await self.refresh_context()
                    
            except Exception as e:
                logger.error("Error in background context refresh", error=str(e))
                await asyncio.sleep(60)  # Wait before retrying