---
name: job-application-vault-workflow
description: Maintain Brayan's job-application pipeline inside ~/personal_vault — preserve CV source packs, create canonical Markdown CVs, and turn job links into structured opportunity records ready for tailoring/review agents.
version: 1.0.0
author: Darwin
license: MIT
---

# Job Application Vault Workflow

Use this skill when Brayan asks to:
- normalize/update his CV inside the personal vault
- preserve CV source files uploaded through Anything Inbox
- create or update the job-application intake system
- turn a job link into a structured vault record for later tailoring

## Prerequisites
Always orient with:
1. `~/personal_vault/_meta/schema.md`
2. `~/personal_vault/_meta/index.md`
3. `~/personal_vault/_meta/log.md`
4. `~/personal_vault/projects/job-application-copilot.md` if it exists
5. `~/personal_vault/domains/opportunities/opportunities-map.md` if it exists

## Canonical file locations
- Master Markdown CV: `~/personal_vault/projects/job-application-cv-master.md`
- CV source-pack note: `~/personal_vault/raw/notes/YYYY-MM-DD-brayan-barajas-cv-source-pack.md`
- Durable source files: `~/personal_vault/raw/assets/YYYY-MM-DD-cv-brayan-barajas.docx` and `.pdf`
- Job workflow note: `~/personal_vault/projects/job-opportunity-intake-workflow.md`
- Job tailoring automation note: `~/personal_vault/projects/job-tailoring-agent-automation.md`
- Per-job records: `~/personal_vault/projects/job-opportunities/YYYY-MM-DD-company-role.md`
- Job opportunity template: `~/personal_vault/_meta/templates/job-opportunity-template.md`
- Tailoring packet template: `~/personal_vault/_meta/templates/job-tailoring-packet-template.md`
- Tailored packets: `~/personal_vault/projects/job-application-packets/<job-stem>/`
- Independent-session dispatcher/scanner script: `~/.hermes/scripts/job_tailoring_ready_scan.py`
- Job-tailoring prompt template: `~/.hermes/agents/job-tailoring/prompt-template.md`
- Job-tailoring specialized skill: `~/.hermes/skills/job-tailoring-agent/SKILL.md`
- Current daily dispatcher cron: `darwin-job-tailoring-agent`

## CV normalization workflow
1. Find the uploaded CV files in `~/personal_vault/inbox/`.
2. Preserve durable copies in `raw/assets/` before editing or transforming anything.
3. Extract text from the best available source.
   - Prefer DOCX extraction when available.
   - If `pandoc` is unavailable, use Python + `zipfile`/Word XML extraction for `.docx`.
   - Use `pdftotext -layout` as a fallback/cross-check for the PDF.
4. Build a clean Markdown CV that preserves all source details, fixing only user-explicit corrections.
5. Record any user-provided corrections in the raw source-pack note so future agents know which differences are intentional.
6. Link the Markdown CV from the source-pack note and from the broader job-application project notes.

## Reliable extraction lesson
On this Hermes setup, `pandoc` may be missing even when `pdftotext` is present. For DOCX extraction, a dependable fallback is:
- use Python stdlib `zipfile` to read `word/document.xml`
- parse `<w:t>` text nodes with `xml.etree.ElementTree`
- use that output to reconstruct the Markdown CV
This is good enough for structured CV recovery when `python-docx` is also unavailable.

## Opportunity intake workflow
For each new job link:
1. Preserve the source URL and any user notes.
2. Create a job note from `_meta/templates/job-opportunity-template.md` under `projects/job-opportunities/`.
3. Read the full public posting.
4. Open the actual application form, not just the listing.
5. Record whether the form requires or requests:
   - CV upload
   - cover letter
   - LinkedIn
   - portfolio/website
   - salary expectation
   - work authorization / visa answers
   - relocation/location constraints
   - custom screening questions
   - additional attachments
6. Extract hard requirements, preferred qualifications, and inferred signals.
7. Assign priority (`P0`–`P3`), fit, `job_work_automation_potential`, and `application_process_complexity`.
   - `job_work_automation_potential` means how easily agents could automate, accelerate, or assist with doing the actual job duties after Brayan has the role.
   - It does **not** mean how easy the application process is to automate.
   - Track form/process friction separately as `application_process_complexity`.
8. Write a tailoring brief so the second agent can draft the role-specific packet without re-reading everything from scratch.
9. When enough information exists for tailoring, set `status: tailoring-ready`.
10. Stop before submission unless Brayan explicitly expands policy.

## Independent-session tailoring workflow
The current implementation intentionally uses only a once-daily cron-backed dispatcher. Do **not** recreate the removed `job_tailoring_autotrigger` plugin/sentinel fast path, and do **not** use `delegate_task` subagents for this job-tailoring fanout unless Brayan explicitly asks to redesign it.

Trigger path:
1. User sends job link/details to the Telegram Anything Inbox.
2. First agent creates/updates a job note in `projects/job-opportunities/`.
3. First agent marks the note `status: tailoring-ready` only when there is enough information to tailor.
4. Cron job `darwin-job-tailoring-agent` (`edfaeb3aed5d`) runs daily at 11:00 with pre-run script `~/.hermes/scripts/job_tailoring_ready_scan.py`.
5. The scanner emits JSON listing all ready jobs and skips any job that already has:
   - a non-empty `tailoring_packet:` field, or
   - an existing packet directory under `projects/job-application-packets/<job-stem>/`.
6. The scanner sorts ready jobs by priority (`P0` before `P1` before `P2` before `P3`) and then by note stem, then selects at most three launchable jobs for the day with `max_sessions: 3` and `selected_count`.
7. The pre-run script itself is the dispatcher: for each selected job, read `~/.hermes/agents/job-tailoring/prompt-template.md`, fill placeholders from the selected job, and launch one fully independent Hermes CLI session with `hermes --skills personal-vault-ops,job-tailoring-agent chat -Q --source job-tailoring-session -q <rendered prompt>`.
8. Stable specialized behavior lives in `~/.hermes/skills/job-tailoring-agent/SKILL.md`; do not embed large job-tailoring prompts in `~/.hermes/scripts/job_tailoring_ready_scan.py`. Scripts are dispatchers only: scan/select, render templates, launch sessions, write locks/logs, and emit wake-gated JSON.
9. Each independent session handles exactly one job, reads the job note and canonical Markdown CV, creates/updates the packet under `projects/job-application-packets/<job-stem>/`, updates the source job note to `awaiting-review` with a `tailoring_packet:` link, and reports blockers or next action to Brayan.
10. The parent cron LLM normally stays asleep: the dispatcher emits `wakeAgent: false` after a clean scan/launch and only wakes the fallback prompt if dispatch errors need repair.
11. The dispatcher records per-job locks/logs under `~/.hermes/state/job_tailoring_sessions/` and `~/.hermes/logs/job_tailoring_sessions/` so the next daily run avoids relaunching active/fresh sessions.

Packet contents should include:
- tailored CV draft or exact CV delta instructions
- cover letter if the application requires or strongly benefits from one
- answers to custom screening questions if present
- reviewer summary and risks/gaps
- related project evidence from the vault: matching coding/research/creative/automation projects, status, why each matches, how to present it (GitHub/demo/write-up/portfolio/application answer), portfolio gaps, and conservative project-priority implications
- quick proof-of-work project ideas if a fellowship/residency/program or job would reward visible work more than conventional experience
- recommended skills/certifications/projects if useful
- manual review checklist

Avoid reverting to after-every-turn scanning, agent-discretionary cron calls, plugin/sentinel immediate handoff, or `delegate_task` subagents unless Brayan explicitly asks. The preferred design is: daily cron → scanner selects at most 3 highest-priority ready jobs → pre-run script launches one independent Hermes session per selected job.

## Required deliverables
When setting up or updating the system, make sure these exist and are linked:
- canonical Markdown CV
- raw CV source-pack note
- intake workflow note
- job opportunity template
- tailoring packet template
- job tailoring automation note
- job-opportunities folder/readme or equivalent index
- job-application-packets folder/readme or equivalent index
- `_meta/index.md` links
- `_meta/log.md` entry documenting the structural change

## Current policy boundary
- Allowed: intake, extraction, prioritization, form inspection, tailored draft preparation, reviewer notification.
- Not yet allowed by default: auto-submission to employers.
- Any security/adversarial testing related to ATS/HR systems must remain sandboxed or consent-based.

## Live-run audit workflow
When auditing whether a Telegram job-link intake actually worked, check all of these instead of relying on one log source:
1. `~/.hermes/logs/notes_preprocessor.jsonl` for URL detection/prefetch counts (`prefetched_ok`, `prefetched_failed`).
2. The relevant `~/.hermes/sessions/session_*.json` for the intake agent's actual tool calls and final response.
3. `~/personal_vault/raw/notes/` for the preserved source capture.
4. `~/personal_vault/projects/job-opportunities/` for created/updated opportunity records and statuses.
5. `~/.hermes/scripts/job_tailoring_ready_scan.py` output for the live tailoring queue.
6. `~/.hermes/cron/output/<job_id>/` and `~/.hermes/sessions/session_cron_<job_id>_*.json` for tailoring-agent executions.
7. `~/personal_vault/projects/job-application-packets/` for generated packets.

Important audit lessons from the first live bundle:
- URL prefetch context may be injected into the model call without being persisted into the session transcript. If the session JSON only shows the raw user message, verify prefetch in `notes_preprocessor.jsonl` before concluding it failed.
- A scheduled tailoring cron can race ahead of a long intake run and skip with `wakeAgent=false` before job notes are finished. This is expected-safe behavior, not necessarily a failure.
- Brayan prefers this workflow to stay low-frequency: no plugin/immediate-trigger handoff by default. Use the daily cron as the intended mechanism; it should select at most three highest-priority ready jobs and launch one independent Hermes session per job.
- If checking whether the daily cron will dispatch, run `~/.hermes/scripts/job_tailoring_ready_scan.py --dry-run` and inspect `ready_count`, `selected_count`, `max_sessions`, `ready_jobs`, and `selected_jobs`. Dry-run should not launch sessions.

## Pitfalls
- Do not rely on the public job page alone; inspect the real apply form.
- Do not silently change CV facts unless the user explicitly corrected them.
- Do not keep uploaded CVs only in `inbox/`; preserve durable copies in `raw/assets/`.
- Do not build a tailoring agent handoff without listing required artifacts and screening questions.
- Do not treat the Markdown CV as replacing the original source files; keep both.

## Verification checklist
Before finishing:
- Confirm the Markdown CV exists and includes the full source content.
- Confirm any explicit user correction is reflected in both the CV and source-pack note.
- Confirm durable source files exist in `raw/assets/`.
- Confirm workflow/template notes exist.
- Confirm `_meta/index.md`, related project/domain notes, and `_meta/log.md` were updated.
- If a specific job was processed, confirm the note states whether a cover letter or additional form responses are needed.
- If implementing/updating the independent-session dispatcher, confirm `hermes config check` passes, the scanner script compiles, `~/.hermes/scripts/job_tailoring_ready_scan.py --dry-run` selects the expected jobs without launching sessions, the cron job exists, and `hermes cron status` says the gateway/cron runner is active.
- When verifying the scanner, check that notes with blank body lines like `- Packet path:` are still detected as ready; the scanner must only treat `Packet path:` as populated when a value appears on the same line, not when regex whitespace crosses into `- Packet status:` on the next line.
- Use a temporary `status: tailoring-ready` test job only if needed; remove it immediately after scanner verification.
