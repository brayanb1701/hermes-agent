# Project closing

Canonical vault workflow: `~/personal_vault/_meta/workflows/projects/project-closing-workflow.md`.

## Trigger

Preferred automation input: `/home/brayan/projects/<slug>/PROJECT_CLOSEOUT.md` with `status: pending`.

## Sufficient input

Need final/outcome facts, proposed status (`complete` or `archived`), result status, result type, summary, evidence/source, artifacts, lessons, follow-up/reopen conditions, and linked opportunity/decision effects.

## Success path

Create/update vault closeout, update README final fields, remove dashboard/backlog rows, add finished row, update decisions/opportunities only when supported, mark workspace closeout complete, and log meaningful structural/finalization changes.

## Insufficient input

Leave project final status and registers unchanged. Mark `PROJECT_CLOSEOUT.md` `status: paused`, append exact missing-info section, and notify Brayan.
