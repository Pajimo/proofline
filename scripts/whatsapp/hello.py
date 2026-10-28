"""Day-2 WhatsApp check on the free test number.

  python scripts/whatsapp/hello.py send [--video clip.mp4]   text + reply buttons (+ a video) to WHATSAPP_TEST_RECIPIENT
  python scripts/whatsapp/hello.py serve [--port 8080]       webhook: verify, print inbound messages, download media

Media lands in evals/raw/inbound/ (git-ignored). The webhook needs a public HTTPS URL pointing at the port,
for example from a tunnel; set that URL and WHATSAPP_VERIFY_TOKEN in the app's WhatsApp > Configuration page.
"""
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))

from proofline.backends import load_env  # noqa: E402
from proofline.backends.base import require_env  # noqa: E402
from proofline.channels.whatsapp import WhatsAppClient, parse_webhook, verify_signature  # noqa: E402

INBOUND = ROOT / "evals" / "raw" / "inbound"


def send(video=None):
    wa, to = WhatsAppClient(), require_env("WHATSAPP_TEST_RECIPIENT")
    print(wa.send_text(to, "Hi, I'm Dave's assistant (an AI). Send me a short video of the problem and I'll take a look."))
    print(wa.send_buttons(to, "Test: does this look right?", [("ok", "Looks right"), ("talk", "Talk to Dave")]))
    if video:
        print(wa.send_video(to, video, caption="Test clip"))


class Hook(BaseHTTPRequestHandler):
    def do_GET(self):  # subscription handshake
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == os.environ.get("WHATSAPP_VERIFY_TOKEN"):
            self._reply(200, q.get("hub.challenge", ""))
        else:
            self._reply(403, "forbidden")

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if not verify_signature(require_env("WHATSAPP_APP_SECRET"), raw, self.headers.get("X-Hub-Signature-256")):
            print("rejected: bad signature")
            return self._reply(401, "bad signature")
        self._reply(200, "ok")  # ack fast; Meta retries slow webhooks
        wa = WhatsAppClient()
        for m in parse_webhook(json.loads(raw)):
            print(f"<- {m.type} from ...{m.sender[-4:]}: {m.text!r} media={m.media_id} button={m.button_id}")
            if m.media_id:
                path = wa.download_media(m.media_id, str(INBOUND))
                print(f"   saved {path} ({path.stat().st_size} bytes)")
                wa.send_text(m.sender, f"Got your {m.type}, thanks. Taking a look.", reply_to=m.message_id)

    def _reply(self, code, text):
        self.send_response(code)
        self.end_headers()
        self.wfile.write(text.encode())

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["send", "serve"])
    ap.add_argument("--video")
    ap.add_argument("--port", type=int, default=8080)
    a = ap.parse_args()
    load_env()
    if a.mode == "send":
        send(a.video)
    else:
        print(f"webhook on http://localhost:{a.port}  (needs a public HTTPS tunnel)")
        HTTPServer(("", a.port), Hook).serve_forever()
