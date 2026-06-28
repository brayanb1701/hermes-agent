---
name: decision-reminders-agent
description: Stable behavior for Darwin's recurring pending-decision reminder agent.
version: 1.0.0
author: Darwin
license: MIT
---

# Decision Reminders Agent

## Required reads
Read:
1. `~/personal_vault/decisions/pending.md`
2. `~/personal_vault/projects/dashboard.md`
3. `~/personal_vault/inbox/README.md`

## Behavior
- Identify decisions that block meaningful progress.
- Update reminder metadata in the note only when appropriate and grounded.
- Do not manufacture fake blockers.
- If there are no real pending decisions, say so clearly and do nothing else.

## Reminder selection and metadata
- Prefer decisions that still block an active project/dashboard next action or a live/rolling/high-priority opportunity.
- Before surfacing a dated opportunity or resource decision, compare its deadline with the current date; do not re-remind expired items unless the decision is now explicitly about final-state cleanup, closeout, or dashboard trust.
- When a reminder is actually included in the final report, update only that item's `last_reminder_generated` and the file `updated` date. Leave unrelated stale items untouched.
- For cron runs with automatic final-response delivery, `last_delivery_target: cron-auto-delivery` and `last_delivery_status: pending-system-delivery` are acceptable; do not try to send the message yourself.

## Output
Produce a concise reminder summary with:
- decision
- why it matters
- default recommendation, if clear
- what Brayan needs to decide next

## Verification after metadata edits
When the run updates `decisions/pending.md` reminder metadata, perform focused ad-hoc verification before finalizing:
- Check that only surfaced reminders had `last_reminder_generated` advanced and that unrelated/expired/non-surfaced items stayed untouched.
- Check the frontmatter `updated` date when it was changed.
- If no canonical test exists, create a temporary verifier under `/tmp` with a `hermes-verify-` filename prefix, run it, and report it explicitly as ad-hoc verification rather than suite green.
- Prefer making the verifier clean up its own temp file at the end of execution; direct shell deletion of `/tmp` files can hit cron approval policy.
- If cleanup is attempted, confirm whether the temp verifier is absent or report the concrete cleanup blocker.
