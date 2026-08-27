# Calcifer remote Hermes helper

Use this reference on Brayan's DarkArmy machine when work should execute on the `calcifer` Tailscale peer and survive the current SSH/Hermes session.

## Installed interface

- Command on `PATH`: `/home/brayan/.local/bin/calcifer-agent`
- Canonical script: `/home/brayan/.hermes/scripts/calcifer_agent.py`
- Transport: the existing `ssh calcifer` alias over Tailscale
- Remote state: `/home/brayan/.local/state/calcifer-agent/goals/<name>/`
- Tests: `/home/brayan/.hermes/scripts/tests/test_calcifer_agent.py`

The personalization bundle preserves the canonical script. If the PATH entry is ever missing after a restore, recreate it with:

```bash
ln -s /home/brayan/.hermes/scripts/calcifer_agent.py /home/brayan/.local/bin/calcifer-agent
```

Run `calcifer-agent doctor` before diagnosing connection/runtime failures. Run `calcifer-agent permissions` to inspect Calcifer's live approval settings and the helper's policies.

Names are user-chosen identifiers such as `fieldlink-tests` or `market-research`: 1–48 lowercase letters, numbers, or hyphens. They become tmux session/systemd unit identifiers; they are not Hermes task types.

## Reconnectable interactive session (tmux)

```bash
calcifer-agent session <name>
calcifer-agent session <name> --workdir /remote/project
calcifer-agent attach <name>
calcifer-agent stop <name> --session
```

Detach without stopping Hermes with `Ctrl-b`, then `d`. Reattach later with `calcifer-agent attach <name>`.

When calling from a non-interactive Hermes terminal tool, always start detached so the tool call does not try to attach a TTY:

```bash
calcifer-agent session <name> --detach --workdir /remote/project
```

The default session uses Calcifer's persisted approval mode. If Hermes reaches an operation that still needs human approval, it waits in tmux; Brayan can attach and decide. Add `--trusted` only when Brayan explicitly wants process-scoped `--yolo` for that session.

## Detached autonomous goal (systemd)

```bash
calcifer-agent run <name> --budget 4h --workdir /remote/project 'SELF-CONTAINED GOAL'
calcifer-agent run <name> --file /local/path/goal.md --budget 1d
calcifer-agent run <name> --reasoning high --trusted --file /local/path/goal.md --budget 1d
printf '%s\n' 'SELF-CONTAINED GOAL' | calcifer-agent run <name> --budget 90m
```

Management:

```bash
calcifer-agent list
calcifer-agent status <name>
calcifer-agent logs <name>
calcifer-agent logs <name> --follow
calcifer-agent stop <name> --goal
```

The remote process runs under Calcifer's systemd user manager. Calcifer has user lingering enabled, so it survives the initiating SSH connection and having no logged-in shell. `--budget` is a wall-clock safety ceiling; the default is `4h`, and `0` means unlimited. Use `--reasoning none|minimal|low|medium|high|xhigh` to pin reasoning effort for a detached goal instead of changing Calcifer's global default.

## Permission policies

The helper makes trust explicit instead of silently changing Calcifer's global config:

- `run` (default): **guarded**. Before launch, the helper verifies that Calcifer's `approvals.single_query_mode` is exactly `deny` and refuses to start otherwise. Hermes single-query mode has no human present, so dangerous commands are deterministically denied rather than waiting for approval. Safe commands continue normally.
- `run --trusted`: **trusted autonomous**. Adds process-scoped `--yolo`, bypassing ordinary approval prompts only for that Hermes process. Hermes hardline catastrophic-command blocks still apply.
- `session` (default): **interactive approvals**. Calcifer's normal approval configuration applies. Detach freely; reattach if human judgment is needed.
- `session --trusted`: **trusted interactive**. Adds process-scoped `--yolo` for that tmux process.

Prefer guarded goals for research, read-only audits, builds, and other work that should fail closed. Prefer tmux when the task may legitimately require risky changes but Brayan wants to approve them. Use `--trusted` only after the task scope and working directory are explicit; it is deliberately visible in command lines, metadata, and status output.

Do not change global `approvals.mode` or `approvals.single_query_mode` just to launch one Calcifer job. The helper's process-scoped modes avoid affecting the gateway or unrelated sessions.

## Agent handoff requirements

A detached goal starts a fresh Hermes session and does not inherit the caller's conversation. Supply a self-contained prompt containing:

- objective and success criteria
- exact remote repository/workspace path
- constraints, non-goals, and permission expectations
- required verification commands or artifacts
- where to save results

After starting a goal, report the chosen name, mode, permission policy, budget, and the exact status/log commands. Verify launch with `calcifer-agent status <name>`; do not claim completion until `calcifer-agent logs <name>` shows the actual final result.

## Verification and recovery

```bash
calcifer-agent doctor
calcifer-agent permissions
calcifer-agent list
```

If a systemd goal disappears from the loaded-unit list after completion, its metadata and journal remain available through `status` and `logs`. If a tmux session is absent, it has exited or was stopped; start it again with `session`.
