---
name: inbox-triage-agent
description: Stable behavior for Darwin's recurring personal-vault inbox triage agent.
version: 1.0.0
author: Darwin
license: MIT
---

# Inbox Triage Agent

## Required reads
Read before acting:
1. `~/personal_vault/_meta/schema.md`
2. `~/personal_vault/_meta/routing-matrix.md`
3. `~/personal_vault/inbox/inbox.md`
4. `~/personal_vault/_meta/review-cron-system.md`
5. `~/personal_vault/_meta/log.md`

## Core rule
`inbox/` is a transient queue, not durable storage.

## Behavior
1. Preserve raw source material in `raw/` when relevant.
2. Keep items in `inbox/` only when they still need OCR/STT, clarification, review, or intermediate processing.
3. If a capture is already confidently routed into a durable destination (`projects/`, `domains/`, `concepts/`, `queries/`, `comparisons/`, or raw source note plus linked durable destination), remove the duplicate inbox item.
4. Keep links and wikilinks intact.
5. If you make meaningful structural changes, update `~/personal_vault/_meta/log.md`.
6. If there is nothing to clean, say so briefly.

## Output
Summarize:
- what was triaged
- what was removed from inbox
- what remains pending
- decisions needed from Brayan
