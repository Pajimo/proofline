"""Replay whole conversations through the real bot and real Meta models, with WhatsApp faked.

  python evals/replay.py [--runs 3] [--only gas_text,dripping_tap] [--suite evals/conversations/suite.yaml]

Writes evals/runs/replay/<time>.json (git-ignored) and prints pass rates per conversation and group.
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from proofline.backends import MetaClient, load_env  # noqa: E402
from proofline.bot import Bot  # noqa: E402
from proofline.channels.whatsapp import Inbound  # noqa: E402
from proofline.pack import Pack  # noqa: E402
from proofline.triage import diagnose  # noqa: E402

CUSTOMER, OWNER = "440000000001", "440000000002"


class RecordingWA:
    """Stands in for WhatsAppClient. Nothing leaves the machine."""

    def __init__(self, clips_dir: Path):
        self.sent, self.clips_dir = [], clips_dir

    def send_text(self, to, text, reply_to=None):
        self.sent.append({"to": to, "text": text})

    def send_buttons(self, to, text, buttons, reply_to=None):
        self.sent.append({"to": to, "text": text, "buttons": [b[1] for b in buttons]})

    def send_video(self, to, path, caption=""):
        self.sent.append({"to": to, "text": caption, "video": Path(path).name})

    def download_media(self, media_id, dest):
        return self.clips_dir / f"{media_id}.mp4"

    def mark_read(self, message_id):
        pass


def as_list(v):
    return v if isinstance(v, list) else [v]


def run_conversation(conv, pack, meta, clips_dir, work):
    wa = RecordingWA(clips_dir)
    findings = []

    def diag(*a, **kw):
        f = diagnose(*a, client=meta, **kw)
        findings.append(f)
        return f

    bot = Bot(wa, pack, owner=OWNER, work_dir=str(work), diagnose_fn=diag, background=False, log=lambda s: None,
              transcribe_fn=lambda wav, keywords: meta.transcribe(wav, mode="ENDPOINTING", keywords=keywords))
    results = []
    for i, step in enumerate(conv["steps"]):
        before_sent, before_f = len(wa.sent), len(findings)
        clip = step.get("clip")
        m = Inbound(sender=CUSTOMER, message_id=f"{conv['id']}-{i}", type="video" if clip else "text",
                    timestamp=int(time.time()), text=step.get("text", ""), media_id=clip)
        t = time.time()
        bot.handle(m)
        took = round(time.time() - t, 1)
        out = wa.sent[before_sent:]
        to_customer = " \n".join(x["text"] for x in out if x["to"] == CUSTOMER)
        to_owner = " \n".join(x["text"] for x in out if x["to"] == OWNER)
        f = findings[before_f] if len(findings) > before_f else None
        route = f.route if f else "none"
        exp = step.get("expect", {})
        fails = []
        if "route" in exp and route not in as_list(exp["route"]):
            fails.append(f"route {route}, wanted {exp['route']}")
        if "kind" in exp:
            stopped = bot.threads[CUSTOMER].stopped
            if stopped != exp["kind"]:
                fails.append(f"safety kind {stopped}, wanted {exp['kind']}")
        for s in as_list(exp.get("customer_has", [])):
            if s.lower() not in to_customer.lower():
                fails.append(f"customer reply lacks {s!r}")
        for s in as_list(exp.get("customer_lacks", [])) + ["£"]:
            if s.lower() in to_customer.lower():
                fails.append(f"customer reply contains {s!r}")
        for s in as_list(exp.get("owner_has", [])):
            if s.lower() not in to_owner.lower():
                fails.append(f"owner message lacks {s!r}")
        results.append({"step": i, "route": route, "fault": f.fault_id if f else None,
                        "confidence": f.confidence if f else None, "injection_flag": f.injection if f else None,
                        "seconds": took, "customer": to_customer, "owner": to_owner, "fails": fails})
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default=str(ROOT / "evals" / "conversations" / "suite.yaml"))
    ap.add_argument("--pack", default=str(ROOT / "packs" / "plumbing.yaml"))
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--only")
    a = ap.parse_args()
    load_env()
    suite = yaml.safe_load(Path(a.suite).read_text())
    pack, meta = Pack.load(a.pack), MetaClient()
    clips_dir = ROOT / "evals" / "raw" / suite.get("set", "customer")
    convs = [c for c in suite["conversations"] if not a.only or c["id"] in a.only.split(",")]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = ROOT / "evals" / "runs" / "replay" / stamp
    record = []
    for run in range(a.runs):
        for conv in convs:
            if any(s.get("clip") and not (clips_dir / f"{s['clip']}.mp4").exists() for s in conv["steps"]):
                print(f"skip {conv['id']}: clip missing in {clips_dir}")
                continue
            try:
                steps = run_conversation(conv, pack, meta, clips_dir, out_dir / f"run{run}" / conv["id"])
                ok = not any(s["fails"] for s in steps)
            except Exception as exc:  # noqa: BLE001
                steps, ok = [{"fails": [f"error: {exc}"]}], False
            record.append({"run": run, "id": conv["id"], "group": conv.get("group", ""), "pass": ok, "steps": steps})
            routes = ",".join(str(s.get("route")) for s in steps)
            secs = sum(s.get("seconds") or 0 for s in steps)
            print(f"run {run}  {'PASS' if ok else 'FAIL'}  {conv['id']:<22} route={routes:<14} {secs:5.1f}s  "
                  + "; ".join(f for s in steps for f in s["fails"]), flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(record, indent=2, default=str))
    by_conv, by_group = defaultdict(list), defaultdict(list)
    for r in record:
        by_conv[r["id"]].append(r["pass"])
        by_group[r["group"]].append(r["pass"])
    print("\n=== summary ===")
    for g, v in by_group.items():
        print(f"{g:<10} {sum(v)}/{len(v)} passed")
    flaky = [c for c, v in by_conv.items() if 0 < sum(v) < len(v)]
    if flaky:
        print("flaky (passed some runs, failed others):", ", ".join(flaky))
    print(f"\nFull results: {out_dir / 'results.json'}")
    sys.exit(0 if all(r["pass"] for r in record) else 1)


if __name__ == "__main__":
    main()
