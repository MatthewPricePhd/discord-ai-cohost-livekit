"""Tests for the TranscriptStore (SQLite transcript archive)."""
import json
import tempfile
import time
from pathlib import Path

import pytest

from src.archive.store import TranscriptStore


@pytest.fixture
def store(tmp_path):
    """Create a TranscriptStore backed by a temporary SQLite database."""
    db_path = tmp_path / "test_transcripts.db"
    return TranscriptStore(db_path=db_path)


def test_create_episode(store):
    episode_id = store.create_episode("Test Episode", guests=["Alice", "Bob"])
    assert episode_id
    ep = store.get_episode(episode_id)
    assert ep is not None
    assert ep["title"] == "Test Episode"
    assert ep["guests"] == ["Alice", "Bob"]
    assert ep["entries"] == []


def test_list_episodes(store):
    store.create_episode("Ep 1")
    store.create_episode("Ep 2")
    episodes = store.list_episodes()
    assert len(episodes) == 2
    # Newest first
    assert episodes[0]["title"] == "Ep 2"


def test_add_entry_and_retrieve(store):
    episode_id = store.create_episode("Entry Test")
    ts = time.time()
    store.add_entry(episode_id, "Alice", "Hello world", timestamp=ts)
    store.add_entry(episode_id, "Bob", "Hi Alice", timestamp=ts + 1)

    ep = store.get_episode(episode_id)
    assert ep is not None
    assert len(ep["entries"]) == 2
    assert ep["entries"][0]["speaker"] == "Alice"
    assert ep["entries"][1]["speaker"] == "Bob"


def test_search_transcripts(store):
    ep_id = store.create_episode("Search Test")
    store.add_entry(ep_id, "Alice", "Machine learning is amazing")
    store.add_entry(ep_id, "Bob", "I prefer deep learning")

    results = store.search_transcripts("machine learning")
    assert len(results) == 1
    assert results[0]["speaker"] == "Alice"


def test_export_markdown(store):
    ep_id = store.create_episode("Export Test", guests=["Charlie"])
    store.add_entry(ep_id, "Charlie", "Test message")

    md = store.export_markdown(ep_id)
    assert md is not None
    assert "# Export Test" in md
    assert "Charlie" in md
    assert "Test message" in md


def test_export_json(store):
    ep_id = store.create_episode("JSON Test")
    store.add_entry(ep_id, "Dave", "JSON content")

    json_str = store.export_json(ep_id)
    assert json_str is not None
    data = json.loads(json_str)
    assert data["title"] == "JSON Test"
    assert len(data["entries"]) == 1


def test_get_nonexistent_episode(store):
    assert store.get_episode("nonexistent-id") is None


def test_export_nonexistent_episode(store):
    assert store.export_markdown("nonexistent-id") is None
    assert store.export_json("nonexistent-id") is None


def test_entry_count_in_list(store):
    ep_id = store.create_episode("Count Test")
    store.add_entry(ep_id, "A", "msg1")
    store.add_entry(ep_id, "B", "msg2")
    store.add_entry(ep_id, "C", "msg3")

    episodes = store.list_episodes()
    assert episodes[0]["entry_count"] == 3
