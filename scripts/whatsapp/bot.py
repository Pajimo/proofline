"""Run the WhatsApp front desk: webhook → safety → triage → reply, owner approves prices.

  python scripts/whatsapp/bot.py [--pack packs/plumbing.yaml] [--port 8080]

Needs WHATSAPP_* and META_API_KEY in .env, and a public HTTPS tunnel to the port set as the app's webhook.
The owner's phone (WHATSAPP_OWNER_NUMBER) must have messaged the number in the last 24 hours to get
approval requests. State and media go to evals/raw/bot/ (git-ignored).
"""
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))

from proofline.backends import MetaClient, load_env  # noqa: E402
from proofline.backends.base import require_env  # noqa: E402
from proofline.bot import Bot  # noqa: E402
from proofline.channels.whatsapp import WhatsAppClient, parse_webhook, verify_signature  # noqa: E402
from proofline.pack import Pack  # noqa: E402
from proofline.triage import diagnose  # noqa: E402

BOT = None
SEEN = set()  # Meta retries webhooks; handle each message id once


def make_handler(app_secret, verify_token):
    class Hook(BaseHTTPRequestHandler):
        def do_GET(self):
            q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
            ok = q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == verify_token
            self._reply(200 if ok else 403, q.get("hub.challenge", "") if ok else "forbidden")

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if not verify_signature(app_secret, raw, self.headers.get("X-Hub-Signature-256")):
                print("rejected: bad signature", flush=True)
                return self._reply(401, "bad signature")
            self._reply(200, "ok")  # ack first; the bot works on its own threads
            for m in parse_webhook(json.loads(raw)):
                if m.message_id in SEEN:
                    continue
                SEEN.add(m.message_id)
                who = "owner" if m.sender == BOT.owner else f"...{m.sender[-4:]}"
                print(f"<- {m.type} from {who}: {m.text[:80]!r} button={m.button_id}", flush=True)
                BOT.handle(m)

        def _reply(self, code, text):
            self.send_response(code)
            self.end_headers()
            self.wfile.write(text.encode())

        def log_message(self, *args):
            pass

    return Hook


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default=str(ROOT / "packs" / "plumbing.yaml"))
    ap.add_argument("--port", type=int, default=8080)
    a = ap.parse_args()
    load_env()
    meta = MetaClient()
    BOT = Bot(WhatsAppClient(), Pack.load(a.pack), owner=os.environ.get("WHATSAPP_OWNER_NUMBER", "").strip(),
              work_dir=str(ROOT / "evals" / "raw" / "bot"),
              diagnose_fn=lambda *args, **kw: diagnose(*args, client=meta, **kw),
              transcribe_fn=lambda wav, keywords: meta.transcribe(wav, mode="ENDPOINTING", keywords=keywords),
              log=lambda s: print(s, flush=True))
    if not BOT.owner:
        print("WHATSAPP_OWNER_NUMBER not set: owner messages are only logged here", flush=True)
    print(f"FirstLook bot on http://localhost:{a.port} for {BOT.business or BOT.pack.name}", flush=True)
    ThreadingHTTPServer(("", a.port), make_handler(require_env("WHATSAPP_APP_SECRET"),
                                                   require_env("WHATSAPP_VERIFY_TOKEN"))).serve_forever()
