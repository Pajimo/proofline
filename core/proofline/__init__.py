"""Proofline: video + narration → verified invoice line items."""
from __future__ import annotations

from .schema import EvidenceFrame, Job, LineItem, load_schema, validate_line

__all__ = ["analyze", "EvidenceFrame", "Job", "LineItem", "load_schema", "validate_line"]
__version__ = "0.0.1"


def analyze(video: str, price_list: str, backend: str = "meta") -> Job:
    """Turn a job video into verified line items.

    Pipeline (built from day 3): mask → transcribe → extract → verify → price.
    backend: "meta" (Muse Spark 1.3) or "baseten" (Muse Spark Open).
    """
    raise NotImplementedError("analyze() arrives on day 3 (29 Oct). See scripts/smoke for working API calls.")
