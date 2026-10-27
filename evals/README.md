# Evals

Labelled ground truth lives here. Raw footage does not: it stays in git-ignored `evals/**/raw/`, and only masked derivatives are ever shared.

## Test set

| Set | Count | What it tests |
|---|---|---|
| `jobs/` | 6 | Real home jobs with written ground truth (steps, parts, minutes) |
| `traps/` | 6 | A part shown but not used; a part named but never shown; a price said out loud |
| `privacy/` | 4 | A face, a family photo, a house number, an addressed letter |
| `narration_only/` | 4 | Audio only, no useful video |

## Measures

| Measure | Target |
|---|---|
| Step precision and recall | Report as measured |
| Invoice line accuracy | ≥ 90% |
| Made-up parts | 0 |
| Proof-link accuracy (±5 s) | ≥ 90% |
| Masking | 100% |
| Approval safety (nothing sent unapproved) | 100% |

## Comparisons

- Spark 1.3 vs Spark Open (Baseten)
- Video plus narration vs narration only
- Cost and seconds per job minute

Scoring scripts arrive on day 3 (29 Oct).
