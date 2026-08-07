# Daily Review Approval-Safe Workable Probe — 2026-08-07

## Context

During an unattended `daily-review-agent` cron run, the review needed fresh Hugging Face Workable evidence plus bakeoff artifact checks before writing `daily/2026-08-07.md`.

## What worked

- Use simple read/search/stat/git probes for local evidence.
- For Workable JSON, split network fetch from parsing:

```bash
curl -sS --max-time 30 -X POST 'https://apply.workable.com/api/v3/accounts/huggingface/jobs' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/plain, */*' \
  -H 'User-Agent: Mozilla/5.0 daily-review check' \
  --data '{"query":"","location":[],"department":[],"worktype":[],"remote":[]}' \
  -o /tmp/hf-workable-jobs-YYYY-MM-DD.json \
  -w 'HTTP %{http_code}\n'
```

Then parse with `jq`:

```bash
jq -r '.total as $t | "total \($t)", (.results[] | select(.title|test("Open-Source Machine Learning Engineer|Senior Python|Xet Storage";"i")) | "\(.shortcode) | \(.title) | \(.state)")' /tmp/hf-workable-jobs-YYYY-MM-DD.json
```

Observed evidence on 2026-08-07: HTTP 200, total 7 jobs, including `19A136F8E2` and `81B46579FE` Open-Source Machine Learning Engineer roles plus Senior Python/Open-Source Contributor and Xet Storage roles.

## Approval-sensitive pitfalls

- `execute_code` may be blocked in cron approval mode for arbitrary Python.
- Shell heredocs and `python -c` can be blocked even for local JSON parsing.
- `curl | python` is correctly treated as network-to-interpreter risk; avoid it.
- `read_file` can inspect a saved JSON file, but one-line JSON may be truncated visually; use `jq` for concise extraction.
- Direct `rm -f /tmp/...` cleanup may be approval-blocked. Prefer scheduled-agent-verification's self-cleaning temp-script pattern when cleanup evidence matters; otherwise report any leftover path if it cannot be removed.

## Reusable lesson

For unattended scheduled agents, use a two-step evidence pattern: fetch to an OS-safe temp file, inspect/parse with read-only tools (`jq`, `read_file`, `search_files`), and avoid arbitrary inline interpreters unless the cron profile explicitly approves them.
