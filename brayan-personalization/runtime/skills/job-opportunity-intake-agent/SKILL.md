---
name: job-opportunity-intake-agent
description: Stable behavior for turning Anything Inbox job/opportunity captures into structured vault records ready for tailoring.
version: 1.0.0
author: Darwin
license: MIT
---

# Job Opportunity Intake Agent

Use this skill when Brayan sends a job link, role listing, internship, fellowship, grant, residency, competition, challenge, call for submissions, or similar opportunity. Treat competitions/challenges as opportunities when they can create recruiting signal, funding/compute access, public proof-of-work, network access, or career leverage.

## Required destination
Create or update a durable opportunity note under:
`~/personal_vault/projects/job-opportunities/`

Use template:
`~/personal_vault/_meta/templates/job-opportunity-template.md`

## Required research
- Use prefetched URL context when present.
- Inspect the full public posting.
- Inspect the actual application form when accessible, not only the listing.

## Required fields
Record:
- source URL and Brayan comments
- company
- role/title
- requirements and preferred qualifications
- application URL
- required artifacts
- whether cover letter/custom answers/recommendations/portfolio are needed
- priority P0-P3
- fit and user interest
- `job_work_automation_potential`
- `application_process_complexity`
- tailoring brief
- open questions / missing data

## Important scoring distinction
`job_work_automation_potential` means how easily agents could automate, accelerate, or assist the actual work of the role after Brayan has it. It does not mean application-form automation.

Track `application_process_complexity` separately for how hard the application itself is.

## Tailoring readiness
Set `status: tailoring-ready` only when enough job details and form requirements are captured for the second tailoring agent to produce a personalized application packet.

For fellowships, residencies, grants, and programs with multiple tracks/workstreams/paths, also inspect the path-specific pages and create a linked application-strategy/project-support note when Brayan asks to understand paths, viable project directions, or how to position himself. The strategy note should compare paths, recommend a primary/secondary application stance, identify viable projects or writing-sample angles before the deadline, and list urgent decisions such as references, visa/location, and artifact gaps. Link this from the opportunity record using a distinct field such as `strategy_note`, `project_support`, or a body link. Do not put strategy/path-analysis/project-support notes in `tailoring_packet`.

For competitions/challenges that Brayan wants to attempt, create both:
1. an opportunity record under `projects/job-opportunities/` capturing rules, deadline, submission process, participant/application form, required artifacts, fit, priority, and recruiting/network value; and
2. a linked short execution sprint/project note when the deadline is near or the task requires active work. The sprint note should define success levels, fast strategy, immediate next actions, risks/constraints, and how Darwin/agents can help. Link the sprint note using a distinct field such as `sprint_note`, `project_support`, or a body link. Do not put sprint/project execution notes in `tailoring_packet`.

Field semantics: reserve `tailoring_packet` only for actual full application-tailoring packets, normally `projects/job-application-packets/<stem>/tailoring-packet`. The job-tailoring dispatcher verifies that a referenced or expected `tailoring-packet.md` file actually exists before skipping a `tailoring-ready` note; strategy/sprint/project-support links still belong in distinct fields such as `strategy_note`, `sprint_note`, or `project_support` so the vault schema stays clear.

If the public posting or application form is blocked by Cloudflare/403/bot detection, create/update the opportunity record as `status: captured` or `researched` with `form_inspection_status: blocked`, record exactly what failed, and do **not** mark it tailoring-ready until a non-blocked copy or manual inspection provides requirements, deadlines, eligibility, and artifacts.

### Blocked-page rescue workflow
When Brayan later provides a Markdown/plaintext copy of a blocked job/program page in `~/personal_vault/inbox/`:
1. Preserve that inbox file verbatim as a raw source note under `~/personal_vault/raw/notes/` before distilling it.
2. Extract any application URL from the manual copy and inspect the actual form if accessible, even if the original public page remains blocked.
3. Update the existing opportunity record rather than creating a duplicate; set `url_prefetch_status` to reflect blocked-then-manual-copy or similar.
4. Mark `form_inspection_status: complete` only after the actual form is inspected; otherwise keep the blocker explicit.
5. Mark `status: tailoring-ready` only when the manual copy + form inspection together provide enough details for tailoring: requirements, logistics/eligibility, deadline/timeline, artifacts, screening questions, and application complexity.
6. Update opportunity indexes and `_meta/log.md` with the rescue/intake completion.
7. Do not delete the original inbox rescue file with a broad/destructive shell command; if cleanup is desired, use a safe file tool or report that the raw copy has been preserved and the inbox duplicate can be removed manually.

For fellowships/residencies/programs with possible eligibility constraints, explicitly separate program-specific logistics from generic company hiring policies. If a page says generic full-time-role policies do not apply to the fellowship/program, treat the program-specific work-authorization/visa language as controlling and record the generic policy only as non-applicable context.

Do not submit external applications.
