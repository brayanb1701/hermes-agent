---
name: file-defined-hermes-agents
description: Design recurring/specialized Hermes agents whose prompts and context live in files, while scripts/hooks/cron only dispatch and provide dynamic data. Use when creating or refactoring cron, hook, webhook, channel-prompt, or script-launched Hermes automations.
version: 1.1.0
author: Darwin
license: MIT
metadata:
  hermes:
    tags: [hermes, agents, cron, hooks, prompts, skills, automation, sessions]
    related_skills: [hermes-agent, personal-vault-ops, hermes-agent-skill-authoring]
---

# File-defined Hermes agents

Use this when Brayan wants to create, maintain, audit, or refactor recurring/specialized Hermes automations activated by cron, hooks, scripts, webhooks, channel prompts, or inbox events.

Core preference: agent behavior belongs in dedicated files, not embedded inside Python dispatcher scripts. Scripts should be mostly mechanical: discover work, select items, render templates, launch sessions, record state/logs, and wake/report only on failures.

This is a procedural design skill, not an umbrella for operational runbooks. For the detailed behavior of a live automation, load that automation's canonical skill by bare name.

## References

- `references/brayan-current-agent-organization.md` — current live organization of Brayan's recurring/specialized Hermes agents, skills, prompt templates, scripts, and cron skill bindings, including retired automation/design skills that should not be recreated.
- `references/opportunity-preparation-agent-pattern.md` — concrete example of the independent-session fanout pattern for the opportunity-preparation workflow.
- `references/opportunity-closeout-agent-pattern.md` — design pattern for file-driven opportunity closeout: deterministic input scaffolds, independent closeout sessions, preserved evidence, and dashboard/finished-register updates.

When reviewing the skill library after an automation-refactor session, patch this skill or its references if the session changed agent organization, uncovered an overlap, or revealed a retirement/verification pitfall.

After editing this skill or its references in Brayan's live runtime, sync the personalization bundle from `/home/brayan/.hermes/hermes-agent` and run `git diff --check` so the change survives reinstall/update workflows.

## Design principle

Separate four concerns:

1. Activation
   - Cron job, hook, webhook, plugin event, channel prompt, or script trigger.
   - Should answer: when should this workflow run?

2. Dispatch / selection
   - Small script or hook code.
   - Should answer: what items are ready, which N should run, and how should sessions be launched?
   - Avoid large natural-language prompts inside this code.

3. Agent behavior
   - Dedicated prompt/context files and/or a Hermes skill.
   - Should answer: how should the agent perform the task?

4. Dynamic task data
   - JSON/script output, selected file paths, item metadata, or rendered template variables.
   - Should answer: what specific item is this session processing?

## Preferred file layout

For a specialized workflow, prefer this shape:

```text
~/.hermes/agents/<agent-name>/
├── README.md                  # optional overview / operator notes
├── prompt-template.md         # per-run prompt with placeholders
├── launcher.yaml              # optional metadata: max_sessions, skills, source tag
└── examples/                  # optional sample rendered prompts / outputs

~/.hermes/skills/<category>/<agent-skill>/SKILL.md
~/.hermes/scripts/<workflow-dispatcher>.py
```

For vault-related workflows, also document meaningful architecture in the vault, usually under `~/personal-vault/_meta/workflows/...`, `~/personal-vault/projects/...`, or `~/personal-vault/_meta/log.md` depending on the workflow.

## Scope rule: inventory all created agents first

When Brayan asks to refactor "agents" or "all agents we created," do not narrow the scope to the most recently discussed workflow. First inventory every recurring/specialized activation surface:

1. List cron jobs (`cronjob action=list`) and inspect each job's prompt, script, skills, schedule, delivery, and enabled state.
2. Search `~/.hermes/config.yaml` for platform/channel prompts, especially `channel_prompts` used as agent-like intake behavior.
3. Search `~/.hermes/plugins/` and gateway hooks for embedded natural-language instructions, pre-LLM hooks, and intake preprocessors.
4. Search `~/.hermes/scripts/` for large prompt strings, `hermes chat -q`, `--skills`, wake gates, and JSON-producing pre-run scripts.
5. Check `~/.hermes/agents/` for prompt templates and launcher metadata.
6. Check canonical skills under `~/.hermes/skills/`, especially `automation-agents/` and workflow-specific categories such as `opportunities/`.

Treat cron agents, hook/plugin agents, channel-prompt agents, and script-launched independent sessions as part of the same automation ecosystem unless Brayan explicitly excludes one. The target state is a complete registry, not a partial conversion.

## Implementation pattern

When a new recurring/specialized workflow is being designed, explicitly account for every file-defined-agent surface before calling the design complete:

- stable behavior skill under `~/.hermes/skills/.../<agent-skill>/SKILL.md`;
- if the workflow has multiple modes/processes but Brayan wants one umbrella skill, add internal support files under that skill's `references/` directory for each process instead of creating a flat list of narrow skills;
- prompt template under `~/.hermes/agents/<agent-name>/prompt-template.md`;
- mechanical dispatcher/scanner script under `~/.hermes/scripts/`;
- cron job or activation surface, with skills/script/delivery/toolsets verified;
- deterministic helper scripts for repetitive scaffolding tasks that should not depend on the LLM hand-writing boilerplate;
- vault workflow/template/register docs when the workflow mutates Brayan's personal vault.

If Brayan says an implementation plan is missing “the agent with its associated skill,” treat that as a design gap: add the skill, prompt-template, scanner/dispatcher, cron binding, and verification steps to the plan, not just more prose in the vault docs.

1. Put stable task instructions in a skill.
   - Example: `opportunity-preparation-agent` contains how to inspect one opportunity, read mode-specific references, search project/profile evidence, draft a preparation packet, update the opportunity note, and notify Brayan.
   - Skills are native Hermes files and can be loaded via `--skills` or cron job `skills=[...]`.

2. Put per-run prompt shape in a template file.
   - Example: `~/.hermes/agents/opportunity-preparation/prompt-template.md`.
   - Use placeholders such as `{{opportunity_path}}`, `{{workflow_mode}}`, `{{priority}}`, and `{{application_url}}`.

3. Keep dispatcher scripts mechanical.
   - Scan source files or APIs.
   - Sort/select ready items.
   - Render templates with dynamic data.
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
   - The attached script should usually do deterministic collection/dispatch.
   - Parent prompt can be fallback-only: inspect script output, diagnose errors, repair only inside the workflow boundary, and report concise status.

6. Wake-gate to avoid wasted model calls.
   - For normal Hermes cron jobs with `script` and `no_agent=false`, the scheduler runs the script before building the LLM prompt. If stdout JSON contains `{"wakeAgent": false}` or `{"ready_count": 0}`, the agent is skipped entirely; if stdout is non-empty and wake is allowed, it is injected as `## Script Output` context.
   - If no work exists or dispatch succeeded cleanly, script can emit `{"wakeAgent": false, ...}`.
   - If dispatch fails, emit `{"wakeAgent": true, "errors": [...]}` so the fallback cron agent wakes for diagnosis.
   - Reserve `no_agent=true` for pure watchdog/reporting scripts where the script output itself is the final delivery; use `no_agent=false` when the script is only a gate/context collector for a real agent.

## Retiring overlapping automation guidance

When two automation/design skills overlap, prefer one class-level procedural skill plus references over parallel umbrella skills. Before deleting or absorbing a skill:

1. Inventory activation surfaces first: cron jobs, config/channel prompts, scripts, agents, plugins, and skill references.
2. Move durable reusable procedure into the class-level `SKILL.md`.
3. Move Brayan-specific runtime inventory or concrete workflow examples into `references/` only when they are likely to be useful again.
4. If the retired skill is fully redundant and the durable process is already documented elsewhere, remove it cleanly instead of preserving a tombstone/"retired skill" entry. Brayan prefers not to keep retirement notes that add no operational value.
5. Delete the redundant skill only after active activation surfaces no longer reference it.
6. Verify both absence and resolution:
   - `skill_view("<deleted-skill>")` should fail.
   - canonical replacement skills should still load by bare name.
   - `skills_list(category="<old-category>")` should not show an accidental empty/stale category.
   - searches over live skills and synced personalization bundle should not show stale references.
6. If `skill_manage(action="delete")` says the skill is not found but stale metadata remains, inspect and clean `~/.hermes/skills/.usage.json` carefully, then sync the personalization bundle.

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

- Script compiles: `python -m py_compile ~/.hermes/scripts/<script>.py`.
- Dry-run does not launch sessions unless explicitly requested.
- Dry-run output shows selected items, max count, wake gate, and error count.
- For deterministic scaffold/template helpers, inspect at least one generated artifact after applying, not just dry-run JSON. Verify the rendered file has the intended real frontmatter/body shape and not a fenced template block or the template note's own metadata.
- Prompt instructions are absent or minimal in script code.
- Agent behavior lives in skill/template/context files.
- Cron job points at the intended script, schedule, skills, delivery, enabled toolsets, and enabled state.
- When using the `cronjob` update tool, preserve explicit delivery (`deliver`) and toolsets in the update call; otherwise defaults may silently change user-visible delivery behavior.
- Trigger the cron once only when safe, then inspect the latest `~/.hermes/cron/output/<job_id>/...` file to verify whether the wake gate skipped the LLM or woke the agent.
- Bare skill names resolve with `skill_view(<name>)` after any category move.
- `hermes config check` passes when Hermes runtime/config changed.
- No plugin was installed or enabled without Brayan's approval.
- Docs/logs in the vault reflect meaningful runtime architecture changes.

## Pitfalls

- Do not embed long natural-language task prompts in Python scripts if the workflow is meant to be maintained as an agent.
- Do not maintain duplicate runbooks in multiple skills; use canonical operational skills and references.
- Do not satisfy an umbrella-skill requirement by only adding vault workflow docs. The runtime skill should have a rich `SKILL.md` and, when there are multiple process modes, a `references/` directory that future agents can load through `skill_view` without rereading unrelated vault analysis files.
- Do not leave stale `.usage.json` metadata for a retired skill; it can keep deleted skills looking active to curator/status tooling.
- Do not install third-party orchestration plugins before showing Brayan what they do.
- Do not use `delegate_task` when the explicit requirement is one independent session per item.
- Do not create immediate-trigger/plugin handoff behavior when Brayan wants low-frequency cron cadence.
- When converting an interval cron to fixed daily times, use a standard cron expression such as `0 10,18 * * *` rather than another interval schedule, and scan active runtime/bundle/vault docs for stale old cadence strings while excluding historical cron output/session logs.
- Do not omit `deliver` when updating an existing cron job through tools; verify delivery after update because a partial update can reset it to `local`.
- If a wake gate reports an empty queue, verify both the script output (`wakeAgent=false` / `ready_count=0`) and the resulting cron output doc that says the agent was skipped; this proves no model call was spent.
- Do not overuse Hermes profiles unless the agent truly needs separate config/memory/state; profiles are powerful but heavier than skills/templates.
