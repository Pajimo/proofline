# Early test on free stock clips (27 Oct 2026)

These are 6 free Pexels clips, 8–31 seconds each, used before any of our own footage existed. They're close-ups of tap and toilet work with no narration. The clips themselves are not in the repo (Pexels licence; videos are git-ignored). Pexels ids: 13945110, 4296258, 7584858, 9890448, 9890450, 9890452.

## Spark 1.3 (video only, no transcript)

- **No made-up work.** On a clip that only shows a dripping tap, it said "no active repair shown" and listed no steps or parts.
- Step times were plausible on every clip. On the toilet clip, it named the mounting bolt, the hand tool and the bag of hardware.
- It described every clip correctly. It sometimes called a tool a "part", for example "supply pipe" listed as a part when nothing was replaced. The pack's parts list has to anchor this.

## SAM 3.1 (one noun phrase per request)

| Prompt | Result |
|---|---|
| `tap` | Found in every clip that has one, in 98–100% of frames |
| `toilet` | 250 of 251 frames |
| `wrench` / `pipe wrench` | **Found in 1 of the 3 wrench clips** (about 92% of frames). It got **0 frames** in the other two, even though the wrench is clearly visible. |
| `glove` / `hand` | Inconsistent: from 0% to 92% of frames on similar clips |

**What this means for the build:** SAM can miss something that is clearly visible. So "SAM found nothing" can't by itself be grounds to call a part made up. Evidence should be:
- **verified** when Spark and SAM agree,
- **weak** when only one of them saw it,
- **missing** when neither did.

Try more than one SAM wording per part (the pack already allows a list) and keep the one that matches best.

Latency figures are in [docs/costs.md](../docs/costs.md).
