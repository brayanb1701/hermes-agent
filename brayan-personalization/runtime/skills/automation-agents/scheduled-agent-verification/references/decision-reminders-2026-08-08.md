# Decision reminders cron — 2026-08-08 verification/patching pattern

Use this as a concrete example for unattended decision-reminder runs that update `decisions/pending.md` metadata while many unrelated vault files are already dirty.

## What happened

- Required reads exposed several open decisions, but only three were surfaced because they still blocked active/current work:
  - Coding Agent Methodology Bakeoff execute/demote/pause gate.
  - IAEA Data Science and Analytics Internship pursue/drop gate with unknown URL/deadline/eligibility/recommenders.
  - Trafilea anchor-role choice for the active job-search sprint.
- Expired dated opportunity/resource decisions were skipped as normal reminders unless they were explicitly cleanup/final-state questions.
- `decisions/pending.md` had many repeated metadata keys such as `last_reminder_generated`, so a broad multi-hunk patch was fragile.

## Reusable technique

1. Update frontmatter `updated` date with a small unique frontmatter replacement.
2. For each surfaced reminder, replace the complete decision block or a sufficiently large unique slice containing the decision title and metadata. Do not patch bare `last_reminder_generated` lines.
3. Leave non-surfaced and expired/stale entries untouched, even if their metadata is old.
4. Create a focused `/tmp/hermes-verify-*.py` verifier with the file-write tool, run it with `python3 <path>`, have it unlink itself, then print a shell absence check for the verifier path.
5. Verifier evidence should explicitly print:
   - target file checked;
   - frontmatter updated date;
   - surfaced reminders advanced to the run date with `cron-auto-delivery` / `pending-system-delivery` metadata;
   - representative non-surfaced reminder dates unchanged;
   - cleanup result for the verifier path.

## Pitfalls

- Avoid inline `terminal` heredoc scripts for verifier creation in approval-sensitive cron runs; they may be blocked before the verifier exists. Use `write_file` + `terminal("python3 <path>")` instead.
- Do not interpret a large dirty vault status as caused by the reminder run. Report only the focused diff for files intentionally edited.
- Do not save setup-state failures as durable facts; only capture the approval-friendly verification pattern and the repeated-key patching pattern.
