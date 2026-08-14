---
name: tax-return-preparation
description: Use when preparing evidence-backed personal tax returns.
version: 1.0.0
author: Darwin
license: MIT
metadata:
  hermes:
    tags: [tax, compliance, evidence, spreadsheets, xlsm]
    related_skills: [xlsx, document-digitization-audit, grounded-citations]
---

# Tax Return Preparation

Prepare high-stakes personal tax drafts from mixed evidence, official instructions, and government workbooks. The deliverable is an auditable draft—not a claim that a return was filed or professionally certified.

## When to Use

Use this skill when a user asks to prepare, reconcile, populate, audit, or verify a personal income-tax return from certificates, statements, payroll records, government reports, form instructions, or an official spreadsheet. It is especially relevant when evidence overlaps, legal limits interact, or a macro-enabled government workbook must remain intact.

Do not use it to imply professional representation, submit a return without explicit authorization, or present an unrecalculated workbook as final.

## Core principles

- Treat statutes, tax-authority instructions, and the correct tax-year form/workbook as authoritative.
- Read project READMEs, taxpayer context, evidence hierarchy, and form instructions before extracting numbers.
- Prefer validated transcripts and canonical spreadsheet exports when the corpus explicitly designates them authoritative.
- Preserve provenance for every material figure: source document, page/row, interpretation, and destination form field.
- Reconcile multiple representations of the same economic event; never sum certificates, payroll records, invoices, bank statements, and exogenous reports blindly.
- Separate arithmetic certainty from legal-treatment uncertainty. Model material alternative treatments when the difference affects tax due.
- Never state that a return was filed, accepted, or final unless that external event was actually verified.

## Workflow

### 1. Establish scope and authority

1. Identify taxpayer, jurisdiction, tax year, filing year, form, residency/status, and whether this is a first return.
2. Read every governing README/context file and the complete official form instructions.
3. Confirm that workbook formulas, UVT/index values, thresholds, and rate tables match the target tax year.
4. Build a checklist of required outputs: form draft, workbook, readable mirror, assumptions/discrepancies, and verification report.

### 2. Build an evidence ledger

Create one canonical record per economic event or closing balance with:

- concept and tax category;
- gross amount, non-taxable amount, withholding, and closing balance as applicable;
- primary source plus corroborating sources;
- duplicate group/event identifier;
- chosen amount and reconciliation rationale;
- intended workbook cell/form line;
- confidence and review flag.

Use certificates or detailed canonical records as primary evidence when an aggregate differs by immaterial rounding. Explicitly document every discrepancy, even one-unit differences.

### 3. Resolve tax treatment

For each category:

1. Map gross income, non-taxable income, costs, deductions, exemptions, withholding, assets, and debts to official instructions.
2. Apply sublimits before global limits in the sequence required by law/formulas.
3. Distinguish benefits inside a global cap from additions outside it.
4. Compute an independent form-line draft using the authority's rounding convention.
5. For material ambiguity, show a recommended treatment and at least one quantified alternative. Flag it for professional confirmation.

### 4. Populate government workbooks conservatively

- Inspect sheet structure, unlocked input cells, formulas, data validations, and VBA dependencies before writing.
- Write only validated unlocked non-formula inputs.
- Use exact data-validation list values, including punctuation and trailing spaces where required.
- Prefer a machine-readable assignment ledger containing sheet, cell, value, reason, and source.
- Do not write helper/protected cells to force an output. Choose the supported user-facing input option that makes the workbook calculate the intended result.

For complex `.xlsm` files with VBA, ActiveX, drawings, or unsupported OOXML extensions, avoid a full `openpyxl` or LibreOffice round trip. Patch only the targeted worksheet XML cells in a copy of the package, preserve all other ZIP members byte-for-byte, and set workbook calculation properties to request a full recalculation on open.

### 5. Produce a readable mirror

The human-readable report should include:

- identity and scope;
- legal/instructional basis;
- asset and income reconciliations;
- deductions/exemptions and limits;
- principal form lines in filing units;
- projected tax, withholding, advance, and balance;
- resolved discrepancies;
- assumptions and material review items;
- exact steps required before filing.

Avoid burying the projected result. Present it near the top and repeat the critical caveat beside it.

### 6. Compare an external preparer's completed form

When reconciling the draft against a completed PDF prepared by an accountant or other professional:

1. Extract the PDF's native text layer first, then use layout-aware OCR when the form is visually dense. Compare both outputs and visually inspect the rendered page before trusting box-to-value mappings.
2. Build explicit `field/casilla → value` maps for both drafts. Compare the maps mechanically and sort differences by absolute amount, not by form order.
3. Separate **independent input/treatment differences** from **propagated calculated differences**. Group downstream fields that share one cause instead of presenting each as a separate disagreement.
4. Reconstruct both sides' arithmetic where possible. Explain the internal draft from cited inputs and formulas; label any explanation of the external preparer's choice as an inference unless their workpapers establish it.
5. Check whether a downstream tax delta exactly matches a previously modeled alternative legal treatment. Exact reconciliation is stronger evidence than a merely plausible narrative.
6. Treat one-thousand-peso differences separately when they arise from rounding order. Show the exact unrounded values and the two rounding sequences.
7. If a total differs but the form lacks supporting schedules, do not reverse-engineer a specific asset or deduction as fact. State the implied residual under an explicit “all other components equal” assumption and ask for the preparer's detail.
8. End with a short set of targeted questions tied to the material root causes.

For a condensed worked pattern, see `references/comparing-external-tax-drafts.md`.

### 7. Verify before delivery

At minimum verify:

- generated file exists and ZIP integrity passes;
- package member names/count match the source where preservation is expected;
- every assignment reads back exactly;
- no assignment replaced a formula;
- formula count and formula text are unchanged;
- VBA project hash matches byte-for-byte;
- ActiveX/drawing/sensitive parts match byte-for-byte;
- workbook requests full recalculation;
- independent calculations reconcile to expected form lines under documented rounding;
- every reported external-draft difference appears in the mechanically generated comparison;
- grouped downstream differences reconcile to their stated root cause.

Do not treat stale formula caches as final. If native Excel/VBA execution is unavailable, say so and require the user to open the workbook in supported Microsoft Excel, enable macros, recalculate, run official macros, and compare outputs against the independent mirror.

## Pitfalls

- **Double counting:** the same payment appears in exogenous data, a certificate, payroll liquidation, and a statement.
- **Wrong-year values:** a later-year cadastral appraisal or vehicle assessment is not automatically the prior tax year's fiscal value.
- **Aggregate/detail mismatch:** preserve the discrepancy and state why detail or aggregate was selected.
- **Unsupported workbook round trip:** saving a macro workbook through a library may rewrite or remove unsupported extensions even when `keep_vba=True`.
- **Protected helper writes:** a failed safeguard is a signal to use the intended validated input, not bypass protection.
- **False precision:** calculations made before native recalc are projections, not final workbook outputs.
- **Legal ambiguity hidden as arithmetic:** quantify the tax delta so the user knows what deserves professional review.

## Supporting references

- See `references/colombia-dian-ayudarenta.md` for DIAN Formulario 210 and AyudaRenta-specific implementation notes learned from a verified preparation workflow.
