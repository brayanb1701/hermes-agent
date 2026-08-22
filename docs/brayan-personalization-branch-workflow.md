# Brayan Hermes personalization branch workflow

This document is the canonical repo-local rulebook for Brayan's personal Hermes runtime customizations.

## Branch boundary

`main` is the clean source/upstream-tracking line for Brayan's fork.

`second-computer-evolution` is the only branch that should contain Brayan/Darwin local runtime personalization, including:

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

1. Verify the live checkout is clean. If an older/raw update moved it to `main`, use the remote personalization branch as the recovery base.
2. Refuse to run during an in-progress merge/rebase.
3. Refuse unrelated dirty source changes.
4. Fetch official Hermes updates:
   ```bash
   git fetch upstream main
   ```
5. Fetch the fork's personalization branch:
   ```bash
   git fetch origin second-computer-evolution
   ```
6. Fast-forward the local personalization branch from `origin/second-computer-evolution` if needed.
7. Sync the current live local personalization state into `brayan-personalization/runtime/`:
   ```bash
   scripts/sync-brayan-personalization.py
   ```
8. If the sync changed only allowed personalization files, commit them on `second-computer-evolution`.
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
    git push --force-with-lease origin HEAD:second-computer-evolution
    ```
12. When the verified candidate differs from the live checkout, schedule a detached transient unit that runs:
    ```bash
    hermes update --branch second-computer-evolution --yes --no-backup
    ```
    This activates the candidate through Hermes' supported updater, refreshes dependencies/config, and restarts the gateway without killing the cron run before it records its result.
13. Emit compact JSON:
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

Use the same deterministic script when triggering the complete workflow manually:

```bash
/home/brayan/.hermes/hermes-agent/venv/bin/python \
  /home/brayan/.hermes/scripts/hermes_upstream_rebase_ci.py

# Then inspect the JSON result/log and, when activation was scheduled:
systemctl --user status 'hermes-personalization-activate-*' --no-pager
hermes gateway status
```

## Installing on another already-installed Hermes machine

```bash
cd ~/.hermes/hermes-agent
git fetch origin
git switch second-computer-evolution
git pull --ff-only origin second-computer-evolution
scripts/apply-brayan-personalization.py          # dry run
scripts/apply-brayan-personalization.py --apply  # writes into ~/.hermes with backups
hermes config check
```

Restore secrets locally after applying. Do not commit `.env`, `auth.json`, provider credentials, Telegram tokens, chat IDs, logs, sessions, state DBs, venvs, checkpoints, model caches, or cron output.

Keep `updates.branch: second-computer-evolution` in `~/.hermes/config.yaml`. This makes both terminal `hermes update` and gateway `/update` target the integration branch instead of switching the live checkout to `main`.

## Recovery if personalization lands on main

If `brayan-personalization/` or equivalent local runtime snapshots accidentally land on `main`:

```bash
cd ~/.hermes/hermes-agent
BAD_COMMIT=$(git rev-parse HEAD)
git branch -f second-computer-evolution "$BAD_COMMIT"
git push --force-with-lease origin second-computer-evolution
git switch main
git reset --hard <previous-clean-main-commit>
git push --force-with-lease origin main
```

Then add/verify a guard such as `.githooks/pre-push` and keep this document linked from `AGENTS.md`.
