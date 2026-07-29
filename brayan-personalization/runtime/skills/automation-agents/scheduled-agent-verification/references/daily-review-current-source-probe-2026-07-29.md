# Daily review current-source probe — 2026-07-29

Session pattern worth reusing for unattended cron runs that need fresh external/current evidence without interactive approval.

## Context

The daily review needed to confirm whether Hugging Face Workable roles were still published. General web search was not available in the run, so the agent used the direct Workable API as the current source instead of relying on stale vault/session notes.

## Approval-friendly pattern

1. Fetch the current-source API response into a temporary file rather than piping it into an interpreter:

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: Mozilla/5.0' \
  -H 'Origin: https://apply.workable.com' \
  -H 'Referer: https://apply.workable.com/huggingface/' \
  --data '{"query":"","location":[],"department":[]}' \
  -o /tmp/hermes-hf-workable-jobs.json \
  -w 'http_code=%{http_code} size=%{size_download}\n' \
  https://apply.workable.com/api/v3/accounts/huggingface/jobs
```

2. Inspect the saved file with read-only tools (`read_file`, `search_files`) or with a small local parser such as `jq`:

```bash
jq -r '.total as $t | "total \($t)", (.results[] | select(.shortcode=="19A136F8E2" or .shortcode=="81B46579FE" or .shortcode=="F8427A442D" or .shortcode=="CB1DEFE6CE" or (.title|test("Open-Source|Machine Learning Engineer|Python"))) | "\(.shortcode) | \(.title) | \(.state) | \(.location.countryCode)" )' /tmp/hermes-hf-workable-jobs.json
```

3. Summarize only the evidence needed by the scheduled note/report: HTTP status, total count, matching IDs/titles/states, and date of check.
4. Clean up the temp file with the simplest allowed command, preferably `unlink /tmp/hermes-...`. If cleanup is blocked by the cron approval policy, report the concrete temp path only when it matters; do not let cleanup failure contaminate the daily priority message.

## Pitfalls avoided

- Avoid `execute_code` or inline Python heredocs in approval-sensitive cron contexts when simple tool calls/shell commands suffice.
- Avoid `curl | python`, `curl | bash`, or similar direct network-to-interpreter pipelines in unattended runs.
- Do not harden transient web/search credential state into a durable claim that a tool or source is broken; use direct-source evidence when accessible and otherwise label the evidence unavailable for that run.
