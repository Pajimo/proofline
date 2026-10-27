"""Check ground-truth files in evals/ground_truth/ before an eval run.

Usage: python evals/check_ground_truth.py [--examples] [files...]
Files starting with "_" (the template and examples) are skipped unless --examples is passed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GT_DIR = ROOT / "evals" / "ground_truth"

SETS = {"job", "trap", "privacy", "narration_only"}
ID_PREFIX = {"job": "job", "trap": "trap", "privacy": "priv", "narration_only": "narr"}
KINDS = {"part", "labour", "callout", "other"}
TRAP_TYPES = {"shown_not_used", "named_not_shown", "price_spoken_aloud"}
TRAP_EXPECT = {"no_line", "flag_narration_only", "use_price_list"}
PRIVACY_TYPES = {"face", "framed_photo", "house_number", "envelope", "other"}


def seconds(value) -> float:
    """'mm:ss' or 'h:mm:ss' → seconds. Raises ValueError on bad input."""
    if isinstance(value, (int, float)):
        return float(value)
    parts = [float(p) for p in str(value).split(":")]
    if not 1 <= len(parts) <= 3:
        raise ValueError(value)
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def check(path: Path, pack_cache: dict) -> list:
    errors = []
    err = errors.append
    try:
        gt = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        return [f"not valid YAML: {exc}"]

    clip_id, set_ = gt.get("clip_id"), gt.get("set")
    if set_ not in SETS:
        err(f"set must be one of {sorted(SETS)}, got {set_!r}")
    elif not str(clip_id).startswith(ID_PREFIX[set_]):
        err(f"clip_id {clip_id!r} should start with {ID_PREFIX[set_]!r} for set {set_!r}")
    if not path.name.startswith("_") and path.stem != clip_id:
        err(f"file name {path.name} doesn't match clip_id {clip_id!r}")

    pack_name = gt.get("pack", "plumbing")
    if pack_name not in pack_cache:
        pack_path = ROOT / "packs" / f"{pack_name}.yaml"
        pack_cache[pack_name] = yaml.safe_load(pack_path.read_text()) if pack_path.exists() else None
    pack = pack_cache[pack_name]
    if pack is None:
        return errors + [f"pack {pack_name!r} not found in packs/"]
    part_ids = {p["id"] for p in pack["parts"]}
    job_ids = {j["id"] for j in pack["jobs"]} | {"other"}
    if gt.get("job_type") not in job_ids:
        err(f"job_type {gt.get('job_type')!r} not in pack jobs {sorted(job_ids)}")

    try:
        duration = seconds(gt.get("duration", 0))
    except ValueError:
        duration = 0
        err(f"duration {gt.get('duration')!r} isn't mm:ss")
    if duration <= 0:
        err("duration is 0. Fill it in.")

    def time_field(where: str, value, required: bool = True):
        if value is None:
            if required:
                err(f"{where}: missing time")
            return None
        try:
            t = seconds(value)
        except ValueError:
            err(f"{where}: {value!r} isn't mm:ss")
            return None
        if duration and t > duration + 1:
            err(f"{where}: {value} is after the end of the clip ({gt.get('duration')})")
        return t

    def span(where: str, start, end):
        s, e = time_field(f"{where} start", start), time_field(f"{where} end", end)
        if s is not None and e is not None and e < s:
            err(f"{where}: end {end} is before start {start}")
        if s == e == 0:
            err(f"{where}: start and end are both 00:00. Fill them in.")

    steps = gt.get("steps") or []
    if set_ == "job" and not steps:
        err("a job needs at least one step")
    for i, step in enumerate(steps):
        if not step.get("name"):
            err(f"steps[{i}]: missing name")
        span(f"steps[{i}] ({step.get('name')})", step.get("start"), step.get("end"))

    for i, part in enumerate(gt.get("parts_used") or []):
        where = f"parts_used[{i}] ({part.get('part')})"
        if part.get("part") not in part_ids:
            err(f"{where}: unknown part id. Pack has {sorted(part_ids)}")
        if not part.get("qty", 0) > 0:
            err(f"{where}: qty must be > 0")
        if part.get("shown"):
            time_field(f"{where} first_seen", part.get("first_seen"))
            time_field(f"{where} fitted_at", part.get("fitted_at"))
        time_field(f"{where} old_part_seen", part.get("old_part_seen"), required=False)

    used = {p.get("part") for p in gt.get("parts_used") or []}
    for i, line in enumerate(gt.get("expected_invoice") or []):
        where = f"expected_invoice[{i}]"
        if line.get("kind") not in KINDS:
            err(f"{where}: kind must be one of {sorted(KINDS)}")
        if line.get("kind") == "part":
            if line.get("part") not in part_ids:
                err(f"{where}: unknown part id {line.get('part')!r}")
            elif line.get("part") not in used:
                err(f"{where}: invoices {line.get('part')!r}, but it isn't in parts_used")
        if not line.get("qty", 0) > 0:
            err(f"{where}: qty must be > 0")
        span(where, line.get("proof_start"), line.get("proof_end"))

    traps = gt.get("traps") or []
    if set_ == "trap" and not traps:
        err("a trap clip needs at least one entry in traps")
    for i, trap in enumerate(traps):
        where = f"traps[{i}]"
        if trap.get("type") not in TRAP_TYPES:
            err(f"{where}: type must be one of {sorted(TRAP_TYPES)}")
        if trap.get("expect") not in TRAP_EXPECT:
            err(f"{where}: expect must be one of {sorted(TRAP_EXPECT)}")
        if trap.get("part") not in part_ids:
            err(f"{where}: unknown part id {trap.get('part')!r}")
        if trap.get("type") == "shown_not_used" and trap.get("part") in used:
            err(f"{where}: {trap.get('part')!r} is a shown_not_used trap but is also in parts_used")
        time_field(f"{where} at", trap.get("at"))

    privacy = gt.get("privacy") or []
    if set_ == "privacy" and not privacy:
        err("a privacy clip needs at least one entry in privacy")
    for i, item in enumerate(privacy):
        if item.get("type") not in PRIVACY_TYPES:
            err(f"privacy[{i}]: type must be one of {sorted(PRIVACY_TYPES)}")
        span(f"privacy[{i}]", item.get("first_seen"), item.get("last_seen"))

    video = gt.get("video")
    if video and not (ROOT / video).exists() and not path.name.startswith("_"):
        print(f"  warning: {path.name}: video {video} not found (fine if it's on another machine)")
    return errors


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    include_examples = "--examples" in sys.argv
    files = [Path(a) for a in args] or sorted(GT_DIR.glob("*.yaml"))
    files = [f for f in files if include_examples or args or not f.name.startswith("_")]
    if not files:
        print("No ground-truth files yet. Copy evals/ground_truth/_template.yaml to start.")
        return 0
    pack_cache: dict = {}
    failed = 0
    for f in files:
        errors = check(f, pack_cache)
        print(f"{'OK  ' if not errors else 'FAIL'} {f.name}")
        for e in errors:
            print(f"     - {e}")
        failed += bool(errors)
    print(f"\n{len(files) - failed}/{len(files)} files OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
