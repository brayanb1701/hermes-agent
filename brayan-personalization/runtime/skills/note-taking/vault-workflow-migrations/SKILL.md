---
name: vault-workflow-migrations
description: Plan and execute scoped migrations of Brayan's personal-vault workflows, templates, dashboards, skills, and automation without over-migrating unrelated records.
version: 1.0.0
author: Darwin
license: MIT
---

# Vault Workflow Migrations

Use this skill when Brayan asks to rename, generalize, migrate, or audit an existing workflow in `~/personal_vault`, especially when the change touches templates, dashboards, opportunity records, Hermes skills, cron jobs, or runtime scripts.

This is a class-level migration skill. For normal vault filing/routing, use `personal-vault-ops`. For the active opportunity pipeline, use `opportunity-intake-agent`, `opportunity-preparation-agent`, and `opportunity-preparation-vault-workflow` when available.

## Core rule

Scope before editing. Brayan often wants a targeted migration, not a vault-wide rewrite. If he names exclusions or a subset, enforce that boundary exactly.

## General workflow

1. Orient with:
   - `~/personal_vault/_meta/schema.md`
   - `~/personal_vault/_meta/index.md`
   - `~/personal_vault/_meta/log.md`
   - the active workflow/template/dashboard files being changed
   - affected Hermes skills/scripts/cron files if automation changes
2. Inventory the records/files that match the requested migration scope.
3. Explicitly list exclusions before editing.
4. Apply metadata/template/file-name changes only to in-scope records.
5. Keep already-reviewable records in their current review state unless the content is actually inadequate.
6. Update dashboards and logs in the same pass when the workflow's visible queue changes.
7. Validate with deterministic checks and report uncommitted changes.

## Opportunity preparation migration pattern

Use this when converting old job/tailoring opportunity records to the broader opportunity/preparation workflow.

- Prefer the general terms `opportunity`, `preparation`, and `preparation-packet.md`.
- Use `status: preparation-ready` only for records that should be picked up by the preparation dispatcher.
- If an opportunity already has good review material, keep `status: awaiting-review` and set `automation_route: none`; do not relaunch the preparation agent just because field names changed.
- Rename `application/tailoring-packet.md` to `application/preparation-packet.md` only for records included in the migration scope.
- Replace retired frontmatter like `tailoring_packet` with `preparation_packet`.
- Preserve `workflow_mode: cv-tailoring` when the opportunity is genuinely CV-heavy; `cv-tailoring` is still a valid mode even though the overall workflow is called preparation.
- For grants or short-form opportunities with an existing `application/application-draft.md`, create a lightweight `application/preparation-packet.md` that links the draft and records the review decision instead of duplicating content.
- Do not migrate explicitly excluded records except for narrow metadata Brayan explicitly requests, such as adding `Kind` to dashboard rows.

## Dashboard migration rule

When touching `opportunities/dashboard.md`:

- Use a single `Kind` column populated from `opportunity_kind` unless Brayan asks otherwise.
- Do not add `Kind / Mode` as the main dashboard label; `workflow_mode` belongs in frontmatter/agent context.
- Preserve priority order: exact `P0`, mixed/ranged `P0/P1` or `P0-P1`, exact `P1`, mixed/ranged `P1/P2` or `P1-P2`, exact `P2`, mixed/ranged `P2/P3` or `P2-P3`, exact `P3`.
- Within the same priority bucket, preserve existing order unless deadline/urgency clearly justifies moving a row.
- Never remove existing dashboard rows unless the opportunity is explicitly archived/closed.

## References

- `references/opportunity-preparation-v2-awaiting-review-migration.md` — concrete case notes for migrating only awaiting-review opportunities to the preparation workflow while preserving review state and excluding named records.

## Validation checklist

Before reporting done:

1. Run `git diff --check` in `~/personal_vault`.
2. If Hermes runtime/personalization changed, run `git diff --check` in the Hermes personalization checkout too.
3. Compile affected Python scripts with `python3 -m py_compile`.
4. Dry-run affected scanners, e.g. `python3 ~/.hermes/scripts/opportunity_preparation_ready_scan.py --dry-run`.
5. Search in-scope folders for retired terms/fields.
6. Verify dashboard rows have valid classification cells. If a quick table validator flags the header row because it starts with `| Priority`, inspect actual data rows before treating it as a failure.
7. Report dirty git state precisely; do not assume unrelated uncommitted files are mistakes.

## Pitfalls

- Do not turn a targeted migration into a mass edit.
- Do not downgrade `awaiting-review` records to `preparation-ready` unless the existing packet/draft is actually unusable.
- Do not preserve obsolete field names for compatibility when Brayan has approved a clean rename.
- Do not blindly replace every instance of `tailoring`; some terms, such as `workflow_mode: cv-tailoring`, may remain semantically correct.
- Do not modify pinned skills directly. If the right umbrella skill is pinned, either ask Brayan to unpin it for a patch or create a broader migration skill only when it adds reusable class-level value.
