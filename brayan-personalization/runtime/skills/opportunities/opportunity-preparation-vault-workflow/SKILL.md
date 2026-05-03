---
name: opportunity-preparation-vault-workflow
description: Maintain Brayan's opportunity pipeline inside ~/personal_vault — preserve profile sources, create opportunity records, and route them into adaptive preparation packets for review.
version: 1.0.0
author: Darwin
license: MIT
---

# Opportunity Preparation Vault Workflow

Use this skill when Brayan asks to set up, audit, or update the opportunity pipeline in the personal vault: opportunity intake, routing metadata, preparation automation, CV/profile source preservation, and review-packet generation.

## Prerequisites

Orient with:

1. `~/personal_vault/_meta/schema.md`
2. `~/personal_vault/_meta/index.md`
3. `~/personal_vault/_meta/log.md`
4. `~/personal_vault/domains/opportunities/opportunities-map.md` if relevant
5. `~/personal_vault/projects/job-application-copilot/README.md` if CV/job-application history is relevant

## Canonical file locations

- Master Markdown CV: `~/personal_vault/profile/cv-master.md`
- CV source-pack notes/assets: `~/personal_vault/raw/notes/` and `~/personal_vault/raw/assets/`
- Opportunity intake workflow: `~/personal_vault/_meta/workflows/opportunities/opportunity-intake-and-routing-workflow.md`
- Opportunity preparation automation note: `~/personal_vault/_meta/workflows/opportunities/opportunity-preparation-agent-automation.md`
- Opportunity template: `~/personal_vault/_meta/templates/opportunity-template.md`
- Preparation packet template: `~/personal_vault/_meta/templates/opportunity-preparation-packet-template.md`
- Opportunity records: `~/personal_vault/opportunities/<slug>/opportunity.md`
- Preparation packets: `~/personal_vault/opportunities/<slug>/application/preparation-packet.md`
- Dispatcher/scanner script: `~/.hermes/scripts/opportunity_preparation_ready_scan.py`
- Preparation prompt template: `~/.hermes/agents/opportunity-preparation/prompt-template.md`
- Intake skill: `~/.hermes/skills/opportunities/opportunity-intake-agent/SKILL.md`
- Preparation skill: `~/.hermes/skills/opportunities/opportunity-preparation-agent/SKILL.md`
- Current daily dispatcher cron: `darwin-opportunity-preparation-agent`

## Opportunity intake workflow

For each new opportunity:

1. Preserve the source URL and any user notes.
2. Create/update a record from `_meta/templates/opportunity-template.md` under `opportunities/<slug>/opportunity.md`.
3. Read the public source and actual form/submission process when accessible.
4. Fill routing fields: `opportunity_kind`, `workflow_mode`, `primary_artifact_focus`, `cv_relevance`, `automation_route`.
5. Extract requirements/rules/eligibility, required artifacts, timeline, blockers, priority, and fit.
6. Set `status: preparation-ready` only when a specific target has enough details for the adaptive preparation agent.
7. Stop before external action unless Brayan explicitly approves the exact action.

## Independent-session preparation workflow

Trigger path:

1. Brayan sends an opportunity to Anything Inbox.
2. Intake creates/updates an opportunity record.
3. Intake marks the note `status: preparation-ready` only when ready and sets `automation_route: opportunity-preparation`.
4. Cron job `darwin-opportunity-preparation-agent` (`edfaeb3aed5d`) runs daily at 11:00 with pre-run script `~/.hermes/scripts/opportunity_preparation_ready_scan.py`.
5. The scanner selects at most three launchable opportunities and launches one independent Hermes CLI session each with `hermes --skills personal-vault-ops,opportunity-preparation-agent chat -Q --source opportunity-preparation-session -q <rendered prompt>`.
6. Each independent session follows `opportunity-preparation-agent`, creates `application/preparation-packet.md`, updates the source note to `awaiting-review` with `preparation_packet`, and notifies Brayan.

## Packet contents

The preparation packet should include:

- reviewer summary
- opportunity kind and workflow mode
- source/form/rules findings
- required artifacts
- mode-specific draft/checklist/proposal/plan sections
- related project/profile/evidence links when useful
- manual blockers and review checklist
- recommended next action

## Current policy boundary

Allowed: intake, extraction, prioritization, source/form/rule inspection, tailored/adaptive draft preparation, reviewer notification.

Not allowed by default: external submissions, public PRs/posts, bounty reports, payments, paid compute commitments, fake credentials, or non-consensual/unsandboxed security testing.

## Verification checklist

When updating the system:

- Workflow/template docs exist and use preparation terminology.
- Opportunity statuses use `preparation-ready`; the older readiness label is retired.
- Active automation uses `opportunity_preparation_ready_scan.py`.
- Cron job `darwin-opportunity-preparation-agent` points to the new script and skill.
- `python3 -m py_compile ~/.hermes/scripts/opportunity_preparation_ready_scan.py` passes.
- `~/.hermes/scripts/opportunity_preparation_ready_scan.py --dry-run` works without launching sessions.
- `hermes config check` passes.
