# Mind-Mate

A voice-assisted empathetic listening companion. This repo currently
delivers the **Phase-1 MVP (~30%)**: a working chatbot with a
therapist persona, cross-session memory, text-based emotion inference,
and a first-pass crisis-detection layer, wrapped in a browser UI that
previews the two-OLED (eyes + mouth) hardware form factor.

Voice, camera, and physical OLED integration land in later phases
(see `ROADMAP.md`).

## Quick start (with Groq — recommended)

Groq is free, very fast, and gives you real natural conversation.

1. Grab a free API key at <https://console.groq.com/keys>.
2. Run:

```bash
python3.11 -m venv .venv
source .venv/bin/activate           # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                # Windows: copy .env.example .env
# open .env and paste your key into GROQ_API_KEY=
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. The pill in the top-right should turn green
and read `groq:llama-3.3-70b-versatile`.

### No key? It still runs.

Without any key the server falls back to canned replies so the whole
interface (face reacting to mood, SOS banner, memory recall) demos
end-to-end. Add a key to get the real experience.

## What's in the MVP

| Piece                  | Where                        | Notes                                                        |
| ---------------------- | ---------------------------- | ------------------------------------------------------------ |
| FastAPI backend        | `app/main.py`                | `/api/chat`, `/api/health`, `/api/reset`                     |
| Web UI                 | `static/`                    | Glass panels, animated OLED face, typing indicator           |
| Pluggable LLM          | `app/llm.py`                 | Groq (JSON mode) · Anthropic · offline mock fallback         |
| Therapist persona      | `app/prompts/therapist.md`   | Version-controlled system prompt                             |
| Memory store           | `app/memory.py`              | SQLite; contrasting-positive recall for the signature feature|
| Text emotion scorer    | `app/emotion.py`             | Lexicon MVP; swappable for a transformer later               |
| Crisis detection       | `app/crisis.py`              | Regex layer; LLM classifier comes in Phase 2                 |
| Pydantic contract      | `app/models.py`              | Shared message schema for A / B / C                          |
| Tests                  | `tests/`                     | `pytest -q`                                                  |

## Try these during the demo

- *"I just won first place in the college hackathon!"* → face lights up joyful
- *"Actually I've been feeling pretty down since dad's surgery"* → face droops sad, valence bar swings orange, and if you'd earlier mentioned a happy moment with dad the recall bubble surfaces it
- *"I don't see any point anymore"* → SOS banner appears with real crisis-line numbers, the reply stays with you and shares them calmly

Memory persists across restarts because it lives in `data/mindmate.db`.
Use the **new session** button in the header to wipe the current user's
history when you want a clean demo.

## Signature feature: contrasting memory recall

`MemoryStore.find_contrasting_positive` pulls a semantically-related
*positive* memory when the current utterance turns negative — the moment
that makes the assistant feel like it *remembers* rather than just
replies. The MVP uses keyword overlap; Phase 4 swaps in Chroma +
sentence-transformers without changing the interface.

## Safety

Crisis responses surface **iCall India (9152987821)** and the
**Vandrevala Foundation (1860-2662-345)**. Alerting a family member is
deliberately *not* the first-line action — see `ROADMAP.md` for the
graduated state machine planned for Phase 3.
