"""Text-emotion scoring for Mind-Mate.

A stand-in for the multimodal (audio + text) fusion module of Phase 2, but
deliberately more than a bag of words: it handles negation ("I'm not happy"),
intensifiers ("really sad" vs "a bit sad") and emotional trajectory, because
getting the *sign* of the feeling wrong is worse than saying nothing.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from .models import EmotionState

# word: (label, valence, arousal)
LEXICON: dict[str, tuple[str, float, float]] = {
    # --- joy -------------------------------------------------------------
    "happy": ("joy", 0.8, 0.5), "great": ("joy", 0.7, 0.4),
    "love": ("joy", 0.9, 0.5), "excited": ("joy", 0.8, 0.8),
    "grateful": ("joy", 0.7, 0.3), "proud": ("joy", 0.7, 0.4),
    "smile": ("joy", 0.6, 0.3), "hope": ("joy", 0.5, 0.3),
    "hopeful": ("joy", 0.6, 0.3), "won": ("joy", 0.8, 0.7),
    "win": ("joy", 0.8, 0.7), "winner": ("joy", 0.8, 0.7),
    "first": ("joy", 0.5, 0.5), "prize": ("joy", 0.7, 0.6),
    "hackathon": ("joy", 0.3, 0.6), "passed": ("joy", 0.7, 0.5),
    "achieved": ("joy", 0.7, 0.5), "achievement": ("joy", 0.7, 0.5),
    "aced": ("joy", 0.8, 0.6), "promoted": ("joy", 0.8, 0.5),
    "amazing": ("joy", 0.8, 0.6), "awesome": ("joy", 0.8, 0.6),
    "wonderful": ("joy", 0.8, 0.5), "thrilled": ("joy", 0.9, 0.8),
    "relieved": ("joy", 0.6, 0.3), "good": ("joy", 0.5, 0.3),
    "better": ("joy", 0.5, 0.3), "celebrate": ("joy", 0.8, 0.7),
    "fun": ("joy", 0.7, 0.6), "enjoyed": ("joy", 0.7, 0.4),
    "glad": ("joy", 0.6, 0.3), "peaceful": ("joy", 0.6, 0.15),
    "calm": ("joy", 0.5, 0.1), "okay": ("joy", 0.3, 0.2),
    "fine": ("joy", 0.3, 0.2),

    # --- sadness ---------------------------------------------------------
    "sad": ("sadness", -0.7, 0.3), "down": ("sadness", -0.6, 0.3),
    "lonely": ("sadness", -0.7, 0.3), "alone": ("sadness", -0.5, 0.3),
    "empty": ("sadness", -0.7, 0.3), "cry": ("sadness", -0.7, 0.5),
    "crying": ("sadness", -0.7, 0.5), "tired": ("sadness", -0.4, 0.2),
    "exhausted": ("sadness", -0.5, 0.2), "hurt": ("sadness", -0.6, 0.5),
    "stings": ("sadness", -0.5, 0.4), "failed": ("sadness", -0.7, 0.5),
    "failure": ("sadness", -0.7, 0.5), "lost": ("sadness", -0.6, 0.4),
    "rejected": ("sadness", -0.7, 0.5), "disappointed": ("sadness", -0.6, 0.4),
    "miss": ("sadness", -0.5, 0.4), "grief": ("sadness", -0.8, 0.4),
    "heartbroken": ("sadness", -0.85, 0.5), "hopeless": ("sadness", -0.85, 0.35),
    "worthless": ("sadness", -0.85, 0.4), "numb": ("sadness", -0.6, 0.15),
    "depressed": ("sadness", -0.8, 0.3), "unwanted": ("sadness", -0.7, 0.4),
    "ignored": ("sadness", -0.6, 0.4), "guilty": ("sadness", -0.6, 0.45),
    "ashamed": ("sadness", -0.7, 0.5), "regret": ("sadness", -0.6, 0.4),

    # --- anger -----------------------------------------------------------
    "angry": ("anger", -0.6, 0.8), "mad": ("anger", -0.6, 0.8),
    "furious": ("anger", -0.8, 0.95), "hate": ("anger", -0.8, 0.7),
    "frustrated": ("anger", -0.5, 0.65), "annoyed": ("anger", -0.4, 0.55),
    "irritated": ("anger", -0.4, 0.55), "unfair": ("anger", -0.6, 0.6),
    "betrayed": ("anger", -0.8, 0.7), "resent": ("anger", -0.7, 0.6),
    "sick": ("anger", -0.5, 0.5), "fed": ("anger", -0.5, 0.6),

    # --- fear ------------------------------------------------------------
    "afraid": ("fear", -0.6, 0.7), "scared": ("fear", -0.7, 0.75),
    "anxious": ("fear", -0.55, 0.65), "anxiety": ("fear", -0.6, 0.7),
    "worried": ("fear", -0.45, 0.55), "worry": ("fear", -0.45, 0.55),
    "panicked": ("fear", -0.75, 0.95), "panic": ("fear", -0.75, 0.9),
    "nervous": ("fear", -0.4, 0.6), "terrified": ("fear", -0.85, 0.9),
    "overwhelmed": ("fear", -0.65, 0.75), "stressed": ("fear", -0.55, 0.7),
    "dread": ("fear", -0.7, 0.6), "insecure": ("fear", -0.5, 0.5),

    # --- surprise / disgust ---------------------------------------------
    "shocked": ("surprise", -0.2, 0.75), "surprised": ("surprise", 0.2, 0.6),
    "stunned": ("surprise", -0.1, 0.7), "unexpected": ("surprise", 0.0, 0.5),
    "disgusted": ("disgust", -0.7, 0.5), "gross": ("disgust", -0.5, 0.4),
}

# Flip the feeling when negated: "not happy" is closer to sad than to neutral.
_NEGATORS = {
    "not", "no", "never", "none", "cant", "can't", "cannot", "dont", "don't",
    "doesnt", "doesn't", "didnt", "didn't", "wont", "won't", "wouldnt",
    "wouldn't", "isnt", "isn't", "arent", "aren't", "wasnt", "wasn't",
    "aint", "ain't", "hardly", "barely", "without", "nothing", "nobody",
}
_INTENSIFIERS = {
    "very": 1.4, "really": 1.35, "so": 1.3, "extremely": 1.6, "incredibly": 1.5,
    "totally": 1.35, "completely": 1.45, "absolutely": 1.45, "super": 1.35,
    "deeply": 1.4, "utterly": 1.5, "always": 1.25, "constantly": 1.3,
}
_DAMPENERS = {
    "slightly": 0.55, "kinda": 0.65, "kind": 0.7, "sort": 0.7, "bit": 0.6,
    "little": 0.65, "somewhat": 0.65, "maybe": 0.7, "mildly": 0.55,
}

# When a feeling is negated, this is what it collapses toward.
_NEGATED_LABEL = {
    "joy": "sadness",
    "sadness": "neutral",
    "anger": "neutral",
    "fear": "neutral",
    "surprise": "neutral",
    "disgust": "neutral",
}

_WORD = re.compile(r"[a-z']+")
_NEG_WINDOW = 3  # how many words back a negator still applies

# A negation does not survive a clause break: in "I'm not angry, just tired"
# the "not" belongs to angry, not to tired.
_CLAUSE_BREAK = re.compile(r"[,.;:!?]+|\b(?:but|though|although|however|just|yet|still)\b")


def _lookup(tok: str) -> Optional[tuple[str, float, float]]:
    """Match a word against the lexicon, tolerating common inflections
    ("loved" -> love, "winning" -> win, "worries" -> worry)."""
    hit = LEXICON.get(tok)
    if hit is not None:
        return hit
    for suffix in ("ing", "ed", "es", "s", "d"):
        if not tok.endswith(suffix) or len(tok) - len(suffix) < 2:
            continue
        stem = tok[: -len(suffix)]
        for candidate in (stem, stem + "e", stem[:-1] if stem[-1:] == stem[-2:-1] else "",
                          stem + "y"):
            if candidate and candidate in LEXICON:
                return LEXICON[candidate]
    return None


def _clauses(text: str) -> list[list[str]]:
    parts = _CLAUSE_BREAK.split(text.lower())
    return [toks for p in parts if p and (toks := _WORD.findall(p))]


def score_text(text: str) -> EmotionState:
    if not text.strip():
        return EmotionState()

    weights: dict[str, float] = defaultdict(float)
    valences: list[float] = []
    arousals: list[float] = []

    for tokens in _clauses(text):
        for i, tok in enumerate(tokens):
            entry = _lookup(tok)
            if entry is None:
                continue
            label, valence, arousal = entry

            window = tokens[max(0, i - _NEG_WINDOW) : i]
            negated = any(w in _NEGATORS for w in window)

            multiplier = 1.0
            for w in window:
                if w in _INTENSIFIERS:
                    multiplier *= _INTENSIFIERS[w]
                elif w in _DAMPENERS:
                    multiplier *= _DAMPENERS[w]

            if negated:
                # "not happy" -> mildly negative, not strongly sad; and never
                # let a negated positive keep reading as joy.
                valence = -valence * 0.75
                arousal *= 0.85
                label = _NEGATED_LABEL.get(label, "neutral")

            valence = max(-1.0, min(1.0, valence * multiplier))
            arousal = max(0.0, min(1.0, arousal * multiplier))

            valences.append(valence)
            arousals.append(arousal)
            if label != "neutral":
                weights[label] += abs(valence)

    if not valences:
        return EmotionState(label="neutral", valence=0.0, arousal=0.1, confidence=0.3)

    valence = sum(valences) / len(valences)
    arousal = sum(arousals) / len(arousals)
    label = max(weights, key=lambda k: weights[k]) if weights else "neutral"

    # A label must agree with the overall sign, otherwise we're better off
    # admitting we don't know than showing the wrong face.
    if label == "joy" and valence < 0:
        label = "sadness"
    elif label in {"sadness", "anger", "fear", "disgust"} and valence > 0.25:
        label = "neutral"

    confidence = min(1.0, 0.4 + 0.15 * len(valences))
    return EmotionState(
        label=label,  # type: ignore[arg-type]
        valence=round(valence, 3),
        arousal=round(arousal, 3),
        confidence=round(confidence, 3),
    )


def trajectory(current: EmotionState, history: list[EmotionState]) -> str:
    """How this turn compares to how they've been sounding.

    Returns "lifting", "dipping" or "steady" so the reply can notice a shift
    the way a friend would ("you sound lighter than earlier").
    """
    past = [e.valence for e in history[-6:]]
    if len(past) < 2:
        return "steady"
    avg = sum(past) / len(past)
    delta = current.valence - avg
    if delta > 0.35:
        return "lifting"
    if delta < -0.35:
        return "dipping"
    return "steady"
