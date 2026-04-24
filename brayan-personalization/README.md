# Brayan Hermes Personalization Bundle

This directory stores Brayan/Darwin runtime behavior that normally lives outside the Hermes source checkout, so a new machine can install the fork and then apply the same local assistant configuration.

## What is included

The generated snapshot lives under `brayan-personalization/runtime/` and currently includes:

- `config.yaml` — Brayan's Hermes config, including model defaults, platform toolsets, notes-intake config, enabled plugins, and small channel prompts.
- `SOUL.md` — Darwin's local persona/operating charter loaded from Hermes home.
- `channel_directory.json` — known messaging targets/channels.
- `cron/jobs.json` — portable cron job definitions with volatile run state reset.
- `agents/` — file-defined agent prompt templates.
- `skills/` — installed/local skills, including Darwin-specific agent skills and vault workflows.
- `plugins/` — local plugins such as `notes_preprocessor`.
- `scripts/` — local dispatcher/CI scripts such as job tailoring and upstream rebase CI.

## What is intentionally excluded

Do **not** store these in Git:

- `.env`
- `auth.json`
- provider OAuth/session credentials
- Telegram/Discord/Slack bot tokens
- sessions, logs, state databases, checkpoints, model caches, venvs, and generated cron output

The fork is private, but credentials still belong only on each machine.

## Updating the snapshot from a live machine

From the repo checkout:

```bash
cd ~/.hermes/hermes-agent
scripts/sync-brayan-personalization.py
```

The daily `hermes-upstream-rebase-ci` script also runs this sync and commits changes to **`brayan/personal-hermes-customizations` only** when the personalization bundle changed. Its required order is: fetch `upstream/main`, fetch the fork personalization branch, sync/commit current local personalization on that branch, rebase the branch onto `upstream/main`, test, then push only `HEAD:brayan/personal-hermes-customizations`. It must never push this bundle to `main`.

See `docs/brayan-personalization-branch-workflow.md` for the full branch/CI rulebook.

## Applying to an already-installed Hermes on another machine

From that machine's Hermes fork checkout:

```bash
cd ~/.hermes/hermes-agent
git switch brayan/personal-hermes-customizations
git pull --ff-only origin brayan/personal-hermes-customizations
scripts/apply-brayan-personalization.py          # dry run
scripts/apply-brayan-personalization.py --apply  # copy into ~/.hermes
```

Then restore local secrets/auth and restart/check Hermes:

```bash
hermes login --provider openai-codex   # or whichever providers are needed
hermes config check
hermes gateway restart
hermes gateway status
```

If the new machine should use a different Telegram bot/chat/vault path, edit `~/.hermes/config.yaml` after applying.

## Applying without replacing existing files

The apply script creates timestamped backups by default, e.g. `config.yaml.bak-YYYYMMDDTHHMMSSZ`. Use `--no-backup` only when you intentionally want direct overwrite.
