from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


EmotionLabel = Literal[
    "joy", "sadness", "anger", "fear", "surprise", "disgust", "neutral"
]


class EmotionState(BaseModel):
    label: EmotionLabel = "neutral"
    valence: float = Field(0.0, ge=-1.0, le=1.0)  # negative..positive
    arousal: float = Field(0.0, ge=0.0, le=1.0)   # calm..intense
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class MemoryItem(BaseModel):
    id: Optional[int] = None
    user_id: str
    text: str
    role: Literal["user", "assistant"] = "user"
    emotion: EmotionState = EmotionState()
    topic_tags: list[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    user_id: str = "demo-user"
    message: str


class ChatResponse(BaseModel):
    reply: str
    emotion: EmotionState
    sos_level: int = 0
    recalled_memory: Optional[str] = None
