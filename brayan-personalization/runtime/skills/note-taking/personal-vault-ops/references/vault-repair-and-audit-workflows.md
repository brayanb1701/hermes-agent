# Vault Repair and Audit Workflows

Use this for unusual vault repair/audit tasks. Normal filing uses `personal-vault-ops`; structural migrations use `vault-workflow-migrations`; recurring report-only audits use `vault-structure-auditor-agent`.

## Schema / orientation repair

If an orientation file such as `_meta/schema.md` is missing, empty, or corrupted:
1. Verify from disk, not only cached tool output.
2. Search session history and nearby vault docs for the intended content.
3. Reconstruct conservatively from stable conventions already used in the vault.
4. Update `_meta/index.md` and `_meta/log.md` if needed.
5. Re-read the repaired files and verify orientation works.

## Retest cleanup

When cleaning artifacts from a failed ingestion/test run:
1. Inventory exact identifiers first: slug, filenames, cache IDs, transcript paths, session/cron IDs if directly tied.
2. Delete only concrete test artifacts that were created solely by that failed test.
3. Clean secondary links in domain maps, indexes, and logs when they now point to removed artifacts.
4. Re-search to verify active vault cleanliness.
5. Call out remaining session/log history as historical residue, not active vault artifacts.

## Retest verification

When auditing whether an ingestion run actually worked:
1. Read relevant handoff/architecture docs.
2. Pull evidence from Hermes logs/session metadata, not only final vault notes.
3. Search the vault for run identifiers.
4. Separate pipeline correctness, fallback correctness, and vault-routing correctness.
5. Report intended path vs actual runtime path.

## Vault organization audit

Start report-only. Inventory filesystem/frontmatter and dependent automation before recommending moves. Treat `projects/` as execution-only. Present a phased plan and do not move/delete/archive notes without approval.

## Meta-folder refinement

Keep `_meta/` root small and move operating docs into clear subfolders such as `architecture/`, `workflows/`, `principles/`, `guides/`, `templates/`, `dashboards/`, `audits/`, and `tmp_analysis/`. Update active links and validate after moves.
