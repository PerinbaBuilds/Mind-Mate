from app import crisis, emotion


def test_positive():
    e = emotion.score_text("I feel so happy and grateful today")
    assert e.label == "joy"
    assert e.valence > 0.5


def test_negative():
    e = emotion.score_text("I feel lonely and tired and empty")
    assert e.label == "sadness"
    assert e.valence < -0.3


def test_neutral():
    e = emotion.score_text("The train arrived at nine")
    assert e.label == "neutral"


def test_crisis_levels():
    assert crisis.assess("I want to kill myself") == 3
    assert crisis.assess("I feel hopeless and worthless") == 2
    assert crisis.assess("I feel so alone lately") == 1
    assert crisis.assess("I went for a walk") == 0
