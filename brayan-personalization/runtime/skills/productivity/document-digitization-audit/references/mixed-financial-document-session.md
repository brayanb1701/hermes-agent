# Mixed financial-document digitization: proven details

This reference records reusable details from a successful Linux run over a mixed folder of PDFs, one image, ordinary XLSX reports, and a large Excel/VBA workbook. It intentionally omits personal identifiers and source-specific financial values.

## Resource-safe local GLM-OCR pattern

- Preflight showed ample RAM/VRAM, but the run still used one model process and one page at a time.
- Launch settings used low OS priority, `OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`, `TOKENIZERS_PARALLELISM=false`, and PyTorch expandable CUDA segments.
- A one-page smoke test confirmed the model, renderer, output schema, and resource footprint before the corpus run.
- Observed steady usage was roughly 4 GB VRAM and 1.6 GB process RSS on a 24 GB GPU / 32 GB RAM workstation.
- Page JSON was written immediately after every generation. After stopping an inefficient run, a restart skipped completed pages and continued successfully.

## Token-limit adaptation

A high generation limit allowed dense pages and decorative separator lines to consume excessive time and emit tens of thousands of repetitive characters. The safe recovery was:

1. keep already completed page records;
2. stop the process cleanly;
3. lower future `max_new_tokens` to the model integration’s conservative default;
4. restart and resume from page JSON;
5. validate earlier oversized pages and replace only the validated transcript layer when needed.

Do not delete raw output; it is evidence of why fallback selection occurred.

## Verification heuristics that worked

Page-level flags included:

- embedded text exists but OCR is under 30% of its character length;
- OCR is over about 2.2× a substantial embedded text layer;
- normalized text-token coverage below about 0.55;
- numeric-token coverage below about 0.65 when several numbers exist;
- empty or under-30-character OCR on image-only pages;
- repeated lines, repeated fixed-size chunks, or symbol-dominated output.

These are triage thresholds, not correctness proofs. Tables and different reading order can lower overlap even when both texts are accurate.

## High-impact identifier lesson

A visual reviewer misread one character in a vehicle plate and incorrectly overrode the OCR; the user verified that the original OCR was right. Durable rule:

- never change ambiguous alphanumeric identifiers from a quick visual impression alone;
- zoom/crop and cross-check another source when possible;
- otherwise preserve the OCR, flag ambiguity, and ask for user verification;
- encode the verified value in both the validated transcript and the rebuild script so regeneration cannot revert it.

## XLSX validation pattern

For ordinary reports:

- exported every row to CSV and JSON;
- produced a Markdown summary;
- independently re-read the source workbook;
- asserted source/export row counts and key totals matched exactly.

This caught extraction regressions more reliably than visually scanning the output.

## XLSM/LibreOffice interpretation

Static package inspection revealed a workbook whose intended navigation depended on auto-run VBA, legacy Excel command bars, ActiveX, UserForms, and many `veryHidden` sheets. A disposable-profile LibreOffice headless export rendered a static blank tax form and showed no obvious formula errors. Correct conclusion:

- Linux can inspect structure, formulas, cached values, VBA source, and static rendering;
- the successful export does not establish that the interactive Excel workflow works;
- final use belongs in Microsoft Excel when VBA/ActiveX controls the workflow.

Also distinguish stale OOXML external-link relationships from live dependencies by scanning formulas for `[n]` external-reference syntax.
