"""Muse Spark 1.3 reads a video (Files API upload → input_file) and returns structured JSON.

Usage: python scripts/smoke/test_01_spark_video.py [--video clip.mp4] [--inline]
"""
import base64
import json
import sys

from _common import run, video_arg

from proofline.backends import APIError, MetaClient
from proofline.backends.meta import SPARK, output_text

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["what_is_on_screen", "spoken_words", "duration_estimate_s"],
    "properties": {
        "what_is_on_screen": {"type": "string"},
        "spoken_words": {"type": "string"},
        "duration_estimate_s": {"type": "number"},
    },
}
PROMPT = ("Describe what is on screen in one sentence, quote any words spoken in the audio "
          "(empty string if none), and estimate the clip length in seconds.")


def body(video_part, structured=True):
    b = {
        "model": SPARK,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 4000,
        "input": [{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": PROMPT}, video_part,
        ]}],
    }
    if structured:
        b["text"] = {"format": {"type": "json_schema", "name": "smoke", "schema": SCHEMA, "strict": False}}
    return b


def call(client, video_part):
    try:
        resp = client.responses(body(video_part))
        mode = "structured (text.format json_schema)"
    except APIError as exc:
        if exc.status != 400 or "format" not in exc.body:
            raise
        print(f"  note: structured output rejected ({exc.body[:300]}); retrying as plain text")
        resp = client.responses(body(video_part, structured=False))
        mode = "plain text"
    text = output_text(resp)
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = text
    return {"mode": mode, "output": parsed, "usage": resp.get("usage")}


def via_files_api():
    client = MetaClient()
    path = video_arg()
    uploaded = client.upload_file(str(path))
    print(f"  uploaded {path.name}: {json.dumps(uploaded)[:400]}")
    try:
        return call(client, {"type": "input_file", "file_id": uploaded["id"]})
    finally:
        try:
            client.delete_file(uploaded["id"])
        except Exception as exc:  # noqa: BLE001
            print(f"  note: could not delete uploaded file: {exc}")


def via_inline():
    path = video_arg()
    data_url = "data:video/mp4;base64," + base64.b64encode(path.read_bytes()).decode()
    return call(MetaClient(), {"type": "input_video", "video_url": data_url})


if __name__ == "__main__":
    if "--inline" in sys.argv:
        sys.exit(run("Spark 1.3 video (inline data URL)", via_inline))
    sys.exit(run("Spark 1.3 video (Files API)", via_files_api))
