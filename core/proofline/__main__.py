"""python -m proofline job.mp4 [--pack packs/plumbing.yaml] [--out evals/runs/job01]"""
from __future__ import annotations

import argparse

from .backends import load_env
from .invoice import render
from .pipeline import analyze


def main() -> None:
    ap = argparse.ArgumentParser(description="Draft a video-verified invoice from a job recording.")
    ap.add_argument("video")
    ap.add_argument("--pack", default="packs/plumbing.yaml")
    ap.add_argument("--out", help="working folder for clips and job.json (default: next to the video)")
    a = ap.parse_args()
    load_env()
    job = analyze(a.video, a.pack, work_dir=a.out)
    print()
    print(render(job))
    print(f"\nFull output: {job.meta['work_dir']}/job.json")


if __name__ == "__main__":
    main()
