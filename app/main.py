"""FastAPI entrypoint for Mind-Mate."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import crisis, emotion
from .llm import TherapistLLM
from .memory import default_store
from .models import ChatRequest, ChatResponse, MemoryItem

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# Load the .env from the project root explicitly so it works no matter
# which directory uvicorn is launched from. override=True lets the file
# win over anything already in the shell environment.
load_dotenv(BASE_DIR / ".env", override=True)

app = FastAPI(title="Mind-Mate", version="0.2.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_store = default_store()
_llm = TherapistLLM()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "favicon.svg"), media_type="image/svg+xml")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_online": _llm.online,
        "provider": _llm.name,
        "reason": _llm.reason,
    }


@app.get("/api/greeting")
def greeting(user_id: str = "demo-user") -> dict:
    """Open the conversation — warm and specific if we've met before."""
    digest = _store.digest(user_id)
    return {
        "reply": _llm.greeting(digest),
        "returning": bool(digest),
        "remembers": _memory_view(user_id),
    }


@app.get("/api/memory")
def memory_view(user_id: str = "demo-user") -> dict:
    return _memory_view(user_id)


def _memory_view(user_id: str) -> dict:
    facts = _store.get_facts(user_id)
    return {
        "name": facts.get("name"),
        "facts": [{"key": k, "value": v} for k, v in facts.items() if k != "name"],
        "sessions": [
            {"summary": s, "when": w.isoformat()} for s, w in _store.recent_summaries(user_id, 4)
        ],
    }


@app.post("/api/new_session")
def new_session(user_id: str = "demo-user") -> dict:
    """End the current conversation and start a fresh one.

    Long-term memory is deliberately KEPT — the point is that Mind-Mate
    still knows you next time. The finished conversation is condensed into
    a summary plus durable facts before we move on.
    """
    sid = _store.current_session_id(user_id)
    turns = _store.session_turns(user_id, sid)
    if turns:
        summary, facts = _llm.summarize_session(turns)
        if summary:
            _store.add_session_summary(user_id, sid, summary)
        for k, v in facts.items():
            _store.set_fact(user_id, k, v)

    digest = _store.digest(user_id)
    return {
        "reply": _llm.greeting(digest),
        "returning": bool(digest),
        "remembers": _memory_view(user_id),
    }


@app.post("/api/forget")
def forget(user_id: str = "demo-user") -> dict:
    """Erase everything about this person — the privacy escape hatch."""
    _store.wipe(user_id)
    return {"ok": True, "reply": _llm.greeting(""), "remembers": _memory_view(user_id)}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    emo = emotion.score_text(req.message)
    sos = crisis.assess(req.message)
    sid = _store.current_session_id(req.user_id)

    recalled = _store.find_contrasting_positive(req.user_id, req.message, emo)
    history = _store.session_turns(req.user_id, sid)[-12:]
    digest = _store.digest(req.user_id)

    _store.add(
        MemoryItem(user_id=req.user_id, role="user", text=req.message, emotion=emo), sid
    )
    if sos >= 2:
        _store.log_crisis(req.user_id, sos, req.message)

    reply_text, mood_label, used_memory = _llm.reply(
        message=req.message,
        emotion=emo,
        sos_level=sos,
        recalled=recalled,
        history=history,
        digest=digest,
    )
    _store.add(
        MemoryItem(user_id=req.user_id, role="assistant", text=reply_text, emotion=emo), sid
    )

    # If the LLM didn't clearly identify a mood, fall back to the lexicon label.
    display_mood = mood_label if mood_label != "neutral" else emo.label

    return ChatResponse(
        reply=reply_text,
        emotion=emo,
        display_mood=display_mood,
        sos_level=sos,
        recalled_memory=(recalled.text if used_memory and recalled else None),
        used_memory=used_memory,
        provider=_llm.name,
    )


