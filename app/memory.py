"""SQLite-backed memory store for the MVP.

Vector retrieval is deferred (Chroma / sentence-transformers) to keep
the review demo dependency-light. We use a keyword overlap score over
recent memories, and a valence filter to pull a *contrasting* positive
memory when the current utterance is negative — the signature feature
of Mind-Mate.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import EmotionState, MemoryItem

_STOP = {
    "the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "in",
    "on", "at", "for", "with", "is", "am", "are", "was", "were", "be",
    "been", "being", "i", "you", "he", "she", "it", "we", "they", "me",
    "my", "your", "his", "her", "its", "our", "their", "this", "that",
    "these", "those", "so", "just", "not", "no", "yes", "do", "did",
    "does", "have", "has", "had", "will", "would", "can", "could", "as",
}

_WORD = re.compile(r"[a-zA-Z']+")


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text) if w.lower() not in _STOP and len(w) > 2}


class MemoryStore:
    def __init__(self, db_path: str = "data/mindmate.db") -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init(self) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    emotion_json TEXT NOT NULL,
                    topic_tags TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS crisis_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    # -- writes ----------------------------------------------------------

    def add(self, item: MemoryItem) -> int:
        with self._lock, self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO memory(user_id, role, text, emotion_json, topic_tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item.user_id,
                    item.role,
                    item.text,
                    item.emotion.model_dump_json(),
                    json.dumps(item.topic_tags),
                    item.created_at.isoformat(),
                ),
            )
            return int(cur.lastrowid or 0)

    def wipe(self, user_id: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM memory WHERE user_id = ?", (user_id,))
            c.execute("DELETE FROM crisis_log WHERE user_id = ?", (user_id,))

    def log_crisis(self, user_id: str, level: int, text: str) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO crisis_log(user_id, level, text, created_at) VALUES (?, ?, ?, ?)",
                (user_id, level, text, datetime.utcnow().isoformat()),
            )

    # -- reads -----------------------------------------------------------

    def recent(self, user_id: str, n: int = 10) -> list[MemoryItem]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM memory WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, n),
            ).fetchall()
        return [self._row_to_item(r) for r in reversed(rows)]

    def find_contrasting_positive(
        self, user_id: str, current_text: str, current: EmotionState
    ) -> Optional[MemoryItem]:
        """Given a negative-valence utterance, retrieve a related positive memory.

        Uses simple keyword overlap; a vector search will replace this later.
        Returns None when nothing meaningful is found.
        """
        if current.valence >= -0.2:
            return None
        cur_tokens = _tokens(current_text)
        if not cur_tokens:
            return None

        with self._conn() as c:
            rows = c.execute(
                """
                SELECT * FROM memory
                 WHERE user_id = ? AND role = 'user'
                 ORDER BY id DESC LIMIT 200
                """,
                (user_id,),
            ).fetchall()

        best: Optional[tuple[float, MemoryItem]] = None
        for r in rows:
            item = self._row_to_item(r)
            if item.emotion.valence < 0.3:
                continue
            overlap = len(cur_tokens & _tokens(item.text))
            if overlap == 0:
                continue
            score = overlap + item.emotion.valence  # tie-break toward more positive
            if best is None or score > best[0]:
                best = (score, item)
        return best[1] if best else None

    def _row_to_item(self, r: sqlite3.Row) -> MemoryItem:
        return MemoryItem(
            id=r["id"],
            user_id=r["user_id"],
            role=r["role"],
            text=r["text"],
            emotion=EmotionState.model_validate_json(r["emotion_json"]),
            topic_tags=json.loads(r["topic_tags"]),
            created_at=datetime.fromisoformat(r["created_at"]),
        )


def default_store() -> MemoryStore:
    return MemoryStore(os.environ.get("MIND_MATE_DB", "data/mindmate.db"))
