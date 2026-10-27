"""video → transcript → Spark extraction → priced, evidence-checked line items.

Not yet included: SAM masking and evidence frames, Wonder drafting, and the Baseten backend.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import List, Optional

from . import media
from .backends.meta import MetaClient
from .extract import extract
from .pack import Pack
from .schema import Job, LineItem, validate_line


def proof_url(video_name: str, t0: float, t1: float) -> str:
    """Media-fragment link to the masked video. Whole seconds, widened outwards so the proof is inside."""
    return f"{video_name}#t={math.floor(t0)},{math.ceil(t1)}"


def _status(seen: bool, said: bool) -> str:
    if seen and said:
        return "verified"
    if seen:
        return "visual_only"
    if said:
        return "narration_only"
    return "missing"


def build_lines(extraction: dict, pack: Pack, video_name: str, offset: float = 0.0,
                start_index: int = 1) -> List[LineItem]:
    """Turn one clip's extraction into invoice lines. Prices come only from the pack."""
    lines: List[LineItem] = []
    n = start_index

    for item in extraction["items"]:
        t0, t1 = offset + item["t_start"], offset + max(item["t_end"], item["t_start"])
        status = _status(item["seen_in_video"], item["said_in_narration"])
        flags: List[str] = []
        if status in ("narration_only", "missing"):
            flags.append("no_evidence")
        part = pack.parts.get(item["part_id"] or "")
        unit_price = pack.part_price(item["part_id"])
        if unit_price is None:
            flags.append("not_in_price_list")
        if item.get("price_spoken") is not None:
            flags.append("price_spoken_aloud")
        if item["confidence"] < 0.5:
            flags.append("low_confidence")
        if pack.excluded_match(f"{item['description']} {item.get('transcript_quote') or ''}"):
            flags.append("excluded_work")
            unit_price = None
        qty = item["qty"] if item["qty"] > 0 else 1
        lines.append(LineItem(
            id=f"L{n}", kind="part",
            description=part["name"] if part else item["description"],
            qty=qty, unit=part["unit"] if part else "each",
            unit_price=unit_price, price=round(qty * unit_price, 2) if unit_price is not None else None,
            t_start=round(t0, 1), t_end=round(t1, 1),
            confidence=max(0.0, min(1.0, float(item["confidence"]))),
            source={"verified": "both", "visual_only": "video"}.get(status, "narration"),
            evidence_status=status, flags=flags, pack_item_id=part["id"] if part else None,
            transcript_quote=item.get("transcript_quote"),
            proof_url=proof_url(video_name, t0, t1),
        ))
        n += 1
    return lines


def labour_line(steps: List[dict], work_minutes: float, pack: Pack, video_name: str,
                t_start: float, t_end: float, index: int) -> LineItem:
    seen = any(s["seen_in_video"] for s in steps)
    hours = pack.labour_hours(work_minutes)
    rate = float(pack.labour["rate_per_hour"])
    return LineItem(
        id=f"L{index}", kind="labour", description=f"Labour ({work_minutes:.0f} min on video)" if work_minutes >= 1
        else f"Labour ({work_minutes * 60:.0f} s on video)",
        qty=hours, unit="hour", unit_price=rate, price=round(hours * rate, 2),
        t_start=round(t_start, 1), t_end=round(t_end, 1), confidence=1.0 if seen else 0.5,
        source="video" if seen else "narration", evidence_status="verified" if seen else "narration_only",
        flags=[] if seen else ["no_evidence"], proof_url=proof_url(video_name, t_start, t_end),
    )


def analyze(video: str, price_list: str, work_dir: Optional[str] = None, client: Optional[MetaClient] = None,
            log=print) -> Job:
    pack = Pack.load(price_list)
    client = client or MetaClient()
    work = Path(work_dir or Path(video).with_suffix("")).resolve()
    work.mkdir(parents=True, exist_ok=True)
    timings = {}

    t = time.time()
    clips = media.prepare(video, str(work / "clips"))
    timings["ffmpeg_s"] = round(time.time() - t, 1)
    log(f"prepared {len(clips)} clip(s) in {timings['ffmpeg_s']}s")

    job = Job(video=str(video))
    all_steps: List[dict] = []
    extractions = []
    work_start, work_end = None, 0.0
    for clip in clips:
        off = clip["offset_s"]
        t = time.time()
        turns = []
        if clip["wav"]:
            turns = client.transcribe(clip["wav"], mode="ENDPOINTING", keywords=pack.keywords()).get("turns", [])
        timings.setdefault("transcribe_s", 0)
        timings["transcribe_s"] += round(time.time() - t, 1)
        log(f"clip {clip['index']}: {len(turns)} narration turn(s)")

        t = time.time()
        fid = client.upload_file(clip["mp4"])["id"]
        try:
            ex = extract(client, fid, turns, pack)
        finally:
            try:
                client.delete_file(fid)
            except Exception:  # noqa: BLE001
                pass
        timings.setdefault("spark_s", 0)
        timings["spark_s"] += round(time.time() - t, 1)
        log(f"clip {clip['index']}: {len(ex['items'])} item(s), {len(ex['steps'])} step(s), "
            f"{len(ex['shown_not_used'])} shown-not-used")
        ex["_turns"] = turns
        ex["_offset"] = off
        extractions.append(ex)

        job.lines += build_lines(ex, pack, Path(video).name, off, start_index=len(job.lines) + 1)
        all_steps += ex["steps"]
        # Labour covers the whole job: first step start to last step end, seen or said.
        spans = [(s["t_start"], s["t_end"]) for s in ex["steps"]] or [(ex["work_start"], ex["work_end"])]
        clip_start, clip_end = off + min(a for a, _ in spans), off + max(b for _, b in spans)
        work_start = clip_start if work_start is None else min(work_start, clip_start)
        work_end = max(work_end, clip_end)

    minutes = max(0.0, work_end - (work_start or 0.0)) / 60.0
    job.lines.append(labour_line(all_steps, minutes, pack, Path(video).name, work_start or 0.0, work_end,
                                 len(job.lines) + 1))

    for line in job.lines:
        validate_line(line.to_dict())

    (work / "job.json").write_text(json.dumps({
        "video": str(video), "pack": pack.name, "timings": timings,
        "lines": [line.to_dict() for line in job.lines],
        "shown_not_used": [s for ex in extractions for s in ex["shown_not_used"]],
        "extractions": extractions,
    }, indent=2))
    job.meta = {"timings": timings, "work_dir": str(work), "pack": pack,
                "shown_not_used": [s for ex in extractions for s in ex["shown_not_used"]],
                "summary": " ".join(ex["summary"] for ex in extractions)}
    return job
