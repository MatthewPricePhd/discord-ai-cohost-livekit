"""
Note-taking and key point extraction for conversations
"""
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..config import get_logger

logger = get_logger(__name__)


class NoteTaker:
    """Extracts and manages key points from conversations"""
    
    def __init__(self):
        self.openai_client = None  # Will be injected as needed
        
        # Pattern for identifying key phrases
        self.key_phrase_patterns = [
            r'\b(?:the key|main|important|crucial|significant|primary)\s+(?:point|issue|question|topic|problem)\b',
            r'\b(?:what|how|why|when|where)\s+(?:is|are|do|did|can|could|should|would)\b',
            r'\b(?:let me|i want to|we need to|the goal is)\b',
            r'\b(?:conclusion|summary|takeaway|insight|lesson)\b',
            r'\b(?:question|problem|challenge|opportunity|solution)\b'
        ]
        
        # Common filler words to ignore
        self.filler_words = {
            'um', 'uh', 'er', 'ah', 'like', 'you know', 'sort of', 'kind of',
            'basically', 'actually', 'literally', 'obviously', 'clearly',
            'i mean', 'well', 'so', 'anyway', 'right', 'okay', 'alright'
        }
    
    async def extract_key_points(self, text: str) -> List[str]:
        """
        Extract key points from conversation text
        
        Args:
            text: The conversation text to analyze
            
        Returns:
            List of key point strings
        """
        try:
            if not text or len(text.strip()) < 20:
                return []
            
            # Try AI-based extraction first
            ai_points = await self._extract_with_ai(text)
            if ai_points:
                return ai_points
            
            # Fallback to pattern-based extraction
            return self._extract_with_patterns(text)
            
        except Exception as e:
            logger.error("Error extracting key points", error=str(e))
            return self._extract_with_patterns(text)
    
    async def identify_questions(self, text: str) -> List[str]:
        """
        Identify questions raised in the conversation
        
        Args:
            text: The conversation text
            
        Returns:
            List of questions found
        """
        try:
            questions = []
            
            # Find sentences ending with question marks
            question_sentences = re.findall(r'[^.!?]*\?', text)
            
            for question in question_sentences:
                clean_question = question.strip()
                if len(clean_question) > 10:  # Ignore very short questions
                    questions.append(clean_question)
            
            # Also look for implied questions
            implied_patterns = [
                r'\b(?:i wonder|wondering|curious about|question is|ask)\s+[^.!?]{10,}',
                r'\b(?:how do|why do|what if|when will|where can)\s+[^.!?]{5,}',
                r'\b(?:does anyone know|anyone have thoughts on|what are your thoughts)\s+[^.!?]{5,}'
            ]
            
            for pattern in implied_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if match not in questions:
                        questions.append(match.strip())
            
            return questions[:5]  # Limit to 5 questions
            
        except Exception as e:
            logger.error("Error identifying questions", error=str(e))
            return []
    
    async def extract_action_items(self, text: str) -> List[str]:
        """
        Extract action items or next steps from conversation
        
        Args:
            text: The conversation text
            
        Returns:
            List of action items
        """
        try:
            action_patterns = [
                r'\b(?:need to|should|must|have to|going to|will|plan to)\s+[^.!?]{10,}[.!?]',
                r'\b(?:next step|action item|to do|follow up|homework)\s*:?\s*[^.!?]{5,}',
                r'\b(?:let\'s|we should|we need to|we\'ll)\s+[^.!?]{5,}[.!?]'
            ]
            
            action_items = []
            
            for pattern in action_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    clean_action = match.strip()
                    if len(clean_action) > 10:
                        action_items.append(clean_action)
            
            # Remove duplicates and limit
            unique_actions = list(dict.fromkeys(action_items))
            return unique_actions[:5]
            
        except Exception as e:
            logger.error("Error extracting action items", error=str(e))
            return []
    
    async def categorize_content(self, text: str) -> Dict[str, List[str]]:
        """
        Categorize conversation content into different types
        
        Args:
            text: The conversation text
            
        Returns:
            Dict with categorized content
        """
        try:
            result = {
                "key_points": await self.extract_key_points(text),
                "questions": await self.identify_questions(text),
                "action_items": await self.extract_action_items(text),
                "topics": self._extract_topics_simple(text),
                "insights": self._extract_insights(text)
            }
            
            return result
            
        except Exception as e:
            logger.error("Error categorizing content", error=str(e))
            return {
                "key_points": [],
                "questions": [],
                "action_items": [],
                "topics": [],
                "insights": []
            }
    
    async def _extract_with_ai(self, text: str) -> List[str]:
        """Use AI to extract key points"""
        try:
            if len(text) < 100:  # Too short for AI processing
                return []
            
            from openai import AsyncOpenAI
            from ..config import settings
            client = AsyncOpenAI(api_key=settings.openai_api_key)

            prompt = f"""Extract 3-5 key points from this conversation segment. Focus on:
1. Important insights or conclusions
2. Significant questions raised
3. Key decisions or agreements
4. Notable information shared

Return each key point as a concise bullet point (1-2 sentences max).

Conversation:
{text[:1500]}"""  # Limit input length

            response = await client.chat.completions.create(
                model="gpt-5.3-instant",
                messages=[
                    {"role": "system", "content": "You extract key points from conversations concisely."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=200,
                temperature=0.3
            )
            
            points_text = response.choices[0].message.content.strip()
            
            # Parse the response
            points = []
            for line in points_text.split('\n'):
                line = line.strip()
                # Remove bullet points and numbers
                line = re.sub(r'^[\d\.\-\*\s]+', '', line)
                if line and len(line) > 10:
                    points.append(line)
            
            return points[:5]  # Limit to 5 points
            
        except Exception as e:
            logger.debug("AI key point extraction failed", error=str(e))
            return []
    
    def _extract_with_patterns(self, text: str) -> List[str]:
        """Extract key points using pattern matching"""
        try:
            key_points = []
            sentences = re.split(r'[.!?]+', text)
            
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 20:  # Skip short sentences
                    continue
                
                # Check if sentence matches key phrase patterns
                for pattern in self.key_phrase_patterns:
                    if re.search(pattern, sentence, re.IGNORECASE):
                        clean_sentence = self._clean_sentence(sentence)
                        if clean_sentence:
                            key_points.append(clean_sentence)
                        break
            
            # Remove duplicates and limit
            unique_points = list(dict.fromkeys(key_points))
            return unique_points[:5]
            
        except Exception as e:
            logger.error("Error in pattern-based extraction", error=str(e))
            return []
    
    def _extract_topics_simple(self, text: str) -> List[str]:
        """Simple topic extraction using noun phrases"""
        try:
            # Find potential topics using capitalized words and noun phrases
            topics = []
            
            # Find capitalized words (potential proper nouns/topics)
            capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', text)
            
            # Count frequency and filter
            word_freq = {}
            for word in capitalized_words:
                if len(word) > 3 and word not in ['The', 'This', 'That', 'When', 'Where', 'What', 'How', 'Why']:
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # Get most frequent as topics
            topics = [word for word, freq in sorted(word_freq.items(), key=lambda x: x[1], reverse=True) if freq > 1]
            
            return topics[:5]
            
        except Exception as e:
            logger.error("Error extracting simple topics", error=str(e))
            return []
    
    def _extract_insights(self, text: str) -> List[str]:
        """Extract insights and conclusions"""
        try:
            insight_patterns = [
                r'\b(?:i think|i believe|it seems|appears that|turns out|realized|discovered)\s+[^.!?]{10,}[.!?]',
                r'\b(?:insight|conclusion|learning|takeaway|understanding)\s*:?\s*[^.!?]{10,}[.!?]',
                r'\b(?:what this means|the implication|this suggests|this indicates)\s+[^.!?]{10,}[.!?]'
            ]
            
            insights = []
            
            for pattern in insight_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    clean_insight = self._clean_sentence(match)
                    if clean_insight and len(clean_insight) > 15:
                        insights.append(clean_insight)
            
            return list(dict.fromkeys(insights))[:3]  # Unique insights, max 3
            
        except Exception as e:
            logger.error("Error extracting insights", error=str(e))
            return []
    
    def prioritize_notes(self, notes: List[str], current_topics: List[str]) -> List[str]:
        """
        Rank notes by relevance to current topics using keyword overlap.

        Args:
            notes: List of note strings
            current_topics: List of current discussion topic strings

        Returns:
            Notes sorted by relevance (most relevant first)
        """
        if not notes or not current_topics:
            return notes

        topic_words = set()
        for topic in current_topics:
            topic_words.update(word.lower() for word in topic.split() if len(word) > 2)

        def score(note: str) -> int:
            note_words = set(word.lower() for word in note.split() if len(word) > 2)
            return len(note_words & topic_words)

        return sorted(notes, key=score, reverse=True)

    def _clean_sentence(self, sentence: str) -> str:
        """Clean and normalize a sentence"""
        try:
            # Remove filler words at the beginning
            words = sentence.split()
            cleaned_words = []
            
            skip_fillers = True
            for word in words:
                word_lower = word.lower().strip('.,!?')
                
                if skip_fillers and word_lower in self.filler_words:
                    continue
                else:
                    skip_fillers = False
                    cleaned_words.append(word)
            
            if not cleaned_words:
                return ""
            
            cleaned_sentence = " ".join(cleaned_words)
            
            # Capitalize first letter
            if cleaned_sentence:
                cleaned_sentence = cleaned_sentence[0].upper() + cleaned_sentence[1:]
            
            # Ensure it ends with punctuation
            if cleaned_sentence and not cleaned_sentence[-1] in '.!?':
                cleaned_sentence += '.'
            
            return cleaned_sentence
            
        except Exception as e:
            logger.error("Error cleaning sentence", error=str(e))
            return sentence
    
    def create_note_summary(self, notes: List[Dict[str, Any]]) -> str:
        """Create a formatted summary of notes"""
        try:
            if not notes:
                return "No notes available."
            
            # Group notes by type if available
            categorized = {}
            for note in notes:
                note_type = note.get("type", "general")
                if note_type not in categorized:
                    categorized[note_type] = []
                categorized[note_type].append(note)
            
            summary_parts = []
            
            for note_type, type_notes in categorized.items():
                if note_type != "general":
                    summary_parts.append(f"\n**{note_type.title()}:**")
                
                for note in type_notes[:3]:  # Limit per type
                    text = note.get("text", "")
                    if text:
                        summary_parts.append(f"• {text}")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            logger.error("Error creating note summary", error=str(e))
            return "Error creating summary."


async def extract_key_points(turns: List[Dict[str, Any]], openai_client) -> List[str]:
    """
    Module-level function to extract notable facts/claims/data points from turns.

    Args:
        turns: List of conversation turn dicts with "speaker" and "text" keys
        openai_client: An AsyncOpenAI client instance

    Returns:
        List of key point strings
    """
    if not turns:
        return []

    conversation_text = "\n".join(
        f"{t.get('speaker', 'Unknown')}: {t.get('text', '')}" for t in turns
    )

    if len(conversation_text.strip()) < 50:
        return []

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-5.3-instant",
            messages=[
                {"role": "system", "content": "Extract notable facts, claims, and data points from this conversation. Return one per line, concise."},
                {"role": "user", "content": conversation_text[:3000]}
            ],
            max_completion_tokens=300,
            temperature=0.2
        )

        points_text = response.choices[0].message.content.strip()
        points = []
        for line in points_text.split("\n"):
            line = re.sub(r'^[\d\.\-\*\s]+', '', line).strip()
            if line and len(line) > 10:
                points.append(line)
        return points[:10]

    except Exception as e:
        logger.error("Error in module-level extract_key_points", error=str(e))
        return []


def prioritize_notes(notes: List[str], current_topics: List[str]) -> List[str]:
    """
    Module-level function to rank notes by keyword overlap with current topics.

    Args:
        notes: List of note strings
        current_topics: List of current discussion topic strings

    Returns:
        Notes sorted by relevance (most relevant first)
    """
    if not notes or not current_topics:
        return notes

    topic_words = set()
    for topic in current_topics:
        topic_words.update(word.lower() for word in topic.split() if len(word) > 2)

    def score(note: str) -> int:
        note_words = set(word.lower() for word in note.split() if len(word) > 2)
        return len(note_words & topic_words)

    return sorted(notes, key=score, reverse=True)