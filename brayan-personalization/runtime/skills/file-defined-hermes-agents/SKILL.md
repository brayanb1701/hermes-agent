---
name: file-defined-hermes-agents
description: Design recurring/specialized Hermes agents whose prompts and context live in files, while scripts/hooks/cron only dispatch and provide dynamic data. Use when creating cron/hook-triggered Hermes workflows, independent session fanout, or agent-like automations.
version: 1.0.0
author: Darwin
license: MIT
metadata:
  hermes:
    tags: [hermes, agents, cron, hooks, prompts, skills, automation, sessions]
    related_skills: [hermes-agent, personal-vault-ops]
---

# File-defined Hermes agents

Use this when Brayan wants recurring/specialized Hermes agents activated by cron, hooks, scripts, webhooks, or inbox events.

Core preference: agent behavior belongs in dedicated files, not embedded inside Python dispatcher scripts. Scripts should be mostly mechanical: discover work, select items, render templates, launch sessions, record state/logs, and wake/report only on failures.

## Design principle

Separate four concerns:

1. Activation
   - Cron job, hook, webhook, or plugin event.
   - Should answer: when should this workflow run?

2. Dispatch / selection
   - Small script or hook code.
   - Should answer: what items are ready, which N should run, and how should sessions be launched?
   - Avoid large natural-language prompts inside this code.

3. Agent behavior
   - Dedicated prompt/context files and/or a Hermes skill.
   - Should answer: how should the agent perform the task?

4. Dynamic task data
   - JSON/script output and rendered template variables.
   - Should answer: what specific item is this session processing?

## Preferred file layout

For a specialized workflow, prefer something like:

```text
~/.hermes/agents/<agent-name>/
├── README.md
├── prompt-template.md       # job/session-specific prompt with placeholders
├── launcher.yaml            # optional metadata: max_sessions, skills, source tag
└── examples/                # optional sample rendered prompts / outputs

~/.hermes/skills/<agent-name>/
└── SKILL.md                 # stable behavior/procedure/context

~/.hermes/scripts/<workflow-dispatcher>.py
```

For vault-related workflows, also document the architecture in:

```text
~/personal_vault/projects/<workflow>.md
~/personal_vault/_meta/log.md
```

## Scope rule: inventory all created agents first

When Brayan asks to refactor "agents" or "all agents we created," do not narrow the scope to the most recently discussed workflow. First inventory every recurring/specialized activation surface:

1. List cron jobs (`cronjob action=list`) and inspect each job's prompt, script, skills, schedule, and delivery.
2. Search `~/.hermes/config.yaml` for platform/channel prompts, especially Telegram `channel_prompts` used as agent-like intake behavior.
3. Search `~/.hermes/plugins/` and gateway hooks for embedded natural-language instructions, pre-LLM hooks, and intake preprocessors.
4. Search `~/.hermes/scripts/` for large prompt strings, `hermes chat -q`, `--skills`, wake-gated dispatchers, and JSON-producing pre-run scripts.
5. Check existing `~/.hermes/agents/` and `~/.hermes/skills/*-agent/` so you update rather than duplicate file-defined agents.

Treat cron agents, hook/plugin agents, channel-prompt agents, and script-launched independent sessions as part of the same refactor unless Brayan explicitly excludes one. The target state is a complete registry, not a partial conversion.

## Implementation pattern

1. Put stable task instructions in a skill.
   - Example: `opportunity-preparation-agent/SKILL.md` contains how to inspect one opportunity, read mode-specific references, search project/profile evidence, draft a preparation packet, update the opportunity note, and notify Brayan.
   - Skills are native Hermes files and can be loaded via `--skills` or cron job `skills=[...]`.

2. Put per-run prompt shape in a template file.
   - Example: `~/.hermes/agents/opportunity-preparation/prompt-template.md`.
   - Use placeholders such as `{{opportunity_path}}`, `{{opportunity_kind}}`, `{{workflow_mode}}`, `{{priority}}`, and `{{application_url}}`.

3. Keep dispatcher scripts mechanical.
   - Scan source files or APIs.
   - Sort/select ready items.
   - Render template with dynamic data.
   - Launch independent sessions when isolation is desired.
   - Write state locks and logs.
   - Emit compact JSON for cron wake-gating.

4. Launch independent Hermes sessions for isolated work.

```bash
hermes --skills personal-vault-ops,<agent-skill> \
  chat -Q --source <source-tag> -q "$(rendered prompt)"
```

Use independent `hermes chat -q` sessions when Brayan wants separate session history/context per item. Do not use `delegate_task` just to get separation; `delegate_task` is useful for bounded subtasks inside a parent session, not for long-running autonomous workflow items that should each have their own session.

5. Keep parent cron prompts tiny.
   - The attached script should usually do the dispatch.
   - Parent prompt can be fallback-only: inspect script errors, notify Brayan, do not process work itself.

6. Wake-gate to avoid wasted model calls.
   - If no work or dispatch succeeded, script can emit `{"wakeAgent": false, ...}`.
   - If dispatch fails, emit `{"wakeAgent": true, "errors": [...]}` so the fallback cron agent wakes for diagnosis.

## Opportunity-preparation-specific lesson

For Brayan's opportunity-preparation workflow, the intended architecture is:

- `darwin-opportunity-preparation-agent` runs once daily.
- It scans `~/personal_vault/opportunities/<slug>/opportunity.md` for `preparation-ready` opportunities with `automation_route: opportunity-preparation`.
- It selects at most 3 highest-priority launchable opportunities.
- It launches one independent Hermes session per selected opportunity.
- The preparation agent is adaptive: it follows mode-specific references based on `workflow_mode`.
- It does not use plugin handoffs, immediate triggers, or `delegate_task` subagents.
- Agent instructions should live in files/skills/templates, not embedded in `opportunity_preparation_ready_scan.py`.

## Search-before-install rule

Before installing a plugin to solve this pattern:

1. Check built-in Hermes features first:
   - cron scripts
   - skills
   - context files (`AGENTS.md`, `.hermes.md`, `HERMES.md`)
   - profiles
   - gateway hooks
   - plugin hooks
   - `BOOT.md`

2. List installed/bundled plugins:

```bash
hermes plugins list
```

3. Inspect candidate external plugins without installing:
   - README
   - plugin.yaml
   - install script side effects
   - required dependencies
   - whether it modifies config/model defaults
   - whether it introduces services/databases

4. Report findings to Brayan before installing anything.

Important experiential finding: `UndiFineD/hermes-fleetmanager-plugin` is conceptually close to file-defined agent fleets (`.github/agents/*.agent.md`) but heavy/opinionated: PostgreSQL, config/model changes, large copied/symlinked runtime tree. Treat it as an architecture reference, not an install default.

## Verification checklist

After implementing/refactoring:

- Script compiles: `python -m py_compile ~/.hermes/scripts/<script>.py`
- Dry-run does not launch sessions.
- Dry-run output shows selected items, max count, wake gate, and error count.
- Prompt instructions are absent or minimal in script code.
- Agent behavior lives in skill/template/context files.
- Cron job still points at correct script and schedule.
- `hermes config check` passes.
- No plugin was installed or enabled without Brayan's approval.
- Docs/logs in the vault reflect the actual runtime architecture.

## Pitfalls

- Do not embed long natural-language task prompts in Python scripts if the workflow is meant to be maintained as an agent.
- Do not install third-party orchestration plugins before showing Brayan what they do.
- Do not use `delegate_task` when the explicit requirement is one independent session per item.
- Do not create immediate-trigger/plugin handoff behavior when Brayan wants low-frequency cron cadence.
- Do not overuse Hermes profiles unless the agent truly needs separate config/memory/state; profiles are powerful but heavier than skills/templates.
