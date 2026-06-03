---
name: daily-review-agent
description: Stable behavior for Darwin's daily priority review cron agent over Brayan's personal vault.
version: 1.0.0
author: Darwin
license: MIT
---

# Daily Review Agent

Use this skill when running Brayan's daily priority review.

## Required reads
Read, at minimum:
1. `~/personal_vault/_meta/schema.md`
2. `~/personal_vault/_meta/index.md`
3. `~/personal_vault/_meta/log.md`
4. `~/personal_vault/projects/dashboard.md`
5. `~/personal_vault/opportunities/dashboard.md`
6. `~/personal_vault/decisions/pending.md`
7. Inspect actual files under `~/personal_vault/inbox/`; treat `inbox/README.md` as policy only

## Recommended checks
- Inspect recent daily notes so the new note can distinguish new signals from repeated stale pressure.
- Scan for finalization handoff files before recommending closeout work:
  - `~/personal_vault/opportunities/*/closeout-input.md`
  - `/home/brayan/projects/*/PROJECT_CLOSEOUT.md`
- If project dashboard rows point to active workspaces, read the relevant `PROJECT_STATUS.md` files when they are needed to identify the real blocker/next action.

## Behavior
- Create or update a daily note under `~/personal_vault/daily/` named with today's date.
- Summarize current priorities, key inbox items, blocked decisions, and best focus for the next 24 hours.
- Prefer leverage and bottleneck removal over busywork.
- Do not go silent just because the inbox is empty; stale dashboards, expired active-looking opportunities, or unresolved blocking decisions are meaningful reportable signals.
- Treat board trust as a first-class daily-review concern: if dashboards or pending decisions carry expired active-looking gates, call out final-state / `user-status-needed` cleanup as a priority before adding new work.
- If meaningful structural changes are made, update `_meta/log.md`.

## Output
Send Brayan a concise briefing with:
- top 3 priorities
- top blockers
- one recommended next action

Keep it short enough for Telegram.
