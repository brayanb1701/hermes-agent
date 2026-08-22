---
name: opportunity-closing-agent
description: Stable behavior for processing one opportunity closeout-input.md into final applied/archived state, dashboard removal, finished-register update, decision cleanup, and preserved closeout evidence.
version: 1.0.0
author: Darwin
license: MIT
---

# Opportunity Closing Agent

Use this skill when a Hermes session is launched by the opportunity closeout dispatcher to process exactly one live `closeout-input.md` for one opportunity in Brayan's personal vault.

## Mission

Turn one factual closeout input into a final opportunity state:

- `status: applied` for submitted/applied opportunities.
- `status: archived` for no-submission, closed, skipped, expired, duplicate, obsolete, superseded, withdrawn, rejected-with-no-active-follow-up, or otherwise inactive opportunities.

The closeout input is evidence. Preserve it and mark it complete or paused; do not delete it.

## Required inputs

The launcher prompt should provide:

- `closeout_input_path`
- `opportunity_path`
- `stem`
- `title`
- `status`
- `proposed_status`
- `proposed_result_status`
- `priority`

Process only those paths. Do not scan or close other opportunities in the same session.

## Required orientation

Read, in this order:

1. `~/personal-vault/_meta/schema.md`
2. `~/personal-vault/_meta/index.md`
3. `~/personal-vault/_meta/log.md`
4. `~/personal-vault/_meta/workflows/opportunities/opportunity-closing-workflow.md`
5. `~/personal-vault/_meta/templates/opportunity-final-result-section-template.md`
6. The provided `closeout-input.md`
7. The provided `opportunity.md`

Read application, preparation, post-application, linked project, and pending-decision files only as needed to validate the closeout facts and cleanup.

## Validation rules

Before mutating final state, validate:

- The closeout input path basename is exactly `closeout-input.md`.
- The closeout input is live, not `closeout-input.example.md`.
- The closeout input frontmatter has `status: pending` unless this is an interactive manual repair of a paused input.
- `proposed_status` is `applied` or `archived`.
- `proposed_status: applied` normally has `proposed_result_status: submitted` plus a submission date or an explicit `unknown` submission date.
- `proposed_status: archived` uses inactive outcomes such as `awarded`, `rejected`, `expired`, `no-submission`, `withdrawn`, `superseded`, or `unknown`.
- Result evidence/source is present or explicitly unknown; do not invent it.
- The project closeout check is one of `not-needed`, `continue-project`, `close-project`, or `needs-review`.

If facts conflict, prefer pausing for Brayan over guessing.

## Insufficient-input behavior

If the input lacks required facts or has inconsistent proposed state:

1. Leave the opportunity final state unchanged.
2. Leave `opportunities/dashboard.md` unchanged.
3. Leave `opportunities/finished.md` unchanged.
4. Update the closeout input frontmatter to `status: paused`.
5. Append a clear `## Missing information / pause reason` section listing exact missing fields and conflicts.
6. Append a processing-log line with the date.
7. Notify Brayan concisely with the closeout input path and exact missing fields.

This prevents cron from relaunching the same underfilled input every day.

## Successful closeout procedure

When facts are sufficient:

1. Update `opportunity.md` frontmatter:
   - `updated: <today>`
   - `status: applied|archived`
   - `closed: <today>`
   - `submitted: <date or unknown>` when applied/submitted
   - `result_status`
   - `result_type`
   - `result_summary`
   - `submitted_artifacts` when applied/submitted
   - `final_artifacts`
   - `project_closeout_check`
   - `automation_route: none`
2. Add or update `## Final result` using the final-result template.
3. Link the processed closeout input: `[[opportunities/<slug>/closeout-input]]`.
4. Add a concise status-log entry.
5. Remove the finalized row from `opportunities/dashboard.md`.
6. Add one row to `opportunities/finished.md` with Finalized, Status, Result, Kind, Opportunity, Company/program, Linked project, and Follow-up.
7. Remove or update pending decisions only when clearly obsolete. If ambiguous, leave the decision and mention it in the notification.
8. For applied opportunities, create `opportunities/<slug>/post-application/` only when the input says follow-up tracking is needed or gives concrete follow-up contacts/platforms/status pages.
9. Mark `closeout-input.md` frontmatter `status: complete` and append a processing-log entry with changed files.
10. Append a concise `_meta/log.md` entry.
11. Verify dashboard removal, finished-register presence, opportunity final fields, and closeout input status.
12. Notify Brayan with final status, result summary, changed files, and follow-up.

## Dashboard and register rules

- Both `applied` and `archived` leave `opportunities/dashboard.md`.
- Both enter `opportunities/finished.md`.
- Use the single finished-opportunities register with Status and Result columns.
- Preserve the dashboard priority ordering for remaining rows.

## Project check semantics

When the closeout input or linked records mention projects, classify project impact as `not-needed`, `continue-project`, `close-project`, or `needs-review`. If the classification is `close-project`, create or fill that project's `/home/brayan/projects/<slug>/PROJECT_CLOSEOUT.md` when facts are sufficient, or notify Brayan with missing fields. Do not directly close the project from the opportunity-closing agent unless all project-closeout facts are already sufficient and the project workflow explicitly permits it.

Classify linked project implications as:

- `not-needed`: no linked project or only passive support.
- `continue-project`: project has independent value beyond this opportunity.
- `close-project`: project existed mainly to pursue this opportunity and should run the project closing workflow.
- `needs-review`: ambiguous; create/keep a pending decision.

Do not close broad ongoing projects merely because one related opportunity ended.

## Boundaries

This agent must not:

- submit an external application, form, public PR/post/report, bounty report, grant proposal, or payment;
- spend compute or money;
- invent result evidence, submission dates, artifacts, or external outcomes;
- auto-archive high-priority ambiguous opportunities without sufficient closeout input;
- process more than the one assigned opportunity;
- delete `closeout-input.md` after processing.

## Notification

Notify Brayan with:

- final status and result summary, or pause reason;
- closeout input path;
- opportunity path;
- dashboard/finished/register changes;
- pending decisions removed/updated or left for review;
- any post-application follow-up path.

## Verification checklist

Before finishing:

- closeout input was read first and preserved;
- opportunity note final state is `applied` or `archived`, or input is `paused` with missing info;
- `automation_route: none` is set on finalized records;
- submitted closeouts use `status: applied` with `result_status: submitted`;
- finalized row is absent from `opportunities/dashboard.md`;
- finalized row is present in `opportunities/finished.md`;
- `_meta/log.md` has a concise entry for successful closeout;
- no external action was taken.
