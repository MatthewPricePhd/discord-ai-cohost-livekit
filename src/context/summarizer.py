"""
Conversation summarization functionality
"""
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..api.openai_client import OpenAIClient
from ..config import get_logger

logger = get_logger(__name__)


class ConversationSummarizer:
    """Handles conversation summarization and topic extraction"""
    
    def __init__(self):
        self.openai_client = None  # Will be injected or created as needed
    
    async def _get_openai_client(self) -> OpenAIClient:
        """Get OpenAI client instance"""
        if not self.openai_client:
            from ..api.openai_client import OpenAIClient
            self.openai_client = OpenAIClient()
        return self.openai_client
    
    async def summarize_conversation(self, conversation_text: str, max_length: int = 1000) -> str:
        """
        Create a summary of conversation content
        
        Args:
            conversation_text: The conversation to summarize
            max_length: Maximum length of summary in characters
            
        Returns:
            Summarized text
        """
        try:
            if not conversation_text or len(conversation_text.strip()) < 100:
                return "No substantial conversation to summarize."
            
            client = await self._get_openai_client()
            
            # Create summary prompt
            prompt = f"""Summarize this podcast conversation segment in a way that would help an AI co-host understand the key topics, main points, and current discussion flow. Focus on:

1. Main topics being discussed
2. Key points made by each speaker
3. Questions raised or areas of interest
4. Current direction of the conversation

Keep the summary concise but informative (around {max_length // 4} words).

Conversation:
{conversation_text}"""
            
            summary = await client.client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at summarizing podcast conversations for AI co-hosts."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_length // 3,  # Rough token estimation
                temperature=0.3
            )
            
            result = summary.choices[0].message.content.strip()
            
            logger.debug("Conversation summarized",
                        original_length=len(conversation_text),
                        summary_length=len(result))
            
            return result
            
        except Exception as e:
            logger.error("Error summarizing conversation", error=str(e))
            return self._create_fallback_summary(conversation_text, max_length)
    
    async def extract_topics(self, conversation_text: str, max_topics: int = 8) -> List[str]:
        """
        Extract key topics from conversation
        
        Args:
            conversation_text: The conversation to analyze
            max_topics: Maximum number of topics to return
            
        Returns:
            List of topic strings
        """
        try:
            if not conversation_text or len(conversation_text.strip()) < 50:
                return []
            
            client = await self._get_openai_client()
            
            prompt = f"""Extract the main topics and themes from this podcast conversation. Focus on:

1. Specific subjects being discussed
2. Concepts, technologies, or ideas mentioned
3. People, places, or organizations referenced
4. Questions or problems being explored

Return {max_topics} or fewer topics as a simple list, one topic per line. Each topic should be 2-5 words.

Conversation:
{conversation_text[:2000]}"""  # Limit input for efficiency
            
            response = await client.client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting topics from conversations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.2
            )
            
            topics_text = response.choices[0].message.content.strip()
            
            # Parse topics from response
            topics = []
            for line in topics_text.split('\n'):
                topic = line.strip().strip('-').strip('*').strip()
                if topic and len(topic) > 2:
                    topics.append(topic)
            
            # Limit to max_topics
            topics = topics[:max_topics]
            
            logger.debug("Topics extracted",
                        topic_count=len(topics),
                        topics=topics)
            
            return topics
            
        except Exception as e:
            logger.error("Error extracting topics", error=str(e))
            return self._extract_fallback_topics(conversation_text, max_topics)
    
    async def create_brief_summary(self, text: str, max_words: int = 30) -> str:
        """
        Create a very brief summary for status display
        
        Args:
            text: Text to summarize
            max_words: Maximum words in summary
            
        Returns:
            Brief summary string
        """
        try:
            if not text or len(text.strip()) < 20:
                return "Brief conversation"
            
            client = await self._get_openai_client()
            
            prompt = f"""Create a very brief summary of this conversation in {max_words} words or less. Focus on the main topic being discussed right now.

Text: {text[:1000]}"""
            
            response = await client.client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "You create very concise summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_words * 2,  # Rough buffer
                temperature=0.2
            )
            
            summary = response.choices[0].message.content.strip()
            
            # Ensure it's not too long
            words = summary.split()
            if len(words) > max_words:
                summary = ' '.join(words[:max_words]) + '...'
            
            return summary
            
        except Exception as e:
            logger.debug("Error creating brief summary", error=str(e))
            return self._create_simple_summary(text, max_words)
    
    async def identify_key_moments(self, conversation_text: str) -> List[Dict[str, Any]]:
        """
        Identify key moments or important points in the conversation
        
        Args:
            conversation_text: Full conversation text
            
        Returns:
            List of key moments with timestamps and descriptions
        """
        try:
            if not conversation_text or len(conversation_text.strip()) < 200:
                return []
            
            client = await self._get_openai_client()
            
            prompt = f"""Identify the key moments, important insights, or significant points in this podcast conversation. Look for:

1. Important insights or revelations
2. Interesting questions raised
3. Key decisions or conclusions
4. Moments that changed the conversation direction
5. Notable quotes or statements

Format as a list with timestamp (if available) and description.

Conversation:
{conversation_text}"""
            
            response = await client.client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "You identify key moments in conversations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.3
            )
            
            moments_text = response.choices[0].message.content.strip()
            
            # Parse the response into structured data
            moments = self._parse_key_moments(moments_text)
            
            logger.debug("Key moments identified", count=len(moments))
            
            return moments
            
        except Exception as e:
            logger.error("Error identifying key moments", error=str(e))
            return []
    
    def _create_fallback_summary(self, text: str, max_length: int) -> str:
        """Create a simple fallback summary when AI summarization fails"""
        if not text:
            return "No conversation content available."
        
        # Simple extractive summarization - take first and last parts
        words = text.split()
        
        if len(words) < 50:
            return text
        
        # Take first quarter and last quarter
        quarter = len(words) // 4
        summary_words = words[:quarter] + ["..."] + words[-quarter:]
        
        summary = " ".join(summary_words)
        
        # Truncate if still too long
        if len(summary) > max_length:
            summary = summary[:max_length - 3] + "..."
        
        return summary
    
    def _extract_fallback_topics(self, text: str, max_topics: int) -> List[str]:
        """Extract topics using simple keyword analysis when AI extraction fails"""
        if not text:
            return []
        
        # Simple topic extraction using word frequency
        # Remove common words and find frequent terms
        
        # Convert to lowercase and split
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Common stop words to ignore
        stop_words = {
            'the', 'and', 'but', 'for', 'are', 'with', 'this', 'that', 'they',
            'have', 'had', 'was', 'were', 'been', 'will', 'can', 'could', 'should',
            'would', 'said', 'say', 'says', 'like', 'just', 'now', 'well', 'also',
            'really', 'think', 'know', 'going', 'get', 'got', 'want', 'way', 'time'
        }
        
        # Count word frequencies
        word_freq = {}
        for word in words:
            if word not in stop_words and len(word) > 3:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get most frequent words as topics
        topics = sorted(word_freq.keys(), key=word_freq.get, reverse=True)[:max_topics]
        
        # Capitalize and return
        return [topic.title() for topic in topics]
    
    def _create_simple_summary(self, text: str, max_words: int) -> str:
        """Create a simple summary without AI"""
        if not text:
            return "No activity"
        
        # Take first sentence or first few words
        sentences = text.split('.')
        if sentences:
            first_sentence = sentences[0].strip()
            words = first_sentence.split()
            
            if len(words) <= max_words:
                return first_sentence
            else:
                return ' '.join(words[:max_words]) + '...'
        
        return text[:50] + '...' if len(text) > 50 else text
    
    def _parse_key_moments(self, moments_text: str) -> List[Dict[str, Any]]:
        """Parse AI response into structured key moments"""
        moments = []
        
        lines = moments_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Remove bullet points or numbers
            line = re.sub(r'^[\d\.\-\*\s]+', '', line)
            
            if len(line) > 10:  # Only meaningful content
                moment = {
                    "description": line,
                    "timestamp": datetime.utcnow().isoformat(),
                    "type": "key_point"
                }
                moments.append(moment)
        
        return moments[:10]  # Limit to 10 key moments