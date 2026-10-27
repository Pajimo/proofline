# Recording checklist

Use this for every clip in the eval set. Raw footage goes in `evals/raw/`. That folder is git-ignored, so footage is never committed.

## Before you start

- [ ] Phone charged, with at least 5 GB free storage.
- [ ] Chest mount on. The frame should show your hands and the work area, not the ceiling.
- [ ] Camera: **1080p or 720p at 30 fps**, not 4K or 60 fps. On iPhone, set Settings → Camera → Formats → **Most Compatible** so it records H.264. This matters because SAM 3.1 rejects WebM and VP9.
- [ ] Turn off HDR video and Action mode, so the frame rate stays steady.
- [ ] Good light on the work area. Turn on a lamp under the sink if you need to.
- [ ] Quiet room: no TV, radio or extractor fan if you can help it.
- [ ] Decide the clip id now (see [Naming](#naming)) and write it on your notes.

## While recording

**Start every clip by saying the clip id and the job**, for example: "trap two, part named but not shown". This makes the files easy to match up later.

Narrate the way a tradesperson would talk to a customer. Don't read a script.

- **Before each step,** say what you're about to do: "Isolating the water at the stop tap."
- **When a part appears,** name it **and** hold it in shot for about 2 seconds: "This is the new ceramic cartridge." SAM needs a clear view to track it.
- **Show "before" and "after" for each part:** the old part coming out, then the new part fitted.
- **When a step finishes,** say so: "That's the cartridge in."
- **Never** read out a phone number, address or full name.

Keep each clip **5 minutes or shorter** where you can. Longer jobs are fine, because the pipeline splits them, but short clips are quicker to label.

## Right after recording (same evening)

1. Copy the clip to `evals/raw/<clip_id>.mp4` (or `.mov`).
2. Copy `evals/ground_truth/_template.yaml` to `evals/ground_truth/<clip_id>.yaml` and fill it in **while you still remember the job**. Scrub through the video to get the times.
3. Run the checker:
   ```bash
   .venv/bin/python evals/check_ground_truth.py
   ```

## Naming

| Set | Ids | Count |
|---|---|---|
| Real jobs | `job01` … `job06` | 6 |
| Trap clips | `trap01` … `trap06` | 6 |
| Privacy clips | `priv01` … `priv04` | 4 |
| Narration only | `narr01` … `narr04` | 4 |

## The 6 trap clips

Each trap has one rule the pipeline must follow. Record **two of each**, in different rooms or with different parts.

| Trap | What you do on camera | What the pipeline must do |
|---|---|---|
| **Shown, not used** | Hold up a spare part ("I've brought a spare TRV"), then put it back in the bag. | No line for it. At most a `shown_not_used` flag. |
| **Named, not shown** | Say "fitted a new washer" while the camera points elsewhere. | Flag it as `narration_only`. Never add it silently. |
| **Price said aloud** | Say "that valve's thirty quid" for a part on the price list. | Use the **price list** price and add a `price_spoken_aloud` flag. |

## The 4 privacy clips

Film something ordinary near the work area that **must** be blurred. For example: a framed family photo on the windowsill, an envelope with an address (use a fake address you printed yourself), a house number through the window, or someone's face walking past. Only film people who have agreed to it.

The target is that 100% of these get masked.

## Narration-only clips

For these, point the phone at the floor or cover the lens and narrate a whole job. They test what the pipeline does when the video shows nothing, so every line should come back `narration_only`.

## Shortcut

You're filming your own home, so you can combine sets: leave a family photo in shot during a trap clip, and that clip also becomes a privacy clip. Record each item in the ground truth's `privacy` list.
