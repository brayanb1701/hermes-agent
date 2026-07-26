# Decision Reminder Cron Run — 2026-07-25 Lessons

This reference captures a reusable pattern from a decision-reminders cron run. It is not a transcript; use it as a checklist for similar scheduled agents.

## Situation

The run loaded `personal-vault-ops` and `decision-reminders-agent`, read the vault orientation files plus `decisions/pending.md`, `projects/dashboard.md`, and `inbox/README.md`, and compared pending decisions against active project blockers.

Two surfaced reminders were grounded:

1. A new project-dashboard gate: `coding-agent-methodology-bakeoff` had become an explicit execute/demote/pause decision after repeated setup-only rollovers.
2. An existing P0/P1 opportunity gate: IAEA Data Science and Analytics still had unknown deadline/eligibility/recommender facts.

## Reusable takeaways

- The decision register is primary, but dashboards can reveal new Brayan-only decision gates not yet registered. If a dashboard row says “decision needed” and names the alternatives, add a concise pending-decision item before surfacing it.
- When adding a new pending-decision item, also update only the surfaced item metadata and frontmatter date; leave unrelated stale items untouched.
- Verification should account for both newly added decision items and existing reminder metadata updates.
- If the vault file has pre-existing dirty state, report/handle the exact scoped changes made by this run rather than trying to normalize the whole file.

## Verification pattern that worked

A written `/tmp/hermes-verify-*.py` verifier was created with the file-write tool, then run with the terminal tool. The verifier printed explicit evidence lines for:

- target file path
- frontmatter updated date
- surfaced reminder dates and delivery metadata
- unchanged non-surfaced reminder dates
- count/list of all items updated to the current run date
- self-removal and final absence of the verifier file

Avoid inline shell heredoc verifier creation in approval-sensitive cron contexts when a file-write + terminal-run sequence is available.
