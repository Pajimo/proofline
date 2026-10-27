"""Muse Voice Transcribe: 16 kHz mono WAV → transcript with per-turn timestamps.

Usage: python scripts/smoke/test_03_transcribe.py [--wav narration.wav]
"""
import sys
from pathlib import Path

from _common import fixture_wav, run

from proofline.backends import MetaClient


def transcribe():
    wav = Path(sys.argv[sys.argv.index("--wav") + 1]) if "--wav" in sys.argv else fixture_wav()
    result = MetaClient().transcribe(str(wav), mode="DIARIZATION", keywords=["cartridge", "O-ring", "stop tap"])
    turns = result.get("turns", [])
    out = [f"audioDurationMs={result.get('audioDurationMs')}  turns={len(turns)}",
           f"transcript: {result.get('transcript')!r}"]
    for t in turns[:10]:
        out.append(f"  [{t.get('startMs')}–{t.get('endMs')} ms] {t.get('speaker', '')}: {t.get('transcript')}")
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(run("Voice Transcribe (file)", transcribe))
