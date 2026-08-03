# Daily review approval-sensitive probe — 2026-08-03

Concrete unattended daily-review evidence pattern.

## Context

A scheduled `daily-review-agent` run needed to verify vault state, bakeoff artifacts, Codex/Superpowers readiness, Hermes upstream branch state, and Hugging Face Workable current-source state before writing `daily/2026-08-03.md`.

## What worked

- Use required `read_file` / `search_files` calls for vault dashboards, pending decisions, daily notes, inbox files, and handoff-file discovery.
- Use simple read-only shell probes for live workspace evidence:
  - `stat -c '%n|%y|%s' <files...>` for artifact mtimes/sizes.
  - `codex --version`, `codex features list`, `codex plugin list` for preflight evidence.
  - `git status --short --branch`, `git rev-parse`, `git rev-list --left-right --count`, and `git ls-remote` for branch/remote state.
- For Workable/current-source JSON, fetch first and parse second:
  - `curl -sS ... -o /tmp/hermes-<task>.json -w 'http=%{http_code} bytes=%{size_download}\n'`
  - `jq -r '...' /tmp/hermes-<task>.json`
- Verify the changed daily note by rereading it and searching for the key signals/recommended action.

## Approval-sensitive patterns to avoid

- Inline Python heredocs (`python3 - <<'PY'`) and `python -c` can request approval in no-user cron contexts even for read-only probing.
- `execute_code` is unsuitable for unattended cron when arbitrary Python/subprocess execution requires user approval.
- Do not pipe untrusted network output directly into interpreters (`curl | python ...`). Fetch to a temp file, then inspect/parse the saved response.
- Avoid truncating noisy Rust/CLI output with `| head` in verification commands; some CLIs print broken-pipe panic noise when stdout closes early. Prefer the full command and let Hermes output limits/truncation handle size, or parse saved output with a non-closing reader.

## Daily-note evidence checklist

A good daily review note should explicitly record:

- inbox state
- closeout/reopen handoff search results
- actual stale/run artifact evidence, including mtimes when the pressure is about non-progress
- current-source API result when live opportunity pressure is mentioned
- fallback project/workspace state when recommending a fallback implementation lane
- one concise binary recommended next action
