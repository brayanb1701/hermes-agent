# Colombia: DIAN Formulario 210 and AyudaRenta

Session-specific technical notes from preparing an evidence-backed individual return for year 2025. Reconfirm annual values against the current DIAN release before reuse.

## Evidence reconciliation patterns

- DIAN exogenous information may overlap with employer certificates, final payroll liquidations, bank certificates, and electronic invoices. Treat these as corroborating representations unless they are distinct economic events.
- A consolidated bank certificate may already include a low-balance affiliate account. Verify inclusion before adding the affiliate's separate certificate.
- Where payroll liquidation differs from exogenous information by a trivial amount, choose one canonical figure, document the difference, and never add both.
- Detailed electronic-invoice records can differ from an aggregate exogenous row by one peso. Record the discrepancy and choose the explicitly designated canonical source.
- Closing asset values must belong to the tax year: do not substitute a next-year cadastral certificate or vehicle tax assessment without a supported legal bridge.

## Formulario 210 patterns for 2025

- UVT 2025: COP 49,799. Reconfirm from the official annual resolution when applying this reference in another return.
- Employment income includes unjustified-dismissal indemnities and other labor payments under the Formulario 210 instructions.
- Ordinary 25% labor exemption has a 790-UVT annual sublimit.
- General exemptions/deductions limit is 40%, capped at 1,340 UVT, with allocation order controlled by the form instructions/workbook.
- A qualifying labor dependent can involve both the ordinary dependent deduction and the additional 72-UVT line when the statutory conditions permit it. The same dependent may support both for employment income under the instructions; verify current law.
- Electronic-invoice 1% and the 72-UVT dependent addition are represented separately in the form's combined limitation lines; follow the current form rather than assuming every benefit is inside the 1,340-UVT cap.
- First-time declarants calculate a 25% next-year advance and subtract current-year withholdings; the result can be zero.

## Termination indemnity issue

AyudaRenta 2025 includes a dedicated input for private-sector definitive-retirement indemnities. Its formula graph can treat 25% of that amount separately from the ordinary 790-UVT sublimit while retaining the overall 1,340-UVT limit. Because this can materially change tax due:

1. Populate the dedicated input rather than combining the amount into generic salary.
2. Independently calculate both the workbook treatment and a conservative alternative that applies only the ordinary sublimit.
3. Report the tax delta prominently.
4. Require professional confirmation before filing; workbook behavior is evidence of DIAN's implementation, not a substitute for legal advice.

## Safe XLSM population method

For the DIAN workbook, a successful preservation workflow was:

1. Reverse-engineer workbook/sheet relationships, formulas, validations, and unlocked inputs.
2. Maintain a JSON assignment ledger: `sheet`, `cell`, `value`, `reason`, `source`.
3. Validate every destination against an unlocked non-formula input index.
4. Copy the source ZIP package and patch only targeted worksheet XML `<c>` elements.
5. Refuse formula-cell writes.
6. Store strings as `inlineStr`, numbers as numeric `<v>` values.
7. Set `calcMode="auto"`, `fullCalcOnLoad="1"`, and `forceFullCalc="1"` in `xl/workbook.xml`.
8. Preserve every unrelated package member and verify VBA, ActiveX, and drawings byte-for-byte.
9. Read all assigned values back and compare source/output formula tuples exactly.

A protected helper cell rejected during assignment should not be bypassed. Use the workbook's validated visible selection value—for example, a generated “valor de compra” option—so formulas reach the result through the intended path.

## Verification boundary

ZIP/XML/VBA hash verification establishes structural preservation but does not execute Excel VBA. Final delivery instructions should require Microsoft Excel for Windows, macro enablement, full recalculation, official macro execution, and comparison of generated form lines with the independent calculation report.
