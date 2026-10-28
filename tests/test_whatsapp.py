import hashlib
import hmac
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from proofline.channels.whatsapp import Window, parse_webhook, verify_signature  # noqa: E402


def payload(*messages):
    return {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"phone_number_id": "123"}, "messages": list(messages)}}]}]}


def test_signature():
    body = b'{"a":1}'
    sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_signature("secret", body, sig)
    assert not verify_signature("secret", body + b" ", sig)
    assert not verify_signature("secret", body, None)
    assert not verify_signature("other", body, sig)


def test_parse_text_video_voice_and_button():
    msgs = parse_webhook(payload(
        {"from": "447700900123", "id": "wamid.1", "timestamp": "1761650000", "type": "text", "text": {"body": "hi"}},
        {"from": "447700900123", "id": "wamid.2", "timestamp": "1761650001", "type": "video",
         "video": {"id": "m1", "mime_type": "video/mp4", "caption": "the leak"}},
        {"from": "447700900123", "id": "wamid.3", "timestamp": "1761650002", "type": "audio",
         "audio": {"id": "m2", "mime_type": "audio/ogg; codecs=opus", "voice": True}},
        {"from": "447700900999", "id": "wamid.4", "timestamp": "1761650003", "type": "interactive",
         "interactive": {"type": "button_reply", "button_reply": {"id": "approve:job1", "title": "Approve"}}},
    ))
    assert [m.type for m in msgs] == ["text", "video", "audio", "interactive"]
    assert msgs[0].text == "hi"
    assert msgs[1].media_id == "m1" and msgs[1].text == "the leak"
    assert msgs[2].is_voice
    assert msgs[3].button_id == "approve:job1"


def test_status_updates_are_ignored():
    p = {"entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.1", "status": "read"}]}}]}]}
    assert parse_webhook(p) == []


def test_24h_window():
    w = Window()
    assert not w.open("44")
    w.saw("44", ts=1000)
    assert w.open("44", now=1000 + 23 * 3600)
    assert not w.open("44", now=1000 + 25 * 3600)
