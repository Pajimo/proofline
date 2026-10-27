"""Parse SAM 3.1 streamed output into boxes per frame.

Each line is one frame:  <Nf>id<|box;x1=..;y1=..;x2=..;y2=..;w=..;h=..[;c=..]|><|mask;...|>[,id<|box;...|><|mask;...|>]
Frame numbers can skip or arrive out of order, and object ids aren't stable across occlusion.
Mask payloads are base85 and can contain almost any character, so records are found by their
all-numeric box token instead of by splitting on separators.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

FRAME_RE = re.compile(r"<(\d+)f>")
RECORD_RE = re.compile(
    r"(?:^<\d+f>|\|>,)(\d+)<\|box;"
    r"x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)(?:;c=([\d.]+))?\|>"
)


@dataclass
class Box:
    obj_id: int
    x1: int
    y1: int
    x2: int
    y2: int
    frame_w: int
    frame_h: int
    confidence: Optional[float] = None

    @property
    def area_frac(self) -> float:
        return (self.x2 - self.x1) * (self.y2 - self.y1) / float(self.frame_w * self.frame_h)


def parse_line(line: str):
    """Return (frame_index, [Box, ...]) for one streamed line, or None if it isn't a frame line."""
    line = line.strip()
    m = FRAME_RE.match(line)
    if not m:
        return None
    boxes = [
        Box(int(r[1]), int(r[2]), int(r[3]), int(r[4]), int(r[5]), int(r[6]), int(r[7]),
            float(r[8]) if r[8] else None)
        for r in RECORD_RE.finditer(line)
    ]
    return int(m.group(1)), boxes


def parse_stream(lines: Iterable[str]) -> Dict[int, List[Box]]:
    """Frame index -> boxes. An empty dict means zero matches."""
    frames: Dict[int, List[Box]] = {}
    for line in lines:
        parsed = parse_line(line)
        if parsed:
            frames[parsed[0]] = parsed[1]
    return frames


def frame_to_seconds(frame: int, fps: float) -> float:
    return frame / fps
