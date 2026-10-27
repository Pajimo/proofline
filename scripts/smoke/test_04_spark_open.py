"""Muse Spark Open on Baseten: one text call, then one video call (inline base64 data URL).

Usage: python scripts/smoke/test_04_spark_open.py [--video clip.mp4]
"""
import base64
import sys

from _common import run, video_arg

from proofline.backends import BasetenClient
from proofline.backends.baseten import message_text


def text():
    client = BasetenClient()
    resp = client.chat([{"role": "user", "content": "Reply with exactly: proofline ok"}], max_tokens=200)
    return f"model={client.model}  reply={message_text(resp)!r}  usage={resp.get('usage')}"


def video():
    client = BasetenClient()
    data_url = "data:video/mp4;base64," + base64.b64encode(video_arg().read_bytes()).decode()
    resp = client.chat([{"role": "user", "content": [
        {"type": "text", "text": "Describe what is on screen in one sentence and quote any spoken words."},
        {"type": "video_url", "video_url": {"url": data_url}},
    ]}], max_tokens=4000)
    return f"reply={message_text(resp)!r}  usage={resp.get('usage')}"


if __name__ == "__main__":
    codes = [run("Spark Open (Baseten): text", text), run("Spark Open (Baseten): video", video)]
    sys.exit(max(codes))
