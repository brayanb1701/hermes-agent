# Reorganizing a digitized corpus without needless re-OCR

Use this pattern when users reorganize originals after OCR derivatives already exist.

## Durable approach

1. Define the active source corpus explicitly. Exclude derivative directories and any user-designated archive/redundant folder from discovery, OCR, validation, and completeness counts.
2. Centralize corpus discovery and output-path rules in one shared module used by OCR, verification, transcript building, and final audits.
3. Mirror each active source's parent directory under both raw OCR and validated-transcript roots. Keep general/root sources at the derivative root.
4. Use a stable transcript filename derived from the source filename only; directory identity comes from the mirrored parent path. This avoids opaque flattened names while preventing collisions across categories.
5. Before OCR, map old source paths to new paths. Migrate resumable page-level records, update their `source` provenance field, and regenerate document-level raw/validated transcripts. Do not re-run a local model solely because a file moved or was renamed.
6. OCR only records that remain missing after migration. Load the model only when the missing-job list is non-empty.
7. Preserve prior derivatives for user-designated excluded sources in a clearly labeled archive outside the preferred corpus. Do not spend resources extracting newly added excluded files unless requested.
8. Publish both:
   - a human README that tells agents to prefer validated derivatives and explains fallback to originals;
   - a machine-readable index mapping every active source to its validated output.
9. Extend final verification to assert:
   - active source document/page totals;
   - validated index exactly matches sorted active sources;
   - every indexed output exists;
   - OCR manifest exactly matches active sources and has no failures;
   - completed pages equal expected pages and missing pages equal zero.
10. Re-run the OCR entry point once after completion. A successful idempotence check reports zero missing/new pages and does not load the model.

## Validation policy

Keep raw model output for provenance, but make validated transcripts the agent-facing default. Select OCR or embedded PDF text page by page based on completeness and numeric/token coverage. A final flagged-page count is acceptable only when every flag is resolved by a documented fallback or a specific manual note.

## Agent guidance

The top-level README should state:

- validated derivatives first;
- structured spreadsheet exports instead of opening workbooks directly;
- originals only for ambiguity, layout, or provenance checks;
- excluded/redundant sources are not active evidence unless explicitly requested;
- exact identifiers and amounts must be cited rather than guessed.

## User-resolved context layer

Keep user-provided factual clarifications separate from OCR output and legal/tax conclusions. A dedicated context Markdown file can record:

- filing/history facts and relationships between similar-looking documents;
- categories the user explicitly confirms do not apply;
- documents the user confirms are sufficient for the intended preparation;
- unavailable documents that should not be requested again as generic prerequisites;
- known overlaps between supporting records and annual or third-party reports;
- exact conditions under which an agent may reopen a resolved question.

Reference this context file from the source-root README, derivative README, validated-transcript README, and any workflow handoff. Extend deterministic verification to assert that the file exists, contains critical anti-double-counting language, and is referenced by every agent entry point.

Do not turn user clarification into an unsupported legal conclusion. Treat it as resolved factual context and scope. Reopen only when the evidence contains a concrete contradiction, a material unreconciled amount, or an exact required field that is absent.

## Duplicate-report reconciliation

When source documents and third-party reports may describe the same economic payment:

1. Build a cited component table rather than summing every line blindly.
2. Independently recompute gross amounts, listed deductions, approximate net amounts, and residual differences.
3. Use supporting documents to classify or explain annual-report lines; do not automatically count both.
4. Preserve small residual discrepancies visibly. Strong overlap can justify an anti-double-counting guard without pretending an exact reconciliation has been proven.
5. Keep tax characterization in the decision ledger when it requires judgment.

## Additional pitfalls

- Do not infer “preliminary” versus “definitive” from filenames when the user explains that same-type documents correspond to separate events.
- Absence of a file may mean either missing evidence or a user-confirmed non-applicable category; preserve the distinction.
- Re-running OCR after a pure path move wastes compute and can introduce transcript drift.

