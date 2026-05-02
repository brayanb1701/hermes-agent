# Upstream Hermes PR Workspace Pattern

Use this when Brayan wants to turn a Hermes bugfix or framework improvement into an upstreamable PR, especially when the live `~/.hermes/hermes-agent` checkout is also used as the runtime/personalization repo.

## Why isolate upstream PR work

Brayan may have multiple Hermes sessions active at once. Keep public/upstreamable framework work separate from live runtime personalization so agents do not confuse:
- local runtime state, agents, skills, cron, plugins, sessions, and config;
- Brayan's private personalization branch;
- official upstream bugfix branches intended for NousResearch/hermes-agent.

## Canonical local layout for Brayan

- Live/runtime checkout: `/home/brayan/.hermes/hermes-agent`
  - Used to run Darwin/Hermes and hold personalization/runtime integration.
  - Personalization branch: `brayan/personal-hermes-customizations`.
- Isolated upstream PR clone: `/home/brayan/projects/hermes-agent-upstream-prs`
  - Used for official upstream PR branches only.
  - `upstream = git@github.com:NousResearch/hermes-agent.git`
  - `origin = git@github.com:brayanb1701/hermes-agent.git`
  - Local `main` should track `upstream/main`.
  - Push feature/fix branches to `origin`.

## Setup pattern

```bash
mkdir -p /home/brayan/projects
cd /home/brayan/projects

git clone git@github.com:NousResearch/hermes-agent.git hermes-agent-upstream-prs
cd hermes-agent-upstream-prs

git remote rename origin upstream
git remote add origin git@github.com:brayanb1701/hermes-agent.git
git fetch --all --prune

git checkout main
git branch --set-upstream-to=upstream/main main
git config remote.pushDefault origin
git config push.default current
git config pull.rebase true

git checkout -b fix/<short-bug-name> upstream/main
```

Prefer safe non-destructive setup commands. Avoid reset/clean during setup unless the target clone is confirmed disposable and Brayan approved destructive cleanup.

## Branch strategy

- Use one focused branch per logical upstream change.
- Good examples:
  - `fix/terminal-cwd-marker-poisoning`
  - `fix/checkpoint-stale-index-lock`
- Do not mix Brayan runtime personalization, vault edits, cron jobs, private IDs, or local config snapshots into upstream PR branches.
- If two fixes are related but separable, make separate PRs unless the implementation proves they are tightly coupled.

## Contribution rules to re-check from the repo

Before coding, read the live checkout's:
- `CONTRIBUTING.md`
- `AGENTS.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- relevant `.github/workflows/*.yml`

Typical requirements observed in Hermes Agent:
- Bug fixes, robustness, cross-platform compatibility, and security hardening are high-priority contributions.
- Keep PRs focused: one logical change per PR.
- Use Conventional Commits: `fix(scope): description`, `test(scope): description`, etc.
- Add regression tests for bug fixes.
- Use the repo's canonical test wrapper when present: `scripts/run_tests.sh`, with focused tests first and the full suite before pushing.
- Include reproduction steps, proof of fix, platform tested, and cross-platform impact in the PR body.
- For file paths/state, use `get_hermes_home()` / `display_hermes_home()` rather than hardcoded `~/.hermes`; tests must not write to the real Hermes home.
- For terminal/process changes, consider Linux/macOS/WSL2/Windows differences and avoid unsafe shell interpolation.

## Vault tracking

When the work is a pending Darwin/Hermes improvement, record it in the vault control layer, usually:
- `~/personal_vault/projects/darwin-improvement/README.md`
- append a concise structural entry to `~/personal_vault/_meta/log.md`

Record workspace path, branch names, live-checkout separation, contribution discipline, and the next action. Do not create a new vault project for every individual bugfix unless it becomes a substantial independent project.

## Verification checklist

- [ ] `git -C /home/brayan/projects/hermes-agent-upstream-prs status --short --branch` is clean or only contains intended PR changes.
- [ ] Current branch is not `main` when editing code.
- [ ] `git remote -v` shows `origin` as Brayan fork and `upstream` as official repo.
- [ ] Branch base is `upstream/main`.
- [ ] Focused regression test fails before the fix and passes after.
- [ ] `scripts/run_tests.sh` passes before pushing/opening PR.
- [ ] PR body follows `.github/PULL_REQUEST_TEMPLATE.md`.
