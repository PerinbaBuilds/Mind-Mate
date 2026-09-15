"""Provider-agnostic tests for the LLM facade.

Network calls to Groq / Anthropic are avoided by stubbing the provider.
"""

from app.llm import TherapistLLM, _parse_reply
from app.models import EmotionState, MemoryItem


class _Fake:
    name = "fake"
    model = "fake-1"

    def __init__(self, canned):
        self.canned = canned
        self.last_messages = None

    def complete(self, system, messages):
        self.last_messages = messages
        return self.canned


def test_parse_valid_json():
    reply, mood, used = _parse_reply(
        '{"reply":"hey, that sounds rough","mood":"sadness","used_memory":true}'
    )
    assert reply == "hey, that sounds rough"
    assert mood == "sadness"
    assert used is True


def test_parse_unknown_mood_falls_back():
    reply, mood, _ = _parse_reply('{"reply":"ok","mood":"wobbly","used_memory":false}')
    assert reply == "ok"
    assert mood == "neutral"


def test_parse_junk_wrapper():
    reply, mood, _ = _parse_reply(
        'Sure! Here you go: {"reply":"nice","mood":"joy","used_memory":false} thanks!'
    )
    assert reply == "nice"
    assert mood == "joy"


def test_history_and_context_are_forwarded():
    llm = TherapistLLM()
    fake = _Fake('{"reply":"remembered!","mood":"joy","used_memory":true}')
    llm.provider = fake

    history = [
        MemoryItem(user_id="u", role="user", text="I won my hackathon today"),
        MemoryItem(user_id="u", role="assistant", text="that's huge!"),
    ]
    reply, mood, used = llm.reply(
        message="but dad still hasn't said anything",
        emotion=EmotionState(label="sadness", valence=-0.5, arousal=0.4),
        sos_level=0,
        recalled=history[0],
        history=history,
    )
    assert reply == "remembered!"
    assert mood == "joy"
    assert used is True

    # history + current context are both in the messages payload
    assert fake.last_messages[0]["content"] == "I won my hackathon today"
    assert fake.last_messages[1]["content"] == "that's huge!"
    assert "[RECALLED_MEMORY" in fake.last_messages[-1]["content"]
    assert "[USER] but dad" in fake.last_messages[-1]["content"]
