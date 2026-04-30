---
name: job-tailoring-agent
description: "Specialized behavior for Brayan's independent job-tailoring Hermes sessions: read the canonical CV, inspect job/application forms, draft tailored packets, update source notes, and notify Brayan without submitting applications."
version: 1.0.0
author: Darwin
license: MIT
---

# Job Tailoring Agent

Use this skill when a Hermes session is launched to create a tailored application packet for exactly one job opportunity in Brayan's personal vault.

## Mission

Turn one `tailoring-ready` opportunity record into a review-ready application packet for Brayan.

The session must:
1. Read the source job note.
2. Read Brayan's canonical Markdown CV.
3. Inspect the application form when needed.
4. Search the vault for relevant proof-of-work/project evidence.
5. Create or update the tailoring packet.
6. Update the source job note to `awaiting-review`.
7. Notify Brayan with the result and blockers.

Do not submit external applications.

## Required inputs

The launcher prompt should provide:
- `job_path`
- `stem`
- `title`
- `company`
- `role`
- `priority`
- `source_url`
- `application_url`

If any field is `unknown`, recover it from the job note when possible and mark unresolved values as manual review items.

## Required orientation

Read these before drafting:
1. `~/personal_vault/_meta/schema.md`
2. `~/personal_vault/_meta/index.md`
3. `~/personal_vault/_meta/log.md`
4. `~/personal_vault/profile/cv-master.md`
5. `~/personal_vault/_meta/templates/job-tailoring-packet-template.md`
6. The provided job note path

Follow `personal-vault-ops` for vault conventions, raw-vs-durable separation, links, and log updates.

## CV reading rules

- Treat `~/personal_vault/profile/cv-master.md` as the canonical editable CV/profile source.
- Preserve factual integrity. Do not invent experience, degrees, dates, tools, citizenship/work authorization, language ability, references, compensation history, or portfolio artifacts.
- Preserve Brayan's explicit correction that Invisible Technologies ended in 2024, not present.
- Use the CV to build a tailored emphasis plan: reorder, compress, expand, and rephrase only within factual bounds.
- If a claim would strengthen the application but is not supported by the CV or vault evidence, list it as a gap or manual review question.

## Application-form inspection

Inspect the real application form when possible, not only the public listing.

Record whether it requires or requests:
- CV upload
- cover letter
- LinkedIn
- portfolio/website/GitHub
- salary expectation
- work authorization / visa sponsorship answers
- relocation/location constraints
- custom screening questions
- writing sample
- recommendation letters or references
- additional attachments

If the form cannot be accessed, say so explicitly and infer only conservative likely artifacts from the posting.

## Project and proof-of-work matching

Search Brayan's vault for relevant evidence, including:
- `~/personal_vault/projects/`
- `~/personal_vault/_meta/dashboards/project-dashboard.md`
- `~/personal_vault/domains/ai/ai-map.md`
- `~/personal_vault/domains/coding/coding-map.md`
- `~/personal_vault/domains/physics/physics-map.md`
- `~/personal_vault/domains/creative/creative-map.md`
- `~/personal_vault/domains/opportunities/opportunities-map.md`

Consider projects regardless of status: seed, not-started, in-progress, finished, archived, or unknown.

For each useful match, explain:
- why it matches the role
- how Brayan should present it: GitHub, demo, portfolio link, write-up, research memo, application answer, or interview story
- whether a quick proof-of-work project would realistically improve this application before the deadline

Be conservative: do not present seed ideas as completed work.

## Packet output

Create/update:
- `~/personal_vault/opportunities/<stem>/application/tailoring-packet.md`
- optionally `~/personal_vault/opportunities/<stem>/application/tailored-cv.md` if the tailored CV is long enough to deserve its own file

The packet must include:
- reviewer summary for Brayan
- role/company/priority/fit
- job-work automation potential assessment
- application process complexity
- required artifacts
- application-form findings
- CV delta plan
- tailored Markdown CV draft or separate `tailored-cv.md`
- cover letter draft if required or strategically useful
- custom application answers if form questions are found
- related project evidence from Brayan's vault
- skill/certification/project recommendations
- risks and manual review checklist

## Source job note update

After packet creation, update the source opportunity note:
- `status: awaiting-review`
- `tailoring_packet: [[opportunities/<stem>/application/tailoring-packet]]`
- add a concise status-log line for packet creation

Keep the source note's original job details and links intact.

## Notification

Notify Brayan, preferably through the configured home messaging channel, with:
- packet path
- one-line recommendation
- required manual blockers
- whether a cover letter/custom answers/recommendation letters are needed

## Boundaries

Allowed:
- intake review
- extraction
- prioritization
- application-form inspection
- tailored draft preparation
- reviewer notification

Not allowed by default:
- external application submission
- fake credentials or unverifiable claims
- unsandboxed ATS/HR prompt-injection/security testing
- processing more than the one assigned job in the prompt

## Queue / log audit workflow

Use this when Brayan asks how many jobs are pending for tailoring, whether the tailoring cron worked, or what steps/scripts were involved.

1. Orient with `personal-vault-ops` and read `_meta/schema.md`, `_meta/index.md`, `_meta/log.md`, plus this skill and `~/personal_vault/_meta/workflows/opportunities/job-tailoring-agent-automation.md`.
2. Count both semantic and dispatcher-launchable pending jobs:
   - semantic: opportunity notes under `~/personal_vault/opportunities/*/opportunity.md` with `status: tailoring-ready`.
   - launchable by current dispatcher: `status: tailoring-ready` AND no existing verified `opportunities/<stem>/application/tailoring-packet.md`; a non-null `tailoring_packet` only blocks launch if it resolves to an existing `tailoring-packet.md` file.
   - Always run `python3 ~/.hermes/scripts/job_tailoring_ready_scan.py --dry-run` from the vault to verify the dispatcher's own `ready_count`, `selected_jobs`, and skipped behavior.
3. Inspect runtime configuration and history:
   - `cronjob(action="list")` for `darwin-job-tailoring-agent`, schedule, last run, next run, script, and enabled state.
   - `~/.hermes/scripts/job_tailoring_ready_scan.py` for scan/select/launch logic.
   - `~/.hermes/agents/job-tailoring/prompt-template.md` for rendered independent-session prompt shape.
   - `~/.hermes/state/job_tailoring_sessions/*.json` for launched job metadata, prompt path, command, PID, log path, skills, and timestamps.
   - `~/.hermes/logs/job_tailoring_sessions/*.log` for actual per-job session outcomes, created files, source-note updates, application-form inspection notes, blockers, and notification status.
   - `~/.hermes/sessions/session_cron_edfaeb3aed5d_*.json` if cron/log files are sparse or older runs need reconstruction.
4. Check whether recorded PIDs are still running with `ps -p ...`; stale lock files can remain after successful completion, so do not assume a JSON lock means an active session.
5. Reconcile edge cases explicitly. A note may be `tailoring-ready` while also containing strategy/sprint/project-support links. These should live in fields such as `strategy_note`, `sprint_note`, or `project_support`; `tailoring_packet` is reserved for a verified full `tailoring-packet.md` created by the tailoring agent.
6. In the final audit, separate:
   - strict launchable pending count from semantic `tailoring-ready` count;
   - jobs completed/awaiting-review with packet paths;
   - scripts/prompts/skills involved;
   - high-level steps the pipeline followed;
   - concrete cleanup recommendations.

## Root-cause fix workflow for tailoring queue semantic mismatches

Use this when the queue count looks wrong, a `tailoring-ready` opportunity is skipped, or Brayan asks why `tailoring_packet` points somewhere unexpected.

1. Do not patch first. Trace provenance from evidence:
   - read the affected opportunity notes;
   - run `python3 ~/.hermes/scripts/job_tailoring_ready_scan.py --dry-run`;
   - search `~/.hermes/sessions/` for the exact bad wikilink/path and opportunity stem;
   - inspect the originating session messages/tool calls to identify whether intake, tailoring, cron, or a manual conversation wrote the field;
   - inspect relevant skills/templates/docs that may have instructed the bad write.
2. Treat `tailoring_packet` as a strict state field, not a generic support-link field. It should only point to a verified full packet at `opportunities/<stem>/application/tailoring-packet` / `.md`.
3. Use distinct fields for non-packet artifacts:
   - `strategy_note` for fellowship/program/path-analysis notes;
   - `sprint_note` for competition/challenge execution plans;
   - `project_support` for other linked support notes.
4. When fixing, update all necessary layers together:
   - affected opportunity frontmatter and body packet section;
   - source status-log lines and `_meta/log.md`;
   - `_meta/templates/job-opportunity-template.md`;
   - workflow docs such as `_meta/workflows/opportunities/job-opportunity-intake-workflow.md` and `_meta/workflows/opportunities/job-tailoring-agent-automation.md`;
   - skills such as `job-opportunity-intake-agent` and this skill;
   - dispatcher script behavior if the automation can enforce the invariant.
5. Verify with both semantic and automated checks:
   - no non-null `tailoring_packet` points anywhere except an existing `tailoring-packet.md`;
   - `py_compile` passes for modified scripts;
   - dry-run selected jobs match expectation;
   - search skills/vault docs for stale phrases like “strategy as tailoring_packet” or “no non-null tailoring_packet”.

## Verification checklist

Before finishing, verify:
- canonical CV was read
- application/source URL was inspected or access failure was documented
- packet file exists
- source job note has `status: awaiting-review`
- source job note links the packet
- `_meta/log.md` has a concise entry
- Brayan was notified or notification failure was clearly recorded
