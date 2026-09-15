"""Pluggable LLM providers for Mind-Mate.

Supported:
  - "groq"      -> Groq API (llama-3.3-70b-versatile by default, JSON mode)
  - "anthropic" -> Anthropic Claude
  - "mock"      -> deterministic offline replies (used when no key is set)

The reply always comes back as a structured (reply, mood, used_memory)
triple so the front-end face can react even before we build a real
emotion-fusion module.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

from .crisis import CRISIS_RESOURCE_LINE
from .models import EmotionState, MemoryItem

_PROMPT_PATH = Path(__file__).parent / "prompts" / "therapist.md"

VALID_MOODS = {"joy", "sadness", "anger", "fear", "surprise", "neutral"}


def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _context_block(
    message: str,
    emotion: EmotionState,
    sos_level: int,
    recalled: Optional[MemoryItem],
) -> str:
    lines = [
        f"[LEXICON_EMOTION_HINT] label={emotion.label} valence={emotion.valence} arousal={emotion.arousal}",
        f"[SOS_LEVEL] {sos_level}",
    ]
    if sos_level >= 2:
        lines.append(f"[CRISIS_RESOURCES] {CRISIS_RESOURCE_LINE}")
    if recalled is not None:
        lines.append(
            f"[RECALLED_MEMORY] (from {recalled.created_at.date().isoformat()}): {recalled.text}"
        )
    lines.append(f"[USER] {message}")
    return "\n".join(lines)


def _build_messages(
    message: str,
    emotion: EmotionState,
    sos_level: int,
    recalled: Optional[MemoryItem],
    history: list[MemoryItem],
) -> list[dict]:
    msgs: list[dict] = []
    for item in history:
        msgs.append(
            {
                "role": "user" if item.role == "user" else "assistant",
                "content": item.text,
            }
        )
    msgs.append({"role": "user", "content": _context_block(message, emotion, sos_level, recalled)})
    return msgs


_JSON_RE = re.compile(r"\{.*\}", re.S)


def _parse_reply(raw: str) -> tuple[str, str, bool]:
    """Return (reply_text, mood, used_memory). Robust to junk around JSON."""
    if not raw:
        return "…", "neutral", False
    match = _JSON_RE.search(raw)
    if match:
        try:
            j = json.loads(match.group(0))
            reply = str(j.get("reply", "")).strip() or raw.strip()
            mood = str(j.get("mood", "neutral")).lower().strip()
            if mood not in VALID_MOODS:
                mood = "neutral"
            used = bool(j.get("used_memory", False))
            return reply, mood, used
        except Exception:
            pass
    return raw.strip(), "neutral", False


# ---------------------------------------------------------------------------
# Mock (offline) provider
# ---------------------------------------------------------------------------


import random

_MOCK_POSITIVE = [
    "Wait, that's genuinely amazing — congratulations! What's the part you're proudest of?",
    "Ohh I love this for you! How long had you been working toward it?",
    "Yes! That's huge. Tell me how it actually went down.",
    "That honestly made me smile. What did that moment feel like for you?",
]
_MOCK_NEGATIVE = [
    "Oof, I'm really sorry — that sounds heavy. Do you want to talk through what happened?",
    "That sounds genuinely hard. I'm right here — what's been the toughest part?",
    "Mm, that stings, and it makes sense that it does. What's weighing on you most?",
    "I hate that you're going through this. Tell me more — I'm listening properly.",
]
_MOCK_NEUTRAL = [
    "Ooh, tell me more about that — I'm curious where it's coming from.",
    "I'm with you. What's been on your mind around it?",
    "Go on — what's the story there?",
    "That's interesting. How are you feeling about it, honestly?",
]


def _mock(message: str, emotion: EmotionState, sos_level: int) -> tuple[str, str, bool]:
    if sos_level >= 2:
        return (
            "Hey — I'm right here with you. Whatever's happening, you're not alone in it. "
            f"{CRISIS_RESOURCE_LINE} Can we call one of them together?",
            "sadness",
            False,
        )
    if emotion.valence > 0.25:
        return (random.choice(_MOCK_POSITIVE), "joy", False)
    if emotion.valence < -0.2:
        return (random.choice(_MOCK_NEGATIVE), "sadness", False)
    return (random.choice(_MOCK_NEUTRAL), "neutral", False)


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class _GroqProvider:
    name = "groq"

    def __init__(self) -> None:
        from groq import Groq  # local import so mock mode has no hard dep

        self.client = Groq(api_key=_env("GROQ_API_KEY"))
        self.model = _env("GROQ_MODEL") or "llama-3.3-70b-versatile"

    def complete(self, system: str, messages: list[dict]) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *messages],
            temperature=0.75,
            max_tokens=350,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or ""


class _AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        import anthropic

        self.client = anthropic.Anthropic(api_key=_env("ANTHROPIC_API_KEY"))
        self.model = _env("ANTHROPIC_MODEL") or "claude-3-5-sonnet-latest"

    def complete(self, system: str, messages: list[dict]) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=400,
            system=system,
            messages=messages,
        )
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------


def _env(name: str) -> str:
    """Read an env var, tolerating a UTF-8 BOM that Windows PowerShell's
    `Out-File -Encoding utf8` prepends to the first line of a .env file."""
    val = os.environ.get(name) or os.environ.get("﻿" + name) or ""
    return val.strip().strip('"').strip("'").lstrip("﻿")


class TherapistLLM:
    def __init__(self) -> None:
        self.reason = ""
        pref = _env("LLM_PROVIDER").lower()
        self.provider = self._pick(pref)

    def _pick(self, pref: str):
        groq_key = _env("GROQ_API_KEY")
        anthropic_key = _env("ANTHROPIC_API_KEY")
        try:
            if (pref == "groq" or not pref) and groq_key:
                return _GroqProvider()
            if (pref == "anthropic" or not pref) and anthropic_key:
                return _AnthropicProvider()
        except Exception as exc:
            self.reason = f"provider init failed: {exc}"
            return None
        if not groq_key and not anthropic_key:
            self.reason = "no API key found in .env (set GROQ_API_KEY)"
        else:
            self.reason = f"LLM_PROVIDER={pref!r} but its key is missing"
        return None

    @property
    def online(self) -> bool:
        return self.provider is not None

    @property
    def name(self) -> str:
        if self.provider is None:
            return "mock"
        return f"{self.provider.name}:{getattr(self.provider, 'model', '?')}"

    def reply(
        self,
        message: str,
        emotion: EmotionState,
        sos_level: int,
        recalled: Optional[MemoryItem],
        history: list[MemoryItem],
    ) -> tuple[str, str, bool]:
        """Return (reply_text, mood_label, used_memory)."""
        if self.provider is None:
            return _mock(message, emotion, sos_level)

        msgs = _build_messages(message, emotion, sos_level, recalled, history)
        try:
            raw = self.provider.complete(_system_prompt(), msgs)
            return _parse_reply(raw)
        except Exception as exc:
            reply, mood, used = _mock(message, emotion, sos_level)
            return f"{reply}\n(fallback — {self.provider.name} error: {exc})", mood, used
