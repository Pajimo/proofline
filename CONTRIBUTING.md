# Contributing

Thanks for helping. The most useful contribution is a **trade pack**: one YAML file that teaches the front desk a new trade (handyman, electrician's non-certificate work, locksmith, roofing, and so on). The engine is the same for every trade.

## Add a trade pack

1. Copy `packs/plumbing.yaml` to `packs/<trade>.yaml`.
2. Fill in:
   - `trade`: the label used in prompts ("handyman"), what the trade **covers** and doesn't, the estimate wording (it must say "subject to inspection"), and the question to ask when the video shows nothing useful.
   - `faults`: for each fault, the symptoms, 1–3 follow-up questions (what to film next), SAM words to outline the part (short noun phrases: SAM is reliable on fixtures like "tap" and poor on tools), likely parts, an estimate range, and when it **needs a visit**.
   - `parts`: the price list. Prices are the tradesperson's own; the ones in the repo are illustrative.
   - `excluded`: work this trade must never advise on or quote by message.
3. **Keep the three hard stops** (`gas`, `carbon_monoxide`, `electrical`) in every pack, whatever the trade. The checker refuses a pack without them, or whose messages don't give the emergency numbers.
4. Check it:
   ```bash
   python scripts/check_pack.py packs/<trade>.yaml
   ```
5. Add replay conversations for it in `evals/conversations/`, including at least one safety case and one out-of-scope case, and run:
   ```bash
   python evals/replay.py --pack packs/<trade>.yaml --suite evals/conversations/<trade>.yaml
   ```

## Rules for all changes

- **Safety lives in code, not prompts.** Hard stops, the approval gate for prices, routing and the outbound price check are deterministic and unit-tested. Don't move any of them into a prompt.
- **Customer content is data.** Anything a customer writes, says or films goes into prompts through `wrap_untrusted`.
- **No real customer media in git.** Raw clips live in git-ignored `evals/**/raw/`.
- **No keys in git.** Keys go in `.env`; only `.env.example` is committed.
- **Don't copy code from AGPL projects.**
- Run `python -m pytest -q` before opening a PR. CI runs it, plus the pack checker, on every push.

## Why there's no RAG (yet)

A whole trade pack is about 2k tokens, so it goes into every prompt in full. Retrieval would add an embedding model, an index and a new way to fail (fetching the wrong chunk), with nothing gained at this size. It becomes worth it when the knowledge outgrows the prompt, for example manufacturer manuals, many trades at once, or searching past jobs.
