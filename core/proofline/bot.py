"""The WhatsApp front desk: inbound message → safety → triage → reply, with the owner approving prices.

A rules-based conversation loop for now. The Muse Wonder agent (tools + memory) replaces the
reply wording later; the safety, routing and approval rules here stay in code either way.

Sent automatically: greeting, follow-up questions, safety stops, "I've passed this to <owner>".
Needs the owner's approval: any price. Estimates go to the owner with Approve / Edit buttons, and only
an approved estimate can reach the customer (safety.check_outbound enforces it).
"""
from __future__ import annotations

import json
import re
import threading
from difflib import SequenceMatcher
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import media
from .channels.whatsapp import Inbound, Window
from .pack import Pack
from .safety import OutboundBlocked, check_outbound, check_text, stop_message
from .triage import Finding, diagnose

HANDOFF = re.compile(r"\b(talk|speak|chat) to (dave|a human|a person|someone|the owner)\b|\bhuman\b|\breal person\b", re.I)
RANGE = re.compile(r"£?\s*(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*£?\s*(\d+(?:\.\d+)?)")
MAX_VIDEO_BYTES = 16 * 1024 * 1024  # WhatsApp's limit for sending video
SAME_QUESTION = 0.75  # similarity above which a follow-up counts as asking the same thing again
OWNER_PREFIX = "👷 For {owner}: "  # marks owner messages, so one phone can play both roles in testing


@dataclass
class Thread:
    customer: str
    greeted: bool = False
    history: List[str] = field(default_factory=list)  # short lines, fed back to triage as context
    asked: List[str] = field(default_factory=list)  # follow-up questions already sent
    jobs: List[str] = field(default_factory=list)
    stopped: Optional[str] = None  # safety kind once a hard stop has fired


@dataclass
class Job:
    id: str
    customer: str
    finding: dict
    status: str = "pending"  # pending | approved | edited | handed_off
    estimate: Optional[dict] = None
    created: float = field(default_factory=time.time)


class Bot:
    def __init__(self, wa, pack: Pack, owner: str, work_dir: str, diagnose_fn: Callable = diagnose,
                 transcribe_fn: Optional[Callable] = None, background: bool = True, log=print):
        self.wa, self.pack, self.owner = wa, pack, owner
        self.work = Path(work_dir)
        self.work.mkdir(parents=True, exist_ok=True)
        self.diagnose_fn, self.transcribe_fn = diagnose_fn, transcribe_fn
        self.background, self.log = background, log
        self.threads: Dict[str, Thread] = {}
        self.jobs: Dict[str, Job] = {}
        self.window = Window()
        self.pending_edit: Optional[str] = None  # job id the owner is typing a new range for
        self._locks: Dict[str, threading.Lock] = {}
        self.owner_name = pack.trade.get("owner_name", "the owner")
        self.business = pack.trade.get("business_name", "")
        self._load()

    # ---- entry point -------------------------------------------------------------------------------
    def handle(self, m: Inbound) -> None:
        """Called once per inbound message. Returns quickly; slow work runs on a thread."""
        self.window.saw(m.sender, m.timestamp or None)
        if self.owner and m.sender == self.owner and (m.button_id or self.pending_edit):
            return self._run(m.sender, self._owner_message, m)
        self._run(m.sender, self._customer_message, m)

    def _run(self, key: str, fn, m: Inbound) -> None:
        lock = self._locks.setdefault(key, threading.Lock())

        def go():
            with lock:  # one message at a time per person, in order
                try:
                    fn(m)
                except Exception:  # noqa: BLE001
                    self.log(f"error handling {m.type} from ...{m.sender[-4:]}:\n{traceback.format_exc()}")
                finally:
                    self._save()

        if self.background:
            threading.Thread(target=go, daemon=True).start()
        else:
            go()

    # ---- customer side -----------------------------------------------------------------------------
    def _customer_message(self, m: Inbound) -> None:
        th = self.threads.setdefault(m.sender, Thread(customer=m.sender))
        try:
            self.wa.mark_read(m.message_id)
        except Exception:  # noqa: BLE001
            pass
        if not th.greeted:
            th.greeted = True
            self._say(m.sender, f"Hi, I'm {self.owner_name}'s assistant{' at ' + self.business if self.business else ''}. "
                                f"I'm an AI. I'll take a look at the problem and get {self.owner_name} what they need. "
                                f"You can type \"talk to {self.owner_name}\" at any time to reach a person.")

        text = m.text or ""
        if m.type == "audio":
            text = self._voice_to_text(m)
            th.history.append(f"Customer voice note: {text}")
        elif text:
            th.history.append(f"Customer: {text}")

        stop = check_text(text, self.pack)
        if stop:
            return self._stop(th, stop.kind, source="rules")
        if HANDOFF.search(text):
            return self._handoff(th, "customer asked for a person")
        excluded = self.pack.excluded_match(text) if text else None
        if excluded:  # e.g. gas-side boiler work: never advised on or quoted by message
            th.history.append(f"Assistant: excluded work ({excluded['id']}).")
            self._say(m.sender, f"{excluded['reason']} I can't advise on that by message, and please don't attempt it "
                                f"yourself. I've let {self.owner_name} know you got in touch.")
            return self._send_owner(f"Customer ...{m.sender[-4:]} asked about excluded work ({excluded['id']}): {text[:200]}")

        if m.type == "video":
            self._say(m.sender, "Thanks, I'm taking a look at the video now. This takes about 30 seconds.")
            path = self.wa.download_media(m.media_id, str(self.work / "media"))
            return self._triage(th, str(path), text)
        if m.type == "image":
            return self._say(m.sender, "Thanks. Could you send a short video instead (10 to 30 seconds)? "
                                       "It helps me see what's happening.")
        if m.type in ("text", "audio") and text:
            return self._triage(th, None, text)
        if m.type in ("interactive", "button"):
            return  # customer tapped an old button; nothing to do
        self._say(m.sender, "Sorry, I can only read text, voice notes and videos for now.")

    def _voice_to_text(self, m: Inbound) -> str:
        if not self.transcribe_fn:
            return ""
        src = self.wa.download_media(m.media_id, str(self.work / "media"))
        wav = media.to_wav_16k(str(src), str(Path(src).with_suffix(".wav")))
        turns = self.transcribe_fn(wav, keywords=self.pack.keywords()).get("turns", [])
        return " ".join(t.get("transcript", "") for t in turns).strip()

    def _triage(self, th: Thread, video: Optional[str], text: str) -> None:
        job_dir = self.work / "jobs" / f"{th.customer[-4:]}-{int(time.time())}"
        f: Finding = self.diagnose_fn(video, self.pack, message=text, history="\n".join(th.history[-12:]),
                                      work_dir=str(job_dir) if video else None)
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "finding.json").write_text(json.dumps(f.to_dict(), indent=2, default=str))
        self.log(f"   triage ...{th.customer[-4:]}: route={f.route} fault={f.fault_id} conf={f.confidence:.2f} "
                 f"injection={f.injection!r} timings={f.timings}")
        if f.description:
            th.history.append(f"Assistant saw: {f.description}")

        if f.route == "stop":
            return self._stop(th, f.safety["kind"], source=f.safety.get("source", "model"))
        if f.route == "out_of_scope":
            area = f.problem_area or "that"
            th.history.append(f"Assistant: out of scope ({area}).")
            return self._say(th.customer, f"Thanks for sending that. It looks like a problem with {area}, which "
                                          f"{self.owner_name} doesn't cover as a {self.pack.trade.get('label', 'tradesperson')}. "
                                          f"If there's water, a leak or damp involved, tell me and I'll pass it on.")
        if f.route == "more":
            if any(SequenceMatcher(None, f.next_question.lower(), q.lower()).ratio() >= SAME_QUESTION for q in th.asked):
                # Asked already and still stuck: a person takes over rather than going round in circles.
                return self._handoff(th, "the assistant couldn't get what it needed")
            th.asked.append(f.next_question)
            th.history.append(f"Assistant asked: {f.next_question}")
            return self._say(th.customer, f.next_question)
        if f.route == "visit":
            self._say(th.customer, f"Thanks. This one needs {self.owner_name} to see it in person. I've passed it on "
                                   f"and {self.owner_name} will be in touch to arrange a visit.")
            return self._notify_owner(th, f, "Needs a visit: " + (f.visit_reason or ""), video=job_dir / "clip.mp4")
        # quote: the estimate goes to the owner, never straight to the customer.
        job = Job(id=uuid.uuid4().hex[:8], customer=th.customer, finding=f.to_dict(), estimate=f.estimate)
        self.jobs[job.id] = job
        th.jobs.append(job.id)
        self._say(th.customer, f"Thanks, that's really helpful. It looks like {f.fault_name.lower()}: {f.description} "
                               f"I've sent this to {self.owner_name} with a suggested estimate. "
                               f"{self.owner_name} will check it and confirm with you shortly.")
        th.history.append("Assistant: sent to the owner for an estimate.")
        self._ask_owner_to_approve(th, job, job_dir / "clip.mp4")

    def _stop(self, th: Thread, kind: str, source: str) -> None:
        th.stopped = kind
        self._say(th.customer, stop_message(kind, self.pack))
        self._send_owner(f"⚠️ SAFETY STOP ({kind.replace('_', ' ')}, caught by {source}) for customer "
                         f"...{th.customer[-4:]}. They were sent the emergency advice. Last messages:\n"
                         + "\n".join(th.history[-4:]))

    def _handoff(self, th: Thread, reason: str) -> None:
        self._say(th.customer, f"No problem. I've asked {self.owner_name} to get back to you directly.")
        self._send_owner(f"Customer ...{th.customer[-4:]} wants to talk to you ({reason}). Their number: "
                         f"+{th.customer}\nConversation so far:\n" + "\n".join(th.history[-8:]))

    # ---- owner side --------------------------------------------------------------------------------
    def _ask_owner_to_approve(self, th: Thread, job: Job, clip: Path) -> None:
        f, est = job.finding, job.estimate
        self._send_owner_video(clip, f"Customer ...{th.customer[-4:]}: {f['fault_name']}")
        body = (f"New job from ...{th.customer[-4:]}\n"
                f"Fault: {f['fault_name']} (confidence {f['confidence']:.0%})\n"
                f"Seen: {f['description']}\n"
                + (f"Reading: {f['reading']}\n" if f.get("reading") else "")
                + (f"Likely parts: {', '.join(self.pack.parts[p]['name'] for p in f['likely_parts'])}\n"
                   if f.get("likely_parts") else "")
                + f"Suggested estimate: £{est['low']:.0f}–£{est['high']:.0f}\n"
                f"Nothing has been sent to the customer about price.")
        if not self.owner:
            return self.log(f"-> owner approval (not set, not sent): {body}")
        try:
            self.wa.send_buttons(self.owner, OWNER_PREFIX.format(owner=self.owner_name) + body, [(f"approve:{job.id}", "Approve"), (f"edit:{job.id}", "Edit")])
        except Exception as exc:  # noqa: BLE001
            self.log(f"   couldn't reach the owner (has their phone messaged the number in the last 24h?): {exc}")

    def _owner_message(self, m: Inbound) -> None:
        if m.button_id and ":" in m.button_id:
            action, job_id = m.button_id.split(":", 1)
            job = self.jobs.get(job_id)
            if not job:
                return self._send_owner("I can't find that job any more.")
            if action == "approve":
                return self._send_estimate(job, "approved")
            if action == "edit":
                self.pending_edit = job_id
                return self._send_owner("Reply with the range you want to quote, e.g. 80-120.")
        if self.pending_edit and m.text:
            match = RANGE.search(m.text)
            if not match:
                return self._send_owner("Sorry, I need a range like 80-120.")
            job = self.jobs[self.pending_edit]
            self.pending_edit = None
            low, high = sorted(float(x) for x in match.groups())
            job.estimate = {**job.estimate, "low": low, "high": high}
            return self._send_estimate(job, "edited")

    def _send_estimate(self, job: Job, status: str) -> None:
        if job.status in ("approved", "edited"):
            return self._send_owner("That estimate has already been sent.")
        est = job.estimate
        text = (f"{self.owner_name} has looked at your video. Estimate for {job.finding['fault_name'].lower()}: "
                f"£{est['low']:.0f}–£{est['high']:.0f}. {est['wording']} "
                f"Reply here and {self.owner_name} will get back to you to book it in.")
        self._say(job.customer, text, approved=True)
        job.status = status
        self._send_owner(f"Sent to ...{job.customer[-4:]}: £{est['low']:.0f}–£{est['high']:.0f}.")

    def _notify_owner(self, th: Thread, f: Finding, headline: str, video: Path) -> None:
        self._send_owner_video(video, f"Customer ...{th.customer[-4:]}")
        self._send_owner(f"{headline}\nCustomer ...{th.customer[-4:]}: {f.description}")

    # ---- sending -----------------------------------------------------------------------------------
    def _say(self, to: str, text: str, approved: bool = False) -> None:
        """Every message to a customer goes through here, and through the outbound price check."""
        try:
            check_outbound(text, approved=approved)
        except OutboundBlocked as exc:  # model wording slipped a price in: send a safe fallback instead
            self.log(f"   blocked: {exc}")
            text = f"Thanks. I've passed this to {self.owner_name}, who will get back to you."
        self.wa.send_text(to, text)
        self.log(f"-> ...{to[-4:]}: {text[:120]}")

    def _send_owner(self, text: str) -> None:
        if not self.owner:
            return self.log(f"-> owner (not set, not sent): {text[:200]}")
        try:
            self.wa.send_text(self.owner, OWNER_PREFIX.format(owner=self.owner_name) + text)
            self.log(f"-> owner: {text[:120]}")
        except Exception as exc:  # noqa: BLE001
            self.log(f"   couldn't reach the owner (has their phone messaged the number in the last 24h?): {exc}")

    def _send_owner_video(self, clip: Path, caption: str) -> None:
        if self.owner and clip.exists() and clip.stat().st_size < MAX_VIDEO_BYTES:
            try:
                self.wa.send_video(self.owner, str(clip), caption=OWNER_PREFIX.format(owner=self.owner_name) + caption)
            except Exception as exc:  # noqa: BLE001
                self.log(f"   couldn't send the clip to the owner: {exc}")

    def _load(self) -> None:
        """Pick up conversations and pending quotes from the last run."""
        path = self.work / "state.json"
        if not path.exists():
            return
        state = json.loads(path.read_text())
        self.threads = {k: Thread(**v) for k, v in state.get("threads", {}).items()}
        self.jobs = {k: Job(**v) for k, v in state.get("jobs", {}).items()}
        self.pending_edit = state.get("pending_edit")
        self.log(f"loaded {len(self.threads)} conversation(s), {len(self.jobs)} job(s) from the last run")

    def _save(self) -> None:
        state = {"threads": {k: asdict(v) for k, v in self.threads.items()},
                 "jobs": {k: asdict(v) for k, v in self.jobs.items()}, "pending_edit": self.pending_edit}
        (self.work / "state.json").write_text(json.dumps(state, indent=2, default=str))
