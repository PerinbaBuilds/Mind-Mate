"""Recall picks the right past moment, and knows when to stay quiet."""

import os
import tempfile

from app.memory import MemoryStore
from app.models import EmotionState, MemoryItem


def _store():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.unlink(tmp.name)
    return MemoryStore(tmp.name)


def _seed(s, text, valence, role="user"):
    label = "joy" if valence > 0.2 else ("sadness" if valence < -0.2 else "neutral")
    return s.add(
        MemoryItem(
            user_id="u",
            role=role,
            text=text,
            emotion=EmotionState(label=label, valence=valence, arousal=0.4),
        ),
        1,
    )


def _pad(s, n=4):
    """Assistant turns so the recall pacing gate is satisfied."""
    for _ in range(n):
        _seed(s, "mm, tell me more", 0.0, role="assistant")


def test_low_mood_pulls_a_related_positive_memory():
    s = _store()
    _seed(s, "dad took me out for my birthday dinner, felt so loved", 0.8)
    _seed(s, "watched a film about racing cars", 0.1)
    _pad(s)

    r = s.recall_for("u", "i miss dad so much, birthday was quiet", EmotionState(valence=-0.6))
    assert r is not None
    assert r.kind == "contrasting_positive"
    assert "dad" in r.item.text.lower()


def test_low_mood_ignores_unrelated_positives():
    s = _store()
    _seed(s, "the biryani at the new place was incredible", 0.8)
    _pad(s)

    r = s.recall_for("u", "my viva went terribly and i feel stupid", EmotionState(valence=-0.7))
    assert r is None


def test_neutral_mood_recalls_for_continuity():
    s = _store()
    _seed(s, "im building a thinking processing unit for my project", 0.3)
    _seed(s, "had chai with my roommate", 0.2)  # intervening turn
    _pad(s)

    r = s.recall_for("u", "the processing unit build is going okay", EmotionState(valence=0.1))
    assert r is not None
    assert r.kind == "related_past"
    assert "processing unit" in r.item.text


def test_recall_is_paced_not_constant():
    s = _store()
    _seed(s, "dad took me out for my birthday, felt loved", 0.8)
    _pad(s)
    # an assistant turn that surfaced a memory resets the gate
    s.add(
        MemoryItem(user_id="u", role="assistant", text="that birthday sounded lovely"),
        1,
        recalled_id=1,
    )
    assert s.turns_since_recall("u") == 0

    r = s.recall_for("u", "i miss dad and the birthday", EmotionState(valence=-0.6))
    assert r is None, "should stay quiet so soon after the last recall"


def test_no_recall_without_shared_topic():
    s = _store()
    _seed(s, "completely unrelated thing about trains", 0.5)
    _pad(s)
    assert s.recall_for("u", "hello", EmotionState(valence=-0.5)) is None
