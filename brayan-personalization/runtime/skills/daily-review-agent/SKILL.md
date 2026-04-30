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
4. `~/personal_vault/_meta/dashboards/project-dashboard.md`
5. `~/personal_vault/decisions/pending.md`
6. Inspect actual files under `~/personal_vault/inbox/`; treat `inbox/README.md` as policy only

## Behavior
- Create or update a daily note under `~/personal_vault/daily/` named with today's date.
- Summarize current priorities, key inbox items, blocked decisions, and best focus for the next 24 hours.
- Prefer leverage and bottleneck removal over busywork.
- If meaningful structural changes are made, update `_meta/log.md`.

## Output
Send Brayan a concise briefing with:
- top 3 priorities
- top blockers
- one recommended next action

Keep it short enough for Telegram.
