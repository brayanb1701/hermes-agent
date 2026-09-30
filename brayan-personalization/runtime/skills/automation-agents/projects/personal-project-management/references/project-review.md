# Project review

Canonical vault workflow: `~/personal_vault/_meta/workflows/projects/project-review-workflow.md`.

## Triggers

- Active review cadence due, measured from the later of actual progress and the newest dated hub review. A future explicit hub `next_review` may postpone cadence, not other signals.
- Workspace `next_review` due and later than the newest dated hub review; dates already covered by a saved review are acknowledged. A newer due workspace signal still triggers even when the hub's next review is later.
- Missing workspace/control files.
- Changelog/status indicates blocker, pause, resume, closeout, or reopen.
- Pending `PROJECT_CLOSEOUT.md` or `PROJECT_REOPEN.md`.
- Dashboard/backlog/finished/readme drift.

## Procedure

Read in order: project README, `PROJECT_STATUS.md`, `PROJECT_CHANGELOG.md`, then signal files/linked decisions/opportunities as needed.

Choose one outcome: continue active, update next action, pause, request decision, create closeout handoff, close/archive, resume/reopen, split project, or produce audit-fix proposal.

Do not auto-close or auto-pause solely because a project is stale.

For every review, save a new or revised dated-today entry under `## Review notes`, `## Cadence review notes`, or `## Review log` in the project hub. Update `updated` and register fields only as supported by the saved review. Do not advance `last_meaningful_update` or workspace progress dates merely because a review occurred; change progress metadata only when real execution evidence supports it. Preserve the real blocker and decision gate without fabricating progress.

In managed cron review mode, `PROJECT_STATUS.md`, `PROJECT_CHANGELOG.md`, and external signal files are read-only execution-side inputs. Do not rewrite workspace dates or mark an external signal paused merely to clear the scanner trigger. The dated hub review acknowledges older workspace due dates; newer due dates and explicit lifecycle/blocker/audit signals remain actionable. Any real workspace repair or lifecycle transition requires an explicitly authorized workspace-writing context, not a write outside the managed vault root.

The managed scanner evaluates persisted review evidence before automatically retaining the five newest dated hub entries. Managed child sessions do not run retention themselves. In a manual authorized review outside the dispatcher, run `project_review_history_retention.py --project <README-path> --keep 5` after saving the review. Promote durable decisions, outcomes, and evidence into canonical fields/sections before old rollover notes age out.

The project job runs as a deterministic `no_agent` scanner plus one reasoning session per selected project, not an LLM reporter. Child prose and zero exit alone are not proof of a saved review. The scanner emits `[CRON_FAILURE]` on failed persistence checks; the ownership wrapper publishes validated good partial work, then reports failure. Live scanner execution requires the configured ownership worktree; use `--dry-run` for inspection.

Verification note: `project_state_audit.py --dry-run` still writes/updates a same-day `_meta/audits/*project-state-audit.md` report, but the script now automatically keeps only the five newest reports in that series. Do not manually delete the same-day report or unrelated/manual audit files.
