from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import requests


class APIError(RuntimeError):
    """A non-2xx response, carrying the exact status and body so callers can print them."""

    def __init__(self, method: str, url: str, status: int, body: str, headers: Optional[dict] = None):
        self.method, self.url, self.status, self.body = method, url, status, body
        self.headers = headers or {}
        super().__init__(f"{method} {url} -> HTTP {status}: {body[:2000]}")


def load_env() -> None:
    """Load .env from the repo root (or the current directory) without overriding real env vars."""
    from dotenv import load_dotenv

    root = Path(__file__).resolve().parents[3]
    for candidate in (root / ".env", Path.cwd() / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)
            return


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise KeyError(f"{name} is not set. Add it to .env (see .env.example).")
    return value


def check(resp: requests.Response) -> requests.Response:
    if not resp.ok:
        raise APIError(resp.request.method, resp.url, resp.status_code, resp.text, dict(resp.headers))
    return resp


def iter_sse(resp: requests.Response):
    """Yield parsed JSON events from a server-sent-events response."""
    for raw in resp.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith("data:"):
            continue
        data = raw[len("data:"):].strip()
        if data == "[DONE]":
            return
        try:
            yield json.loads(data)
        except json.JSONDecodeError:
            yield {"type": "unparsed", "data": data}
