import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from proofline.bot import Bot  # noqa: E402
from proofline.channels.whatsapp import Inbound  # noqa: E402
from proofline.pack import Pack  # noqa: E402
from proofline.triage import Finding  # noqa: E402

PACK = Pack.load(str(Path(__file__).resolve().parents[1] / "packs" / "plumbing.yaml"))
OWNER, CUSTOMER = "447700900999", "447700900123"


class FakeWA:
    def __init__(self):
        self.sent = []

    def send_text(self, to, text, reply_to=None):
        self.sent.append((to, "text", text))

    def send_buttons(self, to, text, buttons, reply_to=None):
        self.sent.append((to, "buttons", text, buttons))

    def send_video(self, to, path, caption=""):
        self.sent.append((to, "video", caption))

    def download_media(self, media_id, dest):
        p = Path(dest) / f"{media_id}.mp4"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        return p

    def mark_read(self, message_id):
        pass

    def to(self, who):
        return [s for s in self.sent if s[0] == who]


def finding(route, **kw):
    base = dict(route=route, fault_id="dripping_tap", fault_name="Dripping tap", description="Cold tap dripping.",
                confidence=0.9, evidence_t_start=1, evidence_t_end=4)
    if route == "quote":
        base["estimate"] = {"low": 65.0, "high": 110.0, "currency": "GBP", "wording": "Estimate, subject to inspection."}
    base.update(kw)
    return Finding(**base)


def bot(tmp_path, result=None, calls=None):
    def fake_diagnose(video, pack, message="", history="", work_dir=None):
        if calls is not None:
            calls.append((video, message, history))
        return result
    return Bot(FakeWA(), PACK, owner=OWNER, work_dir=str(tmp_path), diagnose_fn=fake_diagnose, background=False,
               log=lambda s: None)


def msg(type_, text="", sender=CUSTOMER, **kw):
    return Inbound(sender=sender, message_id=f"wamid.{type_}{text}{kw}", type=type_, timestamp=0, text=text, **kw)


def test_gas_message_stops_without_triage(tmp_path):
    calls = []
    b = bot(tmp_path, calls=calls)
    b.handle(msg("text", "I can smell gas in the kitchen"))
    texts = [s[2] for s in b.wa.to(CUSTOMER)]
    assert any("0800 111 999" in t for t in texts) and calls == []
    assert any("SAFETY STOP" in s[2] for s in b.wa.to(OWNER))


def test_first_message_says_it_is_an_ai(tmp_path):
    b = bot(tmp_path, result=finding("more", next_question="Is it hot or cold?"))
    b.handle(msg("text", "my tap drips"))
    first = b.wa.to(CUSTOMER)[0][2]
    assert "assistant" in first and "AI" in first


def test_quote_goes_to_owner_not_customer(tmp_path):
    b = bot(tmp_path, result=finding("quote"))
    b.handle(msg("video", media_id="m1"))
    assert not any("£" in s[2] for s in b.wa.to(CUSTOMER))
    owner_buttons = [s for s in b.wa.to(OWNER) if s[1] == "buttons"]
    assert owner_buttons and "£65–£110" in owner_buttons[0][2]


def test_owner_approve_sends_estimate_once(tmp_path):
    b = bot(tmp_path, result=finding("quote"))
    b.handle(msg("video", media_id="m1"))
    (job_id,) = b.jobs
    b.handle(msg("interactive", "Approve", sender=OWNER, button_id=f"approve:{job_id}"))
    b.handle(msg("interactive", "Approve", sender=OWNER, button_id=f"approve:{job_id}", media_id="again"))
    priced = [s for s in b.wa.to(CUSTOMER) if "£" in s[2]]
    assert len(priced) == 1 and "£65–£110" in priced[0][2] and "subject to inspection" in priced[0][2]


def test_owner_edit_changes_range(tmp_path):
    b = bot(tmp_path, result=finding("quote"))
    b.handle(msg("video", media_id="m1"))
    (job_id,) = b.jobs
    b.handle(msg("interactive", "Edit", sender=OWNER, button_id=f"edit:{job_id}"))
    b.handle(msg("text", "90 to 130", sender=OWNER))
    assert any("£90–£130" in s[2] for s in b.wa.to(CUSTOMER))


def test_follow_up_question_and_history(tmp_path):
    calls = []
    b = bot(tmp_path, result=finding("more", next_question="Can you film the pressure gauge?"), calls=calls)
    b.handle(msg("video", "boiler pressure low", media_id="m1"))
    b.handle(msg("video", "here's the gauge", media_id="m2"))
    assert any("pressure gauge" in s[2] for s in b.wa.to(CUSTOMER))
    assert "Assistant asked: Can you film the pressure gauge?" in calls[1][2]


def test_talk_to_dave_hands_off(tmp_path):
    b = bot(tmp_path)
    b.handle(msg("text", "can I talk to Dave please"))
    assert any("get back to you" in s[2] for s in b.wa.to(CUSTOMER))
    assert any("wants to talk to you" in s[2] for s in b.wa.to(OWNER))


def test_model_slipping_a_price_is_blocked(tmp_path):
    b = bot(tmp_path, result=finding("more", next_question="That's usually about £80, can you film it?"))
    b.handle(msg("text", "tap drips"))
    assert not any("£" in s[2] for s in b.wa.to(CUSTOMER))


def test_out_of_scope_says_not_us(tmp_path):
    b = bot(tmp_path, result=finding("out_of_scope", fault_id=None, fault_name=None, problem_area="the patio door"))
    b.handle(msg("video", media_id="m1"))
    last = b.wa.to(CUSTOMER)[-1][2]
    assert "patio door" in last and "doesn't cover" in last and "water" in last


def test_same_question_twice_hands_off(tmp_path):
    b = bot(tmp_path, result=finding("more", next_question="Can you film the pressure gauge?"))
    b.handle(msg("video", media_id="m1"))
    b.result = None
    b.diagnose_fn = lambda *a, **k: finding("more", next_question="Could you film the pressure gauge please?")
    b.handle(msg("video", media_id="m2"))
    asked = [s for s in b.wa.to(CUSTOMER) if "pressure gauge" in s[2]]
    assert len(asked) == 1
    assert any("wants to talk to you" in s[2] for s in b.wa.to(OWNER))


def test_state_survives_restart(tmp_path):
    b = bot(tmp_path, result=finding("quote"))
    b.handle(msg("video", media_id="m1"))
    (job_id,) = b.jobs
    b2 = bot(tmp_path)
    assert job_id in b2.jobs and CUSTOMER in b2.threads
    b2.handle(msg("interactive", "Approve", sender=OWNER, button_id=f"approve:{job_id}"))
    assert any("£65–£110" in s[2] for s in b2.wa.to(CUSTOMER))


def test_owner_messages_are_marked(tmp_path):
    b = bot(tmp_path, result=finding("quote"))
    b.handle(msg("video", media_id="m1"))
    assert all(s[2].startswith("👷 For Dave:") for s in b.wa.to(OWNER) if s[1] in ("text", "buttons"))


def test_one_phone_plays_both_roles(tmp_path):
    b = Bot(FakeWA(), PACK, owner=CUSTOMER, work_dir=str(tmp_path), background=False, log=lambda s: None,
            diagnose_fn=lambda *a, **k: finding("quote"))
    b.handle(msg("video", media_id="m1"))
    (job_id,) = b.jobs
    b.handle(msg("interactive", "Approve", button_id=f"approve:{job_id}"))
    assert any("£65–£110" in s[2] and not s[2].startswith("👷") for s in b.wa.sent)


def test_gas_side_work_is_refused_without_triage(tmp_path):
    calls = []
    b = bot(tmp_path, calls=calls)
    b.handle(msg("text", "how do I relight the pilot light on my boiler myself?"))
    last = b.wa.to(CUSTOMER)[-1][2]
    assert "Gas Safe" in last and calls == []
