# 2026-05 live-checkout rebase poisoning incident

## Symptom
Telegram bot stopped returning responses. Creating a new Telegram session did not help. Gateway logs showed:

```text
TypeError: ContextCompressor.__init__() got an unexpected keyword argument 'abort_on_summary_failure'
```

## Root cause
The daily Hermes upstream rebase CI cron mutated the live executable checkout at `/home/brayan/.hermes/hermes-agent` while `hermes-gateway.service` was running. The rebase failed in `gateway/run.py`, leaving conflict markers in live source. The gateway process then had mixed old/new Python module state: a newer `agent_init.py` call site passed `abort_on_summary_failure`, while the running process still held an older in-memory `ContextCompressor.__init__` signature.

A Telegram `/new` session could not help because the failure happened during agent initialization in process/module state, before conversation state mattered.

## Diagnostic pattern
1. Check gateway logs for the surface error.
2. Inspect live checkout git state before restarting:
   - branch/status
   - rebase/merge state
   - conflict markers in gateway/agent files
3. Verify Python compile of touched gateway/agent files before restart.
4. Compare on-disk constructor signatures and call sites when an unexpected-keyword TypeError suggests mixed versions.
5. If live checkout has conflict markers, do not restart gateway yet.

## Durable fix applied
- Resolved `gateway/run.py` conflict preserving both:
  - upstream Telegram topic/session recovery behavior
  - Brayan's Anything Inbox capture isolation/new-session behavior
- Completed the rebase onto upstream.
- Rewrote the daily rebase CI script to run rebases/tests in isolated worktree:
  `/home/brayan/.hermes/worktrees/hermes-upstream-rebase-ci`
- Future conflicts should remain in that worktree instead of poisoning the live gateway checkout.
- Fixed linked-worktree operation detection with `git rev-parse --git-path` because linked worktrees have `.git` as a file, not a directory.
- Used guarded finalizer for verified push.

## Verification checklist used
- Compile relevant gateway/agent/scripts.
- Focused notes-intake/wake-gate tests.
- Broader cron/tooling tests.
- `hermes config check`.
- Direct `AIAgent` initialization smoke test.
- Restart gateway only after clean compile/status.
- Check recent gateway logs for absence of `TypeError`, `ContextCompressor`, `Traceback`, and `ERROR`.
- CLI smoke test returned exactly `OK`.

## Reusable lesson
For any self-updating long-running Python service, never run rebases or tests in the live executable checkout while the service is running. Use an isolated worktree/staging clone, verify there, then fast-forward or deploy atomically. If a running process reports mismatched constructor/call-site errors after source changes, suspect mixed in-memory/on-disk module state before blaming session data.