---
name: opportunity-intake-agent
description: Stable behavior for turning Anything Inbox opportunity captures into structured vault records ready for adaptive preparation.
version: 1.0.0
author: Darwin
license: MIT
---

# Opportunity Intake Agent

Use this skill when Brayan sends a job link, role listing, internship, fellowship, grant, residency, competition, challenge, bounty, scholarship, career watch page, call for submissions, or similar opportunity.

## Mission

Create or update one durable opportunity record under:

`~/personal_vault/opportunities/<slug>/opportunity.md`

Use the canonical template:

`~/personal_vault/_meta/templates/opportunity-template.md`

The intake agent does not prepare the final review packet. It researches, classifies, and routes the opportunity so the adaptive opportunity preparation agent can create the right materials later.

## Required orientation

Read:
1. `~/personal_vault/_meta/schema.md`
2. `~/personal_vault/_meta/index.md`
3. `~/personal_vault/_meta/log.md`
4. `~/personal_vault/_meta/workflows/opportunities/opportunity-intake-and-routing-workflow.md`
5. `~/personal_vault/_meta/templates/opportunity-template.md`

Follow `personal-vault-ops` for vault conventions, raw preservation, links, and log updates.

## Required research

- Use prefetched URL context when present.
- Inspect the full public posting/source.
- Inspect the actual application/participant/submission form when accessible, not only the public listing.
- For blocked forms/pages, record the blocker and keep the status earlier instead of guessing.

## Required routing fields

Every newly created opportunity record should include:

```yaml
opportunity_kind: job|internship|fellowship|residency|grant|scholarship|challenge|bounty|watch|other
workflow_mode: cv-tailoring|application-draft|challenge-execution|grant-proposal|scholarship-planning|bounty-execution|watch-monitoring|research-only
primary_artifact_focus: unknown
cv_relevance: required|strategic|optional-not-primary|irrelevant|unknown
automation_route: opportunity-preparation|manual-review|none
preparation_packet: null
```

Use `automation_route: opportunity-preparation` only when the opportunity is intended for the adaptive preparation agent. Use `manual-review` when Brayan must choose a track/role/program first. Use `none` for archived, purely informational, or not-worth-processing records.

## Canonical opportunity statuses

Use only:

- `captured` — source received but posting/form/eligibility/deadline/artifacts are not sufficiently inspected. Not launchable.
- `researched` — enough is known to summarize fit, requirements, priority, and blockers, but it is not ready for the preparation agent. Not launchable.
- `preparation-ready` — a specific target has enough current information for the adaptive opportunity preparation agent to create a review packet now. This is the only intake/research status launchable by the preparation dispatcher.
- `awaiting-review` — a preparation packet, application draft, proposal, checklist, or equivalent review material exists under `opportunities/<slug>/application/` and Brayan needs to review, edit, decide, submit, or request another iteration.
- `applied` — Brayan submitted/applied, or Darwin submitted only after explicit approval.
- `archived` — closed, expired, skipped, rejected, duplicated, obsolete, or no longer worth tracking; include the reason.

Normal path:

`captured -> researched -> preparation-ready -> awaiting-review -> applied/archived`

When uncertain, choose the earliest defensible status and record the blocker.

## Routing by kind/mode

- Jobs, internships, fellowships, residencies where CV/profile material is primary: `workflow_mode: cv-tailoring`, `cv_relevance: required|strategic`.
- Short forms, compute grants, access forms: `workflow_mode: application-draft` or `grant-proposal`.
- Competitions/challenges: `workflow_mode: challenge-execution`; focus on rules, scoring, reproducibility, code/logs/README/PR/submission checklist.
- Scholarships: `workflow_mode: scholarship-planning`; focus on eligibility, documents, deadline table, transcript/passport/language/recommender blockers.
- Bounties: `workflow_mode: bounty-execution`; focus on scope, rules, evidence, disclosure/report checklist, safety/legal boundaries.
- Broad boards/future cycles: `workflow_mode: watch-monitoring` or `research-only`; usually keep `status: researched` until a specific target is chosen.


## Dashboard update requirement

After creating or materially updating an opportunity record, update `~/personal_vault/opportunities/dashboard.md` in the same pass.

- Add a row for new opportunities and update existing rows when status, priority, deadline, kind, or next action changes.
- Keep the dashboard sorted by Brayan's review priority order: exact `P0`, mixed/ranged `P0/P1` or `P0-P1`, exact `P1`, mixed/ranged `P1/P2` or `P1-P2`, exact `P2`, mixed/ranged `P2/P3` or `P2-P3`, then exact `P3`. Within the same tier, sort by urgency/deadline when known.
- Use one compact classification column: `Kind`. Do not add a combined `Kind / Mode` column. `workflow_mode` belongs in the opportunity frontmatter and agent context, not as the primary dashboard label.
- Preserve useful existing dashboard notes/manual blockers; do not drop Brayan-facing review context while reordering.

## Preparation readiness

Set `status: preparation-ready` only when all are sufficiently clear for the selected mode:

- target/source/form or submission process
- deadline/timeline or explicit uncertainty
- requirements/rules/eligibility
- required artifacts
- priority/fit/user interest
- manual blockers
- `opportunity_kind`, `workflow_mode`, `primary_artifact_focus`, `cv_relevance`, and `automation_route`

Do not mark generic portals, broad boards, future cycles, or blocked forms `preparation-ready` unless Brayan has selected a specific actionable target or the preparation mode explicitly supports a watch/planning packet.

## Packet semantics

Use `preparation_packet` only for the adaptive preparation agent's review-ready packet, normally:

`opportunities/<slug>/application/preparation-packet.md`

Use distinct fields for support material that is not the final preparation packet:

- `strategy_note`
- `sprint_note`
- `project_support`

## External action boundary

Agents may prepare documents, checklists, proposals, drafts, and recommendations. Brayan must manually review before external submission, public PR/post, payment, or other irreversible action unless he explicitly approves that exact action.
