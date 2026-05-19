# Project registration

Use when a capture might become a project.

Canonical vault workflow: `~/personal_vault/_meta/workflows/projects/project-registration-workflow.md`.

## Decision rule

A capture can become a project if it has a concrete outcome, plausible next action, and plausible stop condition. If it is committed current execution work, register `active`; otherwise register `seed`.

## Seed output

- `~/personal_vault/projects/<slug>/README.md`
- `status: seed`
- `external_workspace: null`
- row in `projects/backlog.md`
- no workspace created

## Active output

- project README with active required fields
- `/home/brayan/projects/<slug>/PROJECT_STATUS.md`
- `/home/brayan/projects/<slug>/PROJECT_CHANGELOG.md`
- row in `projects/dashboard.md`
- no backlog row

## Opportunity/project interaction

If a challenge/bounty/opportunity is also an execution project, use `opportunity-intake-agent` for the opportunity record and this skill for the project record. Link both; do not convert opportunity state semantics into project semantics.
