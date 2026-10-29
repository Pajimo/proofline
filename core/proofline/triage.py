"""Customer video in, triage finding out: what's wrong, how sure, what to ask next, where to route it.

Spark 1.3 only describes what it sees and hears. Routing, safety stops and estimates are decided in code,
so a model can't send a price or skip a hard stop.

  route = stop   → a hard stop (gas, CO, electrical). Fixed message, owner told, no diagnosis.
          out_of_scope → clearly not this trade's work (a door for a plumber) and no water involved.
          visit  → low confidence or a needs-a-visit condition. Never a guess.
          more   → a likely fault but a key detail is missing: ask the next question.
          quote  → fault identified with enough evidence: draft an estimate for the owner to approve.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

from . import media
from .backends.meta import SPARK, MetaClient, output_text
from .extract import format_turns
from .pack import Pack
from .safety import Stop, check_text, wrap_untrusted
from .safety.guard import GUARD_INSTRUCTIONS, looks_like_injection

MIN_CONFIDENCE = 0.6  # below this a fault routes to "needs a visit"
DANGER_CONFIDENCE = 0.5  # the model check stops at a lower bar than diagnosis: false alarms are cheap
NOTHING_SEEN_QUESTION = ("I couldn't spot the problem in that video. What's going wrong? "
                         "If you can, send a short video close up of it.")  # packs override via trade.nothing_seen_question

TRIAGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["danger", "danger_confidence", "danger_reason", "in_scope", "problem_area", "fault_id",
                 "description", "confidence",
                 "evidence_t_start", "evidence_t_end", "highlight", "reading", "missing_detail",
                 "next_question", "needs_visit_reason", "likely_parts"],
    "properties": {
        "danger": {"type": "string", "enum": ["none", "gas", "carbon_monoxide", "electrical"]},
        "danger_confidence": {"type": "number"},
        "danger_reason": {"type": ["string", "null"]},
        "in_scope": {"type": "boolean"},
        "problem_area": {"type": "string"},
        "fault_id": {"type": ["string", "null"]},
        "description": {"type": "string"},
        "confidence": {"type": "number"},
        "evidence_t_start": {"type": "number"},
        "evidence_t_end": {"type": "number"},
        "highlight": {"type": ["string", "null"]},
        "reading": {"type": ["string", "null"]},
        "missing_detail": {"type": "boolean"},
        "next_question": {"type": ["string", "null"]},
        "needs_visit_reason": {"type": ["string", "null"]},
        "likely_parts": {"type": "array", "items": {"type": "string"}},
    },
}

PROMPT = """You help a UK {trade} triage a customer's problem from a short video the customer filmed at home.
You describe what you see and hear. You never give prices and never give DIY steps for gas or electrics.

{guard}

{catalogue}

Earlier in this conversation:
{history}

The customer's message:
{message}

What the customer said in the video (times in seconds):
{turns}

Report:
- danger: "gas" (gas smell, hissing gas meter), "carbon_monoxide" (CO alarm sounding, yellow/orange flame,
  soot marks, CO symptoms), "electrical" (burning smell, sparking, scorch marks, water on or near sockets,
  lights or the fuse box), else "none". danger_confidence 0-1 and a short danger_reason.
- in_scope: false only if the problem is clearly outside what this trade covers ({covers}), e.g. a stuck
  door for a plumber, AND no water, leak or damp is involved. If unsure, true.
- problem_area: a few words for what the problem is about, e.g. "kitchen tap", "patio door".
- fault_id: the best match from the list above, or null if it isn't one of them or you can't tell.
- description: one or two plain sentences for the plumber about what you can see, e.g. "Water beading
  on the 15mm compression nut under the kitchen sink."
- confidence: 0-1 that fault_id is right, from what is actually visible or said.
- evidence_t_start/evidence_t_end: the seconds that best show the problem.
- highlight: a short noun phrase for the object to outline on the video (one object, e.g. "tap",
  "pressure gauge", "pipe fitting"), or null.
- reading: any reading you can see, e.g. "pressure gauge at 0.4 bar", else null. Don't guess a number.
- missing_detail: true if one more video or answer would change the diagnosis or the job size.
- next_question: if missing_detail, the single most useful thing to ask, in plain friendly words.
  Prefer the follow-up questions listed for the fault. Else null.
- needs_visit_reason: set if any "needs a visit if" condition for the fault holds, else null.
- likely_parts: part ids from the list that the job will probably need. Can be empty."""


@dataclass
class Finding:
    route: str  # stop | out_of_scope | visit | more | quote
    fault_id: Optional[str]
    fault_name: Optional[str]
    description: str
    confidence: float
    evidence_t_start: float
    evidence_t_end: float
    highlight: Optional[str] = None
    reading: Optional[str] = None
    next_question: Optional[str] = None
    likely_parts: List[str] = field(default_factory=list)
    estimate: Optional[dict] = None  # {low, high, currency, wording}; only on route=quote
    safety: Optional[dict] = None  # Stop as a dict
    visit_reason: Optional[str] = None
    injection: Optional[str] = None  # flagged text, for logs and evals only
    problem_area: Optional[str] = None
    timings: dict = field(default_factory=dict)
    raw: Optional[dict] = None

    def to_dict(self) -> dict:
        return asdict(self)


def route(model: dict, pack: Pack, rules_stop: Optional[Stop]) -> Finding:
    """Decide what happens next from the model's report. Pure code; unit-tested."""
    fault = pack.faults.get(model.get("fault_id") or "")
    base = dict(fault_id=fault["id"] if fault else None, fault_name=fault["name"] if fault else None,
                description=model["description"], confidence=max(0.0, min(1.0, float(model["confidence"]))),
                evidence_t_start=float(model["evidence_t_start"]),
                evidence_t_end=float(max(model["evidence_t_end"], model["evidence_t_start"])),
                highlight=model.get("highlight"), reading=model.get("reading"),
                likely_parts=[p for p in model.get("likely_parts", []) if p in pack.parts], raw=model)

    stop = rules_stop
    if stop is None and model["danger"] != "none" and model["danger_confidence"] >= DANGER_CONFIDENCE:
        stop = Stop(kind=model["danger"], source="model", reason=model.get("danger_reason") or "")
    if stop is not None:
        return Finding(route="stop", safety=asdict(stop), **{**base, "next_question": None})

    if fault is None and model.get("in_scope") is False:
        return Finding(route="out_of_scope", problem_area=model.get("problem_area"), **base)

    if fault is None or base["confidence"] < MIN_CONFIDENCE:
        reason = "couldn't identify the fault from the video" if fault is None else "low confidence"
        if model.get("missing_detail") and model.get("next_question"):
            return Finding(route="more", next_question=model["next_question"], visit_reason=reason, **base)
        if fault is None and not model.get("needs_visit_reason"):
            # Nothing plumbing-related in shot (wrong video, no problem visible): ask, don't book a visit.
            question = pack.trade.get("nothing_seen_question") or NOTHING_SEEN_QUESTION
            return Finding(route="more", next_question=question, visit_reason=reason, **base)
        return Finding(route="visit", visit_reason=reason, **base)
    if model.get("needs_visit_reason"):
        return Finding(route="visit", visit_reason=model["needs_visit_reason"], **base)
    if model.get("missing_detail") and model.get("next_question"):
        return Finding(route="more", next_question=model["next_question"], **base)

    est = fault["estimate"]
    return Finding(route="quote", estimate={
        "low": float(est["low"]), "high": float(est["high"]), "currency": pack.currency,
        "wording": pack.trade.get("estimate_wording", "Estimate, subject to inspection.")}, **base)


def diagnose(video: Optional[str], pack: Pack, message: str = "", history: str = "",
             client: Optional[MetaClient] = None, work_dir: Optional[str] = None,
             effort: str = "medium") -> Finding:
    """Triage one customer turn: an optional video plus their text. Safety rules run before any model."""
    client = client or MetaClient()
    timings = {}
    injection = looks_like_injection(message)

    rules_stop = check_text(message, pack)
    if rules_stop and not video:
        return Finding(route="stop", fault_id=None, fault_name=None, description="", confidence=1.0,
                       evidence_t_start=0, evidence_t_end=0, safety=asdict(rules_stop), injection=injection)

    turns: List[dict] = []
    content = []
    if video:
        work = Path(work_dir or Path(video).with_suffix("")).resolve()
        work.mkdir(parents=True, exist_ok=True)
        t = time.time()
        mp4 = media.to_mp4_720p(video, str(work / "clip.mp4"))
        info = media.probe(mp4)
        timings["ffmpeg_s"] = round(time.time() - t, 1)
        if info.has_audio:
            t = time.time()
            wav = media.to_wav_16k(mp4, str(work / "clip.wav"))
            turns = client.transcribe(wav, mode="ENDPOINTING", keywords=pack.keywords()).get("turns", [])
            timings["transcribe_s"] = round(time.time() - t, 1)
        spoken = " ".join(t.get("transcript", "") for t in turns)
        rules_stop = rules_stop or check_text(spoken, pack)
        injection = injection or looks_like_injection(spoken)
        if rules_stop:  # a hard stop in the voice track: reply now, don't wait for Spark
            return Finding(route="stop", fault_id=None, fault_name=None, description="", confidence=1.0,
                           evidence_t_start=0, evidence_t_end=0, safety=asdict(rules_stop), injection=injection,
                           timings=timings, raw={"_turns": turns})
        t = time.time()
        fid = client.upload_file(mp4)["id"]
        timings["upload_s"] = round(time.time() - t, 1)
        content.append({"type": "input_file", "file_id": fid})
    else:
        fid = None

    prompt = PROMPT.format(trade=pack.trade.get("label", "tradesperson"), guard=GUARD_INSTRUCTIONS,
                           covers=", ".join(pack.trade.get("covers", [])) or "this trade's usual work",
                           catalogue=pack.fault_catalogue(),
                           history=wrap_untrusted(history or "(none)", "conversation_history"),
                           message=wrap_untrusted(message or "(no text)", "whatsapp_text"),
                           turns=wrap_untrusted(format_turns(turns), "video_audio"))
    body = {
        "model": SPARK,
        "reasoning": {"effort": effort},
        "max_output_tokens": 6000,
        "input": [{"type": "message", "role": "user",
                   "content": [{"type": "input_text", "text": prompt}, *content]}],
        "text": {"format": {"type": "json_schema", "name": "triage", "schema": TRIAGE_SCHEMA, "strict": False}},
    }
    t = time.time()
    try:
        resp = client.responses(body)
    finally:
        if fid:
            try:
                client.delete_file(fid)
            except Exception:  # noqa: BLE001
                pass
    timings["spark_s"] = round(time.time() - t, 1)
    text = output_text(resp)
    try:
        model = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"Spark returned non-JSON output: {text[:500]!r}") from exc
    import jsonschema

    jsonschema.validate(model, TRIAGE_SCHEMA)
    model["_usage"] = resp.get("usage")
    model["_turns"] = turns

    finding = route(model, pack, rules_stop)
    finding.injection = injection
    finding.timings = timings
    return finding


def main() -> None:
    import argparse

    from .backends import load_env
    from .safety import stop_message

    ap = argparse.ArgumentParser(description="Triage one customer video and/or message.")
    ap.add_argument("video", nargs="?")
    ap.add_argument("--message", default="")
    ap.add_argument("--pack", default="packs/plumbing.yaml")
    ap.add_argument("--out", help="working folder (default: next to the video)")
    a = ap.parse_args()
    load_env()
    pack = Pack.load(a.pack)
    f = diagnose(a.video, pack, message=a.message, work_dir=a.out)
    print(json.dumps({k: v for k, v in f.to_dict().items() if k != "raw"}, indent=2))
    if f.route == "stop":
        print("\nReply to customer (fixed text):\n" + stop_message(f.safety["kind"], pack))
    if a.video:
        out = Path(a.out or Path(a.video).with_suffix("")) / "finding.json"
        out.write_text(json.dumps(f.to_dict(), indent=2))
        print(f"\nFull output: {out}")


if __name__ == "__main__":
    main()
