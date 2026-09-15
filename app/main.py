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

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Mind-Mate", version="0.2.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_store = default_store()
_llm = TherapistLLM()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_online": _llm.online,
        "provider": _llm.name,
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    emo = emotion.score_text(req.message)
    sos = crisis.assess(req.message)

    recalled = _store.find_contrasting_positive(req.user_id, req.message, emo)
    history = _store.recent(req.user_id, n=12)

    _store.add(
        MemoryItem(user_id=req.user_id, role="user", text=req.message, emotion=emo)
    )
    if sos >= 2:
        _store.log_crisis(req.user_id, sos, req.message)

    reply_text, mood_label, used_memory = _llm.reply(
        message=req.message,
        emotion=emo,
        sos_level=sos,
        recalled=recalled,
        history=history,
    )
    _store.add(
        MemoryItem(user_id=req.user_id, role="assistant", text=reply_text, emotion=emo)
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


@app.post("/api/reset")
def reset(user_id: str = "demo-user") -> dict:
    """Clear one user's history — handy during demos."""
    _store.wipe(user_id)
    return {"ok": True}
