---
name: cv-document-production
description: Use when editing CVs and generating page-limited PDFs.
version: 1.0.0
author: Darwin
license: MIT
---

# CV Document Production

Use this skill when editing a CV/resume source, tailoring it to an opportunity, or generating a polished page-limited PDF.

## Core rule: separate content from layout

Treat the user's latest edited source as authoritative. Unless the user explicitly requests substantive rewriting, preserve:

- section headings
- organization names
- role titles and company/title hierarchy
- dates
- bullet count and bullet-level meaning
- user-selected wording and ordering

Do not silently rename headings, invert organization and role titles, add an invented professional subtitle, merge bullets, remove details, or rewrite content merely to satisfy a page limit.

## Source-of-truth sequence

1. Read the current editable source immediately before generating the document; users may have edited it since the prior render.
2. Identify user comments and resolve only those comments directly.
3. Distinguish requested content edits from presentation requirements.
4. Build the PDF layout from the current source, not from an earlier assistant draft or previously generated HTML.
5. After rendering, verify that visible headings, role titles, dates, and representative bullets still match the source.

## Page-limit optimization order

When asked for one page if possible or a maximum number of pages, optimize presentation before content:

1. Choose a suitable single- or two-column information architecture.
2. Balance column widths according to actual content volume.
3. Reduce redundant layout chrome, not prose.
4. Tune page margins.
5. Tune section, entry, paragraph, and bullet spacing.
6. Tune line height.
7. Tune body, date, heading, and contact font sizes independently.
8. Re-render and inspect page count.
9. If substantial bottom whitespace remains, increase legibility or spacing until the page is well used.
10. If a small typography increase creates an extra page, back off incrementally rather than cutting content.

One page is not automatically better if it requires unreadably small type. Respect the stated maximum and optimize for legibility inside it.

## Two-column CV pattern

A reliable one-page structure for content-heavy technical CVs is:

- full-width header and professional summary
- wider left column for experience
- narrower right column for education, activities/achievements, and skills
- subtle vertical divider
- organization heading followed by the exact role title and date line from the source

Do not change labels such as `Experience` to `Relevant Experience` or `Extra-Curricular Activities` to `Selected Achievements` without explicit approval.

## PDF generation

Keep an editable source alongside the PDF, typically HTML/CSS for precise print layout. Use A4 or Letter according to the target context. Prefer embedded or reliably available fonts and simple ATS-friendly structure.

For an HTML-to-PDF workflow:

1. Write or update the HTML from the current authoritative source.
2. Render with WeasyPrint or another available print renderer.
3. Check page count with `pdfinfo`.
4. Extract text with `pdftotext -layout` and verify key content.
5. Render pages to images with `pdftoppm`.
6. Visually inspect alignment, clipping, overlap, font legibility, hierarchy, and whitespace.
7. Iterate until both content fidelity and visual quality pass.

## Verification checklist

Before delivery, verify:

- page count satisfies the requested maximum
- current source was not unintentionally overwritten
- section headings match the current source
- organization and role titles match the current source
- dates match the current source
- representative bullets from every experience remain present
- no comments or manual-review annotations leaked into the PDF
- no clipping, overlap, cutoff, orphaned fragments, or column overflow
- font size remains professionally readable
- bottom whitespace is intentional and reasonably small
- links and contact details render correctly
- editable layout source and final PDF paths are reported

## User-correction protocol

If the user says content was changed when only formatting was requested:

1. Acknowledge the incorrect trade-off directly.
2. Re-read the latest source instead of reconstructing from memory.
3. Restore exact headings, hierarchy, and all omitted bullets.
4. Solve page count through layout and typography only.
5. Verify source fidelity in extracted PDF text and visually inspect the final render.

## Supporting reference

- `references/content-preserving-one-page-cv.md` — validated two-column workflow and regression checks for preserving edited CV content while minimizing unused page space.

## Pitfalls

- Do not equate tailoring with permission to rewrite every title.
- Do not optimize page count by silently deleting content.
- Do not use a stale generated HTML file after the Markdown/source changed.
- Do not stop at `Pages: 1`; inspect the rendered page for large unused regions and readability.
- Do not increase font size blindly: a tiny change can trigger a second page because of line-wrap thresholds.
- Do not report that titles were preserved without checking extracted PDF text.
