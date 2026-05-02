---
name: hermes-upstream-rebase-ci-agent
description: Stable behavior for Darwin's daily Hermes upstream rebase CI exception handler.
version: 1.0.0
author: Darwin
license: MIT
---

# Hermes Upstream Rebase CI Agent

Use this when the daily `hermes-upstream-rebase-ci` cron wakes because the pre-run script emitted `wakeAgent: true`.

## Context
- Repository: `/home/brayan/.hermes/hermes-agent`
- Target branch: `brayan/personal-hermes-customizations`
- Fork origin: `git@github.com:brayanb1701/hermes-agent.git`
- Official upstream: `git@github.com:NousResearch/hermes-agent.git`
- Workflow doc: `~/personal_vault/_meta/workflows/hermes/hermes-fork-update-workflow.md`
- Pre-run wake-gate script: `~/.hermes/scripts/hermes_upstream_rebase_ci.py`
  - The scheduler runs this before the agent is created.
  - If it emits `wakeAgent: false`, no LLM agent runs.
  - If it emits `wakeAgent: true` or errors, its JSON/stdout is injected into the cron prompt for diagnosis.
  - Do not rerun it casually from the exception agent; inspect its injected output/current logs first. Rerun only when deliberately re-testing the whole pre-run automation after repairs.
- Cron job: `hermes-upstream-rebase-ci`, scheduled after morning startup (`30 9 * * *` as of 2026-04-30), delivery `local`, wake-gated by the script.

## Rules
1. First inspect the script JSON context and current git state.
2. Follow systematic debugging: identify the exact failure stage before fixing anything.
3. Preserve Brayan's source customizations. Do not run `git reset --hard upstream/main` unless there is a deliberate reason and the customization commit is safely recoverable.
4. Before changing Hermes base code, ask whether the improvement/fix can be done via plugin, config, skill, script, or vault workflow. Prefer those unless base-code change is genuinely required.
5. Resolve rebase conflicts or test failures if present.
6. Run focused verification from the script/doc.
7. If verification passes and branch is healthy, push only the personalization branch. For normal no-conflict script runs, `~/.hermes/scripts/hermes_upstream_rebase_ci.py` may push directly. For exception-agent/manual-repair runs, do **not** run direct terminal `git push --force-with-lease ...`; use the skill-owned finalizer script below. Never push personalization to `origin/main`.
8. Prefer programmatic recovery before manual edits: inspect the script output, let the script use `git rerere`/`rerere.autoupdate` and `GIT_EDITOR=true git rebase --continue` when conflicts have already been resolved, and only manually resolve genuinely new conflicts or failing tests.
9. If a conflict is manually resolved, make the resolution durable: keep repo-local `rerere.enabled=true` and `rerere.autoupdate=true`, continue the rebase, run verification, and update this skill/script/docs if the conflict suggests a reusable rule.
10. After a manual conflict resolution, explicitly finalize the rebased personalization branch by running `scripts/finalize_rebase_push.py` from this skill with `--apply`. The finalizer is a narrow deterministic capability: hard-coded repo, branch, remotes, exact force-with-lease, clean-tree checks, tests, and JSON diagnostics. If it refuses or fails, report its `stage`, `message`, failed command output, and `next_action`; do not bypass it with a direct force push.
11. Update the workflow doc or `_meta/log.md` only for meaningful workflow changes, conflict resolution notes, or persistent lessons.
12. Final response should be concise: failure stage, fix, tests/finalizer stage, current HEAD, push status, and manual action needed.

## Finalizer script for exception-agent repairs

When this exception agent has repaired a failed rebase or otherwise needs to complete the final verified push, run the skill-owned finalizer instead of calling `git push --force-with-lease` directly from the terminal tool:

```bash
/home/brayan/.hermes/hermes-agent/venv/bin/python \
  /home/brayan/.hermes/skills/hermes-upstream-rebase-ci-agent/scripts/finalize_rebase_push.py \
  --apply
```

For diagnosis without pushing:

```bash
/home/brayan/.hermes/hermes-agent/venv/bin/python \
  /home/brayan/.hermes/skills/hermes-upstream-rebase-ci-agent/scripts/finalize_rebase_push.py
```

For full verification without pushing:

```bash
/home/brayan/.hermes/hermes-agent/venv/bin/python \
  /home/brayan/.hermes/skills/hermes-upstream-rebase-ci-agent/scripts/finalize_rebase_push.py \
  --check
```

The finalizer emits JSON designed for agent use. On failure, inspect and report:
- `stage`
- `message`
- `next_action`
- failed entries in `commands`
- `checks` / `failed_check` when present

Do not bypass finalizer refusals. The finalizer intentionally hard-codes repo, branch, remotes, clean-tree checks, upstream containment, verification commands, and exact `--force-with-lease=<ref>:<observed-origin-sha>` push semantics.

## Verification commands
Use the repo venv and clear repo-level pytest addopts where needed. These commands are for validating repairs or script/skill changes; they are not an instruction to rerun the pre-run script itself.
```bash
/home/brayan/.hermes/hermes-agent/venv/bin/python -m py_compile ~/.hermes/scripts/hermes_upstream_rebase_ci.py /home/brayan/.hermes/hermes-agent/scripts/sync-brayan-personalization.py /home/brayan/.hermes/hermes-agent/scripts/apply-brayan-personalization.py /home/brayan/.hermes/skills/hermes-upstream-rebase-ci-agent/scripts/finalize_rebase_push.py
/home/brayan/.hermes/hermes-agent/venv/bin/python -m pytest tests/gateway/test_notes_intake_pipeline.py tests/plugins/test_notes_preprocessor_intake.py tests/cron/test_cron_script.py::TestScriptWakeGate -q -o 'addopts='
/home/brayan/.hermes/hermes-agent/venv/bin/python -m pytest tests/cron/test_cron_script.py tests/tools/test_cronjob_tools.py tests/hermes_cli/test_cron.py -q -o 'addopts='
/home/brayan/.local/bin/hermes config check
```

Do not schedule or modify cron jobs from this run.
