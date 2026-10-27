import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from proofline import LineItem, validate_line  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def sample_line(**overrides):
    line = LineItem(id="L1", kind="part", description="Ceramic tap cartridge", qty=1, unit="each",
                    unit_price=12.5, price=12.5, t_start=61.0, t_end=95.5, confidence=0.9,
                    source="both", evidence_status="verified", pack_item_id="ceramic_cartridge").to_dict()
    line.update(overrides)
    return line


def test_valid_line_passes():
    validate_line(sample_line())


def test_unknown_flag_rejected():
    import jsonschema
    with pytest.raises(jsonschema.ValidationError):
        validate_line(sample_line(flags=["looks_fine"]))


def test_plumbing_pack_parts_have_prices_and_sam_prompts():
    pack = yaml.safe_load((ROOT / "packs" / "plumbing.yaml").read_text())
    assert pack["currency"] == "GBP"
    for part in pack["parts"]:
        assert part["price"] >= 0 and part["sam_prompts"], part["id"]


def test_ground_truth_example_passes_checker():
    sys.path.insert(0, str(ROOT / "evals"))
    from check_ground_truth import check

    assert check(ROOT / "evals" / "ground_truth" / "_example_trap.yaml", {}) == []
