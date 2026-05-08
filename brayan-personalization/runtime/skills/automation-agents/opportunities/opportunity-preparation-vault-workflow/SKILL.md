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
- Intake skill: `~/.hermes/skills/automation-agents/opportunities/opportunity-intake-agent/SKILL.md`
- Preparation skill: `~/.hermes/skills/automation-agents/opportunities/opportunity-preparation-agent/SKILL.md`
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

## Retrofitting existing opportunity records

Use this when older `opportunity.md` files predate the adaptive preparation template or routing fields.

1. Respect current review state: skip semantic recategorization for records already marked `awaiting-review` unless Brayan explicitly asks to update them; they already have review material and should not be relaunched casually.
2. For each non-`awaiting-review` record, add or normalize: `opportunity_kind`, `workflow_mode`, `primary_artifact_focus`, `cv_relevance`, `automation_route`, and `preparation_packet: null`.
3. Replace old `tailoring_packet` frontmatter on non-review records with `preparation_packet`; keep support links such as `strategy_note`, `sprint_note`, and `project_support` separate.
4. Choose `preparation-ready` only for specific, launchable targets with enough current information. Keep broad boards, watch surfaces, blocked/generic portals, and role-choice-needed records at `researched` or `captured` with `automation_route: manual-review` or `none`.
5. Add a short routing-update section/status-log entry in each changed record explaining the new kind/mode/route and the blocker or next action.
6. Update `opportunities/dashboard.md` in the same pass for any changed status, kind, priority, or deadline; preserve the six-column table and escaped wikilink aliases.
7. Validate all opportunity frontmatter parses as YAML. Common pitfall: unquoted colons in values such as `role: Internship: Data Management and Analytics` or `role: Board: A, B` break YAML; quote those scalar values even on skipped records if validation discovers them.
8. Run `python3 -m py_compile ~/.hermes/scripts/opportunity_preparation_ready_scan.py` and `~/.hermes/scripts/opportunity_preparation_ready_scan.py --dry-run` to verify launchable selection before reporting readiness.

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

## Updating existing application materials

Use this when Brayan is actively applying and asks for targeted edits to an existing opportunity packet, tailored CV, or form-answer drafts.

1. Locate the exact opportunity folder under `~/personal_vault/opportunities/<slug>/` and read `opportunity.md`, the relevant `application/` files, and `profile/cv-master.md` or source-pack notes as needed.
2. Apply only the requested changes to existing artifacts unless Brayan asks for broader tailoring. For employment-history changes, keep dates/order internally consistent across the tailored CV and any new answer files.
3. For form fields such as achievements, duties, or reason for leaving, create a focused `application/<descriptive-name>.md` draft with paste-ready long answers plus shorter variants for tight form limits.
4. For motivation letters / cover letters that must be pasted into a plain-text web form, create both:
   - `application/letter-of-motivation.md` with frontmatter, sources, character count, and the draft in a fenced `text` block for review.
   - `application/letter-of-motivation.txt` containing only the exact plain text to paste. Avoid bullets, tables, Markdown emphasis, headings, and other style elements in the `.txt` body. Check the field's maximum character count with a script/tool and record `character_count` and `max_character_count` in the MD frontmatter.
5. Keep the tone natural and human for motivation letters: direct, specific, mission-aware, and grounded in Brayan's actual profile evidence; avoid generic AI-cover-letter phrasing and do not invent eligibility, secured recommendations, visa feasibility, or domain experience.
6. Link any new application draft from the existing `application/preparation-packet.md` `outputs` and source-links area so the packet remains the opportunity's review hub.
7. Update `updated:` dates on changed markdown frontmatter using the live date, then verify by rereading the relevant sections and searching for stale/contradictory strings.
8. Validate changed YAML frontmatter when practical. If Python `yaml` is unavailable, Ruby's stdlib YAML can be used only when command execution approval is acceptable; otherwise quote potentially ambiguous frontmatter scalar values and verify by rereading/diffing.

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
