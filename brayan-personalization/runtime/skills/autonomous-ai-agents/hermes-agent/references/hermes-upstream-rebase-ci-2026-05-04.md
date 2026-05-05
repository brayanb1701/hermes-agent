# Hermes upstream rebase CI exception: DNS fetch + stale cron test

Session date: 2026-05-04.

## What happened

The `hermes-upstream-rebase-ci` pre-run script woke the exception agent at `stage: fetch_upstream`:

```text
ssh: Could not resolve hostname github.com: Temporary failure in name resolution
fatal: Could not read from remote repository.
```

Current git state was clean on `brayan/personal-hermes-customizations`, with no rebase in progress. A later `getent hosts github.com` and `git fetch upstream main --quiet` succeeded, confirming transient DNS/network rather than credentials/remotes.

After rerunning the pre-run automation, fetch/rebase succeeded but verification failed in:

```text
tests/cron/test_cron_script.py::TestBuildJobPromptWithScript::test_script_empty_output_noted
AttributeError: 'NoneType' object has no attribute 'lower'
```

## Root cause

Upstream commit `54cd633366 fix(cron): skip AI call when script produces no output` changed cron behavior: for a successful script with empty output, `_build_job_prompt()` returns `None` so `run_job()` can skip the AI call silently. The older test still expected a prompt containing `no output`.

## Correct fix pattern

- Use `git blame` / upstream commit context before changing behavior.
- Do **not** revert the scheduler optimization.
- Update the stale test expectation to assert `prompt is None`, e.g. rename `test_script_empty_output_noted` to `test_script_empty_output_skips_prompt`.
- Run focused verification and finalizer, then push only `origin/brayan/personal-hermes-customizations`.

## Verification used

```bash
/home/brayan/.hermes/hermes-agent/venv/bin/python -m py_compile \
  ~/.hermes/scripts/hermes_upstream_rebase_ci.py \
  /home/brayan/.hermes/hermes-agent/scripts/sync-brayan-personalization.py \
  /home/brayan/.hermes/hermes-agent/scripts/apply-brayan-personalization.py \
  /home/brayan/.hermes/skills/automation-agents/hermes-upstream-rebase-ci-agent/scripts/finalize_rebase_push.py
/home/brayan/.hermes/hermes-agent/venv/bin/python -m pytest \
  tests/gateway/test_notes_intake_pipeline.py \
  tests/plugins/test_notes_preprocessor_intake.py \
  tests/cron/test_cron_script.py::TestScriptWakeGate \
  -q -o 'addopts='
/home/brayan/.hermes/hermes-agent/venv/bin/python -m pytest \
  tests/cron/test_cron_script.py \
  tests/tools/test_cronjob_tools.py \
  tests/hermes_cli/test_cron.py \
  -q -o 'addopts='
/home/brayan/.local/bin/hermes config check
/home/brayan/.hermes/hermes-agent/venv/bin/python \
  /home/brayan/.hermes/skills/automation-agents/hermes-upstream-rebase-ci-agent/scripts/finalize_rebase_push.py \
  --apply
```

## Pitfall

If the finalizer succeeds and you rerun `~/.hermes/scripts/hermes_upstream_rebase_ci.py` to validate end-to-end, the sync step may create a timestamp-only personalization snapshot commit (`cron/jobs.json updated_at`, `manifest.json generated_at`) and push normally. Treat this as acceptable end-to-end verification if tests pass and final output is `wakeAgent: false`.
