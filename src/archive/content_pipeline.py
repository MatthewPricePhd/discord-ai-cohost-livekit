"""Post-episode content pipeline.

Uses the TranscriptStore to retrieve episode transcripts, then calls OpenAI
to generate blog posts, show notes, and social clips.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from ..config import get_logger, settings
from .store import TranscriptStore

logger = get_logger(__name__)


class ContentPipeline:
    """Generate post-episode content from transcripts via LLM."""

    def __init__(self, store: Optional[TranscriptStore] = None) -> None:
        self._store = store or TranscriptStore()
        self._client: Optional[AsyncOpenAI] = None
        # Cache of generated content keyed by (episode_id, content_type)
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    # ------------------------------------------------------------------
    # Transcript helpers
    # ------------------------------------------------------------------

    def _get_transcript_text(self, episode_id: str) -> Optional[str]:
        """Get the full transcript as plain text for prompting."""
        episode = self._store.get_episode(episode_id)
        if not episode:
            return None
        if not episode.get("entries"):
            return None

        lines: list[str] = []
        for entry in episode["entries"]:
            lines.append(f"[{entry['speaker']}]: {entry['text']}")
        return "\n".join(lines)

    def _cache_key(self, episode_id: str, content_type: str) -> str:
        return f"{episode_id}:{content_type}"

    def _store_result(
        self, episode_id: str, content_type: str, content: str
    ) -> Dict[str, Any]:
        result = {
            "episode_id": episode_id,
            "content_type": content_type,
            "content": content,
            "generated_at": time.time(),
        }
        self._cache[self._cache_key(episode_id, content_type)] = result
        return result

    def get_cached(
        self, episode_id: str, content_type: str
    ) -> Optional[Dict[str, Any]]:
        """Return previously generated content if available."""
        return self._cache.get(self._cache_key(episode_id, content_type))

    # ------------------------------------------------------------------
    # Generation methods
    # ------------------------------------------------------------------

    async def generate_blog_post(self, episode_id: str) -> Dict[str, Any]:
        """Generate a blog post / article draft from the episode transcript."""
        transcript = self._get_transcript_text(episode_id)
        if transcript is None:
            return {"success": False, "error": "Episode not found or has no entries"}

        episode = self._store.get_episode(episode_id)
        title = episode["title"] if episode else "Untitled Episode"

        prompt = (
            "You are an expert podcast editor. Given the following podcast transcript, "
            "write a polished blog post / article draft that captures the key discussion. "
            "Use an engaging tone. Include a headline, introduction, main body with "
            "subheadings, and a conclusion. Output in markdown.\n\n"
            f"Episode title: {title}\n\n"
            f"Transcript:\n{transcript}"
        )

        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=settings.openai_reasoning_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
            )
            content = response.choices[0].message.content or ""
            result = self._store_result(episode_id, "blog-post", content)
            result["success"] = True
            logger.info("Blog post generated", episode_id=episode_id)
            return result
        except Exception as exc:
            logger.error("Blog post generation failed", error=str(exc))
            return {"success": False, "error": str(exc)}

    async def generate_show_notes(self, episode_id: str) -> Dict[str, Any]:
        """Generate show notes with key topics, timestamps, and links."""
        transcript = self._get_transcript_text(episode_id)
        if transcript is None:
            return {"success": False, "error": "Episode not found or has no entries"}

        episode = self._store.get_episode(episode_id)
        title = episode["title"] if episode else "Untitled Episode"

        prompt = (
            "You are a podcast producer. Given the following podcast transcript, "
            "generate structured show notes in markdown. Include:\n"
            "1. Episode summary (2-3 sentences)\n"
            "2. Key topics discussed (bullet list)\n"
            "3. Notable timestamps (approximate, based on conversation flow)\n"
            "4. Any links, resources, or references mentioned\n"
            "5. Guest information if identifiable\n\n"
            f"Episode title: {title}\n\n"
            f"Transcript:\n{transcript}"
        )

        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=settings.openai_reasoning_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
            )
            content = response.choices[0].message.content or ""
            result = self._store_result(episode_id, "show-notes", content)
            result["success"] = True
            logger.info("Show notes generated", episode_id=episode_id)
            return result
        except Exception as exc:
            logger.error("Show notes generation failed", error=str(exc))
            return {"success": False, "error": str(exc)}

    async def generate_social_clips(self, episode_id: str) -> Dict[str, Any]:
        """Extract notable quotes suitable for social media posts."""
        transcript = self._get_transcript_text(episode_id)
        if transcript is None:
            return {"success": False, "error": "Episode not found or has no entries"}

        episode = self._store.get_episode(episode_id)
        title = episode["title"] if episode else "Untitled Episode"

        prompt = (
            "You are a social media manager for a podcast. Given the following "
            "podcast transcript, extract 5-8 notable, quotable moments that would "
            "make great social media posts or audiogram clips.\n\n"
            "For each clip, provide:\n"
            "- The quote (exact or lightly edited for clarity)\n"
            "- The speaker\n"
            "- Approximate position in the conversation (e.g. 'early', 'middle', 'late')\n"
            "- A suggested social media caption\n\n"
            "Output as a JSON array of objects with keys: quote, speaker, position, caption.\n"
            "Wrap the JSON in a ```json code fence.\n\n"
            f"Episode title: {title}\n\n"
            f"Transcript:\n{transcript}"
        )

        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=settings.openai_reasoning_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
            )
            raw_content = response.choices[0].message.content or ""

            # Try to parse the JSON clips from the response
            clips: list[dict] = []
            try:
                # Extract JSON from code fence if present
                if "```json" in raw_content:
                    json_str = raw_content.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_content:
                    json_str = raw_content.split("```")[1].split("```")[0].strip()
                else:
                    json_str = raw_content.strip()
                clips = json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                # If JSON parsing fails, store raw content
                pass

            result = self._store_result(episode_id, "social-clips", raw_content)
            result["success"] = True
            result["clips"] = clips
            logger.info(
                "Social clips generated",
                episode_id=episode_id,
                clip_count=len(clips),
            )
            return result
        except Exception as exc:
            logger.error("Social clips generation failed", error=str(exc))
            return {"success": False, "error": str(exc)}
