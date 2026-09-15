"""Thin wrapper around the Anthropic Messages API.

If no ANTHROPIC_API_KEY is set, a deterministic mock reply is produced
so the demo runs offline. This mock is *only* for the interface
walkthrough; it is not a therapist.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .crisis import CRISIS_RESOURCE_LINE
from .models import EmotionState, MemoryItem

_PROMPT_PATH = Path(__file__).parent / "prompts" / "therapist.md"


def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_user_context(
    message: str,
    emotion: EmotionState,
    sos_level: int,
    recalled: Optional[MemoryItem],
    history: list[MemoryItem],
) -> list[dict]:
    """Format prior turns + a context block for the current turn."""
    msgs: list[dict] = []
    for item in history:
        role = "user" if item.role == "user" else "assistant"
        msgs.append({"role": role, "content": item.text})

    ctx_lines = [
        f"[EMOTION] label={emotion.label} valence={emotion.valence} arousal={emotion.arousal}",
        f"[SOS_LEVEL] {sos_level}",
    ]
    if sos_level >= 2:
        ctx_lines.append(f"[CRISIS_RESOURCES] {CRISIS_RESOURCE_LINE}")
    if recalled is not None:
        ctx_lines.append(
            f"[RECALLED_MEMORY] (from {recalled.created_at.date().isoformat()}): {recalled.text}"
        )
    ctx_lines.append(f"[USER] {message}")
    msgs.append({"role": "user", "content": "\n".join(ctx_lines)})
    return msgs


def _mock_reply(message: str, emotion: EmotionState, sos_level: int) -> str:
    if sos_level >= 2:
        return (
            "I hear how heavy this is right now, and I'm staying with you. "
            f"{CRISIS_RESOURCE_LINE} Would you be willing to reach one of them with me?"
        )
    if emotion.valence < -0.2:
        return (
            "That sounds really hard. I'm here — can you tell me a bit "
            "more about what's weighing on you?"
        )
    if emotion.valence > 0.3:
        return "I love hearing that. What made today feel a little lighter?"
    return "Thanks for sharing that with me. What's on your mind right now?"


class TherapistLLM:
    def __init__(self) -> None:
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        self.model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
        self._client = None
        if self.api_key:
            try:
                import anthropic  # noqa: WPS433

                self._client = anthropic.Anthropic(api_key=self.api_key)
            except Exception:  # pragma: no cover - defensive
                self._client = None

    @property
    def online(self) -> bool:
        return self._client is not None

    def reply(
        self,
        message: str,
        emotion: EmotionState,
        sos_level: int,
        recalled: Optional[MemoryItem],
        history: list[MemoryItem],
    ) -> str:
        if not self.online:
            return _mock_reply(message, emotion, sos_level)

        msgs = _build_user_context(message, emotion, sos_level, recalled, history)
        try:
            resp = self._client.messages.create(  # type: ignore[union-attr]
                model=self.model,
                max_tokens=400,
                system=_system_prompt(),
                messages=msgs,
            )
            parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
            return ("\n".join(parts)).strip() or _mock_reply(message, emotion, sos_level)
        except Exception as exc:  # pragma: no cover - network path
            return f"(offline fallback) {_mock_reply(message, emotion, sos_level)}\n[llm error: {exc}]"
