import os
import tempfile

from app.memory import MemoryStore
from app.models import EmotionState, MemoryItem


def _mk_store():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.unlink(tmp.name)
    return MemoryStore(tmp.name), tmp.name


def test_contrasting_positive_memory():
    store, _ = _mk_store()
    store.add(
        MemoryItem(
            user_id="u",
            role="user",
            text="I had an amazing dinner with dad on my birthday, felt so loved",
            emotion=EmotionState(label="joy", valence=0.8, arousal=0.5),
        )
    )
    store.add(
        MemoryItem(
            user_id="u",
            role="user",
            text="Just watched a movie",
            emotion=EmotionState(label="neutral", valence=0.0, arousal=0.1),
        )
    )
    current = EmotionState(label="sadness", valence=-0.6, arousal=0.3)
    hit = store.find_contrasting_positive(
        "u", "I miss dad so much today, birthday was quiet", current
    )
    assert hit is not None
    assert "dad" in hit.text.lower()


def test_no_recall_when_positive():
    store, _ = _mk_store()
    current = EmotionState(label="joy", valence=0.6)
    assert store.find_contrasting_positive("u", "great day today", current) is None
