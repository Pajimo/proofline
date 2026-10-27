import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from proofline.sam import parse_line, parse_stream  # noqa: E402

# Mask payloads are base85 and can contain "|", ">", "," and digits.
ONE = "<0f>0<|box;x1=272;y1=125;x2=657;y2=497;w=1280;h=720|><|mask;x=0;y=0;data=373,386,~!!|>,9<|x,12|>"
TWO = ("<7f>3<|box;x1=1;y1=2;x2=30;y2=40;w=320;h=334;c=0.91|><|mask;x=0;y=0;data=4,4,!a|b>,c|>"
       ",12<|box;x1=5;y1=6;x2=70;y2=80;w=320;h=334|><|mask;x=0;y=0;data=4,4,~zz|>")


def test_single_object():
    frame, boxes = parse_line(ONE)
    assert frame == 0 and len(boxes) == 1
    assert (boxes[0].obj_id, boxes[0].x1, boxes[0].y2, boxes[0].frame_w) == (0, 272, 497, 1280)


def test_two_objects_with_confidence():
    frame, boxes = parse_line(TWO)
    assert frame == 7
    assert [b.obj_id for b in boxes] == [3, 12]
    assert boxes[0].confidence == 0.91 and boxes[1].confidence is None


def test_out_of_order_and_empty():
    frames = parse_stream([TWO, ONE, "", "noise"])
    assert sorted(frames) == [0, 7]
    assert parse_stream([]) == {}
