# Costs

Published prices, checked on 26 Oct 2026. Per-job figures will be measured in the evals.

| Model | Price |
|---|---|
| Muse Spark 1.3 | $1.25 / 1M input tokens, $4.25 / 1M output tokens |
| Muse Wonder 1.0 | $4 / 1M input tokens, $20 / 1M output tokens |
| SAM 3.1 | $0.20 / 1,000 frames (minimum 50 frames per request) |
| Muse Voice Transcribe | $0.18 / hour |
| Muse Spark Open (Baseten) | _To be measured_ |

## Measured (27 Oct 2026, 6 free stock clips of 8–31 s, 720p at 30 fps)

**Spark 1.3 video input is about 270 tokens per second of video.** Input tokens were 1,899 / 2,266 / 2,535 / 3,908 / 7,172 / 8,264 on clips of 7.6 / 8.4 / 9.1 / 14.9 / 26.4 / 30.6 s, including about 200 prompt tokens. At $1.25 per 1M tokens, that is about $0.02 of input per job minute. Output was 1.1k–2.3k tokens per clip (mostly reasoning), about $0.01. Each clip took 10–17 s at medium reasoning.

**SAM 3.1 latency depends on how many frames match, not on the clip length.** A prompt with zero matches came back in 8–25 s. A prompt that matched most frames took about 0.2–2 s **per matched frame**: 793 matched frames took 150–760 s, and 820 matched frames took about 1,580 s. That run sent 4 requests at once, so some of the time may be queuing. Even so, SAM at full frame rate over a whole job is far too slow.

So:
- Run SAM only inside each line's time window (`t_start` to `t_end`), never on the whole job.
- Downsample to a few fps before SAM. The minimum is still 50 frames per request.
- Measure latency again with one request at a time before choosing the fps.

Still to measure: cost per real job minute, and Spark Open on Baseten.

Back-of-envelope for SAM: a 30-minute job at 30 fps is 54,000 frames, or $10.80 per concept. That is too much, so parts are tracked only within each line's time window, and video can be downsampled before masking.

## Measured (28 Oct 2026): customer-style clips, 15 s

**SAM 3.1, one request at a time.** 15 s clips cut from stock video:

| Clip, prompt | 30 fps (450 frames) | 10 fps (150 frames) |
|---|---|---|
| outdoor tap, `tap` | 43.7 s (449 matched) | **12.5 s** (150 matched) |
| toilet, `toilet` | 32.9 s (250 matched) | **13.2 s** (83 matched) |
| kitchen tap, `tap` | 40.3 s (271 matched) | **11.4 s** (90 matched) |
| kitchen tap, `water` | 8.4 s (0 matched) | 4.0 s (0 matched) |

So highlights run at **10 fps on the evidence window**: about 12 s for a 15 s clip, plus about 3 s upload. Cost: 150 frames is $0.03. `water` matched nothing, even on a clip with running water, so highlight the part (tap, joint, gauge), not the water.

**Spark 1.3 triage** (video, transcript and fault pack, medium reasoning): 13–25 s per clip. Total from receiving the clip to finding: 17–30 s, including ffmpeg, Transcribe (about 2 s) and upload (2–6 s).

**Muse Wonder 1.0 tool calling**: two turns (tool call, then reply after the tool result) took 24.6 s in total. Each turn used about 400–500 reasoning tokens. That's slow for chat, so the hard stops and first reply must not wait on Wonder.
