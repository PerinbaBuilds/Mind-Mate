"""FastAPI entrypoint for the Mind-Mate MVP.

Run:  uvicorn app.main:app --reload
"""

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

app = FastAPI(title="Mind-Mate", version="0.1.0")
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
        "model": _llm.model if _llm.online else "mock",
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    emo = emotion.score_text(req.message)
    sos = crisis.assess(req.message)

    recalled = _store.find_contrasting_positive(req.user_id, req.message, emo)
    history = _store.recent(req.user_id, n=8)

    # persist the user turn first so future recall can see it
    _store.add(
        MemoryItem(user_id=req.user_id, role="user", text=req.message, emotion=emo)
    )
    if sos >= 2:
        _store.log_crisis(req.user_id, sos, req.message)

    reply_text = _llm.reply(
        message=req.message,
        emotion=emo,
        sos_level=sos,
        recalled=recalled,
        history=history,
    )
    _store.add(
        MemoryItem(user_id=req.user_id, role="assistant", text=reply_text, emotion=emo)
    )
    return ChatResponse(
        reply=reply_text,
        emotion=emo,
        sos_level=sos,
        recalled_memory=(recalled.text if recalled else None),
    )
