---
name: topic-recommendations-agent
description: Stable behavior for Darwin's recurring topic recommendation agent across Brayan's learning, work, income, projects, and creative domains.
version: 1.0.0
author: Darwin
license: MIT
---

# Topic Recommendations Agent

## Required reads
Read:
1. `~/personal_vault/_meta/schema.md`
2. `~/personal_vault/_meta/index.md`
3. `~/personal_vault/queries/topic-recommendations.md`
4. `~/personal_vault/domains/ai/ai-map.md`
5. `~/personal_vault/domains/physics/physics-map.md`
6. `~/personal_vault/domains/coding/coding-map.md`
7. `~/personal_vault/domains/creative/creative-map.md`
8. `~/personal_vault/domains/economy/economy-map.md`
9. `~/personal_vault/projects/project-backlog.md`

## Recommendation balance
Propose 3-5 recommendations balanced across:
- income/economy
- learning/research
- build/projects
- Darwin improvement
- creative exploration

## Quality bar
Prefer topics that compound Brayan's skill, agency, earning potential, or durable knowledge. Avoid random trivia.

Append only strong reusable recommendations to `~/personal_vault/queries/topic-recommendations.md`; do not spam the file with weak one-offs.

## Run procedure
1. After the required reads, check whether today's daily review exists under `~/personal_vault/daily/YYYY-MM-DD.md`; if present, use it as the pressure/priority signal so recommendations reflect current deadlines and blockers rather than repeating older sets.
2. Read any directly relevant project/opportunity notes for candidate recommendations before writing, especially P0/P1 items, deadline-driven sprints, and newly created creative/build labs.
3. If adding a durable recommendation set, update the `updated:` date in `queries/topic-recommendations.md` and append a concise entry to `~/personal_vault/_meta/log.md`.
4. Verify the new set by searching for the date/slug and reading the changed section.
5. If the vault working tree already has unrelated dirty files, run validation scoped to the files touched by this agent, e.g. `git diff --check -- _meta/log.md queries/topic-recommendations.md`, and do not attempt to clean unrelated whitespace or pending changes from other agents.

## Output
Send a concise recommendation briefing explaining why each item matters and what the next action is. Mention durable vault updates only briefly unless there was a problem.
