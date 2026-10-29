import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_pack import check  # noqa: E402


def test_plumbing_pack_is_valid():
    assert check(ROOT / "packs" / "plumbing.yaml") == []


def test_pack_without_gas_stop_fails(tmp_path):
    data = yaml.safe_load((ROOT / "packs" / "plumbing.yaml").read_text())
    data["safety"] = [s for s in data["safety"] if s["kind"] != "gas"] * 2
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(data))
    assert any("gas" in p for p in check(bad))


def test_estimate_must_say_subject_to_inspection(tmp_path):
    data = yaml.safe_load((ROOT / "packs" / "plumbing.yaml").read_text())
    data["trade"]["estimate_wording"] = "Fixed price."
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(data))
    assert check(bad)
