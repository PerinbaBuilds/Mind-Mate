# Mind-Mate roadmap and three-person split

## Phase 1 — MVP (this repo, for tomorrow's review, ~30%)

- [x] Text chatbot with therapist persona (system prompt in Markdown)
- [x] Web UI with OLED-style eyes + mouth preview
- [x] SQLite memory + contrasting-positive recall
- [x] Text emotion (lexicon MVP) → conditions face + reply
- [x] Layer-1 crisis detection (regex + curated lexicon)
- [x] Pydantic message contract (`ChatRequest`, `ChatResponse`, `MemoryItem`)
- [x] Offline fallback so demos work without an API key

## Phase 2 — Voice loop

- [ ] Mic capture (WebRTC / `sounddevice`)
- [ ] STT (Whisper local or Deepgram/AssemblyAI cloud)
- [ ] Audio-emotion features (valence / arousal / label) — fused with text
- [ ] TTS with prosody control (ElevenLabs or Piper local)
- [ ] Real MQTT/ZeroMQ bus so the brain, ears, and mouth are decoupled processes

## Phase 3 — Hardware & vision

- [ ] Two OLED screens driven from Pi/ESP32; face poses over I²C/SPI
- [ ] Camera-based facial-expression fusion (FER2013 / DeepFace)
- [ ] Layered SOS with a graduated state machine and a *professional*
      crisis line first; opt-in trusted-contact only after L3 sustained

## Phase 4 — Memory upgrade

- [ ] Chroma or Qdrant + sentence-transformers embeddings
- [ ] Metadata filtering by valence + recency + topic
- [ ] Langfuse tracing for prompt/response tuning

---

## Three-person split

### Person A — Perception (ears / eyes)
- Owns mic capture, STT, audio-emotion features, later the camera path.
- Emits `{"audio_emotion": {...}, "transcript": "..."}` to the bus.
- Phase-1 stub: nothing to run — Person B works from typed text.

### Person B — Brain (this repo)
- Owns dialogue, memory, emotion fusion, crisis logic, safety copy.
- Consumes the transcript + audio_emotion; emits `ChatResponse`.
- Phase 1 delivered here.

### Person C — Actuation & platform (mouth / face / SOS)
- Owns TTS with prosody, OLED face animation from `emotion` field,
  the SOS delivery path (Twilio / phone), device bring-up.
- Phase-1 stub: browser UI already renders the face and SOS banner from
  the shared `ChatResponse` — same contract they'll consume on device.

The `ChatResponse` Pydantic model is the single contract between us all;
please break the build rather than silently changing its shape.
