"""Plain-text invoice draft for the terminal. The PDF version comes later."""
from __future__ import annotations

import math

from .schema import Job

STATUS_MARK = {"verified": "✓ seen + said", "visual_only": "◐ seen only", "narration_only": "✗ said, not seen",
               "missing": "✗ no evidence"}


def _money(v):
    return "   —   " if v is None else f"£{v:7.2f}"


def _t(s: float, up: bool = False) -> str:
    s = math.ceil(s) if up else math.floor(s)
    return f"{s // 60}:{s % 60:02d}"


def render(job: Job) -> str:
    out = []
    meta = job.meta
    out.append("PROOFLINE: INVOICE DRAFT (not sent; needs your approval)")
    out.append("=" * 96)
    if meta.get("summary"):
        out.append(meta["summary"])
        out.append("-" * 96)
    out.append(f"{'#':<4}{'Description':<40}{'Qty':>6}{'Price':>11}  {'Proof':<13}{'Evidence':<18}")
    for line in job.lines:
        qty = f"{line.qty:g}"
        out.append(f"{line.id:<4}{line.description[:39]:<40}{qty:>6}{_money(line.price):>11}  "
                   f"{_t(line.t_start) + '–' + _t(line.t_end, up=True):<13}{STATUS_MARK[line.evidence_status]:<18}")
    out.append("-" * 96)
    ok = round(sum(l.price or 0 for l in job.lines if not l.needs_review), 2)
    out.append(f"{'Total, proven lines only':<50}{_money(ok):>11}")
    out.append(f"{'Total, if you approve every flagged line':<50}{_money(job.total):>11}")

    flagged = job.flagged
    if flagged:
        out.append("")
        out.append(f"NEEDS YOUR CHECK ({len(flagged)})")
        for line in flagged:
            why = ", ".join(line.flags) or line.evidence_status
            quote = f'  narration: "{line.transcript_quote}"' if line.transcript_quote else ""
            out.append(f"  {line.id} {line.description}: {why}{quote}")
    snu = meta.get("shown_not_used") or []
    if snu:
        out.append("")
        out.append("Shown but not used (left off the invoice):")
        for s in snu:
            out.append(f"  - {s['description']} at {_t(s['t'])}")
    out.append("")
    out.append("Proof links: " + ", ".join(f"{l.id} → {l.proof_url}" for l in job.lines))
    t = meta.get("timings")
    if t:
        out.append(f"Timings: {t}")
    return "\n".join(out)
