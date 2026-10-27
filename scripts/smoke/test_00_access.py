"""Can this machine (in the UK) reach the Meta API at all? Lists models, then sends one tiny text call."""
import sys

from _common import run

from proofline.backends import MetaClient
from proofline.backends.meta import SPARK, output_text


def list_models():
    models = MetaClient().list_models()
    ids = [m.get("id") for m in models.get("data", [])]
    return f"models visible to this key: {ids}"


def tiny_text():
    resp = MetaClient().responses({
        "model": SPARK,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 200,
        "input": "Reply with exactly: proofline ok",
    })
    return f"reply: {output_text(resp)!r}  usage: {resp.get('usage')}"


if __name__ == "__main__":
    codes = [run("Meta API: list models", list_models), run("Meta API: Spark 1.3 text", tiny_text)]
    sys.exit(max(codes))
