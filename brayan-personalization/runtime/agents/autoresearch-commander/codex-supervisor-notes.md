# Codex Supervisor Notes

For temporary challenge sprints, prefer a project-local supervisor script plus a user systemd service:

- Project-local scripts/logs live under `/home/brayan/projects/<experiment>/`.
- `codex exec` is run non-interactively from the target git repository.
- A loop restarts Codex if it exits and uses `codex exec resume --last` to preserve the Codex session/compaction when possible.
- `systemd --user` keeps the supervisor alive with `Restart=always`.
- A `STOP` file gives Brayan a simple manual kill switch.

This is stronger than a single tmux session: tmux is useful for viewing interactive agents, but systemd + supervisor is the non-stop guarantee.
