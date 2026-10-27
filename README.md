# Proofline

**Video-verified invoices for UK tradespeople.**

A plumber films the job on a chest-mounted phone and talks through it as they work. Proofline turns the footage into an invoice where every line links to the moment in the video that proves it. Lines with no evidence are flagged and never added silently, and nothing is sent until the tradesperson approves it.

> Status: day 1 of the Meta Global AI Developer Hackathon (Indie track, "Build for Your World"). Work in progress.

## Built during the hackathon (from 27 Oct 2026)

All the code in this repository was written during the hackathon building period (27 Oct – 4 Nov 2026). The commit history is the record: the first commit is dated 27 Oct 2026. No earlier code was brought in.

| Date | What was built |
|---|---|
| 27 Oct | Repo scaffold, verified-line-item schema, plumbing job pack, API smoke tests, ffmpeg pipeline |
| 27 Oct | First end-to-end run: video → Voice Transcribe → Spark 1.3 → invoice lines priced from the pack, with proof links and flags |

## How it works

1. **Record.** The phone records the job as 720p MP4 clips of 5 minutes or less. The customer's consent to recording is shown on screen.
2. **Mask.** SAM 3.1 finds faces, family photos and house numbers so they can be blurred. Only the masked copy is stored, read by other models or shown to the customer.
3. **Transcribe.** Muse Voice Transcribe turns the narration into text with timestamps for each speaker turn.
4. **Extract.** Muse Spark 1.3 reads the video and transcript and returns steps, parts and times as JSON lines, each with `t_start` and `t_end`.
5. **Verify.** SAM 3.1 tracks each part inside its line's time window and saves before and after evidence frames.
6. **Draft.** Muse Wonder drafts the job report, the invoice (priced from the job pack's price list) and an optional follow-up quote.
7. **Approve.** Proofline reads a summary aloud. The tradesperson says "send it" or "change labour to 1.5 hours".
8. **Deliver.** The invoice PDF goes to the customer on WhatsApp, and each line links to `video#t=` as proof.

## Which model does what

| Model | Job |
|---|---|
| SAM 3.1 | Privacy masking; part tracking and evidence frames |
| Muse Voice Transcribe | Narration to timestamped turns; voice commands (realtime) |
| Muse Spark 1.3 | Video + transcript to timed line items |
| Muse Spark Open (Baseten) | Open-weight backend for the same extraction; head-to-head eval |
| Muse Wonder 1.0 | Job report, invoice wording, follow-up quote |

At runtime the product calls only Meta's models.

## Rules the product follows

- Every invoice line needs evidence. A line without it is flagged, never included silently. The target is 0 made-up parts.
- Nothing is sent without the tradesperson's approval.
- Proofline never generates Gas Safe records or electrical certificates. See [docs/excluded-certificates.md](docs/excluded-certificates.md).
- The customer's consent to recording is shown on screen. See [docs/privacy-and-consent.md](docs/privacy-and-consent.md).

## Repository layout

```
core/          Python library: video + narration → verified line items
evals/         benchmark: labelled jobs, trap clips, scoring scripts
apps/trades/   Next.js phone app: record, invoice PDF, voice approval, WhatsApp
packs/         job packs (plumbing.yaml first): price list, parts, SAM prompt words
scripts/smoke/ API smoke tests
docs/          privacy and consent, excluded certificates, costs
```

## Library API (target)

```python
import proofline

job = proofline.analyze(video="job.mp4", price_list="packs/plumbing.yaml")
for line in job.lines:
    print(line.description, line.qty, line.price, line.t_start, line.t_end,
          line.evidence_frames, line.confidence)
```

The schema for a verified line item is published at [core/proofline/schemas/verified_line_item.schema.json](core/proofline/schemas/verified_line_item.schema.json).

## Setup

You need Python 3.9 or later. ffmpeg is optional: if it isn't installed, the `imageio-ffmpeg` package supplies a static binary.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
cp .env.example .env   # then add your keys in an editor
python scripts/smoke/run_all.py
```

Draft an invoice from a job video (it prints the draft and sends nothing):

```bash
PYTHONPATH=core python -m proofline job.mp4 --pack packs/plumbing.yaml --out evals/runs/job01
```

## Evals

_Results to come._ The plan is in [evals/README.md](evals/README.md): labelled home jobs, trap clips, privacy clips and narration-only jobs. The scores are line accuracy, made-up parts, proof-link accuracy, masking and approval safety.

## Limits

_To be written. This will cover what Proofline doesn't do, known failure modes and cost per job minute._

## Tooling disclosure

_One module will be built with Muse Code; details to come._ The product itself only calls Meta models.

## License

Apache-2.0. See [LICENSE](LICENSE).
