# Brayan Personalized Hermes Agent Install Guide

This guide installs Brayan's maintained personalized Hermes Agent branch. The same installer can target an experimental branch explicitly on a second computer.

## What this installs

Repository:
- `https://github.com/brayanb1701/hermes-agent`

Default maintained branch:
- `brayan/personal-hermes-customizations`

Official upstream kept as a remote:
- `https://github.com/NousResearch/hermes-agent`

Update safety:
- `updates.branch` is set to the branch selected by the installer, so later `hermes update` and gateway `/update` calls do not silently switch back to `main`.
- The installer does not pin a model version; `hermes setup`, the safe local config, and the current model catalog determine supported models.

Important boundary:
- This guide installs source code and safe baseline configuration only.
- It does not copy API keys, Telegram bot tokens, chat IDs, private vault contents, local credentials, or machine-specific runtime state.
- Notes-intake vision fallback config is local runtime config, not hardcoded into the source install guide.

## Quick install

On Linux, macOS, or WSL2:

```bash
curl -fsSL https://raw.githubusercontent.com/brayanb1701/hermes-agent/brayan%2Fpersonal-hermes-customizations/scripts/install-brayan-personalized.sh | bash
```

The installer defaults to `brayan/personal-hermes-customizations`, applies the safe personalization bundle on a fresh install while preserving setup/auth config, and records that branch as the future update target.

If you want an independent experimental line on another computer instead:

```bash
curl -fsSL https://raw.githubusercontent.com/brayanb1701/hermes-agent/brayan%2Fpersonal-hermes-customizations/scripts/install-brayan-personalized.sh | bash -s -- --branch second-computer-evolution
```

If you want a lab install that does not replace an existing `~/.hermes/hermes-agent` checkout:

```bash
curl -fsSL https://raw.githubusercontent.com/brayanb1701/hermes-agent/brayan%2Fpersonal-hermes-customizations/scripts/install-brayan-personalized.sh | bash -s -- --dir ~/.hermes/hermes-agent-lab --hermes-home ~/.hermes-lab
```

## After install

Reload your shell:

```bash
source ~/.bashrc  # or: source ~/.zshrc
```

Verify Hermes:

```bash
hermes config check
hermes --version
```

Verify Git remotes and branch:

```bash
cd ~/.hermes/hermes-agent
git status --short --branch
git remote -v
git branch --show-current
```

Expected for the default maintained installation:

```text
branch: brayan/personal-hermes-customizations
origin:   brayanb1701/hermes-agent
upstream: NousResearch/hermes-agent
```

## Configure credentials locally

Run setup on the new machine:

```bash
hermes setup
```

Verify the update target and choose a currently supported model if setup did not already do so:

```bash
hermes config get updates.branch
hermes model
```

Do not commit secrets. Keep these local:
- API keys
- provider credentials
- Telegram/Discord/Slack tokens
- personal chat IDs
- machine-specific paths
- vault sync credentials

## Optional: connect the personal vault

If this computer should use the same Obsidian/LLM vault, sync or clone the vault separately. The Hermes source repo does not include the vault.

Recommended default path:

```text
~/personal_vault
```

After syncing it, run:

```bash
test -d ~/personal_vault && echo "vault present"
```

## Development workflow on the second computer

This section is optional. Use the second-computer branch as its own evolutionary line only when intentionally selected with `--branch second-computer-evolution`:

```bash
cd ~/.hermes/hermes-agent
git switch second-computer-evolution
```

Before making changes:

```bash
git fetch upstream origin
git status --short --branch
```

For each experiment:

```bash
git switch -c experiment/<short-name>
# edit, test, commit
git push -u origin experiment/<short-name>
```

When an experiment is good enough for the second-computer line:

```bash
git switch second-computer-evolution
git merge --no-ff experiment/<short-name>
git push origin second-computer-evolution
```

Keep the line updated from official Hermes when practical:

```bash
git fetch upstream origin
git rebase upstream/main
git push --force-with-lease origin second-computer-evolution
```

On Brayan's primary machine, do not use that manual live-checkout rebase. The scheduled `hermes-upstream-rebase-ci` job rebases an isolated candidate, verifies it, pushes with an exact lease, and activates it through the configured fork branch. See `docs/brayan-personalization-branch-workflow.md`.

If a rebase is risky or conflicts heavily, stop and inspect rather than forcing it:

```bash
git status
git diff
git rebase --abort  # if needed
```

## Compare evolution lines later

On the original machine or a clean checkout:

```bash
git fetch origin upstream
git log --oneline --left-right --cherry-pick main...origin/second-computer-evolution
git diff main...origin/second-computer-evolution --stat
git diff main...origin/second-computer-evolution
```

Good candidates to keep:
- changes with passing tests
- changes that reduce token use or operational friction
- plugin/config/skill/script solutions that avoid unnecessary base-code divergence
- source changes that are general enough to upstream or preserve in the fork

Risky candidates:
- hardcoded personal IDs
- secrets or credentials
- machine-specific paths outside documented config
- changes that make updates from `upstream/main` harder
- untested behavior changes in gateway/session/cron logic

## Merge the best parts into a unified point

Create an integration branch from the chosen baseline:

```bash
git switch main
git pull --ff-only origin main
git switch -c integration/unify-evolution-lines
```

Selectively bring in good commits:

```bash
git cherry-pick <commit-sha>
# or inspect/apply specific hunks:
git checkout origin/second-computer-evolution -- path/to/file
```

Run targeted tests. On Brayan's current primary machine, use:

```bash
/home/brayan/.hermes/hermes-agent/venv/bin/python -m pytest tests/cron/test_cron_script.py tests/gateway/test_notes_intake_pipeline.py tests/plugins/test_notes_preprocessor_intake.py -q
/home/brayan/.local/bin/hermes config check
```

On a different machine, use that machine's Hermes venv path or simply:

```bash
python -m pytest tests/cron/test_cron_script.py tests/gateway/test_notes_intake_pipeline.py tests/plugins/test_notes_preprocessor_intake.py -q
hermes config check
```

Push the integration branch:

```bash
git push -u origin integration/unify-evolution-lines
```

After review, fast-forward or merge into `main` and push:

```bash
git switch main
git merge --ff-only integration/unify-evolution-lines || git merge --no-ff integration/unify-evolution-lines
git push origin main
```

## Recovery commands

If install was interrupted:

```bash
rm -rf ~/.hermes/hermes-agent
curl -fsSL https://raw.githubusercontent.com/brayanb1701/hermes-agent/brayan%2Fpersonal-hermes-customizations/scripts/install-brayan-personalized.sh | bash
```

If the maintained branch is wrong:

```bash
cd ~/.hermes/hermes-agent
git fetch origin
git switch brayan/personal-hermes-customizations
hermes config set updates.branch brayan/personal-hermes-customizations
```

If local changes block an update:

```bash
cd ~/.hermes/hermes-agent
git status --short
git stash push --include-untracked -m "before-update"
hermes update --branch brayan/personal-hermes-customizations --yes
git stash apply
```
