---
name: darwin-personal-automation
description: "Umbrella workflow for Brayan/Darwin recurring Hermes automations: file-defined agents, cron wake-gated agents, vault review loops, job-tailoring fanout, topic recommendations, and exception handlers."
version: 1.0.0
author: Darwin
license: MIT
metadata:
  hermes:
    tags: [darwin, hermes, automation, cron, agents, vault, wake-gating, recurring-workflows]
    related_skills: [personal-vault-ops, hermes-agent]
---

# Darwin Personal Automation

Use this skill when creating, maintaining, auditing, or troubleshooting Brayan/Darwin recurring Hermes automations: cron jobs, file-defined agents, wake-gated scripts, independent-session fanout, review agents, intake agents, reminders, topic recommendations, and exception handlers.

This is the class-level umbrella for the former one-agent-one-skill runbooks. Session-specific details live in `references/`.

## Core architecture

Keep four concerns separate:

1. **Activation** — cron, webhook, gateway/channel hook, plugin hook, or script trigger.
2. **Dispatch/selection** — small mechanical code that discovers ready work, sorts/selects, renders prompts, records locks/logs, and emits wake-gated JSON.
3. **Agent behavior** — a stable skill, prompt template, or context file that describes how the agent behaves.
4. **Dynamic task data** — script JSON, selected file paths, item metadata, or rendered template variables.

Avoid embedding long natural-language prompts in Python dispatchers. Prefer `~/.hermes/agents/<agent-name>/prompt-template.md`, class-level skills, and small scripts.

## Inventory before refactoring agents

When asked to refactor, audit, or consolidate “agents,” inventory all activation surfaces before editing:

- `cronjob(action="list")` for schedules, scripts, skills, delivery, enabled state, and last output.
- `~/.hermes/config.yaml` for channel prompts such as Anything Inbox.
- `~/.hermes/plugins/` and gateway hooks for pre-LLM hooks or embedded prompts.
- `~/.hermes/scripts/` for `hermes chat -q`, `--skills`, wake gates, large prompt strings, and dispatchers.
- `~/.hermes/agents/` for prompt templates and launcher metadata.
- `~/.hermes/skills/*-agent/` and archived references for legacy runbooks.

Treat cron agents, plugin/channel prompt agents, script-launched independent sessions, and hook-triggered sessions as one automation ecosystem unless explicitly scoped smaller.

## File-defined agent pattern

Preferred layout:

```text
~/.hermes/agents/<agent-name>/
├── README.md
├── prompt-template.md
├── launcher.yaml              # optional metadata
└── examples/

~/.hermes/skills/<umbrella-or-agent-class>/SKILL.md
~/.hermes/scripts/<workflow-dispatcher>.py
```

For vault workflows, also document architecture in `~/personal_vault/_meta/workflows/...` or `~/personal_vault/projects/...` and append meaningful structural changes to `~/personal_vault/_meta/log.md`.

## Wake-gated cron pattern

A cron script should normally do deterministic collection/dispatch first and emit compact JSON:

- `wakeAgent: false` when no LLM judgment is needed or dispatch succeeded cleanly.
- `wakeAgent: true` with a compact `errors`/`failure_stage` payload when repair or diagnosis is needed.

The fallback LLM prompt should be small: inspect script output, diagnose errors, repair only within the workflow boundary, and report concise status.

## Independent-session fanout

Use independent `hermes chat -q` sessions when each item needs its own session history/context or may run longer than a parent turn.

```bash
hermes --skills personal-vault-ops,<workflow-skill> \
  chat -Q --source <source-tag> -q "$(rendered prompt)"
```

Do not use `delegate_task` merely to obtain separation for long-running autonomous item processing. `delegate_task` is bounded by the parent turn and is best for short subtasks.

## Vault recurring agents

For vault-related recurring agents, orient through `personal-vault-ops` and then the workflow-specific reference.

### Daily review
Read vault schema/index/log, project dashboard, pending decisions, and actual `inbox/` files. Create/update `daily/YYYY-MM-DD.md`. Output top priorities, blockers, and one next action.

### Decision reminders
Read `decisions/pending.md`, project dashboard, and inbox policy. Surface real blocking decisions only; do not manufacture blockers. Output decision, why it matters, default recommendation if clear, and what Brayan needs to decide.

### Inbox triage
Treat `inbox/` as transient. Preserve substantial raw source material first, route durable content out of inbox, remove duplicate inbox items only after confident preservation/routing, and report what remains pending.

### Notes intake
Anything Inbox is a capture surface. Preserve raw input, use preprocessor/OCR/STT/URL context, search for existing related notes, route to the right vault layer, link hubs, and keep output concise. Job/opportunity captures route through the opportunity workflow.

### Topic recommendations
Read current vault priorities and domain hubs, then propose 3–5 recommendations balanced across income, learning/research, build/projects, Darwin improvement, and creative exploration. Append only strong durable recommendations.

### Vault structure auditor
Start report-only. Run/read the deterministic audit script, then perform a semantic pass. Propose exact patch groups and validation commands. Do not autonomously delete raw material, move large groups, archive active items, change priorities, or rewrite application materials without approval.

## Opportunity and job automation

Opportunity/job workflows are vault workflows and may also be automation workflows.

- Intake turns links/listings/programs/challenges/grants into structured `opportunities/<slug>/opportunity.md` records.
- Tailoring-ready means a specific target has enough details for a packet; it is the only launchable intake status for the tailoring dispatcher.
- Tailoring fanout is intentionally daily and low-frequency: a scanner selects at most three highest-priority ready jobs and launches one independent session per job.
- Tailoring sessions create `opportunities/<slug>/application/tailoring-packet.md`, update the source record to `awaiting-review`, and notify Brayan. They must not submit applications.

See `personal-vault-ops` for current vault taxonomy and `references/job-application-vault-workflow.md`, `references/job-opportunity-intake-agent.md`, and `references/job-tailoring-agent.md` for detailed legacy runbooks.

## Hermes upstream rebase CI exception handler

For the daily Hermes personalization rebase CI, wake only on script-reported exceptions. Diagnose the failure stage first, preserve Brayan's customization branch, prefer extension points over base-code changes, resolve conflicts/tests, verify, and push only `HEAD:brayan/personal-hermes-customizations` with `--force-with-lease`. Never push personalization to `origin/main`.

See `references/hermes-upstream-rebase-ci-agent.md` for exact repo paths and verification commands.

## Verification checklist

After creating or changing an automation:

- Script compiles with `python -m py_compile`.
- Dry-run does not launch sessions and shows selected count, max count, wake gate, and errors.
- Long prompts are absent/minimal in script code.
- Agent behavior lives in skill/template/context files.
- Cron job points at the intended script, schedule, skills, and delivery.
- Logs/state paths are documented.
- `hermes config check` passes when Hermes runtime/config changed.
- Vault docs/logs reflect meaningful runtime architecture changes.

## Pitfalls

- Do not install third-party orchestration plugins before inspecting and explaining side effects.
- Do not use immediate plugin handoffs when the designed cadence is low-frequency cron.
- Do not bury one-session bug lore as top-level skills; demote it into references under this umbrella.
- Do not treat usage counters as evidence of value or lack of value; judge content/class overlap.
