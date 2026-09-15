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
    digest: str = "",
) -> str:
    lines = []
    if digest:
        lines.append(f"[WHAT_YOU_REMEMBER_ABOUT_THEM]\n{digest}")
    lines += [
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
    digest: str = "",
) -> list[dict]:
    msgs: list[dict] = []
    for item in history:
        msgs.append(
            {
                "role": "user" if item.role == "user" else "assistant",
                "content": item.text,
            }
        )
    msgs.append(
        {"role": "user", "content": _context_block(message, emotion, sos_level, recalled, digest)}
    )
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

    # Ordered preference of chat models. Groq rotates its lineup, so we
    # resolve against whatever the account actually has access to.
    _PREFERRED = [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "openai/gpt-oss-120b",
        "moonshotai/kimi-k2-instruct",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "meta-llama/llama-4-maverick-17b-128e-instruct",
        "openai/gpt-oss-20b",
        "llama-3.1-8b-instant",
    ]
    _SKIP = ("whisper", "tts", "guard", "embed", "distil", "prompt")

    def __init__(self) -> None:
        from groq import Groq  # local import so mock mode has no hard dep

        self.client = Groq(api_key=_env("GROQ_API_KEY"))
        self.model = self._resolve(_env("GROQ_MODEL") or "llama-3.3-70b-versatile")

    def _resolve(self, want: str) -> str:
        """Pick a model the account can actually use, so a rotated/renamed
        default doesn't 404 the whole app."""
        try:
            available = {m.id for m in self.client.models.list().data}
        except Exception:
            return want  # can't list (offline/permissions) — try as-is
        if want in available:
            return want
        for cand in self._PREFERRED:
            if cand in available:
                return cand
        for mid in sorted(available):
            if not any(bad in mid.lower() for bad in self._SKIP):
                return mid
        return want

    def complete(self, system: str, messages: list[dict], json_mode: bool = True) -> str:
        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *messages],
            temperature=0.75,
            max_tokens=350,
            **kwargs,
        )
        return resp.choices[0].message.content or ""


class _AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        import anthropic

        self.client = anthropic.Anthropic(api_key=_env("ANTHROPIC_API_KEY"))
        self.model = _env("ANTHROPIC_MODEL") or "claude-3-5-sonnet-latest"

    def complete(self, system: str, messages: list[dict], json_mode: bool = True) -> str:
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
        digest: str = "",
    ) -> tuple[str, str, bool]:
        """Return (reply_text, mood_label, used_memory)."""
        if self.provider is None:
            return _mock(message, emotion, sos_level)

        msgs = _build_messages(message, emotion, sos_level, recalled, history, digest)
        try:
            raw = self.provider.complete(_system_prompt(), msgs)
            return _parse_reply(raw)
        except Exception as exc:
            # Keep the full error in the server log, but never dump a raw API
            # payload into the conversation the user is looking at.
            print(f"[mind-mate] {self.provider.name} error: {exc}", flush=True)
            reply, mood, used = _mock(message, emotion, sos_level)
            return reply, mood, used

    # -- long-term memory helpers ---------------------------------------

    def summarize_session(self, turns: list[MemoryItem]) -> tuple[str, dict[str, str]]:
        """Condense a finished conversation into a durable summary + facts."""
        if self.provider is None or not turns:
            return "", {}
        transcript = "\n".join(
            f"{'Them' if t.role == 'user' else 'You'}: {t.text}" for t in turns
        )[:6000]
        system = (
            "You maintain the long-term memory of a companion app. Read the "
            "conversation and extract what is worth remembering about this person "
            "for future conversations.\n\n"
            "Reply with ONE line of JSON, no markdown fences:\n"
            '{"summary": "<2 sentences, what they talked about and how they seemed>", '
            '"facts": {"<short_key>": "<short value>"}}\n\n'
            "Facts should be durable things about their life: their name, ongoing "
            "projects, people who matter to them, struggles, goals. Use short "
            "snake_case keys like name, studies, current_project, close_people. "
            "Only include what they actually said. Use {} if nothing durable came up."
        )
        try:
            raw = self.provider.complete(system, [{"role": "user", "content": transcript}])
            match = _JSON_RE.search(raw or "")
            if not match:
                return "", {}
            j = json.loads(match.group(0))
            summary = str(j.get("summary", "")).strip()
            facts_raw = j.get("facts", {})
            facts = {
                str(k): str(v)
                for k, v in (facts_raw.items() if isinstance(facts_raw, dict) else [])
                if str(v).strip()
            }
            return summary, facts
        except Exception as exc:
            print(f"[mind-mate] summarize error: {exc}", flush=True)
            return "", {}

    def greeting(self, digest: str) -> str:
        """Open a conversation. Warm and specific when we remember them."""
        if not digest:
            first = "Hey, I'm Mind-Mate. I'm here to listen — properly. What's going on with you today?"
            if self.provider is None:
                return first
            return first
        if self.provider is None:
            return "Hey, you're back — good to see you. How have things been since we last talked?"
        system = (
            "You are Mind-Mate, a warm companion greeting someone you genuinely "
            "care about as they come back to talk again.\n\n"
            "Write ONE short greeting (1-2 sentences). Sound delighted they're back "
            "and reference something specific you remember — by name if you know it. "
            "Ask how that specific thing went. Warm and natural, like a close friend, "
            "never clinical, never 'How can I help you today'. Plain text only, no JSON."
        )
        try:
            raw = self.provider.complete(
                system,
                [{"role": "user", "content": f"Here is what you remember:\n{digest}"}],
                json_mode=False,
            )
            return (raw or "").strip().strip('"') or "Hey, you're back — how have you been?"
        except Exception as exc:
            print(f"[mind-mate] greeting error: {exc}", flush=True)
            return "Hey, you're back — good to see you. How have things been?"
