# Terminal cwd marker poisoning (`FileNotFoundError: '%s'`)

## Symptom

Hermes terminal calls in one live session start failing repeatedly with:

```text
Command execution failed: FileNotFoundError: [Errno 2] No such file or directory: '%s'
```

Passing a valid `workdir` may not help, because the local terminal backend calls `subprocess.Popen(..., cwd=self.cwd)` before the wrapper can `cd` to the requested workdir.

## Root cause pattern

The local terminal backend keeps a per-session `LocalEnvironment.cwd` and updates it from Hermes internal cwd markers printed by the command wrapper:

```text
__HERMES_CWD_<session>__<cwd>__HERMES_CWD_<session>__
```

If command output leaks the wrapper command line itself, it may include the literal format string marker:

```text
__HERMES_CWD_<session>__%s__HERMES_CWD_<session>__
```

This can happen through process listings such as `ps`, `pgrep -af`, `systemctl status`, or journal output while the wrapped shell is still running. If the user command then kills or terminates the wrapper before the real final cwd marker is emitted, marker parsing can interpret the leaked `%s` marker as the cwd. The environment then stores `self.cwd = '%s'`, and subsequent terminal calls fail before command execution.

A common trigger is broad cleanup logic that matches its own terminal wrapper, for example `pgrep -f '<project-path>|<service-name>' | xargs kill`, because the command line contains the same strings it is searching for.

## Minimal reproduction idea

Use an isolated `LocalEnvironment`, print a fake leaked cwd marker containing `%s`, then terminate the shell before the wrapper emits the real marker. The next execute should not inherit `%s` as cwd after a fix.

```python
from tools.environments.local import LocalEnvironment

env = LocalEnvironment(cwd='/home/brayan', timeout=10)
marker = env._cwd_marker
literal = f"fake proc with {marker}%s{marker} here"
cmd = "printf '%s\\n' " + repr(literal) + "; kill -TERM $$"
res = env.execute(cmd, timeout=10)
assert env.cwd != '%s'
```

Before the fix, a follow-up `env.execute('pwd')` can raise `FileNotFoundError: '%s'`.

## Diagnostic workflow

1. Search session transcripts for the exact error:
   ```bash
   grep -R "FileNotFoundError: \[Errno 2\] No such file or directory: '%s'" ~/.hermes/sessions ~/.hermes/logs
   ```
2. Inspect the preceding terminal command. Look for:
   - `pgrep -f`, `pkill -f`, `ps -ef`, `systemctl status`, `journalctl`
   - broad regexes containing the project path, service name, or script name
   - commands that kill matching PIDs and might include their own shell/wrapper
3. Confirm whether only one active session is poisoned. A fresh Hermes session usually gets a new terminal environment and may work normally.
4. If debugging live, avoid further terminal calls in the poisoned session; use a fresh session or `execute_code` with direct Python `subprocess.run(..., executable='/bin/bash')` only for urgent verification.

## Corrective design

Preferred framework hardening:

- For `LocalEnvironment._update_cwd`, prefer the local cwd file and do not parse stdout markers when that file was read successfully.
- Make marker parsing strict: only accept marker-only lines emitted by the wrapper near the end of output, not markers embedded inside arbitrary process-list output.
- In `terminal_tool`, if `env.execute()` raises `FileNotFoundError` for the environment cwd, evict/recreate that active environment once before retrying.
- Add regression tests for leaked marker + killed shell.

## Agent behavior pitfall

When stopping processes, do not use broad `pgrep -f` / `pkill -f` patterns that can match the current terminal wrapper. Prefer supervised stops (`systemctl stop ...`) and explicit filtering that excludes the current PID, parent PID, and process group.