"""
Observer Agent for passive background conversation analysis.

Runs as a background asyncio task during podcast sessions, analyzing
conversation turns and generating insights for the dashboard without
interrupting the live conversation.
"""
import asyncio
import json
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from ..config import get_logger, settings

logger = get_logger(__name__)

OBSERVER_MODEL = "gpt-5.3-instant"


class ObserverAgent:
    """
    Background observer that analyzes conversation in real-time and
    generates structured insights (talking points, fact checks, relevant
    docs, conversation direction) surfaced only via the web dashboard.
    """

    def __init__(
        self,
        openai_client: Optional[AsyncOpenAI] = None,
        context_manager=None,
        analysis_frequency: int = 3,
    ):
        self._openai: Optional[AsyncOpenAI] = openai_client
        self._context_manager = context_manager
        self.analysis_frequency = analysis_frequency
        self.enabled = True

        # Conversation buffer
        self._turns: deque = deque(maxlen=100)
        self._unprocessed_turn_count = 0

        # Insights storage (most-recent first, capped at 20)
        self._insights: deque = deque(maxlen=20)

        # Background task handle
        self._task: Optional[asyncio.Task] = None
        self._event = asyncio.Event()
        self._running = False

    # ------------------------------------------------------------------
    # OpenAI client access
    # ------------------------------------------------------------------

    def _get_client(self) -> AsyncOpenAI:
        if not self._openai:
            self._openai = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("ObserverAgent started", frequency=self.analysis_frequency)

    async def stop(self) -> None:
        self._running = False
        self._event.set()  # unblock the loop so it can exit
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("ObserverAgent stopped")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_turn(self, speaker: str, text: str) -> None:
        """Feed a new transcription turn into the observer."""
        self._turns.append({
            "speaker": speaker,
            "text": text,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self._unprocessed_turn_count += 1

        if (
            self.enabled
            and self._unprocessed_turn_count >= self.analysis_frequency
        ):
            self._event.set()

    def get_latest_insights(self) -> List[Dict[str, Any]]:
        """Return the most recent insights (newest first)."""
        return list(self._insights)

    def configure(
        self,
        analysis_frequency: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update observer configuration at runtime."""
        if analysis_frequency is not None and analysis_frequency >= 1:
            self.analysis_frequency = analysis_frequency
        if enabled is not None:
            self.enabled = enabled
        return {
            "analysis_frequency": self.analysis_frequency,
            "enabled": self.enabled,
        }

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self._event.wait()
                self._event.clear()

                if not self._running:
                    break

                if not self.enabled:
                    self._unprocessed_turn_count = 0
                    continue

                await self._analyze()
                self._unprocessed_turn_count = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("ObserverAgent analysis error", error=str(e))
                await asyncio.sleep(2)

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    async def _analyze(self) -> None:
        """Run a single analysis cycle on accumulated turns."""
        turns_snapshot = list(self._turns)
        if not turns_snapshot:
            return

        conversation_text = "\n".join(
            f"[{t['timestamp']}] {t['speaker']}: {t['text']}"
            for t in turns_snapshot
        )

        # Run LLM analysis and optional doc retrieval in parallel
        llm_task = self._llm_analyze(conversation_text)
        doc_task = self._retrieve_relevant_docs(turns_snapshot)

        llm_result, relevant_docs = await asyncio.gather(
            llm_task, doc_task, return_exceptions=True
        )

        if isinstance(llm_result, Exception):
            logger.error("LLM analysis failed", error=str(llm_result))
            llm_result = {}
        if isinstance(relevant_docs, Exception):
            logger.error("Doc retrieval failed", error=str(relevant_docs))
            relevant_docs = []

        insight = {
            "timestamp": datetime.utcnow().isoformat(),
            "turns_analyzed": len(turns_snapshot),
            "talking_points": llm_result.get("talking_points", []),
            "fact_checks": llm_result.get("fact_checks", []),
            "conversation_direction": llm_result.get("conversation_direction", ""),
            "relevant_docs": relevant_docs,
        }

        self._insights.appendleft(insight)
        logger.info(
            "ObserverAgent insight generated",
            talking_points=len(insight["talking_points"]),
            fact_checks=len(insight["fact_checks"]),
            docs=len(insight["relevant_docs"]),
        )

    async def _llm_analyze(self, conversation_text: str) -> Dict[str, Any]:
        client = self._get_client()

        prompt = f"""Analyze this podcast conversation and return a JSON object with exactly these keys:

- "talking_points": list of 3-5 suggested topics or follow-up questions the host could raise
- "fact_checks": list of any claims that may need verification (empty list if none)
- "conversation_direction": a single sentence summarizing where the discussion is heading

Conversation:
{conversation_text[:6000]}"""

        response = await client.chat.completions.create(
            model=OBSERVER_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a podcast production assistant. "
                        "Analyze conversations and return ONLY valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=500,
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("ObserverAgent received non-JSON response", raw=raw[:200])
            return {
                "talking_points": [],
                "fact_checks": [],
                "conversation_direction": raw[:200],
            }

    async def _retrieve_relevant_docs(
        self, turns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not self._context_manager:
            return []

        retriever = getattr(self._context_manager, "retriever", None)
        if not retriever:
            return []

        # Build a short query from the last few turns
        recent_text = " ".join(t["text"] for t in turns[-5:])[:1000]

        try:
            results = await retriever.search_documents(query=recent_text, n_results=3)
            return [
                {
                    "title": r.get("document_title", "Unknown"),
                    "snippet": r.get("text_preview", r.get("text", ""))[:300],
                    "similarity": r.get("similarity", 0),
                }
                for r in results
            ]
        except Exception as e:
            logger.error("ObserverAgent doc retrieval error", error=str(e))
            return []
