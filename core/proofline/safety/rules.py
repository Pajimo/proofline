"""Keyword hard stops from the pack's safety section. Runs before any model sees the message.

False positives are acceptable ("I can't smell gas" still stops); false negatives are not.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# Most severe first: if a message trips several rules, the first one decides the reply.
SEVERITY = ["gas", "carbon_monoxide", "electrical"]


@dataclass
class Stop:
    kind: str  # gas | carbon_monoxide | electrical
    source: str  # rules | model
    matched: List[str] = field(default_factory=list)
    reason: str = ""


def normalise(text: str) -> str:
    text = text.lower().replace("’", "'")
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def check_text(text: str, pack) -> Optional[Stop]:
    """The most severe hard stop this text triggers, if any."""
    low = f" {normalise(text)} "
    hits = []
    for rule in pack.safety:
        matched = [k for k in rule.get("keywords", []) if f" {normalise(k)} " in low]
        if matched:
            hits.append(Stop(kind=rule["kind"], source="rules", matched=matched))
    if not hits:
        return None
    return sorted(hits, key=lambda s: SEVERITY.index(s.kind) if s.kind in SEVERITY else 99)[0]


def stop_message(kind: str, pack) -> str:
    """The fixed reply for a hard stop. Never model-written."""
    rule = next(r for r in pack.safety if r["kind"] == kind)
    return rule["message"].format(owner=pack.trade.get("owner_name", "the owner")).strip()
