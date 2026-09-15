"""Lightweight text-emotion scorer for the MVP.

This is a stand-in for the multimodal (audio + text) fusion module that
Person B will build in a later phase. It uses a hand-tuned lexicon so
the demo works with zero ML dependencies.
"""

from __future__ import annotations

import re
from collections import Counter

from .models import EmotionState

LEXICON: dict[str, tuple[str, float, float]] = {
    # word: (label, valence, arousal)
    "happy": ("joy", 0.8, 0.5),
    "great": ("joy", 0.7, 0.4),
    "love": ("joy", 0.9, 0.5),
    "excited": ("joy", 0.8, 0.8),
    "grateful": ("joy", 0.7, 0.3),
    "proud": ("joy", 0.6, 0.4),
    "smile": ("joy", 0.6, 0.3),
    "hope": ("joy", 0.5, 0.3),
    "won": ("joy", 0.8, 0.7),
    "win": ("joy", 0.8, 0.7),
    "winner": ("joy", 0.8, 0.7),
    "first": ("joy", 0.6, 0.6),
    "prize": ("joy", 0.7, 0.6),
    "hackathon": ("joy", 0.4, 0.6),
    "passed": ("joy", 0.7, 0.5),
    "achieved": ("joy", 0.7, 0.5),
    "achievement": ("joy", 0.7, 0.5),
    "aced": ("joy", 0.8, 0.6),
    "promoted": ("joy", 0.8, 0.5),
    "amazing": ("joy", 0.8, 0.6),
    "awesome": ("joy", 0.8, 0.6),
    "wonderful": ("joy", 0.8, 0.5),
    "thrilled": ("joy", 0.9, 0.8),
    "relieved": ("joy", 0.5, 0.3),
    "good": ("joy", 0.5, 0.3),
    "celebrate": ("joy", 0.8, 0.7),
    "sad": ("sadness", -0.7, 0.3),
    "down": ("sadness", -0.6, 0.3),
    "lonely": ("sadness", -0.7, 0.3),
    "empty": ("sadness", -0.7, 0.3),
    "cry": ("sadness", -0.7, 0.5),
    "crying": ("sadness", -0.7, 0.5),
    "tired": ("sadness", -0.4, 0.2),
    "hurt": ("sadness", -0.6, 0.5),
    "stings": ("sadness", -0.5, 0.4),
    "failed": ("sadness", -0.7, 0.5),
    "lost": ("sadness", -0.6, 0.4),
    "rejected": ("sadness", -0.7, 0.5),
    "disappointed": ("sadness", -0.6, 0.4),
    "miss": ("sadness", -0.5, 0.4),
    "broke": ("sadness", -0.5, 0.4),
    "grief": ("sadness", -0.8, 0.4),
    "heartbroken": ("sadness", -0.8, 0.5),
    "angry": ("anger", -0.6, 0.8),
    "mad": ("anger", -0.6, 0.8),
    "furious": ("anger", -0.8, 0.9),
    "hate": ("anger", -0.8, 0.7),
    "frustrated": ("anger", -0.5, 0.6),
    "afraid": ("fear", -0.6, 0.7),
    "scared": ("fear", -0.7, 0.7),
    "anxious": ("fear", -0.5, 0.6),
    "worried": ("fear", -0.4, 0.5),
    "panicked": ("fear", -0.7, 0.9),
    "shocked": ("surprise", -0.1, 0.7),
    "surprised": ("surprise", 0.2, 0.6),
    "disgusted": ("disgust", -0.7, 0.5),
}

_WORD = re.compile(r"[a-z']+")


def score_text(text: str) -> EmotionState:
    tokens = _WORD.findall(text.lower())
    if not tokens:
        return EmotionState()

    hits: list[tuple[str, float, float]] = [LEXICON[t] for t in tokens if t in LEXICON]
    if not hits:
        return EmotionState(label="neutral", valence=0.0, arousal=0.1, confidence=0.3)

    labels = Counter(h[0] for h in hits)
    top_label = labels.most_common(1)[0][0]
    valence = sum(h[1] for h in hits) / len(hits)
    arousal = sum(h[2] for h in hits) / len(hits)
    confidence = min(1.0, 0.4 + 0.15 * len(hits))
    return EmotionState(
        label=top_label,  # type: ignore[arg-type]
        valence=round(valence, 3),
        arousal=round(arousal, 3),
        confidence=round(confidence, 3),
    )
