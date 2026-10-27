"""Muse Spark Open on Baseten: OpenAI-compatible chat completions."""
from __future__ import annotations

import os
from typing import Optional

import requests

from .base import check, require_env

# The brief's hackathon id (meta-models/muse-spark-open-1026) returns 404; the public id works (27 Oct 2026).
DEFAULT_MODEL = "meta-models/muse-spark-open"


class BasetenClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 model: Optional[str] = None, timeout: float = 600):
        self.api_key = api_key or require_env("BASETEN_API_KEY")
        self.base_url = (base_url or os.environ.get("BASETEN_BASE_URL") or "https://inference.baseten.co/v1").rstrip("/")
        self.model = model or os.environ.get("BASETEN_MODEL") or DEFAULT_MODEL
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {self.api_key}"

    def chat(self, messages: list, max_tokens: int = 4000, **extra) -> dict:
        body = {"model": self.model, "messages": messages, "max_tokens": max_tokens, **extra}
        resp = self.session.post(f"{self.base_url}/chat/completions", json=body, timeout=self.timeout)
        return check(resp).json()


def message_text(response: dict) -> str:
    return response["choices"][0]["message"].get("content") or ""
