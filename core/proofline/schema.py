"""Verified line items: the core data type Proofline produces."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

SCHEMA_PATH = Path(__file__).parent / "schemas" / "verified_line_item.schema.json"

# Lines with any of these statuses need a human look before the invoice can be sent.
NEEDS_REVIEW = {"narration_only", "visual_only", "missing"}


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


@dataclass
class EvidenceFrame:
    t: float
    role: str  # before | during | after
    frame_index: Optional[int] = None
    image: Optional[str] = None
    box: Optional[List[float]] = None
    sam_prompt: Optional[str] = None


@dataclass
class LineItem:
    id: str
    kind: str  # part | labour | callout | other
    description: str
    qty: float
    unit: str
    unit_price: Optional[float]
    price: Optional[float]
    t_start: float
    t_end: float
    confidence: float
    source: str
    evidence_status: str = "missing"
    evidence_frames: List[EvidenceFrame] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    currency: str = "GBP"
    pack_item_id: Optional[str] = None
    transcript_quote: Optional[str] = None
    proof_url: Optional[str] = None

    @property
    def needs_review(self) -> bool:
        return self.evidence_status in NEEDS_REVIEW or bool(self.flags)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Job:
    video: str
    lines: List[LineItem] = field(default_factory=list)

    @property
    def flagged(self) -> List[LineItem]:
        return [line for line in self.lines if line.needs_review]

    @property
    def total(self) -> float:
        return round(sum(line.price or 0 for line in self.lines), 2)


def validate_line(data: dict) -> None:
    """Raise jsonschema.ValidationError if data isn't a valid line item.

    The Meta API's strict mode defaults to false, so every model output goes through this.
    """
    import jsonschema

    jsonschema.validate(data, load_schema())
