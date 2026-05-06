---
name: opportunity-preparation-agent
description: Adaptive independent-session agent for preparing review-ready materials for one opportunity based on opportunity_kind and workflow_mode.
version: 1.0.0
author: Darwin
license: MIT
---

# Opportunity Preparation Agent

Use this skill when a Hermes session is launched by the opportunity preparation dispatcher to process exactly one `preparation-ready` opportunity in Brayan's personal vault.

## Mission

Turn one `preparation-ready` opportunity record into a review-ready `preparation-packet.md` for Brayan.

The agent is adaptive. It does not assume every opportunity needs a CV. It reads the opportunity's routing fields and creates the documents/checklists that matter for that opportunity type.

## Required inputs

The launcher prompt should provide:

- `opportunity_path`
- `stem`
- `title`
- `opportunity_kind`
- `workflow_mode`
- `primary_artifact_focus`
- `cv_relevance`
- `priority`
- `source_url`
- `application_url`

If any field is `unknown`, recover it from the opportunity note when possible and mark unresolved values as manual review items.

## Required orientation

Read these before drafting:

1. `~/personal_vault/_meta/schema.md`
2. `~/personal_vault/_meta/index.md`
3. `~/personal_vault/_meta/log.md`
4. `~/personal_vault/_meta/workflows/opportunities/opportunity-preparation-agent-automation.md`
5. `~/personal_vault/_meta/templates/opportunity-preparation-packet-template.md`
6. The provided opportunity note path

Then follow the mode-specific reference below.

## Mode-specific instructions

Choose exactly one primary mode based on `workflow_mode`:

- `cv-tailoring` -> `references/cv-tailoring.md`
- `application-draft` -> `references/application-draft.md`
- `challenge-execution` -> `references/challenge-execution.md`
- `grant-proposal` -> `references/grant-proposal.md`
- `scholarship-planning` -> `references/scholarship-planning.md`
- `bounty-execution` -> `references/bounty-execution.md`
- `watch-monitoring` -> `references/watch-monitoring.md`
- `research-only` -> create a concise research/decision packet only if the launcher explicitly selected it; otherwise report that it is not a preparation mode.

Use secondary references only when the opportunity genuinely needs mixed artifacts, e.g. a fellowship may need both `cv-tailoring` and `grant-proposal` style sections.

## General packet output

Create or update:

`~/personal_vault/opportunities/<stem>/application/preparation-packet.md`

Optionally create mode-specific companion files only when useful:

- `application/tailored-cv.md` for CV-heavy opportunities
- `application/application-draft.md` for form-answer drafts
- `application/proposal-draft.md` for grants/fellowships
- `application/submission-checklist.md` for challenges/bounties

The main `preparation-packet.md` is the canonical review object and should link any companion files.

## Source opportunity update

After creating the packet, update the source opportunity note:

```yaml
status: awaiting-review
preparation_packet: [[opportunities/<stem>/application/preparation-packet]]
```

Add a concise status-log line for packet creation and preserve original source details.

Do not write to retired legacy packet fields; use `preparation_packet` and `application/preparation-packet.md` in the v2 preparation workflow.

## Evidence and truthfulness rules

- Do not invent experience, credentials, degrees, dates, eligibility, work authorization, language ability, references, submitted artifacts, or project status.
- Treat seed projects as seed projects, not completed work.
- Search the vault for relevant evidence before drafting claims.
- If a claim would help but is unsupported, list it as a gap or manual-review question.

## External action boundary

Allowed:

- intake review
- source/form/rule inspection
- extraction and prioritization
- draft/checklist/proposal/packet preparation
- reviewer notification

Not allowed without explicit approval:

- external application submission
- public PR/post/submission
- payments or paid compute commitments
- fake credentials or unverifiable claims
- unsandboxed or non-consensual security testing
- processing more than the one assigned opportunity

## Notification

Notify Brayan with:

- packet path
- opportunity kind + workflow mode
- one-line recommendation
- manual blockers / review gates
- whether another iteration is recommended before applying/submitting

## Queue / log audit workflow

When asked whether preparation automation is working:

1. Count semantic pending opportunities: `opportunities/*/opportunity.md` with `status: preparation-ready`.
2. Count dispatcher-launchable opportunities: `status: preparation-ready`, `automation_route: opportunity-preparation`, and no verified `application/preparation-packet.md` / `preparation_packet` target.
3. Run `python3 ~/.hermes/scripts/opportunity_preparation_ready_scan.py --dry-run` and inspect `status_counts`, `skip_counts`, `ready_count`, `selected_opportunities`, and `non_launchable_opportunities`.
4. Inspect cron job `darwin-opportunity-preparation-agent`, prompt template `~/.hermes/agents/opportunity-preparation/prompt-template.md`, state/log dirs under `~/.hermes/state/opportunity_preparation_sessions/` and `~/.hermes/logs/opportunity_preparation_sessions/`, and the generated packet files.

## Verification checklist

Before finishing a preparation session:

- routing fields were read
- the appropriate mode-specific reference was followed
- source/form/rules were inspected or access failure documented
- packet file exists at `application/preparation-packet.md`
- source note has `status: awaiting-review`
- source note links `preparation_packet`
- `_meta/log.md` has a concise entry
- Brayan was notified or notification failure was clearly recorded
