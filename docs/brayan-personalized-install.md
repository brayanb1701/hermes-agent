# Brayan Personalized Hermes Agent Install Guide

This guide installs Brayan's personalized Hermes Agent fork on a second computer so it can evolve independently, then later be compared and selectively merged back into a unified line.

## What this installs

Repository:
- `https://github.com/brayanb1701/hermes-agent`

Default branch for the independent machine:
- `second-computer-evolution`

Official upstream kept as a remote:
- `https://github.com/NousResearch/hermes-agent`

Default text model target:
- provider: `openai-codex`
- model: `gpt-5.5`

Important boundary:
- This guide installs source code and safe baseline configuration only.
- It does not copy API keys, Telegram bot tokens, chat IDs, private vault contents, local credentials, or machine-specific runtime state.
- Notes-intake vision fallback config is local runtime config, not hardcoded into the source install guide.

## Quick install

On Linux, macOS, or WSL2:

```bash
curl -fsSL https://raw.githubusercontent.com/brayanb1701/hermes-agent/main/scripts/install-brayan-personalized.sh | bash
```

The personalized installer defaults to the `second-computer-evolution` branch. That gives the new computer its own development line immediately.

If you want to install the current unified baseline instead:

```bash
curl -fsSL https://raw.githubusercontent.com/brayanb1701/hermes-agent/main/scripts/install-brayan-personalized.sh | bash -s -- --branch main
```

If you want a lab install that does not replace an existing `~/.hermes/hermes-agent` checkout:

```bash
curl -fsSL https://raw.githubusercontent.com/brayanb1701/hermes-agent/main/scripts/install-brayan-personalized.sh | bash -s -- --dir ~/.hermes/hermes-agent-lab
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

Expected for the independent evolution machine:

```text
branch: second-computer-evolution
origin:   brayanb1701/hermes-agent
upstream: NousResearch/hermes-agent
```

## Configure credentials locally

Run setup on the new machine:

```bash
hermes setup
```

Then set the default text model if setup did not already do it:

```bash
hermes config set model.provider openai-codex
hermes config set model.default gpt-5.5
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

Use the second-computer branch as its own evolutionary line:

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
curl -fsSL https://raw.githubusercontent.com/brayanb1701/hermes-agent/main/scripts/install-brayan-personalized.sh | bash
```

If the branch is wrong:

```bash
cd ~/.hermes/hermes-agent
git fetch origin
git switch second-computer-evolution
```

If local changes block an update:

```bash
cd ~/.hermes/hermes-agent
git status --short
git stash push --include-untracked -m "before-update"
git pull --ff-only origin second-computer-evolution
git stash apply
```
