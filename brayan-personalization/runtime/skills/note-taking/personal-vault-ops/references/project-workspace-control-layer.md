# Project workspace vs vault control layer

Use this reference when Brayan asks to set up a project that has runnable code, cloned repositories, large logs, experiment artifacts, or autonomous agents.

## Convention

- `/home/brayan/projects/<repo-or-experiment>/` is the live runnable workspace.
- `~/personal_vault/projects/<slug>/README.md` is the project documentation/control note.
- The vault should link to code/log/status paths instead of becoming a checkout or artifact dump.

## Recommended live files for autonomous experiment projects

Inside `/home/brayan/projects/<experiment>/`:

- `FEEDBACK.md` — Brayan's live comments/corrections for the running agent. The agent checks this every cycle and before long work.
- `COMMANDER_STATUS.md` — concise current status, latest plan, blockers, and milestone log.
- `EXPERIMENTS.tsv` — structured history: timestamp, branch/path, hypothesis, command, status, metric, artifact bytes, runtime, notes.
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
