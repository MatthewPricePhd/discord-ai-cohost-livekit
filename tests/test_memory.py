"""Tests for PodcastMemory (Mem0 integration).

These tests verify the PodcastMemory wrapper logic without requiring
a running Mem0 backend or OpenAI API key. The Mem0 Memory object is
mocked to avoid external dependencies.
"""
from unittest.mock import MagicMock, patch

import pytest

from src.memory.podcast_memory import PodcastMemory


@pytest.fixture
def memory():
    """Create a PodcastMemory with a mocked Mem0 backend."""
    pm = PodcastMemory()
    pm._initialised = True

    # Create a mock Mem0 Memory instance
    mock_mem = MagicMock()
    pm._memory = mock_mem
    return pm, mock_mem


def test_add_episode_memory(memory):
    pm, mock_mem = memory
    mock_mem.add.return_value = {
        "results": [
            {"id": "m1", "memory": "Guest mentioned machine learning", "metadata": {"episode_id": "ep1"}}
        ]
    }

    results = pm.add_episode_memory("ep1", "We discussed machine learning today.")
    assert len(results) == 1
    assert results[0]["memory"] == "Guest mentioned machine learning"

    mock_mem.add.assert_called_once()
    call_kwargs = mock_mem.add.call_args
    assert call_kwargs[1]["user_id"] == "podcast_host"
    assert call_kwargs[1]["metadata"]["episode_id"] == "ep1"


def test_search(memory):
    pm, mock_mem = memory
    mock_mem.search.return_value = [
        {"memory": "AI discussed in episode 3", "metadata": {"episode_id": "ep3"}},
        {"memory": "ML in episode 5", "metadata": {"episode_id": "ep5"}},
    ]

    results = pm.search("artificial intelligence")
    assert len(results) == 2
    mock_mem.search.assert_called_once()


def test_search_with_episode_filter(memory):
    pm, mock_mem = memory
    mock_mem.search.return_value = [
        {"memory": "fact A", "metadata": {"episode_id": "ep1"}},
        {"memory": "fact B", "metadata": {"episode_id": "ep2"}},
    ]

    results = pm.search("topic", episode_id="ep1")
    assert len(results) == 1
    assert results[0]["metadata"]["episode_id"] == "ep1"


def test_get_episode_memories(memory):
    pm, mock_mem = memory
    mock_mem.get_all.return_value = {
        "results": [
            {"memory": "fact 1", "metadata": {"episode_id": "ep1"}},
            {"memory": "fact 2", "metadata": {"episode_id": "ep2"}},
            {"memory": "fact 3", "metadata": {"episode_id": "ep1"}},
        ]
    }

    results = pm.get_episode_memories("ep1")
    assert len(results) == 2


def test_get_context_for_prompt(memory):
    pm, mock_mem = memory
    mock_mem.search.return_value = [
        {"memory": "Important fact from ep1", "metadata": {"episode_id": "ep1"}},
    ]

    context = pm.get_context_for_prompt("test query")
    assert "Relevant Memories" in context
    assert "Important fact from ep1" in context
    assert "ep1" in context


def test_get_context_for_prompt_empty(memory):
    pm, mock_mem = memory
    mock_mem.search.return_value = []

    context = pm.get_context_for_prompt("test query")
    assert context == ""


def test_memory_not_available():
    """Test graceful degradation when Mem0 is not initialised."""
    pm = PodcastMemory()
    pm._initialised = True
    pm._memory = None

    assert pm.add_episode_memory("ep1", "text") == []
    assert pm.search("query") == []
    assert pm.get_episode_memories("ep1") == []
    assert pm.get_context_for_prompt("query") == ""
