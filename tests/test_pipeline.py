import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from proofline.pack import Pack  # noqa: E402
from proofline.pipeline import build_lines, labour_line  # noqa: E402
from proofline.schema import validate_line  # noqa: E402

PACK = Pack.load(str(Path(__file__).resolve().parents[1] / "packs" / "plumbing.yaml"))


def item(**kw):
    base = dict(part_id="ceramic_cartridge", description="cartridge", qty=1, t_start=10, t_end=20,
                seen_in_video=True, said_in_narration=True, transcript_quote="new cartridge in",
                price_spoken=None, confidence=0.9)
    base.update(kw)
    return base


def lines_for(*items):
    return build_lines({"items": list(items)}, PACK, "job.mp4", offset=300)


def test_verified_line_priced_from_pack_with_offset():
    (line,) = lines_for(item())
    assert line.evidence_status == "verified" and not line.needs_review
    assert line.price == 12.5 and line.t_start == 310 and line.proof_url == "job.mp4#t=310,320"
    validate_line(line.to_dict())


def test_said_not_seen_is_flagged():
    (line,) = lines_for(item(seen_in_video=False))
    assert line.evidence_status == "narration_only" and "no_evidence" in line.flags


def test_spoken_price_is_ignored_and_flagged():
    (line,) = lines_for(item(price_spoken=30))
    assert line.price == 12.5 and "price_spoken_aloud" in line.flags


def test_unknown_part_has_no_price():
    (line,) = lines_for(item(part_id=None, description="mystery widget"))
    assert line.price is None and "not_in_price_list" in line.flags
    validate_line(line.to_dict())


def test_gas_work_is_blocked():
    (line,) = lines_for(item(part_id=None, description="gas valve on boiler"))
    assert "excluded_work" in line.flags and line.price is None


def test_labour_rounds_up_with_minimum():
    assert PACK.labour_hours(10) == 1.0
    assert PACK.labour_hours(70) == 1.25
    line = labour_line([{"seen_in_video": True}], 70, PACK, "job.mp4", 0, 4200, 3)
    assert line.price == 75.0
    validate_line(line.to_dict())
