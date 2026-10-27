"""Shared helpers for the smoke tests: env loading, fixtures, PASS/FAIL output."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))

from proofline import media  # noqa: E402
from proofline.backends import APIError, load_env  # noqa: E402

FIXTURES = Path(__file__).parent / ".fixtures"  # git-ignored
NARRATION = (
    "Right, I've isolated the water at the stop tap. "
    "Now I'm taking the old tap cartridge out. "
    "Fitting the new ceramic cartridge and a fresh O-ring. "
    "Water back on, no leaks."
)

load_env()


def fixture_video() -> Path:
    """A 10-second 720p H.264 MP4 with synthetic speech. Contains no personal footage."""
    FIXTURES.mkdir(exist_ok=True)
    mp4 = FIXTURES / "smoke.mp4"
    if mp4.exists():
        return mp4
    ff = media.ffmpeg_path()
    speech = FIXTURES / "speech.aiff"
    if shutil.which("say"):
        subprocess.run(["say", "-o", str(speech), NARRATION], check=True)
        audio = ["-i", str(speech)]
    else:
        audio = ["-f", "lavfi", "-i", "sine=frequency=440:duration=10"]
    subprocess.run(
        [ff, "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=10", *audio,
         "-t", "10", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "1",
         "-movflags", "+faststart", str(mp4)],
        check=True,
    )
    return mp4


def fixture_wav() -> Path:
    wav = FIXTURES / "smoke.wav"
    if not wav.exists():
        media.to_wav_16k(str(fixture_video()), str(wav))
    return wav


def video_arg() -> Path:
    """Use --video PATH if given (e.g. a real masked clip), else the synthetic fixture."""
    if "--video" in sys.argv:
        return Path(sys.argv[sys.argv.index("--video") + 1]).expanduser()
    return fixture_video()


def run(name: str, fn) -> int:
    """Run one smoke test and print PASS or the exact error. Returns a process exit code."""
    print(f"\n=== {name} ===")
    t0 = time.time()
    try:
        detail = fn()
        print(f"PASS  {name}  ({time.time() - t0:.1f}s)")
        if detail:
            print(detail if isinstance(detail, str) else json.dumps(detail, indent=2)[:3000])
        return 0
    except KeyError as exc:
        print(f"SKIP  {name}: {exc.args[0]}")
        return 2
    except APIError as exc:
        print(f"FAIL  {name}  ({time.time() - t0:.1f}s)")
        print(f"  {exc.method} {exc.url}")
        print(f"  HTTP {exc.status}")
        for h in ("x-request-id", "x-fb-trace-id", "x-fb-debug", "cf-ray", "server"):
            if h in {k.lower() for k in exc.headers}:
                print(f"  {h}: {next(v for k, v in exc.headers.items() if k.lower() == h)}")
        print(f"  body: {exc.body[:3000]}")
        return 1
    except Exception:  # noqa: BLE001
        print(f"FAIL  {name}  ({time.time() - t0:.1f}s)")
        traceback.print_exc()
        return 1
