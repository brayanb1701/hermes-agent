# Project review

Canonical vault workflow: `~/personal_vault/_meta/workflows/projects/project-review-workflow.md`.

## Triggers

- Active review cadence due.
- Workspace `next_review` due.
- Missing workspace/control files.
- Changelog/status indicates blocker, pause, resume, closeout, or reopen.
- Pending `PROJECT_CLOSEOUT.md` or `PROJECT_REOPEN.md`.
- Dashboard/backlog/finished/readme drift.

## Procedure

Read in order: project README, `PROJECT_STATUS.md`, `PROJECT_CHANGELOG.md`, then signal files/linked decisions/opportunities as needed.

Choose one outcome: continue active, update next action, pause, request decision, create closeout handoff, close/archive, resume/reopen, split project, or produce audit-fix proposal.

Do not auto-close or auto-pause solely because a project is stale.

When continuing an active project after a cadence review, advance the review state coherently enough that `project_review_scan.py` will not relaunch the same stale item immediately: update the project README `last_meaningful_update`/`updated`, dashboard last-update row, workspace `PROJECT_STATUS.md`, and `PROJECT_CHANGELOG.md` `last_meaningful_update`/`next_review` unless there is a stronger reason to leave the project explicitly blocked for immediate user attention. Preserve the real blocker in notes; do not fabricate progress.

Verification pitfall: `project_state_audit.py --dry-run` can still write a same-day `_meta/audits/*project-state-audit.md` report. For ad-hoc single-project reviews, remove that generated report after recording the audit output unless the task explicitly asks to preserve an audit artifact.
