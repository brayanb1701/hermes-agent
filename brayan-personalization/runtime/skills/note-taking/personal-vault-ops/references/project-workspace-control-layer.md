# Project workspace vs vault control layer

Use this reference when Brayan asks to set up a project that has runnable code, cloned repositories, large logs, experiment artifacts, or autonomous agents.

## Convention

- `/home/brayan/projects/<repo-or-experiment>/` is the live runnable workspace.
- `~/personal_vault/projects/<slug>/README.md` is the project documentation/control note.
- The vault should link to code/log/status paths instead of becoming a checkout or artifact dump.

## Recommended live files for active project workspaces

Inside `/home/brayan/projects/<experiment>/`:

- `PROJECT_STATUS.md` — concise current snapshot an agent should read after the vault project README: current objective, status, next action, blockers, active branch/files, and handoff notes.
- `PROJECT_CHANGELOG.md` — chronological, parser-friendly update log for meaningful project changes; stale-project scripts can use it to detect inactivity before proposing pause/close/review actions.
- `FEEDBACK.md` — Brayan's live comments/corrections for a running autonomous agent. The agent checks this every cycle and before long work when the project uses that pattern.
- `COMMANDER_STATUS.md` — optional commander-specific status for autonomous experiment loops; do not use it as the only current-state source if `PROJECT_STATUS.md` exists.
- `EXPERIMENTS.tsv` — structured experiment history when the project is experiment-heavy: timestamp, branch/path, hypothesis, command, status, metric, artifact bytes, runtime, notes.
- Additional logs/artifacts as needed, kept out of the vault unless a concise summary/postmortem is promoted.

## Vault note should include

- Objective and success levels.
- Constraints and risks.
- Links to opportunity records or domain maps when relevant.
- Absolute live workspace paths.
- Stop/completion condition.
- Human-review requirements before external submission.

## Pitfall

Do not create or clone full software repositories inside `~/personal_vault/projects/`. That folder is for true project notes and control documentation, not for bulky code workspaces.
