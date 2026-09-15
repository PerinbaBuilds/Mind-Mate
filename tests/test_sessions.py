"""Cross-session memory: the bond that survives 'new session'."""

import os
import tempfile

from app.memory import MemoryStore
from app.models import MemoryItem


def _store():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.unlink(tmp.name)
    return MemoryStore(tmp.name)


def test_sessions_are_isolated_but_profile_persists():
    s = _store()
    s1 = s.current_session_id("u")
    s.add(MemoryItem(user_id="u", role="user", text="I won my hackathon"), s1)
    s.add_session_summary("u", s1, "Talked about winning a hackathon.")
    s.set_fact("u", "name", "Perinba")

    s2 = s.start_new_session("u")
    s.add(MemoryItem(user_id="u", role="user", text="hey again"), s2)

    # the new conversation does not replay the old turns...
    assert len(s.session_turns("u", s2)) == 1
    # ...but the relationship is still there
    assert s.get_facts("u")["name"] == "Perinba"
    assert s.has_history("u")


def test_digest_mentions_name_and_past_conversation():
    s = _store()
    s.set_fact("u", "name", "Perinba")
    s.set_fact("u", "current_project", "a thinking processing unit")
    s.add_session_summary("u", 1, "Celebrated a hackathon win.")

    d = s.digest("u")
    assert "Perinba" in d
    assert "thinking processing unit" in d
    assert "hackathon" in d


def test_digest_empty_for_stranger():
    assert _store().digest("nobody") == ""


def test_forget_clears_everything():
    s = _store()
    s.add(MemoryItem(user_id="u", role="user", text="hi"), 1)
    s.set_fact("u", "name", "Perinba")
    s.add_session_summary("u", 1, "A chat.")

    s.wipe("u")

    assert s.get_facts("u") == {}
    assert s.recent_summaries("u") == []
    assert s.digest("u") == ""
    assert not s.has_history("u")


def test_fact_update_overwrites():
    s = _store()
    s.set_fact("u", "mood_trend", "struggling")
    s.set_fact("u", "mood_trend", "doing better")
    assert s.get_facts("u")["mood_trend"] == "doing better"
