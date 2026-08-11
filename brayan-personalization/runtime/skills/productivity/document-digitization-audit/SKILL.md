---
name: document-digitization-audit
description: "Use when digitizing mixed PDFs, images, and workbooks."
version: 1.0.0
author: Darwin
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [OCR, PDF, XLSX, XLSM, verification, resource-management]
    related_skills: [ocr-and-documents, pdf, xlsx]
---

# Document Digitization and Workbook Audit

## When to Use

Use this skill when a folder combines PDFs or scans with images and spreadsheets, especially when the deliverable must be reliable for downstream LLMs rather than merely readable by a human. It also applies when a macro-enabled workbook must be inspected safely on Linux and its actual compatibility distinguished from static rendering.

Use this orchestration/quality-assurance skill for mixed folders containing PDFs, scans/images, ordinary spreadsheets, and macro-enabled workbooks. Load the specialized `ocr-and-documents`, `pdf`, and `xlsx` skills for extraction primitives; this skill governs sequencing, resource control, validation, and deliverable structure.

## Core principles

- Preserve originals. Write every derivative under a clearly named output directory.
- Inspect capacity before starting local models: CPU/load, RAM/swap, disk, VRAM, GPU utilization, and competing GPU processes.
- Keep the workstation responsive. Run one local model process at a time, one page/image per generation, at low process priority with restricted CPU threads.
- Save page-level results incrementally so interruption or timeout can resume without recomputing completed pages.
- Keep raw model output for provenance and publish a separate validated transcript for downstream agents.
- Do not silently “correct” ambiguous identifiers from a visual impression. If OCR and vision disagree on a plate, account number, ID, amount, or similar high-impact token, retain the source reading, flag the ambiguity, and request/user-record verification.

## Workflow

### 1. Inventory and classify

1. Recursively enumerate files, sizes, and extensions.
2. For PDFs, record page count, encryption state, and embedded-text character count per page.
3. Record image dimensions/mode.
4. Separate ordinary `.xlsx`/`.csv` extraction from `.xlsm`/macro-workbook auditing.
5. Establish expected totals: documents, pages/images, and workbooks. Verification must reconcile against these counts.

### 2. Resource preflight

Before loading a local OCR/VLM:

- Inspect RAM/swap, disk availability, CPU count/load, VRAM, GPU utilization, and GPU processes.
- Use serial generation and batch size 1 unless measured headroom justifies more.
- Restrict `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, and tokenizer parallelism; use `nice` on Linux.
- Test one representative page first and measure observed RSS/VRAM before launching the full corpus.
- If output becomes pathologically long, reduce `max_new_tokens` for future pages rather than letting decorative-pattern loops waste compute.

### 3. OCR with resumable artifacts

For each page/image, persist a JSON record immediately with:

- source path and page number,
- model/engine and prompt,
- render DPI or original-image status,
- elapsed time and character count,
- raw text and any error.

On restart, skip complete page records. Build document-level Markdown only after all page records exist. Maintain a manifest containing expected/completed pages and failures.

### 4. Validate OCR rather than trusting fluency

For PDFs with embedded text, compare page by page:

- normalized word/token coverage,
- numeric-token coverage,
- relative output length,
- empty/near-empty output,
- repeated lines or repeated character patterns.

Common failure: decorative separator lines can trigger symbol repetition until the token limit, causing meaningful text below the separator to disappear. Flag unusually long output, high symbol ratios, and repeated chunks.

Use targeted visual review for:

- image-only pages,
- pages with low text or numeric coverage,
- pages where the embedded text and OCR differ on identifiers or amounts,
- apparent blank/logo-only pages.

Create two layers:

1. `raw-ocr/`: unchanged model output.
2. `validated-transcripts/`: preferred text for agents, with page-level provenance notes. For a digital PDF page where OCR loops or omits content, using the embedded text layer is acceptable after the discrepancy is documented.

Never represent a visual guess as a correction. Record user verification explicitly and make rebuild scripts preserve it.

### 5. Extract ordinary spreadsheets

- Read formulas and cached values separately when formulas exist.
- Export natural tables as CSV plus JSON; provide Markdown summaries for quick agent consumption.
- Preserve identifiers as strings and dates in ISO format.
- Recompute important counts and sums independently from the source workbook, then assert that exported row counts and totals match.
- State when a source only contains an aggregate and lacks transaction-level or third-party detail.

### 6. Audit macro-enabled workbooks safely

Do not save an `.xlsm` with a library that might strip VBA. Prefer read-only package inspection:

- inspect OOXML ZIP relationships, sheet states, dimensions, formulas, cached errors, external links, drawings, and ActiveX parts;
- extract VBA statically (for example with `olevba`) and identify auto-run events, command bars, UserForms, ActiveX handlers, file/process/network behavior;
- distinguish stale external-link metadata from formulas that actually reference external workbooks;
- run a low-priority LibreOffice headless open/export test in a disposable profile with macros disabled;
- treat successful static rendering as evidence only for readability/rendering, not for Excel-specific VBA/ActiveX workflow compatibility.

If the intended UI depends on `Workbook_Open`, `Application.CommandBars`, ActiveX controls, UserForms, or many `veryHidden` sheets, recommend desktop Microsoft Excel for final use even when LibreOffice can render formulas.

### 7. Final verification and handoff

Before completion:

- expected pages/images == completed page records,
- failures == 0 or each failure is explicitly documented,
- all JSON parses,
- validated document count matches source document count,
- spreadsheet exports match source row counts and important sums,
- no OCR/model process remains running,
- provide one README naming preferred entry points and warning users not to feed raw OCR to downstream agents when validated versions exist.

## Pitfalls

- A readable transcript can still contain a one-character identifier error; prioritize exact tokens over prose fluency.
- Embedded PDF text is often more accurate than OCR for digital documents, but reading order may differ. Use coverage metrics as flags, not automatic proof of error.
- Long OCR output is not automatically better; compare it with native text length and repetition patterns.
- Headless LibreOffice export does not prove VBA or ActiveX ran.
- External-link package entries do not prove live formula dependencies; scan formulas for actual external references.
- Avoid parallel OCR plus other heavy workbook/model operations unless measured headroom clearly supports it.

## Reference

See `references/mixed-financial-document-session.md` for a condensed proven workflow, observed failure modes, and verification thresholds from a successful mixed-document run.
