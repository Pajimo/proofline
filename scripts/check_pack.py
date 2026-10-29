"""Check trade packs before they're used or merged: python scripts/check_pack.py packs/*.yaml

Schema first (core/proofline/schemas/pack.schema.json), then rules the schema can't express.
"""
import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "core" / "proofline" / "schemas" / "pack.schema.json").read_text())
REQUIRED_STOPS = {"gas", "carbon_monoxide", "electrical"}
EMERGENCY = {"gas": "0800 111 999", "carbon_monoxide": "0800 111 999", "electrical": "999"}


def check(path: Path) -> list:
    data = yaml.safe_load(path.read_text())
    problems = [f"{'/'.join(map(str, e.path)) or '(top)'}: {e.message}"
                for e in jsonschema.Draft202012Validator(SCHEMA).iter_errors(data)]
    if problems:
        return problems
    kinds = {s["kind"] for s in data["safety"]}
    if REQUIRED_STOPS - kinds:
        problems.append(f"safety: missing hard stops {sorted(REQUIRED_STOPS - kinds)}")
    for s in data["safety"]:
        if EMERGENCY[s["kind"]] not in s["message"]:
            problems.append(f"safety/{s['kind']}: message must give {EMERGENCY[s['kind']]}")
        if "{owner}" not in s["message"]:
            problems.append(f"safety/{s['kind']}: message should tell the customer {{owner}} has been told")
    parts = {p["id"] for p in data["parts"]}
    for ids in (data["faults"], data["parts"]):
        seen = [x["id"] for x in ids]
        dupes = {i for i in seen if seen.count(i) > 1}
        if dupes:
            problems.append(f"duplicate ids: {sorted(dupes)}")
    for f in data["faults"]:
        if f["estimate"]["low"] > f["estimate"]["high"]:
            problems.append(f"faults/{f['id']}: estimate low is above high")
        for p in f["likely_parts"]:
            if p not in parts:
                problems.append(f"faults/{f['id']}: likely part {p!r} isn't in parts")
    return problems


if __name__ == "__main__":
    bad = 0
    for arg in sys.argv[1:]:
        problems = check(Path(arg))
        print(f"{'OK  ' if not problems else 'FAIL'} {arg}")
        for p in problems:
            print(f"     - {p}")
        bad += bool(problems)
    sys.exit(1 if bad else 0)
