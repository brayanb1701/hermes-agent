# Project-management lifecycle implementation pattern

Session source: Brayan reviewed a project lifecycle proposal and clarified how project automation should differ from the opportunity workflow.

Use this reference when planning or implementing Brayan's project-management lifecycle across `~/personal-vault`, `/home/brayan/projects`, and Hermes runtime automation.

## Key design decisions

- Do not copy the opportunity architecture one-to-one.
  - Opportunities can keep separate specialized skills/agents for intake, preparation, and closing.
  - Projects should use one umbrella class-level skill, recommended `personal-project-management`, with references to registration, activation, review, pausing/reopening, and closing workflows.
- Project registration is the entry point.
  - A capture can become `seed` or directly `active` depending on evidence and commitment.
  - `seed` projects live only in `~/personal-vault/projects/<slug>/README.md` and a backlog surface.
  - `active` projects require an external workspace under `/home/brayan/projects/<slug>/`.
- Active project work happens in `/home/brayan/projects/<slug>/`; the vault project note is only the control/documentation layer.
- Use one non-active register for seed + paused projects: `projects/backlog.md`.
  - `projects/dashboard.md` is active-only.
  - `projects/finished.md` is complete + archived.
  - Do not create both `backlog.md` and `incubation.md` unless Brayan later asks.
- `incubating` is not a canonical project status.
  - Use only `seed`, `active`, `paused`, `complete`, `archived`.
- Preserve Web Friction Interrupter as `area: personal`; do not add `productivity` as a schema area for this case.

## Workspace control-file pattern

For every active project workspace, require a lightweight deterministic state signal:

```text
/home/brayan/projects/<slug>/PROJECT_CHANGELOG.md
```

Required from activation onward:

```text
/home/brayan/projects/<slug>/PROJECT_STATUS.md       # concise current-state snapshot agents read first
/home/brayan/projects/<slug>/PROJECT_CHANGELOG.md    # chronological, parser-friendly activity/state signal
```

Optional/requested handoff files:

```text
/home/brayan/projects/<slug>/PROJECT_CLOSEOUT.md     # workspace closeout handoff/input
/home/brayan/projects/<slug>/PROJECT_REOPEN.md       # reopen/resume handoff
```

Important distinction:

- `PROJECT_CLOSEOUT.md` is a workspace handoff/input from where development happened.
- `personal-vault/projects/<slug>/closeout.md` is the canonical durable vault closeout.
- They are not duplicate purposes; the workspace file feeds the vault closeout and is preserved/marked processed.

## Runtime automation pattern

Prefer this shape:

```text
~/.hermes/skills/automation-agents/projects/personal-project-management/SKILL.md
~/.hermes/agents/project-management/prompt-template.md
~/.hermes/scripts/project_scaffold.py
~/.hermes/scripts/project_review_scan.py
~/.hermes/scripts/project_state_audit.py
cron job: darwin-project-management-agent
```

The scanner should be mechanical and wake-gated:

- inspect project READMEs, dashboard/backlog/finished, workspace changelogs, pending closeout/reopen files, and stale review dates;
- launch bounded independent Hermes sessions only for actionable items;
- emit `wakeAgent: false` when no work exists.

## Drift-prevention contract

Every project state transition must update all relevant surfaces in one pass:

- Seed registration: project README + `projects/backlog.md`.
- Activation: project README + workspace `PROJECT_STATUS.md` + workspace `PROJECT_CHANGELOG.md` + `projects/dashboard.md` + remove backlog row.
- Pause: project README + workspace `PROJECT_STATUS.md` + workspace `PROJECT_CHANGELOG.md` + `projects/backlog.md` + remove dashboard row.
- Close/archive/complete: `PROJECT_CLOSEOUT.md` + project README + vault closeout + `projects/finished.md` + remove dashboard/backlog row + decisions cleanup + `_meta/log.md`.
- Reopen/resume: `PROJECT_REOPEN.md` + project README + workspace `PROJECT_STATUS.md` + workspace `PROJECT_CHANGELOG.md` + dashboard or new project slug + link previous closeout.

## Implementation/verification pattern

For a full vault + Hermes runtime workflow rollout, use this order:

1. Implement vault schema/docs/templates/register surfaces first.
2. Implement runtime skill/prompt/script surfaces second.
3. Compile scripts and run fixture tests against `/tmp/...` vault/workspace roots before touching real project records.
4. Normalize real dashboards/registers only after deterministic scripts exist.
5. Scaffold active workspaces with a dry-run first, then apply and inspect at least one generated `PROJECT_STATUS.md` and `PROJECT_CHANGELOG.md` for rendered real values.
6. Create/update cron jobs with the `cronjob` tool, never by manually editing cron JSON.
7. Sync `~/.hermes` runtime assets into the Hermes personalization bundle and run diff checks there too.
8. Final checks should include the focused audit (`project_state_audit.py --json` or `--dry-run`), the broader vault audit, skill resolution, config check, cron listing, and retired-term searches.

Interpretation rule: a focused lifecycle audit can be clean while the broader vault audit still reports unrelated pre-existing issues. Report that distinction instead of treating unrelated general-vault findings as failure of the workflow migration.

## Planning pitfall

When Brayan asks for an implementation plan for vault + Hermes runtime work, include the personalization-bundle sync path explicitly. Runtime files under `~/.hermes/skills`, `~/.hermes/agents`, `~/.hermes/scripts`, and cron definitions must be synced into `~/.hermes/hermes-agent/brayan-personalization/runtime/...` on `brayan/personal-hermes-customizations` after verification. This is part of the plan, not an afterthought.