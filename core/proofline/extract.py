"""Muse Spark 1.3 reads the job video plus the timestamped transcript and returns candidate lines.

The model only reports what it saw and heard. Prices, evidence status and flags are decided
in code (pipeline.py) so a model can't put an unproven line on an invoice.
"""
from __future__ import annotations

import json
from typing import List

from .backends.meta import SPARK, MetaClient, output_text
from .pack import Pack

EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["job_type", "summary", "work_start", "work_end", "steps", "items", "shown_not_used"],
    "properties": {
        "job_type": {"type": "string"},
        "summary": {"type": "string"},
        "work_start": {"type": "number"},
        "work_end": {"type": "number"},
        "steps": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["action", "t_start", "t_end", "seen_in_video"],
            "properties": {
                "action": {"type": "string"},
                "t_start": {"type": "number"},
                "t_end": {"type": "number"},
                "seen_in_video": {"type": "boolean"},
            }}},
        "items": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["part_id", "description", "qty", "t_start", "t_end", "seen_in_video",
                         "said_in_narration", "transcript_quote", "price_spoken", "confidence"],
            "properties": {
                "part_id": {"type": ["string", "null"]},
                "description": {"type": "string"},
                "qty": {"type": "number"},
                "t_start": {"type": "number"},
                "t_end": {"type": "number"},
                "seen_in_video": {"type": "boolean"},
                "said_in_narration": {"type": "boolean"},
                "transcript_quote": {"type": ["string", "null"]},
                "price_spoken": {"type": ["number", "null"]},
                "confidence": {"type": "number"},
            }}},
        "shown_not_used": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["description", "t"],
            "properties": {"part_id": {"type": ["string", "null"]}, "description": {"type": "string"},
                           "t": {"type": "number"}}}},
    },
}

PROMPT = """You are checking a UK tradesperson's job video so an invoice can be built from evidence.
The video is filmed from the tradesperson's chest. The transcript below is their narration, with times in seconds.

{catalogue}

Transcript turns:
{turns}

Report, with times in seconds from the start of this video:
- steps: each piece of work, with seen_in_video true only if you can actually see it happening.
- items: each part FITTED or CONSUMED in this job. Use the part id from the list above, or null if it
  isn't on the list. For each item:
  - seen_in_video: true only if the new part is clearly visible being fitted or in use.
  - said_in_narration: true if the narration mentions fitting or using it. Quote that turn in transcript_quote.
  - t_start/t_end: the span that best shows the part going in (or being talked about, if never seen).
  - price_spoken: the amount if a price for it is said out loud, else null. Do not use it for anything else.
  - confidence: 0 to 1.
- shown_not_used: parts shown or held up but NOT fitted (spares, packaging put back). Never list these as items.
- work_start/work_end: when hands-on work starts and ends.

Rules: never invent a part that is neither seen nor said. A part that is said but never seen is still
listed, with seen_in_video false. Don't list tools (wrenches, screwdrivers) or fixed fixtures (sinks,
existing pipes) as items. Do not include labour or prices as items."""


def format_turns(turns: List[dict]) -> str:
    if not turns:
        return "(no narration)"
    return "\n".join(f"[{t['startMs'] / 1000:.1f}-{t['endMs'] / 1000:.1f}] {t.get('transcript', '')}" for t in turns)


def extract(client: MetaClient, file_id: str, turns: List[dict], pack: Pack, effort: str = "medium") -> dict:
    body = {
        "model": SPARK,
        "reasoning": {"effort": effort},
        "max_output_tokens": 8000,
        "input": [{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": PROMPT.format(catalogue=pack.prompt_catalogue(), turns=format_turns(turns))},
            {"type": "input_file", "file_id": file_id},
        ]}],
        "text": {"format": {"type": "json_schema", "name": "job_extraction", "schema": EXTRACTION_SCHEMA,
                            "strict": False}},
    }
    resp = client.responses(body)
    text = output_text(resp)
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"Spark returned non-JSON output: {text[:500]!r}") from exc
    # strict defaults to false, so check the shape ourselves.
    import jsonschema

    jsonschema.validate(data, EXTRACTION_SCHEMA)
    data["_usage"] = resp.get("usage")
    return data
