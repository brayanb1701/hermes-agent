# Deterministic project-review dispatch

The managed project job runs `project_review_scan.py` as `no_agent: true`.
The scanner still launches one reasoning session per selected project, but there
is no parent LLM summarizer and no completed-child PID/TTL lock layer.
The ownership wrapper's single writer lock serializes the scanner and children.

Success is persisted evidence, not the child's final answer:
- Review: a new or revised dated-today entry in the project's review section.
- Other lifecycle modes: that evidence, or a changed selection key plus a saved
  change to the project hub/dashboard/backlog/finished control surfaces.
- Nonzero child exit, missing hub, parse failure, or absent evidence is failure.
- Evidence is evaluated before deterministic keep-five history pruning.

The scanner writes the existing `[CRON_FAILURE]` marker itself on partial failure
and exits zero so the ownership wrapper can validate and publish good partial work.
The wrapper then exits nonzero. Crashes still fail closed through normal recovery.
A fixed final report line prevents arbitrary child log text being interpreted as
wake-gate JSON. Child prose is reporting material only, never success evidence.

Live direct scans require the configured ownership worktree; `--dry-run` remains
available against the canonical vault. Managed reviews treat external workspace
controls as read-only inputs. A dated hub review acknowledges workspace due dates
on or before that review; newer due dates still trigger. Review cadence uses the
newest of actual progress and dated review evidence, without relabeling a review
as implementation progress. Explicit lifecycle/blocker/audit signals remain active.
Preventive guards and the recovery journal
remain in place. A canonical dirty/HEAD-change postcheck now stops publication.
If that postcheck fails, do not erase the pending marker or sweep the dirty files:
identify and preserve the unexpected writer's changes, restore a verified canonical
base with operator approval, then reconcile the exact retained run.

Limitations: external workspace controls are not in the vault transaction. If a
child advances selection state without saving a vault review, the report warns
that automatic reselection may not occur. Persisted evidence does not establish
semantic review quality. Hung children still hit the whole-job timeout; per-child
containment/timeouts, cgroups, and journal migration are separate future decisions.
