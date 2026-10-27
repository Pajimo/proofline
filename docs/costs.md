# Costs

Published prices, checked on 26 Oct 2026. Per-job figures will be measured in the evals.

| Model | Price |
|---|---|
| Muse Spark 1.3 | $1.25 / 1M input tokens, $4.25 / 1M output tokens |
| Muse Wonder 1.0 | $4 / 1M input tokens, $20 / 1M output tokens |
| SAM 3.1 | $0.20 / 1,000 frames (minimum 50 frames per request) |
| Muse Voice Transcribe | $0.18 / hour |
| Muse Spark Open (Baseten) | _To be measured_ |

Not documented yet, so to be measured: video frame sampling, video tokens per second on Spark 1.3, and cost per job minute.

Back-of-envelope for SAM: a 30-minute job at 30 fps is 54,000 frames, or $10.80 per concept. That is too much, so parts are tracked only within each line's time window, and video can be downsampled before masking.
