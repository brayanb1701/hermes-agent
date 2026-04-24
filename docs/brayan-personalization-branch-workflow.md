# Brayan Hermes personalization branch workflow

This document is the canonical repo-local rulebook for Brayan's personal Hermes runtime customizations.

## Branch boundary

`main` is the clean source/upstream-tracking line for Brayan's fork.

`brayan/personal-hermes-customizations` is the only branch that should contain Brayan/Darwin local runtime personalization, including:

- `brayan-personalization/runtime/config.yaml`
- `brayan-personalization/runtime/SOUL.md`
- `brayan-personalization/runtime/channel_directory.json`
- `brayan-personalization/runtime/cron/jobs.json`
- `brayan-personalization/runtime/agents/`
- `brayan-personalization/runtime/skills/`
- `brayan-personalization/runtime/plugins/`
- `brayan-personalization/runtime/scripts/`
- `scripts/sync-brayan-personalization.py`
- `scripts/apply-brayan-personalization.py`

Do not commit or push these personalization assets to `main`.

## Daily CI intended behavior

The daily Hermes upstream CI for this setup should do this, in order:

1. Verify the checkout is on `brayan/personal-hermes-customizations`.
2. Refuse to run during an in-progress merge/rebase.
3. Refuse unrelated dirty source changes.
4. Fetch official Hermes updates:
   ```bash
   git fetch upstream main
   ```
5. Fetch the fork's personalization branch:
   ```bash
   git fetch origin brayan/personal-hermes-customizations
   ```
6. Fast-forward the local personalization branch from `origin/brayan/personal-hermes-customizations` if needed.
7. Sync the current live local personalization state into `brayan-personalization/runtime/`:
   ```bash
   scripts/sync-brayan-personalization.py
   ```
8. If the sync changed only allowed personalization files, commit them on `brayan/personal-hermes-customizations`.
9. Rebase the personalization branch onto the latest official upstream source:
   ```bash
   git rebase upstream/main
   ```
   This preserves Brayan's commits, including the updated local personalization snapshot, on top of official Hermes.
10. Run focused verification:
    - `py_compile` for personalization scripts
    - targeted gateway/cron/plugin tests
    - `hermes config check`
11. Push only the personalization branch:
    ```bash
    git push --force-with-lease origin HEAD:brayan/personal-hermes-customizations
    ```
12. Emit compact JSON:
    - `wakeAgent: false` when successful or no-op
    - `wakeAgent: true` with diagnostics when conflicts/tests/pushes fail

The CI must never push personalization changes to `origin/main`.

## Why the order matters

The point is not merely to save local files. The branch should represent:

```text
latest official upstream Hermes
+ Brayan's source customizations
+ latest sanitized local runtime personalization snapshot
```

So the snapshot should be committed on the personalization branch, then that branch should be rebased onto `upstream/main` when upstream has moved. That keeps the branch installable and reviewable while preserving local skills, cronjobs, plugins, agents, and scripts.

## Manual update commands

Use this when doing the workflow manually:

```bash
cd ~/.hermes/hermes-agent
git switch brayan/personal-hermes-customizations
git fetch upstream main
git fetch origin brayan/personal-hermes-customizations
git merge --ff-only origin/brayan/personal-hermes-customizations
scripts/sync-brayan-personalization.py
git status --short
# if only allowed personalization files changed:
git add brayan-personalization scripts/sync-brayan-personalization.py scripts/apply-brayan-personalization.py
git commit -m "chore: sync Brayan Hermes personalization snapshot"
git rebase upstream/main
python -m py_compile scripts/sync-brayan-personalization.py scripts/apply-brayan-personalization.py
hermes config check
git push --force-with-lease origin HEAD:brayan/personal-hermes-customizations
```

## Installing on another already-installed Hermes machine

```bash
cd ~/.hermes/hermes-agent
git fetch origin
git switch brayan/personal-hermes-customizations
git pull --ff-only origin brayan/personal-hermes-customizations
scripts/apply-brayan-personalization.py          # dry run
scripts/apply-brayan-personalization.py --apply  # writes into ~/.hermes with backups
hermes config check
```

Restore secrets locally after applying. Do not commit `.env`, `auth.json`, provider credentials, Telegram tokens, chat IDs, logs, sessions, state DBs, venvs, checkpoints, model caches, or cron output.

## Recovery if personalization lands on main

If `brayan-personalization/` or equivalent local runtime snapshots accidentally land on `main`:

```bash
cd ~/.hermes/hermes-agent
BAD_COMMIT=$(git rev-parse HEAD)
git branch -f brayan/personal-hermes-customizations "$BAD_COMMIT"
git push --force-with-lease origin brayan/personal-hermes-customizations
git switch main
git reset --hard <previous-clean-main-commit>
git push --force-with-lease origin main
```

Then add/verify a guard such as `.githooks/pre-push` and keep this document linked from `AGENTS.md`.
