# Comparing an external tax draft with an internal calculation

Use this pattern when a professional supplies a completed tax-form PDF without the supporting calculation schedule.

## Extraction and validation

- Digital tax forms can have a usable text layer while still losing labels and reading order during extraction.
- Run native layout-preserving extraction and layout-aware OCR independently.
- Prefer the representation that maps labels, field numbers, and values most clearly, but confirm material values against the other extraction and a rendered-page inspection.
- Preserve the OCR output as a derivative, not as authoritative evidence by itself.

## Comparison model

Create two field maps and calculate `external − internal`. Sort nonzero differences by absolute value. Then classify each difference as:

1. **Root input difference** — asset, income, deduction, withholding, etc.
2. **Treatment difference** — same source amount, different legal classification or limit.
3. **Rounding difference** — same exact amounts, different rounding sequence.
4. **Propagated difference** — downstream subtotal, tax, or balance caused by an earlier root difference.

Group propagated fields under their root cause. This keeps a concise report from exaggerating the number of independent disagreements.

## Reconciliation tests

- Recompute subtotals on both sides from visible form fields.
- Test whether a tax delta equals a previously modeled alternative treatment.
- For a total lacking detail, calculate only an implied residual under “all other components equal.” Never present the residual as the professional's actual input.
- For rounding, retain exact source values and show both sequences, e.g. round-then-subtract versus subtract-then-round.

## Report structure

1. Two-sentence conclusion naming the material root causes.
2. Differences ordered largest to smallest, with external value, internal value, signed delta, internal calculation, and cautiously labeled likely cause.
3. Relevant matching fields that constrain the diagnosis.
4. Three to five concrete questions for the professional.
5. Extraction-quality note and professional-review caveat.

## Proven high-value observation

When an internal tax draft already quantifies a conservative alternative treatment, compare it directly with the professional draft. An exact match between the predicted and observed tax delta can identify the disputed treatment much more reliably than inferring from the final balance alone.
