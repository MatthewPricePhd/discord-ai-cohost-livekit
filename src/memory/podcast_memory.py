"""Mem0-backed long-term memory for the podcast AI co-host.

Stores facts, themes, guest preferences, and claims across episodes so the AI
can reference past conversations ("In episode 12, guest Sarah mentioned...").
Uses ChromaDB as the vector backend and OpenAI embeddings.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import get_logger, settings

logger = get_logger(__name__)

# Mem0 is an optional heavy dependency — graceful fallback if missing.
try:
    from mem0 import Memory
    MEM0_AVAILABLE = True
except ImportError:
    Memory = None  # type: ignore[assignment,misc]
    MEM0_AVAILABLE = False


def _build_mem0_config() -> dict:
    """Build the Mem0 configuration dict pointing at our local ChromaDB."""
    chroma_path = Path("./data/mem0_chroma")
    chroma_path.mkdir(parents=True, exist_ok=True)

    return {
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "podcast_memories",
                "path": str(chroma_path),
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "text-embedding-3-small",
                "api_key": settings.openai_api_key,
            },
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gpt-4o-mini",
                "api_key": settings.openai_api_key,
            },
        },
        "version": "v1.1",
    }


class PodcastMemory:
    """Wraps Mem0 to provide episode-scoped long-term memory for the podcast.

    Each memory is tagged with ``user_id="podcast_host"`` and carries an
    ``episode_id`` in its metadata so we can scope queries per episode or
    search across all episodes.
    """

    USER_ID = "podcast_host"

    def __init__(self) -> None:
        self._memory: Optional[Any] = None
        self._initialised = False

    # ------------------------------------------------------------------
    # Lazy initialisation (avoids import-time side effects)
    # ------------------------------------------------------------------

    def _ensure_init(self) -> None:
        if self._initialised:
            return
        self._initialised = True

        if not MEM0_AVAILABLE:
            logger.warning("mem0ai not installed — memory features disabled")
            return

        try:
            config = _build_mem0_config()
            self._memory = Memory.from_config(config)
            logger.info("PodcastMemory initialised with ChromaDB backend")
        except Exception as exc:
            logger.error("Failed to initialise Mem0", error=str(exc))
            self._memory = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_episode_memory(
        self,
        episode_id: str,
        transcript_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Auto-extract and store facts from a transcript chunk.

        Args:
            episode_id: Unique identifier for the episode.
            transcript_text: Raw transcript text to extract facts from.
            metadata: Extra metadata to attach to every extracted memory.

        Returns:
            List of memory dicts that were created by Mem0.
        """
        self._ensure_init()
        if not self._memory:
            return []

        try:
            mem_metadata = {"episode_id": episode_id}
            if metadata:
                mem_metadata.update(metadata)

            result = self._memory.add(
                transcript_text,
                user_id=self.USER_ID,
                metadata=mem_metadata,
            )
            results_list = result.get("results", []) if isinstance(result, dict) else []
            logger.info(
                "Episode memories added",
                episode_id=episode_id,
                count=len(results_list),
            )
            return results_list
        except Exception as exc:
            logger.error("Error adding episode memory", episode_id=episode_id, error=str(exc))
            return []

    def search(
        self,
        query: str,
        episode_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Semantic search across all episode memories.

        Args:
            query: Natural-language search query.
            episode_id: If provided, restrict results to this episode.
            limit: Maximum number of results.

        Returns:
            List of matching memory dicts.
        """
        self._ensure_init()
        if not self._memory:
            return []

        try:
            kwargs: Dict[str, Any] = {
                "query": query,
                "user_id": self.USER_ID,
                "limit": limit,
            }
            results = self._memory.search(**kwargs)

            # If episode_id filter requested, do client-side filtering
            # (Mem0's metadata filter support varies by backend).
            if episode_id and results:
                results = [
                    r for r in results
                    if r.get("metadata", {}).get("episode_id") == episode_id
                ]

            return results
        except Exception as exc:
            logger.error("Memory search failed", query=query[:80], error=str(exc))
            return []

    def get_episode_memories(self, episode_id: str) -> List[Dict[str, Any]]:
        """Return all memories tagged with a specific episode.

        Args:
            episode_id: The episode to fetch memories for.

        Returns:
            List of memory dicts for the episode.
        """
        self._ensure_init()
        if not self._memory:
            return []

        try:
            all_memories = self._memory.get_all(user_id=self.USER_ID)
            memories_list = all_memories.get("results", []) if isinstance(all_memories, dict) else all_memories
            return [
                m for m in memories_list
                if m.get("metadata", {}).get("episode_id") == episode_id
            ]
        except Exception as exc:
            logger.error("Error fetching episode memories", episode_id=episode_id, error=str(exc))
            return []

    def get_context_for_prompt(
        self,
        query: str,
        max_results: int = 5,
    ) -> str:
        """Search memories and format them as a context string for an AI prompt.

        Args:
            query: The topic or question to search for.
            max_results: Maximum memories to include.

        Returns:
            Formatted context string ready to inject into a system prompt.
        """
        results = self.search(query, limit=max_results)
        if not results:
            return ""

        lines = ["## Relevant Memories from Past Episodes\n"]
        for i, mem in enumerate(results, 1):
            memory_text = mem.get("memory", mem.get("text", ""))
            ep_id = mem.get("metadata", {}).get("episode_id", "unknown")
            lines.append(f"{i}. [Episode {ep_id}] {memory_text}")

        return "\n".join(lines)
