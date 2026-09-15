# Mind-Mate

A voice-assisted empathetic listening companion. This repo currently
contains the **Phase-1 MVP (~30%)**: a working text chatbot with a
therapist persona, memory recall, text-based emotion inference, and a
first-pass crisis-detection layer, wrapped in a browser UI that
previews the two-OLED (eyes + mouth) hardware form factor.

Voice, camera, and physical OLED integration land in later phases
(see `ROADMAP.md`).

## Run it

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # optionally set ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

Without an API key the server still runs in an offline mock mode so the
whole interface (chat, emotion → face, crisis banner, memory recall)
demos end-to-end.

## What's in the MVP

| Piece                  | Where                     | Notes                                  |
| ---------------------- | ------------------------- | -------------------------------------- |
| FastAPI + static UI    | `app/main.py`, `static/`  | Chat log, OLED-style avatar, SOS box   |
| Therapist persona      | `app/prompts/therapist.md`| Version-controlled system prompt       |
| LLM wrapper            | `app/llm.py`              | Anthropic SDK w/ deterministic fallback|
| Text emotion scorer    | `app/emotion.py`          | Lexicon MVP; swappable for a transformer|
| Memory store           | `app/memory.py`           | SQLite; contrasting-positive retrieval |
| Crisis detection       | `app/crisis.py`           | Regex layer; LLM classifier comes next |
| Pydantic contract      | `app/models.py`           | Message schema shared with A / C       |
| Tests                  | `tests/`                  | `pytest`                               |

## Signature feature: contrasting memory recall

`MemoryStore.find_contrasting_positive` pulls a semantically-related
*positive* memory when the current utterance turns negative. The MVP
uses keyword overlap; the roadmap swaps in Chroma + sentence-transformers
without changing the interface.

## Safety

Crisis responses always surface **iCall (9152987821)** and the
**Vandrevala Foundation (1860-2662-345)**. Contacting a family member is
deliberately *not* the first-line action — see `ROADMAP.md`.
