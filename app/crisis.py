"""Crisis-detection heuristics.

For the review demo this is a keyword+phrase layer only. In a later
phase a second LLM classifier runs in parallel and both feed a state
machine (levels 0..3). Keep this file conservative: high recall > precision.
"""

from __future__ import annotations

import re

_LEVEL_3_PATTERNS = [
    r"\bkill (myself|me)\b",
    r"\bend (my|it) (life|all)\b",
    r"\bsuicid(e|al)\b",
    r"\bwant to die\b",
    r"\bno reason to live\b",
]

_LEVEL_2_PATTERNS = [
    r"\bhopeless\b",
    r"\bworthless\b",
    r"\bcan'?t go on\b",
    r"\bgive up\b",
    r"\bhurt myself\b",
    r"\bself[- ]harm\b",
]

_LEVEL_1_PATTERNS = [
    r"\bdepressed\b",
    r"\bnothing matters\b",
    r"\balone\b",
    r"\bexhausted\b",
]

_L3 = [re.compile(p, re.I) for p in _LEVEL_3_PATTERNS]
_L2 = [re.compile(p, re.I) for p in _LEVEL_2_PATTERNS]
_L1 = [re.compile(p, re.I) for p in _LEVEL_1_PATTERNS]


def assess(text: str) -> int:
    """Return 0..3 risk level."""
    if any(p.search(text) for p in _L3):
        return 3
    if any(p.search(text) for p in _L2):
        return 2
    if any(p.search(text) for p in _L1):
        return 1
    return 0


CRISIS_RESOURCE_LINE = (
    "If you are in immediate danger, please contact iCall India at "
    "9152987821 or the Vandrevala Foundation Helpline at 1860-2662-345 "
    "(24x7, free)."
)
