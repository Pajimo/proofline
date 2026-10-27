"""SAM 3.1 tracks one concept through a video (Files API upload → input_video file_id, streamed).

Usage: python scripts/smoke/test_02_sam.py [--video clip.mp4] [--prompt "tap cartridge"]
The synthetic fixture is a test pattern, so zero matches for most prompts is a valid PASS.
"""
import re
import sys

from _common import run, video_arg

from proofline import media
from proofline.backends import MetaClient

FRAME_RE = re.compile(r"<(\d+)f>")


def sam():
    prompt = sys.argv[sys.argv.index("--prompt") + 1] if "--prompt" in sys.argv else "circle"
    client = MetaClient()
    path = video_arg()
    info = media.probe(str(path))
    uploaded = client.upload_file(str(path))
    try:
        lines = client.sam_video(prompt, file_id=uploaded["id"])
    finally:
        try:
            client.delete_file(uploaded["id"])
        except Exception:  # noqa: BLE001
            pass
    frames = sorted(int(m.group(1)) for m in (FRAME_RE.match(l.strip()) for l in lines) if m)
    summary = (f"prompt={prompt!r}  source={info.width}x{info.height}@{info.fps}fps {info.duration:.1f}s  "
               f"frames_with_matches={len(frames)}")
    if frames:
        summary += f"  first={frames[0]} (t={frames[0] / info.fps:.2f}s)  last={frames[-1]}"
        summary += f"\n  sample line: {lines[0][:300]}"
    else:
        summary += "  (zero matches: stream returned no output_text deltas)"
    return summary


if __name__ == "__main__":
    sys.exit(run("SAM 3.1 video", sam))
