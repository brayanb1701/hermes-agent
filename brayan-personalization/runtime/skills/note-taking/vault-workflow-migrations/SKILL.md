---
name: vault-workflow-migrations
description: Plan and execute scoped migrations of Brayan's personal-vault workflows, templates, dashboards, skills, scripts, and automation without over-migrating unrelated records.
version: 1.1.0
author: Darwin
license: MIT
---

# Vault Workflow Migrations

Use this skill when Brayan asks to rename, generalize, migrate, consolidate, or audit an existing workflow in `~/personal_vault`, especially when the change touches vault schema, templates, dashboards, Hermes skills, cron jobs, agent prompts, or runtime scripts.

This is a class-level migration skill. It should stay reusable across migration types. Keep one-time migration details in `references/` or vault `_meta/tmp_analysis/` / archive notes, not in the main `SKILL.md`.

For normal vault filing/routing, use `personal-vault-ops`. For domain-specific active workflows, load the relevant operational skill as well, such as opportunity intake/preparation skills when the migration touches opportunities.

## Core rule

Scope before editing. Brayan often wants a targeted migration, not a vault-wide rewrite. If he names exclusions or a subset, enforce that boundary exactly.

## Migration workflow

1. Orient with:
   - `~/personal_vault/_meta/schema.md`
   - `~/personal_vault/_meta/index.md`
   - `~/personal_vault/_meta/log.md`
   - the active workflow/template/dashboard files being changed
   - affected Hermes skills, agent prompts, scripts, cron jobs, and config when automation changes
2. Define the migration contract before editing:
   - goal
   - in-scope folders/files/records
   - explicit exclusions
   - old terms/paths/fields to retire
   - new canonical terms/paths/fields
   - compatibility policy: clean cutover vs temporary bridge
3. Inventory matching records/files and classify them as:
   - active source of truth
   - generated output/cache/history
   - historical archive/migration note
   - unrelated false positive
4. Apply changes only to in-scope active files.
5. Preserve review state/status unless the migration itself proves the content is inadequate.
6. Update visible indexes, dashboards, routing matrices, templates, and logs in the same pass when the workflow's public surface changes.
7. Update activation surfaces atomically when automation depends on the migrated paths or names:
   - Hermes skills
   - agent prompt templates
   - scripts
   - cron job skill lists/prompts/scripts
   - config.yaml values
   - personalization/runtime bundle copies when relevant
8. Validate deterministically before reporting done.

## Reference handling

Use supporting files for concrete cases instead of baking one migration's details into this main skill.

- `references/opportunity-preparation-v2-awaiting-review-migration.md` — concrete case notes for the opportunity-preparation migration. Treat it as historical/example context, not the default migration policy.
- `references/opportunity-project-lifecycle-state-diagnosis.md` — reusable diagnosis notes for auditing/refining opportunity and project lifecycle state models, including file-driven closeout-input patterns and common dashboard/frontmatter drift.

When a migration creates reusable lessons, promote only the general rule into this `SKILL.md`. Keep dates, record names, one-off exclusions, and case-specific field mappings in a reference or vault migration note.

## Dashboard / index migration rule

When touching any dashboard, index, or queue:

- Preserve the dashboard's intended ordering semantics unless Brayan explicitly changes them.
- Do not remove rows/items unless the source record is explicitly archived, closed, deleted, or out of scope by the migration contract.
- Prefer a single clear user-facing label over combined labels that mix internal workflow fields with review-facing categories.
- Keep root `README.md` files as orientation surfaces unless Brayan explicitly asks to make one a dashboard. If a dedicated `dashboard.md` exists, tables/queues/current-state lists should live there; the root README should explain folder purpose, record shape, and canonical links.
- When separating README-vs-dashboard roles, update both content and classification surfaces: frontmatter tags, `_meta/index` dashboard sections, log wording, skills, agent prompts, and audit scripts as applicable.
- Verify generated tables by inspecting data rows, not only headers/separators.

## Validation checklist

Before reporting done:

1. Run `git diff --check` in `~/personal_vault` if the vault changed.
2. If Hermes runtime/personalization changed, run `git diff --check` in the Hermes personalization checkout too.
3. Compile affected Python scripts with `python3 -m py_compile`.
4. Dry-run affected scanners/dispatchers when available.
5. Search in-scope active files for retired terms, fields, and paths.
6. Search activation surfaces for old skill/path names when skills, scripts, or cron jobs moved.
7. Verify dashboards/indexes still point to existing files.
8. Report dirty git state precisely; do not assume unrelated uncommitted files are mistakes.

## Pitfalls

- Do not turn a targeted migration into a mass edit.
- Do not preserve obsolete field names for compatibility when Brayan has approved a clean cutover.
- Do not blindly replace every instance of a retired term; some historical notes, examples, or mode names may remain semantically correct.
- Do not migrate generated logs, old cron outputs, session transcripts, or historical audit files unless the user explicitly asks.
- Do not modify pinned skills directly. If a pinned skill needs an approved patch, unpin it, patch it, repin it, and verify the pin is restored.
- Do not overcorrect from a path/layout migration into generalized structural rules. First update the canonical schema; then keep skills/docs lightweight by pointing to the schema instead of restating exact root files, allowlists, or “do not create X under Y” prohibitions everywhere.
- Do not leave completed migration/design analyses in active orientation paths where future agents may treat stale plans as current instructions.
