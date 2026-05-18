# Opportunity/project lifecycle state diagnosis

Use when auditing or refining Brayan's opportunity/project lifecycle workflows, especially status/state semantics and automation readiness.

## Core diagnosis pattern

1. Inventory all state surfaces, not just workflow docs:
   - `_meta/schema.md`
   - `_meta/workflows/**`
   - `_meta/templates/**`
   - root READMEs, dashboards, finished registers
   - relevant Hermes skills, agent prompts, scripts, cron jobs
   - `decisions/pending.md`
2. Separate three concepts explicitly:
   - `status`: what the vault/agents should do now
   - routing fields: what kind of automation or artifact is relevant
   - outcome fields: what happened in the end
3. Check state invariants across dashboards/frontmatter/body, not only whether values are allowed.
4. Treat phrase-triggered workflows as insufficient for automation. For closing/finalization workflows, prefer a file-driven input surface such as `closeout-input.md` / `final-result-input.md` that a scanner or agent can process deterministically.

## Opportunity lifecycle lessons

Canonical status flow should stay small:

`captured -> researched -> preparation-ready -> awaiting-review -> applied/archived`

Useful invariants:

- `preparation-ready`: specific target, enough current details for preparation, `automation_route: opportunity-preparation`, no existing canonical packet.
- `awaiting-review`: a review object exists or partial review material exists; make the object explicit via `preparation_packet` or a future `review_object` field. Prefer `automation_route: none` after the packet/material exists if `automation_route` means next automation route.
- `applied`: external submission happened and an external result is still worth tracking.
- `archived`: no active opportunity workflow remains; must have `closed`, `result_status`, `result_type`, `result_summary`, finished-register row, and dashboard removal.

Common drift findings:

- expired opportunities remain in active dashboards as `awaiting-review` or `researched`;
- `awaiting-review` is overloaded between full packets, partial drafts, planning packets, and stale post-deadline decisions;
- legacy `tailoring_packet` / `tailoring-packet` artifacts remain in active-looking records;
- `automation_route: opportunity-preparation` remains after packet creation, creating ambiguity about what should run next;
- `decisions/pending.md` keeps expired opportunity reminders alive after the dashboard should have been closed or updated.

## Project lifecycle lessons

Projects need a full lifecycle comparable to opportunities. Recommended minimal status set:

`seed -> active -> paused -> active`
`seed -> archived`
`active -> complete|archived|paused`
`paused -> archived`

Avoid dashboard-only statuses. If a concept like `incubating` is useful, prefer `status: seed` plus `stage: incubating` rather than inventing another status unless schema/workflows/templates/audits all adopt it.

Project README/template invariants should include:

- concrete objective / desired outcome
- next action
- success criteria or success levels
- stop/completion condition
- pause/resume condition when relevant
- linked opportunities/decisions
- external workspace link when code/artifacts live under `/home/brayan/projects/`
- closeout/final result fields once complete or archived

Recommended missing project workflow surfaces:

- project intake/routing workflow
- project activation workflow
- project review/update workflow
- project pause/reopen workflow
- file-driven project closeout input template
- project state audit checks

## File-driven closing pattern

For both projects and opportunities, prefer this shape for automation-ready closing:

1. User or agent writes a small input file under the item folder, e.g. `closeout-input.md` or `final-result-input.md`.
2. The input file records proposed final state, evidence, artifacts, linked opportunity/project action, and unresolved questions.
3. A deterministic scanner detects pending closeout inputs.
4. An agent applies the canonical closing workflow: update item frontmatter/body, update dashboard/finished register, resolve stale decisions, log, and verify.
5. Keep the input file only when it contains substantial evidence or user-provided wording; otherwise merge into the canonical final-result/closeout note and remove/archive the temporary input.
