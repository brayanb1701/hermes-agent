---
name: topic-recommendations-agent
description: Stable behavior for Darwin's recurring topic recommendation agent across Brayan's learning, work, income, projects, and creative domains.
version: 1.0.0
author: Darwin
license: MIT
---

# Topic Recommendations Agent

## Required reads
If this is running from the scheduled topic-recommendations agent, first read `~/.hermes/agents/topic-recommendations/prompt-template.md` when present or explicitly requested by the cron prompt; it may carry delivery/silence instructions that should override generic output wording.

Read:
1. `~/personal_vault/_meta/schema.md`
2. `~/personal_vault/_meta/index.md`
3. `~/personal_vault/queries/topic-recommendations.md`
4. `~/personal_vault/domains/ai/ai-map.md`
5. `~/personal_vault/domains/physics/physics-map.md`
6. `~/personal_vault/domains/coding/coding-map.md`
7. `~/personal_vault/domains/creative/creative-map.md`
8. `~/personal_vault/domains/economy/economy-map.md`
9. `~/personal_vault/projects/dashboard.md`

## Recommendation balance
Propose 3-5 recommendations balanced across:
- income/economy
- learning/research
- build/projects
- Darwin improvement
- creative exploration

When the daily review identifies a board/reset problem, stale deadlines, passed gates, or active-dashboard drift, treat cleanup/final-state classification as a legitimate high-leverage build/project recommendation. Protecting the priority system can matter more than opening new research topics.

When repeated daily/recommendation runs keep surfacing the same stale gates, check whether the daily review reports missing final-state handoff files such as opportunity `closeout-input.md`, workspace `PROJECT_CLOSEOUT.md`, or `PROJECT_REOPEN.md`. If they are missing, recommend creating explicit handoff/final-state inputs or `user-status-needed` markers before recommending broad review again; do not silently propagate unconfirmed outcomes into finished registers.

When a time-boxed resource window has passed (for example expired compute credits), do not keep recommending launch/run-card execution as if the window were still open. Pivot the recommendation to final-state classification (spent/skipped/unknown), cognitive-leak cleanup in the decision register/dashboard, and the nearest replacement leverage path if one exists (such as a still-live compute grant or proof-bundle opportunity).

When a prior recommendation’s setup artifact has been completed since the last durable set, explicitly pivot to the next evidence-producing action instead of repeating the old setup recommendation. Examples: if a project spec was previously blank and is now locked/synced, recommend launching the first run and logging verified results; if a packet was previously missing and is now drafted, recommend review/submission/final-state evidence; if a blocker became Brayan-only, name the smallest artifact Darwin can still produce without inventing user decisions.

## Quality bar
Prefer topics that compound Brayan's skill, agency, earning potential, or durable knowledge. Avoid random trivia.

Append only strong reusable recommendations to `~/personal_vault/queries/topic-recommendations.md`; do not spam the file with weak one-offs. If today's daily review materially changes pressure/ordering, it is valid to append a new set even when some themes repeat from yesterday; make the delta explicit instead of producing novelty for its own sake. A tightening countdown, newly confirmed stale-dashboard drift, or a shift from broad prioritization into a concrete near-deadline action window counts as a material delta — recommend sharper next artifacts rather than inventing unrelated novelty.

## Run procedure
1. After the required reads, check whether today's daily review exists under `~/personal_vault/daily/YYYY-MM-DD.md`; if present, use it as the pressure/priority signal so recommendations reflect current deadlines and blockers rather than repeating older sets.
   - If today's daily review does not exist, do not stall or invent it. Use the latest available daily review plus current dashboards/registers/workspace status files as the pressure signal, and explicitly mention that fallback in the recommendation delta if writing a durable set.
   - When a previously urgent opportunity/resource deadline has passed since the latest daily review, pivot from countdown/submit language to final-state classification (`submitted`, `skipped/no-submission`, `unknown`, or `user-status-needed`) unless there is explicit evidence of manual submission.
2. Read any directly relevant project/opportunity notes for candidate recommendations before writing, especially P0/P1 items, deadline-driven sprints, and newly created creative/build labs.
3. If adding a durable recommendation set, update the `updated:` date in `queries/topic-recommendations.md` and append a concise entry to `~/personal_vault/_meta/log.md`.
4. Verify the new set by searching for the date/slug and reading the changed section.
5. If the vault working tree already has unrelated dirty files, run validation scoped to the files touched by this agent, e.g. `git diff --check -- _meta/log.md queries/topic-recommendations.md`, and do not attempt to clean unrelated whitespace or pending changes from other agents.
6. When the target files are already dirty from previous agents or same-day runs, inspect `git diff -- queries/topic-recommendations.md _meta/log.md` before patching. Preserve existing uncommitted entries, append only the new dated set/log entry, and verify the exact inserted section by searching/reading it. In the final briefing, mention only this run's durable update, not the whole pre-existing diff.

## Output
Produce a concise recommendation briefing explaining why each item matters and what the next action is. Mention durable vault updates only briefly unless there was a problem.

For scheduled cron runs, do **not** call messaging/send tools unless the prompt explicitly asks for manual delivery; the scheduler delivers the final response automatically. If the cron prompt includes a silence contract, follow it exactly (for example, return exactly `[SILENT]` and nothing else when there is genuinely nothing new to report).
