"""Meta Developer API client (https://dev.meta.ai/docs). Request shapes checked on 27 Oct 2026."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator, List, Optional

import requests

from .base import check, iter_sse, require_env

SPARK = "muse-spark-1.3"
WONDER = "muse-wonder-1.0"
SAM = "sam-3.1"
TRANSCRIBE = "muse-voice-transcribe-1.0"


class MetaClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: float = 600):
        self.api_key = api_key or require_env("META_API_KEY")
        self.base_url = (base_url or os.environ.get("META_BASE_URL") or "https://api.meta.ai/v1").rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {self.api_key}"

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def list_models(self) -> dict:
        return check(self.session.get(self._url("models"), timeout=30)).json()

    # Files API: recommended for video (up to 1 GiB; inline is capped at 50 MB).
    def upload_file(self, path: str, purpose: str = "user_data") -> dict:
        p = Path(path)
        with p.open("rb") as f:
            resp = self.session.post(
                self._url("files"),
                data={"purpose": purpose},
                files={"file": (p.name, f, _mime(p))},
                timeout=self.timeout,
            )
        return check(resp).json()

    def delete_file(self, file_id: str) -> dict:
        return check(self.session.delete(self._url(f"files/{file_id}"), timeout=30)).json()

    # Responses API.
    def responses(self, body: dict) -> dict:
        resp = self.session.post(self._url("responses"), json=body, timeout=self.timeout)
        return check(resp).json()

    def responses_stream(self, body: dict) -> Iterator[dict]:
        body = {**body, "stream": True}
        resp = self.session.post(
            self._url("responses"),
            json=body,
            headers={"Accept": "text/event-stream"},
            stream=True,
            timeout=self.timeout,
        )
        check(resp)
        yield from iter_sse(resp)

    def sam_video(self, concept: str, file_id: Optional[str] = None, video_url: Optional[str] = None) -> List[str]:
        """Run SAM 3.1 on a video for one noun phrase. Returns one raw line per frame.

        An empty list means zero matches, not an error.
        """
        video = {"type": "input_video"}
        if file_id:
            video["file_id"] = file_id
        else:
            video["video_url"] = video_url
        body = {
            "model": SAM,
            "input": [{"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": concept},
                video,
            ]}],
        }
        lines: List[str] = []
        for event in self.responses_stream(body):
            if event.get("type") == "response.output_text.delta":
                lines.append(event.get("delta", ""))
            elif event.get("type") in ("response.failed", "error"):
                raise RuntimeError(f"SAM stream failed: {json.dumps(event)[:2000]}")
        return [line for line in lines if line.strip()]

    # Voice Transcribe: WAV only (mono 16-bit PCM, 16/24 kHz), ≤10 min, ≤32 MB.
    def transcribe(self, wav_path: str, mode: str = "DIARIZATION", keywords: Optional[List[str]] = None) -> dict:
        settings = {
            "model": TRANSCRIBE,
            "mode": mode,
            "audioEncoding": "WAV",
            "languageBias": ["English"],
        }
        if keywords:
            settings["keywords"] = keywords
        p = Path(wav_path)
        with p.open("rb") as f:
            resp = self.session.post(
                self._url("asr/transcribe"),
                files={
                    "request": (None, json.dumps(settings), "application/json"),
                    "audio": (p.name, f, "audio/wav"),
                },
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
        return check(resp).json()


def output_text(response: dict) -> str:
    """Join the output_text blocks of a /v1/responses result."""
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    parts = []
    for item in response.get("output", []):
        if item.get("type") == "message":
            for block in item.get("content", []):
                if block.get("type") == "output_text":
                    parts.append(block.get("text", ""))
    return "".join(parts)


def _mime(p: Path) -> str:
    return {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".wav": "audio/wav",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".pdf": "application/pdf",
    }.get(p.suffix.lower(), "application/octet-stream")
