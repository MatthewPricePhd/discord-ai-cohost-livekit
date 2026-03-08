"""Tests for the ContentPipeline (post-episode content generation)."""
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.archive.store import TranscriptStore
from src.archive.content_pipeline import ContentPipeline


@pytest.fixture
def store(tmp_path):
    """Create a TranscriptStore backed by a temporary SQLite database."""
    db_path = tmp_path / "test_transcripts.db"
    return TranscriptStore(db_path=db_path)


@pytest.fixture
def pipeline(store):
    """Create a ContentPipeline with the test store."""
    return ContentPipeline(store=store)


@pytest.fixture
def episode_with_entries(store):
    """Create an episode with several transcript entries."""
    ep_id = store.create_episode("Test Episode", guests=["Alice", "Bob"])
    ts = time.time()
    store.add_entry(ep_id, "Alice", "Welcome to the show! Today we are talking about AI.", timestamp=ts)
    store.add_entry(ep_id, "Bob", "Thanks for having me. AI is a fascinating topic.", timestamp=ts + 5)
    store.add_entry(ep_id, "Alice", "Let's start with machine learning fundamentals.", timestamp=ts + 10)
    store.add_entry(ep_id, "Bob", "Sure, the key insight is that models learn from data.", timestamp=ts + 15)
    store.add_entry(ep_id, "Alice", "And deep learning has really changed everything.", timestamp=ts + 20)
    return ep_id


def _mock_openai_response(content: str):
    """Create a mock OpenAI chat completion response."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


# ── Unit tests for transcript helpers ────────────────────────────


def test_get_transcript_text_returns_none_for_missing_episode(pipeline):
    result = pipeline._get_transcript_text("nonexistent-id")
    assert result is None


def test_get_transcript_text_returns_none_for_empty_episode(pipeline, store):
    ep_id = store.create_episode("Empty Episode")
    result = pipeline._get_transcript_text(ep_id)
    assert result is None


def test_get_transcript_text_formats_correctly(pipeline, store, episode_with_entries):
    text = pipeline._get_transcript_text(episode_with_entries)
    assert text is not None
    assert "[Alice]:" in text
    assert "[Bob]:" in text
    assert "machine learning" in text


# ── Cache tests ──────────────────────────────────────────────────


def test_cache_stores_and_retrieves(pipeline):
    pipeline._store_result("ep-1", "blog-post", "Some blog content")
    cached = pipeline.get_cached("ep-1", "blog-post")
    assert cached is not None
    assert cached["content"] == "Some blog content"
    assert cached["content_type"] == "blog-post"
    assert cached["episode_id"] == "ep-1"
    assert "generated_at" in cached


def test_cache_returns_none_for_missing(pipeline):
    assert pipeline.get_cached("ep-1", "blog-post") is None


# ── Blog post generation ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_blog_post_missing_episode(pipeline):
    result = await pipeline.generate_blog_post("nonexistent-id")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_generate_blog_post_success(pipeline, episode_with_entries):
    mock_response = _mock_openai_response("# Blog Post\n\nGreat episode about AI.")

    with patch.object(pipeline, "_get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_client

        result = await pipeline.generate_blog_post(episode_with_entries)

    assert result["success"] is True
    assert "Blog Post" in result["content"]
    assert result["content_type"] == "blog-post"

    # Should be cached
    cached = pipeline.get_cached(episode_with_entries, "blog-post")
    assert cached is not None
    assert cached["content"] == result["content"]


# ── Show notes generation ────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_show_notes_missing_episode(pipeline):
    result = await pipeline.generate_show_notes("nonexistent-id")
    assert result["success"] is False


@pytest.mark.asyncio
async def test_generate_show_notes_success(pipeline, episode_with_entries):
    mock_response = _mock_openai_response("## Show Notes\n\n- AI discussion\n- ML fundamentals")

    with patch.object(pipeline, "_get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_client

        result = await pipeline.generate_show_notes(episode_with_entries)

    assert result["success"] is True
    assert "Show Notes" in result["content"]
    assert result["content_type"] == "show-notes"


# ── Social clips generation ──────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_social_clips_missing_episode(pipeline):
    result = await pipeline.generate_social_clips("nonexistent-id")
    assert result["success"] is False


@pytest.mark.asyncio
async def test_generate_social_clips_with_valid_json(pipeline, episode_with_entries):
    clips_json = json.dumps([
        {"quote": "AI is fascinating", "speaker": "Bob", "position": "early", "caption": "Great insight!"},
        {"quote": "Deep learning changed everything", "speaker": "Alice", "position": "late", "caption": "So true!"},
    ])
    mock_response = _mock_openai_response(f"```json\n{clips_json}\n```")

    with patch.object(pipeline, "_get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_client

        result = await pipeline.generate_social_clips(episode_with_entries)

    assert result["success"] is True
    assert len(result["clips"]) == 2
    assert result["clips"][0]["speaker"] == "Bob"
    assert result["content_type"] == "social-clips"


@pytest.mark.asyncio
async def test_generate_social_clips_with_invalid_json(pipeline, episode_with_entries):
    mock_response = _mock_openai_response("Here are some great quotes from the episode.")

    with patch.object(pipeline, "_get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_client

        result = await pipeline.generate_social_clips(episode_with_entries)

    # Should succeed even if JSON parsing fails -- stores raw content
    assert result["success"] is True
    assert result["clips"] == []
    assert "great quotes" in result["content"]


# ── API error handling ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_blog_post_api_error(pipeline, episode_with_entries):
    with patch.object(pipeline, "_get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API rate limit"))
        mock_get.return_value = mock_client

        result = await pipeline.generate_blog_post(episode_with_entries)

    assert result["success"] is False
    assert "API rate limit" in result["error"]
