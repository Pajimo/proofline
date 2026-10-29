# Architecture

```
WhatsApp Cloud API ──webhook──▶ scripts/whatsapp/bot.py  (signature check, dedupe, ack fast)
                                   │
                                   ▼
                          core/proofline/bot.py   one thread per customer, history, jobs, state.json
                                   │
   ┌───────────────────────────────┼─────────────────────────────────────────────┐
   │ 1. safety.rules.check_text    │ keyword hard stops (gas, CO, electrical). No model.  → fixed message
   │ 2. "talk to <owner>"          │ handoff                                              → owner told
   │ 3. pack.excluded_match        │ e.g. gas-side boiler work                            → refuse, owner told
   │ 4. triage.diagnose            │ Voice Transcribe → rules again → Spark 1.3 (video + words + pack)
   │ 5. triage.route (pure code)   │ stop | out_of_scope | visit | more | quote
   │ 6. replies                    │ every customer message → safety.check_outbound (no unapproved £)
   │ 7. quote                      │ owner gets clip + summary + range + Approve / Edit; customer gets
   │                               │ the price only after approval, once
   └───────────────────────────────┴─────────────────────────────────────────────┘
```

**The model describes; code decides.** Spark returns a JSON description (fault, confidence, danger, reading, next question, in scope or not). Routing, prices, safety stops and what may be sent are decided in code and unit-tested.

**Knowledge lives in the trade pack** (`packs/*.yaml`), validated by `scripts/check_pack.py` against `core/proofline/schemas/pack.schema.json`. The whole pack fits in the prompt, so there's no retrieval step.

**Evaluation** has three layers:
1. Unit tests (`tests/`): routing, safety rules, the approval gate, webhook parsing. Run in CI.
2. Conversation replay (`evals/replay.py`): whole conversations through the real bot and real models, with WhatsApp faked, run several times to measure the spread.
3. Labelled home-filmed clips (`evals/README.md`): diagnosis, follow-up question, highlight and routing accuracy.

**Coming next:** SAM 3.1 highlight clips in replies, the Muse Wonder agent loop (tools, step limit, code-level fallbacks), and Spark Open on Baseten as an open-weight path.
