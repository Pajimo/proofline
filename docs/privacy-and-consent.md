# Privacy and consent

- **Consent first.** Before recording starts, the customer is shown on screen that the job is being filmed, why, and who will see it. Recording doesn't start without that step.
- **Mask before anything else.** SAM 3.1 runs on every clip for faces, framed photos, house numbers and envelopes or letters. The matches are blurred. Only the masked copy is stored, read by other models or shown to the customer. The unmasked original is deleted once masking succeeds.
- **Minimum retention.** _Policy to be written._
- **Repo hygiene.** No real footage, audio or phone numbers are committed. See `.gitignore`.
- **Masking eval.** The target is 100% on the privacy clips in `evals/`.
