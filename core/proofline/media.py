"""ffmpeg helpers: normalise phone recordings into what Meta's models accept.

- Video: 720p H.264 MP4 (iOS Safari records MP4; Android Chrome often records WebM, which SAM rejects).
- Audio: 16 kHz mono 16-bit PCM WAV for Voice Transcribe.
- Long jobs: split into clips of 5 minutes or less.

CLI:  python -m proofline.media input.webm --out media/job1
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

CLIP_SECONDS = 300


def ffmpeg_path() -> str:
    """System ffmpeg if installed, else the static binary bundled with imageio-ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("ffmpeg not found. Install it (brew install ffmpeg) or `pip install imageio-ffmpeg`.") from exc


def _run(args: List[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run([ffmpeg_path(), "-hide_banner", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}):\n{proc.stderr[-3000:]}")
    return proc


@dataclass
class ProbeInfo:
    duration: float
    fps: float
    width: int
    height: int
    has_audio: bool


def probe(path: str) -> ProbeInfo:
    """Read duration, fps and size by parsing `ffmpeg -i` (works without ffprobe)."""
    proc = subprocess.run([ffmpeg_path(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    err = proc.stderr
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    vid = re.search(r"Stream #.*Video:.*?(\d{2,5})x(\d{2,5}).*?([\d.]+) (?:fps|tbr)", err)
    if not dur or not vid:
        raise RuntimeError(f"Could not probe {path}:\n{err[-2000:]}")
    h, m, s = dur.groups()
    return ProbeInfo(
        duration=int(h) * 3600 + int(m) * 60 + float(s),
        fps=float(vid.group(3)),
        width=int(vid.group(1)),
        height=int(vid.group(2)),
        has_audio=bool(re.search(r"Stream #.*Audio:", err)),
    )


def to_mp4_720p(src: str, dst: str, fps: int = 30, start: Optional[float] = None,
                duration: Optional[float] = None) -> str:
    """Re-encode to 720p (short side) H.264 + AAC MP4, constant frame rate, faststart."""
    args = ["-y"]
    if start is not None:
        args += ["-ss", f"{start:.3f}"]
    args += ["-i", str(src)]
    if duration is not None:
        args += ["-t", f"{duration:.3f}"]
    args += [
        # Short side to 720, keep aspect, even dimensions. Handles portrait phone video.
        "-vf", f"scale='if(gt(iw,ih),-2,720)':'if(gt(iw,ih),720,-2)',fps={fps}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ac", "1",
        "-movflags", "+faststart",
        str(dst),
    ]
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    _run(args)
    return str(dst)


def to_wav_16k(src: str, dst: str) -> str:
    """Extract narration as 16 kHz mono 16-bit PCM WAV (Voice Transcribe's format)."""
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    _run(["-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst)])
    return str(dst)


def prepare(src: str, out_dir: str, clip_seconds: int = CLIP_SECONDS) -> List[dict]:
    """Split a recording into ≤5-minute clips, each as MP4 + WAV. Returns a manifest."""
    info = probe(src)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    start, idx = 0.0, 0
    while start < info.duration - 0.05:
        length = min(clip_seconds, info.duration - start)
        stem = out / f"clip{idx:02d}"
        mp4 = to_mp4_720p(src, f"{stem}.mp4", start=start, duration=length)
        wav = to_wav_16k(mp4, f"{stem}.wav") if info.has_audio else None
        manifest.append({"index": idx, "offset_s": round(start, 3), "duration_s": round(length, 3),
                         "mp4": mp4, "wav": wav})
        start += clip_seconds
        idx += 1
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Normalise a phone recording for Proofline.")
    ap.add_argument("src")
    ap.add_argument("--out", required=True, help="output directory (git-ignored media/ is a good place)")
    ap.add_argument("--clip-seconds", type=int, default=CLIP_SECONDS)
    a = ap.parse_args()
    print(f"ffmpeg: {ffmpeg_path()}")
    for clip in prepare(a.src, a.out, a.clip_seconds):
        print(json.dumps(clip))


if __name__ == "__main__":
    main()
