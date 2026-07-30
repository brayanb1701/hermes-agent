# Daily review approval-sensitive probe — 2026-07-30

Context: unattended daily review cron over `~/personal_vault` needed fresh evidence for bakeoff status, Hugging Face role availability, cwd-marker fallback state, and portfolio no-buy safety.

## Useful pattern

When an unattended cron run needs several independent evidence checks, keep them as simple approval-friendly tool calls instead of a bundled arbitrary script:

- Use `read_file` for the target daily note and key artifacts such as `RUN_LOG.md`, `RESULT.md`, and `USER_FEEDBACK.md`.
- Use `search_files` for inbox contents, daily-note discovery, closeout/reopen handoff files, and post-write verification matches.
- Use small `terminal` commands for live evidence:
  - `stat -c '%n|%y|%s' <paths...>` for mtime/size checks.
  - `codex --version` for CLI readiness.
  - `git -C <repo> status --short --branch`, `rev-parse`, `ls-remote`, and `rev-list --left-right --count` for upstream/fallback state.
  - `wc -l <csvs...>` for header-only safety checks.
  - `curl ... | jq '{...}'` for a bounded JSON API probe when the output is summarized immediately and not executed.

## Pitfall avoided

Do not bundle routine evidence collection into `execute_code`, Python heredocs, or shell heredoc scripts during cron runs. Approval-sensitive cron contexts may pause those calls waiting for user approval, which defeats unattended delivery. If a richer verifier is truly needed, follow the main skill's `/tmp/hermes-verify-*` written-file pattern.

## Daily-review-specific recovery

For a daily review note, after writing:

1. Reread the daily note.
2. Search the note for the key signal(s), blocker(s), and recommended next action.
3. Only report the concise briefing after those checks confirm the note contains the intended evidence and recommendation.
