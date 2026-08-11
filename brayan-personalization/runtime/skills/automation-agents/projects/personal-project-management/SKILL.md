---
name: personal-project-management
description: Umbrella behavior for registering, activating, reviewing, pausing, closing, reopening, and auditing Brayan's personal projects across the vault and /home/brayan/projects workspaces.
version: 1.0.0
author: Darwin
license: MIT
---

# Personal Project Management

Use this skill whenever Darwin registers, activates, reviews, pauses, reopens, closes, audits, or repairs Brayan's personal projects across `~/personal_vault/projects/` and `/home/brayan/projects/`.

This is the single umbrella project-management skill. Do not create separate `project-intake-agent`, `project-activation-agent`, `project-review-agent`, or `project-closing-agent` skills unless Brayan later explicitly changes the architecture.

## Core model

Projects have two layers:

- Vault control layer: `~/personal_vault/projects/<slug>/README.md`, `projects/dashboard.md`, `projects/backlog.md`, `projects/finished.md`, and final `projects/<slug>/closeout.md` records.
- External workspace layer: `/home/brayan/projects/<slug>/` for active project execution, code, experiments, artifacts, and workspace handoff/control files.

Canonical project statuses are exactly:

- `seed`
- `active`
- `paused`
- `complete`
- `archived`

`incubating` is retired. Use `seed` plus activation requirements.

## Mandatory surfaces

- `projects/dashboard.md` — active projects only.
- `projects/backlog.md` — seed and paused projects only.
- `projects/finished.md` — complete and archived projects only.
- Active workspace required files: `PROJECT_STATUS.md` and `PROJECT_CHANGELOG.md`.
- Optional/requested workspace handoffs: `PROJECT_CLOSEOUT.md` and `PROJECT_REOPEN.md`.

## Required orientation

For any project-management session:

1. Read `~/personal_vault/_meta/schema.md`.
2. Read the assigned project README before touching any other project file.
3. Load the relevant internal reference below with `skill_view(name="personal-project-management", file_path="references/<file>.md")`.
4. If the project is active or workspace-related, inspect `PROJECT_STATUS.md` and `PROJECT_CHANGELOG.md` after the vault README.
5. Keep every state transition synchronized across README, dashboard/backlog/finished, workspace control files, and final closeout/decision surfaces.

## Internal references

Load the relevant reference for the current mode:

- Registration: `references/project-registration.md`
- Activation: `references/project-activation.md`
- Review: `references/project-review.md`
- Pausing/reopening: `references/project-pausing-and-reopening.md`
- Closing: `references/project-closing.md`
- Workspace control files: `references/project-workspace-control-files.md`
- Audit/drift contract: `references/project-state-audit-contract.md`

The vault workflow docs mirror these procedures for readability and auditability. If a skill reference and a vault workflow disagree, pause and report drift instead of silently choosing one.

## One-project-at-a-time rule

Independent automation sessions process exactly one project-management item. Do not scan, update, or close other projects unless the prompt explicitly asks for an audit/normalization pass.

## State transition contract

Seed registration:

```text
project README + projects/backlog.md
```

Activation:

```text
project README + /home/brayan/projects/<slug>/PROJECT_STATUS.md + /home/brayan/projects/<slug>/PROJECT_CHANGELOG.md + projects/dashboard.md + remove backlog row
```

Pause:

```text
project README + PROJECT_STATUS.md + PROJECT_CHANGELOG.md + projects/backlog.md + remove dashboard row
```

Close/archive/complete:

```text
PROJECT_CLOSEOUT.md + project README + projects/<slug>/closeout.md + projects/finished.md + remove dashboard/backlog row + decisions cleanup + _meta/log.md
```

Reopen/resume:

```text
PROJECT_REOPEN.md + project README + PROJECT_STATUS.md + PROJECT_CHANGELOG.md + projects/dashboard.md or new project slug + link previous closeout
```

## Boundaries

- Do not create external paid resources without explicit approval.
- Do not submit applications, PRs, publications, forms, or public posts.
- Do not archive active P0/P1 projects only because they are stale.
- Do not infer pause or closeout without explicit evidence.
- Do not process more than the assigned project in independent sessions.
- Do not put code repos or bulky artifacts inside the vault.
- Do not create a workspace for `seed` projects.
- Active non-coding projects can still need an external workspace when they produce living artifacts such as spreadsheets, CSV mirrors, exports, scripts, or generated reports. Keep those artifacts under `/home/brayan/projects/<slug>/` and link them from the vault project README rather than storing bulky/editable operational files directly in the vault.
- Preserve Web Friction Interrupter as `area: personal` unless Brayan explicitly changes it.

## Deterministic helpers

Prefer scripts over hand-writing repetitive boilerplate:

```bash
python3 ~/.hermes/scripts/project_scaffold.py --project /home/brayan/personal_vault/projects/<slug>/README.md --seed
python3 ~/.hermes/scripts/project_scaffold.py --project /home/brayan/personal_vault/projects/<slug>/README.md --activate
python3 ~/.hermes/scripts/project_scaffold.py --project /home/brayan/personal_vault/projects/<slug>/README.md --closeout
python3 ~/.hermes/scripts/project_scaffold.py --project /home/brayan/personal_vault/projects/<slug>/README.md --reopen
python3 ~/.hermes/scripts/project_scaffold.py --all-active --dry-run
- `python3 ~/.hermes/scripts/project_review_scan.py --dry-run`
- `python3 ~/.hermes/scripts/project_review_history_retention.py --project /home/brayan/personal_vault/projects/<slug>/README.md --keep 5`
- `python3 ~/.hermes/scripts/project_state_audit.py --dry-run`
```

## Verification checklist

Before finishing a project-management change:

- Project README status and required fields match the intended lifecycle state.
- Dashboard/backlog/finished membership matches status exactly.
- Active projects have workspace, `PROJECT_STATUS.md`, and `PROJECT_CHANGELOG.md`.
- `PROJECT_CLOSEOUT.md`/`PROJECT_REOPEN.md` was preserved and marked complete/paused when processed.
- `python3 ~/.hermes/scripts/project_review_history_retention.py --project /home/brayan/personal_vault/projects/<slug>/README.md --keep 5` leaves no more than five dated review-history entries in the project hub.
- `python3 ~/.hermes/scripts/project_state_audit.py --dry-run` does not show newly introduced drift for the touched project.
- `git diff --check` passes in `~/personal_vault` when vault files changed.
