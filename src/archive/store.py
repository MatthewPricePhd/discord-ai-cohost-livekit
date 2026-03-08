"""SQLite-backed transcript archive for podcast episodes.

Stores episode metadata and individual transcript entries with speaker
attribution and timestamps.  Supports full-text search and export to
markdown / JSON.
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from ..config import get_logger

logger = get_logger(__name__)

DB_PATH = Path("./data/transcripts.db")


class TranscriptStore:
    """Persistent transcript storage backed by SQLite."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS episodes (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                date        TEXT NOT NULL,
                guests      TEXT NOT NULL DEFAULT '[]',
                metadata    TEXT NOT NULL DEFAULT '{}',
                created_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS transcript_entries (
                id          TEXT PRIMARY KEY,
                episode_id  TEXT NOT NULL,
                speaker     TEXT NOT NULL,
                text        TEXT NOT NULL,
                timestamp   REAL NOT NULL,
                FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_entries_episode
                ON transcript_entries(episode_id);

            CREATE INDEX IF NOT EXISTS idx_entries_timestamp
                ON transcript_entries(episode_id, timestamp);
        """)
        conn.commit()
        logger.info("TranscriptStore schema ensured", db_path=str(self._db_path))

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Episodes
    # ------------------------------------------------------------------

    def create_episode(
        self,
        title: str,
        guests: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new episode record and return its ID."""
        episode_id = str(uuid.uuid4())
        now = time.time()
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO episodes (id, title, date, guests, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                episode_id,
                title,
                datetime.now(tz=None).isoformat(),
                json.dumps(guests or []),
                json.dumps(metadata or {}),
                now,
            ),
        )
        conn.commit()
        logger.info("Episode created", episode_id=episode_id, title=title)
        return episode_id

    def get_episode(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Return full episode record with all transcript entries."""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone()
        if not row:
            return None

        entries = conn.execute(
            "SELECT * FROM transcript_entries WHERE episode_id = ? ORDER BY timestamp",
            (episode_id,),
        ).fetchall()

        return {
            "id": row["id"],
            "title": row["title"],
            "date": row["date"],
            "guests": json.loads(row["guests"]),
            "metadata": json.loads(row["metadata"]),
            "created_at": row["created_at"],
            "entries": [
                {
                    "id": e["id"],
                    "speaker": e["speaker"],
                    "text": e["text"],
                    "timestamp": e["timestamp"],
                }
                for e in entries
            ],
        }

    def list_episodes(self) -> List[Dict[str, Any]]:
        """Return summary list of all episodes (newest first)."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT e.*, COUNT(t.id) AS entry_count "
            "FROM episodes e LEFT JOIN transcript_entries t ON t.episode_id = e.id "
            "GROUP BY e.id ORDER BY e.created_at DESC"
        ).fetchall()

        return [
            {
                "id": r["id"],
                "title": r["title"],
                "date": r["date"],
                "guests": json.loads(r["guests"]),
                "entry_count": r["entry_count"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Transcript entries
    # ------------------------------------------------------------------

    def add_entry(
        self,
        episode_id: str,
        speaker: str,
        text: str,
        timestamp: Optional[float] = None,
    ) -> str:
        """Add a single transcript entry. Returns entry ID."""
        entry_id = str(uuid.uuid4())
        ts = timestamp or time.time()
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO transcript_entries (id, episode_id, speaker, text, timestamp) VALUES (?, ?, ?, ?, ?)",
            (entry_id, episode_id, speaker, text, ts),
        )
        conn.commit()
        return entry_id

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_transcripts(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Full-text search across all transcript entries (simple LIKE match).

        For production use, consider adding an FTS5 virtual table.
        """
        conn = self._get_conn()
        like_pattern = f"%{query}%"
        rows = conn.execute(
            "SELECT t.*, e.title AS episode_title "
            "FROM transcript_entries t "
            "JOIN episodes e ON e.id = t.episode_id "
            "WHERE t.text LIKE ? "
            "ORDER BY t.timestamp DESC LIMIT ?",
            (like_pattern, limit),
        ).fetchall()

        return [
            {
                "id": r["id"],
                "episode_id": r["episode_id"],
                "episode_title": r["episode_title"],
                "speaker": r["speaker"],
                "text": r["text"],
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_markdown(self, episode_id: str) -> Optional[str]:
        """Export an episode transcript as formatted markdown."""
        episode = self.get_episode(episode_id)
        if not episode:
            return None

        lines = [
            f"# {episode['title']}",
            "",
            f"**Date:** {episode['date']}",
            f"**Guests:** {', '.join(episode['guests']) if episode['guests'] else 'None'}",
            f"**Entries:** {len(episode['entries'])}",
            "",
            "---",
            "",
        ]

        for entry in episode["entries"]:
            ts_str = datetime.fromtimestamp(entry["timestamp"]).strftime("%H:%M:%S")
            lines.append(f"**[{ts_str}] {entry['speaker']}:** {entry['text']}")
            lines.append("")

        return "\n".join(lines)

    def export_json(self, episode_id: str) -> Optional[str]:
        """Export an episode transcript as structured JSON."""
        episode = self.get_episode(episode_id)
        if not episode:
            return None
        return json.dumps(episode, indent=2, default=str)
