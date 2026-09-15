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
            # Durable facts about the person (name, ongoing threads, people
            # who matter to them). Survives "new session" on purpose.
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS profile (
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, key)
                )
                """
            )
            # One row per finished conversation, so a returning user can be
            # greeted with what actually happened last time.
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS session_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            # session_id was added after the first release; older DBs need it.
            cols = {r["name"] for r in c.execute("PRAGMA table_info(memory)")}
            if "session_id" not in cols:
                c.execute("ALTER TABLE memory ADD COLUMN session_id INTEGER NOT NULL DEFAULT 1")

    # -- writes ----------------------------------------------------------

    def add(self, item: MemoryItem, session_id: int = 1) -> int:
        with self._lock, self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO memory(user_id, session_id, role, text, emotion_json, topic_tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.user_id,
                    session_id,
                    item.role,
                    item.text,
                    item.emotion.model_dump_json(),
                    json.dumps(item.topic_tags),
                    item.created_at.isoformat(),
                ),
            )
            return int(cur.lastrowid or 0)

    def wipe(self, user_id: str) -> None:
        """Forget this person entirely — conversations, profile, everything."""
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM memory WHERE user_id = ?", (user_id,))
            c.execute("DELETE FROM crisis_log WHERE user_id = ?", (user_id,))
            c.execute("DELETE FROM profile WHERE user_id = ?", (user_id,))
            c.execute("DELETE FROM session_summary WHERE user_id = ?", (user_id,))

    # -- sessions --------------------------------------------------------

    def current_session_id(self, user_id: str) -> int:
        with self._conn() as c:
            row = c.execute(
                "SELECT MAX(session_id) AS s FROM memory WHERE user_id = ?", (user_id,)
            ).fetchone()
        return int(row["s"] or 1)

    def start_new_session(self, user_id: str) -> int:
        return self.current_session_id(user_id) + 1

    def session_turns(self, user_id: str, session_id: int) -> list[MemoryItem]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM memory WHERE user_id = ? AND session_id = ? ORDER BY id",
                (user_id, session_id),
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    # -- durable profile -------------------------------------------------

    def set_fact(self, user_id: str, key: str, value: str) -> None:
        key = key.strip().lower()[:60]
        value = value.strip()[:300]
        if not key or not value:
            return
        with self._lock, self._conn() as c:
            c.execute(
                """
                INSERT INTO profile(user_id, key, value, updated_at) VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (user_id, key, value, datetime.utcnow().isoformat()),
            )

    def get_facts(self, user_id: str) -> dict[str, str]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT key, value FROM profile WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return {r["key"]: r["value"] for r in rows}

    def add_session_summary(self, user_id: str, session_id: int, summary: str) -> None:
        summary = summary.strip()
        if not summary:
            return
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO session_summary(user_id, session_id, summary, created_at) VALUES (?, ?, ?, ?)",
                (user_id, session_id, summary, datetime.utcnow().isoformat()),
            )

    def recent_summaries(self, user_id: str, n: int = 4) -> list[tuple[str, datetime]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT summary, created_at FROM session_summary WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, n),
            ).fetchall()
        return [(r["summary"], datetime.fromisoformat(r["created_at"])) for r in rows]

    def has_history(self, user_id: str) -> bool:
        return bool(self.get_facts(user_id) or self.recent_summaries(user_id, 1))

    def digest(self, user_id: str) -> str:
        """A short 'what I remember about you' block injected into the prompt."""
        facts = self.get_facts(user_id)
        summaries = self.recent_summaries(user_id, 4)
        if not facts and not summaries:
            return ""
        lines: list[str] = []
        name = facts.pop("name", None)
        if name:
            lines.append(f"Their name is {name}.")
        for k, v in list(facts.items())[:10]:
            lines.append(f"- {k}: {v}")
        if summaries:
            lines.append("Previous conversations (most recent first):")
            now = datetime.utcnow()
            for text, when in summaries:
                days = (now - when).days
                ago = "today" if days <= 0 else ("yesterday" if days == 1 else f"{days} days ago")
                lines.append(f"- ({ago}) {text}")
        return "\n".join(lines)

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
