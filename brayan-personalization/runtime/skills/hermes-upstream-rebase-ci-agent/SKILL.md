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
- Script: `~/.hermes/scripts/hermes_upstream_rebase_ci.py`
- Cron job: `hermes-upstream-rebase-ci`, scheduled after morning startup (`30 9 * * *` as of 2026-04-30), delivery `local`, wake-gated by the script.

## Rules
1. First inspect the script JSON context and current git state.
2. Follow systematic debugging: identify the exact failure stage before fixing anything.
3. Preserve Brayan's source customizations. Do not run `git reset --hard upstream/main` unless there is a deliberate reason and the customization commit is safely recoverable.
4. Before changing Hermes base code, ask whether the improvement/fix can be done via plugin, config, skill, script, or vault workflow. Prefer those unless base-code change is genuinely required.
5. Resolve rebase conflicts or test failures if present.
6. Run focused verification from the script/doc.
7. If verification passes and branch is healthy, push only the personalization branch with `git push --force-with-lease origin HEAD:brayan/personal-hermes-customizations`. Never push personalization to `origin/main`.
8. Prefer programmatic recovery before manual edits: inspect the script output, let the script use `git rerere`/`rerere.autoupdate` and `GIT_EDITOR=true git rebase --continue` when conflicts have already been resolved, and only manually resolve genuinely new conflicts or failing tests.
9. If a conflict is manually resolved, make the resolution durable: keep repo-local `rerere.enabled=true` and `rerere.autoupdate=true`, continue the rebase, run verification, and update this skill/script/docs if the conflict suggests a reusable rule.
10. After a manual conflict resolution, explicitly push the rebased personalization branch. Be aware that `git push --force-with-lease ...` may be blocked by Hermes terminal approval in autonomous cron sessions because no human is present. If the approval layer blocks the push, report the exact blocked command and leave the branch state clearly documented; do not falsely report the remote as updated.
11. Update the workflow doc or `_meta/log.md` only for meaningful workflow changes, conflict resolution notes, or persistent lessons.
12. Final response should be concise: failure stage, fix, tests, current HEAD, push status, and manual action needed.

## Verification commands
Use the repo venv and clear repo-level pytest addopts where needed:
```bash
/home/brayan/.hermes/hermes-agent/venv/bin/python -m py_compile ~/.hermes/scripts/hermes_upstream_rebase_ci.py /home/brayan/.hermes/hermes-agent/scripts/sync-brayan-personalization.py /home/brayan/.hermes/hermes-agent/scripts/apply-brayan-personalization.py
/home/brayan/.hermes/hermes-agent/venv/bin/python -m pytest tests/gateway/test_notes_intake_pipeline.py tests/plugins/test_notes_preprocessor_intake.py tests/cron/test_cron_script.py::TestScriptWakeGate -q -o 'addopts='
/home/brayan/.hermes/hermes-agent/venv/bin/python -m pytest tests/cron/test_cron_script.py tests/tools/test_cronjob_tools.py tests/hermes_cli/test_cron.py -q -o 'addopts='
/home/brayan/.local/bin/hermes config check
```

Do not schedule or modify cron jobs from this run.
