import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from proofline.pack import Pack  # noqa: E402
from proofline.safety import Stop  # noqa: E402
from proofline.triage import route  # noqa: E402

PACK = Pack.load(str(Path(__file__).resolve().parents[1] / "packs" / "plumbing.yaml"))


def model(**kw):
    base = dict(danger="none", danger_confidence=0.0, danger_reason=None, fault_id="dripping_tap",
                description="Cold tap dripping steadily.", confidence=0.85, evidence_t_start=2, evidence_t_end=6,
                highlight="tap", reading=None, missing_detail=False, next_question=None,
                needs_visit_reason=None, likely_parts=["tap_washer", "not_a_part"])
    base.update(kw)
    return base


def test_clear_fault_gets_estimate_range_from_pack():
    f = route(model(), PACK, None)
    assert f.route == "quote" and f.estimate["low"] == 65 and f.estimate["high"] == 110
    assert "subject to inspection" in f.estimate["wording"]
    assert f.likely_parts == ["tap_washer"]


def test_rules_stop_wins_over_any_diagnosis():
    f = route(model(), PACK, Stop(kind="gas", source="rules", matched=["smell gas"]))
    assert f.route == "stop" and f.estimate is None and f.safety["kind"] == "gas"


def test_model_danger_stops():
    f = route(model(danger="electrical", danger_confidence=0.7), PACK, None)
    assert f.route == "stop" and f.safety["source"] == "model"


def test_weak_model_danger_does_not_stop():
    assert route(model(danger="electrical", danger_confidence=0.2), PACK, None).route == "quote"


def test_low_confidence_goes_to_visit_not_guess():
    f = route(model(confidence=0.4), PACK, None)
    assert f.route == "visit" and f.estimate is None


def test_unknown_fault_asks_if_it_can():
    f = route(model(fault_id=None, missing_detail=True, next_question="Can you film under the sink?"), PACK, None)
    assert f.route == "more" and f.next_question


def test_missing_detail_asks_next_question():
    f = route(model(fault_id="low_boiler_pressure", missing_detail=True,
                    next_question="Can you film the pressure gauge?"), PACK, None)
    assert f.route == "more" and f.estimate is None


def test_needs_visit_condition():
    f = route(model(needs_visit_reason="water coming through a ceiling"), PACK, None)
    assert f.route == "visit"


def test_nothing_plumbing_in_shot_asks_instead_of_visit():
    f = route(model(fault_id=None, confidence=0.95, highlight="patio door"), PACK, None)
    assert f.route == "more" and "video" in f.next_question and f.estimate is None


def test_unknown_fault_with_visit_condition_still_visits():
    f = route(model(fault_id=None, needs_visit_reason="water coming through a ceiling"), PACK, None)
    assert f.route == "visit"


def test_out_of_scope_when_not_this_trade():
    f = route(model(fault_id=None, in_scope=False, problem_area="patio door"), PACK, None)
    assert f.route == "out_of_scope" and f.problem_area == "patio door"


def test_danger_beats_out_of_scope():
    f = route(model(fault_id=None, in_scope=False, danger="electrical", danger_confidence=0.8), PACK, None)
    assert f.route == "stop"
