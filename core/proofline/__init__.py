"""Proofline: video + narration → verified invoice line items."""
from __future__ import annotations

from .schema import EvidenceFrame, Job, LineItem, load_schema, validate_line

__all__ = ["analyze", "EvidenceFrame", "Job", "LineItem", "load_schema", "validate_line"]
__version__ = "0.0.1"


def analyze(video: str, price_list: str, backend: str = "meta", **kwargs) -> Job:
    """Turn a job video into verified line items.

    Pipeline: transcribe → extract → price → flag. Masking and SAM evidence frames come next.
    backend: "meta" (Muse Spark 1.3). "baseten" (Muse Spark Open) is still to come.
    """
    if backend != "meta":
        raise NotImplementedError(f"backend {backend!r} isn't wired up yet")
    from .pipeline import analyze as _analyze

    return _analyze(video, price_list, **kwargs)
