---
name: codex
description: "Delegate coding to OpenAI Codex CLI (features, PRs)."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Coding-Agent, Codex, OpenAI, Code-Review, Refactoring]
    related_skills: [claude-code, hermes-agent]
---

# Codex CLI

Default to Herdr for managing independent sessions and harnesses. Load multi-project-coordinator for organization and herdr for commands; use native headless modes for explicit batch/structured-output tasks.

Preserve existing subscription auth. After integration installation, inspect the screen for a SessionStart hook approval even when Herdr reports idle; obtain authorization before trusting it.

Delegate coding tasks to [Codex](https://github.com/openai/codex) via the Hermes terminal. Codex is OpenAI's autonomous coding agent CLI.

## When to use

- Building features
- Refactoring
- PR reviews
- Batch issue fixing

Requires the codex CLI and a git repository.

## Prerequisites

- Codex installed: `npm install -g @openai/codex`
- Existing Codex subscription or API authentication configured
- **Must run inside a git repository** — Codex refuses to run outside one
- Use `pty=true` for the interactive TUI (`codex` / `codex resume`). `codex exec` is non-interactive and can run without PTY, including in background/process/systemd supervisors.

## One-Shot Tasks

```
terminal(command="codex exec 'Add dark mode toggle to settings'", workdir="~/project", pty=true)
```

For scratch work (Codex needs a git repo):
```
terminal(command="cd $(mktemp -d) && git init && codex exec 'Build a snake game in Python'", pty=true)
```

## Managed long tasks

Use a named Codex agent in an owned Herdr pane, following multi-project-coordinator and herdr. For explicit headless batch jobs, capture output and use completion notifications.

## Key Flags

| Flag | Effect |
|------|--------|
| `exec "prompt"` | One-shot execution, exits when done |
| `exec resume --last "prompt"` | Resume the most recent recorded exec session; useful for supervisor loops |
| `--approve-for-me` | Sandboxed but auto-approves file changes in workspace |
| `--dangerously-bypass-approvals-and-sandbox` | No sandbox, no approvals (fastest, most dangerous; use only when the environment/workspace is trusted) |
| `-C, --cd <DIR>` | Working root for the agent |
| `--add-dir <DIR>` | Additional writable directory |
| `-c key=value` | Override config, e.g. `-c 'model_reasoning_effort="high"'` |
| `--json` / `--output-last-message FILE` | Machine-readable logs and final response capture for supervisors |

## PR Reviews

Clone to a temp directory for safe review:

```
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && codex review --base origin/main", pty=true)
```

## Parallel Issue Fixing with Worktrees

Assign one authorized worktree or disjoint write scope per worker; launch named Codex agents in the project workspace using the coordinator organization policy. Verify results before any separately authorized publish or cleanup.

## Batch PR Reviews

```
# Fetch all PR refs
terminal(command="git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'", workdir="~/project")

# Review multiple PRs in parallel
terminal(command="codex exec 'Review PR #86. git diff origin/main...origin/pr/86'", workdir="~/project", background=true, pty=true)
terminal(command="codex exec 'Review PR #87. git diff origin/main...origin/pr/87'", workdir="~/project", background=true, pty=true)

# Post results
terminal(command="gh pr comment 86 --body '<review>'", workdir="~/project")
```

## Rules

1. **PTY depends on mode** — use `pty=true` for interactive TUI sessions; `codex exec` can run non-interactively and is suitable for background/systemd supervisors.
2. **Git repo required** — Codex won't run outside a git directory. Use `mktemp -d && git init` for scratch
3. **Use `exec` for one-shots** — `codex exec "prompt"` runs and exits cleanly
4. **`--approve-for-me` for building** — auto-approves changes within the sandbox
5. **Herdr for managed long tasks** — use named agents and native waits; headless batch jobs use completion notifications
6. **Don't interfere without authorization** — inspect owned agents through Herdr; for headless jobs inspect captured output and completion notifications. A status/analysis request is not permission to kill, restart, create STOP files, edit prompts, or change policy unless there is immediate safety/spend risk or Brayan explicitly asks.
7. **Keep project policy out of this generic skill** — if a Codex run needs cloud GPUs, paid APIs, challenge-specific budgets, watchdogs, STOP files, or experiment run cards, put that policy in the project workspace (`AGENTS.md`, `RUNBOOK.md`, status/control files) or a class-level paid-compute/autoresearch skill. Do not pollute the generic Codex skill with one-project details.
8. **Remote paid jobs need separate verification** — stopping a local Codex process/supervisor does not prove external work stopped. Check provider-side app/task/billing state separately before saying spend is contained.
9. **Parallel is fine** — run multiple Codex processes at once for batch work
