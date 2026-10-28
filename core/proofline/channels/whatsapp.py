"""WhatsApp Cloud API adapter: webhook parsing and signature check, media download, sending.

Docs: developers.facebook.com/documentation/business-messaging/whatsapp. Shapes checked on 28 Oct 2026.
Graph version is configurable (WHATSAPP_GRAPH_VERSION); Meta's pages showed both v25.0 and v26.0.

Free-form messages (text, media, buttons) can only be sent within 24 hours of the customer's last
message. Outside that window only approved templates are allowed; Window tracks it.
"""
from __future__ import annotations

import hashlib
import hmac
import mimetypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests

from ..backends.base import check, require_env

GRAPH = "https://graph.facebook.com"
WINDOW_S = 24 * 3600
MAX_BUTTONS = 3
MAX_BUTTON_TITLE = 20


def verify_signature(app_secret: str, raw_body: bytes, header: Optional[str]) -> bool:
    """Check X-Hub-Signature-256 ("sha256=<hex HMAC of the raw body>") in constant time."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):])


@dataclass
class Inbound:
    sender: str  # wa_id, E.164 without "+"
    message_id: str
    type: str  # text | image | video | audio | document | interactive | button | other
    timestamp: int
    text: str = ""
    media_id: Optional[str] = None
    mime_type: Optional[str] = None
    button_id: Optional[str] = None
    is_voice: bool = False


def parse_webhook(payload: dict) -> List[Inbound]:
    """Pull customer messages out of a webhook payload. Status updates (sent/delivered/read) are skipped."""
    out: List[Inbound] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for m in change.get("value", {}).get("messages", []) or []:
                kind = m.get("type", "other")
                msg = Inbound(sender=m.get("from", ""), message_id=m.get("id", ""), type=kind,
                              timestamp=int(m.get("timestamp", 0) or 0))
                if kind == "text":
                    msg.text = m.get("text", {}).get("body", "")
                elif kind in ("image", "video", "audio", "document", "sticker"):
                    media = m.get(kind, {})
                    msg.media_id, msg.mime_type = media.get("id"), media.get("mime_type")
                    msg.text = media.get("caption", "")
                    msg.is_voice = bool(media.get("voice"))
                elif kind == "interactive":
                    reply = m.get("interactive", {})
                    reply = reply.get("button_reply") or reply.get("list_reply") or {}
                    msg.button_id, msg.text = reply.get("id"), reply.get("title", "")
                elif kind == "button":  # quick-reply button on a template
                    msg.button_id, msg.text = m.get("button", {}).get("payload"), m.get("button", {}).get("text", "")
                out.append(msg)
    return out


class Window:
    """Tracks the 24-hour customer service window per number (in memory; fine for the demo)."""

    def __init__(self):
        self.last_inbound: Dict[str, float] = {}

    def saw(self, sender: str, ts: Optional[float] = None) -> None:
        self.last_inbound[sender] = ts or time.time()

    def open(self, sender: str, now: Optional[float] = None) -> bool:
        last = self.last_inbound.get(sender)
        return last is not None and (now or time.time()) - last < WINDOW_S


class WhatsAppClient:
    def __init__(self, token: Optional[str] = None, phone_number_id: Optional[str] = None,
                 version: Optional[str] = None, timeout: float = 120):
        self.token = token or require_env("WHATSAPP_TOKEN")
        self.phone_number_id = phone_number_id or require_env("WHATSAPP_PHONE_NUMBER_ID")
        self.version = version or os.environ.get("WHATSAPP_GRAPH_VERSION") or "v25.0"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {self.token}"

    def _url(self, path: str) -> str:
        return f"{GRAPH}/{self.version}/{path.lstrip('/')}"

    def _send(self, to: str, body: dict, reply_to: Optional[str] = None) -> dict:
        msg = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, **body}
        if reply_to:
            msg["context"] = {"message_id": reply_to}
        resp = self.session.post(self._url(f"{self.phone_number_id}/messages"), json=msg, timeout=self.timeout)
        return check(resp).json()

    def send_text(self, to: str, text: str, reply_to: Optional[str] = None) -> dict:
        return self._send(to, {"type": "text", "text": {"body": text[:4096], "preview_url": False}}, reply_to)

    def send_buttons(self, to: str, text: str, buttons: List[tuple], reply_to: Optional[str] = None) -> dict:
        """buttons: up to 3 (id, title) pairs. Titles are cut to 20 characters (the API limit)."""
        if not 1 <= len(buttons) <= MAX_BUTTONS:
            raise ValueError("WhatsApp reply buttons take 1 to 3 buttons")
        return self._send(to, {"type": "interactive", "interactive": {
            "type": "button", "body": {"text": text[:1024]},
            "action": {"buttons": [{"type": "reply", "reply": {"id": bid, "title": title[:MAX_BUTTON_TITLE]}}
                                   for bid, title in buttons]}}}, reply_to)

    def upload_media(self, path: str, mime: Optional[str] = None) -> str:
        p = Path(path)
        mime = mime or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        with p.open("rb") as f:
            resp = self.session.post(self._url(f"{self.phone_number_id}/media"),
                                     data={"messaging_product": "whatsapp", "type": mime},
                                     files={"file": (p.name, f, mime)}, timeout=self.timeout)
        return check(resp).json()["id"]

    def send_video(self, to: str, path: str, caption: str = "", reply_to: Optional[str] = None) -> dict:
        """MP4 (H.264 + AAC), 16 MB max."""
        mid = self.upload_media(path, "video/mp4")
        return self._send(to, {"type": "video", "video": {"id": mid, "caption": caption[:1024]}}, reply_to)

    def send_document(self, to: str, path: str, caption: str = "") -> dict:
        mid = self.upload_media(path)
        return self._send(to, {"type": "document", "document": {
            "id": mid, "filename": Path(path).name, "caption": caption[:1024]}})

    def download_media(self, media_id: str, dest_dir: str) -> Path:
        """Two steps: look up the short-lived media URL, then fetch it with the same token."""
        meta = check(self.session.get(self._url(media_id), timeout=30)).json()
        resp = check(self.session.get(meta["url"], timeout=self.timeout))
        ext = mimetypes.guess_extension((meta.get("mime_type") or "").split(";")[0]) or ".bin"
        out = Path(dest_dir) / f"{media_id}{ext}"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(resp.content)
        return out

    def mark_read(self, message_id: str) -> dict:
        resp = self.session.post(self._url(f"{self.phone_number_id}/messages"), json={
            "messaging_product": "whatsapp", "status": "read", "message_id": message_id}, timeout=30)
        return check(resp).json()
